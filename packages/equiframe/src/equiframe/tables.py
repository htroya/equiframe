"""Explicit in-memory/local inputs and loss-aware Arrow IPC capture.

Arrow is optional and imported only when a table is accessed. Expected contract
types never drive casts of observed data.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import uuid4

from equiframe.errors import CapabilityError, InvalidExecutionInput, MissingDependencyError
from equiframe.execution_types import PhysicalColumn, TableArtifact
from equiframe.types import ArtifactRef

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    from equiframe.execution import RunContext


def require_dependency(name: str, extra: str) -> None:
    try:
        import_module(name)
    except ImportError as error:
        raise MissingDependencyError(
            f"optional dependency {name} is unavailable; install 'equiframe[{extra}]' "
            "from the team's wheel/checkout (public PyPI release is pending)"
        ) from error


@dataclass(frozen=True)
class LoadedTable:
    table: pa.Table
    native: object | None = None
    native_types: tuple[tuple[str, str], ...] = ()
    index: pa.Table | None = None
    meaningful_index: bool = False
    origin: ArtifactRef | None = None
    notes: tuple[str, ...] = ()


def check_arrow(table: pa.Table) -> None:
    import pyarrow as pa

    if not isinstance(table, pa.Table):
        raise InvalidExecutionInput("an Arrow Table is required")
    if len(set(table.column_names)) != table.num_columns or any(not n for n in table.column_names):
        raise CapabilityError("table column names must be nonempty and unique")
    try:
        table.validate(full=True)
    except pa.ArrowException as error:
        raise InvalidExecutionInput(
            "Arrow table violates physical type/value invariants"
        ) from error
    for field in table.schema:
        dtype = field.type
        if not (
            pa.types.is_null(dtype)
            or pa.types.is_boolean(dtype)
            or pa.types.is_integer(dtype)
            or pa.types.is_string(dtype)
            or pa.types.is_large_string(dtype)
            or pa.types.is_string_view(dtype)
            or (pa.types.is_floating(dtype) and dtype.bit_width in (32, 64))
            or pa.types.is_decimal128(dtype)
            or pa.types.is_decimal256(dtype)
            or pa.types.is_date32(dtype)
            or pa.types.is_date64(dtype)
            or pa.types.is_timestamp(dtype)
        ):
            raise CapabilityError(f"unsupported faithful table transport type: {dtype}")


def detached_arrow(table: pa.Table) -> pa.Table:
    import pyarrow as pa

    check_arrow(table)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
    with pa.ipc.open_file(sink.getvalue()) as reader:
        return cast("pa.Table", reader.read_all())


def copy_pandas_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Isolate both values and index/column buffers, including injected native frames."""
    copied = frame.copy(deep=True)
    copied.index = frame.index.copy(deep=True)
    copied.columns = frame.columns.copy(deep=True)
    return copied


