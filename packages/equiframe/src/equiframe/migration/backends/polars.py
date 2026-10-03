"""Polars compiler using native expressions and independent native execution."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any

from equiframe.contracts import (
    BooleanType,
    Contract,
    DateType,
    DecimalType,
    FloatType,
    IntegerType,
    LogicalType,
    StringType,
)
from equiframe.errors import CapabilityError
from equiframe.registry import PolarsTransformation

from ..ports import CompiledPlan, compiler_check, require_supported
from ..types import (
    Aggregate,
    Boolean,
    Cast,
    Column,
    Compare,
    CompilationCheck,
    EquiJoin,
    Expression,
    Filter,
    IsNaN,
    IsNull,
    LiteralExpression,
    Not,
    Project,
    RelationalPlan,
    Scan,
)
from ..validation import (
    ValidatedIR,
    compilation_identity,
    decimal_limit,
    expression_type,
    integer_bounds,
    literal_scalar,
)

if TYPE_CHECKING:
    import polars as pl

    from equiframe.execution import RunContext


def _dtype(dtype: LogicalType) -> Any:
    import polars as pl

    if isinstance(dtype, IntegerType):
        return getattr(pl, ("Int" if dtype.signed else "UInt") + str(dtype.bits))
    if isinstance(dtype, DecimalType):
        return pl.Decimal(dtype.precision, dtype.scale)
    if isinstance(dtype, FloatType):
        return pl.Float32 if dtype.bits == 32 else pl.Float64
    if isinstance(dtype, BooleanType):
        return pl.Boolean
    if isinstance(dtype, StringType):
        return pl.String
    if isinstance(dtype, DateType):
        return pl.Date
    raise CapabilityError("unsupported Polars IR type")


def _expression(expression: Expression, columns: Any) -> pl.Expr:
    import polars as pl

    if isinstance(expression, Column):
        return pl.col(expression.name)
    if isinstance(expression, LiteralExpression):
        scalar = literal_scalar(expression)
        return pl.lit(scalar, dtype=_dtype(expression.logical_type))
    if isinstance(expression, Compare):
        left, right = _expression(expression.left, columns), _expression(expression.right, columns)
        operation = {"eq": "eq", "ne": "ne", "lt": "lt", "le": "le", "gt": "gt", "ge": "ge"}[
            expression.operation
        ]
        result = getattr(left, operation)(right)
        if isinstance(expression_type(expression.left, columns).logical_type, FloatType):
            nan = left.is_nan().fill_null(False) | right.is_nan().fill_null(False)
            result = pl.when(nan).then(pl.lit(expression.operation == "ne")).otherwise(result)
        return (
            pl.when(left.is_null() | right.is_null())
            .then(pl.lit(None, dtype=pl.Boolean))
            .otherwise(result)
        )
    if isinstance(expression, Boolean):
        values = [_expression(item, columns) for item in expression.arguments]
        result = values[0]
        for value in values[1:]:
            result = result & value if expression.operation == "and" else result | value
        return result
    argument = _expression(expression.argument, columns)
    if isinstance(expression, Not):
        return ~argument
    if isinstance(expression, IsNull):
        return argument.is_null()
    if isinstance(expression, IsNaN):
        return argument.is_nan().fill_null(False)
    raise CapabilityError("unknown Polars expression")


def _coerce(frame: pl.DataFrame, validated: ValidatedIR, node_id: str) -> pl.DataFrame:
    import polars as pl

    for column in validated.schema(node_id):
        dtype, series = column.logical_type, frame[column.name]
        if not column.nullable and series.null_count():
            raise CapabilityError("IR output contains forbidden NULL: " + column.name)
        if isinstance(dtype, (IntegerType, DecimalType)) and frame.height:
            lower, upper = (
                integer_bounds(dtype)
                if isinstance(dtype, IntegerType)
                else (decimal_limit(dtype).copy_negate(), decimal_limit(dtype))
            )
            minimum, maximum = series.min(), series.max()
            if minimum is not None:
                if not isinstance(minimum, (int, Decimal)) or not isinstance(
                    maximum, (int, Decimal)
                ):
                    raise CapabilityError("numeric IR column has incompatible native values")
                if minimum < lower or maximum > upper:
                    raise CapabilityError(
                        "IR output exceeds declared numeric range: " + column.name
                    )
    return frame.select(
        [
            pl.col(c.name).cast(_dtype(c.logical_type), strict=True)
            for c in validated.schema(node_id)
        ]
    )


def _aggregate(frame: pl.DataFrame, node: Aggregate, validated: ValidatedIR) -> pl.DataFrame:
    import polars as pl

    if node.null_groups == "drop" and node.group_by:
        frame = frame.filter(
            pl.all_horizontal([pl.col(name).is_not_null() for name in node.group_by])
        )
    expressions = []
    for measure in node.measures:
        if measure.operation == "count_rows":
            result = pl.len()
        else:
            assert measure.column is not None
            column = pl.col(measure.column)
            if measure.operation == "count_valid":
                result = column.count()
            elif measure.operation == "sum":
                scale = (
                    measure.logical_type.scale
                    if isinstance(measure.logical_type, DecimalType)
                    else 0
                )
                promoted = column.cast(pl.Decimal(38, scale), strict=True)
                # Polars grouped Decimal SUM can wrap i128. A conservative native
                # bound proves safety before any sum; it may reject cancellation.
                if frame.height:
                    with localcontext() as context:
                        context.prec = 100
                        threshold = Decimal((10**38 - 1) // frame.height).scaleb(-scale)
                    maximum = frame.select(promoted.abs().max()).item()
                    if maximum is not None and maximum > threshold:
                        raise CapabilityError(
                            "Polars SUM exceeds conservative exact accumulation bound"
                        )
                zero = Decimal(0).scaleb(-scale)
                result = (
                    pl.when(column.count() == 0)
                    .then(
                        pl.lit(
                            None if node.empty_sum == "null" else zero, dtype=pl.Decimal(38, scale)
                        )
                    )
                    .otherwise(promoted.sum())
                )
            else:
                result = getattr(column, measure.operation)()
        expressions.append(result.alias(measure.name))
    aggregated = (
        frame.group_by(list(node.group_by), maintain_order=True).agg(expressions)
        if node.group_by
        else frame.select(expressions)
    )
    return _coerce(aggregated, validated, node.node_id)


class PolarsCompiler:
    engine = "polars"

    def check(self, plan: RelationalPlan, contract: Contract) -> CompilationCheck:
        return compiler_check(self.engine, plan, contract)

    def compile(self, plan: RelationalPlan, contract: Contract) -> CompiledPlan:
        validated = require_supported(self.engine, plan, contract)
        identifier, ir_sha, contract_sha = compilation_identity(validated, self.engine)

        def transform(tables: Mapping[str, pl.DataFrame], context: RunContext) -> pl.DataFrame:
            import polars as pl

            frames: dict[str, pl.DataFrame] = {}
            for node in plan.nodes:
                context.check()
                if isinstance(node, Scan):
                    frame = tables[node.table].clone()
                elif isinstance(node, Project):
                    frame = (
                        frames[node.source]
                        .with_columns(
                            [
                                _expression(item.expression, validated.schema(node.source)).alias(
                                    item.name
                                )
                                for item in node.columns
                            ]
                        )
                        .select([item.name for item in node.columns])
                    )
                elif isinstance(node, Filter):
                    frame = frames[node.source].filter(
                        _expression(node.predicate, validated.schema(node.source))
                    )
                elif isinstance(node, Cast):
                    frame = frames[node.source]
                elif isinstance(node, EquiJoin):
                    right = frames[node.right].rename(
                        {name: node.right_prefix + name for name in frames[node.right].columns}
                    )
                    frame = frames[node.left].join(
                        right,
                        left_on=[key.left for key in node.keys],
                        right_on=[node.right_prefix + key.right for key in node.keys],
                        how=node.how,
                        nulls_equal=node.null_keys == "equal",
                        coalesce=False,
                        maintain_order="left_right",
                    )
                elif isinstance(node, Aggregate):
                    frame = _aggregate(frames[node.source], node, validated)
                else:
                    frame = frames[node.source]
                    if (
                        node.ties == "reject"
                        and frame.select(
                            pl.struct([key.column for key in node.by]).is_duplicated().any()
                        ).item()
                    ):
                        raise CapabilityError("Sort encountered forbidden ties")
                    frame = frame.sort(
                        [key.column for key in node.by],
                        descending=[key.direction == "descending" for key in node.by],
                        nulls_last=[key.nulls == "last" for key in node.by],
                        maintain_order=True,
                    )
                frames[node.node_id] = _coerce(frame, validated, node.node_id)
            return frames[plan.output]

        transformation = PolarsTransformation(
            identifier, transform, "migration-native-ir1.0/polars"
        )
        return CompiledPlan(
            self.engine, transformation, ir_sha, contract_sha, self.check(plan, contract)
        )
