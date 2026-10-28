"""Fail-closed assertions and integration decisions over existing comparisons.

Nothing here compares data again, changes its policy or authenticates a producer.
By default no evidence files are opened. Optional bounded verification checks
only the current comparison manifest and its complete differences, under an
explicit caller-authorized root. Reports must be written separately beforehand.
"""

from __future__ import annotations

import errno
import json
from pathlib import Path
from typing import cast

from equiframe.assertion_types import (
    EquivalenceCode,
    EquivalenceDecision,
    EquivalencePolicy,
    EvidenceFailureCode,
    EvidenceStatus,
    GuaranteeFailure,
)
from equiframe.comparison_report import comparison_report
from equiframe.comparison_types import ComparisonResult
from equiframe.errors import (
    ArtifactIntegrityError,
    ArtifactIOError,
    EquiFrameError,
    ResourceLimitError,
)
from equiframe.report_types import ReportOptions


class EquivalenceInputError(ValueError, EquiFrameError):
    """Invalid caller input or unsupported assertion configuration, not a verdict."""

    code = "invalid_assertion_input"


class EquivalenceAssertionError(AssertionError, EquiFrameError):
    """Safe failure carrying a detached decision, never the raw comparison data."""

    code = "equivalence_not_accepted"

    def __init__(self, decision: EquivalenceDecision, *, report_path: Path | None = None) -> None:
        self.decision = decision
        self.code = decision.code
        messages = {
            "different": "Comparison differs; review the report and declared policies",
            "not_evaluable": "Comparison is not evaluable; resolve the diagnostic and rerun",
            "guarantee_mismatch": "Required comparison context differs; review policy pins",
            "evidence_missing": "Required evidence is missing; restore finalized comparison files",
            "evidence_corrupt": "Required evidence failed integrity checks; restore or regenerate",
            "evidence_path_rejected": "Evidence path was rejected; use a confined local root",
            "evidence_budget_exceeded": "Evidence verification exceeded its budget; review limits",
            "evidence_unreadable": "Required evidence is unreadable; check local read access",
        }
        message = f"[{decision.code}] {messages.get(decision.code, 'Equivalence was not accepted')}"
        if decision.safe_reason_code is not None:
            message += f" (reason: {decision.safe_reason_code})"
        if report_path is not None:
            # This is a trusted pointer supplied by the caller, not a result URI.
            # No resolution or file access. ASCII JSON escapes terminal controls.
            escaped = json.dumps(str(report_path), ensure_ascii=True)
            pointer = escaped if len(escaped) <= 240 else escaped[:236] + '..."'
            message += f"; report: {pointer}"
        super().__init__(message)


class EquivalenceDifferentError(EquivalenceAssertionError):
    """A completed comparison found differences or contract violations."""

    code = "different"


class EquivalenceNotEvaluableError(EquivalenceAssertionError):
    """A comparison cannot establish equivalence, even if traversal completed."""

    code = "not_evaluable"


class EquivalenceGuaranteeError(EquivalenceAssertionError):
    """Observed equivalence does not satisfy the caller's pinned context."""

    code = "guarantee_mismatch"


class EquivalenceEvidenceError(EquivalenceAssertionError):
    """Observed equivalence lacks the required verified persisted evidence."""

    code = "equivalence_evidence_error"


def _validated(
    result: ComparisonResult, policy: EquivalencePolicy | None, evidence_root: Path | None
) -> tuple[ComparisonResult, EquivalencePolicy]:
    __tracebackhide__ = True
    if not isinstance(result, ComparisonResult):
        raise EquivalenceInputError(
            "[invalid_assertion_input] result must be a ComparisonResult, not a report or mapping"
        ) from None
    if policy is not None and not isinstance(policy, EquivalencePolicy):
        raise EquivalenceInputError(
            "[invalid_assertion_input] policy must be an EquivalencePolicy or None"
        ) from None
    if evidence_root is not None and not isinstance(evidence_root, Path):
        raise EquivalenceInputError(
            "[invalid_assertion_input] evidence_root must be an explicit pathlib.Path"
        ) from None
    if evidence_root is not None and (
        "\x00" in str(evidence_root)
        or any(0xD800 <= ord(char) <= 0xDFFF for char in str(evidence_root))
    ):
        raise EquivalenceInputError(
            "[invalid_assertion_input] evidence_root must contain a valid local path"
        ) from None
    try:
        # FrozenModel revalidates instances recursively, including model_copy and
        # model_construct bypasses. Do not coerce mappings or serialized reports.
        result = ComparisonResult.model_validate(result, strict=True)
        policy = EquivalencePolicy.model_validate(
            policy if policy is not None else EquivalencePolicy(), strict=True
        )
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise EquivalenceInputError(
            "[invalid_assertion_input] invalid comparison result or assertion policy; "
            "recreate it through the typed API"
        ) from None
    if policy.require_persisted_evidence != (evidence_root is not None):
        raise EquivalenceInputError(
            "[invalid_assertion_input] require_persisted_evidence and an explicit evidence_root "
            "must be supplied together"
        ) from None
    return result, policy


