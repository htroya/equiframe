"""Faithful, bounded direct-input capture without running another engine."""

import json
import math
import subprocess
import sys
from datetime import datetime
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from types import ModuleType
from typing import ClassVar

import duckdb
import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe._diff_capture import (
    DiffCaptureOptions,
    _CapturedInput,
    _NativeInput,
    capture_native,
)


def capture(value, **limits):
    return capture_native(value, DiffCaptureOptions(**limits))


def test_options_are_strict_frozen_and_have_inspectable_eager_limits():
    options = DiffCaptureOptions()
    assert options.model_dump() == {"max_rows": 1_000_000, "max_bytes": 256 * 1024 * 1024}
    assert DiffCaptureOptions.model_validate_json(options.model_dump_json()) == options
    for bad in (0, -1, True, 1.5, "1"):
        with pytest.raises(ValidationError):
            DiffCaptureOptions(max_rows=bad)
        with pytest.raises(ValidationError):
            DiffCaptureOptions(max_bytes=bad)
    with pytest.raises(ValidationError):
        DiffCaptureOptions(materialize_lazy=True)
    with pytest.raises(ValidationError):
        options.max_rows = 1


def test_native_input_defers_capture_and_captured_input_reuses_it():
    values = np.array([1], dtype=np.int64)
    pending = _NativeInput(pa.table({"value": values}), DiffCaptureOptions())
    values[0] = 2
    loaded = pending.load()
    reused = _CapturedInput(loaded)
    assert reused.load() is loaded
    values[0] = 3
    assert loaded.table.to_pydict() == {"value": [2]}


def test_arrow_retains_schema_null_nan_decimal_and_timezone():
    table = pa.table(
        {
            "nulls": pa.nulls(3),
            "floating": pa.array([None, float("nan"), -0.0], type=pa.float32()),
            "money": pa.array([Decimal("1.20"), None, Decimal("-2.30")], pa.decimal128(9, 2)),
            "time": pa.array([0, None, 1], pa.timestamp("ns", tz="America/Guayaquil")),
        }
    )
    loaded = capture(table)
    assert loaded.table.schema == table.schema
    assert loaded.table["nulls"].null_count == 3
    floats = loaded.table["floating"].to_pylist()
    assert floats[0] is None and math.isnan(floats[1])
    assert math.copysign(1, floats[2]) == -1
    assert loaded.table["money"].to_pylist() == [Decimal("1.20"), None, Decimal("-2.30")]
    assert loaded.table["time"].cast(pa.int64()).to_pylist() == [0, None, 1]
    assert dict(loaded.native_types)["money"] == "decimal128(9, 2)"


@pytest.mark.parametrize("table", [pa.table({}), pa.table({"value": pa.array([], pa.int16())})])
def test_empty_arrow_keeps_schema(table):
    loaded = capture(table)
    assert loaded.table.schema == table.schema
    assert loaded.table.num_rows == 0


def test_arrow_zero_columns_keeps_nonzero_row_count():
    table = pa.table({"removed": [1, 2]}).drop(["removed"])
    assert capture(table).table.num_rows == 2


def test_arrow_detaches_shared_numpy_values_and_validity():
    values = np.array([1, 2], dtype=np.int64)
    mask = bytearray([1])
    array = pa.Array.from_buffers(pa.int64(), 2, [pa.py_buffer(mask), pa.py_buffer(values)])
    loaded = capture(pa.table({"value": array}))
    values[:] = 7
    mask[0] = 3
    assert loaded.table.to_pydict() == {"value": [1, None]}


@pytest.mark.parametrize(
    "table",
    [
        pa.table({"value": [[1, 2]]}),
        pa.table({"value": [{"nested": 1}]}),
        pa.table({"value": pa.array(["a"]).dictionary_encode()}),
        pa.table({"value": [b"bytes"]}),
        pa.table({"value": pa.array([np.float16(1.0)], pa.float16())}),
        pa.table({"": [1]}),
        pa.Table.from_arrays([pa.array([1]), pa.array([2])], names=["same", "same"]),
    ],
)
def test_arrow_unsupported_shapes_types_and_labels_fail_closed(table):
    with pytest.raises(ef.CapabilityError):
        capture(table)


