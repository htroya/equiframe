"""Second review: real transport boundaries, truthful evidence and failure cleanup."""

import math
from decimal import Decimal

import duckdb
import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
import pytest
from pydantic import ValidationError
from test_execution import ENGINES, data, identity

import equiframe as ef
from equiframe.tables import pandas_capture

INTEGER_CASES = [
    pytest.param(
        ("UInt" if unsigned else "Int") + str(bits)
        if nullable
        else ("u" if unsigned else "") + f"int{bits}",
        [0 if unsigned else -(2 ** (bits - 1)), 2**bits - 1 if unsigned else 2 ** (bits - 1) - 1]
        + ([None] if nullable else []),
        getattr(pa, ("uint" if unsigned else "int") + str(bits))(),
        id=f"{'nullable' if nullable else 'numpy'}-{'u' if unsigned else ''}int{bits}",
    )
    for bits in (8, 16, 32, 64)
    for unsigned in (False, True)
    for nullable in (False, True)
]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("dtype,values,arrow_type", INTEGER_CASES)
def test_native_pandas_integer_widths_bounds_and_masks(engine, dtype, values, arrow_type, tmp_path):
    frame = pd.DataFrame({"v": pd.Series(values, dtype=dtype)})
    before = frame.copy(deep=True)
    table = pa.table({"v": pa.array([], type=arrow_type)})
    result = identity(
        engine, table, tmp_path, source=ef.LocalDataSource({"items": ef.PandasInput(frame)})
    )
    assert data(result)["v"].to_pylist() == values
    assert ef.read_table(result.inputs[0].data)["v"].type == arrow_type
    assert result.inputs[0].columns[0].engine_type == dtype
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("bits", (32, 64))
def test_native_nullable_floating_array_retains_independent_nan_mask(engine, bits, tmp_path):
    values = np.array([float("nan"), 0.0, -0.0, 7.125], dtype=getattr(np, f"float{bits}"))
    mask = np.array([False, False, False, True])
    frame = pd.DataFrame({"v": pd.Series(pd.arrays.FloatingArray(values, mask))})
    table = pa.table({"v": pa.array([], type=getattr(pa, f"float{bits}")())})
    result = identity(
        engine, table, tmp_path, source=ef.LocalDataSource({"items": ef.PandasInput(frame)})
    )
    observed = data(result)["v"].to_pylist()
    assert math.isnan(observed[0]) and observed[3] is None
    assert math.copysign(1, observed[1]) == 1 and math.copysign(1, observed[2]) == -1
    assert result.inputs[0].columns[0].null_count == 1
    assert result.inputs[0].columns[0].nan_count == 1
    assert result.output.columns[0].null_count == 1
    assert result.output.columns[0].nan_count == 1
    assert not bool(frame["v"].array.isna()[0])


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "dtype,values", (("boolean", [True, None, False]), ("string", ["001", None, ""]))
)
def test_native_nullable_boolean_and_string(engine, dtype, values, tmp_path):
    frame = pd.DataFrame({"v": pd.Series(values, dtype=dtype)})
    result = identity(
        engine,
        pa.table({"v": []}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    assert data(result)["v"].to_pylist() == values


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("location", ("column", "index", "column_labels"))
def test_pandas_categories_are_rejected_before_erasing_dictionary_and_order(
    engine, location, tmp_path
):
    categories = pd.Categorical(["b", "a"], categories=["b", "a", "unused"], ordered=True)
    frame = pd.DataFrame({"id": categories if location == "column" else ["001", "002"]})
    if location == "index":
        frame.index = pd.CategoricalIndex(categories, name="category")
    elif location == "column_labels":
        frame.columns = pd.CategoricalIndex(["id"], categories=["id", "unused"], ordered=True)
    result = identity(
        engine,
        pa.table({"id": ["001", "002"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
    assert result.inputs == () and result.output is None
    dtype = (
        frame["id"].dtype
        if location == "column"
        else (frame.index.dtype if location == "index" else frame.columns.dtype)
    )
    assert dtype.ordered


@pytest.mark.parametrize("values", ((1, 0.5), (9007199254740993, 0.5), (Decimal("1.00"), 1)))
def test_heterogeneous_object_numeric_kinds_are_not_coerced(values, tmp_path):
    frame = pd.DataFrame({"v": pd.Series(values, dtype=object)})
    result = identity(
        "pandas",
        pa.table({"v": []}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
    assert tuple(type(value) for value in frame["v"]) == tuple(type(value) for value in values)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    "dtype,value",
    ((pa.decimal128(8, -2), Decimal("12300")), (pa.decimal256(20, 2), Decimal("123.45"))),
)
def test_decimal_storage_width_and_negative_scale_capabilities(engine, dtype, value, tmp_path):
    table = pa.table({"v": pa.array([value], type=dtype)})
    result = identity(engine, table, tmp_path)
    if engine == "pandas":
        assert data(result)["v"].to_pylist() == [value]
        assert data(result)["v"].type == dtype
    else:
        assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
        assert result.output is None
        assert ef.read_table(result.inputs[0].data).equals(table)


@pytest.mark.parametrize(
    "seconds", (-(2**63), 2**63 - 1, -(2**63 // 1000) - 1, (2**63 - 1) // 1000 + 1)
)
def test_polars_seconds_overflow_is_rejected_without_wraparound(seconds, tmp_path):
    table = pa.table({"v": pa.array([seconds, None], type=pa.timestamp("s"))})
    result = identity("polars", table, tmp_path)
    assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
    assert result.output is None
    assert ef.read_table(result.inputs[0].data)["v"].cast(pa.int64()).to_pylist() == [seconds, None]


@pytest.mark.parametrize("seconds", (-(2**63 // 1000), (2**63 - 1) // 1000))
def test_polars_seconds_safe_range_boundary_retains_epoch(seconds, tmp_path):
    table = pa.table({"v": pa.array([seconds, None], type=pa.timestamp("s"))})
    output = data(identity("polars", table, tmp_path))
    assert output["v"].type == pa.timestamp("ms")
    assert output["v"].cast(pa.int64()).to_pylist() == [seconds * 1000, None]


@pytest.mark.parametrize("unit", ("s", "ms", "us", "ns"))
@pytest.mark.parametrize("ticks", (2**63 - 1, -(2**63 - 1), -(2**63)))
def test_duckdb_reserved_temporal_ticks_rejected_before_becoming_infinity(unit, ticks, tmp_path):
    table = pa.table({"v": pa.array([ticks], type=pa.timestamp(unit))})
    result = identity("duckdb", table, tmp_path)
    assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
    assert result.output is None
    assert ef.read_table(result.inputs[0].data)["v"].cast(pa.int64()).to_pylist() == [ticks]


@pytest.mark.parametrize(
    "sql",
    (
        "SELECT 'infinity'::TIMESTAMP AS v",
        "SELECT '-infinity'::TIMESTAMPTZ AS v",
        "SELECT 'infinity'::DATE AS v",
    ),
)
def test_duckdb_native_temporal_infinity_is_not_published_as_finite_arrow(sql, tmp_path):
    result = identity("duckdb", pa.table({"id": ["001"]}), tmp_path, sql=sql)
    assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
    assert result.output is None and result.problem.stage == "materialization"


def test_polars_native_panic_becomes_a_failed_result_with_manifest(tmp_path):
    def native_panic(tables, context):
        # Real unsupported Polars FFI operation inside trusted callback code.
        return pl.from_arrow(
            pa.table({"v": pa.array([Decimal("1.00")], type=pa.decimal256(20, 2))})
        )

    result = identity("polars", pa.table({"id": ["001"]}), tmp_path, callback=native_panic)
    assert result.state == "failed" and result.problem.code == "native_engine_error"
    assert result.problem.stage == "planning" and result.output is None
    manifest = next(tmp_path.glob("*/*/run.json"))
    assert ef.ExecutionResult.model_validate_json(manifest.read_bytes()) == result


class FailingStore:
    def __init__(self, root, fail_on):
        self.delegate = ef.LocalArtifactStore(root)
        self.count = 0
        self.fail_on = fail_on

    def put(self, path, *, media_type):
        self.count += 1
        if self.count == self.fail_on:
            raise OSError("injected index publication failure")
        return self.delegate.put(path, media_type=media_type)

    def get(self, ref, destination):
        return self.delegate.get(ref, destination)


@pytest.mark.parametrize("input_native,fail_on", ((True, 2), (False, 3)))
def test_partial_index_capture_keeps_every_successfully_published_reference(
    input_native, fail_on, tmp_path
):
    table = pa.table({"id": ["001"]})
    store = FailingStore(tmp_path / "store", fail_on)
    source = (
        ef.LocalDataSource({"items": ef.PandasInput(pd.DataFrame({"id": ["001"]}))})
        if input_native
        else None
    )
    result = identity("pandas", table, tmp_path / "runs", source=source, artifact_store=store)
    assert result.state == "failed"
    captured = result.inputs[0] if input_native else result.output
    assert captured.index is None and any("incomplete" in note for note in captured.notes)
    assert ef.read_table(captured.data).to_pylist() == [{"id": "001"}]
    artifacts = [*result.inputs, *([result.output] if result.output else [])]
    known = {
        ref.uri
        for artifact in artifacts
        for ref in (artifact.data, artifact.index)
        if ref is not None
    }
    assert {path.resolve().as_uri() for path in (tmp_path / "store").glob("*.arrow")} == known
    assert not list((tmp_path / "runs").glob("*/*/*.arrow"))
    manifest = next((tmp_path / "runs").glob("*/*/run.json"))
    assert ef.ExecutionResult.model_validate_json(manifest.read_bytes()) == result


def test_index_buffers_respect_transport_budget_before_publication(tmp_path):
    frame = pd.DataFrame({"id": ["001"]}, index=pd.Index(["x" * 512], name="long_index"))
    result = identity(
        "pandas",
        pa.table({"id": ["001"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
        options=ef.ExecutionOptions(max_transport_bytes=64),
    )
    assert result.state == "resource_exhausted" and result.inputs == ()
    assert not list(tmp_path.glob("*/*/artifacts/*.arrow"))
    assert frame.index[0] == "x" * 512


def test_injected_native_pandas_source_cannot_mutate_consumer_index_or_columns(tmp_path):
    frame = pd.DataFrame({"id": ["001", "002"]}, index=pd.Index([41, 42]))
    frame.columns = pd.Index(["id"], dtype=object)
    before = frame.copy(deep=True)
    before.index = frame.index.copy(deep=True)
    before.columns = frame.columns.copy(deep=True)

    class Source:
        table_names = ("items",)

        def resolve(self, name, *, context):
            return pandas_capture(frame)

    def mutate(tables, context):
        native = tables["items"]
        index_values = native.index.to_numpy(copy=False)
        column_values = native.columns.to_numpy(copy=False)
        index_values.setflags(write=True)
        column_values.setflags(write=True)
        index_values[0] = 999
        column_values[0] = "changed"
        native.iloc[0, 0] = "changed"
        return native

    result = identity(
        "pandas", pa.table({"id": ["001", "002"]}), tmp_path, source=Source(), callback=mutate
    )
    assert data(result).column_names == ["changed"]
    pd.testing.assert_frame_equal(frame, before)
    assert ef.read_table(result.inputs[0].index)["level_0"].to_pylist() == [41, 42]


def test_native_unsigned_and_nullable_pandas_index_is_captured(tmp_path):
    frame = pd.DataFrame(
        {"id": ["001", "002"]},
        index=pd.Index(pd.array([2**64 - 1, None], dtype="UInt64"), name="key"),
    )
    result = identity(
        "pandas",
        pa.table({"id": ["001", "002"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.PandasInput(frame)}),
    )
    assert data(result).to_pylist() == [{"id": "001"}, {"id": "002"}]
    observed = ef.read_table(result.output.index)["level_0"]
    assert observed.type == pa.uint64() and observed.to_pylist() == [2**64 - 1, None]


def test_partial_artifact_download_failure_cleans_owned_destination(tmp_path):
    input_file = tmp_path / "input.arrow"
    table = pa.table({"id": ["001"]})
    with input_file.open("wb") as stream, pa.ipc.new_file(stream, table.schema) as writer:
        writer.write_table(table)
    ref = ef.LocalArtifactStore(tmp_path / "origin").put(
        input_file, media_type="application/vnd.apache.arrow.file"
    )

    class PartialDownloadStore:
        def get(self, ref, destination):
            destination.write_bytes(b"partial")
            raise OSError("injected download failure")

        def put(self, path, *, media_type):
            raise AssertionError("nothing should be published")

    result = identity(
        "duckdb",
        table,
        tmp_path / "runs",
        source=ef.LocalDataSource({"items": ref}),
        artifact_store=PartialDownloadStore(),
    )
    assert result.state == "failed" and result.inputs == ()
    assert not list((tmp_path / "runs").glob("*/*/input_*"))


def test_successful_nested_source_stage_does_not_mask_later_input_load_failure(tmp_path):
    class Source:
        table_names = ("items",)

        def resolve(self, name, *, context):
            with context.measure("nested_fetch"):
                assert context.stage == "nested_fetch"
            assert context.stage == "input_load"
            raise OSError("source failure after successful nested measurement")

    result = identity("duckdb", pa.table({"id": ["001"]}), tmp_path, source=Source())
    assert result.state == "failed" and result.problem.stage == "input_load"
    assert {timing.stage for timing in result.timings} >= {"nested_fetch", "input_load"}


def test_duckdb_cancel_during_real_connection_setup_closes_connection(tmp_path, monkeypatch):
    original = duckdb.connect
    opened = []
    token = ef.CancellationToken()

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)
        opened.append(connection)
        token.cancel()
        return connection

    monkeypatch.setattr(duckdb, "connect", connect)
    result = identity("duckdb", pa.table({"id": ["001"]}), tmp_path, cancellation=token)
    assert result.state == "cancelled" and result.problem.stage == "engine_setup"
    assert len(opened) == 1
    with pytest.raises(duckdb.ConnectionException):
        opened[0].execute("SELECT 1")


@pytest.mark.parametrize("names", (("items", "items"), ["items"], "items"))
def test_external_source_names_are_validated_before_resolve(names, tmp_path):
    class Source:
        table_names = names

        def resolve(self, name, *, context):
            raise AssertionError("invalid source must not be used")

    result = identity("duckdb", pa.table({"id": ["001"]}), tmp_path, source=Source())
    assert result.state == "invalid_input" and result.problem.stage == "preflight"


@pytest.mark.parametrize("engine", ENGINES)
def test_invalid_arrow_input_is_reported_as_invalid_input(engine, tmp_path):
    result = identity(
        engine,
        pa.table({"id": ["001"]}),
        tmp_path,
        source=ef.LocalDataSource({"items": ef.ArrowInput(object())}),
    )
    assert result.state == "invalid_input" and result.problem.code == "invalid_execution_input"


def test_invalid_store_media_type_does_not_publish_an_orphan(tmp_path):
    source = tmp_path / "input.json"
    source.write_text("{}", encoding="utf-8")
    store = ef.LocalArtifactStore(tmp_path / "store")
    with pytest.raises(ValidationError):
        store.put(source, media_type="")
    assert not list((tmp_path / "store").glob("*"))


@pytest.mark.parametrize(
    "case,code",
    (
        ("hash", "contract_fingerprint_mismatch"),
        ("missing_inputs", "missing_input_evidence"),
        ("duplicate_inputs", "invalid_input_evidence"),
        ("output_name", "output_evidence_mismatch"),
        ("engine", "engine_evidence_mismatch"),
        ("counts", "impossible_value_counts"),
        ("column_names", "duplicate_physical_column"),
        ("index_ref", "missing_index_artifact"),
        ("data_format", "table_artifact_format"),
    ),
)
def test_execution_manifest_rejects_structurally_false_evidence(case, code, tmp_path):
    result = identity(
        "duckdb",
        pa.table({"v": pa.array([None, float("nan")], from_pandas=False, type=pa.float64())}),
        tmp_path,
    )
    assert data(result).num_rows == 2
    payload = result.model_dump(mode="python")
    if case == "hash":
        payload["contract_sha256"] = "0" * 64
    elif case == "missing_inputs":
        payload["inputs"] = ()
    elif case == "duplicate_inputs":
        payload["inputs"] = payload["inputs"] * 2
    elif case == "output_name":
        payload["output"]["name"] = "other"
    elif case == "engine":
        payload["capabilities"]["engine"] = "pandas"
    elif case == "counts":
        payload["output"]["columns"][0]["null_count"] = 2
    elif case == "column_names":
        payload["output"]["columns"] *= 2
    elif case == "index_ref":
        payload["output"]["index_columns"] = payload["output"]["columns"]
    elif case == "data_format":
        payload["output"]["data"]["format"] = "json"
    with pytest.raises(ValidationError) as raised:
        ef.ExecutionResult.model_validate(payload)
    assert code in {issue["type"] for issue in raised.value.errors(include_input=False)}


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("rows", (0, 2))
def test_zero_column_tables_keep_cardinality_or_reject_explicitly(engine, rows, tmp_path):
    expected = pa.table({"id": ["001"] * rows})
    empty_columns = expected.select([])
    result = identity(
        engine,
        expected,
        tmp_path,
        source=ef.LocalDataSource({"items": ef.ArrowInput(empty_columns)}),
    )
    if engine == "duckdb" or (engine == "pandas" and rows > 0):
        assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
        assert result.output is None
    elif engine == "polars" and result.state == "invalid_input":
        # Old native conversions cannot preserve N rows with zero columns.
        # A safe refusal is permitted; successful execution may never lose N.
        assert rows > 0 and result.problem.code == "unsupported_capability"
        assert result.output is None
        assert result.problem.message == "Execution input could not be validated."
    else:
        assert data(result).num_rows == rows and data(result).num_columns == 0
    assert result.inputs[0].row_count == rows


@pytest.mark.parametrize(
    "values", ((2**31 - 1,), (-(2**31 - 1),), (-(2**31), -(2**31 - 1)), (-(2**31),))
)
def test_duckdb_date_infinity_sentinels_and_finite_minimum(values, tmp_path):
    table = pa.table({"v": pa.array(values, type=pa.date32())})
    result = identity("duckdb", table, tmp_path)
    if values == (-(2**31),):
        assert data(result)["v"].cast(pa.int32()).to_pylist() == list(values)
    else:
        assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
        assert result.output is None


@pytest.mark.parametrize("unit,factor", [("s", 1_000_000), ("ms", 1_000)])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("overflow", [False, True])
def test_duckdb_zoned_timestamp_microsecond_boundaries(unit, factor, sign, overflow, tmp_path):
    limit = (2**63 - 2) // factor
    ticks = sign * (limit + int(overflow))
    table = pa.table({"v": pa.array([ticks], type=pa.timestamp(unit, tz="UTC"))})
    result = identity("duckdb", table, tmp_path)
    assert ef.read_table(result.inputs[0].data)["v"].cast(pa.int64()).to_pylist() == [ticks]
    if overflow:
        assert result.state == "invalid_input" and result.problem.code == "unsupported_capability"
        assert result.output is None and result.problem.stage == "input_capabilities"
    else:
        output = data(result)
        assert output["v"].type == pa.timestamp("us", tz="UTC")
        assert output["v"].cast(pa.int64()).to_pylist() == [ticks * factor]


@pytest.mark.parametrize("axis", ("rows", "columns"))
def test_polars_lossy_input_conversion_never_runs_callback(axis, monkeypatch, tmp_path):
    native = pl.from_arrow
    table = pa.table({"id": ["001", "002"]})

    def lossy(value, *args, **kwargs):
        frame = native(value, *args, **kwargs)
        return frame.head(0) if axis == "rows" else frame.drop("id")

    def forbidden(tables, context):
        raise AssertionError("lossy input reached the transformation")

    monkeypatch.setattr(pl, "from_arrow", lossy)
    result = identity("polars", table, tmp_path, callback=forbidden)
    assert result.state == "invalid_input" and result.output is None
    assert result.problem.code == "unsupported_capability"
    assert result.problem.message == "Execution input could not be validated."


@pytest.mark.parametrize("source_kind", ("arrow", "polars"))
def test_polars_lossy_arrow_capture_is_explicit_failure(source_kind, monkeypatch, tmp_path):
    table = pa.table({"id": ["001", "002"]})
    native = pl.DataFrame.to_arrow

    def lossy(frame, *args, **kwargs):
        return native(frame, *args, **kwargs).slice(0, 0)

    source = ef.LocalDataSource(
        {"items": ef.PolarsInput(pl.from_arrow(table))}
        if source_kind == "polars"
        else {"items": ef.ArrowInput(table)}
    )
    monkeypatch.setattr(pl.DataFrame, "to_arrow", lossy)
    result = identity("polars", table, tmp_path, source=source)
    assert result.state == "invalid_input" and result.output is None
    assert result.problem.code == "unsupported_capability"
    assert result.problem.message == "Execution input could not be validated."
