"""Counterexamples for full native readback against source CSV oracles."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "consumer", Path(__file__).parents[1] / "tools/sercop_local_consumer.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_complete_readback_detects_value_type_missing_duplicate_and_count_changes():
    rows = [{"id": "A", "amount": "9007199254740993.001"}, {"id": "B", "amount": ""}]
    literal = '{"amount":"9007199254740993.001","id":"A"}\n{"amount":"","id":"B"}\n'
    expected = {
        "rows": 2,
        "source_row_sha256": hashlib.sha256(literal.encode()).hexdigest(),
    }
    assert tool.verify_rows(iter(rows), ["id", "amount"], expected) == (
        2,
        expected["source_row_sha256"],
    )
    for wrong in (
        rows[:1],
        [rows[0], rows[0]],
        [{**rows[0], "amount": 9007199254740993.0}, rows[1]],
        [rows[0], {"id": "B", "amount": None}],
    ):
        with pytest.raises(ValueError):
            tool.verify_rows(iter(wrong), ["id", "amount"], expected)
