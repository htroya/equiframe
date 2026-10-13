"""
Ejemplo de uso de SnapshotClient — leer awards_2025.parquet del DW.

Uso:
    python ejemplo_awards.py [base_dir]

    base_dir: carpeta raíz de snapshots publicados por Hernan.
              Por defecto apunta a la VM: /home/ubuntu/datos/snapshots
              En Windows local para pruebas: pasa la ruta como argumento.
"""

import sys
from pathlib import Path

# Permite ejecutar el script directamente sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from snapshot_client import SnapshotClient

# ── Configuración ──────────────────────────────────────────────────────────────

# Ruta donde Hernan publica los snapshots del DW
BASE_DIR_VM = Path("/home/ubuntu/datos/snapshots")

# Ruta del artefacto dentro del snapshot (confirmada con Jhair)
ARTIFACT_PATH = "dataset/anual/parquet/awards_2025.parquet"

# Carpeta local donde se descarga temporalmente el archivo
DESCARGA_LOCAL = Path(__file__).parent / "descargados"

# ── Script principal ───────────────────────────────────────────────────────────

def main() -> None:
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR_VM
    client = SnapshotClient(base_dir=base_dir)

    # 1. Listar versiones disponibles y elegir la más reciente
    versiones = client.list_snapshots()
    if not versiones:
        print(f"No hay snapshots publicados en {base_dir}")
        sys.exit(1)

    version = versiones[0]
    print(f"Snapshots disponibles : {versiones}")
    print(f"Usando version        : {version}")

    # 2. Leer el manifiesto del snapshot
    manifiesto = client.get_snapshot(version)
    print(f"Timestamp del snapshot: {manifiesto.timestamp}")
    print(f"Tablas en el snapshot :")
    for a in manifiesto.artifacts:
        print(f"  - {a.file_path}  ({a.row_count:,} filas, {a.size_bytes:,} bytes)")

    # 3. Localizar el artefacto awards_2025.parquet
    ref = next(
        (a for a in manifiesto.artifacts if a.file_path == ARTIFACT_PATH),
        None,
    )
    if ref is None:
        print(f"\nArtefacto '{ARTIFACT_PATH}' no encontrado en el snapshot '{version}'.")
        print("Rutas disponibles:")
        for a in manifiesto.artifacts:
            print(f"  {a.file_path}")
        sys.exit(1)

    # 4. Descargar y verificar integridad (SHA-256 + tamaño del manifiesto de Hernan)
    print(f"\nDescargando {ARTIFACT_PATH} ...")
    ruta_local = client.download_artifact(ref, DESCARGA_LOCAL)
    print(f"Archivo local         : {ruta_local}")

    # 5. Leer el Parquet y mostrar estructura
    try:
        import polars as pl
        df = pl.read_parquet(ruta_local)
        print(f"\n--- awards_2025.parquet ---")
        print(f"Filas    : {len(df):,}")
        print(f"Columnas : {df.width}")
        print(f"\nNombres de columnas:")
        for col in df.columns:
            print(f"  {col}  ({df[col].dtype})")
        print(f"\nPrimeras 3 filas:")
        print(df.head(3))
    except ImportError:
        # Fallback a pandas si polars no está instalado
        import pandas as pd
        df = pd.read_parquet(ruta_local)
        print(f"\n--- awards_2025.parquet ---")
        print(f"Filas    : {len(df):,}")
        print(f"Columnas : {len(df.columns)}")
        print(f"\nNombres de columnas:")
        for col, dtype in df.dtypes.items():
            print(f"  {col}  ({dtype})")
        print(f"\nPrimeras 3 filas:")
        print(df.head(3))


if __name__ == "__main__":
    main()
