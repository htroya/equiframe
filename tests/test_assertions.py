"""STEP4 acceptance preserves the comparator's truth, bounds evidence and redacts errors."""

import builtins
import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe.assertion_types import EquivalenceDecision, EquivalencePolicy
from equiframe.assertions import (
    EquivalenceAssertionError,
    EquivalenceDifferentError,
    EquivalenceEvidenceError,
    EquivalenceGuaranteeError,
    EquivalenceInputError,
    EquivalenceNotEvaluableError,
    assert_equivalent,
    equivalence_decision,
)
from equiframe.errors import ArtifactIOError, EquiFrameError, ResourceLimitError

REQUIRED = EquivalencePolicy(require_persisted_evidence=True)


def equal(tmp_path, *, reference="expected"):
    table = pa.table({"id": [1, 2], "value": [10, 20]})
    return ef.diff(table, table, keys=["id"], reference=reference, work_dir=tmp_path)


def different(tmp_path, *, examples=20):
    return ef.diff(
        pa.table({"id": [1, 2], "value": [11, 22]}),
        pa.table({"id": [1, 2], "value": [10, 20]}),
        keys=["id"],
        options=ef.ComparisonOptions(max_examples=examples),
        work_dir=tmp_path,
    )


def path_of(result):
    return Path(url2pathname(urlsplit(result.differences.uri).path))


def check_evidence(result, root, *, policy=REQUIRED):
    return equivalence_decision(result, policy=policy, evidence_root=root)


def persist(result):
    path_of(result).with_name("comparison.json").write_text(result.model_dump_json(), "utf-8")
    return result


def integer_column(nullable=True):
    return ef.ColumnSpec(
        name="value",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )


def test_exports_and_error_families():
    for value in (
        assert_equivalent,
        equivalence_decision,
        EquivalencePolicy,
        EquivalenceDecision,
        EquivalenceAssertionError,
        EquivalenceDifferentError,
        EquivalenceNotEvaluableError,
        EquivalenceGuaranteeError,
        EquivalenceEvidenceError,
        EquivalenceInputError,
    ):
        assert getattr(ef, value.__name__) is value
        assert value.__name__ in ef.__all__
    assert issubclass(EquivalenceAssertionError, AssertionError)
    assert issubclass(EquivalenceAssertionError, EquiFrameError)
    assert issubclass(EquivalenceInputError, ValueError)
    assert not issubclass(EquivalenceInputError, AssertionError)


@pytest.mark.parametrize("reference", ["peer", "expected"])
def test_complete_equivalent_has_explicit_acceptance_and_only_observed_guarantee(
    tmp_path, reference
):
    result = equal(tmp_path, reference=reference)
    decision = equivalence_decision(result)
    assert assert_equivalent(result) is None
    assert decision.accepted is True
    assert decision.code == decision.state == "equivalent"
    assert decision.complete and decision.counts_final
    assert decision.guarantee == "observed_contract"
    assert decision.scope == "output_schema"
    assert decision.reference == reference
    assert decision.contract_sha256 == result.contract_sha256
    assert decision.spec_sha256 == result.spec_sha256
    assert decision.guarantee_conforms and decision.guarantee_failures == ()
    assert decision.evidence_status == "not_requested" and decision.evidence_code is None
    assert decision.safe_reason_code is None
    assert EquivalenceDecision.model_validate_json(decision.model_dump_json()) == decision
    with pytest.raises(TypeError, match="accepted explicitly"):
        bool(decision)
    with pytest.raises(ValidationError):
        decision.accepted = False


@pytest.mark.parametrize("examples", [0, 1, 20])
def test_different_is_never_accepted_even_when_display_omits_all_witnesses(tmp_path, examples):
    result = different(tmp_path, examples=examples)
    decision = equivalence_decision(result)
    assert decision.accepted is False
    assert decision.state == decision.code == "different"
    assert decision.complete and decision.counts_final
    assert decision.safe_reason_code == ("cell_value" if examples else None)
    with pytest.raises(EquivalenceDifferentError) as error:
        assert_equivalent(result)
    assert error.value.decision == decision
    assert error.value.code == "different"
    assert not hasattr(error.value, "result")


