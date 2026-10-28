"""Synthetic engineering evidence only; no reviewed thesis models or measured FPR."""

import builtins
import json
from fractions import Fraction
from math import ceil

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from sklearn.ensemble import IsolationForest
from test_preprocessing import spec, training, vector

import equiframe as ef
from equiframe.detector_types import IsolationTree, quantile_rank
from equiframe.profile_types import profile_digest

CONFIG = ef.IsolationForestConfig(random_state=7, n_estimators=17, max_samples=16)
SUPPORT = ef.DetectorSupport(
    min_training_rows=3, min_calibration_rows=2, rationale="Synthetic software test minima"
)


def fit(*profiles, schema=None, support=SUPPORT):
    return ef.fit_detectors(
        training(*(profiles or tuple(vector(i, 16) for i in range(16)))),
        spec=schema or spec(),
        config=CONFIG,
        support=support,
    )


def calibration(*profiles):
    return ef.NormalCalibrationProfiles(
        purpose="normal_calibration",
        selection_manifest_sha256="b" * 64,
        profiles=profiles,
    )


def bundle(fitted=None):
    return ef.calibrate_detectors(
        fitted or fit(), calibration(*(vector(i, 16) for i in range(8))), alpha="0.25"
    )


def test_same_matrix_native_sklearn_reference_and_exact_restore(tmp_path):
    profiles = tuple(vector(i, 16) for i in range(16))
    fitted = fit(*profiles)
    # Producer identity is the executing distribution, independently of the
    # unchanged model algorithm and historically readable explicit records.
    assert fitted.versions.equiframe == ef.__version__
    matrix = ef.transform_profiles(fitted.preprocessor, profiles)
    assert fitted.training_matrix_sha256 == profile_digest(matrix.model_dump(mode="json"))
    reference = IsolationForest(
        random_state=7, n_estimators=17, max_samples=16, contamination="auto", n_jobs=1
    ).fit(np.asarray(matrix.values, dtype=np.float32))
    probes = (vector(0, 16), vector(5, 16), vector(1, 1), vector(0, 0))
    scores = ef.score_detectors(fitted, probes)
    reference_scores = -reference.score_samples(
        np.asarray(ef.transform_profiles(fitted.preprocessor, probes).values, dtype=np.float32)
    )
    np.testing.assert_allclose(scores.m.values, reference_scores, rtol=1e-14, atol=1e-15)
    assert fitted.b.medians == (0.46875, 0.0, 0.0)
    assert fitted.b.deviations == (0.25, 0.0, 0.0)
    assert scores.b.values == (1.875, 0.625, 2.125, "+infinity")
    saved = bundle(fitted)
    path = tmp_path / "model.json"
    fingerprint = ef.write_detector_bundle(saved, path)
    restored = ef.read_detector_bundle(path, expected_sha256=fingerprint)
    assert restored == saved
    assert ef.detect(saved, probes) == ef.detect(restored, probes)
    assert ef.DetectorFit.model_validate_json(fitted.model_dump_json()) == fitted
    with pytest.raises(FileExistsError):
        ef.write_detector_bundle(saved, path)
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_detector_bundle(path, expected_sha256="f" * 64)


@pytest.mark.parametrize("samples", [2, 3, 7, 32])
def test_forest_subsamples_and_repeated_rows_match_reference(samples):
    profiles = tuple(vector(i % 4, 8) for i in range(20))
    config = CONFIG.model_copy(update={"max_samples": samples})
    fitted = ef.fit_detectors(training(*profiles), spec=spec(), config=config, support=SUPPORT)
    matrix = ef.transform_profiles(fitted.preprocessor, profiles)
    reference = IsolationForest(
        random_state=7, n_estimators=17, max_samples=min(samples, 20), contamination="auto"
    ).fit(np.asarray(matrix.values, dtype=np.float32))
    np.testing.assert_allclose(
        ef.score_detectors(fitted, profiles).m.values,
        -reference.score_samples(np.asarray(matrix.values, dtype=np.float32)),
        rtol=1e-14,
    )
    assert fitted.m.effective_samples == min(samples, 20)


