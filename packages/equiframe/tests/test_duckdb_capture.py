"""STEP7: explicit capture ownership, budgets, interruptions and detached evidence."""

import importlib
import json
import math
import subprocess
import sys
from datetime import date
from decimal import Decimal
from threading import Event, Thread
from threading import enumerate as threads

import duckdb
import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe.duckdb_capture import DuckDBCaptureOptions, capture_duckdb
from equiframe.local import local_path

implementation = importlib.import_module("equiframe.duckdb_capture")


@pytest.fixture
def connection():
    session = duckdb.connect(
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
        }
    )
    try:
        yield session
    finally:
        session.close()


def context(artifact):
    prefix = "DuckDB capture context v1: "
    return json.loads(
        next(note[len(prefix) :] for note in artifact.notes if note.startswith(prefix))
    )


def assert_no_capture(root):
    assert not list(root.rglob("capture.json"))
    assert not list(root.rglob("snapshot.arrow"))
    assert not list(root.glob(".duckdb-capture-*"))
    assert not any(thread.name == "equiframe-duckdb-capture" for thread in threads())


@pytest.mark.parametrize("parameters", [None, {"minimum": 1}], ids=["unbound", "bound"])
def test_capture_survives_source_change_and_connection_close(parameters, tmp_path):
    """A volatile expression is evaluated once; later work reads persisted bytes."""
    calls = []
    with duckdb.connect(
        config={"autoinstall_known_extensions": False, "autoload_known_extensions": False}
    ) as connection:
        connection.execute("CREATE TABLE source (id BIGINT, value BIGINT)")
        connection.execute("INSERT INTO source VALUES (1, 10), (2, 20), (3, 20)")

        def record(value):
            calls.append(value)
            return value

        connection.create_function("capture_value", record, ["BIGINT"], "BIGINT", side_effects=True)
        sql = "SELECT id, capture_value(value) AS value FROM source"
        if parameters is not None:
            sql += " WHERE id >= $minimum"
        artifact = capture_duckdb(
            sql + " ORDER BY id",
            parameters=parameters,
            connection=connection,
            exclusive_connection=True,
            options=DuckDBCaptureOptions(batch_rows=1),
            work_dir=tmp_path / "capture",
        )
        assert calls == [10, 20, 20]
        connection.execute("UPDATE source SET value = -1")
        assert connection.execute("SELECT value FROM source ORDER BY id").fetchall() == [(-1,)] * 3
    expected = pa.table({"id": [1, 2, 3], "value": [10, 20, 20]})
    assert ef.read_table(artifact.data).equals(expected)
    first = ef.diff(artifact, expected, keys=["id"], work_dir=tmp_path / "first")
    second = ef.diff(artifact, expected, keys=["id"], work_dir=tmp_path / "second")
    assert first.state == second.state == "equivalent"
    assert first.complete and second.complete
    report = ef.comparison_report(first, evidence_root=tmp_path / "first" / first.comparison_id)
    assert report.state == "equivalent" and report.evidence.inspection == "verified_differences"
    assert "equivalent" in report.to_text() and "equivalent" in report.to_html()
    assert calls == [10, 20, 20]


def test_public_exports_and_base_import_do_not_load_optional_engines():
    assert ef.capture_duckdb is capture_duckdb
    assert ef.DuckDBCaptureOptions is DuckDBCaptureOptions
    assert {"capture_duckdb", "DuckDBCaptureOptions"} <= set(ef.__all__)
    program = """
import json, sys
import equiframe
import equiframe.duckdb_capture
heavy = {'duckdb', 'pyarrow', 'numpy', 'pandas', 'polars', 'sklearn'}
print(json.dumps(sorted(set(sys.modules) & heavy)))
"""
    result = subprocess.run(
        [sys.executable, "-c", program], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []


def test_borrowed_session_requires_explicit_exclusive_ownership(connection, tmp_path):
    with pytest.raises(ef.InvalidExecutionInput, match="exclusive_connection=True"):
        capture_duckdb("SELECT 1 AS value", connection=connection, work_dir=tmp_path)
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path)


@pytest.mark.parametrize("exclusive", [1, "yes", None])
def test_exclusive_ownership_flag_is_not_coerced(exclusive, tmp_path):
    with pytest.raises(ef.InvalidExecutionInput, match="boolean"):
        capture_duckdb("SELECT 1 AS value", exclusive_connection=exclusive, work_dir=tmp_path)
    assert_no_capture(tmp_path)


