"""Shared local document I/O with unchanged historical byte and error contracts.

This module does not serialize models or canonicalize JSON. Each caller keeps
its existing encoding, newline policy, fingerprint and format version.
"""

import json
import os
from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4

from equiframe._regular_io import local_input_path, open_regular_file, regular_directory
from equiframe.errors import ArtifactIOError, ResourceLimitError
from equiframe.serialization import _constant, _JsonObject, _unique_objects


def write_document(path: Path, payload: bytes) -> None:
    """Publish exclusively. A previous profile or bundle is never overwritten."""
    write_document_chunks(path, (payload,))


def write_document_chunks(path: Path, payloads: Iterable[bytes]) -> None:
    """Publish byte chunks exclusively; iterator failures never publish a prefix."""
    path = local_input_path(path)
    try:
        regular_directory(path.parent)
    except ArtifactIOError as error:
        cause = error.__cause__
        if isinstance(cause, OSError):
            raise type(cause)(cause.errno, "document directory cannot be used") from None
        raise
    temporary = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with temporary.open("xb") as output:
            for payload in payloads:
                output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_document(path: Path) -> bytes:
    try:
        with open_regular_file(path) as stream:
            raw = stream.read(64 * 1024 * 1024 + 1)
    except ArtifactIOError as error:
        # Keep the original OS-error contract used by profile/detector and
        # benchmark readers, while omitting filenames and external messages.
        cause = error.__cause__
        if isinstance(cause, OSError):
            raise type(cause)(cause.errno, "document cannot be read") from None
        raise
    if len(raw) > 64 * 1024 * 1024:
        raise ResourceLimitError("document exceeds the 64 MiB read budget")
    _unique_objects(
        json.loads(raw.decode("utf-8"), object_pairs_hook=_JsonObject, parse_constant=_constant)
    )
    return raw
