"""Strict experimental metadata; never features or detector inputs."""

from datetime import datetime
from typing import Annotated, Literal

from equiframe import ArtifactRef, ComparisonResult, ComparisonSpec, Family
from equiframe._base import strict_bool_literal
from equiframe._documents import (
    Digest as Digest,
)
from equiframe._documents import (
    Document as Document,
)
from equiframe._documents import (
    Evidence as Evidence,
)
from equiframe._documents import (
    Text as Text,
)
from equiframe._documents import (
    canonical_text as canonical_text,
)
from equiframe._documents import (
    checked_artifact as checked_artifact,
)
from equiframe._documents import (
    digest as digest,
)
from equiframe.verify_types import (
    ExpectedProvenance,
    IndependentReviewEvidence,
    VerificationBinding,
)
from pydantic import (
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)
from typing_extensions import Self

Label = Literal["normal", "divergent", "not_evaluable"]
Partition = Literal["training", "calibration", "test"]


class InputBinding(Document):
    name: Text
    artifact: Evidence


class Scenario(Document):
    scenario_id: Text
    family: Family
    dependencies: tuple[Text, ...]
    authors: tuple[Text, ...]
    inputs: tuple[InputBinding, ...]
    transformation_revision: Text
    comparison: ComparisonSpec
    rules_sha256: Digest
    features_sha256: Digest
    expected: Evidence
    expected_method: Text
    expected_authors: tuple[Text, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.family != self.comparison.contract.family:
            raise ValueError("scenario and contract families differ")
        for values in (self.dependencies, self.authors, self.expected_authors):
            if not values or len(set(values)) != len(values):
                raise ValueError("dependencies and authors must be nonempty and unique")
        if not self.expected.sha256 or self.expected.size_bytes is None:
            raise ValueError("expected output requires hash and size")
        names = [i.name for i in self.inputs]
        if len(set(names)) != len(names) or set(names) != {
            t.name for t in self.comparison.contract.inputs
        }:
            raise ValueError("input bindings must cover exactly the contract inputs")
        return self


class Catalog(Document):
    catalog_id: Text
    synthetic: bool
    scenarios: tuple[Scenario, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        ids = [s.scenario_id for s in self.scenarios]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("catalog must contain unique scenarios")
        return self


class Candidate(Document):
    candidate_id: Text
    scenario_sha256: Digest
    output: Evidence
    authors: tuple[Text, ...]
    kind: Literal["control", "mutation"]
    description: Text
    implementation: Text
    rules_sha256_before_candidate: Digest

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if not self.authors or len(set(self.authors)) != len(self.authors):
            raise ValueError("candidate authors required and unique")
        if not self.output.sha256 or self.output.size_bytes is None:
            raise ValueError("candidate output requires hash and size")
        return self


class ReviewPacket(Document):
    """Deliberately omits mutation kind, engine, alerts and proposed labels."""

    case_token: Text
    scenario_sha256: Digest
    comparison: ComparisonSpec
    inputs: tuple[InputBinding, ...]
    expected: Evidence
    candidate: Evidence


class ReviewAssignment(Document):
    packet_sha256: Digest
    reviewers: tuple[Text, Text]
    arbitrator: Text
    assigned_at: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T.*(?:Z|\+00:00)$")]

    @model_validator(mode="after")
    def independent(self) -> Self:
        datetime.fromisoformat(self.assigned_at.replace("Z", "+00:00"))
        if len(set((*self.reviewers, self.arbitrator))) != 3:
            raise ValueError("two distinct reviewers and an independent arbitrator required")
        return self


class Review(Document):
    packet_sha256: Digest
    reviewer: Text
    label: Label
    reason: Text
    recorded_at: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T.*(?:Z|\+00:00)$")]
    blind_attestation: Annotated[Literal[True], BeforeValidator(strict_bool_literal)]

    @model_validator(mode="after")
    def valid_date(self) -> Self:
        datetime.fromisoformat(self.recorded_at.replace("Z", "+00:00"))
        if self.reviewer != self.reviewer.strip():
            raise ValueError("reviewer identity must be canonical")
        return self


class OracleResult(Document):
    scenario_sha256: Digest
    candidate_sha256: Digest
    candidate_kind: Literal["control", "mutation"]
    packet_sha256: Digest
    packet: ReviewPacket
    assignment: ReviewAssignment | None
    status: Literal["pending", "disagreement", "confirmed", "not_evaluable"]
    label: Label | None
    comparison: ComparisonResult
    reviews: tuple[Review, ...]
    resolution: Review | None
    mutation_effect: Literal["not_applicable", "changed", "no_effect", "unknown"]
    reason: Text

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.packet_sha256 != digest(self.packet):
            raise ValueError("packet fingerprint mismatch")
        if self.scenario_sha256 != self.packet.scenario_sha256:
            raise ValueError("packet scenario mismatch")
        if (
            self.comparison.spec != self.packet.comparison
            or self.comparison.reference != "expected"
        ):
            raise ValueError("oracle requires the declared independent expected comparison")
        for source, ref in (
            (self.comparison.left, self.packet.candidate),
            (self.comparison.right, self.packet.expected),
        ):
            if source is not None and not same_content(source.data, ref):
                raise ValueError("comparison evidence mismatch")
        if self.assignment:
            if self.assignment.packet_sha256 != self.packet_sha256:
                raise ValueError("assignment packet mismatch")
            if any(r.reviewer not in self.assignment.reviewers for r in self.reviews):
                raise ValueError("unassigned primary reviewer")
            if self.resolution and self.resolution.reviewer != self.assignment.arbitrator:
                raise ValueError("unassigned arbitrator")
        elif self.reviews or self.resolution:
            raise ValueError("reviews require prior assignment")
        if (self.status == "confirmed") != (self.label in ("normal", "divergent")):
            raise ValueError("only confirmed oracles carry an evaluable label")
        if self.status != "confirmed" and self.label is not None:
            raise ValueError("unconfirmed cases have no training label")
        if self.comparison.state == "not_evaluable" and self.status != "not_evaluable":
            raise ValueError("failed comparison cannot produce a decision")
        if len(self.reviews) > 2 or len({r.reviewer for r in self.reviews}) != len(self.reviews):
            raise ValueError("invalid primary reviewers")
        for review in (*self.reviews, *((self.resolution,) if self.resolution else ())):
            if review.packet_sha256 != self.packet_sha256:
                raise ValueError("review packet mismatch")
            if self.assignment and datetime.fromisoformat(
                review.recorded_at.replace("Z", "+00:00")
            ) < datetime.fromisoformat(self.assignment.assigned_at.replace("Z", "+00:00")):
                raise ValueError("assignment must precede reviews")
        if self.resolution:
            if len(self.reviews) != 2 or self.reviews[0].label == self.reviews[1].label:
                raise ValueError("resolution requires a primary disagreement")
            if any(
                datetime.fromisoformat(self.resolution.recorded_at.replace("Z", "+00:00"))
                < datetime.fromisoformat(r.recorded_at.replace("Z", "+00:00"))
                for r in self.reviews
            ):
                raise ValueError("resolution must follow both reviews")
        if self.status == "confirmed":
            observed = "normal" if self.comparison.state == "equivalent" else "divergent"
            if self.label != observed:
                raise ValueError("review contradicts comparison")
            if len(self.reviews) != 2:
                raise ValueError("confirmation requires two reviews")
            labels = {r.label for r in self.reviews}
            if len(labels) == 1:
                if self.label not in labels or self.resolution is not None:
                    raise ValueError("confirmation contradicts primary reviews")
            elif self.resolution is None or self.resolution.label != self.label:
                raise ValueError("disagreement requires a matching resolution")
        if self.resolution and self.resolution.reviewer in {r.reviewer for r in self.reviews}:
            raise ValueError("arbitrator must be independent")
        expected_effect = "not_applicable"
        if self.candidate_kind == "mutation":
            expected_effect = {
                "equivalent": "no_effect",
                "different": "changed",
                "not_evaluable": "unknown",
            }[self.comparison.state]
        if self.mutation_effect != expected_effect:
            raise ValueError("mutation effect contradicts comparison")
        expected_status = "pending"
        if self.comparison.state == "not_evaluable":
            expected_status = "not_evaluable"
        elif len(self.reviews) == 2:
            if self.reviews[0].label != self.reviews[1].label and self.resolution is None:
                expected_status = "disagreement"
            else:
                selected = self.resolution.label if self.resolution else self.reviews[0].label
                observed = "normal" if self.comparison.state == "equivalent" else "divergent"
                expected_status = (
                    "not_evaluable"
                    if selected == "not_evaluable"
                    else "confirmed"
                    if selected == observed
                    else "disagreement"
                )
        if self.status != expected_status:
            raise ValueError("oracle status contradicts evidence and reviews")
        return self


class OracleVerificationBridge(Document):
    """Explicit content binding for reusable Verify; no human authentication."""

    oracle_sha256: Digest
    binding: VerificationBinding
    provenance: ExpectedProvenance
    review: IndependentReviewEvidence | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.provenance.expected_sha256 != self.binding.expected_sha256:
            raise ValueError("bridge expected identity mismatch")
        if self.review and (
            self.review.binding != self.binding
            or self.review.source_document_sha256 != self.oracle_sha256
        ):
            raise ValueError("bridge review identity mismatch")
        return self


def same_content(left: ArtifactRef, right: ArtifactRef) -> bool:
    """Locations can change when blinding; evidence identity cannot."""
    return (left.sha256, left.size_bytes, left.format) == (
        right.sha256,
        right.size_bytes,
        right.format,
    )


class Assignment(Document):
    scenario_id: Text
    group_id: Digest
    partition: Partition


class SplitManifest(Document):
    catalog_sha256: Digest
    algorithm: Literal["sha256-components-balanced-1.0"] = "sha256-components-balanced-1.0"
    seed: Annotated[int, Field(ge=0)]
    weights: tuple[
        Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]
    ]
    assignments: tuple[Assignment, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        ids = [a.scenario_id for a in self.assignments]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("assignments must be nonempty and unique")
        return self