def test_arrow_invalid_utf8_is_a_typed_input_failure():
    array = pa.Array.from_buffers(
        pa.string(),
        1,
        [None, pa.py_buffer(np.array([0, 1], dtype=np.int32)), pa.py_buffer(b"\xff")],
    )
    with pytest.raises(ef.InvalidExecutionInput, match="physical type/value"):
        capture(pa.table({"value": array}))


def test_arrow_extension_type_is_not_unwrapped():
    class AnnotatedInteger(pa.ExtensionType):
        def __init__(self):
            super().__init__(pa.int64(), "equiframe.test.annotated_integer")

        def __arrow_ext_serialize__(self):
            return b"unit=USD"

        @classmethod
        def __arrow_ext_deserialize__(cls, storage_type, serialized):
            return cls()

    array = pa.ExtensionArray.from_storage(AnnotatedInteger(), pa.array([1]))
    with pytest.raises(ef.CapabilityError):
        capture(pa.table({"value": array}))


@pytest.mark.parametrize(
    "table",
    [
        pa.table({"value": [1]}).replace_schema_metadata({b"unit": b"USD"}),
        pa.Table.from_arrays(
            [pa.array([1])],
            schema=pa.schema([pa.field("value", pa.int64(), metadata={b"u": b"m"})]),
        ),
        pa.Table.from_pandas(pd.DataFrame({"value": [1]}, index=pd.Index([10], name="id"))),
    ],
)
def test_arrow_semantic_or_embedded_index_metadata_is_not_silently_ignored(table):
    with pytest.raises(ef.CapabilityError, match="metadata"):
        capture(table)


def test_pandas_default_index_is_omitted_and_observed_null_nan_remain_distinct():
    nullable = pd.arrays.FloatingArray(
        np.array([1.0, float("nan"), 0.0]), np.array([False, False, True])
    )
    frame = pd.DataFrame({"value": nullable})
    loaded = capture(frame)
    values = loaded.table["value"].to_pylist()
    assert values[0] == 1.0 and math.isnan(values[1]) and values[2] is None
    assert loaded.index is None and not loaded.meaningful_index
    assert dict(loaded.native_types) == {"value": "Float64"}


def test_pandas_numpy_nan_is_not_rewritten_as_null():
    loaded = capture(pd.DataFrame({"value": np.array([1.0, float("nan")])}))
    assert loaded.table["value"].null_count == 0
    assert math.isnan(loaded.table["value"][1].as_py())
    assert any("no independent NULL mask" in note for note in loaded.notes)


def test_pandas_decimal_and_zoned_timestamp_capture_is_exact():
    frame = pd.DataFrame(
        {
            "money": [Decimal("1234567890.1200"), None],
            "time": pd.to_datetime(["2025-01-02T03:04:05.123456789Z", None], utc=True),
        }
    )
    loaded = capture(frame)
    assert loaded.table["money"].type.scale == 4
    assert loaded.table["money"].to_pylist() == frame["money"].tolist()
    assert loaded.table["time"].type == pa.timestamp("ns", "UTC")
    assert loaded.table["time"].cast(pa.int64()).to_pylist()[0] == 1735787045123456789
    assert any("tzinfo provider=" in note for note in loaded.notes)


@pytest.mark.parametrize(
    "index",
    [
        pd.RangeIndex(2, name="row_id"),
        pd.RangeIndex(10, 12),
        pd.Index([9, 3], name="id"),
        pd.MultiIndex.from_tuples([("a", 1), ("b", 2)], names=["region", "id"]),
        pd.date_range("2025-01-01", periods=2, tz="UTC", name="when"),
    ],
)
def test_pandas_meaningful_index_is_separate_and_retained(index):
    loaded = capture(pd.DataFrame({"value": [4, 5]}, index=index))
    assert loaded.meaningful_index and loaded.index is not None
    assert loaded.index.num_rows == 2
    assert loaded.table.column_names == ["value"]
    assert any("names=" + repr(tuple(index.names)) in note for note in loaded.notes)


