"""Reusable Verify separates observed agreement, supplied correctness and scientific O."""

from itertools import permutations

import pyarrow as pa
import pytest
from test_migration import Provider, contract, spec, table

import equiframe as ef
from equiframe._comparison_io import file_ref
from equiframe.evidence import canonical_bytes, inventory
from equiframe.serialization import contract_fingerprint
from equiframe.verify import (
    read_verification,
    render_verification_report,
    verification_summary,
    verify,
    verify_migration,
)
from equiframe.verify_types import (
    ExpectedProvenance,
    IndependentReviewEvidence,
    VerificationBinding,
    VerificationResult,
    VerificationReview,
)


def artifact(tmp_path, name, data):
    path = tmp_path / (name + ".arrow")
    with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, data.schema) as writer:
        writer.write_table(data)
    return file_ref(path, "arrow")


def test_equal_wrong_outputs_remain_agreed_but_failed_expected(tmp_path):
    wrong = artifact(tmp_path, "wrong", pa.table({"id": [99, 99, 99], "value": ["a", None, "c"]}))
    expected = artifact(tmp_path, "expected", table())
    result = verify(
        {"first": wrong, "second": wrong}, contract=contract(), expected=expected, work_dir=tmp_path
    )
    assert result.agreement.state == "passed"
    assert [c.state for c in result.expected] == ["failed", "failed"]
    assert result.operational_state == "failed" and not result.publishable
    assert result.independent_review.state == "not_requested"
    assert read_verification(tmp_path / result.verification_id) == result


def test_equal_totals_wrong_keys_are_detected(tmp_path):
    wrong = artifact(tmp_path, "wrong", pa.table({"id": [3, 2, 1], "value": ["a", None, "c"]}))
    expected = artifact(tmp_path, "expected", table())
    assert sum(ef.read_table(wrong)["id"].to_pylist()) == sum(
        ef.read_table(expected)["id"].to_pylist()
    )
    result = verify({"external": wrong}, contract=contract(), expected=expected, work_dir=tmp_path)
    assert result.expected[0].state == "failed"
    assert result.technical.state == "not_requested"


@pytest.mark.parametrize("required,state", [(False, "not_requested"), (True, "not_evaluable")])
def test_absent_expected_is_never_correctness(tmp_path, required, state):
    ref = artifact(tmp_path, "output", table())
    result = verify(
        {"one": ref},
        contract=contract(),
        require_expected=required,
        request_review=True,
        work_dir=tmp_path,
    )
    assert result.expected[0].state == state
    assert result.independent_review.state == "not_evaluable"
    assert result.publishable is (not required)


def review_case(tmp_path, *, count=1, dependent=False, labels=("normal", "normal")):
    ref = artifact(tmp_path, "output", table())
    binding = VerificationBinding(
        contract_sha256=contract_fingerprint(contract()),
        snapshots=(("input", ref.sha256),),
        plan_sha256="1" * 64,
        outputs=(("one", ref.sha256),),
        expected_sha256=ref.sha256,
    )
    provenance = ExpectedProvenance(
        expected_sha256=ref.sha256,
        method="Literal hand construction",
        authors=("expected_author",),
        implementation_authors=("etl_author",),
        independence_declared=True,
        derived_from_engines=("pandas",) if dependent else (),
    )
    reviews = tuple(
        VerificationReview(
            packet_sha256="2" * 64,
            reviewer=name,
            label=label,
            reason="Synthetic review for a software test",
            recorded_at="2026-10-03T10:00:00Z",
            blind_attestation=True,
        )
        for name, label in zip(("reviewer_a", "reviewer_b")[:count], labels[:count], strict=True)
    )
    evidence = IndependentReviewEvidence(
        binding=binding,
        output="one",
        packet_sha256="2" * 64,
        source_document_sha256="3" * 64,
        reviewers=("reviewer_a", "reviewer_b"),
        arbitrator="arbitrator",
        assigned_at="2026-10-03T09:00:00Z",
        reviews=reviews,
    )
    return verify(
        {"one": ref},
        contract=contract(),
        expected=ref,
        provenance=provenance,
        reviews=(evidence,),
        request_review=True,
        snapshots={"input": ref},
        plan_sha256="1" * 64,
        work_dir=tmp_path,
    )


def test_incomplete_review_preserves_operational_approval(tmp_path):
    result = review_case(tmp_path)
    assert result.publishable and result.independent_review.state == "pending_review"


def test_declared_complete_reviews_are_separate_from_authentication(tmp_path):
    result = review_case(tmp_path, count=2)
    assert result.independent_review.state == "passed"
    assert "not authenticated" in result.independent_review.reason


def test_expected_derived_from_test_engine_cannot_establish_O(tmp_path):
    result = review_case(tmp_path, count=2, dependent=True)
    assert result.expected[0].state == "passed" and result.publishable
    assert result.independent_review.state == "not_evaluable"


def test_disagreement_requires_arbitration(tmp_path):
    result = review_case(tmp_path, count=2, labels=("normal", "divergent"))
    assert result.independent_review.state == "pending_review"


