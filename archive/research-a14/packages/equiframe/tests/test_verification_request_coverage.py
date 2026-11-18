"""A complete zero-request receipt must never become publishable by vacuous checks."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_migration import contract

import equiframe as ef


@pytest.mark.parametrize("channel", ["python", "json"])
@pytest.mark.parametrize("complete", [False, True])
def test_zero_requested_outputs_are_not_a_verification(channel, complete):
    data = {
        "outputs_requested": 0,
        "outputs_inspected": 0,
        "comparisons_requested": 0,
        "comparisons_completed": 0,
        "input_execution_evidence_available": False,
        "complete": complete,
    }
    with pytest.raises(ValidationError, match="outputs_requested"):
        if channel == "json":
            ef.VerificationCoverage.model_validate_json(json.dumps(data))
        else:
            ef.VerificationCoverage.model_validate(data)


def test_closed_empty_request_document_is_rejected_by_public_reader():
    # Synthetic closed three-file fixture produced with a2. Its matching report
    # hashes and bytes previously allowed an empty request to return exit 0.
    directory = Path(__file__).parent / "fixtures" / "verification_empty_request"
    with pytest.raises(ValidationError, match="outputs_requested"):
        ef.read_verification(directory)


def test_failed_nonempty_request_can_still_have_no_captured_outputs(tmp_path):
    missing = ef.ArtifactRef(
        schema_version="1.0",
        uri=(tmp_path / "missing.arrow").as_uri(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        sha256="0" * 64,
        size_bytes=1,
    )
    result = ef.verify({"requested": missing}, contract=contract(), work_dir=tmp_path)
    assert result.coverage.outputs_requested == 1
    assert result.coverage.outputs_inspected == 0
    assert result.outputs == ()
    assert not result.coverage.complete
    assert not result.publishable
    assert result.exit_code in (1, 3)
    assert ef.read_verification(tmp_path / result.verification_id) == result


@pytest.fixture
def mismatched_snapshot_result(tmp_path):
    import pyarrow as pa
    from test_migration import table
    from test_verify import artifact

    registry = ef.TransformationRegistry()
    registry.register(
        ef.PandasTransformation("identity", lambda tables, context: tables["input"].copy(), "test")
    )
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract(), engine="pandas", transformation_id="identity"),
        source=ef.LocalDataSource({"input": ef.ArrowInput(table())}),
        registry=registry,
        work_dir=tmp_path / "execution",
    )
    assert execution.state == "completed"
    wrong = artifact(tmp_path, "wrong-input", pa.table({"id": [999], "value": ["different"]}))
    result = ef.verify(
        {"requested": execution},
        contract=contract(),
        snapshots={"input": wrong},
        policy=ef.ComparisonPolicy(index="ignore", justification="Generated index is not identity"),
        work_dir=tmp_path / "verification",
    )
    assert result.executions[0][1].inputs[0].data.sha256 != result.input_artifacts[0][1].sha256
    assert result.integrity.state == "failed"
    assert not result.coverage.complete and not result.publishable
    assert ef.read_verification(tmp_path / "verification" / result.verification_id) == result
    return result


@pytest.mark.parametrize("channel", ["python", "json"])
@pytest.mark.parametrize("promotion", ["integrity", "complete", "both"])
def test_retained_input_identity_mismatch_cannot_be_promoted(
    mismatched_snapshot_result, promotion, channel
):
    data = mismatched_snapshot_result.model_dump(mode=channel)
    if promotion in ("integrity", "both"):
        data["integrity"]["state"] = "passed"
    if promotion in ("complete", "both"):
        data["coverage"]["complete"] = True
    with pytest.raises(ValidationError, match="bound snapshots"):
        if channel == "json":
            ef.VerificationResult.model_validate_json(json.dumps(data))
        else:
            ef.VerificationResult.model_validate(data)


@pytest.mark.parametrize("channel", ["python", "json"])
@pytest.mark.parametrize("state", ["passed", "failed", "pending_review"])
def test_expected_outcome_requires_a_bound_comparison(tmp_path, state, channel):
    from test_migration import table
    from test_verify import artifact

    output = artifact(tmp_path, "output", table())
    result = ef.verify({"one": output}, contract=contract(), work_dir=tmp_path)
    assert result.expected[0].state == "not_requested"
    assert result.expected_artifact is None
    data = result.model_dump(mode=channel)
    data["expected"][0]["state"] = state
    with pytest.raises(ValidationError, match="bound comparison"):
        if channel == "json":
            ef.VerificationResult.model_validate_json(json.dumps(data))
        else:
            ef.VerificationResult.model_validate(data)


def test_failed_optional_expected_capture_remains_representable(tmp_path):
    from test_migration import table
    from test_verify import artifact

    output = artifact(tmp_path, "output", table())
    missing = output.model_copy(update={"uri": (tmp_path / "missing-expected.arrow").as_uri()})
    result = ef.verify({"one": output}, contract=contract(), expected=missing, work_dir=tmp_path)
    assert result.expected_artifact is None and not result.expected_required
    assert result.expected[0].state == "not_evaluable"
    assert result.integrity.state == "failed"
    assert not result.publishable
    assert ef.read_verification(tmp_path / result.verification_id) == result


@pytest.mark.parametrize("state", ["not_requested", "pending_review"])
def test_integrity_role_cannot_skip_byte_verification(tmp_path, state):
    from test_migration import table
    from test_verify import artifact

    output = artifact(tmp_path, "output", table())
    result = ef.verify({"one": output}, contract=contract(), work_dir=tmp_path)
    data = result.model_dump(mode="json")
    data["integrity"]["state"] = state
    with pytest.raises(ValidationError, match="integrity"):
        ef.VerificationResult.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("state", ["failed", "not_evaluable"])
def test_complete_coverage_requires_passed_integrity(tmp_path, state):
    from test_migration import table
    from test_verify import artifact

    output = artifact(tmp_path, "output", table())
    result = ef.verify({"one": output}, contract=contract(), work_dir=tmp_path)
    data = result.model_dump(mode="json")
    data["integrity"]["state"] = state
    assert data["coverage"]["complete"] is True
    with pytest.raises(ValidationError, match="integrity"):
        ef.VerificationResult.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("change", ["inflate_requested", "clear_complete"])
def test_coverage_is_reconstructed_from_recorded_request_dimensions(tmp_path, change):
    from test_migration import table
    from test_verify import artifact

    output = artifact(tmp_path, "output", table())
    result = ef.verify({"one": output}, contract=contract(), work_dir=tmp_path)
    assert result.coverage.comparisons_requested == 1 and result.coverage.complete
    data = result.model_dump(mode="json")
    data["coverage"]["complete"] = False
    if change == "inflate_requested":
        data["coverage"]["comparisons_requested"] = 2
    with pytest.raises(ValidationError, match="coverage"):
        ef.VerificationResult.model_validate_json(json.dumps(data))
