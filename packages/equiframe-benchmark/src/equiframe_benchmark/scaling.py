"""Bounded exact-comparison engineering measurements with crash-safe finalization.

This extends the benchmark distribution, but does not change the scientific
CostProtocol, labels, detector evaluation, or the quarantined core benchmark.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import statistics
import sys
from datetime import datetime
from datetime import timezone as _timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import uuid4

import equiframe as ef
from equiframe._regular_io import regular_directory, regular_files
from equiframe.evidence import describe_file, inventory, load_json, verify_files
from equiframe.local import local_path
from pydantic import model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text, digest
from equiframe_benchmark.scale_io import save_scale_document
from equiframe_benchmark.scale_process import ProcessObservation, supervise
from equiframe_benchmark.scale_types import (
    SCALE_SAMPLE_INTERVAL_SECONDS,
    ScaleSpec,
    ScaleTrial,
    ScaleWorkerCompletion,
)

UTC = _timezone.utc


class _SysconfOS(Protocol):
    def sysconf(self, name: str, /) -> int: ...


_WINDOWS_UNAME_ENV = (
    "EQUIFRAME_SUPERVISED_SYSTEM",
    "EQUIFRAME_SUPERVISED_RELEASE",
    "EQUIFRAME_SUPERVISED_VERSION",
    "EQUIFRAME_SUPERVISED_MACHINE",
)
_WINDOWS_WORKER_BOOTSTRAP = (
    "import os,platform,runpy;"
    "platform._uname_cache=platform.uname_result("
    "os.environ.pop('EQUIFRAME_SUPERVISED_SYSTEM'),'',"
    "os.environ.pop('EQUIFRAME_SUPERVISED_RELEASE'),"
    "os.environ.pop('EQUIFRAME_SUPERVISED_VERSION'),"
    "os.environ.pop('EQUIFRAME_SUPERVISED_MACHINE'));"
    "runpy.run_module('equiframe_benchmark._scale_workload',run_name='__main__')"
)


class ScaleRun(Document):
    run_id: Text
    spec: ScaleSpec
    spec_sha256: Digest
    started_at: Text
    environment: dict[str, str]
    environment_origin: Literal["worker", "parent_only_worker_unavailable"]
    producer_runtime_matches_parent: bool | None
    process: ProcessObservation
    worker_finalized: bool
    trials: tuple[ScaleTrial, ...]
    issues: tuple[Text, ...]
    evidence: tuple[ef.EvidenceFile, ...]
    removed_temporary_bytes: dict[str, int]

    @model_validator(mode="after")
    def bound(self) -> Self:
        if self.spec_sha256 != digest(self.spec):
            raise ValueError("scale specification fingerprint mismatch")
        if any(trial.case_sha256 != self.spec_sha256 for trial in self.trials):
            raise ValueError("scale trial belongs to another specification")
        if tuple(trial.repetition for trial in self.trials) != tuple(range(len(self.trials))):
            raise ValueError("retain an ordered prefix of actual repetitions")
        if len(self.trials) > self.spec.repetitions:
            raise ValueError("too many repetitions")
        if self.worker_finalized and (
            self.environment_origin != "worker" or self.producer_runtime_matches_parent is None
        ):
            raise ValueError("finalized worker must retain its actual producer environment")
        if self.environment_origin != "worker" and self.producer_runtime_matches_parent is not None:
            raise ValueError("missing worker environment cannot claim a runtime binding")
        if self.worker_finalized and len(self.trials) != self.spec.repetitions:
            raise ValueError("worker finalization requires every repetition")
        from equiframe_benchmark._scale_workload import make_contract

        expected_contract = make_contract(self.spec)
        for trial in self.trials:
            expected_cache = (
                "fresh_process_os_cache_uncontrolled"
                if trial.repetition == 0
                else "warm_process_os_cache_uncontrolled"
            )
            if trial.cache_state != expected_cache:
                raise ValueError("cache declaration must match process execution order")
            if (
                trial.comparison.spec.contract != expected_contract
                or trial.comparison.spec.policy != ef.ComparisonPolicy()
                or trial.comparison.reference != "expected"
            ):
                raise ValueError("comparison must use the complete declared exact contract")
            if trial.comparison.complete and (
                trial.comparison.counts.left_rows != self.spec.rows
                or trial.comparison.counts.right_rows != self.spec.rows
            ):
                raise ValueError("complete trial must compare both entire generated inputs")
            if bool(trial.baselines) != self.spec.run_baselines:
                raise ValueError("trial must preserve the requested baseline coverage")
            if trial.comparison.options != self.spec.comparison_options:
                raise ValueError("comparison must preserve the declared resource budgets")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence paths must be unique")
        return self

    @property
    def complete(self) -> bool:
        """A verified measured operation; resource sampling quality remains separate."""
        return (
            self.worker_finalized
            and self.producer_runtime_matches_parent is True
            and self.process.exit_code == 0
            and self.process.termination_reason == "exited"
            and not self.issues
            and all(
                trial.comparison.complete
                and trial.comparison.state == self.spec.expected_state
                and all(
                    baseline.state in ("not_applicable", "not_available", self.spec.expected_state)
                    for baseline in trial.baselines
                )
                for trial in self.trials
            )
        )

    @property
    def resource_measurement_complete(self) -> bool:
        return (
            len(self.trials) == self.spec.repetitions
            and all(trial.resources.state == "complete" for trial in self.trials)
            and self.process.resource_contract_complete
        )


class ScaleFinalization(Document):
    result: ef.EvidenceFile
    complete: bool
    protocol: Literal["atomic_manifest_after_child_exit_and_verified_inventory"] = (
        "atomic_manifest_after_child_exit_and_verified_inventory"
    )


def _environment() -> dict[str, str]:
    result = {
        "python": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "logical_cpus": str(os.cpu_count()),
        "cache": "First trial has a fresh worker; OS page cache never flushed or controlled",
        "engine_memory": "No engine allocator peak available; observed RSS is the entire worker",
        "process_resources": (
            "Direct worker: all repetitions, baselines, imports and in-worker sampler"
        ),
        "excluded_resources": (
            "External supervisor CPU/RSS and operating system overhead; "
            "no child processes supported"
        ),
        "trial_resources": "EquiFrame stages only; baseline services measured separately",
        "hard_memory_or_disk_quota": "none; sampled reactive termination may overshoot",
    }
    for name in ("memory.max", "cpu.max"):
        try:
            result["cgroup_" + name] = (Path("/sys/fs/cgroup") / name).read_text().strip()
        except OSError:
            result["cgroup_" + name] = "not_available"
    for package in (
        "equiframe",
        "equiframe-benchmark",
        "pyarrow",
        "pandas",
        "polars",
        "duckdb",
        "psutil",
        "datacompy",
    ):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not_installed"
    try:
        result["physical_memory_bytes"] = str(
            cast(_SysconfOS, os).sysconf("SC_PAGE_SIZE")
            * cast(_SysconfOS, os).sysconf("SC_PHYS_PAGES")
        )
    except (ValueError, OSError, AttributeError):
        result["physical_memory_bytes"] = "not_available"
    try:
        cpu = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
        result["cpu_model"] = cpu
    except (OSError, StopIteration):
        result["cpu_model"] = platform.processor() or "not_available"
    # Bind runtime code bytes without storing usernames, full paths or environment secrets.
    for label, module in (("core", ef), ("benchmark", sys.modules[__package__])):
        root = Path(module.__file__ or "").parent
        hashed = hashlib.sha256()
        for path in sorted(root.rglob("*.py")):
            hashed.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
        result[label + "_python_sources_sha256"] = hashed.hexdigest()
    return result


def _worker_launch(
    spec_path: Path, worker: Path, environment: dict[str, str]
) -> tuple[list[str], dict[str, str]]:
    """Prepare a worker command without permitting a Windows platform probe child."""
    command = [
        sys.executable,
        "-I",
        "-m",
        "equiframe_benchmark._scale_workload",
        str(spec_path),
        str(worker),
    ]
    if os.name != "nt":
        return command, environment
    facts = platform.uname()
    prepared = {
        key: value
        for key, value in environment.items()
        if key.casefold() not in {name.casefold() for name in _WINDOWS_UNAME_ENV}
    }
    # uname_result exposes five constructor inputs; processor is a lazy property.
    prepared[_WINDOWS_UNAME_ENV[0]] = facts.system
    prepared[_WINDOWS_UNAME_ENV[1]] = facts.release
    prepared[_WINDOWS_UNAME_ENV[2]] = facts.version
    prepared[_WINDOWS_UNAME_ENV[3]] = facts.machine
    return [
        sys.executable,
        "-I",
        "-c",
        _WINDOWS_WORKER_BOOTSTRAP,
        str(spec_path),
        str(worker),
    ], prepared


def _verify_trial(directory: Path, trial: ScaleTrial) -> None:
    verify_files(directory, trial.evidence)
    actual = {
        path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()
    }
    listed = {item.path: item for item in trial.evidence}
    if actual != set(listed):
        raise ValueError("trial inventory must cover exactly its retained files")
    comparison = trial.comparison
    manifest = directory / "comparison" / comparison.comparison_id / "comparison.json"
    if (
        ef.read_comparison(manifest) != comparison
        or ef.read_comparison(directory / "serialized-comparison.json") != comparison
    ):
        raise ValueError("trial comparison manifests contradict the observed outcome")
    references = [comparison.differences]
    references.extend(
        source.data for source in (comparison.left, comparison.right) if source is not None
    )
    for reference in references:
        path = local_path(reference).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("trial artifact escapes its retained evidence")
        relative = path.relative_to(directory.resolve()).as_posix()
        observed = listed.get(relative)
        if observed is None or (observed.sha256, observed.size_bytes) != (
            reference.sha256,
            reference.size_bytes,
        ):
            raise ValueError("comparison artifact does not match the retained inventory")
    # Reading a receipt verifies evidence consistency, not authenticity or a new comparison.


def _read_worker(
    spec: ScaleSpec, directory: Path
) -> tuple[tuple[ScaleTrial, ...], bool, tuple[str, ...], dict[str, str] | None]:
    trials: list[ScaleTrial] = []
    issues: list[str] = []
    for repetition in range(spec.repetitions):
        path = directory / f"trial-{repetition:03d}.json"
        if not path.is_file():
            break
        try:
            trial = load_json(ScaleTrial, path)
            _verify_trial(directory / f"trial-{repetition:03d}", trial)
            trials.append(trial)
        except Exception as error:
            issues.append("invalid_trial_" + type(error).__name__)
            break
    finalized = False
    environment = None
    try:
        completion = load_json(ScaleWorkerCompletion, directory / "worker-completed.json")
        expected = tuple(f"trial-{i:03d}.json" for i in range(spec.repetitions))
        if (
            completion.case_sha256 != digest(spec)
            or tuple(item.path for item in completion.trial_files) != expected
        ):
            raise ValueError("worker finalization does not bind the requested repetitions")
        verify_files(directory, completion.trial_files)
        finalized = len(trials) == spec.repetitions
        environment = completion.environment
    except Exception as error:
        issues.append("missing_or_invalid_worker_completion_" + type(error).__name__)
    return tuple(trials), finalized, tuple(issues), environment


def _clean_worker_temporaries(directory: Path) -> tuple[dict[str, int], tuple[str, ...]]:
    """After reaping, remove only this comparator's known disposable SQLite files."""
    removed: dict[str, int] = {}
    issues: list[str] = []
    for trial in directory.glob("trial-[0-9][0-9][0-9]"):
        for comparison in (trial / "comparison").glob("comparison-*"):
            for name in (
                "work.sqlite",
                "work.sqlite-journal",
                "work.sqlite-wal",
                "work.sqlite-shm",
            ):
                path = comparison / name
                if not path.exists():
                    continue
                try:
                    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                        raise ValueError("temporary path escaped owned directory")
                    size = path.stat().st_size
                    path.unlink()
                    removed[path.relative_to(directory).as_posix()] = size
                except (OSError, ValueError) as error:
                    issues.append("temporary_cleanup_failed_" + type(error).__name__)
    return removed, tuple(issues)


