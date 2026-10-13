"""
Servicio de cargas y publicación de snapshots — equiframe data-gateway.

Endpoints:
  POST   /jobs                  → registrar un trabajo (devuelve job_id)
  GET    /jobs                  → listar todos los trabajos
  GET    /jobs/{job_id}         → estado de un trabajo
  POST   /jobs/{job_id}/run     → ejecutar la carga
  DELETE /jobs/{job_id}         → cancelar un trabajo pendiente
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "equiframe-data"))

from job_manager import JobManager, PENDING, COMPLETED, FAILED, CANCELLED

BASE_DIR = Path(__file__).parent / "data"
manager = JobManager(BASE_DIR)

app = FastAPI(
    title="EquiFrame Data Gateway",
    description="Servicio de cargas con garantía de escritor único y publicación atómica de snapshots.",
    version="1.0.0",
)


# ── Modelos de entrada ────────────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    operation: str
    snapshot_id: str
    idempotency_key: str


class RunRequest(BaseModel):
    archivos: dict[str, str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/jobs", status_code=201)
def submit_job(req: SubmitRequest):
    """Registra un trabajo de carga. Misma clave + mismos datos → mismo job_id."""
    try:
        job = manager.submit_job(req.operation, req.snapshot_id, req.idempotency_key)
        return job.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/jobs")
def list_jobs():
    """Lista todos los trabajos con su estado actual."""
    jobs = manager._list_all_jobs()
    return [j.to_dict() for j in sorted(jobs, key=lambda j: j.created_at)]


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Devuelve el estado actual de un trabajo."""
    try:
        return manager.get_job(job_id).to_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")


@app.post("/jobs/{job_id}/run")
def run_job(job_id: str, req: RunRequest):
    """
    Ejecuta la carga de datos para un trabajo pendiente.
    'archivos' es un dict {nombre_tabla: ruta_absoluta_del_archivo}.
    Un solo proceso puede escribir a la vez.
    """
    try:
        archivos = {tabla: Path(ruta) for tabla, ruta in req.archivos.items()}
        job = manager.run_job(job_id, archivos)
        return job.to_dict()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    """Cancela un trabajo pendiente."""
    try:
        job = manager.cancel_job(job_id)
        return job.to_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
def health():
    """Comprueba que el servicio está activo."""
    return {"status": "ok", "base_dir": str(BASE_DIR)}
