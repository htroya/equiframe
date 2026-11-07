"""STEP7: native type admission and literal, independent transport expectations."""

from datetime import date
from decimal import Decimal

import duckdb
import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe._duckdb_transport import duckdb_arrow_schema, verify_duckdb_table
from equiframe.duckdb_capture import DuckDBCaptureOptions, capture_duckdb

UNSUPPORTED_RESULTS = [
    pytest.param("'170141183460469231731687303715884105727'::HUGEINT", id="hugeint"),
    pytest.param("'340282366920938463463374607431768211455'::UHUGEINT", id="uhugeint-max"),
    pytest.param("'e4130225-5779-4ef5-b3ca-727d0706327a'::UUID", id="uuid"),
    pytest.param("INTERVAL '1 month 2 days 3 microseconds'", id="interval"),
    pytest.param("'12:34:56'::TIME", id="time"),
    pytest.param("'12:34:56+02'::TIMETZ", id="timetz"),
    pytest.param("'hi'::BLOB", id="blob"),
    pytest.param("'101'::BIT", id="bit"),
    pytest.param("1::BIGNUM", id="bignum"),
    pytest.param("'a'::ENUM('a','b')", id="enum"),
    pytest.param("'{\"a\": 1}'::JSON", id="json"),
    pytest.param("{'x': 1}", id="struct"),
    pytest.param("[1,2]", id="list"),
    pytest.param("[1,2]::INTEGER[2]", id="array"),
    pytest.param("map(['a'], [1])", id="map"),
    pytest.param("union_value(i := 1)", id="union"),
]


def execute_query(sql, work_dir, *, parameters=()):
    table = pa.table({"value": [1]})
    declaration = ef.infer_diff_contract(table.schema)
    registry = ef.TransformationRegistry()
    registry.register(ef.DuckDBTransformation("native_types", sql, "synthetic.step7.v1"))
    return ef.execute(
        ef.ExecutionPlan(
            contract=declaration.spec.contract,
            engine="duckdb",
            transformation_id="native_types",
            parameters=parameters,
        ),
        source=ef.LocalDataSource({"source": ef.ArrowInput(table)}),
        registry=registry,
        work_dir=work_dir,
    )


def forbidden_export(*args, **kwargs):
    raise AssertionError("unsupported native type reached Arrow export")


