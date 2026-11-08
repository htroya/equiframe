"""Decimal division composes eagerly without exposing native helper columns."""

from collections import Counter
from decimal import Decimal

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef
from equiframe.values import BooleanValue, DecimalValue

TYPE = ef.DecimalType(precision=6, scale=2)
ENGINES = ("pandas", "polars")


def literal(value):
    return ef.LiteralExpression(logical_type=TYPE, value=DecimalValue(value=value), unit="units")


def divide(left, right, *, rounding="exact"):
    return ef.Arithmetic(
        operation="divide",
        left=left,
        right=right,
        logical_type=TYPE,
        unit="units",
        rounding=rounding,
    )


def fixture(kind):
    a, b = ef.Column(name="a"), ef.Column(name="b")
    quotient = divide(a, b)
    expression = quotient
    if kind == "left_nested":
        expression = divide(quotient, literal("3.00"))
    elif kind == "right_nested":
        expression = divide(a, divide(b, literal("1.00")))
    elif kind == "add":
        expression = ef.Arithmetic(
            operation="add",
            left=quotient,
            right=literal("1.00"),
            logical_type=ef.DecimalType(precision=7, scale=2),
            unit="units",
        )
    elif kind == "coalesce":
        expression = ef.Coalesce(arguments=(ef.Column(name="ratio"), literal("0.00")))
    elif kind == "hidden_coalesce":
        expression = ef.Coalesce(arguments=(literal("0.00"), ef.Column(name="ratio")))
    elif kind == "hidden_null_test":
        expression = ef.IsNull(argument=quotient)
    output = [column("ratio", ef.DecimalType(precision=7, scale=2) if kind == "add" else TYPE)]
    if kind == "filter":
        output = [column("a", TYPE), column("b", TYPE)]
        node = ef.Filter(
            node_id="result",
            source="scan",
            predicate=ef.Compare(operation="gt", left=quotient, right=literal("3.00")),
        )
    else:
        columns = (ef.NamedExpression(name="ratio", expression=expression),)
        if kind == "two_columns":
            columns = (
                ef.NamedExpression(name="a", expression=quotient),
                ef.NamedExpression(name="b", expression=divide(b, a, rounding="half_even")),
            )
            output = [column("a", TYPE), column("b", TYPE)]
        elif kind == "hidden_null_test":
            output = [column("ratio", ef.BooleanType())]
        node = ef.Project(
            node_id="result",
            source="checkpoint" if kind in ("coalesce", "hidden_coalesce") else "scan",
            columns=columns,
        )
    nodes = [ef.Scan(node_id="scan", table="input")]
    if kind in ("coalesce", "hidden_coalesce"):
        nodes.append(
            ef.Project(
                node_id="checkpoint",
                source="scan",
                columns=(ef.NamedExpression(name="ratio", expression=quotient),),
            )
        )
    nodes.append(node)
    if kind == "later_filter":
        nodes.append(
            ef.Filter(
                node_id="filtered",
                source="result",
                predicate=ef.LiteralExpression(
                    logical_type=ef.BooleanType(), value=BooleanValue(value=False)
                ),
            )
        )
    plan = ef.RelationalPlan(nodes=tuple(nodes), output=nodes[-1].node_id)
    schema = contract({"input": [column("a", TYPE), column("b", TYPE)]}, output)
    return plan, schema


def source(*, empty=False, invalid=False):
    left = (
        []
        if empty
        else [Decimal("1.00")]
        if invalid
        else [Decimal("12.30"), Decimal("12.30"), Decimal("-12.30"), None]
    )
    right = (
        []
        if empty
        else [Decimal("3.00")]
        if invalid
        else [Decimal("2.00"), Decimal("2.00"), Decimal("2.00"), Decimal("0.00")]
    )
    return pa.table(
        {
            "a": pa.array(left, type=pa.decimal128(6, 2)),
            "b": pa.array(right, type=pa.decimal128(6, 2)),
        }
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "kind", ("left_nested", "right_nested", "add", "coalesce", "two_columns", "filter")
)
def test_composed_division_preserves_literal_values_and_multiplicity(engine, kind, tmp_path):
    plan, schema = fixture(kind)
    result = run(plan, schema, {"input": source()}, engine, tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    expected = {
        "left_nested": [("2.05",), ("2.05",), ("-2.05",), (None,)],
        "right_nested": [("6.15",), ("6.15",), ("-6.15",), (None,)],
        "add": [("7.15",), ("7.15",), ("-5.15",), (None,)],
        "coalesce": [("6.15",), ("6.15",), ("-6.15",), ("0.00",)],
        "two_columns": [("6.15", "0.16"), ("6.15", "0.16"), ("-6.15", "-0.16"), (None, None)],
        "filter": [("12.30", "2.00"), ("12.30", "2.00")],
    }[kind]
    names = [item.name for item in schema.output.schema_spec.columns]
    assert actual.column_names == names
    assert all(field.type == pa.decimal128(7 if kind == "add" else 6, 2) for field in actual.schema)
    assert Counter(tuple(row[name] for name in names) for row in actual.to_pylist()) == Counter(
        tuple(None if item is None else Decimal(item) for item in row) for row in expected
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("kind", ("hidden_coalesce", "hidden_null_test", "later_filter"))
def test_inexact_division_cannot_be_concealed_by_another_expression(engine, kind, tmp_path):
    plan, schema = fixture(kind)
    result = run(plan, schema, {"input": source(invalid=True)}, engine, tmp_path)
    assert result.state != "completed"
    assert result.output is None
    assert result.problem is not None
    assert result.problem.exception_type == ("Inexact" if engine == "pandas" else "CapabilityError")


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("kind", ("two_columns", "filter"))
def test_composed_division_preserves_empty_schema(engine, kind, tmp_path):
    plan, schema = fixture(kind)
    result = run(plan, schema, {"input": source(empty=True)}, engine, tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.num_rows == 0
    assert actual.column_names == [item.name for item in schema.output.schema_spec.columns]
    assert all(field.type == pa.decimal128(6, 2) for field in actual.schema)
