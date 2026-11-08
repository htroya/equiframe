"""Local file discovery, conservative Pandas loading and explicit data conversion.

This convenience surface converts data, not transformation programs. Engines and
file readers are imported only when selected. It does not run semantic comparison,
train models, execute macros or open a shared DuckDB database.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, Literal
from uuid import uuid4

from equiframe._dataset_provenance import (
    DatasetProvenance,
    DatasetSource,
    arrow_fingerprint,
    pandas_fingerprint,
)
from equiframe.errors import CapabilityError, InvalidExecutionInput, MissingDependencyError

DatasetFormat = Literal["json", "jsonl", "excel", "txt", "xml", "csv", "parquet", "geojson"]
DatasetTarget = Literal["pandas", "polars", "duckdb"]


class DatasetReadError(InvalidExecutionInput):
    """A file cannot be represented using the selected loading options."""

    code = "dataset_read_error"


class DatasetChoiceRequired(DatasetReadError):
    """Only a caller can resolve this structural ambiguity; no data was discarded."""

    code = "dataset_choice_required"

    def __init__(self, option: str, choices: Sequence[str], message: str) -> None:
        self.option = option
        self.choices = tuple(choices)
        super().__init__(message)


@dataclass(frozen=True)
class DatasetReadOptions:
    """Optional disambiguation; the usual call only needs a local file path.

    Text inference accepts canonical integers and finite Decimal text. Leading
    zeros, whitespace, dates, mixed representations and empty strings stay text.
    ``column_types`` overrides individual columns without executing user code.
    JSON ``records_path`` is an RFC 6901 JSON Pointer; XML uses ElementTree paths.
    """

    format: DatasetFormat | None = None
    encoding: str = "utf-8-sig"
    delimiter: str | None = None
    header: bool = True
    sheet: str | None = None
    records_path: str | None = None
    text_mode: Literal["auto", "lines", "delimited"] = "auto"
    infer_text_types: bool = True
    column_types: Mapping[str, Literal["string", "integer", "decimal", "boolean", "json"]] = field(
        default_factory=dict
    )
    max_bytes: int = 128 * 1024 * 1024
    max_rows: int = 1_000_000
    max_cells: int = 2_000_000


@dataclass(frozen=True)
class DatasetColumn:
    name: str
    pandas_dtype: str
    value_types: tuple[str, ...]
    null_count: int
    nan_count: int


@dataclass(frozen=True)
class DatasetInfo:
    format: DatasetFormat
    rows: int
    columns: tuple[DatasetColumn, ...]
    notes: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: DatasetProvenance | None = None

    def to_dict(
        self, *, include_metadata: bool = False, include_provenance: bool = False
    ) -> dict[str, Any]:
        """Describe structure; original file metadata is included only on request."""
        result: dict[str, Any] = {
            "format": self.format,
            "rows": self.rows,
            "columns": [asdict(column) for column in self.columns],
            "notes": list(self.notes),
        }
        if include_metadata:
            result["metadata"] = dict(self.metadata)
        if include_provenance and self.provenance is not None:
            result["provenance"] = self.provenance.to_dict()
        return result


@dataclass
class DatasetResult:
    """The actual Pandas input and actual native destination, with owned resources.

    ``frame`` is a Pandas/Polars DataFrame or a DuckDBPyRelation. For DuckDB the
    private in-memory connection must remain open while the relation is used.
    Use ``with load_dataset(...) as data`` or call ``close()`` explicitly.
    """

    pandas: Any
    frame: Any
    target: DatasetTarget
    info: DatasetInfo
    _connection: Any = field(default=None, repr=False)
    provenance: DatasetProvenance | None = None
    _native_schema: tuple[tuple[str, str], ...] | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if not self._closed:
            if self._connection is not None:
                self._connection.close()
            self._closed = True

    def __enter__(self) -> DatasetResult:
        if self._closed:
            raise DatasetReadError("This dataset result has already been closed.")
        return self

    def __exit__(self, *arguments: object) -> None:
        self.close()

    def to_parquet(self, destination: str | Path) -> None:
        """Atomically publish the original loaded Pandas data as a new file.

        This is a source-data export. Later operations on ``frame`` are not
        implicitly evaluated or substituted for that original Pandas dataset.
        """
        if self._closed:
            raise DatasetReadError("This dataset result has already been closed.")
        path = Path(destination)
        if path.suffix.lower() != ".parquet":
            raise DatasetReadError("Dataset export currently requires a .parquet destination.")
        if path.exists() or path.is_symlink():
            raise FileExistsError("Dataset export refuses to overwrite an existing destination.")
        _assert_pandas_snapshot(self)
        arrow = _pandas_arrow(self.pandas)
        parquet = _dependency("pyarrow.parquet", "arrow")
        temporary: Path | None = None
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            for _ in range(8):
                candidate = path.parent / (".equiframe-parquet-" + uuid4().hex + ".tmp")
                try:
                    descriptor = os.open(candidate, flags, 0o600)
                except FileExistsError:
                    continue
                temporary = candidate
                break
            else:
                raise FileExistsError("Cannot allocate a unique Parquet temporary file.")
            # Retry only actual name collisions. Windows tempfile may repeatedly
            # retry PermissionError because os.access does not reflect its ACL.
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = None  # The stream now owns and closes this handle.
                parquet.write_table(arrow, stream)
                stream.flush()
                os.fsync(stream.fileno())
            # A same-filesystem hard link publishes only the complete file and
            # fails atomically if another writer created the destination first.
            # Do not fall back to rename/replace or expose a partially copied file.
            os.link(temporary, path)
        finally:
            try:
                if descriptor is not None:
                    os.close(descriptor)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def load_dataset(
    source: str | Path,
    *,
    target: DatasetTarget = "pandas",
    options: DatasetReadOptions | None = None,
) -> DatasetResult:
    """Read a local file into Pandas, optionally convert that DataFrame to a target.

    CSV/JSON/JSONL/TXT/XML/Excel/Parquet/GeoJSON are supported. Ambiguous Excel
    sheets, JSON record collections and TXT delimiters require an explicit option.
    There is no network access, automatic dependency install or silent fallback.
    """
    if target not in ("pandas", "polars", "duckdb"):
        raise DatasetReadError("target must be pandas, polars or duckdb.")
    opts = options or DatasetReadOptions()
    _validate_options(opts)
    path = Path(source)
    if not path.is_file():
        raise DatasetReadError("source must be an existing local regular file.")
    if path.stat().st_size > opts.max_bytes:
        raise DatasetReadError("The source exceeds max_bytes; increase the explicit limit.")
    kind = _format(path, opts.format)
    payload = _read_bytes(path, opts.max_bytes)
    pd = _dependency("pandas", "pandas")
    notes: list[str] = []
    metadata: dict[str, Any] = {}
    if kind == "parquet":
        parquet = _dependency("pyarrow.parquet", "arrow")
        with io.BytesIO(payload) as stream:
            reader = parquet.ParquetFile(stream)
            if reader.metadata.num_rows > opts.max_rows:
                raise DatasetReadError("The Parquet file exceeds max_rows.")
            if reader.metadata.num_rows * len(reader.schema_arrow) > opts.max_cells:
                raise DatasetReadError("The Parquet table exceeds max_cells.")
            table = reader.read()
        _column_names(table.column_names)
        frame = table.to_pandas(types_mapper=pd.ArrowDtype)
        notes.append("Parquet Arrow types, temporal metadata and null masks are retained.")
        frame = _override_frame(frame, opts, pd, notes)
    else:
        if kind == "excel":
            rows, names, metadata = _excel_rows(path, opts, notes, payload=payload)
        else:
            if kind == "xml":
                rows, names, metadata = _xml_rows(payload, opts)
            else:
                try:
                    text = payload.decode(opts.encoding)
                except (UnicodeError, LookupError) as error:
                    raise DatasetReadError(
                        "Cannot decode this file; set encoding explicitly."
                    ) from error
                if kind in ("json", "jsonl", "geojson"):
                    rows, names, metadata = _json_rows(text, kind, opts)
                else:
                    rows, names, metadata = _text_rows(text, kind, opts, notes)
        _check_dimensions(rows, names, opts)
        _column_names(names)
        columns: dict[str, Any] = {}
        for index, name in enumerate(names):
            values = [row[index] for row in rows]
            is_free_text = (
                kind == "txt"
                and names == ["text"]
                and any(note.startswith("Free text:") for note in notes)
            )
            if kind in ("csv", "txt", "xml") and opts.infer_text_types and not is_free_text:
                values, inferred = _infer_text(values)
                if inferred:
                    notes.append(f"Column {name!r}: inferred {inferred} without float parsing.")
            if name in opts.column_types:
                values = _convert_column(values, opts.column_types[name])
                notes.append(f"Column {name!r}: explicit {opts.column_types[name]} conversion.")
            columns[name] = _series(values, pd, opts.column_types.get(name))
        unknown = set(opts.column_types).difference(names)
        if unknown:
            raise DatasetReadError("column_types contains a column absent from the file.")
        frame = pd.DataFrame(columns, index=range(len(rows)))
    info = _describe(frame, kind, notes, metadata, pd)
    effective = asdict(opts)
    effective["format"] = kind
    for key in ("sheet", "delimiter", "header", "text_mode"):
        if key in metadata:
            effective[key] = metadata[key]
    source_identity = DatasetSource(
        uri=path.absolute().as_uri(),
        format=kind,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        read_options_json=json.dumps(
            effective, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ),
    )
    fingerprint = pandas_fingerprint(frame, pd)
    provenance = DatasetProvenance(source_identity, fingerprint, "pandas", fingerprint)
    info = replace(info, provenance=provenance)
    original = DatasetResult(frame, frame, "pandas", info, provenance=provenance)
    return original if target == "pandas" else convert_dataset(original, target=target)


def inspect_dataset(
    source: str | Path, *, options: DatasetReadOptions | None = None
) -> DatasetInfo:
    """Load and describe the complete bounded dataset; this is not a sample scan."""
    with load_dataset(source, options=options) as result:
        return result.info


def convert_dataset(dataset: DatasetResult, *, target: DatasetTarget) -> DatasetResult:
    """Convert the current native frame without rereading the file.

    The original Pandas snapshot remains the source identity. Chained
    conversions consume the current Pandas, Polars or DuckDB frame and verify
    that neither that frame nor the original snapshot changed after capture.
    """
    if dataset._closed:
        raise DatasetReadError("Cannot convert a closed dataset result.")
    if target not in ("pandas", "polars", "duckdb"):
        raise DatasetReadError("target must be pandas, polars or duckdb.")
    _assert_pandas_snapshot(dataset)
    table = _current_dataset_table(dataset)
    if target == "pandas":
        if dataset.target == "pandas":
            return _converted_result(dataset, dataset.frame, target)
        pd = _dependency("pandas", "pandas")
        # Rebuild from the actual native values, retaining the source's Pandas
        # dtypes and their nullable masks, instead of returning an old frame.
        pandas_frame = pd.DataFrame(
            {
                name: pd.Series(table[name].to_pylist(), dtype=dataset.pandas[name].dtype)
                for name in table.column_names
            },
            index=range(table.num_rows),
        )
        _assert_conversion(table, _pandas_arrow(pandas_frame), "Pandas")
        return _converted_result(dataset, pandas_frame, target)
    if target == "polars":
        polars = _dependency("polars", "polars")
        try:
            frame = polars.from_arrow(table, rechunk=True)
            _assert_conversion(table, frame.to_arrow(), "Polars")
        except Exception as error:
            if isinstance(error, CapabilityError):
                raise
            raise CapabilityError(
                "Polars cannot represent this inferred schema faithfully."
            ) from error
        return _converted_result(dataset, frame, target, table=frame.to_arrow())
    duckdb = _dependency("duckdb", "duckdb")
    connection = duckdb.connect(
        database=":memory:",
        config={"autoinstall_known_extensions": "false", "autoload_known_extensions": "false"},
    )
    try:
        relation = connection.from_arrow(table)
        # Materialize now: constructing a lazy relation alone does not prove that
        # DuckDB can consume all values of this Arrow schema.
        materialized = relation.to_arrow_table()
        _assert_conversion(table, materialized, "DuckDB")
        native = connection.from_arrow(materialized)
        return _converted_result(dataset, native, target, table=materialized, connection=connection)
    except Exception as error:
        connection.close()
        if isinstance(error, CapabilityError):
            raise
        raise CapabilityError("DuckDB cannot represent this inferred schema faithfully.") from error


def _current_dataset_table(dataset: DatasetResult) -> Any:
    """Capture the selected native input and reject stale or altered identity."""
    pd = _dependency("pandas", "pandas")
    if dataset.target == "pandas":
        if not isinstance(dataset.frame, pd.DataFrame):
            raise DatasetReadError("The selected Pandas frame is not a Pandas DataFrame.")
        table = _pandas_arrow(dataset.frame)
        digest = None
        if dataset.provenance is not None:
            digest = (
                dataset.provenance.pandas_sha256
                if dataset.frame is dataset.pandas
                else pandas_fingerprint(dataset.frame, pd)
            )
    elif dataset.target == "polars":
        pl = _dependency("polars", "polars")
        if not isinstance(dataset.frame, pl.DataFrame):
            raise DatasetReadError("The selected Polars frame is not a Polars DataFrame.")
        _assert_native_schema(
            dataset, tuple((name, str(dtype)) for name, dtype in dataset.frame.schema.items())
        )
        if dataset.frame.height != dataset.info.rows:
            raise DatasetReadError("The native frame row count changed after loading.")
        table = dataset.frame.to_arrow()
        digest = arrow_fingerprint(table, pd) if dataset.provenance is not None else None
    elif dataset.target == "duckdb":
        duckdb = _dependency("duckdb", "duckdb")
        if not isinstance(dataset.frame, duckdb.DuckDBPyRelation):
            raise DatasetReadError("The selected DuckDB frame is not a DuckDB relation.")
        # Arrow alone cannot establish native type fidelity: for example,
        # UHUGEINT may wrap to a negative decimal128 during DuckDB export.
        # Compare the captured native schema before executing/converting it.
        _assert_native_schema(
            dataset,
            tuple(zip(dataset.frame.columns, map(str, dataset.frame.types), strict=True)),
        )
        table = dataset.frame.limit(dataset.info.rows + 1).to_arrow_table()
        digest = arrow_fingerprint(table, pd) if dataset.provenance is not None else None
    else:
        raise DatasetReadError("The dataset input must be pandas, polars or duckdb.")
    if dataset.provenance is not None and (
        dataset.provenance.target != dataset.target or digest != dataset.provenance.target_sha256
    ):
        raise DatasetReadError(
            "The native frame changed after loading; capture modified data as a new input "
            "before conversion instead of reusing its earlier identity."
        )
    if dataset.frame is not dataset.pandas:
        _assert_conversion(_pandas_arrow(dataset.pandas), table, "Native input")
    return table


def _assert_native_schema(dataset: DatasetResult, observed: tuple[tuple[str, str], ...]) -> None:
    if dataset._native_schema is None or observed != dataset._native_schema:
        raise DatasetReadError(
            "The native schema changed or was not captured; reload the source "
            "before conversion instead of reusing an unverified native identity."
        )


def _assert_pandas_snapshot(dataset: DatasetResult) -> None:
    if dataset.provenance is not None:
        pd = _dependency("pandas", "pandas")
        if pandas_fingerprint(dataset.pandas, pd) != dataset.provenance.pandas_sha256:
            raise DatasetReadError(
                "The original Pandas data changed after loading; reload the source or "
                "capture the modified data as a separate execution before conversion/export."
            )


def _converted_result(
    original: DatasetResult,
    frame: Any,
    target: DatasetTarget,
    *,
    table: Any = None,
    connection: Any = None,
) -> DatasetResult:
    native_schema = None
    if target == "polars":
        native_schema = tuple((name, str(dtype)) for name, dtype in frame.schema.items())
    elif target == "duckdb":
        native_schema = tuple(zip(frame.columns, map(str, frame.types), strict=True))
    provenance = original.provenance
    if provenance is not None:
        digest = (
            pandas_fingerprint(frame, _dependency("pandas", "pandas"))
            if target == "pandas"
            else arrow_fingerprint(table, _dependency("pandas", "pandas"))
        )
        provenance = DatasetProvenance(provenance.source, provenance.pandas_sha256, target, digest)
    result = DatasetResult(
        original.pandas,
        frame,
        target,
        replace(original.info, provenance=provenance),
        _connection=connection,
        provenance=provenance,
    )
    result._native_schema = native_schema
    return result


def _arrow_type_equivalent(left: Any, right: Any, pa: ModuleType) -> bool:
    if left.equals(right):
        return True
    if (pa.types.is_string(left) or pa.types.is_large_string(left)) and (
        pa.types.is_string(right) or pa.types.is_large_string(right)
    ):
        return True
    if (pa.types.is_binary(left) or pa.types.is_large_binary(left)) and (
        pa.types.is_binary(right) or pa.types.is_large_binary(right)
    ):
        return True
    if (pa.types.is_list(left) or pa.types.is_large_list(left)) and (
        pa.types.is_list(right) or pa.types.is_large_list(right)
    ):
        return _arrow_type_equivalent(left.value_type, right.value_type, pa)
    if pa.types.is_struct(left) and pa.types.is_struct(right) and len(left) == len(right):
        return all(
            first.name == second.name and _arrow_type_equivalent(first.type, second.type, pa)
            for first, second in zip(left, right, strict=False)
        )
    return False


def _same_value(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, Decimal):
        return isinstance(right, Decimal) and left.as_tuple() == right.as_tuple()
    if isinstance(left, float):
        if not isinstance(right, float):
            return False
        if math.isnan(left):
            return math.isnan(right)
        if left == 0.0 and right == 0.0:
            return math.copysign(1.0, left) == math.copysign(1.0, right)
        return left == right
    if isinstance(left, Mapping):
        return (
            isinstance(right, Mapping)
            and left.keys() == right.keys()
            and all(_same_value(value, right[key]) for key, value in left.items())
        )
    if isinstance(left, (list, tuple)):
        return (
            isinstance(right, (list, tuple))
            and len(left) == len(right)
            and all(_same_value(first, second) for first, second in zip(left, right, strict=False))
        )
    return type(left) is type(right) and bool(left == right)


def _assert_conversion(before: Any, after: Any, engine: str) -> None:
    """Read the full native result back; hashes or samples cannot establish fidelity."""
    pa = _dependency("pyarrow", "arrow")
    if before.num_rows != after.num_rows or before.column_names != after.column_names:
        raise CapabilityError(f"{engine} conversion changed the row count or column names/order.")
    for expected, actual in zip(before.schema, after.schema, strict=False):
        if not _arrow_type_equivalent(expected.type, actual.type, pa):
            raise CapabilityError(
                f"{engine} changed a column type, decimal scale, temporal unit or timezone; "
                "choose an explicit compatible input representation."
            )
    for name in before.column_names:
        expected_values = before[name].to_pylist()
        actual_values = after[name].to_pylist()
        if any(
            not _same_value(first, second)
            for first, second in zip(expected_values, actual_values, strict=False)
        ):
            raise CapabilityError(
                f"{engine} conversion changed a value, null/NaN distinction or row order."
            )


def _dependency(module: str, extra: str) -> ModuleType:
    try:
        return import_module(module)
    except ImportError as error:
        raise MissingDependencyError(
            f"This operation requires {module}; install the equiframe[{extra}] optional extra."
        ) from error
    except (RuntimeError, OSError) as error:
        if module == "polars" and os.name == "nt" and not os.environ.get("PROCESSOR_ARCHITECTURE"):
            raise DatasetReadError(
                "Polars could not initialize without the Windows PROCESSOR_ARCHITECTURE "
                "environment variable; preserve the standard Windows process environment."
            ) from error
        raise CapabilityError(
            f"The installed {module} dependency could not initialize; "
            "check its runtime and the operating-system environment."
        ) from error


def _validate_options(options: DatasetReadOptions) -> None:
    if not isinstance(options, DatasetReadOptions):
        raise DatasetReadError("options must be DatasetReadOptions.")
    for value in (options.max_bytes, options.max_rows, options.max_cells):
        if type(value) is not int or value < 1:
            raise DatasetReadError("max_bytes, max_rows and max_cells must be positive integers.")
    if type(options.header) is not bool or type(options.infer_text_types) is not bool:
        raise DatasetReadError("header and infer_text_types must be booleans.")
    if not isinstance(options.encoding, str) or not options.encoding:
        raise DatasetReadError("encoding must be a nonempty string.")
    if options.format is not None and not isinstance(options.format, str):
        raise DatasetReadError("format must be a documented format name.")
    if options.sheet is not None and not isinstance(options.sheet, str):
        raise DatasetReadError("sheet must be an Excel sheet name.")
    if options.records_path is not None and not isinstance(options.records_path, str):
        raise DatasetReadError("records_path must be a string.")
    if options.delimiter is not None and (
        not isinstance(options.delimiter, str)
        or len(options.delimiter) != 1
        or options.delimiter in "\r\n\x00"
    ):
        raise DatasetReadError("delimiter must be one non-newline character.")
    if options.text_mode not in ("auto", "lines", "delimited"):
        raise DatasetReadError("text_mode must be auto, lines or delimited.")
    if not isinstance(options.column_types, Mapping) or any(
        not isinstance(name, str) or not name for name in options.column_types
    ):
        raise DatasetReadError("column_types must map nonempty column names to types.")
    if any(
        value not in ("string", "integer", "decimal", "boolean", "json")
        for value in options.column_types.values()
    ):
        raise DatasetReadError("column_types supports string, integer, decimal, boolean and json.")


def _format(path: Path, explicit: DatasetFormat | None) -> DatasetFormat:
    extensions: dict[str, DatasetFormat] = {
        ".json": "json",
        ".jsonl": "jsonl",
        ".ndjson": "jsonl",
        ".xlsx": "excel",
        ".xlsm": "excel",
        ".xls": "excel",
        ".txt": "txt",
        ".tsv": "txt",
        ".xml": "xml",
        ".csv": "csv",
        ".parquet": "parquet",
        ".geojson": "geojson",
    }
    if explicit is not None:
        if explicit not in set(extensions.values()):
            raise DatasetReadError("Unsupported format; use a documented dataset format.")
        return explicit
    if path.suffix.lower() not in extensions:
        raise DatasetChoiceRequired(
            "format", sorted(set(extensions.values())), "Specify the format of this file."
        )
    return extensions[path.suffix.lower()]


def _read_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise DatasetReadError("The source exceeds max_bytes.")
    return data


def _column_names(names: Sequence[str]) -> None:
    if any(not isinstance(name, str) or not name for name in names):
        raise DatasetReadError("Every column must have a nonempty string name.")
    if len(set(names)) != len(names):
        raise DatasetReadError("Duplicate column names are refused; select a unique header.")


def _check_dimensions(rows: Sequence[Any], names: Sequence[str], opts: DatasetReadOptions) -> None:
    if len(rows) > opts.max_rows or len(rows) * len(names) > opts.max_cells:
        raise DatasetReadError("The dataset exceeds max_rows or max_cells.")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DatasetReadError("Duplicate JSON object members are refused.")
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise DatasetReadError("JSON NaN and Infinity tokens are not valid JSON numbers.")


def _decode_json(text: str) -> Any:
    try:
        return json.loads(
            text, parse_float=Decimal, object_pairs_hook=_pairs, parse_constant=_constant
        )
    except (ValueError, RecursionError) as error:
        raise DatasetReadError("Invalid or excessively nested JSON input.") from error


def _pointer(root: Any, pointer: str) -> Any:
    if pointer == "":
        return root
    if not pointer.startswith("/"):
        raise DatasetReadError("JSON records_path must be an RFC 6901 pointer such as /data/items.")
    value = root
    try:
        for token in pointer[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
        return value
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise DatasetReadError(
            "JSON records_path does not identify an available collection."
        ) from error


def _json_rows(
    text: str, kind: DatasetFormat, opts: DatasetReadOptions
) -> tuple[list[list[Any]], list[str], dict[str, Any]]:
    if kind == "jsonl":
        records: Any = []
        for line in text.splitlines():
            if line.strip():
                records.append(_decode_json(line))
                if len(records) > opts.max_rows:
                    raise DatasetReadError("The JSONL file exceeds max_rows.")
        if opts.records_path is not None:
            raise DatasetReadError("records_path is not used with JSONL records.")
    else:
        records = _decode_json(text)
    if kind == "geojson" or (
        isinstance(records, dict) and records.get("type") in ("FeatureCollection", "Feature")
    ):
        if opts.records_path is not None:
            raise DatasetReadError("GeoJSON uses its feature structure; do not set records_path.")
        return _geojson_rows(records, opts)
    if opts.records_path is not None:
        records = _pointer(records, opts.records_path)
    elif isinstance(records, dict):
        candidates = _record_paths(records)
        if candidates:
            raise DatasetChoiceRequired(
                "records_path",
                candidates,
                "Choose the JSON record collection; "
                "nested collections are not expanded implicitly.",
            )
    if isinstance(records, dict) or not isinstance(records, list):
        records = [records]
    if any(not isinstance(record, dict) for record in records):
        _check_dimensions(records, ["value"], opts)
        return (
            [[record] for record in records],
            ["value"],
            {"json_layout": "one_value_per_row"},
        )
    names = _mapping_names(records)
    absent = {
        name: [index for index, record in enumerate(records) if name not in record]
        for name in names
        if any(name not in record for record in records)
    }
    metadata: dict[str, Any] = {}
    if absent:
        metadata["absent_json_members_by_row"] = absent
    return _mapping_rows(records, opts), names, metadata


def _record_paths(root: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    pending = [("", root)]
    while pending:
        parent, record = pending.pop()
        for key, value in record.items():
            path = parent + "/" + key.replace("~", "~0").replace("/", "~1")
            if isinstance(value, dict):
                pending.append((path, value))
            elif isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
                candidates.append(path)
                if len(candidates) > 64:
                    raise DatasetReadError(
                        "Too many JSON record collections to list; set records_path explicitly."
                    )
    return candidates


def _mapping_names(records: Any) -> list[str]:
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise DatasetReadError(
            "A JSON table must be a record object or an array of record objects."
        )
    names: dict[str, None] = {}
    for record in records:
        for key in record:
            if not isinstance(key, str) or not key:
                raise DatasetReadError("Record fields must have nonempty string names.")
            names[key] = None
    return list(names)


def _mapping_rows(records: Any, opts: DatasetReadOptions) -> list[list[Any]]:
    names = _mapping_names(records)
    _check_dimensions(records, names, opts)
    return [[record.get(name) for name in names] for record in records]


def _geojson_rows(
    value: Any, opts: DatasetReadOptions
) -> tuple[list[list[Any]], list[str], dict[str, Any]]:
    if not isinstance(value, dict):
        raise DatasetReadError("GeoJSON must contain an object.")
    geometry_types = {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
        "GeometryCollection",
    }
    if value.get("type") in geometry_types:
        return [[value]], ["geometry"], {"geojson_type": value["type"]}
    metadata: dict[str, Any] = {"geojson_type": value.get("type")}
    if value.get("type") == "FeatureCollection":
        features = value.get("features")
        metadata["collection_members"] = {
            key: item for key, item in value.items() if key != "features"
        }
    elif value.get("type") == "Feature":
        features = [value]
    else:
        raise DatasetReadError("Expected a GeoJSON FeatureCollection, Feature or geometry object.")
    if not isinstance(features, list):
        raise DatasetReadError("GeoJSON features must be an array.")
    records: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise DatasetReadError("Every GeoJSON collection member must be a Feature.")
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if properties is not None and not isinstance(properties, dict):
            raise DatasetReadError("GeoJSON properties must be an object or null.")
        if geometry is not None and (
            not isinstance(geometry, dict) or geometry.get("type") not in geometry_types
        ):
            raise DatasetReadError("GeoJSON geometry must be a geometry object or null.")
        record = {"geometry": geometry, "properties": properties}
        if properties is not None:
            record.update({"properties." + key: item for key, item in properties.items()})
        record.update(
            {
                "feature." + key: item
                for key, item in feature.items()
                if key not in ("geometry", "properties")
            }
        )
        records.append(record)
    return _mapping_rows(records, opts), _mapping_names(records), metadata


def _text_rows(
    text: str, kind: DatasetFormat, opts: DatasetReadOptions, notes: list[str]
) -> tuple[list[list[Any]], list[str], dict[str, Any]]:
    if kind == "txt" and opts.text_mode == "lines":
        notes.append("Free text: one line per row, without interpreting or dropping blank lines.")
        return (
            [[line] for line in text.splitlines()],
            ["text"],
            {"text_mode": "lines", "header": False, "delimiter": None},
        )
    delimiter = opts.delimiter
    if delimiter is None:
        candidates: list[str] = []
        for candidate in (",", ";", "\t", "|"):
            try:
                parsed = []
                for row in csv.reader(io.StringIO(text), delimiter=candidate, strict=True):
                    parsed.append(row)
                    if len(parsed) == 64:
                        break
                widths = {len(row) for row in parsed if row}
                if len(widths) == 1 and next(iter(widths), 0) > 1:
                    candidates.append(candidate)
            except csv.Error:
                continue
        if len(candidates) == 1:
            if kind == "txt" and opts.text_mode == "auto":
                raise DatasetChoiceRequired(
                    "text_mode",
                    ["delimited", "lines"],
                    "TXT may be a table or free text; choose how its lines should be interpreted.",
                )
            delimiter = candidates[0]
            notes.append(
                "Detected a consistent delimited structure; header=True unless overridden."
            )
        elif candidates:
            raise DatasetChoiceRequired(
                "delimiter", candidates, "Several delimiters fit; choose one explicitly."
            )
        elif kind == "txt" and opts.text_mode == "auto":
            notes.append(
                "Free text: one line per row; set text_mode='delimited' to require a table."
            )
            return (
                [[line] for line in text.splitlines()],
                ["text"],
                {"text_mode": "lines", "header": False, "delimiter": None},
            )
        elif kind == "csv":
            delimiter = ","
        else:
            raise DatasetChoiceRequired(
                "delimiter",
                [",", ";", "\t", "|"],
                "Set the TXT delimiter or choose text_mode='lines'.",
            )
    rows: list[list[Any]] = []
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True):
            rows.append(row)
            if len(rows) > opts.max_rows + int(opts.header):
                raise DatasetReadError("The delimited file exceeds max_rows.")
    except csv.Error as error:
        raise DatasetReadError("Malformed delimited input; rows were not skipped.") from error
    if not rows:
        raise DatasetReadError("An empty delimited file has no discoverable columns.")
    names = rows.pop(0) if opts.header else [f"column_{index + 1}" for index in range(len(rows[0]))]
    if any(len(row) != len(names) for row in rows):
        raise DatasetReadError(
            "Ragged or blank delimited records are refused; rows were not padded or skipped."
        )
    notes.append("Empty text fields remain empty strings; dates and null tokens are not guessed.")
    return rows, names, {"text_mode": "delimited", "header": opts.header, "delimiter": delimiter}


def _xml_value(element: Any) -> Any:
    children = list(element)
    if not children and not element.attrib:
        return element.text if element.text is not None else ""
    record: dict[str, Any] = {"@" + key: item for key, item in element.attrib.items()}
    if element.text is not None and element.text.strip():
        record["#text"] = element.text
    for child in children:
        child_value = _xml_value(child)
        if child.tag in record:
            previous = record[child.tag]
            record[child.tag] = (
                [*previous, child_value] if isinstance(previous, list) else [previous, child_value]
            )
        else:
            record[child.tag] = child_value
        if child.tail is not None and child.tail.strip():
            raise DatasetReadError(
                "Mixed XML text after child elements needs an explicit preprocessing step."
            )
    return record


def _xml_rows(
    payload: bytes, opts: DatasetReadOptions
) -> tuple[list[list[Any]], list[str], dict[str, Any]]:
    safe_xml = _dependency("defusedxml.ElementTree", "files")
    try:
        root = safe_xml.fromstring(
            payload, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except Exception as error:
        raise DatasetReadError(
            "XML must be well-formed and contain no DTD, entities or external references."
        ) from error
    if opts.records_path is not None:
        try:
            elements = root.findall(opts.records_path)
        except (SyntaxError, KeyError) as error:
            raise DatasetReadError(
                "Invalid XML records_path; use an ElementTree element path."
            ) from error
        if not elements:
            raise DatasetReadError("XML records_path selected no elements.")
    else:
        children = list(root)
        elements = children if children and len({child.tag for child in children}) == 1 else [root]
        if elements is children and (
            (root.text is not None and root.text.strip())
            or any(child.tail is not None and child.tail.strip() for child in children)
        ):
            raise DatasetReadError(
                "Mixed XML container text cannot be discarded while selecting child records."
            )
    records: list[dict[str, Any]] = []
    for element in elements:
        value = _xml_value(element)
        records.append(value if isinstance(value, dict) else {"text": value})
    metadata = {"xml_root": root.tag, "xml_root_attributes": dict(root.attrib)}
    return _mapping_rows(records, opts), _mapping_names(records), metadata


def _choose_sheet(names: Sequence[str], selected: str | None) -> str:
    if selected is None:
        if len(names) != 1:
            raise DatasetChoiceRequired("sheet", names, "Choose the Excel sheet to load.")
        return names[0]
    if selected not in names:
        raise DatasetChoiceRequired("sheet", names, "The requested Excel sheet is not available.")
    return selected


def _excel_rows(
    path: Path, opts: DatasetReadOptions, notes: list[str], *, payload: bytes | None = None
) -> tuple[list[list[Any]], list[str], dict[str, Any]]:
    rows: list[list[Any]] = []
    number_formats: dict[str, set[str]] = {}
    width = 0

    def append_row(row: list[Any]) -> None:
        nonlocal width
        next_width = max(width, len(row))
        data_rows = max(0, len(rows) + 1 - int(opts.header))
        if data_rows > opts.max_rows or next_width * max(1, data_rows) > opts.max_cells:
            raise DatasetReadError("The Excel sheet exceeds max_rows or max_cells.")
        width = next_width
        rows.append(row)

    if path.suffix.lower() == ".xls":
        xlrd = _dependency("xlrd", "files")
        book = (
            xlrd.open_workbook(str(path), on_demand=True)
            if payload is None
            else xlrd.open_workbook(file_contents=payload, on_demand=True)
        )
        try:
            name = _choose_sheet(book.sheet_names(), opts.sheet)
            sheet = book.sheet_by_name(name)
            data_rows = max(0, sheet.nrows - int(opts.header))
            if data_rows > opts.max_rows or sheet.ncols * max(1, data_rows) > opts.max_cells:
                raise DatasetReadError("The Excel sheet exceeds max_rows or max_cells.")
            for row_index in range(sheet.nrows):
                row: list[Any] = []
                for cell in sheet.row(row_index):
                    if cell.ctype == xlrd.XL_CELL_ERROR:
                        raise DatasetReadError("Excel error cells are refused.")
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        value = xlrd.xldate.xldate_as_datetime(cell.value, book.datemode)
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        value = bool(cell.value)
                    elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        value = None
                    else:
                        value = cell.value
                    row.append(value)
                append_row(row)
            notes.append(
                "Legacy XLS exposes stored/cached cell values; "
                "formulas cannot be independently identified by this reader."
            )
        finally:
            book.release_resources()
    else:
        openpyxl = _dependency("openpyxl", "files")
        book = openpyxl.load_workbook(
            path if payload is None else io.BytesIO(payload),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
        try:
            name = _choose_sheet(book.sheetnames, opts.sheet)
            sheet = book[name]
            # Worksheet dimensions are optional producer metadata and can be
            # smaller than the actual stored cells. Never use them to truncate
            # rows/columns; enforce budgets against each observed row instead.
            sheet.reset_dimensions()
            for row_index, cells in enumerate(sheet.iter_rows()):
                if row_index + 1 - int(opts.header) > opts.max_rows:
                    raise DatasetReadError("The Excel sheet exceeds max_rows or max_cells.")
                row = []
                for index, cell in enumerate(cells):
                    if cell.data_type in ("f", "e"):
                        raise DatasetReadError(
                            "Excel formula/error cells are refused; supply a values-only workbook."
                        )
                    value = cell.value
                    fmt = cell.number_format
                    if row_index >= int(opts.header) and value is not None:
                        number_formats.setdefault(str(index), set()).add(fmt)
                        if (
                            isinstance(value, (int, float))
                            and not isinstance(value, bool)
                            and re.fullmatch(r"0{2,}", fmt)
                            and float(value).is_integer()
                        ):
                            value = str(int(value)).zfill(len(fmt))
                            notes.append("Excel zero-padded numeric display retained as text.")
                    row.append(value)
                append_row(row)
        finally:
            book.close()
    if not rows:
        raise DatasetReadError("The selected Excel sheet has no discoverable columns.")
    if opts.header:
        names = rows.pop(0)
        if len(names) != width or any(not isinstance(item, str) or not item for item in names):
            raise DatasetReadError(
                "Excel header cells must be nonempty strings; "
                "use header=False when no header exists."
            )
    else:
        names = [f"column_{index + 1}" for index in range(width)]
    for row in rows:
        row.extend([None] * (width - len(row)))
    notes.append(
        "Excel stored numeric values retain the workbook's numeric precision; "
        "formatting does not recover lost digits."
    )
    return (
        rows,
        names,
        {
            "sheet": name,
            "number_formats_by_position": {
                key: sorted(value) for key, value in number_formats.items()
            },
        },
    )


def _infer_text(values: list[Any]) -> tuple[list[Any], str | None]:
    present = [value for value in values if value is not None]
    if not present or any(not isinstance(value, str) or not value for value in present):
        return values, None
    integer = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
    if all(integer.fullmatch(value) and value != "-0" for value in present):
        return [None if value is None else int(value) for value in values], "integer"
    numeric = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
    if all(numeric.fullmatch(value) for value in present):
        decimals = [None if value is None else Decimal(value) for value in values]
        if all(value is None or value.is_finite() for value in decimals):
            return decimals, "decimal"
    return values, None


def _convert_column(values: list[Any], kind: str) -> list[Any]:
    converted: list[Any] = []
    for value in values:
        if value is None:
            converted.append(None)
            continue
        try:
            if kind == "string":
                if isinstance(value, (dict, list)):
                    raise ValueError("Nested data cannot be implicitly stringified.")
                item: Any = str(value)
            elif kind == "json":
                item = _json_text(value)
            elif kind == "integer":
                if isinstance(value, (bool, float)):
                    raise ValueError("Boolean/float to integer requires explicit preprocessing.")
                item = int(value)
                if isinstance(value, Decimal) and value != item:
                    raise ValueError("Fractional integer conversion.")
            elif kind == "decimal":
                if isinstance(value, (bool, float)):
                    raise ValueError("Binary float to exact Decimal is not automatic.")
                item = Decimal(value)
                if not item.is_finite():
                    raise ValueError("Nonfinite Decimal.")
            elif kind == "boolean":
                if isinstance(value, bool):
                    item = value
                elif value in ("true", "false"):
                    item = value == "true"
                else:
                    raise ValueError("Boolean values must be true or false.")
            else:
                raise ValueError("Unsupported explicit column type.")
        except (ValueError, TypeError, InvalidOperation, OverflowError) as error:
            raise DatasetReadError(
                "An explicit column conversion cannot preserve a value."
            ) from error
        converted.append(item)
    return converted


def _json_text(value: Any) -> str:
    """Explicit JSON-text representation, keeping Decimal numbers out of floats."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("JSON cannot represent a nonfinite Decimal.")
        return str(value)
    if isinstance(value, float):
        return json.dumps(value, allow_nan=False)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_json_text(item) for item in value) + "]"
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return (
            "{"
            + ",".join(
                json.dumps(key, ensure_ascii=True) + ":" + _json_text(item)
                for key, item in value.items()
            )
            + "}"
        )
    raise ValueError("This value has no declared JSON representation.")