def pandas_capture(frame: pd.DataFrame) -> LoadedTable:
    import pandas as pd
    import pyarrow as pa

    if not isinstance(frame, pd.DataFrame):
        raise InvalidExecutionInput("Pandas transformation/input must produce a DataFrame")
    if isinstance(frame.columns, pd.CategoricalIndex):
        raise CapabilityError("categorical Pandas column labels cannot be captured faithfully")
    if (
        not all(isinstance(name, str) and name for name in frame.columns)
        or not frame.columns.is_unique
    ):
        raise CapabilityError("Pandas column labels must be unique nonempty strings")
    if frame.shape[1] == 0 and frame.shape[0] != 0:
        raise CapabilityError(
            "Pandas tables with rows but zero columns cannot be captured faithfully"
        )
    notes = [
        "Pandas missing sentinels already conflated by input construction cannot be recovered."
    ]

    def array_of(series: pd.Series[Any], name: str) -> pa.Array | pa.ChunkedArray:
        dtype = series.dtype
        if isinstance(dtype, pd.CategoricalDtype):
            raise CapabilityError("Pandas categories/ordering cannot be captured as scalar labels")
        if isinstance(dtype, pd.ArrowDtype):
            if pa.types.is_timestamp(dtype.pyarrow_dtype):
                notes.append(
                    f"{name}: Arrow zone metadata; original offset/provider version absent."
                )
            return pa.array(series.array, from_pandas=False)
        if pd.api.types.is_datetime64_any_dtype(dtype):
            tzinfo = getattr(dtype, "tz", None)
            provider = type(tzinfo).__module__ + "." + type(tzinfo).__qualname__
            notes.append(f"{name}: input tzinfo provider={provider}; IANA release not exposed.")
            return pa.array(series, from_pandas=True)
        if (
            pd.api.types.is_integer_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)
            or pd.api.types.is_float_dtype(dtype)
            or isinstance(dtype, pd.StringDtype)
        ):
            if pd.api.types.is_extension_array_dtype(dtype):
                # Extension arrays expose physical widths and their independent validity mask.
                return pa.array(series.array, from_pandas=False)
            if pd.api.types.is_float_dtype(dtype):
                notes.append(
                    f"{name}: NumPy float has no independent NULL mask; observed NaNs retained."
                )
            return pa.array(series.to_numpy(copy=True), from_pandas=False)
        if not pd.api.types.is_object_dtype(dtype):
            raise CapabilityError("unsupported native Pandas dtype for faithful scalar transport")
        values = [None if value is pd.NA or value is pd.NaT else value for value in series]
        if any(isinstance(v, datetime) for v in values if v is not None):
            raise CapabilityError(
                "object timestamps need a temporal/Arrow dtype to preserve precision"
            )
        if any(
            v is not None and not isinstance(v, (str, bool, int, float, Decimal, date))
            for v in values
        ):
            raise CapabilityError(
                "Pandas object columns support only immutable scalar transport values"
            )
        # Inferring a common float/decimal dtype would erase per-cell numeric kinds.
        kinds = {type(v) for v in values if v is not None}
        if len(kinds) > 1:
            raise CapabilityError(
                "heterogeneous Pandas object scalars require an explicit faithful dtype"
            )
        decimals = [v for v in values if isinstance(v, Decimal)]
        if decimals:
            if any(not v.is_finite() or (v.is_zero() and v.is_signed()) for v in decimals):
                raise CapabilityError(
                    "Arrow decimal cannot retain nonfinite or signed-zero Decimal"
                )
            if len({v.as_tuple().exponent for v in decimals}) != 1:
                raise CapabilityError(
                    "Arrow fixed-scale decimal cannot retain per-cell exponent differences"
                )
        try:
            return pa.array(values, from_pandas=False)
        except (pa.ArrowException, TypeError, ValueError, OverflowError) as error:
            raise CapabilityError(
                "Pandas values cannot be captured faithfully as Arrow scalars"
            ) from error

    table = pa.Table.from_arrays(
        [array_of(frame[n], n) for n in frame.columns], names=list(frame.columns)
    )
    check_arrow(table)
    index_frame = frame.index.to_frame(index=False)
    index_frame.columns = [f"level_{i}" for i in range(len(index_frame.columns))]
    index = pa.Table.from_arrays(
        [array_of(index_frame[n], "index." + n) for n in index_frame.columns],
        names=list(index_frame.columns),
    )
    check_arrow(index)
    notes.append("Pandas index stored separately; names=" + repr(tuple(frame.index.names)))
    notes.append("Pandas index dtypes=" + repr(tuple(str(t) for t in index_frame.dtypes)))
    notes.append("Pandas column axis name=" + repr(frame.columns.name))
    meaningful = not (
        isinstance(frame.index, pd.RangeIndex)
        and frame.index.start == 0
        and frame.index.step == 1
        and frame.index.name is None
    )
    return LoadedTable(
        table=table,
        native=frame,
        native_types=tuple((str(n), str(t)) for n, t in frame.dtypes.items()),
        index=index,
        meaningful_index=meaningful,
        notes=tuple(notes),
    )


