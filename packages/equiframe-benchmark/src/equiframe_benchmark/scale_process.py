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
import sys
import time
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Annotated, Literal, Protocol, cast

from equiframe._regular_io import open_regular_file
from equiframe.errors import ArtifactIntegrityError, ArtifactIOError
from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Document, Text


class _PosixOS(Protocol):
    P_PID: int
    WEXITED: int
    WNOHANG: int
    WNOWAIT: int

    def waitid(self, idtype: int, pid: int, options: int, /) -> object | None: ...

    def killpg(self, process_group: int, signal_number: int, /) -> None: ...


class _PosixSignals(Protocol):
    SIGKILL: int


NonnegativeInt = Annotated[int, Field(ge=0)]
NonnegativeFloat = Annotated[float, Field(ge=0)]
MEASUREMENT_CONTRACT_ID: Literal["equiframe_process_resources_v1"] = (
    "equiframe_process_resources_v1"
)
MeasurementPlatform = Literal["linux", "windows", "macos"]
MeasurementMetric = Literal[
    "sampled_rss_peak_bytes",
    "cpu_user_seconds",
    "cpu_system_seconds",
    "io_read_bytes",
    "io_write_bytes",
    "io_read_chars",
    "io_write_chars",
    "disk_apparent_peak_bytes",
    "disk_allocated_peak_bytes",
]
MeasurementSource = Literal[
    "psutil_process_memory_info_rss",
    "psutil_process_cpu_times_user",
    "psutil_process_cpu_times_system",
    "psutil_process_io_counters",
    "linux_proc_pid_io",
    "filesystem_tree_stat_size",
    "filesystem_tree_stat_blocks_512",
]
_MEASUREMENT_METRICS: tuple[MeasurementMetric, ...] = (
    "sampled_rss_peak_bytes",
    "cpu_user_seconds",
    "cpu_system_seconds",
    "io_read_bytes",
    "io_write_bytes",
    "io_read_chars",
    "io_write_chars",
    "disk_apparent_peak_bytes",
    "disk_allocated_peak_bytes",
)
_PLATFORM_UNAVAILABLE: dict[MeasurementPlatform, dict[MeasurementMetric, str]] = {
    "linux": {},
    "windows": {
        "io_read_chars": "windows_psutil_process_io_read_chars_not_exposed",
        "io_write_chars": "windows_psutil_process_io_write_chars_not_exposed",
        "disk_allocated_peak_bytes": "windows_python_stat_result_st_blocks_not_exposed",
    },
    "macos": {
        "io_read_bytes": "macos_psutil_process_io_counters_not_exposed",
        "io_write_bytes": "macos_psutil_process_io_counters_not_exposed",
        "io_read_chars": "macos_psutil_process_io_counters_not_exposed",
        "io_write_chars": "macos_psutil_process_io_counters_not_exposed",
    },
}
TerminationReason = Literal[
    "exited",
    "timeout",
    "rss_budget_exceeded",
    "disk_budget_exceeded",
    "monitoring_failed",
    "launch_failed",
    "unsupported_descendant",
]


def current_measurement_platform(value: str | None = None) -> MeasurementPlatform:
    """Map only the three documented native measurement contracts."""
    selected = sys.platform if value is None else value
    if selected.startswith("linux"):
        return "linux"
    if selected.startswith("win"):
        return "windows"
    if selected == "darwin":
        return "macos"
    raise RuntimeError("unsupported operating system for process resource measurement")


