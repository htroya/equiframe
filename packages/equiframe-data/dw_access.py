"""
Acceso controlado al Data Warehouse DuckDB — equiframe-data (José).

Garantías:
  - Múltiples lectores simultáneos: DWReader abre en modo read_only.
  - Escritura serializada: DWWriter adquiere el lock del JobManager
    antes de abrir la conexión, evitando corrupción por escritores concurrentes.

Uso rápido:
    from dw_access import DWReader, DWWriter
    from dw_config import DW_FILE, DW_JOBS_DIR

    # Leer (seguro para múltiples procesos)
    with DWReader(DW_FILE) as db:
        df = db.query("SELECT * FROM fact_adjudicacion LIMIT 10")

    # Cargar (un solo escritor a la vez)
    with DWWriter(DW_FILE, jobs_dir=DW_JOBS_DIR) as db:
        db.execute("INSERT INTO ...")
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import duckdb
    _DUCKDB_AVAILABLE = True
except ImportError:
    _DUCKDB_AVAILABLE = False


def _require_duckdb() -> None:
    if not _DUCKDB_AVAILABLE:
        raise ImportError(
            "duckdb no está instalado. Ejecuta: pip install duckdb"
        )


# ── Lectura (múltiples procesos simultáneos) ──────────────────────────────────

class DWReader:
    """
    Conexión de solo lectura al DW DuckDB.
    Segura para usarse desde varios procesos/scripts al mismo tiempo.
    """

    def __init__(self, dw_file: Path) -> None:
        _require_duckdb()
        self._path = Path(dw_file)
        self._conn = None

    def __enter__(self) -> "DWReader":
        if not self._path.exists():
            raise FileNotFoundError(
                f"Base DW no encontrada en '{self._path}'. "
                f"Confirma con Jhair que la ruta es correcta y el ETL corrió."
            )
        self._conn = duckdb.connect(database=str(self._path), read_only=True)
        return self

    def __exit__(self, *_) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def query(self, sql: str):
        """Ejecuta una consulta SQL y devuelve un DataFrame de Polars."""
        if self._conn is None:
            raise RuntimeError("DWReader debe usarse como context manager (with).")
        try:
            import polars as pl
            return self._conn.execute(sql).pl()
        except ImportError:
            return self._conn.execute(sql).df()  # fallback a pandas

    def tables(self) -> list[str]:
        """Lista las tablas disponibles en el DW."""
        result = self._conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [row[0] for row in result]


# ── Escritura serializada (un solo proceso a la vez) ──────────────────────────

class DWWriter:
    """
    Conexión de escritura al DW DuckDB con lock de proceso.

    Antes de abrir la conexión escribe el PID en un archivo .lock.
    Si otro proceso ya tiene el lock, lanza RuntimeError en lugar
    de corromper la base de datos.
    """

    def __init__(self, dw_file: Path, jobs_dir: Path) -> None:
        _require_duckdb()
        self._path     = Path(dw_file)
        self._lock     = Path(jobs_dir) / "equiframe.lock.pid"
        self._conn     = None
        self._acquired = False

    def __enter__(self) -> "DWWriter":
        # Crear directorio si no existe
        self._lock.parent.mkdir(parents=True, exist_ok=True)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Verificar si ya hay un escritor activo
        if self._lock.exists():
            existing_pid = self._lock.read_text(encoding="utf-8").strip()
            raise RuntimeError(
                f"Otro proceso (PID {existing_pid}) ya está escribiendo en el DW. "
                f"Solo un escritor puede operar a la vez. "
                f"Si el proceso terminó de forma inesperada, elimina: {self._lock}"
            )

        # Adquirir lock
        self._lock.write_text(str(os.getpid()), encoding="utf-8")
        self._acquired = True

        # Abrir conexión de escritura
        self._conn = duckdb.connect(database=str(self._path), read_only=False)
        return self

    def __exit__(self, exc_type, *_) -> None:
        if self._conn:
            if exc_type is None:
                self._conn.commit()
            else:
                # Rollback implícito al cerrar sin commit
                pass
            self._conn.close()
            self._conn = None

        if self._acquired:
            self._lock.unlink(missing_ok=True)
            self._acquired = False

    def execute(self, sql: str, params=None):
        """Ejecuta una sentencia SQL de escritura (INSERT, CREATE, etc.)."""
        if self._conn is None:
            raise RuntimeError("DWWriter debe usarse como context manager (with).")
        if params:
            return self._conn.execute(sql, params)
        return self._conn.execute(sql)

    def executemany(self, sql: str, data: list):
        """Inserta múltiples filas eficientemente."""
        if self._conn is None:
            raise RuntimeError("DWWriter debe usarse como context manager (with).")
        return self._conn.executemany(sql, data)


# ── Ejemplo de uso ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from dw_config import DW_FILE, DW_JOBS_DIR

    print(f"DW esperado en: {DW_FILE}")
    print(f"Lock en       : {DW_JOBS_DIR / 'equiframe.lock.pid'}")

    if not DW_FILE.exists():
        print("\nArchivo DW no encontrado — esto es normal en desarrollo local.")
        print("Confirma con Jhair la ruta en la VM y que su ETL ya corrió.")
    else:
        print("\nConectando en modo lectura...")
        with DWReader(DW_FILE) as db:
            tablas = db.tables()
            print(f"Tablas disponibles: {tablas}")
            for tabla in tablas:
                df = db.query(f"SELECT COUNT(*) AS filas FROM {tabla}")
                print(f"  {tabla}: {df}")
