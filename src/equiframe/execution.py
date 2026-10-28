"""Local execution only: no semantic validators, comparator or detector orchestration."""

from __future__ import annotations

import os
import platform
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from datetime import timezone as _timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from equiframe._base import Identifier, Text
from equiframe._error_reporting import report_failure
from equiframe._regular_io import local_output_directory
from equiframe.contracts import DecimalType, TimestampType
from equiframe.errors import (
    CapabilityError,
    EquiFrameError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    ResourceLimitError,
)
from equiframe.execution_types import (
    EngineCapabilities,
    ExecutionPlan,
    ExecutionProblem,
    ExecutionResult,
    Parameter,
    StageTiming,
    TableArtifact,
    VersionInfo,
)
from equiframe.local import LocalArtifactStore
from equiframe.registry import TransformationRegistry
from equiframe.serialization import contract_fingerprint
from equiframe.tables import LoadedTable, capture_artifact, require_dependency
from equiframe.types import ExecutionState
from equiframe.values import InfinityValue, NaNValue, NullValue, StringValue

UTC = _timezone.utc

if TYPE_CHECKING:
    import pyarrow as pa

    from equiframe.migration.backends._timestamp_transport import _TimestampCodec
    from equiframe.ports import ArtifactStore, DataSource, EngineAdapter


