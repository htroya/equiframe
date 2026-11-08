"""Native localization follows the installed TZif bytes, including revised history."""

from dataclasses import replace
from datetime import datetime, timezone
from importlib.resources import files
from itertools import permutations
from zoneinfo import ZoneInfo

import polars as pl
import pyarrow as pa
import pytest
from test_migration_backends import column, contract, run
from test_migration_product_semantics import timestamp_column

import equiframe as ef
import equiframe.execution as execution
from equiframe.migration.backends import polars as backend

UNITS = ("s", "ms", "us", "ns")
POLICIES = ("reject", "earlier", "later")
ZONES = (
    "America/Bogota",
    "America/Tijuana",
    "America/Ensenada",
    "America/Santa_Isabel",
    "Mexico/BajaNorte",
    "Factory",
    "America/New_York",
    "Australia/Lord_Howe",
    "Pacific/Chatham",
    "Europe/Dublin",
    "Asia/Tehran",
    "Antarctica/Casey",
)
EPOCH = datetime(1970, 1, 1)


def capture_failures(monkeypatch):
    failures = []
    original = execution.report_failure

    def observe(error, public_message):
        failures.append(error)
        return original(error, public_message)

    monkeypatch.setattr(execution, "report_failure", observe)
    return failures


def ticks(value, unit):
    delta = value - EPOCH
    micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    return micros * 1000 if unit == "ns" else micros // {"s": 1000000, "ms": 1000, "us": 1}[unit]


def candidates(value, zone, unit):
    # Independent scalar reference: round-trip both PEP 495 alternatives using
    # the actual installed file, never a dataframe engine or float timestamp.
    with files("tzdata.zoneinfo").joinpath(*zone.split("/")).open("rb") as stream:
        reference = ZoneInfo.from_file(stream, key=zone)
    found = set()
    for fold in (0, 1):
        utc = value.replace(tzinfo=reference, fold=fold).astimezone(timezone.utc)
        if utc.astimezone(reference).replace(tzinfo=None) == value:
            found.add(ticks(utc.replace(tzinfo=None), unit))
    return sorted(found)


def fixture(zone, unit, policy, values, *, expression=None):
    schema = contract(
        {"input": [timestamp_column(unit, None)]},
        [timestamp_column(unit, zone)],
        family="dates",
    )
    expression = expression or ef.LocalizeTimestamp(
        argument=ef.Column(name="t"), timezone=zone, ambiguous=policy
    )
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
    source = pa.table({"t": pa.array(values, type=pa.int64()).cast(pa.timestamp(unit))})
    return plan, schema, source


