"""Independent literal expectations for the 0.12 bounded IR extensions."""

from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run, verify

import equiframe as ef

ENGINES = ("pandas", "polars", "duckdb")


def outer_fixture(how, nulls):
    inputs = {
        "left": pa.table({"key": ["a", "a", "left", None], "l": [1, 2, 3, 4]}),
        "right": pa.table({"key": ["a", "right", None, None], "r": [10, 20, 30, 40]}),
    }
    schema = contract(
        {
            "left": [
                column("key", ef.StringType()),
                column("l", ef.IntegerType(bits=64, signed=True)),
            ],
            "right": [
                column("key", ef.StringType()),
                column("r", ef.IntegerType(bits=64, signed=True)),
            ],
        },
        [
            column("key", ef.StringType()),
            column("l", ef.IntegerType(bits=64, signed=True)),
            column("right.key", ef.StringType()),
            column("right.r", ef.IntegerType(bits=64, signed=True)),
        ],
        family="joins",
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="l", table="left"),
            ef.Scan(node_id="r", table="right"),
            ef.EquiJoin(
                node_id="j",
                left="l",
                right="r",
                keys=(ef.JoinKey(left="key", right="key"),),
                how=how,
                null_keys=nulls,
            ),
        ),
        output="j",
    )
    rows = [("a", 1, "a", 10), ("a", 2, "a", 10), (None, None, "right", 20)]
    if nulls == "equal":
        rows += [(None, 4, None, 30), (None, 4, None, 40)]
    else:
        rows += [(None, None, None, 30), (None, None, None, 40)]
        if how == "full":
            rows += [(None, 4, None, None)]
    if how == "full":
        rows += [("left", 3, None, None)]
    expected = pa.table(
        {
            name: pa.array([row[i] for row in rows], type=kind)
            for i, (name, kind) in enumerate(
                zip(
                    ("key", "l", "right.key", "right.r"),
                    (pa.string(), pa.int64(), pa.string(), pa.int64()),
                    strict=True,
                )
            )
        }
    )
    return inputs, schema, plan, expected


@pytest.mark.parametrize("how", ("right", "full"))
@pytest.mark.parametrize("nulls", ("equal", "never"))
def test_outer_join_preserves_unmatched_nulls_and_multiplicity(tmp_path, how, nulls):
    inputs, schema, plan, expected = outer_fixture(how, nulls)
    verify(plan, schema, inputs, expected, tmp_path)


@pytest.mark.parametrize("origin,target", tuple(permutations(ENGINES, 2)))
def test_full_join_six_directions(tmp_path, origin, target):
    inputs, schema, plan, expected = outer_fixture("full", "never")
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=origin,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated IR index"
            ),
        ),
        source=ef.LocalDataSource({name: ef.ArrowInput(value) for name, value in inputs.items()}),
        expected=ef.ArrowInput(expected),
        work_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert result.verification == "correct"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("cardinality", ("one_to_one", "one_to_many", "many_to_one"))
def test_cardinality_violations_fail_even_when_other_side_empty(tmp_path, engine, cardinality):
    inputs, schema, plan, _ = outer_fixture("full", "never")
    side = "right" if cardinality == "many_to_one" else "left"
    other = "left" if side == "right" else "right"
    inputs[side] = pa.table({"key": ["a", "a"], "l" if side == "left" else "r": [1, 2]})
    inputs[other] = inputs[other].slice(0, 0)
    join = plan.nodes[-1].model_copy(update={"cardinality": cardinality})
    # Construction validates the newly declared option; no model_copy bypass.
    join = ef.EquiJoin.model_validate(join.model_dump())
    plan = ef.RelationalPlan(nodes=(*plan.nodes[:-1], join), output="j")
    result = run(plan, schema, inputs, engine, tmp_path)
    assert result.state != "completed"
    assert result.problem is not None


