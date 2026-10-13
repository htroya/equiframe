"""Public API for the private data integration component."""

if __package__:
    from .job_manager import Job, JobManager
    from .snapshot_client import ArtifactRef, SnapshotClient, SnapshotManifest
else:
    from job_manager import Job, JobManager
    from snapshot_client import ArtifactRef, SnapshotClient, SnapshotManifest

__all__ = [
    "SnapshotClient",
    "SnapshotManifest",
    "ArtifactRef",
    "JobManager",
    "Job",
]