def test_default_borrowed_settings_are_rejected_instead_of_silently_reconfigured(tmp_path):
    with duckdb.connect() as connection:
        before = connection.execute(
            "SELECT current_setting('autoinstall_known_extensions'), "
            "current_setting('autoload_known_extensions')"
        ).fetchone()
        assert any(before)
        with pytest.raises(ef.CapabilityError, match="extension autoinstall/autoload"):
            capture_duckdb(
                "SELECT 1 AS value",
                connection=connection,
                exclusive_connection=True,
                work_dir=tmp_path,
            )
        assert (
            connection.execute(
                "SELECT current_setting('autoinstall_known_extensions'), "
                "current_setting('autoload_known_extensions')"
            ).fetchone()
            == before
        )
    assert_no_capture(tmp_path)


def test_caller_settings_registrations_and_transaction_are_not_changed(connection, tmp_path):
    connection.execute("SET TimeZone = 'Asia/Kathmandu'")
    connection.execute("SET threads = 2")
    connection.execute("SET memory_limit = '128MB'")
    connection.execute("SET default_order = 'DESC'")
    connection.execute("SET default_null_order = 'NULLS_FIRST'")
    connection.execute("SET preserve_insertion_order = false")
    connection.register("registered", pa.table({"value": [7]}))
    query = "SELECT " + ", ".join(f"current_setting('{key}')" for key in implementation._SETTINGS)
    before = connection.execute(query).fetchone()
    connection.execute("CREATE TABLE source (value BIGINT)")
    connection.execute("BEGIN TRANSACTION")
    connection.execute("INSERT INTO source VALUES (19)")
    artifact = capture_duckdb(
        "SELECT value FROM source",
        connection=connection,
        exclusive_connection=True,
        work_dir=tmp_path,
    )
    assert connection.execute(query).fetchone() == before
    assert connection.execute("SELECT * FROM registered").fetchall() == [(7,)]
    connection.execute("ROLLBACK")
    assert connection.execute("SELECT * FROM source").fetchall() == []
    assert ef.read_table(artifact.data)["value"].to_pylist() == [19]
    assert context(artifact)["session"] == dict(zip(implementation._SETTINGS, before, strict=True))
    assert context(artifact)["connection_owner"] == "caller"


def test_owned_session_has_safe_recorded_defaults_without_query_or_parameters(tmp_path):
    private = "private-value-do-not-copy-to-context"
    artifact = capture_duckdb(
        "SELECT $secret::VARCHAR AS value", parameters={"secret": private}, work_dir=tmp_path
    )
    details = context(artifact)
    assert details["connection_owner"] == "equiframe"
    assert details["session"]["TimeZone"] == "UTC"
    assert details["session"]["threads"] == 1
    for setting in (
        "enable_external_access",
        "autoinstall_known_extensions",
        "autoload_known_extensions",
    ):
        assert details["session"][setting] is False
    assert private not in "\n".join(artifact.notes)
    assert "SELECT $secret" not in "\n".join(artifact.notes)
    assert details["started_at"] <= details["finished_at"]
    assert set(details["versions"]) == {"duckdb", "pyarrow"}
    assert details["options"] == DuckDBCaptureOptions().model_dump(mode="json")
    receipt = local_path(artifact.data).with_name("capture.json")
    assert ef.TableArtifact.model_validate_json(receipt.read_bytes()) == artifact


def test_empty_result_preserves_native_schema_and_zero_counts(tmp_path):
    artifact = capture_duckdb(
        "SELECT 1::SMALLINT AS value WHERE FALSE",
        work_dir=tmp_path,
        options=DuckDBCaptureOptions(max_rows=0),
    )
    table = ef.read_table(artifact.data)
    assert artifact.row_count == 0 and table.num_rows == 0
    assert table.schema == pa.schema([pa.field("value", pa.int16())])
    assert artifact.columns[0].null_count == artifact.columns[0].nan_count == 0


