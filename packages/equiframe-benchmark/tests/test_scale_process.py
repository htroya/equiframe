"""Real bounded child processes; these are conformance tests, not scale claims."""

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from equiframe_benchmark import scale_process
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.scale_process import ProcessObservation, supervise

MIB = 1024**2


def run_child(directory, source, **overrides):
    pytest.importorskip("psutil")
    options = {
        "timeout_seconds": 5.0,
        "rss_budget_bytes": 256 * MIB,
        "disk_budget_bytes": 16 * MIB,
        "sample_interval_seconds": 0.01,
    }
    options.update(overrides)
    return supervise([sys.executable, "-c", source], directory=directory, **options)


def assert_reaped(observation):
    assert observation.cleanup_reaped
    assert observation.pid is not None
    assert observation.exit_code is not None
    if os.name == "posix":
        with pytest.raises(ChildProcessError):
            os.waitpid(observation.pid, os.WNOHANG)


def test_normal_exit_logs_local_temporary_files_and_observed_resources(tmp_path):
    observed = run_child(
        tmp_path,
        "import os, sys, tempfile, time; "
        "from pathlib import Path; "
        "print(os.environ['SUPERVISOR_TEST']); print('diagnostic', file=sys.stderr); "
        "Path('temp-location').write_text(tempfile.gettempdir()); "
        "Path('data').write_bytes(b'x' * 65536); Path('data').read_bytes(); "
        "time.sleep(0.15)",
        env={"SUPERVISOR_TEST": "override", "TMPDIR": "/invalid-outside-directory"},
    )
    assert_reaped(observed)
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    assert (tmp_path / "stdout.log").read_text() == "override\n"
    assert (tmp_path / "stderr.log").read_text() == "diagnostic\n"
    assert Path((tmp_path / "temp-location").read_text()) == tmp_path / "tmp"
    assert observed.sampled_rss_peak_bytes > 0
    assert observed.cpu_user_seconds >= 0
    assert observed.cpu_system_seconds >= 0
    assert observed.sample_count >= 3
    assert observed.max_sample_gap_seconds > 0
    assert observed.disk_apparent_peak_bytes >= 65536
    assert observed.resource_scope == "direct_child_excluding_descendants"
    assert observed.budget_method == "reactive_sampled_thresholds_not_hard_quotas"
    if sys.platform.startswith("linux"):
        assert observed.disk_allocated_peak_bytes > 0
        assert observed.io_read_bytes >= 0
        assert observed.io_write_bytes >= 0
        assert observed.io_read_chars >= 65536
        assert observed.io_write_chars >= 65536
    # An exit is never a declaration that the workload finalized its evidence.
    assert not (tmp_path / "completion.json").exists()
    assert "complete" not in observed.model_dump()
    save_document(observed, tmp_path / "observation.json")
    assert load_document(ProcessObservation, tmp_path / "observation.json") == observed


def test_nonzero_exit_preserved(tmp_path):
    observed = run_child(tmp_path, "import sys, time; time.sleep(0.05); sys.exit(7)")
    assert_reaped(observed)
    assert observed.termination_reason == "exited"
    assert observed.exit_code == 7


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal exit-code convention")
def test_sigkill_preserves_missing_finalization(tmp_path):
    observed = run_child(
        tmp_path,
        "import os, signal, time; from pathlib import Path; "
        "Path('partial.part').write_text('partial'); time.sleep(0.05); "
        "os.kill(os.getpid(), signal.SIGKILL); Path('completion.json').write_text('{}')",
    )
    assert_reaped(observed)
    assert observed.termination_reason == "exited"
    assert observed.exit_code == -signal.SIGKILL
    assert (tmp_path / "partial.part").exists()
    assert not (tmp_path / "completion.json").exists()


def assert_descendant_stopped(pid):
    psutil = pytest.importorskip("psutil")
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            if psutil.Process(pid).status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(0.01)
    # Retain a bounded cleanup even if a regression makes the assertion fail.
    with suppress(psutil.NoSuchProcess):
        psutil.Process(pid).kill()
    pytest.fail("observed descendant survived supervisor cleanup")


def test_descendant_workload_is_rejected_and_observed_child_stopped(tmp_path):
    observed = run_child(
        tmp_path,
        "import subprocess, sys, time; from pathlib import Path; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)']); "
        "Path('descendant.pid').write_text(str(child.pid)); time.sleep(2)",
    )
    assert_reaped(observed)
    assert observed.termination_reason == "unsupported_descendant"
    assert observed.observed_descendant_pids
    for pid in observed.observed_descendant_pids:
        assert_descendant_stopped(pid)