def measure_scale(spec: ScaleSpec, *, work_dir: Path) -> ScaleRun:
    """Run one bounded case in an isolated trusted child, retaining every failure.

    The output is local synthetic evidence. A killed process, missing completion,
    mismatched verdict or incomplete comparison is never a successful scale run.
    Thresholds terminate reactively; they are not kernel RSS/disk hard quotas.
    """
    spec = ScaleSpec.model_validate(spec)
    work_dir.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(work_dir).free < spec.disk_budget_bytes + 256 * 1024**2:
        raise ValueError("insufficient free disk for the admitted budget plus safety margin")
    identifier = "scale-" + uuid4().hex
    directory = work_dir.resolve() / identifier
    directory.mkdir(parents=True, mode=0o700)
    worker = directory / "worker"
    worker.mkdir(mode=0o700)
    save_scale_document(spec, directory / "spec.json")
    started = datetime.now(UTC).isoformat()
    parent_environment = _environment()
    launch_environment = {
        **os.environ,
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "POLARS_MAX_THREADS": "1",
    }
    command, launch_environment = _worker_launch(
        directory / "spec.json", worker, launch_environment
    )
    process = supervise(
        command,
        directory=worker,
        timeout_seconds=spec.timeout_seconds,
        rss_budget_bytes=spec.rss_budget_bytes,
        disk_budget_bytes=spec.disk_budget_bytes,
        sample_interval_seconds=SCALE_SAMPLE_INTERVAL_SECONDS,
        env=launch_environment,
    )
    trials, finalized, issues, worker_environment = _read_worker(spec, worker)
    binding = None if worker_environment is None else worker_environment == parent_environment
    if binding is False:
        issues += ("worker_producer_environment_mismatch",)
    if _environment() != parent_environment:
        issues += ("parent_producer_environment_changed_during_run",)
    if process.cleanup_reaped:
        removed, cleanup_issues = _clean_worker_temporaries(worker)
        issues += cleanup_issues
    else:
        removed = {}
        issues += ("child_not_reaped_cleanup_unsafe",)
    if process.exit_code != 0 or process.termination_reason != "exited":
        issues += ("worker_process_did_not_exit_normally",)
    result = ScaleRun(
        run_id=identifier,
        spec=spec,
        spec_sha256=digest(spec),
        started_at=started,
        environment=worker_environment if worker_environment is not None else parent_environment,
        environment_origin="worker"
        if worker_environment is not None
        else "parent_only_worker_unavailable",
        producer_runtime_matches_parent=binding,
        process=process,
        worker_finalized=finalized,
        trials=trials,
        issues=issues,
        evidence=inventory(directory),
        removed_temporary_bytes=removed,
    )
    save_scale_document(result, directory / "scale.json")
    save_scale_document(
        ScaleFinalization(
            result=describe_file(directory / "scale.json", directory), complete=result.complete
        ),
        directory / "finished.json",
    )
    return result


