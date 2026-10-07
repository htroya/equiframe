"""
Cliente de snapshots del DW de Jhair — equiframe-data (José).

Operaciones principales:
  get_snapshot(snapshot_id)        → manifiesto con tablas, tamaños y SHA-256
  download_artifact(ref, destino)  → descarga y verifica integridad antes de usar

Reglas:
  - Todas las tablas deben pertenecer a la misma versión del snapshot.
  - Si tamaño o SHA-256 no coinciden con el inventario, la copia se rechaza.
  - Las llaves privadas y credenciales nunca se guardan en este archivo.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path


# ── Tipos de datos ────────────────────────────────────────────────────────────

@dataclass
class ArtifactRef:
    """Referencia a un archivo dentro de un snapshot."""
    snapshot_id: str
    table_name: str
    file_path: str
    size_bytes: int
    sha256: str
    row_count: int | None = None


@dataclass
class SnapshotManifest:
    """Manifiesto inmutable de un snapshot del DW."""
    snapshot_id: str
    version: str
    source: str
    timestamp: str
    artifacts: list[ArtifactRef] = field(default_factory=list)

    def get_artifact(self, table_name: str) -> ArtifactRef | None:
        for a in self.artifacts:
            if a.table_name == table_name:
                return a
        return None


# ── Verificación de integridad ────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _verificar_artifact(path: Path, ref: ArtifactRef) -> None:
    """Verifica tamaño y SHA-256. Lanza ValueError si no coinciden."""
    size_real = path.stat().st_size
    if size_real != ref.size_bytes:
        raise ValueError(
            f"Tamaño incorrecto en '{path.name}': "
            f"esperado {ref.size_bytes} bytes, obtenido {size_real} bytes. "
            f"Copia rechazada."
        )
    sha_real = _sha256_file(path)
    if sha_real != ref.sha256:
        raise ValueError(
            f"SHA-256 incorrecto en '{path.name}': "
            f"esperado {ref.sha256}, obtenido {sha_real}. "
            f"Copia rechazada — el archivo puede estar corrupto o modificado."
        )


# ── Cliente principal ─────────────────────────────────────────────────────────

class SnapshotClient:
    """
    Cliente que accede a los snapshots del DW de Jhair.

    En producción, 'base_dir' apunta a la carpeta compartida en la VM
    donde Jhair publica los snapshots exportados como Parquet + manifiesto JSON.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def get_snapshot(self, snapshot_id: str) -> SnapshotManifest:
        """
        Pide el manifiesto de un snapshot concreto.
        Lanza FileNotFoundError si el snapshot no existe.
        Lanza ValueError si el manifiesto está malformado o mezcla versiones.
        """
        manifiesto_path = self.base_dir / snapshot_id / "manifest.json"
        if not manifiesto_path.exists():
            raise FileNotFoundError(
                f"Snapshot '{snapshot_id}' no encontrado en {self.base_dir}. "
                f"Verifica con Jhair que el snapshot fue publicado."
            )

        with open(manifiesto_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        # Validar que todas las tablas son de la misma versión
        versiones = {a.get("version", data.get("version")) for a in data.get("artifacts", [])}
        versiones.discard(None)
        if len(versiones) > 1:
            raise ValueError(
                f"El snapshot '{snapshot_id}' mezcla versiones: {versiones}. "
                f"Todas las tablas deben ser de la misma versión."
            )

        artifacts = [
            ArtifactRef(
                snapshot_id=snapshot_id,
                table_name=a["table_name"],
                file_path=a["file_path"],
                size_bytes=a["size_bytes"],
                sha256=a["sha256"],
                row_count=a.get("row_count"),
            )
            for a in data.get("artifacts", [])
        ]

        return SnapshotManifest(
            snapshot_id=snapshot_id,
            version=data.get("version", ""),
            source=data.get("source", ""),
            timestamp=data.get("timestamp", ""),
            artifacts=artifacts,
        )

    def download_artifact(self, ref: ArtifactRef, destino: Path) -> Path:
        """
        Descarga un archivo del snapshot y verifica tamaño + SHA-256.
        Rechaza la copia si no coinciden con el inventario de Jhair.
        Devuelve la ruta local del archivo verificado.
        """
        origen = self.base_dir / ref.snapshot_id / ref.file_path
        if not origen.exists():
            raise FileNotFoundError(
                f"Archivo '{ref.file_path}' no encontrado en el snapshot '{ref.snapshot_id}'."
            )

        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        archivo_local = destino / Path(ref.file_path).name

        shutil.copy2(origen, archivo_local)

        # Verificar integridad — rechaza si no coincide
        try:
            _verificar_artifact(archivo_local, ref)
        except ValueError:
            archivo_local.unlink(missing_ok=True)
            raise

        print(f"OK  {ref.table_name}: {archivo_local.name} ({ref.size_bytes:,} bytes, SHA-256 verificado)")
        return archivo_local


# ── Uso de ejemplo ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # Apunta a la carpeta de snapshots publicados por Jhair en la VM
    # En produccion: base_dir = Path("/home/ubuntu/datos/snapshots")
    base_dir = Path(__file__).parent / "snapshots_prueba"

    client = SnapshotClient(base_dir=base_dir)

    try:
        manifiesto = client.get_snapshot("20231001")
        print(f"Snapshot : {manifiesto.snapshot_id}")
        print(f"Version  : {manifiesto.version}")
        print(f"Fuente   : {manifiesto.source}")
        print(f"Timestamp: {manifiesto.timestamp}")
        print(f"Tablas   : {[a.table_name for a in manifiesto.artifacts]}")

        destino = Path(__file__).parent / "descargados"
        for artifact in manifiesto.artifacts:
            client.download_artifact(artifact, destino)

        print("\nTodas las tablas descargadas y verificadas correctamente.")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except ValueError as e:
        print(f"RECHAZO: {e}")
