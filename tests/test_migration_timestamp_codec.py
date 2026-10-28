"""Installed native IR timestamp transport, DST policies and preflight boundaries."""

from dataclasses import replace
from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import contract, run
from test_migration_product_semantics import timestamp_column
from test_native_timestamp_localization import seconds

import equiframe as ef
from equiframe.migration.backends._timestamp_transport import _TimestampCodec
from equiframe.tables import LoadedTable

ENGINES = ("pandas", "polars", "duckdb")
UNITS = {"s": 1, "ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}


def fixture(unit, zone="America/New_York", mode="earlier", name="t"):
    schema = contract(
        {"input": [timestamp_column(unit, None).model_copy(update={"name": name})]},
        [timestamp_column(unit, zone)],
        family="dates",
    )
    expression = ef.LocalizeTimestamp(argument=ef.Column(name=name), timezone=zone, ambiguous=mode)
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Project(
                node_id="p",
                source="s",
                columns=(ef.NamedExpression(name="t", expression=expression),),
            ),
        ),
        output="p",
    )
    return schema, plan


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("zone", (None, "UTC", "America/New_York"))
@pytest.mark.parametrize("empty", (False, True))
def test_ir_timestamp_transport_keeps_full_int64_domain(tmp_path, engine, unit, zone, empty):
    stamp = timestamp_column(unit, zone)
    schema = contract({"input": [stamp]}, [stamp], family="dates")
    plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="s", table="input"),), output="s")
    ticks = [] if empty else [-(2**63), -1, 0, 1, 2**63 - 1, None, 1]
    source = pa.table({"t": pa.array(ticks, type=pa.timestamp(unit, tz=zone))})
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    observed = ef.read_table(result.output.data)
    assert observed.schema.field("t").type == pa.timestamp(unit, tz=zone)
    assert observed.column("t").cast(pa.int64()).to_pylist() == ticks
    assert source.column("t").cast(pa.int64()).to_pylist() == ticks


@pytest.mark.parametrize("origin,target", list(permutations(ENGINES, 2)))
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("mode", ("earlier", "later"))
def test_native_dst_migration_six_directions_with_literal_expected(
    tmp_path, origin, target, unit, mode
):
    schema, plan = fixture(unit, mode=mode)
    extra = 0 if unit == "s" else 123
    wall = seconds("2024-11-03T01:30:00") * UNITS[unit] + extra
    instant = (1730611800 if mode == "earlier" else 1730615400) * UNITS[unit] + extra
    source = pa.table({"t": pa.array([wall, wall, None], type=pa.timestamp(unit))})
    expected = pa.table(
        {"t": pa.array([instant, instant, None], type=pa.timestamp(unit, tz="America/New_York"))}
    )

    class Source:
        table_names = ("input",)
        calls = 0

        def resolve(self, name, *, context):
            self.calls += 1
            return LoadedTable(source)

    provider = Source()
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine=origin,
            target_engine=target,
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore",
                justification="Generated IR RangeIndex; the Arrow fixture has no logical index.",
            ),
        ),
        source=provider,
        expected=ef.ArrowInput(expected),
        work_dir=tmp_path,
    )
    assert provider.calls == 1
    assert result.complete, result.stages
    assert result.comparison.state == "equivalent"
    assert result.verification_source.state == "equivalent"
    assert result.verification_target.state == "equivalent"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize(
    "zone,wall",
    [
        ("America/New_York", "2024-03-10T02:30:00"),
        ("Pacific/Apia", "2011-12-30T12:00:00"),
        ("America/New_York", "2024-11-03T01:30:00"),
    ],
)
def test_native_dst_gap_or_unapproved_fold_never_completes(tmp_path, engine, unit, zone, wall):
    schema, plan = fixture(unit, zone, mode="reject")
    ticks = [seconds(wall) * UNITS[unit]]
    source = pa.table({"t": pa.array(ticks, type=pa.timestamp(unit))})
    assert ef.native_compiler_registry().resolve(engine).check(plan, schema).supported
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None
    assert source.column("t").cast(pa.int64()).to_pylist() == ticks


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("empty", (False, True))
def test_native_dst_empty_or_null_preserves_type(tmp_path, engine, unit, empty):
    schema, plan = fixture(unit, mode="reject")
    ticks = [] if empty else [None, None]
    source = pa.table({"t": pa.array(ticks, type=pa.timestamp(unit))})
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    observed = ef.read_table(result.output.data)
    assert observed.schema.field("t").type == pa.timestamp(unit, tz="America/New_York")
    assert observed.column("t").cast(pa.int64()).to_pylist() == ticks


@pytest.mark.parametrize("engine", ENGINES)
def test_later_filter_cannot_hide_nonexistent_wall_time(tmp_path, engine):
    schema, initial = fixture("us", mode="reject")
    plan = ef.RelationalPlan(
        nodes=(
            *initial.nodes,
            ef.Filter(
                node_id="f",
                source="p",
                predicate=ef.LiteralExpression(
                    value=ef.BooleanValue(value=False), logical_type=ef.BooleanType()
                ),
            ),
        ),
        output="f",
    )
    check = ef.native_compiler_registry().resolve(engine).check(plan, schema)
    assert check.supported
    source = pa.table(
        {"t": pa.array([seconds("2024-03-10T02:30:00") * 1_000_000], type=pa.timestamp("us"))}
    )
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state != "completed" and result.output is None
    assert result.problem is not None
    assert result.problem.stage == ("planning" if engine == "polars" else "transformation")


@pytest.mark.parametrize("engine", ("polars", "duckdb"))
def test_codec_mismatch_rejects_before_provider_resolution(tmp_path, engine):
    schema, plan = fixture("ns")
    compiled = ef.native_compiler_registry().resolve(engine).compile(plan, schema)
    wrong = replace(compiled.transformation, timestamp_codec=_TimestampCodec())
    registry = ef.TransformationRegistry()
    registry.register(wrong)

    class Unused:
        table_names = ("input",)

        def resolve(self, name, *, context):
            pytest.fail("mismatched codec must fail in preflight")

    result = ef.execute(
        ef.ExecutionPlan(contract=schema, engine=engine, transformation_id=wrong.transformation_id),
        source=Unused(),
        registry=registry,
        work_dir=tmp_path,
    )
    assert result.state != "completed" and result.output is None
    assert result.problem is not None and result.problem.stage == "preflight"


def test_plain_duckdb_transformation_keeps_zoned_ns_boundary(tmp_path):
    stamp = timestamp_column("ns", "UTC")
    schema = contract({"input": [stamp]}, [stamp], family="dates")
    registry = ef.TransformationRegistry()
    registry.register(ef.DuckDBTransformation("plain", "SELECT * FROM input", "fixture-v1"))

    class Unused:
        table_names = ("input",)

        def resolve(self, name, *, context):
            pytest.fail("ordinary DuckDB path must retain its preflight unit boundary")

    result = ef.execute(
        ef.ExecutionPlan(contract=schema, engine="duckdb", transformation_id="plain"),
        source=Unused(),
        registry=registry,
        work_dir=tmp_path,
    )
    assert result.state != "completed" and result.output is None