@pytest.mark.skipif(
    not scale_process._nonreaping_wait_available(),
    reason="safe group cleanup after leader exit requires POSIX waitid(WNOWAIT)",
)
def test_private_group_is_killed_after_leader_exits_between_samples(tmp_path, monkeypatch):
    def wait_for_leader_without_sampling(process, *args):
        deadline = time.monotonic() + 1.0
        while not scale_process._child_exited(process):
            if time.monotonic() >= deadline:
                raise AssertionError("bounded fixture leader did not exit")
            time.sleep(0.005)
        # The PID remains reserved until cleanup signals the private group.
        assert process.returncode is None
        return "exited"

    monkeypatch.setattr(scale_process, "_watch", wait_for_leader_without_sampling)
    observed = run_child(
        tmp_path,
        "import subprocess, sys; from pathlib import Path; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)']); "
        "Path('descendant.pid').write_text(str(child.pid))",
    )
    assert_reaped(observed)
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    # It escaped sampling, so the supervisor cannot claim it observed the child.
    assert observed.observed_descendant_pids == ()
    assert_descendant_stopped(int((tmp_path / "descendant.pid").read_text()))


@pytest.mark.skipif(os.name != "posix", reason="POSIX group-ID reuse safety")
def test_already_reaped_group_is_not_signaled_without_nonreaping_wait(tmp_path, monkeypatch):
    process = subprocess.Popen([sys.executable, "-c", "pass"], cwd=tmp_path, start_new_session=True)
    process.wait(timeout=5)
    monkeypatch.setattr(scale_process, "_nonreaping_wait_available", lambda: False)

    def forbidden_group_signal(*args):
        raise AssertionError("must not signal a potentially reused group ID")

    monkeypatch.setattr(scale_process.os, "killpg", forbidden_group_signal)
    measurements = scale_process._Measurements()
    assert scale_process._kill_and_wait(process, measurements)
    assert "post_exit_group_cleanup_unavailable_without_nonreaping_wait" in measurements.errors


def test_descendant_probe_failure_stops_the_running_child(tmp_path, monkeypatch):
    class Probe:
        def __init__(self, pid):
            self.pid = pid

        def children(self, recursive=False):
            raise PermissionError("synthetic descendant enumeration failure")

    monkeypatch.setattr(scale_process, "import_module", lambda name: SimpleNamespace(Process=Probe))
    observed = run_child(tmp_path, "import time; time.sleep(2)")
    assert_reaped(observed)
    assert observed.termination_reason == "monitoring_failed"
    assert "monitoring_failed:PermissionError" in observed.monitoring_errors


def test_external_timeout_kills_and_reaps_child(tmp_path):
    observed = run_child(
        tmp_path,
        "import time\nfrom pathlib import Path\n"
        "try:\n    time.sleep(30)\nfinally:\n    Path('finalized').write_text('yes')\n",
        timeout_seconds=0.15,
    )
    assert_reaped(observed)
    assert observed.termination_reason == "timeout"
    assert observed.exit_code != 0
    assert 0.1 <= observed.wall_seconds < 5.0
    assert not (tmp_path / "finalized").exists()
    assert observed.termination_scope == (
        "posix_process_group" if os.name == "posix" else "direct_child"
    )


def test_timeout_watchdog_is_independent_of_slow_directory_sampling(tmp_path, monkeypatch):
    original = scale_process._disk_usage
    calls = 0

    def delayed(directory):
        nonlocal calls
        calls += 1
        if calls == 2:
            time.sleep(0.4)
        return original(directory)

    monkeypatch.setattr(scale_process, "_disk_usage", delayed)
    observed = run_child(
        tmp_path,
        "import time; from pathlib import Path; time.sleep(0.25); "
        "Path('survived-deadline').write_text('yes'); time.sleep(3)",
        timeout_seconds=0.1,
    )
    assert_reaped(observed)
    assert observed.termination_reason == "timeout"
    assert not (tmp_path / "survived-deadline").exists()
    assert observed.max_sample_gap_seconds >= 0.35
    assert "sampling_gap_exceeded_twice_requested_interval" in observed.monitoring_errors


def test_rss_threshold_uses_bounded_allocation_and_is_reactive(tmp_path):
    observed = run_child(
        tmp_path,
        "import time; data = bytearray(24 * 1024**2); "
        "data[::4096] = b'x' * (len(data) // 4096); time.sleep(3)",
        rss_budget_bytes=20 * MIB,
    )
    assert_reaped(observed)
    assert observed.termination_reason == "rss_budget_exceeded"
    assert observed.sampled_rss_peak_bytes > 20 * MIB
    assert observed.exit_code != 0