def test_unicode_empty_null_and_duplicate_occurrences_are_not_normalized(tmp_path):
    values = ["é", "e\u0301", "\U0001f9ed", "", None, "é", "001", "1"]
    sql = (
        "SELECT value FROM (VALUES "
        + ", ".join(f"({i}, $p{i}::VARCHAR)" for i in range(len(values)))
        + ") t(position, value) ORDER BY position"
    )
    artifact = capture_duckdb(
        sql,
        parameters={f"p{i}": value for i, value in enumerate(values)},
        work_dir=tmp_path / "capture",
        options=DuckDBCaptureOptions(batch_rows=2),
    )
    assert ef.read_table(artifact.data)["value"].to_pylist() == values
    assert artifact.row_count == len(values) and artifact.columns[0].null_count == 1
    result = ef.diff(artifact, pa.table({"value": values[:-1]}), work_dir=tmp_path / "comparison")
    assert result.state == "different" and result.complete
    assert result.counts.left_rows == 8 and result.counts.right_rows == 7
    assert result.counts.matched_rows == 7


@pytest.mark.parametrize("native,dtype", [("FLOAT", pa.float32()), ("DOUBLE", pa.float64())])
def test_null_nan_infinity_and_signed_zero_remain_distinct(native, dtype, tmp_path):
    artifact = capture_duckdb(
        f"SELECT value::{native} AS value FROM (VALUES (0, NULL), (1, 'NaN'), "
        "(2, '-0'), (3, '0'), (4, 'Infinity'), (5, '-Infinity'), (6, '1.5')) "
        "t(position, value) ORDER BY position",
        work_dir=tmp_path,
        options=DuckDBCaptureOptions(batch_rows=2),
    )
    observed = ef.read_table(artifact.data)["value"]
    values = observed.to_pylist()
    assert observed.type == dtype
    assert values[0] is None and math.isnan(values[1])
    assert math.copysign(1, values[2]) == -1 and math.copysign(1, values[3]) == 1
    assert values[4:] == [math.inf, -math.inf, 1.5]
    assert artifact.columns[0].null_count == artifact.columns[0].nan_count == 1


@pytest.mark.parametrize(
    "values",
    [
        {"batch_rows": 0},
        {"batch_rows": True},
        {"max_rows": -1},
        {"max_rows": 1.0},
        {"max_batch_bytes": 0},
        {"max_bytes": 0},
        {"timeout_seconds": 0},
        {"timeout_seconds": math.inf},
        {"timeout_seconds": math.nan},
        {"extra": 1},
    ],
)
def test_capture_options_reject_invalid_or_nonfinite_limits(values):
    with pytest.raises(ValidationError):
        DuckDBCaptureOptions(**values)


@pytest.mark.parametrize(
    "options,sql,reason",
    [
        (DuckDBCaptureOptions(max_rows=0), "SELECT 1 AS value", "row budget"),
        (
            DuckDBCaptureOptions(batch_rows=2, max_rows=2),
            "SELECT i AS value FROM range(3) t(i)",
            "row budget",
        ),
        (
            DuckDBCaptureOptions(max_batch_bytes=8),
            "SELECT repeat('x', 100) AS value",
            "batch byte budget",
        ),
        (DuckDBCaptureOptions(max_bytes=1), "SELECT 1 AS value", "serialized byte budget"),
        (
            DuckDBCaptureOptions(max_bytes=1),
            "SELECT 1 AS value WHERE FALSE",
            "serialized byte budget",
        ),
    ],
)
def test_resource_exhaustion_never_publishes_a_partial_capture(options, sql, reason, tmp_path):
    with pytest.raises(ef.ResourceLimitError, match=reason):
        capture_duckdb(sql, options=options, work_dir=tmp_path)
    assert_no_capture(tmp_path)


def test_exact_row_batch_and_serialized_byte_budgets_are_inclusive(tmp_path):
    sql = "SELECT i::BIGINT AS value FROM range(4) t(i) ORDER BY i"
    first = capture_duckdb(
        sql, options=DuckDBCaptureOptions(batch_rows=2), work_dir=tmp_path / "first"
    )
    options = DuckDBCaptureOptions(
        batch_rows=2, max_rows=4, max_batch_bytes=17, max_bytes=first.data.size_bytes
    )
    second = capture_duckdb(sql, options=options, work_dir=tmp_path / "second")
    assert ef.read_table(second.data)["value"].to_pylist() == [0, 1, 2, 3]
    assert first.data.size_bytes == second.data.size_bytes
    with pytest.raises(ef.ResourceLimitError, match="serialized byte budget"):
        capture_duckdb(
            sql,
            options=options.model_copy(update={"max_bytes": first.data.size_bytes - 1}),
            work_dir=tmp_path / "too-small",
        )
    assert_no_capture(tmp_path / "too-small")


