"""Canonical strict JSON and exclusive append-only document publication."""

import json
from pathlib import Path

from equiframe._documents import save_document as save_document

from equiframe_benchmark.models import Document


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
