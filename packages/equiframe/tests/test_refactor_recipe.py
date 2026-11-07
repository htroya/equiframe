"""First-use diagnosis uses public APIs, exact policies and synthetic fixtures."""

import importlib.util
import json
import subprocess
import sys

import pytest
from conftest import EXAMPLES

import equiframe as ef

SCRIPT = EXAMPLES / "refactor_comparison.py"


@pytest.fixture
def recipe():
    spec = importlib.util.spec_from_file_location("refactor_comparison", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("scenario,expected_exit", [("equivalent", 0), ("different", 1)])
@pytest.mark.parametrize("without_key", [False, True])
@pytest.mark.parametrize("redacted", [False, True])
def test_standalone_refactor_diagnosis(tmp_path, scenario, expected_exit, without_key, redacted):
    output = tmp_path / "report"
    args = [sys.executable, str(SCRIPT), "--case", scenario, "--output", str(output)]
    if without_key:
        args.append("--without-key")
    if redacted:
        args.append("--redacted")
    response = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert response.returncode == expected_exit, response.stdout + response.stderr
    report = ef.read_comparison_report(output / "report" / "report.json")
    assert report.state == scenario and report.complete
    assert report.evidence.acceptance == "satisfied"
    assert report.evidence.values_withheld == redacted
    assert report.evidence.metadata_withheld == redacted
    counts = {item.name: item for item in report.counts}
    assert counts["modified_rows"].value == (None if without_key else int(scenario == "different"))
    declaration = ef.DiffContract.model_validate_json((output / "contract.json").read_bytes())
    amount = declaration.spec.contract.output.schema_spec.columns[1]
    assert amount.numeric_policy.comparison == "exact"
    assert amount.numeric_policy.unit == "USD_cent"
    assert amount.logical_type.bits == 64
    assert declaration.spec.contract.output.schema_spec.multiplicity == "preserve"
    assert not list(output.rglob("*.arrow"))
    assert not list(output.rglob("*.jsonl"))
    if scenario == "different" and not redacted:
        assert "integer(2001)" in response.stdout and "integer(2000)" in response.stdout
        assert "int64" in response.stdout and '"exact"' in response.stdout
        assert '"B"' in response.stdout
    if redacted:
        assert "integer(2001)" not in response.stdout
        assert "USD_cent" not in (output / "report" / "report.txt").read_text()
    assert "Traceback" not in response.stderr


def test_keyed_and_bag_contracts_preserve_occurrences_and_reject_lost_types(tmp_path, recipe):
    import pandas as pd

    candidate, expected = recipe.materialize(fault=False)
    duplicate = pd.concat([candidate, candidate.iloc[[0]]], ignore_index=True)
    for without_key in (False, True):
        declaration = recipe.declaration(without_key=without_key)
        result = ef.diff(duplicate, expected, contract=declaration, work_dir=tmp_path)
        assert result.state == "different"
        with pytest.raises(ef.EquivalenceDifferentError):
            ef.assert_equivalent(result)
    candidate["total_cents"] = candidate["total_cents"].astype("float64")
    changed_type = ef.diff(candidate, expected, contract=recipe.declaration(), work_dir=tmp_path)
    assert changed_type.state == "different"
    assert any(
        item.code == "logical_type" for item in ef.iter_differences(changed_type.differences)
    )


def test_reference_validity_and_budget_cannot_become_success(tmp_path, recipe):
    import pandas as pd

    candidate, expected = recipe.materialize(fault=False)
    invalid = pd.concat([expected, expected.iloc[[0]]], ignore_index=True)
    result = ef.diff(candidate, invalid, contract=recipe.declaration(), work_dir=tmp_path)
    assert result.state == "not_evaluable" and result.complete
    with pytest.raises(ef.EquivalenceNotEvaluableError):
        ef.assert_equivalent(result)
    limited = ef.diff(
        candidate,
        expected,
        contract=recipe.declaration(),
        work_dir=tmp_path,
        options=ef.ComparisonOptions(max_rows=1),
    )
    assert limited.state == "not_evaluable" and not limited.complete
    for item in (result, limited):
        with pytest.raises(TypeError):
            bool(item)


def test_evidence_retained_only_when_requested_and_never_overwritten(tmp_path, recipe):
    output, private = tmp_path / "report", tmp_path / "private"
    recipe.run_recipe(output, fault=False, work_dir=private)
    assert list(private.rglob("comparison.json"))
    before = (output / "report" / "report.json").read_bytes()
    with pytest.raises(ValueError, match="new output"):
        recipe.run_recipe(output, fault=True, work_dir=private)
    assert (output / "report" / "report.json").read_bytes() == before
    manifest = json.loads((output / "report" / "evidence-manifest.json").read_text())
    assert manifest["publication_complete"]


@pytest.mark.parametrize("direction", ["equal", "nested", "parent"])
def test_raw_and_report_overlap_is_rejected(tmp_path, recipe, direction):
    output = tmp_path / "new"
    private = (
        output if direction == "equal" else (output / "raw" if direction == "nested" else tmp_path)
    )
    with pytest.raises(ValueError, match="separate"):
        recipe.run_recipe(output, work_dir=private)


def test_missing_pandas_is_sanitized_setup_failure(tmp_path, recipe, monkeypatch, capsys):
    import builtins

    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "pandas":
            raise ImportError("synthetic-private-install-path")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(tmp_path / "report")])
    assert recipe.main() == 2
    output = capsys.readouterr()
    assert "Recipe failed before acceptance" in output.err
    assert "Traceback" not in output.err
    assert "synthetic-private-install-path" not in output.err
    assert output.out == ""