@pytest.mark.parametrize("engine", ENGINES)
def test_dedup_key_with_total_tiebreak_is_permutation_invariant(tmp_path, engine):
    source = pa.table(
        {
            "id": ["a", "a", "b", None, None],
            "revision": [1, 2, 1, 2, 1],
            "value": ["old", "new", "only", "new-null", "old-null"],
        }
    )
    columns = [
        column("id", ef.StringType()),
        column("revision", ef.IntegerType(bits=64, signed=True)),
        column("value", ef.StringType()),
    ]
    schema = contract({"input": columns}, columns)
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Deduplicate(
                node_id="d",
                source="s",
                keys=("id",),
                keep="first",
                by=(ef.SortKey(column="revision", direction="descending", nulls="last"),),
            ),
        ),
        output="d",
    )
    expected = pa.table(
        {"id": ["a", "b", None], "revision": [2, 1, 2], "value": ["new", "only", "new-null"]}
    )
    for value in (source, source.take(pa.array([4, 3, 2, 1, 0]))):
        result = run(plan, schema, {"input": value}, engine, tmp_path)
        assert result.state == "completed", result.problem
        compared = ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        )
        assert compared.state == "equivalent"
    invalid = pa.table({"id": ["a", "a"], "revision": [2, 2], "value": ["x", "y"]})
    rejected = run(plan, schema, {"input": invalid}, engine, tmp_path)
    assert rejected.state != "completed"


