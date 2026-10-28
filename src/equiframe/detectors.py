"""Fit, score and calibrate family detectors independently from rules and the oracle."""

import math
import platform
import struct
from fractions import Fraction
from pathlib import Path
from typing import Literal

from equiframe._document_io import read_document as _read_document
from equiframe._document_io import write_document as _write_document
from equiframe._regular_io import local_input_path
from equiframe.detector_types import (
    ComponentDecision,
    ComponentDetectionResult,
    DetectionResult,
    DetectorBundle,
    DetectorCalibration,
    DetectorDecision,
    DetectorFit,
    DetectorModel,
    DetectorScoreResult,
    DetectorScores,
    DetectorSupport,
    DetectorVersions,
    IsolationForestConfig,
    IsolationNode,
    IsolationTree,
    NormalCalibrationProfiles,
    ScoreValue,
    detector_fingerprint,
    numeric_score,
    quantile_rank,
)
from equiframe.errors import ArtifactIntegrityError, MissingDependencyError, ResourceLimitError
from equiframe.preprocessing import _compatible, fit_preprocessor, transform_profiles
from equiframe.profile_types import (
    FeatureMatrix,
    NormalTrainingProfiles,
    ProfileSpec,
    ProfileVector,
    profile_digest,
)


def _unavailable(method: Literal["isolation_forest", "mad"], reason: str) -> DetectorModel:
    return DetectorModel(method=method, state="not_estimable", reason=reason)


def _float32(row: tuple[float, ...]) -> tuple[float, ...]:
    try:
        converted = tuple(struct.unpack("f", struct.pack("f", v))[0] for v in row)
    except (OverflowError, struct.error) as exc:
        raise ValueError("Isolation Forest input is outside finite float32 range") from exc
    if not all(math.isfinite(v) for v in converted):
        raise ValueError("Isolation Forest input is outside finite float32 range")
    return converted


def _fit_forest(
    matrix: FeatureMatrix, config: IsolationForestConfig
) -> tuple[DetectorModel, str | None, str | None]:
    converted = tuple(_float32(row) for row in matrix.values)
    if len(set(converted)) < 2:
        return _unavailable("isolation_forest", "no_float32_variation"), None, None
    try:
        import numpy as np
        import sklearn
        from sklearn.ensemble import IsolationForest
    except ImportError as exc:
        raise MissingDependencyError("Isolation Forest fit requires equiframe[ml]") from exc
    samples = min(config.max_samples, len(matrix.values))
    model = IsolationForest(
        n_estimators=config.n_estimators,
        max_samples=samples,
        random_state=config.random_state,
        contamination="auto",
        max_features=1.0,
        bootstrap=False,
        n_jobs=1,
    ).fit(np.asarray(converted, dtype=np.float32))
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        nodes = []
        for i in range(tree.node_count):
            leaf = tree.children_left[i] == -1
            nodes.append(
                IsolationNode(
                    samples=int(tree.n_node_samples[i]),
                    left=None if leaf else int(tree.children_left[i]),
                    right=None if leaf else int(tree.children_right[i]),
                    feature=None if leaf else int(tree.feature[i]),
                    threshold=None if leaf else float(tree.threshold[i]),
                )
            )
        trees.append(IsolationTree(nodes=tuple(nodes)))
    if not any(len(tree.nodes) > 1 for tree in trees):
        return (
            _unavailable("isolation_forest", "no_isolation_splits"),
            sklearn.__version__,
            np.__version__,
        )
    return (
        DetectorModel(
            method="isolation_forest", state="fitted", trees=tuple(trees), effective_samples=samples
        ),
        sklearn.__version__,
        np.__version__,
    )


def _median(values: tuple[float, ...]) -> float:
    # statistics.median can overflow while averaging two finite positive numbers.
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return float((Fraction(ordered[middle - 1]) + Fraction(ordered[middle])) / 2)


