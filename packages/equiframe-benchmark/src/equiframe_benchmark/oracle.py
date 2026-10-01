"""Independent expected comparison with assigned, blind human review."""

from pathlib import Path
from typing import Literal
from uuid import uuid4

import equiframe as ef

from equiframe_benchmark.io import save_document
from equiframe_benchmark.models import (
    Candidate,
    InputBinding,
    Label,
    OracleResult,
    Review,
    ReviewAssignment,
    ReviewPacket,
    Scenario,
    digest,
    same_content,
)


def validate_candidate(scenario: Scenario, candidate: Candidate) -> None:
    Scenario.model_validate(scenario)
    Candidate.model_validate(candidate)
    if candidate.scenario_sha256 != digest(scenario):
        raise ValueError("candidate scenario mismatch")
    if candidate.rules_sha256_before_candidate != scenario.rules_sha256:
        raise ValueError("rules were not fixed before candidate generation")


def review_packet(scenario: Scenario, candidate: Candidate, *, directory: Path) -> ReviewPacket:
    """Copy verified evidence under neutral names. Give reviewers only this directory.

    The coordinator must inspect contract/content for incidental clues; this is
    blinding, not anonymization or identity authentication.
    """
    validate_candidate(scenario, candidate)
    token = uuid4().hex
    root = directory / token
    root.mkdir(parents=True, exist_ok=False)
    store = ef.LocalArtifactStore(root)

    def copy(ref: ef.ArtifactRef, name: str) -> ef.ArtifactRef:
        path = root / (name + "." + ref.format)
        store.get(ref, path)
        return ef.ArtifactRef.model_validate({**ref.model_dump(), "uri": path.resolve().as_uri()})

    packet = ReviewPacket(
        case_token=token,
        scenario_sha256=digest(scenario),
        comparison=scenario.comparison,
        inputs=tuple(
            InputBinding(name=item.name, artifact=copy(item.artifact, f"input-{index}"))
            for index, item in enumerate(scenario.inputs)
        ),
        expected=copy(scenario.expected, "expected"),
        candidate=copy(candidate.output, "output"),
    )
    save_document(packet, root / "packet.json")
    return packet


def validate_packet(scenario: Scenario, candidate: Candidate, packet: ReviewPacket) -> None:
    validate_candidate(scenario, candidate)
    ReviewPacket.model_validate(packet)
    if packet.scenario_sha256 != digest(scenario) or packet.comparison != scenario.comparison:
        raise ValueError("packet scenario revision mismatch")
    if not same_content(packet.expected, scenario.expected) or not same_content(
        packet.candidate, candidate.output
    ):
        raise ValueError("packet output evidence mismatch")
    if len(packet.inputs) != len(scenario.inputs) or any(
        a.name != b.name or not same_content(a.artifact, b.artifact)
        for a, b in zip(packet.inputs, scenario.inputs, strict=True)
    ):
        raise ValueError("packet input evidence mismatch")


def validate_assignment(
    scenario: Scenario, candidate: Candidate, packet: ReviewPacket, assignment: ReviewAssignment
) -> None:
    ReviewAssignment.model_validate(assignment)
    if assignment.packet_sha256 != digest(packet):
        raise ValueError("assignment belongs to another packet")
    prohibited = set(scenario.authors + scenario.expected_authors + candidate.authors)
    if prohibited.intersection((*assignment.reviewers, assignment.arbitrator)):
        raise ValueError("reviewers and arbitrator must be independent of authors")


def evaluate_oracle(
    scenario: Scenario,
    candidate: Candidate,
    *,
    packet: ReviewPacket,
    assignment: ReviewAssignment | None = None,
    reviews: tuple[Review, ...] = (),
    resolution: Review | None = None,
    work_dir: Path | None = None,
) -> OracleResult:
    validate_packet(scenario, candidate, packet)
    packet_hash = digest(packet)
    if assignment is not None:
        validate_assignment(scenario, candidate, packet, assignment)
    elif reviews or resolution:
        raise ValueError("reviews require prior assignment")
    if len(reviews) > 2:
        raise ValueError("exactly two independent primary reviews allowed")
    seen: set[str] = set()
    for review in (*reviews, *((resolution,) if resolution is not None else ())):
        Review.model_validate(review)
        if review.packet_sha256 != packet_hash:
            raise ValueError("review belongs to another packet revision")
        if review.reviewer in seen:
            raise ValueError("duplicate reviewer")
        seen.add(review.reviewer)
    if assignment and any(r.reviewer not in assignment.reviewers for r in reviews):
        raise ValueError("unassigned primary reviewer")
    if resolution and assignment and resolution.reviewer != assignment.arbitrator:
        raise ValueError("unassigned arbitrator")
    disagreement = len(reviews) == 2 and reviews[0].label != reviews[1].label
    if resolution is not None and not disagreement:
        raise ValueError("resolution requires two disagreeing primary reviews")
    # Missing/corrupt input raises explicitly; it can never produce a normal label.
    for item in packet.inputs:
        ef.read_table(item.artifact)
    comparison = ef.compare(
        packet.candidate,
        packet.expected,
        contract=scenario.comparison.contract,
        policy=scenario.comparison.policy,
        reference="expected",
        work_dir=work_dir,
    )
    observed: Label
    if comparison.state == "equivalent":
        observed = "normal"
    elif comparison.state == "different":
        observed = "divergent"
    else:
        observed = "not_evaluable"
    label: Label | None = None
    status: Literal["pending", "disagreement", "confirmed", "not_evaluable"] = "pending"
    reason = "two independent blind reviews required"
    if comparison.state == "not_evaluable":
        status, reason = "not_evaluable", "comparison incomplete or failed"
    elif disagreement and resolution is None:
        status, reason = "disagreement", "independent arbitration required"
    elif len(reviews) == 2:
        selected = resolution.label if resolution else reviews[0].label
        if selected == "not_evaluable":
            status, reason = "not_evaluable", "review reports insufficient evidence"
        elif selected != observed:
            status, reason = "disagreement", "human review contradicts expected-output comparison"
        else:
            status, label, reason = (
                "confirmed",
                selected,
                "independent reviews and comparison agree",
            )
    effect: Literal["not_applicable", "changed", "no_effect", "unknown"] = "not_applicable"
    if candidate.kind == "mutation":
        if observed == "normal":
            effect = "no_effect"
        elif observed == "divergent":
            effect = "changed"
        else:
            effect = "unknown"
    return OracleResult(
        scenario_sha256=digest(scenario),
        candidate_sha256=digest(candidate),
        candidate_kind=candidate.kind,
        packet_sha256=packet_hash,
        packet=packet,
        assignment=assignment,
        status=status,
        label=label,
        comparison=comparison,
        reviews=reviews,
        resolution=resolution,
        mutation_effect=effect,
        reason=reason,
    )
