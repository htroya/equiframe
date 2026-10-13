"""Single-writer jobs, atomic receipts and immutable snapshot publication."""

import hashlib
import logging
import os
import re
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .safe_io import (
        MAX_ARTIFACT_BYTES,
        MAX_ARTIFACTS,
        atomic_json,
        confined,
        identifier,
        open_regular,
        read_json,
        safe_error_frames,
        unsigned_integer,
    )
else:
    from safe_io import (
        MAX_ARTIFACT_BYTES,
        MAX_ARTIFACTS,
        atomic_json,
        confined,
        identifier,
        open_regular,
        read_json,
        safe_error_frames,
        unsigned_integer,
    )
if __package__:
    from .snapshot_client import SnapshotClient, _verificar_artifact
else:
    from snapshot_client import SnapshotClient, _verificar_artifact

PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED = (
    "pending",
    "in_progress",
    "completed",
    "failed",
    "cancelled",
)
logger = logging.getLogger("equiframe.data")


class WriterBusyError(RuntimeError):
    """Another writer holds the OS lock."""


class SnapshotConflictError(ValueError):
    """An immutable snapshot already exists."""


@dataclass
class Job:
    job_id: str
    idempotency_key: str
    operation: str
    snapshot_id: str
    state: str
    created_at: str
    updated_at: str
    stage: str = ""
    error: str = ""
    result_snapshot_id: str = ""

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(document):
        if not isinstance(document, dict):
            raise ValueError("Recibo de trabajo inválido.")
        job = Job(**document)
        identifier(job.job_id)
        identifier(job.snapshot_id)
        if not re.fullmatch(r"[0-9a-f]{64}", job.idempotency_key) or job.operation != "load":
            raise ValueError("Recibo de trabajo inválido.")
        if job.state not in (PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED):
            raise ValueError("Estado de trabajo inválido.")
        if job.error and job.error not in ("LOAD_FAILED", "LOAD_INTERRUPTED"):
            job.error = "LOAD_FAILED"  # Redact errors persisted by the legacy prototype.
        if job.result_snapshot_id:
            identifier(job.result_snapshot_id)
        return job


