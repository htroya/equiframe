"""Real bounded child processes; these are conformance tests, not scale claims."""

import json
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
    return supervise([sys.executable, "-I", "-c", source], directory=directory, **options)


def assert_reaped(observation):
    assert observation.cleanup_reaped
    assert observation.pid is not None
    assert observation.exit_code is not None
    if os.name == "posix":
        with pytest.raises(ChildProcessError):
            os.waitpid(observation.pid, os.WNOHANG)


def complete_observation(platform):
    measurements = scale_process._Measurements(measurement_platform=platform)
    measurements.sampled_rss_peak_bytes = 1024
    measurements.cpu_user_seconds = 0.1
    measurements.cpu_system_seconds = 0.2
    measurements.disk_apparent_peak_bytes = 2048
    if platform != "windows":
        measurements.disk_allocated_peak_bytes = 4096
    if platform != "macos":
        measurements.io_read_bytes = 10
        measurements.io_write_bytes = 20
        measurements.io_counter_source = "psutil"
    if platform == "linux":
        measurements.io_read_chars = 30
        measurements.io_write_chars = 40
    measurements.sample_count = 2
    measurements.max_sample_gap_seconds = 0.01
    return measurements.observation(
        SimpleNamespace(pid=419, returncode=0),
        "exited",
        time.monotonic(),
        0.05,
        True,
    )


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
    assert observed.io_counter_source in ("psutil", "linux_proc_pid_io")
    assert (observed.io_counter_fallback_reason is not None) == (
        observed.io_counter_source == "linux_proc_pid_io"
    )
    assert observed.measurement_platform == scale_process.current_measurement_platform()
    assert len(observed.metric_coverage) == len(scale_process._MEASUREMENT_METRICS)
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


@pytest.mark.skipif(os.name != "nt", reason="Windows CPython venv redirector")
def test_windows_venv_redirector_runs_real_interpreter_as_owned_child(tmp_path):
    launcher = Path(sys.executable).resolve()
    base = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    if launcher == base or launcher.parent.name.casefold() != "scripts":
        pytest.skip("the test interpreter does not use a Windows venv redirector")
    source = (
        "import json, os, psutil, sys, time; from pathlib import Path; "
        "Path('identity.json').write_text(json.dumps({"
        "'pid': os.getpid(), 'executable': sys.executable, "
        "'base_executable': sys._base_executable, 'prefix': sys.prefix, "
        "'psutil_path': psutil.__file__, "
        "'launcher_variable': os.environ.get('__PYVENV_LAUNCHER__')})); "
        "time.sleep(0.15)"
    )
    observed = supervise(
        [sys.executable, "-I", "-c", source],
        directory=tmp_path,
        timeout_seconds=5.0,
        rss_budget_bytes=256 * MIB,
        disk_budget_bytes=16 * MIB,
        sample_interval_seconds=0.01,
    )
    identity = json.loads((tmp_path / "identity.json").read_text())
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    assert observed.pid == identity["pid"]
    assert observed.observed_descendant_pids == ()
    assert identity["executable"] == sys.executable
    assert Path(identity["executable"]).resolve() == launcher
    assert Path(identity["base_executable"]).resolve() == base
    assert Path(identity["prefix"]).resolve() == launcher.parent.parent
    assert Path(identity["psutil_path"]).resolve().is_relative_to(launcher.parent.parent)
    assert identity["launcher_variable"] is None


def test_windows_venv_redirect_bypass_does_not_rewrite_an_unbound_command(tmp_path):
    command = [str(tmp_path / "python.exe"), "-c", "pass"]
    environment = {"BOUND": "original"}
    prepared_command, prepared_environment = scale_process._windows_venv_base_launch(
        command, environment
    )
    assert prepared_command is command
    assert prepared_environment is environment
    assert environment == {"BOUND": "original"}


@pytest.mark.skipif(os.name != "nt", reason="Windows environment names are case-insensitive")
def test_windows_venv_redirect_bypass_replaces_all_launcher_variable_casings():
    if Path(sys.executable).resolve() == Path(sys._base_executable).resolve():
        pytest.skip("the test interpreter does not use a Windows venv redirector")
    command = [sys.executable, "-I", "-c", "pass"]
    environment = {
        "__PYVENV_LAUNCHER__": r"C:\bad-upper\python.exe",
        "__pyvenv_launcher__": r"C:\bad-lower\python.exe",
        "RETAINED": "yes",
    }
    prepared_command, prepared_environment = scale_process._windows_venv_base_launch(
        command, environment
    )
    assert prepared_command == [sys._base_executable, "-I", "-c", "pass"]
    launcher_keys = [key for key in prepared_environment if key.casefold() == "__pyvenv_launcher__"]
    assert launcher_keys == ["__PYVENV_LAUNCHER__"]
    assert prepared_environment[launcher_keys[0]] == sys.executable
    assert prepared_environment["RETAINED"] == "yes"
    assert environment["__pyvenv_launcher__"] == r"C:\bad-lower\python.exe"


