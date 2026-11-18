"""Validate local pilot records and summarize attestations, never certify adoption.

Developer-only sdist tool, not a runtime API. Reads one bounded JSON file;
never executes a reproducer, follows evidence references, contacts people or
uploads data. Hashes refer to separately permissioned evidence. Input assertions
are not authenticated. A valid empty registry is honest, not a failed install.
"""

from __future__ import annotations

import argparse
import json
import stat
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing_extensions import Self

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Label = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.+ -]+$")]
Seconds = Annotated[int, Field(ge=0, le=31_536_000)]
Category = Literal[
    "installation", "comprehension", "semantics", "integration", "performance", "evidence"
]
MAX_BYTES = 1_048_576


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class Outcome(Record):
    state: Literal["equivalent", "different", "not_evaluable"]
    complete: bool
    accepted: bool

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.accepted and (self.state != "equivalent" or not self.complete):
            raise ValueError("accepted requires complete equivalent")
        if self.state == "equivalent" and not self.complete:
            raise ValueError("equivalent cannot be incomplete")
        return self


class Issue(Record):
    id: Identifier
    category: Category
    priority: Literal["P0", "P1", "P2", "P3"]
    false_equivalent: bool
    reproducer_sha256: Digest
    expected_sha256: Digest
    observed_sha256: Digest
    data_permission: Literal["synthetic_only", "explicitly_permitted"]
    status: Literal["open", "fix_proposed", "regression_verified", "consumer_confirmed"]
    regression_sha256: Digest | None
    consumer_confirmation_sha256: Digest | None
    support_seconds: Seconds | None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.false_equivalent and (self.priority != "P0" or self.category != "semantics"):
            raise ValueError("false equivalent requires critical semantic incident")
        fixed = self.status in {"regression_verified", "consumer_confirmed"}
        if fixed != (self.regression_sha256 is not None):
            raise ValueError("verified fix requires regression evidence")
        confirmed = self.status == "consumer_confirmed"
        if confirmed != (self.consumer_confirmation_sha256 is not None):
            raise ValueError("consumer confirmation must have its own evidence")
        return self


