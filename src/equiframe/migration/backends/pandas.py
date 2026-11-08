"""Pandas compiler: callbacks operate on native DataFrames, never another engine."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, Inexact, localcontext
from typing import TYPE_CHECKING, Any, Literal, cast

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
from equiframe.registry import PandasTransformation

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
    literal_scalar,
)

if TYPE_CHECKING:
    import pandas as pd

    from equiframe.execution import RunContext

_COMPILER_VERSION = "migration-native-ir1.0/pandas/product-semantics-v4"


def _dtype(dtype: LogicalType) -> Any:
    import pandas as pd
    import pyarrow as pa

    if isinstance(dtype, IntegerType):
        arrow = getattr(pa, ("int" if dtype.signed else "uint") + str(dtype.bits))()
    elif isinstance(dtype, DecimalType):
        arrow = pa.decimal128(dtype.precision, dtype.scale)
    elif isinstance(dtype, FloatType):
        arrow = pa.float32() if dtype.bits == 32 else pa.float64()
    elif isinstance(dtype, BooleanType):
        arrow = pa.bool_()
    elif isinstance(dtype, StringType):
        arrow = pa.string()
    elif isinstance(dtype, DateType):
        arrow = pa.date32()
    elif isinstance(dtype, TimestampType):
        arrow = pa.timestamp(dtype.unit, tz=dtype.timezone)
    else:
        raise CapabilityError("unsupported Pandas IR type")
    return pd.ArrowDtype(arrow)


def _expression(expression: Expression, frame: pd.DataFrame, columns: Any) -> pd.Series[Any]:
    import pandas as pd

    if isinstance(expression, Column):
        return frame[expression.name]
    if isinstance(expression, LiteralExpression):
        import pyarrow as pa

        scalar = literal_scalar(expression)
        dtype = _dtype(expression.logical_type)
        literal_series: pd.Series[Any] = pd.Series(
            # pandas 2.2 stubs omit this documented runtime array class.
            cast(Any, pd.arrays).ArrowExtensionArray(
                pa.array([scalar] * len(frame), type=dtype.pyarrow_dtype, from_pandas=False)
            ),
            index=frame.index,
        )
        return literal_series
    if isinstance(expression, Arithmetic):
        left = _expression(expression.left, frame, columns).astype(object)
        right = _expression(expression.right, frame, columns).astype(object)
        operation = {"add": "add", "subtract": "sub", "multiply": "mul", "divide": "truediv"}[
            expression.operation
        ]
        with localcontext(exact_decimal_context()) as decimal_context:
            if expression.operation == "divide" and expression.rounding == "exact":
                decimal_context.traps[Inexact] = True
            result = cast("pd.Series[Any]", getattr(left, operation)(right))
            if expression.operation == "divide":
                if not (isinstance(expression.logical_type, DecimalType)):
                    raise AssertionError("Internal invariant check failed.")
                quantum = Decimal(1).scaleb(-expression.logical_type.scale)
                rounding = (
                    ROUND_HALF_UP
                    if expression.rounding == "half_away_from_zero"
                    else ROUND_HALF_EVEN
                )
                result = result.map(
                    lambda value: (
                        value if pd.isna(value) else value.quantize(quantum, rounding=rounding)
                    )
                )
        # Every expression has its own declared range. Checking only the final
        # projected column lets a later subtraction or predicate conceal overflow.
        return _checked_series(result, expression_type(expression, columns))
    if isinstance(expression, DecimalRound):
        argument = _expression(expression.argument, frame, columns).astype(object)
        with localcontext(exact_decimal_context()):
            quantum = Decimal(1).scaleb(-expression.logical_type.scale)
            rounding = (
                ROUND_HALF_UP if expression.rounding == "half_away_from_zero" else ROUND_HALF_EVEN
            )
            result = argument.map(
                lambda value: (
                    value if pd.isna(value) else value.quantize(quantum, rounding=rounding)
                )
            )
        return _checked_series(result, expression_type(expression, columns))
    if isinstance(expression, LocalizeTimestamp):
        from equiframe._timezones import timezone

        dtype = expression_type(expression.argument, columns).logical_type
        if not (isinstance(dtype, TimestampType)):
            raise AssertionError("Internal invariant check failed.")
        argument = _expression(expression.argument, frame, columns)
        before = argument.astype(_dtype(IntegerType(bits=64, signed=True)))
        if before.eq(-(2**63)).fillna(False).any():
            raise CapabilityError("Pandas LocalizeTimestamp cannot preserve int64-min NaT sentinel")
        native_dtype: Any = f"datetime64[{dtype.unit}]"
        naive_values = argument.astype(native_dtype)
        zone = timezone(expression.timezone)
        if expression.ambiguous == "reject":
            localized = naive_values.dt.tz_localize(zone, ambiguous="raise", nonexistent="raise")
        else:
            import numpy as np

            first = naive_values.dt.tz_localize(
                zone, ambiguous=np.ones(len(naive_values), dtype=bool), nonexistent="raise"
            )
            second = naive_values.dt.tz_localize(
                zone, ambiguous=np.zeros(len(naive_values), dtype=bool), nonexistent="raise"
            )
            choose_first = (
                first.le(second) if expression.ambiguous == "earlier" else first.ge(second)
            )
            localized = first.where(choose_first, second)
        localized = _checked_series(localized, expression_type(expression, columns))
        after = localized.astype(_dtype(IntegerType(bits=64, signed=True)))
        # A local-to-UTC offset is less than one day. Compare in unbounded
        # Python integers, because subtracting native int64 ticks can itself
        # wrap and hide a timezone kernel overflow across centuries.
        maximum_offset = 86400 * {"s": 1, "ms": 1000, "us": 1000000, "ns": 1000000000}[dtype.unit]
        delta = (after.astype(object) - before.astype(object)).abs()
        if (before.notna() & after.isna()).any() or delta.gt(maximum_offset).fillna(False).any():
            raise CapabilityError("Pandas timestamp localization exceeds faithful int64 range")
        return localized
    if isinstance(expression, Coalesce):
        result = _expression(expression.arguments[0], frame, columns)
        for item in expression.arguments[1:]:
            replacement = _expression(item, frame, columns)
            result = result.where(result.notna(), replacement)
        return result
    if isinstance(expression, Conditional):
        predicate = _expression(expression.predicate, frame, columns).fillna(False)
        left = _expression(expression.then, frame, columns)
        right = _expression(expression.otherwise, frame, columns)
        return left.where(predicate, right)
    if isinstance(expression, Compare):
        left = _expression(expression.left, frame, columns)
        right = _expression(expression.right, frame, columns)
        result = getattr(left, expression.operation)(right)
        if isinstance(expression_type(expression.left, columns).logical_type, FloatType):
            # NaN is an unordered value; NULL remains SQL unknown.
            nan = (left != left).fillna(False) | (right != right).fillna(False)
            result = result.mask(nan, expression.operation == "ne")
        return cast(
            "pd.Series[Any]",
            result.mask(left.isna() | right.isna(), pd.NA).astype(_dtype(BooleanType())),
        )
    if isinstance(expression, Boolean):
        values = [
            _expression(item, frame, columns).astype(_dtype(BooleanType()))
            for item in expression.arguments
        ]
        result = values[0]
        for value in values[1:]:
            result = result & value if expression.operation == "and" else result | value
        return cast("pd.Series[Any]", result)
    argument = _expression(expression.argument, frame, columns)
    if isinstance(expression, Not):
        inverted: pd.Series[Any] = ~argument.astype(_dtype(BooleanType()))
        return inverted
    if isinstance(expression, IsNull):
        null_flags: pd.Series[Any] = argument.isna().astype(_dtype(BooleanType()))
        return null_flags
    if isinstance(expression, IsNaN):
        nan_flags: pd.Series[Any] = (
            (argument != argument).fillna(False).astype(_dtype(BooleanType()))
        )
        return nan_flags
    raise CapabilityError("unknown Pandas expression")


def _checked_series(series: pd.Series[Any], column: IRColumn) -> pd.Series[Any]:
    import pandas as pd

    dtype = column.logical_type
    if isinstance(dtype, (IntegerType, DecimalType)) and len(series):
        values = series.dropna()
        if len(values):
            lower, upper = (
                integer_bounds(dtype)
                if isinstance(dtype, IntegerType)
                else (decimal_limit(dtype).copy_negate(), decimal_limit(dtype))
            )
            if values.min() < lower or values.max() > upper:
                raise CapabilityError("IR output exceeds declared numeric range: " + column.name)
    if not column.nullable and series.isna().any():
        raise CapabilityError("IR output contains forbidden NULL: " + column.name)
    if series.dtype != _dtype(dtype):
        converted = pd.Series(series, dtype=_dtype(dtype), index=series.index, copy=True)
        if not isinstance(converted, pd.Series):
            raise CapabilityError("Pandas numeric conversion did not return a Series")
        return converted
    return series


def _coerce(frame: pd.DataFrame, validated: ValidatedIR, node_id: str) -> pd.DataFrame:
    for column in validated.schema(node_id):
        original = frame[column.name]
        checked = _checked_series(original, column)
        if checked is not original:
            frame[column.name] = checked
    return frame.reset_index(drop=True)


def _aggregate(frame: pd.DataFrame, node: Aggregate, validated: ValidatedIR) -> pd.DataFrame:
    import pandas as pd

    result = []
    group = (
        frame.groupby(list(node.group_by), dropna=node.null_groups == "drop", sort=False)
        if node.group_by
        else None
    )
    for measure in node.measures:
        value: pd.Series[Any]
        if measure.operation == "count_rows":
            value = group.size() if group is not None else pd.Series([len(frame)])
        else:
            if not (measure.column is not None):
                raise AssertionError("Internal invariant check failed.")
            series = frame[measure.column]
            if measure.operation == "count_valid":
                value = (
                    group[measure.column].count()
                    if group is not None
                    else pd.Series([series.count()])
                )
            else:
                # Object integers/Decimal avoid fixed-width Arrow groupby wraparound.
                native = series.astype(object)
                grouping = (
                    native.groupby(
                        [frame[key] for key in node.group_by],
                        dropna=node.null_groups == "drop",
                        sort=False,
                    )
                    if group is not None
                    else None
                )
                with localcontext(exact_decimal_context()):
                    if measure.operation == "sum":
                        value = (
                            grouping.sum(min_count=1)
                            if grouping is not None
                            else pd.Series([native.sum(min_count=1)], dtype=object)
                        )
                        count = (
                            group[measure.column].count()
                            if group is not None
                            else pd.Series([series.count()])
                        )
                        zero: int | Decimal = 0
                        if isinstance(measure.logical_type, DecimalType):
                            zero = Decimal(0).quantize(Decimal(10) ** -measure.logical_type.scale)
                        replacement = pd.Series(
                            [None if node.empty_sum == "null" else zero] * len(value),
                            index=value.index,
                            dtype=object,
                        )
                        value = value.mask(count == 0, replacement)
                    else:
                        value = (
                            getattr(grouping, measure.operation)()
                            if grouping is not None
                            else pd.Series([getattr(series, measure.operation)()], dtype=object)
                        )
        result.append(value.rename(measure.name))
    frame = pd.concat(result, axis=1)
    if node.group_by:
        frame = frame.reset_index()
    return _coerce(frame, validated, node.node_id)


class PandasCompiler:
    engine = "pandas"

    def check(self, plan: RelationalPlan, contract: Contract) -> CompilationCheck:
        return compiler_check(self.engine, plan, contract)

    def compile(self, plan: RelationalPlan, contract: Contract) -> CompiledPlan:
        validated = require_supported(self.engine, plan, contract)
        identifier, ir_sha, contract_sha = compilation_identity(
            validated, self.engine, implementation_version=_COMPILER_VERSION
        )

        def transform(tables: Mapping[str, pd.DataFrame], context: RunContext) -> pd.DataFrame:
            import pandas as pd

            frames: dict[str, pd.DataFrame] = {}
            for node in plan.nodes:
                context.check()
                if isinstance(node, Scan):
                    frame = tables[node.table].copy(deep=True).reset_index(drop=True)
                elif isinstance(node, Project):
                    source = frames[node.source]
                    frame = pd.DataFrame(
                        {
                            item.name: _expression(
                                item.expression, source, validated.schema(node.source)
                            )
                            for item in node.columns
                        },
                        index=source.index,
                    )
                elif isinstance(node, Filter):
                    source = frames[node.source]
                    frame = source.loc[
                        _expression(node.predicate, source, validated.schema(node.source)).fillna(
                            False
                        )
                    ].copy()
                elif isinstance(node, Cast):
                    frame = frames[node.source].copy(deep=True)
                elif isinstance(node, EquiJoin):
                    left = frames[node.left]
                    right = frames[node.right]
                    for side, names, unique in (
                        (
                            left,
                            [key.left for key in node.keys],
                            node.cardinality in ("one_to_one", "one_to_many"),
                        ),
                        (
                            right,
                            [key.right for key in node.keys],
                            node.cardinality in ("one_to_one", "many_to_one"),
                        ),
                    ):
                        matchable = (
                            side
                            if node.null_keys == "equal"
                            else side.loc[side[names].notna().all(axis=1)]
                        )
                        if unique and matchable.duplicated(subset=names).any():
                            raise CapabilityError(
                                "Join violates declared cardinality: " + node.cardinality
                            )
                    if node.how in ("semi", "anti"):
                        keys_left = [key.left for key in node.keys]
                        keys_right = [key.right for key in node.keys]
                        keys = right[keys_right].drop_duplicates()
                        if node.null_keys == "never":
                            keys = keys.loc[keys.notna().all(axis=1)]
                        keys = keys.rename(columns=dict(zip(keys_right, keys_left, strict=True)))
                        matches = left[keys_left].merge(
                            keys, how="left", on=keys_left, indicator=True, sort=False
                        )
                        mask = matches["_merge"].eq("both").to_numpy()
                        frame = left.loc[mask if node.how == "semi" else ~mask].copy()
                        frames[node.node_id] = _coerce(frame, validated, node.node_id)
                        continue
                    incomplete_left = left.iloc[:0]
                    incomplete_right = right.iloc[:0]
                    if node.null_keys == "never":
                        left_complete = left[[key.left for key in node.keys]].notna().all(axis=1)
                        right_complete = right[[key.right for key in node.keys]].notna().all(axis=1)
                        incomplete_left, incomplete_right = (
                            left.loc[~left_complete],
                            right.loc[~right_complete],
                        )
                        left, right = left.loc[left_complete], right.loc[right_complete]
                    right = right.rename(
                        columns={name: node.right_prefix + name for name in right.columns}
                    )
                    if left.empty and right.empty:
                        # Captured empty Arrow columns can have zero chunks.
                        # pandas full-join factorization cannot infer their type;
                        # a native typed empty concatenation is the exact join.
                        frame = pd.concat([left, right], axis=1)
                    else:
                        frame = left.merge(
                            right,
                            how=cast(
                                'Literal["inner", "left", "right", "outer"]',
                                "outer" if node.how == "full" else node.how,
                            ),
                            left_on=[key.left for key in node.keys],
                            right_on=[node.right_prefix + key.right for key in node.keys],
                            sort=False,
                        )
                    extras = []
                    if node.how in ("left", "full") and len(incomplete_left):
                        extras.append(incomplete_left)
                    if node.how in ("right", "full") and len(incomplete_right):
                        extras.append(
                            incomplete_right.rename(
                                columns={
                                    name: node.right_prefix + name
                                    for name in incomplete_right.columns
                                }
                            )
                        )
                    for extra in extras:
                        extra = extra.copy()
                        for column in validated.schema(node.node_id):
                            if column.name not in extra:
                                extra[column.name] = pd.Series(
                                    pd.NA, index=extra.index, dtype=_dtype(column.logical_type)
                                )
                        frame = pd.concat([frame, extra[frame.columns]], ignore_index=True)
                elif isinstance(node, Window):
                    frame = frames[node.source].copy(deep=True)
                    tie_keys = list(
                        dict.fromkeys((*node.partition_by, *(key.column for key in node.by)))
                    )
                    if frame.duplicated(subset=tie_keys).any():
                        raise CapabilityError("Window encountered forbidden order ties")
                    for key in reversed(node.by):
                        frame = frame.sort_values(
                            key.column,
                            ascending=key.direction == "ascending",
                            na_position=key.nulls,
                            kind="stable",
                        )
                    groups = (
                        frame.groupby(list(node.partition_by), dropna=False, sort=False)
                        if node.partition_by
                        else None
                    )
                    for window_measure in node.measures:
                        if window_measure.operation == "row_number":
                            value = (
                                groups.cumcount() + 1
                                if groups is not None
                                else pd.Series(range(1, len(frame) + 1), index=frame.index)
                            )
                        else:
                            if window_measure.column is None:
                                raise CapabilityError("lag/lead require an input column")
                            offset = (
                                window_measure.offset
                                if window_measure.operation == "lag"
                                else -window_measure.offset
                            )
                            value = (
                                groups[window_measure.column].shift(offset)
                                if groups is not None
                                else frame[window_measure.column].shift(offset)
                            )
                        frame[window_measure.name] = value
                elif isinstance(node, Aggregate):
                    frame = _aggregate(frames[node.source], node, validated)
                elif isinstance(node, Concatenate):
                    frame = pd.concat([frames[ref] for ref in node.sources], ignore_index=True)
                elif isinstance(node, Deduplicate):
                    frame = frames[node.source]
                    if node.keep == "first":
                        tie_keys = list(
                            dict.fromkeys((*node.keys, *(key.column for key in node.by)))
                        )
                        if frame.duplicated(subset=tie_keys).any():
                            raise CapabilityError("Deduplicate encountered forbidden tiebreak ties")
                        for key in reversed(node.by):
                            frame = frame.sort_values(
                                key.column,
                                ascending=key.direction == "ascending",
                                na_position=key.nulls,
                                kind="stable",
                            )
                    frame = frame.drop_duplicates(subset=list(node.keys), keep="first").copy()
                else:
                    frame = frames[node.source].copy(deep=True)
                    if (
                        node.ties == "reject"
                        and frame.duplicated(subset=[key.column for key in node.by]).any()
                    ):
                        raise CapabilityError("Sort encountered forbidden ties")
                    for key in reversed(node.by):
                        frame = frame.sort_values(
                            key.column,
                            ascending=key.direction == "ascending",
                            na_position=key.nulls,
                            kind="stable",
                        )
                frames[node.node_id] = _coerce(frame, validated, node.node_id)
            return frames[plan.output]

        transformation = PandasTransformation(identifier, transform, _COMPILER_VERSION)
        return CompiledPlan(
            self.engine, transformation, ir_sha, contract_sha, self.check(plan, contract)
        )