def test_calibration_is_external_exact_and_never_refits():
    fitted = fit(vector(0, 1), vector(1, 2), vector(1, 1))
    frozen = fitted.model_dump_json()
    normal = calibration(vector(1, 4), vector(1, 2), vector(3, 4), vector(1, 1))
    calibrated = ef.calibrate_detectors(fitted, normal, alpha="0.25")
    assert fitted.model_dump_json() == frozen
    assert calibrated.b.scores == (0.5, 0.0, 0.5, 1.0)
    assert calibrated.b.rank == 3 and calibrated.b.threshold == 0.5
    result = ef.detect(calibrated, (vector(3, 4), vector(1, 1)))
    assert result.b[0].result.decision == "no_alert"  # equality is strictly non-alert
    assert result.b[1].result.decision == "alert"
    assert calibrated.m.threshold == sorted(calibrated.m.scores)[2]
    assert ef.detect(calibrated, ()).m == ()


@given(n=st.integers(min_value=1, max_value=10000), percent=st.integers(1, 99))
def test_quantile_position_exact_rational_property(n, percent):
    alpha = f"0.{percent:02d}"
    assert quantile_rank(alpha, n) == ceil(Fraction(100 - percent, 100) * n)


def test_quantile_decimal_boundary_does_not_round_up():
    assert quantile_rank("0.7", 10) == 3
    assert quantile_rank("0.05", 20) == 19
    assert quantile_rank("0.000000000000000001", 2) == 2


@pytest.mark.parametrize("alpha", [0.05, "0", "1", "0.0", "0.000", "-0.1", "NaN", "1/20"])
def test_alpha_must_be_explicit_decimal_in_open_unit_interval(alpha):
    with pytest.raises(ValueError):
        quantile_rank(alpha, 5)


def test_mad_zero_support_and_infinite_calibration_are_explicit():
    fitted = fit(vector(0, 1), vector(0, 1), vector(1, 1))
    assert fitted.b.deviations == (0.0, 0.0, 0.0)
    scores = ef.score_detectors(fitted, (vector(0, 1), vector(1, 1)))
    assert scores.b.values == (0.0, "+infinity")
    unestimable = ef.calibrate_detectors(
        fitted, calibration(vector(0, 1), vector(1, 1)), alpha="0.05"
    )
    assert unestimable.b.state == "not_estimable"
    assert unestimable.b.threshold == "+infinity"
    assert unestimable.b.reason == "infinite_calibration_threshold"
    result = ef.detect(unestimable, (vector(1, 1),))
    assert result.b[0].result.decision == "not_evaluable"
    assert result.b[0].score == "+infinity"
    # Infinity in some scores does not invalidate a finite selected order statistic.
    finite = ef.calibrate_detectors(fitted, calibration(vector(0, 1), vector(1, 1)), alpha="0.5")
    assert finite.b.threshold == 0.0
    assert ef.detect(finite, (vector(1, 1),)).b[0].result.decision == "alert"
    assert "Infinity" not in unestimable.model_dump_json()
    assert ef.DetectorBundle.model_validate_json(unestimable.model_dump_json()) == unestimable


@pytest.mark.parametrize(
    "profiles,reason",
    [
        ((), "preprocessor_not_estimable"),
        ((vector(0, 0),) * 3, "preprocessor_not_estimable"),
        ((vector(0, 1), vector(1, 1)), "insufficient_training_rows"),
        ((vector(1, 2),) * 3, "no_training_variation"),
    ],
)
def test_unestimable_training_never_means_no_alert(profiles, reason):
    fitted = ef.fit_detectors(training(*profiles), spec=spec(), config=CONFIG, support=SUPPORT)
    assert fitted.m.reason == fitted.b.reason == reason
    result = ef.detect(bundle(fitted), (vector(0, 1),))
    assert result.m[0].result.decision == result.b[0].result.decision == "not_evaluable"
    assert result.m[0].score is None


@pytest.mark.parametrize("n", [0, 1])
def test_insufficient_calibration_preserves_scores_but_no_decision(n):
    fitted = fit()
    calibrated = ef.calibrate_detectors(
        fitted, calibration(*(vector(i, 3) for i in range(n))), alpha="0.05"
    )
    assert calibrated.m.reason == calibrated.b.reason == "insufficient_calibration_rows"
    result = ef.detect(calibrated, (vector(0, 1),))
    assert result.m[0].score is not None
    assert result.m[0].result.decision == "not_evaluable"


