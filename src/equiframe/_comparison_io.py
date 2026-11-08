"""Streaming local snapshots/readers. No read_all/read_table on comparison paths."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from equiframe.errors import ArtifactIntegrityError, CapabilityError, ResourceLimitError
from equiframe.local import local_path
from equiframe.tables import ArrowInput, require_dependency
from equiframe.types import ArtifactRef

if TYPE_CHECKING:
    import pyarrow as pa

    from equiframe.comparison_types import ComparisonOptions


def file_ref(
    path: Path, format_name: str, *, check: Callable[[], None] | None = None
) -> ArtifactRef:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            if check:
                check()
            digest.update(block)
            size += len(block)
    return ArtifactRef.model_validate(
        dict(
            schema_version="1.0",
            uri=path.resolve().as_uri(),
            sha256=digest.hexdigest(),
            size_bytes=size,
            format=format_name,
            media_type={
                "arrow": "application/vnd.apache.arrow.file",
                "parquet": "application/vnd.apache.parquet",
                "jsonl": "application/x-ndjson",
                "json": "application/json",
            }[format_name],
        )
    )


def snapshot(
    value: ArrowInput | ArtifactRef | Path,
    directory: Path,
    options: ComparisonOptions,
    check: Callable[[], None],
) -> ArtifactRef:
    require_dependency("pyarrow", "arrow")
    import pyarrow as pa

    if isinstance(value, ArrowInput):
        if not isinstance(value.table, pa.Table):
            raise TypeError("ArrowInput requires an Arrow Table")
        path = directory / (uuid4().hex + ".arrow")
        try:
            with path.open("xb") as sink, pa.ipc.new_file(sink, value.table.schema) as writer:
                for batch in value.table.to_reader(max_chunksize=options.batch_rows):
                    check()
                    if batch.nbytes > options.max_batch_bytes:
                        raise ResourceLimitError("max_batch_bytes")
                    batch.validate(full=True)
                    writer.write_batch(batch)
                    sink.flush()
                    check()
            return file_ref(path, "arrow", check=check)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    ref = ArtifactRef.model_validate(value) if isinstance(value, ArtifactRef) else None
    source = local_path(ref) if ref else value
    if not isinstance(source, Path):
        raise TypeError("comparison input requires ArrowInput, ArtifactRef, or Path")
    format_name = (
        ref.format if ref else {".arrow": "arrow", ".parquet": "parquet"}.get(source.suffix.lower())
    )
    if format_name not in ("arrow", "parquet"):
        raise CapabilityError("comparison supports local Arrow IPC file and Parquet")
    path = directory / (uuid4().hex + "." + format_name)
    digest = hashlib.sha256()
    size = 0
    try:
        with source.open("rb") as reader, path.open("xb") as writer:
            while block := reader.read(min(1024 * 1024, options.max_disk_bytes + 1)):
                check()
                writer.write(block)
                writer.flush()
                digest.update(block)
                size += len(block)
                check()
        if ref and (size != ref.size_bytes or digest.hexdigest() != ref.sha256):
            raise ArtifactIntegrityError("artifact SHA-256 or size mismatch")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return ArtifactRef.model_validate(
        dict(
            schema_version="1.0",
            uri=path.resolve().as_uri(),
            sha256=digest.hexdigest(),
            size_bytes=size,
            format=format_name,
            media_type="application/vnd.apache.arrow.file"
            if format_name == "arrow"
            else "application/vnd.apache.parquet",
        )
    )


@contextmanager
def batches(
    ref: ArtifactRef, options: ComparisonOptions, check: Callable[[], None]
) -> Iterator[tuple[pa.Schema, Iterator[pa.RecordBatch]]]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    with local_path(ref).open("rb") as source:
        if ref.format == "parquet":
            with pq.ParquetFile(source) as reader:
                yield (
                    reader.schema_arrow,
                    _checked(
                        reader.iter_batches(batch_size=options.batch_rows, use_threads=False),
                        options,
                        check,
                    ),
                )
        else:
            reader = pa.ipc.open_file(source)

            def iterate() -> Iterator[pa.RecordBatch]:
                for index in range(reader.num_record_batches):
                    check()
                    batch = reader.get_batch(index)
                    # IPC file batches are indivisible at decode time. This check
                    # is cooperative and follows decode; never a process RSS quota.
                    if batch.nbytes > options.max_batch_bytes:
                        raise ResourceLimitError("IPC stored batch exceeds max_batch_bytes")
                    for start in range(0, batch.num_rows, options.batch_rows):
                        yield batch.slice(start, options.batch_rows)

            yield reader.schema, _checked(iterate(), options, check)


def _checked(
    iterator: Iterator[pa.RecordBatch], options: ComparisonOptions, check: Callable[[], None]
) -> Iterator[pa.RecordBatch]:
    for batch in iterator:
        check()
        if batch.nbytes > options.max_batch_bytes:
            raise ResourceLimitError("max_batch_bytes")
        batch.validate(full=True)
        yield batch
