"""Independent declarative forest, parity, availability and isolated scoring."""

import math

import pytest
from pydantic import ValidationError
from test_preprocessing import spec, training, vector

import equiframe as ef
from equiframe.detector_types import IsolationNode, IsolationTree
from equiframe.profile_types import profile_digest


def frozen_bundle():
    profiles = tuple(vector(i, 4) for i in (0, 1, 2, 4))
    preprocessor = ef.fit_preprocessor(training(*profiles), spec=spec())
    matrix = ef.transform_profiles(preprocessor, profiles)
    fitted = ef.DetectorFit(
        preprocessor=preprocessor,
        config=ef.IsolationForestConfig(random_state=7, n_estimators=1, max_samples=4),
        support=ef.DetectorSupport(
            min_training_rows=2, min_calibration_rows=2, rationale="Synthetic software fixture"
        ),
        versions=ef.DetectorVersions(
            python="3.12", sklearn="declarative-test-fixture", numpy="declarative-test-fixture"
        ),
        training_matrix_sha256=profile_digest(matrix.model_dump(mode="json")),
        m=ef.DetectorModel(
            method="isolation_forest",
            state="fitted",
            effective_samples=4,
            trees=(
                IsolationTree(
                    nodes=(
                        IsolationNode(samples=4, left=1, right=2, feature=0, threshold=0.125),
                        IsolationNode(samples=1),
                        IsolationNode(samples=3, left=3, right=4, feature=0, threshold=0.75),
                        IsolationNode(samples=2),
                        IsolationNode(samples=1),
                    )
                ),
            ),
        ),
        b=ef.DetectorModel(
            method="mad", state="fitted", medians=(0.375, 0.0, 0.0), deviations=(0.25, 0.0, 0.0)
        ),
    )
    return ef.calibrate_detectors(
        fitted,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration", selection_manifest_sha256="b" * 64, profiles=profiles
        ),
        alpha="0.5",
    )


@pytest.mark.parametrize("method,field", [("isolation_forest", "m"), ("mad", "b")])
def test_single_component_matches_joint_inference_and_restoration(tmp_path, method, field):
    bundle = frozen_bundle()
    probes = (vector(0, 4), vector(1, 4), vector(4, 4), vector(0, 0))
    joint = ef.detect(bundle, probes)
    component = ef.detect_component(bundle, probes, method=method)
    assert component.scores == getattr(joint.scores, field)
    assert component.decisions == getattr(joint, field)
    assert component.matrix_sha256 == joint.scores.matrix_sha256
    assert component.bundle_sha256 == joint.bundle_sha256
    assert component.fit_sha256 == joint.scores.fit_sha256
    assert component.profiles_sha256 == profile_digest([p.model_dump(mode="json") for p in probes])
    path = tmp_path / "model.json"
    fingerprint = ef.write_detector_bundle(bundle, path)
    restored = ef.read_detector_bundle(path, expected_sha256=fingerprint)
    assert ef.detect_component(restored, probes, method=method) == component
    assert ef.ComponentDetectionResult.model_validate_json(component.model_dump_json()) == component
    assert ef.detect_component(bundle, (), method=method).decisions == ()


def test_forest_reference_and_other_scorer_is_never_called(monkeypatch):
    import equiframe.detectors as detectors

    def forbidden(*args):
        raise AssertionError("the other detector was evaluated")

    bundle = frozen_bundle()
    frozen = bundle.model_dump_json()
    monkeypatch.setattr(detectors, "_mad_score", forbidden)
    result = ef.detect_component(bundle, (vector(0, 4),), method="isolation_forest")
    average_path = 2 * (math.log(3) + 0.5772156649015329) - 2 * 3 / 4
    assert result.scores.values[0] == pytest.approx(2 ** (-1 / average_path))
    assert bundle.model_dump_json() == frozen


def test_mad_reference_without_forest_inference(monkeypatch):
    import equiframe.detectors as detectors

    bundle = frozen_bundle()

    def forbidden(*args):
        raise AssertionError("the forest was evaluated")

    monkeypatch.setattr(detectors, "_forest_score", forbidden)
    result = ef.detect_component(bundle, (vector(0, 4), vector(4, 4)), method="mad")
    assert result.scores.values == (1.5, 2.5)
    assert [d.result.decision for d in result.decisions] == ["alert", "alert"]


@pytest.mark.parametrize("method", ["isolation_forest", "mad"])
def test_missing_calibration_preserves_scores_and_unavailable_decision(method):
    bundle = frozen_bundle()
    unsupported = ef.calibrate_detectors(
        bundle.fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration", selection_manifest_sha256="c" * 64, profiles=()
        ),
        alpha="0.5",
    )
    result = ef.detect_component(unsupported, (vector(1, 4),), method=method)
    assert not result.complete
    assert result.decisions[0].score is not None
    assert result.decisions[0].result.decision == "not_evaluable"
    assert result.decisions[0].result.reason == "insufficient_calibration_rows"


def test_incompatible_and_failed_profiles_and_invalid_method_are_rejected():
    bundle = frozen_bundle()
    with pytest.raises(ValueError, match="method"):
        ef.detect_component(bundle, (vector(0, 4),), method="unknown")
    other = spec().model_copy(update={"family": "dates"})
    with pytest.raises(ValueError, match="incompatible"):
        ef.detect_component(bundle, (vector(1, 4, other),), method="isolation_forest")
    failed = vector(1, 4).model_copy(
        update={
            "observations": (
                ef.FeatureObservation(name="null_rate", state="not_evaluable", reason="failed"),
            )
        }
    )
    with pytest.raises(ValueError, match="failed measurements"):
        ef.detect_component(bundle, (failed,), method="isolation_forest")


def test_component_result_rejects_missing_matrix_and_tampered_scores():
    result = ef.detect_component(frozen_bundle(), (vector(0, 4),), method="isolation_forest")
    with pytest.raises(ValidationError, match="fingerprint"):
        ef.ComponentDetectionResult.model_validate({**result.model_dump(), "matrix_sha256": None})
    with pytest.raises(ValidationError, match="actual component scores"):
        ef.ComponentDetectionResult.model_validate(
            {**result.model_dump(), "scores": ef.DetectorScores(state="scored", values=(0.3,))}
        )


def test_unestimable_model_preserves_none_scores_without_calling_other_detector(monkeypatch):
    import equiframe.detectors as detectors

    fitted = frozen_bundle().fit
    unavailable = fitted.model_copy(
        update={
            "m": ef.DetectorModel(
                method="isolation_forest", state="not_estimable", reason="no_forest_support"
            )
        }
    )
    bundle = ef.calibrate_detectors(
        unavailable,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration", selection_manifest_sha256="c" * 64, profiles=()
        ),
        alpha="0.5",
    )

    def forbidden(*args):
        raise AssertionError("the other scorer was evaluated")

    monkeypatch.setattr(detectors, "_mad_score", forbidden)
    result = ef.detect_component(bundle, (vector(1, 4),), method="isolation_forest")
    assert not result.complete and result.scores.state == "not_estimable"
    assert result.scores.values == () and result.scores.reason == "no_forest_support"
    assert result.decisions[0].score is None and result.decisions[0].threshold is None
    assert result.decisions[0].result.decision == "not_evaluable"