def test_windows_venv_redirect_bypass_requires_isolated_mode():
    command = [sys.executable, "-c", "pass"]
    environment = {"BOUND": "original"}
    assert scale_process._windows_venv_base_launch(command, environment) == (
        command,
        environment,
    )


def test_descendant_cleanup_uses_captured_identity_without_pid_wait_or_reopen():
    calls = []

    class CapturedIdentity:
        pid = 419

        def kill(self):
            calls.append("kill")

        def is_running(self):
            calls.append("is_running")
            return False  # Includes the safe PID-reused outcome from psutil.

        def wait(self, timeout=None):
            raise AssertionError("a numeric PID wait is unsafe after possible reuse")

    measurements = scale_process._Measurements(descendants=[CapturedIdentity()])
    scale_process._kill_observed_descendants(measurements)
    assert calls == ["kill", "is_running"]
    assert measurements.errors == []


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


def assert_descendant_stopped(pid, created):
    psutil = pytest.importorskip("psutil")
    try:
        process = psutil.Process(pid)
        if process.create_time() != created:
            return
    except psutil.NoSuchProcess:
        return
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            if not process.is_running() or process.status() in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
            ):
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(0.01)
    # Retain a bounded identity-checked cleanup even if a regression makes the assertion fail.
    with suppress(psutil.NoSuchProcess):
        if process.create_time() == created and process.is_running():
            process.kill()
    pytest.fail("observed descendant survived supervisor cleanup")


def test_descendant_workload_is_rejected_and_observed_child_stopped(tmp_path, monkeypatch):
    identities = []
    cleanup = scale_process._kill_observed_descendants

    def capture_before_cleanup(measurements):
        # Detection can stop the worker before it writes a child-identity file.
        # Observe each owned OS identity before real cleanup, without postponing
        # detection or changing the supervisor's termination behavior.
        identities.extend((child.pid, child.create_time()) for child in measurements.descendants)
        cleanup(measurements)

    monkeypatch.setattr(scale_process, "_kill_observed_descendants", capture_before_cleanup)
    observed = run_child(
        tmp_path,
        "import os, subprocess, sys, time; from pathlib import Path; "
        "Path('worker.pid').write_text(str(os.getpid())); "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)']); "
        "time.sleep(2)",
        sample_interval_seconds=0.1,
    )
    assert_reaped(observed)
    assert observed.termination_reason == "unsupported_descendant"
    assert observed.pid == int((tmp_path / "worker.pid").read_text())
    assert observed.observed_descendant_pids
    assert identities
    assert {pid for pid, _ in identities} == set(observed.observed_descendant_pids)
    for identity in identities:
        assert_descendant_stopped(*identity)


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
        "import json, psutil, subprocess, sys; from pathlib import Path; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)']); "
        "Path('descendant.json').write_text(json.dumps("
        "[child.pid, psutil.Process(child.pid).create_time()]))",
    )
    assert_reaped(observed)
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    # It escaped sampling, so the supervisor cannot claim it observed the child.
    assert observed.observed_descendant_pids == ()
    assert_descendant_stopped(*json.loads((tmp_path / "descendant.json").read_text()))


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
    assert observed.monitoring_errors[0] == "resources_extra_unavailable:ModuleNotFoundError"
    assert not observed.resource_contract_complete
    assert all(
        item.state in ("measurement_failed", "unavailable_on_platform")
        for item in observed.metric_coverage
    )


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

    def unavailable_proc(pid):
        raise PermissionError("synthetic unavailable Linux /proc counter file")

    monkeypatch.setattr(scale_process, "import_module", lambda name: SimpleNamespace(Process=Probe))
    monkeypatch.setattr(scale_process, "_read_linux_proc_io", unavailable_proc)
    observed = run_child(tmp_path, "import time; time.sleep(0.1)")
    assert_reaped(observed)
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    assert observed.sampled_rss_peak_bytes > 0
    assert observed.io_read_bytes is None and observed.io_write_bytes is None
    assert observed.io_read_chars is None and observed.io_write_chars is None
    assert "io_counters_unavailable:NotImplementedError" in observed.monitoring_errors
    if sys.platform.startswith("linux"):
        assert "linux_proc_io_unavailable:PermissionError" in observed.monitoring_errors
    assert observed.io_counter_source == "unavailable"
    assert observed.io_counter_fallback_reason is None


