"""Bounded supervision of trusted, single-child scaling workloads.

This is not a sandbox. RSS, CPU and I/O describe only the direct child. Observed
descendants fail the single-process workload restriction. POSIX termination
targets its private process group; observed descendants also receive best-effort
identity-checked termination. Neither escaped sessions nor unobserved short-lived
descendants are contained or reliably detected. RSS and directory peaks are
sampled lower bounds. Thresholds trigger
reactive killing, may overshoot, and are never hard resource quotas. CPU/I/O are
last-observed cumulative counters, not guaranteed final process totals. Directory
walks are non-atomic and cannot observe deleted or unlinked-open temporary files.
An exited process, even exit zero, says nothing about a valid completion manifest.
"""

from __future__ import annotations

import math
import os
import signal
import stat
import subprocess
import time
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Annotated, Literal, Protocol, Self, cast

from pydantic import Field, model_validator

from equiframe_benchmark.models import Document, Text

NonnegativeInt = Annotated[int, Field(ge=0)]
NonnegativeFloat = Annotated[float, Field(ge=0)]
TerminationReason = Literal[
    "exited",
    "timeout",
    "rss_budget_exceeded",
    "disk_budget_exceeded",
    "monitoring_failed",
    "launch_failed",
    "unsupported_descendant",
]


class ProcessObservation(Document):
    """Process facts, deliberately without a workload-success or complete flag.

    Sample counts/gaps cover monitoring rounds, including the preflight and
    final disk-only rounds. ``cleanup_reaped`` refers only to the direct child;
    it is also true when launch never happened. Descendants cannot generally be
    reaped by this process and their absence is not a containment guarantee.
    """

    pid: Annotated[int, Field(gt=0)] | None
    exit_code: int | None
    termination_reason: TerminationReason
    wall_seconds: NonnegativeFloat
    sampled_rss_peak_bytes: NonnegativeInt | None
    cpu_user_seconds: NonnegativeFloat | None
    cpu_system_seconds: NonnegativeFloat | None
    io_read_bytes: NonnegativeInt | None
    io_write_bytes: NonnegativeInt | None
    io_read_chars: NonnegativeInt | None
    io_write_chars: NonnegativeInt | None
    disk_apparent_peak_bytes: NonnegativeInt | None
    disk_allocated_peak_bytes: NonnegativeInt | None
    sample_interval_seconds: Annotated[float, Field(gt=0)]
    max_sample_gap_seconds: NonnegativeFloat | None
    sample_count: NonnegativeInt
    monitoring_errors: tuple[Text, ...]
    cleanup_reaped: bool
    observed_descendant_pids: tuple[Annotated[int, Field(gt=0)], ...] = ()
    resource_scope: Literal["direct_child_excluding_descendants"] = (
        "direct_child_excluding_descendants"
    )
    termination_scope: Literal["posix_process_group", "direct_child"]
    rss_method: Literal["sampled_absolute_lower_bound"] = "sampled_absolute_lower_bound"
    counter_method: Literal["sampled_cumulative_last_available"] = (
        "sampled_cumulative_last_available"
    )
    disk_method: Literal["sampled_tree_inodes_no_symlink_following"] = (
        "sampled_tree_inodes_no_symlink_following"
    )
    budget_method: Literal["reactive_sampled_thresholds_not_hard_quotas"] = (
        "reactive_sampled_thresholds_not_hard_quotas"
    )
    stdout_path: Literal["stdout.log"] = "stdout.log"
    stderr_path: Literal["stderr.log"] = "stderr.log"

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.termination_reason == "exited" and (
            self.exit_code is None or self.pid is None or not self.cleanup_reaped
        ):
            raise ValueError("exited requires a reaped child and its actual exit code")
        if self.pid is None and self.exit_code is not None:
            raise ValueError("an unstarted child cannot have an exit code")
        if self.sample_count < 2 and self.max_sample_gap_seconds is not None:
            raise ValueError("sampling gaps require at least two observations")
        if self.termination_reason in ("monitoring_failed", "launch_failed") and (
            not self.monitoring_errors
        ):
            raise ValueError("failed supervision requires an explicit reason")
        if (
            self.termination_reason == "unsupported_descendant"
            and not self.observed_descendant_pids
        ):
            raise ValueError("unsupported descendants require an observed child identity")
        return self


class _CpuTimes(Protocol):
    user: float
    system: float


class _MemoryInfo(Protocol):
    rss: int


class _Process(Protocol):
    def memory_info(self) -> _MemoryInfo: ...

    def cpu_times(self) -> _CpuTimes: ...

    def io_counters(self) -> object: ...

    def children(self, recursive: bool = False) -> list[_Descendant]: ...


class _Descendant(Protocol):
    pid: int

    def kill(self) -> None: ...