@pytest.mark.parametrize("engine", ENGINES)
def test_decimal_multiply_exact_scale_and_round(tmp_path, engine):
    from decimal import Decimal

    dtype, product = ef.DecimalType(precision=6, scale=3), ef.DecimalType(precision=12, scale=6)
    source = pa.table(
        {"x": pa.array([Decimal("1.245"), Decimal("-1.245"), None], type=pa.decimal128(6, 3))}
    )
    schema = contract({"input": [column("x", dtype)]}, [column("product", product)])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="product",
                        expression=ef.Arithmetic(
                            operation="multiply",
                            left=ef.Column(name="x"),
                            right=ef.Column(name="x"),
                            logical_type=product,
                            unit="units",
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.table(
        {
            "product": pa.array(
                [Decimal("1.550025"), Decimal("1.550025"), None], type=pa.decimal128(12, 6)
            )
        }
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )
    rounded = ef.DecimalType(precision=6, scale=2)
    rounded_schema = contract({"input": [column("x", dtype)]}, [column("rounded", rounded)])
    rounded_plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="rounded",
                        expression=ef.DecimalRound(
                            argument=ef.Column(name="x"),
                            logical_type=rounded,
                            rounding="half_away_from_zero",
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    result = run(rounded_plan, rounded_schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.table(
        {"rounded": pa.array([Decimal("1.25"), Decimal("-1.25"), None], type=pa.decimal128(6, 2))}
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=rounded_schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )


@pytest.mark.parametrize("engine", ENGINES)
def test_decimal_division_declared_scale_and_exact_failure(tmp_path, engine):
    from decimal import Decimal

    dtype = ef.DecimalType(precision=6, scale=2)
    source = pa.table(
        {
            "a": pa.array([Decimal("1.00"), Decimal("2.00"), None], type=pa.decimal128(6, 2)),
            "b": pa.array(
                [Decimal("8.00"), Decimal("3.00"), Decimal("0.00")], type=pa.decimal128(6, 2)
            ),
        }
    )
    schema = contract({"input": [column("a", dtype), column("b", dtype)]}, [column("ratio", dtype)])

    def plan(rounding):
        return ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="s", table="input"),
                ef.Project(
                    node_id="p",
                    source="s",
                    columns=(
                        ef.NamedExpression(
                            name="ratio",
                            expression=ef.Arithmetic(
                                operation="divide",
                                left=ef.Column(name="a"),
                                right=ef.Column(name="b"),
                                logical_type=dtype,
                                unit="units",
                                rounding=rounding,
                            ),
                        ),
                    ),
                ),
            ),
            output="p",
        )

    result = run(plan("half_even"), schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.table(
        {"ratio": pa.array([Decimal("0.12"), Decimal("0.67"), None], type=pa.decimal128(6, 2))}
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )
    result = run(plan("exact"), schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed"
    check = ef.native_compiler_registry().resolve(engine).check(plan("half_even"), schema)
    assert check.supported


def timestamp_column(unit="us", zone="UTC", *, ambiguous="reject"):
    return ef.ColumnSpec(
        name="t",
        logical_type=ef.TimestampType(unit=unit, timezone=zone),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        temporal_policy=ef.TimestampPolicy(
            granularity=unit,
            timezone=zone,
            naive="reject" if zone else "preserve",
            comparison="instant" if zone else "wall_time",
            ambiguous=ambiguous,
            closed="both",
        ),
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "unit,zone",
    [(u, z) for u in ("s", "ms", "us", "ns") for z in (None, "UTC", "America/New_York")],
)
def test_timestamp_ir_exact_unit_zone_transport(tmp_path, engine, unit, zone):
    stamp = timestamp_column(unit, zone)
    schema = contract({"input": [stamp]}, [stamp], family="dates")
    plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="s", table="input"),), output="s")
    compiler = ef.native_compiler_registry().resolve(engine)
    check = compiler.check(plan, schema)
    assert check.supported
    source = pa.table({"t": pa.array([0, 1, -1, None], type=pa.timestamp(unit, tz=zone))})
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(source), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("ambiguous,utc_hour", [("earlier", 5), ("later", 6)])
def test_timestamp_localization_dst_fold_gap_exact(tmp_path, engine, ambiguous, utc_hour):
    from datetime import datetime

    input_column = timestamp_column("ns", None)
    output_column = timestamp_column("ns", "America/New_York")
    schema = contract({"input": [input_column]}, [output_column], family="dates")
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="t",
                        expression=ef.LocalizeTimestamp(
                            argument=ef.Column(name="t"),
                            timezone="America/New_York",
                            ambiguous=ambiguous,
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    source = pa.table(
        {"t": pa.array([datetime(2024, 11, 3, 1, 30), None], type=pa.timestamp("ns"))}
    )
    # Literal POSIX nanoseconds: 2024-11-03 05:30 / 06:30 UTC.
    ticks = 1730611800000000000 if utc_hour == 5 else 1730615400000000000
    expected = pa.table(
        {"t": pa.array([ticks, None], type=pa.timestamp("ns", tz="America/New_York"))}
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )
    gap = pa.table({"t": pa.array([datetime(2024, 3, 10, 2, 30)], type=pa.timestamp("ns"))})
    assert run(plan, schema, {"input": gap}, engine, tmp_path).state != "completed"
    reject_expr = ef.LocalizeTimestamp(
        argument=ef.Column(name="t"), timezone="America/New_York", ambiguous="reject"
    )
    reject_plan = ef.RelationalPlan(
        nodes=(
            plan.nodes[0],
            ef.Project(
                node_id="p",
                source="s",
                columns=(ef.NamedExpression(name="t", expression=reject_expr),),
            ),
        ),
        output="p",
    )
    assert run(reject_plan, schema, {"input": source}, engine, tmp_path).state != "completed"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("how", ("inner", "left", "right", "full", "semi", "anti"))
@pytest.mark.parametrize("nulls", ("equal", "never"))
@pytest.mark.parametrize(
    "cardinality", ("one_to_one", "one_to_many", "many_to_one", "many_to_many")
)
def test_join_cardinality_composite_key_option_matrix(tmp_path, engine, how, nulls, cardinality):
    inputs = {
        "left": pa.table({"a": ["a", "a", None, None], "b": [1, 2, 1, 1]}),
        "right": pa.table({"a": ["a", None, None], "b": [1, 1, 1]}),
    }
    base = [column("a", ef.StringType()), column("b", ef.IntegerType(bits=64, signed=True))]
    output = (
        base
        if how in ("semi", "anti")
        else [*base, *[c.model_copy(update={"name": "right." + c.name}) for c in base]]
    )
    schema = contract({"left": base, "right": base}, output, family="joins")
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="l", table="left"),
            ef.Scan(node_id="r", table="right"),
            ef.EquiJoin(
                node_id="j",
                left="l",
                right="r",
                keys=(ef.JoinKey(left="a", right="a"), ef.JoinKey(left="b", right="b")),
                how=how,
                null_keys=nulls,
                cardinality=cardinality,
            ),
        ),
        output="j",
    )
    result = run(plan, schema, inputs, engine, tmp_path)
    if nulls == "equal" and cardinality != "many_to_many":
        assert result.state != "completed"
    else:
        assert result.state == "completed", result.problem
        # Counts specified directly for this fixed bag, not computed with an engine.
        expected_rows = {
            "equal": {"inner": 5, "left": 6, "right": 5, "full": 6, "semi": 3, "anti": 1},
            "never": {"inner": 1, "left": 4, "right": 3, "full": 6, "semi": 1, "anti": 3},
        }
        assert result.output.row_count == expected_rows[nulls][how]


