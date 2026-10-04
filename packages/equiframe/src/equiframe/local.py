"""Local-only artifact storage; verified, exclusive copies without overwrites."""

import hashlib
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from uuid import uuid4

from equiframe._base import Text
from equiframe.errors import ArtifactIntegrityError, ArtifactIOError, CapabilityError
from equiframe.types import ArtifactRef

_FORMATS = {".json": "json", ".jsonl": "jsonl", ".arrow": "arrow", ".parquet": "parquet"}
_BUNDLE_PATHS: ContextVar[Mapping[str, Path] | None] = ContextVar("bundle_paths", default=None)


@contextmanager
def _bundle_paths(paths: Mapping[str, Path]) -> Iterator[None]:
    """Resolve only verified bundle members, restoring scope even after a failure."""
    token = _BUNDLE_PATHS.set(dict(paths))
    try:
        yield
    finally:
        _BUNDLE_PATHS.reset(token)


def local_path(ref: ArtifactRef) -> Path:
    mapping = _BUNDLE_PATHS.get()
    if mapping is not None:
        if ref.uri not in mapping:
            raise ArtifactIntegrityError("artifact reference is outside the portable inventory")
        return mapping[ref.uri]
    parts = urlsplit(ref.uri)
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        raise CapabilityError("only local file URIs are supported; remote access is unavailable")
    decoded = unquote(parts.path)
    if decoded.startswith("//") or "\\" in decoded:
        raise CapabilityError("network/UNC paths are not supported")
    return Path(url2pathname(parts.path))


def _copy(source: Path, destination: Path, expected: ArtifactRef | None = None) -> tuple[str, int]:
    temporary = destination.with_name(destination.name + "." + uuid4().hex + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, temporary.open("xb") as writer:
            while block := reader.read(1024 * 1024):
                writer.write(block)
                digest.update(block)
                size += len(block)
            writer.flush()
            os.fsync(writer.fileno())
        if expected and (digest.hexdigest() != expected.sha256 or size != expected.size_bytes):
            raise ArtifactIntegrityError("artifact bytes do not match declared SHA-256/size")
        # Atomic publication that fails if destination exists, including concurrent writers.
        os.link(temporary, destination)
        return digest.hexdigest(), size
    except (OSError, ValueError) as error:
        raise ArtifactIOError(
            "cannot copy/publish local artifact: " + type(error).__name__
        ) from error
    finally:
        temporary.unlink(missing_ok=True)


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, path: Path, *, media_type: str) -> ArtifactRef:
        from pydantic import TypeAdapter

        media_type = TypeAdapter(Text).validate_python(media_type, strict=True)
        format_name = _FORMATS.get(path.suffix.lower())
        if format_name is None:
            raise CapabilityError("supported artifact suffixes: .json, .jsonl, .arrow, .parquet")
        destination = self.root / (uuid4().hex + path.suffix.lower())
        sha256, size = _copy(path, destination)
        return ArtifactRef.model_validate(
            {
                "schema_version": "1.0",
                "uri": destination.as_uri(),
                "sha256": sha256,
                "format": format_name,
                "media_type": media_type,
                "size_bytes": size,
            }
        )

    def get(self, ref: ArtifactRef, destination: Path) -> Path:
        ref = ArtifactRef.model_validate(ref)
        _copy(local_path(ref), destination, ref)
        return destination
