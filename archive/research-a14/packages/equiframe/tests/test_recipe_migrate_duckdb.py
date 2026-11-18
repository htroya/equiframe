"""Standalone bounded migration recipe: native execution, gates and safe evidence."""

import importlib.util
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import EXAMPLES

import equiframe as ef

SCRIPT = EXAMPLES / "migrate_duckdb_recipe.py"
EXPECTED = [
    {"currency": "EUR", "total": None, "rows": 2},
    {"currency": "JPY", "total": Decimal("0.00"), "rows": 1},
    {"currency": "USD", "total": Decimal("1000000000000000.03"), "rows": 3},
]


@pytest.fixture
def recipe():
    spec = importlib.util.spec_from_file_location("migrate_duckdb_recipe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(reference):
    return sorted(ef.read_table(reference).to_pylist(), key=lambda row: row["currency"])


@pytest.mark.parametrize(
    ("scenario", "state", "verification", "code"),
    [
        ("equivalent", "equivalent", "correct", 0),
        ("different", "equivalent", "divergent", 1),
        ("not_evaluable", "not_evaluable", "not_evaluable", 3),
    ],
)
def test_native_outputs_share_input_not_expected_and_survive_session(
    tmp_path, recipe, scenario, state, verification, code
):
    result = recipe.execute_migration(tmp_path, scenario)
    assert (result.state, result.verification, result.exit_code) == (state, verification, code)
    assert result.complete is (scenario != "not_evaluable")
    assert result.inputs[0].row_count == 6
    assert rows(result.expected) == EXPECTED
    for engine, pipeline in (("pandas", result.source), ("duckdb", result.target)):
        execution = pipeline.execution
        assert execution.state == "completed"
        assert execution.plan.engine == engine
        assert execution.inputs[0].data.sha256 == result.inputs[0].data.sha256
        assert execution.inputs[0].data.sha256 != result.expected.sha256
        actual = rows(execution.output.data)
        expected = [dict(row) for row in EXPECTED]
        if scenario == "different":
            expected[0]["total"] = Decimal("0.00")
        assert actual == expected
        assert execution.output.row_count == 3
        assert actual[2]["total"] == Decimal("1000000000000000.03")
        assert pipeline.rules.decision == "no_alert"
    # Reading materialized native captures here happens after DuckDB has returned
    # and closed its per-execution session. A live connection is not needed.
    assert ef.read_migration(tmp_path / result.migration_id) == result
    assert len(list(tmp_path.rglob("run.json"))) == 2
    if scenario == "different":
        for comparison in (result.verification_source, result.verification_target):
            assert comparison.state == "different" and comparison.counts.final
            differences = list(ef.iter_differences(comparison.differences))
            assert len(differences) == 1
            assert differences[0].column == "total"
    if scenario == "not_evaluable":
        for comparison in (
            result.comparison,
            result.verification_source,
            result.verification_target,
        ):
            assert comparison.state == "not_evaluable"
            assert not comparison.complete and not comparison.counts.final


def assert_redacted_bundle(directory, recipe, expected_state):
    assert {p.name for p in directory.iterdir()} == set(recipe.COMPARISONS)
    for label in recipe.COMPARISONS:
        folder = directory / label
        recipe.verify_report(folder)
        report = ef.read_comparison_report(folder / "report.json")
        state = "equivalent" if label == "source-target" else expected_state
        if expected_state == "not_evaluable":
            state = "not_evaluable"
        assert report.state == state
        assert report.evidence.values_withheld and report.evidence.metadata_withheld
        assert report.evidence.inspection == "verified_differences"
        for path in folder.iterdir():
            text = path.read_text("utf-8")
            for secret in ("USD", "EUR", "JPY", "1000000000000000", "file://", "orders"):
                assert secret not in text


@pytest.mark.parametrize(
    ("scenario", "code", "state"),
    [
        ("equivalent", 0, "equivalent"),
        ("different", 1, "different"),
        ("not_evaluable", 3, "not_evaluable"),
    ],
)
def test_copied_standalone_cli_preserves_gates_and_reports(tmp_path, recipe, scenario, code, state):
    copy = tmp_path / SCRIPT.name
    shutil.copyfile(SCRIPT, copy)
    report = tmp_path / "report"
    environment = {**os.environ, "PRIVATE_SENTINEL": "not-for-any-report"}
    environment.pop("PYTHONPATH", None)
    run = subprocess.run(
        [sys.executable, "-I", str(copy), "--case", scenario, "--output", str(report)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == code, run.stdout + run.stderr
    assert "Raw evidence was temporary and has been removed" in run.stdout
    assert "not-for-any-report" not in run.stdout + run.stderr
    assert "1000000000000000" not in run.stdout + run.stderr
    assert "human acceptance established" in run.stdout
    assert_redacted_bundle(report, recipe, state)


def test_raw_retention_and_opt_in_values_are_explicit(tmp_path, recipe, capsys):
    private = tmp_path / "private"
    assert recipe.run_recipe(tmp_path / "report", work_dir=private, show_values=True) == 0
    migrations = list(private.glob("migration_*"))
    assert len(migrations) == 1
    result = ef.read_migration(migrations[0])
    assert rows(result.expected) == EXPECTED
    text = capsys.readouterr().out
    assert "literal expected:" in text and "DuckDB candidate:" in text
    assert "1000000000000000.03" in text
    assert "Raw evidence retained separately" in text


def test_default_private_lifetime_ends_after_report_publication(tmp_path, recipe, monkeypatch):
    original = recipe.tempfile.TemporaryDirectory
    allocated = []

    def temporary(**kwargs):
        context = original(dir=tmp_path, **kwargs)
        allocated.append(Path(context.name))
        return context

    monkeypatch.setattr(recipe.tempfile, "TemporaryDirectory", temporary)
    report = tmp_path / "report"
    assert recipe.run_recipe(report) == 0
    assert allocated and all(not path.exists() for path in allocated)
    assert_redacted_bundle(report, recipe, "equivalent")


@pytest.mark.parametrize("relation", ["same", "raw_child", "report_child"])
def test_raw_evidence_must_be_separate(tmp_path, recipe, relation):
    report = tmp_path / "report"
    private = report
    if relation == "raw_child":
        private = report / "raw"
    elif relation == "report_child":
        private = tmp_path
    with pytest.raises(recipe.RecipeError, match="must be separate"):
        recipe.run_recipe(report, work_dir=private)
    assert not report.exists()


def test_existing_output_is_never_reused(tmp_path, recipe):
    report = tmp_path / "report"
    report.mkdir()
    private_file = report / "do-not-share"
    private_file.write_text("keep me", "utf-8")
    with pytest.raises(recipe.RecipeError, match="new report directory"):
        recipe.run_recipe(report)
    assert private_file.read_text("utf-8") == "keep me"


def test_failed_publication_is_not_a_successful_gate(tmp_path, recipe, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise OSError("private credential must not appear")

    monkeypatch.setattr(recipe.ef, "write_comparison_report", fail)
    with pytest.raises(recipe.RecipeError, match="No successful recipe gate") as error:
        recipe.run_recipe(tmp_path / "report")
    assert "private credential" not in str(error.value)
    assert "Redacted reports verified" not in capsys.readouterr().out
    assert not list((tmp_path / "report").rglob("evidence-manifest.json"))


def test_tampered_redacted_report_is_rejected(tmp_path, recipe):
    report = tmp_path / "report"
    assert recipe.run_recipe(report) == 0
    (report / "source-target" / "report.txt").write_text("modified", "utf-8")
    with pytest.raises(recipe.RecipeError, match="integrity"):
        recipe.verify_report(report / "source-target")