@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("policy", POLICIES)
def test_installed_history_and_posix_continuation_keep_exact_native_ticks(
    tmp_path, zone, unit, policy
):
    walls = [
        datetime(1900, 1, 15, 12),
        datetime(1992, 5, 2, 1),
        datetime(1992, 5, 3, 12),
        datetime(2000, 1, 15, 12),
        datetime(2100, 7, 15, 12),
        datetime(1992, 5, 2, 1),
    ]
    choices = [candidates(wall, zone, unit) for wall in walls]
    assert all(len(options) == 1 for options in choices)
    subsecond = 0 if unit == "s" else 1
    values = [ticks(wall, unit) + subsecond for wall in walls] + [None]
    expected = [options[0] + subsecond for options in choices] + [None]
    plan, schema, source = fixture(zone, unit, policy, values)
    result = run(plan, schema, {"input": source}, "polars", tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.schema.field("t").type == pa.timestamp(unit, tz=zone)
    assert actual.column("t").cast(pa.int64()).to_pylist() == expected


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize(
    "zone,wall,cause",
    (
        ("America/Bogota", datetime(1992, 5, 2, 0, 30), "nonexistent"),
        ("America/New_York", datetime(2024, 3, 10, 2, 30), "nonexistent"),
        ("Australia/Lord_Howe", datetime(2024, 10, 6, 2, 15), "nonexistent"),
        ("Europe/Dublin", datetime(2024, 10, 27, 1, 30), "ambiguous"),
        ("Australia/Lord_Howe", datetime(2024, 4, 7, 1, 45), "ambiguous"),
    ),
)
def test_gap_fold_counts_and_policy_follow_installed_tzif(
    tmp_path, monkeypatch, zone, wall, cause, unit, policy
):
    options = candidates(wall, zone, unit)
    assert len(options) == (0 if cause == "nonexistent" else 2)
    plan, schema, source = fixture(zone, unit, policy, [ticks(wall, unit), None])
    failures = capture_failures(monkeypatch)
    result = run(plan, schema, {"input": source}, "polars", tmp_path)
    if cause == "nonexistent" or policy == "reject":
        assert result.state != "completed"
        assert len(failures) == 1
        assert isinstance(failures[0], pl.exceptions.ComputeError)
        assert cause + " wall time" in str(failures[0])
        assert result.problem.exception_type == "ComputeError"
        assert cause + " wall time" not in result.problem.message
    else:
        assert failures == []
        assert result.state == "completed", result.problem
        actual = ef.read_table(result.output.data)
        assert actual.column("t").cast(pa.int64()).to_pylist() == [
            options[-1 if policy == "later" else 0],
            None,
        ]


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("empty", (False, True))
def test_literal_null_localization_preserves_source_multiplicity(tmp_path, unit, empty):
    expression = ef.LocalizeTimestamp(
        argument=ef.LiteralExpression(
            logical_type=ef.TimestampType(unit=unit, timezone=None), value=ef.NullValue()
        ),
        timezone="America/Bogota",
        ambiguous="reject",
    )
    values = [] if empty else [0, 1, 1, None]
    plan, schema, source = fixture("America/Bogota", unit, "reject", values, expression=expression)
    result = run(plan, schema, {"input": source}, "polars", tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    assert actual.num_rows == len(values)
    assert actual.column("t").cast(pa.int64()).to_pylist() == [None] * len(values)


@pytest.mark.parametrize("origin,target", tuple(permutations(("pandas", "polars", "duckdb"), 2)))
@pytest.mark.parametrize("unit", UNITS)
def test_revised_bogota_history_migrates_all_six_directions(tmp_path, origin, target, unit):
    walls = [datetime(1992, 5, 2, 1), datetime(1992, 5, 3, 0, 30)]
    values = [ticks(wall, unit) for wall in walls] + [None]
    expected_ticks = [candidates(wall, "America/Bogota", unit)[0] for wall in walls] + [None]
    plan, schema, source = fixture("America/Bogota", unit, "reject", values)
    expected = pa.table(
        {
            "t": pa.array(expected_ticks, type=pa.int64()).cast(
                pa.timestamp(unit, tz="America/Bogota")
            )
        }
    )
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


def test_resource_change_after_compilation_rejects_execution(monkeypatch, tmp_path):
    plan, schema, source = fixture("America/Bogota", "ms", "reject", [0])
    compiled = backend.PolarsCompiler().compile(plan, schema)
    assert "/tzif-" in compiled.transformation.code_version
    monkeypatch.setattr(backend, "_timezone_resource_hash", lambda key: "0" * 64)
    failures = capture_failures(monkeypatch)
    registry = ef.TransformationRegistry()
    registry.register(compiled.transformation)
    result = ef.execute(
        ef.ExecutionPlan(
            contract=schema,
            engine="polars",
            transformation_id=compiled.transformation.transformation_id,
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        registry=registry,
        work_dir=tmp_path,
    )
    assert result.state != "completed"
    assert len(failures) == 1
    assert isinstance(failures[0], ef.CapabilityError)
    assert "timezone resource changed after compilation" in str(failures[0])
    assert result.problem.exception_type == "CapabilityError"
    assert "timezone resource changed after compilation" not in result.problem.message


def test_compilation_identity_includes_actual_resource_bytes(monkeypatch):
    plan, schema, _ = fixture("America/Bogota", "ms", "reject", [0])
    original = backend.PolarsCompiler().compile(plan, schema)
    data = backend._timezone_data("America/Bogota")
    monkeypatch.setattr(
        backend, "_timezone_data", lambda key: replace(data, resource_sha256="1" * 64)
    )
    changed = backend.PolarsCompiler().compile(plan, schema)
    assert original.transformation.transformation_id != changed.transformation.transformation_id


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("pruning", ("conditional", "boolean", "filter", "later_filter"))
def test_invalid_localization_is_checked_before_relational_or_branch_pruning(
    tmp_path, monkeypatch, unit, pruning
):
    localized = ef.LocalizeTimestamp(
        argument=ef.Column(name="t"), timezone="America/Bogota", ambiguous="reject"
    )
    false = ef.LiteralExpression(logical_type=ef.BooleanType(), value=ef.BooleanValue(value=False))
    if pruning == "conditional":
        expression = ef.Conditional(
            predicate=false,
            then=localized,
            otherwise=ef.LiteralExpression(
                logical_type=ef.TimestampType(unit=unit, timezone="America/Bogota"),
                value=ef.NullValue(),
            ),
        )
        plan, schema, source = fixture(
            "America/Bogota",
            unit,
            "reject",
            [ticks(datetime(1992, 5, 2, 0, 30), unit)],
            expression=expression,
        )
    elif pruning == "later_filter":
        plan, schema, source = fixture(
            "America/Bogota", unit, "reject", [ticks(datetime(1992, 5, 2, 0, 30), unit)]
        )
        plan = ef.RelationalPlan(
            nodes=(*plan.nodes, ef.Filter(node_id="f", source="p", predicate=false)), output="f"
        )
    else:
        stamp = timestamp_column(unit, None)
        schema = contract({"input": [stamp]}, [stamp], family="dates")
        plan = ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="s", table="input"),
                ef.Filter(
                    node_id="f",
                    source="s",
                    predicate=(
                        ef.Boolean(
                            operation="and", arguments=(false, ef.IsNull(argument=localized))
                        )
                        if pruning == "boolean"
                        else ef.IsNull(argument=localized)
                    ),
                ),
            ),
            output="f",
        )
        source = pa.table(
            {
                "t": pa.array([ticks(datetime(1992, 5, 2, 0, 30), unit)], type=pa.int64()).cast(
                    pa.timestamp(unit)
                )
            }
        )
    if pruning in ("conditional", "boolean"):
        with pytest.raises(ef.CapabilityError, match="fallible arithmetic inside"):
            backend.PolarsCompiler().compile(plan, schema)
        return
    failures = capture_failures(monkeypatch)
    result = run(plan, schema, {"input": source}, "polars", tmp_path)
    assert result.state != "completed"
    assert len(failures) == 1
    assert isinstance(failures[0], pl.exceptions.ComputeError)
    assert "nonexistent wall time" in str(failures[0])
    assert result.problem.exception_type == "ComputeError"
    assert "nonexistent wall time" not in result.problem.message


