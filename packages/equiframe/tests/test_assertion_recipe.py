"""Real subprocess evidence for the opt-in pytest and sanitized CI recipe."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import EXAMPLES

import equiframe as ef

SCRIPT = EXAMPLES / "assertion_ci.py"
PYTEST_RECIPE = EXAMPLES / "test_assertion_recipe.py"
ALLOWED = {"report.json", "report.html", "report.txt", "evidence-manifest.json"}
SENTINEL = "synthetic-environment-private-marker"


@pytest.fixture
def recipe():
    spec = importlib.util.spec_from_file_location("assertion_ci", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_safe_report(path: Path, state: str) -> None:
    assert {item.name for item in path.iterdir()} == ALLOWED
    receipt = json.loads((path / "evidence-manifest.json").read_text())
    assert receipt["publication_complete"] is True
    assert {item["path"] for item in receipt["files"]} == ALLOWED - {"evidence-manifest.json"}
    for item in receipt["files"]:
        content = (path / item["path"]).read_bytes()
        assert item["size_bytes"] == len(content)
        assert item["sha256"] == hashlib.sha256(content).hexdigest()
    report = ef.read_comparison_report(path / "report.json")
    assert report.state == state
    assert report.evidence.values_withheld and report.evidence.metadata_withheld
    assert report.evidence.inspection == "verified_differences"
    for file in path.iterdir():
        text = file.read_text()
        for private in (
            SENTINEL,
            "North depot",
            "South depot",
            "West depot",
            "private-raw",
            "quantity",
        ):
            assert private not in text
        assert "file://" not in text
        assert "reproduction/" not in text


@pytest.mark.parametrize(
    ("scenario", "code", "state"),
    [
        ("equivalent", 0, "equivalent"),
        ("different", 1, "different"),
        ("not_evaluable", 3, "not_evaluable"),
    ],
)
def test_ci_subprocess_publishes_redacted_report_before_failed_assertion(
    tmp_path, scenario, code, state
):
    output = tmp_path / "upload"
    private = tmp_path / "private-raw"
    response = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case",
            scenario,
            "--output",
            str(output),
            "--work-dir",
            str(private),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "EQUIFRAME_PRIVATE_TEST_VALUE": SENTINEL},
        check=False,
    )
    assert response.returncode == code, response.stderr
    assert_safe_report(output, state)
    assert any(private.rglob("comparison.json"))
    assert not list(output.rglob("*.arrow"))
    assert not list(output.rglob("*.jsonl"))
    if code:
        assert json.dumps(str(output / "report.html"), ensure_ascii=True) in response.stderr
        assert response.stdout == ""
    else:
        assert "Complete equivalence accepted" in response.stdout
        assert response.stderr == ""
    assert SENTINEL not in response.stdout + response.stderr
    assert "North depot" not in response.stdout + response.stderr
    assert "Traceback" not in response.stderr


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
def test_ci_recipe_native_optional_outputs_are_independent_and_materialized(tmp_path, engine):
    pytest.importorskip(engine)
    output = tmp_path / "upload"
    response = subprocess.run(
        [sys.executable, str(SCRIPT), "--engine", engine, "--output", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert response.returncode == 0, response.stderr
    assert_safe_report(output, "equivalent")


@pytest.mark.parametrize(
    ("scenario", "code"), [("equivalent", 0), ("different", 1), ("not_evaluable", 1)]
)
def test_pytest_recipe_is_a_real_failing_test_with_report_ready(tmp_path, scenario, code):
    response = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            str(PYTEST_RECIPE),
            "-k",
            scenario,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert response.returncode == code, response.stdout + response.stderr
    output = tmp_path / "ci-reports" / scenario
    assert_safe_report(output, scenario)
    if code:
        assert "1 failed" in response.stdout
        assert "report.html" in response.stdout
        assert "Equivalence" in response.stdout
    else:
        assert "1 passed" in response.stdout
    for value in ("North depot", "South depot", "West depot", SENTINEL):
        assert value not in response.stdout + response.stderr


@pytest.mark.parametrize("scenario", ["equivalent", "different", "not_evaluable"])
def test_report_io_failure_is_not_pass_and_keeps_original_state(
    tmp_path, recipe, monkeypatch, scenario
):
    def fail(*args, **kwargs):
        raise OSError(SENTINEL)

    monkeypatch.setattr(ef, "write_comparison_report", fail)
    output = tmp_path / "upload"
    with pytest.raises(recipe.RecipeError) as caught:
        recipe.run_recipe(output, scenario=scenario)
    message = str(caught.value)
    assert "Report publication failed" in message
    assert "comparison state=" + scenario in message
    assert json.dumps(str(output), ensure_ascii=True) in message
    assert SENTINEL not in message
    assert caught.value.__suppress_context__
    assert not output.exists()


@pytest.mark.parametrize("kind", ["extra", "corrupt", "missing", "symlink"])
def test_upload_allowlist_and_manifest_are_closed(tmp_path, recipe, kind):
    output = tmp_path / "upload"
    recipe.run_recipe(output)
    if kind == "extra":
        (output / "raw-secret.jsonl").write_text(SENTINEL)
    elif kind == "corrupt":
        (output / "report.txt").write_text(SENTINEL)
    elif kind == "missing":
        (output / "report.html").unlink()
    else:
        (output / "report.txt").unlink()
        target = tmp_path / "outside"
        target.write_text(SENTINEL)
        try:
            (output / "report.txt").symlink_to(target)
        except OSError:
            pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(recipe.RecipeError, match="do not upload"):
        recipe.verify_upload_directory(output)


@pytest.mark.parametrize("relation", ["same", "raw_inside_report", "report_inside_raw"])
def test_raw_evidence_cannot_share_upload_tree(tmp_path, recipe, relation):
    output = tmp_path / "upload"
    private = (
        output
        if relation == "same"
        else output / "raw"
        if relation == "raw_inside_report"
        else tmp_path
    )
    with pytest.raises(recipe.RecipeError, match="must be separate"):
        recipe.run_recipe(output, work_dir=private)
    assert not output.exists()


def test_preexisting_report_directory_is_not_reused_or_silently_uploaded(tmp_path, recipe):
    output = tmp_path / "upload"
    output.mkdir()
    (output / "private.txt").write_text(SENTINEL)
    with pytest.raises(recipe.RecipeError, match="Do not upload"):
        recipe.run_recipe(output, scenario="different")
    assert {item.name for item in output.iterdir()} == {"private.txt"}
    assert (output / "private.txt").read_text() == SENTINEL


@pytest.mark.parametrize("scenario", ["equivalent", "different", "not_evaluable"])
def test_partial_report_write_has_no_success_manifest_or_upload_approval(
    tmp_path, recipe, monkeypatch, scenario
):
    import importlib

    reporting = importlib.import_module("equiframe.comparison_report")
    original = reporting._write

    def fail_after_json(path, content):
        if path.name == "report.txt":
            raise OSError(SENTINEL)
        original(path, content)

    monkeypatch.setattr(reporting, "_write", fail_after_json)
    output = tmp_path / "upload"
    with pytest.raises(recipe.RecipeError, match="comparison state=" + scenario):
        recipe.run_recipe(output, scenario=scenario)
    assert (output / "report.json").is_file()
    assert not (output / "evidence-manifest.json").exists()
    with pytest.raises(recipe.RecipeError, match="do not upload"):
        recipe.verify_upload_directory(output)
    assert SENTINEL not in (output / "report.json").read_text()


def test_setup_errors_are_redacted_and_never_become_success(tmp_path, recipe, monkeypatch):
    def fail(**kwargs):
        raise OSError(SENTINEL)

    monkeypatch.setattr(recipe.tempfile, "TemporaryDirectory", fail)
    with pytest.raises(recipe.RecipeError) as caught:
        recipe.run_recipe(tmp_path / "upload")
    assert "comparison state=unavailable" in str(caught.value)
    assert SENTINEL not in str(caught.value)
    assert caught.value.__suppress_context__
    assert not (tmp_path / "upload").exists()


def test_cleanup_error_keeps_original_difference_in_diagnostic(tmp_path, recipe, monkeypatch):
    class CleanupFails:
        def __enter__(self):
            return str(tmp_path / "private")

        def __exit__(self, *args):
            raise OSError(SENTINEL)

    monkeypatch.setattr(recipe.tempfile, "TemporaryDirectory", lambda **kwargs: CleanupFails())
    output = tmp_path / "upload"
    with pytest.raises(recipe.RecipeError) as caught:
        recipe.run_recipe(output, scenario="different")
    assert "comparison state=different" in str(caught.value)
    assert SENTINEL not in str(caught.value)
    assert caught.value.__suppress_context__
    assert_safe_report(output, "different")


def test_missing_result_or_failed_materialization_cannot_publish_report(
    tmp_path, recipe, monkeypatch
):
    monkeypatch.setattr(ef, "diff", lambda *args, **kwargs: None)
    output = tmp_path / "upload"
    with pytest.raises(recipe.RecipeError, match="before a valid final result"):
        recipe.run_recipe(output)
    assert not output.exists()

    def fail(*args):
        raise ImportError(SENTINEL)

    monkeypatch.setattr(recipe, "materialize", fail)
    with pytest.raises(recipe.RecipeError, match="selected optional engine extra") as caught:
        recipe.run_recipe(output)
    assert SENTINEL not in str(caught.value)
    assert not output.exists()