def test_precancelled_request_never_opens_a_connection(monkeypatch, tmp_path):
    signal = ef.CancellationToken()
    signal.cancel()

    def forbidden(*args, **kwargs):
        raise AssertionError("cancelled capture opened DuckDB")

    monkeypatch.setattr(duckdb, "connect", forbidden)
    with pytest.raises(ef.ExecutionCancelled):
        capture_duckdb("SELECT 1 AS value", cancellation=signal, work_dir=tmp_path)
    assert_no_capture(tmp_path)


def test_cancellation_interrupts_active_native_fetch_and_releases_caller(
    connection, monkeypatch, tmp_path
):
    signal = ef.CancellationToken()
    entered = Event()
    original = duckdb.DuckDBPyRelation.to_arrow_reader

    def fetch(relation, *args, **kwargs):
        entered.set()
        return original(relation, *args, **kwargs)

    def cancel():
        if entered.wait(5):
            signal.cancel()

    monkeypatch.setattr(duckdb.DuckDBPyRelation, "to_arrow_reader", fetch)
    trigger = Thread(target=cancel)
    trigger.start()
    try:
        with pytest.raises(ef.ExecutionCancelled):
            capture_duckdb(
                "SELECT CAST(sum(i % 2) AS BIGINT) AS value FROM range(1000000000000) t(i)",
                connection=connection,
                exclusive_connection=True,
                cancellation=signal,
                options=DuckDBCaptureOptions(timeout_seconds=5),
                work_dir=tmp_path,
            )
    finally:
        trigger.join(6)
    assert entered.is_set() and not trigger.is_alive()
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path)


def test_native_timeout_fails_closed_and_connection_can_be_reused(connection, tmp_path):
    with pytest.raises(ef.ExecutionTimeout):
        capture_duckdb(
            "SELECT CAST(sum(i % 2) AS BIGINT) AS value FROM range(1000000000000) t(i)",
            connection=connection,
            exclusive_connection=True,
            options=DuckDBCaptureOptions(timeout_seconds=0.05),
            work_dir=tmp_path,
        )
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path)
    artifact = capture_duckdb(
        "SELECT 42 AS value", connection=connection, exclusive_connection=True, work_dir=tmp_path
    )
    assert ef.read_table(artifact.data)["value"].to_pylist() == [42]


@pytest.mark.parametrize(
    "sql",
    [
        "",
        " ",
        "SELECT 1; SELECT 2",
        "CREATE TABLE x (v INTEGER)",
        "SET threads=2",
        "COPY (SELECT 1) TO '/unrequested.csv'",
    ],
)
def test_capture_accepts_only_one_nonempty_select(sql, tmp_path):
    with pytest.raises(ef.InvalidExecutionInput):
        capture_duckdb(sql, work_dir=tmp_path)
    assert_no_capture(tmp_path)


@pytest.mark.parametrize("parameters", [{"extra": 1}, {}, {"value": 1, "extra": 2}])
def test_named_parameters_must_match_exactly(parameters, tmp_path):
    with pytest.raises(ef.InvalidExecutionInput, match="parameters"):
        capture_duckdb("SELECT $value AS value", parameters=parameters, work_dir=tmp_path)
    assert_no_capture(tmp_path)


@pytest.mark.parametrize(
    "value",
    [
        date(2024, 1, 1),
        2**64,
        -(2**63) - 1,
        Decimal("-0.00"),
        Decimal("1E+2"),
        Decimal("NaN"),
        object(),
    ],
)
def test_unsupported_parameters_are_rejected_before_native_execution(value, tmp_path):
    with pytest.raises(ef.CapabilityError, match="parameters"):
        capture_duckdb("SELECT $value AS value", parameters={"value": value}, work_dir=tmp_path)
    assert_no_capture(tmp_path)


def test_bound_text_cannot_become_an_extra_statement(connection, tmp_path):
    value = "'; DROP TABLE source; --"
    connection.execute("CREATE TABLE source (value INTEGER)")
    artifact = capture_duckdb(
        "SELECT $value::VARCHAR AS value",
        parameters={"value": value},
        connection=connection,
        exclusive_connection=True,
        work_dir=tmp_path,
    )
    assert ef.read_table(artifact.data)["value"].to_pylist() == [value]
    assert connection.execute("SELECT count(*) FROM source").fetchone() == (0,)


