"""Closed, immutable tabular IR; documents never contain executable code."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from equiframe._base import FrozenModel, Identifier, Text
from equiframe.contracts import LogicalType
from equiframe.values import ScalarValue

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


Expression = Annotated[
    Column | LiteralExpression | Compare | Boolean | Not | IsNull | IsNaN,
    Field(discriminator="kind"),
]
for _model in (Compare, Boolean, Not, IsNull, IsNaN):
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
    how: Literal["inner", "left"]
    null_keys: Literal["equal", "never"]
    right_prefix: Text = "right."


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


Node = Annotated[
    Scan | Project | Filter | Cast | EquiJoin | Aggregate | Sort, Field(discriminator="kind")
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


class CompilationCheck(FrozenModel):
    engine: Text
    supported: bool
    diagnostics: tuple[CompilationDiagnostic, ...] = ()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.supported == bool(self.diagnostics):
            raise ValueError("supported checks have no diagnostics; unsupported checks require one")
        return self
