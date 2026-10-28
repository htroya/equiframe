"""Consumer-side comparisons of independent native runs on one pinned snapshot."""

import time
from collections.abc import Callable
from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import equiframe as ef
from equiframe._base import strict_bool_literal
from equiframe._comparison_io import snapshot as capture_snapshot
from equiframe.comparison import ComparisonInput
from equiframe.errors import ExecutionCancelled, ExecutionTimeout, ResourceLimitError
from equiframe.evidence import (
    EventJournal,
    inventory,
    load_json,
    publish_json,
    verify_events,
    verify_files,
)
from equiframe.local import local_path
from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text, digest
from equiframe_benchmark.snapshot import (
    SnapshotDataSource,
    SnapshotManifest,
    snapshot_fingerprint,
)

UTC = _timezone.utc

Engine = Literal["pandas", "polars", "duckdb"]
ENGINES: tuple[Engine, ...] = ("pandas", "polars", "duckdb")
PEERS: tuple[tuple[Engine, Engine], ...] = (
    ("pandas", "polars"),
    ("pandas", "duckdb"),
    ("polars", "duckdb"),
)


class IntegrationSpec(Document):
    pipelines: tuple[ef.PipelineSpec, ...]
    domain_schema_revision: Text
    comparison_policy: ef.ComparisonPolicy
    comparison_options: ef.ComparisonOptions = ef.ComparisonOptions()

    @model_validator(mode="after")
    def compatible(self) -> Self:
        if tuple(item.execution.engine for item in self.pipelines) != ENGINES:
            raise ValueError("integration requires Pandas, Polars and DuckDB once, in order")
        baseline = self.pipelines[0]
        for item in self.pipelines[1:]:
            if (
                item.execution.contract != baseline.execution.contract
                or item.execution.transformation_id != baseline.execution.transformation_id
                or item.execution.transformation_revision
                != baseline.execution.transformation_revision
                or item.execution.parameters != baseline.execution.parameters
                or item.profile != baseline.profile
                or item.profile_options != baseline.profile_options
                or item.rule_options != baseline.rule_options
            ):
                raise ValueError("native plans require the same contract and transformation")
        return self


class IntegrationRun(Document):
    engine: Engine
    code: Literal["pipeline_recorded", "operation_failed"]
    result: ef.PipelineResult | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.code == "pipeline_recorded") != (self.result is not None):
            raise ValueError("recorded native run requires its pipeline result")
        if self.result is not None and self.result.spec.execution.engine != self.engine:
            raise ValueError("native run engine contradicts its pipeline")
        return self


class IntegrationComparison(Document):
    left_engine: Engine
    right_engine: Literal["pandas", "polars", "duckdb", "expected"]
    code: Literal[
        "comparison_recorded", "execution_unavailable", "inputs_unverified", "operation_failed"
    ]
    result: ef.ComparisonResult | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.code == "comparison_recorded") != (self.result is not None):
            raise ValueError("recorded comparison requires its result")
        if self.result is not None and self.result.reference != (
            "expected" if self.right_engine == "expected" else "peer"
        ):
            raise ValueError("comparison reference contradicts its declared role")
        return self