def fit_detectors(
    training: NormalTrainingProfiles,
    *,
    spec: ProfileSpec,
    config: IsolationForestConfig,
    support: DetectorSupport,
    empty_policy: Literal["drop", "not_estimable"] = "drop",
) -> DetectorFit:
    """Fit M and B on the same matrix. Eligibility is verified by the caller/benchmark."""
    config = IsolationForestConfig.model_validate(config)
    support = DetectorSupport.model_validate(support)
    training = NormalTrainingProfiles.model_validate(training)
    preprocessor = fit_preprocessor(training, spec=spec, empty_policy=empty_policy)
    matrix = (
        transform_profiles(preprocessor, training.profiles)
        if preprocessor.state == "ready"
        else None
    )
    reason = (
        "preprocessor_not_estimable"
        if matrix is None
        else "insufficient_training_rows"
        if len(matrix.values) < support.min_training_rows
        else "no_training_variation"
        if len(set(matrix.values)) < 2
        else None
    )
    sklearn_version = numpy_version = None
    if reason is not None:
        m = _unavailable("isolation_forest", reason)
        b = _unavailable("mad", reason)
    else:
        if not (matrix is not None):
            raise AssertionError("Internal invariant check failed.")
        columns = tuple(zip(*matrix.values, strict=True))
        medians = tuple(_median(c) for c in columns)
        deviations = tuple(
            _median(tuple(abs(v - center) for v in values))
            for center, values in zip(medians, columns, strict=True)
        )
        b = DetectorModel(method="mad", state="fitted", medians=medians, deviations=deviations)
        m, sklearn_version, numpy_version = _fit_forest(matrix, config)
    return DetectorFit(
        preprocessor=preprocessor,
        config=config,
        support=support,
        versions=DetectorVersions(
            python=platform.python_version(), sklearn=sklearn_version, numpy=numpy_version
        ),
        training_matrix_sha256=profile_digest(matrix.model_dump(mode="json")) if matrix else None,
        m=m,
        b=b,
    )


def _average_path(samples: int) -> float:
    if samples <= 1:
        return 0.0
    if samples == 2:
        return 1.0
    # The approximation used by sklearn IsolationForest, not the harmonic series.
    return 2 * (math.log(samples - 1) + 0.5772156649015329) - 2 * (samples - 1) / samples


def _forest_score(model: DetectorModel, row: tuple[float, ...]) -> float:
    row = _float32(row)
    total = 0.0
    for tree in model.trees:
        index = depth = 0
        node = tree.nodes[index]
        while node.left is not None:
            if not (
                node.feature is not None and node.threshold is not None and node.right is not None
            ):
                raise AssertionError("Internal invariant check failed.")
            index = node.left if row[node.feature] <= node.threshold else node.right
            depth += 1
            node = tree.nodes[index]
        total += depth + _average_path(node.samples)
    if not (model.effective_samples is not None):
        raise AssertionError("Internal invariant check failed.")
    return float(2 ** (-total / (len(model.trees) * _average_path(model.effective_samples))))


def _mad_score(model: DetectorModel, row: tuple[float, ...]) -> ScoreValue:
    maximum = 0.0
    for value, center, scale in zip(row, model.medians, model.deviations, strict=True):
        if scale == 0:
            if value != center:
                return "+infinity"
            continue
        deviation = abs(value - center) / scale
        if not math.isfinite(deviation):
            # Mathematical infinity is reserved for MAD=0, not floating overflow.
            raise ValueError("finite MAD score exceeds numeric range")
        maximum = max(maximum, deviation)
    return maximum


def _inference_matrix(
    fit: DetectorFit, profiles: tuple[ProfileVector, ...]
) -> FeatureMatrix | None:
    profiles = tuple(_compatible(p, fit.preprocessor.spec) for p in profiles)
    return (
        transform_profiles(fit.preprocessor, profiles)
        if fit.preprocessor.state == "ready"
        else None
    )


def _score_model(model: DetectorModel, matrix: FeatureMatrix | None) -> DetectorScores:
    if model.state == "not_estimable":
        return DetectorScores(state="not_estimable", reason=model.reason)
    if not (matrix is not None):
        raise AssertionError("Internal invariant check failed.")
    scorer = _forest_score if model.method == "isolation_forest" else _mad_score
    return DetectorScores(state="scored", values=tuple(scorer(model, row) for row in matrix.values))


def score_detectors(fit: DetectorFit, profiles: tuple[ProfileVector, ...]) -> DetectorScoreResult:
    """Frozen inference. Incompatible/failed profiles raise, never become no-alert."""
    fit = DetectorFit.model_validate(fit)
    matrix = _inference_matrix(fit, profiles)
    return DetectorScoreResult(
        fit_sha256=detector_fingerprint(fit),
        matrix_sha256=profile_digest(matrix.model_dump(mode="json")) if matrix else None,
        rows=len(profiles),
        m=_score_model(fit.m, matrix),
        b=_score_model(fit.b, matrix),
    )


def _calibrate(scores: DetectorScores, alpha: str, n: int, minimum: int) -> DetectorCalibration:
    if scores.state == "not_estimable" or n < minimum:
        return DetectorCalibration(
            alpha=alpha,
            sample_count=n,
            state="not_estimable",
            reason=scores.reason or "insufficient_calibration_rows",
        )
    rank = quantile_rank(alpha, n)
    threshold = sorted(scores.values, key=numeric_score)[rank - 1]
    infinite = threshold == "+infinity"
    return DetectorCalibration(
        alpha=alpha,
        sample_count=n,
        scores=scores.values,
        rank=rank,
        threshold=threshold,
        state="not_estimable" if infinite else "ready",
        reason="infinite_calibration_threshold" if infinite else None,
    )


