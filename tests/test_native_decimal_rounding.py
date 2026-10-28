"""Decimal tie, coefficient and scale boundaries against independent expectations."""

from collections import Counter
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from random import Random

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef

ENGINES = ("pandas", "polars", "duckdb")
MODES = ("half_even", "half_away_from_zero")


def fixture(values, precision, scale, output_precision, output_scale, name="x"):
    dtype = ef.DecimalType(precision=precision, scale=scale)
    output = ef.DecimalType(precision=output_precision, scale=output_scale)
    schema = contract({"input": [column(name, dtype)]}, [column("rounded", output)])
    source = pa.table({name: pa.array(values, type=pa.decimal128(precision, scale))})
    return schema, source, output


def plan(output, rounding, name="x"):
    return ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="rounded",
                        expression=ef.DecimalRound(
                            argument=ef.Column(name=name), logical_type=output, rounding=rounding
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )


def expected(values, scale, mode):
    with localcontext() as context:
        context.prec = 256
        quantum = Decimal(1).scaleb(-scale)
        rounding = ROUND_HALF_EVEN if mode == "half_even" else ROUND_HALF_UP
        return [
            None if value is None else value.quantize(quantum, rounding=rounding)
            for value in values
        ]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", MODES)
@pytest.mark.parametrize(
    "input_scale,output_scale", [(3, 2), (1, 0), (38, 0), (38, 37), (38, 38), (0, 0)]
)
def test_native_rounding_large_coefficients_and_seeded_oracle(
    tmp_path, engine, rounding, input_scale, output_scale
):
    rng = Random(714)
    coefficients = [10**38 - 1, -(10**38 - 1), 0, 5, -5, 15, -15, 25, -25]
    if input_scale:
        factor = 10 ** (input_scale - output_scale)
        if factor > 1:
            ties = [
                factor // 2,
                -factor // 2,
                factor + factor // 2,
                -(factor + factor // 2),
            ]
            coefficients += [value for value in ties if abs(value) < 10**38]
    coefficients += [rng.randrange(-(10**37), 10**37) for _ in range(48)]
    with localcontext() as context:
        context.prec = 256
        values = [Decimal(value).scaleb(-input_scale) for value in coefficients]
    values += [values[3], None, None]
    schema, source, output = fixture(values, 38, input_scale, 38, output_scale)
    ir = plan(output, rounding)
    assert ef.native_compiler_registry().resolve(engine).check(ir, schema).supported
    result = run(ir, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    table = ef.read_table(result.output.data)
    assert table.schema.field("rounded").type == pa.decimal128(38, output_scale)
    assert Counter(table.column("rounded").to_pylist()) == Counter(
        expected(values, output_scale, rounding)
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", MODES)
@pytest.mark.parametrize("name", ["x", "_equiframe_decimal_division_q", 'q";select', "^.*$"])
def test_native_rounding_empty_and_literal_names(tmp_path, engine, rounding, name):
    for position, values in enumerate(
        ([], [Decimal("1.245"), Decimal("1.255"), Decimal("-1.245"), None])
    ):
        schema, source, output = fixture(values, 6, 3, 6, 2, name)
        result = run(
            plan(output, rounding, name),
            schema,
            {"input": source},
            engine,
            tmp_path / str(position),
        )
        assert result.state == "completed", result.problem
        table = ef.read_table(result.output.data)
        assert table.schema.field("rounded").type == pa.decimal128(6, 2)
        assert table.column("rounded").to_pylist() == expected(values, 2, rounding)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", MODES)
@pytest.mark.parametrize(
    "value", ["9999999999999999999999999999999999999.5", "-9999999999999999999999999999999999999.5"]
)
def test_native_rounding_carry_overflow_is_failure(tmp_path, engine, rounding, value):
    schema, source, output = fixture([Decimal(value), None], 38, 1, 37, 0)
    result = run(plan(output, rounding), schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None