def _inspect(
    result: ComparisonResult, policy: EquivalencePolicy, root: Path | None
) -> tuple[EvidenceStatus, EvidenceFailureCode | None]:
    __tracebackhide__ = True
    if root is None:
        return "not_requested", None
    from equiframe._report_io import EvidencePathError, inspect_evidence

    try:
        inspect_evidence(
            result,
            root,
            max_bytes=policy.max_evidence_bytes,
            max_records=policy.max_records,
            max_examples=0,
        )
    except EvidencePathError:
        return "path_rejected", "evidence_path_rejected"
    except ResourceLimitError:
        return "budget_exceeded", "evidence_budget_exceeded"
    except ArtifactIOError as error:
        cause = error.__cause__
        if isinstance(cause, FileNotFoundError):
            return "missing", "evidence_missing"
        if isinstance(cause, OSError) and cause.errno in (errno.ELOOP, errno.ENOTDIR):
            return "path_rejected", "evidence_path_rejected"
        return "unreadable", "evidence_unreadable"
    except ArtifactIntegrityError:
        return "corrupt", "evidence_corrupt"
    return "verified", None


def _safe_reason(result: ComparisonResult) -> str | None:
    __tracebackhide__ = True
    if result.state == "equivalent":
        return None
    try:
        report = comparison_report(result, options=ReportOptions(max_examples=1))
    except Exception:
        # Presentation is best-effort, with no authority over acceptance. A
        # formatting failure or budget must not mask the comparison verdict.
        return None
    if report.reasons:
        return report.reasons[0].partition(":")[0]
    return report.examples[0].code if report.examples else None


def equivalence_decision(
    result: ComparisonResult,
    *,
    policy: EquivalencePolicy | None = None,
    evidence_root: Path | None = None,
) -> EquivalenceDecision:
    """Return explicit acceptance of a validated, full output-schema comparison.

    Only equivalent + complete + final counts can pass. Both peer and expected
    references establish only observed_contract equivalence. Optional pins and
    persisted evidence can tighten acceptance, never change comparison truth.

    Invalid inputs/configuration raise EquivalenceInputError. Other failures are
    recorded without raising. Precedence is original state, guarantee pins, then
    evidence; all requested checks remain visible on the returned decision.
    Supplying evidence_root requires policy.require_persisted_evidence=True.
    """
    __tracebackhide__ = True
    result, policy = _validated(result, policy, evidence_root)
    failures: list[GuaranteeFailure] = []
    for field, required, observed in (
        ("required_contract_sha256", policy.required_contract_sha256, result.contract_sha256),
        ("required_spec_sha256", policy.required_spec_sha256, result.spec_sha256),
        ("required_reference", policy.required_reference, result.reference),
    ):
        if required is not None and required != observed:
            failures.append(cast(GuaranteeFailure, field))
    evidence_status, evidence_code = _inspect(result, policy, evidence_root)
    code: EquivalenceCode = (
        result.state
        if result.state != "equivalent"
        else "guarantee_mismatch"
        if failures
        else evidence_code or "equivalent"
    )
    return EquivalenceDecision(
        accepted=code == "equivalent",
        code=code,
        state=result.state,
        complete=result.complete,
        counts_final=result.counts.final,
        scope=result.scope,
        reference=result.reference,
        contract_sha256=result.contract_sha256,
        spec_sha256=result.spec_sha256,
        guarantee=policy.guarantee,
        guarantee_conforms=not failures,
        guarantee_failures=tuple(failures),
        evidence_status=evidence_status,
        evidence_code=evidence_code,
        safe_reason_code=_safe_reason(result),
    )


def assert_equivalent(
    result: ComparisonResult,
    *,
    policy: EquivalencePolicy | None = None,
    evidence_root: Path | None = None,
    report_path: Path | None = None,
) -> None:
    """Return None on accepted equivalence; otherwise raise a safe typed assertion.

    Write any desired report before calling. report_path is only a caller-trusted,
    escaped, bounded pointer displayed on failure; no report is written or read.
    Values, names, producer diagnostics and result paths are never displayed.
    Pytest can hide helper frames; a caller's own source/locals and separately
    published artifacts remain the caller's responsibility.
    """
    __tracebackhide__ = True
    if report_path is not None and not isinstance(report_path, Path):
        raise EquivalenceInputError(
            "[invalid_assertion_input] report_path must be a pathlib.Path or None"
        ) from None
    decision = equivalence_decision(result, policy=policy, evidence_root=evidence_root)
    if decision.accepted:
        return
    error_type = (
        EquivalenceDifferentError
        if decision.code == "different"
        else EquivalenceNotEvaluableError
        if decision.code == "not_evaluable"
        else EquivalenceGuaranteeError
        if decision.code == "guarantee_mismatch"
        else EquivalenceEvidenceError
    )
    raise error_type(decision, report_path=report_path) from None
