import json

import equiframe as ef
import pytest
from conftest import oracle, reviews
from pydantic import ValidationError

import equiframe_benchmark as eb
from equiframe_benchmark.fixtures import cases, expected_table
from equiframe_benchmark.mutations import semantic_fault

FAMILIES = ("nulls_types", "joins", "duplicates_order", "aggregations", "dates")


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("mode", ("control", "permuted", "fault", "no_effect"))
def test_independent_expected_and_mutation_effect(make_case, tmp_path, family, mode):
    expected = expected_table(next(c for c in cases() if c.contract.family == family))
    table = semantic_fault(family, expected) if mode == "fault" else expected
    if mode == "permuted":
        table = expected.take(list(reversed(range(expected.num_rows))))
    data = make_case(
        family, table=table, kind="mutation" if mode in ("fault", "no_effect") else "control"
    )
    s, c, p, _a, _, _ = data
    pending = eb.evaluate_oracle(s, c, packet=p, work_dir=tmp_path)
    assert pending.status == "pending" and pending.label is None
    label = "divergent" if mode == "fault" else "normal"
    result = oracle(data, tmp_path, (label, label))
    assert result.status == "confirmed" and result.label == label
    assert result.mutation_effect == {"fault": "changed", "no_effect": "no_effect"}.get(
        mode, "not_applicable"
    )
    assert eb.OracleResult.model_validate_json(result.model_dump_json()) == result


def test_swap_totals_preserves_sum_but_diverges(make_case, tmp_path):
    case = next(c for c in cases() if c.contract.family == "aggregations")
    expected = expected_table(case)
    changed = semantic_fault("aggregations", expected)
    assert sum(changed["total"].to_pylist()) == sum(expected["total"].to_pylist())
    assert (
        oracle(
            make_case("aggregations", table=changed, kind="mutation"),
            tmp_path,
            ("divergent", "divergent"),
        ).label
        == "divergent"
    )


def test_packet_has_inputs_and_neutral_filenames(make_case):
    s, c, packet, *_ = make_case()
    payload = packet.model_dump_json()
    for secret in (
        "secret-mutant",
        "duckdb",
        "private proposed mutation",
        '"kind":"mutation"',
        "test-author",
    ):
        assert secret not in payload
    assert len(packet.inputs) == len(s.inputs)
    assert packet.candidate.sha256 == c.output.sha256
    assert packet.candidate.uri != c.output.uri


@pytest.mark.parametrize("role", ("reviewer", "arbitrator"))
def test_authors_cannot_review_or_arbitrate(make_case, tmp_path, role):
    s, c, p, a, *_ = make_case()
    update = (
        {"reviewers": ("test-author", "test-reviewer-b")}
        if role == "reviewer"
        else {"arbitrator": "test-author"}
    )
    a = a.model_copy(update=update)
    with pytest.raises(ValueError, match="independent"):
        eb.evaluate_oracle(s, c, packet=p, assignment=a, work_dir=tmp_path)


@pytest.mark.parametrize(
    "labels,status",
    [
        (("normal", "divergent"), "disagreement"),
        (("divergent", "divergent"), "disagreement"),
        (("not_evaluable", "not_evaluable"), "not_evaluable"),
    ],
)
def test_disagreement_and_insufficient_evidence(make_case, tmp_path, labels, status):
    result = oracle(make_case(), tmp_path, labels)
    assert result.status == status and result.label is None


def test_independent_resolution(make_case, tmp_path):
    data = make_case()
    p = data[2]
    resolution = eb.Review(
        packet_sha256=eb.digest(p),
        reviewer="test-arbitrator",
        label="normal",
        reason="test arbitration",
        recorded_at="2026-10-01T02:00:00Z",
        blind_attestation=True,
    )
    assert oracle(data, tmp_path, ("normal", "divergent"), resolution=resolution).label == "normal"
    with pytest.raises(ValueError, match="disagreeing"):
        oracle(data, tmp_path, resolution=resolution)


@pytest.mark.parametrize("fault", ("duplicate", "unassigned", "stale", "no_assignment", "predated"))
def test_invalid_reviews(make_case, tmp_path, fault):
    s, c, p, a, *_ = make_case()
    r = reviews(p)
    if fault == "duplicate":
        r = (r[0], r[0])
    if fault == "unassigned":
        r = (r[0].model_copy(update={"reviewer": "unassigned"}), r[1])
    if fault == "stale":
        r = (r[0].model_copy(update={"packet_sha256": "f" * 64}), r[1])
    if fault == "no_assignment":
        a = None
    if fault == "predated":
        r = (r[0].model_copy(update={"recorded_at": "2026-09-01T00:00:00Z"}), r[1])
    with pytest.raises(ValueError):
        eb.evaluate_oracle(s, c, packet=p, assignment=a, reviews=r, work_dir=tmp_path)


@pytest.mark.parametrize("fault", ("scenario", "rules", "packet", "authors"))
def test_invalid_provenance(make_case, tmp_path, fault):
    s, c, p, a, *_ = make_case()
    field = {"scenario": "scenario_sha256", "rules": "rules_sha256_before_candidate"}.get(fault)
    if field:
        c = c.model_copy(update={field: "f" * 64})
    if fault == "packet":
        p = p.model_copy(update={"inputs": ()})
    if fault == "authors":
        c = c.model_copy(update={"authors": ("test-author ",)})
    with pytest.raises(ValueError):
        eb.evaluate_oracle(s, c, packet=p, assignment=a, work_dir=tmp_path)


def test_corrupt_output_never_becomes_normal(make_case, tmp_path):
    s, c, p, *_ = make_case()
    # Use the library's portable file-URI resolver, without interpreting URI paths by OS.
    from equiframe.local import local_path

    local_path(p.candidate).write_bytes(b"broken")
    result = eb.evaluate_oracle(s, c, packet=p, work_dir=tmp_path)
    assert result.status == "not_evaluable" and result.label is None


def test_tampered_confirmation_rejected(make_case, tmp_path):
    result = oracle(make_case(), tmp_path)
    payload = result.model_dump(mode="json")
    payload["reviews"] = []
    with pytest.raises(ValidationError):
        eb.OracleResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "update", ({"mutation_effect": "changed"}, {"status": "pending", "label": None})
)
def test_inconsistent_stored_decision_rejected(make_case, tmp_path, update):
    result = oracle(make_case(), tmp_path)
    with pytest.raises(ValidationError):
        eb.OracleResult.model_validate(result.model_copy(update=update))


def test_pending_without_detector_imports(make_case, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("oracle must not invoke rules or profiles")

    monkeypatch.setattr(ef, "evaluate_rules", forbidden)
    monkeypatch.setattr(ef, "profile_execution", forbidden)
    s, c, p, *_ = make_case()
    assert eb.evaluate_oracle(s, c, packet=p, work_dir=tmp_path).label is None
