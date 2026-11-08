"""Meaningful loss and path counterexamples for the local export organizer."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "exports", Path(__file__).parents[1] / "tools/sercop_local_exports.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_complete_text_csv_preserves_precision_order_duplicates_and_empty(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text(
        'id,amount,description\nA,9007199254740993.001,"line1\nline2"\n\nA,9007199254740993.001,"line1\nline2"\nB,-0,\n',
        encoding="utf-8",
        newline="",
    )
    expected = [
        {"id": "A", "amount": "9007199254740993.001", "description": "line1\nline2"},
        {"id": "A", "amount": "9007199254740993.001", "description": "line1\nline2"},
        {"id": "B", "amount": "-0", "description": ""},
    ]
    assert list(tool.csv_rows(path)) == expected
    report = tool.text_csv(path, tmp_path / "table.parquet")
    import pyarrow.parquet as pq

    assert report["rows"] == 3 and report["full_readback_verified"]
    assert pq.read_table(tmp_path / "table.parquet").to_pylist() == expected


def test_ambiguous_header_and_wrong_width_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    for contents in ("x,x\n1,2\n", "x,y\n1\n"):
        path.write_text(contents, encoding="utf-8")
        with pytest.raises(ValueError):
            list(tool.csv_rows(path))


def test_archive_path_cannot_escape_destination(tmp_path):
    for name in ("../other", "/other", "C:/other", "folder\\other"):
        with pytest.raises(ValueError):
            tool.safe_member(tmp_path, name)
    assert tool.safe_member(tmp_path, "data/source.csv") == tmp_path / "data/source.csv"