@pytest.mark.parametrize("engine", ENGINES)
def test_decimal_product_and_round_overflow_are_failures(tmp_path, engine):
    from decimal import Decimal

    dtype = ef.DecimalType(precision=5, scale=2)
    source = pa.table({"x": pa.array([Decimal("99.99")], type=pa.decimal128(5, 2))})
    for expression, output_type in (
        (
            ef.Arithmetic(
                operation="multiply",
                left=ef.Column(name="x"),
                right=ef.Column(name="x"),
                logical_type=ef.DecimalType(precision=5, scale=4),
                unit="units",
            ),
            ef.DecimalType(precision=5, scale=4),
        ),
        (
            ef.DecimalRound(
                argument=ef.Column(name="x"),
                logical_type=ef.DecimalType(precision=2, scale=0),
                rounding="half_away_from_zero",
            ),
            ef.DecimalType(precision=2, scale=0),
        ),
    ):
        schema = contract({"input": [column("x", dtype)]}, [column("x", output_type)])
        plan = ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="s", table="input"),
                ef.Project(
                    node_id="p",
                    source="s",
                    columns=(ef.NamedExpression(name="x", expression=expression),),
                ),
            ),
            output="p",
        )
        assert run(plan, schema, {"input": source}, engine, tmp_path).state != "completed"


