"""Complete structural integration port; implementation belongs to later steps."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from equiframe.types import ArtifactRef

if TYPE_CHECKING:
    from equiframe.execution import RunContext
    from equiframe.execution_types import EngineCapabilities
    from equiframe.registry import Transformation
    from equiframe.tables import LoadedTable


class ArtifactStore(Protocol):
    def put(self, path: Path, *, media_type: str) -> ArtifactRef: ...

    def get(self, ref: ArtifactRef, destination: Path) -> Path: ...


class DataSource(Protocol):
    @property
    def table_names(self) -> tuple[str, ...]: ...

    def resolve(self, name: str, *, context: RunContext) -> LoadedTable: ...


class EngineAdapter(Protocol):
    @property
    def engine(self) -> str: ...

    def capabilities(self) -> EngineCapabilities: ...

    def execute(
        self, transformation: Transformation, inputs: Mapping[str, LoadedTable], context: RunContext
    ) -> LoadedTable: ...
