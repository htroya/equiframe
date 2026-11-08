"""Closed, immutable tabular IR; documents never contain executable code."""

from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, Text, _ExplicitOutcome
from equiframe.contracts import DecimalType, LogicalType
from equiframe.values import ScalarValue, TimeZone

Engine = Literal["pandas", "polars", "duckdb"]


class Column(FrozenModel):
    kind: Literal["column"] = "column"
    name: Text


class LiteralExpression(FrozenModel):
    kind: Literal["literal"] = "literal"
    logical_type: LogicalType
    value: ScalarValue
    unit: Text | None = None


class Compare(FrozenModel):
    kind: Literal["compare"] = "compare"
    operation: Literal["eq", "ne", "lt", "le", "gt", "ge"]
    left: Expression
    right: Expression
    nan: Literal["unordered"] = "unordered"


class Boolean(FrozenModel):
    kind: Literal["boolean"] = "boolean"
    operation: Literal["and", "or"]
    arguments: Annotated[tuple[Expression, ...], Field(min_length=2, max_length=32)]


class Not(FrozenModel):
    kind: Literal["not"] = "not"
    argument: Expression


class IsNull(FrozenModel):
    kind: Literal["is_null"] = "is_null"
    argument: Expression


class IsNaN(FrozenModel):
    kind: Literal["is_nan"] = "is_nan"
    argument: Expression


