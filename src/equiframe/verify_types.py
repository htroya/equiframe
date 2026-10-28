"""Reusable verification dimensions and declared independent-review provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    Text,
    _ExplicitOutcome,
    strict_bool_literal,
)
from equiframe.comparison_types import ComparisonOptions, ComparisonPolicy, ComparisonResult
from equiframe.contracts import Contract
from equiframe.execution_types import ExecutionResult
from equiframe.pipeline_types import EvidenceFile
from equiframe.rule_types import RuleEvaluation
from equiframe.serialization import contract_fingerprint
from equiframe.types import ArtifactRef, Sha256

VerificationState = Literal["passed", "failed", "not_evaluable", "not_requested", "pending_review"]


class VerificationCheck(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .state explicitly; not_requested and pending_review are not approval"
    )

    state: VerificationState
    reason: Text
    output: Identifier | None = None
    comparison_id: Identifier | None = None


class VerificationBinding(FrozenModel):
    """Content identities; locations and names never authenticate a producer."""

    contract_sha256: Sha256
    snapshots: tuple[tuple[Identifier, Sha256], ...] = ()
    plan_sha256: Sha256 | None = None
    outputs: tuple[tuple[Identifier, Sha256], ...]
    expected_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def unique(self) -> Self:
        for entries in (self.snapshots, self.outputs):
            if len({name for name, _ in entries}) != len(entries):
                raise ValueError("verification identities must have unique names")
        return self


class ExpectedProvenance(FrozenModel):
    expected_sha256: Sha256
    method: Text
    authors: tuple[Text, ...]
    implementation_authors: tuple[Text, ...] = ()
    derived_from_engines: tuple[Identifier, ...] = ()
    independence_declared: bool = False

    @model_validator(mode="after")
    def unique(self) -> Self:
        if not self.authors or len(set(self.authors)) != len(self.authors):
            raise ValueError("expected authors must be nonempty and distinct")
        return self

    @property
    def independently_constructed(self) -> bool:
        return (
            self.independence_declared
            and not self.derived_from_engines
            and not set(self.authors).intersection(self.implementation_authors)
        )


class VerificationReview(FrozenModel):
    packet_sha256: Sha256
    reviewer: Text
    label: Literal["normal", "divergent", "not_evaluable"]
    reason: Text
    recorded_at: Text
    blind_attestation: Annotated[Literal[True], BeforeValidator(strict_bool_literal)]

    @model_validator(mode="after")
    def date(self) -> Self:
        value = datetime.fromisoformat(self.recorded_at.replace("Z", "+00:00"))
        offset = value.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("review time requires UTC")
        return self


class IndependentReviewEvidence(FrozenModel):
    binding: VerificationBinding
    output: Identifier
    packet_sha256: Sha256
    source_document_sha256: Sha256
    reviewers: tuple[Text, Text]
    arbitrator: Text
    assigned_at: Text
    reviews: tuple[VerificationReview, ...] = ()
    resolution: VerificationReview | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        assigned = datetime.fromisoformat(self.assigned_at.replace("Z", "+00:00"))
        offset = assigned.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("assignment time requires UTC")
        if len(set((*self.reviewers, self.arbitrator))) != 3:
            raise ValueError("two distinct reviewers and an independent arbitrator required")
        if self.output not in dict(self.binding.outputs):
            raise ValueError("review output must belong to the bound evidence")
        if len(self.reviews) > 2 or len({r.reviewer for r in self.reviews}) != len(self.reviews):
            raise ValueError("at most two distinct primary reviews allowed")
        for r in (*self.reviews, *((self.resolution,) if self.resolution else ())):
            if r.packet_sha256 != self.packet_sha256:
                raise ValueError("review packet identity mismatch")
            if datetime.fromisoformat(r.recorded_at.replace("Z", "+00:00")) < assigned:
                raise ValueError("assignment must precede review")
        if any(r.reviewer not in self.reviewers for r in self.reviews):
            raise ValueError("unassigned primary reviewer")
        if self.resolution:
            if (
                self.resolution.reviewer != self.arbitrator
                or len(self.reviews) != 2
                or self.reviews[0].label == self.reviews[1].label
            ):
                raise ValueError("resolution requires assigned arbitrator and disagreement")
            if any(
                datetime.fromisoformat(self.resolution.recorded_at.replace("Z", "+00:00"))
                < datetime.fromisoformat(r.recorded_at.replace("Z", "+00:00"))
                for r in self.reviews
            ):
                raise ValueError("resolution must follow both primary reviews")
        return self


class VerificationCoverage(FrozenModel):
    scope: Literal["complete_output_artifacts"] = "complete_output_artifacts"
    outputs_requested: PositiveInt
    outputs_inspected: NonNegativeInt
    comparisons_requested: NonNegativeInt
    comparisons_completed: NonNegativeInt
    input_execution_evidence_available: bool
    complete: bool

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.outputs_inspected > self.outputs_requested:
            raise ValueError("inspected outputs exceed requested outputs")
        if self.comparisons_completed > self.comparisons_requested:
            raise ValueError("completed comparisons exceed requested comparisons")
        if self.complete and (
            self.outputs_inspected != self.outputs_requested
            or self.comparisons_completed != self.comparisons_requested
        ):
            raise ValueError("complete verification requires complete coverage")
        return self


class VerificationResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .operational_state, .publishable and the required verification "
        "dimensions explicitly"
    )

    schema_version: Literal["1.0"] = "1.0"
    verification_id: Identifier
    contract: Contract
    binding: VerificationBinding
    outputs: tuple[tuple[Identifier, ArtifactRef], ...]
    expected_artifact: ArtifactRef | None
    expected_source_engine: Identifier | None = None
    comparison_policy: ComparisonPolicy = ComparisonPolicy()
    comparison_options: ComparisonOptions = ComparisonOptions()
    input_artifacts: tuple[tuple[Identifier, ArtifactRef], ...] = ()
    expected_required: bool = False
    rules_required: bool = False
    review_requested: bool = False
    technical_outcomes: tuple[VerificationCheck, ...] = ()
    provenance: ExpectedProvenance | None
    review_evidence: tuple[IndependentReviewEvidence, ...] = ()
    inputs: VerificationCheck
    technical: VerificationCheck
    integrity: VerificationCheck
    agreement: VerificationCheck
    expected: tuple[VerificationCheck, ...]
    rules: tuple[VerificationCheck, ...]
    coverage: VerificationCoverage
    independent_review: VerificationCheck
    comparisons: tuple[ComparisonResult, ...]
    input_comparisons: tuple[ComparisonResult, ...] = ()
    executions: tuple[tuple[Identifier, ExecutionResult], ...] = ()
    rule_evaluations: tuple[RuleEvaluation, ...] = ()
    started_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    evidence: tuple[EvidenceFile, ...] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.binding.contract_sha256 != contract_fingerprint(self.contract):
            raise ValueError("verification contract identity mismatch")
        if self.binding.outputs != tuple((name, ref.sha256) for name, ref in self.outputs):
            raise ValueError("verification output identity mismatch")
        if self.binding.expected_sha256 != (
            self.expected_artifact.sha256 if self.expected_artifact else None
        ):
            raise ValueError("verification expected identity mismatch")
        if self.provenance and self.provenance.expected_sha256 != self.binding.expected_sha256:
            raise ValueError("expected provenance identity mismatch")
        if (
            self.expected_source_engine is not None
            and self.provenance is not None
            and self.expected_source_engine not in self.provenance.derived_from_engines
        ):
            raise ValueError("expected execution engine dependency must remain recorded")
        if self.binding.snapshots != tuple(
            (name, ref.sha256) for name, ref in self.input_artifacts
        ):
            raise ValueError("verification snapshot identity mismatch")
        from equiframe.verify import _validate_dimensions

        _validate_dimensions(self)
        return self

    @property
    def operational_state(self) -> VerificationState:
        checks = (
            self.inputs,
            self.technical,
            self.integrity,
            self.agreement,
            *self.expected,
            *self.rules,
        )
        if any(c.state == "failed" for c in checks):
            return "failed"
        if not self.coverage.complete or any(c.state == "not_evaluable" for c in checks):
            return "not_evaluable"
        return "passed"

    @property
    def publishable(self) -> bool:
        return self.operational_state == "passed"

    @property
    def exit_code(self) -> int:
        return 0 if self.publishable else 1 if self.operational_state == "failed" else 3