class ResourceMetricCoverage(Document):
    """One metric's actual observation or its exact platform capability boundary."""

    metric: MeasurementMetric
    state: Literal["observed", "unavailable_on_platform", "measurement_failed"]
    source: MeasurementSource | None
    reason: Text | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.state == "observed" and (self.source is None or self.reason is not None):
            raise ValueError("an observed metric requires its source and no absence reason")
        if self.state != "observed" and (self.source is not None or self.reason is None):
            raise ValueError("an unobserved metric requires a reason and cannot claim a source")
        return self


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
    io_counter_source: Literal[
        "psutil", "linux_proc_pid_io", "unavailable", "legacy_unspecified"
    ] = "legacy_unspecified"
    io_counter_fallback_reason: Text | None = None
    disk_apparent_peak_bytes: NonnegativeInt | None
    disk_allocated_peak_bytes: NonnegativeInt | None
    measurement_contract: Literal["equiframe_process_resources_v1", "legacy_unspecified"] = (
        "legacy_unspecified"
    )
    measurement_platform: Literal["linux", "windows", "macos", "legacy_unspecified"] = (
        "legacy_unspecified"
    )
    metric_coverage: tuple[ResourceMetricCoverage, ...] = ()
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
        io_values = (
            self.io_read_bytes,
            self.io_write_bytes,
            self.io_read_chars,
            self.io_write_chars,
        )
        if self.io_counter_source == "unavailable" and any(
            value is not None for value in io_values
        ):
            raise ValueError("unavailable I/O counters cannot contain observations")
        if self.io_counter_source in ("psutil", "linux_proc_pid_io") and not any(
            value is not None for value in io_values
        ):
            raise ValueError("an observed I/O counter source requires actual observations")
        if (self.io_counter_fallback_reason is not None) != (
            self.io_counter_source == "linux_proc_pid_io"
        ):
            raise ValueError("Linux /proc I/O fallback must preserve its bounded reason")
        if self.measurement_contract == "legacy_unspecified":
            if self.measurement_platform != "legacy_unspecified" or self.metric_coverage:
                raise ValueError("legacy observations cannot claim a current platform contract")
            return self
        if self.measurement_platform == "legacy_unspecified":
            raise ValueError("the current measurement contract requires a platform")
        if tuple(item.metric for item in self.metric_coverage) != _MEASUREMENT_METRICS:
            raise ValueError("metric coverage must contain the exact ordered contract")
        platform = self.measurement_platform
        unavailable = _PLATFORM_UNAVAILABLE[platform]
        for item in self.metric_coverage:
            value = getattr(self, item.metric)
            expected_reason = unavailable.get(item.metric)
            if expected_reason is not None:
                if (
                    item.state != "unavailable_on_platform"
                    or item.reason != expected_reason
                    or value is not None
                ):
                    raise ValueError("platform-unavailable metrics require their exact reason")
            elif item.state == "unavailable_on_platform":
                raise ValueError("a supported platform metric cannot be declared unavailable")
            if item.state == "observed" and value is None:
                raise ValueError("observed metric coverage requires its actual value")
            if item.state != "observed" and value is not None:
                raise ValueError("an unobserved metric cannot contain a value")
            if item.state == "measurement_failed" and item.reason not in self.monitoring_errors:
                raise ValueError("measurement failures must bind to a monitoring error")
            allowed_sources = _metric_sources(item.metric, platform)
            if item.source is not None and item.source not in allowed_sources:
                raise ValueError("metric source is not valid for this platform contract")
        io_coverage = tuple(item for item in self.metric_coverage if item.metric.startswith("io_"))
        observed_io_sources = {
            item.source
            for item in io_coverage
            if item.state == "observed" and item.source is not None
        }
        if len(observed_io_sources) > 1:
            raise ValueError("one process observation cannot mix I/O counter sources")
        if observed_io_sources:
            only_source = next(iter(observed_io_sources))
            if only_source == "psutil_process_io_counters":
                expected_io_source = "psutil"
            elif only_source == "linux_proc_pid_io":
                expected_io_source = "linux_proc_pid_io"
            else:
                raise ValueError("I/O coverage used a non-I/O metric source")
            if self.io_counter_source != expected_io_source:
                raise ValueError("I/O coverage source contradicts the counter source")
        elif self.io_counter_source != "unavailable":
            raise ValueError("missing I/O coverage cannot claim a counter source")
        return self

    @property
    def resource_contract_complete(self) -> bool:
        """Whether every metric satisfies the declared native platform contract."""
        return (
            self.measurement_contract == MEASUREMENT_CONTRACT_ID
            and self.measurement_platform != "legacy_unspecified"
            and len(self.metric_coverage) == len(_MEASUREMENT_METRICS)
            and not self.monitoring_errors
            and all(item.state != "measurement_failed" for item in self.metric_coverage)
        )


def _metric_sources(
    metric: MeasurementMetric, platform: MeasurementPlatform
) -> frozenset[MeasurementSource]:
    fixed: dict[MeasurementMetric, MeasurementSource] = {
        "sampled_rss_peak_bytes": "psutil_process_memory_info_rss",
        "cpu_user_seconds": "psutil_process_cpu_times_user",
        "cpu_system_seconds": "psutil_process_cpu_times_system",
        "disk_apparent_peak_bytes": "filesystem_tree_stat_size",
        "disk_allocated_peak_bytes": "filesystem_tree_stat_blocks_512",
    }
    if metric in fixed:
        return frozenset((fixed[metric],))
    if platform == "linux":
        return frozenset(("psutil_process_io_counters", "linux_proc_pid_io"))
    if platform == "windows":
        return frozenset(("psutil_process_io_counters",))
    return frozenset()


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

    def is_running(self) -> bool: ...


