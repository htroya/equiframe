"""Pandas compiler: callbacks operate on native DataFrames, never another engine."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any, cast

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
    Deduplicate,
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
    import pandas as pd

    from equiframe.execution import RunContext


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
        return pd.Series(
            pd.arrays.ArrowExtensionArray(
                pa.array([scalar] * len(frame), type=dtype.pyarrow_dtype, from_pandas=False)
            ),
            index=frame.index,
        )
    if isinstance(expression, Arithmetic):
        left = _expression(expression.left, frame, columns).astype(object)
        right = _expression(expression.right, frame, columns).astype(object)
        operation = {"add": "add", "subtract": "sub", "multiply": "mul"}[expression.operation]
        with localcontext() as context:
            context.prec = 100
            return cast("pd.Series[Any]", getattr(left, operation)(right))
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
        return ~argument.astype(_dtype(BooleanType()))
    if isinstance(expression, IsNull):
        return argument.isna().astype(_dtype(BooleanType()))
    if isinstance(expression, IsNaN):
        return (argument != argument).fillna(False).astype(_dtype(BooleanType()))
    raise CapabilityError("unknown Pandas expression")


def _coerce(frame: pd.DataFrame, validated: ValidatedIR, node_id: str) -> pd.DataFrame:
    import pandas as pd

    for column in validated.schema(node_id):
        series = frame[column.name]
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
                    raise CapabilityError(
                        "IR output exceeds declared numeric range: " + column.name
                    )
        if not column.nullable and series.isna().any():
            raise CapabilityError("IR output contains forbidden NULL: " + column.name)
        if series.dtype != _dtype(dtype):
            frame[column.name] = pd.Series(pd.array(series, dtype=_dtype(dtype)), index=frame.index)
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
            assert measure.column is not None
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
                with localcontext() as context:
                    context.prec = 100
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
                        value = value.mask(count == 0, None if node.empty_sum == "null" else zero)
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
        identifier, ir_sha, contract_sha = compilation_identity(validated, self.engine)

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
                    if node.null_keys == "never":
                        right = right.loc[
                            right[[key.right for key in node.keys]].notna().all(axis=1)
                        ]
                        if node.how == "inner":
                            left = left.loc[
                                left[[key.left for key in node.keys]].notna().all(axis=1)
                            ]
                    right = right.rename(
                        columns={name: node.right_prefix + name for name in right.columns}
                    )
                    frame = left.merge(
                        right,
                        how="inner" if node.how == "inner" else "left",
                        left_on=[key.left for key in node.keys],
                        right_on=[node.right_prefix + key.right for key in node.keys],
                        sort=False,
                    )
                elif isinstance(node, Aggregate):
                    frame = _aggregate(frames[node.source], node, validated)
                elif isinstance(node, Concatenate):
                    frame = pd.concat([frames[ref] for ref in node.sources], ignore_index=True)
                elif isinstance(node, Deduplicate):
                    frame = frames[node.source].drop_duplicates(subset=list(node.keys)).copy()
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

        transformation = PandasTransformation(
            identifier, transform, "migration-native-ir1.0/pandas"
        )
        return CompiledPlan(
            self.engine, transformation, ir_sha, contract_sha, self.check(plan, contract)
        )
