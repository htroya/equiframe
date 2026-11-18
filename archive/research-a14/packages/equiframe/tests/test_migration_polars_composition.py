"""Scalar native references compose literally, including on minimum Polars 1.30."""

from decimal import Decimal
from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import column, contract
from test_migration_literal_names import check, table

import equiframe as ef

INT = ef.IntegerType(bits=64, signed=True)
BOOL = ef.BooleanType()
NAMES = (
    ("left", "right"),
    ("*", "^a$"),
    ("^[a$", "^.*$"),
    ("^[ab]$", "line\nbreak"),
    ("_equiframe_column_1", "_equiframe_column_0"),
    ("_equiframe_project_0", "_equiframe_measure_0"),
)
OPERATIONS = (
    "and",
    "or",
    "not",
    "eq",
    "ne",
    "lt",
    "le",
    "gt",
    "ge",
    "add",
    "subtract",
    "multiply",
    "coalesce",
    "conditional",
)


def literal(value):
    return ef.LiteralExpression(logical_type=INT, value=ef.IntegerValue(value=value), unit="units")


def expression_case(names, operation):
    left, right = (ef.Column(name=name) for name in names)
    first = ef.Compare(operation="gt", left=left, right=literal(1))
    second = ef.Compare(operation="lt", left=right, right=literal(4))
    # Expectations are explicit fixture values, never another engine's output.
    expected = {
        "and": [True, False, None, False, None],
        "or": [True, None, True, True, None],
        "not": [False, True, None, True, None],
        "eq": [False, None, None, True, None],
        "ne": [True, None, None, False, None],
        "lt": [True, None, None, False, None],
        "le": [True, None, None, True, None],
        "gt": [False, None, None, False, None],
        "ge": [False, None, None, True, None],
        "add": [5, None, None, 2, None],
        "subtract": [-1, None, None, 0, None],
        "multiply": [6, None, None, 1, None],
        "coalesce": [2, 5, 4, 1, None],
        "conditional": [2, 5, None, 1, None],
    }
    if operation in ("and", "or", "not"):
        expression = ef.Boolean(
            operation="or" if operation == "or" else "and", arguments=(first, second)
        )
        if operation == "not":
            expression = ef.Not(argument=expression)
    elif operation in ("eq", "ne", "lt", "le", "gt", "ge"):
        expression = ef.Compare(operation=operation, left=left, right=right)
    elif operation in ("add", "subtract", "multiply"):
        expression = ef.Arithmetic(
            operation=operation, left=left, right=right, logical_type=INT, unit="units"
        )
    elif operation == "coalesce":
        expression = ef.Coalesce(arguments=(left, right))
    else:
        expression = ef.Conditional(
            predicate=ef.Boolean(operation="and", arguments=(first, second)),
            then=ef.Coalesce(arguments=(left, right)),
            otherwise=right,
        )
    dtype = INT if operation in ("add", "subtract", "multiply", "coalesce", "conditional") else BOOL
    return expression, dtype, expected[operation]


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("empty", (False, True))
def test_polars_composed_expressions_have_independent_values(tmp_path, names, operation, empty):
    left, right = names
    data = table({left: [2, None, 4, 1, None], right: [3, 5, None, 1, None], "a": [99] * 5})
    expression, dtype, values = expression_case(names, operation)
    input_type = ef.IntegerType(bits=32, signed=True) if operation == "multiply" else INT
    if operation == "multiply":
        data = data.cast(pa.schema([(name, pa.int32()) for name in data.column_names]))
    if empty:
        data, values = data.slice(0, 0), []
    expected = pa.table(
        {"^result$": pa.array(values, type=pa.int64() if dtype == INT else pa.bool_())}
    )
    schema = contract(
        {"input": [column(name, input_type) for name in data.column_names]},
        [column("^result$", dtype)],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(ef.NamedExpression(name="^result$", expression=expression),),
            ),
        ),
        output="out",
    )
    check(plan, schema, {"input": data}, expected, "polars", tmp_path, ordered=True)


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("empty", (False, True))
def test_polars_simultaneous_aliases_reorder_then_compose(tmp_path, names, empty):
    left, right = names
    # Physical input order also differs from the validated Scan schema. execute
    # is a lower-level compiler consumer; _coerce must resolve by actual name.
    data = table({right: [3, 5], "a": [99, 98], left: [2, 4]})
    if empty:
        data = data.slice(0, 0)
    schema = contract(
        {"input": [column(left, INT), column(right, INT), column("a", INT)]},
        [column("^result$", INT), column(left, INT), column(right, INT)],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="swap",
                source="scan",
                columns=(
                    ef.NamedExpression(name=right, expression=ef.Column(name=left)),
                    ef.NamedExpression(name="^extra$", expression=ef.Column(name="a")),
                    ef.NamedExpression(name=left, expression=ef.Column(name=right)),
                ),
            ),
            ef.Project(
                node_id="out",
                source="swap",
                columns=(
                    ef.NamedExpression(
                        name="^result$",
                        expression=ef.Arithmetic(
                            operation="subtract",
                            left=ef.Column(name=left),
                            right=ef.Column(name=right),
                            logical_type=INT,
                            unit="units",
                        ),
                    ),
                    ef.NamedExpression(name=left, expression=ef.Column(name=left)),
                    ef.NamedExpression(name=right, expression=ef.Column(name=right)),
                ),
            ),
        ),
        output="out",
    )
    expected = table({"^result$": [1, 1], left: [3, 5], right: [2, 4]})
    check(
        plan,
        schema,
        {"input": data},
        expected.slice(0, 0) if empty else expected,
        "polars",
        tmp_path,
        ordered=True,
    )


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("source,target", tuple(permutations(("pandas", "polars", "duckdb"), 2)))
def test_composed_filter_public_migration_six_directions(tmp_path, names, source, target):
    left, right = names
    data = table({left: [2, None, 4, 1, None], right: [3, 5, None, 1, None], "a": [99] * 5})
    columns = [column(name, INT) for name in data.column_names]
    schema = contract({"input": columns}, columns)
    predicate, _, _ = expression_case(names, "and")
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Filter(node_id="out", source="scan", predicate=predicate),
        ),
        output="out",
    )
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=source,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated index is not identity"
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(data)}),
        expected=ef.ArrowInput(table({left: [2], right: [3], "a": [99]})),
        work_dir=tmp_path,
    )
    assert result.complete and result.exit_code == 0
    assert result.state == "equivalent" and result.verification == "correct"


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("operation", ("add", "subtract", "multiply"))
def test_polars_multi_column_decimal_arithmetic_is_exact(tmp_path, names, operation):
    left, right = names
    dtype = ef.DecimalType(precision=6, scale=2)
    output_dtype = (
        ef.DecimalType(precision=12, scale=4)
        if operation == "multiply"
        else ef.DecimalType(precision=7, scale=2)
    )
    data = pa.table(
        {
            left: pa.array([Decimal("1.20"), None, Decimal("-2.50")], type=pa.decimal128(6, 2)),
            right: pa.array(
                [Decimal("3.40"), Decimal("2.00"), Decimal("2.00")], type=pa.decimal128(6, 2)
            ),
        }
    )
    values = {
        "add": [Decimal("4.60"), None, Decimal("-0.50")],
        "subtract": [Decimal("-2.20"), None, Decimal("-4.50")],
        "multiply": [Decimal("4.0800"), None, Decimal("-5.0000")],
    }[operation]
    schema = contract(
        {"input": [column(left, dtype), column(right, dtype)]}, [column("*", output_dtype)]
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(
                    ef.NamedExpression(
                        name="*",
                        expression=ef.Arithmetic(
                            operation=operation,
                            left=ef.Column(name=left),
                            right=ef.Column(name=right),
                            logical_type=output_dtype,
                            unit="units",
                        ),
                    ),
                ),
            ),
        ),
        output="out",
    )
    expected = pa.table(
        {"*": pa.array(values, type=pa.decimal128(output_dtype.precision, output_dtype.scale))}
    )
    check(plan, schema, {"input": data}, expected, "polars", tmp_path, ordered=True)


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("null_groups", ("retain", "drop"))
@pytest.mark.parametrize("empty", (False, True))
def test_polars_composite_groups_and_post_aggregate_projection(tmp_path, names, null_groups, empty):
    left, right = names
    data = table({left: [1, 1, None, 2], "amount": [5, 7, 10, None], right: [1, 1, None, 1]})
    if empty:
        data = data.slice(0, 0)
    schema = contract(
        {"input": [column(name, INT) for name in data.column_names]},
        [column("^total$", INT), column(right, INT), column(left, INT)],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Aggregate(
                node_id="agg",
                source="scan",
                group_by=(right, left),
                measures=(
                    ef.Measure(
                        name="^total$",
                        operation="sum",
                        column="amount",
                        logical_type=INT,
                        unit="units",
                    ),
                ),
                null_groups=null_groups,
                empty_sum="null",
            ),
            ef.Project(
                node_id="out",
                source="agg",
                columns=(
                    ef.NamedExpression(name="^total$", expression=ef.Column(name="^total$")),
                    ef.NamedExpression(name=right, expression=ef.Column(name=right)),
                    ef.NamedExpression(name=left, expression=ef.Column(name=left)),
                ),
            ),
        ),
        output="out",
    )
    expected = table({"^total$": [12, 10, None], right: [1, None, 1], left: [1, None, 2]})
    if empty:
        expected = expected.slice(0, 0)
    elif null_groups == "drop":
        expected = table({"^total$": [12, None], right: [1, 1], left: [1, 2]})
    check(plan, schema, {"input": data}, expected, "polars", tmp_path, ordered=True)


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("empty", (False, True))
def test_polars_composite_dedup_sort_after_reordered_projection(tmp_path, names, empty):
    left, right = names
    data = table({left: [1, 1, 2, None, None], right: [2, 2, 1, 1, 1], "revision": [1, 2, 1, 1, 2]})
    if empty:
        data = data.slice(0, 0)
    order = ["revision", right, left]
    schema = contract(
        {"input": [column(name, INT) for name in data.column_names]},
        [column(name, INT) for name in order],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="project",
                source="scan",
                columns=tuple(
                    ef.NamedExpression(name=name, expression=ef.Column(name=name)) for name in order
                ),
            ),
            ef.Concatenate(node_id="concat", sources=("project", "project")),
            ef.Deduplicate(node_id="identical", source="concat", keys=tuple(order)),
            ef.Deduplicate(
                node_id="first",
                source="identical",
                keys=(left, right),
                keep="first",
                by=(ef.SortKey(column="revision", direction="descending", nulls="last"),),
            ),
            ef.Sort(
                node_id="out",
                source="first",
                by=(
                    ef.SortKey(column=left, direction="ascending", nulls="last"),
                    ef.SortKey(column=right, direction="descending", nulls="last"),
                ),
                ties="reject",
            ),
        ),
        output="out",
    )
    expected = table({"revision": [2, 1, 2], right: [2, 1, 1], left: [1, 2, None]})
    check(
        plan,
        schema,
        {"input": data},
        expected.slice(0, 0) if empty else expected,
        "polars",
        tmp_path,
        ordered=True,
    )


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("null_keys", ("equal", "never"))
def test_polars_composite_join_and_downstream_comparison(tmp_path, names, null_keys):
    left, right = names
    data = table({left: [1, 1, None, 2], right: [1, 2, None, 1]})
    columns = [column(name, INT) for name in data.column_names]
    schema = contract({"input": columns}, columns, family="joins")
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.EquiJoin(
                node_id="join",
                left="scan",
                right="scan",
                keys=(
                    ef.JoinKey(left=left, right=left),
                    ef.JoinKey(left=right, right=right),
                ),
                how="inner",
                null_keys=null_keys,
                cardinality="one_to_one",
                right_prefix="joined.",
            ),
            ef.Filter(
                node_id="filter",
                source="join",
                predicate=ef.Compare(
                    operation="lt",
                    left=ef.Column(name=left),
                    right=ef.Column(name="joined." + right),
                ),
            ),
            ef.Project(
                node_id="out",
                source="filter",
                columns=(
                    ef.NamedExpression(name=left, expression=ef.Column(name=left)),
                    ef.NamedExpression(name=right, expression=ef.Column(name="joined." + right)),
                ),
            ),
        ),
        output="out",
    )
    check(
        plan,
        schema,
        {"input": data},
        table({left: [1], right: [2]}),
        "polars",
        tmp_path,
        ordered=True,
    )


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("operation", ("eq", "ne", "lt", "le", "gt", "ge"))
def test_polars_composed_float_comparisons_distinguish_nan_null_infinity(
    tmp_path, names, operation
):
    left, right = names
    dtype = ef.FloatType(bits=64)
    data = pa.table(
        {
            left: pa.array(
                [float("nan"), 1.0, None, float("inf"), float("-inf"), -0.0], type=pa.float64()
            ),
            right: pa.array([2.0, float("nan"), 3.0, float("inf"), 0.0, 0.0], type=pa.float64()),
        }
    )
    values = {
        "eq": [False, False, None, True, False, True],
        "ne": [True, True, None, False, True, False],
        "lt": [False, False, None, False, True, False],
        "le": [False, False, None, True, True, True],
        "gt": [False, False, None, False, False, False],
        "ge": [False, False, None, True, False, True],
    }[operation]
    schema = contract({"input": [column(left, dtype), column(right, dtype)]}, [column("*", BOOL)])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(
                    ef.NamedExpression(
                        name="*",
                        expression=ef.Compare(
                            operation=operation,
                            left=ef.Column(name=left),
                            right=ef.Column(name=right),
                        ),
                    ),
                ),
            ),
        ),
        output="out",
    )
    check(
        plan,
        schema,
        {"input": data},
        pa.table({"*": pa.array(values, type=pa.bool_())}),
        "polars",
        tmp_path,
        ordered=True,
    )


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("empty", (False, True))
def test_polars_literal_only_projection_preserves_row_count(tmp_path, names, empty):
    left, right = names
    data = table({left: [1, 2], right: [3, 4]})
    if empty:
        data = data.slice(0, 0)
    schema = contract(
        {"input": [column(left, INT), column(right, INT)]}, [column(right, INT), column(left, INT)]
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(
                    ef.NamedExpression(name=right, expression=literal(7)),
                    ef.NamedExpression(
                        name=left,
                        expression=ef.LiteralExpression(
                            logical_type=INT, value=ef.NullValue(), unit="units"
                        ),
                    ),
                ),
            ),
        ),
        output="out",
    )
    expected = table({right: [7, 7], left: [None, None]})
    check(
        plan,
        schema,
        {"input": data},
        expected.slice(0, 0) if empty else expected,
        "polars",
        tmp_path,
        ordered=True,
    )