def capture_artifact(
    name: str, loaded: LoadedTable, context: RunContext, *, output: bool = False
) -> TableArtifact:
    import pyarrow as pa
    import pyarrow.compute as pc

    check_arrow(loaded.table)
    context.check_table(loaded.table, output=output, enforce_rows=False)
    if loaded.index is not None:
        check_arrow(loaded.index)
        if loaded.index.num_rows != loaded.table.num_rows:
            raise InvalidExecutionInput("index row count must match table row count")
        context.check_table(loaded.index, output=output, enforce_rows=False)

    def persist(table: pa.Table) -> ArtifactRef:
        path = context.directory / (uuid4().hex + ".arrow")
        try:
            with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
                writer.write_table(table)
            return context.store.put(path, media_type="application/vnd.apache.arrow.file")
        finally:
            path.unlink(missing_ok=True)

    def describe(
        table: pa.Table, native: tuple[tuple[str, str], ...]
    ) -> tuple[PhysicalColumn, ...]:
        types = dict(native)
        return tuple(
            PhysicalColumn(
                name=field.name,
                engine_type=types.get(field.name, str(field.type)),
                arrow_type=str(field.type),
                null_count=table.column(field.name).null_count,
                nan_count=(
                    int(pc.sum(pc.is_nan(table.column(field.name))).as_py() or 0)
                    if pa.types.is_floating(field.type)
                    else 0
                ),
            )
            for field in table.schema
        )

    from pydantic import TypeAdapter

    from equiframe._base import Text

    # Validate all metadata before publishing bytes. A successful data publication
    # is retained in the failed result even if the separate index publication fails.
    notes = TypeAdapter(tuple[Text, ...]).validate_python(loaded.notes, strict=True)
    origin = ArtifactRef.model_validate(loaded.origin) if loaded.origin is not None else None
    columns = describe(loaded.table, loaded.native_types)
    index_columns = describe(loaded.index, ()) if loaded.index is not None else ()
    artifact = TableArtifact(
        name=name,
        data=persist(loaded.table),
        origin=origin,
        row_count=loaded.table.num_rows,
        columns=columns,
        notes=notes
        + (
            ("Index capture incomplete; see execution failure.",)
            if loaded.index is not None
            else ()
        ),
    )
    if output:
        context.captured_output = artifact
    else:
        context.captured_inputs.append(artifact)
    if loaded.index is not None:
        index_ref = persist(loaded.index)
        artifact = TableArtifact(
            name=name,
            data=artifact.data,
            origin=origin,
            row_count=loaded.table.num_rows,
            columns=columns,
            index=index_ref,
            index_columns=index_columns,
            notes=notes,
        )
        if output:
            context.captured_output = artifact
        else:
            context.captured_inputs[-1] = artifact
    return artifact


@dataclass(frozen=True)
class ArrowInput:
    table: pa.Table

    def load(self, context: RunContext) -> LoadedTable:
        require_dependency("pyarrow", "arrow")
        context.check_table(self.table, output=False)
        return LoadedTable(
            detached_arrow(self.table),
            notes=(
                "Arrow retains distinctions already encoded in types, values and validity masks.",
            ),
        )


@dataclass(frozen=True)
class PandasInput:
    frame: pd.DataFrame
    index_policy: Literal["preserve", "columns", "discard"] = "preserve"

    def load(self, context: RunContext) -> LoadedTable:
        require_dependency("pandas", "pandas")
        require_dependency("pyarrow", "pandas")
        import pandas as pd

        if not isinstance(self.frame, pd.DataFrame):
            raise InvalidExecutionInput("PandasInput requires a DataFrame")
        if self.index_policy not in ("preserve", "columns", "discard"):
            raise InvalidExecutionInput("unknown Pandas index policy")
        # Supported cells are immutable scalars; deep=True then isolates container mutation.
        copied = copy_pandas_frame(self.frame)
        if self.index_policy == "columns":
            copied = copied.reset_index()
        elif self.index_policy == "discard":
            copied = copied.reset_index(drop=True)
        loaded = pandas_capture(copied)
        context.check_table(loaded.table, output=False)
        return loaded


