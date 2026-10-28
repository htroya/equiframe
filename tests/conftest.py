import json
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
EXAMPLES = PACKAGE / "examples"


def document(family: str = "nulls_types") -> dict[str, object]:
    result: dict[str, object] = json.loads((EXAMPLES / (family + ".json")).read_text("utf-8"))
    return result


def at(root: object, *path: str | int) -> object:
    result = root
    for part in path:
        if isinstance(part, int):
            assert isinstance(result, list)
        else:
            assert isinstance(result, dict)
        result = result[part]
    return result


def change(
    root: dict[str, object], path: tuple[str | int, ...], value: object
) -> dict[str, object]:
    target = at(root, *path[:-1])
    if isinstance(path[-1], int):
        assert isinstance(target, list)
    else:
        assert isinstance(target, dict)
    target[path[-1]] = value
    return root


@pytest.fixture
def valid_document() -> dict[str, object]:
    return document()