def test_pandas_original_mutation_cannot_change_values_or_index():
    source = np.array([1, 2], dtype=np.int64)
    series = pd.Series(pa.array(source), dtype=pd.ArrowDtype(pa.int64()))
    frame = pd.DataFrame({"value": series}, index=pd.Index([0, 1], name="id"))
    loaded = capture(frame)
    source[:] = 77
    frame.iloc[0, 0] = 90
    frame.index = [8, 9]
    frame.columns = ["renamed"]
    assert loaded.table.to_pydict() == {"value": [1, 2]}
    assert loaded.index.to_pydict() == {"level_0": [0, 1]}
    assert loaded.native is None


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"value": pd.Categorical(["a", "b"])}),
        pd.DataFrame({"value": [[1], [2]]}),
        pd.DataFrame({"value": [{"a": 1}]}),
        pd.DataFrame({"value": pd.Series([1, 1.0], dtype=object)}),
        pd.DataFrame({"value": [Decimal("1.0"), Decimal("1.00")]}),
        pd.DataFrame({"value": [Decimal("-0.00")]}),
        pd.DataFrame({"value": [Decimal("NaN")]}),
        pd.DataFrame({"value": pd.Series([datetime(2025, 1, 1)], dtype=object)}),
        pd.DataFrame({"value": pd.arrays.SparseArray([1, 0])}),
        pd.DataFrame({"value": [1, 2]}, index=pd.CategoricalIndex(["a", "b"])),
        pd.DataFrame({"value": [1]}, index=pd.MultiIndex.from_tuples([(1, 2)], names=["x", "x"])),
        pd.DataFrame(index=[1]),
    ],
)
def test_pandas_unsupported_distinctions_are_not_coerced(frame):
    with pytest.raises(ef.CapabilityError):
        capture(frame)


def test_pandas_named_column_axis_and_attrs_require_policy():
    frame = pd.DataFrame({"value": [1]})
    frame.columns.name = "measures"
    with pytest.raises(ef.CapabilityError, match="column axis"):
        capture(frame)
    frame.columns.name = None
    frame.attrs["unit"] = "USD"
    with pytest.raises(ef.CapabilityError, match="attrs"):
        capture(frame)


def test_polars_eager_preserves_null_nan_decimal_and_zones():
    frame = pl.DataFrame(
        {
            "value": pl.Series([1.0, float("nan"), None], dtype=pl.Float32),
            "money": pl.Series([Decimal("1.20"), None, Decimal("2.30")], dtype=pl.Decimal(9, 2)),
            "time": pl.Series([0, 1, None], dtype=pl.Datetime("ns", "UTC")),
        }
    )
    loaded = capture(frame)
    assert loaded.table.schema == frame.to_arrow().schema
    assert loaded.table["value"].null_count == 1
    assert math.isnan(loaded.table["value"][1].as_py())
    assert loaded.table["money"].to_pylist() == [Decimal("1.20"), None, Decimal("2.30")]
    assert loaded.table["time"].cast(pa.int64()).to_pylist() == [0, 1, None]
    assert dict(loaded.native_types)["value"] == "Float32"


def test_polars_snapshot_detaches_shared_numpy_buffers():
    values = np.array([1, 2], dtype=np.int64)
    frame = pl.DataFrame({"value": values})
    loaded = capture(frame)
    values[:] = 8
    frame[0, "value"] = 9
    assert loaded.table.to_pydict() == {"value": [1, 2]}


@pytest.mark.parametrize("dtype", [pl.Categorical, pl.Enum(["a"]), pl.List(pl.String)])
def test_polars_categories_or_nested_data_are_not_decoded(dtype):
    values = [["a"]] if isinstance(dtype, pl.List) else ["a"]
    with pytest.raises(ef.CapabilityError):
        capture(pl.DataFrame({"value": pl.Series(values, dtype=dtype)}))


def test_lazy_polars_plan_is_rejected_without_collecting():
    calls = []

    def observe(frame):
        calls.append(True)
        return frame

    lazy = pl.DataFrame({"value": [1]}).lazy().map_batches(observe)
    with pytest.raises(ef.CapabilityError, match=r"materialize.*first"):
        capture(lazy)
    assert calls == []


