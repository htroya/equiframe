"""Synthetic repeat-use checks do not assert that humans adopted the package."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal

import pytest
from conftest import EXAMPLES

import equiframe as ef

SCRIPT = EXAMPLES / "adoption_replay.py"
SENTINEL = "private-environment-or-error-message"


def symlink_or_skip(link, target, *, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable on this host: {error}")


@pytest.fixture
def recipe():
    spec = importlib.util.spec_from_file_location("adoption_replay", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def replay(recipe, tmp_path):
    output = tmp_path / "replay"
    return output, recipe.run_replay(output, wheel_sha256="a" * 64)


def test_all_contexts_repeat_changed_input_under_unchanged_contract(recipe, replay):
    output, receipt = replay
    assert receipt["technical_pass"] is True
    assert receipt["exit_code"] == 0
    assert len(receipt["observations"]) == 24
    expected = {
        "equivalent": ("equivalent", True, True, 0, None),
        "different": ("different", True, False, 1, "EquivalenceDifferentError"),
        "invalid_expected": ("not_evaluable", True, False, 3, "EquivalenceNotEvaluableError"),
        "resource_limited": ("not_evaluable", False, False, 3, "EquivalenceNotEvaluableError"),
    }
    for row in receipt["observations"]:
        actual = row["observed"]
        assert (
            tuple(
                actual[key]
                for key in (
                    "state",
                    "complete",
                    "accepted",
                    "gate_code",
                    "assertion",
                )
            )
            == expected[row["case"]]
        )
        assert row["observed"] == row["expected"]
        assert row["technical_pass"] and row["error_type"] is None
        assert row["evidence_status"] == "verified"
        assert row["contract_revision"] == 1
        assert row["human_contract_review"] == "not_claimed"
        assert len(row["captured_sha256"]["candidate"]) == 64
        if row["case"] == "resource_limited":
            # The real row-budget stop happens before the right capture is
            # compared; a missing observed reference must stay missing.
            assert row["captured_sha256"]["expected"] is None
        else:
            assert len(row["captured_sha256"]["expected"]) == 64
        assert row["report_sha256"] == recipe.verify_report(output / row["id"])
        if row["case"] == "invalid_expected":
            assert row["literal_expected_sha256"] != row["compared_expected_sha256"]
        else:
            assert row["literal_expected_sha256"] == row["compared_expected_sha256"]
    for context in ("refactor_python", "sql_duckdb", "ci_regression"):
        rows = [row for row in receipt["observations"] if row["context"] == context]
        assert len({row["contract_sha256"] for row in rows}) == 1
        assert len({row["declaration_sha256"] for row in rows}) == 1
        assert len({row["input_sha256"] for row in rows}) == 2
        assert len({row["literal_expected_sha256"] for row in rows}) == 2
    assert all(
        row["input_changed"] and row["literal_expected_changed"] and row["same_declaration"]
        for row in receipt["repeat_checks"]
    )


def test_receipt_and_closed_reports_keep_redaction_and_human_gates(replay):
    output, receipt = replay
    assert json.loads((output / "receipt.json").read_bytes()) == receipt
    assert receipt["kind"] == "synthetic_replay"
    assert receipt["human_adoption"] is False
    assert receipt["production_ci_job"] is False
    assert receipt["independent_human_confirmation"] is False
    assert receipt["human_reporting_awareness"] == "pending"
    assert receipt["human_upgrading_awareness"] == "pending"
    assert receipt["human_integration_effort"] is None
    provenance = receipt["provenance"]
    assert provenance["wheel_sha256"] == "a" * 64
    assert provenance["wheel_binding"] == "runner_supplied_not_verified_here"
    assert provenance["script_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert provenance["imports"]["equiframe"]["file"] == ef.__file__
    assert all(item["file"] and item["version"] for item in provenance["imports"].values())
    assert {path.name for path in output.iterdir()} == {
        "receipt.json",
        *(row["id"] for row in receipt["observations"]),
    }
    for row in receipt["observations"]:
        report_dir = output / row["id"]
        assert len(list(report_dir.iterdir())) == 4
        report = ef.read_comparison_report(report_dir / "report.json")
        assert report.evidence.values_withheld and report.evidence.metadata_withheld
        for path in report_dir.iterdir():
            text = path.read_text()
            for private in (SENTINEL, "café", "niño", "unit_price", "equiframe-replay-private-"):
                assert private not in text
            assert "file://" not in text
    assert not list(output.rglob("*.arrow"))
    assert not list(output.rglob("*.jsonl"))


@pytest.mark.parametrize("phase", ["initial", "follow_up"])
def test_duckdb_capture_survives_mutated_dropped_source_and_preserves_exact_rows(
    recipe, tmp_path, phase
):
    source, expected = recipe.fixture("sql_duckdb", phase)
    captured = recipe.materialize("sql_duckdb", source, expected, fault=False, private=tmp_path)
    rows = ef.read_table(captured.data).to_pylist()
    amount = Decimal("30.30") if phase == "follow_up" else Decimal("20.20")
    assert rows.count({"id": "café", "value": amount}) == 2
    assert {"id": "空", "value": None} in rows
    assert {"id": "", "value": Decimal("0.00")} in rows
    if phase == "follow_up":
        assert {"id": "new", "value": Decimal("2.25")} in rows
    assert len(rows) == (6 if phase == "follow_up" else 5)


@pytest.mark.parametrize("context", ["refactor_python", "ci_regression"])
def test_repeat_expected_is_literal_and_deliberate_bug_does_not_mutate_it(
    recipe, tmp_path, context
):
    source, expected = recipe.fixture(context, "follow_up")
    before = expected.to_pylist()
    assert expected["value"].to_pylist() == (
        [1000, 5000, 3000, 1000] if context == "refactor_python" else [6, 0, 10, 16]
    )
    recipe.materialize(context, source, expected, fault=True, private=tmp_path)
    assert expected.to_pylist() == before


def test_swallowed_assertion_failure_cannot_pass_replay(recipe, monkeypatch, tmp_path):
    monkeypatch.setattr(ef, "assert_equivalent", lambda *args, **kwargs: None)
    row = recipe.run_case("ci_regression", "follow_up", "different", tmp_path)
    assert row["technical_pass"] is False
    assert row["observed"]["state"] == "different"
    assert row["observed"]["accepted"] is False
    assert row["observed"]["gate_code"] == 0
    assert row["expected"]["gate_code"] == 1
    assert row["report_sha256"]


def test_report_failure_keeps_real_verdict_and_suppresses_private_error(
    recipe, monkeypatch, tmp_path
):
    def fail(*args, **kwargs):
        raise OSError(SENTINEL)

    monkeypatch.setattr(ef, "write_comparison_report", fail)
    row = recipe.run_case("ci_regression", "initial", "different", tmp_path)
    assert row["technical_pass"] is False
    assert row["stage"] == "report"
    assert row["observed"]["state"] == "different"
    assert row["observed"]["assertion"] == "not_run"
    assert row["error_type"] == "OSError"
    assert SENTINEL not in json.dumps(row)


def test_materialization_failure_is_retained_and_other_contexts_still_run(
    recipe, monkeypatch, tmp_path
):
    real = recipe.materialize

    def fail_one(context, *args, **kwargs):
        if context == "refactor_python":
            raise RuntimeError(SENTINEL)
        return real(context, *args, **kwargs)

    monkeypatch.setattr(recipe, "materialize", fail_one)
    receipt = recipe.run_replay(tmp_path / "failed")
    assert receipt["exit_code"] == 2 and receipt["technical_pass"] is False
    assert len(receipt["observations"]) == 24
    assert sum(row["technical_pass"] for row in receipt["observations"]) == 16
    failed = receipt["observations"][0]
    assert failed["stage"] == "materialize" and failed["observed"] is None
    assert failed["error_type"] == "RuntimeError"
    assert SENTINEL not in (tmp_path / "failed" / "receipt.json").read_text()


def test_repeating_identical_fixture_is_not_repeat_use_evidence(recipe, monkeypatch, tmp_path):
    real = recipe.fixture
    monkeypatch.setattr(recipe, "fixture", lambda context, phase: real(context, "initial"))
    receipt = recipe.run_replay(tmp_path / "unchanged")
    assert all(row["technical_pass"] for row in receipt["observations"])
    assert receipt["technical_pass"] is False and receipt["exit_code"] == 2
    assert all(not row["input_changed"] for row in receipt["repeat_checks"])


@pytest.mark.parametrize("kind", ["extra", "missing", "corrupt", "symlink"])
def test_report_verifier_rejects_open_or_corrupted_inventory(recipe, tmp_path, kind):
    row = recipe.run_case("ci_regression", "initial", "different", tmp_path)
    report = tmp_path / row["id"]
    if kind == "extra":
        (report / "extra-private.json").write_text(SENTINEL)
    elif kind == "missing":
        (report / "report.html").unlink()
    elif kind == "corrupt":
        (report / "report.txt").write_text(SENTINEL)
    else:
        target = tmp_path / "outside.txt"
        target.write_text(SENTINEL)
        (report / "report.txt").unlink()
        symlink_or_skip(report / "report.txt", target)
    with pytest.raises(recipe.ReplayError):
        recipe.verify_report(report)


def test_output_and_hash_validation_do_not_overwrite_evidence(recipe, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    prior = output / "receipt.json"
    prior.write_text("previous failed attempt")
    with pytest.raises(recipe.ReplayError, match="new output"):
        recipe.run_replay(output)
    assert prior.read_text() == "previous failed attempt"
    with pytest.raises(recipe.ReplayError, match="SHA-256"):
        recipe.run_replay(tmp_path / "invalid", wheel_sha256="not-a-hash")
    assert not (tmp_path / "invalid").exists()


def test_linked_output_is_rejected(recipe, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    link = tmp_path / "linked"
    symlink_or_skip(link, output, directory=True)
    with pytest.raises(recipe.ReplayError, match="symlink"):
        recipe.run_replay(link / "nested")
    assert not (output / "nested").exists()


def test_standalone_copy_executes_without_sibling_recipe_imports(tmp_path):
    script = tmp_path / "adoption_replay.py"
    shutil.copyfile(SCRIPT, script)
    response = subprocess.run(
        [sys.executable, "-I", str(script), "--output", "evidence"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "EQUIFRAME_PRIVATE_TEST_VALUE": SENTINEL},
    )
    assert response.returncode == 0, response.stdout + response.stderr
    assert "Synthetic repeat-use replay: passed" in response.stdout
    assert response.stderr == ""
    assert SENTINEL not in response.stdout
    receipt = json.loads((tmp_path / "evidence" / "receipt.json").read_bytes())
    assert receipt["provenance"]["wheel_sha256"] is None
    assert receipt["provenance"]["wheel_binding"] == "not_supplied"
    assert receipt["provenance"]["script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    assert SENTINEL not in json.dumps(receipt)