class _ProcessFactory(Protocol):
    def Process(self, pid: int) -> _Process: ...


@dataclass
class _Measurements:
    measurement_platform: MeasurementPlatform = field(default_factory=current_measurement_platform)
    errors: list[str] = field(default_factory=list)
    sampled_rss_peak_bytes: int | None = None
    cpu_user_seconds: float | None = None
    cpu_system_seconds: float | None = None
    io_read_bytes: int | None = None
    io_write_bytes: int | None = None
    io_read_chars: int | None = None
    io_write_chars: int | None = None
    io_counter_source: Literal["psutil", "linux_proc_pid_io", "unavailable"] = "unavailable"
    io_counter_fallback_reason: str | None = None
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
            if self.measurement_platform != "windows":
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
                if self.sampled_rss_peak_bytes is None:
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
        if self.measurement_platform == "macos":
            # psutil deliberately has no Process.io_counters implementation on macOS.
            # The exact capability boundary is recorded in metric_coverage.
            return True
        try:
            counters: object = probe.io_counters()
        except Exception as psutil_error:
            if self.measurement_platform == "linux":
                try:
                    counters = _read_linux_proc_io(process.pid)
                except Exception as proc_error:
                    if (
                        isinstance(
                            proc_error, (PermissionError, FileNotFoundError, ProcessLookupError)
                        )
                        and self.io_counter_source in ("psutil", "linux_proc_pid_io")
                        and all(
                            value is not None
                            for value in (
                                self.io_read_bytes,
                                self.io_write_bytes,
                                self.io_read_chars,
                                self.io_write_chars,
                            )
                        )
                        and _child_exited(process)
                    ):
                        # A zombie may deny /proc/PID/io after valid live samples.
                        # Retain the declared last-available counters; do not
                        # invent a final sample or hide a denial while alive.
                        return True
                    self.error("io_counters_unavailable", psutil_error)
                    self.error("linux_proc_io_unavailable", proc_error)
                else:
                    self._io(counters, "linux_proc_pid_io")
                    self.io_counter_fallback_reason = (
                        "psutil_io_counters_unavailable:" + type(psutil_error).__name__
                    )
            else:
                self.error("io_counters_unavailable", psutil_error)
        else:
            self._io(counters, "psutil")
        return True

    def _io(
        self,
        counters: object,
        source: Literal["psutil", "linux_proc_pid_io"],
    ) -> None:
        observed = False
        names = (
            ("read_bytes", "write_bytes")
            if self.measurement_platform == "windows"
            else ("read_bytes", "write_bytes", "read_chars", "write_chars")
        )
        for name in names:
            value: object = (
                counters.get(name) if isinstance(counters, dict) else getattr(counters, name, None)
            )
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                setattr(self, "io_" + name, value)
                observed = True
            else:
                self.error("io_" + name + "_unavailable")
        if observed:
            self.io_counter_source = source
            if source == "psutil":
                self.io_counter_fallback_reason = None

    def coverage(self) -> tuple[ResourceMetricCoverage, ...]:
        """Bind every value or absence to the current platform contract."""
        result: list[ResourceMetricCoverage] = []
        unavailable = _PLATFORM_UNAVAILABLE[self.measurement_platform]
        for metric in _MEASUREMENT_METRICS:
            value = getattr(self, metric)
            unavailable_reason = unavailable.get(metric)
            if unavailable_reason is not None:
                if value is not None:
                    raise ValueError("a platform-unavailable metric unexpectedly has a value")
                result.append(
                    ResourceMetricCoverage(
                        metric=metric,
                        state="unavailable_on_platform",
                        source=None,
                        reason=unavailable_reason,
                    )
                )
                continue
            if value is None:
                reason = metric + "_measurement_unavailable"
                self.error(reason)
                result.append(
                    ResourceMetricCoverage(
                        metric=metric,
                        state="measurement_failed",
                        source=None,
                        reason=reason,
                    )
                )
                continue
            if metric == "sampled_rss_peak_bytes":
                source: MeasurementSource = "psutil_process_memory_info_rss"
            elif metric == "cpu_user_seconds":
                source = "psutil_process_cpu_times_user"
            elif metric == "cpu_system_seconds":
                source = "psutil_process_cpu_times_system"
            elif metric == "disk_apparent_peak_bytes":
                source = "filesystem_tree_stat_size"
            elif metric == "disk_allocated_peak_bytes":
                source = "filesystem_tree_stat_blocks_512"
            elif self.io_counter_source == "psutil":
                source = "psutil_process_io_counters"
            elif self.io_counter_source == "linux_proc_pid_io":
                source = "linux_proc_pid_io"
            else:
                raise ValueError("an observed I/O value requires its actual source")
            result.append(
                ResourceMetricCoverage(
                    metric=metric,
                    state="observed",
                    source=source,
                    reason=None,
                )
            )
        return tuple(result)

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
        coverage = self.coverage()
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
            io_counter_source=self.io_counter_source,
            io_counter_fallback_reason=self.io_counter_fallback_reason,
            disk_apparent_peak_bytes=self.disk_apparent_peak_bytes,
            disk_allocated_peak_bytes=self.disk_allocated_peak_bytes,
            measurement_contract=MEASUREMENT_CONTRACT_ID,
            measurement_platform=self.measurement_platform,
            metric_coverage=coverage,
            sample_interval_seconds=interval,
            max_sample_gap_seconds=self.max_sample_gap_seconds,
            sample_count=self.sample_count,
            monitoring_errors=tuple(self.errors),
            cleanup_reaped=reaped,
            observed_descendant_pids=tuple(sorted({item.pid for item in self.descendants})),
            termination_scope="posix_process_group" if os.name == "posix" else "direct_child",
        )