class _ProcessFactory(Protocol):
    def Process(self, pid: int) -> _Process: ...


@dataclass
class _Measurements:
    errors: list[str] = field(default_factory=list)
    sampled_rss_peak_bytes: int | None = None
    cpu_user_seconds: float | None = None
    cpu_system_seconds: float | None = None
    io_read_bytes: int | None = None
    io_write_bytes: int | None = None
    io_read_chars: int | None = None
    io_write_chars: int | None = None
    disk_apparent_peak_bytes: int | None = None
    disk_allocated_peak_bytes: int | None = None
    sample_count: int = 0
    max_sample_gap_seconds: float | None = None
    previous_time: float | None = None
    descendants: list[_Descendant] = field(default_factory=list)
    cleanup_lock: Lock = field(default_factory=Lock)

    def error(self, code: str, error: BaseException | None = None) -> None:
        # Keep errors bounded and avoid leaking paths, commands or environment data.
        message = code if error is None else f"{code}:{type(error).__name__}"
        if message not in self.errors:
            self.errors.append(message)

    def tick(self) -> None:
        now = time.monotonic()
        if self.previous_time is not None:
            gap = now - self.previous_time
            self.max_sample_gap_seconds = max(self.max_sample_gap_seconds or 0.0, gap)
        self.previous_time = now
        self.sample_count += 1

    def disk(self, directory: Path) -> None:
        apparent, allocated = _disk_usage(directory)
        self.disk_apparent_peak_bytes = max(self.disk_apparent_peak_bytes or 0, apparent)
        if allocated is None:
            self.error("disk_allocated_bytes_unavailable")
        else:
            self.disk_allocated_peak_bytes = max(self.disk_allocated_peak_bytes or 0, allocated)

    def child(self, probe: _Process, process: subprocess.Popen[bytes]) -> bool:
        """Return false if a running child cannot be monitored for RSS."""
        try:
            rss = probe.memory_info().rss
            if rss < 0:
                raise ValueError("negative RSS")
            self.sampled_rss_peak_bytes = max(self.sampled_rss_peak_bytes or 0, rss)
        except Exception as error:
            if _child_exited(process):
                self.error("rss_unavailable_at_exit", error)
                return True
            self.error("rss_monitoring_failed", error)
            return False
        try:
            cpu = probe.cpu_times()
            if any(not math.isfinite(value) or value < 0 for value in (cpu.user, cpu.system)):
                raise ValueError("invalid CPU counters")
            self.cpu_user_seconds, self.cpu_system_seconds = cpu.user, cpu.system
        except Exception as error:
            self.error("cpu_counters_unavailable", error)
        try:
            counters = probe.io_counters()
            for name in ("read_bytes", "write_bytes", "read_chars", "write_chars"):
                value: object = getattr(counters, name, None)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    setattr(self, "io_" + name, value)
                else:
                    self.error("io_" + name + "_unavailable")
        except Exception as error:
            self.error("io_counters_unavailable", error)
        return True

    def disk_exceeded(self, budget: int) -> bool:
        return max(self.disk_apparent_peak_bytes or 0, self.disk_allocated_peak_bytes or 0) > budget

    def observation(
        self,
        process: subprocess.Popen[bytes] | None,
        reason: TerminationReason,
        started: float,
        interval: float,
        reaped: bool,
    ) -> ProcessObservation:
        if self.max_sample_gap_seconds is not None and self.max_sample_gap_seconds > 2 * interval:
            self.error("sampling_gap_exceeded_twice_requested_interval")
        return ProcessObservation(
            pid=process.pid if process is not None else None,
            exit_code=process.returncode if process is not None else None,
            termination_reason=reason,
            wall_seconds=time.monotonic() - started,
            sampled_rss_peak_bytes=self.sampled_rss_peak_bytes,
            cpu_user_seconds=self.cpu_user_seconds,
            cpu_system_seconds=self.cpu_system_seconds,
            io_read_bytes=self.io_read_bytes,
            io_write_bytes=self.io_write_bytes,
            io_read_chars=self.io_read_chars,
            io_write_chars=self.io_write_chars,
            disk_apparent_peak_bytes=self.disk_apparent_peak_bytes,
            disk_allocated_peak_bytes=self.disk_allocated_peak_bytes,
            sample_interval_seconds=interval,
            max_sample_gap_seconds=self.max_sample_gap_seconds,
            sample_count=self.sample_count,
            monitoring_errors=tuple(self.errors),
            cleanup_reaped=reaped,
            observed_descendant_pids=tuple(sorted({item.pid for item in self.descendants})),
            termination_scope="posix_process_group" if os.name == "posix" else "direct_child",
        )


