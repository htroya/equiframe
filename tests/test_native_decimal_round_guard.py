"""Regressions for checked native DecimalRound and exact native error classification."""

from decimal import Decimal

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run
from test_native_decimal_rounding import fixture, plan
from test_native_tzif_timezone import capture_failures

import equiframe as ef
from equiframe.values import BooleanValue, DecimalValue

ENGINES = ("pandas", "polars", "duckdb")
ROUNDING = ("half_even", "half_away_from_zero")
MAXIMUM_38_18 = "99999999999999999999.999999999999999999"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", ROUNDING)
@pytest.mark.parametrize("sign", ("", "-"))
def test_round_38_digit_carry_rejects_declared_output_before_native_panic(
    tmp_path, monkeypatch, engine, rounding, sign
):
    value = Decimal(sign + MAXIMUM_38_18)
    schema, source, output = fixture([value, None, value], 38, 18, 1, 1)
    failures = capture_failures(monkeypatch)
    result = run(plan(output, rounding), schema, {"input": source}, engine, tmp_path)
    assert result.output is None and result.state != "completed"
    assert result.problem is not None
    assert len(failures) == 1
    native_error = failures[0]
    message = str(native_error)
    diagnostic = (type(native_error).__module__, type(native_error).__qualname__, message)
    conversion = engine == "duckdb" and rounding == "half_away_from_zero"
    expected_type = "CapabilityError"
    if engine == "duckdb":
        expected_type = "ConversionException" if conversion else "InvalidInputException"
    assert result.problem.exception_type == expected_type, diagnostic
    assert type(native_error).__name__ == expected_type, diagnostic
    if conversion:
        expected_message = (
            f'Conversion Error: Casting value "{sign}100000000000000000000.0" '
            "to type DECIMAL(1,1) failed: value is out of range!"
        )
        assert message.splitlines()[0] == expected_message, diagnostic
    else:
        assert (
            message
            == {
                "pandas": "IR output exceeds declared numeric range: decimal_round",
                "polars": "Polars Decimal division: output precision exceeded",
                "duckdb": "Invalid Input Error: Decimal division: output precision exceeded",
            }[engine]
        ), diagnostic


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", ROUNDING)
@pytest.mark.parametrize("sign", ("", "-"))
def test_round_38_digit_carry_keeps_valid_wider_destination_and_nulls(
    tmp_path, engine, rounding, sign
):
    value = Decimal(sign + MAXIMUM_38_18)
    schema, source, output = fixture([value, None, value], 38, 18, 38, 1)
    original = source.to_pylist()
    result = run(plan(output, rounding), schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert result.output is not None
    table = ef.read_table(result.output.data)
    assert table.schema.field("rounded").type == pa.decimal128(38, 1)
    expected = Decimal(sign + "100000000000000000000.0")
    assert table.column("rounded").to_pylist() == [expected, None, expected]
    assert source.to_pylist() == original


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", ROUNDING)
def test_round_even_odd_halfway_signs_and_duplicates_use_literal_expectations(
    tmp_path, engine, rounding
):
    texts = ["9.85", "-9.85", "9.75", "-9.75", "0.05", "-0.05", "0.00", None, None, "9.85"]
    values = [None if value is None else Decimal(value) for value in texts]
    wanted = {
        "half_even": ["9.8", "-9.8", "9.8", "-9.8", "0.0", "0.0", "0.0", None, None, "9.8"],
        "half_away_from_zero": [
            "9.9",
            "-9.9",
            "9.8",
            "-9.8",
            "0.1",
            "-0.1",
            "0.0",
            None,
            None,
            "9.9",
        ],
    }[rounding]
    schema, source, output = fixture(values, 4, 2, 3, 1)
    result = run(plan(output, rounding), schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert result.output is not None
    table = ef.read_table(result.output.data)
    assert table.schema.field("rounded").type == pa.decimal128(3, 1)
    assert table.column("rounded").to_pylist() == [
        None if value is None else Decimal(value) for value in wanted
    ]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", ROUNDING)
@pytest.mark.parametrize("values", ([], [None, None, None]), ids=("empty", "all-null"))
def test_round_checked_path_does_not_invent_overflow_for_absent_values(
    tmp_path, engine, rounding, values
):
    schema, source, output = fixture(values, 38, 18, 1, 1)
    result = run(plan(output, rounding), schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert result.output is not None
    table = ef.read_table(result.output.data)
    assert table.schema.field("rounded").type == pa.decimal128(1, 1)
    assert table.column("rounded").to_pylist() == values


@pytest.mark.parametrize("rounding", ROUNDING)
def test_round_invalid_intermediate_cannot_be_hidden_by_later_empty_filter(
    tmp_path, monkeypatch, rounding
):
    schema, source, output = fixture([Decimal(MAXIMUM_38_18), None], 38, 18, 1, 1)
    initial = plan(output, rounding)
    ir = ef.RelationalPlan(
        nodes=(
            *initial.nodes,
            ef.Filter(
                node_id="drop",
                source=initial.output,
                predicate=ef.LiteralExpression(
                    logical_type=ef.BooleanType(), value=BooleanValue(value=False)
                ),
            ),
        ),
        output="drop",
    )
    failures = capture_failures(monkeypatch)
    result = run(ir, schema, {"input": source}, "polars", tmp_path)
    assert result.output is None and result.state != "completed"
    assert result.problem is not None
    assert result.problem.exception_type == "CapabilityError"
    assert len(failures) == 1 and type(failures[0]) is ef.CapabilityError
    assert str(failures[0]) == "Polars Decimal division: output precision exceeded"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", ROUNDING)
def test_round_preparation_preserves_nested_round_and_exact_division_sibling(
    tmp_path, engine, rounding
):
    input_type = ef.DecimalType(precision=38, scale=18)
    rounded_type = ef.DecimalType(precision=6, scale=2)
    outer_type = ef.DecimalType(precision=6, scale=1)
    exact_type = ef.DecimalType(precision=6, scale=3)
    source = pa.table(
        {"x": pa.array([Decimal("1.245"), Decimal("-1.245"), None], type=pa.decimal128(38, 18))}
    )
    schema = contract(
        {"input": [column("x", input_type)]},
        [column("rounded", rounded_type), column("outer", outer_type), column("exact", exact_type)],
    )
    rounded = ef.DecimalRound(
        argument=ef.Column(name="x"), logical_type=rounded_type, rounding=rounding
    )
    exact = ef.Arithmetic(
        operation="divide",
        left=ef.Column(name="x"),
        right=ef.LiteralExpression(
            logical_type=ef.DecimalType(precision=1, scale=0),
            value=DecimalValue(value="1"),
            unit="units",
        ),
        logical_type=exact_type,
        unit="units",
        rounding="exact",
    )
    ir = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(name="rounded", expression=rounded),
                    ef.NamedExpression(
                        name="outer",
                        expression=ef.DecimalRound(
                            argument=rounded, logical_type=outer_type, rounding=rounding
                        ),
                    ),
                    ef.NamedExpression(name="exact", expression=exact),
                ),
            ),
        ),
        output="p",
    )
    result = run(ir, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert result.output is not None
    table = ef.read_table(result.output.data)
    assert [field.type for field in table.schema] == [
        pa.decimal128(6, 2),
        pa.decimal128(6, 1),
        pa.decimal128(6, 3),
    ]
    two_places = "1.24" if rounding == "half_even" else "1.25"
    one_place = "1.2" if rounding == "half_even" else "1.3"
    assert table.to_pylist() == [
        {"rounded": Decimal(two_places), "outer": Decimal(one_place), "exact": Decimal("1.245")},
        {
            "rounded": Decimal("-" + two_places),
            "outer": Decimal("-" + one_place),
            "exact": Decimal("-1.245"),
        },
        {"rounded": None, "outer": None, "exact": None},
    ]


@pytest.mark.parametrize("rounding", ROUNDING)
@pytest.mark.parametrize("output_precision", (1, 38), ids=("invalid", "valid"))
def test_round_direct_filter_predicate_has_checked_native_rounding(
    tmp_path, monkeypatch, rounding, output_precision
):
    source_type = ef.DecimalType(precision=38, scale=18)
    rounded_type = ef.DecimalType(precision=output_precision, scale=1)
    values = [Decimal(MAXIMUM_38_18), Decimal("-" + MAXIMUM_38_18), None, Decimal(MAXIMUM_38_18)]
    source = pa.table({"x": pa.array(values, type=pa.decimal128(38, 18))})
    schema = contract({"input": [column("x", source_type)]}, [column("x", source_type)])
    ir = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Filter(
                node_id="f",
                source="s",
                predicate=ef.Compare(
                    operation="gt",
                    left=ef.DecimalRound(
                        argument=ef.Column(name="x"),
                        logical_type=rounded_type,
                        rounding=rounding,
                    ),
                    right=ef.LiteralExpression(
                        logical_type=rounded_type,
                        value=DecimalValue(value="0.0"),
                        unit="units",
                    ),
                ),
            ),
        ),
        output="f",
    )
    failures = capture_failures(monkeypatch)
    result = run(ir, schema, {"input": source}, "polars", tmp_path)
    if output_precision == 1:
        assert result.output is None and result.state != "completed"
        assert result.problem is not None and result.problem.exception_type == "CapabilityError"
        assert len(failures) == 1 and type(failures[0]) is ef.CapabilityError
        assert str(failures[0]) == "Polars Decimal division: output precision exceeded"
    else:
        assert result.state == "completed", result.problem
        assert failures == [] and result.output is not None
        actual = ef.read_table(result.output.data)
        assert actual.schema.field("x").type == pa.decimal128(38, 18)
        assert actual.column("x").to_pylist() == [values[0], values[0]]


@pytest.mark.parametrize("rounding", ROUNDING)
def test_round_native_temporary_style_source_name_preserves_valid_carry(tmp_path, rounding):
    name = "_equiframe_round_0_result"
    value = Decimal(MAXIMUM_38_18)
    schema, source, output = fixture([value, None, value], 38, 18, 38, 1, name=name)
    result = run(plan(output, rounding, name=name), schema, {"input": source}, "polars", tmp_path)
    assert result.state == "completed", result.problem
    assert result.output is not None
    actual = ef.read_table(result.output.data)
    assert actual.schema.field("rounded").type == pa.decimal128(38, 1)
    assert actual.column("rounded").to_pylist() == [
        Decimal("100000000000000000000.0"),
        None,
        Decimal("100000000000000000000.0"),
    ]
    assert source.column_names == [name]
    assert source.column(name).to_pylist() == [value, None, value]