def _input_reason(snapshot: SnapshotManifest, runs: tuple[IntegrationRun, ...]) -> str:
    available = {table.name: table for table in snapshot.tables}
    baseline: tuple[tuple[str, str, int], ...] | None = None
    for run in runs:
        execution = run.result.execution if run.result is not None else None
        selected: set[str] = (
            {table.name for table in run.result.spec.execution.contract.inputs}
            if run.result is not None
            else set()
        )
        if not selected <= set(available):
            return "snapshot_table_missing"
        expected = {name: available[name] for name in selected}
        if execution is None or {table.name for table in execution.inputs} != set(expected):
            return "input_capture_unavailable"
        configuration = {
            parameter.name: parameter.value
            for parameter in execution.effective_configuration
            if parameter.name.startswith("snapshot_")
        }
        for name, value in (
            ("snapshot_id", snapshot.snapshot_id),
            ("snapshot_domain_schema_revision", snapshot.domain_schema_revision),
            ("snapshot_extraction_revision", snapshot.extraction_revision),
            ("snapshot_manifest_sha256", snapshot_fingerprint(snapshot)),
        ):
            if configuration.get(name) != ef.StringValue(value=value):
                return "snapshot_configuration_mismatch"
        captured = []
        for table in execution.inputs:
            source = expected[table.name]
            if table.origin != source.artifact:
                return "snapshot_artifact_mismatch"
            if table.row_count != source.row_count or tuple(
                (column.name, column.arrow_type) for column in table.columns
            ) != tuple((column.name, column.physical_type) for column in source.columns):
                return "snapshot_capture_schema_mismatch"
            if table.index is not None:
                return "unexpected_snapshot_index"
            captured.append((table.name, table.data.sha256, table.data.size_bytes))
        current = tuple(sorted(captured))
        if baseline is not None and current != baseline:
            return "native_input_capture_mismatch"
        baseline = current
    return "verified_same_snapshot"


class IntegrationResult(Document):
    integration_id: Text
    spec: IntegrationSpec
    spec_sha256: Digest
    snapshot: SnapshotManifest
    snapshot_sha256: Digest
    started_at: Text
    finished_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    cancelled: bool
    expected_requested: bool
    expected_artifact: ef.ArtifactRef | None
    inputs_verified: bool
    input_reason: Text
    runs: tuple[IntegrationRun, ...]
    comparisons: tuple[IntegrationComparison, ...]
    scientific_equivalence_confirmed: Annotated[
        Literal[False], BeforeValidator(strict_bool_literal)
    ] = False
    evidence: tuple[ef.EvidenceFile, ...]
    event_count: Annotated[int, Field(ge=2)]
    event_head_sha256: Digest

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.spec_sha256 != digest(self.spec):
            raise ValueError("integration specification fingerprint mismatch")
        _check_contract(self.spec, self.snapshot)
        if self.snapshot_sha256 != snapshot_fingerprint(self.snapshot):
            raise ValueError("integration snapshot fingerprint mismatch")
        if self.snapshot.domain_schema_revision != self.spec.domain_schema_revision:
            raise ValueError("snapshot domain revision contradicts the integration specification")
        if tuple(run.engine for run in self.runs) != ENGINES:
            raise ValueError("integration must record each native engine once")
        for run, pipeline in zip(self.runs, self.spec.pipelines, strict=True):
            if run.result is not None and run.result.spec != pipeline:
                raise ValueError("native pipeline contradicts its configured specification")
        reason = _input_reason(self.snapshot, self.runs)
        if self.input_reason not in (reason, "snapshot_changed") or self.inputs_verified != (
            self.input_reason == "verified_same_snapshot"
        ):
            raise ValueError("input verification contradicts the captured snapshot evidence")
        pairs: tuple[tuple[str, str], ...] = PEERS
        if self.expected_requested:
            pairs += tuple((engine, "expected") for engine in ENGINES)
        if tuple((item.left_engine, item.right_engine) for item in self.comparisons) != pairs:
            raise ValueError("integration comparison pairs are missing or duplicated")
        executions = {
            run.engine: run.result.execution if run.result is not None else None
            for run in self.runs
        }
        native_runs = {run.engine: run for run in self.runs}
        for item in self.comparisons:
            compared = item.result
            if compared is None:
                continue
            if item.right_engine == "expected" and (
                self.expected_artifact is None
                or compared.right is None
                or (
                    compared.right.data.sha256,
                    compared.right.data.size_bytes,
                    compared.right.data.format,
                )
                != (
                    self.expected_artifact.sha256,
                    self.expected_artifact.size_bytes,
                    self.expected_artifact.format,
                )
            ):
                raise ValueError("expected comparisons must use one fixed expected artifact")
            participating = (native_runs[item.left_engine],) + (
                (native_runs[item.right_engine],) if item.right_engine != "expected" else ()
            )
            if (
                self.input_reason == "snapshot_changed"
                or _input_reason(self.snapshot, participating) != "verified_same_snapshot"
                or compared.spec.contract != self.spec.pipelines[0].execution.contract
                or compared.spec.policy != self.spec.comparison_policy
                or compared.options != self.spec.comparison_options
                or (compared.left and compared.left.execution != executions[item.left_engine])
                or (
                    item.right_engine != "expected"
                    and compared.right
                    and compared.right.execution != executions[item.right_engine]
                )
            ):
                raise ValueError("comparison does not belong to the recorded native executions")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate integration evidence paths")
        if not self.expected_requested and self.expected_artifact is not None:
            raise ValueError("unrequested expected output cannot claim an artifact")
        return self

    @property
    def complete(self) -> bool:
        return (
            not self.cancelled
            and self.inputs_verified
            and all(run.result is not None and run.result.complete for run in self.runs)
            and all(item.result is not None and item.result.complete for item in self.comparisons)
        )

    @property
    def exit_code(self) -> int:
        if any(
            run.result is not None
            and run.result.execution is not None
            and run.result.execution.problem
            and run.result.execution.problem.code == "artifact_integrity_error"
            for run in self.runs
        ):
            return 3
        if any(run.result is not None and run.result.exit_code == 2 for run in self.runs):
            return 2
        if not self.complete:
            return 3
        return int(
            any(run.result is not None and run.result.exit_code == 1 for run in self.runs)
            or any(
                item.result is not None and item.result.state == "different"
                for item in self.comparisons
            )
        )


