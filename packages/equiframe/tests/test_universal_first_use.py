"""Complete source interchange, explanatory discrepancies and failed inputs."""

import importlib
import json

import pytest
from conftest import EXAMPLES


@pytest.mark.parametrize("case,expected_code", [("good", 0), ("different", 1), ("corrupt", 3)])
def test_universal_example_has_eighteen_real_native_runs(
    tmp_path, monkeypatch, case, expected_code
):
    monkeypatch.syspath_prepend(str(EXAMPLES / "integrations"))
    demo = importlib.import_module("universal_first_use")
    output = tmp_path / case
    assert demo.run_demo(output, case) == expected_code
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    assert len(receipt["runs"]) == 18
    assert {r["engine"] for r in receipt["runs"]} == {"pandas", "polars", "duckdb"}
    for run in receipt["runs"]:
        if case == "different" and run["source"] == "sqlite":
            assert run["execution_state"] == "completed" and run["comparison_state"] == "different"
        elif case == "corrupt" and run["source"] == "api_response":
            assert run["execution_state"] != "completed" and run["comparison_state"] is None
            assert run["problem"]["code"] == "artifact_integrity_error"
        else:
            assert run["execution_state"] == "completed" and run["comparison_state"] == "equivalent"
            assert run["comparison_complete"] is True