def test_explicit_duckdb_relation_capture_is_bounded_and_consumed_once():
    calls = []

    def observe(value):
        calls.append(value)
        return value

    with duckdb.connect() as connection:
        connection.create_function("observe", observe, ["BIGINT"], "BIGINT", side_effects=True)
        relation = connection.sql("select observe(range) as value from range(2)")
        assert calls == []
        loaded = capture(relation)
        assert loaded.native_types == (("value", "BIGINT"),)
        assert any("duckdb=" in note for note in loaded.notes)
        assert loaded.table.to_pydict() == {"value": [0, 1]}
        assert sorted(calls) == [0, 1]
        with pytest.raises(ef.ResourceLimitError, match="row budget"):
            capture(connection.sql("select range as value from range(3)"), max_rows=2)


@pytest.mark.parametrize("kind", ["arrow", "pandas", "polars"])
def test_native_row_limit_precedes_copy_or_conversion(kind, monkeypatch):
    import equiframe._diff_capture as implementation

    def forbidden(*args, **kwargs):
        raise AssertionError("copy/conversion ran despite row preflight")

    values = {"value": [1, 2]}
    factories = {"arrow": pa.table, "pandas": pd.DataFrame, "polars": pl.DataFrame}
    value = factories[kind](values)
    monkeypatch.setattr(implementation, "detached_arrow", forbidden)
    monkeypatch.setattr(implementation, "copy_pandas_frame", forbidden)
    monkeypatch.setattr(pl.DataFrame, "clone", forbidden)
    with pytest.raises(ef.ResourceLimitError, match="row budget"):
        capture(value, max_rows=1)


@pytest.mark.parametrize("kind", ["arrow", "pandas", "polars"])
def test_native_byte_limit_precedes_copy_or_conversion(kind, monkeypatch):
    import equiframe._diff_capture as implementation

    def forbidden(*args, **kwargs):
        raise AssertionError("copy/conversion ran despite byte preflight")

    values = {"value": ["larger than one byte"]}
    factories = {"arrow": pa.table, "pandas": pd.DataFrame, "polars": pl.DataFrame}
    value = factories[kind](values)
    monkeypatch.setattr(implementation, "detached_arrow", forbidden)
    monkeypatch.setattr(implementation, "copy_pandas_frame", forbidden)
    monkeypatch.setattr(pl.DataFrame, "clone", forbidden)
    with pytest.raises(ef.ResourceLimitError, match="byte budget"):
        capture(value, max_bytes=1)


def test_captured_meaningful_index_bytes_are_included_in_postflight_budget():
    frame = pd.DataFrame({"value": [True] * 100}, index=pd.RangeIndex(100, name="row"))
    estimate = int(frame.memory_usage(index=True, deep=True).sum())
    assert estimate < 900
    with pytest.raises(ef.ResourceLimitError, match="byte budget"):
        capture(frame, max_bytes=estimate)


def test_polars_arrow_buffers_are_checked_even_if_native_estimate_is_smaller(monkeypatch):
    frame = pl.DataFrame({"value": [1, 2]})
    monkeypatch.setattr(pl.DataFrame, "estimated_size", lambda *args: 1)
    with pytest.raises(ef.ResourceLimitError, match="byte budget"):
        capture(frame, max_bytes=1)


def test_unknown_dataframe_protocol_is_not_executed():
    class UnknownFrame:
        def __dataframe__(self, *args, **kwargs):
            raise AssertionError("dataframe protocol should not run")

        def to_arrow(self):
            raise AssertionError("conversion should not run")

    with pytest.raises(ef.InvalidExecutionInput, match="eager"):
        capture(UnknownFrame())


