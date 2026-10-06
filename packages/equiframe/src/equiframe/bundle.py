"""Closed portable evidence, retaining historical bytes and resolving owned artifacts."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator

from equiframe._base import FrozenModel, Text
from equiframe.errors import ArtifactIntegrityError
from equiframe.evidence import describe_file, load_json, parse_json, publish_json, verify_files
from equiframe.local import _bundle_paths, local_path
from equiframe.pipeline_types import EvidenceFile
from equiframe.types import ArtifactRef


class BundleReference(FrozenModel):
    uri: Text
    member: EvidenceFile


class EvidenceBundle(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["migration", "verification", "workflow"]
    root_document: Text
    files: tuple[EvidenceFile, ...]
    references: tuple[BundleReference, ...]
    producer: Literal["equiframe"] = "equiframe"
    producer_version: Text

    @model_validator(mode="after")
    def consistent(self) -> Self:
        names = {f.path for f in self.files}
        if len(names) != len(self.files) or self.root_document not in names:
            raise ValueError("bundle requires a unique closed inventory and root document")
        if "bundle.json" in names:
            raise ValueError("bundle cannot inventory its own root manifest")
        if len({r.uri for r in self.references}) != len(self.references):
            raise ValueError("bundle URI mappings must be unique")
        inventory = {f.path: f for f in self.files}
        if any(inventory.get(r.member.path) != r.member for r in self.references):
            raise ValueError("bundle mapping must bind an inventoried member")
        return self


def _members(root: Path) -> tuple[Path, ...]:
    root = root.resolve()
    members: list[Path] = []
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in (*dirs, *files):
            p = Path(parent) / name
            if p.is_symlink() or p.is_junction() or not p.resolve().is_relative_to(root):
                raise ArtifactIntegrityError(
                    "portable evidence rejects symlinks and escaping paths"
                )
        members.extend(Path(parent) / name for name in files)
    return tuple(sorted(members))


def _references(value: object) -> tuple[ArtifactRef, ...]:
    result: list[ArtifactRef] = []
    if isinstance(value, dict):
        if {"uri", "sha256", "format", "media_type", "size_bytes"} <= value.keys():
            result.append(ArtifactRef.model_validate(value))
        else:
            for child in value.values():
                result.extend(_references(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_references(child))
    return tuple(result)


def _document_references(root: Path, members: tuple[Path, ...]) -> dict[str, ArtifactRef]:
    result: dict[str, ArtifactRef] = {}
    for path in members:
        if path.suffix == ".json":
            for ref in _references(parse_json(path.read_bytes())):
                if ref.uri in result and result[ref.uri] != ref:
                    raise ArtifactIntegrityError("one artifact URI has conflicting identities")
                result[ref.uri] = ref
    return result


def _inspect(root: Path, kind: str, document: str) -> object:
    if kind == "migration":
        from equiframe.migration.io import read_migration

        return read_migration(root / document)
    if kind == "verification":
        from equiframe.verify import read_verification

        return read_verification(root / document)
    from equiframe.workflow import read_workflow

    return read_workflow(root / document)


def export_bundle(source: Path, destination: Path) -> EvidenceBundle:
    """Export checked migration/Verify/workflow bytes to a new directory.

    No artifact is fetched from outside the source. External provenance can map
    only to an already captured member with exactly the same hash and size.
    """
    source = source.resolve()
    if source.is_file():
        source = source.parent
    names = {
        "migration.json": "migration",
        "verification.json": "verification",
        "workflow.json": "workflow",
    }
    found = [(name, kind) for name, kind in names.items() if (source / name).is_file()]
    if len(found) != 1:
        raise ValueError("export requires one supported finalized operation")
    document, kind = found[0]
    members = _members(source)
    _inspect(source, kind, document)
    refs = _document_references(source, members)
    entries = tuple(describe_file(p, source) for p in members)
    by_path = {f.path: f for f in entries}
    by_identity = {(f.sha256, f.size_bytes): f for f in entries}
    mappings: list[BundleReference] = []
    for ref in refs.values():
        p = local_path(ref).resolve()
        item = by_path.get(p.relative_to(source).as_posix()) if p.is_relative_to(source) else None
        if item is None:
            item = by_identity.get((ref.sha256, ref.size_bytes))
        if item is None or (item.sha256, item.size_bytes) != (ref.sha256, ref.size_bytes):
            raise ArtifactIntegrityError("artifact reference is outside the captured bundle")
        member = EvidenceFile(
            path="operation/" + item.path, sha256=item.sha256, size_bytes=item.size_bytes
        )
        mappings.append(BundleReference(uri=ref.uri, member=member))
    destination = destination.resolve()
    if destination.is_relative_to(source):
        raise ValueError("portable destination must be outside the source operation")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, destination / "operation")
    from equiframe import __version__

    bundle = EvidenceBundle.model_validate(
        dict(
            kind=kind,
            root_document="operation/" + document,
            files=tuple(
                EvidenceFile(path="operation/" + e.path, sha256=e.sha256, size_bytes=e.size_bytes)
                for e in entries
            ),
            references=tuple(mappings),
            producer_version=__version__,
        )
    )
    publish_json(bundle, destination / "bundle.json")
    read_bundle(destination)
    return bundle


def read_bundle(path: Path, *, expected_sha256: str | None = None) -> EvidenceBundle:
    """Verify membership and operation; only None omits the optional manifest pin."""
    root = path if path.is_dir() else path.parent
    root = root.resolve()
    manifest = root / "bundle.json"
    if (
        expected_sha256 is not None
        and hashlib.sha256(manifest.read_bytes()).hexdigest() != expected_sha256
    ):
        raise ArtifactIntegrityError("portable manifest differs from trusted SHA-256")
    bundle = load_json(EvidenceBundle, manifest)
    members = _members(root)
    actual = {p.relative_to(root).as_posix() for p in members if p != manifest}
    if actual != {f.path for f in bundle.files}:
        raise ArtifactIntegrityError("portable inventory is not closed")
    verify_files(root, bundle.files)
    mappings = {r.uri: root / r.member.path for r in bundle.references}
    refs = _document_references(root, tuple(p for p in members if p != manifest))
    if set(refs) != set(mappings):
        raise ArtifactIntegrityError("portable URI mapping differs from captured documents")
    for uri, ref in refs.items():
        entry = next(r.member for r in bundle.references if r.uri == uri)
        if (entry.sha256, entry.size_bytes) != (ref.sha256, ref.size_bytes):
            raise ArtifactIntegrityError("portable reference content identity mismatch")
    with _bundle_paths(mappings):
        _inspect(root, bundle.kind, bundle.root_document)
    return bundle


def import_bundle(
    source: Path, destination: Path, *, expected_sha256: str | None = None
) -> EvidenceBundle:
    """Copy to a new directory and verify again; original bytes are preserved."""
    read_bundle(source, expected_sha256=expected_sha256)
    root = source if source.is_dir() else source.parent
    destination = destination.resolve()
    if destination.exists() or destination.is_relative_to(root.resolve()):
        raise ValueError("bundle import requires a new destination outside the source")
    shutil.copytree(root, destination)
    return read_bundle(destination, expected_sha256=expected_sha256)


def inspect_bundle(path: Path, *, expected_sha256: str | None = None) -> dict[str, object]:
    """Inspect semantic/technical outcomes while resolving original portable URIs."""
    bundle = read_bundle(path, expected_sha256=expected_sha256)
    root = (path if path.is_dir() else path.parent).resolve()
    mapping = {r.uri: root / r.member.path for r in bundle.references}
    with _bundle_paths(mapping):
        if bundle.kind == "migration":
            from equiframe.migration.io import migration_summary, read_migration

            outcome = migration_summary(read_migration(root / bundle.root_document))
        elif bundle.kind == "verification":
            from equiframe.verify import read_verification, verification_summary

            outcome = verification_summary(read_verification(root / bundle.root_document))
        else:
            from equiframe.workflow import read_workflow

            workflow = read_workflow(root / bundle.root_document)
            outcome = {
                "run_id": workflow.run_id,
                "complete": workflow.complete,
                "exit_code": workflow.exit_code,
                "first_divergent_stage": workflow.first_divergent_stage,
                "checkpoints": [c.model_dump(mode="json") for c in workflow.checkpoints],
            }
    return {"kind": bundle.kind, "integrity": "passed", "outcome": outcome}
