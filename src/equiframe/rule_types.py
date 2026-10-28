"""Supplementary v1 evidence for operational rules; contract 1.0 stays unchanged."""

from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    Text,
    _ExplicitOutcome,
    fail,
)
from equiframe.comparison_types import ComparisonValue
from equiframe.types import ArtifactRef, DecisionState, Sha256

CheckState = Literal["satisfied", "violated", "not_applicable", "not_evaluable"]


class RuleOptions(FrozenModel):
    max_rows: PositiveInt = 1_000_000
    max_artifact_bytes: PositiveInt = 128 * 1024 * 1024
    max_evidence_bytes: PositiveInt = 64 * 1024 * 1024
    max_work: PositiveInt = 10_000_000
    max_examples: NonNegativeInt = 20
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None


class RuleFinding(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    check_id: Identifier
    code: Text
    table: Identifier
    position: NonNegativeInt | None = None
    column: str | None = None
    observed: tuple[ComparisonValue, ...] = ()
    expected: tuple[ComparisonValue, ...] = ()
    message: Text


class CheckResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .state and .complete explicitly; not_applicable is not approval"
    )

    check_id: Identifier
    revision: PositiveInt | None = None
    kind: Literal["precondition", "rule"]
    implementation: Text | None = None
    state: CheckState
    complete: bool
    required: bool | None = None
    severity: Literal["info", "warning", "error"] | None = None
    reason: Text | None = None
    violation_count: NonNegativeInt = 0
    examined_rows: NonNegativeInt = 0
    examples: tuple[RuleFinding, ...] = ()
    findings: ArtifactRef | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.kind == "rule" and (
            self.revision is None or self.required is None or self.severity is None
        ):
            fail("rule_metadata", "rule requires revision, required and severity", "kind")
        if self.kind == "precondition" and (self.required is not None or self.severity is not None):
            fail("precondition_metadata", "precondition does not carry rule policy", "kind")
        if self.state == "satisfied" and (not self.complete or self.violation_count):
            fail("rule_state", "satisfied requires complete check without violations", "state")
        if self.state == "violated" and not self.violation_count:
            fail("rule_state", "violated requires observed findings", "state")
        if self.state in ("not_applicable", "not_evaluable") and not self.reason:
            fail("rule_state", "skipped or unavailable checks require a reason", "reason")
        if self.state == "not_applicable" and (not self.complete or self.violation_count):
            fail("rule_state", "not_applicable requires a verified reason", "state")
        if self.state == "not_evaluable" and (self.complete or self.violation_count):
            fail("rule_state", "not_evaluable cannot claim a completed check or findings", "state")
        if len(self.examples) > self.violation_count:
            fail("rule_examples", "examples exceed finding count", "examples")
        if any(example.check_id != self.check_id for example in self.examples):
            fail("rule_examples", "example belongs to another check", "examples")
        if self.findings is not None and self.findings.format != "jsonl":
            fail("rule_evidence", "findings must be JSONL", "findings")
        return self


class RuleCoverage(FrozenModel):
    declared: NonNegativeInt
    checked: NonNegativeInt
    skipped: NonNegativeInt
    unavailable: NonNegativeInt
    required_declared: NonNegativeInt
    required_checked: NonNegativeInt
    alerts: NonNegativeInt
    finding_count: NonNegativeInt
    preconditions_declared: NonNegativeInt
    preconditions_verified: NonNegativeInt
    preconditions_unavailable: NonNegativeInt
    highest_alert_severity: Literal["info", "warning", "error"] | None = None


class RuleEvaluation(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .decision, .complete and .coverage explicitly; no_alert is not equivalence"
    )

    schema_version: Literal["1.0"] = "1.0"
    evaluation_id: Identifier
    run_id: Identifier
    execution_id: Identifier
    contract_id: Identifier
    contract_revision: PositiveInt
    contract_sha256: Sha256
    rule_set_sha256: Sha256
    execution_state: Text
    options: RuleOptions
    decision: DecisionState
    complete: bool
    preconditions: tuple[CheckResult, ...]
    rules: tuple[CheckResult, ...]
    coverage: RuleCoverage
    started_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    work_units: NonNegativeInt
    diagnostic: Text | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if any(item.kind != "precondition" for item in self.preconditions):
            fail("rule_evidence", "precondition result has wrong kind", "preconditions")
        if any(item.kind != "rule" for item in self.rules):
            fail("rule_evidence", "rule result has wrong kind", "rules")
        checked = tuple(r for r in self.rules if r.state in ("satisfied", "violated"))
        alerts = tuple(r for r in self.rules if r.state == "violated")
        severities = {"info": 1, "warning": 2, "error": 3}
        highest = max(
            (r.severity for r in alerts if r.severity is not None),
            key=severities.__getitem__,
            default=None,
        )
        expected_coverage = RuleCoverage(
            declared=len(self.rules),
            checked=len(checked),
            skipped=sum(r.state == "not_applicable" for r in self.rules),
            unavailable=sum(r.state == "not_evaluable" for r in self.rules),
            required_declared=sum(r.required is True for r in self.rules),
            required_checked=sum(r.required is True for r in checked),
            alerts=len(alerts),
            finding_count=sum(r.violation_count for r in self.rules),
            preconditions_declared=len(self.preconditions),
            preconditions_verified=sum(r.complete for r in self.preconditions),
            preconditions_unavailable=sum(not r.complete for r in self.preconditions),
            highest_alert_severity=highest,
        )
        if self.coverage != expected_coverage:
            fail("rule_coverage", "coverage does not match check results", "coverage")
        expected_complete = (
            bool(self.rules)
            and self.diagnostic is None
            and self.execution_state == "completed"
            and all(item.complete for item in (*self.preconditions, *self.rules))
            and any(item.state in ("satisfied", "violated") for item in self.rules)
        )
        if self.complete != expected_complete:
            fail(
                "rule_completeness",
                "completeness does not match checked rules and execution",
                "complete",
            )
        expected_decision: DecisionState = (
            "alert" if alerts else "no_alert" if self.complete else "not_evaluable"
        )
        if self.decision != expected_decision:
            fail("rule_decision", "decision does not match completed checks and alerts", "decision")
        return self