class CancellationToken:
    """A caller-owned cooperative cancellation signal; no background callback threads."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


@dataclass
class RunContext:
    run_id: str
    execution_id: str
    plan: ExecutionPlan
    directory: Path
    store: ArtifactStore
    cancellation: CancellationToken
    deadline: float | None
    timings: list[StageTiming] = field(default_factory=list)
    effective_configuration: list[Parameter] = field(default_factory=list)
    stage: str = "preflight"
    captured_inputs: list[TableArtifact] = field(default_factory=list)
    captured_output: TableArtifact | None = None

    @property
    def parameters(self) -> Mapping[str, object]:
        # Temporal literals stay ISO text; trusted SQL/callbacks must choose explicit casts.
        def scalar(item: Parameter) -> object:
            if isinstance(item.value, NullValue):
                return None
            if isinstance(item.value, NaNValue):
                return float("nan")
            if isinstance(item.value, InfinityValue):
                return float("inf") if item.value.sign == "positive" else -float("inf")
            return item.value.value

        return {item.name: scalar(item) for item in self.plan.parameters}

    def check(self) -> None:
        if self.cancellation.cancelled:
            raise ExecutionCancelled("cancellation requested; execution stopped at a checkpoint")
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            raise ExecutionTimeout(
                "time budget exceeded; execution returned/stopped at a checkpoint"
            )

    def check_table(self, table: pa.Table, *, output: bool, enforce_rows: bool = True) -> None:
        if type(output) is not bool or type(enforce_rows) is not bool:
            raise InvalidExecutionInput("table budget flags require explicit booleans")
        self.check()
        import pyarrow as pa

        if not isinstance(table, pa.Table):
            raise InvalidExecutionInput("data source must provide an Arrow Table")
        options = self.plan.options
        rows = options.max_output_rows if output else options.max_input_rows
        if enforce_rows and rows is not None and table.num_rows > rows:
            raise ResourceLimitError("materialized table exceeds row budget")
        if options.max_transport_bytes is not None and table.nbytes > options.max_transport_bytes:
            raise ResourceLimitError("materialized table exceeds Arrow buffer byte budget")

    def record_configuration(self, name: str, value: str) -> None:
        self.effective_configuration.append(Parameter(name=name, value=StringValue(value=value)))

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        TypeAdapter(Text).validate_python(stage, strict=True)
        previous = self.stage
        self.stage = stage
        self.check()
        start = time.perf_counter()
        succeeded = False
        try:
            yield
            self.check()
            succeeded = True
        finally:
            self.timings.append(StageTiming(stage=stage, seconds=time.perf_counter() - start))
            if succeeded:
                self.stage = previous


def _versions(engine: str) -> tuple[VersionInfo, ...]:
    result = [VersionInfo(name="python", version=platform.python_version())]
    for name in ("equiframe", "pydantic", "tzdata", "pyarrow", engine, "polars-runtime-32"):
        if name == "polars-runtime-32" and engine != "polars":
            continue
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = "not-installed"
        result.append(VersionInfo(name=name, version=installed))
    return tuple(result)


def _contract_capabilities(
    plan: ExecutionPlan,
    capabilities: EngineCapabilities,
    *,
    timestamp_codec: _TimestampCodec | None = None,
) -> None:
    if timestamp_codec is not None and timestamp_codec != timestamp_codec.for_contract(
        plan.contract
    ):
        raise CapabilityError("IR timestamp codec differs from the execution contract")
    for table in (*plan.contract.inputs, plan.contract.output):
        for column in table.schema_spec.columns:
            dtype = column.logical_type
            if isinstance(dtype, DecimalType) and dtype.precision > capabilities.decimal_precision:
                raise CapabilityError(
                    f"{plan.engine} cannot execute declared decimal precision {dtype.precision}"
                )
            if isinstance(dtype, TimestampType):
                if timestamp_codec is not None:
                    continue
                supported = (
                    capabilities.zoned_timestamp_units
                    if dtype.timezone
                    else capabilities.timestamp_units
                )
                if dtype.unit not in supported:
                    raise CapabilityError(
                        f"{plan.engine} cannot preserve declared timestamp unit/zone {dtype.unit}"
                    )
                if (
                    plan.engine == "duckdb"
                    and dtype.timezone
                    and dtype.timezone != plan.options.duckdb_timezone
                ):
                    raise CapabilityError(
                        "DuckDB zoned columns require the explicitly configured session timezone"
                    )


def execute(
    plan: ExecutionPlan,
    *,
    source: DataSource,
    registry: TransformationRegistry,
    adapter: EngineAdapter | None = None,
    artifact_store: ArtifactStore | None = None,
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
) -> ExecutionResult:
    """Execute trusted native code synchronously and persist run.json in a fresh directory.

    Invalid plan objects and failure to create/publish the run directory raise;
    operational failures inside a run become typed results. completed is not a
    statement of semantic correctness. Callback timeouts are cooperative.
    """
    plan = ExecutionPlan.model_validate(plan)
    if adapter is None:
        from equiframe.adapters import native_adapter

        adapter = native_adapter(plan.engine)
    capabilities = EngineCapabilities.model_validate(adapter.capabilities())
    run_id, execution_id = "run_" + uuid4().hex, "exec_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / run_id
        / execution_id
    )
    directory.mkdir(parents=True, exist_ok=False)
    store = (
        artifact_store
        if artifact_store is not None
        else LocalArtifactStore(directory / "artifacts")
    )
    started = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    timeout = plan.options.timeout_seconds
    context = RunContext(
        run_id,
        execution_id,
        plan,
        directory,
        store,
        cancellation if cancellation is not None else CancellationToken(),
        start + timeout if timeout is not None else None,
    )
    context.record_configuration(
        "control_scope", "synchronous cooperative checkpoints; no callback preemption or sandbox"
    )
    context.record_configuration(
        "contract_timezone_source",
        "locked Python tzdata package; engine timezone rules recorded separately",
    )
    state: ExecutionState = "completed"
    problem: ExecutionProblem | None = None
    implementation_version: str | None = None
    try:
        with context.measure("preflight"):
            if adapter.engine != plan.engine or capabilities.engine != plan.engine:
                raise InvalidExecutionInput("adapter engine does not match execution plan")
            names = TypeAdapter(tuple[Identifier, ...]).validate_python(
                source.table_names, strict=True
            )
            if len(set(names)) != len(names):
                raise InvalidExecutionInput("source table names must be unique")
            if set(names) != {item.name for item in plan.contract.inputs}:
                raise InvalidExecutionInput("source tables must match declared input names")
            transformation = registry.resolve(plan)
            for dependency in capabilities.required_packages:
                require_dependency(dependency, plan.engine)
            implementation_version = transformation.code_version
            from equiframe.adapters import _timestamp_codec

            _contract_capabilities(
                plan, capabilities, timestamp_codec=_timestamp_codec(adapter, transformation)
            )
        tables: dict[str, LoadedTable] = {}
        with context.measure("input_load"):
            for item in plan.contract.inputs:
                resolved = source.resolve(item.name, context=context)
                if not isinstance(resolved, LoadedTable):
                    raise InvalidExecutionInput("data source must return LoadedTable")
                tables[item.name] = resolved
                context.check_table(tables[item.name].table, output=False)
                capture_artifact(item.name, tables[item.name], context)
        context.stage = "adapter_dispatch"
        loaded = adapter.execute(transformation, tables, context)
        if not isinstance(loaded, LoadedTable):
            raise InvalidExecutionInput("engine adapter must return LoadedTable")
        with context.measure("output_capture"):
            context.check_table(loaded.table, output=True)
            capture_artifact(plan.contract.output.name, loaded, context, output=True)
    except Exception as error:
        if isinstance(error, ExecutionCancelled):
            state = "cancelled"
        elif isinstance(error, ExecutionTimeout):
            state = "timeout"
        elif isinstance(error, (MemoryError, ResourceLimitError)):
            state = "resource_exhausted"
        elif isinstance(error, (InvalidExecutionInput, ValidationError)):
            state = "invalid_input"
        else:
            state = "failed"
        public_message = {
            "cancelled": "Execution was cancelled.",
            "timeout": "Execution exceeded its time budget.",
            "resource_exhausted": "Execution exceeded a resource budget.",
            "invalid_input": "Execution input could not be validated.",
            "failed": "Execution failed. Check the declared engine and configuration.",
        }[state]
        # Engine labels come from this closed map, never exception text or SQL.
        from equiframe.errors import MissingDependencyError

        if isinstance(error, MissingDependencyError):
            requirements = {
                "arrow": "equiframe[arrow]",
                "pandas": "equiframe[pandas]",
                "polars": "equiframe[polars]",
                "duckdb": "equiframe[duckdb]",
            }
            requirement = requirements.get(plan.engine)
            if requirement is not None:
                public_message += " Install " + requirement + " from your reviewed wheelhouse."
        problem = ExecutionProblem(
            code=error.code if isinstance(error, EquiFrameError) else state,
            stage=context.stage,
            exception_type=type(error).__name__,
            message=report_failure(error, public_message),
        )
    result = ExecutionResult(
        run_id=run_id,
        execution_id=execution_id,
        plan=plan,
        contract_sha256=contract_fingerprint(plan.contract),
        implementation_version=implementation_version,
        state=state,
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
        elapsed_seconds=time.perf_counter() - start,
        timings=tuple(context.timings),
        versions=_versions(plan.engine),
        capabilities=capabilities,
        effective_configuration=tuple(context.effective_configuration),
        inputs=tuple(context.captured_inputs),
        output=context.captured_output,
        problem=problem,
    )
    # Directory is owned by this execution. Exclusive publication never replaces a previous run.
    temporary = directory / "run.part.json"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as manifest:
            manifest.write(result.model_dump_json())
            manifest.flush()
            os.fsync(manifest.fileno())
        os.link(temporary, directory / "run.json")
    finally:
        temporary.unlink(missing_ok=True)
    return result
