"""Compilation checks metadata; migration separately admits actual physical inputs."""

import pyarrow as pa
import pytest
from test_migration_backends import column, contract

import equiframe as ef


def fixture():
    integer = ef.IntegerType(bits=64, signed=True)
    schema = contract({"input": [column("x", integer)]}, [column("x", integer)])
    plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="scan", table="input"),), output="scan")
    return plan, schema, pa.table({"x": pa.array([1.5], type=pa.float64())})


def test_migrate_rejects_wrong_physical_input_before_native_execution(tmp_path):
    plan, schema, physical = fixture()

    class UnusedPandasAdapter(ef.PandasAdapter):
        def execute(self, transformation, inputs, context):
            pytest.fail("migration must reject physical mismatch before either native execution")

    class UnusedDuckDBAdapter(ef.DuckDBAdapter):
        def execute(self, transformation, inputs, context):
            pytest.fail("migration must reject physical mismatch before either native execution")

    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine="pandas",
            target_engine="duckdb",
            require_rules=False,
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(physical)}),
        adapters={"pandas": UnusedPandasAdapter(), "duckdb": UnusedDuckDBAdapter()},
        work_dir=tmp_path,
    )
    assert result.exit_code == 2
    assert not result.complete
    assert result.state == "not_evaluable"
    assert result.stages[1].code == "invalid_input"
    assert result.source is None and result.target is None


def test_direct_compiled_execution_records_native_behavior_without_equivalence(tmp_path):
    plan, schema, physical = fixture()
    compiled = ef.native_compiler_registry().resolve("duckdb").compile(plan, schema)
    registry = ef.TransformationRegistry()
    registry.register(compiled.transformation)
    result = ef.execute(
        ef.ExecutionPlan(
            contract=schema,
            engine="duckdb",
            transformation_id=compiled.transformation.transformation_id,
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(physical)}),
        registry=registry,
        work_dir=tmp_path,
    )
    # Bypassing migrate deliberately omits physical-input admission. DuckDB's
    # own generated BIGINT cast rounds 1.5 to 2; capture must record both facts.
    assert result.state == "completed", result.problem
    assert ef.read_table(result.inputs[0].data).equals(physical)
    assert result.inputs[0].columns[0].arrow_type == "double"
    assert result.output.columns[0].arrow_type == "int64"
    assert ef.read_table(result.output.data).equals(pa.table({"x": pa.array([2], type=pa.int64())}))
    # An ExecutionResult is not an accepted-equivalence assertion result.
    with pytest.raises(ef.EquivalenceInputError, match="result must be a ComparisonResult"):
        ef.assert_equivalent(result)
