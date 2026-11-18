"""User tasks and failure paths for the installation check and role exercises."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import equiframe as ef
import equiframe._doctor as doctor
import equiframe.cli as cli


def installed_metadata(monkeypatch):
    """Make unit checks independent of an editable developer environment's old metadata."""
    original = doctor.metadata.version
    monkeypatch.setattr(
        doctor.metadata,
        "version",
        lambda name: ef.__version__ if name == "equiframe" else original(name),
    )


def test_doctor_shows_identity_mismatch_and_a_private_recovery(monkeypatch):
    original = doctor.metadata.version
    monkeypatch.setattr(
        doctor.metadata, "version", lambda name: "0.11.1" if name == "equiframe" else original(name)
    )
    result = CliRunner().invoke(cli.app, ["doctor", "--json"])
    assert result.exit_code == 3
    report = json.loads(result.stdout)
    assert not report["identity_matches"] and not report["ready_metadata"]
    assert "Reinstall" in report["next_action"]
    assert report["installed_version"] == "0.11.1"
    assert report["code_version"] == ef.__version__
    assert not result.stderr


def test_doctor_missing_extra_gives_interpreter_specific_action(monkeypatch):
    installed_metadata(monkeypatch)
    original = doctor.metadata.version

    def without_arrow(name):
        if name == "pyarrow":
            raise doctor.metadata.PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(doctor.metadata, "version", without_arrow)
    result = CliRunner().invoke(cli.app, ["doctor", "--extra", "arrow", "--json"])
    assert result.exit_code == 3
    report = json.loads(result.stdout)
    assert not report["ready_metadata"]
    assert "equiframe[arrow]==" + ef.__version__ in report["next_action"]
    assert not report["native_execution_tested"] and not report["dependency_ranges_tested"]


def test_doctor_missing_module_is_not_hidden_by_distribution_metadata(monkeypatch):
    installed_metadata(monkeypatch)
    original = doctor.find_spec
    monkeypatch.setattr(
        doctor, "find_spec", lambda name: None if name == "polars" else original(name)
    )
    result = CliRunner().invoke(cli.app, ["doctor", "--extra", "polars"])
    assert result.exit_code == 3 and "polars: missing" in result.stdout
    assert "private wheelhouse" in result.stdout


@pytest.mark.parametrize("extra", [item.value for item in doctor.Extra])
def test_doctor_available_metadata_does_not_claim_native_validation(monkeypatch, extra):
    installed_metadata(monkeypatch)
    result = CliRunner().invoke(cli.app, ["doctor", "--extra", extra, "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["ready_metadata"] and report["extra"] == extra
    assert not report["native_execution_tested"] and "pip check" in report["next_action"]
    if extra == "base":
        assert {item["distribution"] for item in report["dependencies"]} == {
            "typing-extensions",
            "pydantic",
            "typer",
            "tzdata",
        }


def test_doctor_does_not_import_optional_runtimes():
    code = """
import sys
from equiframe._doctor import Extra, diagnose
diagnose(Extra.engines)
assert not ({'pyarrow', 'pandas', 'polars', 'duckdb', 'numpy', 'sklearn'} & set(sys.modules))
"""
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("optimized", [False, True])
@pytest.mark.parametrize("role", ["architect", "scientist"])
@pytest.mark.parametrize(
    "case,state,exit_code",
    [
        ("good", "equivalent", 0),
        ("different", "different", 1),
        ("not-evaluable", "not_evaluable", 3),
    ],
)
def test_role_demo_saves_explanations_then_rejects_and_never_overwrites(
    tmp_path, optimized, role, case, state, exit_code
):
    output = tmp_path / "exercise"
    command = [
        sys.executable,
        "-I",
        *(["-O"] if optimized else []),
        "-m",
        "equiframe",
        "demo",
        "--role",
        role,
        "--case",
        case,
        "--output",
        str(output),
    ]
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, timeout=120)
    assert result.returncode == exit_code, result.stdout + result.stderr
    summary = json.loads(result.stdout.splitlines()[-1])
    assert summary["state"] == state and summary["accepted"] == (exit_code == 0)
    report = ef.read_comparison_report(output / "report" / "report.json")
    detail = ef.read_comparison_report(output / "synthetic-detail" / "report.json")
    assert report.state == detail.state == state
    assert not report.options.include_values and not report.options.include_metadata
    assert detail.options.include_values and detail.options.include_metadata
    assert report.next_action and detail.next_action
    for view in (report, detail):
        assert state in view.to_text() and state in view.to_html() and state in view._repr_html_()
    if case == "different":
        assert ("quantity" if role == "architect" else "duration_s") in detail.to_text()
    original = (output / "report" / "report.json").read_bytes()
    repeat = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, timeout=120)
    assert repeat.returncode == 3 and "existing_output" in repeat.stderr
    assert (output / "report" / "report.json").read_bytes() == original


def test_demo_report_write_failure_cannot_approve_data(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise PermissionError("private-output")

    monkeypatch.setattr(ef, "write_comparison_report", unavailable)
    result = CliRunner().invoke(
        cli.app, ["demo", "--role", "scientist", "--output", str(tmp_path / "exercise")]
    )
    assert result.exit_code == 3 and not result.stdout
    assert "permission_denied" in result.stderr and "private-output" not in result.stderr


@pytest.mark.parametrize(
    "args", [["doctor", "--extra", "unknown"], ["demo", "--role", "unknown", "--output", "new"]]
)
def test_unknown_role_or_extra_is_usage_error(args):
    assert CliRunner().invoke(cli.app, args).exit_code == 2


def test_current_installation_guides_match_package_version():
    root = Path(__file__).resolve().parents[1]
    for name in ("installed-private.md", "quickstart.md", "index.md", "first-use.md"):
        text = (root / "docs" / name).read_text("utf-8")
        assert ef.__version__ in text
        assert "0.12.0a10" not in text and "0.12.0a11" not in text


def test_fault_explanation_precedes_technical_policies_in_all_views(tmp_path):
    from equiframe._first_use import Case, Role, run_demo

    run_demo(Role.scientist, Case.different, tmp_path / "exercise")
    report = ef.read_comparison_report(tmp_path / "exercise" / "synthetic-detail" / "report.json")
    for view in (report.to_text(), report.to_html(), report._repr_html_()):
        assert view.index("Reasons") < view.index("Next action") < view.index("Policies")
        assert view.index("Example 1: values and types") < view.index("Policies")
        assert 'Decimal("1.251")' in view or "Decimal(&quot;1.251&quot;)" in view
        assert "duration_s" in view and "sample_id" in view
        assert "Evidence and limitations" in view and "physical_types" in view
