"""Object existence must not grant approval at any operational result boundary."""

import inspect
from pathlib import Path

import pyarrow as pa
import pytest
from pydantic import BaseModel
from test_detector_component import frozen_bundle
from test_ingestion import fields
from test_migration import contract, spec, table
from test_pipeline import registered, run
from test_preprocessing import vector
from test_reduction import reduce
from test_verify import artifact
from test_workflow import CountingSource, reference, stage

import equiframe as ef
from equiframe._base import FrozenModel, _ExplicitOutcome

# Deliberate inventory: never attach the guard to every Pydantic model.
GUARDED = {
    "CheckResult",
    "CompilationCheck",
    "ComparisonReport",
    "ComponentDecision",
    "ComponentDetectionResult",
    "DetectionResult",
    "DetectorDecision",
    "DetectorScoreResult",
    "DetectorScores",
    "ExecutionResult",
    "HybridDecision",
    "IngestionResult",
    "MigrationResult",
    "PipelineResult",
    "ProfileResult",
    "RReviewResult",
    "ReductionResult",
    "ReviewedDecision",
    "RuleEvaluation",
    "VerificationCheck",
    "VerificationResult",
    "WorkflowCheckpoint",
    "WorkflowResult",
}


def _conditional(value):
    if value:
        return "accepted"
    return "rejected"


def _assertion(value):
    assert value


def _guarded_tree(value):
    """Check actual validated outcomes and nested decisions without inventing records."""
    found = set()
    if isinstance(value, _ExplicitOutcome):
        found.add(type(value).__name__)
        original = value.model_dump_json()
        for operation in (
            bool,
            _conditional,
            _assertion,
            lambda v: not v,
            lambda v: v and True,
            lambda v: v or False,
            lambda v: any((v,)),
            lambda v: all((v,)),
        ):
            with pytest.raises(TypeError, match=type(value).__name__ + " has no truth value"):
                operation(value)
        assert type(value).model_validate_json(original) == value
        assert value.model_dump_json() == original
        assert [value][0] is value
        assert value is not None
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            found.update(_guarded_tree(getattr(value, name)))
    elif isinstance(value, (tuple, list)):
        for child in value:
            found.update(_guarded_tree(child))
    return found


def test_explicit_inventory_preserves_data_and_configuration_truthiness():
    actual = {
        name
        for name, value in vars(ef).items()
        if inspect.isclass(value) and issubclass(value, _ExplicitOutcome)
    }
    assert actual == GUARDED
    assert "__bool__" not in FrozenModel.__dict__
    for name in GUARDED:
        assert "_truth_value_guidance" not in getattr(ef, name).model_fields
    for value in (ef.ComparisonOptions(), ef.ExecutionOptions(), spec(), table()):
        assert not isinstance(value, _ExplicitOutcome)
    assert bool(ef.ComparisonOptions()) is True
    assert bool(frozen_bundle()) is True


def test_r_review_outcomes_require_explicit_acceptance_and_preserve_alerts():
    table = pa.table({"value": [1]})
    reviewed = ef.finalize_with_r(
        ef.ComponentDecision(decision="alert", complete=True),
        ef.ComponentDecision(decision="no_alert", complete=True),
        left=table,
        right=table,
        contract=ef.infer_diff_contract(table.schema),
        options=ef.RReviewOptions(rscript="equiframe-qa-nonexistent-rscript"),
    )
    assert reviewed.r_review.state == "not_evaluable"
    assert reviewed.r_review.reason == "rscript_unavailable"
    assert reviewed.result.decision == "alert" and not reviewed.result.complete
    assert not reviewed.accepted
    assert _guarded_tree(reviewed) >= {"ReviewedDecision", "RReviewResult"}


@pytest.mark.parametrize(
    "sql,exit_code,execution_state,rule_decision",
    [
        ('SELECT * FROM "input"', 0, "completed", "no_alert"),
        ('SELECT * FROM "input" LIMIT 1', 1, "completed", "alert"),
        ('SELECT missing FROM "input"', 3, "failed", "not_evaluable"),
    ],
)
def test_native_pipeline_and_children_require_explicit_outcomes(
    tmp_path, sql, exit_code, execution_state, rule_decision
):
    result = run(tmp_path, registry=registered(sql), comparison=ef.ArrowInput(table()))
    assert result.exit_code == exit_code
    assert result.execution.state == execution_state
    assert result.rules.decision == rule_decision
    assert _guarded_tree(result) >= {
        "PipelineResult",
        "ExecutionResult",
        "RuleEvaluation",
        "CheckResult",
        "ProfileResult",
        "HybridDecision",
        "ComponentDecision",
    }
    assert ef.read_pipeline(tmp_path / result.pipeline_id) == result


@pytest.mark.parametrize("state", ["passed", "failed", "not_evaluable"])
def test_workflow_and_migration_keep_gate_semantics(tmp_path, state):
    token = ef.CancellationToken()
    if state == "not_evaluable":
        token.cancel()
    expected = reference(pa.table({"n": [0, 2]}), tmp_path / "expected.arrow")
    result = ef.run_workflow(
        ef.WorkflowSpec(workflow_id="gates", stages=(stage("one"),)),
        source=CountingSource(),
        expected={"one": expected} if state == "failed" else None,
        work_dir=tmp_path,
        cancellation=token,
    )
    assert result.exit_code == {"passed": 0, "failed": 1, "not_evaluable": 3}[state]
    guarded = _guarded_tree(result)
    assert guarded >= {"WorkflowResult", "WorkflowCheckpoint"}
    if state != "not_evaluable":
        assert guarded >= {"MigrationResult", "PipelineResult", "CompilationCheck"}
        assert result.checkpoints[0].migration.state == "equivalent"
    assert ef.read_workflow(tmp_path / result.run_id) == result


