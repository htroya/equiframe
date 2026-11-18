"""Explicit scalar ingestion; proposals never become approved contracts implicitly."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TextIO
from uuid import uuid4

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, NonNegativeInt, Text, _ExplicitOutcome
from equiframe._decimal import exact_decimal_context
from equiframe._document_io import write_document_chunks
from equiframe._error_reporting import report_failure
from equiframe._regular_io import local_input_path, local_output_directory, open_regular_file
from equiframe.contracts import (
    BooleanType,
    ColumnSpec,
    DateType,
    DecimalType,
    FloatType,
    IntegerType,
    StringType,
    TimestampPolicy,
)
from equiframe.errors import InvalidExecutionInput, ResourceLimitError
from equiframe.evidence import canonical_bytes, publish_json
from equiframe.local import LocalArtifactStore
from equiframe.migration.validation import decimal_limit, integer_bounds
from equiframe.tables import LoadedTable, check_arrow, read_table, require_dependency
from equiframe.types import ArtifactRef, Sha256
from equiframe.values import TimestampValue

if TYPE_CHECKING:
    from equiframe.execution import RunContext


class FieldMapping(FrozenModel):
    column: ColumnSpec
    path: tuple[Text, ...]
    scope: Literal["record", "root", "ancestor"] = "record"
    ancestor_levels: int = Field(default=1, ge=1)
    null_tokens: tuple[str, ...] = ()
    missing: Literal["reject", "null"] = "reject"
    decimal_separator: Literal[".", ","] = "."
    thousands_separator: Literal[",", ".", " "] | None = None
    date_format: Text | None = None
    true_tokens: tuple[str, ...] = ("true",)
    false_tokens: tuple[str, ...] = ("false",)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if not self.path or "*" in self.path:
            raise ValueError(
                "field paths are explicit nonempty object paths without array expansion"
            )
        if self.thousands_separator == self.decimal_separator:
            raise ValueError("decimal and thousands separators must differ")
        if set(self.true_tokens) & set(self.false_tokens):
            raise ValueError("boolean token sets must be disjoint")
        if (self.missing == "null" or self.null_tokens) and not self.column.nullable:
            raise ValueError("absence conversions require nullable columns")
        return self


class IngestionSpec(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    format: Literal["csv", "json", "jsonl"]
    fields: tuple[FieldMapping, ...]
    encoding: Text = "utf-8"
    delimiter: str = ","
    header: bool = True
    fieldnames: tuple[Text, ...] = ()
    records_path: tuple[Text, ...] = ()
    extra_fields: Literal["reject", "ignore"] = "reject"
    invalid_records: Literal["reject", "quarantine"] = "reject"
    max_source_bytes: int = Field(default=256 * 1024 * 1024, gt=0)
    max_records: int = Field(default=1_000_000, ge=0)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        names = tuple(field.column.name for field in self.fields)
        if not names or len(names) != len(set(names)):
            raise ValueError("ingestion fields must have unique nonempty output names")
        if len(self.delimiter) != 1:
            raise ValueError("CSV delimiter must be one character")
        if self.format == "csv":
            if self.records_path or any(
                f.scope != "record" or len(f.path) != 1 for f in self.fields
            ):
                raise ValueError("CSV requires direct record fields and no records_path")
            if not self.header and not self.fieldnames:
                raise ValueError("CSV without a header requires explicit fieldnames")
        return self


class SourceReceipt(FrozenModel):
    uri: Text
    preserved_uri: Text
    sha256: Sha256
    size_bytes: NonNegativeInt


class ConversionReceipt(FrozenModel):
    record: NonNegativeInt
    path: Text
    column: Text
    original_kind: Text
    original_text: str
    converted_text: str
    operation: Text


class QuarantinedRecord(FrozenModel):
    record: NonNegativeInt
    path: Text
    original_text: str
    code: Text


class IngestionResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .state and the accepted/quarantined counts explicitly"

    schema_version: Literal["1.0"] = "1.0"
    ingestion_id: Text
    spec: IngestionSpec
    source: SourceReceipt
    state: Literal["completed", "rejected", "quarantined"]
    inspected_records: NonNegativeInt
    accepted_records: NonNegativeInt
    quarantined: tuple[QuarantinedRecord, ...]
    conversions: tuple[ConversionReceipt, ...]
    output: ArtifactRef | None
    elapsed_seconds: float = Field(ge=0)
    extractor_version: Literal["equiframe-ingestion-1.0"] = "equiframe-ingestion-1.0"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.inspected_records != self.accepted_records + len(self.quarantined):
            raise ValueError("ingestion coverage counts differ")
        if (self.state == "rejected") != (self.output is None):
            raise ValueError("rejected ingestion cannot publish a partial accepted table")
        if self.state == "completed" and self.quarantined:
            raise ValueError("quarantine cannot be labelled complete ingestion")
        return self


_MISSING = object()


def _text(value: object) -> str:
    if value is _MISSING:
        return "<missing>"
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _path(value: object, parts: tuple[str, ...]) -> object:
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _records(
    value: object,
    parts: tuple[str, ...],
    ancestors: tuple[object, ...] = (),
    location: str = "$",
    *,
    max_records: int | None = None,
    check: Callable[[], None] | None = None,
) -> list[tuple[object, tuple[object, ...], str]]:
    result: list[tuple[object, tuple[object, ...], str]] = []

    def visit(
        current: object, remaining: tuple[str, ...], parents: tuple[object, ...], path: str
    ) -> None:
        if check:
            check()
        if not remaining:
            if isinstance(current, list):
                raise ValueError("array grain requires an explicit '*' in records_path")
            if max_records is not None and len(result) >= max_records:
                raise ResourceLimitError("expanded records exceed ingestion record budget")
            result.append((current, parents, path))
            return
        part, suffix = remaining[0], remaining[1:]
        if part == "*":
            if not isinstance(current, list):
                raise ValueError("records_path '*' requires an array")
            for index, child in enumerate(current):
                visit(child, suffix, (*parents, current), f"{path}[{index}]")
        else:
            child = _path(current, (part,))
            if child is _MISSING:
                raise ValueError("records_path field is absent")
            visit(child, suffix, (*parents, current), path + "." + part)

    visit(value, parts, ancestors, location)
    return result


def _arrow_type(field: FieldMapping) -> Any:
    import pyarrow as pa

    dtype = field.column.logical_type
    if isinstance(dtype, IntegerType):
        return getattr(pa, ("int" if dtype.signed else "uint") + str(dtype.bits))()
    if isinstance(dtype, DecimalType):
        return (pa.decimal128 if dtype.precision <= 38 else pa.decimal256)(
            dtype.precision, dtype.scale
        )
    if isinstance(dtype, StringType):
        return pa.string()
    if isinstance(dtype, BooleanType):
        return pa.bool_()
    if isinstance(dtype, FloatType):
        return pa.float32() if dtype.bits == 32 else pa.float64()
    if isinstance(dtype, DateType):
        return pa.date32()
    return pa.timestamp(dtype.unit, tz=dtype.timezone)


def _convert(value: object, field: FieldMapping) -> object:
    column, dtype = field.column, field.column.logical_type
    if value is _MISSING:
        if field.missing != "null":
            raise ValueError("missing_field")
        value = None
    if isinstance(value, str) and value in field.null_tokens:
        value = None
    if value is None:
        if not column.nullable:
            raise ValueError("forbidden_null")
        return None
    if isinstance(dtype, StringType):
        if not isinstance(value, str):
            raise ValueError("string_required_identifiers_are_not_coerced")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("invalid_unicode")
        return value
    if isinstance(dtype, BooleanType):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value in field.true_tokens:
            return True
        if isinstance(value, str) and value in field.false_tokens:
            return False
        raise ValueError("invalid_boolean")
    if isinstance(dtype, IntegerType):
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("integer_required")
        if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value) is None:
            raise ValueError("invalid_integer")
        integer_number = int(value)
        lower, upper = integer_bounds(dtype)
        if not lower <= integer_number <= upper:
            raise ValueError("integer_overflow")
        return integer_number
    if isinstance(dtype, DecimalType):
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            raise ValueError("exact_decimal_required")
        if isinstance(value, Decimal):
            # JSON numeric exponents must not expand to an unbounded plain string
            # before precision/range validation (e.g. a tiny 1e-999999999 token).
            with localcontext(exact_decimal_context()):
                if (
                    not value.is_finite()
                    or value.copy_abs() > decimal_limit(dtype)
                    or (value.is_zero() and value.is_signed())
                ):
                    raise ValueError("decimal_overflow_or_precision_loss")
                exact = value.quantize(Decimal(10) ** -dtype.scale)
                if exact != value:
                    raise ValueError("decimal_overflow_or_precision_loss")
                return exact
        text = str(value)
        separator = re.escape(field.decimal_separator)
        integer = r"[0-9]+"
        if field.thousands_separator:
            group = re.escape(field.thousands_separator)
            integer = rf"(?:[0-9]+|[0-9]{{1,3}}(?:{group}[0-9]{{3}})+)"
        if re.fullmatch(rf"[+-]?{integer}(?:{separator}[0-9]+)?", text) is None:
            raise ValueError("invalid_decimal")
        if field.thousands_separator:
            text = text.replace(field.thousands_separator, "")
        text = text.replace(field.decimal_separator, ".")
        with localcontext(exact_decimal_context()):
            decimal_number = Decimal(text)
            if (
                decimal_number.copy_abs() > decimal_limit(dtype)
                or decimal_number != decimal_number.quantize(Decimal(10) ** -dtype.scale)
                or (decimal_number.is_zero() and decimal_number.is_signed())
            ):
                raise ValueError("decimal_overflow_or_precision_loss")
            return decimal_number.quantize(Decimal(10) ** -dtype.scale)
    if isinstance(dtype, FloatType):
        if isinstance(value, bool) or not isinstance(value, (int, str, float, Decimal)):
            raise ValueError("float_required")
        float_number = float(value)
        if not math.isfinite(float_number):
            raise ValueError("nonfinite_float_requires_explicit_external_input")
        if dtype.bits == 32:
            import struct

            if struct.unpack("f", struct.pack("f", float_number))[0] != float_number:
                raise ValueError("float32_precision_loss")
        return float_number
    if not isinstance(value, str):
        raise ValueError("temporal_text_required")
    if isinstance(dtype, DateType):
        if field.date_format:
            from datetime import datetime

            return datetime.strptime(value, field.date_format).date()
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("ISO_date_required")
        return date.fromisoformat(value)
    stamp = TimestampValue(value=value, zone=dtype.timezone)
    if (dtype.timezone is None) != (not stamp.has_offset):
        raise ValueError("timestamp_zone_or_offset_mismatch")
    divisor = {"s": 10**9, "ms": 10**6, "us": 10**3, "ns": 1}[dtype.unit]
    epoch = TimestampValue(
        value="1970-01-01T00:00:00Z" if stamp.has_offset else "1970-01-01T00:00:00"
    )
    ticks = stamp.nanoseconds(instant=stamp.has_offset) - epoch.nanoseconds(
        instant=stamp.has_offset
    )
    if ticks % divisor:
        raise ValueError("timestamp_precision_loss")
    timestamp_ticks = ticks // divisor
    if not -(2**63) <= timestamp_ticks < 2**63:
        raise ValueError("timestamp_overflow")
    policy = column.temporal_policy
    if isinstance(policy, TimestampPolicy):
        policy._bound(stamp, "ingestion")
    return timestamp_ticks


def _json(text: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_field")
            result[key] = value
        return result

    def invalid(value: str) -> object:
        raise ValueError("nonfinite_json_number")

    def decimal_number(value: str) -> Decimal:
        # Decimal construction preserves the numeric token exactly, but rejects
        # exponents beyond its implementation range. Isolate even those errors
        # from the consumer's traps and flags, then apply the declared row policy.
        try:
            with localcontext(exact_decimal_context()):
                return Decimal(value)
        except InvalidOperation as error:
            raise ValueError("json_decimal_outside_supported_range") from error

    return json.loads(
        text, parse_float=decimal_number, object_pairs_hook=pairs, parse_constant=invalid
    )


def _jsonl_documents(source: TextIO) -> Iterator[str]:
    # Preserve the historical str.splitlines() boundaries, including Unicode
    # separators, without keeping all documents or a second decoded source copy.
    for physical_line in source:
        yield from physical_line.splitlines()


def _result_chunks(result: IngestionResult, *, context: RunContext | None) -> Iterator[bytes]:
    """Keep historical canonical JSON bytes without a second complete receipt graph."""
    sequences = {"conversions": result.conversions, "quarantined": result.quarantined}
    metadata = result.model_dump(mode="json", exclude=set(sequences))
    yield b"{"
    for index, name in enumerate(sorted((*metadata, *sequences))):
        if context:
            context.check()
        yield (b"," if index else b"") + canonical_bytes(name) + b":"
        if name not in sequences:
            yield canonical_bytes(metadata[name])
            continue
        yield b"["
        for item_index, item in enumerate(sequences[name]):
            if context and item_index % 4096 == 0:
                context.check()
            yield (b"," if item_index else b"") + canonical_bytes(item.model_dump(mode="json"))
        yield b"]"
    yield b"}\n"


def ingest_file(
    path: Path,
    *,
    spec: IngestionSpec,
    work_dir: Path,
    context: RunContext | None = None,
    batch_rows: int = 4096,
) -> IngestionResult:
    """Preserve original bytes and parse accepted values in bounded row batches.

    CSV/JSONL decode incrementally. JSON documents, per-document expansion and
    the public conversion/quarantine receipts still materialize; this is not a
    hard memory quota. A rejected file never publishes a partial accepted table.
    """
    if isinstance(batch_rows, bool) or not isinstance(batch_rows, int) or batch_rows <= 0:
        raise ValueError("batch_rows must be a positive integer")
    require_dependency("pyarrow", "arrow")
    import pyarrow as pa

    spec = IngestionSpec.model_validate(spec)
    start = time.perf_counter()
    directory = local_output_directory(work_dir) / ("ingestion_" + uuid4().hex)
    source_path = local_input_path(path)
    digest, size = hashlib.sha256(), 0
    preserved = directory / "source.original"
    with open_regular_file(source_path) as source_reader:
        directory.mkdir(parents=True, exist_ok=False)
        with preserved.open("xb") as source_writer:
            while block := source_reader.read(min(1024 * 1024, spec.max_source_bytes - size + 1)):
                if context:
                    context.check()
                size += len(block)
                if size > spec.max_source_bytes:
                    raise ResourceLimitError("source exceeds ingestion byte budget before parsing")
                digest.update(block)
                source_writer.write(block)
    receipt = SourceReceipt(
        uri=source_path.as_uri(),
        preserved_uri=preserved.as_uri(),
        sha256=digest.hexdigest(),
        size_bytes=size,
    )
    publish_json(receipt, directory / "source.json")
    values: dict[str, list[object]] = {f.column.name: [] for f in spec.fields}
    conversions: list[ConversionReceipt] = []
    quarantine: list[QuarantinedRecord] = []
    count = 0
    accepted = 0
    buffered = 0
    transport_bytes = 0
    schema = pa.schema([(f.column.name, _arrow_type(f)) for f in spec.fields])
    staging = directory / "accepted.arrow.part"
    writer: Any = None

    def flush() -> None:
        nonlocal buffered, transport_bytes
        if not buffered:
            return
        table = pa.Table.from_arrays(
            [
                pa.array(values[f.column.name], type=_arrow_type(f), from_pandas=False)
                for f in spec.fields
            ],
            schema=schema,
        )
        check_arrow(table)
        transport_bytes += table.nbytes
        if context:
            # Batch-local checks must not reset cumulative input budgets.
            context.check_table(table, output=False, enforce_rows=False)
            options = context.plan.options
            if options.max_input_rows is not None and accepted > options.max_input_rows:
                raise ResourceLimitError("materialized table exceeds row budget")
            if (
                options.max_transport_bytes is not None
                and transport_bytes > options.max_transport_bytes
            ):
                raise ResourceLimitError("materialized table exceeds Arrow buffer byte budget")
        writer.write_table(table)
        for column_values in values.values():
            column_values.clear()
        buffered = 0

    def accept(
        raw: object,
        root: object,
        ancestors: tuple[object, ...],
        location: str,
        *,
        has_extra_fields: bool = False,
        diagnostic: object = _MISSING,
    ) -> bool:
        nonlocal count, accepted, buffered
        if context:
            context.check()
        if count >= spec.max_records:
            raise ResourceLimitError("expanded records exceed ingestion record budget")
        index = count
        count += 1
        converted = {}
        pending = []
        try:
            if not isinstance(raw, dict):
                raise ValueError("record_object_required")
            if spec.extra_fields == "reject":
                permitted = {f.path[0] for f in spec.fields if f.scope == "record"}
                if has_extra_fields or set(raw) - permitted:
                    raise ValueError("new_or_extra_field")
            for field in spec.fields:
                scope = raw if field.scope == "record" else root
                if field.scope == "ancestor":
                    if len(ancestors) < field.ancestor_levels:
                        raise ValueError("ancestor_scope_unavailable")
                    scope = ancestors[-field.ancestor_levels]
                original = _path(scope, field.path)
                converted[field.column.name] = _convert(original, field)
                pending.append(
                    ConversionReceipt(
                        record=index,
                        path=location,
                        column=field.column.name,
                        original_kind="missing"
                        if original is _MISSING
                        else type(original).__name__,
                        original_text=_text(original),
                        converted_text=_text(converted[field.column.name]),
                        operation="declared_scalar_parse",
                    )
                )
        except (ValueError, TypeError, OverflowError) as error:
            quarantine.append(
                QuarantinedRecord(
                    record=index,
                    path=location,
                    original_text=_text(raw if diagnostic is _MISSING else diagnostic),
                    code=str(error),
                )
            )
            return spec.invalid_records == "quarantine"
        conversions.extend(pending)
        for name, value in converted.items():
            values[name].append(value)
        accepted += 1
        buffered += 1
        if buffered >= batch_rows:
            flush()
        return True

    rejected = False
    output = None
    try:
        with ExitStack() as stack:
            try:
                source = stack.enter_context(preserved.open(encoding=spec.encoding))
                if spec.format != "json":
                    # A malformed encoding historically rejected the whole source
                    # before accepting any rows. Keep that contract with a bounded
                    # validation pass, then parse the same preserved bytes.
                    while source.read(64 * 1024):
                        if context:
                            context.check()
                    source.seek(0)
                sink = stack.enter_context(pa.OSFile(str(staging), "wb"))
                writer = stack.enter_context(pa.ipc.new_file(sink, schema))
                if spec.format == "csv":
                    reader = csv.DictReader(
                        source,
                        delimiter=spec.delimiter,
                        fieldnames=None if spec.header else list(spec.fieldnames),
                        strict=True,
                    )
                    names = reader.fieldnames or []
                    if len(names) != len(set(names)) or any(not name for name in names):
                        raise ValueError("invalid_or_duplicate_csv_header")
                    required = {field.path[0] for field in spec.fields if field.missing == "reject"}
                    if required - set(names):
                        raise ValueError("missing_csv_header_field")
                    permitted = {field.path[0] for field in spec.fields}
                    if spec.extra_fields == "reject" and set(names) - permitted:
                        raise ValueError("new_or_extra_csv_header_field")
                    for csv_record in reader:
                        surplus = csv_record.pop(None, _MISSING)
                        diagnostic = _MISSING
                        if surplus is not _MISSING:
                            # Separate conversion values from diagnostic labels.
                            # Retain legacy text where its labels cannot collide;
                            # otherwise put real fields in their own namespace.
                            if {"null", "<surplus_fields>"} & (set(csv_record) | permitted):
                                diagnostic = {"fields": dict(csv_record), "surplus_fields": surplus}
                            else:
                                diagnostic = {
                                    **csv_record,
                                    None: surplus,
                                    "<surplus_fields>": surplus,
                                }
                        csv_record = {
                            name: value for name, value in csv_record.items() if value is not None
                        }
                        if not accept(
                            csv_record,
                            csv_record,
                            (),
                            f"$[{count}]",
                            has_extra_fields=surplus is not _MISSING,
                            diagnostic=diagnostic,
                        ):
                            rejected = True
                            break
                else:
                    text = source.read() if spec.format == "json" else ""
                    if spec.format == "json" and not text.strip():
                        raise ValueError("empty_json_document")
                    documents = _jsonl_documents(source) if spec.format == "jsonl" else iter([text])
                    for line_number, document in enumerate(documents, 1):
                        if not document.strip():
                            if spec.format == "jsonl" and not accept(
                                None, None, (), f"line:{line_number}"
                            ):
                                rejected = True
                                break
                            continue
                        try:
                            root = _json(document)
                            records = _records(
                                root,
                                spec.records_path,
                                max_records=spec.max_records - count,
                                check=context.check if context else None,
                            )
                        except ValueError as error:
                            if count >= spec.max_records:
                                raise ResourceLimitError(
                                    "records exceed ingestion record budget"
                                ) from error
                            quarantine.append(
                                QuarantinedRecord(
                                    record=count,
                                    path=f"line:{line_number}",
                                    original_text=document,
                                    code=str(error),
                                )
                            )
                            count += 1
                            if spec.invalid_records == "reject":
                                rejected = True
                                break
                            continue
                        for raw, ancestors, location in records:
                            if not accept(raw, root, ancestors, f"line:{line_number}" + location):
                                rejected = True
                                break
                        if rejected:
                            break
            except (UnicodeError, csv.Error, ValueError) as error:
                if count >= spec.max_records:
                    raise ResourceLimitError("records exceed ingestion record budget") from error
                source_code = (
                    "UnicodeDecodeError:invalid_source_encoding"
                    if isinstance(error, UnicodeDecodeError)
                    else "Error:unexpected end of data"
                    if type(error) is csv.Error
                    and len(error.args) == 1
                    and type(error.args[0]) is str
                    and error.args[0] == "unexpected end of data"
                    else "Error:invalid_csv_source"
                    if isinstance(error, csv.Error)
                    else "ValueError:empty_json_document"
                    if type(error) is ValueError
                    and len(error.args) == 1
                    and type(error.args[0]) is str
                    and error.args[0] == "empty_json_document"
                    else "invalid_ingestion_source"
                )
                quarantine.append(
                    QuarantinedRecord(
                        record=count,
                        path="$",
                        original_text="",
                        code=report_failure(error, source_code),
                    )
                )
                count += 1
                rejected = True
            if not rejected:
                flush()
                if context:
                    context.check()
        if not rejected:
            target = directory / "accepted.arrow"
            staging.rename(target)
            output = LocalArtifactStore(directory / "artifacts").put(
                target, media_type="application/vnd.apache.arrow.file"
            )
    finally:
        staging.unlink(missing_ok=True)
    result = IngestionResult(
        ingestion_id=directory.name,
        spec=spec,
        source=receipt,
        state="rejected" if rejected else ("quarantined" if quarantine else "completed"),
        inspected_records=count,
        accepted_records=accepted,
        quarantined=tuple(quarantine),
        conversions=tuple(conversions),
        output=output,
        elapsed_seconds=time.perf_counter() - start,
    )
    write_document_chunks(directory / "ingestion.json", _result_chunks(result, context=context))
    return result


@dataclass(frozen=True)
class FileInput:
    path: Path
    spec: IngestionSpec
    batch_rows: int = 4096

    def load(self, context: RunContext) -> LoadedTable:
        result = ingest_file(
            self.path,
            spec=self.spec,
            work_dir=context.directory,
            context=context,
            batch_rows=self.batch_rows,
        )
        if result.state != "completed" or result.output is None:
            raise InvalidExecutionInput(
                "ingestion rejected/quarantined records; inspect ingestion receipt"
            )
        return LoadedTable(
            read_table(result.output),
            origin=result.output,
            notes=(
                "Source original SHA-256=" + result.source.sha256,
                "Explicit ingestion specification and conversion receipts retained.",
            ),
        )