def calibrate_detectors(
    fit: DetectorFit, calibration: NormalCalibrationProfiles, *, alpha: str
) -> DetectorBundle:
    """Use separate normal calibration; the benchmark enforces disjoint group lineage."""
    fit = DetectorFit.model_validate(fit)
    calibration = NormalCalibrationProfiles.model_validate(calibration)
    quantile_rank(alpha, max(1, len(calibration.profiles)))
    if calibration.selection_manifest_sha256 == fit.preprocessor.selection_manifest_sha256:
        raise ValueError("training and calibration selection manifests must differ")
    scores = score_detectors(fit, calibration.profiles)
    return DetectorBundle(
        fit=fit,
        calibration_manifest_sha256=calibration.selection_manifest_sha256,
        calibration_matrix_sha256=scores.matrix_sha256,
        m=_calibrate(scores.m, alpha, scores.rows, fit.support.min_calibration_rows),
        b=_calibrate(scores.b, alpha, scores.rows, fit.support.min_calibration_rows),
    )


def _decisions(
    calibrated: DetectorCalibration, scored: DetectorScores, count: int
) -> tuple[DetectorDecision, ...]:
    rows = []
    for index in range(count):
        score = scored.values[index] if scored.state == "scored" else None
        if calibrated.state != "ready":
            rows.append(
                DetectorDecision(
                    result=ComponentDecision(
                        decision="not_evaluable", complete=False, reason=calibrated.reason
                    ),
                    score=score,
                    threshold=None,
                )
            )
            continue
        if not (isinstance(calibrated.threshold, float) and score is not None):
            raise AssertionError("Internal invariant check failed.")
        rows.append(
            DetectorDecision(
                result=ComponentDecision(
                    decision="alert" if numeric_score(score) > calibrated.threshold else "no_alert",
                    complete=True,
                ),
                score=score,
                threshold=calibrated.threshold,
            )
        )
    return tuple(rows)


def detect(bundle: DetectorBundle, profiles: tuple[ProfileVector, ...]) -> DetectionResult:
    bundle = DetectorBundle.model_validate(bundle)
    scores = score_detectors(bundle.fit, profiles)
    return DetectionResult(
        bundle_sha256=detector_fingerprint(bundle),
        scores=scores,
        m=_decisions(bundle.m, scores.m, scores.rows),
        b=_decisions(bundle.b, scores.b, scores.rows),
    )


def detect_component(
    bundle: DetectorBundle,
    profiles: tuple[ProfileVector, ...],
    *,
    method: Literal["isolation_forest", "mad"],
) -> ComponentDetectionResult:
    """Score and decide one frozen detector, without evaluating the other method.

    The shared preprocessor and strict decision threshold are identical to
    ``detect``. Invalid or technically failed profiles raise; missing model or
    calibration support produces explicit not-evaluable decisions.
    """
    if method not in ("isolation_forest", "mad"):
        raise ValueError("method must be isolation_forest or mad")
    bundle = DetectorBundle.model_validate(bundle)
    matrix = _inference_matrix(bundle.fit, profiles)
    model, calibrated = (
        (bundle.fit.m, bundle.m) if method == "isolation_forest" else (bundle.fit.b, bundle.b)
    )
    scores = _score_model(model, matrix)
    return ComponentDetectionResult(
        method=method,
        bundle_sha256=detector_fingerprint(bundle),
        fit_sha256=detector_fingerprint(bundle.fit),
        profiles_sha256=profile_digest([p.model_dump(mode="json") for p in profiles]),
        matrix_sha256=profile_digest(matrix.model_dump(mode="json")) if matrix else None,
        rows=len(profiles),
        scores=scores,
        decisions=_decisions(calibrated, scores, len(profiles)),
    )


def write_detector_bundle(bundle: DetectorBundle, path: Path) -> str:
    """Append-only JSON. Returns semantic digest for a trusted external manifest."""
    bundle = DetectorBundle.model_validate(bundle)
    payload = bundle.model_dump_json().encode("utf-8")
    if len(payload) > 64 * 1024 * 1024:
        raise ValueError("detector bundle exceeds the 64 MiB document limit")
    _write_document(path, payload)
    return detector_fingerprint(bundle)


def read_detector_bundle(path: Path, *, expected_sha256: str | None = None) -> DetectorBundle:
    """Read bounded declarative data only; no pickle, estimator restoration or imports."""
    try:
        raw = _read_document(local_input_path(path))
    except ResourceLimitError:
        raise ValueError("detector bundle exceeds the 64 MiB document limit") from None
    bundle = DetectorBundle.model_validate_json(raw)
    if expected_sha256 is not None and detector_fingerprint(bundle) != expected_sha256:
        raise ArtifactIntegrityError("detector bundle fingerprint mismatch")
    return bundle