class Attempt(Record):
    id: Identifier
    phase: Literal["initial", "follow_up"]
    occurred_at: datetime
    change_sha256: Digest
    package_version: Label
    wheel_sha256: Digest
    dependency_lock_sha256: Digest
    contract_sha256: Digest | None
    contract_review_sha256: Digest | None
    python: Label
    os: Label
    architecture: Label
    engines: dict[Identifier, Label] = Field(max_length=12)
    installation_seconds: Seconds | None
    integration_seconds: Seconds | None
    diagnosis_seconds: Seconds | None
    help_received: Literal["none", "documentation", "assisted", "unknown"]
    expected: Outcome | None
    observed: Outcome | None
    usefulness: Literal["useful", "blocked", "not_assessed"]
    integration_retained: bool
    knows_reporting: bool | None
    knows_upgrading: bool | None
    evidence_sha256: Digest
    issues: tuple[Issue, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("observation time requires timezone")
        if (self.expected is None) != (self.observed is None):
            raise ValueError("expected and observed must be recorded together")
        if self.observed is not None and self.contract_sha256 is None:
            raise ValueError("comparison observation requires a contract identity")
        if self.usefulness == "useful" and self.observed is None:
            raise ValueError("useful comparison requires an observed outcome")
        if self.integration_retained and self.phase != "follow_up":
            raise ValueError("initial integration cannot establish retained use")
        if len({issue.id for issue in self.issues}) != len(self.issues):
            raise ValueError("duplicate issue ID in one observation")
        return self


class Pilot(Record):
    id: Identifier
    project_id: Identifier
    context: Literal["refactor_python", "sql_duckdb", "ci_regression"]
    kind: Literal["human_pilot", "synthetic_replay"]
    independent: bool
    consent: Literal["recorded", "not_recorded", "synthetic_only"]
    consent_sha256: Digest | None
    attempts: tuple[Attempt, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.kind == "synthetic_replay":
            if self.independent or self.consent != "synthetic_only" or self.consent_sha256:
                raise ValueError("synthetic replay must not claim independent human consent")
            if any(
                issue.status == "consumer_confirmed" for a in self.attempts for issue in a.issues
            ):
                raise ValueError("technical replay cannot confirm an affected human consumer")
        else:
            if self.consent == "synthetic_only":
                raise ValueError("human consent cannot be synthetic")
            if (self.consent == "recorded") != (self.consent_sha256 is not None):
                raise ValueError("recorded consent needs a separately held receipt identity")
            if self.attempts and self.consent != "recorded":
                raise ValueError("do not collect human attempts without recorded consent")
        seen = set()
        previous = None
        for attempt in self.attempts:
            if attempt.id in seen:
                raise ValueError("duplicate attempt ID")
            seen.add(attempt.id)
            if previous is None:
                if attempt.phase != "initial" or attempt.contract_review_sha256 is not None:
                    raise ValueError("first attempt must be initial without a change review")
            else:
                if attempt.occurred_at <= previous.occurred_at:
                    raise ValueError("attempts require strictly increasing observation times")
                if attempt.phase != "follow_up":
                    raise ValueError("later attempts must be follow_up")
                changed = attempt.contract_sha256 != previous.contract_sha256
                if changed and previous.contract_sha256 is not None:
                    if attempt.contract_review_sha256 is None:
                        raise ValueError("changed contract requires explicit review evidence")
                elif attempt.contract_review_sha256 is not None:
                    raise ValueError(
                        "unchanged or first established contract needs no change review"
                    )
            previous = attempt
        return self


class Registry(Record):
    schema_version: Literal["equiframe-adoption-1"] = Field(alias="schema")
    pilots: tuple[Pilot, ...] = Field(max_length=1000)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({pilot.id for pilot in self.pilots}) != len(self.pilots):
            raise ValueError("duplicate pilot ID")
        histories = {(pilot.project_id, pilot.context) for pilot in self.pilots}
        if len(histories) != len(self.pilots):
            raise ValueError("one chronological history is required per project/context")
        return self


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON member")
        result[name] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError("nonfinite JSON token")


def read_registry(path: Path) -> Registry:
    """Parse bounded, regular local input. No external references are resolved."""
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > MAX_BYTES:
        raise ValueError("registry must be a regular file at most 1 MiB")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("registry exceeds size limit")
    # Pydantic's JSON mode intentionally admits datetime/tuple JSON encodings;
    # preparse rejects duplicate members and JSON extensions before validation.
    json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    return Registry.model_validate_json(raw)


def summarize(registry: Registry) -> dict[str, Any]:
    """Count supplied records, preserving unknowns and separating simulations."""
    humans = [pilot for pilot in registry.pilots if pilot.kind == "human_pilot"]
    observed = [pilot for pilot in humans if pilot.attempts]
    independent = [pilot for pilot in observed if pilot.independent]
    retained = []
    for pilot in independent:
        last = pilot.attempts[-1]
        baselines = [
            (index, attempt)
            for index, attempt in enumerate(pilot.attempts)
            if attempt.observed is not None
            and attempt.observed.complete
            and attempt.observed.state != "not_evaluable"
            and attempt.usefulness == "useful"
            and attempt.expected == attempt.observed
        ]
        if not baselines:
            continue
        baseline_index, first = baselines[0]
        latest_issues = {issue.id: issue for a in pilot.attempts for issue in a.issues}
        critical_ids = {
            issue.id
            for a in pilot.attempts
            for issue in a.issues
            if issue.priority == "P0" or issue.false_equivalent
        }
        unresolved_critical = any(
            latest_issues[issue_id].status != "consumer_confirmed" for issue_id in critical_ids
        )
        if (
            baseline_index < len(pilot.attempts) - 1
            and not unresolved_critical
            and last.change_sha256 != first.change_sha256
            and last.integration_retained
            and last.usefulness == "useful"
            and last.knows_reporting is True
            and last.knows_upgrading is True
            and last.expected == last.observed
        ):
            retained.append(pilot)
    attempts = [attempt for pilot in humans for attempt in pilot.attempts]
    measured = [a.integration_seconds for a in attempts if a.integration_seconds is not None]
    issues = [issue for attempt in attempts for issue in attempt.issues]
    support = [issue.support_seconds for issue in issues if issue.support_seconds is not None]
    contexts = {pilot.context for pilot in retained}
    return {
        "schema": "equiframe-adoption-summary-1",
        "scope": "record consistency only; no consent, identity or semantic authentication",
        "human_adoption_verified": False,
        "manual_acceptance": "pending_independent_evidence_review",
        "human_pilot_records": len(humans),
        "human_projects_with_observations": len({pilot.project_id for pilot in observed}),
        "independent_project_attestations": len({pilot.project_id for pilot in independent}),
        "retained_project_attestations": len({pilot.project_id for pilot in retained}),
        "retained_context_attestations": sorted(contexts),
        "proposed_diversity_target_recorded": len({p.project_id for p in retained}) >= 3
        and len(contexts) == 3,
        "synthetic_replay_records": sum(p.kind == "synthetic_replay" for p in registry.pilots),
        "human_attempts": len(attempts),
        "recorded_outcomes": {
            state: sum(a.observed is not None and a.observed.state == state for a in attempts)
            for state in ("equivalent", "different", "not_evaluable")
        },
        "human_issue_observations_by_category": {
            category: sum(i.category == category for i in issues)
            for category in (
                "installation",
                "comprehension",
                "semantics",
                "integration",
                "performance",
                "evidence",
            )
        },
        "support_seconds_measured_issue_observations": len(support),
        "support_seconds_total": sum(support) if support else None,
        "support_seconds_unknown_issue_observations": len(issues) - len(support),
        "false_equivalent_issue_observations": sum(i.false_equivalent for i in issues),
        "consumer_confirmed_issue_observations": sum(
            i.status == "consumer_confirmed" for i in issues
        ),
        "integration_seconds_measured_attempts": len(measured),
        "integration_seconds_total": sum(measured) if measured else None,
        "integration_seconds_unknown_attempts": len(attempts) - len(measured),
        "five_minute_human_acceptance": "not_established_by_this_tool",
        "owner_assignments": "outside_record_check_requires_explicit_approval",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path, nargs="?")
    parser.add_argument("--schema", action="store_true", help="print this tool-only JSON Schema")
    args = parser.parse_args()
    if args.schema:
        if args.registry is not None:
            parser.error("use either --schema or a registry")
        print(json.dumps(Registry.model_json_schema(), indent=2, sort_keys=True))
        return 0
    if args.registry is None:
        parser.error("provide a registry or --schema")
    try:
        report = summarize(read_registry(args.registry))
    except (OSError, UnicodeError, ValueError, ValidationError, RecursionError):
        # Do not echo private values, paths, fields or raw validation errors.
        print("Adoption record invalid or unreadable; no acceptance established")
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
