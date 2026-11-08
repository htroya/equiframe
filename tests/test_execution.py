"""Real engine integrations and small independent expected results; no benchmark."""

import math
import runpy
import threading
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import equiframe as ef

DEMO = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "execute_native.py"))
ENGINES = ("pandas", "polars", "duckdb")


def identity(
    engine,
    table,
    tmp_path,
    *,
    logical=None,
    options=None,
    source=None,
    callback=None,
    sql=None,
    **execution_kwargs,
):
    logical = logical or ef.StringType()
    columns = tuple(DEMO["column"](name, logical) for name in table.column_names)
    contract = DEMO["contract"]("nulls_types", {"items": columns}, columns)
    registry = ef.TransformationRegistry()
    if engine == "pandas":
        registry.register(
            ef.PandasTransformation(
                "identity", callback or (lambda t, c: t["items"].copy(deep=True)), "test.v1"
            )
        )
    elif engine == "polars":
        registry.register(
            ef.PolarsTransformation(
                "identity", callback or (lambda t, c: t["items"].lazy()), "test.v1"
            )
        )
    else:
        registry.register(
            ef.DuckDBTransformation("identity", sql or 'SELECT * FROM "items"', "test.v1")
        )
    return ef.execute(
        ef.ExecutionPlan(
            contract=contract,
            engine=engine,
            transformation_id="identity",
            options=options or ef.ExecutionOptions(),
        ),
        source=source
        if source is not None
        else ef.LocalDataSource({"items": ef.ArrowInput(table)}),
        registry=registry,
        work_dir=tmp_path,
        **execution_kwargs,
    )


def data(result):
    assert result.state == "completed", result.problem
    assert result.output is not None
    return ef.read_table(result.output.data)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("case_index", range(5))
def test_five_families_native(engine, case_index, tmp_path):
    case = DEMO["cases"]()[case_index]
    result = ef.execute(
        ef.ExecutionPlan(
            contract=case.contract, engine=engine, transformation_id=case.contract.family
        ),
        source=ef.LocalDataSource({n: ef.ArrowInput(t) for n, t in case.inputs.items()}),
        registry=DEMO["registry"](),
        work_dir=tmp_path,
    )
    DEMO["assert_expected"](data(result).to_pylist(), case.expected)
    assert result.implementation_version == "synthetic.v1"
    assert result.contract_sha256 == ef.contract_fingerprint(case.contract)
    assert (
        ef.ExecutionResult.model_validate_json(next(tmp_path.glob("*/*/run.json")).read_bytes())
        == result
    )
    if engine == "polars":
        stages = {t.stage for t in result.timings}
        assert {"planning", "materialization"} <= stages


@pytest.mark.parametrize("engine", ENGINES)
def test_empty_input_and_empty_output(engine, tmp_path):
    table = pa.table({"id": pa.array([], type=pa.string())})
    assert data(identity(engine, table, tmp_path)).num_rows == 0
    table = pa.table({"id": ["001"]})
    callback = (
        (lambda t, c: t["items"].head(0))
        if engine != "polars"
        else (lambda t, c: t["items"].lazy().head(0))
    )
    result = identity(
        engine, table, tmp_path, callback=callback, sql='SELECT * FROM "items" WHERE FALSE'
    )
    assert data(result).num_rows == 0


@pytest.mark.parametrize("engine", ENGINES)
def test_duplicate_ids_observed_order_and_input_untouched(engine, tmp_path):
    table = pa.table({"id": ["003", "001", "001", "002"]})
    assert data(identity(engine, table, tmp_path)).column("id").to_pylist() == [
        "003",
        "001",
        "001",
        "002",
    ]
    assert table.column("id").to_pylist() == ["003", "001", "001", "002"]