def _check_contract(spec: IntegrationSpec, snapshot: SnapshotManifest) -> None:
    if snapshot.domain_schema_revision != spec.domain_schema_revision:
        raise ValueError("snapshot domain schema revision differs from the requested revision")
    inputs = spec.pipelines[0].execution.contract.inputs
    tables = {table.name: table for table in snapshot.tables}
    if not {table.name for table in inputs} <= set(tables):
        raise ValueError("supplied contract inputs must exist in the pinned snapshot")
    for table in inputs:
        declared = tables[table.name]
        if tuple(
            (column.name, column.logical_type, column.nullable)
            for column in table.schema_spec.columns
        ) != tuple(
            (column.name, column.logical_type, column.nullable) for column in declared.columns
        ):
            raise ValueError("snapshot logical schema differs from the supplied domain contract")


def _freeze_expected(
    expected: ComparisonInput,
    *,
    spec: IntegrationSpec,
    directory: Path,
    cancellation: ef.CancellationToken,
) -> tuple[ComparisonInput, ef.ArtifactRef]:
    """Capture expected bytes once, preserving a supplied table's separate index."""
    directory.mkdir(exist_ok=False)
    start = time.perf_counter()
    options = spec.comparison_options

    def check() -> None:
        if cancellation.cancelled:
            raise ExecutionCancelled("expected snapshot capture cancelled")
        if (
            options.timeout_seconds is not None
            and time.perf_counter() - start >= options.timeout_seconds
        ):
            raise ExecutionTimeout("expected snapshot capture exceeded its time budget")
        if (
            sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
            > options.max_disk_bytes
        ):
            raise ResourceLimitError("expected snapshot capture exceeded its disk budget")

    check()
    table = None
    source_execution = None
    pinned_inputs: tuple[ef.TableArtifact, ...] = ()

    def pin_table(original: ef.TableArtifact) -> ef.TableArtifact:
        captured = capture_snapshot(original.data, directory, options, check)
        index = (
            capture_snapshot(original.index, directory, options, check) if original.index else None
        )
        return ef.TableArtifact.model_validate(
            original.model_copy(update={"data": captured, "index": index})
        )

    if isinstance(expected, ef.ExecutionResult):
        expected = ef.ExecutionResult.model_validate(expected)
        if expected.state != "completed" or expected.output is None:
            raise ValueError("expected execution has no completed output")
        if expected.contract_sha256 != ef.contract_fingerprint(
            spec.pipelines[0].execution.contract
        ):
            raise ValueError("expected execution belongs to another contract")
        publish_json(expected, directory / "source.json")
        # Preserve and verify the source execution's declared inputs once, rather
        # than consulting external files again for each expected comparison.
        source_execution = expected
        pinned_inputs = tuple(pin_table(original) for original in expected.inputs)
        table = expected.output
    elif isinstance(expected, ef.TableArtifact):
        table = ef.TableArtifact.model_validate(expected)
        publish_json(table, directory / "source.json")
    data = table.data if table is not None else expected
    if not isinstance(data, (ef.ArrowInput, ef.ArtifactRef, Path)):
        raise TypeError("expected output requires a supported explicit comparison input")
    reference = capture_snapshot(data, directory, options, check)
    if table is not None:
        index = capture_snapshot(table.index, directory, options, check) if table.index else None
        pinned = ef.TableArtifact.model_validate(
            table.model_copy(update={"data": reference, "index": index})
        )
        if source_execution is not None:
            return ef.ExecutionResult.model_validate(
                source_execution.model_copy(update={"inputs": pinned_inputs, "output": pinned})
            ), reference
        return pinned, reference
    return reference, reference


