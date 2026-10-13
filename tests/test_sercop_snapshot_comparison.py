"""Snapshot counterexamples: metadata-only, exact numeric scale and new packages."""

import importlib.util
import zipfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "snapshots", Path(__file__).parents[1] / "tools/sercop_snapshot_comparison.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def archive(path, payload):
    with zipfile.ZipFile(path, "x") as bundle:
        bundle.writestr("source.json", payload)
    return path


def test_metadata_changes_are_separate_from_complete_equal_release_arrays(tmp_path):
    old = archive(
        tmp_path / "old.zip",
        '[{"publishedDate":"old","releases":[{"amount":9007199254740993.001,"id":"x"}]}]',
    )
    new = archive(
        tmp_path / "new.zip",
        '[{"publishedDate":"new","releases":[{"amount":9007199254740993.001,"id":"x"}]}]',
    )
    result = tool.compare_packages(old, new, tmp_path / "metadata-result")
    assert result["release_arrays_equal"] and result[
        "changed_package_metadata_keys"
    ] == {"publishedDate": 1}
    assert result["counts"]["equal_release_arrays"] == 1


def test_numeric_scale_signed_zero_and_unpaired_packages_are_not_hidden(tmp_path):
    old = archive(tmp_path / "old.zip", '[{"releases":[{"amount":1.00,"zero":-0}]}]')
    new = archive(
        tmp_path / "new.zip",
        '[{"releases":[{"amount":1.0,"zero":0}]},{"releases":[{"id":"extra"}]}]',
    )
    result = tool.compare_packages(old, new, tmp_path / "different-result")
    assert result["release_arrays_equal"] is False
    assert result["counts"]["different_release_arrays"] == 1
    assert result["counts"]["unpaired_packages"] == 1
    assert result["counts"]["old_release_occurrences"] == 1
    assert result["counts"]["new_release_occurrences"] == 2
