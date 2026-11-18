"""Independent literal expected rows exercise genuine native window execution."""

from decimal import Decimal
from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run, verify

import equiframe as ef

ENGINES = ("pandas", "polars", "duckdb")
DEC = ef.DecimalType(precision=12, scale=2)
INT = ef.IntegerType(bits=64, signed=True)


def fixture(partition=True):
    source = pa.table(
        {
            "group": ["a", "a", "a", None, None],
            "sequence": pa.array([2, 1, 3, 2, 1], type=pa.int64()),
            "amount": pa.array(
                [None, Decimal("1.20"), Decimal("2.30"), Decimal("7.00"), None],
                type=pa.decimal128(12, 2),
            ),
        }
    )
    inputs = [
        column("group", ef.StringType()),
        column("sequence", INT),
        column("amount", DEC, unit="USD"),
    ]
    output = [
        *inputs,
        column("position", INT, nullable=False, unit="rows"),
        column("previous", DEC, unit="USD"),
        column("next", DEC, unit="USD"),
    ]
    schema = contract({"input": inputs}, output)
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Window(
                node_id="window",
                source="scan",
                partition_by=("group",) if partition else (),
                by=(ef.SortKey(column="sequence", direction="ascending", nulls="last"),),
                measures=(
                    ef.WindowMeasure(
                        name="position", operation="row_number", logical_type=INT, unit="rows"
                    ),
                    ef.WindowMeasure(
                        name="previous", operation="lag", column="amount", logical_type=DEC
                    ),
                    ef.WindowMeasure(
                        name="next", operation="lead", column="amount", logical_type=DEC
                    ),
                ),
            ),
        ),
        output="window",
    )
    expected = pa.table(
        {
            "group": ["a", "a", "a", None, None],
            "sequence": [1, 2, 3, 1, 2],
            "amount": pa.array(
                [Decimal("1.20"), None, Decimal("2.30"), None, Decimal("7.00")],
                type=pa.decimal128(12, 2),
            ),
            "position": [1, 2, 3, 1, 2],
            "previous": pa.array(
                [None, Decimal("1.20"), None, None, None], type=pa.decimal128(12, 2)
            ),
            "next": pa.array(
                [None, Decimal("2.30"), None, Decimal("7.00"), None], type=pa.decimal128(12, 2)
            ),
        }
    )
    return plan, schema, source, expected


@pytest.mark.parametrize("order", [(0, 1, 2, 3, 4), (4, 2, 0, 3, 1)])
def test_partitioned_windows_preserve_exact_money_nulls_and_permutation(tmp_path, order):
    plan, schema, source, expected = fixture()
    verify(plan, schema, {"input": source.take(list(order))}, expected, tmp_path)


@pytest.mark.parametrize("engine", ENGINES)
def test_window_ties_are_errors_even_when_rows_are_identical(tmp_path, engine):
    plan, schema, source, _ = fixture()
    result = run(
        plan, schema, {"input": pa.concat_tables([source, source.slice(0, 1)])}, engine, tmp_path
    )
    assert result.state != "completed"
    # Native exceptions are intentionally redacted by the execution boundary.
    assert result.problem is not None
    assert result.problem.exception_type in ("CapabilityError", "InvalidInputException")


@pytest.mark.parametrize("engine", ENGINES)
def test_empty_partitioned_window_keeps_declared_types(tmp_path, engine):
    plan, schema, source, _ = fixture()
    result = run(plan, schema, {"input": source.slice(0, 0)}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert ef.read_table(result.output.data).num_rows == 0


@pytest.mark.parametrize("source_engine,target_engine", tuple(permutations(ENGINES, 2)))
def test_six_migration_directions_verify_windows_against_literal_expected(
    tmp_path, source_engine, target_engine
):
    plan, schema, source, expected = fixture()
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=source_engine,
            target_engine=target_engine,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore",
                justification="The declared relational bag has no native index identity.",
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        expected=ef.ArrowInput(expected),
        work_dir=tmp_path,
    )
    assert result.state == "equivalent", result
    assert result.verification == "correct"


def test_window_does_not_allow_type_or_unit_repair():
    plan, schema, _, _ = fixture()
    window = plan.nodes[1]
    wrong = window.measures[1].model_copy(update={"logical_type": ef.FloatType(bits=64)})
    modified = plan.model_copy(
        update={
            "nodes": (
                plan.nodes[0],
                window.model_copy(
                    update={"measures": (window.measures[0], wrong, window.measures[2])}
                ),
            )
        }
    )
    for engine in ENGINES:
        check = ef.native_compiler_registry().resolve(engine).check(modified, schema)
        assert not check.supported
        assert "exact input type" in check.diagnostics[0].message