class Arithmetic(FrozenModel):
    kind: Literal["arithmetic"] = "arithmetic"
    operation: Literal["add", "subtract", "multiply", "divide"]
    left: Expression
    right: Expression
    logical_type: LogicalType
    unit: Text
    overflow: Literal["reject"] = "reject"
    rounding: Literal["exact", "half_even", "half_away_from_zero"] = "exact"

    @model_serializer(mode="wrap")
    def historical_defaults(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result = cast("dict[str, Any]", handler(self))
        if self.rounding == "exact":
            result.pop("rounding", None)
        return result

    @model_validator(mode="after")
    def rounding_scope(self) -> Self:
        if self.operation != "divide" and self.rounding != "exact":
            raise ValueError("only division declares rounding; use DecimalRound explicitly")
        return self


class DecimalRound(FrozenModel):
    kind: Literal["decimal_round"] = "decimal_round"
    argument: Expression
    logical_type: DecimalType
    rounding: Literal["half_even", "half_away_from_zero"]
    overflow: Literal["reject"] = "reject"


class LocalizeTimestamp(FrozenModel):
    kind: Literal["localize_timestamp"] = "localize_timestamp"
    argument: Expression
    timezone: TimeZone
    ambiguous: Literal["reject", "earlier", "later"]
    nonexistent: Literal["reject"] = "reject"


class Coalesce(FrozenModel):
    kind: Literal["coalesce"] = "coalesce"
    arguments: Annotated[tuple[Expression, ...], Field(min_length=2, max_length=32)]


class Conditional(FrozenModel):
    kind: Literal["conditional"] = "conditional"
    predicate: Expression
    then: Expression
    otherwise: Expression
    unknown: Literal["otherwise"] = "otherwise"


Expression = Annotated[
    Column
    | LiteralExpression
    | Compare
    | Boolean
    | Not
    | IsNull
    | IsNaN
    | Arithmetic
    | DecimalRound
    | LocalizeTimestamp
    | Coalesce
    | Conditional,
    Field(discriminator="kind"),
]
for _model in (
    Compare,
    Boolean,
    Not,
    IsNull,
    IsNaN,
    Arithmetic,
    DecimalRound,
    LocalizeTimestamp,
    Coalesce,
    Conditional,
):
    _model.model_rebuild()


class NamedExpression(FrozenModel):
    name: Text
    expression: Expression


class Scan(FrozenModel):
    kind: Literal["scan"] = "scan"
    node_id: Identifier
    table: Text


class Project(FrozenModel):
    kind: Literal["project"] = "project"
    node_id: Identifier
    source: Identifier
    columns: Annotated[tuple[NamedExpression, ...], Field(min_length=1, max_length=256)]


class Filter(FrozenModel):
    kind: Literal["filter"] = "filter"
    node_id: Identifier
    source: Identifier
    predicate: Expression


class CastColumn(FrozenModel):
    column: Text
    logical_type: LogicalType


class Cast(FrozenModel):
    kind: Literal["cast"] = "cast"
    node_id: Identifier
    source: Identifier
    columns: Annotated[tuple[CastColumn, ...], Field(min_length=1, max_length=256)]
    loss: Literal["reject"] = "reject"


class JoinKey(FrozenModel):
    left: Text
    right: Text


class EquiJoin(FrozenModel):
    kind: Literal["join"] = "join"
    node_id: Identifier
    left: Identifier
    right: Identifier
    keys: Annotated[tuple[JoinKey, ...], Field(min_length=1, max_length=32)]
    how: Literal["inner", "left", "right", "full", "semi", "anti"]
    null_keys: Literal["equal", "never"]
    right_prefix: Text = "right."
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"] = (
        "many_to_many"
    )

    @model_serializer(mode="wrap")
    def historical_defaults(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result = cast("dict[str, Any]", handler(self))
        if self.cardinality == "many_to_many":
            result.pop("cardinality", None)
        return result


class Measure(FrozenModel):
    name: Text
    operation: Literal["count_rows", "count_valid", "sum", "min", "max"]
    column: Text | None = None
    logical_type: LogicalType
    unit: Text | None = None

    @model_validator(mode="after")
    def column_required(self) -> Self:
        if (self.operation == "count_rows") != (self.column is None):
            raise ValueError("count_rows has no column; other measures require a column")
        return self


class Aggregate(FrozenModel):
    kind: Literal["aggregate"] = "aggregate"
    node_id: Identifier
    source: Identifier
    group_by: Annotated[tuple[Text, ...], Field(max_length=32)] = ()
    measures: Annotated[tuple[Measure, ...], Field(min_length=1, max_length=128)]
    null_groups: Literal["retain", "drop"]
    empty_sum: Literal["null", "zero"]


class SortKey(FrozenModel):
    column: Text
    direction: Literal["ascending", "descending"]
    nulls: Literal["first", "last"]


class Sort(FrozenModel):
    kind: Literal["sort"] = "sort"
    node_id: Identifier
    source: Identifier
    by: Annotated[tuple[SortKey, ...], Field(min_length=1, max_length=32)]
    ties: Literal["unspecified", "identical_rows", "reject"]


class WindowMeasure(FrozenModel):
    name: Text
    operation: Literal["row_number", "lag", "lead"]
    column: Text | None = None
    logical_type: LogicalType
    unit: Text | None = None
    offset: int = Field(default=1, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def column_required(self) -> Self:
        if (self.operation == "row_number") != (self.column is None):
            raise ValueError("row_number has no column; lag/lead require a column")
        if self.operation == "row_number" and self.offset != 1:
            raise ValueError("offset applies only to lag/lead")
        return self


class Window(FrozenModel):
    kind: Literal["window"] = "window"
    node_id: Identifier
    source: Identifier
    partition_by: Annotated[tuple[Text, ...], Field(max_length=32)] = ()
    by: Annotated[tuple[SortKey, ...], Field(min_length=1, max_length=32)]
    measures: Annotated[tuple[WindowMeasure, ...], Field(min_length=1, max_length=128)]
    ties: Literal["reject"] = "reject"


class Concatenate(FrozenModel):
    kind: Literal["concatenate"] = "concatenate"
    node_id: Identifier
    sources: Annotated[tuple[Identifier, ...], Field(min_length=2, max_length=32)]
    schema_policy: Literal["identical"] = "identical"


class Deduplicate(FrozenModel):
    kind: Literal["deduplicate"] = "deduplicate"
    node_id: Identifier
    source: Identifier
    keys: Annotated[tuple[Text, ...], Field(min_length=1, max_length=256)]
    keep: Literal["identical", "first"] = "identical"
    nulls: Literal["equal"] = "equal"
    by: Annotated[tuple[SortKey, ...], Field(max_length=32)] = ()
    ties: Literal["reject"] = "reject"

    @model_serializer(mode="wrap")
    def historical_defaults(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result = cast("dict[str, Any]", handler(self))
        if not self.by:
            result.pop("by", None)
        result.pop("ties", None)
        return result

    @model_validator(mode="after")
    def deterministic_selection(self) -> Self:
        if (self.keep == "first") != bool(self.by):
            raise ValueError("keep=first requires by; keep=identical forbids by")
        return self


Node = Annotated[
    Scan
    | Project
    | Filter
    | Cast
    | EquiJoin
    | Aggregate
    | Sort
    | Concatenate
    | Deduplicate
    | Window,
    Field(discriminator="kind"),
]


class RelationalPlan(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    nodes: Annotated[tuple[Node, ...], Field(min_length=1, max_length=128)]
    output: Identifier


class IRColumn(FrozenModel):
    name: Text
    logical_type: LogicalType
    nullable: bool
    unit: Text | None = None


class NodeSchema(FrozenModel):
    node_id: Identifier
    columns: tuple[IRColumn, ...]


class CompilationDiagnostic(FrozenModel):
    code: Identifier
    message: Text
    node_id: Identifier | None = None


class CompilationCheck(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .supported explicitly; preflight support does not establish equivalence"
    )

    engine: Text
    supported: bool
    diagnostics: tuple[CompilationDiagnostic, ...] = ()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.supported == bool(self.diagnostics):
            raise ValueError("supported checks have no diagnostics; unsupported checks require one")
        return self
