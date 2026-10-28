"""Compile and execute two native ETLs over one fixed, faithful input capture."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import datetime
from datetime import timezone as _timezone
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeVar
from uuid import uuid4

from typing_extensions import TypeAliasType

from equiframe._comparison_io import snapshot
from equiframe._duckdb_transport import duckdb_temporal_capabilities
from equiframe._physical import physical_size
from equiframe._regular_io import local_output_directory
from equiframe.adapters import _input_capabilities, _timestamp_codec, native_adapter
from equiframe.comparison import compare
from equiframe.comparison_types import ComparisonResult
from equiframe.detector_types import DetectorBundle
from equiframe.errors import (
    CapabilityError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    MissingDependencyError,
    ResourceLimitError,
)
from equiframe.evidence import EventJournal, inventory, publish_json
from equiframe.execution import CancellationToken, RunContext, _contract_capabilities
from equiframe.execution_types import ExecutionPlan, TableArtifact
from equiframe.local import LocalArtifactStore
from equiframe.normalization import logical_signature, normalize, physical_value
from equiframe.pipeline import run_pipeline
from equiframe.pipeline_types import PipelineResult, PipelineSpec
from equiframe.ports import DataSource, EngineAdapter
from equiframe.profile_types import profile_digest
from equiframe.registry import TransformationRegistry
from equiframe.rules import RuleRegistry
from equiframe.serialization import contract_fingerprint
from equiframe.tables import (
    ArrowInput,
    ArtifactInput,
    LoadedTable,
    capture_artifact,
    detached_arrow,
    require_dependency,
)
from equiframe.types import ArtifactRef

from .ports import CompiledPlan, CompilerRegistry, native_compiler_registry
from .runner_types import (
    CompilerRecord,
    MigrationResult,
    MigrationSpec,
    MigrationStage,
    MigrationStageName,
    pipeline_complete,
)
from .types import CompilationCheck
from .validation import ir_fingerprint

UTC = _timezone.utc
_T = TypeVar("_T")

if TYPE_CHECKING:
    from equiframe.contracts import TableSpec

ExpectedInput = TypeAliasType("ExpectedInput", ArrowInput | ArtifactRef | Path)


def check_migration(
    spec: MigrationSpec,
    *,
    compilers: CompilerRegistry | None = None,
) -> tuple[CompilationCheck, CompilationCheck]:
    """Check both compiler capabilities without loading inputs or native engines."""
    spec = MigrationSpec.model_validate(spec)
    registry = compilers if compilers is not None else native_compiler_registry()
    return (
        registry.resolve(spec.source_engine).check(spec.ir, spec.contract),
        registry.resolve(spec.target_engine).check(spec.ir, spec.contract),
    )


class _Steps:
    def __init__(self, journal: EventJournal, token: CancellationToken, deadline: float | None):
        self.journal = journal
        self.token = token
        self.deadline = deadline
        self.records: list[MigrationStage] = []

    def check(self) -> None:
        if self.token.cancelled:
            raise ExecutionCancelled("migration cancelled at a cooperative checkpoint")
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            raise ExecutionTimeout("migration budget exceeded at a cooperative checkpoint")

    def run(
        self,
        name: MigrationStageName,
        action: Callable[[], _T],
        complete: Callable[[_T], bool],
        *,
        skip: str | None = None,
    ) -> _T | None:
        if skip:
            record = MigrationStage(stage=name, state="skipped", code=skip, elapsed_seconds=0.0)
            result = None
        else:
            start = time.perf_counter()
            self.journal.emit(name, "started", "stage_started")
            result = None
            try:
                self.check()
                result = action()
                self.check()
                ok = complete(result)
                record = MigrationStage(
                    stage=name,
                    state="completed" if ok else "not_evaluable",
                    code="stage_completed" if ok else "component_unavailable",
                    elapsed_seconds=time.perf_counter() - start,
                )
            except Exception as error:
                result = None
                code = (
                    "missing_dependency"
                    if isinstance(error, MissingDependencyError)
                    else "unsupported_capability"
                    if isinstance(error, CapabilityError)
                    else "cancelled"
                    if isinstance(error, ExecutionCancelled)
                    else "timeout"
                    if isinstance(error, ExecutionTimeout)
                    else "resource_exhausted"
                    if isinstance(error, (ResourceLimitError, MemoryError))
                    else "invalid_input"
                    if isinstance(error, (InvalidExecutionInput, ValueError))
                    else "operation_failed"
                )
                record = MigrationStage(
                    stage=name,
                    state="failed",
                    code=code,
                    elapsed_seconds=time.perf_counter() - start,
                )
        self.records.append(record)
        self.journal.emit(name, record.state, record.code)
        return result

    def timeout(self, declared: float | None) -> float | None:
        self.check()
        remaining = self.deadline - time.perf_counter() if self.deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise ExecutionTimeout("migration budget exhausted")
        return (
            min(declared, remaining)
            if declared is not None and remaining is not None
            else (declared if remaining is None else remaining)
        )


def _validate_input(loaded: LoadedTable, declared: TableSpec, context: RunContext) -> None:
    """Check actual data; normalized values are inspected but never written back."""
    context.check_table(loaded.table, output=False)
    columns = declared.schema_spec.columns
    if tuple(loaded.table.column_names) != tuple(c.name for c in columns):
        raise InvalidExecutionInput("captured input columns/order differ from the contract")
    for column in columns:
        values = loaded.table[column.name]
        if logical_signature(values.type) != tuple(column.logical_type.model_dump().values()):
            raise InvalidExecutionInput("captured input physical type differs from the contract")
        for chunk in values.chunks:
            context.check()
            for n, scalar in enumerate(chunk):
                if n % 4096 == 0:
                    context.check()
                _, violations = normalize(physical_value(scalar), column)
                if violations:
                    raise InvalidExecutionInput(
                        "captured input violates declared value constraints"
                    )


class _PinnedSource:
    def __init__(self, inputs: tuple[TableArtifact, ...]) -> None:
        self._inputs = {t.name: t for t in inputs}

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._inputs)

    def resolve(self, name: str, *, context: RunContext) -> LoadedTable:
        ref = self._inputs[name]
        value = ArtifactInput(ref.data).load(context)
        index = ArtifactInput(ref.index).load(context).table if ref.index else None
        return LoadedTable(
            value.table,
            native_types=tuple((column.name, column.engine_type) for column in ref.columns),
            index=index,
            origin=ref.data,
            notes=(
                *ref.notes,
                "Fixed migration snapshot; original provider is not called again.",
            ),
        )


def _compiler_record(compiled: CompiledPlan, spec: MigrationSpec) -> CompilerRecord:
    t = compiled.transformation
    if (
        compiled.engine != t.engine
        or not compiled.check.supported
        or compiled.check.engine != compiled.engine
        or compiled.ir_sha256 != ir_fingerprint(spec.ir)
        or compiled.contract_sha256 != contract_fingerprint(spec.contract)
    ):
        raise InvalidExecutionInput("compiler output contradicts its specification")
    return CompilerRecord(
        engine=t.engine,
        transformation_id=t.transformation_id,
        revision=t.revision,
        code_version=t.code_version,
        ir_sha256=compiled.ir_sha256,
        contract_sha256=compiled.contract_sha256,
        check=compiled.check,
    )


def migrate(
    spec: MigrationSpec,
    *,
    source: DataSource,
    work_dir: Path | None = None,
    expected: ExpectedInput | None = None,
    compilers: CompilerRegistry | None = None,
    adapters: Mapping[str, EngineAdapter] | None = None,
    rule_registry: RuleRegistry | None = None,
    detector_bundle: DetectorBundle | None = None,
    cancellation: CancellationToken | None = None,
) -> MigrationResult:
    """Execute native origin/destination; never translate arbitrary Python or execute JSON code.

    Invalid configuration and publication failures raise. Operational stage failures
    persist a non-success result. Captures and callbacks are synchronous; budgets
    are cooperative checkpoints, not process memory quotas or preemptive threads.
    """
    spec = MigrationSpec.model_validate(spec)
    if detector_bundle is not None:
        detector_bundle = DetectorBundle.model_validate(detector_bundle)
        if spec.profile is None:
            raise ValueError("a detector bundle requires an explicit profile")
    identifier = "migration_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    token = cancellation if cancellation is not None else CancellationToken()
    start = time.perf_counter()
    started = datetime.now(UTC).isoformat()
    deadline = start + spec.options.timeout_seconds if spec.options.timeout_seconds else None
    journal = EventJournal(directory, identifier)
    journal.emit("migration", "started", "migration_started")
    publish_json(spec, directory / "spec.json")
    if detector_bundle is not None:
        publish_json(detector_bundle, directory / "detector-bundle.json")
    steps = _Steps(journal, token, deadline)
    compiler_registry = compilers if compilers is not None else native_compiler_registry()
    resolved_adapters: dict[str, EngineAdapter] = {}

    def preflight() -> tuple[CompiledPlan, CompiledPlan]:
        engines = (spec.source_engine, spec.target_engine)
        checks = check_migration(spec, compilers=compiler_registry)
        if any(not c.supported for c in checks):
            raise CapabilityError("migration IR is unsupported by a configured compiler")
        compiled = tuple(
            compiler_registry.resolve(e).compile(spec.ir, spec.contract) for e in engines
        )
        records = tuple(_compiler_record(c, spec) for c in compiled)
        if tuple(r.engine for r in records) != engines:
            raise InvalidExecutionInput("compiled engines do not match the pair")
        if len(set(source.table_names)) != len(source.table_names) or set(source.table_names) != {
            t.name for t in spec.contract.inputs
        }:
            raise InvalidExecutionInput("provider bindings do not match the contract")
        for engine, record, implementation in zip(engines, records, compiled, strict=True):
            adapter = (
                adapters[engine] if adapters and engine in adapters else native_adapter(engine)
            )
            capabilities = adapter.capabilities()
            if adapter.engine != engine or capabilities.engine != engine:
                raise InvalidExecutionInput("adapter does not match its configured engine")
            for dependency in capabilities.required_packages:
                require_dependency(dependency, engine)
            _contract_capabilities(
                ExecutionPlan(
                    contract=spec.contract,
                    engine=engine,
                    transformation_id=record.transformation_id,
                    transformation_revision=record.revision,
                    options=spec.execution_options,
                ),
                capabilities,
                timestamp_codec=_timestamp_codec(adapter, implementation.transformation),
            )
            resolved_adapters[engine] = adapter
            steps.check()
        return compiled[0], compiled[1]

    compiled = steps.run("preflight", preflight, lambda _: True)
    records = tuple(_compiler_record(c, spec) for c in compiled) if compiled else ()
    captured: list[TableArtifact] = []
    expected_ref: ArtifactRef | None = None

    def capture() -> bool:
        nonlocal expected_ref
        if not (compiled is not None):
            raise AssertionError("Internal invariant check failed.")
        capture_dir = directory / "capture"
        capture_dir.mkdir(exist_ok=False)
        context = RunContext(
            identifier,
            identifier + ".capture",
            ExecutionPlan(
                contract=spec.contract,
                engine=spec.source_engine,
                transformation_id=records[0].transformation_id,
                options=spec.execution_options,
            ),
            capture_dir,
            LocalArtifactStore(capture_dir / "artifacts"),
            token,
            deadline,
        )
        rows = total_bytes = 0
        for table in spec.contract.inputs:
            context.check()
            value = source.resolve(table.name, context=context)
            if not isinstance(value, LoadedTable):
                raise InvalidExecutionInput("provider must return LoadedTable")
            context.check_table(value.table, output=False)
            if value.meaningful_index or (
                value.index is not None and spec.comparison_policy.index != "ignore"
            ):
                raise CapabilityError(
                    "input index must be explicit columns; RangeIndex needs authorization"
                )
            value = LoadedTable(
                detached_arrow(value.table),
                native_types=value.native_types,
                index=detached_arrow(value.index) if value.index is not None else None,
                origin=value.origin,
                notes=value.notes,
            )
            _validate_input(value, table, context)
            for implementation in compiled:
                engine = implementation.engine
                if engine in ("pandas", "polars", "duckdb"):
                    codec = _timestamp_codec(
                        resolved_adapters[engine], implementation.transformation
                    )
                    native_value = codec.encode_input(table.name, value) if codec else value
                    _input_capabilities(native_value, engine, context)
                    if engine == "duckdb":
                        duckdb_temporal_capabilities(native_value.table)
            rows += value.table.num_rows
            total_bytes += value.table.nbytes
            if value.index is not None:
                context.check_table(value.index, output=False)
                total_bytes += value.index.nbytes
            if rows > spec.options.max_capture_rows or total_bytes > spec.options.max_capture_bytes:
                raise ResourceLimitError("aggregate migration capture budget exhausted")
            captured.append(capture_artifact(table.name, value, context))
        if expected is not None:
            expected_dir = capture_dir / "expected"
            expected_dir.mkdir(exist_ok=False)
            ref = snapshot(expected, expected_dir, spec.comparison_options, steps.check)
            expected_rows, expected_bytes = physical_size(ref, check=steps.check)
            rows += expected_rows
            total_bytes += expected_bytes
            if rows > spec.options.max_capture_rows or total_bytes > spec.options.max_capture_bytes:
                raise ResourceLimitError("aggregate capture including expected exceeds budget")
            expected_ref = ref
        publish_json(
            {
                "schema_version": "1.0",
                "inputs": [t.model_dump(mode="json") for t in captured],
                "expected": expected_ref.model_dump(mode="json") if expected_ref else None,
                "rows": rows,
                "arrow_buffer_bytes": total_bytes,
            },
            directory / "capture.json",
        )
        return True

    ready = steps.run(
        "capture",
        capture,
        bool,
        skip="preflight_unavailable" if compiled is None else None,
    )
    pinned = _PinnedSource(tuple(captured))
    registry = TransformationRegistry()
    if compiled:
        for c in compiled:
            registry.register(c.transformation)

    def native(n: int) -> PipelineResult:
        record = records[n]
        options = spec.execution_options.model_copy(
            update={
                "timeout_seconds": steps.timeout(spec.execution_options.timeout_seconds),
            }
        )
        return run_pipeline(
            PipelineSpec(
                execution=ExecutionPlan(
                    contract=spec.contract,
                    engine=record.engine,
                    transformation_id=record.transformation_id,
                    transformation_revision=record.revision,
                    options=options,
                ),
                profile=spec.profile,
                profile_options=spec.profile_options,
                rule_options=spec.rule_options,
                comparison_policy=spec.comparison_policy,
                comparison_options=spec.comparison_options,
            ),
            source=pinned,
            registry=registry,
            work_dir=directory,
            adapter=resolved_adapters[record.engine],
            rule_registry=rule_registry,
            detector_bundle=detector_bundle,
            cancellation=token,
        )

    src = steps.run(
        "source",
        lambda: native(0),
        lambda p: pipeline_complete(spec, p),
        skip="capture_unavailable" if ready is None else None,
    )
    dst = steps.run(
        "target",
        lambda: native(1),
        lambda p: pipeline_complete(spec, p),
        skip="capture_unavailable" if ready is None else None,
    )

    def compared(
        left: PipelineResult | None,
        right: PipelineResult | ArtifactRef | None,
        reference: Literal["peer", "expected"],
    ) -> ComparisonResult:
        if not (left is not None and left.execution is not None and right is not None):
            raise AssertionError("Internal invariant check failed.")
        target = right.execution if isinstance(right, PipelineResult) else right
        if not (target is not None):
            raise AssertionError("Internal invariant check failed.")
        return compare(
            left.execution,
            target,
            contract=spec.contract,
            policy=spec.comparison_policy,
            options=spec.comparison_options.model_copy(
                update={
                    "timeout_seconds": steps.timeout(spec.comparison_options.timeout_seconds),
                }
            ),
            reference=reference,
            work_dir=directory,
            cancellation=token,
        )

    def has_output(p: PipelineResult | None) -> bool:
        return p is not None and p.execution is not None and p.execution.state == "completed"

    peer = steps.run(
        "comparison",
        lambda: compared(src, dst, "peer"),
        lambda c: c.complete and c.state != "not_evaluable",
        skip=None if has_output(src) and has_output(dst) else "execution_unavailable",
    )
    verifications: list[ComparisonResult | None] = []
    verification_steps: tuple[tuple[MigrationStageName, PipelineResult | None], ...] = (
        ("verification_source", src),
        ("verification_target", dst),
    )
    for name, child in verification_steps:
        verifications.append(
            steps.run(
                name,
                partial(compared, child, expected_ref, "expected"),
                lambda c: c.complete and c.state != "not_evaluable",
                skip="not_requested"
                if expected is None
                else "expected_unavailable"
                if expected_ref is None
                else "execution_unavailable"
                if not has_output(child)
                else None,
            )
        )
    journal.emit("migration", "finished", "migration_finished")
    result = MigrationResult(
        migration_id=identifier,
        spec=spec,
        spec_sha256=profile_digest(spec.model_dump(mode="json")),
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
        elapsed_seconds=time.perf_counter() - start,
        stages=tuple(steps.records),
        compilers=records,
        inputs=tuple(captured),
        expected_requested=expected is not None,
        expected=expected_ref,
        detection_requested=detector_bundle is not None,
        source=src,
        target=dst,
        comparison=peer,
        verification_source=verifications[0],
        verification_target=verifications[1],
        cancelled=token.cancelled,
        evidence=(),
        event_count=journal.count,
        event_head_sha256=journal.head,
    )
    from .io import migration_summary, render_migration_report

    publish_json(migration_summary(result), directory / "report.json")
    from equiframe._document_io import write_document as _write_document

    _write_document(directory / "report.html", render_migration_report(result).encode("utf-8"))
    result = MigrationResult.model_validate(
        {**result.model_dump(), "evidence": inventory(directory)}
    )
    publish_json(result, directory / "migration.json")
    return result
