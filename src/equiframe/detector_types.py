"""Declarative detector state: no executable estimators, labels or row metadata."""

from fractions import Fraction
from math import ceil
from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, NonNegativeInt, PositiveInt, Text, _ExplicitOutcome
from equiframe.profile_types import PreprocessorBundle, ProfileVector, profile_digest
from equiframe.types import DecisionState, Sha256

ScoreValue = Annotated[float, Field(ge=0)] | Literal["+infinity"]


def numeric_score(value: ScoreValue) -> float:
    return float("inf") if value == "+infinity" else value


def quantile_rank(alpha: str, n: int) -> int:
    """Decimal probability and exact rank; binary rounding must not change ceil."""
    import re

    if not isinstance(alpha, str) or not re.fullmatch(r"0\.[0-9]{1,18}", alpha):
        raise ValueError("alpha must be an explicit decimal string, e.g. '0.05'")
    probability = Fraction(alpha)
    if not 0 < probability < 1 or n < 1:
        raise ValueError("alpha must be between zero and one and n must be positive")
    return ceil((1 - probability) * n)


class NormalCalibrationProfiles(FrozenModel):
    purpose: Literal["normal_calibration"]
    selection_manifest_sha256: Sha256
    profiles: tuple[ProfileVector, ...]


class DetectorSupport(FrozenModel):
    """Technical minima, not a statistical power or false-alarm guarantee."""

    min_training_rows: Annotated[int, Field(ge=2)]
    min_calibration_rows: PositiveInt
    rationale: Text


class IsolationForestConfig(FrozenModel):
    random_state: Annotated[int, Field(ge=0, le=2**32 - 1)]
    n_estimators: Annotated[int, Field(ge=1, le=2048)] = 200
    max_samples: Annotated[int, Field(ge=2, le=4096)] = 256


class IsolationNode(FrozenModel):
    samples: PositiveInt
    left: NonNegativeInt | None = None
    right: NonNegativeInt | None = None
    feature: NonNegativeInt | None = None
    threshold: float | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        fields = (self.left, self.right, self.feature, self.threshold)
        if any(f is None for f in fields) and not all(f is None for f in fields):
            raise ValueError("node must be a leaf or a complete binary split")
        return self


