"""
Gestor de trabajos de carga del DW — equiframe-data (José).

Garantías:
  - Un solo proceso escribe a la vez (lock en archivo).
  - Si la carga falla, la versión anterior del snapshot queda disponible.
  - Cada trabajo tiene un estado visible: pending, in_progress, completed, failed.
  - Peticiones repetidas con la misma clave no duplican la carga (idempotencia).
"""

import json
import os
import sys
import uuid
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict


# ── Estados de un trabajo ─────────────────────────────────────────────────────

PENDING     = "pending"
IN_PROGRESS = "in_progress"
COMPLETED   = "completed"
FAILED      = "failed"
CANCELLED   = "cancelled"


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

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Job":
        return Job(**d)


# ── Gestor principal ──────────────────────────────────────────────────────────

class JobManager:
    """
    Gestiona trabajos de carga con un único escritor a la vez.

    Estructura en disco:
      base_dir/
        jobs/           ← un JSON por trabajo
        snapshots/
          <id>/         ← snapshot publicado (inmutable)
          <id>.tmp/     ← carga en curso (temporal)
        lock            ← archivo de bloqueo del escritor
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir  = Path(base_dir)
        self.jobs_dir  = self.base_dir / "jobs"
        self.snaps_dir = self.base_dir / "snapshots"
        self.lock_file = self.base_dir / "lock"

        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.snaps_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file.touch(exist_ok=True)

    # ── Lock multiplataforma ──────────────────────────────────────────────────

    def _acquire_lock(self) -> bool:
        """Intenta adquirir el lock exclusivo. Devuelve True si lo obtuvo."""
        pid_file = self.lock_file.with_suffix(".pid")
        try:
            pid_file.write_text(str(os.getpid()), encoding="utf-8")
            self._lock_pid = pid_file
            return True
        except Exception:
            return False

    def _release_lock(self) -> None:
        pid_file = self.lock_file.with_suffix(".pid")
        try:
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _save_job(self, job: Job) -> None:
        job.updated_at = self._now()
        self._job_path(job.job_id).write_text(
            json.dumps(job.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_job(self, job_id: str) -> Job:
        path = self._job_path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"Trabajo '{job_id}' no encontrado.")
        return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _idempotency_hash(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    # ── API pública ───────────────────────────────────────────────────────────

    def submit_job(self, operation: str, snapshot_id: str, idempotency_key: str) -> Job:
        """
        Registra un trabajo de carga.
        Si ya existe un trabajo con la misma clave e igual contenido,
        devuelve ese trabajo sin duplicar la carga.
        """
        key_hash = self._idempotency_hash(idempotency_key)

        # Buscar trabajo existente con la misma clave
        for existing in self._list_all_jobs():
            if existing.idempotency_key == key_hash:
                if existing.operation == operation and existing.snapshot_id == snapshot_id:
                    print(f"Trabajo existente reutilizado: {existing.job_id}")
                    return existing
                else:
                    raise ValueError(
                        f"Clave '{idempotency_key}' ya usada con otro contenido. Conflicto."
                    )

        job = Job(
            job_id          = str(uuid.uuid4())[:8],
            idempotency_key = key_hash,
            operation       = operation,
            snapshot_id     = snapshot_id,
            state           = PENDING,
            created_at      = self._now(),
            updated_at      = self._now(),
        )
        self._save_job(job)
        print(f"Trabajo registrado: {job.job_id} | {operation} | snapshot={snapshot_id}")
        return job

    def get_job(self, job_id: str) -> Job:
        """Devuelve el estado actual de un trabajo."""
        return self._load_job(job_id)

    def cancel_job(self, job_id: str) -> Job:
        """Cancela un trabajo pendiente. No cancela uno ya en progreso."""
        job = self._load_job(job_id)
        if job.state == IN_PROGRESS:
            raise ValueError(f"Trabajo '{job_id}' ya está en progreso — no se puede cancelar.")
        if job.state in (COMPLETED, FAILED, CANCELLED):
            raise ValueError(f"Trabajo '{job_id}' ya terminó con estado '{job.state}'.")
        job.state = CANCELLED
        self._save_job(job)
        print(f"Trabajo cancelado: {job_id}")
        return job

    def run_job(self, job_id: str, archivos: dict[str, Path]) -> Job:
        """
        Ejecuta un trabajo de carga con un único escritor a la vez.

        'archivos' es un dict {nombre_tabla: ruta_archivo_parquet/csv}.

        Si la carga falla, la versión anterior del snapshot permanece intacta.
        """
        job = self._load_job(job_id)
        if job.state != PENDING:
            raise ValueError(f"Solo se pueden ejecutar trabajos en estado '{PENDING}'. Estado actual: '{job.state}'.")

        snap_final = self.snaps_dir / job.snapshot_id
        snap_tmp   = self.snaps_dir / f"{job.snapshot_id}.tmp"

        # Bloqueo — un solo escritor a la vez
        acquired = self._acquire_lock()
        if not acquired:
            raise RuntimeError(
                "Otro proceso está cargando datos. "
                "Solo un escritor puede operar a la vez. Intenta más tarde."
            )
        try:

            try:
                # Marcar como en progreso
                job.state = IN_PROGRESS
                job.stage = "iniciando"
                self._save_job(job)

                # Preparar carpeta temporal
                if snap_tmp.exists():
                    shutil.rmtree(snap_tmp)
                snap_tmp.mkdir(parents=True)

                # Copiar archivos a carpeta temporal
                job.stage = "copiando archivos"
                self._save_job(job)

                manifest_artifacts = []
                for tabla, ruta in archivos.items():
                    ruta = Path(ruta)
                    destino = snap_tmp / ruta.name
                    shutil.copy2(ruta, destino)

                    # Calcular SHA-256 y tamaño
                    size = destino.stat().st_size
                    h = hashlib.sha256()
                    with open(destino, "rb") as f:
                        for bloque in iter(lambda: f.read(1 << 20), b""):
                            h.update(bloque)

                    manifest_artifacts.append({
                        "table_name": tabla,
                        "file_path":  ruta.name,
                        "size_bytes": size,
                        "sha256":     h.hexdigest(),
                        "version":    job.snapshot_id,
                    })
                    print(f"  Copiado: {tabla} ({size:,} bytes)")

                # Guardar manifiesto en carpeta temporal
                job.stage = "generando manifiesto"
                self._save_job(job)

                manifiesto = {
                    "snapshot_id": job.snapshot_id,
                    "version":     job.snapshot_id,
                    "source":      "equiframe-data",
                    "timestamp":   self._now(),
                    "artifacts":   manifest_artifacts,
                }
                (snap_tmp / "manifest.json").write_text(
                    json.dumps(manifiesto, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

                # Publicar: renombrar tmp → final (operación atómica)
                job.stage = "publicando snapshot"
                self._save_job(job)

                if snap_final.exists():
                    shutil.rmtree(snap_final)
                snap_tmp.rename(snap_final)

                # Completado
                job.state              = COMPLETED
                job.stage              = "completado"
                job.result_snapshot_id = job.snapshot_id
                self._save_job(job)
                print(f"Snapshot '{job.snapshot_id}' publicado correctamente.")

            except Exception as e:
                # Si falla: limpiar tmp, versión anterior intacta
                if snap_tmp.exists():
                    shutil.rmtree(snap_tmp)
                job.state = FAILED
                job.stage = "fallido"
                job.error = str(e)
                self._save_job(job)
                print(f"ERROR en trabajo {job_id}: {e}")
                print("La version anterior del snapshot permanece disponible.")
                raise

        finally:
            self._release_lock()

        return job

    def _list_all_jobs(self) -> list[Job]:
        return [
            Job.from_dict(json.loads(p.read_text(encoding="utf-8")))
            for p in self.jobs_dir.glob("*.json")
        ]

    def list_jobs(self) -> None:
        """Muestra el estado de todos los trabajos."""
        jobs = sorted(self._list_all_jobs(), key=lambda j: j.created_at)
        if not jobs:
            print("No hay trabajos registrados.")
            return
        print(f"{'ID':<10} {'Estado':<12} {'Snapshot':<12} {'Etapa':<20} {'Actualizado'}")
        print("-" * 75)
        for j in jobs:
            print(f"{j.job_id:<10} {j.state:<12} {j.snapshot_id:<12} {j.stage:<20} {j.updated_at}")


# ── Prueba local ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    base = Path(__file__).parent / "jobs_prueba"
    mgr  = JobManager(base_dir=base)

    # Archivo de prueba
    archivo_prueba = Path(__file__).parent / "snapshots_prueba" / "20231001" / "fact_adjudicacion.csv"

    print("=== Registrar trabajo ===")
    job = mgr.submit_job("load", "snap-001", idempotency_key="carga-inicial-001")
    print(f"Job ID: {job.job_id}\n")

    print("=== Idempotencia: misma clave no duplica ===")
    job2 = mgr.submit_job("load", "snap-001", idempotency_key="carga-inicial-001")
    print(f"Mismo job devuelto: {job.job_id == job2.job_id}\n")

    print("=== Ejecutar carga ===")
    mgr.run_job(job.job_id, {"fact_adjudicacion": archivo_prueba})
    print()

    print("=== Estado de trabajos ===")
    mgr.list_jobs()
