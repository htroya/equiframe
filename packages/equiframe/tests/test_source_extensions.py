"""External providers, real batches and cooperative interruption fail explicitly."""

import sqlite3
import time
from contextlib import contextmanager
from threading import Timer

import pyarrow as pa
import pytest
from test_migration_backends import column, contract
from test_source_inputs import context, spec

import equiframe as ef


def opener(batches, closed):
    @contextmanager
    def opened():
        try:
            yield iter(batches)
        finally:
            closed.append(True)

    return opened


@pytest.mark.parametrize(
    "options,phrase",
    [
        ({"max_input_rows": 1}, "cumulative row"),
        ({"max_transport_bytes": 12}, "cumulative Arrow byte"),
    ],
)
def test_batch_budgets_are_cumulative_and_close_reader(tmp_path, options, phrase):
    first = pa.record_batch({"id": [1]})
    closed = []
    with pytest.raises(ef.ResourceLimitError, match=phrase):
        ef.RecordBatchInput(opener([first, first], closed), first.schema).load(
            context(tmp_path, **options)
        )
    assert closed == [True]


def test_batches_preserve_explicit_empty_schema_and_metadata(tmp_path):
    schema = pa.schema([pa.field("id", pa.string(), nullable=False)], metadata={b"revision": b"1"})
    closed = []
    empty = ef.RecordBatchInput(opener([], closed), schema).load(context(tmp_path))
    assert empty.table.schema.equals(schema, check_metadata=True)
    assert empty.table.num_rows == 0 and closed == [True]


@pytest.mark.parametrize("change", ["type", "metadata", "nullability"])
def test_batches_reject_schema_drift_and_illegal_nulls(tmp_path, change):
    schema = pa.schema([pa.field("id", pa.string(), nullable=False)], metadata={b"revision": b"1"})
    if change == "type":
        batch = pa.record_batch({"id": [1]})
    elif change == "metadata":
        batch = pa.RecordBatch.from_arrays(
            [pa.array(["001"])], schema=schema.with_metadata({b"revision": b"2"})
        )
    else:
        batch = pa.RecordBatch.from_arrays([pa.array([None], type=pa.string())], schema=schema)
    closed = []
    with pytest.raises(ef.InvalidExecutionInput):
        ef.RecordBatchInput(opener([batch], closed), schema).load(context(tmp_path))
    assert closed == [True]


def test_composite_external_source_is_captured_once_and_runs_native_migration(tmp_path):
    class ExternalProvider:
        table_names = ("customers",)
        calls = 0

        def resolve(self, name, *, context):
            assert name == "customers"
            context.check()
            self.calls += 1
            return ef.LoadedTable(pa.table({"id": ["001", "001", None]}))

    provider = ExternalProvider()
    bindings = {"input": (provider, "customers")}
    source = ef.CompositeDataSource(bindings)
    bindings.clear()  # Caller mutations cannot silently rebind the input.
    columns = [column("id", ef.StringType())]
    schema = contract({"input": columns}, columns)
    plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="s", table="input"),), output="s")
    result = ef.migrate(
        ef.MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine="polars",
            target_engine="duckdb",
            require_rules=False,
        ),
        source=source,
        expected=ef.ArrowInput(pa.table({"id": ["001", "001", None]})),
        work_dir=tmp_path,
    )
    assert result.state == "equivalent" and result.verification == "correct"
    assert provider.calls == 1 and source.table_names == ("input",)
    with pytest.raises(ef.InvalidExecutionInput, match="unavailable"):
        source.resolve("missing", context=context(tmp_path))


def test_composite_does_not_swallow_provider_failure(tmp_path):
    class Unavailable:
        table_names = ("table",)

        def resolve(self, name, *, context):
            raise ConnectionError("provider unavailable")

    source = ef.CompositeDataSource({"input": (Unavailable(), "table")})
    with pytest.raises(ConnectionError):
        source.resolve("input", context=context(tmp_path))
    with pytest.raises(ef.InvalidExecutionInput, match="unavailable"):
        ef.CompositeDataSource({"input": (Unavailable(), "missing")})


@pytest.mark.parametrize("interrupt", ["timeout", "cancel"])
def test_sql_progress_interrupts_before_first_result_and_cleans_up(tmp_path, interrupt):
    path = tmp_path / "expensive.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE input (id TEXT, amount TEXT)")
    run = context(tmp_path)
    timer = None
    if interrupt == "timeout":
        run.deadline = time.perf_counter() + 0.03
        error = ef.ExecutionTimeout
    else:
        timer = Timer(0.03, run.cancellation.cancel)
        timer.start()
        error = ef.ExecutionCancelled
    started = time.perf_counter()
    try:
        with pytest.raises(error):
            ef.SQLiteInput(
                path,
                """WITH RECURSIVE numbers(x) AS (
                SELECT 1 UNION ALL SELECT x+1 FROM numbers WHERE x<1000000000
                ) SELECT '001' AS id, CAST(sum(x) AS TEXT) AS amount FROM numbers""",
                spec(),
            ).load(run)
    finally:
        if timer is not None:
            timer.cancel()
            timer.join(timeout=5)
    assert time.perf_counter() - started < 5
    assert not list(tmp_path.glob("sqlite_*.jsonl"))
    # An owned read transaction was closed, so another writer can commit.
    with sqlite3.connect(path, timeout=0.1) as db:
        db.execute("INSERT INTO input VALUES ('002','1.00')")
