"""Independent R review: unavailable states and, when installed, real base R."""

import math
import os
import shutil
from decimal import Decimal

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.comparison_types import ComparisonPolicy
from equiframe.diff_contracts import infer_diff_contract
from equiframe.r_review import RReviewOptions, review_with_r


def declaration():
    return infer_diff_contract(pa.schema([("value", pa.int64())]))


def test_missing_r_is_not_evaluable_instead_of_equivalent():
    table = pa.table({"value": [1, 2]})
    result = review_with_r(
        table,
        table,
        contract=declaration(),
        options=RReviewOptions(rscript="equiframe-qa-nonexistent-rscript"),
    )
    assert result.state == "not_evaluable"
    assert not result.complete
    assert result.reason == "rscript_unavailable"
    assert result.r_version is None


def test_r_does_not_silently_replace_a_relaxed_type_contract():
    table = pa.table({"value": [1, 2]})
    contract = infer_diff_contract(
        table.schema,
        policy=ComparisonPolicy(
            physical_types="lossless", justification="Deliberate unsupported review policy"
        ),
    )
    result = review_with_r(
        table,
        table,
        contract=contract,
        options=RReviewOptions(rscript="equiframe-qa-nonexistent-rscript"),
    )
    assert result.state == "not_evaluable"
    assert not result.complete
    assert result.reason == "r_review_requires_exact_physical_types"


@pytest.mark.parametrize(
    "right,expected,matched,unmatched",
    [
        ([2, 1], "equivalent", 2, 0),
        ([1, 3], "different", 1, 2),
        ([1, 1, 2], "different", 2, 1),
    ],
)
def test_real_base_r_compares_values_and_multiplicity(right, expected, matched, unmatched):
    executable = os.environ.get("EQUIFRAME_QA_RSCRIPT") or shutil.which("Rscript")
    if executable is None:
        pytest.skip("Real Rscript unavailable; this is not a passing R runtime test")
    left = pa.table({"value": [1, 2]})
    result = review_with_r(
        left,
        pa.table({"value": right}),
        contract=declaration(),
        options=RReviewOptions(rscript=executable),
    )
    assert result.complete, result.reason
    assert result.state == expected
    assert result.matched_rows == matched
    assert result.unmatched_rows == unmatched
    assert result.returncode == 0
    assert result.r_version
    assert result.left_transport_sha256 and result.right_transport_sha256


def real_options():
    executable = os.environ.get("EQUIFRAME_QA_RSCRIPT") or shutil.which("Rscript")
    if executable is None:
        pytest.skip("Real Rscript unavailable; this is not a passing R runtime test")
    return RReviewOptions(rscript=executable)


def test_r_binding_matches_the_actual_compared_artifacts(tmp_path):
    left = pa.table({"value": [1, 2]})
    right = pa.table({"value": [1, 3]})
    compared = ef.diff(left, right, contract=declaration(), work_dir=tmp_path / "compare")
    review = review_with_r(
        left, right, contract=compared.spec, comparison=compared, options=real_options()
    )
    assert review.complete, review.reason
    assert review.state == "different"
    assert review.binding.comparison_id == compared.comparison_id
    assert review.binding.left_artifact_sha256 == compared.left.data.sha256
    assert review.binding.right_artifact_sha256 == compared.right.data.sha256


def test_r_rejects_comparison_with_other_input_values(tmp_path):
    left = pa.table({"value": [1, 2]})
    compared = ef.diff(left, left, contract=declaration(), work_dir=tmp_path / "compare")
    review = review_with_r(
        pa.table({"value": [99, 2]}),
        left,
        contract=compared.spec,
        comparison=compared,
        options=real_options(),
    )
    assert not review.complete
    assert review.state == "not_evaluable"
    assert review.reason == "r_review_comparison_data_mismatch"
    assert review.binding is None


def test_previous_alert_survives_missing_r():
    result = ef.finalize_with_r(
        ef.ComponentDecision(decision="alert", complete=True),
        ef.ComponentDecision(decision="no_alert", complete=True),
        left=pa.table({"value": [1]}),
        right=pa.table({"value": [1]}),
        contract=declaration(),
        options=RReviewOptions(rscript="equiframe-qa-nonexistent-rscript"),
    )
    assert result.result.decision == "alert"
    assert not result.result.complete
    assert not result.accepted


