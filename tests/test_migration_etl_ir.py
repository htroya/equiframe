"""ETL additions execute independently in all engines and migration directions."""

from decimal import Decimal
from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run, verify

import equiframe as ef
from equiframe.contracts import (
    BooleanType,
    DecimalType,
    IntegerType,
    StringType,
    TimestampPolicy,
    TimestampType,
)
from equiframe.migration.runner import migrate
from equiframe.migration.runner_types import MigrationSpec
from equiframe.migration.types import (
    Arithmetic,
    Coalesce,
    Column,
    Concatenate,
    Conditional,
    Deduplicate,
    EquiJoin,
    JoinKey,
    LiteralExpression,
    NamedExpression,
    Project,
    RelationalPlan,
    Scan,
)
from equiframe.values import IntegerValue

ENGINES = ("pandas", "polars", "duckdb")
INT = IntegerType(bits=32, signed=True)
WIDE = IntegerType(bits=64, signed=True)


def arithmetic_fixture():
    source = pa.table(
        {
            "id": ["001", "002", "003"],
            "x": pa.array([2, None, -4], type=pa.int32()),
            "y": pa.array([3, 5, None], type=pa.int32()),
            "ok": [True, None, False],
        }
    )
    schema = contract(
        {
            "input": [
                column("id", StringType()),
                column("x", INT),
                column("y", INT),
                column("ok", BooleanType()),
            ]
        },
        [
            column("renamed", StringType()),
            column("product", WIDE),
            column("fill", INT),
            column("choice", INT),
        ],
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="s", table="input"),
            Project(
                node_id="p",
                source="s",
                columns=(
                    NamedExpression(name="renamed", expression=Column(name="id")),
                    NamedExpression(
                        name="product",
                        expression=Arithmetic(
                            operation="multiply",
                            left=Column(name="x"),
                            right=Column(name="y"),
                            logical_type=WIDE,
                            unit="units",
                        ),
                    ),
                    NamedExpression(
                        name="fill",
                        expression=Coalesce(arguments=(Column(name="x"), Column(name="y"))),
                    ),
                    NamedExpression(
                        name="choice",
                        expression=Conditional(
                            predicate=Column(name="ok"),
                            then=Column(name="x"),
                            otherwise=Column(name="y"),
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    expected = pa.table(
        {
            "renamed": ["001", "002", "003"],
            "product": pa.array([6, None, None], type=pa.int64()),
            "fill": pa.array([2, 5, -4], type=pa.int32()),
            "choice": pa.array([2, 5, None], type=pa.int32()),
        }
    )
    return source, schema, plan, expected


def test_arithmetic_coalesce_conditional_and_projection_expected(tmp_path):
    source, schema, plan, expected = arithmetic_fixture()
    verify(plan, schema, {"input": source}, expected, tmp_path)


@pytest.mark.parametrize("origin,target", tuple(permutations(ENGINES, 2)))
def test_etl_expression_all_six_migration_directions(tmp_path, origin, target):
    source, schema, plan, expected = arithmetic_fixture()
    result = migrate(
        MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=origin,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="IR generated RangeIndex is not a logical key"
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        expected=ef.ArrowInput(expected),
        work_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert result.verification == "correct"
    assert result.source.execution.plan.engine == origin
    assert result.target.execution.plan.engine == target


def test_decimal_guard_digit_addition_is_exact(tmp_path):
    dec = DecimalType(precision=10, scale=2)
    wider = DecimalType(precision=11, scale=2)
    source = pa.table(
        {
            "a": pa.array([Decimal("0.10"), None], type=pa.decimal128(10, 2)),
            "b": pa.array([Decimal("0.20"), Decimal("2.00")], type=pa.decimal128(10, 2)),
        }
    )
    schema = contract(
        {"input": [column("a", dec, unit="USD"), column("b", dec, unit="USD")]},
        [column("amount", wider, unit="USD")],
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="s", table="input"),
            Project(
                node_id="p",
                source="s",
                columns=(
                    NamedExpression(
                        name="amount",
                        expression=Arithmetic(
                            operation="add",
                            left=Column(name="a"),
                            right=Column(name="b"),
                            logical_type=wider,
                            unit="USD",
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    verify(
        plan,
        schema,
        {"input": source},
        pa.table({"amount": pa.array([Decimal("0.30"), None], type=pa.decimal128(11, 2))}),
        tmp_path,
    )


@pytest.mark.parametrize("engine", ENGINES)
def test_integer_overflow_is_failure_not_wrapped_success(tmp_path, engine):
    source = pa.table({"x": pa.array([2**31 - 1], type=pa.int32())})
    schema = contract({"input": [column("x", INT)]}, [column("x", INT)])
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="s", table="input"),
            Project(
                node_id="p",
                source="s",
                columns=(
                    NamedExpression(
                        name="x",
                        expression=Arithmetic(
                            operation="add",
                            left=Column(name="x"),
                            right=LiteralExpression(
                                logical_type=INT, value=IntegerValue(value=1), unit="units"
                            ),
                            logical_type=INT,
                            unit="units",
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed"


def test_concatenate_preserves_and_dedup_requires_explicit_all_columns(tmp_path):
    source = pa.table({"id": ["001", "001", "002"], "n": [1, 1, 2]})
    schema = contract(
        {
            "left": [column("id", StringType()), column("n", WIDE)],
            "right": [column("id", StringType()), column("n", WIDE)],
        },
        [column("id", StringType()), column("n", WIDE)],
    )
    nodes = (
        Scan(node_id="l", table="left"),
        Scan(node_id="r", table="right"),
        Concatenate(node_id="u", sources=("l", "r")),
    )
    verify(
        RelationalPlan(nodes=nodes, output="u"),
        schema,
        {"left": source, "right": source},
        pa.concat_tables([source, source]),
        tmp_path,
    )
    verify(
        RelationalPlan(
            nodes=(*nodes, Deduplicate(node_id="d", source="u", keys=("id", "n"))), output="d"
        ),
        schema,
        {"left": source, "right": source},
        pa.table({"id": ["001", "002"], "n": [1, 2]}),
        tmp_path,
    )
    incomplete = RelationalPlan(
        nodes=(*nodes, Deduplicate(node_id="d", source="u", keys=("id",))), output="d"
    )
    assert all(
        not ef.native_compiler_registry().resolve(engine).check(incomplete, schema).supported
        for engine in ENGINES
    )


@pytest.mark.parametrize(
    "how,nulls,expected_ids",
    [
        ("semi", "equal", ["a", "b", "n"]),
        ("semi", "never", ["a", "b"]),
        ("anti", "equal", ["c"]),
        ("anti", "never", ["n", "c"]),
    ],
)
def test_native_semi_anti_keep_left_multiplicity(tmp_path, how, nulls, expected_ids):
    left = pa.table({"id": ["a", "b", "n", "c"], "key": ["01", "01", None, "02"]})
    right = pa.table({"key": ["01", "01", None]})
    schema = contract(
        {
            "left": [column("id", StringType()), column("key", StringType())],
            "right": [column("key", StringType())],
        },
        [column("id", StringType()), column("key", StringType())],
        family="joins",
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="l", table="left"),
            Scan(node_id="r", table="right"),
            EquiJoin(
                node_id="j",
                left="l",
                right="r",
                keys=(JoinKey(left="key", right="key"),),
                how=how,
                null_keys=nulls,
            ),
        ),
        output="j",
    )
    expected = pa.table(
        {
            "id": expected_ids,
            "key": [{"a": "01", "b": "01", "n": None, "c": "02"}[id] for id in expected_ids],
        }
    )
    verify(plan, schema, {"left": left, "right": right}, expected, tmp_path)


def test_error_bearing_arithmetic_cannot_be_pruned_by_later_project(tmp_path):
    source, schema, plan, expected = arithmetic_fixture()
    # All final names still match, but an intermediate arithmetic value is prunable.
    suffix = Project(
        node_id="last",
        source="p",
        columns=tuple(
            NamedExpression(name=column.name, expression=Column(name=column.name))
            for column in schema.output.schema_spec.columns
        ),
    )
    appended = RelationalPlan(nodes=(*plan.nodes, suffix), output="last")
    check = ef.native_compiler_registry().resolve("duckdb").check(appended, schema)
    assert check.supported
    verify(appended, schema, {"input": source}, expected, tmp_path)


@pytest.mark.parametrize("how", ("right", "full"))
def test_right_full_require_both_sides_in_output_contract(how):
    schema = contract(
        {"left": [column("key", StringType())], "right": [column("key", StringType())]},
        [column("key", StringType())],
        family="joins",
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="l", table="left"),
            Scan(node_id="r", table="right"),
            EquiJoin(
                node_id="j",
                left="l",
                right="r",
                keys=(JoinKey(left="key", right="key"),),
                how=how,
                null_keys="never",
            ),
        ),
        output="j",
    )
    for engine in ENGINES:
        check = ef.native_compiler_registry().resolve(engine).check(plan, schema)
        assert not check.supported
        assert "output names/order" in check.diagnostics[0].message


def test_zoned_nanosecond_timestamp_ir_has_per_engine_support(tmp_path):
    stamp = column("t", StringType()).model_copy(
        update={
            "logical_type": TimestampType(unit="ns", timezone="UTC"),
            "temporal_policy": TimestampPolicy(
                granularity="ns",
                timezone="UTC",
                naive="reject",
                comparison="instant",
                ambiguous="reject",
                closed="both",
            ),
        }
    )
    schema = contract({"input": (stamp,)}, (stamp,), family="dates")
    plan = RelationalPlan(nodes=(Scan(node_id="s", table="input"),), output="s")
    source = pa.table(
        {"t": pa.array([0, 1, -1, None, 2**63 - 1], type=pa.timestamp("ns", tz="UTC"))}
    )
    for engine in ENGINES:
        check = ef.native_compiler_registry().resolve(engine).check(plan, schema)
        assert check.supported
        result = run(plan, schema, {"input": source}, engine, tmp_path / engine)
        assert result.state == "completed", result.problem
        assert ef.read_table(result.output.data).equals(source)
