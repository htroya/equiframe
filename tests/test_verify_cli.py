"""CLI distinguishes semantic outcomes from intact evidence and portable inspection."""

import json

import pyarrow as pa
from test_migration import contract, run, table
from test_verify import artifact
from typer.testing import CliRunner

from equiframe.cli import app
from equiframe.evidence import publish_json
from equiframe.pipeline_types import PipelineInput
from equiframe.verification_request import VerificationRequest


def request(tmp_path, *, wrong=False, require_expected=False):
    expected = artifact(tmp_path, "expected", table())
    output = artifact(
        tmp_path,
        "output",
        pa.table({"id": [99, 99, 99], "value": ["a", None, "c"]}) if wrong else table(),
    )
    path = tmp_path / "request.json"
    publish_json(
        VerificationRequest(
            contract=contract(),
            outputs=(PipelineInput(name="external", artifact=output),),
            expected=expected if wrong else None,
            require_expected=require_expected,
        ),
        path,
    )
    return path


def test_cli_metadata_validation_and_semantic_run_inspection(tmp_path):
    path = request(tmp_path, wrong=True)
    runner = CliRunner()
    validated = runner.invoke(app, ["verify", "validate", str(path)])
    assert validated.exit_code == 0 and json.loads(validated.stdout)["metadata_valid"]
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(tmp_path / "runs")])
    assert result.exit_code == 1
    summary = json.loads(result.stdout)
    assert summary["operational_state"] == "failed"
    directory = tmp_path / "runs" / summary["verification_id"]
    inspected = runner.invoke(app, ["verify", "inspect", str(directory)])
    assert inspected.exit_code == 0
    assert json.loads(inspected.stdout)["publishable"] is False
    (directory / "report.json").write_text("{}", encoding="utf-8")
    assert runner.invoke(app, ["verify", "inspect", str(directory)]).exit_code == 3


def test_cli_required_expected_absent_and_invalid_request(tmp_path):
    path = request(tmp_path, require_expected=True)
    runner = CliRunner()
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(tmp_path / "runs")])
    assert result.exit_code == 3
    data = json.loads(path.read_bytes())
    data["outputs"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    assert runner.invoke(app, ["verify", "validate", str(path)]).exit_code == 2


def test_cli_bundle_export_import_verify_preserve_semantic_failure(tmp_path):
    runner = CliRunner()
    path = request(tmp_path, wrong=True)
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(tmp_path / "runs")])
    directory = tmp_path / "runs" / json.loads(result.stdout)["verification_id"]
    portable = tmp_path / "portable"
    relocated = tmp_path / "relocated"
    assert runner.invoke(app, ["bundle", "export", str(directory), str(portable)]).exit_code == 0
    directory.rename(tmp_path / "hidden_original")
    assert runner.invoke(app, ["bundle", "import", str(portable), str(relocated)]).exit_code == 0
    verified = runner.invoke(app, ["bundle", "verify", str(relocated)])
    assert verified.exit_code == 0
    assert json.loads(verified.stdout)["outcome"]["operational_state"] == "failed"
    assert (
        runner.invoke(app, ["bundle", "verify", str(relocated), "--sha256", "0" * 64]).exit_code
        == 3
    )


def test_cli_existing_migration_is_verified_without_native_callbacks(tmp_path, monkeypatch):
    migration = run(tmp_path / "migration_runs")

    def prohibited(*args, **kwargs):
        raise AssertionError("native ETL must not rerun during Verify")

    monkeypatch.setattr("equiframe.migration.runner.migrate", prohibited)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "verify",
            "migration",
            str(tmp_path / "migration_runs" / migration.migration_id),
            "--output",
            str(tmp_path / "verify_runs"),
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["dimensions"]["technical"]["state"] == "passed"
