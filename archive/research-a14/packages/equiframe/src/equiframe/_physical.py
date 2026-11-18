"""Verify captured physical metadata without executing or normalizing a transformation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from equiframe.errors import ArtifactIntegrityError, CapabilityError
from equiframe.local import local_path
from equiframe.tables import require_dependency

if TYPE_CHECKING:
    from equiframe.execution_types import PhysicalColumn, TableArtifact
    from equiframe.types import ArtifactRef


@dataclass(frozen=True)
class _Observation:
    schema: tuple[tuple[str, str], ...]
    rows: int
    buffer_bytes: int
    nulls: tuple[int, ...]
    nans: tuple[int, ...]


def _observe(ref: ArtifactRef, *, check: Callable[[], None] | None = None) -> _Observation:
    """Hash first, then decode batches; buffer bytes are distinct from file bytes."""
    require_dependency("pyarrow", "arrow")
    import pyarrow as pa
    import pyarrow.compute as pc

    if ref.format not in ("arrow", "parquet"):
        raise ArtifactIntegrityError("physical table requires Arrow IPC or Parquet")
    try:
        with local_path(ref).open("rb") as source:
            if check:
                check()
            digest = hashlib.sha256()
            file_bytes = 0
            while block := source.read(1024 * 1024):
                if check:
                    check()
                digest.update(block)
                file_bytes += len(block)
                if check:
                    check()
            if (digest.hexdigest(), file_bytes) != (ref.sha256, ref.size_bytes):
                raise ArtifactIntegrityError("physical table SHA-256 or size mismatch")
            source.seek(0)
            if ref.format == "arrow":
                reader = pa.ipc.open_file(source)
                schema = reader.schema
                batches = (reader.get_batch(i) for i in range(reader.num_record_batches))
            else:
                import pyarrow.parquet as pq

                parquet = pq.ParquetFile(source)
                schema = parquet.schema_arrow
                # Preserve row-group boundaries. A 65536-row subdivision is byte
                # aligned for validity bitmaps and does not change materialized
                # Arrow nbytes through additional partial bitmap boundaries.
                batches = (
                    batch
                    for group in range(parquet.num_row_groups)
                    for batch in parquet.iter_batches(
                        batch_size=65536, row_groups=[group], use_threads=False
                    )
                )
            nulls = [0] * len(schema)
            nans = [0] * len(schema)
            rows = buffer_bytes = 0
            batch_iterator = iter(batches)
            while True:
                if check:
                    check()
                try:
                    batch = next(batch_iterator)
                except StopIteration:
                    break
                batch.validate(full=True)
                if batch.schema != schema:
                    raise ArtifactIntegrityError("physical batch schema changed")
                rows += batch.num_rows
                buffer_bytes += batch.nbytes
                for i, array in enumerate(batch.columns):
                    nulls[i] += array.null_count
                    if pa.types.is_floating(array.type):
                        nans[i] += int(pc.sum(pc.is_nan(array)).as_py() or 0)
                if check:
                    check()
            return _Observation(
                schema=tuple((field.name, str(field.type)) for field in schema),
                rows=rows,
                buffer_bytes=buffer_bytes,
                nulls=tuple(nulls),
                nans=tuple(nans),
            )
    except (OSError, ValueError, CapabilityError, pa.ArrowException) as error:
        raise ArtifactIntegrityError("cannot verify captured physical table") from error


def physical_size(ref: ArtifactRef, *, check: Callable[[], None] | None = None) -> tuple[int, int]:
    """Return rows and materialized Arrow buffer bytes, with verified source bytes.

    Decoding is by record batch. An IPC record batch can itself be large; this
    function does not impose a process-memory quota or execute native engines.
    """
    observed = _observe(ref, check=check)
    return observed.rows, observed.buffer_bytes


def _verify_columns(observed: _Observation, columns: tuple[PhysicalColumn, ...], rows: int) -> None:
    if observed.rows != rows or observed.schema != tuple(
        (column.name, column.arrow_type) for column in columns
    ):
        raise ArtifactIntegrityError("captured physical rows or schema contradict metadata")
    if observed.nulls != tuple(column.null_count for column in columns) or (
        observed.nans != tuple(column.nan_count for column in columns)
    ):
        raise ArtifactIntegrityError("captured physical NULL or NaN counts contradict metadata")


def verify_table_metadata(table: TableArtifact) -> None:
    """Verify schema, counts and a separate index against captured table bytes.

    Native ``engine_type`` is provenance and cannot be inferred from IPC/Parquet.
    No casts, contract normalization, ETL, plugins or engine imports occur here.
    """
    _verify_columns(_observe(table.data), table.columns, table.row_count)
    if table.index is not None:
        _verify_columns(_observe(table.index), table.index_columns, table.row_count)