def test_external_rules_cannot_be_claimed_without_execution_inputs(tmp_path):
    ref = artifact(tmp_path, "output", table())
    result = verify({"one": ref}, contract=contract(), require_rules=True, work_dir=tmp_path)
    assert result.rules[0].state == "not_evaluable" and not result.publishable


@pytest.mark.parametrize("source,target", list(permutations(("pandas", "polars", "duckdb"), 2)))
def test_migration_verify_keeps_native_execution_and_dimensions(tmp_path, source, target):
    migration = ef.migrate(
        spec(source, target), source=Provider(), expected=ef.ArrowInput(table()), work_dir=tmp_path
    )
    result = verify_migration(tmp_path / migration.migration_id, work_dir=tmp_path)
    assert result.publishable and result.technical.state == "passed"
    assert result.agreement.state == "passed"
    assert all(c.state == "passed" for c in (*result.expected, *result.rules))
    assert {e.plan.engine for _, e in result.executions} == {source, target}
    assert read_verification(tmp_path / result.verification_id) == result


def test_corrupt_artifact_is_retained_as_failed_integrity(tmp_path):
    ref = artifact(tmp_path, "output", table())
    (tmp_path / "output.arrow").write_bytes(b"not Arrow")
    result = verify({"one": ref}, contract=contract(), work_dir=tmp_path)
    assert result.integrity.state == "failed" and not result.publishable


def test_evidence_report_tampering_is_rejected(tmp_path):
    ref = artifact(tmp_path, "output", table())
    result = verify({"one": ref}, contract=contract(), work_dir=tmp_path)
    root = tmp_path / result.verification_id
    (root / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ef.ArtifactIntegrityError):
        read_verification(root)


def test_forged_dimension_is_rejected_even_with_valid_comparison_documents(tmp_path):
    wrong = artifact(tmp_path, "wrong", pa.table({"id": [99, 99, 99], "value": ["a", None, "c"]}))
    expected = artifact(tmp_path, "expected", table())
    result = verify({"one": wrong}, contract=contract(), expected=expected, work_dir=tmp_path)
    forged = result.model_dump()
    forged["expected"] = (result.expected[0].model_copy(update={"state": "passed"}),)
    with pytest.raises(ValueError, match="dimension contradicts"):
        VerificationResult.model_validate(forged)


def test_failed_execution_without_output_remains_not_evaluable(tmp_path):
    migration = ef.migrate(spec(), source=Provider(), work_dir=tmp_path)
    execution = migration.source.execution
    failed = execution.model_copy(
        update={
            "state": "failed",
            "output": None,
            "problem": ef.ExecutionProblem(
                code="failure",
                stage="execution",
                exception_type="RuntimeError",
                message="Synthetic controlled failure",
            ),
        }
    )
    result = verify({"failed": failed}, contract=contract(), work_dir=tmp_path)
    assert result.technical.state == "not_evaluable" and not result.publishable
    assert read_verification(tmp_path / result.verification_id) == result


def test_physical_metadata_contradiction_is_failed_integrity(tmp_path):
    migration = ef.migrate(spec(), source=Provider(), work_dir=tmp_path)
    execution = migration.source.execution
    output = execution.output.model_copy(update={"row_count": 999})
    forged = execution.model_copy(update={"output": output})
    result = verify({"one": forged}, contract=contract(), work_dir=tmp_path)
    assert result.integrity.state == "failed" and not result.publishable


def test_comparison_budget_cannot_become_success(tmp_path):
    ref = artifact(tmp_path, "output", table())
    result = verify(
        {"one": ref},
        contract=contract(),
        expected=ref,
        options=ef.ComparisonOptions(max_rows=1),
        work_dir=tmp_path,
    )
    assert not result.publishable and result.operational_state == "not_evaluable"
    assert read_verification(tmp_path / result.verification_id) == result


def test_captured_input_contract_violation_is_failed_separately(tmp_path):
    migration = ef.migrate(spec(), source=Provider(), work_dir=tmp_path)
    execution = migration.source.execution
    bad = artifact(
        tmp_path,
        "bad_input",
        pa.table({"id": pa.array([None, 2, 3], type=pa.int64()), "value": ["a", None, "c"]}),
    )
    original = execution.inputs[0]
    columns = (original.columns[0].model_copy(update={"null_count": 1}), original.columns[1])
    altered = original.model_copy(update={"data": bad, "columns": columns})
    observed = execution.model_copy(update={"inputs": (altered,)})
    result = verify(
        {"one": observed}, contract=contract(), policy=spec().comparison_policy, work_dir=tmp_path
    )
    assert result.inputs.state == "failed" and result.integrity.state == "passed"
    assert not result.publishable


def test_native_execution_parameters_must_match(tmp_path):
    migration = ef.migrate(spec(), source=Provider(), work_dir=tmp_path)
    left, right = migration.source.execution, migration.target.execution
    parameters = (ef.Parameter(name="declared_parameter", value=ef.StringValue(value="different")),)
    right = right.model_copy(
        update={"plan": right.plan.model_copy(update={"parameters": parameters})}
    )
    result = verify(
        {"source": left, "target": right},
        contract=contract(),
        policy=spec().comparison_policy,
        work_dir=tmp_path,
    )
    assert result.agreement.state == "not_evaluable" and not result.publishable


