"""Shared local document I/O with unchanged historical byte and error contracts.

This module does not serialize models or canonicalize JSON. Each caller keeps
its existing encoding, newline policy, fingerprint and format version.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from equiframe.serialization import _constant, _JsonObject, _unique_objects


def write_document(path: Path, payload: bytes) -> None:
    """Publish exclusively. A previous profile or bundle is never overwritten."""
    temporary = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_document(path: Path) -> bytes:
    raw = path.read_bytes()
    _unique_objects(
        json.loads(raw.decode("utf-8"), object_pairs_hook=_JsonObject, parse_constant=_constant)
    )
    return raw