def test_linux_proc_io_parses_only_kernel_cumulative_counters(tmp_path):
    path = tmp_path / "419" / "io"
    path.parent.mkdir()
    path.write_text(
        "rchar: 101\n"
        "wchar: 202\n"
        "syscr: 3\n"
        "syscw: 4\n"
        "read_bytes: 303\n"
        "write_bytes: 404\n"
        "cancelled_write_bytes: 9\n",
        encoding="ascii",
    )
    assert scale_process._read_linux_proc_io(419, proc_root=tmp_path) == {
        "read_bytes": 303,
        "write_bytes": 404,
        "read_chars": 101,
        "write_chars": 202,
    }


@pytest.mark.parametrize(
    "contents",
    [
        "rchar: 1\nwchar: 2\nread_bytes: 3\n",
        "rchar: 1\nrchar: 2\nwchar: 3\nread_bytes: 4\nwrite_bytes: 5\n",
        "rchar: -1\nwchar: 2\nread_bytes: 3\nwrite_bytes: 4\n",
    ],
)
def test_linux_proc_io_rejects_incomplete_duplicate_or_invalid_data(tmp_path, contents):
    path = tmp_path / "419" / "io"
    path.parent.mkdir()
    path.write_text(contents, encoding="ascii")
    with pytest.raises(ValueError):
        scale_process._read_linux_proc_io(419, proc_root=tmp_path)


def test_linux_proc_io_replaces_denied_psutil_counter_probe(monkeypatch):
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            raise PermissionError("synthetic psutil access denial")

    monkeypatch.setattr(scale_process.sys, "platform", "linux")
    monkeypatch.setattr(
        scale_process,
        "_read_linux_proc_io",
        lambda pid: {
            "read_bytes": 10,
            "write_bytes": 20,
            "read_chars": 30,
            "write_chars": 40,
        },
    )
    observed = scale_process._Measurements()
    process = SimpleNamespace(pid=419, poll=lambda: None)
    assert observed.child(Probe(), process)
    assert (
        observed.io_read_bytes,
        observed.io_write_bytes,
        observed.io_read_chars,
        observed.io_write_chars,
    ) == (10, 20, 30, 40)
    assert observed.io_counter_source == "linux_proc_pid_io"
    assert observed.io_counter_fallback_reason == "psutil_io_counters_unavailable:PermissionError"
    assert observed.errors == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux /proc process counters")
def test_linux_proc_io_fallback_observes_the_owned_live_child(tmp_path, monkeypatch):
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
            raise PermissionError("synthetic psutil access denial")

    monkeypatch.setattr(scale_process, "import_module", lambda name: SimpleNamespace(Process=Probe))
    observed = run_child(
        tmp_path,
        "import time; from pathlib import Path; "
        "Path('payload').write_bytes(b'x' * 4096); Path('payload').read_bytes(); "
        "time.sleep(0.1)",
    )
    assert_reaped(observed)
    assert observed.termination_reason == "exited" and observed.exit_code == 0
    assert observed.io_counter_source == "linux_proc_pid_io"
    assert observed.io_counter_fallback_reason == ("psutil_io_counters_unavailable:PermissionError")
    assert observed.io_read_bytes is not None and observed.io_write_bytes is not None
    assert observed.io_read_chars is not None and observed.io_write_chars is not None
    io_coverage = tuple(item for item in observed.metric_coverage if item.metric.startswith("io_"))
    assert tuple(item.metric for item in io_coverage) == (
        "io_read_bytes",
        "io_write_bytes",
        "io_read_chars",
        "io_write_chars",
    )
    assert all(
        (item.state, item.source, item.reason) == ("observed", "linux_proc_pid_io", None)
        for item in io_coverage
    )
    # A denied probe before exit is observed must remain a partial measurement,
    # even when earlier native I/O counters were available.
    io_failures = tuple(
        error for error in observed.monitoring_errors if error.startswith(("io_", "linux_proc_io_"))
    )
    assert io_failures in (
        (),
        ("io_counters_unavailable:PermissionError", "linux_proc_io_unavailable:PermissionError"),
    )
    if io_failures:
        assert observed.resource_contract_complete is False