@pytest.mark.parametrize("state", ["passed", "failed", "not_evaluable"])
def test_verification_dimensions_do_not_inherit_presence_as_approval(tmp_path, state):
    output = artifact(tmp_path, "output", table())
    expected = artifact(tmp_path, "expected", table().slice(0, 1) if state == "failed" else table())
    result = ef.verify(
        {"native_capture": output},
        contract=contract(),
        expected=None if state == "not_evaluable" else expected,
        require_expected=True,
        work_dir=tmp_path,
    )
    assert result.operational_state == state
    assert result.publishable is (state == "passed")
    assert _guarded_tree(result) >= {"VerificationResult", "VerificationCheck"}
    assert ef.read_verification(tmp_path / result.verification_id) == result


@pytest.mark.parametrize("state", ["completed", "quarantined", "rejected", "empty"])
def test_ingestion_empty_or_quarantined_output_cannot_approve(tmp_path, state):
    source = tmp_path / "source.jsonl"
    source.write_text(
        ""
        if state == "empty"
        else '{"id":"one","money":"1.00"}\n'
        + ('{"id":"bad","money":"1.001"}\n' if state != "completed" else ""),
        encoding="utf-8",
    )
    result = ef.ingest_file(
        source,
        spec=ef.IngestionSpec(
            format="jsonl",
            fields=fields(),
            invalid_records="quarantine" if state == "quarantined" else "reject",
        ),
        work_dir=tmp_path,
    )
    assert result.state == ("completed" if state == "empty" else state)
    assert result.accepted_records == (0 if state == "empty" else 1)
    assert _guarded_tree(result) == {"IngestionResult"}


@pytest.mark.parametrize("state", ["equivalent", "different", "not_evaluable", "empty"])
def test_generated_reports_are_views_never_gate_authority(tmp_path, state):
    expected = pa.table({"id": [1], "value": [10]})
    candidate = pa.table({"id": [1], "value": [11]}) if state == "different" else expected
    if state == "empty":
        candidate, expected = candidate.slice(0, 0), expected.slice(0, 0)
    result = ef.diff(
        candidate,
        expected,
        keys=["id"],
        work_dir=tmp_path / "comparison",
        options=ef.ComparisonOptions(max_work=1) if state == "not_evaluable" else None,
    )
    report = ef.write_comparison_report(result, tmp_path / "report")
    assert report.state == ("equivalent" if state == "empty" else state)
    assert report.to_text() and report.to_html()
    assert _guarded_tree(report) == {"ComparisonReport"}
    if state in ("equivalent", "empty"):
        ef.assert_equivalent(result)
    else:
        with pytest.raises(ef.EquivalenceAssertionError):
            ef.assert_equivalent(result)


@pytest.mark.parametrize("state", ["no_alert", "alert", "not_evaluable", "empty"])
def test_detector_scores_decisions_and_empty_coverage_remain_separate(state):
    bundle = frozen_bundle()
    if state == "not_evaluable":
        bundle = ef.calibrate_detectors(
            bundle.fit,
            ef.NormalCalibrationProfiles(
                purpose="normal_calibration",
                selection_manifest_sha256="c" * 64,
                profiles=(),
            ),
            alpha="0.5",
        )
    probes = () if state == "empty" else (vector(4 if state == "alert" else 1, 4),)
    joint = ef.detect(bundle, probes)
    component = ef.detect_component(bundle, probes, method="mad")
    assert component.rows == len(probes)
    if state != "empty":
        assert component.decisions[0].result.decision == state
        hybrid = ef.combine_decisions(component.decisions[0].result, component.decisions[0].result)
        assert _guarded_tree(hybrid) >= {"HybridDecision", "ComponentDecision"}
    assert _guarded_tree((joint, component)) >= {
        "DetectionResult",
        "ComponentDetectionResult",
        "DetectorScoreResult",
        "DetectorScores",
    }
    if state != "empty":
        assert _guarded_tree(component) >= {"DetectorDecision", "ComponentDecision"}


def test_unsupported_preflight_is_not_a_comparison_verdict():
    for check in ef.check_migration(spec()):
        assert check.supported is True
        assert _guarded_tree(check) == {"CompilationCheck"}
    unsupported = ef.CompilationCheck(
        engine="example",
        supported=False,
        diagnostics=(
            ef.CompilationDiagnostic(code="unsupported", message="Synthetic restriction"),
        ),
    )
    assert _guarded_tree(unsupported) == {"CompilationCheck"}


@pytest.mark.parametrize("state", ["reduced", "invalid_baseline", "budget_exhausted"])
def test_reduction_status_is_explicit(tmp_path, state):
    kwargs = {}
    if state == "invalid_baseline":
        kwargs["predicate"] = lambda _: ef.ReductionObservation(preconditions="not_evaluable")
    elif state == "budget_exhausted":
        kwargs["options"] = ef.ReductionOptions(max_evaluations=1)
    result = reduce(tmp_path, **kwargs)
    assert result.status == state
    assert _guarded_tree(result) == {"ReductionResult"}


def test_documented_inventory_matches_guarded_types():
    documentation = Path(__file__).resolve().parents[1] / "docs" / "outcome-gates.md"
    text = documentation.read_text(encoding="utf-8")
    for name in GUARDED | {"ComparisonResult", "EquivalenceDecision"}:
        assert f"`{name}`" in text
