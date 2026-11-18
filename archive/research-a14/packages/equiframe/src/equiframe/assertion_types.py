"""Acceptance policy and detached decisions over existing comparison results.

These models describe integration acceptance, not another comparison algorithm.
The sole guarantee is complete observed equivalence under the declared output
contract. A peer or expected reference does not establish independent correctness,
and evidence integrity does not authenticate the producer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from typing_extensions import Never, Self

from equiframe._base import FrozenModel, PositiveInt
from equiframe.types import ComparisonState, Sha256

EquivalenceCode = Literal[
    "equivalent",
    "different",
    "not_evaluable",
    "guarantee_mismatch",
    "evidence_missing",
    "evidence_corrupt",
    "evidence_path_rejected",
    "evidence_budget_exceeded",
    "evidence_unreadable",
]
EvidenceFailureCode = Literal[
    "evidence_missing",
    "evidence_corrupt",
    "evidence_path_rejected",
    "evidence_budget_exceeded",
    "evidence_unreadable",
]
EvidenceStatus = Literal[
    "not_requested",
    "verified",
    "missing",
    "corrupt",
    "path_rejected",
    "budget_exceeded",
    "unreadable",
]
GuaranteeFailure = Literal["required_contract_sha256", "required_spec_sha256", "required_reference"]


class EquivalencePolicy(FrozenModel):
    """Require complete output-schema equivalence, optionally pinning its context.

    No setting weakens evaluation, changes a comparison policy, permits partial
    results or asserts independent correctness. Persisted inspection requires an
    explicit evidence_root and verifies the current manifest and all differences
    within these budgets; source captures are not opened.
    """

    schema_version: Literal["1.0"] = "1.0"
    guarantee: Literal["observed_contract"] = "observed_contract"
    required_contract_sha256: Sha256 | None = None
    required_spec_sha256: Sha256 | None = None
    required_reference: Literal["peer", "expected"] | None = None
    require_persisted_evidence: bool = False
    max_evidence_bytes: PositiveInt = 64 * 1024 * 1024
    max_records: PositiveInt = 100000


class EquivalenceDecision(FrozenModel):
    """Safe integration summary preserving the original comparison verdict.

    Inspect accepted explicitly. Comparison state failures take precedence over
    guarantee mismatches and evidence failures, which remain separately visible.
    This document is not accepted as input to assert_equivalent.
    """

    schema_version: Literal["1.0"] = "1.0"
    accepted: bool
    code: EquivalenceCode
    state: ComparisonState
    complete: bool
    counts_final: bool
    scope: Literal["output_schema"] = "output_schema"
    reference: Literal["peer", "expected"]
    contract_sha256: Sha256
    spec_sha256: Sha256
    guarantee: Literal["observed_contract"] = "observed_contract"
    guarantee_conforms: bool
    guarantee_failures: tuple[GuaranteeFailure, ...]
    evidence_status: EvidenceStatus
    evidence_code: EvidenceFailureCode | None
    safe_reason_code: str | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.complete != self.counts_final:
            raise ValueError("decision count completeness must preserve result completeness")
        if self.state in ("equivalent", "different") and not self.complete:
            raise ValueError("a final verdict requires complete evaluation")
        if self.guarantee_conforms != (not self.guarantee_failures):
            raise ValueError("guarantee conformance must describe its unmet requirements")
        if len(set(self.guarantee_failures)) != len(self.guarantee_failures):
            raise ValueError("guarantee failures must be unique")
        expected_evidence = (
            None
            if self.evidence_status in ("not_requested", "verified")
            else "evidence_" + self.evidence_status
        )
        if self.evidence_code != expected_evidence:
            raise ValueError("evidence status and failure code must agree")
        expected_code = (
            self.state
            if self.state != "equivalent"
            else "guarantee_mismatch"
            if not self.guarantee_conforms
            else self.evidence_code or "equivalent"
        )
        if self.code != expected_code or self.accepted != (expected_code == "equivalent"):
            raise ValueError("acceptance must preserve comparison, guarantee and evidence failures")
        return self

    def __bool__(self) -> Never:
        raise TypeError("EquivalenceDecision has no truth value; inspect .accepted explicitly")