def test_native_failure_diagnostic_does_not_echo_private_sql_or_literal(tmp_path):
    secret = "not-an-integer-private-sentinel"
    with pytest.raises(ef.NativeEngineError) as caught:
        capture_duckdb(
            "SELECT $secret::INTEGER AS value", parameters={"secret": secret}, work_dir=tmp_path
        )
    assert secret not in str(caught.value) and "SELECT" not in str(caught.value)
    assert_no_capture(tmp_path)


def test_capture_bytes_tampering_cannot_produce_equivalence(tmp_path):
    artifact = capture_duckdb("SELECT 1::BIGINT AS value", work_dir=tmp_path / "capture")
    path = local_path(artifact.data)
    raw = bytearray(path.read_bytes())
    raw[len(raw) // 2] ^= 1
    path.write_bytes(raw)
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_table(artifact.data)
    result = ef.diff(artifact, pa.table({"value": [1]}), work_dir=tmp_path / "comparison")
    assert result.state == "not_evaluable" and not result.complete
    assert result.counts.final is False


@pytest.mark.parametrize("change", ["row_count", "null_count", "arrow_type"])
def test_tampered_physical_metadata_is_not_trusted_as_equivalence(change, tmp_path):
    artifact = capture_duckdb("SELECT 1::BIGINT AS value", work_dir=tmp_path / "capture")
    if change == "row_count":
        artifact = artifact.model_copy(update={"row_count": 2})
    else:
        column = artifact.columns[0].model_copy(
            update={change: 1 if change == "null_count" else "int32"}
        )
        artifact = artifact.model_copy(update={"columns": (column,)})
    result = ef.diff(artifact, pa.table({"value": [1]}), work_dir=tmp_path / "comparison")
    assert result.state == "not_evaluable" and not result.complete


def test_malicious_value_stays_data_and_reports_escape_html_after_connection_close(tmp_path):
    value = '<script>alert("private")</script>'
    artifact = capture_duckdb(
        "SELECT $value::VARCHAR AS value",
        parameters={"value": value},
        work_dir=tmp_path / "capture",
    )
    result = ef.diff(artifact, pa.table({"value": ["safe"]}), work_dir=tmp_path / "comparison")
    assert result.state == "different" and result.complete
    redacted = ef.comparison_report(result)
    assert value not in redacted.to_text() + redacted.to_html() + redacted.model_dump_json()
    disclosed = ef.comparison_report(
        result, options=ef.ReportOptions(include_values=True, include_metadata=True)
    )
    assert "<script>" not in disclosed.to_html()
    assert "&lt;script&gt;" in disclosed.to_html()


def test_batch_size_does_not_change_values_types_counts_or_comparison(tmp_path):
    sql = """
        SELECT i::BIGINT AS id,
               CASE WHEN i % 3 = 0 THEN NULL ELSE i::DECIMAL(38,2) / 8 END AS value
        FROM range(17) t(i) ORDER BY id
    """
    expected = pa.table(
        {
            "id": list(range(17)),
            "value": [None if i % 3 == 0 else i / 8 for i in range(17)],
        }
    )
    captures = [
        capture_duckdb(
            sql,
            work_dir=tmp_path / f"capture-{size}",
            options=DuckDBCaptureOptions(batch_rows=size),
        )
        for size in (1, 4, 100)
    ]
    assert [artifact.row_count for artifact in captures] == [17] * 3
    assert captures[0].columns == captures[1].columns == captures[2].columns
    for size, artifact in zip((1, 4, 100), captures, strict=True):
        assert ef.read_table(artifact.data).equals(expected)
        with pa.ipc.open_file(local_path(artifact.data)) as reader:
            assert all(
                reader.get_batch(i).num_rows <= size for i in range(reader.num_record_batches)
            )
        result = ef.diff(artifact, expected, keys=["id"], work_dir=tmp_path / f"diff-{size}")
        assert result.state == "equivalent" and result.complete


def test_many_to_many_join_retains_multiplicity_and_declared_order(tmp_path):
    sql = """
        WITH l(position, k) AS (VALUES (0, 'x'), (1, 'x'), (2, 'y')),
             r(position, k) AS (VALUES (0, 'x'), (1, 'x'), (2, 'x'), (3, 'z'))
        SELECT l.position AS l_position, r.position AS r_position, l.k
        FROM l JOIN r ON l.k = r.k
        ORDER BY l.position ASC, r.position DESC
    """
    artifact = capture_duckdb(
        sql, work_dir=tmp_path / "capture", options=DuckDBCaptureOptions(batch_rows=2)
    )
    expected = pa.table(
        {
            "l_position": pa.array([0, 0, 0, 1, 1, 1], type=pa.int32()),
            "r_position": pa.array([2, 1, 0, 2, 1, 0], type=pa.int32()),
            "k": ["x"] * 6,
        }
    )
    assert ef.read_table(artifact.data).equals(expected)
    assert artifact.row_count == 6
    columns = ef.infer_diff_contract(expected.schema).spec.contract.output.schema_spec.columns
    declaration = ef.sequence_contract(
        columns,
        by=[
            ef.SortSpec(column="l_position", direction="ascending", nulls="last"),
            ef.SortSpec(column="r_position", direction="descending", nulls="last"),
        ],
    )
    result = ef.diff(artifact, expected, contract=declaration, work_dir=tmp_path / "ordered")
    assert result.state == "equivalent" and result.strategy == "sequence" and result.complete
    reversed_table = expected.take(pa.array([5, 4, 3, 2, 1, 0]))
    different = ef.diff(
        reversed_table, artifact, contract=declaration, work_dir=tmp_path / "reverse"
    )
    assert different.state == "different" and different.complete


def test_private_connection_cannot_scan_python_stack_or_external_file(tmp_path):
    private_input = pa.table({"value": [123]})
    assert private_input.num_rows == 1
    with pytest.raises(ef.NativeEngineError):
        capture_duckdb("SELECT * FROM private_input", work_dir=tmp_path / "replacement")
    source = tmp_path / "private.csv"
    source.write_text("value\n123\n", "utf-8")
    with pytest.raises(ef.NativeEngineError):
        capture_duckdb(
            "SELECT * FROM read_csv($path)",
            parameters={"path": str(source)},
            work_dir=tmp_path / "external",
        )
    assert_no_capture(tmp_path / "replacement")
    assert_no_capture(tmp_path / "external")
    assert source.read_text("utf-8") == "value\n123\n"


def test_reentrant_capture_on_same_connection_is_rejected_without_breaking_owner(
    connection, monkeypatch, tmp_path
):
    original = implementation._write_reader

    def nested(*args, **kwargs):
        with pytest.raises(ef.InvalidExecutionInput, match="already has an active"):
            capture_duckdb(
                "SELECT 2 AS value",
                connection=connection,
                exclusive_connection=True,
                work_dir=tmp_path / "nested",
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(implementation, "_write_reader", nested)
    artifact = capture_duckdb(
        "SELECT 1 AS value",
        connection=connection,
        exclusive_connection=True,
        work_dir=tmp_path / "outer",
    )
    assert ef.read_table(artifact.data)["value"].to_pylist() == [1]
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path / "nested")


@pytest.mark.parametrize("limited", [False, True])
def test_reader_is_consumed_incrementally_once_and_closed_on_success_or_failure(
    limited, monkeypatch, tmp_path
):
    calls = {"open": 0, "fetch": 0, "close": 0}
    original = duckdb.DuckDBPyRelation.to_arrow_reader

    class Reader:
        def __init__(self, reader):
            self.reader = reader
            self.schema = reader.schema

        def read_next_batch(self):
            calls["fetch"] += 1
            return self.reader.read_next_batch()

        def close(self):
            calls["close"] += 1
            self.reader.close()

    def stream(relation, *args, **kwargs):
        calls["open"] += 1
        return Reader(original(relation, *args, **kwargs))

    monkeypatch.setattr(duckdb.DuckDBPyRelation, "to_arrow_reader", stream)
    options = DuckDBCaptureOptions(batch_rows=1, max_rows=1 if limited else 3)
    sql = "SELECT i AS value FROM range(3) t(i) ORDER BY i"
    if limited:
        with pytest.raises(ef.ResourceLimitError, match="row budget"):
            capture_duckdb(sql, work_dir=tmp_path, options=options)
        assert_no_capture(tmp_path)
    else:
        artifact = capture_duckdb(sql, work_dir=tmp_path, options=options)
        assert ef.read_table(artifact.data)["value"].to_pylist() == [0, 1, 2]
    assert calls == {"open": 1, "fetch": 2 if limited else 4, "close": 1}


def test_publication_failure_does_not_leave_success_evidence_or_close_caller(
    connection, monkeypatch, tmp_path
):
    def fail(*args, **kwargs):
        raise OSError("synthetic storage failure")

    monkeypatch.setattr(implementation.os, "fsync", fail)
    with pytest.raises(OSError, match="storage failure"):
        capture_duckdb(
            "SELECT 1 AS value", connection=connection, exclusive_connection=True, work_dir=tmp_path
        )
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path)


