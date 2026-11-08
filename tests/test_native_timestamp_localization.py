"""Literal UTC expectations for the native SQL localization kernel."""

from datetime import datetime

import duckdb
import pyarrow as pa
import pytest

from equiframe.migration.backends.duckdb_time import localize

UNITS = {"s": 1, "ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}


def seconds(iso):
    delta = datetime.fromisoformat(iso) - datetime(1970, 1, 1)
    return delta.days * 86400 + delta.seconds


def query(values, unit, zone, ambiguity, name="t"):
    quoted = '"' + name.replace('"', '""') + '"'
    expression = localize(quoted, unit=unit, timezone=zone, ambiguous=ambiguity, columns=(name,))
    with duckdb.connect(
        ":memory:", config={"threads": 1, "enable_external_access": False}
    ) as connection:
        connection.register("fixture", pa.table({name: pa.array(values, type=pa.int64())}))
        return [
            row[0]
            for row in connection.execute("SELECT " + expression + " FROM fixture").fetchall()
        ]


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("mode", ("earlier", "later"))
@pytest.mark.parametrize(
    "zone,wall,earlier,later",
    [
        ("America/New_York", "2024-11-03T01:30:00", "2024-11-03T05:30:00", "2024-11-03T06:30:00"),
        (
            "Australia/Lord_Howe",
            "2024-04-07T01:45:00",
            "2024-04-06T14:45:00",
            "2024-04-06T15:15:00",
        ),
    ],
)
def test_native_timestamp_fold_policy_preserves_subseconds_and_duplicates(
    unit, mode, zone, wall, earlier, later
):
    extra = 0 if unit == "s" else 123
    value = seconds(wall) * UNITS[unit] + extra
    expected = seconds(earlier if mode == "earlier" else later) * UNITS[unit] + extra
    assert query([value, value, None], unit, zone, mode) == [expected, expected, None]
    with pytest.raises(duckdb.InvalidInputException, match="ambiguous wall time"):
        query([value], unit, zone, "reject")


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize(
    "zone,wall",
    [("America/New_York", "2024-03-10T02:30:00"), ("Pacific/Apia", "2011-12-30T12:00:00")],
)
def test_native_timestamp_gap_and_skipped_day_reject(unit, zone, wall):
    with pytest.raises(duckdb.InvalidInputException, match="nonexistent wall time"):
        query([seconds(wall) * UNITS[unit]], unit, zone, "earlier")


@pytest.mark.parametrize("unit", UNITS)
def test_native_timestamp_utc_negative_tick_and_null(unit):
    assert query([-1, 0, 1, None], unit, "UTC", "reject") == [-1, 0, 1, None]


@pytest.mark.parametrize("unit", UNITS)
def test_native_timestamp_empty_and_all_null(unit):
    assert query([], unit, "America/New_York", "reject") == []
    assert query([None, None], unit, "America/New_York", "reject") == [None, None]


@pytest.mark.parametrize("name", ("_equiframe_timestamp_localization_tick", 't";select'))
def test_native_timestamp_internal_names_cannot_shadow_input(name):
    value = seconds("2024-11-03T01:30:00") * UNITS["ns"] + 123
    expected = seconds("2024-11-03T06:30:00") * UNITS["ns"] + 123
    assert query([value, None], "ns", "America/New_York", "later", name) == [expected, None]
