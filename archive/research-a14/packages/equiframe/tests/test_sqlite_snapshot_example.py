"""Ordinary functional checks of the external SQLite snapshot integration."""

import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal

import pyarrow as pa
import pytest
from conftest import EXAMPLES

import equiframe as ef


@pytest.fixture
def example(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES / "integrations"))
    producer = importlib.import_module("sqlite_snapshot")
    demo = importlib.import_module("sqlite_snapshot_demo")
    return producer, demo


@pytest.fixture
def database(tmp_path, example):
    _, demo = example
    path = tmp_path / "synthetic.sqlite"
    demo.create_synthetic_database(path, discrepant=False)
    return path


def capture(example, database, **changes):
    producer, demo = example
    kwargs = {
        "snapshot_id": "test.sqlite.001",
        "queries": demo.declarations(),
        "domain_schema_revision": "test.schema.1",
        "extraction_revision": "test.extraction.1",
        "provenance": ("Synthetic integration fixture; no external service",),
    }
    return producer.capture_sqlite_snapshot(database, **(kwargs | changes))


def context(tmp_path, example, client):
    _, demo = example
    directory = tmp_path / "capture"
    directory.mkdir()
    return ef.RunContext(
        run_id="sqlite.run",
        execution_id="sqlite.execution",
        plan=ef.ExecutionPlan(
            contract=demo.contract_for(client.manifest), engine="duckdb", transformation_id="join"
        ),
        directory=directory,
        store=ef.LocalArtifactStore(directory / "artifacts"),
        cancellation=ef.CancellationToken(),
        deadline=None,
    )


def test_snapshot_is_detached_pinned_and_preserves_exact_values(tmp_path, example, database):
    client = capture(example, database, batch_rows=1)
    run = context(tmp_path, example, client)
    # The service port has no database handle after capture; later source changes
    # do not change either table, its manifest, or any artifact bytes.
    database.unlink()
    source = ef.SnapshotDataSource("test.sqlite.001", client=client)
    accounts = source.resolve("accounts", context=run)
    entries = source.resolve("entries", context=run)
    assert accounts.table.to_pylist() == [
        {"account_id": 1, "label": "Café"},
        {"account_id": 2, "label": None},
    ]
    assert entries.table.to_pylist() == [
        {"id": "A", "account_id": 1, "amount": Decimal("1.10"), "currency": "USD"},
        {"id": "B", "account_id": 1, "amount": None, "currency": "USD"},
        {"id": "C", "account_id": 2, "amount": Decimal("-0.01"), "currency": "EUR"},
    ]
    assert entries.table.schema == example[1].declarations()[1].schema
    assert entries.origin == client.manifest.tables[1].artifact
    assert client.get_snapshot("test.sqlite.001") is client.manifest
    with pytest.raises(LookupError, match="identity"):
        client.get_snapshot("latest")
    with pytest.raises(LookupError, match="artifact"):
        client.download_artifact(
            entries.origin.model_copy(update={"sha256": "0" * 64}), tmp_path / "not-created.arrow"
        )
    saved = ef.SnapshotManifest.model_validate_json(
        (run.directory / "snapshot-manifest.json").read_text()
    )
    assert saved == client.manifest
    recorded = {item.name: item.value.value for item in run.effective_configuration}
    assert recorded["snapshot_manifest_sha256"] == ef.snapshot_fingerprint(client.manifest)
    assert saved.provenance == ("Synthetic integration fixture; no external service",)


def test_native_transaction_keeps_tables_consistent_during_committed_wal_write(
    tmp_path, monkeypatch, example, database
):
    producer, _ = example
    writer = sqlite3.connect(database)
    assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    original = producer._read_query
    observed = []

    def read_then_update(connection, query, **kwargs):
        table = original(connection, query, **kwargs)
        observed.append(connection.in_transaction)
        if query.name == "accounts":
            with writer:
                writer.execute("UPDATE accounts SET label = 'next' WHERE account_id = 1")
                writer.execute("UPDATE entries SET amount = '2.20' WHERE id = 'A'")
        return table

    monkeypatch.setattr(producer, "_read_query", read_then_update)
    try:
        client = capture(example, database)
        assert observed == [True, True]
        run = context(tmp_path, example, client)
        source = ef.SnapshotDataSource("test.sqlite.001", client=client)
        assert source.resolve("accounts", context=run).table["label"][0].as_py() == "Café"
        assert source.resolve("entries", context=run).table["amount"][0].as_py() == Decimal("1.10")
        # The committed writer was real and visible to the next independent read.
        assert writer.execute("SELECT amount FROM entries WHERE id = 'A'").fetchone() == ("2.20",)
        monkeypatch.setattr(producer, "_read_query", original)
        next_client = capture(example, database, snapshot_id="test.sqlite.002")
        other = tmp_path / "next"
        other.mkdir()
        next_run = context(other, example, next_client)
        next_source = ef.SnapshotDataSource("test.sqlite.002", client=next_client)
        assert next_source.resolve("accounts", context=next_run).table["label"][0].as_py() == "next"
        assert next_source.resolve("entries", context=next_run).table["amount"][
            0
        ].as_py() == Decimal("2.20")
    finally:
        writer.close()


