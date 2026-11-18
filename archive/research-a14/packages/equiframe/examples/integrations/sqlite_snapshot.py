"""Small trusted SQLite producer for EquiFrame's existing SnapshotClient port.

This external example is deliberately not an equiframe module, general DB-API
adapter, remote data service or SQL sandbox. See docs/sqlite-snapshots.md.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote
from uuid import uuid4

import pyarrow as pa

import equiframe as ef


@dataclass(frozen=True)
class SQLiteQuery:
    """Trusted SELECT/WITH and its independently declared output Arrow schema.

    Positional parameters are bound by SQLite, never interpolated. Only int64,
    string and decimal128 with nonnegative scale are supported by this example.
    Decimal input must be exact decimal TEXT, never SQLite REAL or NUMERIC.
    """

    name: str
    sql: str
    schema: pa.Schema
    parameters: tuple[str | int | float | bytes | None, ...] = ()


@dataclass(frozen=True)
class SQLiteSnapshotClient:
    """Detached immutable bytes; no live connection or database re-query on fetch."""

    manifest: ef.SnapshotManifest
    _payloads: Mapping[str, bytes]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_payloads", MappingProxyType(dict(self._payloads)))

    def get_snapshot(self, snapshot_id: str) -> ef.SnapshotManifest:
        if snapshot_id != self.manifest.snapshot_id:
            raise LookupError("unknown snapshot identity; request the captured ID")
        return self.manifest

    def download_artifact(self, ref: ef.ArtifactRef, destination: Path) -> None:
        if not any(table.artifact == ref for table in self.manifest.tables):
            raise LookupError("artifact is not part of this captured snapshot")
        # The URI is an identifier, not a network location this client visits.
        with destination.open("xb") as stream:
            stream.write(self._payloads[ref.uri])


def _logical_type(data_type: pa.DataType) -> ef.LogicalType:
    if pa.types.is_int64(data_type):
        return ef.IntegerType(bits=64, signed=True)
    if pa.types.is_string(data_type):
        return ef.StringType()
    if pa.types.is_decimal128(data_type) and 0 <= data_type.scale <= data_type.precision:
        return ef.DecimalType(precision=data_type.precision, scale=data_type.scale)
    raise ValueError("SQLite example supports only int64, string and decimal128(p, 0..p)")


def _decode(value: object, field: pa.Field) -> object:
    if value is None:
        if not field.nullable:
            raise ValueError("SQLite returned NULL for a nonnullable declared field")
        return None
    if pa.types.is_int64(field.type):
        if type(value) is not int:
            raise ValueError("declared int64 requires SQLite INTEGER; no implicit cast")
        return value
    if pa.types.is_string(field.type):
        if type(value) is not str:
            raise ValueError("declared string requires SQLite TEXT; no implicit cast")
        return value
    if type(value) is not str or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None:
        raise ValueError("declared decimal requires plain exact decimal TEXT, never REAL")
    result = Decimal(value)
    if result.is_zero() and result.is_signed():
        raise ValueError("Arrow decimal cannot preserve negative zero; revise the source schema")
    # pa.array(..., safe=True) below rejects overflow and any nonzero digits
    # beyond the declared scale. No float intermediary or rounding is used.
    return result


def _read_query(
    connection: sqlite3.Connection,
    query: SQLiteQuery,
    *,
    max_rows_per_table: int,
    batch_rows: int,
) -> pa.Table:
    cursor = connection.cursor()
    try:
        cursor.execute(query.sql, query.parameters)
        if cursor.description is None or tuple(item[0] for item in cursor.description) != tuple(
            query.schema.names
        ):
            raise ValueError("query names/order differ from the declared Arrow schema")
        batches = []
        count = 0
        while rows := cursor.fetchmany(batch_rows):
            count += len(rows)
            if count > max_rows_per_table:
                raise ef.ResourceLimitError("SQLite capture exceeds its per-table row budget")
            arrays = [
                pa.array([_decode(row[index], field) for row in rows], type=field.type, safe=True)
                for index, field in enumerate(query.schema)
            ]
            batches.append(pa.RecordBatch.from_arrays(arrays, schema=query.schema))
        if not connection.in_transaction:
            raise RuntimeError("the native SQLite read transaction ended before capture finished")
        return pa.Table.from_batches(batches, schema=query.schema)
    finally:
        cursor.close()


def capture_sqlite_snapshot(
    database: Path,
    *,
    snapshot_id: str,
    queries: tuple[SQLiteQuery, ...],
    domain_schema_revision: str,
    extraction_revision: str,
    provenance: tuple[str, ...],
    max_rows_per_table: int = 10_000,
    max_payload_bytes: int = 16 * 1024 * 1024,
    batch_rows: int = 256,
    lock_timeout_seconds: float = 5.0,
) -> SQLiteSnapshotClient:
    """Capture every query in one owned read transaction; publish only on success.

    The database must already exist. No caller connection is borrowed, committed
    or closed. The snapshot is anchored by the first native read, shared across
    queries, then detached. All cursors and the connection close on every path.
    Budget checks are cooperative, not hard memory, query-time or process limits.
    """
    for value in (max_rows_per_table, max_payload_bytes, batch_rows):
        if type(value) is not int or value <= 0:
            raise ValueError("capture budgets and batch_rows must be positive integers")
    if (
        type(lock_timeout_seconds) not in (int, float)
        or not math.isfinite(lock_timeout_seconds)
        or lock_timeout_seconds < 0
    ):
        raise ValueError("lock_timeout_seconds must be finite and nonnegative")
    if not queries or len({query.name for query in queries}) != len(queries):
        raise ValueError("capture requires nonempty queries with unique table names")
    declarations = []
    # Validate the complete declaration before opening a connection or doing SQL.
    for query in queries:
        if re.match(r"\s*(?:SELECT|WITH)\b", query.sql, re.IGNORECASE) is None:
            raise ValueError("provide one trusted SELECT/WITH query per table")
        if not query.schema.names or len(set(query.schema.names)) != len(query.schema.names):
            raise ValueError("each Arrow schema requires unique nonempty column names")
        if query.schema.metadata is not None or any(field.metadata for field in query.schema):
            raise ValueError("this example does not interpret Arrow schema/field metadata")
        declarations.append(
            tuple(
                ef.SnapshotColumn(
                    name=field.name,
                    physical_type=str(field.type),
                    logical_type=_logical_type(field.type),
                    nullable=field.nullable,
                )
                for field in query.schema
            )
        )
    # An opaque per-capture namespace avoids identifying two captures as the same
    # artifact when their human labels are reused. It is not authentication.
    namespace = uuid4().hex
    refs = tuple(
        ef.ArtifactRef(
            schema_version="1.0",
            uri=f"https://example.invalid/sqlite/{namespace}/{quote(query.name, safe='')}.arrow",
            sha256="0" * 64,
            format="arrow",
            media_type="application/vnd.apache.arrow.file",
            size_bytes=0,
        )
        for query in queries
    )
    declaration = ef.SnapshotManifest(
        snapshot_id=snapshot_id,
        domain_schema_revision=domain_schema_revision,
        extraction_revision=extraction_revision,
        provenance=provenance,
        tables=tuple(
            ef.SnapshotTable(name=query.name, artifact=ref, row_count=0, columns=columns)
            for query, ref, columns in zip(queries, refs, declarations, strict=True)
        ),
    )
    payloads: dict[str, bytes] = {}
    tables = []
    total_bytes = 0
    # URI mode=ro refuses a missing database rather than creating an empty one.
    connection = sqlite3.connect(
        database.resolve().as_uri() + "?mode=ro",
        uri=True,
        isolation_level=None,
        timeout=lock_timeout_seconds,
    )
    try:
        connection.execute("BEGIN").close()
        for query, table_declaration in zip(queries, declaration.tables, strict=True):
            table = _read_query(
                connection, query, max_rows_per_table=max_rows_per_table, batch_rows=batch_rows
            )
            sink = pa.BufferOutputStream()
            with pa.ipc.new_file(sink, table.schema) as writer:
                writer.write_table(table)
            payload = sink.getvalue().to_pybytes()
            total_bytes += len(payload)
            if total_bytes > max_payload_bytes:
                raise ef.ResourceLimitError(
                    "SQLite capture exceeds its total serialized-byte budget"
                )
            ref = table_declaration.artifact.model_copy(
                update={"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
            )
            tables.append(
                table_declaration.model_copy(update={"artifact": ref, "row_count": len(table)})
            )
            payloads[ref.uri] = payload
    finally:
        try:
            if connection.in_transaction:
                connection.rollback()
        finally:
            connection.close()
    # No manifest/client is exposed until ALL tables succeeded and SQLite closed.
    manifest = ef.SnapshotManifest.model_validate(
        {**declaration.model_dump(), "tables": tuple(tables)}
    )
    return SQLiteSnapshotClient(manifest, payloads)