@dataclass(frozen=True)
class PolarsInput:
    frame: pl.DataFrame | pl.LazyFrame

    def load(self, context: RunContext) -> LoadedTable:
        require_dependency("polars", "polars")
        require_dependency("pyarrow", "polars")
        import polars as pl

        if not isinstance(self.frame, (pl.DataFrame, pl.LazyFrame)):
            raise InvalidExecutionInput("PolarsInput requires a DataFrame or LazyFrame")
        with context.measure("input_materialization"):
            frame = (
                self.frame.collect() if isinstance(self.frame, pl.LazyFrame) else self.frame.clone()
            )
        table = frame.to_arrow()
        if table.shape != frame.shape:
            raise CapabilityError("Polars input capture changed table dimensions")
        check_arrow(table)
        context.check_table(table, output=False)
        return LoadedTable(
            table, native=frame, native_types=tuple((n, str(t)) for n, t in frame.schema.items())
        )


@dataclass(frozen=True)
class ArtifactInput:
    ref: ArtifactRef

    def load(self, context: RunContext) -> LoadedTable:
        # Reject remote URIs even if the optional transport is not installed.
        from equiframe.local import local_path

        local_path(self.ref)
        if self.ref.format not in ("arrow", "parquet"):
            raise CapabilityError("tabular artifact format must be Arrow IPC file or Parquet")
        require_dependency("pyarrow", "arrow")
        import pyarrow as pa
        import pyarrow.parquet as pq

        if (
            context.plan.options.max_transport_bytes is not None
            and self.ref.size_bytes > context.plan.options.max_transport_bytes
        ):
            from equiframe.errors import ResourceLimitError

            raise ResourceLimitError("input artifact exceeds transport byte budget")
        path = context.directory / ("input_" + uuid4().hex + "." + self.ref.format)
        try:
            context.store.get(self.ref, path)
            if self.ref.format == "parquet":
                table = pq.read_table(path)
            else:
                with path.open("rb") as source_file, pa.ipc.open_file(source_file) as reader:
                    table = reader.read_all()
            check_arrow(table)
            context.check_table(table, output=False)
            return LoadedTable(
                table, origin=self.ref, notes=("Source file SHA-256 and size verified.",)
            )
        finally:
            path.unlink(missing_ok=True)


if TYPE_CHECKING:
    from typing import Protocol

    class TableInput(Protocol):
        def load(self, context: RunContext) -> LoadedTable: ...


class LocalDataSource:
    def __init__(self, inputs: Mapping[str, TableInput | ArtifactRef]) -> None:
        self._inputs = dict(inputs)

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._inputs)

    def resolve(self, name: str, *, context: RunContext) -> LoadedTable:
        try:
            value = self._inputs[name]
        except KeyError:
            raise InvalidExecutionInput("input table is unavailable: " + name) from None
        return (
            ArtifactInput(value).load(context)
            if isinstance(value, ArtifactRef)
            else value.load(context)
        )


def read_table(ref: ArtifactRef) -> pa.Table:
    """Read a local Arrow IPC/Parquet reference after verifying its bytes and size."""
    from equiframe.local import LocalArtifactStore, local_path

    local_path(ref)
    if ref.format not in ("arrow", "parquet"):
        raise CapabilityError("tabular artifact format must be Arrow IPC file or Parquet")
    require_dependency("pyarrow", "arrow")
    import pyarrow as pa
    import pyarrow.parquet as pq

    with tempfile.TemporaryDirectory(prefix="equiframe-read-") as directory:
        path = Path(directory) / ("input." + ref.format)
        LocalArtifactStore(Path(directory)).get(ref, path)
        if ref.format == "parquet":
            table = pq.read_table(path)
        else:
            with path.open("rb") as source_file, pa.ipc.open_file(source_file) as reader:
                table = reader.read_all()
        check_arrow(table)
        return cast("pa.Table", table)