def test_new_default_fields_preserve_historical_canonical_ir():
    import hashlib
    import json

    document = {
        "schema_version": "1.0",
        "nodes": [
            {"kind": "scan", "node_id": "l", "table": "left"},
            {"kind": "scan", "node_id": "r", "table": "right"},
            {
                "kind": "join",
                "node_id": "j",
                "left": "l",
                "right": "r",
                "keys": [{"left": "k", "right": "k"}],
                "how": "left",
                "null_keys": "never",
                "right_prefix": "right.",
            },
            {
                "kind": "deduplicate",
                "node_id": "d",
                "source": "j",
                "keys": ["k", "right.k"],
                "keep": "identical",
                "nulls": "equal",
            },
        ],
        "output": "d",
    }
    plan = ef.RelationalPlan.model_validate_json(json.dumps(document))
    assert plan.model_dump(mode="json") == document
    assert (
        ef.ir_fingerprint(plan)
        == hashlib.sha256(
            json.dumps(
                document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()
    )
    arithmetic = {
        "kind": "arithmetic",
        "operation": "add",
        "left": {"kind": "column", "name": "a"},
        "right": {"kind": "column", "name": "b"},
        "logical_type": {"kind": "integer", "bits": 64, "signed": True},
        "unit": "units",
        "overflow": "reject",
    }
    assert (
        ef.Arithmetic.model_validate_json(json.dumps(arithmetic)).model_dump(mode="json")
        == arithmetic
    )


@pytest.mark.parametrize("nulls", ("equal", "never"))
@pytest.mark.parametrize("engine", ENGINES)
def test_full_join_both_typed_inputs_empty(tmp_path, nulls, engine):
    inputs, schema, plan, _ = outer_fixture("full", nulls)
    join = ef.EquiJoin(
        node_id="j",
        left="l",
        right="r",
        how="full",
        null_keys=nulls,
        keys=(ef.JoinKey(left="key", right="key"), ef.JoinKey(left="l", right="r")),
    )
    plan = ef.RelationalPlan(nodes=(*plan.nodes[:-1], join), output="j")
    inputs = {name: pa.Table.from_pylist([], schema=table.schema) for name, table in inputs.items()}
    result = run(plan, schema, inputs, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.Table.from_pylist(
        [],
        schema=pa.schema(
            [
                pa.field("key", pa.string()),
                pa.field("l", pa.int64()),
                pa.field("right.key", pa.string()),
                pa.field("right.r", pa.int64()),
            ]
        ),
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "p1,s1,p2,s2,expected_text",
    [
        (15, 2, 15, 3, "9999999999999980000000000.00001"),
        (18, 0, 18, 0, "999999999999999998000000000000000001"),
    ],
)
def test_decimal_multiply_valid_max_coefficients(tmp_path, engine, p1, s1, p2, s2, expected_text):
    from decimal import Decimal

    left_type, right_type = (
        ef.DecimalType(precision=p1, scale=s1),
        ef.DecimalType(precision=p2, scale=s2),
    )
    output_type = ef.DecimalType(precision=p1 + p2, scale=s1 + s2)
    source = pa.table(
        {
            "a": pa.array([Decimal(f"{10**p1 - 1}e-{s1}")], type=pa.decimal128(p1, s1)),
            "b": pa.array([Decimal(f"{10**p2 - 1}e-{s2}")], type=pa.decimal128(p2, s2)),
        }
    )
    schema = contract(
        {"input": [column("a", left_type), column("b", right_type)]},
        [column("product", output_type)],
    )
    expression = ef.Arithmetic(
        operation="multiply",
        left=ef.Column(name="a"),
        right=ef.Column(name="b"),
        logical_type=output_type,
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
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.table(
        {"product": pa.array([Decimal(expected_text)], type=pa.decimal128(p1 + p2, s1 + s2))}
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )


@pytest.mark.parametrize("engine", ENGINES)
def test_timestamp_localization_never_silently_changes_int64_min_to_null(tmp_path, engine):
    schema = contract(
        {"input": [timestamp_column("ns", None)]}, [timestamp_column("ns", "UTC")], family="dates"
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="t",
                        expression=ef.LocalizeTimestamp(
                            argument=ef.Column(name="t"), timezone="UTC", ambiguous="reject"
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    source = pa.table(
        {"t": pa.array([-(2**63), -(2**63) + 1, None, 2**63 - 1], type=pa.timestamp("ns"))}
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    if engine == "pandas":
        assert result.state != "completed"
    else:
        assert result.state == "completed", result.problem
        expected = pa.table(
            {
                "t": pa.array(
                    [-(2**63), -(2**63) + 1, None, 2**63 - 1], type=pa.timestamp("ns", tz="UTC")
                )
            }
        )
        assert (
            ef.compare(
                result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
            ).state
            == "equivalent"
        )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "zone,ticks", [("America/New_York", 2**63 - 1), ("Europe/Berlin", -(2**63) + 1)]
)
def test_timestamp_localization_overflow_never_wraps(tmp_path, engine, zone, ticks):
    schema = contract(
        {"input": [timestamp_column("ns", None)]}, [timestamp_column("ns", zone)], family="dates"
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="t",
                        expression=ef.LocalizeTimestamp(
                            argument=ef.Column(name="t"), timezone=zone, ambiguous="reject"
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    source = pa.table({"t": pa.array([ticks], type=pa.timestamp("ns"))})
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed"
    assert source.column("t").cast(pa.int64()).to_pylist() == [ticks]


@pytest.mark.parametrize("origin,target", list(permutations(ENGINES, 2)))
def test_shared_timestamp_wrap_cannot_become_equivalent_migration(tmp_path, origin, target):
    schema = contract(
        {"input": [timestamp_column("ns", None)]},
        [timestamp_column("ns", "Etc/GMT-1")],
        family="dates",
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="t",
                        expression=ef.LocalizeTimestamp(
                            argument=ef.Column(name="t"), timezone="Etc/GMT-1", ambiguous="reject"
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    source = pa.table({"t": pa.array([-(2**63) + 1], type=pa.timestamp("ns"))})
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=origin,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated IR index"
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        work_dir=tmp_path,
    )
    # Even identical wrong native outputs must not pass the no-expected-output gate.
    if result.complete or result.exit_code == 0 or result.state == "equivalent":
        raise RuntimeError("Shared int64 timestamp overflow was falsely accepted")
    assert result.state == "not_evaluable"


@pytest.mark.parametrize(
    "rounding,expected_text",
    [("exact", "0.125"), ("half_even", "0.12"), ("half_away_from_zero", "0.13")],
)
@pytest.mark.parametrize("engine", ENGINES)
def test_decimal_division_exact_and_rounding_values(tmp_path, rounding, expected_text, engine):
    from decimal import Decimal

    dtype = ef.DecimalType(precision=6, scale=3)
    output = ef.DecimalType(precision=6, scale=3 if rounding == "exact" else 2)
    source = pa.table(
        {
            "a": pa.array([Decimal("1.000"), None], type=pa.decimal128(6, 3)),
            "b": pa.array([Decimal("8.000"), Decimal("0.000")], type=pa.decimal128(6, 3)),
        }
    )
    schema = contract(
        {"input": [column("a", dtype), column("b", dtype)]}, [column("ratio", output)]
    )
    expr = ef.Arithmetic(
        operation="divide",
        left=ef.Column(name="a"),
        right=ef.Column(name="b"),
        logical_type=output,
        unit="units",
        rounding=rounding,
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(ef.NamedExpression(name="ratio", expression=expr),),
            ),
        ),
        output="p",
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.table(
        {"ratio": pa.array([Decimal(expected_text), None], type=pa.decimal128(6, output.scale))}
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )
    invalid = source.set_column(
        1, "b", pa.array([Decimal("0.000"), Decimal("0.000")], type=pa.decimal128(6, 3))
    )
    assert run(plan, schema, {"input": invalid}, engine, tmp_path).state != "completed"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "rounding,expected_text", [("half_even", "1.24"), ("half_away_from_zero", "1.25")]
)
def test_decimal_round_all_modes_native(tmp_path, engine, rounding, expected_text):
    from decimal import Decimal

    dtype, output = ef.DecimalType(precision=6, scale=3), ef.DecimalType(precision=6, scale=2)
    source = pa.table(
        {"x": pa.array([Decimal("1.245"), Decimal("-1.245"), None], type=pa.decimal128(6, 3))}
    )
    schema = contract({"input": [column("x", dtype)]}, [column("x", output)])
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="x",
                        expression=ef.DecimalRound(
                            argument=ef.Column(name="x"), logical_type=output, rounding=rounding
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    expected = pa.table(
        {
            "x": pa.array(
                [Decimal(expected_text), Decimal("-" + expected_text), None],
                type=pa.decimal128(6, 2),
            )
        }
    )
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )


def test_native_metadata_boundaries_remain_explicit(tmp_path):
    from decimal import Decimal

    dtype, output = ef.DecimalType(precision=19, scale=1), ef.DecimalType(precision=38, scale=2)
    schema = contract({"input": [column("x", dtype)]}, [column("x", output)])
    expr = ef.Arithmetic(
        operation="multiply",
        left=ef.Column(name="x"),
        right=ef.Column(name="x"),
        logical_type=output,
        unit="units",
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p", source="s", columns=(ef.NamedExpression(name="x", expression=expr),)
            ),
        ),
        output="p",
    )
    check = ef.native_compiler_registry().resolve("polars").check(plan, schema)
    assert check.supported
    source = pa.table(
        {"x": pa.array([Decimal("999999999999999999.9"), None], type=pa.decimal128(19, 1))}
    )
    expected = pa.table(
        {
            "x": pa.array(
                [Decimal("999999999999999999800000000000000000.01"), None],
                type=pa.decimal128(38, 2),
            )
        }
    )
    for engine in ENGINES:
        assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
        result = run(plan, schema, {"input": source}, engine, tmp_path / engine)
        assert result.state == "completed", result.problem
        assert ef.read_table(result.output.data).equals(expected)
    schema = contract(
        {"input": [timestamp_column("us", None)]}, [timestamp_column("us", "UTC")], family="dates"
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(
                    ef.NamedExpression(
                        name="t",
                        expression=ef.LocalizeTimestamp(
                            argument=ef.Column(name="t"), timezone="UTC", ambiguous="reject"
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    check = ef.native_compiler_registry().resolve("duckdb").check(plan, schema)
    assert check.supported


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("direction", ("ascending", "descending"))
@pytest.mark.parametrize("nulls", ("first", "last"))
def test_dedup_tiebreak_direction_and_null_placement(tmp_path, engine, direction, nulls):
    source = pa.table(
        {
            "id": ["001", "001", "001", "001", None, None],
            "rank": [None, 1, 1, 2, 2, 1],
            "seq": [0, 3, 1, 0, 0, 0],
            "value": ["null", "one3", "one1", "two", "n2", "n1"],
        }
    )
    cols = [
        column("id", ef.StringType()),
        column("rank", ef.IntegerType(bits=64, signed=True)),
        column("seq", ef.IntegerType(bits=64, signed=True)),
        column("value", ef.StringType()),
    ]
    schema = contract({"input": cols}, cols)
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Deduplicate(
                node_id="d",
                source="s",
                keys=("id",),
                keep="first",
                by=(
                    ef.SortKey(column="rank", direction=direction, nulls=nulls),
                    ef.SortKey(column="seq", direction="ascending", nulls="last"),
                ),
            ),
        ),
        output="d",
    )
    rank, value = (
        (None, "null")
        if nulls == "first"
        else (1, "one1")
        if direction == "ascending"
        else (2, "two")
    )
    null_rank = 1 if direction == "ascending" else 2
    expected = pa.table(
        {
            "id": pa.array(["001", None], type=pa.string()),
            "rank": pa.array([rank, null_rank], type=pa.int64()),
            "seq": pa.array([1 if value == "one1" else 0, 0], type=pa.int64()),
            "value": [value, "n1" if direction == "ascending" else "n2"],
        }
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    assert (
        ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        ).state
        == "equivalent"
    )
