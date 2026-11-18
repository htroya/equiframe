"""Final evidence must retain captured bytes and their declared references."""

import json

import pytest
from pydantic import ValidationError
from test_pipeline import run, table
from typer.testing import CliRunner

import equiframe as ef
from equiframe.cli import app
from equiframe.evidence import describe_file
from equiframe.local import local_path


@pytest.mark.parametrize("delete_capture", [False, True])
def test_omitted_capture_cannot_be_verified(tmp_path, delete_capture):
    result = run(tmp_path)
    directory = tmp_path / result.pipeline_id
    capture = local_path(result.execution.output.data)
    manifest = directory / "manifest.json"
    raw = json.loads(manifest.read_bytes())
    relative = capture.relative_to(directory).as_posix()
    raw["evidence"] = [item for item in raw["evidence"] if item["path"] != relative]
    manifest.write_text(json.dumps(raw), encoding="utf8")
    if delete_capture:
        capture.unlink()
    with pytest.raises(ef.ArtifactIntegrityError, match="inventory"):
        ef.read_pipeline(directory)
    assert CliRunner().invoke(app, ["evidence", "verify", str(directory)]).exit_code == 3


def test_deleted_inventoried_capture_is_integrity_failure(tmp_path):
    result = run(tmp_path)
    local_path(result.execution.output.data).unlink()
    with pytest.raises(ef.ArtifactIntegrityError, match="missing or unreadable"):
        ef.read_pipeline(tmp_path / result.pipeline_id)


@pytest.mark.parametrize(
    "field,value", [("sha256", "b" * 64), ("size_bytes", 1), ("uri", "outside-operation")]
)
def test_captured_reference_must_match_verified_bytes(tmp_path, field, value):
    result = run(tmp_path, comparison=ef.ArrowInput(table()))
    directory = tmp_path / result.pipeline_id
    manifest = directory / "manifest.json"
    raw = json.loads(manifest.read_bytes())
    raw["comparison"]["right"]["data"][field] = (
        (tmp_path / "external.arrow").as_uri() if field == "uri" else value
    )
    component = directory / "comparison.json"
    component.write_text(json.dumps(raw["comparison"]), encoding="utf8")
    raw["evidence"] = [
        describe_file(component, directory).model_dump(mode="json")
        if item["path"] == "comparison.json"
        else item
        for item in raw["evidence"]
    ]
    manifest.write_text(json.dumps(raw), encoding="utf8")
    message = "escapes" if field == "uri" else "reference contradicts"
    with pytest.raises(ef.ArtifactIntegrityError, match=message):
        ef.read_pipeline(directory)


def test_external_comparison_provenance_uses_owned_snapshot(tmp_path):
    reference = run(tmp_path / "reference")
    result = run(tmp_path / "current", comparison=reference.execution)
    assert result.complete
    assert result.comparison.right.execution == reference.execution
    local_path(reference.execution.output.data).unlink()
    assert ef.read_pipeline(tmp_path / "current" / result.pipeline_id) == result


@pytest.mark.parametrize(
    "field,value", [("run_id", "run_unrelated"), ("contract_sha256", "b" * 64), ("artifacts", ())]
)
def test_profile_provenance_must_match_captured_execution(tmp_path, field, value):
    result = run(tmp_path)
    raw = result.model_dump()
    raw["profile"]["metadata"][field] = value
    with pytest.raises(ValidationError, match="profile does not belong"):
        ef.PipelineResult.model_validate(raw)


@pytest.mark.parametrize("command", ["evidence", "report"])
@pytest.mark.parametrize("contents", ['{"truncated":', '{"schema_version":"invalid"}'])
def test_corrupt_persisted_manifest_is_evidence_failure(tmp_path, command, contents):
    result = run(tmp_path)
    directory = tmp_path / result.pipeline_id
    (directory / "manifest.json").write_text(contents, encoding="utf8")
    arguments = (
        ["evidence", "verify", str(directory)]
        if command == "evidence"
        else ["report", str(directory), "--output", str(tmp_path / "report")]
    )
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 3
    assert response.output.splitlines()[0] == "operation_failed"
    assert not (tmp_path / "report").exists()