def test_incomplete_budget_never_passes_as_empty_differences(tmp_path):
    table = pa.table({"value": [1, 2, 3]})
    result = ef.diff(table, table, work_dir=tmp_path, options=ef.ComparisonOptions(max_rows=1))
    assert result.state == "not_evaluable" and not result.complete
    decision = equivalence_decision(result)
    assert not decision.accepted and not decision.counts_final
    assert decision.code == "not_evaluable" and decision.safe_reason_code == "resource_exhausted"
    with pytest.raises(EquivalenceNotEvaluableError):
        assert_equivalent(result)


def test_invalid_expected_with_complete_final_counts_still_fails(tmp_path):
    result = ef.diff(
        pa.table({"value": [1]}),
        pa.table({"value": pa.array([None], pa.int64())}),
        contract=ef.bag_contract((integer_column(nullable=False),)),
        work_dir=tmp_path,
    )
    decision = equivalence_decision(result)
    assert result.complete and result.counts.final
    assert not decision.accepted and decision.safe_reason_code == "invalid_expected"
    with pytest.raises(EquivalenceNotEvaluableError, match="not evaluable"):
        assert_equivalent(result)
    verified = check_evidence(result, tmp_path)
    assert verified.code == "not_evaluable" and verified.evidence_status == "verified"


@pytest.mark.parametrize("code", ["cancelled", "timeout", "invalid_artifact", "evaluation_failed"])
def test_not_evaluable_diagnostics_keep_original_state(tmp_path, code):
    result = equal(tmp_path).model_copy(
        update={
            "state": "not_evaluable",
            "diagnostics": (ef.ComparisonDiagnostic(code=code, message="PRIVATE_DIAGNOSTIC"),),
        }
    )
    with pytest.raises(EquivalenceNotEvaluableError) as error:
        assert_equivalent(result)
    assert error.value.decision.safe_reason_code == code
    assert "PRIVATE_DIAGNOSTIC" not in str(error.value)


def test_policy_can_pin_all_comparison_context(tmp_path):
    result = equal(tmp_path)
    policy = EquivalencePolicy(
        required_contract_sha256=result.contract_sha256,
        required_spec_sha256=result.spec_sha256,
        required_reference=result.reference,
    )
    assert assert_equivalent(result, policy=policy) is None
    assert equivalence_decision(result, policy=policy).guarantee_conforms
    assert EquivalencePolicy.model_validate_json(policy.model_dump_json()) == policy


@pytest.mark.parametrize(
    "field,value",
    [
        ("required_contract_sha256", "0" * 64),
        ("required_spec_sha256", "0" * 64),
        ("required_reference", "peer"),
    ],
)
def test_pin_mismatches_fail_without_changing_equivalent_state(tmp_path, field, value):
    result = equal(tmp_path)
    policy = EquivalencePolicy(**{field: value})
    decision = equivalence_decision(result, policy=policy)
    assert decision.state == "equivalent" and not decision.accepted
    assert decision.code == "guarantee_mismatch"
    assert decision.guarantee_failures == (field,)
    with pytest.raises(EquivalenceGuaranteeError) as error:
        assert_equivalent(result, policy=policy)
    assert error.value.decision == decision


def test_all_pins_and_evidence_failures_remain_visible_without_masking_state(tmp_path):
    result = different(tmp_path)
    path_of(result).unlink()
    policy = EquivalencePolicy(
        required_contract_sha256="0" * 64,
        required_spec_sha256="0" * 64,
        required_reference="peer",
        require_persisted_evidence=True,
    )
    decision = check_evidence(result, tmp_path, policy=policy)
    assert decision.code == "different"
    assert len(decision.guarantee_failures) == 3
    assert decision.evidence_code == "evidence_missing"
    with pytest.raises(EquivalenceDifferentError) as error:
        assert_equivalent(result, policy=policy, evidence_root=tmp_path)
    assert error.value.decision == decision