def test_closed_borrowed_connection_fails_without_success_evidence(tmp_path):
    connection = duckdb.connect(
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
        }
    )
    connection.close()
    with pytest.raises(ef.NativeEngineError):
        capture_duckdb(
            "SELECT 1 AS value", connection=connection, exclusive_connection=True, work_dir=tmp_path
        )
    assert_no_capture(tmp_path)


@pytest.mark.parametrize("kind", ["relation", "result", "partially-consumed-reader"])
def test_raw_native_inputs_are_refused_without_consuming_them(kind, connection, tmp_path):
    sql = "SELECT i AS value FROM range(3) t(i) ORDER BY i"
    if kind == "result":
        raw = connection.execute(sql)
    else:
        raw = connection.sql(sql)
        if kind == "partially-consumed-reader":
            raw = raw.to_arrow_reader(1)
            assert raw.read_next_batch().column(0).to_pylist() == [0]
    with pytest.raises(ef.InvalidExecutionInput, match="SQL string"):
        capture_duckdb(raw, work_dir=tmp_path)
    if kind == "partially-consumed-reader":
        assert raw.read_next_batch().column(0).to_pylist() == [1]
        raw.close()
    else:
        assert raw.fetchone() == (0,)
    assert_no_capture(tmp_path)


@pytest.mark.parametrize("kind", ["relation", "reader"])
def test_relation_or_reader_cannot_impersonate_connection(kind, connection, tmp_path):
    raw = connection.sql("SELECT i AS value FROM range(2) t(i)")
    if kind == "reader":
        raw = raw.to_arrow_reader(1)
    with pytest.raises(ef.InvalidExecutionInput, match="DuckDBPyConnection"):
        capture_duckdb(
            "SELECT 1 AS value", connection=raw, exclusive_connection=True, work_dir=tmp_path
        )
    if kind == "reader":
        assert raw.read_next_batch().column(0).to_pylist() == [0]
        raw.close()
    else:
        assert raw.fetchone() == (0,)
    assert_no_capture(tmp_path)


