"""Paired operational costs on fixed captures, without ETL, labels or fitting.

Trusted actions include their internal artifact verification, rereads and evidence
publication. Initial DW reading, transformation and capture are outside this API.
RSS is an absolute sampled process maximum (a lower bound), never an allocation
delta or a hard quota. CPU includes the sampler thread and excludes subprocesses.
"""

from __future__ import annotations

import hashlib
import platform
import random
import time
from collections.abc import Callable
from datetime import datetime
from datetime import timezone as _timezone
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from itertools import pairwise
from pathlib import Path
from threading import Event, Thread
from typing import Annotated, Literal, Protocol, cast
from uuid import uuid4

import equiframe as ef
from equiframe._base import strict_int_literal
from equiframe._regular_io import open_regular_file
from equiframe.evidence import inventory, verify_files
from equiframe.local import local_path
from equiframe.profile_types import profile_digest
from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import Digest, Document, Text, digest

UTC = _timezone.utc

Seconds = Annotated[float, Field(ge=0)]
Bytes = Annotated[int, Field(ge=0)]
Method = Literal["profile_m", "comparison"]
OperationState = Literal[
    "completed", "not_evaluable", "failed", "cancelled", "timeout", "resource_exhausted"
]


class CostProtocol(Document):
    warmups: Annotated[Literal[1], BeforeValidator(strict_int_literal)] = 1
    repetitions: Annotated[Literal[5], BeforeValidator(strict_int_literal)] = 5
    seed: Annotated[int, Field(ge=0, le=2**32 - 1)]
    sample_interval_seconds: Annotated[float, Field(ge=0.001, le=1)] = 0.01
    cache_policy: Text
    threads: Annotated[int, Field(gt=0)]
    memory_budget_bytes: Annotated[int, Field(gt=0)] | None = None
    concurrent_loads: Text
    controls_rationale: Text


class CostSpec(Document):
    case_id: Text
    execution: ef.ExecutionResult
    reference: ef.ArtifactRef | ef.TableArtifact | ef.ExecutionResult
    profile: ef.ProfileSpec
    detector_bundle_sha256: Digest
    comparison_policy: ef.ComparisonPolicy
    comparison_reference: Literal["peer", "expected"] = "expected"
    profile_options: ef.ProfileOptions = ef.ProfileOptions()
    comparison_options: ef.ComparisonOptions = ef.ComparisonOptions()
    protocol: CostProtocol

    @model_validator(mode="after")
    def materialized(self) -> Self:
        if self.execution.state != "completed":
            raise ValueError("costs require an already completed captured execution")
        if self.profile.family != self.execution.plan.contract.family:
            raise ValueError("cost profile family must match the captured contract")
        if isinstance(self.reference, ef.ExecutionResult) and self.reference.state != "completed":
            raise ValueError("reference execution must already be completed")
        by_uri: dict[str, ef.ArtifactRef] = {}
        for ref in self.artifacts:
            if ref.format not in ("arrow", "parquet"):
                raise ValueError("costs require captured Arrow or Parquet tables")
            if ref.uri in by_uri and by_uri[ref.uri] != ref:
                raise ValueError("one URI cannot declare different captured contents")
            by_uri[ref.uri] = ref
        return self

    @property
    def artifacts(self) -> tuple[ef.ArtifactRef, ...]:
        refs = list(_execution_refs(self.execution))
        if isinstance(self.reference, ef.ExecutionResult):
            refs.extend(_execution_refs(self.reference))
        elif isinstance(self.reference, ef.TableArtifact):
            refs.extend(_table_refs(self.reference))
        else:
            refs.append(self.reference)
        return tuple(dict.fromkeys(refs))


class ProfileMCostResult(Document):
    profile: ef.ProfileResult
    detection: ef.ComponentDetectionResult | None

    @model_validator(mode="after")
    def isolated(self) -> Self:
        if self.profile.complete and self.detection is None:
            raise ValueError("a complete profile requires its actual isolated M outcome")
        if self.detection is not None and (
            not self.profile.complete
            or self.detection.method != "isolation_forest"
            or self.detection.rows != 1
        ):
            raise ValueError("M cost requires a complete profile and one isolated M result")
        return self

    @property
    def complete(self) -> bool:
        return self.profile.complete and self.detection is not None and self.detection.complete