def _series(values: list[Any], pandas: ModuleType, declared: str | None = None) -> Any:
    present = [value for value in values if value is not None]
    if not present:
        if declared in ("string", "json"):
            return pandas.Series(values, dtype=pandas.StringDtype(storage="python"))
        if declared == "integer":
            return pandas.Series(values, dtype="Int64")
        if declared == "boolean":
            return pandas.Series(values, dtype="boolean")
    if present and all(isinstance(value, bool) for value in present):
        return pandas.Series(values, dtype="boolean")
    if present and all(type(value) is int for value in present):
        low, high = min(present), max(present)
        if low >= -(2**63) and high < 2**63:
            return pandas.Series(values, dtype="Int64")
        if low >= 0 and high < 2**64:
            return pandas.Series(values, dtype="UInt64")
    if present and all(isinstance(value, str) for value in present):
        return pandas.Series(values, dtype=pandas.StringDtype(storage="python"))
    # object preserves Decimal, nested values, datetime objects and the distinction
    # between a None and a floating NaN; no binary float intermediate is introduced.
    return pandas.Series(values, dtype=object)


def _override_frame(frame: Any, opts: DatasetReadOptions, pd: ModuleType, notes: list[str]) -> Any:
    if set(opts.column_types).difference(frame.columns):
        raise DatasetReadError("column_types contains a column absent from the file.")
    for name, kind in opts.column_types.items():
        values = [
            None if item is pd.NA or item is pd.NaT else item for item in frame[name].tolist()
        ]
        frame[name] = _series(_convert_column(values, kind), pd, kind)
        notes.append(f"Column {name!r}: explicit {kind} conversion.")
    return frame


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, datetime):
        return "timestamp"
    if isinstance(value, date):
        return "date"
    if isinstance(value, time):
        return "time"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, bytes):
        return "binary"
    return type(value).__name__


