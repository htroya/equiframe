"""Versioned local Parquet publication with a single atomic visibility pointer."""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import uuid4

from pydantic import TypeAdapter, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, NonNegativeInt
from equiframe._regular_io import local_output_directory
from equiframe.errors import ArtifactIntegrityError
from equiframe.evidence import canonical_bytes, describe_file, load_json, publish_json, verify_files
from equiframe.local import local_path
from equiframe.pipeline_types import EvidenceFile
from equiframe.tables import read_table, require_dependency
from equiframe.types import ArtifactRef, Sha256
from equiframe.verify_types import VerificationResult


class PublishedTable(FrozenModel):
    name: Identifier
    source_sha256: Sha256
    source_size_bytes: NonNegativeInt
    source_format: Literal["arrow", "parquet"]
    parquet: EvidenceFile
    row_count: NonNegativeInt
    verification_id: Identifier
    verification_sha256: Sha256


class LoadReceipt(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    policy: Literal["create", "replace"]
    identity_sha256: Sha256
    previous_run: Identifier | None
    tables: tuple[PublishedTable, ...]
    guarantee: Literal["local_atomic_pointer"] = "local_atomic_pointer"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if not self.tables or len({t.name for t in self.tables}) != len(self.tables):
            raise ValueError("publication table names must be nonempty and unique")
        if len({table.name.casefold() for table in self.tables}) != len(self.tables):
            raise ValueError(
                "publication table names must be unique on case-insensitive filesystems"
            )
        if any(t.parquet.path != t.name + ".parquet" for t in self.tables):
            raise ValueError("publication Parquet paths must correspond to table names")
        identity = hashlib.sha256(
            canonical_bytes(
                {
                    table.name: {
                        "sha256": table.source_sha256,
                        "size": table.source_size_bytes,
                        "format": table.source_format,
                    }
                    for table in sorted(self.tables, key=lambda item: item.name)
                }
            )
        ).hexdigest()
        if identity != self.identity_sha256:
            raise ValueError("publication identity differs from source inventory")
        if self.previous_run == self.run_id:
            raise ValueError("publication cannot be its own previous version")
        return self


class PublicationPointer(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    receipt_sha256: Sha256


class Destination(Protocol):
    def publish(
        self,
        tables: Mapping[str, ArtifactRef],
        *,
        run_id: str,
        verifications: Mapping[str, VerificationResult | Path],
        policy: Literal["create", "replace"] = "create",
    ) -> LoadReceipt: ...


class ParquetDestination:
    """One local writer under an exclusive lock. Versions remain immutable.

    Directory rename publishes a new version; os.replace switches current.json
    atomically on its local filesystem. This is not a power-loss durability or
    distributed transaction guarantee. An interrupted writer can leave staging,
    an unreferenced version or a lock; inspect those before removing a stale lock.
    """

    def __init__(self, root: Path) -> None:
        self.root = local_output_directory(root)

    def current(self) -> LoadReceipt | None:
        pointer_path = self.root / "current.json"
        if not pointer_path.exists():
            return None
        pointer = load_json(PublicationPointer, pointer_path)
        directory = self.root / "versions" / pointer.run_id
        manifest = directory / "load.json"
        if describe_file(manifest, directory).sha256 != pointer.receipt_sha256:
            raise ArtifactIntegrityError("publication receipt hash differs from visibility pointer")
        result = load_json(LoadReceipt, manifest)
        if result.run_id != pointer.run_id:
            raise ArtifactIntegrityError("publication identity differs from pointer")
        verify_files(directory, tuple(table.parquet for table in result.tables))
        require_dependency("pyarrow", "arrow")
        import pyarrow.parquet as pq

        for table in result.tables:
            if pq.ParquetFile(directory / table.parquet.path).metadata.num_rows != table.row_count:
                raise ArtifactIntegrityError("publication row count differs from Parquet metadata")
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        if actual != {"load.json", *(table.parquet.path for table in result.tables)}:
            raise ArtifactIntegrityError("published version inventory contains unexpected files")
        return result

    def publish(
        self,
        tables: Mapping[str, ArtifactRef],
        *,
        run_id: str,
        verifications: Mapping[str, VerificationResult | Path],
        policy: Literal["create", "replace"] = "create",
    ) -> LoadReceipt:
        require_dependency("pyarrow", "arrow")
        import pyarrow.parquet as pq

        run_id = TypeAdapter(Identifier).validate_python(run_id, strict=True)
        if not tables or set(tables) != set(verifications):
            raise ValueError("every published table requires exactly one verification gate")
        for name in tables:
            TypeAdapter(Identifier).validate_python(name, strict=True)
        if len({name.casefold() for name in tables}) != len(tables):
            raise ValueError(
                "publication table names must be unique on case-insensitive filesystems"
            )
        if policy not in ("create", "replace"):
            raise ValueError("publication policy must be create or replace")
        checked: dict[str, ArtifactRef] = {}
        reports: dict[str, VerificationResult] = {}
        for name, ref in tables.items():
            ref = ArtifactRef.model_validate(ref)
            if ref.format not in ("arrow", "parquet"):
                raise ValueError("published sources require Arrow or Parquet")
            from equiframe.verify import read_verification

            provided = verifications[name]
            if isinstance(provided, Path):
                report = read_verification(provided)
            else:
                provided = VerificationResult.model_validate(provided)
                if not provided.outputs:
                    raise ValueError("publication requires persisted verification evidence")
                report = read_verification(local_path(provided.outputs[0][1]).parent)
                if provided != report:
                    raise ArtifactIntegrityError(
                        "provided verification differs from persisted evidence"
                    )
            if not report.publishable:
                raise ValueError("publication gate is not approved for table " + name)
            if ref.sha256 not in {hash for _, hash in report.binding.outputs}:
                raise ValueError("verification gate does not bind the published output bytes")
            checked[name] = ref
            reports[name] = report
        identity = hashlib.sha256(
            canonical_bytes(
                {
                    name: {"sha256": ref.sha256, "size": ref.size_bytes, "format": ref.format}
                    for name, ref in sorted(checked.items())
                }
            )
        ).hexdigest()
        local_output_directory(self.root)
        local_output_directory(self.root / "versions")
        local_output_directory(self.root / ".staging")
        local_output_directory(self.root / ".validation")
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / ".publication.lock"
        with lock.open("xb") as stream:
            stream.write(run_id.encode("utf-8"))
        staging = self.root / ".staging" / (run_id + "-" + uuid4().hex)
        try:
            current = self.current()
            final = self.root / "versions" / run_id
            if final.exists():
                receipt = load_json(LoadReceipt, final / "load.json")
                if receipt.run_id != run_id:
                    raise ArtifactIntegrityError(
                        "stored publication receipt has a different run identity"
                    )
                verify_files(final, tuple(table.parquet for table in receipt.tables))
                actual_files = {
                    path.relative_to(final).as_posix()
                    for path in final.rglob("*")
                    if path.is_file()
                }
                if actual_files != {"load.json", *(table.parquet.path for table in receipt.tables)}:
                    raise ArtifactIntegrityError(
                        "stored publication version inventory is not closed"
                    )
                if any(
                    pq.ParquetFile(final / table.parquet.path).metadata.num_rows != table.row_count
                    for table in receipt.tables
                ):
                    raise ArtifactIntegrityError(
                        "stored publication row count differs from Parquet"
                    )
                if receipt.identity_sha256 != identity:
                    raise ValueError("run identity already exists with different source bytes")
                # A retry cannot silently roll back a newer visible version.
                if current and current.run_id != run_id and receipt.previous_run != current.run_id:
                    raise ValueError("idempotent retry conflicts with a newer current publication")
                if current is None or current.run_id != run_id:
                    self._switch(final, receipt)
                return receipt
            if current is not None and policy == "create":
                raise FileExistsError(
                    "destination already has a published version; request replace explicitly"
                )
            staging.mkdir(parents=True, exist_ok=False)
            published = []
            for name, reference in sorted(checked.items()):
                table = read_table(reference)
                target = staging / (name + ".parquet")
                pq.write_table(table, target)
                restored = pq.read_table(target)
                # Validate complete values through the same explicit semantic policy;
                # byte equality between IPC and Parquet is neither expected nor useful.
                from equiframe.comparison import compare
                from equiframe.tables import ArrowInput

                report = reports[name]
                comparison = compare(
                    ArrowInput(table),
                    ArrowInput(restored),
                    contract=report.contract,
                    policy=report.comparisons[0].spec.policy,
                    work_dir=self.root / ".validation",
                )
                if comparison.state != "equivalent" or not comparison.complete:
                    raise ArtifactIntegrityError("staged Parquet differs from verified output")
                published.append(
                    PublishedTable(
                        name=name,
                        source_sha256=reference.sha256,
                        source_size_bytes=reference.size_bytes,
                        source_format=cast("Literal['arrow', 'parquet']", reference.format),
                        parquet=describe_file(target, staging),
                        row_count=table.num_rows,
                        verification_id=report.verification_id,
                        verification_sha256=hashlib.sha256(
                            canonical_bytes(report.model_dump(mode="json"))
                        ).hexdigest(),
                    )
                )
            receipt = LoadReceipt(
                run_id=run_id,
                policy=policy,
                identity_sha256=identity,
                previous_run=current.run_id if current else None,
                tables=tuple(published),
            )
            publish_json(receipt, staging / "load.json")
            final.parent.mkdir(parents=True, exist_ok=True)
            os.rename(staging, final)
            self._switch(final, receipt)
            return receipt
        finally:
            if staging.exists():
                shutil.rmtree(staging)
            lock.unlink(missing_ok=True)

    def _switch(self, directory: Path, receipt: LoadReceipt) -> None:
        pointer = PublicationPointer(
            run_id=receipt.run_id,
            receipt_sha256=describe_file(directory / "load.json", directory).sha256,
        )
        temporary = self.root / ("current-" + uuid4().hex + ".json")
        try:
            publish_json(pointer, temporary)
            os.replace(temporary, self.root / "current.json")
        finally:
            temporary.unlink(missing_ok=True)
