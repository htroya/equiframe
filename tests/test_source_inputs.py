"""Real SQLite and caller-owned responses retain exact types and failure states."""

import hashlib
import io
import sqlite3
from contextlib import closing
from decimal import Decimal

import pytest
from test_migration_backends import column, contract

import equiframe as ef
from equiframe.execution import CancellationToken, RunContext
from equiframe.local import LocalArtifactStore
from equiframe.sources import SQLiteInput, StreamInput


def spec(format="jsonl", **options):
    return ef.IngestionSpec(
        format=format,
        fields=(
            ef.FieldMapping(column=column("id", ef.StringType()), path=("id",)),
            ef.FieldMapping(
                column=column("amount", ef.DecimalType(precision=12, scale=2), unit="USD"),
                path=("amount",),
            ),
        ),
        **options,
    )


def context(tmp_path, **options):
    schema = contract(
        {"input": [field.column for field in spec().fields]},
        [field.column for field in spec().fields],
    )
    return RunContext(
        "test",
        "test",
        ef.ExecutionPlan(
            contract=schema,
            engine="pandas",
            transformation_id="test",
            options=ef.ExecutionOptions(**options),
        ),
        tmp_path,
        LocalArtifactStore(tmp_path / "artifacts"),
        CancellationToken(),
        None,
    )


def test_sql_and_csv_produce_same_exact_bag(tmp_path):
    path = tmp_path / "amounts.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE values_table (id TEXT, amount TEXT)")
        db.executemany(
            "INSERT INTO values_table VALUES (?, ?)",
            [("001", "12.30"), ("001", "12.30"), ("002", None)],
        )
    csv = tmp_path / "amounts.csv"
    csv.write_text("id,amount\n001,12.30\n001,12.30\n002,NULL\n", encoding="utf-8")
    mappings = spec("csv").fields
    csv_spec = ef.IngestionSpec(
        format="csv",
        fields=(mappings[0], mappings[1].model_copy(update={"null_tokens": ("NULL",)})),
    )
    left = SQLiteInput(
        path,
        "SELECT id, amount FROM values_table WHERE id <> ?",
        spec(),
        ("excluded",),
        batch_rows=1,
    ).load(context(tmp_path))
    right = ef.FileInput(csv, csv_spec, batch_rows=1).load(context(tmp_path))
    expected = [
        {"id": "001", "amount": Decimal("12.30")},
        {"id": "001", "amount": Decimal("12.30")},
        {"id": "002", "amount": None},
    ]
    assert left.table.to_pylist() == right.table.to_pylist() == expected


def test_sql_real_cannot_become_exact_money(tmp_path):
    path = tmp_path / "amounts.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE values_table (id TEXT, amount REAL)")
        db.execute("INSERT INTO values_table VALUES ('001', 12.30)")
    with pytest.raises(ef.InvalidExecutionInput, match="exact TEXT"):
        SQLiteInput(path, "SELECT * FROM values_table", spec()).load(context(tmp_path))
    assert not list(tmp_path.glob("sqlite_*.jsonl"))


@pytest.mark.parametrize(
    "query", ["DELETE FROM values_table", "SELECT id AS x, amount AS x FROM values_table"]
)
def test_sql_rejects_writes_and_ambiguous_columns(tmp_path, query):
    path = tmp_path / "amounts.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE values_table (id TEXT, amount TEXT)")
    with pytest.raises(ef.InvalidExecutionInput):
        SQLiteInput(path, query, spec()).load(context(tmp_path))


def test_response_is_verified_closed_and_preserved(tmp_path):
    raw = b'{"id":"001","amount":"12.30"}\n'
    stream = io.BytesIO(raw)
    loaded = StreamInput(lambda: closing(stream), spec(), hashlib.sha256(raw).hexdigest()).load(
        context(tmp_path)
    )
    assert stream.closed
    assert loaded.table.to_pylist() == [{"id": "001", "amount": Decimal("12.30")}]
    assert any(path.read_bytes() == raw for path in tmp_path.glob("ingestion_*/source.original"))


@pytest.mark.parametrize(
    "limit,expected,error",
    [(5, None, ef.ResourceLimitError), (1000, "0" * 64, ef.ArtifactIntegrityError)],
)
def test_failed_response_never_publishes_an_accepted_table(tmp_path, limit, expected, error):
    stream = io.BytesIO(b'{"id":"001","amount":"12.30"}\n')
    with pytest.raises(error):
        StreamInput(lambda: closing(stream), spec(max_source_bytes=limit), expected).load(
            context(tmp_path)
        )
    assert stream.closed
    assert not list(tmp_path.glob("response_*"))
    assert not list(tmp_path.glob("ingestion_*/accepted.arrow"))


def test_sql_enforces_cumulative_rows(tmp_path):
    path = tmp_path / "amounts.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE values_table (id TEXT, amount TEXT)")
        db.executemany("INSERT INTO values_table VALUES (?, ?)", [("001", "1.00"), ("002", "2.00")])
    with pytest.raises(ef.ResourceLimitError, match="row budget"):
        SQLiteInput(path, "SELECT * FROM values_table", spec(), batch_rows=1).load(
            context(tmp_path, max_input_rows=1)
        )


def test_sql_reads_when_python_omits_extension_loading_api(tmp_path, monkeypatch):
    path = tmp_path / "portable.db"
    connect = sqlite3.connect
    with connect(path) as db:
        db.execute("CREATE TABLE input (id TEXT, amount TEXT)")
        db.execute("INSERT INTO input VALUES ('001', '12.30')")

    class WithoutExtensionLoading:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            if name == "enable_load_extension":
                raise AttributeError(name)
            return getattr(self.connection, name)

    monkeypatch.setattr(
        sqlite3, "connect", lambda *a, **kw: WithoutExtensionLoading(connect(*a, **kw))
    )
    loaded = SQLiteInput(path, "SELECT * FROM input", spec()).load(context(tmp_path))
    assert loaded.table.to_pylist() == [{"id": "001", "amount": Decimal("12.30")}]