def test_base_import_and_invalid_dispatch_never_import_optional_engines():
    program = """
import json
import sys
import equiframe
from equiframe._diff_capture import capture_native, DiffCaptureOptions
try:
    capture_native(object(), DiffCaptureOptions())
except equiframe.InvalidExecutionInput:
    pass
heavy = {'numpy', 'pandas', 'polars', 'duckdb', 'pyarrow', 'sklearn'}
print(json.dumps(sorted(set(sys.modules) & heavy)))
"""
    result = subprocess.run(
        [sys.executable, "-c", program], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []


def test_polars_object_and_int128_are_rejected_before_arrow_conversion(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unsupported native dtype reached Arrow conversion")

    frames = [
        pl.DataFrame({"value": pl.Series([object()], dtype=pl.Object)}),
        pl.DataFrame({"value": pl.Series([1], dtype=pl.Int128)}),
    ]
    monkeypatch.setattr(pl.DataFrame, "to_arrow", forbidden)
    for frame in frames:
        with pytest.raises(ef.CapabilityError, match="Polars dtype"):
            capture(frame)


def test_unknown_numeric_pandas_extension_is_rejected_before_copy_or_conversion():
    class ExtraSemanticsDtype(pd.api.extensions.ExtensionDtype):
        name = "equiframe_numeric_extension"
        type = int
        kind = "i"
        _is_numeric = True

        @classmethod
        def construct_array_type(cls):
            return ExtraSemanticsArray

    class ExtraSemanticsArray(pd.api.extensions.ExtensionArray):
        @property
        def dtype(self):
            return ExtraSemanticsDtype()

        def __len__(self):
            return 1

        def __getitem__(self, item):
            if isinstance(item, int):
                return 1
            return self

        def isna(self):
            return np.array([False])

        def copy(self):
            return type(self)()

        @property
        def nbytes(self):
            return 8

        def __arrow_array__(self, type=None):
            raise AssertionError("unknown extension metadata must not reach Arrow conversion")

    frame = pd.DataFrame({"value": ExtraSemanticsArray()})
    assert pd.api.types.is_integer_dtype(frame["value"].dtype)
    with pytest.raises(ef.CapabilityError, match="unsupported Pandas extension"):
        capture(frame)


@pytest.mark.parametrize("engine", ["arrow", "pandas", "polars"])
def test_capture_notes_identify_installed_transport_and_native_versions(engine):
    factories = {"arrow": pa.table, "pandas": pd.DataFrame, "polars": pl.DataFrame}
    notes = capture(factories[engine]({"value": [1]})).notes
    assert f"Native capture installed distribution: pyarrow={version('pyarrow')}" in notes
    if engine != "arrow":
        assert f"Native capture installed distribution: {engine}={version(engine)}" in notes
    if engine == "polars":
        for variant in ("32", "64", "compat"):
            if f"_polars_runtime_{variant}" in sys.modules:
                name = f"polars-runtime-{variant}"
                assert f"Native capture installed distribution: {name}={version(name)}" in notes
    assert not any("duckdb=" in note for note in notes)


def test_capture_version_notes_use_distribution_metadata_not_module_internals(monkeypatch):
    monkeypatch.setattr(pd, "__version__", "ignored-module-internal-value")
    notes = capture(pd.DataFrame({"value": [1]})).notes
    assert f"Native capture installed distribution: pandas={version('pandas')}" in notes
    assert not any("ignored-module-internal-value" in note for note in notes)


def test_capture_version_missing_distribution_has_explicit_fallback(monkeypatch):
    import equiframe._diff_capture as implementation

    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(implementation, "version", missing)
    notes = capture(pa.table({"value": [1]})).notes
    assert "Native capture installed distribution: pyarrow=not-installed" in notes


@pytest.mark.parametrize("unsafe", ["1.0\nprivate-session", "/private/path", "x" * 129])
def test_capture_version_notes_do_not_leak_malformed_metadata(unsafe, monkeypatch):
    import equiframe._diff_capture as implementation

    monkeypatch.setattr(implementation, "version", lambda name: unsafe)
    notes = capture(pa.table({"value": [1]})).notes
    assert "Native capture installed distribution: pyarrow=invalid-version-metadata" in notes
    assert all(unsafe not in note for note in notes)


def test_capture_records_only_loaded_polars_runtime_variants(monkeypatch):
    import equiframe._diff_capture as implementation

    for variant in ("32", "64", "compat"):
        monkeypatch.delitem(sys.modules, f"_polars_runtime_{variant}", raising=False)
    monkeypatch.setitem(sys.modules, "_polars_runtime_compat", ModuleType("_polars_runtime_compat"))
    monkeypatch.setattr(implementation, "version", lambda name: "1.2.3")
    notes = capture(pl.DataFrame({"value": [1]})).notes
    assert "Native capture installed distribution: polars-runtime-compat=1.2.3" in notes
    assert not any("polars-runtime-32=" in note or "polars-runtime-64=" in note for note in notes)


def test_pandas_subclass_unit_metadata_is_rejected_before_it_can_disappear():
    class MoneyFrame(pd.DataFrame):
        _metadata: ClassVar[list[str]] = ["unit"]

    left = MoneyFrame({"amount": [Decimal("1.00")]})
    right = MoneyFrame({"amount": [Decimal("1.00")]})
    left.unit = "USD"
    right.unit = "EUR"
    for frame in (left, right):
        with pytest.raises(ef.CapabilityError, match="subclasses"):
            capture(frame)


def test_pandas_subclass_without_metadata_cannot_override_capture():
    class CustomFrame(pd.DataFrame):
        _metadata: ClassVar[list[str]] = []

        def memory_usage(self, *args, **kwargs):
            raise AssertionError("subclass size override should not run")

        def copy(self, *args, **kwargs):
            raise AssertionError("subclass copy override should not run")

    with pytest.raises(ef.CapabilityError, match="subclasses"):
        capture(CustomFrame({"value": [1]}))


def test_polars_subclass_cannot_override_capture():
    class CustomFrame(pl.DataFrame):
        def estimated_size(self, *args, **kwargs):
            raise AssertionError("subclass size override should not run")

        def clone(self):
            raise AssertionError("subclass clone override should not run")

        def to_arrow(self, *args, **kwargs):
            raise AssertionError("subclass conversion override should not run")

    with pytest.raises(ef.CapabilityError, match="subclasses"):
        capture(CustomFrame({"value": [1]}))


@pytest.mark.parametrize("scalar_class", [Decimal, str])
@pytest.mark.parametrize("as_index", [False, True])
def test_pandas_scalar_subclass_metadata_is_rejected_before_capture(
    scalar_class, as_index, monkeypatch
):
    import equiframe._diff_capture as implementation

    class Currency(scalar_class):
        def __new__(cls, value, unit):
            result = super().__new__(cls, value)
            result.unit = unit
            return result

        def __sizeof__(self):
            raise AssertionError("scalar size override must not run")

        def as_tuple(self):
            raise AssertionError("scalar conversion override must not run")

    def forbidden(*args, **kwargs):
        raise AssertionError("scalar subclass metadata reached the copying step")

    for unit in ("USD", "EUR"):
        value = Currency("2.00", unit)
        if as_index:
            frame = pd.DataFrame({"value": [1]}, index=pd.Index([value], dtype=object))
        else:
            frame = pd.DataFrame({"value": pd.Series([value], dtype=object)})
        monkeypatch.setattr(implementation, "copy_pandas_frame", forbidden)
        with pytest.raises(ef.CapabilityError, match="plain immutable scalars"):
            capture(frame)


@pytest.mark.parametrize("as_index", [False, True])
def test_pandas_numpy_dtype_metadata_is_rejected_before_copy(as_index, monkeypatch):
    import equiframe._diff_capture as implementation

    def forbidden(*args, **kwargs):
        raise AssertionError("dtype metadata reached the copying step")

    for unit in ("USD", "EUR"):
        values = np.array([1], dtype=np.dtype("int64", metadata={"unit": unit}))
        if as_index:
            frame = pd.DataFrame({"value": [1]}, index=pd.Index(values, name="id"))
            assert frame.index.dtype.metadata == {"unit": unit}
        else:
            frame = pd.DataFrame({"value": values})
            assert frame["value"].dtype.metadata == {"unit": unit}
        monkeypatch.setattr(implementation, "copy_pandas_frame", forbidden)
        with pytest.raises(ef.CapabilityError, match="dtype metadata"):
            capture(frame)


def test_empty_pandas_frame_with_default_empty_column_index_is_supported():
    loaded = capture(pd.DataFrame())
    assert loaded.table.num_rows == 0 and loaded.table.num_columns == 0
    assert loaded.index is None


def test_polars_direct_capture_rejects_lost_cardinality(monkeypatch):
    frame = pl.DataFrame({"value": [1, 2]})
    native = pl.DataFrame.to_arrow

    def lossy(value, *args, **kwargs):
        return native(value, *args, **kwargs).slice(0, 0)

    monkeypatch.setattr(pl.DataFrame, "to_arrow", lossy)
    with pytest.raises(ef.CapabilityError, match="direct capture changed table dimensions"):
        capture(frame)
