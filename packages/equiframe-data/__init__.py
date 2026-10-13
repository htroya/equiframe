"""
equiframe-data — componente de acceso a datos del DW (José).

API pública:
    SnapshotClient  → seleccionar versión, consultar tablas, descargar archivos
    JobManager      → gestionar trabajos de carga con escritor único
    DWReader        → consultas SQL en modo lectura (múltiples procesos seguros)
    DWWriter        → escrituras serializadas con lock de proceso
"""

from .snapshot_client import SnapshotClient, SnapshotManifest, ArtifactRef
from .job_manager import JobManager, Job
from .dw_access import DWReader, DWWriter

__all__ = [
    "SnapshotClient",
    "SnapshotManifest",
    "ArtifactRef",
    "JobManager",
    "Job",
    "DWReader",
    "DWWriter",
]
