"""Immutable local snapshots with bounded manifests and verified copies."""

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

if __package__:
    from .safe_io import (
        MAX_ARTIFACT_BYTES,
        MAX_ARTIFACTS,
        confined,
        digest,
        identifier,
        open_regular,
        read_json,
        relative_path,
        unsigned_integer,
    )
else:
    from safe_io import (
        MAX_ARTIFACT_BYTES,
        MAX_ARTIFACTS,
        confined,
        digest,
        identifier,
        open_regular,
        read_json,
        relative_path,
        unsigned_integer,
    )


@dataclass(frozen=True)
class ArtifactRef:
    snapshot_id: str
    table_name: str
    file_path: str
    size_bytes: int
    sha256: str
    row_count: int | None = None


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    version: str
    source: str
    timestamp: str
    artifacts: tuple[ArtifactRef, ...] = ()

    def get_artifact(self, table_name):
        return next((a for a in self.artifacts if a.table_name == table_name), None)


def _sha256_file(path):
    h = hashlib.sha256()
    with open_regular(path) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _verificar_artifact(path, ref):
    if path.stat().st_size != ref.size_bytes:
        raise ValueError("Tamaño incorrecto. Copia rechazada.")
    if _sha256_file(path) != ref.sha256:
        raise ValueError("SHA-256 incorrecto. Copia rechazada.")


def _validate_ref(ref, maximum):
    if not isinstance(ref, ArtifactRef):
        raise ValueError("Referencia de artefacto inválida.")
    identifier(ref.snapshot_id)
    identifier(ref.table_name)
    relative_path(ref.file_path)
    digest(ref.sha256)
    unsigned_integer(ref.size_bytes, maximum=maximum)
    if ref.row_count is not None:
        unsigned_integer(ref.row_count, maximum=2**63 - 1)


class SnapshotClient:
    def __init__(self, base_dir, *, max_artifact_bytes=MAX_ARTIFACT_BYTES):
        self.base_dir = Path(base_dir).resolve()
        self.max_artifact_bytes = unsigned_integer(max_artifact_bytes, maximum=MAX_ARTIFACT_BYTES)
        self._pinned = {}

    def get_snapshot(self, snapshot_id):
        identifier(snapshot_id)
        if snapshot_id in self._pinned:
            return self._pinned[snapshot_id]
        if not self.base_dir.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' no encontrado.")
        path = confined(self.base_dir, f"{snapshot_id}/manifest.json")
        if not path.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' no encontrado.")
        data = read_json(path)
        required = {"snapshot_id", "version", "source", "timestamp", "artifacts"}
        if (
            not isinstance(data, dict)
            or not required <= data.keys()
            or (data.keys() - required - {"producer_job_id"})
        ):
            raise ValueError("Manifiesto inválido.")
        if data["snapshot_id"] != snapshot_id:
            raise ValueError("Identidad de snapshot incompatible.")
        version = identifier(data["version"])
        source, timestamp = data["source"], data["timestamp"]
        if (
            not isinstance(source, str)
            or not 1 <= len(source) <= 256
            or any(ord(c) < 32 for c in source)
        ):
            raise ValueError("Fuente inválida.")
        if not isinstance(timestamp, str) or len(timestamp) > 64:
            raise ValueError("Timestamp inválido.")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Timestamp inválido.") from exc
        if parsed.tzinfo is None:
            raise ValueError("Timestamp sin zona horaria.")
        entries = data["artifacts"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ARTIFACTS:
            raise ValueError("Inventario vacío o demasiado grande.")
        artifacts = []
        names, paths = set(), set()
        for entry in entries:
            fields = {"table_name", "file_path", "size_bytes", "sha256"}
            if (
                not isinstance(entry, dict)
                or not fields <= entry.keys()
                or (entry.keys() - fields - {"row_count", "version"})
            ):
                raise ValueError("Entrada de inventario inválida.")
            if entry.get("version", version) != version:
                raise ValueError("El snapshot mezcla versiones.")
            ref = ArtifactRef(
                snapshot_id,
                entry["table_name"],
                entry["file_path"],
                entry["size_bytes"],
                entry["sha256"],
                entry.get("row_count"),
            )
            _validate_ref(ref, self.max_artifact_bytes)
            if ref.table_name in names or ref.file_path.casefold() in paths:
                raise ValueError("Tablas o archivos duplicados.")
            names.add(ref.table_name)
            paths.add(ref.file_path.casefold())
            confined(self.base_dir, f"{snapshot_id}/{ref.file_path}")
            artifacts.append(ref)
        manifest = SnapshotManifest(snapshot_id, version, source, timestamp, tuple(artifacts))
        self._pinned[snapshot_id] = manifest
        return manifest

    def list_snapshots(self):
        if not self.base_dir.exists():
            return []
        snapshots = []
        for directory in self.base_dir.iterdir():
            try:
                self.get_snapshot(directory.name)
            except (ValueError, FileNotFoundError, NotADirectoryError):
                continue
            snapshots.append(directory.name)
        return sorted(snapshots, reverse=True)

    def download_artifact(self, ref, destino):
        _validate_ref(ref, self.max_artifact_bytes)
        if ref not in self.get_snapshot(ref.snapshot_id).artifacts:
            raise ValueError("Referencia ajena al inventario fijado.")
        source = confined(self.base_dir, f"{ref.snapshot_id}/{ref.file_path}")
        destination = Path(destino)
        if destination.is_symlink():
            raise ValueError("No se permiten enlaces en el destino.")
        destination.mkdir(parents=True, exist_ok=True)
        final = confined(destination, relative_path(ref.file_path).name)
        if final.exists():
            _verificar_artifact(final, ref)
            return final
        fd, temporary = tempfile.mkstemp(prefix=".download-", dir=destination)
        try:
            with os.fdopen(fd, "wb") as output, open_regular(source) as stream:
                remaining = ref.size_bytes
                h = hashlib.sha256()
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError("Tamaño incorrecto. Copia rechazada.")
                    output.write(block)
                    h.update(block)
                    remaining -= len(block)
                if stream.read(1):
                    raise ValueError("Tamaño incorrecto. Copia rechazada.")
                if h.hexdigest() != ref.sha256:
                    raise ValueError("SHA-256 incorrecto. Copia rechazada.")
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, final)
            return final
        finally:
            Path(temporary).unlink(missing_ok=True)
