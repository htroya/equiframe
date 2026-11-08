"""Pure IR inference and shared restrictions, without engine imports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, localcontext

from equiframe._decimal import exact_decimal_context
from equiframe.contracts import (
    BooleanType,
    Contract,
    DecimalType,
    FloatType,
    IntegerType,
    LogicalType,
    SignificantOrder,
    StringType,
    TimestampType,
)
from equiframe.errors import CapabilityError
from equiframe.serialization import contract_fingerprint
from equiframe.values import (
    BooleanValue,
    DecimalValue,
    FloatValue,
    IntegerValue,
    NaNValue,
    NullValue,
    StringValue,
)

from .types import (
    Aggregate,
    Arithmetic,
    Boolean,
    Cast,
    Coalesce,
    Column,
    Compare,
    Concatenate,
    Conditional,
    DecimalRound,
    Deduplicate,
    EquiJoin,
    Expression,
    Filter,
    IRColumn,
    IsNaN,
    LiteralExpression,
    LocalizeTimestamp,
    Node,
    NodeSchema,
    Not,
    Project,
    RelationalPlan,
    Scan,
    Window,
)


@dataclass(frozen=True)
class ValidatedIR:
    plan: RelationalPlan
    contract: Contract
    node_schemas: tuple[NodeSchema, ...]
    source_tables: tuple[str, ...]
    output_columns: tuple[IRColumn, ...]

    def schema(self, node_id: str) -> tuple[IRColumn, ...]:
        return next(s.columns for s in self.node_schemas if s.node_id == node_id)


def ir_fingerprint(plan: RelationalPlan) -> str:
    plan = RelationalPlan.model_validate(plan)
    return hashlib.sha256(
        json.dumps(
            plan.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def integer_bounds(dtype: IntegerType) -> tuple[int, int]:
    return (
        (-(2 ** (dtype.bits - 1)), 2 ** (dtype.bits - 1) - 1)
        if dtype.signed
        else (0, 2**dtype.bits - 1)
    )


def decimal_limit(dtype: DecimalType) -> Decimal:
    with localcontext(exact_decimal_context()):
        return Decimal(10) ** (dtype.precision - dtype.scale) - Decimal(10) ** -dtype.scale


def _unique(names: tuple[str, ...]) -> None:
    if len(names) != len(set(names)):
        raise ValueError("IR names/keys must be unique")


def _column(name: str, columns: tuple[IRColumn, ...]) -> IRColumn:
    for column in columns:
        if column.name == name:
            return column
    raise ValueError("unknown IR column: " + name)


def _literal(expression: LiteralExpression) -> IRColumn:
    dtype, value = expression.logical_type, expression.value
    valid = isinstance(value, NullValue)
    if isinstance(dtype, BooleanType):
        valid |= isinstance(value, BooleanValue)
    elif isinstance(dtype, IntegerType) and isinstance(value, IntegerValue):
        lower, upper = integer_bounds(dtype)
        valid = lower <= value.value <= upper
    elif isinstance(dtype, DecimalType) and isinstance(value, DecimalValue):
        with localcontext(exact_decimal_context()):
            exponent = value.value.as_tuple().exponent
            if not (isinstance(exponent, int)):
                raise AssertionError("Internal invariant check failed.")
            valid = (
                exponent >= -dtype.scale
                and not (value.value.is_zero() and value.value.is_signed())
                and value.value.copy_abs() <= decimal_limit(dtype)
                and value.value == value.value.quantize(Decimal(10) ** -dtype.scale)
            )
    elif isinstance(dtype, FloatType):
        valid |= isinstance(value, (FloatValue, NaNValue))
        if dtype.bits == 32 and isinstance(value, FloatValue):
            import struct

            try:
                valid = struct.unpack("f", struct.pack("f", value.value))[0] == value.value
            except OverflowError:
                valid = False
    elif isinstance(dtype, StringType):
        valid |= isinstance(value, StringValue)
    if not valid:
        raise ValueError("literal does not fit its exact declared type")
    return IRColumn(
        name="literal",
        logical_type=dtype,
        nullable=isinstance(value, NullValue),
        unit=expression.unit,
    )


def expression_type(
    expression: Expression, columns: tuple[IRColumn, ...], *, depth: int = 0
) -> IRColumn:
    if depth > 32:
        raise ValueError("IR expression depth exceeds32")
    if isinstance(expression, Column):
        return _column(expression.name, columns)
    if isinstance(expression, LiteralExpression):
        return _literal(expression)
    if isinstance(expression, Arithmetic):
        left = expression_type(expression.left, columns, depth=depth + 1)
        right = expression_type(expression.right, columns, depth=depth + 1)
        dtype = expression.logical_type
        if isinstance(dtype, DecimalType) and dtype.precision > 38:
            raise CapabilityError("native Decimal arithmetic supports precision<=38")
        operand = left.logical_type
        if expression.operation in ("add", "subtract") or isinstance(operand, IntegerType):
            if left.logical_type != right.logical_type:
                raise CapabilityError("arithmetic requires identical operand types")
            if left.unit != right.unit or expression.unit != left.unit:
                raise CapabilityError("arithmetic requires explicit matching units")
        if isinstance(operand, IntegerType) and isinstance(dtype, IntegerType):
            if expression.operation == "divide":
                raise CapabilityError("division requires Decimal operands and output")
        elif (
            isinstance(operand, DecimalType)
            and isinstance(right.logical_type, DecimalType)
            and isinstance(dtype, DecimalType)
        ):
            if expression.operation in ("add", "subtract") and (
                operand.precision > 37
                or dtype.scale != operand.scale
                or dtype.precision < operand.precision + 1
            ):
                raise CapabilityError(
                    "decimal add/subtract requires same scale and one guard digit"
                )
            if expression.operation == "multiply" and (
                dtype.scale != operand.scale + right.logical_type.scale
                or operand.precision > 38
                or right.logical_type.precision > 38
            ):
                raise CapabilityError(
                    "exact Decimal multiply requires operands precision<=38 and summed scales"
                )
        else:
            raise CapabilityError("arithmetic supports integer or exact Decimal operands")
        return IRColumn(
            name="arithmetic",
            logical_type=dtype,
            nullable=left.nullable or right.nullable,
            unit=expression.unit,
        )
    if isinstance(expression, DecimalRound):
        if expression.logical_type.precision > 38:
            raise CapabilityError("native DecimalRound supports precision<=38")
        argument = expression_type(expression.argument, columns, depth=depth + 1)
        if not isinstance(argument.logical_type, DecimalType):
            raise CapabilityError("DecimalRound requires a Decimal argument")
        if expression.logical_type.scale > argument.logical_type.scale:
            raise CapabilityError("DecimalRound output scale cannot exceed input scale")
        return argument.model_copy(
            update={"name": "decimal_round", "logical_type": expression.logical_type}
        )
    if isinstance(expression, LocalizeTimestamp):
        argument = expression_type(expression.argument, columns, depth=depth + 1)
        dtype = argument.logical_type
        if not isinstance(dtype, TimestampType) or dtype.timezone is not None:
            raise CapabilityError(
                "LocalizeTimestamp requires naive timestamps; zone conversion is not localization"
            )
        return argument.model_copy(
            update={
                "name": "localize_timestamp",
                "logical_type": TimestampType(unit=dtype.unit, timezone=expression.timezone),
            }
        )
    if isinstance(expression, Coalesce):
        if any(contains_arithmetic(item) for item in expression.arguments):
            raise CapabilityError(
                "fallible arithmetic inside coalesce requires a preceding checkpoint"
            )
        types = tuple(
            expression_type(item, columns, depth=depth + 1) for item in expression.arguments
        )
        first = types[0]
        if any(c.logical_type != first.logical_type or c.unit != first.unit for c in types):
            raise ValueError("coalesce requires identical types and units")
        return first.model_copy(
            update={"name": "coalesce", "nullable": all(c.nullable for c in types)}
        )
    if isinstance(expression, Conditional):
        if any(
            contains_arithmetic(item)
            for item in (expression.predicate, expression.then, expression.otherwise)
        ):
            raise CapabilityError(
                "fallible arithmetic inside conditional requires a preceding checkpoint"
            )
        predicate = expression_type(expression.predicate, columns, depth=depth + 1)
        left = expression_type(expression.then, columns, depth=depth + 1)
        right = expression_type(expression.otherwise, columns, depth=depth + 1)
        if not isinstance(predicate.logical_type, BooleanType):
            raise ValueError("conditional predicate requires boolean")
        if left.logical_type != right.logical_type or left.unit != right.unit:
            raise ValueError("conditional branches require identical types and units")
        return left.model_copy(
            update={"name": "conditional", "nullable": left.nullable or right.nullable}
        )
    if isinstance(expression, Compare):
        left = expression_type(expression.left, columns, depth=depth + 1)
        right = expression_type(expression.right, columns, depth=depth + 1)
        if left.logical_type != right.logical_type or (
            left.unit is not None and right.unit is not None and left.unit != right.unit
        ):
            raise ValueError("comparison requires identical types and compatible units")
        return IRColumn(
            name="predicate", logical_type=BooleanType(), nullable=left.nullable or right.nullable
        )
    if isinstance(expression, (Boolean, Not)):
        if contains_arithmetic(expression):
            raise CapabilityError(
                "fallible arithmetic inside boolean logic requires a preceding checkpoint"
            )
        arguments = (
            expression.arguments if isinstance(expression, Boolean) else (expression.argument,)
        )
        types = tuple(expression_type(argument, columns, depth=depth + 1) for argument in arguments)
        if any(not isinstance(column.logical_type, BooleanType) for column in types):
            raise ValueError("boolean operators require boolean expressions")
        return IRColumn(
            name="predicate",
            logical_type=BooleanType(),
            nullable=any(column.nullable for column in types),
        )
    argument = expression_type(expression.argument, columns, depth=depth + 1)
    if isinstance(expression, IsNaN) and not isinstance(argument.logical_type, FloatType):
        raise ValueError("is_nan requires float")
    return IRColumn(name="predicate", logical_type=BooleanType(), nullable=False)


def contains_arithmetic(expression: Expression) -> bool:
    if isinstance(expression, (Arithmetic, DecimalRound, LocalizeTimestamp)):
        return True
    if isinstance(expression, (Column, LiteralExpression)):
        return False
    if isinstance(expression, Compare):
        return contains_arithmetic(expression.left) or contains_arithmetic(expression.right)
    if isinstance(expression, (Boolean, Coalesce)):
        return any(contains_arithmetic(item) for item in expression.arguments)
    if isinstance(expression, Conditional):
        return any(
            contains_arithmetic(item)
            for item in (expression.predicate, expression.then, expression.otherwise)
        )
    return contains_arithmetic(expression.argument)


def references(node: Node) -> tuple[str, ...]:
    if isinstance(node, Scan):
        return ()
    if isinstance(node, EquiJoin):
        return node.left, node.right
    if isinstance(node, Concatenate):
        return node.sources
    return (node.source,)


def _widen(source: LogicalType, target: LogicalType) -> bool:
    if source == target:
        return True
    if isinstance(source, IntegerType) and isinstance(target, IntegerType):
        lower, upper = integer_bounds(source)
        next_lower, next_upper = integer_bounds(target)
        return next_lower <= lower and next_upper >= upper
    return (
        isinstance(source, DecimalType)
        and isinstance(target, DecimalType)
        and target.scale == source.scale
        and target.precision >= source.precision
    )


def validate_ir(plan: RelationalPlan, contract: Contract) -> ValidatedIR:
    plan = RelationalPlan.model_validate(plan)
    contract = Contract.model_validate(contract)
    schemas: dict[str, tuple[IRColumn, ...]] = {}
    depths: dict[str, int] = {}
    sources: set[str] = set()
    inputs = {table.name: table.schema_spec.columns for table in contract.inputs}
    for node in plan.nodes:
        if node.node_id in schemas:
            raise ValueError("duplicate IR node")
        prior = references(node)
        if any(ref not in schemas for ref in prior):
            raise ValueError(
                "IR references require preceding nodes; cycles/forward references are rejected"
            )
        depths[node.node_id] = 1 + max((depths[ref] for ref in prior), default=0)
        if depths[node.node_id] > 32:
            raise ValueError("IR node depth exceeds32")
        if isinstance(node, Scan):
            if node.table not in inputs:
                raise ValueError("Scan requires a declared input table")
            sources.add(node.table)
            columns = tuple(
                IRColumn(
                    name=c.name,
                    logical_type=c.logical_type,
                    nullable=c.nullable,
                    unit=c.numeric_policy.unit if c.numeric_policy else None,
                )
                for c in inputs[node.table]
            )
        elif isinstance(node, Project):
            columns = tuple(
                expression_type(item.expression, schemas[node.source]).model_copy(
                    update={"name": item.name}
                )
                for item in node.columns
            )
        elif isinstance(node, Filter):
            columns = schemas[node.source]
            if not isinstance(expression_type(node.predicate, columns).logical_type, BooleanType):
                raise ValueError("Filter requires a boolean predicate")
        elif isinstance(node, Cast):
            _unique(tuple(c.column for c in node.columns))
            replacements = {c.column: c.logical_type for c in node.columns}
            for name, dtype in replacements.items():
                if not _widen(_column(name, schemas[node.source]).logical_type, dtype):
                    raise CapabilityError(
                        "Cast only supports identity or exact integer/decimal widening"
                    )
            columns = tuple(
                c.model_copy(update={"logical_type": replacements.get(c.name, c.logical_type)})
                for c in schemas[node.source]
            )
        elif isinstance(node, EquiJoin):
            _unique(tuple(k.left for k in node.keys))
            _unique(tuple(k.right for k in node.keys))
            for key in node.keys:
                left, right = (
                    _column(key.left, schemas[node.left]),
                    _column(key.right, schemas[node.right]),
                )
                if left.logical_type != right.logical_type or left.unit != right.unit:
                    raise ValueError("join keys must have identical types and units")
                if isinstance(left.logical_type, FloatType):
                    raise CapabilityError("float join keys are not supported")
            columns = tuple(
                c.model_copy(update={"nullable": c.nullable or node.how in ("right", "full")})
                for c in schemas[node.left]
            ) + (
                ()
                if node.how in ("semi", "anti")
                else tuple(
                    c.model_copy(
                        update={
                            "name": node.right_prefix + c.name,
                            "nullable": c.nullable or node.how in ("left", "full"),
                        }
                    )
                    for c in schemas[node.right]
                )
            )
        elif isinstance(node, Concatenate):
            columns = schemas[node.sources[0]]
            if any(schemas[ref] != columns for ref in node.sources[1:]):
                raise ValueError(
                    "concatenate requires identical ordered schemas/types/units/nullability"
                )
        elif isinstance(node, Deduplicate):
            columns = schemas[node.source]
            _unique(node.keys)
            if node.keep == "identical" and set(node.keys) != {c.name for c in columns}:
                raise CapabilityError("deduplicate identical requires every column as key")
            _unique(tuple(key.column for key in node.by))
            for name in (*node.keys, *(key.column for key in node.by)):
                if isinstance(_column(name, columns).logical_type, FloatType):
                    raise CapabilityError("float deduplicate keys/tiebreak remain unsupported")
        elif isinstance(node, Window):
            source_columns = schemas[node.source]
            _unique(node.partition_by)
            _unique(tuple(key.column for key in node.by))
            for name in (*node.partition_by, *(key.column for key in node.by)):
                if isinstance(_column(name, source_columns).logical_type, FloatType):
                    raise CapabilityError("float window partition/order keys are unsupported")
            measures = []
            for window_measure in node.measures:
                if window_measure.operation == "row_number":
                    if window_measure.logical_type != IntegerType(bits=64, signed=True):
                        raise ValueError("row_number requires signed64 output")
                    column = IRColumn(
                        name=window_measure.name,
                        logical_type=window_measure.logical_type,
                        nullable=False,
                        unit=window_measure.unit,
                    )
                else:
                    if window_measure.column is None:
                        raise ValueError("lag/lead require an input column")
                    window_source = _column(window_measure.column, source_columns)
                    if window_measure.logical_type != window_source.logical_type:
                        raise ValueError("lag/lead preserve the exact input type")
                    if (
                        window_measure.unit is not None
                        and window_measure.unit != window_source.unit
                    ):
                        raise ValueError("window units must preserve source units")
                    column = window_source.model_copy(
                        update={"name": window_measure.name, "nullable": True}
                    )
                measures.append(column)
            columns = source_columns + tuple(measures)
        elif isinstance(node, Aggregate):
            _unique(node.group_by)
            groups = tuple(_column(name, schemas[node.source]) for name in node.group_by)
            if any(isinstance(c.logical_type, FloatType) for c in groups):
                raise CapabilityError("float group keys are not supported")
            measures = []
            for measure in node.measures:
                source = _column(measure.column, schemas[node.source]) if measure.column else None
                dtype = measure.logical_type
                count = measure.operation in ("count_rows", "count_valid")
                if count:
                    if dtype != IntegerType(bits=64, signed=True):
                        raise ValueError("counts require signed64 output")
                elif source is None or not isinstance(
                    source.logical_type, (IntegerType, DecimalType)
                ):
                    raise CapabilityError("exact aggregates support integer/decimal only")
                elif measure.operation == "sum":
                    if isinstance(source.logical_type, IntegerType):
                        if (
                            dtype != IntegerType(bits=64, signed=True)
                            or not source.logical_type.signed
                        ):
                            raise CapabilityError(
                                "integer sums require signed input and signed64 output"
                            )
                    elif (
                        not isinstance(dtype, DecimalType)
                        or dtype.scale != source.logical_type.scale
                        or dtype.precision < source.logical_type.precision
                    ):
                        raise ValueError("decimal sum must preserve scale and not narrow precision")
                elif dtype != source.logical_type:
                    raise ValueError("min/max preserve input type")
                if (
                    source
                    and not count
                    and measure.unit is not None
                    and measure.unit != source.unit
                ):
                    raise ValueError("aggregate units must match source units")
                measures.append(
                    IRColumn(
                        name=measure.name,
                        logical_type=dtype,
                        nullable=not count
                        and (measure.operation != "sum" or node.empty_sum == "null"),
                        unit=source.unit if source and not count else measure.unit,
                    )
                )
            columns = groups + tuple(measures)
        else:
            columns = schemas[node.source]
            _unique(tuple(key.column for key in node.by))
            for sort_key in node.by:
                if isinstance(_column(sort_key.column, columns).logical_type, FloatType):
                    raise CapabilityError("float sort keys are not supported")
            if node.ties == "identical_rows" and set(key.column for key in node.by) != {
                c.name for c in columns
            }:
                raise CapabilityError("identical_rows ties require sorting every output column")
        _unique(tuple(column.name for column in columns))
        if len(columns) > 256:
            raise ValueError("IR schema exceeds256 columns")
        if any(
            isinstance(c.logical_type, DecimalType) and c.logical_type.precision > 38
            for c in columns
        ):
            raise CapabilityError("native common IR supports decimal precision<=38")
        schemas[node.node_id] = columns
    if plan.output not in schemas:
        raise ValueError("IR output node does not exist")
    reachable = {plan.output}
    for node in reversed(plan.nodes):
        if node.node_id in reachable:
            reachable.update(references(node))
    if reachable != set(schemas):
        raise ValueError("IR contains unused nodes")
    if sources != set(inputs):
        raise ValueError("IR Scans must cover exactly the contract inputs")
    expected, actual = contract.output.schema_spec.columns, schemas[plan.output]
    order = contract.output.schema_spec.order
    if isinstance(order, SignificantOrder):
        from .types import Sort

        final = next(node for node in plan.nodes if node.node_id == plan.output)
        matching_ties = isinstance(final, Sort) and (
            (final.ties == "reject" and order.ties == "reject")
            or (final.ties == "identical_rows" and order.ties == "preserve")
        )
        if (
            not isinstance(final, Sort)
            or tuple((k.column, k.direction, k.nulls) for k in final.by)
            != tuple((k.column, k.direction, k.nulls) for k in order.by)
            or not matching_ties
        ):
            raise CapabilityError("significant output order requires a matching final Sort")
    if tuple(c.name for c in expected) != tuple(c.name for c in actual):
        raise ValueError("IR output names/order differ from contract")
    for observed, wanted in zip(actual, expected, strict=True):
        if (
            observed.logical_type != wanted.logical_type
            or (observed.nullable and not wanted.nullable)
            or observed.unit != (wanted.numeric_policy.unit if wanted.numeric_policy else None)
        ):
            raise ValueError("IR output type/nullability/unit differs from contract")
    return ValidatedIR(
        plan,
        contract,
        tuple(NodeSchema(node_id=n.node_id, columns=schemas[n.node_id]) for n in plan.nodes),
        tuple(sorted(sources)),
        actual,
    )


def compilation_identity(
    validated: ValidatedIR, engine: str, *, implementation_version: str | None = None
) -> tuple[str, str, str]:
    ir_sha256 = ir_fingerprint(validated.plan)
    contract_sha256 = contract_fingerprint(validated.contract)
    identity = implementation_version or f"migration-native-ir1.0:{engine}"
    fingerprint = hashlib.sha256(f"{identity}:{ir_sha256}:{contract_sha256}".encode()).hexdigest()
    return "migration_" + fingerprint, ir_sha256, contract_sha256


def literal_scalar(expression: LiteralExpression) -> bool | int | float | str | Decimal | None:
    value = expression.value
    if isinstance(value, NullValue):
        return None
    if isinstance(value, NaNValue):
        return float("nan")
    if isinstance(value, (BooleanValue, IntegerValue, FloatValue, DecimalValue, StringValue)):
        return value.value
    raise CapabilityError("unsupported IR literal")


def iter_expressions(expression: Expression) -> Iterator[Expression]:
    """Walk a closed expression without importing any optional runtime."""
    yield expression
    if isinstance(expression, (Column, LiteralExpression)):
        return
    children: tuple[Expression, ...]
    if isinstance(expression, (Arithmetic, Compare)):
        children = (expression.left, expression.right)
    elif isinstance(expression, (Boolean, Coalesce)):
        children = expression.arguments
    elif isinstance(expression, Conditional):
        children = (expression.predicate, expression.then, expression.otherwise)
    else:
        children = (expression.argument,)
    for child in children:
        yield from iter_expressions(child)
