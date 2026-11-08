"""CLI acceptance preserves operational outcomes and never runs ETL on inspection."""

import json

import pyarrow as pa
from test_ingestion import fields
from test_workflow import reference, stage
from typer.testing import CliRunner

from equiframe.cli import app
from equiframe.ingestion import IngestionSpec
from equiframe.pipeline_types import PipelineInput
from equiframe.workflow import WorkflowSpec
from equiframe.workflow_request import WorkflowExpected, WorkflowRequest

runner = CliRunner()


def test_ingestion_cli_completed_and_quarantine_exit_codes(tmp_path):
    source = tmp_path / "money.csv"
    source.write_text("id,money\n001,1.50\n002,0.00\n", encoding="utf-8")
    spec_path = tmp_path / "ingestion.json"
    spec_path.write_text(
        IngestionSpec(format="csv", fields=fields()).model_dump_json(), encoding="utf-8"
    )
    completed = runner.invoke(
        app, ["ingestion", "run", str(spec_path), str(source), "--output", str(tmp_path)]
    )
    assert completed.exit_code == 0, completed.output
    result = json.loads(completed.stdout)
    assert result["state"] == "completed" and result["accepted_records"] == 2
    source.write_text("id,money\n001,1.50\n002,bad\n", encoding="utf-8")
    spec_path.write_text(
        IngestionSpec(
            format="csv", fields=fields(), invalid_records="quarantine"
        ).model_dump_json(),
        encoding="utf-8",
    )
    partial = runner.invoke(
        app, ["ingestion", "run", str(spec_path), str(source), "--output", str(tmp_path)]
    )
    assert partial.exit_code == 1, partial.output
    result = json.loads(partial.stdout)
    assert result["state"] == "quarantined" and result["accepted_records"] == 1
    assert len(result["quarantined"]) == 1


def test_ingestion_cli_invalid_request_and_io_codes(tmp_path):
    spec_path = tmp_path / "invalid.json"
    spec_path.write_text('{"format":"unknown"}', encoding="utf-8")
    invalid = runner.invoke(
        app, ["ingestion", "run", str(spec_path), str(tmp_path / "missing.csv")]
    )
    assert invalid.exit_code == 2 and "Traceback" not in invalid.output
    spec_path.write_text(
        IngestionSpec(format="csv", fields=fields()).model_dump_json(), encoding="utf-8"
    )
    missing = runner.invoke(
        app,
        [
            "ingestion",
            "run",
            str(spec_path),
            str(tmp_path / "missing.csv"),
            "--output",
            str(tmp_path),
        ],
    )
    assert missing.exit_code == 3 and "Traceback" not in missing.output


def test_workflow_cli_validate_run_inspect_and_corruption(tmp_path):
    source = reference(pa.table({"n": [1, 2]}), tmp_path / "source.arrow")
    request = WorkflowRequest(
        spec=WorkflowSpec(workflow_id="cli", stages=(stage("one"),)),
        inputs=(PipelineInput(name="original", artifact=source),),
    )
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json(), encoding="utf-8")
    validated = runner.invoke(app, ["workflow", "validate", str(path)])
    assert validated.exit_code == 0, validated.output
    assert json.loads(validated.stdout)["compilation_only"]
    executed = runner.invoke(app, ["workflow", "run", str(path), "--output", str(tmp_path)])
    assert executed.exit_code == 0, executed.output
    result = json.loads(executed.stdout)
    directory = tmp_path / result["run_id"]
    inspected = runner.invoke(app, ["workflow", "inspect", str(directory)])
    assert inspected.exit_code == 0, inspected.output
    assert json.loads(inspected.stdout) == result
    (directory / "unexpected.txt").write_text("extra", encoding="utf-8")
    corrupt = runner.invoke(app, ["workflow", "inspect", str(directory)])
    assert corrupt.exit_code == 3 and "Traceback" not in corrupt.output


def test_workflow_cli_expected_divergent_and_dependent_skipped(tmp_path):
    source = reference(pa.table({"n": [1, 2]}), tmp_path / "source.arrow")
    expected = reference(pa.table({"n": [9, 2]}), tmp_path / "expected.arrow")
    request = WorkflowRequest(
        spec=WorkflowSpec(workflow_id="cli", stages=(stage("one"), stage("two", "one"))),
        inputs=(PipelineInput(name="original", artifact=source),),
        expected=(WorkflowExpected(stage_id="one", artifact=expected),),
    )
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json(), encoding="utf-8")
    executed = runner.invoke(app, ["workflow", "run", str(path), "--output", str(tmp_path)])
    assert executed.exit_code == 1, executed.output
    result = json.loads(executed.stdout)
    assert result["first_divergent_stage"] == "one"
    assert [checkpoint["state"] for checkpoint in result["checkpoints"]] == ["failed", "skipped"]
    assert result["checkpoints"][1]["migration"] is None


def test_workflow_cli_invalid_request_exits_2(tmp_path):
    path = tmp_path / "request.json"
    path.write_text('{"spec":{"workflow_id":"bad","stages":[]},"inputs":[]}', encoding="utf-8")
    for command in ("validate", "run"):
        result = runner.invoke(app, ["workflow", command, str(path)])
        assert result.exit_code == 2 and "Traceback" not in result.output