def read_scale(directory: Path) -> ScaleRun:
    """Verify atomic finalization and every retained file; never execute a source."""
    directory = regular_directory(directory)
    try:
        final = load_json(ScaleFinalization, directory / "finished.json")
    except ef.ArtifactIOError as error:
        cause = error.__cause__
        if isinstance(cause, OSError):
            raise type(cause)(cause.errno, "scale finalization is missing or unreadable") from None
        raise ef.ArtifactIntegrityError("scale finalization is missing or unreadable") from None
    if final.result.path != "scale.json":
        raise ValueError("unexpected scale result path")
    verify_files(directory, (final.result,))
    result = load_json(ScaleRun, directory / "scale.json")
    verify_files(directory, result.evidence)
    expected = {item.path for item in result.evidence} | {"scale.json", "finished.json"}
    actual = {path.relative_to(directory).as_posix() for path in regular_files(directory)}
    if actual != expected:
        raise ValueError("scale evidence inventory changed")
    spec = load_json(ScaleSpec, directory / "spec.json")
    if spec != result.spec:
        raise ValueError("scale specification changed")
    trials, finalized, issues, worker_environment = _read_worker(spec, directory / "worker")
    if (
        trials != result.trials
        or finalized != result.worker_finalized
        or not set(issues) <= set(result.issues)
        or (worker_environment is not None and worker_environment != result.environment)
        or (worker_environment is None) != (result.environment_origin != "worker")
    ):
        raise ValueError("scale worker evidence changed")
    if final.complete != result.complete:
        raise ValueError("finalization contradicts the actual measurement outcome")
    return result


