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
from equiframe._regular_io import (
    local_input_path,
    new_directory_path,
    open_regular_file,
    regular_directory,
)
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
    source = local_input_path(source)
    destination = local_input_path(destination)
    new_directory_path(destination.parent)
    temporary = destination.with_name(destination.name + "." + uuid4().hex + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with open_regular_file(source) as reader:
            destination.parent.mkdir(parents=True, exist_ok=True)
            regular_directory(destination.parent)
            with temporary.open("xb") as writer:
                while True:
                    capacity = 1024 * 1024
                    if expected is not None:
                        capacity = min(capacity, expected.size_bytes - size + 1)
                    block = reader.read(capacity)
                    if not block:
                        break
                    if expected is not None and size + len(block) > expected.size_bytes:
                        raise ArtifactIntegrityError("artifact exceeds its declared byte size")
                    writer.write(block)
                    digest.update(block)
                    size += len(block)
                writer.flush()
                os.fsync(writer.fileno())
        if expected is not None and (
            digest.hexdigest() != expected.sha256 or size != expected.size_bytes
        ):
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
        if not isinstance(root, Path):
            raise TypeError("artifact store root must be a Path")
        self.root = new_directory_path(local_input_path(root))

    def put(self, path: Path, *, media_type: str) -> ArtifactRef:
        from pydantic import TypeAdapter

        if not isinstance(path, Path):
            raise TypeError("artifact input must be a Path")
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
        if not isinstance(destination, Path):
            raise TypeError("artifact destination must be a Path")
        ref = ArtifactRef.model_validate(ref)
        _copy(local_path(ref), destination, ref)
        return destination