@pytest.mark.parametrize("target", ["payload", "stdout"])
def test_disk_and_logs_threshold_use_bounded_one_mib_write(tmp_path, target):
    source = (
        "import os, time; from pathlib import Path; "
        + (
            "os.write(1, b'x' * 1024**2); "
            if target == "stdout"
            else "Path('payload').write_bytes(b'x' * 1024**2); "
        )
        + "time.sleep(3)"
    )
    observed = run_child(tmp_path, source, disk_budget_bytes=128 * 1024)
    assert_reaped(observed)
    assert observed.termination_reason == "disk_budget_exceeded"
    assert observed.disk_apparent_peak_bytes > 128 * 1024
    assert observed.exit_code != 0
    path = tmp_path / ("stdout.log" if target == "stdout" else "payload")
    assert 128 * 1024 < path.stat().st_size <= MIB


def test_preexisting_disk_budget_stops_before_launch(tmp_path):
    (tmp_path / "existing").write_bytes(b"x" * 65536)
    observed = run_child(tmp_path, "raise AssertionError('must not start')", disk_budget_bytes=1024)
    assert observed.termination_reason == "disk_budget_exceeded"
    assert observed.pid is None and observed.exit_code is None
    assert observed.cleanup_reaped
    assert observed.sampled_rss_peak_bytes is None


def test_missing_dependency_fails_closed_without_launch(tmp_path, monkeypatch):
    def missing(name):
        assert name == "psutil"
        raise ModuleNotFoundError("synthetic optional-dependency failure")

    monkeypatch.setattr(scale_process, "import_module", missing)
    observed = supervise(
        [sys.executable, "-c", "raise AssertionError('must not start')"],
        directory=tmp_path,
        timeout_seconds=1.0,
        rss_budget_bytes=MIB,
        disk_budget_bytes=MIB,
    )
    assert observed.termination_reason == "monitoring_failed"
    assert observed.pid is None and observed.exit_code is None
    assert observed.sampled_rss_peak_bytes is None and observed.cpu_user_seconds is None
    assert observed.sample_count == 0 and observed.max_sample_gap_seconds is None
    assert observed.monitoring_errors == ("resources_extra_unavailable:ModuleNotFoundError",)


def test_psutil_is_not_imported_when_loading_module(tmp_path):
    script = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'psutil': raise AssertionError('eager psutil import')\n"
        "sys.meta_path.insert(0, Block())\n"
        "import equiframe_benchmark.scale_process\n"
        "assert 'psutil' not in sys.modules\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, timeout=10, check=False
    )
    assert completed.returncode == 0, completed.stderr.decode()


def test_unavailable_executable_preserves_launch_failure(tmp_path):
    pytest.importorskip("psutil")
    observed = supervise(
        [str(tmp_path / "missing-executable")],
        directory=tmp_path,
        timeout_seconds=1.0,
        rss_budget_bytes=MIB,
        disk_budget_bytes=MIB,
    )
    assert observed.termination_reason == "launch_failed"
    assert observed.pid is None and observed.exit_code is None
    assert observed.cleanup_reaped
    assert "launch_failed:FileNotFoundError" in observed.monitoring_errors


def test_existing_logs_are_never_overwritten(tmp_path):
    (tmp_path / "stdout.log").write_text("retained evidence")
    observed = run_child(tmp_path, "print('replacement')")
    assert observed.termination_reason == "launch_failed"
    assert observed.pid is None
    assert (tmp_path / "stdout.log").read_text() == "retained evidence"


def test_directory_monitor_exception_always_kills_and_reaps(tmp_path, monkeypatch):
    original = scale_process._disk_usage
    calls = 0

    def fail_after_launch(directory):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("synthetic disk-monitor failure")
        return original(directory)

    monkeypatch.setattr(scale_process, "_disk_usage", fail_after_launch)
    observed = run_child(tmp_path, "import time; time.sleep(30)")
    assert_reaped(observed)
    assert observed.termination_reason == "monitoring_failed"
    assert observed.exit_code != 0
    assert "monitoring_failed:OSError" in observed.monitoring_errors
    assert "final_disk_sample_failed:OSError" in observed.monitoring_errors


def test_keyboard_interrupt_reaps_before_propagating(tmp_path, monkeypatch):
    original = scale_process._watch
    children = []

    def interrupt(process, *args):
        children.append(process)
        raise KeyboardInterrupt

    monkeypatch.setattr(scale_process, "_watch", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_child(tmp_path, "import time; time.sleep(30)")
    assert len(children) == 1
    assert children[0].returncode is not None
    monkeypatch.setattr(scale_process, "_watch", original)
    if os.name == "posix":
        with pytest.raises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)