@pytest.mark.parametrize("engine", ENGINES)
def test_decimal_exact_beyond_float53(engine, tmp_path):
    value = Decimal("9007199254740993.01")
    table = pa.table(
        {"amount": pa.array([value, None, Decimal("0.00")], type=pa.decimal128(20, 2))}
    )
    result = identity(engine, table, tmp_path, logical=ef.DecimalType(precision=20, scale=2))
    assert data(result).column("amount").to_pylist() == [value, None, Decimal("0.00")]


@pytest.mark.parametrize("engine", ENGINES)
def test_decimal_declared_capacity(engine, tmp_path):
    table = pa.table({"amount": pa.array([Decimal("1.00")], type=pa.decimal256(50, 2))})
    result = identity(engine, table, tmp_path, logical=ef.DecimalType(precision=50, scale=2))
    if engine == "pandas":
        assert data(result).column("amount").to_pylist() == [Decimal("1.00")]
    else:
        assert result.state == "invalid_input"
        assert result.problem.code == "unsupported_capability"
        assert result.problem.stage == "preflight"


@pytest.mark.parametrize("engine", ENGINES)
def test_observed_decimal_capacity_is_checked_even_when_contract_disagrees(engine, tmp_path):
    table = pa.table({"amount": pa.array([Decimal("1.00")], type=pa.decimal256(50, 2))})
    result = identity(engine, table, tmp_path, logical=ef.DecimalType(precision=10, scale=2))
    if engine == "pandas":
        assert data(result).column("amount")[0].as_py() == Decimal("1.00")
    else:
        assert result.state == "invalid_input"
        assert result.inputs[0].columns[0].arrow_type == "decimal256(50, 2)"


@pytest.mark.parametrize("engine", ENGINES)
def test_null_nan_zero_and_signed_zero(engine, tmp_path):
    table = pa.table(
        {"v": pa.array([None, float("nan"), 0.0, -0.0], type=pa.float64(), from_pandas=False)}
    )
    result = identity(engine, table, tmp_path, logical=ef.FloatType(bits=64))
    values = data(result).column("v").to_pylist()
    assert values[0] is None and math.isnan(values[1]) and values[2] == 0.0
    assert math.copysign(1.0, values[3]) == -1.0
    assert result.output.columns[0].null_count == 1
    assert result.output.columns[0].nan_count == 1


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("zoned", (False, True))
def test_nanoseconds_zone_and_mask(engine, zoned, tmp_path):
    zone = "UTC" if zoned else None
    epoch = 1700000000123456789
    table = pa.table({"t": pa.array([epoch, None], type=pa.timestamp("ns", tz=zone))})
    result = identity(engine, table, tmp_path, logical=ef.TimestampType(unit="ns", timezone=zone))
    if engine == "duckdb" and zoned:
        assert result.state == "invalid_input"
        assert result.problem.code == "unsupported_capability"
    else:
        observed = data(result).column("t").cast(pa.int64()).to_pylist()
        assert observed == [epoch, None]
        assert data(result).schema.field("t").type.tz == zone


@pytest.mark.parametrize("engine", ENGINES)
def test_zoned_us_offset_around_dst(engine, tmp_path):
    zone = "Europe/Berlin"
    values = [
        datetime.fromisoformat("2024-10-27T02:30:00.123456+02:00"),
        datetime.fromisoformat("2024-10-27T02:30:00.123456+01:00"),
    ]
    table = pa.table({"t": pa.array(values, type=pa.timestamp("us", tz=zone))})
    result = identity(
        engine,
        table,
        tmp_path,
        logical=ef.TimestampType(unit="us", timezone=zone),
        options=ef.ExecutionOptions(duckdb_timezone=zone),
    )
    actual = data(result).column("t")
    assert actual.cast(pa.int64()).to_pylist() == table.column("t").cast(pa.int64()).to_pylist()
    assert actual.type.tz == zone


