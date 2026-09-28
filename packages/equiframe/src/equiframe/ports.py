"""Complete structural integration port; implementation belongs to later steps."""

from pathlib import Path
from typing import Protocol

from equiframe.types import ArtifactRef


class ArtifactStore(Protocol):
    def put(self, path: Path, *, media_type: str) -> ArtifactRef: ...

    def get(self, ref: ArtifactRef, destination: Path) -> Path: ...
