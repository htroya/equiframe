"""Boundary values must survive native windows, never be repaired for comparison."""

from datetime import date
from decimal import Decimal

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run, verify
from test_migration_product_semantics import timestamp_column

import equiframe as ef

INT = ef.IntegerType(bits=64, signed=True)
ENGINES = ("pandas", "polars", "duckdb")


@pytest.mark.parametrize(
    "dtype,arrow,values",
    [
        (INT, pa.int64(), [2**63 - 1, None, -(2**63)]),
        (ef.StringType(), pa.string(), ["001", None, "á"]),
        (ef.BooleanType(), pa.bool_(), [True, None, False]),
        (ef.DateType(), pa.date32(), [date(2026, 1, 2), None, date(2025, 12, 31)]),
        (ef.FloatType(bits=64), pa.float64(), [float("nan"), None, -0.0]),
        (
            ef.DecimalType(precision=38, scale=2),
            pa.decimal128(38, 2),
            [Decimal("999999999999999999999999999999999999.99"), None, Decimal("-0.01")],
        ),
        (ef.TimestampType(unit="us", timezone="UTC"), pa.timestamp("us", tz="UTC"), [1, None, -1]),
    ],
)
def test_native_lag_preserves_values_and_literal_column_names(tmp_path, dtype, arrow, values):
    if isinstance(dtype, ef.TimestampType):
        value = timestamp_column("us", "UTC").model_copy(update={"name": "*"})
    elif isinstance(dtype, ef.DateType):
        value = ef.ColumnSpec(
            name="*",
            logical_type=dtype,
            nullable=True,
            null_policy=ef.NullPolicy(representations=("null",)),
            temporal_policy=ef.DatePolicy(closed="both"),
        )
    else:
        value = column("*", dtype)
    inputs = [column("sequence", INT), value]
    previous = value.model_copy(update={"name": "_equiframe_window_0", "nullable": True})
    schema = contract({"input": inputs}, [*inputs, previous])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Window(
                node_id="w",
                source="s",
                by=(ef.SortKey(column="sequence", direction="ascending", nulls="last"),),
                measures=(
                    ef.WindowMeasure(
                        name=previous.name, operation="lag", column="*", logical_type=dtype
                    ),
                ),
            ),
        ),
        output="w",
    )
    source = pa.table({"sequence": [1, 2, 3], "*": pa.array(values, type=arrow)})
    expected = pa.table(
        {
            "sequence": [1, 2, 3],
            "*": pa.array(values, type=arrow),
            previous.name: pa.array([None, values[0], None], type=arrow),
        }
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)


def test_global_window_null_order_descending_and_offset(tmp_path):
    inputs = [column("sequence", INT), column("value", ef.StringType())]
    schema = contract(
        {"input": inputs},
        [*inputs, column("previous", ef.StringType()), column("next", ef.StringType())],
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Window(
                node_id="w",
                source="s",
                by=(ef.SortKey(column="sequence", direction="descending", nulls="first"),),
                measures=tuple(
                    ef.WindowMeasure(
                        name=name,
                        operation=operation,
                        column="value",
                        logical_type=ef.StringType(),
                        offset=2,
                    )
                    for name, operation in (("previous", "lag"), ("next", "lead"))
                ),
            ),
        ),
        output="w",
    )
    source = pa.table({"sequence": [2, None, 1, 3], "value": ["two", "null", "one", "three"]})
    expected = pa.table(
        {
            "sequence": [None, 3, 2, 1],
            "value": ["null", "three", "two", "one"],
            "previous": [None, None, "null", "three"],
            "next": ["two", "one", None, None],
        }
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)


def test_window_error_cannot_be_hidden_by_a_filter(tmp_path):
    from test_migration_windows import fixture

    plan, schema, source, _ = fixture()
    filtered = ef.RelationalPlan(
        nodes=(
            *plan.nodes,
            ef.Filter(
                node_id="hidden",
                source="window",
                predicate=ef.LiteralExpression(
                    value=ef.BooleanValue(value=False), logical_type=ef.BooleanType()
                ),
            ),
        ),
        output="hidden",
    )
    assert ef.native_compiler_registry().resolve("duckdb").check(filtered, schema).supported
    tied = pa.concat_tables([source, source.slice(0, 1)])
    for engine in ENGINES:
        result = run(filtered, schema, {"input": tied}, engine, tmp_path)
        assert result.state != "completed"
        assert result.problem is not None
        assert result.problem.stage == ("planning" if engine == "polars" else "transformation")
        if engine == "duckdb":
            continue
        assert result.problem.code == "unsupported_capability"
        assert result.problem.message == "Execution input could not be validated."


@pytest.mark.parametrize(
    "operation,dtype,unit,phrase",
    [
        ("row_number", ef.IntegerType(bits=32, signed=True), "rows", "signed64"),
        ("lag", ef.FloatType(bits=64), "USD", "exact input type"),
        ("lag", ef.DecimalType(precision=12, scale=2), "EUR", "source units"),
    ],
)
def test_invalid_window_semantics_fail_at_compilation(operation, dtype, unit, phrase):
    from test_migration_windows import fixture

    plan, schema, _, _ = fixture()
    measure = ef.WindowMeasure(
        name="invalid",
        operation=operation,
        logical_type=dtype,
        unit=unit,
        column=None if operation == "row_number" else "amount",
    )
    window = ef.Window.model_validate({**plan.nodes[1].model_dump(), "measures": (measure,)})
    changed = ef.RelationalPlan(nodes=(plan.nodes[0], window), output=window.node_id)
    for engine in ENGINES:
        check = ef.native_compiler_registry().resolve(engine).check(changed, schema)
        assert not check.supported
        assert phrase in check.diagnostics[0].message
