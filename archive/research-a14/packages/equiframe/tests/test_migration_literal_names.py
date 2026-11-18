"""Literal-name regressions with independent values, including native selectors."""

from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef

INT = ef.IntegerType(bits=64, signed=True)
ENGINES = ("pandas", "polars", "duckdb")
NAMES = ("*", "^a$", "^.*$", "^[a$", "^[ab]$", "line\nbreak", 'quote"é', "a.b", "ordinary")


def table(values):
    return pa.table({name: pa.array(rows, type=pa.int64()) for name, rows in values.items()})


def check(plan, schema, inputs, expected, engine, tmp_path, *, ordered=False):
    result = run(plan, schema, inputs, engine, tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.column_names == expected.column_names
    assert actual.schema.types == expected.schema.types
    if ordered:
        assert actual.to_pylist() == expected.to_pylist()
    else:
        compared = ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        )
        assert compared.state == "equivalent"
    return result


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("empty", (False, True))
def test_scan_and_project_literal_names(tmp_path, engine, name, empty):
    values = [] if empty else [7, 3]
    other = [] if empty else [99, 98]
    data = table({name: values, "a": other, "other": other})
    schema = contract(
        {"input": [column(n, INT) for n in data.column_names]},
        [column("^output$", INT), column("*", INT)],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(
                    ef.NamedExpression(name="^output$", expression=ef.Column(name=name)),
                    ef.NamedExpression(name="*", expression=ef.Column(name="other")),
                ),
            ),
        ),
        output="out",
    )
    check(
        plan,
        schema,
        {"input": data},
        table({"^output$": values, "*": other}),
        engine,
        tmp_path,
        ordered=True,
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("name", ("*", "^a$"))
@pytest.mark.parametrize("operation", ("filter", "cast", "sort", "deduplicate"))
def test_literal_filter_cast_sort_dedup(tmp_path, engine, name, operation):
    data = table({name: [2, 1, 2], "a": [90, 80, 70], "revision": [1, 1, 2]})
    columns = [column(n, INT) for n in data.column_names]
    if operation == "filter":
        node = ef.Filter(
            node_id="out",
            source="scan",
            predicate=ef.Compare(
                operation="eq",
                left=ef.Column(name=name),
                right=ef.LiteralExpression(
                    logical_type=INT, value=ef.IntegerValue(value=2), unit="units"
                ),
            ),
        )
        expected = table({name: [2, 2], "a": [90, 70], "revision": [1, 2]})
    elif operation == "cast":
        node = ef.Cast(
            node_id="out", source="scan", columns=(ef.CastColumn(column=name, logical_type=INT),)
        )
        expected = data
    elif operation == "sort":
        node = ef.Sort(
            node_id="out",
            source="scan",
            by=(
                ef.SortKey(column=name, direction="ascending", nulls="last"),
                ef.SortKey(column="revision", direction="descending", nulls="last"),
            ),
            ties="reject",
        )
        expected = table({name: [1, 2, 2], "a": [80, 70, 90], "revision": [1, 2, 1]})
    else:
        node = ef.Deduplicate(
            node_id="out",
            source="scan",
            keys=(name,),
            keep="first",
            by=(ef.SortKey(column="revision", direction="descending", nulls="last"),),
        )
        expected = table({name: [2, 1], "a": [70, 80], "revision": [2, 1]})
    plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="scan", table="input"), node), output="out")
    check(
        plan,
        contract({"input": columns}, columns),
        {"input": data},
        expected,
        engine,
        tmp_path,
        ordered=operation == "sort",
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("name", ("*", "^a$"))
@pytest.mark.parametrize("nulls", ("retain", "drop"))
def test_literal_aggregate_keys_and_measures(tmp_path, engine, name, nulls):
    value = "^value$"
    data = table({name: [2, 2, None], value: [3, 4, 5], "a": [90, 80, 70]})
    schema = contract(
        {"input": [column(n, INT) for n in data.column_names]},
        [column(name, INT), column("*total", INT)],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Aggregate(
                node_id="out",
                source="scan",
                group_by=(name,),
                measures=(
                    ef.Measure(
                        name="*total", operation="sum", column=value, logical_type=INT, unit="units"
                    ),
                ),
                null_groups=nulls,
                empty_sum="zero",
            ),
        ),
        output="out",
    )
    expected = table(
        {
            name: [2, None] if nulls == "retain" else [2],
            "*total": [7, 5] if nulls == "retain" else [7],
        }
    )
    check(plan, schema, {"input": data}, expected, engine, tmp_path)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("name", ("*", "^a$"))
@pytest.mark.parametrize("how", ("inner", "left", "right", "full", "semi", "anti"))
@pytest.mark.parametrize("nulls", ("equal", "never"))
def test_literal_join_keys_and_hygienic_column_names(tmp_path, engine, name, how, nulls):
    payload = "_equiframe_join_left_0"
    left = table({name: [1, 2, None], payload: [10, 20, 30], "a": [91, 92, 93]})
    right = table({name: [1, 3, None], payload: [40, 50, 60], "a": [81, 82, 83]})
    names = left.column_names
    output_names = names if how in ("semi", "anti") else [*names, *("^" + n for n in names)]
    matched = [(1, 10, 91, 1, 40, 81)]
    if nulls == "equal":
        matched.append((None, 30, 93, None, 60, 83))
    missing_left = [(2, 20, 92)] + ([] if nulls == "equal" else [(None, 30, 93)])
    missing_right = [(3, 50, 82)] + ([] if nulls == "equal" else [(None, 60, 83)])
    rows = (
        [r[:3] for r in matched]
        if how == "semi"
        else missing_left
        if how == "anti"
        else matched
        + ([(*r, None, None, None) for r in missing_left] if how in ("left", "full") else [])
        + ([(None, None, None, *r) for r in missing_right] if how in ("right", "full") else [])
    )
    expected = table({n: [r[i] for r in rows] for i, n in enumerate(output_names)})
    schema = contract(
        {"left": [column(n, INT) for n in names], "right": [column(n, INT) for n in names]},
        [column(n, INT) for n in output_names],
        family="joins",
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="l", table="left"),
            ef.Scan(node_id="r", table="right"),
            ef.EquiJoin(
                node_id="out",
                left="l",
                right="r",
                keys=(ef.JoinKey(left=name, right=name),),
                how=how,
                null_keys=nulls,
                right_prefix="^",
                cardinality="one_to_one",
            ),
        ),
        output="out",
    )
    check(plan, schema, {"left": left, "right": right}, expected, engine, tmp_path)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("name", ("*", "^a$"))