class ResourceSample(Document):
    """Cumulative process CPU and instantaneous RSS returned by an explicit probe."""

    cpu_seconds: Seconds
    rss_bytes: Bytes


class ResourceProbe(Protocol):
    def sample(self) -> ResourceSample: ...


class ResourcePoint(Document):
    monotonic_seconds: Seconds
    sample: ResourceSample


class CostIssue(Document):
    stage: Literal["operation", "measurement", "integrity"]
    code: Text
    exception_type: Text | None = None


class ResourceMeasurement(Document):
    scope: Literal["process_including_sampler_thread_excluding_subprocesses"] = (
        "process_including_sampler_thread_excluding_subprocesses"
    )
    rss_method: Literal["sampled_absolute_lower_bound"] = "sampled_absolute_lower_bound"
    cpu_method: Literal["process_counter_delta_over_sample_bracket"] = (
        "process_counter_delta_over_sample_bracket"
    )
    state: Literal["complete", "partial", "not_available"]
    wall_seconds: Seconds | None
    cpu_seconds: Seconds | None
    rss_baseline_bytes: Bytes | None
    sampled_rss_peak_bytes: Bytes | None
    sample_interval_seconds: Annotated[float, Field(gt=0)]
    max_sample_gap_seconds: Seconds | None
    samples: tuple[ResourcePoint, ...]
    issues: tuple[CostIssue, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.state == "complete" and (
            self.issues
            or self.wall_seconds is None
            or self.cpu_seconds is None
            or self.rss_baseline_bytes is None
            or self.sampled_rss_peak_bytes is None
            or len(self.samples) < 2
        ):
            raise ValueError("complete resource measurement requires actual observations")
        if self.state != "complete" and not self.issues:
            raise ValueError("incomplete resource measurement requires a reason")
        if self.sampled_rss_peak_bytes != (
            max(p.sample.rss_bytes for p in self.samples) if self.samples else None
        ):
            raise ValueError("sampled peak must preserve the actual absolute RSS maximum")
        if self.rss_baseline_bytes is not None and (
            not self.samples or self.rss_baseline_bytes != self.samples[0].sample.rss_bytes
        ):
            raise ValueError("baseline must preserve the initial RSS sample")
        times = tuple(p.monotonic_seconds for p in self.samples)
        if tuple(sorted(times)) != times:
            raise ValueError("resource samples must be chronological")
        if self.cpu_seconds is not None and (
            len(self.samples) < 2
            or self.cpu_seconds
            != self.samples[-1].sample.cpu_seconds - self.samples[0].sample.cpu_seconds
        ):
            raise ValueError("CPU duration must preserve the observed process counter delta")
        gap = max((b - a for a, b in pairwise(times)), default=None)
        if self.max_sample_gap_seconds != gap:
            raise ValueError("sampling gap must preserve the actual timestamps")
        if self.state == "complete" and gap is not None and gap > 2 * self.sample_interval_seconds:
            raise ValueError("sampling lag must be declared as a partial measurement")
        if self.state == "complete" and any(
            b.sample.cpu_seconds < a.sample.cpu_seconds for a, b in pairwise(self.samples)
        ):
            raise ValueError("decreasing CPU counters cannot represent a complete measurement")
        return self


class ArtifactVerification(Document):
    artifact: ef.ArtifactRef
    state: Literal["verified", "mismatch", "unavailable"]
    observed_sha256: Digest | None
    observed_size_bytes: Bytes | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        observed = (self.observed_sha256, self.observed_size_bytes)
        expected = (self.artifact.sha256, self.artifact.size_bytes)
        if self.state == "unavailable":
            if observed != (None, None):
                raise ValueError("unavailable artifact cannot claim observed bytes")
        elif None in observed or (self.state == "verified") != (observed == expected):
            raise ValueError("artifact verification must reflect its actual digest and size")
        return self


class CostObservation(Document):
    phase: Literal["warmup", "measurement"]
    repetition: Annotated[int, Field(ge=0, le=5)]
    position: Annotated[Literal[0, 1], BeforeValidator(strict_int_literal)]
    method: Method
    state: OperationState
    profile_m: ProfileMCostResult | None
    comparison: ef.ComparisonResult | None
    resources: ResourceMeasurement
    artifacts_before: tuple[ArtifactVerification, ...]
    artifacts_after: tuple[ArtifactVerification, ...]
    issues: tuple[CostIssue, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.phase == "warmup") != (self.repetition == 0):
            raise ValueError("warmup and measured repetitions must remain separate")
        if self.method == "profile_m" and self.comparison is not None:
            raise ValueError("M observation cannot contain a comparison")
        if self.method == "comparison" and self.profile_m is not None:
            raise ValueError("comparison observation cannot contain detector output")
        returned = self.profile_m if self.method == "profile_m" else self.comparison
        if self.state in ("completed", "not_evaluable"):
            available = (
                returned is not None
                and returned.complete
                and (
                    not isinstance(returned, ef.ComparisonResult)
                    or returned.state != "not_evaluable"
                )
            )
            if returned is None or (self.state == "completed") != available:
                raise ValueError("operation state must preserve actual component availability")
        elif not self.issues:
            raise ValueError("unsuccessful operation requires a diagnostic")
        if self.state == "completed" and any(
            item.state != "verified" for item in (*self.artifacts_before, *self.artifacts_after)
        ):
            raise ValueError("completed cost requires unchanged captured artifacts")
        return self


class CostComparisonResult(Document):
    cost_id: Text
    spec: CostSpec
    spec_sha256: Digest
    started_at: Text
    finished_at: Text
    environment: tuple[ef.VersionInfo, ...]
    artifacts_before: tuple[ArtifactVerification, ...]
    artifacts_after: tuple[ArtifactVerification, ...]
    warmups: tuple[CostObservation, ...]
    observations: tuple[CostObservation, ...]
    evidence: tuple[ef.EvidenceFile, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.spec_sha256 != digest(self.spec):
            raise ValueError("cost specification fingerprint mismatch")
        schedule = _schedule(self.spec.protocol.seed)
        for phase, records, pairs in (
            ("warmup", self.warmups, schedule[:1]),
            ("measurement", self.observations, schedule[1:]),
        ):
            expected = tuple(
                (phase, repetition, position, method)
                for repetition, methods in pairs
                for position, method in enumerate(methods)
            )
            actual = tuple((r.phase, r.repetition, r.position, r.method) for r in records)
            if actual != expected:
                raise ValueError("cost observations must preserve the full alternating schedule")
            for record in records:
                for checks in (record.artifacts_before, record.artifacts_after):
                    if tuple(c.artifact for c in checks) != self.spec.artifacts:
                        raise ValueError("observed captures must match the cost specification")
                if record.state in ("completed", "not_evaluable"):
                    _validate_outcome(self.spec, record.profile_m, record.comparison)
        for checks in (self.artifacts_before, self.artifacts_after):
            if tuple(c.artifact for c in checks) != self.spec.artifacts:
                raise ValueError("top-level captures must bind the cost specification")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("cost evidence paths must be unique")
        return self

    @property
    def complete(self) -> bool:
        return all(c.state == "verified" for c in self.artifacts_after) and all(
            r.state == "completed" and r.resources.state == "complete"
            for r in (*self.warmups, *self.observations)
        )


def _table_refs(table: ef.TableArtifact) -> tuple[ef.ArtifactRef, ...]:
    return (table.data,) + ((table.index,) if table.index else ())


def _execution_refs(execution: ef.ExecutionResult) -> tuple[ef.ArtifactRef, ...]:
    return tuple(
        ref
        for table in (*execution.inputs, *((execution.output,) if execution.output else ()))
        for ref in _table_refs(table)
    )


def _schedule(seed: int) -> tuple[tuple[int, tuple[Method, Method]], ...]:
    first: tuple[Method, Method] = (
        ("profile_m", "comparison")
        if random.Random(seed).randrange(2) == 0
        else ("comparison", "profile_m")
    )
    return ((0, first), *((n, first if n % 2 else (first[1], first[0])) for n in range(1, 6)))


def _verify(artifacts: tuple[ef.ArtifactRef, ...]) -> tuple[ArtifactVerification, ...]:
    checks = []
    for ref in artifacts:
        try:
            size = 0
            hashed = hashlib.sha256()
            with open_regular_file(local_path(ref)) as stream:
                while block := stream.read(1024 * 1024):
                    size += len(block)
                    hashed.update(block)
            observed = hashed.hexdigest()
            checks.append(
                ArtifactVerification(
                    artifact=ref,
                    state="verified"
                    if (observed, size) == (ref.sha256, ref.size_bytes)
                    else "mismatch",
                    observed_sha256=observed,
                    observed_size_bytes=size,
                )
            )
        except (OSError, ef.EquiFrameError, ValueError):
            checks.append(
                ArtifactVerification(
                    artifact=ref,
                    state="unavailable",
                    observed_sha256=None,
                    observed_size_bytes=None,
                )
            )
    return tuple(checks)


def _reference_data(
    reference: ef.ArtifactRef | ef.TableArtifact | ef.ExecutionResult,
) -> ef.ArtifactRef:
    if isinstance(reference, ef.ExecutionResult):
        if not (reference.output is not None):
            raise AssertionError("Internal invariant check failed.")
        return reference.output.data
    return reference.data if isinstance(reference, ef.TableArtifact) else reference


def _validate_outcome(
    spec: CostSpec, profile_m: ProfileMCostResult | None, comparison: ef.ComparisonResult | None
) -> None:
    if profile_m is not None:
        profile = profile_m.profile
        if (
            profile.vector.spec != spec.profile
            or profile.options != spec.profile_options
            or profile.metadata.execution_sha256
            != profile_digest(spec.execution.model_dump(mode="json"))
            or profile.metadata.run_id != spec.execution.run_id
            or profile.metadata.execution_id != spec.execution.execution_id
            or profile.metadata.contract_sha256 != spec.execution.contract_sha256
            or profile.metadata.artifacts != _execution_refs(spec.execution)
        ):
            raise ValueError("profile does not belong to the declared captured execution")
        if profile_m.detection is not None and (
            profile_m.detection.bundle_sha256 != spec.detector_bundle_sha256
            or profile_m.detection.profiles_sha256
            != profile_digest([profile.vector.model_dump(mode="json")])
        ):
            raise ValueError("M result does not belong to the declared frozen bundle and profile")
    if comparison is not None:
        if (
            comparison.spec
            != ef.ComparisonSpec(
                contract=spec.execution.plan.contract, policy=spec.comparison_policy
            )
            or comparison.options != spec.comparison_options
            or comparison.reference != spec.comparison_reference
        ):
            raise ValueError("comparison does not use the declared contract, policy and options")
        if comparison.left and (
            comparison.left.execution != spec.execution
            or comparison.left.data.sha256 != _reference_data(spec.execution).sha256
        ):
            raise ValueError("comparison left side does not use the captured execution")
        if comparison.right:
            ref = _reference_data(spec.reference)
            if (
                comparison.right.data.sha256,
                comparison.right.data.size_bytes,
                comparison.right.data.format,
            ) != (ref.sha256, ref.size_bytes, ref.format):
                raise ValueError("comparison reference changed its captured content")
            if (
                isinstance(spec.reference, ef.ExecutionResult)
                and comparison.right.execution != spec.reference
            ):
                raise ValueError("reference execution preconditions must remain available")
            if (
                isinstance(spec.reference, ef.TableArtifact)
                and comparison.right.table != spec.reference
            ):
                raise ValueError("reference table metadata must remain available")


class _CpuTimes(Protocol):
    user: float
    system: float


class _MemoryInfo(Protocol):
    rss: int


class _Process(Protocol):
    def cpu_times(self) -> _CpuTimes: ...

    def memory_info(self) -> _MemoryInfo: ...


class _PsutilProbe:
    def __init__(self) -> None:
        try:
            psutil = import_module("psutil")
        except ImportError as error:
            raise ef.MissingDependencyError(
                "cost resources require equiframe-benchmark[resources]"
            ) from error
        self.process = cast(_Process, psutil.Process())

    def sample(self) -> ResourceSample:
        times = self.process.cpu_times()
        return ResourceSample(
            cpu_seconds=times.user + times.system, rss_bytes=self.process.memory_info().rss
        )


class _Monitor:
    def __init__(self, factory: Callable[[], ResourceProbe], interval: float) -> None:
        self.interval = interval
        self.samples: list[ResourcePoint] = []
        self.issues: list[CostIssue] = []
        self.initial: ResourcePoint | None = None
        self.final: ResourcePoint | None = None
        self.stop_event = Event()
        self.thread: Thread | None = None
        try:
            self.probe: ResourceProbe | None = factory()
        except Exception as error:
            self.probe = None
            self.issues.append(
                CostIssue(
                    stage="measurement",
                    code="resource_probe_unavailable",
                    exception_type=type(error).__name__,
                )
            )

    def sample(self) -> ResourcePoint | None:
        if self.probe is None:
            return None
        try:
            observed = ResourceSample.model_validate(self.probe.sample())
            point = ResourcePoint(monotonic_seconds=time.perf_counter(), sample=observed)
            self.samples.append(point)
            return point
        except Exception as error:
            self.issues.append(
                CostIssue(
                    stage="measurement",
                    code="resource_sample_failed",
                    exception_type=type(error).__name__,
                )
            )
            return None

    def start(self) -> None:
        self.initial = self.sample()
        if self.probe is not None:
            self.thread = Thread(target=self.watch, name="equiframe-cost-rss")
            try:
                self.thread.start()
            except Exception as error:
                self.thread = None
                self.issues.append(
                    CostIssue(
                        stage="measurement",
                        code="sampling_thread_unavailable",
                        exception_type=type(error).__name__,
                    )
                )

    def watch(self) -> None:
        while not self.stop_event.wait(self.interval):
            self.sample()

    def finish(self, wall_seconds: float | None) -> ResourceMeasurement:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join()
        self.final = self.sample()
        times = tuple(p.monotonic_seconds for p in self.samples)
        gap = max((b - a for a, b in pairwise(times)), default=None)
        cpu = None
        if self.initial and self.final:
            cpu = self.final.sample.cpu_seconds - self.initial.sample.cpu_seconds
            if cpu < 0:
                cpu = None
        if any(b.sample.cpu_seconds < a.sample.cpu_seconds for a, b in pairwise(self.samples)):
            self.issues.append(CostIssue(stage="measurement", code="cpu_counter_decreased"))
        if gap is not None and gap > 2 * self.interval:
            self.issues.append(CostIssue(stage="measurement", code="sampling_lagged"))
        return ResourceMeasurement(
            state="partial" if self.issues else "complete",
            wall_seconds=wall_seconds,
            cpu_seconds=cpu,
            rss_baseline_bytes=self.initial.sample.rss_bytes if self.initial else None,
            sampled_rss_peak_bytes=max(p.sample.rss_bytes for p in self.samples)
            if self.samples
            else None,
            sample_interval_seconds=self.interval,
            max_sample_gap_seconds=gap,
            samples=tuple(self.samples),
            issues=tuple(self.issues),
        )


def _unavailable(interval: float, code: str) -> ResourceMeasurement:
    return ResourceMeasurement(
        state="not_available",
        wall_seconds=None,
        cpu_seconds=None,
        rss_baseline_bytes=None,
        sampled_rss_peak_bytes=None,
        sample_interval_seconds=interval,
        max_sample_gap_seconds=None,
        samples=(),
        issues=(CostIssue(stage="measurement", code=code),),
    )


def _attempt(
    spec: CostSpec,
    method: Method,
    phase: Literal["warmup", "measurement"],
    repetition: int,
    position: Literal[0, 1],
    directory: Path,
    token: ef.CancellationToken,
    action: Callable[[Path, ef.CancellationToken], ProfileMCostResult | ef.ComparisonResult],
    factory: Callable[[], ResourceProbe],
) -> CostObservation:
    before = _verify(spec.artifacts)
    profile_m = None
    compared = None
    issues: list[CostIssue] = []
    state: OperationState
    interval = spec.protocol.sample_interval_seconds
    if token.cancelled or any(c.state != "verified" for c in before):
        state = "cancelled" if token.cancelled else "failed"
        issues.append(
            CostIssue(
                stage="operation" if token.cancelled else "integrity",
                code="cancelled_before_operation"
                if token.cancelled
                else "captured_artifact_unavailable",
            )
        )
        resources = _unavailable(interval, "operation_not_started")
    else:
        monitor = _Monitor(factory, interval)
        monitor.start()
        start = time.perf_counter()
        try:
            returned = action(directory, token)
            if method == "profile_m":
                if not isinstance(returned, ProfileMCostResult):
                    raise TypeError("profile_m callback must return ProfileMCostResult")
                profile_m = ProfileMCostResult.model_validate(returned)
                state = "completed" if profile_m.complete else "not_evaluable"
                if not profile_m.complete and token.cancelled:
                    state = "cancelled"
                    issues.append(CostIssue(stage="operation", code="cancelled_during_operation"))
            else:
                if not isinstance(returned, ef.ComparisonResult):
                    raise TypeError("comparison callback must return ComparisonResult")
                compared = ef.ComparisonResult.model_validate(returned)
                state = "completed" if compared.state != "not_evaluable" else "not_evaluable"
                if compared.state == "not_evaluable":
                    failures = {d.code for d in compared.diagnostics}
                    for code in ("cancelled", "timeout", "resource_exhausted"):
                        if code in failures:
                            state = cast(OperationState, code)
                            issues.append(CostIssue(stage="operation", code=code))
                            break
            _validate_outcome(spec, profile_m, compared)
        except Exception as error:
            state = (
                "cancelled"
                if isinstance(error, ef.ExecutionCancelled)
                else "timeout"
                if isinstance(error, ef.ExecutionTimeout)
                else "resource_exhausted"
                if isinstance(error, ef.ResourceLimitError)
                else "failed"
            )
            issues.append(
                CostIssue(
                    stage="operation", code="operation_failed", exception_type=type(error).__name__
                )
            )
        finally:
            resources = monitor.finish(time.perf_counter() - start)
    after = _verify(spec.artifacts)
    if any(c.state != "verified" for c in after):
        state = "failed"
        issues.append(CostIssue(stage="integrity", code="captured_artifact_changed"))
    return CostObservation(
        phase=phase,
        repetition=repetition,
        position=position,
        method=method,
        state=state,
        profile_m=profile_m,
        comparison=compared,
        resources=resources,
        artifacts_before=before,
        artifacts_after=after,
        issues=tuple(issues),
    )


def measure_costs(
    spec: CostSpec,
    *,
    profile_m: Callable[[Path, ef.CancellationToken], ProfileMCostResult],
    comparison: Callable[[Path, ef.CancellationToken], ef.ComparisonResult],
    work_dir: Path | None = None,
    cancellation: ef.CancellationToken | None = None,
    probe_factory: Callable[[], ResourceProbe] | None = None,
) -> CostComparisonResult:
    """Measure one warmup pair and five alternating pairs on the same fixed bytes.

    Actions are trusted synchronous code, never imported from JSON. Resource
    collection failure does not skip an action. Cancellation is cooperative;
    failures and partial measurements are persisted, with no fabricated zeros.
    Thread/cache/memory controls are caller declarations, not enforced quotas.
    """
    spec = CostSpec.model_validate(spec)
    identifier = "cost_" + uuid4().hex
    directory = (work_dir or Path.cwd() / "equiframe-costs").resolve() / identifier
    directory.mkdir(parents=True, exist_ok=False)
    save_document(spec, directory / "spec.json")
    token = cancellation if cancellation is not None else ef.CancellationToken()
    started = datetime.now(UTC).isoformat()
    before = _verify(spec.artifacts)
    records = []
    actions: dict[
        Method, Callable[[Path, ef.CancellationToken], ProfileMCostResult | ef.ComparisonResult]
    ] = {"profile_m": profile_m, "comparison": comparison}
    for repetition, methods in _schedule(spec.protocol.seed):
        phase: Literal["warmup", "measurement"] = "warmup" if repetition == 0 else "measurement"
        for position, method in enumerate(methods):
            folder = directory / f"{phase}-{repetition}-{method}"
            folder.mkdir()
            record = _attempt(
                spec,
                method,
                phase,
                repetition,
                0 if position == 0 else 1,
                folder,
                token,
                actions[method],
                probe_factory or _PsutilProbe,
            )
            save_document(record, folder / "observation.json")
            records.append(record)
    environment = [
        ef.VersionInfo(name="python", version=platform.python_version()),
        ef.VersionInfo(name="system", version=platform.system()),
        ef.VersionInfo(name="machine", version=platform.machine()),
    ]
    for name in ("equiframe", "equiframe-benchmark", "pyarrow", "psutil"):
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = "not-installed"
        environment.append(ef.VersionInfo(name=name, version=installed))
    result = CostComparisonResult(
        cost_id=identifier,
        spec=spec,
        spec_sha256=digest(spec),
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
        environment=tuple(environment),
        artifacts_before=before,
        artifacts_after=_verify(spec.artifacts),
        warmups=tuple(records[:2]),
        observations=tuple(records[2:]),
        evidence=inventory(directory),
    )
    save_document(result, directory / "costs.json")
    return result


def read_costs(path: Path) -> CostComparisonResult:
    """Revalidate schedules, original outcomes, captures and every local evidence byte."""
    path = path / "costs.json" if path.is_dir() else path
    result = load_document(CostComparisonResult, path)
    directory = path.parent.resolve()
    verify_files(directory, result.evidence)
    listed = {item.path for item in result.evidence}
    actual = {
        p.relative_to(directory).as_posix()
        for p in directory.rglob("*")
        if p.is_file() and p != path.resolve()
    }
    if (
        actual != listed
        or "spec.json" not in listed
        or load_document(CostSpec, directory / "spec.json") != result.spec
    ):
        raise ef.ArtifactIntegrityError("cost files contradict the final manifest")
    for record in (*result.warmups, *result.observations):
        relative = f"{record.phase}-{record.repetition}-{record.method}/observation.json"
        if relative not in listed or load_document(CostObservation, directory / relative) != record:
            raise ef.ArtifactIntegrityError("cost observation contradicts its final manifest")
        if record.comparison is not None:
            refs = [record.comparison.differences] + [
                source.data
                for source in (record.comparison.left, record.comparison.right)
                if source
            ]
            for ref in refs:
                owned = local_path(ref).resolve()
                if not owned.is_relative_to(directory):
                    raise ef.ArtifactIntegrityError("comparison evidence escapes cost operation")
                match = next(
                    (
                        item
                        for item in result.evidence
                        if item.path == owned.relative_to(directory).as_posix()
                    ),
                    None,
                )
                if match is None or (match.sha256, match.size_bytes) != (
                    ref.sha256,
                    ref.size_bytes,
                ):
                    raise ef.ArtifactIntegrityError(
                        "comparison artifact contradicts cost inventory"
                    )
    if all(c.state == "verified" for c in result.artifacts_after) and any(
        c.state != "verified" for c in _verify(result.spec.artifacts)
    ):
        raise ef.ArtifactIntegrityError("original captured artifacts no longer match cost evidence")
    return result
