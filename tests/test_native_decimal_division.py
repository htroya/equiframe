"""Literal quotient expectations, exact failures and adversarial native names."""

from collections import Counter
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from itertools import permutations
from random import Random

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef

ENGINES = ("pandas", "polars", "duckdb")
CASES = (
    ("12.30", "2.00", 4, 2, 4, 2, 12, 2, "exact", "6.15"),
    ("6.67", "2.00", 4, 2, 4, 2, 12, 2, "half_even", "3.34"),
    ("6.69", "2.00", 4, 2, 4, 2, 12, 2, "half_even", "3.34"),
    ("-6.69", "2.00", 4, 2, 4, 2, 12, 2, "half_away_from_zero", "-3.35"),
    ("1", "-3", 1, 0, 1, 0, 12, 2, "half_even", "-0.33"),
    ("9" * 38, "1", 38, 0, 1, 0, 38, 0, "exact", "9" * 38),
    ("0." + "0" * 37 + "1", "1", 38, 38, 1, 0, 38, 0, "half_even", "0"),
    ("1", "10", 1, 0, 2, 0, 38, 38, "exact", "0.1" + "0" * 37),
    (
        "0." + "0" * 37 + "1",
        "0." + "0" * 37 + "1",
        38,
        38,
        38,
        38,
        12,
        2,
        "exact",
        "1.00",
    ),
    ("9" * 37 + "8", "9" * 38, 38, 0, 38, 0, 38, 38, "half_even", "0." + "9" * 38),
    ("99.9", "1", 3, 1, 1, 0, 2, 0, "half_even", None),
    ("1", "3", 1, 0, 1, 0, 12, 2, "exact", None),
    ("1", "0", 1, 0, 1, 0, 12, 2, "exact", None),
    ("999", "1", 3, 0, 1, 0, 2, 0, "exact", None),
    ("0." + "0" * 37 + "1", "1", 38, 38, 1, 0, 38, 0, "exact", None),
    ("1", "0." + "0" * 37 + "1", 1, 0, 38, 38, 38, 38, "half_even", None),
)

PANDAS_FAILURES = {
    ("99.9", "1"): "CapabilityError",
    ("1", "3"): "Inexact",
    ("1", "0"): "DivisionByZero",
    ("999", "1"): "CapabilityError",
    ("0." + "0" * 37 + "1", "1"): "Inexact",
    ("1", "0." + "0" * 37 + "1"): "CapabilityError",
}


def fixture(case, names=("a", "b"), *, empty=False):
    a, b, ap, asc, bp, bsc, precision, scale, rounding, _ = case
    left_type = ef.DecimalType(precision=ap, scale=asc)
    right_type = ef.DecimalType(precision=bp, scale=bsc)
    output_type = ef.DecimalType(precision=precision, scale=scale)
    schema = contract(
        {"input": [column(names[0], left_type), column(names[1], right_type)]},
        [column("ratio", output_type)],
    )
    source = pa.table(
        {
            names[0]: pa.array(
                [] if empty else [Decimal(a), Decimal(a), None], type=pa.decimal128(ap, asc)
            ),
            names[1]: pa.array(
                [] if empty else [Decimal(b), Decimal(b), Decimal(0)], type=pa.decimal128(bp, bsc)
            ),
        }
    )
    expression = ef.Arithmetic(
        operation="divide",
        left=ef.Column(name=names[0]),
        right=ef.Column(name=names[1]),
        logical_type=output_type,
        unit="units",
        rounding=rounding,
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="project",
                source="scan",
                columns=(ef.NamedExpression(name="ratio", expression=expression),),
            ),
        ),
        output="project",
    )
    return plan, schema, source, output_type


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("case", CASES)
def test_native_decimal_quotient_preserves_exactness_and_failure(tmp_path, engine, case):
    plan, schema, source, output_type = fixture(case)
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    if case[-1] is None:
        assert result.state != "completed" and result.output is None
        assert result.problem is not None
        expected_failure = (
            "InvalidInputException"
            if engine == "duckdb"
            else PANDAS_FAILURES[(case[0], case[1])]
            if engine == "pandas"
            else "CapabilityError"
        )
        assert result.problem.exception_type == expected_failure
    else:
        assert result.state == "completed", result.problem
        table = ef.read_table(result.output.data)
        assert table.schema.field("ratio").type == pa.decimal128(
            output_type.precision, output_type.scale
        )
        assert table.to_pylist() == [
            {"ratio": Decimal(case[-1])},
            {"ratio": Decimal(case[-1])},
            {"ratio": None},
        ]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "names",
    (
        ("q", "b"),
        ("_equiframe_decimal_division_a0", "_equiframe_decimal_division__b"),
        ('a"quote', "^.*$"),
    ),
)
def test_native_division_does_not_shadow_logical_input_names(tmp_path, engine, names):
    plan, schema, source, _ = fixture(CASES[0], names)
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert ef.read_table(result.output.data).to_pylist() == [
        {"ratio": Decimal("6.15")},
        {"ratio": Decimal("6.15")},
        {"ratio": None},
    ]