def _read_linux_proc_io(pid: int, *, proc_root: Path = Path("/proc")) -> dict[str, int]:
    """Read Linux's kernel-provided cumulative counters for one known child PID."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise ValueError("Linux process I/O counters require a positive PID")
    required = {
        "read_bytes": "read_bytes",
        "write_bytes": "write_bytes",
        "rchar": "read_chars",
        "wchar": "write_chars",
    }
    observed: dict[str, int] = {}
    for line in (proc_root / str(pid) / "io").read_text(encoding="ascii").splitlines():
        name, separator, raw = line.partition(":")
        if not separator or name not in required:
            continue
        target = required[name]
        if target in observed:
            raise ValueError("duplicate Linux process I/O counter")
        value = raw.strip()
        if not value.isdecimal():
            raise ValueError("invalid Linux process I/O counter")
        observed[target] = int(value)
    if set(observed) != set(required.values()):
        raise ValueError("incomplete Linux process I/O counters")
    return observed


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
                cast(_PosixOS, os).waitid(
                    cast(_PosixOS, os).P_PID,
                    process.pid,
                    cast(_PosixOS, os).WEXITED
                    | cast(_PosixOS, os).WNOHANG
                    | cast(_PosixOS, os).WNOWAIT,
                )
                is not None
            )
        except ChildProcessError:
            # A concurrent watchdog may already have reaped this owned child.
            return process.poll() is not None
    return process.poll() is not None


def _venv_config(path: Path) -> dict[str, str] | None:
    """Read only bounded, regular venv configuration with unique keys."""
    try:
        with open_regular_file(path) as stream:
            raw = stream.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            return None
        values: dict[str, str] = {}
        for raw_line in raw.decode("utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            key = key.strip().casefold()
            if not separator or not key or key in values:
                return None
            values[key] = value.strip()
        implementation = values.get("implementation")
        if implementation is not None and implementation.casefold() != "cpython":
            return None
        return values
    except (OSError, UnicodeError, ValueError, ArtifactIntegrityError, ArtifactIOError):
        return None


def _creator_matches_base(configured: Path, base: Path, home: Path) -> bool:
    """Validate at most 16 creator venvs; never execute a configured creator."""
    seen: set[Path] = set()
    for _ in range(16):
        if configured == base:
            return True
        if (
            configured in seen
            or configured.name.casefold() != base.name.casefold()
            or configured.parent.name.casefold() != "scripts"
            or not configured.is_file()
        ):
            return False
        seen.add(configured)
        values = _venv_config(configured.parent.parent / "pyvenv.cfg")
        if values is None:
            return False
        try:
            raw_home = Path(values.get("home", ""))
            creator = Path(values.get("executable", str(home / base.name)))
            if not raw_home.is_absolute() or not creator.is_absolute():
                return False
            if raw_home.resolve(strict=True) != home:
                return False
            configured = creator.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            return False
    return configured == base


def _windows_venv_base_launch(
    command: list[str], environment: dict[str, str]
) -> tuple[list[str], dict[str, str]]:
    """Bypass only this process's validated Windows CPython venv redirector.

    Windows CPython virtual environments may use a small ``Scripts/python.exe``
    redirector which waits on the base interpreter.  Treating that implementation
    detail as a workload descendant either rejects every supervised run or forces
    the supervisor to aggregate two identities.  Launching the already-bound base
    executable with CPython's launcher variable preserves ``sys.prefix`` and
    ``sys.executable`` while making the real interpreter the owned ``Popen`` child.

    The substitution is deliberately restricted to the currently running CPython
    environment and to an internally consistent ``pyvenv.cfg``.  Any other command
    is returned unchanged and remains subject to normal fail-closed descendant
    detection.
    """
    if (
        os.name != "nt"
        or len(command) < 2
        or command[1] != "-I"
        or sys.implementation.name != "cpython"
    ):
        return command, environment
    reported_base = getattr(sys, "_base_executable", None)
    if not isinstance(reported_base, str) or not reported_base:
        return command, environment
    try:
        launcher = Path(command[0]).resolve(strict=True)
        current_launcher = Path(sys.executable).resolve(strict=True)
        base = Path(reported_base).resolve(strict=True)
        prefix = Path(sys.prefix).resolve(strict=True)
        base_prefix = Path(sys.base_prefix).resolve(strict=True)
    except (OSError, RuntimeError):
        return command, environment
    if (
        launcher != current_launcher
        or launcher == base
        or launcher.parent.parent.resolve() != prefix
    ):
        return command, environment
    if launcher.name.casefold() != "python.exe" or launcher.parent.name.casefold() != "scripts":
        return command, environment
    config_path = launcher.parent.parent / "pyvenv.cfg"
    values = _venv_config(config_path)
    if values is None:
        return command, environment
    try:
        raw_home = values.get("home")
        if not raw_home:
            return command, environment
        home = Path(raw_home)
        if not home.is_absolute():
            return command, environment
        home = home.resolve(strict=True)
        configured = Path(values.get("executable", str(home / launcher.name)))
        if not configured.is_absolute():
            return command, environment
        configured = configured.resolve(strict=True)
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return command, environment
    if (
        home != base_prefix
        or base.parent != home
        or base.name.casefold() != launcher.name.casefold()
        or not base.is_file()
        or not _creator_matches_base(configured, base, home)
    ):
        return command, environment
    prepared_environment = {
        key: value for key, value in environment.items() if key.casefold() != "__pyvenv_launcher__"
    }
    prepared_environment["__PYVENV_LAUNCHER__"] = sys.executable
    return [reported_base, *command[1:]], prepared_environment


def _kill_observed_descendants(measurements: _Measurements) -> None:
    """Best-effort cleanup using only the identities captured by psutil."""
    for descendant in measurements.descendants:
        try:
            # psutil checks its cached PID/create-time identity before signaling.
            descendant.kill()
        except Exception as error:
            measurements.error("observed_descendant_kill_unavailable", error)
    pending = list(measurements.descendants)
    deadline = time.monotonic() + 5.0
    while pending:
        remaining: list[_Descendant] = []
        for descendant in pending:
            try:
                # Do not reopen or wait on a bare PID: is_running checks the
                # captured psutil identity and treats PID reuse as stopped.
                if descendant.is_running():
                    remaining.append(descendant)
            except Exception as error:
                measurements.error("observed_descendant_status_unavailable", error)
        if not remaining:
            return
        if time.monotonic() >= deadline:
            measurements.error("observed_descendant_cleanup_incomplete")
            return
        pending = remaining
        time.sleep(0.01)


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
                        cast(_PosixOS, os).killpg(process.pid, cast(_PosixSignals, signal).SIGKILL)
                    except ProcessLookupError:
                        pass
                    except OSError as error:
                        measurements.error("process_group_kill_failed", error)
                        process.kill()
                else:
                    process.kill()
            _kill_observed_descendants(measurements)
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
        launch_command, environment = _windows_venv_base_launch(command, environment)
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
                    launch_command,
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
        except Exception:
            if _child_exited(process):
                # The owned process identity can disappear between the exit check
                # and this final probe. Earlier rounds remain the declared sampled,
                # non-atomic descendant coverage; this normal race is not a failed
                # resource observation.
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
