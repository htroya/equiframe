"""
Configuración de rutas del Data Warehouse — acordadas con Jhair.

Todas las rutas son absolutas en la VM. Para pruebas locales se pueden
sobreescribir pasando las rutas como argumento a DWReader / DWWriter.
"""

from pathlib import Path

# ── Rutas acordadas con Jhair (VM: 157.137.227.1) ────────────────────────────

# Carpeta raíz del DW en la VM
DW_BASE_DIR: Path = Path("/home/ubuntu/datos/dw")

# Archivo DuckDB principal (Jhair lo genera con su ETL)
DW_FILE: Path = DW_BASE_DIR / "equiframe.duckdb"

# Carpeta de snapshots Parquet que Jhair publica (leídos con SnapshotClient)
DW_SNAPSHOTS_DIR: Path = DW_BASE_DIR / "snapshots"

# Carpeta de trabajos de carga (gestionada por JobManager)
DW_JOBS_DIR: Path = DW_BASE_DIR / "jobs"

# Archivo de lock para serializar escrituras
DW_LOCK_FILE: Path = DW_BASE_DIR / "equiframe.lock"