def _disk_usage(directory: Path) -> tuple[int, int | None]:
    """Count tree inodes, including directory metadata, once per device/inode."""
    apparent, allocated = 0, 0
    blocks_available = True
    pending = [directory]
    seen: set[tuple[int, int]] = set()
    while pending:
        path = pending.pop()
        try:
            item = path.lstat()
        except FileNotFoundError:
            if path == directory:
                raise
            continue  # A live workload may remove a temporary file during the walk.
        identity = (item.st_dev, item.st_ino)
        if item.st_ino and identity in seen:
            continue
        seen.add(identity)
        apparent += item.st_size
        blocks: object = getattr(item, "st_blocks", None)
        if isinstance(blocks, int) and blocks >= 0:
            allocated += blocks * 512
        else:
            blocks_available = False
        if stat.S_ISDIR(item.st_mode):
            try:
                pending.extend(path.iterdir())
            except FileNotFoundError:
                if path == directory:
                    raise
    return apparent, allocated if blocks_available else None


def _nonreaping_wait_available() -> bool:
    return os.name == "posix" and all(
        hasattr(os, name) for name in ("waitid", "P_PID", "WEXITED", "WNOHANG", "WNOWAIT")
    )


def _child_exited(process: subprocess.Popen[bytes]) -> bool:
    """Keep an exited POSIX leader's PID reserved until group termination."""
    if process.returncode is not None:
        return True
    if _nonreaping_wait_available():
        try:
            return (
                os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
            )
        except ChildProcessError:
            # A concurrent watchdog may already have reaped this owned child.
            return process.poll() is not None
    return process.poll() is not None


def _kill_and_wait(process: subprocess.Popen[bytes], measurements: _Measurements) -> bool:
    """Kill the private group before reaping; never signal a reused group ID."""
    # The watchdog and main thread must not race group signaling against reaping.
    with measurements.cleanup_lock:
        try:
            if (
                os.name == "posix"
                and not _nonreaping_wait_available()
                and process.returncode is not None
            ):
                measurements.error("post_exit_group_cleanup_unavailable_without_nonreaping_wait")
            if process.returncode is None:
                if os.name == "posix":
                    try:
                        # waitid(WNOWAIT) preserves this leader, including a zombie,
                        # so this session/group ID cannot have been reused.
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except OSError as error:
                        measurements.error("process_group_kill_failed", error)
                        process.kill()
                else:
                    process.kill()
            for descendant in measurements.descendants:
                try:
                    # psutil checks the process identity before signaling a PID.
                    descendant.kill()
                except Exception as error:
                    measurements.error("observed_descendant_kill_unavailable", error)
            process.wait(timeout=5.0)
        except Exception as error:
            measurements.error("child_cleanup_failed", error)
            return False
    return True


class _DeadlineGuard:
    """Terminate independently of a delayed sampler; not an OS hard time quota."""

    def __init__(
        self, process: subprocess.Popen[bytes], deadline: float, measurements: _Measurements
    ) -> None:
        self.process = process
        self.deadline = deadline
        self.measurements = measurements
        self.cancel = Event()
        self.expired = Event()
        self.failed = Event()
        self.started = False
        self.thread = Thread(target=self._watch, name="equiframe-scale-deadline", daemon=True)

    def start(self) -> None:
        self.thread.start()
        self.started = True

    def close(self) -> None:
        self.cancel.set()
        if self.started:
            self.thread.join()

    def _watch(self) -> None:
        try:
            if not self.cancel.wait(
                max(0.0, self.deadline - time.monotonic())
            ) and not _child_exited(self.process):
                self.expired.set()
                _kill_and_wait(self.process, self.measurements)
        except Exception as error:
            self.failed.set()
            self.measurements.error("deadline_watchdog_failed", error)
            _kill_and_wait(self.process, self.measurements)


def _validate(command: list[str], timeout: float, rss: int, disk: int, interval: float) -> None:
    if not command or any(not isinstance(arg, str) or "\x00" in arg for arg in command):
        raise ValueError("a nonempty trusted command with valid string arguments is required")
    for value in (timeout, interval):
        if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError("timeout and sampling interval must be finite and positive")
    for budget in (rss, disk):
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise ValueError("RSS and disk budgets must be positive integers")