def test_execution_expected_automatically_retains_engine_dependency(tmp_path):
    migration = ef.migrate(spec(), source=Provider(), work_dir=tmp_path)
    expected = migration.source.execution
    provenance = ExpectedProvenance(
        expected_sha256=expected.output.data.sha256,
        method="Claimed independent reference",
        authors=("expected_author",),
        implementation_authors=("etl_author",),
        independence_declared=True,
    )
    result = verify(
        {"one": migration.target.execution},
        contract=contract(),
        expected=expected,
        provenance=provenance,
        request_review=True,
        policy=spec().comparison_policy,
        plan_sha256="1" * 64,
        work_dir=tmp_path,
    )
    assert result.expected[0].state == "passed"
    assert result.expected_source_engine == "pandas"
    assert result.provenance.derived_from_engines == ("pandas",)
    assert result.independent_review.state == "not_evaluable"


def write_forged_verification(root, result):
    """Recompute every file hash so rejection tests semantic binding, not corruption."""
    (root / "report.json").write_bytes(canonical_bytes(verification_summary(result)) + b"\n")
    (root / "report.html").write_text(render_verification_report(result), encoding="utf-8")
    evidence = tuple(item for item in inventory(root) if item.path != "verification.json")
    (root / "verification.json").write_bytes(
        canonical_bytes(result.model_copy(update={"evidence": evidence}).model_dump(mode="json"))
        + b"\n"
    )


def test_peer_cannot_be_replaced_by_genuine_self_comparison(tmp_path):
    left = artifact(tmp_path, "left", table())
    right = artifact(tmp_path, "right", pa.table({"id": [9, 2, 3], "value": ["a", None, "c"]}))
    result = verify({"left": left, "right": right}, contract=contract(), work_dir=tmp_path)
    assert result.agreement.state == "failed"
    root = tmp_path / result.verification_id
    substitute = ef.compare(left, left, contract=contract(), work_dir=root)
    forged = result.model_copy(
        update={
            "comparisons": (*result.comparisons[:-1], substitute),
            "agreement": result.agreement.model_copy(update={"state": "passed"}),
        }
    )
    with pytest.raises(ValueError, match="requested pair"):
        VerificationResult.model_validate(forged.model_dump())
    write_forged_verification(root, forged)
    with pytest.raises(ValueError, match="requested pair"):
        read_verification(root)


@pytest.mark.parametrize("changed", ["contract", "policy", "options"])
def test_peer_and_expected_use_requested_contract_policy_and_options(tmp_path, changed):
    ref = artifact(tmp_path, "output", table())
    result = verify(
        {"left": ref, "right": ref}, contract=contract(), expected=ref, work_dir=tmp_path
    )
    root = tmp_path / result.verification_id
    kwargs = dict(
        contract=contract(), policy=result.comparison_policy, options=result.comparison_options
    )
    if changed == "contract":
        kwargs["contract"] = contract().model_copy(update={"revision": 2})
    elif changed == "policy":
        kwargs["policy"] = ef.ComparisonPolicy(index="ignore", justification="Synthetic test")
    else:
        kwargs["options"] = ef.ComparisonOptions(max_examples=0)
    for position, reference in ((2, "peer"), (3, "expected")):
        substitute = ef.compare(ref, ref, reference=reference, work_dir=root, **kwargs)
        comparisons = list(result.comparisons)
        checks = list(result.expected)
        comparisons[position] = substitute
        if reference == "expected":
            checks[0] = checks[0].model_copy(update={"comparison_id": substitute.comparison_id})
        forged = result.model_copy(
            update={"comparisons": tuple(comparisons), "expected": tuple(checks)}
        )
        with pytest.raises(ValueError, match=r"contradict.*verification request"):
            VerificationResult.model_validate(forged.model_dump())
        write_forged_verification(root, forged)
        with pytest.raises(ValueError, match=r"contradict.*verification request"):
            read_verification(root)


def test_native_technical_success_cannot_be_changed_to_external_absence(tmp_path):
    migration = ef.migrate(spec(), source=Provider(), work_dir=tmp_path)
    result = verify(
        {"one": migration.source.execution},
        contract=contract(),
        policy=spec().comparison_policy,
        work_dir=tmp_path,
    )
    forged = result.model_copy(
        update={
            "technical_outcomes": (
                result.technical_outcomes[0].model_copy(
                    update={
                        "state": "not_requested",
                        "reason": (
                            "External execution status was not supplied; artifact inspection only"
                        ),
                    }
                ),
            ),
            "technical": result.technical.model_copy(
                update={
                    "state": "not_requested",
                    "reason": "Artifact inspection does not assert ETL execution",
                }
            ),
        }
    )
    with pytest.raises(ValueError, match="captured execution state"):
        VerificationResult.model_validate(forged.model_dump())
    root = tmp_path / result.verification_id
    write_forged_verification(root, forged)
    with pytest.raises(ValueError, match="captured execution state"):
        read_verification(root)
