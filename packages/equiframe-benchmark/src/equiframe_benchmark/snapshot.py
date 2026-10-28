"""Compatibility aliases for the generic pinned-snapshot API now in core.

Existing imports and manifest format 1.0 remain supported. New integrations may
use equiframe.snapshot without installing this experimental package.
"""

from equiframe.snapshot import (
    SnapshotClient as SnapshotClient,
)
from equiframe.snapshot import (
    SnapshotColumn as SnapshotColumn,
)
from equiframe.snapshot import (
    SnapshotDataSource as SnapshotDataSource,
)
from equiframe.snapshot import (
    SnapshotManifest as SnapshotManifest,
)
from equiframe.snapshot import (
    SnapshotTable as SnapshotTable,
)
from equiframe.snapshot import (
    snapshot_fingerprint as snapshot_fingerprint,
)
