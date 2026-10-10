"""Explicit bounded inputs for trusted byte streams and read-only SQLite queries."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO
from uuid import uuid4

from pydantic import TypeAdapter

from equiframe._base import Identifier
from equiframe.contracts import DecimalType
from equiframe.errors import (
    ArtifactIntegrityError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    ResourceLimitError,
)
from equiframe.ingestion import FileInput, IngestionSpec
from equiframe.types import Sha256

if TYPE_CHECKING:
    import pyarrow as pa

    from equiframe.execution import RunContext
    from equiframe.ports import DataSource
    from equiframe.tables import LoadedTable


class CompositeDataSource:
    """Bind logical names to explicitly injected providers and their table names.

    Composition does not create cross-provider transaction/snapshot consistency.
    Providers own their immutable identity and must return faithful LoadedTables.
    """

    def __init__(self, bindings: Mapping[str, tuple[DataSource, str]]) -> None:
        self._bindings = dict(bindings)
        for name, (provider, table) in self._bindings.items():
            TypeAdapter(Identifier).validate_python(name, strict=True)
            if table not in provider.table_names:
                raise InvalidExecutionInput("bound provider table is unavailable")

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._bindings)

    def resolve(self, name: str, *, context: RunContext) -> LoadedTable:
        from equiframe.tables import check_arrow

        context.check()
        try:
            provider, table = self._bindings[name]
        except KeyError:
            raise InvalidExecutionInput("composite input table is unavailable: " + name) from None
        if table not in provider.table_names:
            raise InvalidExecutionInput("bound provider table is no longer available")
        loaded = provider.resolve(table, context=context)
        check_arrow(loaded.table)
        context.check_table(loaded.table, output=False)
        return loaded


@dataclass(frozen=True)
class RecordBatchInput:
    """Consume caller-owned Arrow batches without inference or silent casts.

    Batch schemas, including metadata, must match the explicit schema exactly.
    Cumulative rows/buffer bytes are checked before final table materialization.
    This bounds admitted data cooperatively, not process RSS or blocked I/O.
    """

    open_batches: Callable[[], AbstractContextManager[Iterable[pa.RecordBatch]]]
    schema: pa.Schema

    def load(self, context: RunContext) -> LoadedTable:
        from equiframe.tables import LoadedTable, check_arrow, require_dependency

        require_dependency("pyarrow", "arrow")
        import pyarrow as pa

        if not isinstance(self.schema, pa.Schema):
            raise InvalidExecutionInput("record batches require an explicit Arrow schema")
        check_arrow(pa.Table.from_batches([], schema=self.schema))
        batches: list[pa.RecordBatch] = []
        rows = size = 0
        context.check()
        with self.open_batches() as reader:
            for batch in reader:
                context.check()
                if not isinstance(batch, pa.RecordBatch) or not batch.schema.equals(
                    self.schema, check_metadata=True
                ):
                    raise InvalidExecutionInput("record batch schema differs from declared schema")
                check_arrow(pa.Table.from_batches([batch]))
                if any(
                    not field.nullable and batch.column(index).null_count
                    for index, field in enumerate(self.schema)
                ):
                    raise InvalidExecutionInput("record batch violates nonnullable field")
                rows += batch.num_rows
                size += batch.nbytes
                options = context.plan.options
                if options.max_input_rows is not None and rows > options.max_input_rows:
                    raise ResourceLimitError("record batches exceed cumulative row budget")
                if options.max_transport_bytes is not None and size > options.max_transport_bytes:
                    raise ResourceLimitError("record batches exceed cumulative Arrow byte budget")
                batches.append(batch)
        table = pa.Table.from_batches(batches, schema=self.schema)
        context.check_table(table, output=False)
        return LoadedTable(table, notes=("explicit_schema_record_batches",))


@dataclass(frozen=True)
class StreamInput:
    """Use a caller-owned API/file response; the caller owns authentication and timeouts.

    No URL is opened implicitly. The context manager closes the stream on every
    outcome. Reads, parsing and transport have cooperative, explicit budgets.
    The original response and conversion receipts are retained by ingestion.
    """

    open_stream: Callable[[], AbstractContextManager[BinaryIO]]
    spec: IngestionSpec
    expected_sha256: str | None = None
    batch_rows: int = 4096

    def load(self, context: RunContext) -> LoadedTable:
        spec = IngestionSpec.model_validate(self.spec)
        expected = (
            TypeAdapter(Sha256).validate_python(self.expected_sha256, strict=True)
            if self.expected_sha256 is not None
            else None
        )
        path = context.directory / ("response_" + uuid4().hex + "." + spec.format)
        digest = hashlib.sha256()
        size = 0
        try:
            context.check()
            with self.open_stream() as source, path.open("xb") as target:
                while True:
                    context.check()
                    block = source.read(64 * 1024)
                    if not isinstance(block, bytes) or len(block) > 64 * 1024:
                        raise InvalidExecutionInput("stream must honor bounded binary reads")
                    if not block:
                        break
                    size += len(block)
                    if size > spec.max_source_bytes:
                        raise ResourceLimitError("response exceeds ingestion byte budget")
                    digest.update(block)
                    target.write(block)
            if expected is not None and digest.hexdigest() != expected:
                raise ArtifactIntegrityError("response differs from the declared SHA-256")
            return FileInput(path, spec, self.batch_rows).load(context)
        finally:
            path.unlink(missing_ok=True)


@dataclass(frozen=True)
class SQLiteInput:
    """Read a trusted parameterized query in one owned read-only transaction.

    Explicit JSONL field mappings preserve textual identifiers and Decimal TEXT.
    SQLite REAL is rejected for Decimal: a binary float cannot recover the
    original amount. This local input neither manages a shared DW nor promises
    another SQL provider's isolation or type mappings.
    """

    path: Path
    query: str
    spec: IngestionSpec
    parameters: tuple[str | int | float | bytes | None, ...] = ()
    batch_rows: int = 4096

    def load(self, context: RunContext) -> LoadedTable:
        spec = IngestionSpec.model_validate(self.spec)
        if (
            spec.format != "jsonl"
            or spec.records_path
            or any(field.scope != "record" or len(field.path) != 1 for field in spec.fields)
        ):
            raise InvalidExecutionInput("SQLite requires direct JSONL record field mappings")
        if not re.match(r"\s*(SELECT|WITH)\b", self.query, re.IGNORECASE):
            raise InvalidExecutionInput("SQLite input requires one trusted SELECT/WITH query")
        if (
            isinstance(self.batch_rows, bool)
            or not isinstance(self.batch_rows, int)
            or self.batch_rows <= 0
        ):
            raise ValueError("batch_rows must be a positive integer")
        path = self.path.resolve()
        if not path.is_file():
            raise InvalidExecutionInput("SQLite input must name an existing local database")
        target = context.directory / ("sqlite_" + uuid4().hex + ".jsonl")
        context.check()
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        decimal_fields = {
            field.path[0]
            for field in spec.fields
            if isinstance(field.column.logical_type, DecimalType)
        }
        records = size = 0
        interruption: ExecutionCancelled | ExecutionTimeout | None = None

        def progress() -> int:
            nonlocal interruption
            try:
                context.check()
            except (ExecutionCancelled, ExecutionTimeout) as error:
                interruption = error
                return 1
            return 0

        try:
            connection.set_progress_handler(progress, 1000)
            # Some Python builds omit extension-loading support entirely.
            # Fresh SQLite connections keep it disabled; never require that API.
            if hasattr(connection, "enable_load_extension"):
                connection.enable_load_extension(False)
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
            cursor = connection.execute(self.query, self.parameters)
            names = tuple(item[0] for item in cursor.description or ())
            if not names or any(not name for name in names) or len(names) != len(set(names)):
                raise InvalidExecutionInput("SQLite query columns must be unique and nonempty")
            with target.open("xb") as output:
                while True:
                    context.check()
                    batch = cursor.fetchmany(self.batch_rows)
                    if not batch:
                        break
                    for row in batch:
                        context.check()
                        records += 1
                        maximum = context.plan.options.max_input_rows
                        if records > spec.max_records or (
                            maximum is not None and records > maximum
                        ):
                            raise ResourceLimitError("SQLite query exceeds input row budget")
                        record = dict(zip(names, row, strict=True))
                        if any(
                            record.get(name) is not None and type(record[name]) is not str
                            for name in decimal_fields
                        ):
                            raise InvalidExecutionInput(
                                "SQLite Decimal requires exact TEXT, never REAL"
                            )
                        if any(isinstance(value, bytes) for value in row):
                            raise InvalidExecutionInput(
                                "SQLite BLOB has no declared scalar JSON mapping"
                            )
                        try:
                            raw = (
                                json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
                            ).encode("utf-8")
                        except (ValueError, TypeError) as error:
                            raise InvalidExecutionInput(
                                "SQLite returned an unsupported scalar"
                            ) from error
                        size += len(raw)
                        if size > spec.max_source_bytes:
                            raise ResourceLimitError(
                                "SQLite response exceeds ingestion byte budget"
                            )
                        output.write(raw)
            loaded = FileInput(target, spec, self.batch_rows).load(context)
            return loaded
        except sqlite3.OperationalError:
            if interruption is not None:
                raise interruption from None
            raise
        finally:
            connection.close()
            target.unlink(missing_ok=True)
