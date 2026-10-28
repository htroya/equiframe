"""Factory must retain its declared identity through genuine native execution."""

from itertools import permutations

import pyarrow as pa
import pytest
from test_migration_backends import contract, run
from test_migration_product_semantics import timestamp_column

import equiframe as ef
from equiframe import _timezones

ENGINES = ("pandas", "polars", "duckdb")


def fixture(unit, ambiguity):
    schema = contract(
        {"input": [timestamp_column(unit, None)]},
        [timestamp_column(unit, "Factory")],
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
                            argument=ef.Column(name="t"),
                            timezone="Factory",
                            ambiguous=ambiguity,
                        ),
                    ),
                ),
            ),
        ),
        output="p",
    )
    # Independent literal zero-offset expectations: negative/subsecond ticks,
    # repeated rows and NULL must survive without a zone rename in the output.
    ticks = [-1, 0, 1, 947937600, 1721044800, 1, None]
    source = pa.table({"t": pa.array(ticks, type=pa.int64()).cast(pa.timestamp(unit))})
    expected = pa.table(
        {"t": pa.array(ticks, type=pa.int64()).cast(pa.timestamp(unit, tz="Factory"))}
    )
    return plan, schema, source, expected


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("unit", ("s", "ms", "us", "ns"))
@pytest.mark.parametrize("ambiguity", ("reject", "earlier", "later"))
def test_factory_native_localization_keeps_ticks_nulls_duplicates_and_zone(
    tmp_path, engine, unit, ambiguity
):
    plan, schema, source, expected = fixture(unit, ambiguity)
    result = run(plan, schema, {"input": source}, engine, tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.schema.field("t").type == pa.timestamp(unit, tz="Factory")
    assert (
        actual.column("t").cast(pa.int64()).to_pylist()
        == expected.column("t").cast(pa.int64()).to_pylist()
    )


@pytest.mark.parametrize("origin,target", tuple(permutations(ENGINES, 2)))
@pytest.mark.parametrize("unit", ("s", "ms", "us", "ns"))
def test_factory_six_direction_migration_retains_declared_schema(tmp_path, origin, target, unit):
    plan, schema, source, expected = fixture(unit, "reject")
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
        expected=ef.ArrowInput(expected),
        work_dir=tmp_path,
    )
    assert result.state == "equivalent"
    assert result.verification == "correct"
    assert result.exit_code == 0


def test_factory_resource_change_is_not_silently_treated_as_zero_offset(monkeypatch):
    class ChangedFactory:
        def joinpath(self, name):
            assert name == "Factory"
            return self

        def read_bytes(self):
            # A resource with another offset must never enter the UTC kernel.
            return b"changed installed Factory timezone"

    monkeypatch.setattr(_timezones, "files", lambda package: ChangedFactory())
    with pytest.raises(ValueError, match="verified fixed-zero TZif"):
        _timezones.native_timezone_key("Factory")
    assert _timezones.native_timezone_key("America/Guayaquil") == "America/Guayaquil"
    assert _timezones.native_timezone_key("Etc/GMT+3") == "Etc/GMT+3"
