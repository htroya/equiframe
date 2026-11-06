"""
EquiFrame Portal API — FastAPI
Ejecutar en la VM:
    cd /home/ubuntu/equiframe/packages/equiframe-portal
    source /home/ubuntu/venv312/bin/activate
    pip install fastapi uvicorn
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "equiframe-data"))

from api.config import API_PREFIX, ALLOWED_ORIGINS, DW_FILE  # noqa: E402
from api.routers import sercop, demos                         # noqa: E402

app = FastAPI(
    title="EquiFrame Portal API",
    version="1.0.0",
    description="API de datos SERCOP–OCDS 2025 y demostraciones EquiFrame",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(sercop.router, prefix=API_PREFIX)
app.include_router(demos.router,  prefix=API_PREFIX)


@app.get("/")
def raiz():
    return {"api": "EquiFrame Portal", "version": "1.0.0", "prefix": API_PREFIX}


@app.get("/health")
def health():
    """Estado del servicio y disponibilidad del DW."""
    dw_ok = DW_FILE.exists()
    return JSONResponse(
        status_code=200 if dw_ok else 503,
        content={
            "status": "ok" if dw_ok else "degradado",
            "dw_disponible": dw_ok,
            "dw_ruta": str(DW_FILE),
            "mensaje": None if dw_ok else (
                "El DW no está disponible. Jhair debe ejecutar el ETL."
            ),
        }
    )