def test_float32_loss_of_variation_is_not_silent():
    fitted = fit(vector(50000000, 100000000), vector(50000001, 100000000), vector(1, 2))
    assert fitted.m.state == "not_estimable" and fitted.m.reason == "no_float32_variation"
    assert fitted.b.state == "fitted"


def test_native_tiny_variation_matches_installed_sklearn_splits():
    # Native sklearn thresholds changed across permitted versions. Do not
    # promise identical fitted trees across them or suppress a real split.
    profiles = (vector(0, 10**9), vector(1, 10**9), vector(2, 10**9))
    fitted = fit(*profiles)
    matrix = ef.transform_profiles(fitted.preprocessor, profiles)
    native = IsolationForest(
        random_state=7, n_estimators=17, max_samples=3, contamination="auto", n_jobs=1
    ).fit(np.asarray(matrix.values, dtype=np.float32))
    has_split = any(tree.tree_.node_count > 1 for tree in native.estimators_)
    if has_split:
        assert fitted.m.state == "fitted"
        np.testing.assert_allclose(
            ef.score_detectors(fitted, profiles).m.values,
            -native.score_samples(np.asarray(matrix.values, dtype=np.float32)),
            rtol=1e-14,
        )
    else:
        assert fitted.m.state == "not_estimable" and fitted.m.reason == "no_isolation_splits"
    assert fitted.b.state == "fitted"


def test_degenerate_native_forest_is_not_estimable(monkeypatch):
    # Fault-inject an actual fitted but unsplit native model. This guard must
    # not depend on the installed sklearn version's tiny-value threshold.
    native_fit = IsolationForest.fit

    def without_splits(model, matrix, *args, **kwargs):
        return native_fit(model, np.zeros_like(matrix), *args, **kwargs)

    monkeypatch.setattr(IsolationForest, "fit", without_splits)
    fitted = fit(vector(0, 16), vector(1, 16), vector(2, 16))
    assert fitted.m.state == "not_estimable" and fitted.m.reason == "no_isolation_splits"
    assert fitted.b.state == "fitted"


def test_actual_rule_evaluation_retains_alert_when_m_is_missing(tmp_path):
    import pyarrow as pa
    from rule_helpers import captured
    from test_rules import example, rule

    # The helper uses captured synthetic tables; this tests the actual R -> H boundary.
    contract = example("aggregations").model_copy(
        update={
            "rules": (rule("count", ef.CardinalityCheck(table="result", minimum=1, maximum=1)),),
            "preconditions": (),
        }
    )
    execution = captured(
        contract,
        {"source": pa.table({"currency": ["USD"], "amount": [1]})},
        pa.table({"currency": ["USD", "EUR"], "total": [1, 2]}),
        tmp_path,
    )
    rules = ef.evaluate_rules(execution, work_dir=tmp_path / "rules")
    model = ef.ComponentDecision(decision="not_evaluable", complete=False, reason="no_model")
    hybrid = ef.combine_decisions(rules, model)
    assert rules.decision == hybrid.result.decision == "alert"
    assert hybrid.r.decision == rules.decision and hybrid.r.complete == rules.complete
    assert not hybrid.result.complete


@pytest.mark.parametrize(
    "family", ["nulls_types", "joins", "duplicates_order", "aggregations", "dates"]
)
def test_family_scoping_and_incompatible_profiles(family):
    schema = spec().model_copy(update={"family": family})
    fitted = fit(*(vector(i, 5, schema) for i in range(5)), schema=schema)
    assert fitted.m.state == fitted.b.state == "fitted"
    other = schema.model_copy(update={"family": "joins" if family != "joins" else "dates"})
    with pytest.raises(ValueError, match="incompatible"):
        ef.score_detectors(fitted, (vector(1, 2, other),))