def _describe(
    frame: Any, kind: DatasetFormat, notes: list[str], metadata: dict[str, Any], pd: ModuleType
) -> DatasetInfo:
    columns: list[DatasetColumn] = []
    for name in frame.columns:
        values = frame[name].tolist()
        nonnull = [
            value
            for value in values
            if value is not None and value is not pd.NA and value is not pd.NaT
        ]
        columns.append(
            DatasetColumn(
                name,
                str(frame[name].dtype),
                tuple(sorted({_value_type(value) for value in nonnull})),
                len(values) - len(nonnull),
                sum(isinstance(value, float) and math.isnan(value) for value in nonnull),
            )
        )
    return DatasetInfo(kind, len(frame), tuple(columns), tuple(dict.fromkeys(notes)), metadata)


def _pandas_arrow(frame: Any) -> Any:
    pa = _dependency("pyarrow", "arrow")
    pd = _dependency("pandas", "pandas")
    arrays = []
    if len(frame.columns) == 0 and len(frame) > 0:
        raise CapabilityError("A nonempty dataset with no columns cannot be converted faithfully.")
    try:
        for name in frame.columns:
            series = frame[name]
            if not pd.api.types.is_object_dtype(series.dtype):
                # Preserve signedness, widths and nullable extension masks,
                # including an explicitly typed column containing only nulls.
                arrays.append(pa.array(series.array, from_pandas=False))
            else:
                values = [
                    None if value is pd.NA or value is pd.NaT else value
                    for value in series.tolist()
                ]
                array = pa.array(values, from_pandas=False)
                if any(
                    not _same_value(original, represented)
                    for original, represented in zip(values, array.to_pylist(), strict=False)
                ):
                    raise CapabilityError(
                        "Arrow inference would change a value or nested field presence; "
                        "declare column_types explicitly (json preserves nested JSON as text)."
                    )
                arrays.append(array)
        return pa.Table.from_arrays(arrays, names=list(frame.columns))
    except Exception as error:
        if isinstance(error, CapabilityError):
            raise
        raise CapabilityError(
            "The Pandas columns cannot be represented faithfully in Arrow; "
            "declare compatible column_types or preprocess explicitly."
        ) from error
