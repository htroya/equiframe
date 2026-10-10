#!/usr/bin/env python3
"""Execute one native OS/architecture/Python universality cell and inventory its evidence."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from contextlib import suppress
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised by the Python 3.10 cells
    import tomli as tomllib


CORE_PROFILES = ("base", "arrow", "pandas", "polars", "duckdb", "engines", "ml", "all")
BENCHMARK_PROFILES = ("base", "engines", "ml", "resources", "all")
ENDPOINTS = ("minimum", "latest")
SHA256 = re.compile(r"[0-9a-f]{64}")
GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
REPOSITORY_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
PINNED_TOOLCHAIN = {"uv": "0.12.19", "packaging": "26.3", "tomli": "2.3.0"}
PINNED_BUILD_FRONTEND = "1.3.0"
EXPECTED_BUILD_BACKEND = "hatchling.build"
EXPECTED_BUILD_REQUIREMENTS = {"hatchling": "1.28.0"}
MAX_ARCHIVE_MEMBERS = 20_000
MAX_ARCHIVE_MEMBER_BYTES = 64 * 1024**2
MAX_ARCHIVE_TOTAL_BYTES = 512 * 1024**2
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
CONSUMER_PROGRAMS = ("reconciliation", "refactor", "migration", "preparation")
CONSUMER_DIRECTIONS = (
    ("pandas", "polars"),
    ("pandas", "duckdb"),
    ("polars", "pandas"),
    ("polars", "duckdb"),
    ("duckdb", "pandas"),
    ("duckdb", "polars"),
)
CONSUMER_VARIANTS = ("good", "defect", "not_evaluable")
CONSUMER_EXIT_CODES = {"good": 0, "defect": 1, "not_evaluable": 3}
CONSUMER_SUMMARY_NOTE = (
    "Expected nonzero exits never accept data; missing receipts/timeouts have unavailable "
    "native counts, not invented zeros"
)
EVIDENCE_RESERVE_SECONDS = 120
PROCESS_CLEANUP_GRACE_SECONDS = 15
PROCESS_POLL_SECONDS = 0.05
MEASUREMENT_CONTRACT_ID = "equiframe_process_resources_v1"
MEASUREMENT_METRICS = (
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
MEASUREMENT_PLATFORM = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}
MEASUREMENT_UNAVAILABLE = {
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

PROCESS_SENTINEL = r"""
import json
import os
import pathlib
import subprocess
import sys
import time

specification = pathlib.Path(sys.argv[1])
go = pathlib.Path(sys.argv[2])
result = pathlib.Path(sys.argv[3])
while not go.exists():
    time.sleep(0.01)
try:
    command = json.loads(specification.read_text(encoding="utf-8"))["command"]
    child = subprocess.Popen(command)
    outcome = {"returncode": child.wait()}
except BaseException as error:
    outcome = {
        "launcher_error": type(error).__name__,
        "message": str(error),
    }