def test_guarantee_failure_precedes_evidence_failure_but_preserves_both(tmp_path):
    result = equal(tmp_path)
    path_of(result).unlink()
    policy = REQUIRED.model_copy(update={"required_reference": "peer"})
    decision = check_evidence(result, tmp_path, policy=policy)
    assert decision.code == "guarantee_mismatch" and decision.evidence_code == "evidence_missing"
    with pytest.raises(EquivalenceGuaranteeError):
        assert_equivalent(result, policy=policy, evidence_root=tmp_path)


@pytest.mark.parametrize(
    "factory",
    [
        lambda result: result.model_dump(),
        ef.comparison_report,
        equivalence_decision,
        lambda result: True,
        lambda result: None,
    ],
)
def test_report_mapping_decision_and_other_non_result_inputs_are_rejected(tmp_path, factory):
    value = factory(equal(tmp_path))
    with pytest.raises(EquivalenceInputError, match="ComparisonResult") as error:
        assert_equivalent(value)
    assert error.value.code == "invalid_assertion_input"


@pytest.mark.parametrize(
    "updates",
    [
        {"state": "equivalent", "complete": False},
        {"scope": "sample"},
        {"schema_version": "999"},
        {"state": "unknown"},
        {"reference": "trusted_oracle"},
        {"contract_sha256": "0" * 64},
        {"spec_sha256": "0" * 64},
        {"complete": 1},
        {"counts": ef.ComparisonCounts.model_construct(final=True, matched_rows=-1)},
        {"options": ef.ComparisonOptions.model_construct(max_rows="PRIVATE_BAD_OPTION")},
    ],
)
def test_copied_and_constructed_models_are_revalidated_without_leaking_errors(tmp_path, updates):
    malformed = equal(tmp_path).model_copy(update=updates)
    with pytest.raises(EquivalenceInputError) as error:
        assert_equivalent(malformed)
    assert error.value.code == "invalid_assertion_input"
    displayed = "".join(traceback.format_exception(error.value))
    assert "PRIVATE_BAD_OPTION" not in displayed
    assert error.value.__cause__ is None and error.value.__suppress_context__


def test_missing_constructed_fields_are_invalid_input(tmp_path):
    with pytest.raises(EquivalenceInputError):
        assert_equivalent(ef.ComparisonResult.model_construct(state="equivalent"))


@pytest.mark.parametrize(
    "updates",
    [
        {"guarantee": "exact"},
        {"guarantee": "independent_correctness"},
        {"max_records": 0},
        {"max_evidence_bytes": True},
        {"require_persisted_evidence": 1},
        {"required_reference": "independent"},
        {"required_spec_sha256": "INVALID_HASH"},
    ],
)
def test_unsupported_or_bypassed_policy_is_invalid_configuration(tmp_path, updates):
    policy = EquivalencePolicy.model_copy(EquivalencePolicy(), update=updates)
    with pytest.raises(EquivalenceInputError):
        assert_equivalent(equal(tmp_path), policy=policy)
    with pytest.raises(ValidationError):
        EquivalencePolicy(**updates)


def test_no_partial_policy_exists():
    with pytest.raises(ValidationError):
        EquivalencePolicy(allow_partial=True)
    with pytest.raises(ValidationError):
        EquivalencePolicy(require_complete=False)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"policy": {}},
        {"evidence_root": "raw-root"},
        {"policy": REQUIRED},
        {"evidence_root": Path("raw-root")},
        {"report_path": "report.html"},
    ],
)
def test_configuration_types_and_evidence_root_pairing_are_explicit(tmp_path, kwargs):
    with pytest.raises(EquivalenceInputError):
        assert_equivalent(equal(tmp_path), **kwargs)


def test_default_does_no_evidence_or_report_io(tmp_path, monkeypatch):
    result = equal(tmp_path)
    # Even removed evidence is accepted unless its current integrity is required.
    path_of(result).unlink()
    path_of(result).with_name("comparison.json").unlink()

    def forbidden(*args, **kwargs):
        pytest.fail("assertion default attempted filesystem IO")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    assert assert_equivalent(result, report_path=Path("not-created/report.html")) is None
    assert equivalence_decision(result).evidence_status == "not_requested"


