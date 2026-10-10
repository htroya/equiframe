"""DuckDB compiler: one quoted SELECT/WITH, no external SQL or callbacks."""

from __future__ import annotations

import re

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
from equiframe.registry import DuckDBTransformation
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
    contains_arithmetic,
    expression_type,
    iter_expressions,
    references,
)

_COMPILER_VERSION = "migration-native-ir1.0/duckdb/product-semantics-v3"


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
        return (
            "TIMESTAMPTZ"
            if dtype.timezone is not None
            else {
                "s": "TIMESTAMP_S",
                "ms": "TIMESTAMP_MS",
                "us": "TIMESTAMP",
                "ns": "TIMESTAMP_NS",
            }[dtype.unit]
        )
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


def _expression(expression: Expression, columns: tuple[IRColumn, ...]) -> str:
    if isinstance(expression, Column):
        return quote(expression.name)
    if isinstance(expression, LiteralExpression):
        return _literal(expression)
    if isinstance(expression, Arithmetic):
        left = _expression(expression.left, columns)
        right = _expression(expression.right, columns)
        operand = expression_type(expression.left, columns).logical_type
        if expression.operation == "multiply" and isinstance(operand, DecimalType):
            right_type = expression_type(expression.right, columns).logical_type
            assert isinstance(right_type, DecimalType)
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
        return (
            f"CAST(round({_expression(expression.argument, columns)}, "
            f"{expression.logical_type.scale}) AS {_dtype(expression.logical_type)})"
        )
    if isinstance(expression, Coalesce):
        return (
            "coalesce("
            + ", ".join(_expression(item, columns) for item in expression.arguments)
            + ")"
        )
    if isinstance(expression, Conditional):
        return (
            f"CASE WHEN {_expression(expression.predicate, columns)} "
            f"THEN {_expression(expression.then, columns)} "
            f"ELSE {_expression(expression.otherwise, columns)} END"
        )
    if isinstance(expression, Compare):
        left, right = _expression(expression.left, columns), _expression(expression.right, columns)
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
            + operator.join(_expression(argument, columns) for argument in expression.arguments)
            + ")"
        )
    argument = _expression(expression.argument, columns)
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
                if any(
                    isinstance(column.logical_type, TimestampType)
                    and column.logical_type.timezone is not None
                    and (column.logical_type.unit != "us" or column.logical_type.timezone != "UTC")
                    for column in schema.columns
                ):
                    return CompilationCheck(
                        engine=self.engine,
                        supported=False,
                        diagnostics=(
                            CompilationDiagnostic(
                                code="timestamp_unit_zone_not_supported",
                                message=(
                                    "DuckDB timestamp IR zoned transport requires exact "
                                    "microseconds and UTC session zone"
                                ),
                                node_id=schema.node_id,
                            ),
                        ),
                    )
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
            consumers = {
                node.node_id: tuple(
                    other for other in plan.nodes if node.node_id in references(other)
                )
                for node in plan.nodes
            }
            for node in plan.nodes:
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
                        if isinstance(item, LocalizeTimestamp):
                            message = (
                                "DuckDB timestamp localization cannot preserve "
                                "explicit DST ambiguity/gap rejection policies"
                            )
                        if isinstance(item, Arithmetic) and item.operation == "divide":
                            message = (
                                "DuckDB Decimal division produces DOUBLE and cannot "
                                "preserve the declared exact/rounding contract"
                            )
                        if (
                            isinstance(item, DecimalRound)
                            and item.rounding != "half_away_from_zero"
                        ):
                            message = (
                                "DuckDB exact Decimal rounding supports half_away_from_zero only"
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
                if any(
                    contains_arithmetic(expression)
                    and (
                        not isinstance(expression, (Arithmetic, DecimalRound))
                        or (
                            isinstance(expression, Arithmetic)
                            and (
                                contains_arithmetic(expression.left)
                                or contains_arithmetic(expression.right)
                            )
                        )
                        or (
                            isinstance(expression, DecimalRound)
                            and contains_arithmetic(expression.argument)
                        )
                    )
                    for expression in expressions
                ):
                    # DuckDB can use the declared result range to simplify an
                    # arithmetic predicate without evaluating its fallible cast,
                    # or propagate NULL past a nested arithmetic operation.
                    # Even a final projection or materialized CTE does not provide
                    # an eager checkpoint for each intermediate expression.
                    return CompilationCheck(
                        engine=self.engine,
                        supported=False,
                        diagnostics=(
                            CompilationDiagnostic(
                                code="eager_semantics_not_supported",
                                message=(
                                    "DuckDB cannot preserve eager overflow rejection in nested "
                                    "arithmetic or arithmetic predicates; arithmetic requires "
                                    "one direct projected operation with only a final sort suffix"
                                ),
                                node_id=node.node_id,
                            ),
                        ),
                    )
                if not (
                    isinstance(node, (Aggregate, Window))
                    or (isinstance(node, EquiJoin) and node.cardinality != "many_to_many")
                    or (isinstance(node, Deduplicate) and node.keep == "first")
                    or (isinstance(node, Sort) and node.ties == "reject")
                    or (
                        isinstance(node, Project)
                        and any(contains_arithmetic(item.expression) for item in node.columns)
                    )
                ):
                    continue
                # SQL optimizers may prune a checked aggregate column, even in
                # a materialized CTE. Later projection/filter/join must therefore
                # not turn an eager IR error into a successful execution. Sort
                # preserves every row and column and remains a supported suffix.
                pending = list(consumers[node.node_id])
                visited: set[str] = set()
                while pending:
                    consumer = pending.pop()
                    if consumer.node_id in visited:
                        continue
                    visited.add(consumer.node_id)
                    if not isinstance(consumer, Sort):
                        return CompilationCheck(
                            engine=self.engine,
                            supported=False,
                            diagnostics=(
                                CompilationDiagnostic(
                                    code="eager_semantics_not_supported",
                                    message=(
                                        "DuckDB error-bearing aggregate/sort/arithmetic/"
                                        "join/deduplicate/window nodes "
                                        "only support "
                                        "a final sort suffix; later relational nodes may "
                                        "prune errors"
                                    ),
                                    node_id=node.node_id,
                                ),
                            ),
                        )
                    pending.extend(consumers[consumer.node_id])
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
        names = {
            node.node_id: quote(prefix + str(position)) for position, node in enumerate(plan.nodes)
        }
        clauses = []
        for node in plan.nodes:
            if isinstance(node, Scan):
                body = f"SELECT {_projection(validated, node.node_id)} FROM {quote(node.table)}"
            elif isinstance(node, Project):
                project_columns = ", ".join(
                    _expression(item.expression, validated.schema(node.source))
                    + " AS "
                    + quote(item.name)
                    for item in node.columns
                )
                body = f"SELECT {project_columns} FROM {names[node.source]}"
            elif isinstance(node, Filter):
                predicate = _expression(node.predicate, validated.schema(node.source))
                body = f"SELECT * FROM {names[node.source]} WHERE {predicate}"
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
                # or selected input is empty. Later pruning nodes are rejected.
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
            clauses.append(names[node.node_id] + " AS (" + body + ")")
        sql = (
            "WITH "
            + ", ".join(clauses)
            + " SELECT "
            + _projection(validated, plan.output)
            + " FROM "
            + names[plan.output]
        )
        output = next(node for node in plan.nodes if node.node_id == plan.output)
        if isinstance(output, Sort):
            sql += " ORDER BY " + ", ".join(
                quote(key.column)
                + (" ASC" if key.direction == "ascending" else " DESC")
                + " NULLS "
                + key.nulls.upper()
                for key in output.by
            )
        transformation = DuckDBTransformation(identifier, sql, _COMPILER_VERSION)
        return CompiledPlan(self.engine, transformation, ir_sha, contract_sha, check)
