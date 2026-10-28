"""Consume one explicitly pinned snapshot through a trusted, injected data client.

The client owns authentication, transport and the coordinating service. Fetching
the manifest in the constructor precedes RunContext budgets; clients must impose
their own transport timeouts. Downloads and verification use cooperative context
checkpoints. Neither a blocked client nor Arrow decoding can be preempted here.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Protocol
from uuid import uuid4

from pydantic import BeforeValidator, Field, StringConstraints, TypeAdapter, model_validator
from typing_extensions import Self

from equiframe._base import strict_bool_literal
from equiframe._documents import (
    Document,
    Evidence,
    Text,
    canonical_document_bytes,
    digest,
    save_document,
)
from equiframe.contracts import LogicalType
from equiframe.errors import (
    ArtifactIntegrityError,
    ExecutionCancelled,
    InvalidExecutionInput,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken
from equiframe.normalization import logical_signature
from equiframe.tables import LoadedTable, check_arrow, require_dependency
from equiframe.types import ArtifactRef
from equiframe.values import StringValue

if TYPE_CHECKING:
    import pyarrow as pa

    from equiframe.execution import RunContext

TableName = Annotated[Text, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]


class SnapshotColumn(Document):
    """Exact observed Arrow type plus independently declared logical expectation."""

    name: Text
    physical_type: Text
    logical_type: LogicalType
    nullable: bool


class SnapshotTable(Document):
    name: TableName
    artifact: Evidence
    row_count: Annotated[int, Field(ge=0)]
    columns: Annotated[tuple[SnapshotColumn, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_columns(self) -> Self:
        if len({column.name for column in self.columns}) != len(self.columns):
            raise ValueError("snapshot columns must have unique names")
        return self


class SnapshotManifest(Document):
    snapshot_id: Text
    domain_schema_revision: Text
    extraction_revision: Text
    provenance: Annotated[tuple[Text, ...], Field(min_length=1)]
    tables: Annotated[tuple[SnapshotTable, ...], Field(min_length=1)]
    state: Literal["published"] = "published"
    immutable: Annotated[Literal[True], BeforeValidator(strict_bool_literal)] = True

    @model_validator(mode="after")
    def pinned_identity(self) -> Self:
        if self.snapshot_id.casefold() == "latest":
            raise ValueError("snapshot identity must be explicit; latest is not immutable")
        if len({table.name for table in self.tables}) != len(self.tables):
            raise ValueError("snapshot tables must have unique names")
        if len(set(self.provenance)) != len(self.provenance):
            raise ValueError("snapshot provenance must have unique entries")
        return self


def snapshot_fingerprint(manifest: SnapshotManifest) -> str:
    return digest(SnapshotManifest.model_validate(manifest))


class SnapshotClient(Protocol):
    """Minimal client boundary; no HTTP, credentials or mutable DW handles here."""

    def get_snapshot(self, snapshot_id: str) -> SnapshotManifest: ...

    def download_artifact(self, ref: ArtifactRef, destination: Path) -> None: ...


class SnapshotDataSource:
    """DataSource whose manifest is fetched and pinned once before any execution.

    Each resolve downloads to a fresh directory beneath that run and checks the
    original SHA-256, byte count, row count and declared column schema before
    exposing Arrow data. A subsequent publication cannot alter this manifest.
    A table selection limits this consumer's inputs while retaining the complete
    pinned manifest and its fingerprint as provenance.
    The source does not retry a failed client or perform implicit latest lookup.
    """

    def __init__(
        self,
        snapshot_id: str,
        *,
        client: SnapshotClient,
        expected_domain_schema_revision: str | None = None,
        cancellation: CancellationToken | None = None,
        table_names: tuple[str, ...] | None = None,
    ) -> None:
        snapshot_id = TypeAdapter(Text).validate_python(snapshot_id, strict=True)
        if snapshot_id.casefold() == "latest":
            raise ValueError("snapshot identity must be explicit; latest is not immutable")
        if expected_domain_schema_revision is not None:
            TypeAdapter(Text).validate_python(expected_domain_schema_revision, strict=True)
        if cancellation is not None and cancellation.cancelled:
            raise ExecutionCancelled("snapshot manifest fetch was cancelled")
        manifest = SnapshotManifest.model_validate(client.get_snapshot(snapshot_id))
        if cancellation is not None and cancellation.cancelled:
            raise ExecutionCancelled("snapshot manifest fetch returned after cancellation")
        if manifest.snapshot_id != snapshot_id:
            raise ArtifactIntegrityError("client returned a different snapshot identity")
        if (
            expected_domain_schema_revision is not None
            and manifest.domain_schema_revision != expected_domain_schema_revision
        ):
            raise InvalidExecutionInput(
                "snapshot domain schema revision differs from the requested revision"
            )
        self._client = client
        self._manifest = manifest
        self._fingerprint = snapshot_fingerprint(manifest)
        available = {table.name: table for table in manifest.tables}
        selected = (
            tuple(available)
            if table_names is None
            else TypeAdapter(tuple[TableName, ...]).validate_python(table_names, strict=True)
        )
        if (
            not selected
            or len(set(selected)) != len(selected)
            or not set(selected) <= set(available)
        ):
            raise ValueError("snapshot table selection must be nonempty, unique and available")
        self._tables = {name: available[name] for name in selected}

    @property
    def snapshot_id(self) -> str:
        return self._manifest.snapshot_id

    @property
    def manifest(self) -> SnapshotManifest:
        return self._manifest

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._tables)

    def resolve(self, name: str, *, context: RunContext) -> LoadedTable:
        context.check()
        try:
            expected = self._tables[name]
        except KeyError:
            raise InvalidExecutionInput("table is absent from the pinned snapshot") from None
        options = context.plan.options
        if options.max_input_rows is not None and expected.row_count > options.max_input_rows:
            raise ResourceLimitError("snapshot table exceeds the input row budget")
        if (
            options.max_transport_bytes is not None
            and expected.artifact.size_bytes > options.max_transport_bytes
        ):
            raise ResourceLimitError("snapshot artifact exceeds the transport byte budget")
        require_dependency("pyarrow", "arrow")
        import pyarrow as pa
        import pyarrow.parquet as pq

        self._record_manifest(context)
        directory = context.directory / ("snapshot_" + uuid4().hex)
        directory.mkdir(mode=0o700, exist_ok=False)
        partial = directory / ("download.part." + expected.artifact.format)
        path = directory / ("verified." + expected.artifact.format)
        try:
            context.check()
            self._client.download_artifact(expected.artifact, partial)
            context.check()
            if (
                partial.is_symlink()
                or not partial.is_file()
                or not partial.resolve().is_relative_to(directory.resolve())
            ):
                raise ArtifactIntegrityError(
                    "snapshot client did not produce a local private artifact"
                )
            size = partial.stat().st_size
            if options.max_transport_bytes is not None and size > options.max_transport_bytes:
                raise ResourceLimitError("downloaded snapshot artifact exceeds the byte budget")
            if size != expected.artifact.size_bytes:
                raise ArtifactIntegrityError(
                    "snapshot artifact byte count differs from its manifest"
                )
            checksum = hashlib.sha256()
            with partial.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    context.check()
                    checksum.update(block)
            context.check()
            if checksum.hexdigest() != expected.artifact.sha256:
                raise ArtifactIntegrityError("snapshot artifact SHA-256 differs from its manifest")
            os.link(partial, path)
            partial.unlink()
            context.check()
            if expected.artifact.format == "parquet":
                table = pq.read_table(path)
            else:
                with path.open("rb") as stream, pa.ipc.open_file(stream) as reader:
                    table = reader.read_all()
            check_arrow(table)
            context.check_table(table, output=False)
            self._verify_schema(table, expected)
            context.check()
            return LoadedTable(
                table,
                origin=expected.artifact,
                notes=(
                    "Pinned snapshot ID and schema revision recorded in execution configuration.",
                    "Snapshot SHA-256, bytes, rows and physical/logical column schema verified.",
                ),
            )
        finally:
            partial.unlink(missing_ok=True)

    def _record_manifest(self, context: RunContext) -> None:
        # Workflow captures can use multiple contexts with distinct budgets but
        # the same run directory and configuration. Keep no source-owned run
        # cache: reuse only an exact published manifest and consistent records.
        path = context.directory / "snapshot-manifest.json"
        payload = canonical_document_bytes(self._manifest) + b"\n"
        configuration = {
            "snapshot_id": self.snapshot_id,
            "snapshot_domain_schema_revision": self._manifest.domain_schema_revision,
            "snapshot_extraction_revision": self._manifest.extraction_revision,
            "snapshot_manifest_sha256": self._fingerprint,
        }
        recorded = [item for item in context.effective_configuration if item.name in configuration]
        if len({item.name for item in recorded}) != len(recorded) or any(
            not isinstance(item.value, StringValue) or item.value.value != configuration[item.name]
            for item in recorded
        ):
            raise ArtifactIntegrityError("run configuration differs from its pinned snapshot")
        if path.exists() or path.is_symlink():
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != len(payload)
                or path.read_bytes() != payload
            ):
                raise ArtifactIntegrityError("run manifest differs from its pinned snapshot")
        elif recorded:
            raise ArtifactIntegrityError("recorded snapshot manifest is missing from the run")
        else:
            save_document(self._manifest, path)
        names = {item.name for item in recorded}
        for name, value in configuration.items():
            if name not in names:
                context.record_configuration(name, value)

    @staticmethod
    def _verify_schema(table: pa.Table, expected: SnapshotTable) -> None:
        if table.num_rows != expected.row_count:
            raise ArtifactIntegrityError("snapshot row count differs from its manifest")
        if tuple(table.column_names) != tuple(column.name for column in expected.columns):
            raise ArtifactIntegrityError("snapshot column names/order differ from its manifest")
        for field, column in zip(table.schema, expected.columns, strict=True):
            if str(field.type) != column.physical_type or logical_signature(field.type) != tuple(
                column.logical_type.model_dump().values()
            ):
                raise ArtifactIntegrityError(
                    "snapshot physical/logical column type differs from its manifest"
                )
            if not column.nullable and table[column.name].null_count:
                raise ArtifactIntegrityError(
                    "snapshot contains NULL in a declared nonnullable column"
                )
