"""Native integer arithmetic against independent arbitrary-precision Python integers."""

import operator
from collections import Counter
from itertools import permutations
from random import Random

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef

ENGINES = ("pandas", "polars", "duckdb")
OPERATIONS = {"add": operator.add, "subtract": operator.sub, "multiply": operator.mul}


def bounds(bits, signed):
    return (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1) if signed else (0, 2**bits - 1)


def arrow_type(bits, signed):
    return getattr(pa, ("int" if signed else "uint") + str(bits))()


def expected(operation, left, right):
    return None if left is None or right is None else OPERATIONS[operation](left, right)


def valid_pairs(operation, bits, signed):
    low, high = bounds(bits, signed)
    pairs = [(0, 0), (0, 1), (1, 0), (1, 1), (high, 0), (high, 1), (low, 0), (low, 1)]
    if signed:
        pairs.extend([(-1, -1), (-1, 1), (low, -1), (high, -1), (high, low)])
    rng = Random(814)
    for _ in range(32):
        left = rng.randint(low, high)
        right = rng.randint(max(low, -3), 3) if operation == "multiply" else rng.randint(low, high)
        pairs.append((left, right))
    pairs = [(a, b) for a, b in pairs if low <= OPERATIONS[operation](a, b) <= high]
    return [*pairs, pairs[0], (None, high), (high, None), (None, None)]


def overflow_pair(operation, bits, signed, which):
    low, high = bounds(bits, signed)
    pairs = {
        "add": [(high, 1), (low, -1) if signed else (high, high)],
        "subtract": [(low, 1), (high, -1) if signed else (0, high)],
        "multiply": [(low, -1) if signed else (high, 2), (high, 2) if signed else (high, high)],
    }
    pair = pairs[operation][which]
    assert all(low <= value <= high for value in pair)
    assert not low <= OPERATIONS[operation](*pair) <= high
    return pair


def fixture(operation, bits, signed, pairs):
    dtype = ef.IntegerType(bits=bits, signed=signed)
    schema = contract({"input": [column("a", dtype), column("b", dtype)]}, [column("n", dtype)])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="n",
                        expression=ef.Arithmetic(
                            operation=operation,
                            left=ef.Column(name="a"),
                            right=ef.Column(name="b"),
                            logical_type=dtype,
                            unit="units",
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    source = pa.table(
        {
            "a": pa.array([a for a, _ in pairs], type=arrow_type(bits, signed)),
            "b": pa.array([b for _, b in pairs], type=arrow_type(bits, signed)),
        }
    )
    values = [expected(operation, a, b) for a, b in pairs]
    return plan, schema, source, values


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("bits", (8, 16, 32, 64))
@pytest.mark.parametrize("signed", (False, True))
@pytest.mark.parametrize("mode", ("values", "empty", "null"))
def test_native_integer_results_preserve_exact_width_and_bag(
    tmp_path, engine, operation, bits, signed, mode
):
    pairs = (
        []
        if mode == "empty"
        else [(None, None), (None, None)]
        if mode == "null"
        else valid_pairs(operation, bits, signed)
    )
    plan, schema, source, values = fixture(operation, bits, signed, pairs)
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.schema.field("n").type == arrow_type(bits, signed)
    assert Counter(actual.column("n").to_pylist()) == Counter(values)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("bits", (8, 16, 32, 64))
@pytest.mark.parametrize("signed", (False, True))
@pytest.mark.parametrize("which", (0, 1))
def test_native_integer_overflow_never_wraps_or_rounds(
    tmp_path, engine, operation, bits, signed, which
):
    plan, schema, source, _ = fixture(
        operation, bits, signed, [overflow_pair(operation, bits, signed, which), (None, None)]
    )
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None


@pytest.mark.parametrize("origin,target", list(permutations(ENGINES, 2)))
@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("bits", (8, 16, 32, 64))
@pytest.mark.parametrize("signed", (False, True))
def test_integer_six_directions_verify_independent_expected(
    tmp_path, origin, target, operation, bits, signed
):
    plan, schema, source, values = fixture(
        operation, bits, signed, valid_pairs(operation, bits, signed)
    )
    literal = pa.table({"n": pa.array(values, type=arrow_type(bits, signed))})
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=origin,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore",
                justification="Generated IR RangeIndex; Arrow fixture has no logical index",
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        expected=ef.ArrowInput(literal),
        work_dir=tmp_path,
    )
    assert result.complete, result.stages
    assert result.verification_source.state == "equivalent"
    assert result.verification_target.state == "equivalent"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("signed", (False, True))
def test_integer_overflow_precedes_later_filter(tmp_path, engine, operation, signed):
    base, schema, source, _ = fixture(
        operation, 64, signed, [overflow_pair(operation, 64, signed, 0)]
    )
    plan = ef.RelationalPlan(
        nodes=(
            *base.nodes,
            ef.Filter(
                node_id="filtered",
                source=base.output,
                predicate=ef.LiteralExpression(
                    value=ef.BooleanValue(value=False), logical_type=ef.BooleanType()
                ),
            ),
        ),
        output="filtered",
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None
    if engine != "duckdb":
        assert result.problem.exception_type == "CapabilityError"
    else:
        assert result.problem.stage == "transformation"