def supervise(
    command: list[str],
    *,
    directory: Path,
    timeout_seconds: float,
    rss_budget_bytes: int,
    disk_budget_bytes: int,
    sample_interval_seconds: float = 0.05,
    env: dict[str, str] | None = None,
) -> ProcessObservation:
    """Run a fixed trusted command with exclusive logs and sampled budget checks.

    ``directory`` is owned by this run and may contain prewritten inputs. Existing
    stdout/stderr logs are never overwritten. Environment overrides extend the
    inherited environment; TMPDIR/TMP/TEMP always point to ``directory/tmp``.
    The disk threshold applies to either apparent or allocated observed bytes.
    Measurement or launch failures remain explicit and fail closed. Interruptions
    propagate only after child cleanup. Retained files are evidence, not removed.
    Wall duration includes launching, monitoring, reaping and the final disk walk.
    A separate watchdog triggers timeout termination even if a sample is delayed;
    OS scheduling and cleanup can delay termination/return beyond that deadline.
    Children are disallowed and sampled recursively, not atomically. On POSIX
    with waitid(WNOWAIT), cleanup signals the private group before reaping even
    when the leader exited. Other POSIX platforms cannot safely signal an
    already-reaped group ID and report that cleanup limitation explicitly.
    """
    _validate(
        command, timeout_seconds, rss_budget_bytes, disk_budget_bytes, sample_interval_seconds
    )
    if directory.is_symlink():
        raise ValueError("the owned work directory cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    started = time.monotonic()
    measurements = _Measurements()
    process: subprocess.Popen[bytes] | None = None
    watchdog: _DeadlineGuard | None = None
    reason: TerminationReason = "launch_failed"
    reaped = True
    try:
        psutil = import_module("psutil")
    except ImportError as error:
        measurements.error("resources_extra_unavailable", error)
        return measurements.observation(
            None, "monitoring_failed", started, sample_interval_seconds, reaped
        )
    try:
        temporary = directory / "tmp"
        if temporary.is_symlink():
            raise ValueError("the owned temporary directory cannot be a symlink")
        temporary.mkdir(exist_ok=True)
        environment = dict(os.environ)
        environment.update(env or {})
        environment.update({name: str(temporary) for name in ("TMPDIR", "TMP", "TEMP")})
        with (
            (directory / "stdout.log").open("xb") as stdout,
            (directory / "stderr.log").open("xb") as stderr,
        ):
            reason = "monitoring_failed"
            measurements.tick()
            measurements.disk(directory)
            if measurements.disk_exceeded(disk_budget_bytes):
                reason = "disk_budget_exceeded"
            else:
                reason = "launch_failed"
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=directory,
                    env=environment,
                    start_new_session=os.name == "posix",
                )
                reason = "monitoring_failed"
                watchdog = _DeadlineGuard(process, started + timeout_seconds, measurements)
                watchdog.start()
                reason = _watch(
                    process,
                    psutil,
                    directory,
                    measurements,
                    started + timeout_seconds,
                    rss_budget_bytes,
                    disk_budget_bytes,
                    sample_interval_seconds,
                )
    except Exception as error:
        if reason == "exited":
            reason = "monitoring_failed"
        measurements.error(reason, error)
    finally:
        if process is not None:
            reaped = _kill_and_wait(process, measurements)
        if watchdog is not None:
            watchdog.close()
            if watchdog.failed.is_set():
                reason = "monitoring_failed"
            elif watchdog.expired.is_set() and reason != "unsupported_descendant":
                reason = "timeout"
        try:
            measurements.tick()
            measurements.disk(directory)
            if reason == "exited" and measurements.disk_exceeded(disk_budget_bytes):
                reason = "disk_budget_exceeded"
        except Exception as error:
            measurements.error("final_disk_sample_failed", error)
            if reason == "exited":
                reason = "monitoring_failed"
    if not reaped:
        reason = "monitoring_failed"
    return measurements.observation(process, reason, started, sample_interval_seconds, reaped)


def _watch(
    process: subprocess.Popen[bytes],
    psutil: object,
    directory: Path,
    measurements: _Measurements,
    deadline: float,
    rss_budget: int,
    disk_budget: int,
    interval: float,
) -> TerminationReason:
    # Dynamic import keeps psutil optional without importing its untyped package.
    factory = cast(_ProcessFactory, psutil)
    try:
        probe = factory.Process(process.pid)
    except Exception as error:
        if _child_exited(process):
            measurements.error("process_probe_unavailable_at_exit", error)
            return "exited"
        raise
    while True:
        if time.monotonic() >= deadline:
            return "timeout"
        measurements.tick()
        try:
            descendants = probe.children(recursive=True)
        except Exception as error:
            if _child_exited(process):
                measurements.error("descendant_probe_unavailable_at_exit", error)
                descendants = []
            else:
                raise
        if descendants:
            measurements.descendants.extend(descendants)
            return "unsupported_descendant"
        if not measurements.child(probe, process):
            return "monitoring_failed"
        measurements.disk(directory)
        if (measurements.sampled_rss_peak_bytes or 0) > rss_budget:
            return "rss_budget_exceeded"
        if measurements.disk_exceeded(disk_budget):
            return "disk_budget_exceeded"
        if _child_exited(process):
            return "exited"
        if time.monotonic() >= deadline:
            return "timeout"
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