def test_failed_linux_proc_io_fallback_remains_explicitly_incomplete(monkeypatch):
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            raise PermissionError("synthetic psutil access denial")

    def denied(pid):
        raise PermissionError("synthetic /proc access denial")

    monkeypatch.setattr(scale_process.sys, "platform", "linux")
    monkeypatch.setattr(scale_process, "_read_linux_proc_io", denied)
    observed = scale_process._Measurements()
    assert observed.child(Probe(), SimpleNamespace(pid=419, poll=lambda: None))
    assert (
        observed.io_read_bytes,
        observed.io_write_bytes,
        observed.io_read_chars,
        observed.io_write_chars,
    ) == (None, None, None, None)
    assert observed.io_counter_source == "unavailable"
    assert observed.io_counter_fallback_reason is None
    assert set(observed.errors) == {
        "io_counters_unavailable:PermissionError",
        "linux_proc_io_unavailable:PermissionError",
    }


@pytest.mark.parametrize("source", ["psutil", "linux_proc_pid_io"])
@pytest.mark.parametrize("failure", [PermissionError, FileNotFoundError, ProcessLookupError])
def test_linux_io_exit_race_preserves_complete_live_samples(monkeypatch, source, failure):
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            raise PermissionError("synthetic psutil denial")

    def disappeared(pid):
        raise failure("synthetic unavailable exited process")

    monkeypatch.setattr(scale_process, "_read_linux_proc_io", disappeared)
    monkeypatch.setattr(scale_process, "_child_exited", lambda process: True)
    observed = scale_process._Measurements(measurement_platform="linux")
    observed._io({"read_bytes": 10, "write_bytes": 20, "read_chars": 30, "write_chars": 40}, source)
    if source == "linux_proc_pid_io":
        observed.io_counter_fallback_reason = "psutil_io_counters_unavailable:PermissionError"
    assert observed.child(Probe(), SimpleNamespace(pid=419))
    assert (
        observed.io_read_bytes,
        observed.io_write_bytes,
        observed.io_read_chars,
        observed.io_write_chars,
    ) == (10, 20, 30, 40)
    assert observed.io_counter_source == source
    assert observed.errors == []


@pytest.mark.parametrize(
    "case", ["alive", "no_prior_sample", "incomplete_prior_sample", "invalid_counters"]
)
def test_linux_io_exit_race_cannot_hide_unavailable_or_invalid_live_measurement(monkeypatch, case):
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            raise PermissionError("synthetic psutil denial")

    def denied(pid):
        if case == "invalid_counters":
            raise ValueError("synthetic malformed counters")
        raise PermissionError("synthetic /proc denial")

    monkeypatch.setattr(scale_process, "_read_linux_proc_io", denied)
    monkeypatch.setattr(scale_process, "_child_exited", lambda process: case != "alive")
    observed = scale_process._Measurements(measurement_platform="linux")
    if case != "no_prior_sample":
        observed._io(
            {"read_bytes": 10, "write_bytes": 20, "read_chars": 30, "write_chars": 40},
            "linux_proc_pid_io",
        )
    if case == "incomplete_prior_sample":
        observed.io_write_chars = None
    assert observed.child(Probe(), SimpleNamespace(pid=419))
    assert "io_counters_unavailable:PermissionError" in observed.errors
    expected = "ValueError" if case == "invalid_counters" else "PermissionError"
    assert "linux_proc_io_unavailable:" + expected in observed.errors


def test_windows_native_io_character_absence_is_not_zero_or_failure():
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            return SimpleNamespace(read_bytes=100, write_bytes=200)

    observed = scale_process._Measurements(measurement_platform="windows")
    assert observed.child(Probe(), SimpleNamespace(poll=lambda: None))
    assert observed.io_read_bytes == 100 and observed.io_write_bytes == 200
    assert observed.io_read_chars is None and observed.io_write_chars is None
    assert observed.io_counter_source == "psutil"
    assert observed.errors == []


def test_macos_documented_io_absence_does_not_call_an_unsupported_probe():
    class Probe:
        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.2)

        def io_counters(self):
            raise AssertionError("macOS contract must not call an unsupported psutil API")

    observed = scale_process._Measurements(measurement_platform="macos")
    assert observed.child(Probe(), SimpleNamespace(poll=lambda: None))
    assert observed.io_counter_source == "unavailable"
    assert observed.io_read_bytes is None and observed.io_write_bytes is None
    assert observed.io_read_chars is None and observed.io_write_chars is None
    assert observed.errors == []


def test_missing_allocated_blocks_are_expected_only_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(scale_process, "_disk_usage", lambda directory: (10, None))
    windows = scale_process._Measurements(measurement_platform="windows")
    windows.disk(tmp_path)
    assert windows.disk_apparent_peak_bytes == 10
    assert windows.disk_allocated_peak_bytes is None
    assert windows.errors == []

    for platform in ("linux", "macos"):
        measured = scale_process._Measurements(measurement_platform=platform)
        measured.disk(tmp_path)
        assert measured.disk_allocated_peak_bytes is None
        assert measured.errors == ["disk_allocated_bytes_unavailable"]


