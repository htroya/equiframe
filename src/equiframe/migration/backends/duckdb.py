"""DuckDB compiler: native SELECT checkpoints preserve eager IR failures."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

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
from equiframe.values import (
    BooleanValue,
    DecimalValue,
    FloatValue,
    IntegerValue,
    NaNValue,
    NullValue,
    StringValue,
)

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
    Sort,
    Window,
)
from ..validation import (
    ValidatedIR,
    compilation_identity,
    expression_type,
    iter_expressions,
    references,
)
from ._timestamp_transport import _TimestampCodec, _TimestampDuckDBTransformation

_COMPILER_VERSION = "migration-native-ir1.0/duckdb/product-semantics-v9"


@dataclass(frozen=True)
class _DuckDBCheckpoint:
    name: str
    sql: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class _DuckDBProgram(_TimestampDuckDBTransformation):
    checkpoints: tuple[_DuckDBCheckpoint, ...] = ()
    final_sql: str = ""
    output_relation: str = ""


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _dtype(dtype: LogicalType) -> str:
    if isinstance(dtype, IntegerType):
        return ("" if dtype.signed else "U") + {
            8: "TINYINT",
            16: "SMALLINT",
            32: "INTEGER",
            64: "BIGINT",
        }[dtype.bits]
    if isinstance(dtype, DecimalType):
        return f"DECIMAL({dtype.precision},{dtype.scale})"
    if isinstance(dtype, FloatType):
        return "FLOAT" if dtype.bits == 32 else "DOUBLE"
    if isinstance(dtype, BooleanType):
        return "BOOLEAN"
    if isinstance(dtype, StringType):
        return "VARCHAR"
    if isinstance(dtype, DateType):
        return "DATE"
    if isinstance(dtype, TimestampType):
        return "BIGINT"
    raise CapabilityError("unsupported DuckDB IR type")


def _literal(expression: LiteralExpression) -> str:
    value = expression.value
    if isinstance(value, NullValue):
        text = "NULL"
    elif isinstance(value, NaNValue):
        text = "'NaN'"
    elif isinstance(value, BooleanValue):
        text = "TRUE" if value.value else "FALSE"
    elif isinstance(value, (IntegerValue, FloatValue)):
        text = repr(value.value)
    elif isinstance(value, DecimalValue):
        text = "'" + str(value.value) + "'"
    elif isinstance(value, StringValue):
        # An embedded NUL in SQL source terminates parsing. Construct the same
        # VARCHAR value without putting that byte into the SQL source itself.
        text = " || chr(0) || ".join(
            "'" + part.replace("'", "''") + "'" for part in value.value.split("\x00")
        )
    else:
        raise CapabilityError("unsupported DuckDB literal")
    return f"CAST({text} AS {_dtype(expression.logical_type)})"


def _expression(
    expression: Expression,
    columns: tuple[IRColumn, ...],
    prepared: Mapping[int, str] | None = None,
) -> str:
    if prepared is not None and id(expression) in prepared:
        return quote(prepared[id(expression)])
    if isinstance(expression, Column):
        return quote(expression.name)
    if isinstance(expression, LiteralExpression):
        return _literal(expression)
    if isinstance(expression, Arithmetic):
        left = _expression(expression.left, columns, prepared)
        right = _expression(expression.right, columns, prepared)
        operand = expression_type(expression.left, columns).logical_type
        if expression.operation == "divide":
            from .duckdb_decimal import divide

            right_type = expression_type(expression.right, columns).logical_type
            output = expression.logical_type
            if not (
                isinstance(operand, DecimalType)
                and isinstance(right_type, DecimalType)
                and isinstance(output, DecimalType)
            ):
                raise CapabilityError("Decimal division requires declared Decimal types")
            return divide(
                left,
                right,
                left_scale=operand.scale,
                right_scale=right_type.scale,
                precision=output.precision,
                scale=output.scale,
                rounding=expression.rounding,
                columns=tuple(column.name for column in columns),
            )
        if expression.operation == "multiply" and isinstance(operand, DecimalType):
            right_type = expression_type(expression.right, columns).logical_type
            if not (isinstance(right_type, DecimalType)):
                raise AssertionError("Internal invariant check failed.")
            # Widen before multiplication: DuckDB otherwise uses a DECIMAL(18)
            # intermediate for <=18-digit operands even when the outer cast is
            # DECIMAL(38). Preserve each original scale during promotion.
            return (
                f"CAST((CAST({left} AS DECIMAL(38,{operand.scale})) * "
                f"CAST({right} AS DECIMAL(38,{right_type.scale}))) "
                f"AS {_dtype(expression.logical_type)})"
            )
        intermediate = (
            "HUGEINT" if isinstance(operand, IntegerType) else _dtype(expression.logical_type)
        )
        operator = {"add": "+", "subtract": "-", "multiply": "*"}[expression.operation]
        return (
            f"CAST((CAST({left} AS {intermediate}) {operator} "
            f"CAST({right} AS {intermediate})) AS {_dtype(expression.logical_type)})"
        )
    if isinstance(expression, DecimalRound):
        if expression.rounding == "half_even":
            from .duckdb_decimal import divide

            operand = expression_type(expression.argument, columns).logical_type
            if not isinstance(operand, DecimalType):
                raise CapabilityError("Decimal rounding requires a declared Decimal argument")
            # Rounding x is exact coefficient division by one at the requested
            # scale. Native round_even promotes DECIMAL to DOUBLE in DuckDB;
            # the existing HUGEINT kernel preserves all 38 coefficient digits.
            return divide(
                _expression(expression.argument, columns, prepared),
                "CAST(1 AS DECIMAL(1,0))",
                left_scale=operand.scale,
                right_scale=0,
                precision=expression.logical_type.precision,
                scale=expression.logical_type.scale,
                rounding="half_even",
                columns=tuple(column.name for column in columns),
            )
        return (
            f"CAST(round({_expression(expression.argument, columns, prepared)}, "
            f"{expression.logical_type.scale}) AS {_dtype(expression.logical_type)})"
        )
    if isinstance(expression, LocalizeTimestamp):
        from .duckdb_time import localize

        dtype = expression_type(expression.argument, columns).logical_type
        if not isinstance(dtype, TimestampType):
            raise CapabilityError("timestamp localization requires a declared timestamp argument")
        return localize(
            _expression(expression.argument, columns, prepared),
            unit=dtype.unit,
            timezone=expression.timezone,
            ambiguous=expression.ambiguous,
            columns=tuple(column.name for column in columns),
        )
    if isinstance(expression, Coalesce):
        return (
            "coalesce("
            + ", ".join(_expression(item, columns, prepared) for item in expression.arguments)
            + ")"
        )
    if isinstance(expression, Conditional):
        return (
            f"CASE WHEN {_expression(expression.predicate, columns, prepared)} "
            f"THEN {_expression(expression.then, columns, prepared)} "
            f"ELSE {_expression(expression.otherwise, columns, prepared)} END"
        )
    if isinstance(expression, Compare):
        left, right = (
            _expression(expression.left, columns, prepared),
            _expression(expression.right, columns, prepared),
        )
        operator = {"eq": "=", "ne": "<>", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}[
            expression.operation
        ]
        result = f"({left} {operator} {right})"
        if isinstance(expression_type(expression.left, columns).logical_type, FloatType):
            nan_value = "TRUE" if expression.operation == "ne" else "FALSE"
            result = (
                f"CASE WHEN {left} IS NULL OR {right} IS NULL THEN NULL "
                f"WHEN isnan({left}) OR isnan({right}) THEN {nan_value} ELSE {result} END"
            )
        return "(" + result + ")"
    if isinstance(expression, Boolean):
        operator = " AND " if expression.operation == "and" else " OR "
        return (
            "("
            + operator.join(
                _expression(argument, columns, prepared) for argument in expression.arguments
            )
            + ")"
        )
    argument = _expression(expression.argument, columns, prepared)
    if isinstance(expression, Not):
        return f"(NOT {argument})"
    if isinstance(expression, IsNull):
        return f"({argument} IS NULL)"
    if isinstance(expression, IsNaN):
        return f"coalesce(isnan({argument}), FALSE)"
    raise CapabilityError("unknown DuckDB expression")


def _projection(validated: ValidatedIR, node_id: str) -> str:
    expressions = []
    for column in validated.schema(node_id):
        value = quote(column.name)
        if not column.nullable:
            value = (
                f"CASE WHEN {value} IS NULL THEN error('IR contains forbidden NULL') "
                f"ELSE {value} END"
            )
        expressions.append(
            f"CAST({value} AS {_dtype(column.logical_type)}) AS {quote(column.name)}"
        )
    return ", ".join(expressions)


class DuckDBCompiler:
    engine = "duckdb"

    def check(self, plan: RelationalPlan, contract: Contract) -> CompilationCheck:
        check = compiler_check(self.engine, plan, contract)
        if check.supported:
            validated = require_supported(self.engine, plan, contract)
            if any(
                re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", table) is None
                for table in validated.source_tables
            ) or len({table.casefold() for table in validated.source_tables}) != len(
                validated.source_tables
            ):
                return CompilationCheck(
                    engine=self.engine,
                    supported=False,
                    diagnostics=(
                        CompilationDiagnostic(
                            code="input_identifier",
                            message=(
                                "DuckDB inputs require unique case-insensitive ASCII identifiers"
                            ),
                        ),
                    ),
                )
            for schema in validated.node_schemas:
                if any("\x00" in column.name for column in schema.columns):
                    return CompilationCheck(
                        engine=self.engine,
                        supported=False,
                        diagnostics=(
                            CompilationDiagnostic(
                                code="nul_identifier",
                                message="DuckDB SQL identifiers cannot contain a NUL character",
                                node_id=schema.node_id,
                            ),
                        ),
                    )
                names = [column.name.casefold() for column in schema.columns]
                if len(names) != len(set(names)):
                    return CompilationCheck(
                        engine=self.engine,
                        supported=False,
                        diagnostics=(
                            CompilationDiagnostic(
                                code="case_collision",
                                message="DuckDB identifiers are case insensitive",
                                node_id=schema.node_id,
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
            validated, self.engine, implementation_version=_COMPILER_VERSION
        )
        prefix = "__eq_" + ir_sha[:16] + "_"
        occupied = {table.name.casefold() for table in contract.inputs}
        while any((prefix + str(index)).casefold() in occupied for index in range(len(plan.nodes))):
            prefix += "_"
        raw_names = {
            node.node_id: prefix + str(position) for position, node in enumerate(plan.nodes)
        }
        names = {node_id: quote(name) for node_id, name in raw_names.items()}
        occupied.update(name.casefold() for name in raw_names.values())
        occupied.update(
            c.name.casefold() for schema in validated.node_schemas for c in schema.columns
        )
        checkpoints: list[_DuckDBCheckpoint] = []

        def fresh(kind: str) -> str:
            name = prefix + kind + "_" + str(len(checkpoints))
            while name.casefold() in occupied:
                name += "_"
            occupied.add(name.casefold())
            return name

        def prepare(
            source_id: str, expressions: tuple[Expression, ...]
        ) -> tuple[str, dict[int, str], str | None]:
            current = raw_names[source_id]
            columns = validated.schema(source_id)
            fallible = tuple(
                item
                for expression in expressions
                for item in reversed(tuple(iter_expressions(expression)))
                if isinstance(item, (Arithmetic, DecimalRound, LocalizeTimestamp))
            )
            prepared: dict[int, str] = {}
            if not fallible:
                return current, prepared, None
            # Scalar SQL kernels can reorder rows. A native ordinal restores the
            # observed input order after every eager expression checkpoint.
            ordinal = fresh("order")
            name = fresh("input")
            checkpoints.append(
                _DuckDBCheckpoint(
                    name,
                    f"SELECT *, row_number() OVER () AS {quote(ordinal)} FROM {quote(current)}",
                    (current,),
                )
            )
            current = name
            for item in fallible:
                if id(item) in prepared:
                    continue
                field = fresh("value")
                name = fresh("expression")
                value = _expression(item, columns, prepared)
                dtype = _dtype(expression_type(item, columns).logical_type)
                checkpoints.append(
                    _DuckDBCheckpoint(
                        name,
                        f"SELECT *, CAST({value} AS {dtype}) AS {quote(field)} "
                        f"FROM {quote(current)} ORDER BY {quote(ordinal)}",
                        (current,),
                    )
                )
                current = name
                prepared[id(item)] = field
            return current, prepared, ordinal

        for node in plan.nodes:
            dependencies = tuple(raw_names[ref] for ref in references(node))
            prepared: dict[int, str] = {}
            ordinal = None
            expression_source = ""
            if isinstance(node, (Project, Filter)):
                node_expressions = (
                    tuple(item.expression for item in node.columns)
                    if isinstance(node, Project)
                    else (node.predicate,)
                )
                relation, prepared, ordinal = prepare(node.source, node_expressions)
                expression_source = quote(relation)
                dependencies = (relation,)
            if isinstance(node, Scan):
                dependencies = (node.table,)
                body = f"SELECT {_projection(validated, node.node_id)} FROM {quote(node.table)}"
            elif isinstance(node, Project):
                project_columns = ", ".join(
                    _expression(item.expression, validated.schema(node.source), prepared)
                    + " AS "
                    + quote(item.name)
                    for item in node.columns
                )
                body = f"SELECT {project_columns} FROM {expression_source}"
            elif isinstance(node, Filter):
                predicate = _expression(node.predicate, validated.schema(node.source), prepared)
                body = f"SELECT * FROM {expression_source} WHERE {predicate}"
            elif isinstance(node, Cast):
                body = f"SELECT {_projection(validated, node.node_id)} FROM {names[node.source]}"
            elif isinstance(node, EquiJoin):
                join_columns = [
                    "l." + quote(c.name) + " AS " + quote(c.name)
                    for c in validated.schema(node.left)
                ]
                join_columns += (
                    []
                    if node.how in ("semi", "anti")
                    else [
                        "r." + quote(c.name) + " AS " + quote(node.right_prefix + c.name)
                        for c in validated.schema(node.right)
                    ]
                )
                operator = "IS NOT DISTINCT FROM" if node.null_keys == "equal" else "="
                predicate = " AND ".join(
                    f"l.{quote(key.left)} {operator} r.{quote(key.right)}" for key in node.keys
                )
                body = (
                    f"SELECT {', '.join(join_columns)} FROM {names[node.left]} l "
                    f"{node.how.upper()} JOIN {names[node.right]} r ON {predicate}"
                )
            elif isinstance(node, Window):
                partition = (
                    ("PARTITION BY " + ", ".join(quote(name) for name in node.partition_by) + " ")
                    if node.partition_by
                    else ""
                )
                order = ", ".join(
                    quote(key.column)
                    + (" ASC" if key.direction == "ascending" else " DESC")
                    + " NULLS "
                    + key.nulls.upper()
                    for key in node.by
                )
                window = f"OVER ({partition}ORDER BY {order})"
                expressions = [quote(column.name) for column in validated.schema(node.source)]
                for window_measure in node.measures:
                    if window_measure.operation == "row_number":
                        raw = "row_number()"
                    else:
                        if window_measure.column is None:
                            raise CapabilityError("lag/lead require an input column")
                        raw = (
                            f"{window_measure.operation}("
                            f"{quote(window_measure.column)}, {window_measure.offset})"
                        )
                    expressions.append(
                        f"CAST({raw} {window} AS {_dtype(window_measure.logical_type)}) "
                        f"AS {quote(window_measure.name)}"
                    )
                body = f"SELECT {', '.join(expressions)} FROM {names[node.source]}"
            elif isinstance(node, Aggregate):
                aggregate_columns = [quote(name) for name in node.group_by]
                for measure in node.measures:
                    column = quote(measure.column) if measure.column is not None else "*"
                    if measure.operation in ("count_rows", "count_valid"):
                        expression = f"count({column})"
                    elif measure.operation == "sum":
                        scale = (
                            measure.logical_type.scale
                            if isinstance(measure.logical_type, DecimalType)
                            else 0
                        )
                        raw = f"sum(CAST({column} AS DECIMAL(38,{scale})))"
                        expression = f"coalesce({raw}, 0)" if node.empty_sum == "zero" else raw
                    else:
                        expression = f"{measure.operation}({column})"
                    aggregate_columns.append(
                        f"CAST({expression} AS {_dtype(measure.logical_type)}) "
                        f"AS {quote(measure.name)}"
                    )
                body = f"SELECT {', '.join(aggregate_columns)} FROM {names[node.source]}"
                if node.null_groups == "drop" and node.group_by:
                    body += " WHERE " + " AND ".join(
                        quote(name) + " IS NOT NULL" for name in node.group_by
                    )
                if node.group_by:
                    body += " GROUP BY " + ", ".join(quote(name) for name in node.group_by)
            elif isinstance(node, Concatenate):
                body = " UNION ALL ".join(f"SELECT * FROM {names[ref]}" for ref in node.sources)
            elif isinstance(node, Deduplicate):
                if node.keep == "identical":
                    body = f"SELECT DISTINCT * FROM {names[node.source]}"
                else:
                    partition = ", ".join(quote(name) for name in node.keys)
                    order_by = ", ".join(
                        quote(key.column)
                        + (" ASC" if key.direction == "ascending" else " DESC")
                        + " NULLS "
                        + key.nulls.upper()
                        for key in node.by
                    )
                    body = (
                        f"SELECT * FROM {names[node.source]} QUALIFY row_number() "
                        f"OVER (PARTITION BY {partition} ORDER BY {order_by}) = 1"
                    )
            else:
                body = f"SELECT {_projection(validated, node.node_id)} FROM {names[node.source]}"
                if node.ties == "reject":
                    partition = ", ".join(quote(key.column) for key in node.by)
                    body += (
                        f" QUALIFY CASE WHEN count(*) OVER (PARTITION BY {partition}) > 1 "
                        "THEN error('Sort encountered forbidden ties') ELSE TRUE END"
                    )
                body += " ORDER BY " + ", ".join(
                    quote(key.column)
                    + (" ASC" if key.direction == "ascending" else " DESC")
                    + " NULLS "
                    + key.nulls.upper()
                    for key in node.by
                )
            guards = []
            if isinstance(node, Window):
                keys = tuple(dict.fromkeys((*node.partition_by, *(key.column for key in node.by))))
                grouped = ", ".join(quote(key) for key in keys)
                guards.append(
                    f"EXISTS (SELECT 1 FROM {names[node.source]} "
                    f"GROUP BY {grouped} HAVING count(*) > 1)"
                )
            if isinstance(node, EquiJoin) and node.cardinality != "many_to_many":
                for ref, keys, unique in (
                    (
                        node.left,
                        tuple(key.left for key in node.keys),
                        node.cardinality in ("one_to_one", "one_to_many"),
                    ),
                    (
                        node.right,
                        tuple(key.right for key in node.keys),
                        node.cardinality in ("one_to_one", "many_to_one"),
                    ),
                ):
                    if unique:
                        where = (
                            " WHERE " + " AND ".join(quote(key) + " IS NOT NULL" for key in keys)
                            if node.null_keys == "never"
                            else ""
                        )
                        grouped = ", ".join(quote(key) for key in keys)
                        guards.append(
                            f"EXISTS (SELECT 1 FROM {names[ref]}{where} "
                            f"GROUP BY {grouped} HAVING count(*) > 1)"
                        )
            if isinstance(node, Deduplicate) and node.keep == "first":
                keys = tuple(dict.fromkeys((*node.keys, *(key.column for key in node.by))))
                grouped = ", ".join(quote(key) for key in keys)
                guards.append(
                    f"EXISTS (SELECT 1 FROM {names[node.source]} "
                    f"GROUP BY {grouped} HAVING count(*) > 1)"
                )
            if guards:
                # A separate UNION branch evaluates violations even if the join
                # or selected input is empty. This node is consumed in full.
                message = (
                    "Join violates declared cardinality"
                    if isinstance(node, EquiJoin)
                    else "Window encountered forbidden order ties"
                    if isinstance(node, Window)
                    else "Deduplicate encountered forbidden tiebreak ties"
                )
                failure = ", ".join(
                    f"CAST(error('{message}') AS {_dtype(column.logical_type)}) "
                    f"AS {quote(column.name)}"
                    for column in validated.schema(node.node_id)
                )
                body = f"({body}) UNION ALL SELECT {failure} WHERE " + " OR ".join(guards)
            if ordinal is not None:
                body += " ORDER BY " + quote(ordinal)
            # Every node's entire declared schema is converted and consumed
            # before a later projection/filter/join can discard its values.
            checkpoints.append(
                _DuckDBCheckpoint(
                    raw_names[node.node_id],
                    "SELECT "
                    + _projection(validated, node.node_id)
                    + " FROM ("
                    + body
                    + ") AS "
                    + quote(fresh("checked")),
                    dependencies,
                )
            )
        sql = "SELECT " + _projection(validated, plan.output) + " FROM " + names[plan.output]
        output = next(node for node in plan.nodes if node.node_id == plan.output)
        if isinstance(output, Sort):
            sql += " ORDER BY " + ", ".join(
                quote(key.column)
                + (" ASC" if key.direction == "ascending" else " DESC")
                + " NULLS "
                + key.nulls.upper()
                for key in output.by
            )
        codec = _TimestampCodec.for_contract(contract)
        transformation = _DuckDBProgram(
            identifier,
            "SELECT error('This IR program requires the native DuckDB checkpoint adapter')",
            _COMPILER_VERSION,
            timestamp_codec=codec,
            checkpoints=tuple(checkpoints),
            final_sql=sql,
            output_relation=raw_names[plan.output],
        )
        return CompiledPlan(self.engine, transformation, ir_sha, contract_sha, check)
