#!/usr/bin/env python3
"""Fail closed unless all 20 native cell artifacts form one complete matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PYTHONS = ("3.10", "3.11", "3.12", "3.13")
PLATFORMS = (
    ("linux-x64", "Linux", "x64"),
    ("linux-arm64", "Linux", "arm64"),
    ("windows-x64", "Windows", "x64"),
    ("macos-intel", "Darwin", "x64"),
    ("macos-arm64", "Darwin", "arm64"),
)
EXPECTED = {
    f"{label}-py{minor.replace('.', '')}": {
        "python": minor,
        "system": system,
        "architecture": architecture,
    }
    for label, system, architecture in PLATFORMS
    for minor in PYTHONS
}
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
FORBIDDEN_PARTS = {
    "venv",
    ".venv",
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
    "work",
}


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


def record(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular file: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def valid_record(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"sha256", "size_bytes"}
        and isinstance(value.get("sha256"), str)
        and SHA256.fullmatch(value["sha256"]) is not None
        and type(value.get("size_bytes")) is int
        and value["size_bytes"] >= 0
    )


def valid_distribution_inventory(value: object, name: str, version: str) -> bool:
    if (
        not isinstance(value, dict)
        or set(value) != {"name", "version", "file_count", "files_sha256", "files"}
        or value.get("name") != canonicalize_name(name)
        or value.get("version") != version
        or type(value.get("file_count")) is not int
        or value["file_count"] <= 0
        or not isinstance(value.get("files_sha256"), str)
        or SHA256.fullmatch(value["files_sha256"]) is None
        or not isinstance(value.get("files"), dict)
        or len(value["files"]) != value["file_count"]
    ):
        return False
    files = value["files"]
    folded: set[str] = set()
    for relative, member_record in files.items():
        if (
            not isinstance(relative, str)
            or not relative
            or "\\" in relative
            or any(ord(character) < 32 for character in relative)
            or relative.casefold() in folded
            or not valid_record(member_record)
        ):
            return False
        folded.add(relative.casefold())
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    files_sha256 = value["files_sha256"]
    return isinstance(files_sha256, str) and hashlib.sha256(encoded).hexdigest() == files_sha256


def read_object(path: Path) -> dict[str, Any]:
    loaded: object = json.loads(path.read_text("utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"JSON root is not an object: {path}")
    return cast(dict[str, Any], loaded)


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(temporary, path)


def safe_member(root: Path, name: str) -> Path:
    if "\\" in name:
        raise ValueError(f"nonportable evidence path: {name}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError(f"unsafe evidence path: {name}")
    path = root.joinpath(*pure.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"evidence path escapes cell root: {name}")
    return path


def verify_inventory(root: Path) -> tuple[dict[str, Any], Path]:
    inventory_path = root / "evidence-inventory.json"
    inventory = read_object(inventory_path)
    if inventory.get("schema") != "equiframe-universality-evidence-inventory-1":
        raise ValueError("cell evidence inventory schema differs")
    if inventory.get("unsigned") is not True:
        raise ValueError("cell evidence inventory trust flag differs")
    files = inventory.get("files")
    if not isinstance(files, dict) or "receipt.json" not in files:
        raise ValueError("cell evidence inventory lacks files or receipt")
    if "evidence-inventory.json" in files:
        raise ValueError("cell evidence inventory must not inventory itself")
    for name, expected_record in files.items():
        if not isinstance(name, str) or not valid_record(expected_record):
            raise ValueError("cell evidence inventory record is malformed")
        safe_member(root, name)
        pure = PurePosixPath(name)
        if FORBIDDEN_PARTS.intersection(pure.parts) or any(
            part.endswith("-pytest-tmp") for part in pure.parts
        ):
            raise ValueError(f"cell artifact retains a reconstructible directory: {name}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"cell attestation contains a symbolic link: {path}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path != inventory_path
    }
    if actual != set(files):
        raise ValueError("cell evidence artifact and its closed inventory differ")
    for name in actual:
        if record(safe_member(root, name)) != files[name]:
            raise ValueError(f"cell attestation bytes differ: {name}")
    return inventory, inventory_path


def exact_profile_scope(items: object, profiles: tuple[str, ...], expected_count: int) -> bool:
    if not isinstance(items, list) or len(items) != expected_count:
        return False
    observed = {
        (item.get("profile"), item.get("endpoint"))
        for item in items
        if isinstance(item, dict) and item.get("status") == "passed"
    }
    return observed == {(profile, endpoint) for profile in profiles for endpoint in ENDPOINTS}


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
        raise ValueError("cell core installed-suite skip contract differs")
    if expected_manifest is not None and (
        value.get("tests") != expected_manifest["test_count"]
        or value.get("junit_identities_sha256") != expected_manifest["junit_identities_sha256"]
        or value.get("identity_contract_matches") is not True
    ):
        raise ValueError("cell core installed-suite test denominator differs")


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
        raise ValueError("cell consumer 72-case summary fields or totals differ")
    records = value["records"]
    if not isinstance(records, list) or len(records) != 72:
        raise ValueError("cell consumer 72-case record count differs")
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
    for index, (case_record, expected_case) in enumerate(
        zip(records, expected_cases, strict=True), 1
    ):
        if not isinstance(case_record, dict) or set(case_record) != record_fields:
            raise ValueError(f"cell consumer case {index:03d} fields differ")
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
            not exact_value(case_record.get(name), expected)
            for name, expected in expected_values.items()
        ):
            raise ValueError(f"cell consumer case {case_id} outcome differs")
        elapsed = case_record["elapsed_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError(f"cell consumer case {case_id} elapsed time differs")
        command = case_record["command"]
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
            raise ValueError(f"cell consumer case {case_id} command differs")
        normalized_output = command[output_path_index].replace("\\", "/")
        suffix = f"/cases/{case_id}"
        if not normalized_output.endswith(suffix):
            raise ValueError(f"cell consumer case {case_id} output path differs")
        current_output_root = normalized_output[: -len(suffix)]
        expected_output_suffix = "/consumer-72-optimized" if optimized else "/consumer-72"
        if not current_output_root.endswith(expected_output_suffix):
            raise ValueError(f"cell consumer case {case_id} matrix output root differs")
        if interpreter is None:
            interpreter = command[0]
            data_root = command[data_index]
            output_root = current_output_root
        elif (
            command[0] != interpreter
            or command[data_index] != data_root
            or current_output_root != output_root
        ):
            raise ValueError("cell consumer commands do not share one execution context")


def verify_fault_checks(value: dict[str, Any]) -> None:
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
        raise ValueError("cell optimized fault receipt header differs")
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
        raise ValueError("cell optimized fault fields or states differ")


def verify_h_summary(
    value: dict[str, Any],
    scenario: str,
    expected_exit: int,
    *,
    bundle_manifest: Path | None = None,
) -> None:
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
        raise ValueError(f"cell optimized H {scenario} summary header differs")
    if scenario == "error":
        if set(value) != set(expected_top):
            raise ValueError("cell optimized H error summary has unexpected fields")
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
        raise ValueError(f"cell optimized H {scenario} state differs")
    if (
        bundle_manifest is None
        or bundle_manifest.is_symlink()
        or not bundle_manifest.is_file()
        or sha256(bundle_manifest) != value["bundle_manifest_sha256"]
    ):
        raise ValueError(f"cell optimized H {scenario} bundle manifest bytes differ")
    comparisons = value.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) != 2:
        raise ValueError(f"cell optimized H {scenario} comparisons are incomplete")
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
            raise ValueError(f"cell optimized H {scenario} comparison fields differ")
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
            raise ValueError(f"cell optimized H {scenario} comparison contract differs")


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
            raise ValueError("sdist rebuild lock is not exact and SHA-256 authenticated")
        name = canonicalize_name(requirement.name)
        if name in result:
            raise ValueError("sdist rebuild lock repeats a distribution")
        result[name] = specifications[0].version
    if not result:
        raise ValueError("sdist rebuild lock is empty")
    return result


def _valid_wheel_identity(value: object, distribution: str, version: str) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "distribution",
            "version",
            "build_tag",
            "tags",
            "member_count",
            "installed_member_count",
            "installed_payload_sha256",
            "record_valid",
        }
        and value.get("distribution") == canonicalize_name(distribution)
        and value.get("version") == version
        and isinstance(value.get("build_tag"), list)
        and all(isinstance(item, str) for item in value["build_tag"])
        and isinstance(value.get("tags"), list)
        and bool(value["tags"])
        and value["tags"] == sorted(set(value["tags"]))
        and all(isinstance(item, str) and item for item in value["tags"])
        and type(value.get("member_count")) is int
        and type(value.get("installed_member_count")) is int
        and value["member_count"] > 1
        and value["installed_member_count"] == value["member_count"] - 1
        and isinstance(value.get("installed_payload_sha256"), str)
        and SHA256.fullmatch(value["installed_payload_sha256"]) is not None
        and value.get("record_valid") is True
    )


def verify_sdist_rebuild(root: Path, receipt: dict[str, Any], candidate: dict[str, Any]) -> None:
    summary = receipt.get("sdist_rebuild")
    expected_summary_keys = {"status", "receipt", "receipt_record"}
    if (
        not isinstance(summary, dict)
        or set(summary) != expected_summary_keys
        or summary.get("status") != "passed"
        or summary.get("receipt") != "sdist-rebuild/receipt.json"
    ):
        raise ValueError("cell sdist rebuild summary differs")
    rebuild_path = safe_member(root, summary["receipt"])
    if record(rebuild_path) != summary.get("receipt_record"):
        raise ValueError("cell sdist rebuild receipt bytes differ")
    rebuild = read_object(rebuild_path)
    if (
        set(rebuild)
        != {
            "schema",
            "status",
            "started_at",
            "finished_at",
            "errors",
            "packages",
            "build_systems",
            "build_tools",
            "installation",
            "command_indexes",
        }
        or rebuild.get("schema") != "equiframe-universality-sdist-rebuild-1"
        or rebuild.get("status") != "passed"
        or rebuild.get("errors") != []
        or not all(
            isinstance(rebuild.get(name), str) and rebuild[name]
            for name in ("started_at", "finished_at")
        )
    ):
        raise ValueError("cell sdist rebuild receipt header differs")
    expected_packages = {
        "core": "equiframe",
        "benchmark": "equiframe-benchmark",
        "consumer": "equiframe-consumer-lab",
    }
    build_systems = rebuild.get("build_systems")
    packages = rebuild.get("packages")
    if (
        not isinstance(build_systems, dict)
        or set(build_systems) != set(expected_packages)
        or any(
            value
            != {
                "backend": EXPECTED_BUILD_BACKEND,
                "requirements": EXPECTED_BUILD_REQUIREMENTS,
            }
            for value in build_systems.values()
        )
        or not isinstance(packages, dict)
        or set(packages) != set(expected_packages)
    ):
        raise ValueError("cell sdist build-system or package inventory differs")
    for key, distribution in expected_packages.items():
        package = packages[key]
        artifact = candidate["artifacts"][key]
        version = str(artifact["version"])
        if (
            not isinstance(package, dict)
            or set(package)
            != {
                "distribution",
                "version",
                "source_sdist",
                "candidate_wheel",
                "candidate_identity",
                "rebuilt_wheel_path",
                "rebuilt_wheel",
                "rebuilt_identity",
                "installed_payload_match",
            }
            or package.get("distribution") != canonicalize_name(distribution)
            or package.get("version") != version
            or package.get("source_sdist") != artifact["sdist_record"]
            or package.get("candidate_wheel") != artifact["wheel_record"]
            or not valid_record(package.get("rebuilt_wheel"))
            or not isinstance(package.get("rebuilt_wheel_path"), str)
            or not package["rebuilt_wheel_path"].startswith("sdist-rebuild/rebuilt-wheels/")
            or not package["rebuilt_wheel_path"].endswith(".whl")
            or package.get("installed_payload_match") is not True
            or not _valid_wheel_identity(package.get("candidate_identity"), distribution, version)
            or package.get("rebuilt_identity") != package.get("candidate_identity")
        ):
            raise ValueError(f"cell {key} sdist rebuild identity or payload differs")

    build_tools = rebuild.get("build_tools")
    if (
        not isinstance(build_tools, dict)
        or set(build_tools) != {"frontend", "lock", "lock_record", "versions", "binding"}
        or build_tools.get("frontend") != {"name": "build", "version": PINNED_BUILD_FRONTEND}
        or build_tools.get("lock") != "sdist-rebuild/build-tools.lock"
    ):
        raise ValueError("cell sdist rebuild build-tool receipt differs")
    build_lock = safe_member(root, build_tools["lock"])
    if record(build_lock) != build_tools.get("lock_record"):
        raise ValueError("cell sdist rebuild build-tool lock bytes differ")
    build_versions = parse_hashed_lock(build_lock)
    build_binding = build_tools.get("binding")
    if (
        build_versions != build_tools.get("versions")
        or build_versions.get("build") != PINNED_BUILD_FRONTEND
        or any(
            build_versions.get(name) != version
            for name, version in EXPECTED_BUILD_REQUIREMENTS.items()
        )
        or not isinstance(build_binding, dict)
        or set(build_binding) != {"versions", "paths", "python", "system", "machine"}
        or build_binding.get("versions") != build_versions
        or build_binding.get("paths") != {}
    ):
        raise ValueError("cell sdist rebuild build-tool binding differs")

    installation = rebuild.get("installation")
    if (
        not isinstance(installation, dict)
        or set(installation)
        != {
            "runtime_lock",
            "runtime_lock_record",
            "runtime_versions",
            "binding",
            "binding_path",
            "binding_record",
            "api_probe",
            "api_probe_path",
            "api_probe_record",
            "cli",
            "pip_check",
        }
        or installation.get("runtime_lock") != "sdist-rebuild/runtime.lock"
        or installation.get("binding_path") != "sdist-rebuild/installed-binding.json"
        or installation.get("api_probe_path") != "sdist-rebuild/api-probe.json"
        or installation.get("pip_check") != "passed"
    ):
        raise ValueError("cell sdist rebuild installation receipt differs")
    runtime_lock = safe_member(root, installation["runtime_lock"])
    binding_path = safe_member(root, installation["binding_path"])
    api_path = safe_member(root, installation["api_probe_path"])
    if (
        record(runtime_lock) != installation.get("runtime_lock_record")
        or record(binding_path) != installation.get("binding_record")
        or record(api_path) != installation.get("api_probe_record")
    ):
        raise ValueError("cell sdist rebuild supporting evidence bytes differ")
    runtime_versions = parse_hashed_lock(runtime_lock)
    local_versions = {
        distribution: str(candidate["artifacts"][key]["version"])
        for key, distribution in expected_packages.items()
    }
    expected_versions = {**runtime_versions, **local_versions}
    binding = read_object(binding_path)
    api_probe = read_object(api_path)
    expected_api = {
        "accepted": True,
        "complete": True,
        "difference_records": 0,
        "state": "equivalent",
        "versions": local_versions,
    }
    requested = receipt.get("requested")
    actual = receipt.get("actual")
    if (
        runtime_versions != installation.get("runtime_versions")
        or binding != installation.get("binding")
        or not isinstance(binding, dict)
        or set(binding) != {"versions", "paths", "python", "system", "machine"}
        or binding.get("versions") != expected_versions
        or set(binding.get("paths", {})) != set(local_versions)
        or not all(isinstance(value, str) and value for value in binding["paths"].values())
        or not isinstance(requested, dict)
        or not isinstance(actual, dict)
        or binding.get("system") != requested.get("system")
        or binding.get("python") != actual.get("python_full")
        or api_probe != expected_api
        or installation.get("api_probe") != expected_api
        or installation.get("cli")
        != {
            name: {"entry_point": name, "status": "passed"}
            for name in ("equiframe", "equiframe-benchmark", "equiframe-consumer-lab")
        }
    ):
        raise ValueError("cell rebuilt-wheel binding, API or CLI evidence differs")

    indexes = rebuild.get("command_indexes")
    commands = receipt.get("commands")
    required_labels = {
        "sdist-resolve-build-tools",
        "sdist-build-tools-venv",
        "sdist-install-build-tools",
        "sdist-build-tools-binding",
        "sdist-rebuild-core",
        "sdist-rebuild-benchmark",
        "sdist-rebuild-consumer",
        "sdist-rebuild-runtime-venv",
        "sdist-rebuild-install-runtime",
        "sdist-rebuild-install-wheels",
        "sdist-rebuild-pip-check",
        "sdist-rebuild-binding",
        "sdist-rebuild-api",
        "sdist-rebuild-cli-equiframe",
        "sdist-rebuild-cli-equiframe-benchmark",
        "sdist-rebuild-cli-equiframe-consumer-lab",
    }
    if (
        not isinstance(indexes, list)
        or len(indexes) != len(required_labels)
        or indexes != list(range(indexes[0], indexes[0] + len(indexes)))
        or not isinstance(commands, list)
        or any(type(index) is not int or index < 0 or index >= len(commands) for index in indexes)
        or {
            commands[index].get("label")
            for index in indexes
            if isinstance(commands[index], dict) and commands[index].get("status") == "passed"
        }
        != required_labels
    ):
        raise ValueError("cell sdist rebuild command receipt differs")


def verify_joint(root: Path, receipt: dict[str, Any], candidate: dict[str, Any]) -> None:
    joint = receipt.get("joint")
    if not isinstance(joint, dict) or joint.get("status") != "passed":
        raise ValueError("cell installed benchmark/consumer journey did not pass")
    if joint.get("errors") != []:
        raise ValueError("cell installed journey retains errors")
    requested = receipt.get("requested")
    if not isinstance(requested, dict):
        raise TypeError("cell requested identity is absent")
    benchmark_manifest = candidate["test_manifests"]["benchmark"]
    consumer_manifest = candidate["test_manifests"]["consumer"]
    expected_test_versions = {
        "hypothesis": benchmark_manifest["hypothesis_version"],
        "pytest": benchmark_manifest["pytest_version"],
    }
    if expected_test_versions != {
        "hypothesis": consumer_manifest["hypothesis_version"],
        "pytest": consumer_manifest["pytest_version"],
    }:
        raise ValueError("candidate benchmark and consumer test-tool identities differ")
    test_tools = joint.get("test_tools")
    if (
        not isinstance(test_tools, dict)
        or set(test_tools) != {"versions", "binding", "lock", "lock_record"}
        or test_tools.get("versions") != expected_test_versions
        or not isinstance(test_tools.get("binding"), dict)
        or test_tools["binding"].get("versions") != expected_test_versions
        or not isinstance(test_tools.get("lock"), str)
    ):
        raise ValueError("cell installed test-tool identity differs")
    if record(safe_member(root, test_tools["lock"])) != test_tools.get("lock_record"):
        raise ValueError("cell test-tool lock bytes differ")
    for suite_name in ("benchmark_suite", "consumer_suite"):
        suite = joint.get(suite_name)
        manifest = benchmark_manifest if suite_name == "benchmark_suite" else consumer_manifest
        expected_skips = (
            benchmark_skip_contract(requested["system"], requested["python"])
            if suite_name == "benchmark_suite"
            else set()
        )
        expected_records = skip_records(expected_skips)
        if (
            not isinstance(suite, dict)
            or suite.get("accepted") is not True
            or not isinstance(suite.get("tests"), int)
            or suite["tests"] <= 0
            or any(suite.get(name) != 0 for name in ("failures", "errors"))
            or suite.get("skipped") != len(expected_skips)
            or suite["tests"] < len(expected_skips)
            or suite.get("expected_skips") != expected_records
            or suite.get("observed_skips") != expected_records
            or suite.get("tests") != manifest["test_count"]
            or suite.get("junit_identities_sha256") != manifest["junit_identities_sha256"]
            or suite.get("identity_contract_matches") is not True
        ):
            raise ValueError(f"cell {suite_name} receipt is incomplete")
    optimized_h = joint.get("optimized_h")
    expected_h = {"good": 0, "different": 1, "not_evaluable": 3, "error": 2}
    if not isinstance(optimized_h, dict) or set(optimized_h) != set(expected_h):
        raise ValueError("cell optimized H scenario inventory differs")
    for scenario, expected_exit in expected_h.items():
        item = optimized_h[scenario]
        expected_path = f"joint-all-latest/optimized-H-{scenario}/summary.json"
        expected_item_fields = {"path", "record"}
        if scenario != "error":
            expected_item_fields.update({"bundle_manifest", "bundle_manifest_record"})
        if (
            not isinstance(item, dict)
            or set(item) != expected_item_fields
            or item.get("path") != expected_path
        ):
            raise ValueError(f"cell optimized H {scenario} receipt path differs")
        path = safe_member(root, expected_path)
        if record(path) != item.get("record"):
            raise ValueError(f"cell optimized H {scenario} summary bytes differ")
        bundle_manifest = None
        if scenario != "error":
            expected_manifest = f"joint-all-latest/optimized-H-{scenario}/portable/bundle.json"
            if item.get("bundle_manifest") != expected_manifest:
                raise ValueError(f"cell optimized H {scenario} bundle path differs")
            bundle_manifest = safe_member(root, expected_manifest)
            if record(bundle_manifest) != item.get("bundle_manifest_record"):
                raise ValueError(f"cell optimized H {scenario} bundle bytes differ")
        verify_h_summary(
            read_object(path),
            scenario,
            expected_exit,
            bundle_manifest=bundle_manifest,
        )
    summary_name = joint.get("consumer_summary")
    if summary_name != "joint-all-latest/consumer-72/summary.json":
        raise TypeError("cell consumer summary path is absent")
    summary_path = safe_member(root, summary_name)
    if record(summary_path) != joint.get("consumer_summary_record"):
        raise ValueError("cell consumer summary bytes differ")
    verify_consumer_summary(
        read_object(summary_path),
        str(candidate["artifacts"]["consumer"]["version"]),
        optimized=False,
    )
    optimized_summary_name = joint.get("consumer_optimized_summary")
    if optimized_summary_name != "joint-all-latest/consumer-72-optimized/summary.json":
        raise TypeError("cell optimized consumer summary path is absent")
    optimized_summary_path = safe_member(root, optimized_summary_name)
    if record(optimized_summary_path) != joint.get("consumer_optimized_summary_record"):
        raise ValueError("cell optimized consumer summary bytes differ")
    verify_consumer_summary(
        read_object(optimized_summary_path),
        str(candidate["artifacts"]["consumer"]["version"]),
        optimized=True,
    )
    measurement = joint.get("measurement")
    if not isinstance(measurement, dict) or measurement.get("status") != "passed":
        raise ValueError("cell bounded measurement did not pass")
    for name, relative in (
        ("protocol", "joint-all-latest/measurements/protocol.json"),
        ("summary", "joint-all-latest/measurements/summary.json"),
        ("bounded_limit", "joint-all-latest/measurements/bounded-limit.json"),
    ):
        if record(safe_member(root, relative)) != measurement.get(name):
            raise ValueError(f"cell measurement {name} bytes differ")
    verify_measurement_documents(
        read_object(safe_member(root, "joint-all-latest/measurements/protocol.json")),
        read_object(safe_member(root, "joint-all-latest/measurements/summary.json")),
        read_object(safe_member(root, "joint-all-latest/measurements/bounded-limit.json")),
        requested_system=requested["system"],
        requested_architecture=requested["architecture"],
        requested_python=requested["python"],
    )
    faults = joint.get("consumer_faults")
    if not isinstance(faults, dict) or not isinstance(faults.get("path"), str):
        raise TypeError("cell consumer fault receipt is absent")
    fault_path = safe_member(root, faults["path"])
    if record(fault_path) != faults.get("record"):
        raise ValueError("cell consumer fault receipt differs")
    verify_fault_checks(read_object(fault_path))
    pair_path = safe_member(root, "joint-all-latest/installed-pair.json")
    if record(pair_path) != joint.get("installed_pair"):
        raise ValueError("cell installed pair bytes differ")
    pair = read_object(pair_path)
    expected_versions = {
        "equiframe": candidate["artifacts"]["core"]["version"],
        "equiframe-benchmark": candidate["artifacts"]["benchmark"]["version"],
        "equiframe-consumer-lab": candidate["artifacts"]["consumer"]["version"],
    }
    if any(
        pair.get("versions", {}).get(name) != version for name, version in expected_versions.items()
    ):
        raise ValueError("cell installed pair versions differ")
    expected_artifacts = {
        name: candidate["artifacts"][name]["wheel_record"]
        for name in ("core", "benchmark", "consumer")
    }
    if joint.get("artifact_records") != expected_artifacts:
        raise ValueError("cell installed artifact records differ")
    commands = receipt.get("commands")
    required_labels = {
        "toolchain-uv-version",
        "joint-resolve-test-tools",
        "joint-install-test-tools",
        "joint-test-tools-binding",
        "joint-pip-check",
        "benchmark-installed-suite",
        "consumer-installed-suite",
        "optimized-H-good",
        "optimized-H-different",
        "optimized-H-not_evaluable",
        "optimized-H-error",
        "bounded-measurements",
        "consumer-72-cases",
        "consumer-72-optimized-cases",
        "consumer-fault-checks",
        "installed-pair-binding",
    }
    passed_labels = (
        {
            item.get("label")
            for item in commands
            if isinstance(item, dict) and item.get("status") == "passed"
        }
        if isinstance(commands, list)
        else set()
    )
    if not required_labels <= passed_labels:
        raise ValueError("cell joint command receipts are incomplete")
    if not isinstance(commands, list) or any(
        not isinstance(item, dict) or item.get("status") != "passed" for item in commands
    ):
        raise ValueError("cell command receipts contain a non-passing command")
    toolchain = receipt.get("toolchain")
    if (
        not isinstance(toolchain, dict)
        or set(toolchain)
        != {
            "packages",
            "distributions",
            "requirements",
            "python_version",
            "python_implementation",
            "pip_version",
            "python_executable",
            "uv_executable",
            "uv_path",
        }
        or toolchain.get("packages") != PINNED_TOOLCHAIN
        or not isinstance(toolchain.get("distributions"), dict)
        or set(toolchain["distributions"]) != set(PINNED_TOOLCHAIN)
        or any(
            not valid_distribution_inventory(toolchain["distributions"].get(name), name, version)
            for name, version in PINNED_TOOLCHAIN.items()
        )
        or not isinstance(toolchain.get("requirements"), dict)
        or set(toolchain["requirements"]) != {"path", "record"}
        or toolchain["requirements"].get("path") != "toolchain/controller-requirements.txt"
        or record(safe_member(root, toolchain["requirements"]["path"]))
        != toolchain["requirements"].get("record")
        or toolchain.get("python_version") != receipt.get("actual", {}).get("python_full")
        or toolchain.get("python_implementation") != "CPython"
        or not isinstance(toolchain.get("pip_version"), str)
        or not toolchain["pip_version"]
        or not valid_record(toolchain.get("python_executable"))
        or not valid_record(toolchain.get("uv_executable"))
        or not isinstance(toolchain.get("uv_path"), str)
        or not toolchain["uv_path"]
    ):
        raise ValueError("cell controller toolchain identity differs")


def verify_candidate_test_manifests(root: Path, candidate: dict[str, Any]) -> None:
    expected_packages = {
        "core": "equiframe",
        "benchmark": "equiframe-benchmark",
        "consumer": "equiframe-consumer-lab",
    }
    manifests = candidate.get("test_manifests")
    if not isinstance(manifests, dict) or set(manifests) != set(expected_packages):
        raise ValueError("candidate test-manifest inventory differs")
    for key, package in expected_packages.items():
        expected = manifests[key]
        if not isinstance(expected, dict) or set(expected) != {
            "path",
            "record",
            "test_count",
            "junit_identities_sha256",
            "pytest_version",
            "hypothesis_version",
        }:
            raise ValueError(f"candidate {key} test-manifest record differs")
        path = safe_member(root, expected["path"])
        if record(path) != expected["record"]:
            raise ValueError(f"candidate {key} test-manifest bytes differ")
        loaded = read_object(path)
        tests = loaded.get("tests")
        if (
            loaded.get("schema") != "equiframe-test-manifest-1"
            or loaded.get("package") != package
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
            raise ValueError(f"candidate {key} test-manifest header differs")
        identities: list[tuple[str, str]] = []
        nodeids: list[str] = []
        for item in tests:
            if not isinstance(item, dict) or set(item) != {
                "nodeid",
                "classname",
                "name",
            }:
                raise ValueError(f"candidate {key} test identity differs")
            nodeid, classname, name = item["nodeid"], item["classname"], item["name"]
            if not all(isinstance(value, str) and value for value in (nodeid, classname, name)):
                raise ValueError(f"candidate {key} test identity is empty")
            nodeids.append(nodeid)
            identities.append((classname, name))
        if len(nodeids) != len(set(nodeids)) or len(identities) != len(set(identities)):
            raise ValueError(f"candidate {key} test identities are duplicated")
        encoded = json.dumps(sorted(identities), separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != expected["junit_identities_sha256"]:
            raise ValueError(f"candidate {key} JUnit identity digest differs")


def verify_candidate(root: Path) -> tuple[dict[str, Any], str]:
    path = root / "candidate.json"
    candidate = read_object(path)
    if candidate.get("schema") != "equiframe-universality-actions-candidate-1":
        raise ValueError("candidate schema differs")
    if (
        candidate.get("credentials_included") is not False
        or candidate.get("results_included") is not False
    ):
        raise ValueError("candidate scope flags differ")
    if candidate.get("required_python_versions") != list(PYTHONS):
        raise ValueError("candidate Python scope differs")
    expected_platforms = [
        {"system": system, "architecture": architecture}
        for _label, system, architecture in PLATFORMS
    ]
    if candidate.get("required_native_platforms") != expected_platforms:
        raise ValueError("candidate native platform scope differs")
    verify_candidate_test_manifests(root, candidate)
    files = candidate.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("candidate inventory is absent")
    if "candidate.json" in files:
        raise ValueError("candidate inventory must not inventory itself")
    for name, expected_record in files.items():
        if (
            not isinstance(name, str)
            or not valid_record(expected_record)
            or record(safe_member(root, name)) != expected_record
        ):
            raise ValueError(f"candidate member differs: {name}")
    for item in root.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"candidate contains a symbolic link: {item}")
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and not item.is_symlink() and item != path
    }
    if actual != set(files):
        raise ValueError("candidate has missing or additional files")
    return candidate, sha256(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--github-workflow-ref", required=True)
    parser.add_argument("--github-workflow-sha", required=True)
    parser.add_argument("--candidate-job-result", required=True)
    parser.add_argument("--matrix-job-result", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        parser.error("output must be new")
    if (
        not args.run_id.isdigit()
        or not args.run_attempt.isdigit()
        or int(args.run_id) <= 0
        or int(args.run_attempt) <= 0
        or REPOSITORY_NAME.fullmatch(args.github_repository) is None
        or GIT_COMMIT.fullmatch(args.github_workflow_sha) is None
        or not args.github_workflow_ref
    ):
        parser.error("workflow execution identity is malformed")
    output.mkdir(parents=True)
    workflow_execution = {
        "provider": "github-actions",
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "repository": args.github_repository,
        "workflow_ref": args.github_workflow_ref,
        "workflow_sha": args.github_workflow_sha,
    }
    result: dict[str, Any] = {
        "schema": "equiframe-universality-actions-matrix-1",
        "status": "running",
        "started_at": now(),
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "workflow_execution": workflow_execution,
        "candidate_job_result": args.candidate_job_result,
        "matrix_job_result": args.matrix_job_result,
        "required_cell_count": 20,
        "aggregation_scope": (
            "Compact per-cell attestations; every full evidence tree remains a separate "
            "required workflow artifact"
        ),
        "cells": [],
        "errors": [],
        "receipts_authenticated": False,
        "independent_human_acceptance": False,
    }
    exit_code = 1
    try:
        expected_environment = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": args.run_id,
            "GITHUB_RUN_ATTEMPT": args.run_attempt,
            "GITHUB_JOB": "aggregate",
            "GITHUB_REPOSITORY": args.github_repository,
            "GITHUB_WORKFLOW_REF": args.github_workflow_ref,
            "GITHUB_WORKFLOW_SHA": args.github_workflow_sha,
        }
        if any(os.environ.get(name) != value for name, value in expected_environment.items()):
            raise ValueError("GitHub Actions aggregation environment differs")
        candidate, candidate_hash = verify_candidate(args.candidate.resolve())
        if candidate.get("workflow_execution") != workflow_execution:
            raise ValueError("candidate belongs to a different workflow execution")
        if args.candidate_job_result != "success" or args.matrix_job_result != "success":
            result["errors"].append(
                {
                    "stage": "workflow_jobs",
                    "candidate": args.candidate_job_result,
                    "native_matrix": args.matrix_job_result,
                }
            )
        result["candidate_manifest_sha256"] = candidate_hash
        result["source"] = candidate.get("source")
        result["artifacts"] = candidate.get("artifacts")
        common_source = None
        common_artifacts = None
        for cell, requested in EXPECTED.items():
            directory = args.cells.resolve() / (
                f"universality-cell-{cell}-{args.run_id}-{args.run_attempt}"
            )
            item: dict[str, Any] = {
                "cell": cell,
                "requested": requested,
                "status": "running",
            }
            result["cells"].append(item)
            try:
                if not directory.is_dir() or directory.is_symlink():
                    raise ValueError("cell artifact directory is absent or linked")
                inventory, inventory_path = verify_inventory(directory)
                receipt_path = directory / "receipt.json"
                receipt = read_object(receipt_path)
                if receipt.get("schema") != "equiframe-universality-actions-cell-1":
                    raise ValueError("cell receipt schema differs")
                if receipt.get("requested") != requested:
                    raise ValueError("cell requested identity differs")
                actual = receipt.get("actual", {})
                if not isinstance(actual, dict) or any(
                    actual.get(name) != value for name, value in requested.items()
                ):
                    raise ValueError("cell actual native identity differs")
                if receipt.get("candidate_manifest_sha256") != candidate_hash:
                    raise ValueError("cell used a different candidate manifest")
                if receipt.get("status") != "passed":
                    raise ValueError("cell receipt is not passed")
                if receipt.get("errors") != []:
                    raise ValueError("cell receipt retains errors")
                execution = receipt.get("execution")
                expected_runner_os = {
                    "Linux": "Linux",
                    "Windows": "Windows",
                    "Darwin": "macOS",
                }[requested["system"]]
                expected_runner_arch = "X64" if requested["architecture"] == "x64" else "ARM64"
                expected_execution = {
                    **workflow_execution,
                    "job": "native-cell",
                    "runner_os": expected_runner_os,
                    "runner_arch": expected_runner_arch,
                    "runner_environment": "github-hosted",
                    "cell_id": cell,
                }
                if (
                    not isinstance(execution, dict)
                    or any(
                        execution.get(name) != value for name, value in expected_execution.items()
                    )
                    or not isinstance(execution.get("runner_name"), str)
                    or not execution["runner_name"]
                    or not isinstance(execution.get("runner_image_os"), str)
                    or not execution["runner_image_os"]
                    or not isinstance(execution.get("runner_image_version"), str)
                    or not execution["runner_image_version"]
                ):
                    raise ValueError("cell GitHub Actions execution identity differs")
                if receipt.get("deadline_seconds") != 19_800:
                    raise ValueError("cell cleanup/upload deadline reserve differs")
                if receipt.get("receipts_authenticated") is not False:
                    raise ValueError("cell receipt authentication flag differs")
                if not exact_profile_scope(receipt.get("core_profiles"), CORE_PROFILES, 16):
                    raise ValueError("cell core profile scope is incomplete")
                core_profiles = receipt["core_profiles"]
                for core_profile in core_profiles:
                    if core_profile.get("profile") == "all":
                        verify_core_suite_summary(
                            core_profile.get("installed_suite"),
                            requested["system"],
                            candidate["test_manifests"]["core"],
                        )
                    elif "installed_suite" in core_profile:
                        raise ValueError("cell non-all core profile has a full-suite claim")
                if not exact_profile_scope(
                    receipt.get("benchmark_profiles"), BENCHMARK_PROFILES, 10
                ):
                    raise ValueError("cell benchmark profile scope is incomplete")
                verify_sdist_rebuild(directory, receipt, candidate)
                verify_joint(directory, receipt, candidate)
                if common_source is None:
                    common_source = receipt.get("source")
                    common_artifacts = receipt.get("artifacts")
                if (
                    receipt.get("source") != common_source
                    or receipt.get("artifacts") != common_artifacts
                    or receipt.get("source") != candidate.get("source")
                    or receipt.get("artifacts") != candidate.get("artifacts")
                ):
                    raise ValueError("cell source/artifact identity differs across the matrix")
                item.update(
                    status="passed",
                    receipt_record=record(receipt_path),
                    inventory_record=record(inventory_path),
                    inventoried_files=len(inventory["files"]),
                )
            # Every malformed cell must become a durable failed-cell record.
            except Exception as error:
                item.update(
                    status="failed",
                    error={"type": type(error).__name__, "message": str(error)},
                )
        expected_directories = {
            f"universality-cell-{cell}-{args.run_id}-{args.run_attempt}" for cell in EXPECTED
        }
        unexpected = sorted(
            path.name
            for path in args.cells.resolve().iterdir()
            if path.name not in expected_directories
        )
        if unexpected:
            result["errors"].append({"unexpected_cell_artifacts": unexpected})
        passed = (
            len(result["cells"]) == 20
            and all(item["status"] == "passed" for item in result["cells"])
            and not result["errors"]
        )
        result["status"] = "passed" if passed else "failed"
        exit_code = 0 if passed else 1
    # Preserve a machine-readable receipt even for an unexpected verifier fault.
    except Exception as error:
        result["status"] = "failed"
        result["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        result["finished_at"] = now()
        result["counts"] = {
            status: sum(item.get("status") == status for item in result["cells"])
            for status in ("passed", "failed", "running")
        }
        write_json(output / "matrix-receipt.json", result)
        evidence = {
            "schema": "equiframe-universality-matrix-inventory-1",
            "files": {"matrix-receipt.json": record(output / "matrix-receipt.json")},
            "unsigned": True,
        }
        write_json(output / "evidence-inventory.json", evidence)
    print(json.dumps({"status": result["status"], "counts": result["counts"]}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
