"""Validated execution metadata. Runtime objects and trusted code live separately."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, PositiveInt, Text, fail
from equiframe.contracts import Contract
from equiframe.types import ArtifactRef, ExecutionState, Sha256
from equiframe.values import ScalarValue, TimeUnit, TimeZone


class Parameter(FrozenModel):
    name: Identifier
    value: ScalarValue


class ExecutionOptions(FrozenModel):
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None
    max_input_rows: NonNegativeInt | None = None
    max_output_rows: NonNegativeInt | None = None
    max_transport_bytes: PositiveInt | None = None
    duckdb_memory_mb: PositiveInt = 512
    duckdb_threads: PositiveInt = 1
    duckdb_timezone: TimeZone = "UTC"


class ExecutionPlan(FrozenModel):
    contract: Contract
    engine: Identifier
    transformation_id: Identifier
    transformation_revision: PositiveInt = 1
    parameters: tuple[Parameter, ...] = ()
    options: ExecutionOptions = Field(default_factory=ExecutionOptions)

    @model_validator(mode="after")
    def unique_parameters(self) -> Self:
        names = tuple(item.name for item in self.parameters)
        if len(set(names)) != len(names):
            fail("duplicate_parameter", "parameter names must be unique", "parameters")
        return self


class EngineCapabilities(FrozenModel):
    engine: Identifier
    decimal_precision: Annotated[int, Field(ge=1, le=76)]
    timestamp_units: tuple[TimeUnit, ...]
    zoned_timestamp_units: tuple[TimeUnit, ...]
    lazy: bool
    cancellation: Literal["cooperative", "interrupt_query"]
    resource_controls: tuple[Text, ...]
    required_packages: tuple[Text, ...] = ()


class PhysicalColumn(FrozenModel):
    name: Annotated[str, Field(min_length=1)]
    engine_type: Text
    arrow_type: Text
    null_count: NonNegativeInt
    nan_count: NonNegativeInt


class TableArtifact(FrozenModel):
    name: Text
    data: ArtifactRef
    origin: ArtifactRef | None = None
    row_count: NonNegativeInt
    columns: tuple[PhysicalColumn, ...]
    index: ArtifactRef | None = None
    index_columns: tuple[PhysicalColumn, ...] = ()
    notes: tuple[Text, ...] = ()


class StageTiming(FrozenModel):
    stage: Text
    seconds: Annotated[float, Field(ge=0)]


class VersionInfo(FrozenModel):
    name: Text
    version: Text


class ExecutionProblem(FrozenModel):
    code: Text
    stage: Text
    exception_type: Text
    message: Text


class ExecutionResult(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    execution_id: Identifier
    plan: ExecutionPlan
    contract_sha256: Sha256
    implementation_version: Text | None
    state: ExecutionState
    started_at: Text
    finished_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    timings: tuple[StageTiming, ...]
    versions: tuple[VersionInfo, ...]
    capabilities: EngineCapabilities
    effective_configuration: tuple[Parameter, ...]
    inputs: tuple[TableArtifact, ...]
    output: TableArtifact | None
    problem: ExecutionProblem | None

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if self.state == "completed" and (self.output is None or self.problem is not None):
            fail("incomplete_result", "completed requires output and no problem", "state")
        if self.state != "completed" and self.problem is None:
            fail("missing_problem", "unsuccessful execution requires a diagnostic", "problem")
        return self