def test_watchdog_start_failure_stops_and_reaps_child(tmp_path, monkeypatch):
    def fail_start(self):
        raise RuntimeError("synthetic watchdog thread failure")

    monkeypatch.setattr(scale_process._DeadlineGuard, "start", fail_start)
    observed = run_child(tmp_path, "import time; time.sleep(30)")
    assert_reaped(observed)
    assert observed.termination_reason == "monitoring_failed"
    assert "monitoring_failed:RuntimeError" in observed.monitoring_errors


def test_optional_io_counter_failure_preserves_partial_observation(tmp_path, monkeypatch):
    psutil = pytest.importorskip("psutil")

    class Probe:
        def __init__(self, pid):
            self.actual = psutil.Process(pid)

        def children(self, recursive=False):
            return self.actual.children(recursive=recursive)

        def memory_info(self):
            return self.actual.memory_info()

        def cpu_times(self):
            return self.actual.cpu_times()

        def io_counters(self):
            raise NotImplementedError("synthetic platform without I/O counters")

    monkeypatch.setattr(scale_process, "import_module", lambda name: SimpleNamespace(Process=Probe))
    observed = run_child(tmp_path, "import time; time.sleep(0.1)")
    assert_reaped(observed)
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    assert observed.sampled_rss_peak_bytes > 0
    assert observed.io_read_bytes is None and observed.io_write_bytes is None
    assert observed.io_read_chars is None and observed.io_write_chars is None
    assert "io_counters_unavailable:NotImplementedError" in observed.monitoring_errors


def test_io_missing_fields_remain_unknown_not_zero():
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            return SimpleNamespace(read_bytes=100, write_bytes=200)

    observed = scale_process._Measurements()
    assert observed.child(Probe(), SimpleNamespace(poll=lambda: None))
    assert observed.io_read_bytes == 100 and observed.io_write_bytes == 200
    assert observed.io_read_chars is None and observed.io_write_chars is None
    assert set(observed.errors) == {"io_read_chars_unavailable", "io_write_chars_unavailable"}


def test_rss_probe_error_fails_closed_for_running_child(tmp_path, monkeypatch):
    psutil = pytest.importorskip("psutil")

    class Probe:
        def __init__(self, pid):
            self.actual = psutil.Process(pid)

        def children(self, recursive=False):
            return self.actual.children(recursive=recursive)

        def memory_info(self):
            raise PermissionError("synthetic RSS access denial")

    monkeypatch.setattr(scale_process, "import_module", lambda name: SimpleNamespace(Process=Probe))
    observed = run_child(tmp_path, "import time; time.sleep(30)")
    assert_reaped(observed)
    assert observed.termination_reason == "monitoring_failed"
    assert observed.sampled_rss_peak_bytes is None
    assert "rss_monitoring_failed:PermissionError" in observed.monitoring_errors


@pytest.mark.skipif(os.name != "posix", reason="POSIX hard links and symlinks")
def test_disk_usage_deduplicates_inodes_and_does_not_follow_symlinks(tmp_path):
    directory = tmp_path / "owned"
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"x" * MIB)
    owned = directory / "owned"
    owned.write_bytes(b"x" * 1024)
    os.link(owned, directory / "hardlink")
    (directory / "symlink").symlink_to(outside)
    (directory / "cycle").symlink_to(directory, target_is_directory=True)
    apparent, allocated = scale_process._disk_usage(directory)
    expected = sum((directory / name).lstat().st_size for name in ("owned", "symlink", "cycle"))
    assert apparent == directory.stat().st_size + expected
    assert apparent < MIB
    assert allocated is not None and allocated > 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("timeout_seconds", 0.0),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", float("nan")),
        ("sample_interval_seconds", 0.0),
        ("sample_interval_seconds", True),
        ("rss_budget_bytes", 0),
        ("rss_budget_bytes", True),
        ("disk_budget_bytes", -1),
    ],
)
def test_invalid_limits_rejected_before_start(tmp_path, key, value):
    with pytest.raises(ValueError):
        run_child(tmp_path, "print('never')", **{key: value})
    assert not (tmp_path / "stdout.log").exists()


def test_observation_strict_model_rejects_false_exit_claim(tmp_path):
    observed = run_child(tmp_path, "pass")
    data = observed.model_dump()
    data["exit_code"] = None
    with pytest.raises(ValidationError, match="reaped child"):
        ProcessObservation.model_validate(data)
    data = observed.model_dump()
    data["wall_seconds"] = float("nan")
    with pytest.raises(ValidationError):
        ProcessObservation.model_validate(data)