@pytest.mark.parametrize("engine", ENGINES)
def test_native_division_empty_input_does_not_invent_a_zero_division(tmp_path, engine):
    plan, schema, source, _ = fixture(CASES[0], empty=True)
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert ef.read_table(result.output.data).num_rows == 0


@pytest.mark.parametrize("source_engine,target_engine", tuple(permutations(ENGINES, 2)))
@pytest.mark.parametrize("case", (CASES[0], CASES[3]))
def test_decimal_division_migrates_in_all_six_directions(
    tmp_path, source_engine, target_engine, case
):
    plan, schema, data, dtype = fixture(case)
    expected = pa.table(
        {
            "ratio": pa.array(
                [Decimal(case[-1]), Decimal(case[-1]), None],
                type=pa.decimal128(dtype.precision, dtype.scale),
            )
        }
    )
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=source_engine,
            target_engine=target_engine,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated indexes are not a declared key"
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(data)}),
        expected=ef.ArrowInput(expected),
        work_dir=tmp_path,
    )
    assert result.complete and result.exit_code == 0
    assert result.state == "equivalent" and result.verification == "correct"
    for child, engine in ((result.source, source_engine), (result.target, target_engine)):
        assert child.execution.plan.engine == engine
        actual = ef.read_table(child.execution.output.data)
        assert actual.schema.field("ratio").type == expected.schema.field("ratio").type
        assert Counter(actual["ratio"].to_pylist()) == Counter(expected["ratio"].to_pylist())


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rounding", ("half_even", "half_away_from_zero"))
@pytest.mark.parametrize(
    "scales", ((0, 0, 38), (38, 38, 12), (38, 0, 0), (0, 38, 0), (38, 0, 38), (0, 0, 0))
)
def test_native_quotients_match_an_independent_high_precision_oracle(
    tmp_path, engine, rounding, scales
):
    left_scale, right_scale, output_scale = scales
    plan, schema, _, _ = fixture(
        ("1", "1", 38, left_scale, 38, right_scale, 38, output_scale, rounding, None),
        empty=True,
    )
    generator = Random(73014 + left_scale + 100 * right_scale + 10000 * output_scale)
    pairs = []

    def decimal_from_coefficient(coefficient, scale):
        # Construct all 38 digits without the ambient Decimal precision of 28.
        return Decimal((int(coefficient < 0), tuple(map(int, str(abs(coefficient)))), -scale))

    for _ in range(32):
        if scales in ((0, 0, 38), (38, 38, 12)):
            b = generator.randrange(10**37, 10**38)
            a = generator.randrange(1, b)
        elif scales == (0, 38, 0):
            a = generator.randrange(1, 10**18)
            b = generator.randrange(10**37, 10**38)
        else:
            a = generator.randrange(1, 10**38)
            b = generator.randrange(1, 10)
        a *= generator.choice((-1, 1))
        b *= generator.choice((-1, 1))
        pairs.append(
            (decimal_from_coefficient(a, left_scale), decimal_from_coefficient(b, right_scale))
        )
    pairs += [pairs[0], (None, Decimal(0)), (Decimal(0), None), (None, None)]
    expected = []
    with localcontext() as context:
        context.prec = 256
        quantum = Decimal((0, (1,), -output_scale))
        mode = ROUND_HALF_EVEN if rounding == "half_even" else ROUND_HALF_UP
        for a, b in pairs:
            expected.append(
                None if a is None or b is None else (a / b).quantize(quantum, rounding=mode)
            )
    data = pa.table(
        {
            "a": pa.array([a for a, _ in pairs], type=pa.decimal128(38, left_scale)),
            "b": pa.array([b for _, b in pairs], type=pa.decimal128(38, right_scale)),
        }
    )
    result = run(plan, schema, {"input": data}, engine, tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.schema.field("ratio").type == pa.decimal128(38, output_scale)
    assert Counter(actual["ratio"].to_pylist()) == Counter(expected)
