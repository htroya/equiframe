"""Fail-closed CLI gates with machine-readable stdout and redacted diagnostics."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_comparison_decisions import decision_contract, table
from typer.testing import CliRunner

import equiframe as ef
import equiframe.cli as cli
from equiframe.errors import ArtifactIOError

SECRET = "synthetic-private-diagnostic-value"


def files(tmp_path: Path, left: list[int | None], right: list[int | None]) -> list[str]:
    spec = tmp_path / "spec.json"
    spec.write_text(ef.ComparisonSpec(contract=decision_contract()).model_dump_json())
    lhs, rhs = tmp_path / "left.parquet", tmp_path / "right.parquet"
    pq.write_table(table(left), lhs)
    pq.write_table(table(right), rhs)
    return ["compare", str(spec), str(lhs), str(rhs), "--output", str(tmp_path / "evidence")]


@pytest.mark.parametrize(
    ("left", "right", "expected", "code", "state", "diagnostic"),
    [
        ([1, 2], [2, 1], False, 0, "equivalent", ""),
        ([1, 2], [1, 3], False, 1, "different", "comparison_different"),
        ([None], [1], True, 1, "different", "comparison_different"),
        ([1], [None], True, 3, "not_evaluable", "comparison_not_evaluable"),
        ([None], [None], True, 3, "not_evaluable", "comparison_not_evaluable"),
    ],
)
def test_compare_subprocess_keeps_json_stdout_and_exit_contract(
    tmp_path, left, right, expected, code, state, diagnostic
):
    args = files(tmp_path, left, right)
    if expected:
        args.append("--expected")
    response = subprocess.run(
        [sys.executable, "-m", "equiframe", *args], capture_output=True, text=True, check=False
    )
    assert response.returncode == code, response.stderr
    summary = json.loads(response.stdout)
    assert set(summary) == {
        "comparison_id",
        "state",
        "complete",
        "accepted",
        "code",
        "evidence_status",
    }
    assert summary["accepted"] is (code == 0)
    assert summary["evidence_status"] == "verified"
    assert summary["state"] == state and summary["complete"] is True
    assert diagnostic in response.stderr
    if code == 0:
        assert response.stderr == ""
    else:
        assert "Traceback" not in response.stderr
        assert "id" not in response.stderr.split(":")[0]
        assert str(tmp_path) not in response.stderr
    persisted = ef.read_comparison(
        tmp_path / "evidence" / summary["comparison_id"] / "comparison.json"
    )
    assert persisted.state == state


def test_compare_partial_result_reports_unavailable_not_known_difference(tmp_path, monkeypatch):
    result = ef.compare(
        ef.ArrowInput(table([None, None, None])),
        ef.ArrowInput(table([1, 2, 3])),
        contract=decision_contract(),
        options=ef.ComparisonOptions(max_rows=2),
        work_dir=tmp_path / "private",
    )
    assert result.counts.difference_records > 0 and not result.complete
    monkeypatch.setattr(cli, "compare", lambda *args, **kwargs: result)
    response = CliRunner().invoke(cli.app, files(tmp_path, [1], [1]))
    assert response.exit_code == 3
    assert json.loads(response.stdout)["complete"] is False
    assert "comparison_not_evaluable" in response.stderr
    assert "comparison_different" not in response.stderr


@pytest.mark.parametrize(
    "produced",
    [
        None,
        {},
        {"state": "equivalent", "complete": True},
        SimpleNamespace(state="equivalent", complete=True),
    ],
)
def test_compare_absent_or_malformed_final_result_never_prints_success(
    tmp_path, monkeypatch, produced
):
    monkeypatch.setattr(cli, "compare", lambda *args, **kwargs: produced)
    response = CliRunner().invoke(cli.app, files(tmp_path, [1], [1]))
    assert response.exit_code == 3
    assert response.stdout == ""
    assert response.stderr.splitlines()[0] == "operation_failed"


@pytest.mark.parametrize(
    "updates",
    [
        {"complete": False},
        {"state": "completed"},
        {"counts": {"final": False}},
        {"counts": {"final": True}},
        {"comparison_id": SECRET + "\nfalse-success"},
    ],
)
def test_compare_revalidates_constructed_producer_results(tmp_path, monkeypatch, updates):
    source = pa.table({"id": [1]})
    original = ef.diff(source, source, work_dir=tmp_path / "private")
    malformed = original.model_copy(update=updates)
    monkeypatch.setattr(cli, "compare", lambda *args, **kwargs: malformed)
    response = CliRunner().invoke(cli.app, files(tmp_path, [1], [1]))
    assert response.exit_code == 3
    assert response.stdout == ""
    assert response.stderr.splitlines()[0] == "operation_failed"
    assert SECRET not in response.output


@pytest.mark.parametrize(
    ("exception", "code", "diagnostic"),
    [
        (ValueError(SECRET), 2, "invalid_input"),
        (ArtifactIOError(SECRET), 3, "operation_failed"),
        (PermissionError(SECRET), 3, "operation_failed"),
        (RuntimeError(SECRET), 3, "operation_failed"),
    ],
)
def test_compare_exception_matrix_has_no_secret_or_false_json(
    tmp_path, monkeypatch, exception, code, diagnostic
):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(cli, "compare", fail)
    response = CliRunner().invoke(cli.app, files(tmp_path, [1], [1]))
    assert response.exit_code == code
    assert response.stdout == ""
    assert response.stderr.splitlines()[0] == diagnostic
    assert SECRET not in response.output
    assert "Traceback" not in response.output


def test_compare_diagnostic_does_not_echo_producer_message(tmp_path, monkeypatch):
    result = ef.compare(
        ef.ArrowInput(table([1])),
        tmp_path / "missing.parquet",
        contract=decision_contract(),
        work_dir=tmp_path / "private",
    )
    poisoned = result.model_copy(
        update={
            "diagnostics": (
                ef.ComparisonDiagnostic(code=SECRET, message=SECRET, exception_type=SECRET),
            )
        }
    )
    monkeypatch.setattr(cli, "compare", lambda *args, **kwargs: poisoned)
    response = CliRunner().invoke(cli.app, files(tmp_path, [1], [1]))
    assert response.exit_code == 3
    assert json.loads(response.stdout)["state"] == "not_evaluable"
    assert "comparison_not_evaluable" in response.stderr
    assert SECRET not in response.output


def test_compare_subprocess_persistence_failure_leaves_stdout_empty(tmp_path):
    args = files(tmp_path, [1], [1])
    occupied = tmp_path / "evidence"
    occupied.write_text(SECRET)
    response = subprocess.run(
        [sys.executable, "-m", "equiframe", *args], capture_output=True, text=True, check=False
    )
    assert response.returncode == 3
    assert response.stdout == ""
    assert response.stderr.splitlines()[0] == "operation_failed"
    assert occupied.read_text() == SECRET


@pytest.mark.parametrize(
    "damage", ["missing_manifest", "corrupt_manifest", "missing_differences", "corrupt_differences"]
)
def test_equivalent_cli_requires_current_finalized_persisted_evidence(
    tmp_path, monkeypatch, damage
):
    source = pa.table({"id": [1]})
    result = ef.diff(source, source, work_dir=tmp_path / "evidence")
    root = tmp_path / "evidence" / result.comparison_id
    target = root / ("comparison.json" if damage.endswith("manifest") else "differences.jsonl")
    if damage.startswith("missing"):
        target.unlink()
    else:
        target.write_text(SECRET)
    monkeypatch.setattr(cli, "compare", lambda *args, **kwargs: result)
    response = CliRunner().invoke(cli.app, files(tmp_path, [1], [1]))
    assert response.exit_code == 3
    summary = json.loads(response.stdout)
    assert summary["state"] == "equivalent" and summary["complete"] is True
    assert summary["accepted"] is False
    assert summary["code"] in ("evidence_missing", "evidence_corrupt")
    assert summary["evidence_status"] in ("missing", "corrupt")
    assert "comparison_unavailable" in response.stderr
    assert SECRET not in response.output
    assert str(tmp_path) not in response.stderr