@pytest.mark.parametrize(
    "error_type,expected",
    [
        (duckdb.ConversionException, ef.NativeEngineError),
        (OSError, ef.NativeEngineError),
        (pa.ArrowInvalid, ef.NativeEngineError),
        (pa.ArrowMemoryError, ef.ResourceLimitError),
    ],
)
def test_late_native_fetch_failure_removes_earlier_batches(
    error_type, expected, connection, monkeypatch, tmp_path
):
    original = duckdb.DuckDBPyRelation.to_arrow_reader
    calls = {"fetched": 0, "closed": 0}

    class FailingReader:
        def __init__(self, reader):
            self.reader = reader
            self.schema = reader.schema

        def read_next_batch(self):
            calls["fetched"] += 1
            if calls["fetched"] == 2:
                raise error_type("synthetic private failure after first batch")
            return self.reader.read_next_batch()

        def close(self):
            calls["closed"] += 1
            self.reader.close()

    def failing(relation, *args, **kwargs):
        return FailingReader(original(relation, *args, **kwargs))

    monkeypatch.setattr(duckdb.DuckDBPyRelation, "to_arrow_reader", failing)
    with pytest.raises(expected) as caught:
        capture_duckdb(
            "SELECT i AS value FROM range(3) t(i)",
            connection=connection,
            exclusive_connection=True,
            options=DuckDBCaptureOptions(batch_rows=1),
            work_dir=tmp_path,
        )
    assert "private failure" not in str(caught.value)
    assert calls == {"fetched": 2, "closed": 1}
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path)