class IsolationTree(FrozenModel):
    nodes: Annotated[tuple[IsolationNode, ...], Field(min_length=1, max_length=8191)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        parents = [0] * len(self.nodes)
        for index, node in enumerate(self.nodes):
            if node.left is None or node.right is None:
                continue
            if not index < node.left < len(self.nodes) or not index < node.right < len(self.nodes):
                raise ValueError("tree children must be forward references inside the tree")
            parents[node.left] += 1
            parents[node.right] += 1
            if self.nodes[node.left].samples + self.nodes[node.right].samples != node.samples:
                raise ValueError("child sample counts must partition the parent")
        if parents != [0] + [1] * (len(self.nodes) - 1):
            raise ValueError("tree must have one root and no shared or disconnected nodes")
        return self


class DetectorModel(FrozenModel):
    method: Literal["isolation_forest", "mad"]
    state: Literal["fitted", "not_estimable"]
    reason: Text | None = None
    trees: Annotated[tuple[IsolationTree, ...], Field(max_length=2048)] = ()
    effective_samples: Annotated[int, Field(ge=2, le=4096)] | None = None
    medians: tuple[float, ...] = ()
    deviations: tuple[Annotated[float, Field(ge=0)], ...] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.state == "not_estimable":
            if self.reason is None or self.trees or self.medians or self.deviations:
                raise ValueError("unestimable model requires reason and no fitted parameters")
            if self.effective_samples is not None:
                raise ValueError("unestimable model has no effective subsample")
        elif self.reason is not None:
            raise ValueError("fitted model cannot have a failure reason")
        elif self.method == "isolation_forest":
            if not self.trees or self.effective_samples is None or self.medians or self.deviations:
                raise ValueError("Isolation Forest requires only trees and effective samples")
            if any(t.nodes[0].samples != self.effective_samples for t in self.trees):
                raise ValueError("tree roots must match effective subsample")
            if any(len(t.nodes) > 2 * self.effective_samples - 1 for t in self.trees):
                raise ValueError("tree size exceeds subsample support")
            if not any(len(t.nodes) > 1 for t in self.trees):
                raise ValueError("fitted Isolation Forest must contain at least one split")
        elif (
            not self.medians
            or len(self.medians) != len(self.deviations)
            or self.trees
            or self.effective_samples is not None
        ):
            raise ValueError("MAD requires only equally sized medians and deviations")
        return self


class DetectorVersions(FrozenModel):
    equiframe: Literal[
        "0.7.0",
        "0.8.0",
        "0.8.1",
        "0.9.0",
        "0.10.0",
        "0.11.0",
        "0.11.1",
        "0.12.0a1",
        "0.12.0a2",
        "0.12.0a3",
        "0.12.0a4",
        "0.12.0a5",
        "0.12.0a6",
        "0.12.0a7",
        "0.12.0a8",
        "0.12.0a9",
        "0.12.0a10",
        "0.12.0a11",
        "0.12.0a12",
        "0.12.0a13",
        "0.12.0a14",
        "0.12.0",
        "0.12.1",
        "0.12.2",
    ] = "0.12.2"
    python: Text
    sklearn: Text | None = None
    numpy: Text | None = None


class DetectorFit(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    algorithm: Literal["equiframe-if-mad-1.0"] = "equiframe-if-mad-1.0"
    preprocessor: PreprocessorBundle
    config: IsolationForestConfig
    support: DetectorSupport
    versions: DetectorVersions
    training_matrix_sha256: Sha256 | None
    m: DetectorModel
    b: DetectorModel

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.m.method != "isolation_forest" or self.b.method != "mad":
            raise ValueError("M and B must remain separate methods")
        ready = self.preprocessor.state == "ready"
        if ready != (self.training_matrix_sha256 is not None):
            raise ValueError("matrix fingerprint must reflect preprocessor availability")
        for model in (self.m, self.b):
            if model.state == "fitted" and (
                not ready or self.preprocessor.training_rows < self.support.min_training_rows
            ):
                raise ValueError("fitted model lacks preprocessing or training support")
        if self.m.state == "fitted":
            if len(self.m.trees) != self.config.n_estimators:
                raise ValueError("tree count differs from configuration")
            if self.m.effective_samples != min(
                self.config.max_samples, self.preprocessor.training_rows
            ):
                raise ValueError("effective subsample differs from configuration")
            if not self.versions.sklearn or not self.versions.numpy:
                raise ValueError("fitted Isolation Forest requires producer versions")
            if any(
                n.feature is not None and n.feature >= len(self.preprocessor.columns)
                for t in self.m.trees
                for n in t.nodes
            ):
                raise ValueError("tree references a feature outside the frozen matrix")
        if self.b.state == "fitted" and len(self.b.medians) != len(self.preprocessor.columns):
            raise ValueError("MAD parameters differ from frozen matrix width")
        return self


class DetectorScores(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .state explicitly; scores are not an approval decision"

    state: Literal["scored", "not_estimable"]
    values: tuple[ScoreValue, ...] = ()
    reason: Text | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.state == "scored" and self.reason is not None:
            raise ValueError("successful scores cannot have a failure reason")
        if self.state == "not_estimable" and (self.reason is None or self.values):
            raise ValueError("unestimable scores require reason and no invented values")
        return self


class DetectorScoreResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .m.state, .b.state and .rows explicitly; scores are not approval"
    )

    schema_version: Literal["1.0"] = "1.0"
    fit_sha256: Sha256
    matrix_sha256: Sha256 | None
    rows: NonNegativeInt
    m: DetectorScores
    b: DetectorScores

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if any(s.state == "scored" and len(s.values) != self.rows for s in (self.m, self.b)):
            raise ValueError("score count must match input row count")
        if any(s.state == "scored" for s in (self.m, self.b)) and self.matrix_sha256 is None:
            raise ValueError("scores require a matrix fingerprint")
        return self


class DetectorCalibration(FrozenModel):
    alpha: Text
    sample_count: NonNegativeInt
    state: Literal["ready", "not_estimable"]
    scores: tuple[ScoreValue, ...] = ()
    rank: PositiveInt | None = None
    threshold: ScoreValue | None = None
    reason: Text | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        quantile_rank(self.alpha, max(1, self.sample_count))
        if self.scores:
            if len(self.scores) != self.sample_count:
                raise ValueError("calibration count does not match its scores")
            rank = quantile_rank(self.alpha, self.sample_count)
            expected = sorted(self.scores, key=numeric_score)[rank - 1]
            if len(self.scores) != self.sample_count or self.rank != rank:
                raise ValueError("calibration count/rank does not match its scores")
            if self.threshold != expected:
                raise ValueError("threshold must be the exact empirical order statistic")
            infinite = expected == "+infinity"
            if self.state != ("not_estimable" if infinite else "ready"):
                raise ValueError("calibration state must reflect finite threshold availability")
            if self.reason != ("infinite_calibration_threshold" if infinite else None):
                raise ValueError("calibration reason contradicts its threshold")
        elif (
            self.state != "not_estimable"
            or self.reason is None
            or self.rank is not None
            or self.threshold is not None
        ):
            raise ValueError("missing calibration scores cannot produce a threshold or success")
        return self


class DetectorBundle(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    fit: DetectorFit
    calibration_manifest_sha256: Sha256
    calibration_matrix_sha256: Sha256 | None
    m: DetectorCalibration
    b: DetectorCalibration

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.calibration_manifest_sha256 == self.fit.preprocessor.selection_manifest_sha256:
            raise ValueError("calibration must have a separate selection manifest")
        if self.m.alpha != self.b.alpha or self.m.sample_count != self.b.sample_count:
            raise ValueError("M and B must use the same alpha and normal calibration rows")
        for model, calibrated in ((self.fit.m, self.m), (self.fit.b, self.b)):
            if calibrated.scores and (
                model.state != "fitted"
                or self.calibration_matrix_sha256 is None
                or calibrated.sample_count < self.fit.support.min_calibration_rows
            ):
                raise ValueError("calibration lacks model, matrix or minimum support")
        if any(s == "+infinity" or not 0 < s <= 1 for s in self.m.scores):
            raise ValueError("Isolation Forest scores must be finite in (0, 1]")
        return self


class ComponentDecision(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .decision and .complete explicitly; no_alert is not equivalence"
    )

    decision: DecisionState
    complete: bool
    reason: Text | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.complete != (self.reason is None):
            raise ValueError("incomplete decision requires an explicit reason")
        if self.decision == "no_alert" and not self.complete:
            raise ValueError("absence of alert requires a complete evaluation")
        if self.decision == "not_evaluable" and self.complete:
            raise ValueError("unavailable decision cannot be complete")
        return self


class DetectorDecision(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .result.decision and .result.complete explicitly; no_alert is not equivalence"
    )

    result: ComponentDecision
    score: ScoreValue | None
    threshold: Annotated[float, Field(ge=0)] | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.result.complete:
            if self.score is None or self.threshold is None:
                raise ValueError("decision requires score and finite calibrated threshold")
            expected = "alert" if numeric_score(self.score) > self.threshold else "no_alert"
            if self.result.decision != expected:
                raise ValueError("decision must use strict score > threshold")
        elif self.result.decision != "not_evaluable" or self.threshold is not None:
            raise ValueError("uncalibrated detector cannot claim a decision or threshold")
        return self


class DetectionResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .m and .b decisions and coverage explicitly; no_alert is not equivalence"
    )

    schema_version: Literal["1.0"] = "1.0"
    bundle_sha256: Sha256
    scores: DetectorScoreResult
    m: tuple[DetectorDecision, ...]
    b: tuple[DetectorDecision, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(self.m) != self.scores.rows or len(self.b) != self.scores.rows:
            raise ValueError("decisions must cover every input profile")
        for decisions, scores in ((self.m, self.scores.m), (self.b, self.scores.b)):
            expected = scores.values if scores.state == "scored" else (None,) * self.scores.rows
            if tuple(d.score for d in decisions) != expected:
                raise ValueError("decisions must preserve the actual scores")
        return self


class ComponentDetectionResult(_ExplicitOutcome, FrozenModel):
    """Frozen inference for one method; the other detector is not scored."""

    _truth_value_guidance = (
        "inspect .decisions, .complete and .rows explicitly; no_alert is not equivalence"
    )

    schema_version: Literal["1.0"] = "1.0"
    method: Literal["isolation_forest", "mad"]
    bundle_sha256: Sha256
    fit_sha256: Sha256
    profiles_sha256: Sha256
    matrix_sha256: Sha256 | None
    rows: NonNegativeInt
    scores: DetectorScores
    decisions: tuple[DetectorDecision, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(self.decisions) != self.rows:
            raise ValueError("decisions must cover every input profile")
        if self.scores.state == "scored":
            if len(self.scores.values) != self.rows or self.matrix_sha256 is None:
                raise ValueError("scores require every profile and a matrix fingerprint")
            if self.method == "isolation_forest" and any(
                s == "+infinity" or not 0 < s <= 1 for s in self.scores.values
            ):
                raise ValueError("Isolation Forest scores must be finite in (0, 1]")
        expected = self.scores.values if self.scores.state == "scored" else (None,) * self.rows
        if tuple(d.score for d in self.decisions) != expected:
            raise ValueError("decisions must preserve the actual component scores")
        return self

    @property
    def complete(self) -> bool:
        return all(decision.result.complete for decision in self.decisions)


class HybridDecision(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .result.decision and .result.complete explicitly; no_alert is not equivalence"
    )

    schema_version: Literal["1.0"] = "1.0"
    r: ComponentDecision
    m: ComponentDecision
    result: ComponentDecision

    @model_validator(mode="after")
    def consistent(self) -> Self:
        decision = (
            "alert"
            if "alert" in (self.r.decision, self.m.decision)
            else "no_alert"
            if self.r.decision == self.m.decision == "no_alert"
            else "not_evaluable"
        )
        if self.result.decision != decision or self.result.complete != (
            self.r.complete and self.m.complete
        ):
            raise ValueError("H must preserve OR decisions and component completeness")
        return self


def detector_fingerprint(value: DetectorFit | DetectorBundle) -> str:
    validated = type(value).model_validate(value)
    return profile_digest(validated.model_dump(mode="json"))
