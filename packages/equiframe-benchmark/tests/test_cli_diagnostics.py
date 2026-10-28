"""Benchmark commands share guidance while retaining their original exit policy."""

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from equiframe_benchmark.cli import app


@pytest.mark.parametrize(
    ("command", "contents", "code", "exit_code", "category"),
    [
        ("validate", "{}", "invalid_input", 2, "document_validation"),
        ("validate", "{", "invalid_input", 2, "document_syntax"),
        ("validate", None, "operation_failed", 3, "missing_path"),
        ("scale", "{}", "scale_operation_failed", 3, "document_validation"),
        ("scale", None, "scale_operation_failed", 3, "missing_path"),
        ("verify-scale", None, "scale_evidence_invalid_or_incomplete", 3, "missing_path"),
    ],
)
def test_normal_consumer_failures_have_safe_fixed_hints(
    tmp_path, command, contents, code, exit_code, category
):
    source = tmp_path / "private-request.json"
    if contents is not None:
        source.write_text(contents, encoding="utf-8")
    arguments = [command, str(source)]
    if command == "scale":
        arguments.extend(("--output", str(tmp_path / "output")))
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == exit_code and not result.stdout
    assert result.stderr.splitlines()[0] == code
    assert result.stderr.splitlines()[1].startswith(f"hint[{category}]: ")
    assert len(result.stderr.splitlines()) == 2
    assert str(tmp_path) not in result.stderr and "Traceback" not in result.stderr


def test_existing_split_output_has_recovery_hint(make_case, tmp_path):
    import equiframe_benchmark as eb

    catalog = eb.Catalog(catalog_id="cli.synthetic", synthetic=True, scenarios=(make_case()[0],))
    source, output = tmp_path / "catalog.json", tmp_path / "split.json"
    eb.save_document(catalog, source)
    output.write_text("existing evidence", encoding="utf-8")
    result = CliRunner().invoke(app, ["split", str(source), "--output", str(output), "--seed", "8"])
    assert result.exit_code == 3 and not result.stdout
    assert result.stderr.splitlines()[0] == "operation_failed"
    assert "hint[existing_output]" in result.stderr
    assert output.read_text(encoding="utf-8") == "existing evidence"


def test_standalone_pilot_existing_output_preserves_exit_one(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "equiframe_benchmark.pilot", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and not result.stdout
    assert result.stderr.splitlines()[0] == "pilot_operation_failed"
    assert "hint[existing_output]" in result.stderr
    assert "Traceback" not in result.stderr and str(tmp_path) not in result.stderr
