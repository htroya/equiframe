"""
Configuración de la API — rutas del DW y parámetros de operación.
Ajustar DW_FILE si Jhair cambia la ruta en la VM.
"""
import sys
from pathlib import Path

# Permite importar equiframe-data desde la VM o localmente
_ROOT = Path(__file__).resolve().parents[3]
_DATA_PKG = _ROOT / "packages" / "equiframe-data"
if str(_DATA_PKG) not in sys.path:
    sys.path.insert(0, str(_DATA_PKG))

from dw_config import DW_FILE, DW_JOBS_DIR  # noqa: E402

# ── Parámetros de la API ──────────────────────────────────────────────────
API_VERSION  = "v1"
API_PREFIX   = f"/api/{API_VERSION}"
SNAPSHOT_ID  = "test_20231001"  # actualizar cuando Jhair publique nueva versión

# ── Límites de paginación ─────────────────────────────────────────────────
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50

# ── Orígenes permitidos (CORS) ────────────────────────────────────────────
# Agregar el dominio de Cloudflare Pages cuando esté desplegado
ALLOWED_ORIGINS = [
    "http://localhost:7890",
    "http://127.0.0.1:7890",
    "http://localhost:5173",   # Vite dev (futuro)
    "*",                       # Quitar en producción
]
