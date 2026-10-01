"""Canonical strict JSON and exclusive append-only document publication."""

import json
import os
from pathlib import Path
from uuid import uuid4

from equiframe_benchmark.models import Document


def save_document(document: Document, path: Path) -> None:
    document = type(document).model_validate(document)
    data = json.dumps(
        document.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    temporary = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with temporary.open("xb") as stream:
            stream.write(data + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_document[T: Document](model: type[T], path: Path) -> T:
    data = path.read_bytes()
    json.loads(data, object_pairs_hook=_pairs, parse_constant=_constant)
    return model.model_validate_json(data)


def _constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant: " + value)