@pytest.mark.parametrize("platform", ["linux", "windows", "macos"])
def test_platform_contract_accepts_only_its_documented_complete_coverage(platform):
    observed = complete_observation(platform)
    assert observed.resource_contract_complete
    coverage = {item.metric: item for item in observed.metric_coverage}
    assert tuple(coverage) == scale_process._MEASUREMENT_METRICS
    for metric, reason in scale_process._PLATFORM_UNAVAILABLE[platform].items():
        assert getattr(observed, metric) is None
        assert coverage[metric].state == "unavailable_on_platform"
        assert coverage[metric].source is None
        assert coverage[metric].reason == reason
    for metric in set(scale_process._MEASUREMENT_METRICS) - set(
        scale_process._PLATFORM_UNAVAILABLE[platform]
    ):
        assert getattr(observed, metric) is not None
        assert coverage[metric].state == "observed"
        assert coverage[metric].source is not None
        assert coverage[metric].reason is None


def test_supported_metric_failure_cannot_be_closed_as_platform_unavailable():
    observed = complete_observation("windows")
    failed = observed.model_dump()
    failed["io_read_bytes"] = None
    item = next(entry for entry in failed["metric_coverage"] if entry["metric"] == "io_read_bytes")
    item.update(
        state="unavailable_on_platform",
        source=None,
        reason="windows_psutil_process_io_read_chars_not_exposed",
    )
    with pytest.raises(ValidationError, match="supported platform metric"):
        ProcessObservation.model_validate(failed)


def test_platform_absence_requires_the_exact_reason_and_never_a_value():
    observed = complete_observation("windows")
    wrong_reason = observed.model_dump()
    item = next(
        entry for entry in wrong_reason["metric_coverage"] if entry["metric"] == "io_read_chars"
    )
    item["reason"] = "generic_unavailable"
    with pytest.raises(ValidationError, match="exact reason"):
        ProcessObservation.model_validate(wrong_reason)

    invented = observed.model_dump()
    invented["io_read_chars"] = 0
    with pytest.raises(ValidationError, match="exact reason"):
        ProcessObservation.model_validate(invented)


def test_linux_contract_requires_all_four_io_semantics():
    observed = complete_observation("linux")
    data = observed.model_dump()
    data["io_read_chars"] = None
    data["monitoring_errors"] = ("io_read_chars_measurement_unavailable",)
    item = next(entry for entry in data["metric_coverage"] if entry["metric"] == "io_read_chars")
    item.update(
        state="measurement_failed",
        source=None,
        reason="io_read_chars_measurement_unavailable",
    )
    partial = ProcessObservation.model_validate(data)
    assert not partial.resource_contract_complete


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


def test_rss_exit_race_is_benign_only_after_an_actual_observation():
    class Probe:
        def memory_info(self):
            raise RuntimeError("synthetic process already exited")

    process = SimpleNamespace(pid=419, returncode=0, poll=lambda: 0)
    observed = scale_process._Measurements()
    observed.sampled_rss_peak_bytes = 1024
    assert observed.child(Probe(), process)
    assert observed.errors == []

    missing = scale_process._Measurements()
    assert missing.child(Probe(), process)
    assert missing.errors == ["rss_unavailable_at_exit:RuntimeError"]


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
    legacy = observed.model_dump()
    legacy.pop("io_counter_source")
    legacy.pop("io_counter_fallback_reason")
    legacy.pop("measurement_contract")
    legacy.pop("measurement_platform")
    legacy.pop("metric_coverage")
    restored = ProcessObservation.model_validate(legacy)
    assert restored.io_counter_source == "legacy_unspecified"
    assert restored.io_counter_fallback_reason is None
    assert restored.measurement_contract == "legacy_unspecified"
    assert not restored.resource_contract_complete
    contradictory = observed.model_dump()
    contradictory["io_counter_source"] = "unavailable"
    with pytest.raises(ValidationError, match="cannot contain observations"):
        ProcessObservation.model_validate(contradictory)
    data = observed.model_dump()
    data["exit_code"] = None
    with pytest.raises(ValidationError, match="reaped child"):
        ProcessObservation.model_validate(data)
    data = observed.model_dump()
    data["wall_seconds"] = float("nan")
    with pytest.raises(ValidationError):
        ProcessObservation.model_validate(data)