@pytest.mark.parametrize("failure", [None, "sql", "rows", "bytes", "decoding"])
def test_owns_one_connection_and_closes_it_on_success_or_failure(
    monkeypatch, example, database, failure
):
    producer, demo = example
    if failure == "decoding":
        connection = sqlite3.connect(database)
        try:
            with connection:
                connection.execute("UPDATE entries SET amount = '1.111' WHERE id = 'A'")
        finally:
            connection.close()
    native_connect = sqlite3.connect
    connections = []
    statements = []

    def observed_connect(*args, **kwargs):
        connection = native_connect(*args, **kwargs)
        connections.append(connection)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(producer.sqlite3, "connect", observed_connect)
    changes = {}
    if failure == "sql":
        changes["queries"] = (
            demo.declarations()[0],
            replace(demo.declarations()[1], sql="SELECT * FROM missing_table"),
        )
    elif failure == "rows":
        changes["max_rows_per_table"] = 1
    elif failure == "bytes":
        changes["max_payload_bytes"] = 1
    if failure is None:
        capture(example, database, **changes)
    else:
        with pytest.raises((sqlite3.OperationalError, ef.ResourceLimitError, pa.ArrowInvalid)):
            capture(example, database, **changes)
    assert len(connections) == 1
    assert statements.count("BEGIN") == statements.count("ROLLBACK") == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


def test_consumer_pins_manifest_once_and_subset_keeps_full_identity(tmp_path, example, database):
    client = capture(example, database)
    calls = []

    class CountingClient:
        def get_snapshot(self, snapshot_id):
            calls.append(snapshot_id)
            return client.get_snapshot(snapshot_id)

        def download_artifact(self, ref, destination):
            client.download_artifact(ref, destination)

    source = ef.SnapshotDataSource(
        "test.sqlite.001", client=CountingClient(), table_names=("entries",)
    )
    run = context(tmp_path, example, client)
    source.resolve("entries", context=run)
    source.resolve("entries", context=run)
    assert calls == ["test.sqlite.001"]
    assert source.table_names == ("entries",)
    assert source.manifest == client.manifest
    assert len(source.manifest.tables) == 2


@pytest.mark.parametrize("mismatch", ["sha256", "bytes", "schema", "rows", "nullability"])
def test_existing_consumer_rejects_controlled_transport_or_declaration_mismatch(
    tmp_path, example, database, mismatch
):
    producer, demo = example
    client = capture(example, database)
    run = context(tmp_path, example, client)
    if mismatch == "sha256":
        delivered = demo.CorruptingTransport(client)
    elif mismatch == "bytes":

        class ExtraByteClient(demo.CorruptingTransport):
            def download_artifact(self, ref, destination):
                client.download_artifact(ref, destination)
                with destination.open("ab") as stream:
                    stream.write(b"x")

        delivered = ExtraByteClient(client)
    else:
        table = client.manifest.tables[1]
        if mismatch == "rows":
            table = table.model_copy(update={"row_count": 999})
        else:
            column = table.columns[2].model_copy(
                update=(
                    {"nullable": False}
                    if mismatch == "nullability"
                    else {"physical_type": "string", "logical_type": ef.StringType()}
                )
            )
            table = table.model_copy(
                update={"columns": (*table.columns[:2], column, table.columns[3])}
            )
        manifest = client.manifest.model_copy(update={"tables": (client.manifest.tables[0], table)})
        delivered = producer.SQLiteSnapshotClient(manifest, client._payloads)
    source = ef.SnapshotDataSource("test.sqlite.001", client=delivered)
    with pytest.raises(ef.ArtifactIntegrityError):
        source.resolve("entries", context=run)