def test_pandas_consumer_and_index_mutation_protected(tmp_path):
    frame = pd.DataFrame({"id": ["001", "001"]}, index=pd.Index(["a", "b"], name="row_id"))
    original = frame.copy(deep=True)

    def mutate(tables, ctx):
        tables["items"].iloc[0, 0] = "changed"
        try:
            tables["items"].index.values[0] = "changed-index"
        except ValueError as error:
            if "read-only" not in str(error):
                raise
            index_values = tables["items"].index.tolist()
            index_values[0] = "changed-index"
            tables["items"].index = pd.Index(index_values, name=tables["items"].index.name)
        assert tables["items"].index[0] == "changed-index"
        return tables["items"]

    result = identity(
        "pandas",
        pa.table({"id": ["001", "001"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
        callback=mutate,
    )
    assert data(result).column("id").to_pylist() == ["changed", "001"]
    assert frame["id"].tolist() == ["001", "001"]
    assert frame.index.tolist() == ["a", "b"]
    assert result.output.index is not None
    assert ef.read_table(result.output.index).column(0).to_pylist() == ["changed-index", "b"]
    assert original["id"].tolist() == frame["id"].tolist()


@pytest.mark.parametrize("engine", ("polars", "duckdb"))
def test_index_requires_explicit_transport_policy(engine, tmp_path):
    frame = pd.DataFrame({"id": ["001"]}, index=pd.Index(["key"], name="row_id"))
    result = identity(
        engine,
        pa.table({"id": ["001"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    assert result.state == "invalid_input"
    result = identity(
        engine,
        pa.table({"id": ["001"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame, index_policy="columns")}),
    )
    assert data(result).column("row_id").to_pylist() == ["key"]


def test_polars_lazy_input_and_consumer_protected(tmp_path):
    frame = pl.DataFrame({"id": ["001", "002"]})

    def mutate(tables, ctx):
        tables["items"].drop_in_place("id")
        return pl.DataFrame({"id": ["done"]}).lazy()

    result = identity(
        "polars",
        pa.table({"id": ["001", "002"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PolarsInput(frame.lazy())}),
        callback=mutate,
    )
    assert data(result).column("id").to_pylist() == ["done"]
    assert frame["id"].to_list() == ["001", "002"]
    assert "input_materialization" in {t.stage for t in result.timings}


@pytest.mark.parametrize(
    "values", ([Decimal("-0.00")], [Decimal("1.0"), Decimal("1.00")], [["nested"]])
)
def test_pandas_uncapturable_object_values_fail_before_callback(values, tmp_path):
    frame = pd.DataFrame({"id": values}, dtype=object)
    result = identity(
        "pandas",
        pa.table({"id": ["001"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"


def test_pandas_nan_already_conflated_records_limit(tmp_path):
    frame = pd.DataFrame({"v": [None, float("nan"), 0.0]})
    table = pa.table({"v": [1.0]})
    result = identity(
        "pandas",
        table,
        tmp_path,
        logical=ef.FloatType(bits=64),
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    values = data(result).column("v").to_pylist()
    assert math.isnan(values[0]) and math.isnan(values[1]) and values[2] == 0.0
    assert result.inputs[0].columns[0].null_count == 0
    assert any("cannot be recovered" in n for n in result.inputs[0].notes)


@pytest.mark.parametrize("engine", ENGINES)
def test_observed_mismatch_is_not_cast_to_contract(engine, tmp_path):
    table = pa.table({"id": ["001"]})
    callback = (
        (lambda t, c: pd.DataFrame({"unexpected": [3.5]}))
        if engine == "pandas"
        else (lambda t, c: pl.DataFrame({"unexpected": [3.5]}).lazy())
    )
    result = identity(
        engine, table, tmp_path, callback=callback, sql="SELECT 3.5::DOUBLE AS unexpected"
    )
    assert data(result).to_pylist() == [{"unexpected": 3.5}]
    assert result.output.columns[0].name == "unexpected"
    assert result.plan.contract.output.schema_spec.columns[0].name == "id"


@pytest.mark.parametrize("engine", ENGINES)
def test_callback_or_sql_failure_preserves_inputs(engine, tmp_path):
    def fail(tables, context):
        raise RuntimeError("secret example should not be included in the manifest")

    result = identity(
        engine,
        pa.table({"id": ["001"]}),
        tmp_path,
        callback=fail,
        sql="SELECT no_such_column FROM items",
    )
    assert result.state == "failed" and result.output is None and len(result.inputs) == 1
    assert "secret example" not in result.model_dump_json()


@pytest.mark.parametrize("engine", ENGINES)
def test_materialized_resource_limits(engine, tmp_path):
    result = identity(
        engine, pa.table({"id": ["001"]}), tmp_path, options=ef.ExecutionOptions(max_output_rows=0)
    )
    assert result.state == "resource_exhausted"
    assert result.output is None
    result = identity(
        engine, pa.table({"id": ["001"]}), tmp_path, options=ef.ExecutionOptions(max_input_rows=0)
    )
    assert result.state == "resource_exhausted" and not result.inputs


def test_callback_timeout_is_cooperative_and_returns_after_callback(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import equiframe.execution as execution

    clock = [10.0]
    monkeypatch.setattr(execution, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    finished = []
    table = pa.table({"id": ["001"]})

    def slow(tables, context):
        assert context.deadline == 10.05
        clock[0] = 10.25
        finished.append(True)
        return tables["items"]

    result = identity(
        "pandas", table, tmp_path, callback=slow, options=ef.ExecutionOptions(timeout_seconds=0.05)
    )
    assert result.state == "timeout" and finished == [True] and result.output is None
    assert result.elapsed_seconds == 0.25


def test_timeout_before_callback_does_not_start_callback(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import equiframe.execution as execution

    ticks = iter((10.0, 10.25))
    monkeypatch.setattr(execution, "time", SimpleNamespace(perf_counter=lambda: next(ticks, 10.25)))

    def never(tables, context):
        raise AssertionError("expired execution must not enter callback")

    result = identity(
        "pandas",
        pa.table({"id": ["001"]}),
        tmp_path,
        callback=never,
        options=ef.ExecutionOptions(timeout_seconds=0.05),
    )
    assert result.state == "timeout" and result.output is None and not result.inputs


def test_cancellation_at_callback_checkpoint(tmp_path):
    token = ef.CancellationToken()

    def cancel(tables, ctx):
        ctx.cancellation.cancel()
        ctx.check()
        raise AssertionError("unreachable")

    result = identity("pandas", pa.table({"id": ["001"]}), tmp_path, callback=cancel)
    assert result.state == "cancelled"
    token.cancel()
    case = DEMO["cases"]()[0]
    result = ef.execute(
        ef.ExecutionPlan(contract=case.contract, engine="pandas", transformation_id="nulls_types"),
        source=ef.LocalDataSource({"items": ef.ArrowInput(case.inputs["items"])}),
        registry=DEMO["registry"](),
        work_dir=tmp_path,
        cancellation=token,
    )
    assert result.state == "cancelled" and result.inputs == ()


def test_duckdb_interrupt_and_connection_close_even_on_failure(tmp_path, monkeypatch):
    opened = []
    original = duckdb.connect

    def observe(*args, **kwargs):
        connection = original(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(duckdb, "connect", observe)
    table = pa.table({"id": ["001"]})
    data(identity("duckdb", table, tmp_path))
    result = identity(
        "duckdb",
        table,
        tmp_path,
        sql="SELECT sum(i) AS result FROM range(100000000000) t(i)",
        options=ef.ExecutionOptions(timeout_seconds=1.0),
    )
    assert result.state == "timeout" and result.problem.stage == "transformation"
    failed = identity("duckdb", table, tmp_path, sql="SELECT missing FROM items")
    assert failed.state == "failed"
    for connection in opened:
        with pytest.raises(duckdb.ConnectionException):
            connection.execute("SELECT 1")
    assert not any(t.name.endswith("_interrupt") for t in threading.enumerate())
    data(identity("duckdb", table, tmp_path))


def test_duckdb_values_are_bound_and_identifiers_are_controlled(tmp_path):
    case = DEMO["cases"]()[0]
    registry = ef.TransformationRegistry()
    registry.register(
        ef.DuckDBTransformation("pick", "SELECT id FROM items WHERE id=$chosen", "test.v1")
    )
    text = "001' OR TRUE --"
    result = ef.execute(
        ef.ExecutionPlan(
            contract=case.contract,
            engine="duckdb",
            transformation_id="pick",
            parameters=(ef.Parameter(name="chosen", value=ef.StringValue(value=text)),),
        ),
        source=ef.LocalDataSource({"items": ef.ArrowInput(case.inputs["items"])}),
        registry=registry,
        work_dir=tmp_path,
    )
    assert data(result).num_rows == 0
    result = identity("duckdb", pa.table({"id": ["001"]}), tmp_path, sql="SELECT $missing AS id")
    assert result.state == "invalid_input"
    result = identity(
        "duckdb",
        pa.table({"id": ["001"]}),
        tmp_path,
        sql="CREATE TABLE hidden(i INTEGER); SELECT 1 AS id",
    )
    assert result.state == "invalid_input"


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("format_name", ("arrow", "parquet"))
def test_local_file_integrity_and_exchange(engine, format_name, tmp_path):
    table = pa.table({"id": ["001", "001"]})
    source = tmp_path / ("source." + format_name)
    if format_name == "parquet":
        pq.write_table(table, source)
    else:
        with pa.OSFile(str(source), "wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)
    store = ef.LocalArtifactStore(tmp_path / "source-store")
    ref = store.put(source, media_type="application/octet-stream")
    result = identity(engine, table, tmp_path / "runs", source=ef.LocalDataSource({"items": ref}))
    assert data(result).to_pylist() == [{"id": "001"}, {"id": "001"}]
    assert result.inputs[0].origin == ref
    bad = ref.model_copy(update={"sha256": "0" * 64})
    failed = identity(engine, table, tmp_path / "runs", source=ef.LocalDataSource({"items": bad}))
    assert failed.state == "invalid_input" and failed.problem.code == "artifact_integrity_error"
    assert source.exists()


@pytest.mark.parametrize("engine", ENGINES)
def test_independent_concurrent_runs_do_not_mix(engine, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    def run(identifier):
        return identity(engine, pa.table({"id": [identifier]}), tmp_path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(run, ["001", "002"]))
    assert first.run_id != second.run_id and first.execution_id != second.execution_id
    assert first.output.data.uri != second.output.data.uri
    assert data(first).to_pylist() == [{"id": "001"}]
    assert data(second).to_pylist() == [{"id": "002"}]
    assert len(list(tmp_path.glob("*/*/run.json"))) == 2


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("unit", ("s", "ms", "us"))
def test_naive_time_units_are_preserved_without_truncation(engine, unit, tmp_path):
    value = 1700000000123 if unit == "ms" else (1700000000123456 if unit == "us" else 1700000000)
    table = pa.table({"t": pa.array([value, None], type=pa.timestamp(unit))})
    result = identity(engine, table, tmp_path, logical=ef.TimestampType(unit=unit, timezone=None))
    actual = data(result).column("t")
    # A physical precision widening may occur; cast to the source unit must be lossless.
    assert actual.cast(pa.timestamp(unit), safe=True).cast(pa.int64()).to_pylist() == [value, None]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "dtype,logical,values",
    (
        (pa.uint64(), ef.IntegerType(bits=64, signed=False), [2**64 - 1, 0, None]),
        (pa.int8(), ef.IntegerType(bits=8, signed=True), [-128, 127, None]),
        (pa.bool_(), ef.BooleanType(), [True, False, None]),
        (pa.float32(), ef.FloatType(bits=32), [0.5, -0.0, None]),
    ),
)
def test_scalar_types_boundaries_and_masks(engine, dtype, logical, values, tmp_path):
    result = identity(
        engine, pa.table({"v": pa.array(values, type=dtype)}), tmp_path, logical=logical
    )
    assert data(result).column("v").to_pylist() == values


def test_duckdb_actual_memory_limit_and_invalid_sql(tmp_path):
    table = pa.table({"id": ["001"]})
    result = identity(
        "duckdb",
        table,
        tmp_path,
        sql="SELECT i FROM range(1000000) t(i) ORDER BY i DESC",
        options=ef.ExecutionOptions(duckdb_memory_mb=1),
    )
    assert result.state == "resource_exhausted"
    assert result.problem.code == "resource_limit"
    result = identity("duckdb", table, tmp_path, sql="SELECT (")
    assert result.state == "failed" and result.problem.exception_type == "ParserException"
    data(identity("duckdb", table, tmp_path))


def test_duckdb_cancellation_during_native_query(tmp_path):
    table = pa.table({"id": ["001"]})
    data(identity("duckdb", table, tmp_path))
    token = ef.CancellationToken()
    case = DEMO["cases"]()[0]
    registry = ef.TransformationRegistry()
    registry.register(
        ef.DuckDBTransformation("slow", "SELECT sum(i) FROM range(100000000000) t(i)", "test.v1")
    )
    finished = threading.Event()

    def cancel_active_query():
        deadline = time.perf_counter() + 10.0
        while time.perf_counter() < deadline and not finished.is_set():
            if any(t.name.endswith("_interrupt") for t in threading.enumerate()):
                time.sleep(0.05)
                token.cancel()
                return
            time.sleep(0.005)

    thread = threading.Thread(target=cancel_active_query)
    thread.start()
    try:
        result = ef.execute(
            ef.ExecutionPlan(contract=case.contract, engine="duckdb", transformation_id="slow"),
            source=ef.LocalDataSource({"items": ef.ArrowInput(case.inputs["items"])}),
            registry=registry,
            work_dir=tmp_path,
            cancellation=token,
        )
    finally:
        finished.set()
        thread.join()
    assert result.state == "cancelled" and result.problem.stage == "transformation"
    assert not any(t.name.endswith("_interrupt") for t in threading.enumerate())


@pytest.mark.parametrize("engine", ENGINES)
def test_join_null_keys_are_captured_with_native_semantics(engine, tmp_path):
    case = DEMO["cases"]()[2]
    left = pa.table({"id": ["001"], "product_id": pa.array([None], type=pa.string())})
    right = pa.table(
        {"product_id": pa.array([None], type=pa.string()), "category": ["null-key-match"]}
    )
    result = ef.execute(
        ef.ExecutionPlan(contract=case.contract, engine=engine, transformation_id="joins"),
        source=ef.LocalDataSource(
            {"orders": ef.ArrowInput(left), "products": ef.ArrowInput(right)}
        ),
        registry=DEMO["registry"](),
        work_dir=tmp_path,
    )
    expected = "null-key-match" if engine == "pandas" else None
    assert data(result).to_pylist() == [{"id": "001", "product_id": None, "category": expected}]


def test_arrow_buffers_detached_from_mutable_consumer(tmp_path):
    import numpy as np

    values = np.array([1, 2], dtype=np.int64)
    table = pa.table({"v": pa.array(values)})

    def mutate(tables, ctx):
        values[0] = 999  # Mutate original input after loading; callback still sees its snapshot.
        return tables["items"]

    result = identity(
        "pandas", table, tmp_path, logical=ef.IntegerType(bits=64, signed=True), callback=mutate
    )
    assert data(result).column("v").to_pylist() == [1, 2]


def test_memory_and_transport_budget_diagnostics(tmp_path):
    table = pa.table({"id": ["001"]})

    def exhausted(tables, ctx):
        raise MemoryError()

    result = identity("pandas", table, tmp_path, callback=exhausted)
    assert result.state == "resource_exhausted"
    result = identity("pandas", table, tmp_path, options=ef.ExecutionOptions(max_transport_bytes=1))
    assert result.state == "resource_exhausted"


@pytest.mark.parametrize("engine", ENGINES)
def test_date64_full_days_and_subday_capacity(engine, tmp_path):
    from datetime import date

    table = pa.table({"d": pa.array([86400000, None], type=pa.date64())})
    result = identity(engine, table, tmp_path, logical=ef.DateType())
    if engine == "polars":
        assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
    else:
        assert data(result).column("d").to_pylist() == [date(1970, 1, 2), None]
    subday = pa.table({"d": pa.array([86400001], type=pa.date64())})
    result = identity(engine, subday, tmp_path, logical=ef.DateType())
    assert result.state == "invalid_input" and result.problem.code == "invalid_execution_input"


def test_external_ports_adapter_and_shared_store_injection(tmp_path):
    class ExternalSource:
        table_names = ("items",)

        def resolve(self, name, *, context):
            assert name == "items"
            return ef.LoadedTable(
                pa.table({"id": ["007"]}), notes=("explicit external source adapter",)
            )

    table = pa.table({"id": ["007"]})
    columns = (DEMO["column"]("id", ef.StringType()),)
    contract = DEMO["contract"]("nulls_types", {"items": columns}, columns)
    registry = ef.TransformationRegistry()
    registry.register(ef.DuckDBTransformation("identity", "SELECT * FROM items", "test.v1"))
    plan = ef.ExecutionPlan(contract=contract, engine="duckdb", transformation_id="identity")
    store = ef.LocalArtifactStore(tmp_path / "shared-store")
    results = [
        ef.execute(
            plan,
            source=ExternalSource(),
            registry=registry,
            adapter=ef.DuckDBAdapter(),
            artifact_store=store,
            work_dir=tmp_path / "runs",
        )
        for _ in range(2)
    ]
    assert results[0].output.data.uri != results[1].output.data.uri
    for result in results:
        assert data(result).to_pylist() == table.to_pylist()
        assert result.inputs[0].notes == ("explicit external source adapter",)


def test_partial_arrow_capture_failure_cleans_temporary_file(tmp_path, monkeypatch):
    original = pa.ipc.new_file

    class InterruptedWriter:
        def __init__(self, writer):
            self.writer = writer

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.writer.close()

        def write_table(self, table):
            self.writer.write_table(table)
            raise OSError("injected fault after writing a real Arrow file")

    def interrupt_file_capture(sink, *args, **kwargs):
        writer = original(sink, *args, **kwargs)
        return InterruptedWriter(writer) if isinstance(sink, pa.OSFile) else writer

    monkeypatch.setattr(pa.ipc, "new_file", interrupt_file_capture)
    table = pa.table({"id": ["001"]})
    result = identity("pandas", table, tmp_path)
    assert result.state == "failed"
    assert len(list(tmp_path.glob("*/*/run.json"))) == 1
    assert not list(tmp_path.glob("*/*/*.arrow"))
    assert table.to_pylist() == [{"id": "001"}]


@pytest.mark.parametrize("engine", ENGINES)
def test_column_names_differing_only_by_case_are_not_silently_renamed(engine, tmp_path):
    table = pa.table({"Id": ["01"], "id": ["02"]})
    result = identity(engine, table, tmp_path)
    if engine == "duckdb":
        assert result.state == "invalid_input"
        assert result.problem.code == "unsupported_capability"
        assert result.output is None
        assert ef.read_table(result.inputs[0].data).equals(table)
    else:
        output = data(result)
        assert output.column_names == table.column_names
        assert output.to_pylist() == table.to_pylist()
    assert table.to_pylist() == [{"Id": "01", "id": "02"}]