def test_real_late_native_conversion_error_is_redacted_and_atomic(tmp_path):
    # This fails during Arrow stream consumption, after successful earlier
    # batches. PyArrow exposes the native error as OSError, not duckdb.Error.
    with pytest.raises(ef.NativeEngineError) as caught:
        capture_duckdb(
            "SELECT CASE WHEN i=999999 THEN 'private_late_literal' ELSE '1' END::INTEGER "
            "AS value FROM range(1000000) t(i)",
            options=DuckDBCaptureOptions(batch_rows=4096),
            work_dir=tmp_path,
        )
    assert "private_late_literal" not in str(caught.value)
    assert "SELECT" not in str(caught.value)
    assert caught.value.__cause__ is not None
    assert "private_late_literal" in str(caught.value.__cause__)
    assert_no_capture(tmp_path)


def test_arrow_wrapped_interrupt_preserves_cancellation(connection, monkeypatch, tmp_path):
    token = ef.CancellationToken()
    original = duckdb.DuckDBPyRelation.to_arrow_reader

    class InterruptedReader:
        def __init__(self, reader):
            self.reader = reader
            self.schema = reader.schema

        def read_next_batch(self):
            token.cancel()
            raise OSError("INTERRUPT Error: private wrapped interruption")

        def close(self):
            self.reader.close()

    monkeypatch.setattr(
        duckdb.DuckDBPyRelation,
        "to_arrow_reader",
        lambda relation, *args: InterruptedReader(original(relation, *args)),
    )
    with pytest.raises(ef.ExecutionCancelled):
        capture_duckdb(
            "SELECT 1 AS value",
            connection=connection,
            exclusive_connection=True,
            cancellation=token,
            work_dir=tmp_path,
        )
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path)


def test_capture_fsync_oserror_is_not_misclassified_as_native_failure(monkeypatch, tmp_path):
    def fail_fsync(*args):
        raise OSError("synthetic filesystem full")

    monkeypatch.setattr(implementation.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="filesystem full"):
        capture_duckdb("SELECT 1 AS value", work_dir=tmp_path)
    assert_no_capture(tmp_path)


def test_capture_fsyncs_snapshot_through_its_writable_descriptor(monkeypatch, tmp_path):
    real_open = implementation.Path.open
    real_fsync = implementation.os.fsync
    opened_files = {}
    synced_modes = []

    def tracked_open(path, mode="r", *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        opened_files[stream.fileno()] = (path.name, mode)
        return stream

    def checked_fsync(descriptor):
        name, mode = opened_files.get(descriptor, (None, None))
        if name == "snapshot.arrow":
            assert mode is not None
            assert any(marker in mode for marker in ("w", "a", "x", "+"))
            synced_modes.append(mode)
        return real_fsync(descriptor)

    monkeypatch.setattr(implementation.Path, "open", tracked_open)
    monkeypatch.setattr(implementation.os, "fsync", checked_fsync)
    artifact = capture_duckdb("SELECT 1 AS value", work_dir=tmp_path)

    assert ef.read_table(artifact.data)["value"].to_pylist() == [1]
    assert synced_modes == ["xb"]


def test_concurrent_capture_same_session_is_refused_while_first_finishes(
    connection, monkeypatch, tmp_path
):
    entered = Event()
    release = Event()
    captured = []
    failures = []
    original = implementation._write_reader

    def paused(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise AssertionError("test did not release the first capture")
        return original(*args, **kwargs)

    def first():
        try:
            captured.append(
                capture_duckdb(
                    "SELECT 1 AS value",
                    connection=connection,
                    exclusive_connection=True,
                    work_dir=tmp_path / "first",
                )
            )
        except BaseException as error:
            failures.append(error)

    monkeypatch.setattr(implementation, "_write_reader", paused)
    worker = Thread(target=first)
    worker.start()
    try:
        assert entered.wait(5)
        with pytest.raises(ef.InvalidExecutionInput, match="already has an active"):
            capture_duckdb(
                "SELECT 2 AS value",
                connection=connection,
                exclusive_connection=True,
                work_dir=tmp_path / "second",
            )
    finally:
        release.set()
        worker.join(6)
    assert not worker.is_alive() and failures == []
    assert len(captured) == 1
    assert ef.read_table(captured[0].data)["value"].to_pylist() == [1]
    assert connection.execute("SELECT 42").fetchone() == (42,)
    assert_no_capture(tmp_path / "second")