class JobManager:
    def __init__(self, base_dir, *, input_dir=None, max_bytes=MAX_ARTIFACT_BYTES, max_jobs=10000):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.jobs_dir = self.base_dir / "jobs"
        self.snaps_dir = self.base_dir / "snapshots"
        self.lock_file = self.base_dir / "lock"
        self.input_dir = Path(input_dir).resolve(strict=True) if input_dir is not None else None
        self.max_bytes = unsigned_integer(max_bytes, maximum=MAX_ARTIFACT_BYTES)
        self.max_jobs = unsigned_integer(max_jobs, maximum=100000)
        self._thread_lock = threading.Lock()
        self._lock_handle = None
        for directory in (self.jobs_dir, self.snaps_dir):
            confined(self.base_dir, directory.name)
            directory.mkdir(mode=0o700, exist_ok=True)
        confined(self.base_dir, "lock")
        with self.lock_file.open("ab") as stream:
            if self.lock_file.stat().st_size == 0:
                stream.write(b"\0")
        # The OS releases the lock on process death. Recover only with exclusive ownership.
        if self._acquire_lock():
            try:
                self._recover()
            finally:
                self._release_lock()

    def _acquire_lock(self):
        if not self._thread_lock.acquire(blocking=False):
            return False
        handle = None
        try:
            confined(self.base_dir, "lock")
            handle = self.lock_file.open("r+b")
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_handle = handle
            return True
        except OSError:
            if handle is not None:
                handle.close()
            self._thread_lock.release()
            return False
        except BaseException:
            if handle is not None:
                handle.close()
            self._thread_lock.release()
            raise

    def _release_lock(self):
        handle, self._lock_handle = self._lock_handle, None
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._thread_lock.release()

    @contextmanager
    def _writer(self, *, wait=False):
        deadline = time.monotonic() + (5 if wait else 0)
        while not self._acquire_lock():
            if time.monotonic() >= deadline:
                raise WriterBusyError("Otro escritor está activo.")
            time.sleep(0.01)
        try:
            yield
        finally:
            self._release_lock()

    def _now(self):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _job_path(self, job_id):
        return confined(self.jobs_dir, identifier(job_id) + ".json")

    def _save_job(self, job):
        job.updated_at = self._now()
        atomic_json(self._job_path(job.job_id), job.to_dict())

    def _load_job(self, job_id):
        path = self._job_path(job_id)
        job = Job.from_dict(read_json(path, maximum=16384))
        if job.job_id != job_id:
            raise ValueError("Identidad del trabajo incompatible.")
        return job

    def _list_all_jobs(self):
        paths = sorted(self.jobs_dir.glob("*.json"))
        if len(paths) > self.max_jobs:
            raise ValueError("Inventario de trabajos fuera de límite.")
        return [self._load_job(p.stem) for p in paths]

    def list_jobs(self):
        return self._list_all_jobs()

    def submit_job(self, operation, snapshot_id, idempotency_key):
        if operation != "load":
            raise ValueError("Operación no registrada.")
        identifier(snapshot_id)
        if (
            not isinstance(idempotency_key, str)
            or not 1 <= len(idempotency_key) <= 256
            or any(ord(c) < 32 or ord(c) == 127 for c in idempotency_key)
        ):
            raise ValueError("Clave de idempotencia inválida.")
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        with self._writer(wait=True):
            existing_jobs = self._list_all_jobs()
            for existing in existing_jobs:
                if existing.idempotency_key == key_hash:
                    if existing.operation == operation and existing.snapshot_id == snapshot_id:
                        return existing
                    raise ValueError("Conflicto de idempotencia.")
            if len(existing_jobs) >= self.max_jobs:
                raise ValueError("Límite de trabajos alcanzado.")
            job = Job(
                uuid.uuid4().hex,
                key_hash,
                operation,
                snapshot_id,
                PENDING,
                self._now(),
                self._now(),
            )
            self._save_job(job)
            return job

    def get_job(self, job_id):
        return self._load_job(job_id)

    def cancel_job(self, job_id):
        with self._writer(wait=True):
            job = self._load_job(job_id)
            if job.state != PENDING:
                raise ValueError("Solo se cancela un trabajo pending; ya está " + job.state + ".")
            job.state = CANCELLED
            self._save_job(job)
            return job

    def _staging(self, job):
        return self.snaps_dir / f".staging-{identifier(job.snapshot_id)}-{identifier(job.job_id)}"

    def _cleanup(self, path):
        if path.parent != self.snaps_dir or not path.name.startswith(".staging-"):
            raise ValueError("Destino de limpieza inválido.")
        if path.exists():
            for member in (path, *path.rglob("*")):
                if member.is_symlink() or not member.resolve().is_relative_to(self.snaps_dir):
                    raise ValueError("No se limpian árboles con enlaces.")
            shutil.rmtree(path)

    def _recover(self):
        for job in self._list_all_jobs():
            if job.state != IN_PROGRESS:
                continue
            published = confined(self.snaps_dir, job.snapshot_id)
            if published.exists():
                document = read_json(published / "manifest.json")
                if document.get("producer_job_id") != job.job_id:
                    raise ValueError("Publicación recuperada con propietario incompatible.")
                manifest = SnapshotClient(self.snaps_dir).get_snapshot(job.snapshot_id)
                for ref in manifest.artifacts:
                    _verificar_artifact(confined(published, ref.file_path), ref)
                job.state, job.stage = COMPLETED, "recuperado"
                job.result_snapshot_id = job.snapshot_id
            else:
                job.state, job.stage, job.error = FAILED, "interrumpido", "LOAD_INTERRUPTED"
            self._cleanup(self._staging(job))
            self._save_job(job)

    def run_job(self, job_id, archivos):
        with self._writer():
            job = self._load_job(job_id)
            if job.state != PENDING:
                raise ValueError("Solo se ejecutan trabajos pending.")
            final = confined(self.snaps_dir, job.snapshot_id)
            staging = self._staging(job)
            job.state, job.stage = IN_PROGRESS, "validando"
            self._save_job(job)
            committed = False
            try:
                if final.exists():
                    raise SnapshotConflictError("El snapshot ya existe y es inmutable.")
                if not isinstance(archivos, dict) or not 1 <= len(archivos) <= MAX_ARTIFACTS:
                    raise ValueError("Inventario de archivos vacío o demasiado grande.")
                files, total = [], 0
                for table, value in archivos.items():
                    identifier(table)
                    source = Path(value)
                    if self.input_dir is not None:
                        if source.is_absolute():
                            raise ValueError(
                                "La API requiere rutas relativas a la entrada autorizada."
                            )
                        source = confined(self.input_dir, source.as_posix())
                    if source.suffix.lower() not in (".csv", ".parquet", ".arrow", ".json"):
                        raise ValueError("Formato de archivo no admitido.")
                    with open_regular(source) as stream:
                        size = os.fstat(stream.fileno()).st_size
                    unsigned_integer(size, maximum=self.max_bytes)
                    total += size
                    files.append((table, source, size))
                if (
                    total > self.max_bytes
                    or shutil.disk_usage(self.snaps_dir).free < total + 16 * 1024**2
                ):
                    raise ValueError("Presupuesto de bytes o disco insuficiente.")
                staging.mkdir(mode=0o700, exist_ok=False)
                entries = []
                for table, source, size in files:
                    target = staging / (table + source.suffix.lower())
                    h, remaining = hashlib.sha256(), size
                    with open_regular(source) as stream, target.open("xb") as output:
                        while remaining:
                            block = stream.read(min(1024 * 1024, remaining))
                            if not block:
                                raise ValueError("El archivo de entrada cambió de tamaño.")
                            output.write(block)
                            h.update(block)
                            remaining -= len(block)
                        if stream.read(1):
                            raise ValueError("El archivo de entrada cambió de tamaño.")
                        output.flush()
                        os.fsync(output.fileno())
                    entries.append(
                        {
                            "table_name": table,
                            "file_path": target.name,
                            "size_bytes": size,
                            "sha256": h.hexdigest(),
                            "version": job.snapshot_id,
                        }
                    )
                atomic_json(
                    staging / "manifest.json",
                    {
                        "snapshot_id": job.snapshot_id,
                        "version": job.snapshot_id,
                        "source": "equiframe-data",
                        "timestamp": self._now(),
                        "producer_job_id": job.job_id,
                        "artifacts": entries,
                    },
                )
                job.stage = "publicando"
                self._save_job(job)
                staging.rename(final)  # cooperating writers cannot replace an existing snapshot
                committed = True
                job.state, job.stage, job.result_snapshot_id = (
                    COMPLETED,
                    "completado",
                    job.snapshot_id,
                )
                self._save_job(job)
                return job
            except Exception as exc:
                if not committed:
                    self._cleanup(staging)
                    job.state, job.stage, job.error = FAILED, "fallido", "LOAD_FAILED"
                    self._save_job(job)
                # Persisted/public diagnostics never include input paths, values or exception text.
                logger.warning(
                    "job_failed id=%s kind=%s committed=%s frames=%s",
                    job.job_id,
                    type(exc).__name__,
                    committed,
                    safe_error_frames(exc),
                )
                raise