@pytest.mark.parametrize("unit", UNITS)
def test_localization_checkpoints_compose_with_coalesce_and_integer_arithmetic(tmp_path, unit):
    integer = ef.IntegerType(bits=64, signed=True)
    localized = ef.LocalizeTimestamp(
        argument=ef.Coalesce(arguments=(ef.Column(name="t"), ef.Column(name="t"))),
        timezone="America/Bogota",
        ambiguous="reject",
    )
    schema = contract(
        {"input": [timestamp_column(unit, None), column("v", integer)]},
        [
            column("v", integer),
            column("missing", ef.BooleanType()),
            timestamp_column(unit, "America/Bogota"),
        ],
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
                        name="v",
                        expression=ef.Arithmetic(
                            operation="multiply",
                            left=ef.Column(name="v"),
                            right=ef.LiteralExpression(
                                logical_type=integer, value=ef.IntegerValue(value=2), unit="units"
                            ),
                            logical_type=integer,
                            unit="units",
                        ),
                    ),
                    ef.NamedExpression(name="missing", expression=ef.IsNull(argument=localized)),
                    ef.NamedExpression(name="t", expression=localized),
                ),
            ),
        ),
        output="p",
    )
    wall = datetime(1992, 5, 2, 1)
    source = pa.table(
        {
            "t": pa.array([ticks(wall, unit), None, ticks(wall, unit)], type=pa.int64()).cast(
                pa.timestamp(unit)
            ),
            "v": [2, -3, None],
        }
    )
    result = run(plan, schema, {"input": source}, "polars", tmp_path)
    assert result.state == "completed", result.problem
    actual = ef.read_table(result.output.data)
    expected = candidates(wall, "America/Bogota", unit)[0]
    assert actual.column("t").cast(pa.int64()).to_pylist() == [expected, None, expected]
    assert actual.column("v").to_pylist() == [4, -6, None]
    assert actual.column("missing").to_pylist() == [False, True, False]