@pytest.fixture
def native_execution_context(tmp_path):
    """A real native execution and tiny synthetic IF fit; no scientific claim."""
    table = pa.table({"value": [1, 2, 3, 4]})
    contract = declaration().spec.contract.model_copy(
        update={
            "rules": (
                ef.RuleSpec(
                    rule_id="qa_schema",
                    revision=1,
                    required=True,
                    severity="error",
                    specification=ef.SchemaCheck(table="result"),
                ),
            )
        }
    )
    registry = ef.TransformationRegistry()
    registry.register(
        ef.PandasTransformation(
            "qa_identity", lambda frames, context: frames["source"].copy(), "qa-1"
        )
    )
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract, engine="pandas", transformation_id="qa_identity"),
        source=ef.LocalDataSource({"source": ef.ArrowInput(table)}),
        registry=registry,
        work_dir=tmp_path / "execution",
    )
    assert execution.state == "completed"
    rules = ef.evaluate_rules(execution, work_dir=tmp_path / "rules")
    spec = ef.ProfileSpec(
        family="nulls_types",
        features=(ef.ProfileFeature(name="rows", metric="log_filas", table="result"),),
    )
    profile = ef.profile_execution(execution, spec=spec, work_dir=tmp_path / "profile")
    vectors = tuple(
        ef.ProfileVector(
            spec=spec,
            spec_sha256=ef.profile_spec_fingerprint(spec),
            observations=(
                ef.FeatureObservation(
                    name="rows", state="available", numerator=count, value=math.log1p(count)
                ),
            ),
        )
        for count in range(1, 8)
    )
    fit = ef.fit_detectors(
        ef.NormalTrainingProfiles(
            purpose="normal_training", selection_manifest_sha256="a" * 64, profiles=vectors
        ),
        spec=spec,
        config=ef.IsolationForestConfig(random_state=17, n_estimators=4, max_samples=7),
        support=ef.DetectorSupport(
            min_training_rows=3,
            min_calibration_rows=2,
            rationale="Tiny synthetic software fixture, not a validated thesis model",
        ),
    )
    bundle = ef.calibrate_detectors(
        fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration", selection_manifest_sha256="b" * 64, profiles=vectors
        ),
        alpha="0.2",
    )
    detection = ef.detect_component(bundle, (profile.vector,), method="isolation_forest")
    comparison = ef.diff(
        execution,
        ef.ArrowInput(table),
        contract=contract,
        policy=ef.ComparisonPolicy(
            index="ignore",
            justification="Explicitly ignore the Pandas index in this software fixture",
        ),
        work_dir=tmp_path / "comparison",
    )
    return execution, rules, profile, detection, comparison


def test_bound_finalization_uses_real_rules_profile_if_and_r(native_execution_context):
    execution, rules, profile, detection, comparison = native_execution_context
    result = ef.finalize_execution_with_r(
        execution, rules, profile, detection, comparison=comparison, options=real_options()
    )
    assert result.r_review.complete, result.r_review.reason
    assert result.r_review.state == "equivalent"
    assert result.execution_binding.execution_id == execution.execution_id
    assert result.execution_binding.profile_id == profile.metadata.profile_id
    assert result.execution_binding.output_sha256 == execution.output.data.sha256
    assert result.result.complete
    assert result.accepted == (
        rules.decision == detection.decisions[0].result.decision == "no_alert"
    )


@pytest.mark.parametrize("other", ["rules", "profile", "detection"])
def test_bound_finalization_rejects_unrelated_execution_information(
    native_execution_context, other
):
    execution, rules, profile, detection, comparison = native_execution_context
    if other == "rules":
        rules = rules.model_copy(update={"execution_id": "exec_unrelated"})
    elif other == "profile":
        profile = profile.model_copy(
            update={
                "metadata": profile.metadata.model_copy(update={"execution_id": "exec_unrelated"})
            }
        )
    else:
        detection = detection.model_copy(update={"profiles_sha256": "f" * 64})
    with pytest.raises(ValueError, match="belong"):
        ef.finalize_execution_with_r(
            execution, rules, profile, detection, comparison=comparison, options=real_options()
        )


@pytest.mark.parametrize(
    "dtype,left_values,right_values,expected",
    [
        (pa.string(), ["", "雪"], ["", "雪"], "equivalent"),
        (pa.bool_(), [True, None], [False, None], "different"),
        (pa.int64(), [9007199254740993], [9007199254740992], "different"),
        (
            pa.decimal128(38, 9),
            [Decimal("12345678901234567890.123456789")],
            [Decimal("12345678901234567890.123456788")],
            "different",
        ),
        (pa.float64(), [None, float("nan")], [None, None], "different"),
        (pa.timestamp("ns", "UTC"), [1700000000000000001], [1700000000000000002], "different"),
    ],
    ids=[
        "unicode-empty",
        "boolean-null",
        "integer-over-double",
        "decimal-exact",
        "null-versus-nan",
        "timestamp-ns-utc",
    ],
)
def test_real_r_preserves_critical_type_distinctions(dtype, left_values, right_values, expected):
    left = pa.table({"value": pa.array(left_values, type=dtype, from_pandas=False)})
    right = pa.table({"value": pa.array(right_values, type=dtype, from_pandas=False)})
    result = review_with_r(
        left, right, contract=ef.infer_diff_contract(left.schema), options=real_options()
    )
    assert result.complete, result.reason
    assert result.state == expected
    assert result.returncode == 0 and result.r_version


def test_real_r_enforces_unique_keys_even_for_identical_invalid_inputs():
    table = pa.table({"value": [1, 1]})
    result = review_with_r(
        table,
        table,
        contract=ef.infer_diff_contract(table.schema, keys=("value",)),
        options=real_options(),
    )
    assert result.complete, result.reason
    assert result.state == "different"
    assert result.contract_violations > 0


def test_real_r_does_not_sort_significant_order_to_hide_a_difference():
    left = pa.table({"value": [1, 2]})
    right = pa.table({"value": [2, 1]})
    columns = declaration().spec.contract.output.schema_spec.columns
    contract = ef.sequence_contract(
        columns, by=(ef.SortSpec(column="value", direction="ascending", nulls="last"),)
    )
    result = review_with_r(left, right, contract=contract, options=real_options())
    assert result.complete, result.reason
    assert result.state == "different"
