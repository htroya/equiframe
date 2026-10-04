"""Existing O retains its procedure when linked to reusable Verify."""

import equiframe as ef
import pytest
from conftest import oracle

import equiframe_benchmark as eb
from equiframe_benchmark.oracle import oracle_verification_bridge


def test_bridge_preserves_confirmed_existing_reviews(make_case, tmp_path):
    data = make_case()
    scenario, candidate, _, assignment, execution, profile = data
    scenario = scenario.model_copy(update={"expected_authors": ("test-expected-author",)})
    candidate = candidate.model_copy(update={"scenario_sha256": eb.digest(scenario)})
    packet = eb.review_packet(scenario, candidate, directory=tmp_path / "independent_packet")
    assignment = assignment.model_copy(update={"packet_sha256": eb.digest(packet)})
    data = scenario, candidate, packet, assignment, execution, profile
    result = oracle(data, tmp_path / "oracle")
    bridge = oracle_verification_bridge(
        scenario,
        candidate,
        result,
        output_name="candidate",
        plan_sha256="1" * 64,
        independence_declared=True,
    )
    assert bridge.oracle_sha256 == eb.digest(result)
    assert bridge.review.source_document_sha256 == eb.digest(result)
    assert len(bridge.review.reviews) == 2
    verified = ef.verify(
        {"candidate": candidate.output},
        contract=scenario.comparison.contract,
        expected=scenario.expected,
        provenance=bridge.provenance,
        reviews=(bridge.review,),
        request_review=True,
        snapshots={i.name: i.artifact for i in scenario.inputs},
        plan_sha256="1" * 64,
        policy=scenario.comparison.policy,
        work_dir=tmp_path / "verify",
    )
    assert verified.independent_review.state == "passed"


def test_bridge_keeps_pending_review_and_dependent_expected(make_case, tmp_path):
    scenario, candidate, packet, *_ = make_case()
    result = eb.evaluate_oracle(scenario, candidate, packet=packet, work_dir=tmp_path)
    bridge = oracle_verification_bridge(
        scenario,
        candidate,
        result,
        output_name="candidate",
        plan_sha256="1" * 64,
        independence_declared=True,
        derived_from_engines=("pandas",),
    )
    assert bridge.review is None and not bridge.provenance.independently_constructed
    assert result.status == "pending" and result.label is None


def test_bridge_rejects_a_different_candidate_identity(make_case, tmp_path):
    data = make_case()
    scenario, candidate = data[:2]
    result = oracle(data, tmp_path)
    changed = candidate.model_copy(update={"candidate_id": "different_candidate"})
    with pytest.raises(ValueError, match="different scenario/candidate"):
        oracle_verification_bridge(
            scenario, changed, result, output_name="candidate", plan_sha256="1" * 64
        )


def test_bridge_rejects_changed_candidate_kind_without_relabeling_o(make_case, tmp_path):
    data = make_case()
    scenario, candidate = data[:2]
    result = oracle(data, tmp_path)
    inconsistent = eb.OracleResult.model_validate(
        result.model_copy(update={"candidate_kind": "mutation", "mutation_effect": "no_effect"})
    )
    with pytest.raises(ValueError, match="oracle candidate kind differs"):
        oracle_verification_bridge(
            scenario, candidate, inconsistent, output_name="candidate", plan_sha256="1" * 64
        )
