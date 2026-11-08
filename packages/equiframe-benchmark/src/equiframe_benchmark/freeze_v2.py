"""V2 seals bind the paired principal protocol; V1 seals remain unchanged."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal, cast

import equiframe as ef
from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe_benchmark import freeze as legacy
from equiframe_benchmark.costs import CostProtocol
from equiframe_benchmark.evaluation_v2 import (
    PRIMARY_FAMILIES as FAMILIES,
)
from equiframe_benchmark.evaluation_v2 import (
    EvaluationConfigV2 as EvaluationConfig,
)
from equiframe_benchmark.evaluation_v2 import (
    evaluation_protocol_sha256_v2 as evaluation_protocol_sha256,
)
from equiframe_benchmark.freeze import (
    DECISIONS,
    EnvironmentPin,
    ExperimentalDecision,
    FreezeAudit,
    FreezeCount,
    FrozenFamilyModel,
    FrozenInput,
    ModelBinding,
    SelectionEvidence,
    TestCaseDefinition,
    _environment,
    _PhysicalEvidence,
    _verify_oracle,
    _verify_selection_evidence,
)
from equiframe_benchmark.models import (
    Candidate,
    Catalog,
    Digest,
    Partition,
    Scenario,
    SplitManifest,
    Text,
    digest,
)
from equiframe_benchmark.models_v2 import DocumentV2 as Document
from equiframe_benchmark.oracle import validate_candidate
from equiframe_benchmark.reproduction import _bounded_json, _plain_path, _stream_file
from equiframe_benchmark.splits import validate_splits

_PARTITIONS: tuple[Partition, ...] = ("training", "calibration", "test")


class ProtocolReviewV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    status: Literal["pending", "approved"]
    protocol_sha256: Digest | None
    reviewer: Text | None
    rationale: Text

    @model_validator(mode="after")
    def binding(self) -> Self:
        if self.status == "approved":
            if self.protocol_sha256 is None or self.reviewer is None:
                raise ValueError("protocol approval requires an exact fingerprint and reviewer")
        elif self.protocol_sha256 is not None or self.reviewer is not None:
            raise ValueError("pending review cannot claim approval metadata")
        return self


class FreezeDefinitionV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    protocol_review: ProtocolReviewV2
    study_id: Text
    revision: Annotated[int, Field(gt=0)]
    mode: Literal["pilot", "final"]
    catalog: Catalog
    splits: SplitManifest
    cases: tuple[TestCaseDefinition, ...]
    models: tuple[FrozenFamilyModel, ...]
    selection_evidence: tuple[SelectionEvidence, ...]
    decisions: tuple[ExperimentalDecision, ...]
    files: tuple[FrozenInput, ...]
    environment: tuple[EnvironmentPin, ...]
    code_revision: Text
    evaluation: EvaluationConfig
    cost_protocol: CostProtocol

    @model_validator(mode="after")
    def metadata(self) -> Self:
        if tuple(m.family for m in self.models) != FAMILIES:
            raise ValueError("freeze requires the three primary families in canonical order")
        if {d.name for d in self.decisions} != set(DECISIONS) or len(self.decisions) != len(
            DECISIONS
        ):
            raise ValueError("freeze requires the twelve explicit experimental decisions")
        if self.evaluation.mode != "pilot" or self.evaluation.freeze_sha256 is not None:
            raise ValueError(
                "pre-freeze evaluation protocol must not contain a circular freeze hash"
            )
        for values in (
            [c.case_id for c in self.cases],
            [e.candidate.candidate_id for e in self.selection_evidence],
            [f.name for f in self.files],
            [p.package for p in self.environment],
        ):
            if len(values) != len(set(values)):
                raise ValueError(
                    "freeze case, evidence, input and environment names must be unique"
                )
        if self.protocol_review.status == "approved" and (
            self.protocol_review.protocol_sha256 != evaluation_protocol_sha256(self.evaluation)
        ):
            raise ValueError("protocol review must bind this exact V2 protocol")
        _evaluation_scope(self)
        locations: dict[str, tuple[str, int]] = {}
        for item in self.files:
            location = str(Path(item.path)).casefold()
            identity = (item.sha256, item.size_bytes)
            if location in locations and locations[location] != identity:
                raise ValueError("one frozen path cannot declare different contents")
            locations[location] = identity
        return self


def _counts(definition: FreezeDefinitionV2) -> tuple[FreezeCount, ...]:
    partitions = {a.scenario_id: a.partition for a in definition.splits.assignments}
    scenarios = {s.scenario_id: s for s in definition.catalog.scenarios}
    result = []
    for family in FAMILIES:
        for partition in _PARTITIONS:
            selected = {
                s.scenario_id
                for s in scenarios.values()
                if s.family == family and partitions.get(s.scenario_id) == partition
            }
            cases = [c for c in definition.cases if c.scenario_id in selected]
            states = [c.oracle.status if c.oracle is not None else "pending" for c in cases]
            result.append(
                FreezeCount(
                    family=family,
                    partition=partition,
                    scenarios=len(selected),
                    cases=len(cases),
                    confirmed=states.count("confirmed"),
                    pending=states.count("pending"),
                    disagreement=states.count("disagreement"),
                    not_evaluable=states.count("not_evaluable"),
                )
            )
    return tuple(result)


def _evaluation_scope(definition: FreezeDefinitionV2) -> None:
    families = {scenario.family for scenario in definition.catalog.scenarios} | {
        case.pipeline.execution.contract.family for case in definition.cases
    }
    if not families <= set(definition.evaluation.expected_families):
        raise ValueError("V2 cases and catalog must use the three primary families")
    for case in definition.cases:
        if (
            case.migration not in definition.evaluation.expected_migrations
            or case.pipeline.execution.engine not in case.migration.split("-")
        ):
            raise ValueError("V2 case must bind one declared engine pair and its native engine")


def _bindings(definition: FreezeDefinitionV2) -> tuple[ModelBinding, ...]:
    # Shared helpers read common metadata; no V1 document is constructed.
    return legacy._bindings(cast(legacy.FreezeDefinition, definition))


def _verify_model(model: FrozenFamilyModel, definition: FreezeDefinitionV2) -> None:
    legacy._verify_model(model, cast(legacy.FreezeDefinition, definition))


def _scientific_blockers(definition: FreezeDefinitionV2) -> list[str]:
    blockers = legacy._scientific_blockers(cast(legacy.FreezeDefinition, definition))
    if definition.protocol_review.status != "approved":
        blockers.append("scientific:pending_paired_protocol_review_v2")
    for family in definition.evaluation.expected_families:
        for migration in definition.evaluation.expected_migrations:
            if not any(
                case.pipeline.execution.contract.family == family and case.migration == migration
                for case in definition.cases
            ):
                blockers.append(f"scientific:empty_primary_stratum:{family}:{migration}")
    return blockers


class FreezeManifestV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    definition: FreezeDefinitionV2
    definition_sha256: Digest
    evaluation_protocol_sha256: Digest
    cost_protocol_sha256: Digest
    catalog_sha256: Digest
    splits_sha256: Digest
    model_bindings: tuple[ModelBinding, ...]
    audit: FreezeAudit

    @model_validator(mode="after")
    def closed(self) -> Self:
        _evaluation_scope(self.definition)
        expected = (
            digest(self.definition),
            evaluation_protocol_sha256(self.definition.evaluation),
            digest(self.definition.cost_protocol),
            digest(self.definition.catalog),
            digest(self.definition.splits),
            _bindings(self.definition),
        )
        actual = (
            self.definition_sha256,
            self.evaluation_protocol_sha256,
            self.cost_protocol_sha256,
            self.catalog_sha256,
            self.splits_sha256,
            self.model_bindings,
        )
        if actual != expected or self.audit.definition_sha256 != self.definition_sha256:
            raise ValueError("freeze fingerprints and model bindings must close exactly")
        if self.audit.counts != _counts(self.definition):
            raise ValueError("freeze counts must describe the actual definitions")
        expected_blockers = tuple(sorted(set(_scientific_blockers(self.definition))))
        if self.audit.blockers != expected_blockers:
            raise ValueError("published freeze blockers must describe its exact configuration")
        ready = (
            self.audit.technical_ready
            if self.definition.mode == "pilot"
            else self.audit.scientific_ready
        )
        if self.audit.ready != ready or not ready:
            raise ValueError("published freeze must satisfy its explicit pilot/final gate")
        return self


def audit_freeze_v2(
    definition: FreezeDefinitionV2,
    *,
    rule_registry: ef.RuleRegistry | None = None,
    work_dir: Path | None = None,
) -> FreezeAudit:
    """Check actual evidence and support without executing ETL or fitting models.

    Verification creates disposable comparison/profile evidence in a private folder.
    Unconfirmed cases remain unconfirmed; reviewer identities are not authenticated.
    """
    definition = FreezeDefinitionV2.model_validate(definition)
    integrity: list[str] = []
    evidence = _PhysicalEvidence()

    def check(name: str, action: Callable[[], None]) -> None:
        try:
            action()
        except (ValueError, OSError, ef.EquiFrameError) as exc:
            integrity.append("integrity:" + name + ":" + type(exc).__name__)

    check("splits", lambda: validate_splits(definition.catalog, definition.splits))
    check("evaluation_scope", partial(_evaluation_scope, definition))
    for frozen_file in definition.files:
        check(
            "input:" + frozen_file.name,
            partial(evidence.frozen_input, frozen_file),
        )
    for pin in definition.environment:
        check("environment:" + pin.package, partial(_environment, pin))
    registry = rule_registry if rule_registry is not None else ef.default_rule_registry()
    if work_dir is not None:
        _plain_path(work_dir, directory=True)
    with TemporaryDirectory(prefix="equiframe-freeze-", dir=work_dir) as scratch:
        verification = Path(scratch)
        scenarios = {s.scenario_id: s for s in definition.catalog.scenarios}
        hashes = {digest(s): s for s in definition.catalog.scenarios}
        assignments = {a.scenario_id: a for a in definition.splits.assignments}
        models = {m.family: m for m in definition.models}
        known_candidates: dict[str, Candidate] = {}
        for scenario in definition.catalog.scenarios:

            def verify_scenario(scenario: Scenario = scenario) -> None:
                for ref in (*[i.artifact for i in scenario.inputs], scenario.expected):
                    evidence.artifact(ref)
                if scenario.features_sha256 != ef.profile_spec_fingerprint(
                    models[scenario.family].profile
                ):
                    raise ValueError("scenario features differ from frozen family")
                options = (
                    ef.RuleOptions(),
                    *(
                        c.pipeline.rule_options
                        for c in definition.cases
                        if c.pipeline.execution.contract.family == scenario.family
                    ),
                )
                if not any(
                    ef.rule_set_fingerprint(scenario.comparison.contract, registry, option)
                    == scenario.rules_sha256
                    for option in options
                ):
                    raise ValueError(
                        "scenario rules differ from frozen registry and declared options"
                    )

            check("scenario:" + scenario.scenario_id, verify_scenario)
        for case in definition.cases:

            def verify_case(case: TestCaseDefinition = case) -> None:
                scenario = scenarios.get(case.scenario_id)
                assignment = assignments.get(case.scenario_id)
                if scenario is None or assignment is None or assignment.partition != "test":
                    raise ValueError("only declared held-out test scenarios may become cases")
                validate_candidate(scenario, case.candidate)
                prior = known_candidates.get(case.candidate.candidate_id)
                if prior is not None and prior != case.candidate:
                    raise ValueError("one candidate ID cannot bind different evidence")
                known_candidates[case.candidate.candidate_id] = case.candidate
                evidence.artifact(case.candidate.output)
                if (
                    case.pipeline.execution.contract != scenario.comparison.contract
                    or case.pipeline.comparison_policy != scenario.comparison.policy
                ):
                    raise ValueError("case contract or comparison policy differs from scenario")
                if case.pipeline.profile != models[scenario.family].profile:
                    raise ValueError("case feature definition differs from frozen family")
                actual_rules = ef.rule_set_fingerprint(
                    scenario.comparison.contract, registry, case.pipeline.rule_options
                )
                if actual_rules != scenario.rules_sha256:
                    raise ValueError(
                        "case rule options differ from the rules fixed before its candidate"
                    )
                if case.pipeline.comparison_reference != "expected":
                    raise ValueError("experimental cases require independent expected reference")
                if case.oracle is not None:
                    _verify_oracle(scenario, case.candidate, case.oracle, evidence, verification)

            check("case:" + case.case_id, verify_case)
        for item in definition.selection_evidence:

            def verify_item(item: SelectionEvidence = item) -> None:
                scenario = hashes.get(item.candidate.scenario_sha256)
                if scenario is None:
                    raise ValueError("selection candidate refers to an unknown scenario")
                prior = known_candidates.get(item.candidate.candidate_id)
                if prior is not None and prior != item.candidate:
                    raise ValueError("one candidate ID cannot bind different evidence")
                known_candidates[item.candidate.candidate_id] = item.candidate
                _verify_selection_evidence(item, scenario, evidence, verification)

            check("selection:" + item.candidate.candidate_id, verify_item)
        for model in definition.models:
            check("model:" + model.family, partial(_verify_model, model, definition))
        check("sources_unchanged", evidence.recheck)
    blockers = tuple(sorted(set((*_scientific_blockers(definition), *integrity))))
    return FreezeAudit(
        definition_sha256=digest(definition),
        ready=not integrity if definition.mode == "pilot" else not blockers,
        blockers=blockers,
        integrity_blockers=tuple(sorted(set(integrity))),
        counts=_counts(definition),
    )


def create_freeze_v2(
    definition: FreezeDefinitionV2,
    *,
    rule_registry: ef.RuleRegistry | None = None,
    work_dir: Path | None = None,
) -> FreezeManifestV2:
    """Return a closed seal only after its explicit technical/scientific gate passes."""
    definition = FreezeDefinitionV2.model_validate(definition)
    audit = audit_freeze_v2(definition, rule_registry=rule_registry, work_dir=work_dir)
    if not audit.ready:
        raise ValueError("freeze is blocked: " + "; ".join(audit.blockers))
    return FreezeManifestV2(
        definition=definition,
        definition_sha256=digest(definition),
        evaluation_protocol_sha256=evaluation_protocol_sha256(definition.evaluation),
        cost_protocol_sha256=digest(definition.cost_protocol),
        catalog_sha256=digest(definition.catalog),
        splits_sha256=digest(definition.splits),
        model_bindings=_bindings(definition),
        audit=audit,
    )


def read_freeze_v2(
    path: Path,
    *,
    expected_sha256: str | None = None,
    rule_registry: ef.RuleRegistry | None = None,
    work_dir: Path | None = None,
    max_bytes: int = 64 * 1024**2,
) -> FreezeManifestV2:
    """Recheck a seal, its physical sources and exact audit; never execute stored code."""
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("freeze JSON byte budget must be a positive integer")
    manifest, checksum = _bounded_json(FreezeManifestV2, path, max_bytes)
    if expected_sha256 is not None and checksum != expected_sha256:
        raise ValueError("freeze document SHA-256 mismatch")
    observed = audit_freeze_v2(manifest.definition, rule_registry=rule_registry, work_dir=work_dir)
    if _stream_file(path, max_bytes)[0] != checksum:
        raise ValueError("freeze document changed during verification")
    if observed != manifest.audit or not observed.ready:
        raise ValueError("freeze verification no longer matches its sealed audit")
    return manifest