def run_integration(
    spec: IntegrationSpec,
    *,
    source: SnapshotDataSource,
    registry: ef.TransformationRegistry,
    work_dir: Path | None = None,
    detector_bundle: ef.DetectorBundle | None = None,
    expected: ComparisonInput | None = None,
    cancellation: ef.CancellationToken | None = None,
    rule_registry: ef.RuleRegistry | None = None,
    conversion_provider: Callable[[ef.ExecutionResult], tuple[ef.ConversionReceipt, ...]]
    | None = None,
) -> IntegrationResult:
    """Execute three native implementations once; never train, label or publish a DW.

    The caller supplies a pinned snapshot source and the actual domain contract.
    Expected output is optional explicit comparison evidence, without oracle review.
    Publication errors raise and retain partial evidence in a fresh operation folder.
    """
    spec = IntegrationSpec.model_validate(spec)
    if detector_bundle is not None:
        detector_bundle = ef.DetectorBundle.model_validate(detector_bundle)
        if spec.pipelines[0].profile is None:
            raise ValueError("detectors require an explicit profile specification")
    snapshot = SnapshotManifest.model_validate(source.manifest)
    if source.snapshot_id != snapshot.snapshot_id:
        raise ValueError("source snapshot identity differs from its pinned manifest")
    _check_contract(spec, snapshot)
    if set(source.table_names) != {
        table.name for table in spec.pipelines[0].execution.contract.inputs
    }:
        raise ValueError("selected snapshot tables must match the contract inputs exactly")
    snapshot_sha256 = snapshot_fingerprint(snapshot)
    token = cancellation if cancellation is not None else ef.CancellationToken()
    identifier = "integration_" + uuid4().hex
    directory = (work_dir or Path.cwd() / "equiframe-integration").resolve() / identifier
    directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    journal = EventJournal(directory, identifier)
    journal.emit("integration", "started", "integration_started")
    publish_json(spec, directory / "spec.json")
    publish_json(snapshot, directory / "snapshot.json")
    pinned_expected = None
    expected_artifact = None
    if expected is not None:
        journal.emit("expected", "started", "expected_capture_started")
        try:
            pinned_expected, expected_artifact = _freeze_expected(
                expected, spec=spec, directory=directory / "expected", cancellation=token
            )
            expected_code = "expected_captured"
        except Exception:
            expected_code = "expected_unavailable"
        journal.emit("expected", "finished", expected_code)
    runs = []
    snapshot_changed = False
    for engine, pipeline in zip(ENGINES, spec.pipelines, strict=True):
        journal.emit(engine, "started", "pipeline_started")
        try:
            native = ef.run_pipeline(
                pipeline,
                source=source,
                registry=registry,
                detector_bundle=detector_bundle,
                cancellation=token,
                rule_registry=rule_registry,
                conversion_provider=conversion_provider,
                work_dir=directory,
            )
            recorded = IntegrationRun(engine=engine, code="pipeline_recorded", result=native)
        except Exception:
            recorded = IntegrationRun(engine=engine, code="operation_failed", result=None)
        runs.append(recorded)
        snapshot_changed |= snapshot_fingerprint(source.manifest) != snapshot_sha256
        journal.emit(engine, "finished", recorded.code)
    recorded_runs = tuple(runs)
    input_reason = (
        "snapshot_changed" if snapshot_changed else _input_reason(snapshot, recorded_runs)
    )
    inputs_verified = input_reason == "verified_same_snapshot"
    executions = {
        run.engine: run.result.execution if run.result is not None else None
        for run in recorded_runs
    }
    native_runs = {run.engine: run for run in recorded_runs}
    pairs: tuple[tuple[Engine, Literal["pandas", "polars", "duckdb", "expected"]], ...] = PEERS
    if expected is not None:
        pairs += tuple((engine, "expected") for engine in ENGINES)
    comparisons = []
    for left_engine, right_engine in pairs:
        stage = left_engine + "_" + right_engine
        journal.emit(stage, "started", "comparison_started")
        left = executions[left_engine]
        right = pinned_expected if right_engine == "expected" else executions[right_engine]
        participating = (native_runs[left_engine],) + (
            (native_runs[right_engine],) if right_engine != "expected" else ()
        )
        if snapshot_changed or _input_reason(snapshot, participating) != "verified_same_snapshot":
            compared = IntegrationComparison(
                left_engine=left_engine,
                right_engine=right_engine,
                code="inputs_unverified",
                result=None,
            )
        elif (
            left is None
            or right is None
            or (right_engine == "expected" and (left.state != "completed" or left.output is None))
        ):
            compared = IntegrationComparison(
                left_engine=left_engine,
                right_engine=right_engine,
                code="execution_unavailable",
                result=None,
            )
        else:
            try:
                comparison = ef.compare(
                    left,
                    right,
                    contract=spec.pipelines[0].execution.contract,
                    policy=spec.comparison_policy,
                    options=spec.comparison_options,
                    reference="expected" if right_engine == "expected" else "peer",
                    cancellation=token,
                    work_dir=directory,
                )
                compared = IntegrationComparison(
                    left_engine=left_engine,
                    right_engine=right_engine,
                    code="comparison_recorded",
                    result=comparison,
                )
            except Exception:
                compared = IntegrationComparison(
                    left_engine=left_engine,
                    right_engine=right_engine,
                    code="operation_failed",
                    result=None,
                )
        comparisons.append(compared)
        journal.emit(stage, "finished", compared.code)
    journal.emit("integration", "finished", "integration_finished")
    result = IntegrationResult(
        integration_id=identifier,
        spec=spec,
        spec_sha256=digest(spec),
        snapshot=snapshot,
        snapshot_sha256=snapshot_sha256,
        started_at=started_at,
        finished_at=datetime.now(UTC).isoformat(),
        elapsed_seconds=time.perf_counter() - start,
        cancelled=token.cancelled,
        expected_requested=expected is not None,
        expected_artifact=expected_artifact,
        inputs_verified=inputs_verified,
        input_reason=input_reason,
        runs=recorded_runs,
        comparisons=tuple(comparisons),
        evidence=inventory(directory),
        event_count=journal.count,
        event_head_sha256=journal.head,
    )
    publish_json(result, directory / "integration.json")
    return result


