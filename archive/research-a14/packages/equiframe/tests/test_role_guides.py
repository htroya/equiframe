"""Run complete role-guide examples outside the checkout, including optimized gates."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import equiframe as ef

DOCS = Path(__file__).resolve().parents[1] / "docs"
SCIENCE = (
    ("good", "equivalent"),
    ("different", "different"),
    ("dropped_row", "different"),
    ("changed_id", "different"),
    ("time_shift", "different"),
    ("missing_changed", "different"),
    ("invalid_expected", "not_evaluable"),
    ("not_evaluable", "not_evaluable"),
)


def snippet(name: str, number: int = 0) -> str:
    return re.findall(r"```python\n(.*?)```", (DOCS / name).read_text(), re.DOTALL)[number]


@pytest.mark.parametrize("optimized", (False, True))
@pytest.mark.parametrize(
    "guide,scenario,state",
    [("cientifico.md", case, state) for case, state in SCIENCE]
    + [("arquitecto.md", "good", "equivalent"), ("arquitecto.md", "different", "different")],
)
def test_role_script_preserves_diagnosis_before_gate(tmp_path, optimized, guide, scenario, state):
    script = tmp_path / "role.py"
    script.write_text(snippet(guide), encoding="utf-8")
    output = tmp_path / "result"
    command = [sys.executable, "-I", *(["-O"] if optimized else []), str(script)]
    completed = subprocess.run(
        [*command, "--case", scenario, "--output", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == (0 if state == "equivalent" else 1), completed.stderr
    if state != "equivalent":
        kind = (
            "EquivalenceDifferentError" if state == "different" else "EquivalenceNotEvaluableError"
        )
        assert kind in completed.stderr
    report = ef.read_comparison_report(output / "report" / "report.json")
    detail = ef.read_comparison_report(output / "synthetic-detail" / "report.json")
    assert report.state == detail.state == state
    assert report.complete == detail.complete
    assert report.next_action and detail.next_action
    assert not report.options.include_metadata and not report.options.include_values
    assert detail.options.include_metadata and detail.options.include_values
    for view in (report, detail):
        assert view.state in view.to_text()
        assert view.state in view.to_html()
        assert view.state in view._repr_html_()
    if scenario in {"time_shift", "changed_id", "missing_changed", "different"}:
        assert detail.examples
        column = {
            "time_shift": "observed_at",
            "changed_id": "sample_id",
            "missing_changed": "duration_s",
            "different": "quantity" if guide == "arquitecto.md" else "duration_s",
        }[scenario]
        assert column in detail.to_text()
    # A repeated destination is rejected and cannot replace the previous report.
    original = (output / "report" / "report.json").read_bytes()
    repeated = subprocess.run(
        [*command, "--case", "good", "--output", str(output)],
        cwd=tmp_path,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert repeated.returncode != 0
    assert (output / "report" / "report.json").read_bytes() == original


def test_architect_pytest_recipe_is_a_real_local_test(tmp_path):
    (tmp_path / "integracion.py").write_text(snippet("arquitecto.md"), encoding="utf-8")
    (tmp_path / "test_integracion.py").write_text(snippet("arquitecto.md", 1), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(tmp_path / "pytest-work"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "1 passed" in completed.stdout
