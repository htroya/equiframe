"""Bounded native snapshots for ``diff``, including caller-supplied DuckDB relations.

Native size estimates and Arrow buffer checks are cooperative limits, not hard
RSS or latency guarantees. No expected schema participates in capture.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Literal, cast

from equiframe._base import FrozenModel, PositiveInt
from equiframe.errors import (
    CapabilityError,
    ExecutionCancelled,
    InvalidExecutionInput,
    ResourceLimitError,
)
from equiframe.tables import (
    LoadedTable,
    check_arrow,
    copy_pandas_frame,
    detached_arrow,
    pandas_capture,
    require_dependency,
)

if TYPE_CHECKING:
    import duckdb
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    from equiframe.execution import CancellationToken


class DiffCaptureOptions(FrozenModel):
    """Per-input eager capture limits, separate from comparison budgets.

    ``max_bytes`` bounds native estimated size before copying/conversion and
    captured Arrow data plus meaningful index buffers afterward. Intermediate
    allocations, Python overhead and serialization buffers are not hard-capped.
    Passing an actual DuckDB relation explicitly authorizes consuming that
    relation. Capture limits rows with max_rows+1 and checks Arrow batches before
    detachment. Native planning/first-batch allocations are cooperative, not hard
    memory/time limits. Polars lazy frames, SQL strings and connections are not
    accepted as native tables.
    """

    max_rows: PositiveInt = 1_000_000
    max_bytes: PositiveInt = 256 * 1024 * 1024


@dataclass(frozen=True)
class _NativeInput:
    value: object
    options: DiffCaptureOptions
    cancellation: CancellationToken | None = None

    def load(self) -> LoadedTable:
        return capture_native(self.value, self.options, cancellation=self.cancellation)


@dataclass(frozen=True)
class _CapturedInput:
    loaded: LoadedTable

    def load(self) -> LoadedTable:
        return self.loaded


def _is_loaded_type(value: object, module_name: str, type_name: str) -> bool:
    """Check actual engine classes without importing an unrelated extra."""
    module = sys.modules.get(module_name)
    native_type = getattr(module, type_name, None) if module is not None else None
    return isinstance(native_type, type) and isinstance(value, native_type)


def _require_base_class(value: object, module_name: str, type_name: str) -> None:
    # A subclass may attach units/index semantics or replace copy/conversion.
    # Merely being isinstance-compatible does not authorize discarding those.
    if type(value) is not getattr(sys.modules[module_name], type_name):
        raise CapabilityError(
            f"{module_name}.{type_name} subclasses require an explicit metadata/capture policy"
        )


def _capture_versions(engine: Literal["arrow", "pandas", "polars", "duckdb"]) -> tuple[str, ...]:
    """Record installed capture distributions, not a tested compatibility matrix.

    Only fixed distribution names and bounded version tokens enter evidence.
    Loaded Polars runtime modules identify the variant without importing another
    engine or consulting paths, session settings, or module version internals.
    """
    names = ["pyarrow"]
    if engine != "arrow":
        names.append(engine)
    if engine == "polars":
        for variant in ("32", "64", "compat"):
            if f"_polars_runtime_{variant}" in sys.modules:
                names.append(f"polars-runtime-{variant}")
    notes = []
    for name in names:
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = "not-installed"
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}", installed) is None:
            installed = "invalid-version-metadata"
        notes.append(f"Native capture installed distribution: {name}={installed}")
    return tuple(notes)


def _check_size(rows: int, size: int, options: DiffCaptureOptions) -> None:
    if rows > options.max_rows:
        raise ResourceLimitError("native diff input exceeds capture row budget")
    if size > options.max_bytes:
        raise ResourceLimitError("native diff input exceeds capture byte budget")


def _check_metadata(table: pa.Table) -> None:
    # Schema metadata may contain units, extension types or an embedded index.
    # Keeping its bytes is insufficient when the comparator cannot interpret it.
    if table.schema.metadata or any(field.metadata for field in table.schema):
        raise CapabilityError(
            "native Arrow schema/field metadata has no supported comparison policy; "
            "provide an explicitly prepared faithful capture"
        )


def _finish(loaded: LoadedTable, options: DiffCaptureOptions) -> LoadedTable:
    check_arrow(loaded.table)
    index = loaded.index if loaded.meaningful_index else None
    if index is not None:
        check_arrow(index)
        if index.num_rows != loaded.table.num_rows:
            raise InvalidExecutionInput("captured index row count must match the data")
    _check_size(
        loaded.table.num_rows,
        loaded.table.nbytes + (index.nbytes if index is not None else 0),
        options,
    )
    # Arrow can alias writable NumPy buffers, including in pandas extension
    # arrays and Polars frames. IPC detachment isolates every accepted snapshot.
    table = detached_arrow(loaded.table)
    index = detached_arrow(index) if index is not None else None
    _check_size(table.num_rows, table.nbytes + (index.nbytes if index is not None else 0), options)
    return replace(loaded, table=table, native=None, index=index)


def _check_pandas_metadata(frame: pd.DataFrame) -> None:
    import pandas as pd

    if type(frame.columns) not in (pd.Index, pd.RangeIndex):
        raise CapabilityError("unsupported Pandas column index type/metadata for diff capture")
    if any(type(name) is not str for name in frame.columns):
        raise CapabilityError("Pandas column labels must be plain strings without extra metadata")
    if any(name is not None for name in frame.columns.names):
        raise CapabilityError("Pandas column axis names require an explicit metadata policy")
    if frame.attrs:
        raise CapabilityError("Pandas attrs require an explicit metadata policy")
    if type(frame.index) not in (pd.Index, pd.RangeIndex, pd.MultiIndex, pd.DatetimeIndex):
        raise CapabilityError("unsupported Pandas index type/metadata for faithful diff capture")
    # pandas_capture understands only these native extension representations.
    # Generic is_integer_dtype/is_float_dtype alone would also accept arbitrary
    # user extensions whose conversion might erase additional semantics.
    supported_extensions = (
        pd.ArrowDtype,
        pd.BooleanDtype,
        pd.Int8Dtype,
        pd.Int16Dtype,
        pd.Int32Dtype,
        pd.Int64Dtype,
        pd.UInt8Dtype,
        pd.UInt16Dtype,
        pd.UInt32Dtype,
        pd.UInt64Dtype,
        pd.Float32Dtype,
        pd.Float64Dtype,
        pd.StringDtype,
        pd.DatetimeTZDtype,
    )
    index_dtypes = (
        tuple(level.dtype for level in frame.index.levels)
        if isinstance(frame.index, pd.MultiIndex)
        else (frame.index.dtype,)
    )
    for dtype in (*frame.dtypes, *index_dtypes):
        if isinstance(dtype, pd.CategoricalDtype):
            raise CapabilityError("Pandas categories/ordering cannot be captured as scalar labels")
        if (
            isinstance(dtype, pd.api.extensions.ExtensionDtype)
            and type(dtype) not in supported_extensions
        ):
            raise CapabilityError("unsupported Pandas extension dtype for faithful diff capture")
        if getattr(dtype, "metadata", None):
            raise CapabilityError("Pandas dtype metadata requires an explicit comparison policy")
    if any(name is not None and type(name) not in (str, int) for name in frame.index.names):
        raise CapabilityError("unsupported Pandas index name metadata")
    if isinstance(frame.index, pd.MultiIndex):
        names = tuple(name for name in frame.index.names if name is not None)
        if len(names) != len(set(names)):
            raise CapabilityError("duplicate Pandas index names cannot be captured faithfully")

    def check_scalars(values: Iterable[object]) -> None:
        for value in values:
            if value is None or value is pd.NA or value is pd.NaT:
                continue
            if type(value) not in (str, bool, int, float, Decimal, date):
                raise CapabilityError(
                    "Pandas object values must be plain immutable scalars; "
                    "subclasses and their metadata require an explicit capture policy"
                )

    for _, series in frame.items():
        if pd.api.types.is_object_dtype(series.dtype):
            check_scalars(series)
    levels = frame.index.levels if isinstance(frame.index, pd.MultiIndex) else (frame.index,)
    for level in levels:
        if pd.api.types.is_object_dtype(level.dtype):
            check_scalars(level)


def _check_polars_schema(frame: pl.DataFrame) -> None:
    import polars as pl

    supported = (
        pl.Null,
        pl.Boolean,
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
        pl.Float32,
        pl.Float64,
        pl.String,
        pl.Decimal,
        pl.Date,
        pl.Datetime,
    )
    if any(dtype.base_type() not in supported for dtype in frame.schema.values()):
        raise CapabilityError("unsupported Polars dtype for faithful scalar diff capture")


def _capture_duckdb_relation(
    relation: duckdb.DuckDBPyRelation,
    options: DiffCaptureOptions,
    cancellation: CancellationToken | None,
) -> LoadedTable:
    """Consume only the real relation explicitly supplied by the caller.

    No SQL text is accepted, reconstructed or loaded from evidence. The caller
    owns the relation's connection/settings and must trust its native plan.
    Cancellation is checked before execution and between batches; a blocking
    native first fetch is not an interruptible or sandboxed operation.
    """
    require_dependency("pyarrow", "duckdb")
    import duckdb
    import pyarrow as pa

    from equiframe._duckdb_transport import duckdb_arrow_schema, verify_duckdb_table

    def checkpoint() -> None:
        if cancellation is not None and cancellation.cancelled:
            raise ExecutionCancelled("cancelled during native DuckDB relation capture")

    checkpoint()
    reader = None
    try:
        native_types = tuple(zip(relation.columns, map(str, relation.types), strict=True))
        duckdb_arrow_schema(native_types, "UTC")
        # No count query, fetch-all or second consumption: this one result has
        # at most one excess row, which lets capture reject rather than truncate.
        reader = relation.limit(options.max_rows + 1).to_arrow_reader(
            min(4096, options.max_rows + 1)
        )
        zones = {
            field.type.tz
            for field in reader.schema
            if pa.types.is_timestamp(field.type) and field.type.tz is not None
        }
        if len(zones) > 1:
            raise CapabilityError("DuckDB relation exposes inconsistent timestamp timezones")
        timezone = next(iter(zones), "UTC")
        expected = duckdb_arrow_schema(native_types, timezone)
        if not reader.schema.equals(expected, check_metadata=True):
            raise CapabilityError("DuckDB relation Arrow schema differs from its native types")
        batches = []
        rows = size = 0
        while True:
            checkpoint()
            try:
                batch = reader.read_next_batch()
            except StopIteration:
                break
            rows += batch.num_rows
            size += batch.nbytes
            _check_size(rows, size, options)
            batches.append(batch)
        checkpoint()
        table = pa.Table.from_batches(batches, schema=expected)
        verify_duckdb_table(table, native_types, timezone)
        captured = _finish(
            LoadedTable(
                table,
                native_types=native_types,
                notes=(
                    "Caller-supplied DuckDB relation explicitly consumed once for this input.",
                    "Native row order, Decimal precision, NULL and IEEE NaN are retained; "
                    "no index.",
                    "The caller owns relation/session settings; no SQL text or connection "
                    "is accepted.",
                    *_capture_versions("duckdb"),
                ),
            ),
            options,
        )
        checkpoint()
        return captured
    except (duckdb.Error, pa.ArrowException) as error:
        raise InvalidExecutionInput(
            "DuckDB relation cannot be captured as a native table"
        ) from error
    finally:
        if reader is not None:
            reader.close()


def capture_native(
    value: object, options: DiffCaptureOptions, *, cancellation: CancellationToken | None = None
) -> LoadedTable:
    """Capture a real eager table or explicitly supplied DuckDB relation.

    Unsupported inputs raise a typed input/capability error. Native row/size
    preflight runs before the first copy or conversion. Repeated calls create
    separate snapshots; reuse is represented internally by ``_CapturedInput``.
    """
    options = DiffCaptureOptions.model_validate(options)
    if cancellation is not None and cancellation.cancelled:
        raise ExecutionCancelled("cancelled before native input capture")
    if _is_loaded_type(value, "polars", "LazyFrame"):
        raise CapabilityError(
            "diff does not execute a Polars LazyFrame; materialize it through "
            "explicit native execution/capture first"
        )
    if _is_loaded_type(value, "duckdb", "DuckDBPyRelation") or _is_loaded_type(
        value, "_duckdb", "DuckDBPyRelation"
    ):
        module_name = (
            "duckdb" if _is_loaded_type(value, "duckdb", "DuckDBPyRelation") else "_duckdb"
        )
        _require_base_class(value, module_name, "DuckDBPyRelation")
        return _capture_duckdb_relation(
            cast("duckdb.DuckDBPyRelation", value), options, cancellation
        )
    if _is_loaded_type(value, "pyarrow", "Table"):
        _require_base_class(value, "pyarrow", "Table")
        table = cast("pa.Table", value)
        _check_size(table.num_rows, table.nbytes, options)
        _check_metadata(table)
        return _finish(
            LoadedTable(
                table,
                native_types=tuple((field.name, str(field.type)) for field in table.schema),
                notes=(
                    "Arrow retains distinctions already encoded in types, values "
                    "and validity masks.",
                    "Direct eager diff input captured once; no native execution performed.",
                    *_capture_versions("arrow"),
                ),
            ),
            options,
        )
    if _is_loaded_type(value, "pandas", "DataFrame"):
        _require_base_class(value, "pandas", "DataFrame")
        frame = cast("pd.DataFrame", value)
        _check_size(len(frame), 0, options)
        _check_pandas_metadata(frame)
        _check_size(len(frame), int(frame.memory_usage(index=True, deep=True).sum()), options)
        require_dependency("pyarrow", "pandas")
        import pyarrow as pa

        try:
            captured = pandas_capture(copy_pandas_frame(frame))
        except (pa.ArrowException, TypeError, ValueError, OverflowError) as error:
            raise CapabilityError("Pandas input cannot be captured faithfully as Arrow") from error
        return _finish(
            replace(
                captured,
                notes=(
                    *captured.notes,
                    "Direct eager diff input captured once; no native execution performed.",
                    *_capture_versions("pandas"),
                ),
            ),
            options,
        )
    if _is_loaded_type(value, "polars", "DataFrame"):
        _require_base_class(value, "polars", "DataFrame")
        frame_pl = cast("pl.DataFrame", value)
        _check_size(frame_pl.height, int(frame_pl.estimated_size()), options)
        _check_polars_schema(frame_pl)
        require_dependency("pyarrow", "polars")
        copied = frame_pl.clone()
        table = copied.to_arrow()
        if table.shape != copied.shape:
            raise CapabilityError("Polars direct capture changed table dimensions")
        _check_metadata(table)
        return _finish(
            LoadedTable(
                table,
                native_types=tuple((name, str(dtype)) for name, dtype in copied.schema.items()),
                notes=(
                    "Direct eager diff input captured once; no native execution performed.",
                    *_capture_versions("polars"),
                ),
            ),
            options,
        )
    raise InvalidExecutionInput(
        "diff native input must be an eager pyarrow.Table, pandas.DataFrame, polars.DataFrame "
        "or an explicitly supplied DuckDBPyRelation"
    )
