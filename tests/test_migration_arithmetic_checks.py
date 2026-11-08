"""Each declared arithmetic range is checked before its value can be consumed."""

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef
from equiframe.contracts import BooleanType, IntegerType
from equiframe.migration.ports import native_compiler_registry
from equiframe.migration.types import (
    Arithmetic,
    Column,
    Compare,
    Filter,
    IsNull,
    LiteralExpression,
    NamedExpression,
    Project,
    RelationalPlan,
    Scan,
)
from equiframe.migration.validation import compilation_identity, validate_ir
from equiframe.values import IntegerValue, NullValue

INT8 = IntegerType(bits=8, signed=True)
ENGINES = ("pandas", "polars", "duckdb")


def fixture(kind):
    def literal(value):
        return LiteralExpression(logical_type=INT8, value=IntegerValue(value=value), unit="units")

    addition = Arithmetic(
        operation="add",
        left=Column(name="x"),
        right=literal(1),
        logical_type=INT8,
        unit="units",
    )
    if kind == "direct":
        expression = addition
    elif kind == "nested":
        expression = Arithmetic(
            operation="subtract", left=addition, right=addition, logical_type=INT8, unit="units"
        )
    elif kind == "nested_null":
        expression = Arithmetic(
            operation="add",
            left=addition,
            right=LiteralExpression(logical_type=INT8, value=NullValue(), unit="units"),
            logical_type=INT8,
            unit="units",
        )
    elif kind == "null_test":
        expression = IsNull(argument=addition)
    else:
        expression = Compare(operation="eq", left=addition, right=literal(0))
    node = (
        Filter(node_id="result", source="scan", predicate=expression)
        if kind == "filter"
        else Project(
            node_id="result",
            source="scan",
            columns=(NamedExpression(name="x", expression=expression),),
        )
    )
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"), node), output="result")
    output_type = INT8 if kind in ("direct", "nested", "nested_null", "filter") else BooleanType()
    schema = contract({"input": [column("x", INT8)]}, [column("x", output_type)])
    return plan, schema


@pytest.mark.parametrize("kind", ("nested", "nested_null"))
@pytest.mark.parametrize("engine", ENGINES)
def test_nested_arithmetic_checks_intermediate_overflow_before_cancellation(kind, engine, tmp_path):
    plan, schema = fixture(kind)
    result = run(
        plan,
        schema,
        {"input": pa.table({"x": pa.array([127], type=pa.int8())})},
        engine,
        tmp_path,
    )
    # The inner 127+1 cannot fit int8, even if subtraction or NULL hides its value.
    assert result.state != "completed"
    assert result.output is None


@pytest.mark.parametrize("engine", ENGINES)
def test_nested_arithmetic_keeps_valid_boundary_and_null_results(engine, tmp_path):
    plan, schema = fixture("nested")
    result = run(
        plan,
        schema,
        {"input": pa.table({"x": pa.array([-128, 126, None], type=pa.int8())})},
        engine,
        tmp_path,
    )
    assert result.state == "completed", result.problem
    assert ef.read_table(result.output.data).equals(
        pa.table({"x": pa.array([0, 0, None], type=pa.int8())})
    )


@pytest.mark.parametrize("engine", ENGINES)
def test_direct_arithmetic_preserves_native_support_and_exact_boundary_values(engine, tmp_path):
    plan, schema = fixture("direct")
    compiled = native_compiler_registry().resolve(engine).compile(plan, schema)
    previous_identity, _, _ = compilation_identity(validate_ir(plan, schema), engine)
    compiler_revision = {"pandas": "v4", "polars": "v14", "duckdb": "v9"}[engine]
    assert compiled.transformation.code_version == (
        f"migration-native-ir1.0/{engine}/product-semantics-{compiler_revision}"
    )
    assert compiled.transformation.transformation_id != previous_identity
    result = run(
        plan,
        schema,
        {"input": pa.table({"x": pa.array([-128, 126, None], type=pa.int8())})},
        engine,
        tmp_path,
    )
    assert result.state == "completed", result.problem
    assert ef.read_table(result.output.data).equals(
        pa.table({"x": pa.array([-127, 127, None], type=pa.int8())})
    )


@pytest.mark.parametrize("kind", ("filter", "comparison", "null_test"))
@pytest.mark.parametrize("engine", ENGINES)
def test_arithmetic_predicates_cannot_conceal_overflow(kind, engine, tmp_path):
    plan, schema = fixture(kind)
    result = run(
        plan,
        schema,
        {"input": pa.table({"x": pa.array([127], type=pa.int8())})},
        engine,
        tmp_path,
    )
    assert result.state != "completed"
    assert result.output is None


@pytest.mark.parametrize("kind", ("filter", "comparison", "null_test"))
@pytest.mark.parametrize("engine", ENGINES)
def test_arithmetic_predicates_preserve_valid_values_and_unknown(kind, engine, tmp_path):
    plan, schema = fixture(kind)
    result = run(
        plan,
        schema,
        {"input": pa.table({"x": pa.array([-1, 126, None], type=pa.int8())})},
        engine,
        tmp_path,
    )
    assert result.state == "completed", result.problem
    expected = {
        "filter": pa.array([-1], type=pa.int8()),
        "comparison": pa.array([True, False, None], type=pa.bool_()),
        "null_test": pa.array([False, False, True], type=pa.bool_()),
    }[kind]
    assert ef.read_table(result.output.data).equals(pa.table({"x": expected}))


@pytest.mark.parametrize("kind", ("filter", "comparison", "null_test", "nested", "nested_null"))
@pytest.mark.parametrize("source,target", (("pandas", "duckdb"), ("duckdb", "pandas")))
def test_duckdb_nested_and_predicate_migration_verifies_expected(kind, source, target, tmp_path):
    plan, schema = fixture(kind)
    checked = native_compiler_registry().resolve("duckdb").check(plan, schema)
    assert checked.supported
    expected = {
        "filter": pa.array([-1], type=pa.int8()),
        "comparison": pa.array([True, False, None], type=pa.bool_()),
        "null_test": pa.array([False, False, True], type=pa.bool_()),
        "nested": pa.array([0, 0, None], type=pa.int8()),
        "nested_null": pa.array([None, None, None], type=pa.int8()),
    }[kind]
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=source,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="IR RangeIndex is not part of the Arrow fixture"
            ),
        ),
        source=ef.LocalDataSource(
            {"input": ef.ArrowInput(pa.table({"x": pa.array([-1, 126, None], type=pa.int8())}))}
        ),
        expected=ef.ArrowInput(pa.table({"x": expected})),
        work_dir=tmp_path,
    )
    assert result.complete, result.stages
    assert result.verification_source.state == "equivalent"
    assert result.verification_target.state == "equivalent"
