"""
equiframe-data — componente de acceso a datos del DW (José).

API pública:
    SnapshotClient  → seleccionar versión, consultar tablas, descargar archivos
    JobManager      → gestionar trabajos de carga con escritor único
"""

from .snapshot_client import SnapshotClient, SnapshotManifest, ArtifactRef
from .job_manager import JobManager, Job

__all__ = [
    "SnapshotClient",
    "SnapshotManifest",
    "ArtifactRef",
    "JobManager",
    "Job",
]