def read_integration(path: Path, *, verify: bool = True) -> IntegrationResult:
    """Verify final evidence; only explicit False selects a metadata-only read.

    Metadata-only reads preserve recorded outcomes but do not establish current
    file integrity. Other Python truthy/falsey values are invalid options.
    """
    if type(verify) is not bool:
        raise TypeError("verify must be a bool; only explicit False skips integrity checks")
    path = path / "integration.json" if path.is_dir() else path
    result = load_json(IntegrationResult, path)
    if not verify:
        return result
    directory = path.parent
    verify_files(directory, result.evidence)
    listed = {item.path: item for item in result.evidence}
    actual = {
        item.relative_to(directory).as_posix()
        for item in directory.rglob("*")
        if item.is_file() and item != path
    }
    if set(listed) != actual or not {"spec.json", "snapshot.json", "events.jsonl"} <= actual:
        raise ef.ArtifactIntegrityError("integration evidence inventory is incomplete")
    if (
        load_json(IntegrationSpec, directory / "spec.json") != result.spec
        or load_json(SnapshotManifest, directory / "snapshot.json") != result.snapshot
    ):
        raise ef.ArtifactIntegrityError("persisted integration configuration mismatch")
    events = verify_events(directory / "events.jsonl", operation_id=result.integration_id)
    if (
        len(events) != result.event_count
        or not events
        or events[-1].sha256 != result.event_head_sha256
        or (events[0].stage, events[0].state) != ("integration", "started")
        or (events[-1].stage, events[-1].state) != ("integration", "finished")
    ):
        raise ef.ArtifactIntegrityError("integration journal contradicts its final manifest")
    outcomes = tuple(
        (event.stage, event.code)
        for event in events
        if event.stage != "integration" and event.state == "finished"
    )
    expected_outcomes = (
        (
            (
                (
                    "expected",
                    "expected_captured" if result.expected_artifact else "expected_unavailable",
                ),
            )
            if result.expected_requested
            else ()
        )
        + tuple((run.engine, run.code) for run in result.runs)
        + tuple(
            (item.left_engine + "_" + item.right_engine, item.code) for item in result.comparisons
        )
    )
    if outcomes != expected_outcomes:
        raise ef.ArtifactIntegrityError("integration journal contradicts recorded components")
    for run in result.runs:
        if (
            run.result is not None
            and ef.read_pipeline(directory / run.result.pipeline_id) != run.result
        ):
            raise ef.ArtifactIntegrityError("persisted native pipeline contradicts its integration")
    root = directory.resolve()
    if result.expected_artifact is not None:
        expected = local_path(result.expected_artifact).resolve()
        entry = (
            listed.get(expected.relative_to(root).as_posix())
            if expected.is_relative_to(root)
            else None
        )
        if entry is None or (entry.sha256, entry.size_bytes) != (
            result.expected_artifact.sha256,
            result.expected_artifact.size_bytes,
        ):
            raise ef.ArtifactIntegrityError(
                "fixed expected output contradicts the evidence inventory"
            )
    for item in result.comparisons:
        if item.result is None:
            continue
        compared = item.result
        differences = local_path(compared.differences).resolve()
        if not differences.is_relative_to(root):
            raise ef.ArtifactIntegrityError(
                "integration comparison escapes its operation directory"
            )
        if load_json(ef.ComparisonResult, differences.parent / "comparison.json") != compared:
            raise ef.ArtifactIntegrityError("persisted comparison contradicts its integration")
        references = [compared.differences]
        for source in (compared.left, compared.right):
            if source is None:
                continue
            references.append(source.data)
            tables = [source.table] if source.table else []
            if source.execution is not None:
                tables.extend(source.execution.inputs)
                if source.execution.output:
                    tables.append(source.execution.output)
            for table in tables:
                references.append(table.data)
                if table.index:
                    references.append(table.index)
        for reference in references:
            captured = local_path(reference).resolve()
            if not captured.is_relative_to(root):
                raise ef.ArtifactIntegrityError(
                    "integration artifact escapes its operation directory"
                )
            entry = listed.get(captured.relative_to(root).as_posix())
            if entry is None or (entry.sha256, entry.size_bytes) != (
                reference.sha256,
                reference.size_bytes,
            ):
                raise ef.ArtifactIntegrityError("integration artifact contradicts its inventory")
    return result
