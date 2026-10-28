"""Canonical strict JSON and exclusive append-only document publication."""

import json
from pathlib import Path
from typing import TypeVar

from equiframe._documents import save_document as save_document
from pydantic import BaseModel

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_document(model: type[_ModelT], path: Path) -> _ModelT:
    data = path.read_bytes()
    json.loads(data, object_pairs_hook=_pairs, parse_constant=_constant)
    return model.model_validate_json(data)


def _constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant: " + value)