@pytest.mark.parametrize("expression", UNSUPPORTED_RESULTS)
def test_native_result_guard_rejects_lossy_types(expression, monkeypatch, tmp_path):
    monkeypatch.setattr(duckdb.DuckDBPyRelation, "to_arrow_reader", forbidden_export)
    with pytest.raises(ef.CapabilityError):
        capture_duckdb(f"SELECT {expression} AS value", work_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("expression", UNSUPPORTED_RESULTS)
def test_runner_uses_same_closed_native_admission(expression, monkeypatch, tmp_path):
    monkeypatch.setattr(duckdb.DuckDBPyConnection, "to_arrow_table", forbidden_export)
    result = execute_query(f"SELECT {expression} AS value", tmp_path)
    assert result.state == "invalid_input"
    assert result.problem.code == "unsupported_capability"
    assert result.output is None


def test_valid_arrow_decimal_cannot_sanitize_native_uhugeint_corruption():
    # DuckDB 1.5.6 exports UHUGEINT max as a valid decimal128(-1). Arrow's
    # physical validator cannot identify the lost unsigned 128-bit value.
    wrong_but_valid = pa.table({"value": pa.array([Decimal(-1)], type=pa.decimal128(38, 0))})
    wrong_but_valid.validate(full=True)
    assert wrong_but_valid["value"][0].as_py() != Decimal(2**128 - 1)
    with pytest.raises(ef.CapabilityError, match="HUGEINT/UHUGEINT"):
        verify_duckdb_table(wrong_but_valid, (("value", "UHUGEINT"),), "UTC")


@pytest.mark.parametrize(
    "native",
    [
        "HUGEINT",
        "UHUGEINT",
        "DECIMAL(39,0)",
        "DECIMAL(3,4)",
        "DECIMAL(0,0)",
        "DECIMAL(4,-1)",
        "unknown",
        "INTEGER ",
    ],
)
def test_unknown_or_malformed_native_types_are_not_inferred_from_values(native):
    with pytest.raises(ef.CapabilityError):
        duckdb_arrow_schema((("value", native),), "UTC")


@pytest.mark.parametrize("native", [(), (("", "INTEGER"),), (("v", "INTEGER"), ("v", "INTEGER"))])
def test_native_schema_requires_nonempty_unique_names(native):
    with pytest.raises(ef.CapabilityError):
        duckdb_arrow_schema(native, "UTC")


@pytest.mark.parametrize(
    "schema",
    [
        pa.schema([pa.field("value", pa.int32(), nullable=False)]),
        pa.schema([pa.field("value", pa.int32(), metadata={b"unit": b"USD"})]),
        pa.schema([pa.field("value", pa.int32())], metadata={b"source": b"changed"}),
        pa.schema([pa.field("value", pa.int64())]),
    ],
)
def test_post_export_schema_drift_is_rejected_without_casts(schema):
    table = pa.Table.from_arrays([pa.array([1], type=schema.field(0).type)], schema=schema)
    with pytest.raises(ef.CapabilityError, match="schema differs"):
        verify_duckdb_table(table, (("value", "INTEGER"),), "UTC")


INTEGER_CASES = [
    ("TINYINT", pa.int8(), -(2**7), 2**7 - 1),
    ("SMALLINT", pa.int16(), -(2**15), 2**15 - 1),
    ("INTEGER", pa.int32(), -(2**31), 2**31 - 1),
    ("BIGINT", pa.int64(), -(2**63), 2**63 - 1),
    ("UTINYINT", pa.uint8(), 0, 2**8 - 1),
    ("USMALLINT", pa.uint16(), 0, 2**16 - 1),
    ("UINTEGER", pa.uint32(), 0, 2**32 - 1),
    ("UBIGINT", pa.uint64(), 0, 2**64 - 1),
]


@pytest.mark.parametrize("native,dtype,minimum,maximum", INTEGER_CASES)
def test_integer_bounds_null_masks_and_width_are_exact(native, dtype, minimum, maximum, tmp_path):
    artifact = capture_duckdb(
        f"SELECT value::{native} AS value FROM (VALUES "
        f"(0, '{minimum}'), (1, '{maximum}'), (2, NULL)) t(position, value) ORDER BY position",
        work_dir=tmp_path,
        options=DuckDBCaptureOptions(batch_rows=1),
    )
    table = ef.read_table(artifact.data)
    assert table.schema == pa.schema([pa.field("value", dtype)])
    assert table["value"].to_pylist() == [minimum, maximum, None]
    assert artifact.row_count == 3
    assert artifact.columns[0].engine_type == native
    assert artifact.columns[0].null_count == 1
    assert artifact.columns[0].nan_count == 0


@pytest.mark.parametrize(
    "scale,literal",
    [
        (0, "99999999999999999999999999999999999999"),
        (2, "999999999999999999999999999999999999.99"),
        (38, "0.12345678901234567890123456789012345678"),
    ],
)
def test_decimal38_retains_every_digit_sign_and_scale(scale, literal, tmp_path):
    artifact = capture_duckdb(
        f"SELECT value::DECIMAL(38,{scale}) AS value FROM "
        f"(VALUES (0, '{literal}'), (1, '-{literal}'), (2, NULL)) t(position, value) "
        "ORDER BY position",
        work_dir=tmp_path,
        options=DuckDBCaptureOptions(batch_rows=1),
    )
    observed = ef.read_table(artifact.data)["value"]
    assert observed.type == pa.decimal128(38, scale)
    assert observed.to_pylist() == [Decimal(literal), Decimal("-" + literal), None]
    assert observed[0].as_py().as_tuple().exponent == -scale


@pytest.mark.parametrize(
    "native,unit,literal,ticks",
    [
        ("TIMESTAMP_S", "s", "1970-01-02 00:00:00", 86400),
        ("TIMESTAMP_MS", "ms", "1970-01-02 00:00:00.123", 86400123),
        ("TIMESTAMP", "us", "1970-01-02 00:00:00.123456", 86400123456),
        ("TIMESTAMP_NS", "ns", "1970-01-02 00:00:00.123456789", 86400123456789),
    ],
)
def test_timestamp_units_are_retained_with_exact_epoch_ticks(
    native, unit, literal, ticks, tmp_path
):
    artifact = capture_duckdb(
        f"SELECT value::{native} AS value FROM (VALUES "
        f"(0, '{literal}'), (1, '1969-12-31 00:00:00'), (2, NULL)) "
        "t(position, value) ORDER BY position",
        work_dir=tmp_path,
    )
    observed = ef.read_table(artifact.data)["value"]
    multiplier = {"s": 1, "ms": 1000, "us": 1000000, "ns": 1000000000}[unit]
    assert observed.type == pa.timestamp(unit)
    assert observed.cast(pa.int64()).to_pylist() == [ticks, -86400 * multiplier, None]
    assert artifact.columns[0].engine_type == native


def test_timezone_capture_preserves_instants_and_effective_session_zone(tmp_path):
    with duckdb.connect(
        config={"autoinstall_known_extensions": False, "autoload_known_extensions": False}
    ) as connection:
        connection.execute("SET TimeZone = 'Asia/Kathmandu'")
        artifact = capture_duckdb(
            "SELECT value::TIMESTAMPTZ AS value FROM (VALUES "
            "(0, '1970-01-01 05:45:00+05:45'), "
            "(1, '2024-11-03 01:30:00-04'), "
            "(2, '2024-11-03 01:30:00-05'), (3, NULL)) "
            "t(position, value) ORDER BY position",
            connection=connection,
            exclusive_connection=True,
            work_dir=tmp_path,
        )
        assert (
            connection.execute("SELECT current_setting('TimeZone')").fetchone()[0]
            == "Asia/Kathmandu"
        )
    observed = ef.read_table(artifact.data)["value"]
    assert observed.type == pa.timestamp("us", tz="Asia/Kathmandu")
    assert observed.cast(pa.int64()).to_pylist() == [0, 1730611800000000, 1730615400000000, None]


def test_date_days_and_leap_day_survive_without_timestamp_conversion(tmp_path):
    artifact = capture_duckdb(
        "SELECT value::DATE AS value FROM (VALUES "
        "(0, '1969-12-31'), (1, '1970-01-01'), (2, '2000-02-29'), (3, NULL)) "
        "t(position, value) ORDER BY position",
        work_dir=tmp_path,
    )
    observed = ef.read_table(artifact.data)["value"]
    assert observed.type == pa.date32()
    assert observed.to_pylist() == [date(1969, 12, 31), date(1970, 1, 1), date(2000, 2, 29), None]
    assert observed.cast(pa.int32()).to_pylist() == [-1, 0, 11016, None]


@pytest.mark.parametrize(
    "native", ["DATE", "TIMESTAMP_S", "TIMESTAMP_MS", "TIMESTAMP", "TIMESTAMP_NS", "TIMESTAMPTZ"]
)
@pytest.mark.parametrize("infinity", ["infinity", "-infinity"])
def test_temporal_infinity_is_not_published_as_an_ordinary_arrow_tick(native, infinity, tmp_path):
    with pytest.raises(ef.CapabilityError, match=r"infinity|sentinel"):
        capture_duckdb(f"SELECT '{infinity}'::{native} AS value", work_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_explicit_checked_cast_is_callers_visible_policy(tmp_path):
    artifact = capture_duckdb(
        "SELECT '99999999999999999999999999999999999999'::HUGEINT::DECIMAL(38,0) AS value",
        work_dir=tmp_path,
    )
    assert artifact.columns[0].engine_type == "DECIMAL(38,0)"
    assert ef.read_table(artifact.data)["value"].to_pylist() == [Decimal("9" * 38)]
    with pytest.raises(ef.NativeEngineError):
        capture_duckdb(
            "SELECT '340282366920938463463374607431768211455'::UHUGEINT::DECIMAL(38,0) AS value",
            work_dir=tmp_path / "outside-range",
        )
    assert not list((tmp_path / "outside-range").glob("**/capture.json"))


@pytest.mark.parametrize("zone,expected_ticks", [("UTC", 0), ("America/Guayaquil", 18000000000)])
def test_date_to_timestamptz_promotion_retains_session_semantics(zone, expected_ticks, tmp_path):
    with duckdb.connect(
        config={"autoinstall_known_extensions": False, "autoload_known_extensions": False}
    ) as connection:
        connection.execute("SET TimeZone = ?", [zone])
        artifact = capture_duckdb(
            "SELECT DATE '1970-01-01'::TIMESTAMPTZ AS value",
            connection=connection,
            exclusive_connection=True,
            work_dir=tmp_path,
        )
    observed = ef.read_table(artifact.data)["value"]
    assert observed.type == pa.timestamp("us", tz=zone)
    assert observed.cast(pa.int64()).to_pylist() == [expected_ticks]
    assert artifact.columns[0].engine_type == "TIMESTAMP WITH TIME ZONE"


def test_sql_decimal_division_remains_native_double_not_relabelled_decimal(tmp_path):
    artifact = capture_duckdb(
        "SELECT 1::DECIMAL(38,2) / 8::DECIMAL(38,2) AS value", work_dir=tmp_path
    )
    assert artifact.columns[0].engine_type == "DOUBLE"
    observed = ef.read_table(artifact.data)["value"]
    assert observed.type == pa.float64() and observed.to_pylist() == [0.125]


def test_column_collation_does_not_authorize_text_normalization(tmp_path):
    with duckdb.connect(
        config={"autoinstall_known_extensions": False, "autoload_known_extensions": False}
    ) as connection:
        connection.execute("CREATE TABLE source (position INTEGER, value VARCHAR COLLATE NOCASE)")
        connection.execute("INSERT INTO source VALUES (0, 'A'), (1, 'a')")
        assert connection.execute("SELECT count(*) FROM source WHERE value = 'a'").fetchone() == (
            2,
        )
        artifact = capture_duckdb(
            "SELECT value FROM source ORDER BY position",
            connection=connection,
            exclusive_connection=True,
            work_dir=tmp_path / "capture",
        )
    assert ef.read_table(artifact.data)["value"].to_pylist() == ["A", "a"]
    result = ef.diff(artifact, pa.table({"value": ["a", "a"]}), work_dir=tmp_path / "comparison")
    assert result.state == "different" and result.complete


def test_runner_private_connection_disables_python_replacement_scans(tmp_path):
    private_frame = pa.table({"value": [999]})
    assert private_frame.num_rows == 1
    result = execute_query("SELECT * FROM private_frame", tmp_path)
    assert result.state == "failed" and result.output is None
    assert result.problem is not None


# Expected precision, scale and coefficient/exponent are literals independent of
# DuckDB binding, Arrow inference, and the transform under test.
DECIMAL_PARAMETERS = [
    ("1E-38", 38, 38, (0, (1,), -38)),
    ("-1E-38", 38, 38, (1, (1,), -38)),
    ("0E-38", 38, 38, (0, (0,), -38)),
    (
        "0.01234567890123456789012345678901234567",
        38,
        38,
        (0, tuple(int(digit) for digit in "1234567890123456789012345678901234567"), -38),
    ),
    ("1.00E-36", 38, 38, (0, (1, 0, 0), -38)),
    ("-1.00E-36", 38, 38, (1, (1, 0, 0), -38)),
    ("123.4500", 7, 4, (0, (1, 2, 3, 4, 5, 0, 0), -4)),
    ("0.000", 3, 3, (0, (0,), -3)),
    ("99999999999999999999999999999999999999", 38, 0, (0, (9,) * 38, 0)),
    ("-999999999999999999999999999999999999.99", 38, 2, (1, (9,) * 38, -2)),
]


@pytest.mark.parametrize("literal,precision,scale,expected_tuple", DECIMAL_PARAMETERS)
@pytest.mark.parametrize("route", ["capture", "execute"])
def test_decimal_parameter_binding_preserves_coefficient_exponent_and_native_type(
    literal, precision, scale, expected_tuple, route, tmp_path
):
    value = Decimal(literal)
    assert value.as_tuple() == expected_tuple
    if route == "capture":
        artifact = capture_duckdb(
            "SELECT $value AS value", parameters={"value": value}, work_dir=tmp_path
        )
    else:
        result = execute_query(
            "SELECT $value AS value",
            tmp_path,
            parameters=(ef.Parameter(name="value", value=ef.DecimalValue(value=value)),),
        )
        assert result.state == "completed", result.problem
        artifact = result.output
        assert artifact is not None
    assert artifact.columns[0].engine_type == f"DECIMAL({precision},{scale})"
    observed = ef.read_table(artifact.data)["value"]
    assert observed.type == pa.decimal128(precision, scale)
    assert observed[0].as_py().as_tuple() == expected_tuple
    assert observed.to_pylist() == [value]


UNSUPPORTED_PARAMETERS = [
    Decimal("-0"),
    Decimal("-0.00"),
    Decimal("1E+2"),
    Decimal("1E-39"),
    Decimal("100000000000000000000000000000000000000"),
    -(2**63) - 1,
    2**64,
]


@pytest.mark.parametrize("value", UNSUPPORTED_PARAMETERS)
@pytest.mark.parametrize("route", ["capture", "execute"])
def test_lossy_parameter_scope_is_rejected_before_query_execution(
    value, route, monkeypatch, tmp_path
):
    sql = "SELECT $value AS value"
    calls = []
    original_execute = duckdb.DuckDBPyConnection.execute
    original_sql = duckdb.DuckDBPyConnection.sql

    def execute(connection, query, *args, **kwargs):
        if query == sql:
            calls.append(query)
            raise AssertionError("unsupported parameter reached native SQL execution")
        return original_execute(connection, query, *args, **kwargs)

    def relation(connection, query, *args, **kwargs):
        if query == sql:
            calls.append(query)
            raise AssertionError("unsupported parameter reached native relation binding")
        return original_sql(connection, query, *args, **kwargs)

    monkeypatch.setattr(duckdb.DuckDBPyConnection, "execute", execute)
    monkeypatch.setattr(duckdb.DuckDBPyConnection, "sql", relation)
    if route == "capture":
        with pytest.raises(ef.CapabilityError):
            capture_duckdb(sql, parameters={"value": value}, work_dir=tmp_path)
        assert list(tmp_path.iterdir()) == []
    else:
        scalar = (
            ef.DecimalValue(value=value)
            if isinstance(value, Decimal)
            else ef.IntegerValue(value=value)
        )
        result = execute_query(
            sql, tmp_path, parameters=(ef.Parameter(name="value", value=scalar),)
        )
        assert result.state == "invalid_input" and result.output is None
        assert result.problem.code == "unsupported_capability"
    assert calls == []


@pytest.mark.parametrize("literal", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_decimal_is_rejected_before_native_parameter_binding(
    literal, monkeypatch, tmp_path
):
    def forbidden(*args, **kwargs):
        raise AssertionError("nonfinite decimal reached DuckDB")

    monkeypatch.setattr(duckdb, "connect", forbidden)
    with pytest.raises(ef.CapabilityError):
        capture_duckdb(
            "SELECT $value AS value", parameters={"value": Decimal(literal)}, work_dir=tmp_path
        )
    with pytest.raises(ValidationError, match="finite"):
        ef.DecimalValue(value=Decimal(literal))
    assert list(tmp_path.iterdir()) == []
