"""Explicit, single-consumption DuckDB capture into a detached Arrow artifact.

This is a trusted-query boundary, not a SQL sandbox or a distributed snapshot.
The comparison kernel neither owns a connection nor executes this query again.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import weakref
from collections.abc import Callable, Mapping
from datetime import datetime
from datetime import timezone as _timezone
from importlib.metadata import version
from pathlib import Path
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from pydantic import Field, TypeAdapter

from equiframe._base import FrozenModel, NonNegativeInt, PositiveInt, Text
from equiframe._comparison_io import file_ref
from equiframe._duckdb_transport import (
    duckdb_arrow_schema,
    duckdb_parameters,
    verify_duckdb_table,
)
from equiframe._regular_io import local_output_directory
from equiframe.errors import (
    CapabilityError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    NativeEngineError,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken
from equiframe.execution_types import PhysicalColumn, TableArtifact
from equiframe.tables import require_dependency

UTC = _timezone.utc

if TYPE_CHECKING:
    import duckdb
    import pyarrow as pa


class DuckDBCaptureOptions(FrozenModel):
    """Cooperative capture limits; not an engine or whole-process RSS quota.

    Limits apply to rows, each Arrow batch and the final serialized IPC file.
    A native fetch/allocation can exceed a limit before the next checkpoint.
    Borrowed sessions keep their own memory/thread/spill/timezone settings.
    """

    batch_rows: PositiveInt = 4096
    max_rows: NonNegativeInt = 1_000_000
    max_batch_bytes: PositiveInt = 64 * 1024 * 1024
    max_bytes: PositiveInt = 256 * 1024 * 1024
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None


# Locks coordinate only captures through this module, never unrelated caller SQL.
# Weak keys do not retain a caller's connection after capture has returned.
_LOCKS: weakref.WeakKeyDictionary[object, Lock] = weakref.WeakKeyDictionary()
_LOCKS_GUARD = Lock()
_SETTINGS = (
    "TimeZone",
    "threads",
    "default_collation",
    "default_order",
    "default_null_order",
    "preserve_insertion_order",
    "memory_limit",
    "max_temp_directory_size",
    "enable_external_access",
    "autoinstall_known_extensions",
    "autoload_known_extensions",
)


def _parameters(parameters: Mapping[str, object] | None) -> dict[str, object]:
    values = dict(parameters) if parameters is not None else {}
    for name in values:
        if type(name) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) is None:
            raise InvalidExecutionInput("capture parameters require ASCII identifier names")
    return values


def capture_duckdb(
    sql: str,
    *,
    work_dir: Path,
    name: str = "result",
    connection: duckdb.DuckDBPyConnection | None = None,
    exclusive_connection: bool = False,
    parameters: Mapping[str, object] | None = None,
    options: DuckDBCaptureOptions | None = None,
    cancellation: CancellationToken | None = None,
) -> TableArtifact:
    """Execute one trusted SELECT/WITH and persist a reusable, complete snapshot.

    A borrowed connection requires ``exclusive_connection=True``: the caller
    promises no outstanding result/reader, concurrent SQL or mutable external
    source changes during capture. The API may interrupt that connection and
    consumes its current result slot. It never closes it, commits/rolls back,
    changes session settings, or creates/removes registered tables. A query
    error can abort the caller's transaction; recovery belongs to the caller.

    Without a connection, create/close a private in-memory session: UTC, one
    thread, 512MB engine-managed memory, no spill, external access, extension
    autoload/install or Python replacement scans. No global DuckDB connection.
    Borrowed SQL has the caller's capabilities, including external effects:
    SELECT and bound parameters do not make untrusted SQL safe. Borrowed sessions
    must already disable extension autoinstall and autoload; capture will reject
    rather than change those settings for the caller.

    Raw relations, already-executed results and readers are intentionally not
    accepted: ownership, previous consumption and pre-Arrow types are unknown.
    The new reader is consumed once, closed, and never escapes this call. No
    pandas conversion, schema inference, output casts or SQL replay occurs.
    Decimal parameters are explicitly typed from exact text to avoid native
    inference falling back to float; precision and scale are retained.

    Returns an existing TableArtifact accepted by compare/diff with an explicit
    contract whose output name matches ``name``. The new capture directory has
    snapshot.arrow and capture.json (the returned TableArtifact); only complete
    captures are published. Exceptions leave no success artifact. Callers own
    retention; capture contains their data. Notes record fixed safe session
    settings and a capture interval, not SQL/parameters or a source-version
    attestation. A snapshot freezes captured bytes, not external systems.
    """
    if type(sql) is not str or not sql.strip():
        raise InvalidExecutionInput("capture requires a nonempty trusted SQL string")
    checked = DuckDBCaptureOptions.model_validate(
        DuckDBCaptureOptions() if options is None else options
    )
    name = TypeAdapter(Text).validate_python(name)
    if type(exclusive_connection) is not bool:
        raise InvalidExecutionInput("exclusive_connection must be a boolean")
    if connection is not None and not exclusive_connection:
        raise InvalidExecutionInput(
            "borrowed capture requires exclusive_connection=True and no outstanding reader"
        )
    work_dir = local_output_directory(work_dir)
    values = _parameters(parameters)
    signal = cancellation if cancellation is not None else CancellationToken()
    started = datetime.now(UTC).isoformat()
    tick = time.monotonic()

    def check() -> None:
        if signal.cancelled:
            raise ExecutionCancelled("DuckDB capture cancelled; no complete snapshot published")
        if (
            checked.timeout_seconds is not None
            and time.monotonic() - tick >= checked.timeout_seconds
        ):
            raise ExecutionTimeout("DuckDB capture timed out; no complete snapshot published")

    check()
    require_dependency("duckdb", "duckdb")
    require_dependency("pyarrow", "duckdb")
    import duckdb

    values = duckdb_parameters(values)
    owned = connection is None
    if connection is not None and type(connection) is not duckdb.DuckDBPyConnection:
        raise InvalidExecutionInput("capture requires an explicit DuckDBPyConnection")
    session = connection
    lock: Lock | None = None
    stopped = Event()
    watcher: Thread | None = None
    relation: duckdb.DuckDBPyRelation | None = None
    reader: pa.RecordBatchReader | None = None
    try:
        if session is None:
            session = duckdb.connect(
                ":memory:",
                config={
                    "threads": 1,
                    "memory_limit": "512MB",
                    "max_temp_directory_size": "0B",
                    "enable_external_access": False,
                    "autoinstall_known_extensions": False,
                    "autoload_known_extensions": False,
                    "python_enable_replacements": False,
                },
            )
            session.execute("SET TimeZone = 'UTC'")
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(session, Lock())
        if not lock.acquire(blocking=False):
            lock = None
            raise InvalidExecutionInput("this connection already has an active DuckDB capture")
        check()

        def watch() -> None:
            if not (session is not None):
                raise AssertionError("Internal invariant check failed.")
            while not stopped.wait(0.01):
                if signal.cancelled or (
                    checked.timeout_seconds is not None
                    and time.monotonic() - tick >= checked.timeout_seconds
                ):
                    # Repeat until stopped to cover the race with starting native execution.
                    session.interrupt()

        watcher = Thread(target=watch, name="equiframe-duckdb-capture", daemon=False)
        watcher.start()
        statements = session.extract_statements(sql)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise InvalidExecutionInput("DuckDB capture accepts exactly one SELECT/WITH query")
        if set(statements[0].named_parameters) != set(values):
            raise InvalidExecutionInput("SQL parameters must match capture parameter names exactly")
        settings_query = "SELECT " + ", ".join(f"current_setting('{key}')" for key in _SETTINGS)
        row = session.execute(settings_query).fetchone()
        if row is None:
            raise NativeEngineError("DuckDB did not return the required session description")
        settings = dict(zip(_SETTINGS, row, strict=True))
        if settings["autoinstall_known_extensions"] or settings["autoload_known_extensions"]:
            raise CapabilityError(
                "DuckDB capture requires extension autoinstall/autoload already disabled; "
                "configure your own connection explicitly before capture"
            )
        timezone = str(settings["TimeZone"])
        # DuckDB can execute/materialize parameterized SQL here, before Arrow
        # batch limits apply. Unparameterized binding can also evaluate constants.
        relation = session.sql(sql, params=values or None)
        native_types = tuple(zip(relation.columns, map(str, relation.types), strict=True))
        schema = duckdb_arrow_schema(native_types, timezone)
        check()
        reader = relation.to_arrow_reader(checked.batch_rows)
        if not reader.schema.equals(schema, check_metadata=True):
            raise CapabilityError("DuckDB reader schema differs from its admitted native types")
        work_dir.mkdir(parents=True, exist_ok=True)
        final = work_dir / ("duckdb-" + uuid4().hex)
        with tempfile.TemporaryDirectory(prefix=".duckdb-capture-", dir=work_dir) as temporary:
            stage = Path(temporary)
            path = stage / "snapshot.arrow"
            rows, nulls, nans = _write_reader(reader, path, native_types, timezone, checked, check)
            check()
            data = file_ref(path, "arrow", check=check).model_copy(
                update={"uri": (final / path.name).as_uri()}
            )
            artifact = TableArtifact(
                name=name,
                data=data,
                row_count=rows,
                columns=tuple(
                    PhysicalColumn(
                        name=column,
                        engine_type=dtype,
                        arrow_type=str(schema.field(i).type),
                        null_count=nulls[i],
                        nan_count=nans[i],
                    )
                    for i, (column, dtype) in enumerate(native_types)
                ),
                notes=(
                    "DuckDB explicit capture: one query/result consumption; detached Arrow IPC.",
                    "Observed values/types only; original source nullability, collations, "
                    "per-value timezone labels and distinctions already lost are not inferred.",
                    "Observed order retained; reproducibility needs an explicitly total SQL order.",
                    "Capture interval is not a coordinated or externally attested source snapshot.",
                    "DuckDB capture context v1: "
                    + json.dumps(
                        {
                            "started_at": started,
                            "finished_at": datetime.now(UTC).isoformat(),
                            "connection_owner": "equiframe" if owned else "caller",
                            "session": settings,
                            "versions": {
                                "duckdb": version("duckdb"),
                                "pyarrow": version("pyarrow"),
                            },
                            "options": checked.model_dump(mode="json"),
                        },
                        sort_keys=True,
                        ensure_ascii=True,
                        allow_nan=False,
                    ),
                ),
            )
            with (stage / "capture.json").open("x", encoding="utf-8") as receipt:
                receipt.write(artifact.model_dump_json(indent=2) + "\n")
                receipt.flush()
                os.fsync(receipt.fileno())
            # Close native resources and join watcher BEFORE publishing/releasing ownership.
            stopped.set()
            watcher.join()
            reader.close()
            reader = None
            relation.close()
            relation = None
            if owned:
                session.close()
                session = None
            check()
            if final.exists():
                raise FileExistsError("capture destination already exists")
            stage.rename(final)
        return artifact
    except duckdb.OutOfMemoryException as error:
        raise ResourceLimitError("DuckDB capture exhausted engine-managed memory") from error
    except duckdb.InterruptException as error:
        check()
        raise NativeEngineError("DuckDB capture was interrupted externally") from error
    except duckdb.Error as error:
        check()
        # Native exceptions may contain SQL literals/paths. Keep those out of ordinary diagnostics.
        raise NativeEngineError("DuckDB capture failed; no complete snapshot published") from error
    finally:
        stopped.set()
        if watcher is not None and watcher.ident is not None:
            watcher.join()
        try:
            if reader is not None:
                reader.close()
        finally:
            try:
                if relation is not None:
                    relation.close()
            finally:
                if lock is not None:
                    lock.release()
                if owned and session is not None:
                    session.close()


def _write_reader(
    reader: pa.RecordBatchReader,
    path: Path,
    native_types: tuple[tuple[str, str], ...],
    timezone: str,
    options: DuckDBCaptureOptions,
    check: Callable[[], None],
) -> tuple[int, list[int], list[int]]:
    # Imported here to keep the public module optional-dependency-free.
    import pyarrow as pa
    import pyarrow.compute as pc

    rows = 0
    nulls, nans = [0] * len(native_types), [0] * len(native_types)
    with path.open("xb") as sink:
        with pa.ipc.new_file(sink, reader.schema) as writer:
            while True:
                check()
                try:
                    batch = reader.read_next_batch()
                except StopIteration:
                    break
                except (OSError, pa.ArrowException) as error:
                    # The Arrow stream bridge can wrap DuckDB conversion/UDF and
                    # interrupt errors in OSError, outside duckdb.Error's hierarchy.
                    # Inspect cancellation/deadline before assigning a native failure.
                    # Keep this boundary around fetch only: disk write/fsync failures
                    # below remain filesystem errors rather than being mislabeled.
                    check()
                    if isinstance(error, pa.ArrowMemoryError):
                        raise ResourceLimitError("DuckDB capture exhausted Arrow memory") from error
                    raise NativeEngineError(
                        "DuckDB capture fetch failed; no complete snapshot published"
                    ) from error
                check()
                rows += batch.num_rows
                if rows > options.max_rows:
                    raise ResourceLimitError("DuckDB capture row budget exhausted")
                if batch.nbytes > options.max_batch_bytes:
                    raise ResourceLimitError("DuckDB capture batch byte budget exhausted")
                table = pa.Table.from_batches([batch])
                verify_duckdb_table(table, native_types, timezone)
                for i, column in enumerate(batch.columns):
                    nulls[i] += column.null_count
                    if pa.types.is_floating(column.type):
                        nans[i] += int(pc.sum(pc.is_nan(column)).as_py() or 0)
                writer.write_batch(batch)
                sink.flush()
                if sink.tell() > options.max_bytes:
                    raise ResourceLimitError("DuckDB capture serialized byte budget exhausted")
            check()
        # Arrow writes its footer while closing the writer. Flush and sync that
        # complete file through the original writable descriptor: Windows rejects
        # fsync on a descriptor reopened read-only.
        sink.flush()
        if sink.tell() > options.max_bytes:
            raise ResourceLimitError("DuckDB capture serialized byte budget exhausted")
        os.fsync(sink.fileno())
    if path.stat().st_size > options.max_bytes:
        raise ResourceLimitError("DuckDB capture serialized byte budget exhausted")
    return rows, nulls, nans