@pytest.mark.parametrize(
    ("query", "schema", "error"),
    [
        ("SELECT 1.5 AS value", pa.schema([("value", pa.int64())]), ValueError),
        ("SELECT 1 AS value", pa.schema([("value", pa.string())]), ValueError),
        ("SELECT 1.25 AS value", pa.schema([("value", pa.decimal128(8, 2))]), ValueError),
        ("SELECT '-0.00' AS value", pa.schema([("value", pa.decimal128(8, 2))]), ValueError),
        ("SELECT '1.251' AS value", pa.schema([("value", pa.decimal128(8, 2))]), pa.ArrowInvalid),
        ("SELECT '1234.00' AS value", pa.schema([("value", pa.decimal128(4, 2))]), pa.ArrowInvalid),
        (
            "SELECT NULL AS value",
            pa.schema([pa.field("value", pa.string(), nullable=False)]),
            ValueError,
        ),
        ("SELECT 1 AS other_name", pa.schema([("value", pa.int64())]), ValueError),
    ],
)
def test_declared_schema_rejects_lossy_or_invalid_sqlite_values(
    example, database, query, schema, error
):
    producer, _ = example
    with pytest.raises(error):
        capture(example, database, queries=(producer.SQLiteQuery("values", query, schema),))


def test_empty_typed_table_and_all_null_values_preserve_schema(tmp_path, example, database):
    producer, _ = example
    schema = pa.schema([("value", pa.decimal128(8, 2))])
    for name, sql, expected_rows in (
        ("empty", "SELECT NULL AS value WHERE 0", []),
        ("nulls", "SELECT NULL AS value UNION ALL SELECT NULL", [{"value": None}, {"value": None}]),
    ):
        client = capture(example, database, queries=(producer.SQLiteQuery(name, sql, schema),))
        target = tmp_path / (name + ".arrow")
        client.download_artifact(client.manifest.tables[0].artifact, target)
        with target.open("rb") as stream, pa.ipc.open_file(stream) as reader:
            table = reader.read_all()
        assert table.schema == schema
        assert table.to_pylist() == expected_rows


def test_missing_database_is_not_created_and_latest_never_captures(example, tmp_path):
    path = tmp_path / "absent.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        capture(example, path)
    assert not path.exists()
    with pytest.raises(ValueError, match="latest"):
        capture(example, path, snapshot_id="latest")
    assert not path.exists()


@pytest.mark.parametrize("unsupported", ["timestamp", "metadata", "duplicates"])
def test_unsupported_declaration_is_rejected_before_database_read(example, tmp_path, unsupported):
    producer, _ = example
    schema = {
        "timestamp": pa.schema([("value", pa.timestamp("ns"))]),
        "metadata": pa.schema([("value", pa.string())], metadata={b"unit": b"text"}),
        "duplicates": pa.schema([("value", pa.string()), ("value", pa.string())]),
    }[unsupported]
    with pytest.raises(ValueError):
        capture(
            example,
            tmp_path / "not-opened.sqlite",
            queries=(producer.SQLiteQuery("values", "SELECT NULL AS value", schema),),
        )


@pytest.mark.parametrize(
    ("case", "code", "state"),
    [("good", 0, "equivalent"), ("different", 1, "different"), ("corrupt", 3, "not_evaluable")],
)
def test_standalone_demo_runs_outside_checkout_and_enforces_gate(tmp_path, case, code, state):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("sqlite_snapshot.py", "sqlite_snapshot_demo.py"):
        shutil.copyfile(EXAMPLES / "integrations" / name, scripts / name)
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    output = tmp_path / "evidence"
    completed = subprocess.run(
        [
            sys.executable,
            str(scripts / "sqlite_snapshot_demo.py"),
            "--output",
            str(output),
            "--case",
            case,
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == code, completed.stderr
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["comparison_state"] == state
    assert receipt["exit_code"] == code
    if case == "corrupt":
        assert receipt["execution_state"] == "invalid_input"
        assert not (output / "report").exists()
    else:
        assert receipt["execution_state"] == "completed"
        assert (output / "report").is_dir()


def test_demo_refuses_reused_output_without_changing_it(tmp_path, example):
    _, demo = example
    marker = tmp_path / "keep.txt"
    marker.write_text("unchanged")
    with pytest.raises(FileExistsError):
        demo.run_demo(tmp_path, "good")
    assert marker.read_text() == "unchanged"
    assert not (tmp_path / "synthetic.sqlite").exists()