def test_required_current_evidence_verifies_all_records_without_opening_sources(
    tmp_path, monkeypatch
):
    import equiframe._report_io as io

    result = equal(tmp_path)
    assert result.left is not None and result.right is not None
    # Raw input artifacts are deliberately absent. Required evidence covers the
    # finalized comparison and differences, not source authenticity/reexecution.
    Path(url2pathname(urlsplit(result.left.data.uri).path)).unlink()
    original = io._open_regular
    opened = []

    def capture(path):
        opened.append(path.name)
        return original(path)

    monkeypatch.setattr(io, "_open_regular", capture)
    decision = check_evidence(result, tmp_path)
    assert decision.accepted and decision.evidence_status == "verified"
    assert opened == ["comparison.json", "differences.jsonl"]
    assert assert_equivalent(result, policy=REQUIRED, evidence_root=tmp_path) is None


@pytest.mark.parametrize("name", ["comparison.json", "differences.jsonl"])
def test_missing_required_evidence_is_a_distinct_failure(tmp_path, name):
    result = equal(tmp_path)
    path_of(result).with_name(name).unlink()
    decision = check_evidence(result, tmp_path)
    assert decision.code == decision.evidence_code == "evidence_missing"
    assert decision.state == "equivalent" and not decision.accepted
    with pytest.raises(EquivalenceEvidenceError) as error:
        assert_equivalent(result, policy=REQUIRED, evidence_root=tmp_path)
    assert error.value.code == "evidence_missing"
    assert str(tmp_path) not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize("name", ["comparison.json", "differences.jsonl"])
def test_corrupt_required_evidence_never_passes(tmp_path, name):
    result = equal(tmp_path)
    path_of(result).with_name(name).write_text("CORRUPT_PRIVATE_CONTENT", "utf-8")
    decision = check_evidence(result, tmp_path)
    assert decision.evidence_status == "corrupt" and decision.code == "evidence_corrupt"
    with pytest.raises(EquivalenceEvidenceError) as error:
        assert_equivalent(result, policy=REQUIRED, evidence_root=tmp_path)
    assert "CORRUPT_PRIVATE_CONTENT" not in str(error.value)


def test_current_manifest_must_match_the_result(tmp_path):
    result = equal(tmp_path)
    persist(result.model_copy(update={"work_units": result.work_units + 1}))
    assert check_evidence(result, tmp_path).evidence_code == "evidence_corrupt"


def test_hash_verification_is_not_just_size_verification(tmp_path):
    result = different(tmp_path)
    original = path_of(result).read_bytes()
    # Change only a free-text message while retaining a valid JSONL byte length.
    modified = original.replace(b"values", b"VALUES", 1)
    assert modified != original and len(modified) == len(original)
    path_of(result).write_bytes(modified)
    decision = check_evidence(result, tmp_path)
    assert decision.code == "different" and decision.evidence_code == "evidence_corrupt"


