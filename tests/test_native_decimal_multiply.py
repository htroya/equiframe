"""Native coefficient products with independent 256-digit Decimal expectations."""

from collections import Counter
from decimal import Decimal, localcontext
from itertools import permutations
from random import Random

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run

import equiframe as ef

ENGINES = ("pandas", "polars", "duckdb")
DIMENSIONS = (
    (19, 1, 19, 1),
    (38, 0, 38, 0),
    (38, 38, 38, 0),
    (38, 19, 38, 19),
    (30, 20, 30, 18),
    (20, 0, 20, 0),
    (12, 2, 17, 3),
)


def fixture(dimensions, coefficients, *, precision=38):
    p1, s1, p2, s2 = dimensions
    left, right = ef.DecimalType(precision=p1, scale=s1), ef.DecimalType(precision=p2, scale=s2)
    output = ef.DecimalType(precision=precision, scale=s1 + s2)
    with localcontext() as ctx:
        ctx.prec = 256
        a = [None if x is None else Decimal(x).scaleb(-s1) for x, _ in coefficients]
        b = [None if y is None else Decimal(y).scaleb(-s2) for _, y in coefficients]
        expected = [
            None if x is None or y is None else (x * y).quantize(Decimal(1).scaleb(-(s1 + s2)))
            for x, y in zip(a, b, strict=True)
        ]
    source = pa.table(
        {"a": pa.array(a, type=pa.decimal128(p1, s1)), "b": pa.array(b, type=pa.decimal128(p2, s2))}
    )
    schema = contract(
        {"input": [column("a", left), column("b", right)]}, [column("product", output)]
    )
    expression = ef.Arithmetic(
        operation="multiply",
        left=ef.Column(name="a"),
        right=ef.Column(name="b"),
        logical_type=output,
        unit="units",
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(ef.NamedExpression(name="product", expression=expression),),
            ),
        ),
        output="p",
    )
    return schema, plan, source, expected


def valid_coefficients(dimensions):
    p1, _, p2, _ = dimensions
    a_max, b_max = 10**p1 - 1, 10**p2 - 1
    pairs = [
        (a_max, 1),
        (-a_max, 1),
        (a_max, -1),
        (0, b_max),
        (1, min(b_max, 10**38 - 1)),
        (None, b_max),
        (a_max, None),
        (None, None),
        (a_max, 0),
    ]
    rng = Random(714)
    for _ in range(32):
        b = rng.randrange(1, min(b_max, 10**10) + 1)
        bound = min(a_max, (10**38 - 1) // b)
        a = rng.randrange(-bound, bound + 1)
        pairs.append((a, b if rng.randrange(2) else -b))
    return [*pairs, pairs[0]]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("dimensions", DIMENSIONS)
@pytest.mark.parametrize("empty", (False, True))
def test_native_decimal_product_preserves_declared_scale_and_multiplicity(
    tmp_path, engine, dimensions, empty
):
    coefficients = [] if empty else valid_coefficients(dimensions)
    schema, plan, source, expected = fixture(dimensions, coefficients)
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    table = ef.read_table(result.output.data)
    assert table.schema.field("product").type == pa.decimal128(38, dimensions[1] + dimensions[3])
    assert Counter(table.column("product").to_pylist()) == Counter(expected)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "a,b,precision",
    [
        (10**38 - 1, 2, 38),
        (-(10**38 - 1), 2, 38),
        (10**19, 10**19, 38),
        (9 * 10**37, 2, 38),
        (999999999999, 2, 12),
    ],
)
def test_native_decimal_product_overflow_never_wraps(tmp_path, engine, a, b, precision):
    schema, plan, source, _ = fixture((38, 0, 38, 0), [(a, b), (None, b)], precision=precision)
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None


@pytest.mark.parametrize("origin,target", list(permutations(ENGINES, 2)))
@pytest.mark.parametrize("dimensions", [(19, 1, 19, 1), (38, 19, 38, 19), (38, 38, 38, 0)])
def test_native_decimal_product_six_directions_verify_independent_expected(
    tmp_path, origin, target, dimensions
):
    schema, plan, source, expected = fixture(dimensions, valid_coefficients(dimensions))
    literal = pa.table(
        {"product": pa.array(expected, type=pa.decimal128(38, dimensions[1] + dimensions[3]))}
    )
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=origin,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated IR RangeIndex"
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        expected=ef.ArrowInput(literal),
        work_dir=tmp_path,
    )
    assert result.complete, result.stages
    assert result.verification_source.state == "equivalent"
    assert result.verification_target.state == "equivalent"


@pytest.mark.parametrize("engine", ("pandas", "polars"))
def test_native_decimal_product_error_is_eager_inside_coalesce(tmp_path, engine):
    schema, base, source, _ = fixture((38, 0, 38, 0), [(10**38 - 1, 2)])
    expression = ef.Coalesce(
        arguments=(
            ef.LiteralExpression(
                value=ef.DecimalValue(value="0"),
                logical_type=ef.DecimalType(precision=38, scale=0),
                unit="units",
            ),
            ef.Column(name="product"),
        )
    )
    plan = ef.RelationalPlan(
        nodes=(
            *base.nodes,
            ef.Project(
                node_id="masked",
                source=base.output,
                columns=(ef.NamedExpression(name="product", expression=expression),),
            ),
        ),
        output="masked",
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
