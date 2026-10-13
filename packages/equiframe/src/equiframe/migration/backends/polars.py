"""Polars compiler using native expressions and independent native execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any, Literal

from equiframe._decimal import exact_decimal_context
from equiframe.contracts import (
    BooleanType,
    Contract,
    DateType,
    DecimalType,
    FloatType,
    IntegerType,
    LogicalType,
    StringType,
    TimestampType,
)
from equiframe.errors import CapabilityError
from equiframe.registry import PolarsTransformation

from ..ports import CompiledPlan, compiler_check, require_supported
from ..types import (
    Aggregate,
    Arithmetic,
    Boolean,
    Cast,
    Coalesce,
    Column,
    Compare,
    CompilationCheck,
    CompilationDiagnostic,
    Concatenate,
    Conditional,
    DecimalRound,
    Deduplicate,
    EquiJoin,
    Expression,
    Filter,
    IRColumn,
    IsNaN,
    IsNull,
    LiteralExpression,
    LocalizeTimestamp,
    Not,
    Project,
    RelationalPlan,
    Scan,
    Window,
)
from ..validation import (
    ValidatedIR,
    compilation_identity,
    decimal_limit,
    expression_type,
    integer_bounds,
    iter_expressions,
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
    if isinstance(dtype, TimestampType) and dtype.unit != "s":
        return pl.Datetime(dtype.unit, time_zone=dtype.timezone)
    raise CapabilityError("unsupported Polars IR type")


def _native_name(position: int) -> str:
    return f"_equiframe_column_{position}"


def _native_frame(frame: pl.DataFrame) -> pl.DataFrame:
    """Enter a collision-free namespace before any native name resolution."""
    return frame.rename({name: _native_name(i) for i, name in enumerate(frame.columns)})


def _logical_frame(frame: pl.DataFrame, names: Sequence[str]) -> pl.DataFrame:
    """Restore the declared names only after native expression evaluation."""
    return frame.rename(dict(zip(frame.columns, names, strict=True)))


def _column(name: str, names: Sequence[str]) -> pl.Expr:
    """Resolve a literal logical name in an already renamed native frame."""
    import polars as pl

    # Polars 1.30 cannot compose different escaped-name regex selectors. Even
    # nth(index) resolves back to a name which may expand '*' or '^...$'. All
    # evaluated frames therefore use safe generated names, never user patterns.
    return pl.col(_native_name(names.index(name)))


def _expression(expression: Expression, columns: tuple[IRColumn, ...]) -> pl.Expr:
    import polars as pl

    if isinstance(expression, Column):
        return _column(expression.name, tuple(column.name for column in columns))
    if isinstance(expression, LiteralExpression):
        scalar = literal_scalar(expression)
        return pl.lit(scalar, dtype=_dtype(expression.logical_type))
    if isinstance(expression, Arithmetic):
        operand = expression_type(expression.left, columns).logical_type
        scale = (
            (
                expression.logical_type.scale
                if expression.operation == "multiply"
                and isinstance(expression.logical_type, DecimalType)
                else operand.scale
            )
            if isinstance(operand, DecimalType)
            else 0
        )
        left = _expression(expression.left, columns).cast(pl.Decimal(38, scale), strict=True)
        right = _expression(expression.right, columns).cast(pl.Decimal(38, scale), strict=True)
        result = {
            "add": lambda: left + right,
            "subtract": lambda: left - right,
            "multiply": lambda: left * right,
        }[expression.operation]()
        return result.cast(_dtype(expression.logical_type), strict=True)
    if isinstance(expression, DecimalRound):
        mode: Literal["half_away_from_zero", "half_to_even"] = (
            "half_away_from_zero"
            if expression.rounding == "half_away_from_zero"
            else "half_to_even"
        )
        return (
            _expression(expression.argument, columns)
            .round(expression.logical_type.scale, mode=mode)
            .cast(_dtype(expression.logical_type), strict=True)
        )
    if isinstance(expression, LocalizeTimestamp):
        ambiguity: Literal["raise", "earliest", "latest"] = (
            "raise"
            if expression.ambiguous == "reject"
            else "earliest"
            if expression.ambiguous == "earlier"
            else "latest"
        )
        return _expression(expression.argument, columns).dt.replace_time_zone(
            expression.timezone, ambiguous=ambiguity, non_existent="raise"
        )
    if isinstance(expression, Coalesce):
        return pl.coalesce([_expression(item, columns) for item in expression.arguments])
    if isinstance(expression, Conditional):
        return (
            pl.when(_expression(expression.predicate, columns))
            .then(_expression(expression.then, columns))
            .otherwise(_expression(expression.otherwise, columns))
        )
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


def _check_localizations(
    frame: pl.DataFrame, expression: Expression, columns: tuple[IRColumn, ...]
) -> None:
    """Validate each fallible native localization before relational pruning."""
    import polars as pl

    for item in iter_expressions(expression):
        if not isinstance(item, LocalizeTimestamp):
            continue
        dtype = expression_type(item.argument, columns).logical_type
        if not (isinstance(dtype, TimestampType)):
            raise AssertionError("Internal invariant check failed.")
        before = _expression(item.argument, columns).cast(pl.Int64)
        after = _expression(item, columns).cast(pl.Int64)
        # Decimal(38,0) subtraction is native and wide enough for the full
        # difference of two signed int64 values. An int64 subtraction here
        # would wrap too and silently certify the broken timestamp kernel.
        maximum_offset = 86400 * {"s": 1, "ms": 1000, "us": 1000000, "ns": 1000000000}[dtype.unit]
        delta = (after.cast(pl.Decimal(38, 0)) - before.cast(pl.Decimal(38, 0))).abs()
        bad = (before.is_not_null() & after.is_null()) | (
            delta > pl.lit(Decimal(maximum_offset), dtype=pl.Decimal(38, 0))
        )
        if _native_frame(frame).select(bad.fill_null(False).any()).item():
            raise CapabilityError("Polars timestamp localization exceeds faithful int64 range")


def _coerce(frame: pl.DataFrame, validated: ValidatedIR, node_id: str) -> pl.DataFrame:
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
    names = frame.columns
    selected = _native_frame(frame).select(
        [
            _column(c.name, names).cast(_dtype(c.logical_type), strict=True)
            for c in validated.schema(node_id)
        ]
    )
    return _logical_frame(selected, [c.name for c in validated.schema(node_id)])


def _aggregate(frame: pl.DataFrame, node: Aggregate, validated: ValidatedIR) -> pl.DataFrame:
    import polars as pl

    names = frame.columns
    frame = _native_frame(frame)
    if node.null_groups == "drop" and node.group_by:
        frame = frame.filter(
            pl.all_horizontal([_column(name, names).is_not_null() for name in node.group_by])
        )
    expressions = []
    for i, measure in enumerate(node.measures):
        if measure.operation == "count_rows":
            result = pl.len()
        else:
            if not (measure.column is not None):
                raise AssertionError("Internal invariant check failed.")
            column = _column(measure.column, names)
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
                    with localcontext(exact_decimal_context()):
                        threshold = Decimal((10**38 - 1) // frame.height).scaleb(-scale)
                    maximum = frame.select(promoted.abs().max()).item()
                    if maximum is not None and maximum > threshold:
                        raise CapabilityError(
                            "Polars SUM exceeds conservative exact accumulation bound"
                        )
                zero = Decimal((0, (0,), -scale))
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
        expressions.append(result.alias(f"_equiframe_measure_{i}"))
    aggregated = (
        frame.group_by([_column(name, names) for name in node.group_by], maintain_order=True).agg(
            expressions
        )
        if node.group_by
        else frame.select(expressions)
    )
    logical = _logical_frame(aggregated, [*node.group_by, *(m.name for m in node.measures)])
    return _coerce(logical, validated, node.node_id)


def _join(left: pl.DataFrame, right: pl.DataFrame, node: EquiJoin) -> pl.DataFrame:
    """Keep join-key selectors scalar using collision-free native-local names."""
    # Polars forbids selector expressions as join keys, including by_name().
    # Rename every column simultaneously into disjoint safe namespaces; this
    # also handles inputs whose real names equal one of these internal names.
    left_names = {name: f"_equiframe_join_left_{i}" for i, name in enumerate(left.columns)}
    right_names = {name: f"_equiframe_join_right_{i}" for i, name in enumerate(right.columns)}
    joined = left.rename(left_names).join(
        right.rename(right_names),
        left_on=[left_names[key.left] for key in node.keys],
        right_on=[right_names[key.right] for key in node.keys],
        how=node.how,
        nulls_equal=node.null_keys == "equal",
        coalesce=False,
        maintain_order="left_right",
    )
    restored = {temporary: name for name, temporary in left_names.items()}
    if node.how not in ("semi", "anti"):
        restored.update(
            {temporary: node.right_prefix + name for name, temporary in right_names.items()}
        )
    return joined.rename(restored)


class PolarsCompiler:
    engine = "polars"

    def check(self, plan: RelationalPlan, contract: Contract) -> CompilationCheck:
        check = compiler_check(self.engine, plan, contract)
        if check.supported:
            validated = require_supported(self.engine, plan, contract)
            if any(
                isinstance(column.logical_type, TimestampType) and column.logical_type.unit == "s"
                for schema in validated.node_schemas
                for column in schema.columns
            ):
                return CompilationCheck(
                    engine=self.engine,
                    supported=False,
                    diagnostics=(
                        CompilationDiagnostic(
                            code="timestamp_unit_not_supported",
                            message=(
                                "Polars timestamp IR cannot preserve seconds physical unit; "
                                "declare explicit millisecond input"
                            ),
                        ),
                    ),
                )
            for node in plan.nodes:
                if not isinstance(node, (Project, Filter)):
                    continue
                expressions = (
                    tuple(item.expression for item in node.columns)
                    if isinstance(node, Project)
                    else (node.predicate,)
                    if isinstance(node, Filter)
                    else ()
                )
                for expression in expressions:
                    for item in iter_expressions(expression):
                        message = None
                        if isinstance(item, Arithmetic) and item.operation == "divide":
                            message = (
                                "Polars Decimal division cannot preserve "
                                "declared exact/rounding semantics"
                            )
                        if isinstance(item, Arithmetic) and item.operation == "multiply":
                            left = expression_type(
                                item.left, validated.schema(node.source)
                            ).logical_type
                            right = expression_type(
                                item.right, validated.schema(node.source)
                            ).logical_type
                            if (
                                isinstance(left, DecimalType)
                                and isinstance(right, DecimalType)
                                and left.precision + right.precision + left.scale + right.scale > 38
                            ):
                                message = (
                                    "Polars Decimal multiply exceeds conservative "
                                    "exact intermediate coefficient bound"
                                )
                        if message:
                            return CompilationCheck(
                                engine=self.engine,
                                supported=False,
                                diagnostics=(
                                    CompilationDiagnostic(
                                        code="native_decimal_not_supported",
                                        message=message,
                                        node_id=node.node_id,
                                    ),
                                ),
                            )
        return check

    def compile(self, plan: RelationalPlan, contract: Contract) -> CompiledPlan:
        check = self.check(plan, contract)
        if not check.supported:
            raise CapabilityError(check.diagnostics[0].message)
        validated = require_supported(self.engine, plan, contract)
        identifier, ir_sha, contract_sha = compilation_identity(
            validated,
            self.engine,
            implementation_version="migration-native-ir1.0/polars/product-semantics-v5",
        )

        def transform(tables: Mapping[str, pl.DataFrame], context: RunContext) -> pl.DataFrame:
            import polars as pl

            frames: dict[str, pl.DataFrame] = {}
            for node in plan.nodes:
                context.check()
                if isinstance(node, Scan):
                    frame = tables[node.table].clone()
                elif isinstance(node, Project):
                    for item in node.columns:
                        _check_localizations(
                            frames[node.source], item.expression, validated.schema(node.source)
                        )
                    # Stored source frames have validated order after _coerce.
                    # Evaluate every expression against the same renamed source;
                    # distinct temporary output names preserve simultaneous aliases.
                    frame = _native_frame(frames[node.source]).with_columns(
                        [
                            _expression(item.expression, validated.schema(node.source)).alias(
                                f"_equiframe_project_{i}"
                            )
                            for i, item in enumerate(node.columns)
                        ]
                    )
                    frame = frame.select(
                        [pl.col(f"_equiframe_project_{i}") for i in range(len(node.columns))]
                    )
                    frame = _logical_frame(frame, [item.name for item in node.columns])
                elif isinstance(node, Filter):
                    _check_localizations(
                        frames[node.source], node.predicate, validated.schema(node.source)
                    )
                    source = frames[node.source]
                    frame = _logical_frame(
                        _native_frame(source).filter(
                            _expression(node.predicate, validated.schema(node.source))
                        ),
                        source.columns,
                    )
                elif isinstance(node, Cast):
                    frame = frames[node.source]
                elif isinstance(node, EquiJoin):
                    for side, names, unique in (
                        (
                            frames[node.left],
                            [key.left for key in node.keys],
                            node.cardinality in ("one_to_one", "one_to_many"),
                        ),
                        (
                            frames[node.right],
                            [key.right for key in node.keys],
                            node.cardinality in ("one_to_one", "many_to_one"),
                        ),
                    ):
                        native = _native_frame(side)
                        matchable = (
                            native
                            if node.null_keys == "equal"
                            else native.filter(
                                pl.all_horizontal(
                                    [_column(name, side.columns).is_not_null() for name in names]
                                )
                            )
                        )
                        if (
                            unique
                            and matchable.select(
                                pl.struct([_column(name, side.columns) for name in names])
                                .is_duplicated()
                                .any()
                            ).item()
                        ):
                            raise CapabilityError(
                                "Join violates declared cardinality: " + node.cardinality
                            )
                    frame = _join(frames[node.left], frames[node.right], node)
                elif isinstance(node, Window):
                    names = frames[node.source].columns
                    frame = _native_frame(frames[node.source])
                    tie_keys = list(
                        dict.fromkeys((*node.partition_by, *(key.column for key in node.by)))
                    )
                    if frame.select(
                        pl.struct([_column(name, names) for name in tie_keys]).is_duplicated().any()
                    ).item():
                        raise CapabilityError("Window encountered forbidden order ties")
                    frame = frame.sort(
                        [_column(key.column, names) for key in node.by],
                        descending=[key.direction == "descending" for key in node.by],
                        nulls_last=[key.nulls == "last" for key in node.by],
                        maintain_order=True,
                    )
                    window_expressions: list[pl.Expr] = []
                    for window_measure in node.measures:
                        if window_measure.operation == "row_number":
                            value = pl.int_range(1, pl.len() + 1, dtype=pl.Int64)
                        else:
                            if window_measure.column is None:
                                raise CapabilityError("lag/lead require an input column")
                            offset = (
                                window_measure.offset
                                if window_measure.operation == "lag"
                                else -window_measure.offset
                            )
                            value = _column(window_measure.column, names).shift(offset)
                        if node.partition_by:
                            value = value.over([_column(name, names) for name in node.partition_by])
                        window_expressions.append(
                            value.alias(f"_equiframe_window_{len(window_expressions)}")
                        )
                    frame = frame.with_columns(window_expressions)
                    frame = _logical_frame(
                        frame, [*names, *(window_measure.name for window_measure in node.measures)]
                    )
                elif isinstance(node, Aggregate):
                    frame = _aggregate(frames[node.source], node, validated)
                elif isinstance(node, Concatenate):
                    frame = pl.concat([frames[ref] for ref in node.sources], how="vertical")
                elif isinstance(node, Deduplicate):
                    names = frames[node.source].columns
                    frame = _native_frame(frames[node.source])
                    if node.keep == "first":
                        tie_keys = list(
                            dict.fromkeys((*node.keys, *(key.column for key in node.by)))
                        )
                        if frame.select(
                            pl.struct([_column(name, names) for name in tie_keys])
                            .is_duplicated()
                            .any()
                        ).item():
                            raise CapabilityError("Deduplicate encountered forbidden tiebreak ties")
                        frame = frame.sort(
                            [_column(key.column, names) for key in node.by],
                            descending=[key.direction == "descending" for key in node.by],
                            nulls_last=[key.nulls == "last" for key in node.by],
                            maintain_order=True,
                        )
                    frame = frame.unique(
                        subset=[_native_name(names.index(name)) for name in node.keys],
                        keep="first",
                        maintain_order=True,
                    )
                    frame = _logical_frame(frame, names)
                else:
                    names = frames[node.source].columns
                    frame = _native_frame(frames[node.source])
                    if (
                        node.ties == "reject"
                        and frame.select(
                            pl.struct([_column(key.column, names) for key in node.by])
                            .is_duplicated()
                            .any()
                        ).item()
                    ):
                        raise CapabilityError("Sort encountered forbidden ties")
                    frame = frame.sort(
                        [_column(key.column, names) for key in node.by],
                        descending=[key.direction == "descending" for key in node.by],
                        nulls_last=[key.nulls == "last" for key in node.by],
                        maintain_order=True,
                    )
                    frame = _logical_frame(frame, names)
                frames[node.node_id] = _coerce(frame, validated, node.node_id)
            return frames[plan.output]

        transformation = PolarsTransformation(
            identifier, transform, "migration-native-ir1.0/polars/product-semantics-v5"
        )
        return CompiledPlan(
            self.engine, transformation, ir_sha, contract_sha, self.check(plan, contract)
        )