def test_all_persisted_records_verified_even_without_examples(tmp_path):
    result = different(tmp_path, examples=0)
    records = [json.loads(line) for line in path_of(result).read_bytes().splitlines()]
    records[-1]["position"] = 9000
    raw = b"".join(json.dumps(record).encode() + b"\n" for record in records)
    path_of(result).write_bytes(raw)
    forged = persist(
        result.model_copy(
            update={
                "differences": result.differences.model_copy(
                    update={"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
                )
            }
        )
    )
    decision = check_evidence(forged, tmp_path)
    assert decision.code == "different" and decision.evidence_code == "evidence_corrupt"


def test_byte_and_record_budget_failures_are_distinct_from_corruption(tmp_path):
    result = equal(tmp_path)
    policy = REQUIRED.model_copy(update={"max_evidence_bytes": 1})
    decision = check_evidence(result, tmp_path, policy=policy)
    assert decision.code == "evidence_budget_exceeded"
    with pytest.raises(EquivalenceEvidenceError) as error:
        assert_equivalent(result, policy=policy, evidence_root=tmp_path)
    assert error.value.code == "evidence_budget_exceeded"
    unequal = different(tmp_path)
    policy = REQUIRED.model_copy(update={"max_records": 1})
    decision = check_evidence(unequal, tmp_path, policy=policy)
    assert decision.code == "different" and decision.evidence_code == "evidence_budget_exceeded"


@pytest.mark.parametrize("path_kind", ["outside", "traversal", "remote", "encoded", "filename"])
def test_required_evidence_paths_are_confined_before_any_file_read(
    tmp_path, monkeypatch, path_kind
):
    import equiframe._report_io as io

    result = equal(tmp_path)
    paths = {
        "outside": (tmp_path.parent / "private-outside" / "differences.jsonl").as_uri(),
        "traversal": tmp_path.as_uri() + "/../private-outside/differences.jsonl",
        "remote": "https://example.com/private/differences.jsonl",
        "encoded": tmp_path.as_uri() + "/%FF/differences.jsonl",
        "filename": path_of(result).with_name("private-secret.jsonl").as_uri(),
    }
    result = result.model_copy(
        update={"differences": result.differences.model_copy(update={"uri": paths[path_kind]})}
    )

    def forbidden(*args, **kwargs):
        pytest.fail("unconfined evidence was read")

    monkeypatch.setattr(io, "_open_regular", forbidden)
    decision = check_evidence(result, tmp_path)
    assert decision.evidence_status == "path_rejected"
    assert decision.code == "evidence_path_rejected"


@pytest.mark.parametrize("name", ["comparison.json", "differences.jsonl"])
def test_symlinked_evidence_is_rejected(tmp_path, name):
    result = equal(tmp_path)
    path = path_of(result).with_name(name)
    original = path.with_name(name + ".original")
    path.rename(original)
    try:
        path.symlink_to(original)
    except OSError:
        pytest.skip("symlinks unavailable on this host")
    decision = check_evidence(result, tmp_path)
    assert decision.code == "evidence_path_rejected"


def test_symlinked_root_and_parent_traversal_root_are_rejected(tmp_path):
    result = equal(tmp_path)
    link = tmp_path / "linked-root"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this host")
    assert check_evidence(result, link).code == "evidence_path_rejected"
    assert check_evidence(result, tmp_path / ".." / tmp_path.name).code == "evidence_path_rejected"


def test_unreadable_evidence_failure_uses_exception_type_not_private_text(tmp_path, monkeypatch):
    import equiframe._report_io as io

    result = equal(tmp_path)

    def denied(*args, **kwargs):
        try:
            raise PermissionError("PRIVATE_OS_PATH")
        except PermissionError as cause:
            raise ArtifactIOError("PRIVATE_ERROR_TEXT") from cause

    monkeypatch.setattr(io, "_open_regular", denied)
    decision = check_evidence(result, tmp_path)
    assert decision.code == "evidence_unreadable"
    with pytest.raises(EquivalenceEvidenceError) as error:
        assert_equivalent(result, policy=REQUIRED, evidence_root=tmp_path)
    displayed = "".join(traceback.format_exception(error.value))
    assert "PRIVATE_OS_PATH" not in displayed and "PRIVATE_ERROR_TEXT" not in displayed


def test_assertion_error_messages_and_decisions_have_no_values_names_or_result_paths(tmp_path):
    secret_name = "PRIVATE_COLUMN_73828"
    result = ef.diff(
        pa.table({secret_name: ["PRIVATE_VALUE_A"]}),
        pa.table({secret_name: ["PRIVATE_VALUE_B"]}),
        work_dir=tmp_path,
    )
    difference = result.examples[0].model_copy(
        update={"message": "PRIVATE_RAW_MESSAGE", "code": "PRIVATE_FREEFORM_CODE"}
    )
    result = result.model_copy(update={"examples": (difference, *result.examples[1:])})
    with pytest.raises(EquivalenceDifferentError) as error:
        assert_equivalent(result)
    text = str(error.value) + repr(error.value) + error.value.decision.model_dump_json()
    for private in (
        secret_name,
        "PRIVATE_VALUE_A",
        "PRIVATE_VALUE_B",
        "PRIVATE_RAW_MESSAGE",
        "PRIVATE_FREEFORM_CODE",
        str(tmp_path),
        result.comparison_id,
    ):
        assert private not in text
    assert len(str(error.value)) < 250


def test_report_pointer_is_explicit_bounded_escaped_and_never_written(tmp_path):
    result = different(tmp_path)
    path = tmp_path / "visible-report\n\x1b[31m.html"
    with pytest.raises(EquivalenceDifferentError) as error:
        assert_equivalent(result, report_path=path)
    assert "report:" in str(error.value)
    assert "\\n" in str(error.value) and "\\u001b" in str(error.value)
    assert "\n" not in str(error.value) and "\x1b" not in str(error.value)
    assert not path.exists()
    with pytest.raises(EquivalenceDifferentError) as long_error:
        assert_equivalent(result, report_path=Path("x" * 3000))
    assert len(str(long_error.value)) < 500


def test_report_budget_cannot_mask_a_comparison_failure(tmp_path, monkeypatch):
    import equiframe.assertions as api

    def over_budget(*args, **kwargs):
        raise ResourceLimitError("PRIVATE_REPORT_PATH")

    monkeypatch.setattr(api, "comparison_report", over_budget)
    with pytest.raises(EquivalenceDifferentError) as error:
        assert_equivalent(different(tmp_path))
    assert error.value.decision.safe_reason_code is None
    assert "PRIVATE_REPORT_PATH" not in str(error.value)


def test_pytest_hides_internal_frames_and_does_not_print_raw_result(tmp_path):
    result = different(tmp_path)
    document = tmp_path / "result.json"
    document.write_text(result.model_dump_json(), "utf-8")
    test = tmp_path / "test_consumer.py"
    test.write_text(
        "from pathlib import Path\n"
        "import equiframe as ef\n"
        f"RESULT_FILE = Path({str(document)!r})\n"
        "def test_consumer():\n"
        "    result = ef.read_comparison(RESULT_FILE)\n"
        "    ef.assert_equivalent(result)\n",
        "utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=long", "-o", "addopts=", str(test)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "ef.assert_equivalent(result)" in completed.stdout
    assert "EquivalenceDifferentError" in completed.stdout
    assert "assertions.py" not in completed.stdout
    assert "ComparisonResult(" not in completed.stdout
    assert "differences.jsonl" not in completed.stdout


def test_authorized_normalization_is_preserved_and_never_reinterpreted_as_strict_identity(tmp_path):
    column = ef.ColumnSpec(
        name="value",
        logical_type=ef.StringType(),
        nullable=True,
        null_policy=ef.NullPolicy(
            representations=("null", "empty_string"), justification="source sentinel"
        ),
    )
    left = pa.table({"value": [""]})
    right = pa.table({"value": pa.array([None], pa.string())})
    relaxed = ef.diff(left, right, contract=ef.bag_contract((column,)), work_dir=tmp_path)
    assert relaxed.applied_policies
    assert assert_equivalent(relaxed) is None
    strict_column = column.model_copy(
        update={"null_policy": ef.NullPolicy(representations=("null",))}
    )
    strict = ef.diff(left, right, contract=ef.bag_contract((strict_column,)), work_dir=tmp_path)
    with pytest.raises(EquivalenceDifferentError):
        assert_equivalent(strict)
    with pytest.raises(EquivalenceGuaranteeError):
        assert_equivalent(
            relaxed, policy=EquivalencePolicy(required_spec_sha256=strict.spec_sha256)
        )


def test_tolerance_policy_is_observed_equivalence_without_recomparison(tmp_path):
    column = ef.ColumnSpec(
        name="value",
        logical_type=ef.FloatType(bits=64),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        nan_policy=ef.NaNPolicy(handling="distinct"),
        numeric_policy=ef.NumericPolicy(
            comparison="approximate",
            unit="sensor",
            tolerance=ef.Tolerance(
                absolute="0.1", unit="sensor", justification="sensor resolution"
            ),
        ),
    )
    result = ef.diff(
        pa.table({"value": [1.0]}),
        pa.table({"value": [1.05]}),
        contract=ef.bag_contract((column,)),
        work_dir=tmp_path,
    )
    assert result.strategy == "matching"
    assert assert_equivalent(result) is None
    assert equivalence_decision(result).guarantee == "observed_contract"


def test_decision_rejects_internally_inconsistent_acceptance(tmp_path):
    decision = equivalence_decision(equal(tmp_path))
    for update in (
        {"accepted": False},
        {"state": "different"},
        {"complete": False},
        {"code": "different"},
        {"guarantee_conforms": False},
        {"evidence_status": "missing"},
    ):
        with pytest.raises(ValidationError):
            EquivalenceDecision.model_validate(decision.model_copy(update=update))


@pytest.mark.parametrize("factory", ["copy", "construct"])
def test_completed_capture_row_counts_cannot_be_forged_as_zero_defaults(tmp_path, factory):
    result = equal(tmp_path)
    if factory == "copy":
        malformed = result.model_copy(update={"counts": {"final": True}})
    else:
        malformed = ef.ComparisonResult.model_construct(
            **(result.model_dump() | {"counts": ef.ComparisonCounts(final=True)})
        )
    with pytest.raises(ValidationError, match="captured table metadata"):
        ef.ComparisonResult.model_validate(malformed)
    with pytest.raises(EquivalenceInputError):
        assert_equivalent(malformed)


@pytest.mark.parametrize("path", [Path("bad\x00path"), Path("bad\ud800path")])
def test_invalid_caller_root_path_has_redacted_configuration_failure(tmp_path, path):
    with pytest.raises(EquivalenceInputError) as error:
        assert_equivalent(equal(tmp_path), policy=REQUIRED, evidence_root=path)
    assert "bad" not in str(error.value)


@pytest.mark.parametrize("uri", ["file://[invalid/path", "https://[invalid/x"])
def test_malformed_uri_model_bypass_is_invalid_input(tmp_path, uri):
    result = equal(tmp_path)
    malformed = result.model_copy(
        update={"differences": result.differences.model_copy(update={"uri": uri})}
    )
    with pytest.raises(EquivalenceInputError) as error:
        assert_equivalent(malformed, policy=REQUIRED, evidence_root=tmp_path)
    assert uri not in str(error.value)


def test_any_presentation_failure_preserves_original_comparison_failure(tmp_path, monkeypatch):
    import equiframe.assertions as api

    def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE_FORMATTING_DIAGNOSTIC")

    monkeypatch.setattr(api, "comparison_report", broken)
    with pytest.raises(EquivalenceDifferentError) as error:
        assert_equivalent(different(tmp_path))
    assert error.value.decision.safe_reason_code is None
    assert "PRIVATE_FORMATTING_DIAGNOSTIC" not in str(error.value)


def test_default_failure_does_not_read_or_persist_report_files(tmp_path, monkeypatch):
    result = different(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("failing assertion attempted filesystem IO")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    with pytest.raises(EquivalenceDifferentError):
        assert_equivalent(result, report_path=Path("caller-report.html"))


def test_not_evaluable_evidence_failure_does_not_change_primary_failure(tmp_path):
    result = equal(tmp_path).model_copy(
        update={
            "state": "not_evaluable",
            "diagnostics": (ef.ComparisonDiagnostic(code="cancelled", message="Cancelled"),),
        }
    )
    persist(result)
    path_of(result).unlink()
    decision = check_evidence(result, tmp_path)
    assert decision.code == "not_evaluable"
    assert decision.evidence_code == "evidence_missing"
    with pytest.raises(EquivalenceNotEvaluableError) as error:
        assert_equivalent(result, policy=REQUIRED, evidence_root=tmp_path)
    assert error.value.decision == decision


def test_complete_counts_validation_does_not_require_absent_optional_table_metadata(tmp_path):
    result = equal(tmp_path)
    assert result.left is not None and result.right is not None
    result = result.model_copy(
        update={
            "left": result.left.model_copy(update={"table": None}),
            "right": result.right.model_copy(update={"table": None}),
        }
    )
    assert assert_equivalent(result) is None