temporary = result.with_suffix(result.suffix + ".partial")
temporary.write_text(json.dumps(outcome), encoding="utf-8")
os.replace(temporary, result)
# Keep the container leader alive until the controller has killed the complete group/job.
while True:
    time.sleep(60)
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_value(value: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return (
            isinstance(value, dict)
            and set(value) == set(expected)
            and all(exact_value(value[name], item) for name, item in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(value, list)
            and len(value) == len(expected)
            and all(
                exact_value(observed, item) for observed, item in zip(value, expected, strict=True)
            )
        )
    return type(value) is type(expected) and value == expected


def _measurement_architecture(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.casefold()
    if lowered in {"amd64", "x86_64", "x64"}:
        return "x64"
    if lowered in {"aarch64", "arm64"}:
        return "arm64"
    return None


def _nonnegative_number(value: object, *, integer: bool = False) -> bool:
    if integer:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _verify_measurement_metrics(
    contract: object, process: dict[str, Any], expected_platform: str
) -> None:
    if not isinstance(contract, dict) or set(contract) != {"id", "platform", "metrics"}:
        raise ValueError("measurement metric contract fields differ")
    metrics = contract.get("metrics")
    if (
        contract.get("id") != MEASUREMENT_CONTRACT_ID
        or contract.get("platform") != expected_platform
        or not isinstance(metrics, list)
        or len(metrics) != len(MEASUREMENT_METRICS)
        or process.get("measurement_contract") != MEASUREMENT_CONTRACT_ID
        or process.get("measurement_platform") != expected_platform
        or not exact_value(process.get("metric_coverage"), metrics)
    ):
        raise ValueError("measurement metric contract identity differs")
    fixed_sources = {
        "sampled_rss_peak_bytes": "psutil_process_memory_info_rss",
        "cpu_user_seconds": "psutil_process_cpu_times_user",
        "cpu_system_seconds": "psutil_process_cpu_times_system",
        "disk_apparent_peak_bytes": "filesystem_tree_stat_size",
        "disk_allocated_peak_bytes": "filesystem_tree_stat_blocks_512",
    }
    unavailable = MEASUREMENT_UNAVAILABLE[expected_platform]
    io_sources: set[str] = set()
    for expected_metric, item in zip(MEASUREMENT_METRICS, metrics, strict=True):
        if (
            not isinstance(item, dict)
            or set(item) != {"schema_version", "metric", "state", "source", "reason"}
            or item.get("schema_version") != "1.0"
            or item.get("metric") != expected_metric
        ):
            raise ValueError("measurement metric coverage order or fields differ")
        reason = unavailable.get(expected_metric)
        value = process.get(expected_metric)
        if reason is not None:
            if (
                not exact_value(
                    item,
                    {
                        "schema_version": "1.0",
                        "metric": expected_metric,
                        "state": "unavailable_on_platform",
                        "source": None,
                        "reason": reason,
                    },
                )
                or value is not None
            ):
                raise ValueError("measurement platform absence differs from its contract")
            continue
        if item.get("state") != "observed" or item.get("reason") is not None:
            raise ValueError("supported measurement metric was not observed")
        if expected_metric in fixed_sources:
            allowed_sources = {fixed_sources[expected_metric]}
        elif expected_platform == "linux":
            allowed_sources = {"psutil_process_io_counters", "linux_proc_pid_io"}
        elif expected_platform == "windows":
            allowed_sources = {"psutil_process_io_counters"}
        else:
            allowed_sources = set()
        source = item.get("source")
        if source not in allowed_sources:
            raise ValueError("measurement metric source differs from its platform contract")
        if expected_metric.startswith("io_"):
            io_sources.add(source)
        if not _nonnegative_number(
            value,
            integer=expected_metric.endswith(("_bytes", "_chars")),
        ):
            raise ValueError("observed measurement metric has no actual nonnegative value")
    if len(io_sources) > 1:
        raise ValueError("measurement mixed distinct process I/O sources")
    expected_counter_source = (
        "unavailable"
        if not io_sources
        else "psutil"
        if io_sources == {"psutil_process_io_counters"}
        else "linux_proc_pid_io"
    )
    fallback = process.get("io_counter_fallback_reason")
    if (
        process.get("io_counter_source") != expected_counter_source
        or (
            expected_counter_source == "linux_proc_pid_io"
            and (
                not isinstance(fallback, str)
                or not fallback.startswith("psutil_io_counters_unavailable:")
            )
        )
        or (expected_counter_source != "linux_proc_pid_io" and fallback is not None)
    ):
        raise ValueError("measurement I/O source binding differs")


def verify_measurement_documents(
    protocol: dict[str, Any],
    summary: dict[str, Any],
    bounded_limit: dict[str, Any],
    *,
    requested_system: str,
    requested_architecture: str,
    requested_python: str,
) -> None:
    expected_platform = MEASUREMENT_PLATFORM.get(requested_system)
    if expected_platform is None or requested_architecture not in {"x64", "arm64"}:
        raise ValueError("measurement requested platform is unsupported")
    protocol_fields = {
        "rows",
        "width",
        "repetitions",
        "rss_budget_bytes",
        "disk_budget_bytes",
        "timeout_seconds",
        "supervisor_sample_interval_seconds",
        "threads_per_engine",
        "expected_state",
        "storage",
        "filesystem_observed",
        "filesystem_observation",
        "resource_measurement_contract",
        "concurrent_known_loads",
        "os_cache",
        "slo_accepted",
        "scope",
        "python",
        "machine",
        "executable",
    }
    expected_protocol = {
        "rows": [100, 1000],
        "width": 2,
        "repetitions": 3,
        "rss_budget_bytes": 512 * 1024**2,
        "disk_budget_bytes": 64 * 1024**2,
        "timeout_seconds": 120,
        "supervisor_sample_interval_seconds": 0.25,
        "threads_per_engine": 1,
        "expected_state": "different",
        "storage": "disk",
        "resource_measurement_contract": {
            "id": MEASUREMENT_CONTRACT_ID,
            "platform": expected_platform,
        },
        "concurrent_known_loads": ("No other task-controlled suite; shared host not controlled"),
        "os_cache": "uncontrolled",
        "slo_accepted": False,
        "scope": ("local synthetic capture/compare/evidence; no network transport or VM claim"),
    }
    if set(protocol) != protocol_fields or any(
        not exact_value(protocol.get(name), value) for name, value in expected_protocol.items()
    ):
        raise ValueError("measurement protocol fields or fixed controls differ")
    python_version = protocol.get("python")
    if (
        not isinstance(python_version, str)
        or re.fullmatch(rf"{re.escape(requested_python)}\.\d+[A-Za-z0-9.+-]*", python_version)
        is None
        or _measurement_architecture(protocol.get("machine")) != requested_architecture
        or not isinstance(protocol.get("executable"), str)
        or not protocol["executable"]
    ):
        raise ValueError("measurement runtime identity differs from the requested cell")
    filesystem = protocol.get("filesystem_observation")
    methods = {
        "Linux": ("linux_proc_self_mountinfo", "current_mount_namespace"),
        "Windows": (
            "windows_get_volume_information_and_drive_type",
            {"fixed", "remote", "removable"},
        ),
        "Darwin": ("macos_sbin_mount_table", "mount_table_filesystem_type"),
    }
    expected_method, expected_backing = methods[requested_system]
    if (
        not isinstance(filesystem, dict)
        or set(filesystem)
        != {
            "filesystem",
            "storage",
            "method",
            "mount_point",
            "backing_kind",
            "limitations",
        }
        or filesystem.get("filesystem") != protocol.get("filesystem_observed")
        or not isinstance(filesystem.get("filesystem"), str)
        or not filesystem["filesystem"]
        or filesystem.get("storage") != "disk"
        or filesystem.get("method") != expected_method
        or (
            filesystem.get("backing_kind") not in expected_backing
            if isinstance(expected_backing, set)
            else filesystem.get("backing_kind") != expected_backing
        )
        or not isinstance(filesystem.get("mount_point"), str)
        or not filesystem["mount_point"]
        or not isinstance(filesystem.get("limitations"), list)
        or not filesystem["limitations"]
        or any(not isinstance(item, str) or not item for item in filesystem["limitations"])
    ):
        raise ValueError("measurement filesystem observation differs from the platform contract")
    if set(summary) != {"protocol", "results"} or not exact_value(
        summary.get("protocol"), protocol
    ):
        raise ValueError("measurement summary protocol differs from protocol.json")
    results = summary.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise ValueError("measurement summary must contain exactly two sizes")
    result_fields = {
        "run_id",
        "case_id",
        "complete",
        "resource_measurement_complete",
        "resource_measurement_contract",
        "requested_repetitions",
        "observed_repetitions",
        "correct_complete_repetitions",
        "unsuccessful_or_missing_repetitions",
        "resource_quality",
        "process",
        "statistics_by_cache",
        "issues",
    }
    for rows, result in zip((100, 1000), results, strict=True):
        if (
            not isinstance(result, dict)
            or set(result) != result_fields
            or not isinstance(result.get("run_id"), str)
            or re.fullmatch(r"scale-[0-9a-f]{32}", result["run_id"]) is None
            or result.get("case_id") != f"maturity-{rows}"
            or result.get("complete") is not True
            or result.get("resource_measurement_complete") is not True
            or result.get("requested_repetitions") != 3
            or result.get("observed_repetitions") != 3
            or result.get("correct_complete_repetitions") != 3
            or result.get("unsuccessful_or_missing_repetitions") != 0
            or result.get("resource_quality") != ["complete", "complete", "complete"]
            or result.get("issues") != []
        ):
            raise ValueError("measurement result counts or completion state differ")
        process = result.get("process")
        required_process_fields = set(MEASUREMENT_METRICS) | {
            "pid",
            "exit_code",
            "termination_reason",
            "wall_seconds",
            "io_counter_source",
            "io_counter_fallback_reason",
            "measurement_contract",
            "measurement_platform",
            "metric_coverage",
            "sample_interval_seconds",
            "max_sample_gap_seconds",
            "sample_count",
            "monitoring_errors",
            "cleanup_reaped",
            "observed_descendant_pids",
            "resource_scope",
            "termination_scope",
            "rss_method",
            "counter_method",
            "disk_method",
            "budget_method",
        }
        expected_termination_scope = (
            "direct_child" if requested_system == "Windows" else "posix_process_group"
        )
        if (
            not isinstance(process, dict)
            or not required_process_fields <= set(process)
            or type(process.get("pid")) is not int
            or process["pid"] <= 0
            or process.get("exit_code") != 0
            or process.get("termination_reason") != "exited"
            or not _nonnegative_number(process.get("wall_seconds"))
            or process.get("sample_interval_seconds") != 0.25
            or not _nonnegative_number(process.get("max_sample_gap_seconds"))
            or process["max_sample_gap_seconds"] > 0.5
            or type(process.get("sample_count")) is not int
            or process["sample_count"] < 2
            or process.get("monitoring_errors") != []
            or process.get("cleanup_reaped") is not True
            or process.get("observed_descendant_pids") != []
            or process.get("resource_scope") != "direct_child_excluding_descendants"
            or process.get("termination_scope") != expected_termination_scope
            or process.get("rss_method") != "sampled_absolute_lower_bound"
            or process.get("counter_method") != "sampled_cumulative_last_available"
            or process.get("disk_method") != "sampled_tree_inodes_no_symlink_following"
            or process.get("budget_method") != "reactive_sampled_thresholds_not_hard_quotas"
        ):
            raise ValueError("measurement process observation is incomplete")
        _verify_measurement_metrics(
            result.get("resource_measurement_contract"), process, expected_platform
        )
        statistics = result.get("statistics_by_cache")
        if (
            not isinstance(statistics, dict)
            or set(statistics)
            != {
                "fresh_process_os_cache_uncontrolled",
                "warm_process_os_cache_uncontrolled",
            }
            or not isinstance(statistics["fresh_process_os_cache_uncontrolled"], dict)
            or statistics["fresh_process_os_cache_uncontrolled"].get("n") != 1
            or not isinstance(statistics["warm_process_os_cache_uncontrolled"], dict)
            or statistics["warm_process_os_cache_uncontrolled"].get("n") != 2
        ):
            raise ValueError("measurement cache repetition statistics differ")
    counts = bounded_limit.get("counts")
    options = bounded_limit.get("options")
    diagnostics = bounded_limit.get("diagnostics")
    if (
        bounded_limit.get("scope") != "output_schema"
        or bounded_limit.get("state") != "not_evaluable"
        or bounded_limit.get("complete") is not False
        or bounded_limit.get("reference") != "expected"
        or bounded_limit.get("strategy") != "pending"
        or bounded_limit.get("right") is not None
        or not isinstance(counts, dict)
        or counts.get("final") is not False
        or counts.get("difference_records") != 0
        or counts.get("contract_violations") != 0
        or not isinstance(options, dict)
        or options.get("max_rows") != 1
        or not isinstance(diagnostics, list)
        or len(diagnostics) != 1
        or not exact_value(
            diagnostics[0],
            {
                "code": "resource_exhausted",
                "message": "max_rows (combined inputs)",
                "side": "left",
                "exception_type": "ResourceLimitError",
            },
        )
    ):
        raise ValueError("bounded resource limit was not preserved as not_evaluable")


def file_record(path: Path) -> dict[str, object]:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"evidence member is not a regular file: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def distribution_inventory(name: str) -> dict[str, Any]:
    distribution = importlib.metadata.distribution(name)
    members = distribution.files
    if members is None or not members:
        raise RuntimeError(f"installed distribution has no file inventory: {name}")
    files: dict[str, dict[str, object]] = {}
    folded: set[str] = set()
    for member in sorted(members, key=lambda item: item.as_posix()):
        relative = member.as_posix()
        if not relative or "\\" in relative or any(ord(character) < 32 for character in relative):
            raise RuntimeError(f"installed distribution has a malformed member: {name}")
        canonical = relative.casefold()
        if canonical in folded:
            raise RuntimeError(f"installed distribution has colliding members: {name}")
        folded.add(canonical)
        path = Path(str(distribution.locate_file(member)))
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise RuntimeError(f"installed distribution member is not a regular file: {name}")
        files[relative] = file_record(path)
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "name": canonicalize_name(distribution.metadata["Name"]),
        "version": distribution.version,
        "file_count": len(files),
        "files_sha256": hashlib.sha256(encoded).hexdigest(),
        "files": files,
    }


def read_object(path: Path) -> dict[str, Any]:
    loaded: object = json.loads(path.read_text("utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"JSON root is not an object: {path}")
    return cast(dict[str, Any], loaded)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(temporary, path)


def remove_tree(path: Path) -> None:
    if not path.exists():
        return

    def retry(function: Any, target: str, _info: object) -> None:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        function(target)

    shutil.rmtree(path, onerror=retry)


def clean_environment() -> dict[str, str]:
    # A denylist cannot cover credential names such as AWS_ACCESS_KEY_ID, GH_PAT,
    # SSH_AUTH_SOCK, or future provider-specific variables.  Native test processes
    # receive only the small operating-system surface needed to launch tools, use
    # temporary/home directories, select a locale, and locate public CA bundles.
    allowed = {
        "APPDATA",
        "COLORTERM",
        "COMMONPROGRAMFILES",
        "COMMONPROGRAMFILES(X86)",
        "COMMONPROGRAMW6432",
        "COMSPEC",
        "CURL_CA_BUNDLE",
        "DEVELOPER_DIR",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOCALAPPDATA",
        "MACOSX_DEPLOYMENT_TARGET",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "REQUESTS_CA_BUNDLE",
        "SDKROOT",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "TMPDIR",
        "TZ",
        "USERPROFILE",
        "WINDIR",
    }
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        UV_NO_CONFIG="1",
        UV_PYTHON_DOWNLOADS="never",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        POLARS_MAX_THREADS="1",
    )
    return environment


class CellDeadlineExceeded(RuntimeError):
    """Stop the cell early enough to inventory and upload its failure evidence."""


class ProcessTreeCleanupError(RuntimeError):
    """A contained command left processes that could not be proven terminated."""


class _WindowsJob:
    """Minimal Windows Job Object wrapper with fail-closed process accounting."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class BasicAccountingInformation(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
        ]
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            kernel32.CloseHandle(handle)
            raise error
        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = kernel32
        self._accounting_type = BasicAccountingInformation
        self._handle = handle

    def assign(self, process: subprocess.Popen[Any]) -> None:
        process_handle = self._wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        if not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            raise self._ctypes.WinError(self._ctypes.get_last_error())

    def terminate(self) -> None:
        if self._handle and not self._kernel32.TerminateJobObject(self._handle, 1):
            raise self._ctypes.WinError(self._ctypes.get_last_error())

    def active_processes(self) -> int:
        accounting = self._accounting_type()
        if not self._kernel32.QueryInformationJobObject(
            self._handle,
            1,
            self._ctypes.byref(accounting),
            self._ctypes.sizeof(accounting),
            None,
        ):
            raise self._ctypes.WinError(self._ctypes.get_last_error())
        return int(accounting.ActiveProcesses)

    def close(self) -> None:
        if self._handle:
            handle, self._handle = self._handle, None
            if not self._kernel32.CloseHandle(handle):
                raise self._ctypes.WinError(self._ctypes.get_last_error())


def _wait_for_contained_result(
    process: subprocess.Popen[Any], result: Path, timeout: int
) -> tuple[dict[str, Any] | None, bool]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result.is_file():
            loaded: object = json.loads(result.read_text("utf-8"))
            if not isinstance(loaded, dict):
                raise RuntimeError("process sentinel returned a malformed result")
            return cast(dict[str, Any], loaded), False
        time.sleep(min(PROCESS_POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    return None, True


def _posix_group_members(process_group: int) -> list[tuple[int, str]]:
    ps = shutil.which("ps")
    if ps is None:
        raise ProcessTreeCleanupError("ps is unavailable for process-group verification")
    observed = subprocess.run(
        [ps, "-axo", "pid=,pgid=,stat="],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if observed.returncode != 0:
        raise ProcessTreeCleanupError("cannot enumerate the contained POSIX process group")
    members: list[tuple[int, str]] = []
    for raw in observed.stdout.splitlines():
        fields = raw.split(None, 2)
        if len(fields) != 3:
            continue
        try:
            pid, group = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        if group == process_group:
            members.append((pid, fields[2]))
    return members


def _cleanup_posix_group(process: subprocess.Popen[Any]) -> None:
    kill_error: Exception | None = None
    try:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)  # type: ignore[attr-defined]
    except Exception as error:
        kill_error = error
        with suppress(Exception):
            process.kill()
    deadline = time.monotonic() + PROCESS_CLEANUP_GRACE_SECONDS
    active: list[tuple[int, str]] = []
    verification_error = kill_error
    try:
        while time.monotonic() < deadline:
            active = [
                member
                for member in _posix_group_members(process.pid)
                if member[0] != process.pid and not member[1].startswith("Z")
            ]
            if not active:
                break
            time.sleep(PROCESS_POLL_SECONDS)
    except Exception as error:
        verification_error = error
    try:
        process.wait(timeout=PROCESS_CLEANUP_GRACE_SECONDS)
    except Exception as error:
        verification_error = verification_error or error
    if verification_error is not None:
        raise ProcessTreeCleanupError("POSIX process-group cleanup could not be verified") from (
            verification_error
        )
    if active:
        raise ProcessTreeCleanupError(
            f"process group {process.pid} retained active members: {active}"
        )
    remaining = [
        member for member in _posix_group_members(process.pid) if not member[1].startswith("Z")
    ]
    if remaining:
        raise ProcessTreeCleanupError(
            f"process group {process.pid} retained members after leader reap: {remaining}"
        )


def _cleanup_windows_job(process: subprocess.Popen[Any], job: _WindowsJob) -> None:
    cleanup_error: Exception | None = None
    try:
        job.terminate()
    except Exception as error:
        cleanup_error = error
    deadline = time.monotonic() + PROCESS_CLEANUP_GRACE_SECONDS
    remaining = -1
    try:
        while True:
            remaining = job.active_processes()
            if remaining == 0 or time.monotonic() >= deadline:
                break
            time.sleep(PROCESS_POLL_SECONDS)
    except Exception as error:
        cleanup_error = cleanup_error or error
    try:
        job.close()
    except Exception as error:
        cleanup_error = cleanup_error or error
    try:
        process.wait(timeout=PROCESS_CLEANUP_GRACE_SECONDS)
    except Exception as error:
        cleanup_error = cleanup_error or error
    if cleanup_error is not None:
        raise ProcessTreeCleanupError("Windows process job cleanup failed") from cleanup_error
    if remaining != 0:
        raise ProcessTreeCleanupError(
            f"Windows process job retained {remaining} active process(es)"
        )


def run_contained_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    stdout: Any,
    stderr: Any,
    timeout: int,
    control: Path,
) -> int:
    """Run a command in an owned process container and prove the tree was removed."""
    control.mkdir(parents=True)
    specification = control / "command.json"
    go = control / "go"
    result = control / "result.json"
    write_json(specification, {"command": command})
    sentinel = [
        sys.executable,
        "-I",
        "-c",
        PROCESS_SENTINEL,
        str(specification),
        str(go),
        str(result),
    ]
    process: subprocess.Popen[Any] | None = None
    job: _WindowsJob | None = None
    outcome: dict[str, Any] | None = None
    timed_out = False
    cleanup_error: Exception | None = None
    try:
        options: dict[str, Any] = {
            "cwd": cwd,
            "env": environment,
            "stdout": stdout,
            "stderr": stderr,
        }
        if os.name == "nt":
            options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            job = _WindowsJob()
        else:
            options["start_new_session"] = True
        process = subprocess.Popen(sentinel, **options)
        if job is not None:
            try:
                job.assign(process)
            except Exception:
                process.terminate()
                process.wait(timeout=PROCESS_CLEANUP_GRACE_SECONDS)
                raise
        go.write_text("assigned\n", "utf-8")
        outcome, timed_out = _wait_for_contained_result(process, result, timeout)
    finally:
        if process is not None:
            try:
                if job is None:
                    _cleanup_posix_group(process)
                else:
                    _cleanup_windows_job(process, job)
            except Exception as error:
                cleanup_error = error
        elif job is not None:
            try:
                job.close()
            except Exception as error:
                cleanup_error = error
        try:
            remove_tree(control)
        except Exception as error:
            cleanup_error = cleanup_error or error
    if cleanup_error is not None:
        raise ProcessTreeCleanupError("contained process tree cleanup failed") from cleanup_error
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout)
    if outcome is None:
        raise RuntimeError("process sentinel did not return an outcome")
    if "launcher_error" in outcome:
        raise RuntimeError(
            f"process sentinel could not launch command: {outcome['launcher_error']}: "
            f"{outcome.get('message', '')}"
        )
    return int(outcome["returncode"])


class Recorder:
    def __init__(
        self,
        output: Path,
        receipt: dict[str, Any],
        *,
        deadline_monotonic: float,
        evidence_reserve_seconds: int = EVIDENCE_RESERVE_SECONDS,
    ) -> None:
        self.output = output
        self.receipt = receipt
        self.deadline_monotonic = deadline_monotonic
        self.evidence_reserve_seconds = evidence_reserve_seconds
        self.logs = output / "logs"
        self.logs.mkdir()
        self.environment = clean_environment()
        self.save()

    def save(self) -> None:
        write_json(self.output / "receipt.json", self.receipt)

    def require_work_window(self, operation: str, minimum_seconds: int = 1) -> float:
        remaining = self.deadline_monotonic - time.monotonic()
        usable = remaining - self.evidence_reserve_seconds
        if usable < minimum_seconds:
            raise CellDeadlineExceeded(
                f"insufficient work window before evidence reserve for {operation}: "
                f"{max(0.0, usable):.1f}s available"
            )
        return usable

    def run(
        self,
        label: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        expected: int = 0,
        timeout: int = 3600,
    ) -> subprocess.CompletedProcess[str]:
        index = len(self.receipt["commands"])
        stdout = self.logs / f"{index:03d}-{label}.stdout.log"
        stderr = self.logs / f"{index:03d}-{label}.stderr.log"
        entry: dict[str, Any] = {
            "label": label,
            "command": command,
            "cwd": str((cwd or self.output).resolve()),
            "expected_exit": expected,
            "started_at": now(),
            "requested_timeout_seconds": timeout,
            "stdout": stdout.relative_to(self.output).as_posix(),
            "stderr": stderr.relative_to(self.output).as_posix(),
            "status": "running",
            "process_container": (
                "windows-job-object-kill-on-close"
                if os.name == "nt"
                else "posix-new-session-process-group"
            ),
        }
        self.receipt["commands"].append(entry)
        self.save()
        started = time.monotonic()
        try:
            remaining = self.require_work_window(label)
            effective_timeout = max(1, min(timeout, int(remaining)))
            deadline_limited = effective_timeout < timeout
            entry["timeout_seconds"] = effective_timeout
            entry["deadline_limited"] = deadline_limited
            free = shutil.disk_usage(self.output).free
            entry["disk_free_before_bytes"] = free
            if free < 2 * 1024**3:
                raise RuntimeError("less than 2 GiB free before the next command")
            control = self.logs / ".process-control" / f"{index:03d}"
            with (
                stdout.open("w", encoding="utf-8", errors="replace") as stdout_stream,
                stderr.open("w", encoding="utf-8", errors="replace") as stderr_stream,
            ):
                returncode = run_contained_process(
                    command,
                    cwd=cwd or self.output,
                    environment=self.environment,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    timeout=effective_timeout,
                    control=control,
                )
            completed = subprocess.CompletedProcess(
                command,
                returncode,
                stdout.read_text("utf-8", errors="replace"),
                stderr.read_text("utf-8", errors="replace"),
            )
            entry.update(
                exit_code=completed.returncode,
                status="passed" if completed.returncode == expected else "failed",
                process_tree_cleanup="passed",
            )
        except subprocess.TimeoutExpired as error:
            out = (
                error.stdout.decode("utf-8", "replace")
                if isinstance(error.stdout, bytes)
                else error.stdout
            )
            err = (
                error.stderr.decode("utf-8", "replace")
                if isinstance(error.stderr, bytes)
                else error.stderr
            )
            stdout.write_text(out or "", "utf-8")
            stderr.write_text(err or "", "utf-8")
            entry.update(
                exit_code=None,
                status="timeout",
                error="TimeoutExpired",
                process_tree_cleanup="passed",
            )
            if deadline_limited:
                raise CellDeadlineExceeded(
                    f"{label} reached the native-cell evidence deadline"
                ) from error
            raise RuntimeError(f"{label} exceeded {effective_timeout} seconds") from error
        except ProcessTreeCleanupError as error:
            entry.update(
                exit_code=None,
                status="process_cleanup_failed",
                error=type(error).__name__,
                process_tree_cleanup="failed",
            )
            raise
        except Exception as error:
            if not stdout.exists():
                stdout.write_text("", "utf-8")
            if not stderr.exists():
                stderr.write_text(str(error) + "\n", "utf-8")
            entry.update(exit_code=None, status="failed_to_start", error=type(error).__name__)
            raise
        finally:
            entry.update(finished_at=now(), duration_seconds=time.monotonic() - started)
            if stdout.exists():
                entry["stdout_record"] = file_record(stdout)
            if stderr.exists():
                entry["stderr_record"] = file_record(stderr)
            self.save()
        if completed.returncode != expected:
            raise RuntimeError(
                f"{label} exited {completed.returncode}; expected {expected}; see {stderr}"
            )
        return completed


def checked_member(root: Path, relative: str) -> Path:
    if "\\" in relative:
        raise ValueError(f"nonportable candidate path: {relative}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError(f"unsafe candidate path: {relative}")
    path = root.joinpath(*pure.parts)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"candidate member is absent, linked or outside root: {relative}")
    return path


def verify_candidate(root: Path) -> dict[str, Any]:
    manifest_path = checked_member(root, "candidate.json")
    loaded: object = json.loads(manifest_path.read_text("utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("candidate manifest must be an object")
    candidate = cast(dict[str, Any], loaded)
    if candidate.get("schema") != "equiframe-universality-actions-candidate-1":
        raise ValueError("unsupported workflow candidate schema")
    if (
        candidate.get("credentials_included") is not False
        or candidate.get("results_included") is not False
    ):
        raise ValueError("candidate scope flags differ")
    files = candidate.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("candidate file inventory is absent")
    for name, expected in files.items():
        if not isinstance(expected, dict) or file_record(checked_member(root, name)) != expected:
            raise ValueError(f"candidate member bytes differ: {name}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path != manifest_path
    }
    if actual != set(files):
        raise ValueError("downloaded candidate inventory has missing or additional files")
    return candidate


def artifact(candidate_root: Path, candidate: dict[str, Any], package: str, kind: str) -> Path:
    record = candidate["artifacts"][package]
    path = checked_member(candidate_root, record[kind])
    if file_record(path) != record[kind + "_record"]:
        raise ValueError(f"{package} {kind} differs from its artifact record")
    return path


def candidate_test_manifest(
    candidate_root: Path, candidate: dict[str, Any], package: str
) -> tuple[Path, dict[str, Any], set[tuple[str, str]]]:
    expected_packages = {
        "core": "equiframe",
        "benchmark": "equiframe-benchmark",
        "consumer": "equiframe-consumer-lab",
    }
    manifests = candidate.get("test_manifests")
    if not isinstance(manifests, dict) or set(manifests) != set(expected_packages):
        raise ValueError("candidate test-manifest inventory differs")
    expected = manifests.get(package)
    if not isinstance(expected, dict) or set(expected) != {
        "path",
        "record",
        "test_count",
        "junit_identities_sha256",
        "pytest_version",
        "hypothesis_version",
    }:
        raise ValueError(f"candidate {package} test-manifest record differs")
    path = checked_member(candidate_root, expected["path"])
    if file_record(path) != expected["record"]:
        raise ValueError(f"candidate {package} test-manifest bytes differ")
    loaded: object = json.loads(path.read_text("utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"candidate {package} test manifest must be an object")
    tests = loaded.get("tests")
    if (
        loaded.get("schema") != "equiframe-test-manifest-1"
        or loaded.get("package") != expected_packages[package]
        or loaded.get("plugin_autoload_disabled") is not True
        or loaded.get("pytest_version") != expected["pytest_version"]
        or loaded.get("hypothesis_version") != expected["hypothesis_version"]
        or not isinstance(loaded.get("files"), dict)
        or not loaded["files"]
        or not isinstance(tests, list)
        or loaded.get("test_count") != len(tests)
        or expected["test_count"] != len(tests)
        or not tests
    ):
        raise ValueError(f"candidate {package} test manifest header differs")
    identities: list[tuple[str, str]] = []
    nodeids: list[str] = []
    for item in tests:
        if not isinstance(item, dict) or set(item) != {"nodeid", "classname", "name"}:
            raise ValueError(f"candidate {package} test identity differs")
        nodeid, classname, name = item["nodeid"], item["classname"], item["name"]
        if not all(isinstance(value, str) and value for value in (nodeid, classname, name)):
            raise ValueError(f"candidate {package} test identity is empty")
        nodeids.append(nodeid)
        identities.append((classname, name))
    if len(nodeids) != len(set(nodeids)) or len(identities) != len(set(identities)):
        raise ValueError(f"candidate {package} test identities are duplicated")
    encoded = json.dumps(sorted(identities), separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != expected["junit_identities_sha256"]:
        raise ValueError(f"candidate {package} JUnit identity digest differs")
    return path, expected, set(identities)


def portable_archive_parts(name: str) -> tuple[str, ...]:
    """Return a cross-platform-safe archive path or reject it fail-closed."""
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError(f"nonportable archive member: {name!r}")
    raw = name[:-1] if name.endswith("/") else name
    components = raw.split("/")
    if not raw or any(part in ("", ".", "..") for part in components):
        raise ValueError(f"unsafe archive member: {name!r}")
    if len(raw.encode("utf-8")) > 1024:
        raise ValueError(f"archive member path is too long: {name!r}")
    for part in components:
        if (
            unicodedata.normalize("NFC", part) != part
            or len(part.encode("utf-8")) > 255
            or part.endswith((" ", "."))
            or ":" in part
            or any(ord(character) < 32 or ord(character) == 127 for character in part)
            or part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
        ):
            raise ValueError(f"nonportable archive member: {name!r}")
    return tuple(components)


def portable_archive_inventory(names: list[str]) -> dict[str, tuple[str, ...]]:
    if not names or len(names) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("archive member count is empty or exceeds its bound")
    result: dict[str, tuple[str, ...]] = {}
    casefolded: dict[str, str] = {}
    for name in names:
        parts = portable_archive_parts(name)
        normalized = "/".join(parts)
        portable_key = unicodedata.normalize("NFC", normalized).casefold()
        if normalized in result or portable_key in casefolded:
            other = casefolded.get(portable_key, normalized)
            raise ValueError(f"archive paths collide portably: {other!r} and {name!r}")
        result[normalized] = parts
        casefolded[portable_key] = name
    return result


def extract_sdist(path: Path, destination: Path) -> Path:
    if destination.exists() or destination.is_symlink():
        raise ValueError("sdist extraction destination must be new")
    destination.mkdir(parents=True)
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            paths = portable_archive_inventory([member.name for member in members])
            total_size = 0
            for member in members:
                normalized = "/".join(portable_archive_parts(member.name))
                parts = paths[normalized]
                if not (member.isfile() or member.isdir()) or getattr(member, "sparse", None):
                    raise ValueError(f"sdist contains a link or special member: {member.name}")
                if member.size < 0 or member.size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise ValueError(f"sdist member exceeds its size bound: {member.name}")
                if member.isfile():
                    total_size += member.size
                    if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                        raise ValueError("sdist expanded bytes exceed their bound")
                target = destination.joinpath(*parts)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise ValueError(f"sdist member escapes extraction root: {member.name}")
                if member.isdir():
                    if target.exists() and not target.is_dir():
                        raise ValueError(f"sdist path changes type: {member.name}")
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    raise ValueError(f"sdist path is repeated: {member.name}")
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"cannot read sdist member: {member.name}")
                copied = 0
                with source, target.open("xb") as stream:
                    while True:
                        block = source.read(min(1024 * 1024, member.size - copied + 1))
                        if not block:
                            break
                        copied += len(block)
                        if copied > member.size:
                            raise ValueError(f"sdist member expands past its header: {member.name}")
                        stream.write(block)
                if copied != member.size:
                    raise ValueError(f"sdist member length differs from its header: {member.name}")
            roots = [item for item in destination.iterdir() if item.is_dir()]
        if len(roots) != 1 or any(not item.is_dir() for item in destination.iterdir()):
            raise ValueError(f"sdist must contain exactly one source root: {path.name}")
        return roots[0]
    except Exception:
        with suppress(Exception):
            remove_tree(destination)
        raise


def python_in(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def normalized_architecture(value: str) -> str:
    lowered = value.lower()
    if lowered in ("amd64", "x86_64"):
        return "x64"
    if lowered in ("arm64", "aarch64"):
        return "arm64"
    return lowered


def wheel_metadata(path: Path) -> Any:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError(f"expected one METADATA in {path.name}")
        return BytesParser().parsebytes(archive.read(names[0]))


def _urlsafe_sha256(value: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b"=").decode("ascii")


def wheel_payload(
    path: Path, *, expected_distribution: str, expected_version: str
) -> dict[str, Any]:
    """Validate one wheel and summarize its exact installed payload."""
    distribution, version, build_tag, filename_tags = parse_wheel_filename(path.name)
    expected_name = canonicalize_name(expected_distribution)
    if canonicalize_name(distribution) != expected_name or str(version) != expected_version:
        raise ValueError(f"wheel filename identity differs: {path.name}")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        paths = portable_archive_inventory([item.filename for item in infos])
        files: dict[str, dict[str, object]] = {}
        contents: dict[str, bytes] = {}
        total_size = 0
        for info in infos:
            normalized = "/".join(paths["/".join(portable_archive_parts(info.filename))])
            if info.flag_bits & 0x1:
                raise ValueError(f"wheel member is encrypted: {info.filename}")
            unix_type = (info.external_attr >> 16) & 0o170000
            if unix_type == stat.S_IFLNK or (
                unix_type not in (0, stat.S_IFREG, stat.S_IFDIR) and not info.is_dir()
            ):
                raise ValueError(f"wheel contains a link or special member: {info.filename}")
            if info.file_size < 0 or info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ValueError(f"wheel member exceeds its size bound: {info.filename}")
            if info.is_dir():
                continue
            total_size += info.file_size
            if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("wheel expanded bytes exceed their bound")
            value = archive.read(info)
            if len(value) != info.file_size:
                raise ValueError(f"wheel member length differs: {info.filename}")
            contents[normalized] = value
            files[normalized] = {
                "sha256": hashlib.sha256(value).hexdigest(),
                "size_bytes": len(value),
            }

    metadata_names = [name for name in files if name.endswith(".dist-info/METADATA")]
    wheel_names = [name for name in files if name.endswith(".dist-info/WHEEL")]
    record_names = [name for name in files if name.endswith(".dist-info/RECORD")]
    if not (len(metadata_names) == len(wheel_names) == len(record_names) == 1):
        raise ValueError(f"wheel metadata inventory differs: {path.name}")
    dist_info = metadata_names[0].rsplit("/", 1)[0]
    if (
        wheel_names[0].rsplit("/", 1)[0] != dist_info
        or record_names[0].rsplit("/", 1)[0] != dist_info
    ):
        raise ValueError(f"wheel dist-info roots differ: {path.name}")
    metadata = BytesParser().parsebytes(contents[metadata_names[0]])
    if (
        canonicalize_name(str(metadata.get("Name", ""))) != expected_name
        or str(metadata.get("Version", "")) != expected_version
    ):
        raise ValueError(f"wheel METADATA identity differs: {path.name}")
    wheel_document = BytesParser().parsebytes(contents[wheel_names[0]])
    metadata_tags = sorted(str(item) for item in wheel_document.get_all("Tag", []))
    if metadata_tags != sorted(str(item) for item in filename_tags):
        raise ValueError(f"wheel tag identity differs: {path.name}")

    rows = list(csv.reader(io.StringIO(contents[record_names[0]].decode("utf-8"))))
    if len(rows) != len(files) or any(len(row) != 3 for row in rows):
        raise ValueError(f"wheel RECORD inventory differs: {path.name}")
    observed_record_paths: set[str] = set()
    for name, encoded_hash, encoded_size in rows:
        normalized = "/".join(portable_archive_parts(name))
        if normalized in observed_record_paths or normalized not in files:
            raise ValueError(f"wheel RECORD path differs: {name}")
        observed_record_paths.add(normalized)
        if normalized == record_names[0]:
            if encoded_hash or encoded_size:
                raise ValueError(f"wheel RECORD self-entry is not empty: {path.name}")
            continue
        if encoded_hash != "sha256=" + _urlsafe_sha256(contents[normalized]):
            raise ValueError(f"wheel RECORD hash differs: {name}")
        if encoded_size != str(len(contents[normalized])):
            raise ValueError(f"wheel RECORD size differs: {name}")
    if observed_record_paths != set(files):
        raise ValueError(f"wheel RECORD omits payload members: {path.name}")

    installed_payload = {name: value for name, value in files.items() if name != record_names[0]}
    payload_bytes = json.dumps(installed_payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return {
        "distribution": expected_name,
        "version": expected_version,
        "build_tag": [str(item) for item in build_tag],
        "tags": metadata_tags,
        "member_count": len(files),
        "installed_member_count": len(installed_payload),
        "installed_payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "record_valid": True,
    }


def benchmark_requirements(core: Path, benchmark: Path, profile: str) -> list[str]:
    core_metadata, benchmark_metadata = wheel_metadata(core), wheel_metadata(benchmark)
    selected = (
        {"engines", "ml", "resources"}
        if profile == "all"
        else set()
        if profile == "base"
        else {profile}
    )
    marker_environment = {key: str(value) for key, value in default_environment().items()}
    core_extras: set[str] = set()
    result: set[str] = set()
    for metadata, extras in (
        (benchmark_metadata, selected),
        (core_metadata, core_extras),
    ):
        for raw in metadata.get_all("Requires-Dist", []):
            requirement = Requirement(raw)
            if requirement.marker is not None and not any(
                requirement.marker.evaluate({**marker_environment, "extra": extra})
                for extra in ("", *sorted(extras))
            ):
                continue
            if canonicalize_name(requirement.name) == "equiframe":
                if str(core_metadata["Version"]) not in requirement.specifier:
                    raise ValueError("benchmark requires a different core version")
                core_extras.update(requirement.extras)
                continue
            if requirement.url is not None:
                raise ValueError("direct URL requirements are not allowed in benchmark profiles")
            requirement.marker = None
            result.add(str(requirement))
    if not result:
        raise ValueError(f"empty benchmark runtime profile: {profile}")
    return sorted(result)


def parse_hashed_lock(path: Path) -> dict[str, str]:
    logical = path.read_text("utf-8").replace("\\\n", " ")
    result: dict[str, str] = {}
    for raw_line in logical.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        requirement = Requirement(parts[0])
        specifications = list(requirement.specifier)
        if (
            requirement.url is not None
            or requirement.marker is not None
            or requirement.extras
            or len(specifications) != 1
            or specifications[0].operator != "=="
            or "*" in specifications[0].version
            or len(parts) < 2
            or any(re.fullmatch(r"--hash=sha256:[a-f0-9]{64}", item) is None for item in parts[1:])
        ):
            raise ValueError("benchmark runtime lock is not exact and SHA-256 authenticated")
        name = canonicalize_name(requirement.name)
        if name in result:
            raise ValueError("benchmark runtime lock repeats a distribution")
        result[name] = specifications[0].version
    if not result:
        raise ValueError("benchmark runtime lock is empty")
    return result


def benchmark_skip_contract(system: str, python: str) -> set[tuple[str, str, str]]:
    classname = "tests.test_scale_process"
    windows_redirector = (
        classname,
        "test_windows_venv_redirector_runs_real_interpreter_as_owned_child",
        "Windows CPython venv redirector",
    )
    windows_environment_case = (
        classname,
        "test_windows_venv_redirect_bypass_replaces_all_launcher_variable_casings",
        "Windows environment names are case-insensitive",
    )
    posix_signal = (
        classname,
        "test_sigkill_preserves_missing_finalization",
        "POSIX signal exit-code convention",
    )
    nonreaping_wait = (
        classname,
        "test_private_group_is_killed_after_leader_exits_between_samples",
        "safe group cleanup after leader exit requires POSIX waitid(WNOWAIT)",
    )
    posix_group = (
        classname,
        "test_already_reaped_group_is_not_signaled_without_nonreaping_wait",
        "POSIX group-ID reuse safety",
    )
    linux_proc = (
        classname,
        "test_linux_proc_io_fallback_observes_the_owned_live_child",
        "Linux /proc process counters",
    )
    posix_links = (
        classname,
        "test_disk_usage_deduplicates_inodes_and_does_not_follow_symlinks",
        "POSIX hard links and symlinks",
    )
    if system == "Linux":
        return {windows_redirector, windows_environment_case}
    if system == "Windows":
        return {posix_signal, nonreaping_wait, posix_group, linux_proc, posix_links}
    if system == "Darwin":
        result = {windows_redirector, windows_environment_case, linux_proc}
        if python != "3.13":
            result.add(nonreaping_wait)
        return result
    raise ValueError(f"unsupported benchmark skip-contract system: {system}")


def skip_records(values: set[tuple[str, str, str]]) -> list[dict[str, str]]:
    return [
        {"classname": classname, "name": name, "message": message}
        for classname, name, message in sorted(values)
    ]


def core_skip_records(system: str) -> list[dict[str, str]]:
    if system == "Windows":
        return [
            {
                "class": "tests.test_report_io",
                "name": "test_special_evidence_file_rejected_before_open",
                "message": "FIFO unavailable",
            }
        ]
    if system in ("Linux", "Darwin"):
        return []
    raise ValueError(f"unsupported core skip-contract system: {system}")


def verify_core_suite_summary(
    value: object, system: str, expected_manifest: dict[str, Any] | None = None
) -> None:
    expected = core_skip_records(system)
    if (
        not isinstance(value, dict)
        or value.get("accepted") is not True
        or value.get("failures") != 0
        or value.get("errors") != 0
        or value.get("xfail") != 0
        or value.get("skipped") != len(expected)
        or value.get("expected_skips") != expected
        or value.get("observed_skips") != expected
        or not isinstance(value.get("tests"), int)
        or value["tests"] <= len(expected)
    ):
        raise RuntimeError("core installed-suite skip contract differs")
    if expected_manifest is not None and (
        value.get("tests") != expected_manifest["test_count"]
        or value.get("junit_identities_sha256") != expected_manifest["junit_identities_sha256"]
        or value.get("identity_contract_matches") is not True
    ):
        raise RuntimeError("core installed-suite test denominator differs")


def inspect_junit(
    path: Path,
    expected_skips: set[tuple[str, str, str]],
    expected_manifest: dict[str, Any],
    expected_identities: set[tuple[str, str]],
) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError(f"JUnit contains no test cases: {path}")
    observed_skips: list[tuple[str, str, str]] = []
    observed_identities: list[tuple[str, str]] = []
    for case in cases:
        classname, name = case.get("classname"), case.get("name")
        if not classname or not name:
            raise ValueError(f"JUnit test identity is incomplete: {path}")
        observed_identities.append((classname, name))
        skipped = case.find("skipped")
        if skipped is None:
            continue
        message = skipped.get("message")
        if message is None:
            raise ValueError(f"JUnit skip identity is incomplete: {path}")
        observed_skips.append((classname, name, message))
    skip_contract_matches = (
        len(observed_skips) == len(set(observed_skips)) and set(observed_skips) == expected_skips
    )
    encoded = json.dumps(sorted(observed_identities), separators=(",", ":")).encode("utf-8")
    identity_digest = hashlib.sha256(encoded).hexdigest()
    identity_contract_matches = (
        len(observed_identities) == len(set(observed_identities))
        and set(observed_identities) == expected_identities
        and len(observed_identities) == expected_manifest["test_count"]
        and identity_digest == expected_manifest["junit_identities_sha256"]
    )
    counts = {
        "tests": len(cases),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skipped": len(observed_skips),
        "expected_skips": skip_records(expected_skips),
        "observed_skips": skip_records(set(observed_skips)),
        "junit_identities_sha256": identity_digest,
        "identity_contract_matches": identity_contract_matches,
    }
    counts["accepted"] = (
        counts["failures"] == 0
        and counts["errors"] == 0
        and skip_contract_matches
        and identity_contract_matches
    )
    return counts


def verify_consumer_summary(
    value: object, consumer_version: str, *, optimized: bool = False
) -> None:
    summary_fields = {
        "consumer_version",
        "status",
        "planned_cases",
        "distinct_cases",
        "attempted_cases",
        "case_launch_attempts",
        "case_subprocesses",
        "completed_case_processes",
        "not_attempted_cases",
        "not_run_cases",
        "cases_with_valid_receipts",
        "native_execution_attempts",
        "recorded_native_executions",
        "cases_with_unavailable_native_count",
        "case_status_counts",
        "accepted_cases",
        "rejected_cases",
        "cases_with_unavailable_acceptance",
        "optimization_required",
        "optimized",
        "all_expected_outcomes_observed",
        "terminal_errors",
        "note",
        "records",
    }
    expected_summary = {
        "consumer_version": consumer_version,
        "status": "PASS",
        "planned_cases": 72,
        "distinct_cases": 72,
        "attempted_cases": 72,
        "case_launch_attempts": 72,
        "case_subprocesses": 72,
        "completed_case_processes": 72,
        "not_attempted_cases": 0,
        "not_run_cases": 0,
        "cases_with_valid_receipts": 72,
        "native_execution_attempts": 144,
        "recorded_native_executions": 144,
        "cases_with_unavailable_native_count": 0,
        "case_status_counts": {"PASS": 24, "EXPECTED_REJECTION": 48, "FAIL": 0},
        "accepted_cases": 24,
        "rejected_cases": 48,
        "cases_with_unavailable_acceptance": 0,
        "optimization_required": optimized,
        "optimized": optimized,
        "all_expected_outcomes_observed": True,
        "terminal_errors": [],
        "note": CONSUMER_SUMMARY_NOTE,
    }
    if (
        not isinstance(value, dict)
        or set(value) != summary_fields
        or any(
            not exact_value(value.get(name), expected)
            for name, expected in expected_summary.items()
        )
    ):
        raise RuntimeError("consumer 72-case summary fields or totals differ")
    records = value["records"]
    if not isinstance(records, list) or len(records) != 72:
        raise RuntimeError("consumer 72-case record count differs")
    expected_cases = [
        (program, variant, source, target)
        for program in CONSUMER_PROGRAMS
        for source, target in CONSUMER_DIRECTIONS
        for variant in CONSUMER_VARIANTS
    ]
    record_fields = {
        "case_id",
        "program",
        "variant",
        "source",
        "target",
        "command",
        "expected_exit",
        "actual_exit",
        "process_outcome",
        "process_error",
        "receipt_error",
        "logs_error",
        "unwritten_stdout",
        "unwritten_stderr",
        "accepted",
        "published",
        "status",
        "harness_pass",
        "elapsed_seconds",
        "case_receipt",
    }
    interpreter: str | None = None
    data_root: str | None = None
    output_root: str | None = None
    for index, (record, expected_case) in enumerate(zip(records, expected_cases, strict=True), 1):
        if not isinstance(record, dict) or set(record) != record_fields:
            raise RuntimeError(f"consumer case {index:03d} fields differ")
        program, variant, source, target = expected_case
        case_id = f"{index:03d}-{program}-{source}-{target}-{variant}"
        accepted = variant == "good"
        expected_exit = CONSUMER_EXIT_CODES[variant]
        expected_values = {
            "case_id": case_id,
            "program": program,
            "variant": variant,
            "source": source,
            "target": target,
            "expected_exit": expected_exit,
            "actual_exit": expected_exit,
            "process_outcome": "completed",
            "process_error": None,
            "receipt_error": None,
            "logs_error": None,
            "unwritten_stdout": None,
            "unwritten_stderr": None,
            "accepted": accepted,
            "published": accepted,
            "status": "PASS" if accepted else "EXPECTED_REJECTION",
            "harness_pass": True,
            "case_receipt": f"cases/{case_id}/case.json",
        }
        if any(
            not exact_value(record.get(name), expected)
            for name, expected in expected_values.items()
        ):
            raise RuntimeError(f"consumer case {case_id} outcome differs")
        elapsed = record["elapsed_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise RuntimeError(f"consumer case {case_id} elapsed time differs")
        command = record["command"]
        command_prefix = [
            "-I",
            *(["-O"] if optimized else []),
            "-m",
            "equiframe_consumer_lab",
            "run",
            "--program",
            program,
            "--variant",
            variant,
            "--source",
            source,
            "--target",
            target,
            "--data",
        ]
        data_index = 1 + len(command_prefix)
        output_flag_index = data_index + 1
        output_path_index = data_index + 2
        if (
            not isinstance(command, list)
            or len(command) != output_path_index + 1
            or not all(isinstance(argument, str) and "\x00" not in argument for argument in command)
            or command[1:data_index] != command_prefix
            or command[output_flag_index] != "--output"
            or not command[0]
            or not command[data_index]
            or not command[output_path_index]
        ):
            raise RuntimeError(f"consumer case {case_id} command differs")
        normalized_output = command[output_path_index].replace("\\", "/")
        suffix = f"/cases/{case_id}"
        if not normalized_output.endswith(suffix):
            raise RuntimeError(f"consumer case {case_id} output path differs")
        current_output_root = normalized_output[: -len(suffix)]
        expected_output_suffix = "/consumer-72-optimized" if optimized else "/consumer-72"
        if not current_output_root.endswith(expected_output_suffix):
            raise RuntimeError(f"consumer case {case_id} matrix output root differs")
        if interpreter is None:
            interpreter = command[0]
            data_root = command[data_index]
            output_root = current_output_root
        elif (
            command[0] != interpreter
            or command[data_index] != data_root
            or current_output_root != output_root
        ):
            raise RuntimeError("consumer case commands do not share one execution context")


def verify_fault_checks(value: object) -> None:
    if not isinstance(value, dict):
        raise RuntimeError("consumer fault receipt is not an object")
    environment = value.get("environment")
    checks = value.get("checks")
    if (
        set(value) != {"status", "environment", "synthetic_fixture", "checks"}
        or value.get("status") != "PASS"
        or value.get("synthetic_fixture") is not True
        or not isinstance(environment, dict)
        or type(environment.get("isolated")) is not int
        or environment["isolated"] != 1
        or type(environment.get("optimized")) is not int
        or environment["optimized"] != 1
        or not isinstance(checks, list)
        or len(checks) != 6
        or not all(isinstance(item, dict) for item in checks)
    ):
        raise RuntimeError("consumer optimized fault receipt header differs")
    expected_checks = [
        {"case": "accept", "state": "equivalent", "accepted": True, "error": None},
        {
            "case": "compensated_reject",
            "state": "different",
            "accepted": False,
            "error": "EquivalenceAssertionError",
        },
        {
            "case": "budget_reject",
            "state": "not_evaluable",
            "accepted": False,
            "error": "EquivalenceAssertionError",
        },
        {
            "case": "rejected_input",
            "prior_publication_preserved": True,
            "staging_clean": True,
        },
        {
            "case": "write_fault",
            "prior_publication_preserved": True,
            "staging_clean": True,
        },
        {"case": "report_corruption", "rejected": True},
    ]
    if not exact_value(checks, expected_checks):
        raise RuntimeError("consumer optimized fault fields or states differ")


def verify_h_summary(
    value: object,
    scenario: str,
    expected_exit: int,
    *,
    bundle_manifest: Path | None = None,
) -> None:
    if not isinstance(value, dict):
        raise RuntimeError(f"optimized H {scenario} summary is not an object")
    expected_top = {
        "journey": "H",
        "synthetic": True,
        "scenario": scenario,
        "accepted": scenario == "good",
        "exit_code": expected_exit,
        "integrity": "rejected" if scenario == "error" else "passed",
        "report_created": scenario != "error",
        "original_paths_available": False,
    }
    if any(value.get(name) != expected for name, expected in expected_top.items()):
        raise RuntimeError(f"optimized H {scenario} summary header differs")
    if scenario == "error":
        if set(value) != set(expected_top):
            raise RuntimeError("optimized H error summary has an unexpected field set")
        return
    comparison_expectation = tuple[str, bool, bool, bool, int, int, list[str]]
    expected_states: dict[str, tuple[str, list[comparison_expectation]]] = {
        "good": (
            "passed",
            [
                ("equivalent", True, True, True, 0, 0, []),
                ("equivalent", True, True, True, 0, 0, []),
            ],
        ),
        "different": (
            "failed",
            [
                ("equivalent", True, True, True, 0, 0, []),
                ("different", True, True, False, 1, 1, []),
            ],
        ),
        "not_evaluable": (
            "not_evaluable",
            [
                ("not_evaluable", False, False, False, 3, 0, ["resource_exhausted"]),
                ("not_evaluable", False, False, False, 3, 0, ["resource_exhausted"]),
            ],
        ),
    }
    operational_state, expected_comparisons = expected_states[scenario]
    if (
        set(value)
        != set(expected_top)
        | {
            "operational_state",
            "independent_review",
            "bundle_manifest_sha256",
            "comparisons",
        }
        or value.get("operational_state") != operational_state
        or value.get("independent_review") != "not_requested"
        or not isinstance(value.get("bundle_manifest_sha256"), str)
        or SHA256.fullmatch(value["bundle_manifest_sha256"]) is None
    ):
        raise RuntimeError(f"optimized H {scenario} verification state differs")
    if (
        bundle_manifest is None
        or bundle_manifest.is_symlink()
        or not bundle_manifest.is_file()
        or sha256(bundle_manifest) != value["bundle_manifest_sha256"]
    ):
        raise RuntimeError(f"optimized H {scenario} bundle manifest bytes differ")
    comparisons = value.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) != 2:
        raise RuntimeError(f"optimized H {scenario} comparisons are incomplete")
    comparison_fields = {
        "state",
        "complete",
        "counts_final",
        "accepted",
        "exit_code",
        "difference_records",
        "diagnostic_codes",
        "report",
    }
    for index, (comparison, expected) in enumerate(
        zip(comparisons, expected_comparisons, strict=True)
    ):
        if not isinstance(comparison, dict) or set(comparison) != comparison_fields:
            raise RuntimeError(f"optimized H {scenario} comparison fields differ")
        observed = (
            comparison.get("state"),
            comparison.get("complete"),
            comparison.get("counts_final"),
            comparison.get("accepted"),
            comparison.get("exit_code"),
            comparison.get("difference_records"),
            comparison.get("diagnostic_codes"),
        )
        if observed != expected or comparison.get("report") != (
            f"reports/comparison-{index}/report.html"
        ):
            raise RuntimeError(f"optimized H {scenario} comparison contract differs")


def clean_profile_output(path: Path, *, keep_venv: bool = False) -> None:
    targets = [
        target
        for target in path.rglob("*")
        if target.is_dir()
        and target.name
        in {
            "uv-cache",
            "bytecode",
            "pytest-tmp",
            "hypothesis-storage",
            ".cache",
            ".pytest_cache",
            ".hypothesis",
            ".mypy_cache",
            ".ruff_cache",
            "__pycache__",
            "sdist",
            "artifacts",
        }
    ]
    for target in sorted(targets, key=lambda item: len(item.parts), reverse=True):
        if target.exists():
            remove_tree(target)
    if not keep_venv:
        for target in sorted(path.rglob("venv"), key=lambda item: len(item.parts), reverse=True):
            if target.is_dir() and target.exists():
                remove_tree(target)


def run_core_profiles(
    recorder: Recorder,
    core_source: Path,
    core_wheel: Path,
    core_sdist: Path,
    core_test_manifest: Path,
    core_test_contract: dict[str, Any],
    uv: str,
    work: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    recorder.receipt["core_profiles"] = results
    for profile in CORE_PROFILES:
        for endpoint in ENDPOINTS:
            destination = recorder.output / "core" / profile / endpoint
            item: dict[str, Any] = {
                "profile": profile,
                "endpoint": endpoint,
                "status": "running",
                "started_at": now(),
            }
            results.append(item)
            try:
                recorder.run(
                    f"core-{profile}-{endpoint}",
                    [
                        sys.executable,
                        str(core_source / "tools/verify_compatibility.py"),
                        "--wheel",
                        str(core_wheel),
                        "--sdist",
                        str(core_sdist),
                        "--test-manifest",
                        str(core_test_manifest),
                        "--python",
                        sys.executable,
                        "--profile",
                        profile,
                        "--endpoint",
                        endpoint,
                        "--uv",
                        uv,
                        "--timeout",
                        "1800",
                        "--output",
                        str(destination),
                    ],
                    cwd=work,
                    timeout=3900,
                )
                matrix = json.loads((destination / "matrix.json").read_text("utf-8"))
                cells = matrix.get("cells", [])
                if (
                    matrix.get("status") != "passed"
                    or len(cells) != 1
                    or cells[0].get("status") != "passed"
                    or cells[0].get("profile") != profile
                    or cells[0].get("endpoint") != endpoint
                ):
                    raise RuntimeError("core compatibility matrix receipt differs")
                cell_receipt_path = Path(str(cells[0].get("receipt", ""))).resolve()
                if not cell_receipt_path.is_relative_to(destination.resolve()) or file_record(
                    cell_receipt_path
                ) != cells[0].get("receipt_artifact"):
                    raise RuntimeError("core compatibility cell receipt bytes differ")
                cell_receipt = json.loads(cell_receipt_path.read_text("utf-8"))
                expected_test_summary = {
                    name: core_test_contract[name]
                    for name in (
                        "record",
                        "test_count",
                        "junit_identities_sha256",
                        "pytest_version",
                        "hypothesis_version",
                    )
                }
                if cell_receipt.get("test_manifest") != expected_test_summary:
                    raise RuntimeError("core compatibility test manifest differs")
                if profile == "all":
                    verify_core_suite_summary(
                        cell_receipt.get("suite"),
                        platform.system(),
                        core_test_contract,
                    )
                    item["installed_suite"] = cell_receipt["suite"]
                elif "suite" in cell_receipt:
                    raise RuntimeError("non-all core profile unexpectedly ran the full suite")
                item.update(
                    status="passed",
                    matrix=(destination / "matrix.json").relative_to(recorder.output).as_posix(),
                    matrix_record=file_record(destination / "matrix.json"),
                )
                clean_profile_output(destination)
            except CellDeadlineExceeded as error:
                item.update(
                    status="failed",
                    error={"type": type(error).__name__, "message": str(error)},
                )
                clean_profile_output(destination)
                raise
            # Record ordinary profile failures and continue so the receipt is complete.
            except Exception as error:
                item.update(
                    status="failed",
                    error={"type": type(error).__name__, "message": str(error)},
                )
                clean_profile_output(destination)
            finally:
                item["finished_at"] = now()
                recorder.save()
    return results


PROBE = r"""
import importlib, importlib.metadata, json, pathlib, platform, sys
names = sys.argv[1:]
versions = {name: importlib.metadata.version(name) for name in names}
modules = {"equiframe": "equiframe", "equiframe-benchmark": "equiframe_benchmark",
           "equiframe-consumer-lab": "equiframe_consumer_lab"}
paths = {}
for name, module_name in modules.items():
    if name not in names:
        continue
    module = importlib.import_module(module_name)
    path = pathlib.Path(module.__file__).resolve()
    if not path.is_relative_to(pathlib.Path(sys.prefix).resolve()):
        raise RuntimeError(name + " import is outside the isolated environment")
    paths[name] = str(path)
print(json.dumps({"versions": versions, "paths": paths, "python": platform.python_version(),
                  "system": platform.system(), "machine": platform.machine()}))
"""

REBUILD_API_PROBE = r"""
import importlib.metadata
import json
import pathlib
import sys

import equiframe as ef
import pyarrow as pa

output = pathlib.Path(sys.argv[1])
work = pathlib.Path(sys.argv[2])
table = pa.table({"id": [1, 2], "value": ["one", "two"]})
result = ef.diff(table, table, keys=["id"], work_dir=work)
document = {
    "accepted": result.state == "equivalent" and result.complete,
    "complete": result.complete,
    "difference_records": result.counts.difference_records,
    "state": result.state,
    "versions": {
        name: importlib.metadata.version(name)
        for name in ("equiframe", "equiframe-benchmark", "equiframe-consumer-lab")
    },
}
if document != {
    "accepted": True,
    "complete": True,
    "difference_records": 0,
    "state": "equivalent",
    "versions": {
        "equiframe": sys.argv[3],
        "equiframe-benchmark": sys.argv[4],
        "equiframe-consumer-lab": sys.argv[5],
    },
}:
    raise RuntimeError("rebuilt-wheel API probe differs")
temporary = output.with_suffix(output.suffix + ".partial")
temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(output)
"""


def build_system_contract(source: Path) -> dict[str, Any]:
    configuration = tomllib.loads((source / "pyproject.toml").read_text("utf-8"))
    build_system = configuration.get("build-system")
    if not isinstance(build_system, dict) or set(build_system) != {
        "requires",
        "build-backend",
    }:
        raise ValueError("sdist build-system contract differs")
    raw_requirements = build_system.get("requires")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise ValueError("sdist build requirements are absent")
    requirements: dict[str, str] = {}
    for raw in raw_requirements:
        if not isinstance(raw, str):
            raise ValueError("sdist build requirement is not text")
        requirement = Requirement(raw)
        specifications = list(requirement.specifier)
        if (
            requirement.url is not None
            or requirement.marker is not None
            or requirement.extras
            or len(specifications) != 1
            or specifications[0].operator != "=="
            or "*" in specifications[0].version
        ):
            raise ValueError("sdist build requirement is not an exact index pin")
        name = canonicalize_name(requirement.name)
        if name in requirements:
            raise ValueError("sdist build requirement repeats a distribution")
        requirements[name] = specifications[0].version
    backend = build_system.get("build-backend")
    if backend != EXPECTED_BUILD_BACKEND or requirements != EXPECTED_BUILD_REQUIREMENTS:
        raise ValueError("sdist build backend or requirements differ from the reviewed contract")
    return {"backend": backend, "requirements": requirements}


def installed_script(environment_python: Path, name: str) -> Path:
    environment = environment_python.parent.parent
    candidates = (
        environment / "Scripts" / f"{name}.exe",
        environment / "Scripts" / name,
        environment / "bin" / name,
    )
    scripts = [path for path in candidates if path.is_file() and not path.is_symlink()]
    if len(scripts) != 1:
        raise RuntimeError(f"installed entry point differs for {name}: {scripts}")
    return scripts[0]


def run_sdist_rebuild(
    recorder: Recorder,
    uv: str,
    work: Path,
    runtime_lock: Path,
    packages: dict[str, tuple[Path, Path, Path, str, str]],
) -> dict[str, Any]:
    """Rebuild all candidate wheels from sdists and exercise only those rebuilt bytes."""
    directory = recorder.output / "sdist-rebuild"
    directory.mkdir()
    phase_work = work / "sdist-rebuild"
    phase_work.mkdir()
    start_index = len(recorder.receipt["commands"])
    phase: dict[str, Any] = {
        "schema": "equiframe-universality-sdist-rebuild-1",
        "status": "running",
        "started_at": now(),
        "errors": [],
        "packages": {},
    }
    summary: dict[str, Any] = {
        "status": "running",
        "receipt": "sdist-rebuild/receipt.json",
    }
    recorder.receipt["sdist_rebuild"] = summary
    receipt_path = directory / "receipt.json"
    try:
        build_systems = {
            key: build_system_contract(source)
            for key, (
                source,
                _sdist,
                _wheel,
                _distribution,
                _version,
            ) in packages.items()
        }
        phase["build_systems"] = build_systems
        build_inputs = [f"build=={PINNED_BUILD_FRONTEND}"]
        build_inputs.extend(
            f"{name}=={version}" for name, version in sorted(EXPECTED_BUILD_REQUIREMENTS.items())
        )
        build_input = phase_work / "build-tools.in"
        build_input.write_text("\n".join(build_inputs) + "\n", "utf-8")
        build_lock = directory / "build-tools.lock"
        recorder.run(
            "sdist-resolve-build-tools",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(phase_work / "uv-cache"),
                "pip",
                "compile",
                str(build_input),
                "--python",
                sys.executable,
                "--resolution",
                "highest",
                "--generate-hashes",
                "--only-binary",
                ":all:",
                "--refresh",
                "--index-url",
                "https://pypi.org/simple",
                "--no-header",
                "--no-annotate",
                "--output-file",
                str(build_lock),
            ],
            timeout=1800,
        )
        build_versions = parse_hashed_lock(build_lock)
        if build_versions.get("build") != PINNED_BUILD_FRONTEND or any(
            build_versions.get(name) != version
            for name, version in EXPECTED_BUILD_REQUIREMENTS.items()
        ):
            raise RuntimeError("resolved build tool versions differ from their exact inputs")
        build_environment = phase_work / "build-env"
        recorder.run(
            "sdist-build-tools-venv",
            [
                uv,
                "--no-config",
                "venv",
                "--python",
                sys.executable,
                "--no-project",
                str(build_environment),
            ],
            timeout=180,
        )
        build_python = python_in(build_environment)
        recorder.run(
            "sdist-install-build-tools",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(phase_work / "uv-cache"),
                "pip",
                "install",
                "--python",
                str(build_python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--link-mode",
                "copy",
                "-r",
                str(build_lock),
            ],
            timeout=1200,
        )
        build_binding_process = recorder.run(
            "sdist-build-tools-binding",
            [str(build_python), "-I", "-c", PROBE, *sorted(build_versions)],
            timeout=120,
        )
        build_binding = json.loads(build_binding_process.stdout)
        if build_binding.get("versions") != build_versions:
            raise RuntimeError("installed build tools differ from the hash-locked resolution")
        phase["build_tools"] = {
            "frontend": {"name": "build", "version": PINNED_BUILD_FRONTEND},
            "lock": "sdist-rebuild/build-tools.lock",
            "lock_record": file_record(build_lock),
            "versions": build_versions,
            "binding": build_binding,
        }

        rebuilt_directory = directory / "rebuilt-wheels"
        rebuilt_directory.mkdir()
        rebuilt_paths: dict[str, Path] = {}
        package_receipts: dict[str, Any] = {}
        for key, (
            source,
            sdist,
            candidate_wheel,
            distribution,
            version,
        ) in packages.items():
            before = set(rebuilt_directory.glob("*.whl"))
            recorder.run(
                f"sdist-rebuild-{key}",
                [
                    str(build_python),
                    "-I",
                    "-m",
                    "build",
                    "--wheel",
                    "--no-isolation",
                    "--outdir",
                    str(rebuilt_directory),
                    str(source),
                ],
                cwd=phase_work,
                timeout=900,
            )
            created = set(rebuilt_directory.glob("*.whl")) - before
            if len(created) != 1:
                raise RuntimeError(f"{key} sdist did not produce exactly one new wheel")
            rebuilt = created.pop()
            candidate_identity = wheel_payload(
                candidate_wheel,
                expected_distribution=distribution,
                expected_version=version,
            )
            rebuilt_identity = wheel_payload(
                rebuilt,
                expected_distribution=distribution,
                expected_version=version,
            )
            if candidate_identity != rebuilt_identity:
                raise RuntimeError(f"{key} rebuilt wheel payload differs from the candidate wheel")
            rebuilt_paths[key] = rebuilt
            package_receipts[key] = {
                "distribution": canonicalize_name(distribution),
                "version": version,
                "source_sdist": file_record(sdist),
                "candidate_wheel": file_record(candidate_wheel),
                "candidate_identity": candidate_identity,
                "rebuilt_wheel_path": rebuilt.relative_to(recorder.output).as_posix(),
                "rebuilt_wheel": file_record(rebuilt),
                "rebuilt_identity": rebuilt_identity,
                "installed_payload_match": True,
            }
        phase["packages"] = package_receipts

        copied_runtime_lock = directory / "runtime.lock"
        shutil.copyfile(runtime_lock, copied_runtime_lock)
        runtime_versions = parse_hashed_lock(copied_runtime_lock)
        install_environment = phase_work / "install-env"
        recorder.run(
            "sdist-rebuild-runtime-venv",
            [
                uv,
                "--no-config",
                "venv",
                "--python",
                sys.executable,
                "--no-project",
                str(install_environment),
            ],
            timeout=180,
        )
        install_python = python_in(install_environment)
        recorder.run(
            "sdist-rebuild-install-runtime",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(phase_work / "runtime-cache"),
                "pip",
                "install",
                "--python",
                str(install_python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--link-mode",
                "copy",
                "-r",
                str(copied_runtime_lock),
            ],
            timeout=1800,
        )
        recorder.run(
            "sdist-rebuild-install-wheels",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(phase_work / "runtime-cache"),
                "pip",
                "install",
                "--python",
                str(install_python),
                "--no-index",
                "--no-deps",
                "--reinstall",
                "--link-mode",
                "copy",
                *(str(rebuilt_paths[key]) for key in sorted(rebuilt_paths)),
            ],
            timeout=600,
        )
        recorder.run(
            "sdist-rebuild-pip-check",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(phase_work / "runtime-cache"),
                "pip",
                "check",
                "--python",
                str(install_python),
            ],
            timeout=300,
        )
        local_versions = {
            distribution: version
            for _key, (
                _source,
                _sdist,
                _wheel,
                distribution,
                version,
            ) in packages.items()
        }
        expected_versions = {**runtime_versions, **local_versions}
        binding_process = recorder.run(
            "sdist-rebuild-binding",
            [str(install_python), "-I", "-c", PROBE, *sorted(expected_versions)],
            timeout=120,
        )
        binding = json.loads(binding_process.stdout)
        if binding.get("versions") != expected_versions:
            raise RuntimeError("rebuilt-wheel installed identity differs")
        binding_path = directory / "installed-binding.json"
        write_json(binding_path, binding)
        api_path = directory / "api-probe.json"
        recorder.run(
            "sdist-rebuild-api",
            [
                str(install_python),
                "-I",
                "-c",
                REBUILD_API_PROBE,
                str(api_path),
                str(phase_work / "api-evidence"),
                local_versions["equiframe"],
                local_versions["equiframe-benchmark"],
                local_versions["equiframe-consumer-lab"],
            ],
            timeout=300,
        )
        api_probe = json.loads(api_path.read_text("utf-8"))
        entry_points = (
            "equiframe",
            "equiframe-benchmark",
            "equiframe-consumer-lab",
        )
        cli_records: dict[str, Any] = {}
        for name in entry_points:
            script = installed_script(install_python, name)
            recorder.run(
                f"sdist-rebuild-cli-{name}",
                [str(script), "--help"],
                timeout=120,
            )
            cli_records[name] = {"entry_point": name, "status": "passed"}
        phase["installation"] = {
            "runtime_lock": "sdist-rebuild/runtime.lock",
            "runtime_lock_record": file_record(copied_runtime_lock),
            "runtime_versions": runtime_versions,
            "binding": binding,
            "binding_path": "sdist-rebuild/installed-binding.json",
            "binding_record": file_record(binding_path),
            "api_probe": api_probe,
            "api_probe_path": "sdist-rebuild/api-probe.json",
            "api_probe_record": file_record(api_path),
            "cli": cli_records,
            "pip_check": "passed",
        }
        phase["status"] = "passed"
    except CellDeadlineExceeded as error:
        phase["status"] = "failed"
        phase["errors"].append({"type": type(error).__name__, "message": str(error)})
        raise
    except Exception as error:
        phase["status"] = "failed"
        phase["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        phase["finished_at"] = now()
        phase["command_indexes"] = list(range(start_index, len(recorder.receipt["commands"])))
        write_json(receipt_path, phase)
        summary.update(status=phase["status"], receipt_record=file_record(receipt_path))
        recorder.save()
    return summary


def run_benchmark_profile(
    recorder: Recorder,
    core_wheel: Path,
    benchmark_wheel: Path,
    profile_probe: Path,
    uv: str,
    profile: str,
    endpoint: str,
) -> tuple[dict[str, Any], Path | None, Path | None]:
    destination = recorder.output / "benchmark" / profile / endpoint
    destination.mkdir(parents=True)
    start_index = len(recorder.receipt["commands"])
    receipt: dict[str, Any] = {
        "schema": "equiframe-actions-benchmark-profile-1",
        "profile": profile,
        "endpoint": endpoint,
        "status": "running",
        "started_at": now(),
        "artifacts": {
            "core": file_record(core_wheel),
            "benchmark": file_record(benchmark_wheel),
        },
    }
    env_python: Path | None = None
    runtime_lock: Path | None = None
    try:
        requirements = benchmark_requirements(core_wheel, benchmark_wheel, profile)
        runtime_input = destination / "runtime.in"
        runtime_input.write_text("\n".join(requirements) + "\n", "utf-8")
        runtime_lock = destination / "runtime.lock"
        resolution = "lowest-direct" if endpoint == "minimum" else "highest"
        recorder.run(
            f"benchmark-{profile}-{endpoint}-resolve",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(destination / "uv-cache"),
                "pip",
                "compile",
                str(runtime_input),
                "--python",
                sys.executable,
                "--generate-hashes",
                "--only-binary",
                ":all:",
                "--resolution",
                resolution,
                "--refresh",
                "--index-url",
                "https://pypi.org/simple",
                "--no-header",
                "--no-annotate",
                "--output-file",
                str(runtime_lock),
            ],
            timeout=1800,
        )
        runtime_versions = parse_hashed_lock(runtime_lock)
        venv = destination / "venv"
        recorder.run(
            f"benchmark-{profile}-{endpoint}-venv",
            [
                uv,
                "--no-config",
                "venv",
                "--python",
                sys.executable,
                "--no-python-downloads",
                str(venv),
            ],
        )
        env_python = python_in(venv)
        recorder.run(
            f"benchmark-{profile}-{endpoint}-dependencies",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(destination / "uv-cache"),
                "pip",
                "sync",
                "--python",
                str(env_python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--link-mode",
                "copy",
                str(runtime_lock),
            ],
            timeout=1800,
        )
        recorder.run(
            f"benchmark-{profile}-{endpoint}-artifacts",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(destination / "uv-cache"),
                "pip",
                "install",
                "--python",
                str(env_python),
                "--no-index",
                "--link-mode",
                "copy",
                str(core_wheel),
                str(benchmark_wheel),
            ],
            timeout=600,
        )
        recorder.run(
            f"benchmark-{profile}-{endpoint}-pip-check",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(destination / "uv-cache"),
                "pip",
                "check",
                "--python",
                str(env_python),
            ],
        )
        probe = recorder.run(
            f"benchmark-{profile}-{endpoint}-binding",
            [
                str(env_python),
                "-I",
                "-c",
                PROBE,
                *sorted((*runtime_versions, "equiframe", "equiframe-benchmark")),
            ],
        )
        binding = json.loads(probe.stdout)
        expected_versions = {
            **runtime_versions,
            "equiframe": str(wheel_metadata(core_wheel)["Version"]),
            "equiframe-benchmark": str(wheel_metadata(benchmark_wheel)["Version"]),
        }
        if binding.get("versions") != expected_versions:
            raise RuntimeError("installed benchmark pair versions differ")
        recorder.run(
            f"benchmark-{profile}-{endpoint}-cli",
            [str(env_python), "-I", "-m", "equiframe_benchmark", "--help"],
            timeout=120,
        )
        if profile in ("engines", "all"):
            recorder.run(
                f"benchmark-{profile}-{endpoint}-pilot",
                [
                    str(env_python),
                    "-I",
                    "-m",
                    "equiframe_benchmark.pilot",
                    "--output",
                    str(destination / "pilot"),
                ],
                timeout=900,
            )
        recorder.run(
            f"benchmark-{profile}-{endpoint}-boundary",
            [
                str(env_python),
                "-I",
                str(profile_probe),
                "--profile",
                profile,
                "--output",
                str(destination / "boundary.json"),
            ],
            timeout=600,
        )
        boundary = json.loads((destination / "boundary.json").read_text("utf-8"))
        if boundary.get("status") != "passed" or boundary.get("profile") != profile:
            raise RuntimeError("benchmark boundary receipt differs")
        receipt.update(
            status="passed",
            selected_requirements=requirements,
            runtime_lock=file_record(runtime_lock),
            runtime_versions=runtime_versions,
            binding=binding,
            boundary=file_record(destination / "boundary.json"),
        )
    except CellDeadlineExceeded as error:
        receipt.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        raise
    # Convert all ordinary cell-local failures into a durable benchmark receipt.
    except Exception as error:
        receipt.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
    finally:
        receipt.update(
            finished_at=now(),
            command_indexes=list(range(start_index, len(recorder.receipt["commands"]))),
        )
        write_json(destination / "receipt.json", receipt)
    return receipt, env_python, runtime_lock


def add_test_tools(
    recorder: Recorder,
    uv: str,
    env_python: Path,
    runtime_lock: Path,
    benchmark_source: Path,
    directory: Path,
    test_contracts: tuple[dict[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    configuration = tomllib.loads((benchmark_source / "pyproject.toml").read_text("utf-8"))
    requirements = configuration.get("dependency-groups", {}).get("dev", [])
    if not requirements or not all(isinstance(item, str) for item in requirements):
        raise ValueError("benchmark sdist has no flat development dependency group")
    versions = {
        (contract["pytest_version"], contract["hypothesis_version"]) for contract in test_contracts
    }
    if len(versions) != 1:
        raise ValueError("benchmark and consumer test-tool identities differ")
    pytest_version, hypothesis_version = versions.pop()
    inputs = directory / "test-tools.in"
    inputs.write_text(
        "\n".join(
            [
                *requirements,
                f"pytest=={pytest_version}",
                f"hypothesis=={hypothesis_version}",
            ]
        )
        + "\n",
        "utf-8",
    )
    lock = directory / "test-tools.lock"
    recorder.run(
        "joint-resolve-test-tools",
        [
            uv,
            "--no-config",
            "--cache-dir",
            str(directory / "uv-cache"),
            "pip",
            "compile",
            str(runtime_lock),
            str(inputs),
            "--constraint",
            str(runtime_lock),
            "--python",
            str(env_python),
            "--resolution",
            "highest",
            "--generate-hashes",
            "--only-binary",
            ":all:",
            "--output-file",
            str(lock),
        ],
        timeout=1800,
    )
    recorder.run(
        "joint-install-test-tools",
        [
            uv,
            "--no-config",
            "--cache-dir",
            str(directory / "uv-cache"),
            "pip",
            "install",
            "--python",
            str(env_python),
            "--require-hashes",
            "--only-binary",
            ":all:",
            "--link-mode",
            "copy",
            "-r",
            str(lock),
        ],
        timeout=1800,
    )
    expected_versions = {"hypothesis": hypothesis_version, "pytest": pytest_version}
    process = recorder.run(
        "joint-test-tools-binding",
        [str(env_python), "-I", "-c", PROBE, *sorted(expected_versions)],
        timeout=120,
    )
    binding = json.loads(process.stdout)
    if binding.get("versions") != expected_versions:
        raise RuntimeError("installed test-tool identity differs from candidate manifests")
    return {
        "versions": expected_versions,
        "binding": binding,
        "lock": lock.relative_to(recorder.output).as_posix(),
        "lock_record": file_record(lock),
    }


def run_installed_suite(
    recorder: Recorder,
    label: str,
    env_python: Path,
    source: Path,
    output: Path,
    test_contract: dict[str, Any],
    test_identities: set[tuple[str, str]],
) -> dict[str, Any]:
    junit = output / f"{label}-junit.xml"
    recorder.run(
        f"{label}-installed-suite",
        [
            str(env_python),
            "-I",
            "-B",
            "-m",
            "pytest",
            "-p",
            "_hypothesis_pytestplugin",
            "-q",
            str(source / "tests"),
            "--junitxml",
            str(junit),
            "-o",
            "xfail_strict=true",
            "--basetemp",
            str(output / (label + "-pytest-tmp")),
        ],
        timeout=2400,
    )
    expected_skips = (
        benchmark_skip_contract(platform.system(), ".".join(map(str, sys.version_info[:2])))
        if label == "benchmark"
        else set()
    )
    summary = inspect_junit(junit, expected_skips, test_contract, test_identities)
    if summary["accepted"] is not True:
        raise RuntimeError(f"{label} suite failures/errors or skip contract differ")
    return summary


def run_joint_consumer(
    recorder: Recorder,
    repository: Path,
    candidate_root: Path,
    candidate: dict[str, Any],
    uv: str,
    env_python: Path,
    runtime_lock: Path,
    benchmark_source: Path,
    consumer_source: Path,
    consumer_wheel: Path,
    core_wheel: Path,
    benchmark_wheel: Path,
    benchmark_test_contract: dict[str, Any],
    benchmark_test_identities: set[tuple[str, str]],
    consumer_test_contract: dict[str, Any],
    consumer_test_identities: set[tuple[str, str]],
) -> dict[str, Any]:
    joint = recorder.output / "joint-all-latest"
    joint.mkdir()
    result: dict[str, Any] = {"status": "running", "started_at": now(), "errors": []}
    recorder.receipt["joint"] = result
    try:
        result["test_tools"] = add_test_tools(
            recorder,
            uv,
            env_python,
            runtime_lock,
            benchmark_source,
            joint,
            (benchmark_test_contract, consumer_test_contract),
        )
        recorder.run(
            "joint-install-consumer",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(joint / "uv-cache"),
                "pip",
                "install",
                "--python",
                str(env_python),
                "--no-index",
                "--no-deps",
                "--reinstall",
                "--link-mode",
                "copy",
                str(consumer_wheel),
            ],
            timeout=600,
        )
        recorder.run(
            "joint-pip-check",
            [
                uv,
                "--no-config",
                "--cache-dir",
                str(joint / "uv-cache"),
                "pip",
                "check",
                "--python",
                str(env_python),
            ],
        )
        result["benchmark_suite"] = run_installed_suite(
            recorder,
            "benchmark",
            env_python,
            benchmark_source,
            joint,
            benchmark_test_contract,
            benchmark_test_identities,
        )
        result["consumer_suite"] = run_installed_suite(
            recorder,
            "consumer",
            env_python,
            consumer_source,
            joint,
            consumer_test_contract,
            consumer_test_identities,
        )
        optimized_h: dict[str, Any] = {}
        result["optimized_h"] = optimized_h
        for scenario, expected_exit in (
            ("good", 0),
            ("different", 1),
            ("not_evaluable", 3),
            ("error", 2),
        ):
            scenario_output = joint / ("optimized-H-" + scenario)
            recorder.run(
                "optimized-H-" + scenario,
                [
                    str(env_python),
                    "-I",
                    "-O",
                    "-m",
                    "equiframe.examples.journeys.h_portable_ci",
                    "--case",
                    scenario,
                    "--output",
                    str(scenario_output),
                ],
                expected=expected_exit,
                timeout=180,
            )
            summary_path = scenario_output / "summary.json"
            summary = json.loads(summary_path.read_text("utf-8"))
            bundle_manifest = (
                scenario_output / "portable/bundle.json" if scenario != "error" else None
            )
            verify_h_summary(
                summary,
                scenario,
                expected_exit,
                bundle_manifest=bundle_manifest,
            )
            scenario_receipt = {
                "path": summary_path.relative_to(recorder.output).as_posix(),
                "record": file_record(summary_path),
            }
            if bundle_manifest is not None:
                scenario_receipt.update(
                    bundle_manifest=bundle_manifest.relative_to(recorder.output).as_posix(),
                    bundle_manifest_record=file_record(bundle_manifest),
                )
            optimized_h[scenario] = scenario_receipt
            recorder.save()
        measurement: dict[str, Any] = {"status": "running", "started_at": now()}
        result["measurement"] = measurement
        try:
            recorder.run(
                "bounded-measurements",
                [
                    str(env_python),
                    "-I",
                    str(repository / "tools/maturity_lab/scripts/measure_maturity.py"),
                    "--output",
                    str(joint / "measurements"),
                    "--storage",
                    "disk",
                ],
                timeout=900,
            )
            requested = recorder.receipt.get("requested")
            if not isinstance(requested, dict):
                raise TypeError("measurement requested identity is absent")
            measurement_root = joint / "measurements"
            verify_measurement_documents(
                read_object(measurement_root / "protocol.json"),
                read_object(measurement_root / "summary.json"),
                read_object(measurement_root / "bounded-limit.json"),
                requested_system=requested["system"],
                requested_architecture=requested["architecture"],
                requested_python=requested["python"],
            )
            measurement.update(
                status="passed",
                protocol=file_record(joint / "measurements/protocol.json"),
                summary=file_record(joint / "measurements/summary.json"),
                bounded_limit=file_record(joint / "measurements/bounded-limit.json"),
            )
        except CellDeadlineExceeded as error:
            failure = {
                "stage": "measurement",
                "type": type(error).__name__,
                "message": str(error),
            }
            measurement.update(status="failed", error=failure)
            result["errors"].append(failure)
            raise
        # An ordinary measurement failure is evidence; the consumer run still proceeds.
        except Exception as error:
            failure = {
                "stage": "measurement",
                "type": type(error).__name__,
                "message": str(error),
            }
            measurement.update(status="failed", error=failure)
            result["errors"].append(failure)
        finally:
            measurement["finished_at"] = now()
            recorder.save()
        data = checked_member(candidate_root, candidate["consumer_data"]["manifest"]).parent
        consumer_output = joint / "consumer-72"
        recorder.run(
            "consumer-72-cases",
            [
                str(env_python),
                "-I",
                "-m",
                "equiframe_consumer_lab",
                "run",
                "--all",
                "--data",
                str(data),
                "--output",
                str(consumer_output),
            ],
            timeout=2400,
        )
        optimized_consumer_output = joint / "consumer-72-optimized"
        recorder.run(
            "consumer-72-optimized-cases",
            [
                str(env_python),
                "-I",
                "-O",
                "-m",
                "equiframe_consumer_lab",
                "run",
                "--all",
                "--require-optimized",
                "--data",
                str(data),
                "--output",
                str(optimized_consumer_output),
            ],
            timeout=2400,
        )
        recorder.run(
            "consumer-fault-checks",
            [
                str(env_python),
                "-I",
                "-O",
                "-m",
                "equiframe_consumer_lab",
                "fault-checks",
                "--output",
                str(joint / "consumer-faults"),
            ],
            timeout=300,
        )
        summary_path = consumer_output / "summary.json"
        summary = json.loads(summary_path.read_text("utf-8"))
        verify_consumer_summary(
            summary,
            str(candidate["artifacts"]["consumer"]["version"]),
            optimized=False,
        )
        optimized_summary_path = optimized_consumer_output / "summary.json"
        optimized_summary = json.loads(optimized_summary_path.read_text("utf-8"))
        verify_consumer_summary(
            optimized_summary,
            str(candidate["artifacts"]["consumer"]["version"]),
            optimized=True,
        )
        fault = json.loads((joint / "consumer-faults/fault-checks.json").read_text("utf-8"))
        verify_fault_checks(fault)
        result["consumer_faults"] = {
            "path": (joint / "consumer-faults/fault-checks.json")
            .relative_to(recorder.output)
            .as_posix(),
            "record": file_record(joint / "consumer-faults/fault-checks.json"),
        }
        pair = recorder.run(
            "installed-pair-binding",
            [
                str(env_python),
                "-I",
                "-c",
                PROBE,
                *sorted(
                    (
                        *parse_hashed_lock(runtime_lock),
                        "equiframe",
                        "equiframe-benchmark",
                        "equiframe-consumer-lab",
                    )
                ),
            ],
        )
        binding = json.loads(pair.stdout)
        expected_versions = {
            **parse_hashed_lock(runtime_lock),
            "equiframe": str(candidate["artifacts"]["core"]["version"]),
            "equiframe-benchmark": str(candidate["artifacts"]["benchmark"]["version"]),
            "equiframe-consumer-lab": str(candidate["artifacts"]["consumer"]["version"]),
        }
        if binding.get("versions") != expected_versions:
            raise RuntimeError("installed three-package identity differs from the candidate")
        write_json(joint / "installed-pair.json", binding)
        result.update(
            status="passed" if not result["errors"] else "failed",
            consumer_summary=summary_path.relative_to(recorder.output).as_posix(),
            consumer_summary_record=file_record(summary_path),
            consumer_optimized_summary=optimized_summary_path.relative_to(
                recorder.output
            ).as_posix(),
            consumer_optimized_summary_record=file_record(optimized_summary_path),
            installed_pair=file_record(joint / "installed-pair.json"),
            artifact_records={
                "core": file_record(core_wheel),
                "benchmark": file_record(benchmark_wheel),
                "consumer": file_record(consumer_wheel),
            },
        )
    except CellDeadlineExceeded as error:
        result.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        raise
    # Convert all ordinary joint-path failures into a durable receipt.
    except Exception as error:
        result.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
    finally:
        result["finished_at"] = now()
        recorder.save()
    return result


def inventory_evidence(output: Path) -> dict[str, Any]:
    files = {}
    inventory_path = output / "evidence-inventory.json"
    for path in sorted(output.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"evidence contains a symbolic link: {path}")
        if path.is_file() and path != inventory_path:
            files[path.relative_to(output).as_posix()] = file_record(path)
    return {
        "schema": "equiframe-universality-evidence-inventory-1",
        "files": files,
        "unsigned": True,
    }


def create_attestation(evidence: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError("attestation output must be new")
    output.mkdir(parents=True)
    required = ("receipt.json", "evidence-inventory.json")
    optional = (
        "joint-all-latest/consumer-72/summary.json",
        "joint-all-latest/consumer-72-optimized/summary.json",
        "joint-all-latest/consumer-faults/fault-checks.json",
        "joint-all-latest/installed-pair.json",
        "joint-all-latest/optimized-H-good/summary.json",
        "joint-all-latest/optimized-H-good/portable/bundle.json",
        "joint-all-latest/optimized-H-different/summary.json",
        "joint-all-latest/optimized-H-different/portable/bundle.json",
        "joint-all-latest/optimized-H-not_evaluable/summary.json",
        "joint-all-latest/optimized-H-not_evaluable/portable/bundle.json",
        "joint-all-latest/optimized-H-error/summary.json",
        "joint-all-latest/measurements/protocol.json",
        "joint-all-latest/measurements/summary.json",
        "joint-all-latest/measurements/bounded-limit.json",
        "sdist-rebuild/receipt.json",
        "sdist-rebuild/build-tools.lock",
        "sdist-rebuild/runtime.lock",
        "sdist-rebuild/installed-binding.json",
        "sdist-rebuild/api-probe.json",
    )
    for name in (*required, *optional):
        source = evidence.joinpath(*PurePosixPath(name).parts)
        if not source.is_file() or source.is_symlink():
            if name in required:
                raise ValueError(f"required attestation member is absent: {name}")
            continue
        target = output.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _record_finalization_failure(receipt: dict[str, Any], stage: str, error: BaseException) -> None:
    receipt["status"] = "failed"
    receipt.setdefault("errors", []).append(
        {"stage": stage, "type": type(error).__name__, "message": str(error)}
    )


def _failed_inventory(output: Path, error: BaseException) -> dict[str, Any]:
    files: dict[str, object] = {}
    receipt_path = output / "receipt.json"
    try:
        if receipt_path.is_file() and not receipt_path.is_symlink():
            files["receipt.json"] = file_record(receipt_path)
    except OSError:
        pass
    return {
        "schema": "equiframe-universality-evidence-inventory-1",
        "status": "failed",
        "complete": False,
        "files": files,
        "unsigned": True,
        "error": {"type": type(error).__name__, "message": str(error)},
    }


def finalize_cell(
    recorder: Recorder,
    receipt: dict[str, Any],
    *,
    work: Path,
    kept_environment: Path | None,
    attestation_output: Path,
    exit_code: int,
) -> tuple[int, dict[str, Any]]:
    """Best-effort cleanup that still attempts every durable evidence artifact."""

    def cleanup(stage: str, path: Path) -> None:
        nonlocal exit_code
        try:
            remove_tree(path)
        except Exception as error:
            _record_finalization_failure(receipt, stage, error)
            exit_code = 1

    if kept_environment is not None:
        environment_root = (
            kept_environment.parent.parent
            if kept_environment.parent.name in ("bin", "Scripts")
            else kept_environment.parent
        )
        cleanup("cleanup_kept_environment", environment_root)
    cleanup("cleanup_work", work)
    try:
        reconstructible = [
            path
            for path in recorder.output.rglob("*")
            if path.is_dir()
            and (
                path.name
                in {
                    "uv-cache",
                    "bytecode",
                    "pytest-tmp",
                    "hypothesis-storage",
                    ".cache",
                    "__pycache__",
                    ".pytest_cache",
                    ".hypothesis",
                    ".mypy_cache",
                    ".ruff_cache",
                    ".process-control",
                }
                or path.name.endswith("-pytest-tmp")
            )
        ]
    except Exception as error:
        _record_finalization_failure(receipt, "discover_reconstructible_cleanup", error)
        exit_code = 1
        reconstructible = []
    for path in sorted(reconstructible, key=lambda item: len(item.parts), reverse=True):
        cleanup("cleanup_reconstructible", path)

    receipt["finished_at"] = now()
    try:
        receipt["final_disk_free_bytes"] = shutil.disk_usage(recorder.output).free
    except Exception as error:
        _record_finalization_failure(receipt, "final_disk_observation", error)
        exit_code = 1

    inventory: dict[str, Any] = {
        "schema": "equiframe-universality-evidence-inventory-1",
        "status": "failed",
        "complete": False,
        "files": {},
        "unsigned": True,
    }

    def persist() -> dict[str, Any]:
        recorder.save()
        observed = inventory_evidence(recorder.output)
        write_json(recorder.output / "evidence-inventory.json", observed)
        return observed

    try:
        inventory = persist()
    except Exception as error:
        _record_finalization_failure(receipt, "write_evidence_inventory", error)
        exit_code = 1
        with suppress(Exception):
            recorder.save()
        inventory = _failed_inventory(recorder.output, error)
        with suppress(Exception):
            write_json(recorder.output / "evidence-inventory.json", inventory)

    try:
        create_attestation(recorder.output, attestation_output)
    except Exception as first_error:
        _record_finalization_failure(receipt, "create_attestation", first_error)
        exit_code = 1
        # The output was validated as new before work began, so any directory here is partial.
        cleanup("cleanup_partial_attestation", attestation_output)
        try:
            inventory = persist()
        except Exception as inventory_error:
            _record_finalization_failure(receipt, "rewrite_evidence_inventory", inventory_error)
            inventory = _failed_inventory(recorder.output, inventory_error)
            try:
                recorder.save()
                inventory = _failed_inventory(recorder.output, inventory_error)
                write_json(recorder.output / "evidence-inventory.json", inventory)
            except Exception:
                pass
        try:
            create_attestation(recorder.output, attestation_output)
        except Exception as retry_error:
            _record_finalization_failure(receipt, "retry_attestation", retry_error)
            try:
                recorder.save()
                inventory = inventory_evidence(recorder.output)
                write_json(recorder.output / "evidence-inventory.json", inventory)
            except Exception:
                pass
    return (1 if receipt.get("status") == "failed" else exit_code), inventory


def expected_cell_id(python: str, system: str, architecture: str) -> str:
    labels = {
        ("Linux", "x64"): "linux-x64",
        ("Linux", "arm64"): "linux-arm64",
        ("Windows", "x64"): "windows-x64",
        ("Darwin", "x64"): "macos-intel",
        ("Darwin", "arm64"): "macos-arm64",
    }
    return f"{labels[(system, architecture)]}-py{python.replace('.', '')}"


def verify_github_execution(value: dict[str, str], args: argparse.Namespace) -> None:
    if (
        not value["run_id"].isdigit()
        or not value["run_attempt"].isdigit()
        or int(value["run_id"]) <= 0
        or int(value["run_attempt"]) <= 0
        or value["job"] != "native-cell"
        or REPOSITORY_NAME.fullmatch(value["repository"]) is None
        or GIT_COMMIT.fullmatch(value["workflow_sha"]) is None
        or not value["workflow_ref"]
        or not value["runner_name"]
        or value["runner_environment"] != "github-hosted"
        or not value["runner_image_os"]
        or not value["runner_image_version"]
        or value["cell_id"]
        != expected_cell_id(args.expected_python, args.expected_system, args.expected_architecture)
    ):
        raise RuntimeError("GitHub Actions execution identity is malformed")
    expected_runner_os = {
        "Linux": "Linux",
        "Windows": "Windows",
        "Darwin": "macOS",
    }[args.expected_system]
    if (
        value["runner_os"] != expected_runner_os
        or normalized_architecture(value["runner_arch"]) != args.expected_architecture
    ):
        raise RuntimeError("GitHub Actions runner identity differs from the requested cell")
    expected_environment = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ID": value["run_id"],
        "GITHUB_RUN_ATTEMPT": value["run_attempt"],
        "GITHUB_JOB": value["job"],
        "GITHUB_REPOSITORY": value["repository"],
        "GITHUB_WORKFLOW_REF": value["workflow_ref"],
        "GITHUB_WORKFLOW_SHA": value["workflow_sha"],
        "RUNNER_NAME": value["runner_name"],
        "RUNNER_OS": value["runner_os"],
        "RUNNER_ARCH": value["runner_arch"],
        "RUNNER_ENVIRONMENT": value["runner_environment"],
        "ImageOS": value["runner_image_os"],
        "ImageVersion": value["runner_image_version"],
    }
    if any(os.environ.get(name) != expected for name, expected in expected_environment.items()):
        raise RuntimeError("GitHub Actions environment differs from the declared execution")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attestation-output", type=Path, required=True)
    parser.add_argument("--expected-python", required=True)
    parser.add_argument("--expected-system", choices=("Linux", "Windows", "Darwin"), required=True)
    parser.add_argument("--expected-architecture", choices=("x64", "arm64"), required=True)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--deadline-seconds", type=int, required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-run-attempt", required=True)
    parser.add_argument("--github-job", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--github-workflow-ref", required=True)
    parser.add_argument("--github-workflow-sha", required=True)
    parser.add_argument("--runner-name", required=True)
    parser.add_argument("--runner-os", required=True)
    parser.add_argument("--runner-arch", required=True)
    parser.add_argument("--runner-environment", required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    attestation_output = args.attestation_output.resolve()
    if output.exists() or output.is_symlink():
        parser.error("output must be a new external directory")
    candidate_root = args.candidate.resolve()
    repository = args.repository.resolve()
    if output.is_relative_to(repository):
        parser.error("evidence output must be outside the source checkout")
    if attestation_output == output or attestation_output.is_relative_to(output):
        parser.error("attestation output must be outside the evidence tree")
    if attestation_output.exists() or attestation_output.is_symlink():
        parser.error("attestation output must be a new directory")
    if not 300 <= args.deadline_seconds <= 21_000:
        parser.error("deadline seconds must reserve bounded time within the workflow job")
    output.mkdir(parents=True)
    execution = {
        "provider": "github-actions",
        "run_id": args.github_run_id,
        "run_attempt": args.github_run_attempt,
        "job": args.github_job,
        "repository": args.github_repository,
        "workflow_ref": args.github_workflow_ref,
        "workflow_sha": args.github_workflow_sha,
        "runner_name": args.runner_name,
        "runner_os": args.runner_os,
        "runner_arch": args.runner_arch,
        "runner_environment": args.runner_environment,
        "runner_image_os": os.environ.get("ImageOS", ""),  # noqa: SIM112 - GitHub name
        "runner_image_version": os.environ.get(
            "ImageVersion",  # noqa: SIM112 - GitHub name
            "",
        ),
        "cell_id": args.cell_id,
    }
    receipt: dict[str, Any] = {
        "schema": "equiframe-universality-actions-cell-1",
        "status": "running",
        "started_at": now(),
        "requested": {
            "python": args.expected_python,
            "system": args.expected_system,
            "architecture": args.expected_architecture,
        },
        "commands": [],
        "core_profiles": [],
        "benchmark_profiles": [],
        "errors": [],
        "execution": execution,
        "deadline_seconds": args.deadline_seconds,
        "evidence_reserve_seconds": EVIDENCE_RESERVE_SECONDS,
        "receipts_authenticated": False,
        "independent_human_acceptance": False,
    }
    recorder = Recorder(
        output,
        receipt,
        deadline_monotonic=time.monotonic() + args.deadline_seconds,
        evidence_reserve_seconds=EVIDENCE_RESERVE_SECONDS,
    )
    work = output / "work"
    kept_environment: Path | None = None
    exit_code = 1
    try:
        verify_github_execution(execution, args)
        recorder.require_work_window("candidate verification", 30)
        if shutil.disk_usage(output).free < 8 * 1024**3:
            raise RuntimeError("at least 8 GiB free disk is required before a native cell")
        candidate = verify_candidate(candidate_root)
        candidate_hash = sha256(candidate_root / "candidate.json")
        actual = {
            "python": ".".join(map(str, sys.version_info[:2])),
            "python_full": platform.python_version(),
            "system": platform.system(),
            "architecture": normalized_architecture(platform.machine()),
            "machine": platform.machine(),
            "platform": platform.platform(),
        }
        receipt["actual"] = actual
        if actual["python"] != args.expected_python:
            raise RuntimeError("actual Python minor differs from the requested cell")
        if actual["system"] != args.expected_system:
            raise RuntimeError("actual operating system differs from the requested cell")
        if actual["architecture"] != args.expected_architecture:
            raise RuntimeError("actual architecture differs from the requested cell")
        if args.expected_python not in candidate.get("required_python_versions", []):
            raise RuntimeError("requested Python is outside the frozen candidate scope")
        requested_platform = {
            "system": args.expected_system,
            "architecture": args.expected_architecture,
        }
        if requested_platform not in candidate.get("required_native_platforms", []):
            raise RuntimeError("requested platform is outside the frozen candidate scope")
        repository_commit = subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            text=True,
            encoding="utf-8",
        ).strip()
        expected_commit = candidate["source"]["equiframe"]["commit"]
        if GIT_COMMIT.fullmatch(repository_commit) is None or repository_commit != expected_commit:
            raise RuntimeError("workflow source checkout differs from the built candidate commit")
        if execution["workflow_sha"] != expected_commit:
            raise RuntimeError("workflow definition commit differs from the built candidate commit")
        receipt.update(
            candidate_manifest_sha256=candidate_hash,
            source=candidate["source"],
            artifacts=candidate["artifacts"],
            tooling={
                "runner": file_record(Path(__file__)),
                "benchmark_profile_probe": file_record(
                    repository / "tools/maturity_lab/scripts/profile_boundary_probe.py"
                ),
                "measurement": file_record(
                    repository / "tools/maturity_lab/scripts/measure_maturity.py"
                ),
            },
        )
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("pinned uv executable is unavailable")
        package_versions = {name: importlib.metadata.version(name) for name in PINNED_TOOLCHAIN}
        if package_versions != PINNED_TOOLCHAIN:
            raise RuntimeError("native-cell controller toolchain differs from its pins")
        uv_path = Path(uv).resolve()
        toolchain_evidence = output / "toolchain"
        toolchain_evidence.mkdir()
        requirements_source = repository / ".github/controller-requirements.txt"
        requirements_copy = toolchain_evidence / "controller-requirements.txt"
        shutil.copyfile(requirements_source, requirements_copy)
        receipt["toolchain"] = {
            "packages": package_versions,
            "distributions": {
                name: distribution_inventory(name) for name in sorted(PINNED_TOOLCHAIN)
            },
            "requirements": {
                "path": requirements_copy.relative_to(output).as_posix(),
                "record": file_record(requirements_copy),
            },
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "pip_version": importlib.metadata.version("pip"),
            "python_executable": file_record(Path(sys.executable).resolve()),
            "uv_executable": file_record(uv_path),
            "uv_path": str(uv_path),
        }
        uv_version = recorder.run("toolchain-uv-version", [str(uv_path), "--version"], timeout=30)
        if (
            re.fullmatch(
                rf"uv {re.escape(PINNED_TOOLCHAIN['uv'])}(?: \([^\r\n]+\))?",
                uv_version.stdout.strip(),
            )
            is None
        ):
            raise RuntimeError("uv executable version differs from the installed distribution")
        work.mkdir()
        recorder.environment["HYPOTHESIS_STORAGE_DIRECTORY"] = str(work / "hypothesis-storage")
        recorder.require_work_window("candidate artifact extraction", 120)
        core_wheel = artifact(candidate_root, candidate, "core", "wheel")
        core_sdist = artifact(candidate_root, candidate, "core", "sdist")
        benchmark_wheel = artifact(candidate_root, candidate, "benchmark", "wheel")
        benchmark_sdist = artifact(candidate_root, candidate, "benchmark", "sdist")
        consumer_wheel = artifact(candidate_root, candidate, "consumer", "wheel")
        consumer_sdist = artifact(candidate_root, candidate, "consumer", "sdist")
        core_test_manifest, core_test_contract, _core_test_identities = candidate_test_manifest(
            candidate_root, candidate, "core"
        )
        (
            _benchmark_test_manifest,
            benchmark_test_contract,
            benchmark_test_identities,
        ) = candidate_test_manifest(candidate_root, candidate, "benchmark")
        (
            _consumer_test_manifest,
            consumer_test_contract,
            consumer_test_identities,
        ) = candidate_test_manifest(candidate_root, candidate, "consumer")
        core_source = extract_sdist(core_sdist, work / "core")
        benchmark_source = extract_sdist(benchmark_sdist, work / "benchmark")
        consumer_source = extract_sdist(consumer_sdist, work / "consumer")
        recorder.require_work_window("declared source staging", 60)
        declared = work / "declared-source-packages"
        for source, name in (
            (core_source, "equiframe"),
            (benchmark_source, "equiframe-benchmark"),
        ):
            target = declared / name
            target.mkdir(parents=True)
            for filename in ("pyproject.toml", "uv.lock", "README.md"):
                shutil.copyfile(source / filename, target / filename)
            shutil.copytree(source / "src", target / "src")
        recorder.environment["EQUIFRAME_TEST_SOURCE_PACKAGES"] = str(declared)
        recorder.require_work_window("core profile matrix", 60)
        core_results = run_core_profiles(
            recorder,
            core_source,
            core_wheel,
            core_sdist,
            core_test_manifest,
            core_test_contract,
            uv,
            work,
        )
        receipt["core_profiles"] = core_results
        benchmark_results = []
        joint_runtime_lock: Path | None = None
        profile_probe = repository / "tools/maturity_lab/scripts/profile_boundary_probe.py"
        for profile in BENCHMARK_PROFILES:
            for endpoint in ENDPOINTS:
                recorder.require_work_window(f"benchmark {profile}/{endpoint} profile", 60)
                result, env_python, runtime_lock = run_benchmark_profile(
                    recorder,
                    core_wheel,
                    benchmark_wheel,
                    profile_probe,
                    uv,
                    profile,
                    endpoint,
                )
                benchmark_results.append(result)
                receipt["benchmark_profiles"] = benchmark_results
                destination = output / "benchmark" / profile / endpoint
                keep = result["status"] == "passed" and profile == "all" and endpoint == "latest"
                if keep:
                    kept_environment, joint_runtime_lock = env_python, runtime_lock
                clean_profile_output(destination, keep_venv=keep)
                recorder.save()
        receipt["benchmark_profiles"] = benchmark_results
        if kept_environment is None or joint_runtime_lock is None:
            raise RuntimeError("benchmark all/latest profile did not produce the joint environment")
        recorder.require_work_window("sdist rebuild and clean installation", 60)
        sdist_rebuild = run_sdist_rebuild(
            recorder,
            uv,
            work,
            joint_runtime_lock,
            {
                "core": (
                    core_source,
                    core_sdist,
                    core_wheel,
                    "equiframe",
                    str(candidate["artifacts"]["core"]["version"]),
                ),
                "benchmark": (
                    benchmark_source,
                    benchmark_sdist,
                    benchmark_wheel,
                    "equiframe-benchmark",
                    str(candidate["artifacts"]["benchmark"]["version"]),
                ),
                "consumer": (
                    consumer_source,
                    consumer_sdist,
                    consumer_wheel,
                    "equiframe-consumer-lab",
                    str(candidate["artifacts"]["consumer"]["version"]),
                ),
            },
        )
        recorder.require_work_window("joint installed consumer path", 60)
        receipt["joint"] = run_joint_consumer(
            recorder,
            repository,
            candidate_root,
            candidate,
            uv,
            kept_environment,
            joint_runtime_lock,
            benchmark_source,
            consumer_source,
            consumer_wheel,
            core_wheel,
            benchmark_wheel,
            benchmark_test_contract,
            benchmark_test_identities,
            consumer_test_contract,
            consumer_test_identities,
        )
        passed = (
            len(core_results) == 16
            and all(item["status"] == "passed" for item in core_results)
            and len(benchmark_results) == 10
            and all(item["status"] == "passed" for item in benchmark_results)
            and sdist_rebuild["status"] == "passed"
            and receipt["joint"]["status"] == "passed"
        )
        receipt["status"] = "passed" if passed else "failed"
        exit_code = 0 if passed else 1
    # Preserve root evidence even for an unexpected controller failure.
    except Exception as error:
        receipt["status"] = "failed"
        receipt["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        exit_code, inventory = finalize_cell(
            recorder,
            receipt,
            work=work,
            kept_environment=kept_environment,
            attestation_output=attestation_output,
            exit_code=exit_code,
        )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "output": str(output),
                "inventory_files": len(inventory["files"]),
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