def summarize_scale(result: ScaleRun) -> dict[str, object]:
    """Retain failed counts; statistics use only complete, correct measured trials."""
    valid = tuple(
        trial
        for trial in result.trials
        if trial.comparison.complete and trial.comparison.state == result.spec.expected_state
    )
    statistics_by_cache: dict[str, object] = {}
    for cache in ("fresh_process_os_cache_uncontrolled", "warm_process_os_cache_uncontrolled"):
        subset = tuple(trial for trial in valid if trial.cache_state == cache)
        values = [trial.end_to_end_seconds for trial in subset]
        statistics_by_cache[cache] = {
            "n": len(values),
            "median_seconds": statistics.median(values) if values else None,
            "minimum_seconds": min(values) if values else None,
            "maximum_seconds": max(values) if values else None,
            "stages": {
                name: {
                    "median_seconds": statistics.median(
                        stage.wall_seconds
                        for trial in subset
                        for stage in trial.stages
                        if stage.name == name
                    ),
                    "minimum_seconds": min(
                        stage.wall_seconds
                        for trial in subset
                        for stage in trial.stages
                        if stage.name == name
                    ),
                    "maximum_seconds": max(
                        stage.wall_seconds
                        for trial in subset
                        for stage in trial.stages
                        if stage.name == name
                    ),
                }
                for name in (subset[0].stages[i].name for i in range(len(subset[0].stages)))
            }
            if subset
            else {},
        }
    return {
        "run_id": result.run_id,
        "case_id": result.spec.case_id,
        "complete": result.complete,
        "resource_measurement_complete": result.resource_measurement_complete,
        "resource_measurement_contract": {
            "id": result.process.measurement_contract,
            "platform": result.process.measurement_platform,
            "metrics": [item.model_dump(mode="json") for item in result.process.metric_coverage],
        },
        "requested_repetitions": result.spec.repetitions,
        "observed_repetitions": len(result.trials),
        "correct_complete_repetitions": len(valid),
        "unsuccessful_or_missing_repetitions": result.spec.repetitions - len(valid),
        "resource_quality": [trial.resources.state for trial in result.trials],
        "process": result.process.model_dump(mode="json"),
        "statistics_by_cache": statistics_by_cache,
        "issues": result.issues,
    }
