"""Bridge verified local transport to the core's explicit schema contract."""

import os
import tempfile
from pathlib import Path


class CoreSnapshotClient:
    """An operator supplies a core manifest with independently declared schema/rows.

    This bridge does not infer business types, silently convert CSV or approve
    domain semantics. Core remains independent of this optional component.
    """

    def __init__(self, client, manifest):
        import equiframe as ef

        self._client = client
        self._manifest = ef.SnapshotManifest.model_validate(manifest)
        local = client.get_snapshot(self._manifest.snapshot_id)
        available = {a.table_name: a for a in local.artifacts}
        if set(available) != {t.name for t in self._manifest.tables}:
            raise ef.ArtifactIntegrityError("Core and local inventories differ.")
        self._references = {}
        for table in self._manifest.tables:
            ref = available[table.name]
            artifact = table.artifact
            if (
                artifact.sha256 != ref.sha256
                or artifact.size_bytes != ref.size_bytes
                or artifact.format not in ("arrow", "parquet")
                or Path(ref.file_path).suffix != "." + artifact.format
                or (ref.row_count is not None and ref.row_count != table.row_count)
                or artifact.uri in self._references
            ):
                raise ef.ArtifactIntegrityError("Core artifact differs from the pinned inventory.")
            self._references[artifact.uri] = (artifact, ref)

    def get_snapshot(self, snapshot_id):
        if snapshot_id != self._manifest.snapshot_id:
            raise ValueError("Only the pinned snapshot can be requested.")
        return self._manifest

    def download_artifact(self, ref, destination):
        import equiframe as ef

        registered = self._references.get(ref.uri)
        if registered is None or registered[0] != ref:
            raise ef.ArtifactIntegrityError("Unregistered core artifact reference.")
        destination = Path(destination)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Destination must be new.")
        with tempfile.TemporaryDirectory(prefix=".transport-", dir=destination.parent) as folder:
            verified = self._client.download_artifact(registered[1], Path(folder))
            os.link(verified, destination)