@pytest.mark.parametrize("operation", ("join", "sort", "deduplicate"))
def test_literal_key_rejections_do_not_expand_to_unique_decoy(tmp_path, engine, name, operation):
    data = table({name: [1, 1], "a": [90, 80], "revision": [1, 1]})
    columns = [column(n, INT) for n in data.column_names]
    nodes = [ef.Scan(node_id="scan", table="input")]
    if operation == "join":
        nodes.append(
            ef.EquiJoin(
                node_id="out",
                left="scan",
                right="scan",
                keys=(ef.JoinKey(left=name, right=name),),
                how="semi",
                null_keys="never",
                cardinality="one_to_one",
            )
        )
    elif operation == "sort":
        nodes.append(
            ef.Sort(
                node_id="out",
                source="scan",
                by=(ef.SortKey(column=name, direction="ascending", nulls="last"),),
                ties="reject",
            )
        )
    else:
        nodes.append(
            ef.Deduplicate(
                node_id="out",
                source="scan",
                keys=(name,),
                keep="first",
                by=(ef.SortKey(column="revision", direction="descending", nulls="last"),),
            )
        )
    result = run(
        ef.RelationalPlan(nodes=tuple(nodes), output="out"),
        contract({"input": columns}, columns),
        {"input": data},
        engine,
        tmp_path,
    )
    assert result.state == ("failed" if engine == "duckdb" else "invalid_input")
    assert result.problem.exception_type == (
        "InvalidInputException" if engine == "duckdb" else "CapabilityError"
    )


@pytest.mark.parametrize("source,target", tuple(permutations(ENGINES, 2)))
def test_literal_name_public_migration_six_directions(tmp_path, source, target):
    data = table({"*": [7], "^a$": [8], "a": [99]})
    schema = contract(
        {"input": [column(n, INT) for n in data.column_names]}, [column("selected", INT)]
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(ef.NamedExpression(name="selected", expression=ef.Column(name="*")),),
            ),
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
                index="ignore", justification="Generated index is not business identity"
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(data)}),
        expected=ef.ArrowInput(table({"selected": [7]})),
        work_dir=tmp_path,
    )
    assert result.complete and result.exit_code == 0
    assert result.state == "equivalent" and result.verification == "correct"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("alias", ("*", "^a$", "^[a$", "^[ab]$"))
def test_generated_literal_alias_does_not_expand_input_columns(tmp_path, engine, alias):
    data = table({"value": [7], "a": [99], "b": [98]})
    schema = contract({"input": [column(n, INT) for n in data.column_names]}, [column(alias, INT)])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="out",
                source="scan",
                columns=(ef.NamedExpression(name=alias, expression=ef.Column(name="value")),),
            ),
        ),
        output="out",
    )
    check(plan, schema, {"input": data}, table({alias: [7]}), engine, tmp_path, ordered=True)


@pytest.mark.parametrize("name", ("*", "^a$"))
@pytest.mark.parametrize("how", ("inner", "left", "right", "full", "semi", "anti"))
@pytest.mark.parametrize("empty", ("left", "right", "both"))
def test_literal_polars_join_empty_sides_preserve_exact_schema(tmp_path, name, how, empty):
    left_values = [] if empty in ("left", "both") else [1]
    right_values = [] if empty in ("right", "both") else [1]
    left, right = (
        table({name: left_values, "a": left_values}),
        table({name: right_values, "a": right_values}),
    )
    output = [name, "a"] if how in ("semi", "anti") else [name, "a", "right." + name, "right.a"]
    rows = []
    if left_values and how in ("left", "full"):
        rows = [(1, 1, None, None)]
    elif right_values and how in ("right", "full"):
        rows = [(None, None, 1, 1)]
    elif left_values and how == "anti":
        rows = [(1, 1)]
    expected = table({n: [r[i] for r in rows] for i, n in enumerate(output)})
    schema = contract(
        {
            "left": [column(n, INT) for n in left.column_names],
            "right": [column(n, INT) for n in right.column_names],
        },
        [column(n, INT) for n in output],
        family="joins",
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="l", table="left"),
            ef.Scan(node_id="r", table="right"),
            ef.EquiJoin(
                node_id="out",
                left="l",
                right="r",
                keys=(ef.JoinKey(left=name, right=name),),
                how=how,
                null_keys="equal",
            ),
        ),
        output="out",
    )
    check(plan, schema, {"left": left, "right": right}, expected, "polars", tmp_path)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("name", ("*", "^a$"))
def test_literal_identical_dedup_after_concatenation(tmp_path, engine, name):
    data = table({name: [2, 1], "a": [90, 80]})
    columns = [column(n, INT) for n in data.column_names]
    schema = contract({"input": columns}, columns)
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Concatenate(node_id="twice", sources=("scan", "scan")),
            ef.Deduplicate(node_id="out", source="twice", keys=(name, "a")),
        ),
        output="out",
    )
    check(plan, schema, {"input": data}, data, engine, tmp_path)
