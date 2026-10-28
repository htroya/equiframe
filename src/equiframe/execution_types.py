"""Validated execution metadata. Runtime objects and trusted code live separately."""

from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    Text,
    _ExplicitOutcome,
    fail,
)
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

    @model_validator(mode="after")
    def consistent_table(self) -> Self:
        if self.data.format not in ("arrow", "parquet"):
            fail("table_artifact_format", "table data requires Arrow/Parquet", "data")
        if self.index is None and self.index_columns:
            fail("missing_index_artifact", "index columns require an index artifact", "index")
        if self.index is not None and self.index.format not in ("arrow", "parquet"):
            fail("table_artifact_format", "index requires Arrow/Parquet", "index")
        for location, columns in (("columns", self.columns), ("index_columns", self.index_columns)):
            if len({c.name for c in columns}) != len(columns):
                fail("duplicate_physical_column", "physical column names must be unique", location)
            for position, column in enumerate(columns):
                if column.null_count + column.nan_count > self.row_count:
                    fail(
                        "impossible_value_counts",
                        "NULL/NaN counts exceed row count",
                        location,
                        position,
                    )
        return self


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


class ExecutionResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .state explicitly; completed execution does not establish correctness"
    )

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
        from equiframe.serialization import contract_fingerprint

        if self.contract_sha256 != contract_fingerprint(self.plan.contract):
            fail(
                "contract_fingerprint_mismatch",
                "fingerprint must match the embedded contract",
                "contract_sha256",
            )
        names = tuple(table.name for table in self.inputs)
        declared = {table.name for table in self.plan.contract.inputs}
        if len(set(names)) != len(names) or not set(names) <= declared:
            fail(
                "invalid_input_evidence",
                "captured inputs must be unique declared table names",
                "inputs",
            )
        if self.state == "completed":
            if set(names) != declared:
                fail("missing_input_evidence", "completed requires every input artifact", "inputs")
            if self.capabilities.engine != self.plan.engine:
                fail(
                    "engine_evidence_mismatch",
                    "completed engine capabilities must match plan",
                    "capabilities",
                )
            if self.output is not None and self.output.name != self.plan.contract.output.name:
                fail("output_evidence_mismatch", "output table name must match the plan", "output")
        return self
