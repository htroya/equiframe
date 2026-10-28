"""Polars compiler using native expressions and independent native execution."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, localcontext
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from equiframe._decimal import exact_decimal_context
from equiframe._timezones import (
    _timezone_data,
    _timezone_resource_hash,
    _TimezoneData,
    _TimezoneRule,
)
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
from ._timestamp_transport import _TimestampCodec, _TimestampPolarsTransformation

if TYPE_CHECKING:
    import polars as pl

    from equiframe.execution import RunContext

_COMPILER_VERSION = "migration-native-ir1.0/polars/product-semantics-v14"


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
    if isinstance(dtype, TimestampType):
        return pl.Int64
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


def _native_civil_year(seconds: pl.Expr) -> pl.Expr:
    import polars as pl

    days = seconds // 86400 + 719468
    era = days // 146097
    day_of_era = days - era * 146097
    year_of_era = (
        day_of_era - day_of_era // 1460 + day_of_era // 36524 - day_of_era // 146096
    ) // 365
    year = year_of_era + era * 400
    day_of_year = day_of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    month_prime = (5 * day_of_year + 2) // 153
    month = month_prime + pl.when(month_prime < 10).then(3).otherwise(-9)
    return year + (month <= 2).cast(pl.Int64)


def _native_civil_days(year: pl.Expr, month: int, day: int | pl.Expr) -> pl.Expr:
    adjusted = year - int(month <= 2)
    era = adjusted // 400
    yoe = adjusted - era * 400
    mp = month + (-3 if month > 2 else 9)
    doy = (153 * mp + 2) // 5 + day - 1
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def _native_leap_year(year: pl.Expr) -> pl.Expr:
    return (year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))


def _native_rule_seconds(year: pl.Expr, rule: _TimezoneRule) -> pl.Expr:
    import polars as pl

    if rule.kind == "M":
        month, week, weekday = rule.values
        first = _native_civil_days(year, month, 1)
        day = 1 + (weekday - (first + 4) % 7) % 7 + (week - 1) * 7
        if week == 5:
            length: int | pl.Expr = 29 if month == 2 else 30 if month in (4, 6, 9, 11) else 31
            if month == 2:
                length = 28 + _native_leap_year(year).cast(pl.Int64)
            day = day - pl.when(day > length).then(7).otherwise(0)
        days = _native_civil_days(year, month, day)
    else:
        number = rule.values[0]
        extra = _native_leap_year(year).cast(pl.Int64) if rule.kind == "J" and number >= 60 else 0
        days = _native_civil_days(year, 1, 1) + number - int(rule.kind == "J") + extra
    wide = pl.Decimal(38, 0)
    return days.cast(wide) * pl.lit(Decimal(86400), dtype=wide) + pl.lit(
        Decimal(rule.seconds), dtype=wide
    )


def _native_timezone_offset(
    frame: pl.DataFrame, data: _TimezoneData, context: RunContext
) -> pl.DataFrame:
    import polars as pl

    context.check()
    seconds = pl.col("_seconds")
    if data.transitions:
        boundaries = pl.lit(pl.Series("_boundaries", data.transitions, dtype=pl.Int64))
        history = pl.lit(pl.Series("_offset_values", data.interval_offsets, dtype=pl.Int64)).gather(
            boundaries.search_sorted(seconds, side="right")
        )
    else:
        history = pl.lit(data.interval_offsets[0], dtype=pl.Int64)
    continuation = data.continuation
    if continuation is None:
        return frame.with_columns(history.alias("_actual_offset"))
    if continuation.daylight is None:
        tail = pl.lit(continuation.standard, dtype=pl.Int64)
    else:
        start_rule, end_rule = continuation.start, continuation.end
        if start_rule is None or end_rule is None:
            raise AssertionError("Invalid internal TZif continuation")
        if data.transitions and not frame.select((seconds >= data.transitions[-1]).any()).item():
            return frame.with_columns(history.alias("_actual_offset"))
        frame = frame.with_columns(_native_civil_year(seconds).alias("_year"))
        events = []
        expressions = []
        for index, shift in enumerate((-1, 0, 1)):
            first = "_start" + str(index)
            last = "_end" + str(index)
            expressions.append(
                (
                    _native_rule_seconds(pl.col("_year") + shift, start_rule)
                    - continuation.standard
                ).alias(first)
            )
            expressions.append(
                (
                    _native_rule_seconds(pl.col("_year") + shift, end_rule) - continuation.daylight
                ).alias(last)
            )
            events.extend([(first, continuation.daylight), (last, continuation.standard)])
        frame = frame.with_columns(expressions)
        frame = frame.with_columns(
            pl.max_horizontal(
                [
                    pl.when(seconds >= pl.col(name)).then(pl.col(name)).otherwise(None)
                    for name, _ in events
                ]
            ).alias("_last_transition")
        )
        tail = pl.lit(continuation.standard, dtype=pl.Int64)
        for name, offset in events:
            tail = pl.when(pl.col("_last_transition") == pl.col(name)).then(offset).otherwise(tail)
    actual_offset = (
        pl.when(seconds >= data.transitions[-1]).then(tail).otherwise(history)
        if data.transitions
        else tail
    )
    return frame.with_columns(actual_offset.alias("_actual_offset"))


def _native_localized_frame(
    frame: pl.DataFrame,
    argument: pl.Expr,
    *,
    data: _TimezoneData,
    unit: str,
    ambiguous: str,
    context: RunContext,
) -> tuple[pl.Series, pl.Series, pl.Series, pl.Series]:
    import polars as pl

    context.check()
    if not (unit in ("s", "ms", "us", "ns") and ambiguous in ("reject", "earlier", "later")):
        raise CapabilityError("Invalid timestamp policy")
    factor = {"s": 1, "ms": 1000, "us": 1000000, "ns": 1000000000}[unit]
    wide = pl.Decimal(38, 0)
    state = frame.with_columns(argument.cast(pl.Int64).alias("_wall")).select("_wall")
    seconds_view = unit == "s"
    if seconds_view:
        state = state.with_columns(
            (pl.col("_wall").cast(wide) * pl.lit(Decimal(1000), dtype=wide))
            .cast(pl.Int64, strict=True)
            .alias("_wall")
        )
        factor = 1000
    state = state.with_columns(
        pl.lit(0, dtype=pl.UInt16).alias("_count"), pl.lit(None, dtype=wide).alias("_chosen")
    )
    for offset in data.offsets:
        context.check()
        candidate = pl.col("_wall").cast(wide) - pl.lit(Decimal(offset * factor), dtype=wide)
        work = state.with_columns(candidate.alias("_candidate"))
        work = work.with_columns(
            (pl.col("_wall") // factor - offset).fill_null(0).alias("_seconds")
        )
        work = _native_timezone_offset(work, data, context)
        valid = (pl.col("_wall").is_not_null() & (pl.col("_actual_offset") == offset)).fill_null(
            False
        )
        work = work.with_columns(valid.alias("_valid_candidate"))
        work = work.with_columns(
            pl.when(pl.col("_valid_candidate"))
            .then(pl.col("_candidate"))
            .otherwise(None)
            .alias("_candidate_option")
        )
        previous = pl.col("_chosen")
        option = pl.col("_candidate_option")
        better = option > previous if ambiguous == "later" else option < previous
        choice = pl.when(previous.is_null() | better).then(option).otherwise(previous)
        state = work.select(
            pl.col("_wall"),
            (pl.col("_count") + pl.col("_valid_candidate").cast(pl.UInt16)).alias("_count"),
            choice.alias("_chosen"),
        )
    fits = pl.col("_chosen").is_between(
        pl.lit(Decimal(-(2**63)), dtype=wide), pl.lit(Decimal(2**63 - 1), dtype=wide)
    )
    state = state.with_columns(
        (pl.col("_chosen").is_not_null() & ~fits).fill_null(False).alias("_output_range_failed")
    )
    state = state.with_columns(
        pl.when(fits)
        .then(pl.col("_chosen"))
        .otherwise(None)
        .cast(pl.Int64, strict=True)
        .alias("_value")
    )
    if seconds_view:
        state = state.with_columns((pl.col("_value") // 1000).alias("_value"))
    return (
        state["_value"],
        state["_count"],
        state["_output_range_failed"],
        state["_wall"].is_not_null(),
    )


def _expression(
    expression: Expression,
    columns: tuple[IRColumn, ...],
    prepared: Mapping[int, pl.Expr] | None = None,
) -> pl.Expr:
    import polars as pl

    if prepared is not None and id(expression) in prepared:
        return prepared[id(expression)]
    if isinstance(expression, Column):
        return _column(expression.name, tuple(column.name for column in columns))
    if isinstance(expression, LiteralExpression):
        scalar = literal_scalar(expression)
        return pl.lit(scalar, dtype=_dtype(expression.logical_type))
    if isinstance(expression, Arithmetic):
        operand = expression_type(expression.left, columns).logical_type
        if (
            isinstance(operand, IntegerType)
            or expression.operation == "divide"
            or (expression.operation == "multiply" and isinstance(operand, DecimalType))
        ):
            raise CapabilityError("arithmetic requires its native eager checkpoint")
        scale = operand.scale if isinstance(operand, DecimalType) else 0
        left = _expression(expression.left, columns, prepared).cast(
            pl.Decimal(38, scale), strict=True
        )
        right = _expression(expression.right, columns, prepared).cast(
            pl.Decimal(38, scale), strict=True
        )
        result = {
            "add": lambda: left + right,
            "subtract": lambda: left - right,
            "multiply": lambda: left * right,
        }[expression.operation]()
        return result.cast(_dtype(expression.logical_type), strict=True)
    if isinstance(expression, DecimalRound):
        raise CapabilityError("DecimalRound requires its native eager checkpoint")
    if isinstance(expression, LocalizeTimestamp):
        raise CapabilityError("timestamp localization requires its native eager checkpoint")
    if isinstance(expression, Coalesce):
        return pl.coalesce([_expression(item, columns, prepared) for item in expression.arguments])
    if isinstance(expression, Conditional):
        return (
            pl.when(_expression(expression.predicate, columns, prepared))
            .then(_expression(expression.then, columns, prepared))
            .otherwise(_expression(expression.otherwise, columns, prepared))
        )
    if isinstance(expression, Compare):
        left = _expression(expression.left, columns, prepared)
        right = _expression(expression.right, columns, prepared)
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
        values = [_expression(item, columns, prepared) for item in expression.arguments]
        result = values[0]
        for value in values[1:]:
            result = result & value if expression.operation == "and" else result | value
        return result
    argument = _expression(expression.argument, columns, prepared)
    if isinstance(expression, Not):
        return ~argument
    if isinstance(expression, IsNull):
        return argument.is_null()
    if isinstance(expression, IsNaN):
        return argument.is_nan().fill_null(False)
    raise CapabilityError("unknown Polars expression")


def _check_localizations(
    frame: pl.DataFrame,
    expression: Expression,
    columns: tuple[IRColumn, ...],
    prepared: Mapping[int, pl.Expr],
) -> None:
    """Validate each fallible native localization before relational pruning."""
    import polars as pl

    for item in iter_expressions(expression):
        if not isinstance(item, LocalizeTimestamp):
            continue
        dtype = expression_type(item.argument, columns).logical_type
        if not (isinstance(dtype, TimestampType)):
            raise AssertionError("Internal invariant check failed.")
        before = _expression(item.argument, columns, prepared).cast(pl.Int64)
        after = _expression(item, columns, prepared).cast(pl.Int64)
        # Decimal(38,0) subtraction is native and wide enough for the full
        # difference of two signed int64 values. An int64 subtraction here
        # would wrap too and silently certify the broken timestamp kernel.
        maximum_offset = 86400 * {"s": 1, "ms": 1000, "us": 1000000, "ns": 1000000000}[dtype.unit]
        delta = (after.cast(pl.Decimal(38, 0)) - before.cast(pl.Decimal(38, 0))).abs()
        bad = (before.is_not_null() & after.is_null()) | (
            delta > pl.lit(Decimal(maximum_offset), dtype=pl.Decimal(38, 0))
        )
        if frame.select(bad.fill_null(False).any()).item():
            raise CapabilityError("Polars timestamp localization exceeds faithful int64 range")


def _prepare_arithmetic(
    frame: pl.DataFrame,
    expressions: tuple[Expression, ...],
    columns: tuple[IRColumn, ...],
    context: RunContext,
    zones: Mapping[str, _TimezoneData],
) -> tuple[pl.DataFrame, dict[int, pl.Expr]]:
    import polars as pl

    from .polars_decimal import divide, multiply

    prepared: dict[int, pl.Expr] = {}
    for expression in expressions:
        for item in reversed(tuple(iter_expressions(expression))):
            if id(item) in prepared:
                continue
            if isinstance(item, LocalizeTimestamp):
                declared = expression_type(item.argument, columns).logical_type
                if not isinstance(declared, TimestampType):
                    raise CapabilityError("timestamp localization requires a timestamp argument")
                values, counts, outside, present = _native_localized_frame(
                    frame,
                    _expression(item.argument, columns, prepared),
                    data=zones[item.timezone],
                    unit=declared.unit,
                    ambiguous=item.ambiguous,
                    context=context,
                )
                if ((counts == 0) & present).any():
                    raise pl.exceptions.ComputeError(
                        "Timestamp localization: nonexistent wall time"
                    )
                if item.ambiguous == "reject" and ((counts > 1) & present).any():
                    raise pl.exceptions.ComputeError("Timestamp localization: ambiguous wall time")
                if outside.any():
                    raise CapabilityError(
                        "Polars timestamp localization exceeds faithful int64 range"
                    )
                prefix = f"_equiframe_timestamp_{len(prepared)}_"
                while any(name.startswith(prefix) for name in frame.columns):
                    prefix += "_"
                name = prefix + "result"
                frame = frame.with_columns(values.alias(name))
                prepared[id(item)] = pl.col(name)
                context.check()
                continue
            if isinstance(item, DecimalRound):
                declared = expression_type(item.argument, columns).logical_type
                if not isinstance(declared, DecimalType):
                    raise CapabilityError("DecimalRound requires a Decimal argument")
                prefix = f"_equiframe_round_{len(prepared)}_"
                while any(name.startswith(prefix) for name in frame.columns):
                    prefix += "_"
                # The checked native coefficient quotient rounds before its
                # destination cast. A wide input carry never materializes a
                # 39-digit value in the narrower input Decimal storage.
                frame, result = divide(
                    frame,
                    _expression(item.argument, columns, prepared),
                    pl.lit(Decimal(1), dtype=pl.Decimal(1, 0)),
                    left_scale=declared.scale,
                    right_scale=0,
                    precision=item.logical_type.precision,
                    scale=item.logical_type.scale,
                    rounding=item.rounding,
                    prefix=prefix,
                    context=context,
                )
                prepared[id(item)] = result
                continue
            if not isinstance(item, Arithmetic):
                continue
            left = expression_type(item.left, columns).logical_type
            right = expression_type(item.right, columns).logical_type
            output = item.logical_type
            if isinstance(left, IntegerType) and isinstance(output, IntegerType):
                prefix = f"_equiframe_arithmetic_{len(prepared)}_"
                lower, upper = integer_bounds(output)
                first = _expression(item.left, columns, prepared)
                second = _expression(item.right, columns, prepared)
                context.check()
                if item.operation == "multiply":
                    # UInt64 products can exceed signed Int128 and Decimal128.
                    # Prove a safe coefficient bound before any native product.
                    frame, result = multiply(
                        frame,
                        first,
                        second,
                        precision=len(str(max(abs(lower), abs(upper)))),
                        scale=0,
                        prefix=prefix,
                        context=context,
                    )
                else:
                    first = first.cast(pl.String).cast(pl.Decimal(38, 0))
                    second = second.cast(pl.String).cast(pl.Decimal(38, 0))
                    raw = first + second if item.operation == "add" else first - second
                    frame = frame.with_columns(raw.alias(prefix + "result"))
                    result = pl.col(prefix + "result")
                # Check the exact signed/unsigned destination range before its
                # native integer cast; a cast must never conceal an overflow.
                low = pl.lit(str(lower)).cast(pl.Decimal(38, 0))
                high = pl.lit(str(upper)).cast(pl.Decimal(38, 0))
                if frame.select(((result < low) | (result > high)).any()).item():
                    raise CapabilityError("Polars integer arithmetic exceeds declared range")
                context.check()
                prepared[id(item)] = result.cast(pl.String).cast(_dtype(output), strict=True)
                continue
            if item.operation not in ("divide", "multiply"):
                continue
            if not (
                isinstance(left, DecimalType)
                and isinstance(right, DecimalType)
                and isinstance(output, DecimalType)
            ):
                raise CapabilityError("Decimal arithmetic requires declared Decimal types")
            if item.operation == "divide":
                frame, result = divide(
                    frame,
                    _expression(item.left, columns, prepared),
                    _expression(item.right, columns, prepared),
                    left_scale=left.scale,
                    right_scale=right.scale,
                    precision=output.precision,
                    scale=output.scale,
                    rounding=item.rounding,
                    prefix=f"_equiframe_arithmetic_{len(prepared)}_",
                    context=context,
                )
            else:
                frame, result = multiply(
                    frame,
                    _expression(item.left, columns, prepared),
                    _expression(item.right, columns, prepared),
                    precision=output.precision,
                    scale=output.scale,
                    prefix=f"_equiframe_arithmetic_{len(prepared)}_",
                    context=context,
                )
            prepared[id(item)] = result
    return frame, prepared


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


def _plan_timezone_data(plan: RelationalPlan) -> dict[str, _TimezoneData]:
    zones: dict[str, _TimezoneData] = {}
    for node in plan.nodes:
        roots = (
            tuple(item.expression for item in node.columns)
            if isinstance(node, Project)
            else (node.predicate,)
            if isinstance(node, Filter)
            else ()
        )
        for root in roots:
            for expression in iter_expressions(root):
                if isinstance(expression, LocalizeTimestamp) and expression.timezone not in zones:
                    zones[expression.timezone] = _timezone_data(expression.timezone)
    return zones


class PolarsCompiler:
    engine = "polars"

    def check(self, plan: RelationalPlan, contract: Contract) -> CompilationCheck:
        return compiler_check(self.engine, plan, contract)

    def compile(self, plan: RelationalPlan, contract: Contract) -> CompiledPlan:
        check = self.check(plan, contract)
        if not check.supported:
            raise CapabilityError(check.diagnostics[0].message)
        validated = require_supported(self.engine, plan, contract)
        zones = _plan_timezone_data(plan)
        version = _COMPILER_VERSION
        if zones:
            resource_bytes = json.dumps(
                {key: value.resource_sha256 for key, value in sorted(zones.items())},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            version += "/tzif-" + sha256(resource_bytes).hexdigest()
        identifier, ir_sha, contract_sha = compilation_identity(
            validated,
            self.engine,
            implementation_version=version,
        )

        def transform(tables: Mapping[str, pl.DataFrame], context: RunContext) -> pl.DataFrame:
            import polars as pl

            for key, data in zones.items():
                context.check()
                if _timezone_resource_hash(key) != data.resource_sha256:
                    raise CapabilityError("timezone resource changed after compilation")
            frames: dict[str, pl.DataFrame] = {}
            for node in plan.nodes:
                context.check()
                if isinstance(node, Scan):
                    frame = tables[node.table].clone()
                elif isinstance(node, Project):
                    native, prepared = _prepare_arithmetic(
                        _native_frame(frames[node.source]),
                        tuple(item.expression for item in node.columns),
                        validated.schema(node.source),
                        context,
                        zones,
                    )
                    for item in node.columns:
                        _check_localizations(
                            native, item.expression, validated.schema(node.source), prepared
                        )
                    # Stored source frames have validated order after _coerce.
                    # Evaluate every expression against the same renamed source;
                    # distinct temporary output names preserve simultaneous aliases.
                    frame = native.with_columns(
                        [
                            _expression(
                                item.expression, validated.schema(node.source), prepared
                            ).alias(f"_equiframe_project_{i}")
                            for i, item in enumerate(node.columns)
                        ]
                    )
                    frame = frame.select(
                        [pl.col(f"_equiframe_project_{i}") for i in range(len(node.columns))]
                    )
                    frame = _logical_frame(frame, [item.name for item in node.columns])
                elif isinstance(node, Filter):
                    source = frames[node.source]
                    native, prepared = _prepare_arithmetic(
                        _native_frame(source),
                        (node.predicate,),
                        validated.schema(node.source),
                        context,
                        zones,
                    )
                    _check_localizations(
                        native, node.predicate, validated.schema(node.source), prepared
                    )
                    frame = _logical_frame(
                        native.filter(
                            _expression(node.predicate, validated.schema(node.source), prepared)
                        ).select([pl.col(_native_name(i)) for i in range(len(source.columns))]),
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

        codec = _TimestampCodec.for_contract(contract)
        transformation = (
            _TimestampPolarsTransformation(identifier, transform, version, timestamp_codec=codec)
            if codec.inputs or codec.output
            else PolarsTransformation(identifier, transform, version)
        )
        return CompiledPlan(
            self.engine, transformation, ir_sha, contract_sha, self.check(plan, contract)
        )
