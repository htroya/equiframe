"""Native eager execution must survive pruning, branching and adapter boundaries."""

import duckdb
import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run, verify

import equiframe as ef
from equiframe.adapters import DuckDBAdapter

INT = ef.IntegerType(bits=64, signed=True)


def false_filter(source):
    return ef.Filter(
        node_id="hidden",
        source=source,
        predicate=ef.LiteralExpression(
            value=ef.BooleanValue(value=False), logical_type=ef.BooleanType()
        ),
    )


@pytest.mark.parametrize(
    "guard,empty_left", (("join", False), ("join", True), ("deduplicate", False))
)
@pytest.mark.parametrize("engine", ("pandas", "polars", "duckdb"))
def test_native_guards_survive_later_empty_filter(tmp_path, guard, empty_left, engine):
    if guard == "join":
        inputs = {
            "left": pa.table({"id": pa.array([] if empty_left else [1], type=pa.int64())}),
            "right": pa.table({"id": [1, 1]}),
        }
        schema = contract(
            {"left": [column("id", INT)], "right": [column("id", INT)]},
            [column("id", INT), column("r_id", INT)],
            family="joins",
        )
        nodes = (
            ef.Scan(node_id="l", table="left"),
            ef.Scan(node_id="r", table="right"),
            ef.EquiJoin(
                node_id="guarded",
                left="l",
                right="r",
                how="left",
                keys=(ef.JoinKey(left="id", right="id"),),
                cardinality="many_to_one",
                null_keys="equal",
                right_prefix="r_",
            ),
        )
    else:
        # Duplicate tiebreaks remain forbidden before a later empty filter.
        inputs = {"input": pa.table({"id": [1, 1], "rank": [0, 0]})}
        schema = contract(
            {"input": [column("id", INT), column("rank", INT)]},
            [column("id", INT), column("rank", INT)],
        )
        nodes = (
            ef.Scan(node_id="s", table="input"),
            ef.Deduplicate(
                node_id="guarded",
                source="s",
                keys=("id",),
                keep="first",
                by=(ef.SortKey(column="rank", direction="ascending", nulls="last"),),
            ),
        )
    plan = ef.RelationalPlan(nodes=(*nodes, false_filter("guarded")), output="hidden")
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, inputs, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None
    assert result.problem.stage == ("planning" if engine == "polars" else "transformation")


@pytest.mark.parametrize("empty", (False, True))
def test_shared_checkpoint_remains_available_for_both_branches(tmp_path, empty):
    values = [] if empty else [1, None, 2, 1]
    source = pa.table({"n": pa.array(values, type=pa.int64())})
    schema = contract({"input": [column("n", INT)]}, [column("n", INT)])

    def branch(name, operation):
        return ef.Project(
            node_id=name,
            source="s",
            columns=(
                ef.NamedExpression(
                    name="n",
                    expression=ef.Arithmetic(
                        operation=operation,
                        left=ef.Column(name="n"),
                        right=ef.LiteralExpression(
                            value=ef.IntegerValue(value=1), logical_type=INT, unit="units"
                        ),
                        logical_type=INT,
                        unit="units",
                    ),
                ),
            ),
        )

    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            branch("a", "add"),
            branch("b", "subtract"),
            ef.Concatenate(node_id="u", sources=("a", "b")),
        ),
        output="u",
    )
    expected = pa.table(
        {"n": pa.array([] if empty else [2, None, 3, 2, 0, None, 1, 0], type=pa.int64())}
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)


def simple_plan():
    schema = contract({"input": [column("n", INT)]}, [column("n", INT)])
    plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="s", table="input"),), output="s")
    return plan, schema


def test_non_native_adapter_is_rejected_before_provider_even_without_timestamps(tmp_path):
    plan, schema = simple_plan()
    compiled = ef.native_compiler_registry().resolve("duckdb").compile(plan, schema)
    registry = ef.TransformationRegistry()
    registry.register(compiled.transformation)

    class Provider:
        table_names = ("input",)

        def resolve(self, name, *, context):
            pytest.fail("checkpoint adapter admission must precede provider resolution")

    class Adapter:
        engine = "duckdb"

        def capabilities(self):
            return DuckDBAdapter().capabilities()

        def execute(self, transformation, inputs, context):
            pytest.fail("a non-native adapter cannot consume the compiled checkpoint program")

    result = ef.execute(
        ef.ExecutionPlan(
            contract=schema,
            engine="duckdb",
            transformation_id=compiled.transformation.transformation_id,
        ),
        source=Provider(),
        registry=registry,
        adapter=Adapter(),
        work_dir=tmp_path,
    )
    assert result.state != "completed" and result.output is None
    assert result.problem is not None and result.problem.stage == "preflight"


def test_replaying_only_program_sql_fails_instead_of_bypassing_checkpoints():
    plan, schema = simple_plan()
    compiled = ef.native_compiler_registry().resolve("duckdb").compile(plan, schema)
    with (
        duckdb.connect(":memory:", config={"enable_external_access": False}) as connection,
        pytest.raises(duckdb.Error, match="requires the native DuckDB checkpoint adapter"),
    ):
        connection.execute(compiled.transformation.sql).fetchall()


def test_transport_budget_checks_materialized_intermediate_before_empty_output(tmp_path):
    source = pa.table({"n": [1, 2]})
    schema = contract({"input": [column("n", INT)]}, [column("text", ef.StringType())])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="text",
                        expression=ef.LiteralExpression(
                            value=ef.StringValue(value="x" * 128), logical_type=ef.StringType()
                        ),
                    ),
                ),
            ),
            false_filter("p"),
        ),
        output="hidden",
    )
    compiled = ef.native_compiler_registry().resolve("duckdb").compile(plan, schema)
    registry = ef.TransformationRegistry()
    registry.register(compiled.transformation)
    for limit in (128, 1024):
        result = ef.execute(
            ef.ExecutionPlan(
                contract=schema,
                engine="duckdb",
                transformation_id=compiled.transformation.transformation_id,
                options=ef.ExecutionOptions(max_transport_bytes=limit),
            ),
            source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
            registry=registry,
            work_dir=tmp_path / str(limit),
        )
        if limit == 128:
            assert result.state == "resource_exhausted" and result.output is None
            assert result.problem.stage == "transformation"
        else:
            assert result.state == "completed", result.problem
            assert ef.read_table(result.output.data).num_rows == 0
