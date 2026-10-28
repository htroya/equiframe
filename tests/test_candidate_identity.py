"""Current package identity must not mislabel new detector evidence as history."""

import runpy
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

import equiframe as ef


@pytest.mark.parametrize(
    "version",
    [
        "0.7.0",
        "0.8.0",
        "0.8.1",
        "0.9.0",
        "0.10.0",
        "0.11.0",
        "0.11.1",
        "0.12.0a1",
        "0.12.0a2",
        "0.12.0a3",
        "0.12.0a4",
        "0.12.0a5",
        "0.12.0a6",
        "0.12.0a7",
        "0.12.0a8",
        "0.12.0a9",
        "0.12.0a10",
        "0.12.0a11",
        "0.12.0a12",
        "0.12.0a13",
        "0.12.0a14",
        "0.12.0",
        "0.12.1",
        "0.12.2",
        "0.12.3",
    ],
)
def test_detector_producer_history_remains_readable(version: str) -> None:
    record = ef.DetectorVersions(equiframe=version, python="3.12.14")
    restored = ef.DetectorVersions.model_validate_json(record.model_dump_json())
    assert restored.equiframe == version


def test_current_detector_producer_matches_candidate_metadata() -> None:
    config = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text("utf-8"))
    assert ef.DetectorVersions(python="3.12.14").equiframe == ef.__version__
    assert config["project"]["dynamic"] == ["version"] and "version" not in config["project"]
    backend = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "release_version.py"))
    assert backend["project_version"](Path(__file__).parents[1]) == ef.__version__ == "0.12.4"


def test_unknown_detector_producer_is_not_silently_accepted() -> None:
    with pytest.raises(ValidationError):
        ef.DetectorVersions(equiframe="99.0.0", python="3.12.14")  # type: ignore[arg-type]
