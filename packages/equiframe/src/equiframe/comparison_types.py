"""Comparison document v1; independent of unchanged contract/execution format 1.0."""

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, PositiveInt, Text, fail
from equiframe.contracts import Contract
from equiframe.execution_types import ExecutionResult, TableArtifact, VersionInfo
from equiframe.types import ArtifactRef, ComparisonState, Sha256

Side = Literal["left", "right"]


class ComparisonPolicy(FrozenModel):
    column_order: Literal["significant", "ignored"] = "significant"
    physical_types: Literal["exact", "lossless"] = "exact"
    index: Literal["reject", "ignore"] = "reject"
    justification: Text | None = None

    @model_validator(mode="after")
    def explicit_authorization(self) -> Self:
        if (
            self.column_order == "ignored"
            or self.physical_types == "lossless"
            or self.index == "ignore"
        ) and self.justification is None:
            fail(
                "comparison_authorization",
                "relaxed policies require justification",
                "justification",
            )
        return self


class ComparisonSpec(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    contract: Contract
    policy: ComparisonPolicy = Field(default_factory=ComparisonPolicy)


class ComparisonOptions(FrozenModel):
    batch_rows: PositiveInt = 4096
    max_batch_bytes: PositiveInt = 64 * 1024 * 1024
    max_row_bytes: PositiveInt = 1024 * 1024
    partitions: Annotated[int, Field(ge=1, le=4096)] = 16
    sqlite_cache_kib: PositiveInt = 4096
    max_rows: PositiveInt = 10_000_000
    max_work: PositiveInt = 100_000_000
    max_disk_bytes: PositiveInt = 4 * 1024**3
    max_evidence_bytes: PositiveInt = 512 * 1024**2
    max_matching_rows: PositiveInt = 2000
    max_matching_bytes: PositiveInt = 32 * 1024**2
    max_pair_checks: PositiveInt = 2_000_000
    max_numeric_digits: PositiveInt = 4096
    max_examples: NonNegativeInt = 20
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None


class ComparisonValue(FrozenModel):
    """Lossless scalar evidence. Numeric text; dates/instants use integer epochs."""

    kind: Literal[
        "null",
        "nan",
        "infinity",
        "boolean",
        "integer",
        "string",
        "decimal",
        "float",
        "date",
        "timestamp",
    ]
    value: str | None = None
    unit: Literal["day", "s", "ms", "us", "ns"] | None = None
    timezone: str | None = None

    @model_validator(mode="after")
    def tagged(self) -> Self:
        if (self.kind in ("null", "nan")) != (self.value is None):
            fail("comparison_value", "only null/NaN omit value", "value")
        if self.kind not in ("date", "timestamp") and (self.unit or self.timezone):
            fail("comparison_value", "only temporal values carry units/zones", "unit")
        if self.kind in ("integer", "date", "timestamp") and not re.fullmatch(
            r"-?[0-9]+", self.value or ""
        ):
            fail("comparison_value", "integer text required", "value")
        if self.kind == "boolean" and self.value not in ("true", "false"):
            fail("comparison_value", "boolean text required", "value")
        if self.kind == "infinity" and self.value not in ("positive", "negative"):
            fail("comparison_value", "infinity sign required", "value")
        if self.kind in ("decimal", "float"):
            try:
                valid = Decimal(self.value or "").is_finite()
                if self.kind == "float":
                    valid = valid and math.isfinite(float(self.value or ""))
            except (InvalidOperation, ValueError):
                valid = False
            if not valid:
                fail("comparison_value", "finite numeric text required", "value")
        if self.kind == "date" and (self.unit not in ("day", "ms") or self.timezone):
            fail("comparison_value", "date requires day/ms without timezone", "unit")
        if self.kind == "timestamp" and self.unit not in ("s", "ms", "us", "ns"):
            fail("comparison_value", "timestamp requires an epoch unit", "unit")
        return self


class ComparisonDifference(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    category: Literal["contract", "content", "schema"]
    code: Text
    side: Side | None = None
    position: NonNegativeInt | None = None
    other_position: NonNegativeInt | None = None
    column: str | None = None
    key: tuple[ComparisonValue, ...] = ()
    left: tuple[ComparisonValue, ...] = ()
    right: tuple[ComparisonValue, ...] = ()
    left_count: NonNegativeInt = 0
    right_count: NonNegativeInt = 0
    message: Text


class ComparisonDiagnostic(FrozenModel):
    code: Text
    message: Text
    side: Side | None = None
    exception_type: Text | None = None


class ComparisonSource(FrozenModel):
    data: ArtifactRef
    table: TableArtifact | None = None
    execution: ExecutionResult | None = None
    observed_schema: tuple[tuple[str, str], ...] = ()


class AppliedPolicy(FrozenModel):
    side: Side
    column: str | None = None
    operation: Text
    count: NonNegativeInt


class ComparisonCounts(FrozenModel):
    left_rows: NonNegativeInt = 0
    right_rows: NonNegativeInt = 0
    matched_rows: NonNegativeInt = 0
    difference_records: NonNegativeInt = 0
    contract_violations: NonNegativeInt = 0
    final: bool = False


class ComparisonResult(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    scope: Literal["output_schema"] = "output_schema"
    comparison_id: Identifier
    spec: ComparisonSpec
    contract_sha256: Sha256
    spec_sha256: Sha256
    state: ComparisonState
    complete: bool
    reference: Literal["peer", "expected"]
    strategy: Literal["pending", "sequence", "key", "multiset", "matching"]
    selected_key: str | None = None
    left: ComparisonSource | None
    right: ComparisonSource | None
    counts: ComparisonCounts
    options: ComparisonOptions
    applied_policies: tuple[AppliedPolicy, ...]
    diagnostics: tuple[ComparisonDiagnostic, ...]
    examples: tuple[ComparisonDifference, ...]
    differences: ArtifactRef
    started_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    work_units: NonNegativeInt
    pair_checks: NonNegativeInt
    peak_disk_bytes: NonNegativeInt
    versions: tuple[VersionInfo, ...]

    def __bool__(self) -> bool:
        """Object existence must never imply observed equivalence."""
        raise TypeError(
            "ComparisonResult has no truth value; use assert_equivalent(result) "
            "or inspect result.state and result.complete explicitly"
        )

    @model_validator(mode="after")
    def consistent(self) -> Self:
        from equiframe.comparison import comparison_fingerprint
        from equiframe.serialization import contract_fingerprint

        if self.contract_sha256 != contract_fingerprint(self.spec.contract):
            fail("comparison_fingerprint", "contract fingerprint mismatch", "contract_sha256")
        if self.spec_sha256 != comparison_fingerprint(self.spec):
            fail("comparison_fingerprint", "spec fingerprint mismatch", "spec_sha256")
        if self.counts.final != self.complete:
            fail("comparison_completeness", "count completeness mismatch", "counts")
        if self.complete and (
            self.left is None or self.right is None or self.strategy == "pending"
        ):
            fail(
                "comparison_completeness", "complete requires both sources and strategy", "complete"
            )
        if self.complete:
            for source, rows in (
                (self.left, self.counts.left_rows),
                (self.right, self.counts.right_rows),
            ):
                if (
                    source is not None
                    and source.table is not None
                    and source.table.row_count != rows
                ):
                    fail(
                        "comparison_counts",
                        "final row count differs from captured table metadata",
                        "counts",
                    )
        if self.counts.matched_rows > min(self.counts.left_rows, self.counts.right_rows):
            fail("comparison_counts", "matched rows exceed observed rows", "counts")
        if self.counts.contract_violations > self.counts.difference_records:
            fail("comparison_counts", "violations exceed difference records", "counts")
        if (self.strategy == "key") != (self.selected_key is not None):
            fail("comparison_strategy", "selected key must match key strategy", "selected_key")
        if self.selected_key is not None and self.selected_key not in {
            key.name for key in self.spec.contract.output.schema_spec.keys if key.unique
        }:
            fail("comparison_strategy", "selected key is not a declared unique key", "selected_key")
        if len(self.examples) > min(self.options.max_examples, self.counts.difference_records):
            fail(
                "comparison_examples", "examples exceed their budget or recorded count", "examples"
            )
        if self.differences.format != "jsonl":
            fail("comparison_evidence", "difference artifact must be JSONL", "differences")
        if self.state == "equivalent" and (
            not self.complete
            or self.counts.difference_records
            or self.diagnostics
            or self.counts.matched_rows != self.counts.left_rows
            or self.counts.matched_rows != self.counts.right_rows
        ):
            fail(
                "false_equivalent",
                "equivalent requires complete checks without differences",
                "state",
            )
        if self.state == "different" and (not self.complete or not self.counts.difference_records):
            fail("comparison_state", "different requires completed checks and differences", "state")
        if self.state == "not_evaluable" and not self.diagnostics:
            fail("comparison_diagnostic", "not_evaluable requires a diagnostic", "diagnostics")
        return self