def test_failed_measurements_and_leaked_metadata_rejected():
    fitted = fit()
    base = vector(1, 2)
    failed = base.model_copy(
        update={
            "observations": (
                ef.FeatureObservation(
                    name="null_rate", state="not_evaluable", reason="capture_failed"
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="failed measurements"):
        ef.score_detectors(fitted, (failed,))
    with pytest.raises(ValidationError):
        ef.ProfileVector.model_validate({**base.model_dump(), "label": "normal"})
    with pytest.raises(ValidationError):
        ef.calibrate_detectors(fitted, training(base), alpha="0.05")
    with pytest.raises(ValueError, match="must differ"):
        ef.calibrate_detectors(
            fitted,
            calibration(base).model_copy(update={"selection_manifest_sha256": "a" * 64}),
            alpha="0.05",
        )


@pytest.mark.parametrize(
    "fault", ["version", "order", "threshold", "rank", "count", "feature", "cycle", "samples"]
)
def test_corrupted_bundle_is_rejected(fault, tmp_path):
    value = json.loads(bundle().model_dump_json())
    if fault == "version":
        value["schema_version"] = "99.0"
    elif fault == "order":
        value["fit"]["preprocessor"]["features"][0]["name"] = "wrong"
    elif fault == "threshold":
        value["m"]["threshold"] = 999.0
    elif fault == "rank":
        value["m"]["rank"] = 999
    elif fault == "count":
        value["m"]["sample_count"] = 999
    else:
        node = value["fit"]["m"]["trees"][0]["nodes"][0]
        node[{"feature": "feature", "cycle": "left", "samples": "samples"}[fault]] = (
            0 if fault == "cycle" else 99999
        )
    path = tmp_path / "corrupt.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        ef.read_detector_bundle(path)


def test_tree_rejects_disconnected_shared_children_and_partial_nodes():
    for nodes in [
        [{"samples": 1}, {"samples": 1}],
        [{"samples": 2, "left": 1, "right": 1, "feature": 0, "threshold": 0.5}, {"samples": 1}],
        [{"samples": 2, "left": 1}],
    ]:
        with pytest.raises(ValueError):
            IsolationTree.model_validate_json(json.dumps({"nodes": nodes}))


def test_duplicate_json_keys_and_nonfinite_numbers_rejected(tmp_path):
    path = tmp_path / "invalid.json"
    for payload in ['{"schema_version":"1.0","schema_version":"1.0"}', '{"x":NaN}']:
        path.write_text(payload, encoding="utf-8")
        with pytest.raises((ValueError, ef.ContractParseError)):
            ef.read_detector_bundle(path)


def test_missing_ml_dependency_and_declarative_scoring(monkeypatch, tmp_path):
    saved = bundle()
    path = tmp_path / "bundle.json"
    ef.write_detector_bundle(saved, path)
    original = builtins.__import__

    def no_ml(name, *args, **kwargs):
        if name.split(".")[0] in ("numpy", "sklearn"):
            raise ImportError("test deliberately omits ML extras")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_ml)
    assert ef.detect(ef.read_detector_bundle(path), (vector(1, 1),)).m[0].score is not None
    with pytest.raises(ef.MissingDependencyError, match=r"equiframe\[ml\]"):
        fit()


@pytest.mark.parametrize(
    "r,m,expected",
    [
        ("alert", "alert", "alert"),
        ("alert", "no_alert", "alert"),
        ("alert", "not_evaluable", "alert"),
        ("no_alert", "alert", "alert"),
        ("no_alert", "no_alert", "no_alert"),
        ("no_alert", "not_evaluable", "not_evaluable"),
        ("not_evaluable", "alert", "alert"),
        ("not_evaluable", "no_alert", "not_evaluable"),
        ("not_evaluable", "not_evaluable", "not_evaluable"),
    ],
)
def test_hybrid_nine_combinations(r, m, expected):
    def component(state):
        available = state != "not_evaluable"
        return ef.ComponentDecision(
            decision=state, complete=available, reason=None if available else "missing"
        )

    result = ef.combine_decisions(component(r), component(m))
    assert result.result.decision == expected
    assert result.result.complete == (r != "not_evaluable" and m != "not_evaluable")


def test_partial_rule_alert_is_preserved_and_cannot_claim_complete():
    r = ef.ComponentDecision(decision="alert", complete=False, reason="some_rules_failed")
    m = ef.ComponentDecision(decision="no_alert", complete=True)
    result = ef.combine_decisions(r, m)
    assert result.result.decision == "alert" and not result.result.complete
    with pytest.raises(ValueError):
        ef.ComponentDecision(decision="no_alert", complete=False, reason="missing")
