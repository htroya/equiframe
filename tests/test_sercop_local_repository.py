"""Real counterexamples for complete local SERCOP occurrence extraction."""

import importlib.util
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

SPEC = importlib.util.spec_from_file_location(
    "sercop_local", Path(__file__).parents[1] / "tools/sercop_local_repository.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_flat_transport_encoding_has_exact_original_bytes_and_rejects_inference():
    row = {
        "ñ/key": 'escaped\\quote"\n\t',
        "missing": None,
        "index": 123,
        "payload": '{"amount":9007199254740993.001,"zero":-0,"tiny":1E-30}',
    }
    assert tool.row_json(row) == tool.exact_json(row)
    for value in (1.0, True, [], {}, Decimal("1.00")):
        with pytest.raises(ValueError):
            tool.row_json({"scalar": value})


def test_exact_numbers_and_escaped_field_names_remain_distinct():
    source = {
        "amount": Decimal("9007199254740993.001"),
        "signed": Decimal("-0"),
        "tiny": Decimal("1E-30"),
        "a/b": None,
        "a~b": False,
        "empty": {},
        "items": [],
    }
    serialized = tool.exact_json(source)
    assert "9007199254740993.001" in serialized
    assert '"signed":-0' in serialized
    assert json.loads(serialized, parse_float=Decimal, parse_int=Decimal) == source
    values = tool.fields(source)
    assert values["/amount"] == ("9007199254740993.001", "number_exact_decimal_text")
    assert values["/a~1b"] == (None, "null")
    assert values["/a~0b"] == ("false", "boolean")
    assert "/absent" not in values


def test_full_zip_extraction_preserves_duplicates_positions_missing_and_null(tmp_path):
    archive = tmp_path / "source.zip"
    payload = (
        '[{"license":"fixture","releases":[{"ocid":"o","id":"r","awards":['
        '{"id":"a","value":{"amount":9007199254740993.001,"currency":"USD"},"suppliers":[{"id":"s"}]},'
        '{"id":"a","value":null},{"id":"a"}]}]}]'
    )
    with zipfile.ZipFile(archive, "x") as bundle:
        bundle.writestr("releases.json", payload)
    repository = tmp_path / "repository"
    tool.build(archive, repository)
    catalog = json.loads(
        next(repository.glob("02_tablas/*/catalog.json")).read_text("utf-8")
    )
    assert catalog["releases"] == 1
    assert catalog["award_occurrences"] == 3
    assert catalog["duplicates_dropped"] is False
    awards = next(t for t in catalog["tables"] if t["collection"] == "releases/awards")
    rows = pq.read_table(repository / awards["file"]).to_pylist()
    assert [r["/id"] for r in rows] == ["a", "a", "a"]
    assert len({r["__row_path"] for r in rows}) == 3
    assert rows[0]["/value/amount"] == "9007199254740993.001"
    assert rows[1]["@type:/value"] == "null"
    assert rows[2]["@type:/value"] == "missing"
    assert all(r["__parent_row_path"] == "/packages/0/releases/0" for r in rows)
    suppliers = next(
        t for t in catalog["tables"] if t["collection"].endswith("/suppliers")
    )
    supplier = pq.read_table(repository / suppliers["file"]).to_pylist()[0]
    assert supplier["__parent_row_path"] == rows[0]["__row_path"]


def test_metadata_unknown_fields_and_scalar_arrays_are_not_dropped(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "x") as bundle:
        bundle.writestr(
            "releases.json",
            '[{"extension":"custom","releases":[{"id":"r","ocid":"o","new":{"codes":["x",null,false]}}]}]',
        )
    repository = tmp_path / "repository"
    tool.build(archive, repository)
    catalog = json.loads(
        next(repository.glob("02_tablas/*/catalog.json")).read_text("utf-8")
    )
    table = next(
        t for t in catalog["tables"] if t["collection"] == "releases/new/codes"
    )
    rows = pq.read_table(repository / table["file"]).to_pylist()
    assert [json.loads(r["__payload_json"]) for r in rows] == ["x", None, False]
    packages = next(t for t in catalog["tables"] if t["collection"] == "packages")
    assert (
        pq.read_table(repository / packages["file"]).to_pylist()[0]["/extension"]
        == "custom"
    )
