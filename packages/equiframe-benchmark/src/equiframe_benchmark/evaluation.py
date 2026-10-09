"""Pure, paired evaluation of evidence verified by the experimental producer.

This module neither trains detectors nor authenticates review identities. A final
hash binding records the producer's intent, not independent scientific approval.
All intervals resample whole dependency groups and estimate execution aggregates.
"""

import hashlib
import json
import random
import re
from collections import defaultdict
from fractions import Fraction
from math import ceil
from typing import Annotated, Literal

from equiframe import ComponentDecision, Family
from equiframe.detector_types import ScoreValue, numeric_score
from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text, digest

Method = Literal["R", "M", "B", "H"]
Engine = Literal["pandas", "polars", "duckdb"]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
METHODS: tuple[Method, ...] = ("R", "M", "B", "H")
SCORE_METHODS: tuple[Literal["M", "B"], ...] = ("M", "B")
FAMILIES: tuple[Family, ...] = ("nulls_types", "joins", "duplicates_order", "aggregations", "dates")


class EvaluationRecord(Document):
    """One unique native execution; migration is declared, never guessed from IDs."""

    case_id: Text
    scenario_id: Text
    group_id: Text
    family: Family
    migration: Text
    engine: Engine
    candidate_sha256: Digest
    pipeline_sha256: Digest | None
    oracle_sha256: Digest | None
    oracle_state: Literal["pending", "disagreement", "confirmed", "not_evaluable"]
    oracle_label: Literal["normal", "divergent"] | None
    r: ComponentDecision
    m: ComponentDecision
    b: ComponentDecision
    h: ComponentDecision
    m_score: Annotated[float, Field(gt=0, le=1)] | None
    b_score: ScoreValue | None
    detector_bundle_sha256: Digest | None
    freeze_sha256: Digest | None
    failure_reason: Text | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        confirmed = self.oracle_state == "confirmed"
        if confirmed != (self.oracle_label is not None):
            raise ValueError("only a confirmed independent label can enter evaluation")
        if confirmed and self.oracle_sha256 is None:
            raise ValueError("confirmed labels require their evidence fingerprint")
        for decision, score in ((self.m, self.m_score), (self.b, self.b_score)):
            if decision.complete and (score is None or self.detector_bundle_sha256 is None):
                raise ValueError("complete statistical decisions require score and bundle")
            if not decision.complete and decision.decision != "not_evaluable":
                raise ValueError("uncalibrated statistical components cannot claim alerts")
        if (self.m_score is not None or self.b_score is not None) and (
            self.detector_bundle_sha256 is None
        ):
            raise ValueError("scores require their model bundle provenance")
        decisions = (self.r.decision, self.m.decision)
        expected = (
            "alert"
            if "alert" in decisions
            else "no_alert"
            if decisions == ("no_alert", "no_alert")
            else "not_evaluable"
        )
        if self.h.decision != expected or self.h.complete != (self.r.complete and self.m.complete):
            raise ValueError("H must preserve the OR and availability of R and M")
        if self.pipeline_sha256 is None:
            if self.failure_reason is None or any(_component(self, m).complete for m in METHODS):
                raise ValueError("a missing pipeline is an explicit unavailable execution")
            if self.m_score is not None or self.b_score is not None:
                raise ValueError("a missing pipeline cannot contain invented scores")
        return self


class BootstrapPlan(Document):
    """Explicit support justification; a group count alone never proves independence."""

    seed: Annotated[int, Field(ge=0, le=2**32 - 1)]
    repetitions: PositiveInt = 2000
    confidence: Text = "0.95"
    min_groups: PositiveInt
    independence_supported: bool
    rationale: Text

    @model_validator(mode="after")
    def probability(self) -> Self:
        if not re.fullmatch(r"0\.[0-9]{1,18}", self.confidence):
            raise ValueError("confidence must be an explicit decimal probability")
        if not 0 < Fraction(self.confidence) < 1:
            raise ValueError("confidence must lie strictly between zero and one")
        return self


class EvaluationConfig(Document):
    mode: Literal["pilot", "final"]
    freeze_sha256: Digest | None
    bootstrap: BootstrapPlan
    expected_families: Annotated[tuple[Family, ...], Field(min_length=1)] = FAMILIES
    expected_migrations: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def binding(self) -> Self:
        if (self.mode == "final") != (self.freeze_sha256 is not None):
            raise ValueError("final evaluation requires a freeze; pilot has no final binding")
        for scopes in (self.expected_families, self.expected_migrations):
            if len(scopes) != len(set(scopes)):
                raise ValueError("declared evaluation scopes must be unique")
        return self


def evaluation_protocol_sha256(config: EvaluationConfig) -> str:
    """Noncircular fingerprint to fix inside a freeze before its digest exists."""
    config = EvaluationConfig.model_validate(config)
    payload = {
        "schema_version": "1.0",
        "bootstrap": config.bootstrap.model_dump(mode="json"),
        "expected_families": config.expected_families,
        "expected_migrations": config.expected_migrations,
        "principal": "confirmed_label_and_complete_R_M_B_H",
        "average_precision": "tied_thresholds_two_classes_homogeneous_family_and_bundle",
        "interval": "whole_groups_execution_aggregate_nearest_ceil_no_undefined_omission",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class MetricValue(Document):
    """Exact rational estimate, or an explicit undefined denominator/reason."""

    numerator: NonNegativeInt
    denominator: NonNegativeInt
    value: float | None
    reason: Text | None

    @model_validator(mode="after")
    def arithmetic(self) -> Self:
        if self.denominator == 0:
            if self.numerator or self.value is not None or self.reason is None:
                raise ValueError("undefined metrics require zero counts and an explicit reason")
        elif self.reason is not None or self.value != float(
            Fraction(self.numerator, self.denominator)
        ):
            raise ValueError("metric value must equal its exact numerator/denominator")
        return self


class ConfusionMetrics(Document):
    tp: NonNegativeInt
    fp: NonNegativeInt
    fn: NonNegativeInt
    tn: NonNegativeInt
    precision: MetricValue
    recall: MetricValue
    f1: MetricValue
    false_positive_rate: MetricValue


class MethodEvaluation(Document):
    method: Method
    complete_case_ids: tuple[Text, ...]
    own_case_ids: tuple[Text, ...]
    partial_alert_case_ids: tuple[Text, ...]
    unavailable_case_ids: tuple[Text, ...]
    coverage: MetricValue
    principal: ConfusionMetrics
    own_support: ConfusionMetrics


class AveragePrecisionEvaluation(Document):
    method: Literal["M", "B"]
    principal_case_ids: tuple[Text, ...]
    own_case_ids: tuple[Text, ...]
    principal: MetricValue
    own_support: MetricValue


class IncrementalEvaluation(Document):
    additional_true_positive_case_ids: tuple[Text, ...]
    additional_false_positive_case_ids: tuple[Text, ...]
    additional_true_positive_rate: MetricValue
    additional_false_positive_rate: MetricValue


class CoverageSummary(Document):
    total_cases: NonNegativeInt
    oracle_confirmed: NonNegativeInt
    oracle_pending: NonNegativeInt
    oracle_disagreement: NonNegativeInt
    oracle_not_evaluable: NonNegativeInt
    failed_case_ids: tuple[Text, ...]
    principal_case_ids: tuple[Text, ...]
    excluded_case_ids: tuple[Text, ...]
    principal_coverage: MetricValue


class IntervalEstimate(Document):
    metric: Text
    lower: float | None
    upper: float | None
    defined_replicates: NonNegativeInt
    undefined_replicates: NonNegativeInt
    reason: Text | None


class GroupBootstrapResult(Document):
    group_ids: tuple[Text, ...]
    attempted_replicates: NonNegativeInt
    lower_rank: PositiveInt | None
    upper_rank: PositiveInt | None
    intervals: tuple[IntervalEstimate, ...]


class EvaluationStratum(Document):
    kind: Literal["global", "family", "migration", "family_migration"]
    family: Family | None
    migration: Text | None
    coverage: CoverageSummary
    methods: tuple[MethodEvaluation, ...]
    average_precision: tuple[AveragePrecisionEvaluation, ...]
    incremental: IncrementalEvaluation
    bootstrap: GroupBootstrapResult


class EvaluationReport(Document):
    """Self-contained derived report, recalculated on every model/JSON validation."""

    scientific: bool
    config_sha256: Digest
    protocol_sha256: Digest
    records_sha256: Digest
    config: EvaluationConfig
    records: tuple[EvaluationRecord, ...]
    strata: tuple[EvaluationStratum, ...]

    @model_validator(mode="after")
    def recalculate(self) -> Self:
        _validate_inputs(self.records, self.config)
        if self.records != tuple(sorted(self.records, key=lambda r: r.case_id)):
            raise ValueError("report records require canonical case order")
        if (
            self.scientific != (self.config.mode == "final")
            or self.config_sha256 != digest(self.config)
            or self.protocol_sha256 != evaluation_protocol_sha256(self.config)
            or self.records_sha256 != _records_digest(self.records)
            or self.strata != _strata(self.records, self.config)
        ):
            raise ValueError("report disagrees with its bound records, protocol or calculations")
        return self


def _component(record: EvaluationRecord, method: Method) -> ComponentDecision:
    return {"R": record.r, "M": record.m, "B": record.b, "H": record.h}[method]


def _confirmed(record: EvaluationRecord) -> bool:
    return record.oracle_state == "confirmed"


def _principal(record: EvaluationRecord) -> bool:
    return _confirmed(record) and all(_component(record, method).complete for method in METHODS)


def _ratio(numerator: int, denominator: int, reason: str = "zero_denominator") -> MetricValue:
    return MetricValue(
        numerator=numerator if denominator else 0,
        denominator=denominator,
        value=float(Fraction(numerator, denominator)) if denominator else None,
        reason=None if denominator else reason,
    )


def _confusion(records: tuple[EvaluationRecord, ...], method: Method) -> ConfusionMetrics:
    tp = fp = fn = tn = 0
    for record in records:
        positive = record.oracle_label == "divergent"
        alert = _component(record, method).decision == "alert"
        tp += positive and alert
        fp += not positive and alert
        fn += positive and not alert
        tn += not positive and not alert
    return ConfusionMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        f1=_ratio(2 * tp, 2 * tp + fp + fn),
        false_positive_rate=_ratio(fp, fp + tn),
    )


def _ap(records: tuple[EvaluationRecord, ...], method: Literal["M", "B"]) -> MetricValue:
    if not records:
        return _ratio(0, 0, "no_score_support")
    if (
        len({r.family for r in records}) != 1
        or len({r.detector_bundle_sha256 for r in records}) != 1
    ):
        return _ratio(0, 0, "not_defined_heterogeneous_model_scores")
    positives = sum(r.oracle_label == "divergent" for r in records)
    if positives in (0, len(records)):
        return _ratio(0, 0, "average_precision_requires_two_classes")
    thresholds: dict[float, list[int]] = defaultdict(lambda: [0, 0])
    for record in records:
        score = record.m_score if method == "M" else record.b_score
        if score is None:
            raise ValueError("average precision support contains a missing score")
        bucket = thresholds[numeric_score(score)]
        bucket[0] += record.oracle_label == "divergent"
        bucket[1] += 1
    accumulated_positive = accumulated_total = 0
    result = Fraction(0)
    for threshold in sorted(thresholds, reverse=True):
        positive, total = thresholds[threshold]
        accumulated_positive += positive
        accumulated_total += total
        result += Fraction(positive, positives) * Fraction(accumulated_positive, accumulated_total)
    return _ratio(result.numerator, result.denominator)


def _incremental(records: tuple[EvaluationRecord, ...]) -> IncrementalEvaluation:
    additional = tuple(r for r in records if r.h.decision == "alert" and r.r.decision == "no_alert")
    true = tuple(r.case_id for r in additional if r.oracle_label == "divergent")
    false = tuple(r.case_id for r in additional if r.oracle_label == "normal")
    positives = sum(r.oracle_label == "divergent" for r in records)
    return IncrementalEvaluation(
        additional_true_positive_case_ids=true,
        additional_false_positive_case_ids=false,
        additional_true_positive_rate=_ratio(len(true), positives),
        additional_false_positive_rate=_ratio(len(false), len(records) - positives),
    )


def _estimates(records: tuple[EvaluationRecord, ...]) -> dict[str, MetricValue]:
    estimates: dict[str, MetricValue] = {}
    for method in METHODS:
        metrics = _confusion(records, method)
        for name in ("precision", "recall", "f1", "false_positive_rate"):
            estimates[f"{method}.{name}"] = getattr(metrics, name)
    estimates["M.average_precision"] = _ap(records, "M")
    estimates["B.average_precision"] = _ap(records, "B")
    incremental = _incremental(records)
    estimates["H1.additional_true_positive_rate"] = incremental.additional_true_positive_rate
    estimates["H2.additional_false_positive_rate"] = incremental.additional_false_positive_rate
    return estimates


def _bootstrap(records: tuple[EvaluationRecord, ...], plan: BootstrapPlan) -> GroupBootstrapResult:
    groups: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for record in records:
        groups[record.group_id].append(record)
    group_ids = tuple(sorted(groups))
    points = _estimates(records)
    reason = (
        "independence_not_supported"
        if not plan.independence_supported
        else "insufficient_groups"
        if len(group_ids) < plan.min_groups
        else None
    )
    if reason is not None:
        return GroupBootstrapResult(
            group_ids=group_ids,
            attempted_replicates=0,
            lower_rank=None,
            upper_rank=None,
            intervals=tuple(
                IntervalEstimate(
                    metric=name,
                    lower=None,
                    upper=None,
                    defined_replicates=0,
                    undefined_replicates=0,
                    reason=reason,
                )
                for name in points
            ),
        )
    samples: dict[str, list[Fraction]] = {name: [] for name in points}
    undefined = dict.fromkeys(points, 0)
    rng = random.Random(plan.seed)
    for _ in range(plan.repetitions):
        sampled = tuple(
            record for _ in group_ids for record in groups[group_ids[rng.randrange(len(group_ids))]]
        )
        for name, value in _estimates(sampled).items():
            if value.value is None:
                undefined[name] += 1
            else:
                samples[name].append(Fraction(value.numerator, value.denominator))
    tail = (1 - Fraction(plan.confidence)) / 2
    lower_rank = max(1, ceil(tail * plan.repetitions))
    upper_rank = ceil((1 - tail) * plan.repetitions)
    intervals: list[IntervalEstimate] = []
    for name, point in points.items():
        values = sorted(samples[name])
        failure = (
            point.reason
            if point.value is None
            else "undefined_bootstrap_replicates"
            if undefined[name]
            else None
        )
        intervals.append(
            IntervalEstimate(
                metric=name,
                lower=float(values[lower_rank - 1]) if failure is None else None,
                upper=float(values[upper_rank - 1]) if failure is None else None,
                defined_replicates=len(values),
                undefined_replicates=undefined[name],
                reason=failure,
            )
        )
    return GroupBootstrapResult(
        group_ids=group_ids,
        attempted_replicates=plan.repetitions,
        lower_rank=lower_rank,
        upper_rank=upper_rank,
        intervals=tuple(intervals),
    )


def _stratum(
    records: tuple[EvaluationRecord, ...],
    plan: BootstrapPlan,
    kind: Literal["global", "family", "migration", "family_migration"],
    family: Family | None = None,
    migration: str | None = None,
) -> EvaluationStratum:
    principal = tuple(r for r in records if _principal(r))
    labelled = tuple(r for r in records if _confirmed(r))
    principal_ids = tuple(r.case_id for r in principal)
    support: dict[Method, tuple[EvaluationRecord, ...]] = {}
    methods: list[MethodEvaluation] = []
    for method in METHODS:
        own = tuple(r for r in labelled if _component(r, method).complete)
        support[method] = own
        methods.append(
            MethodEvaluation(
                method=method,
                complete_case_ids=tuple(
                    r.case_id for r in records if _component(r, method).complete
                ),
                own_case_ids=tuple(r.case_id for r in own),
                partial_alert_case_ids=tuple(
                    r.case_id
                    for r in records
                    if (
                        not _component(r, method).complete
                        and _component(r, method).decision == "alert"
                    )
                ),
                unavailable_case_ids=tuple(
                    r.case_id
                    for r in records
                    if (_component(r, method).decision == "not_evaluable")
                ),
                coverage=_ratio(len(own), len(labelled), "no_confirmed_labels"),
                principal=_confusion(principal, method),
                own_support=_confusion(own, method),
            )
        )
    return EvaluationStratum(
        kind=kind,
        family=family,
        migration=migration,
        coverage=CoverageSummary(
            total_cases=len(records),
            oracle_confirmed=len(labelled),
            oracle_pending=sum(r.oracle_state == "pending" for r in records),
            oracle_disagreement=sum(r.oracle_state == "disagreement" for r in records),
            oracle_not_evaluable=sum(r.oracle_state == "not_evaluable" for r in records),
            failed_case_ids=tuple(r.case_id for r in records if r.failure_reason is not None),
            principal_case_ids=principal_ids,
            excluded_case_ids=tuple(r.case_id for r in records if not _principal(r)),
            principal_coverage=_ratio(len(principal), len(labelled), "no_confirmed_labels"),
        ),
        methods=tuple(methods),
        average_precision=tuple(
            AveragePrecisionEvaluation(
                method=method,
                principal_case_ids=principal_ids,
                own_case_ids=tuple(r.case_id for r in support[method]),
                principal=_ap(principal, method),
                own_support=_ap(support[method], method),
            )
            for method in SCORE_METHODS
        ),
        incremental=_incremental(principal),
        bootstrap=_bootstrap(principal, plan),
    )


def _strata(
    records: tuple[EvaluationRecord, ...],
    config: EvaluationConfig,
) -> tuple[EvaluationStratum, ...]:
    plan = config.bootstrap
    # Identical sets occur, for example, in a one-family/one-migration pilot.
    # Share only immutable calculations within this call; scope labels remain
    # separate and no bootstrap samples or results survive into another report.
    cache: dict[tuple[str, ...], EvaluationStratum] = {}

    def scoped(
        selected: tuple[EvaluationRecord, ...],
        kind: Literal["global", "family", "migration", "family_migration"],
        family: Family | None = None,
        migration: str | None = None,
    ) -> EvaluationStratum:
        key = tuple(r.case_id for r in selected)
        if key not in cache:
            cache[key] = _stratum(selected, plan, kind, family, migration)
        return cache[key].model_copy(
            update={"kind": kind, "family": family, "migration": migration}
        )

    result = [scoped(records, "global")]
    families = sorted(config.expected_families)
    migrations = sorted(set(config.expected_migrations) | {r.migration for r in records})
    for family in families:
        result.append(scoped(tuple(r for r in records if r.family == family), "family", family))
    for migration in migrations:
        result.append(
            scoped(
                tuple(r for r in records if r.migration == migration),
                "migration",
                migration=migration,
            )
        )
    for family in families:
        for migration in migrations:
            result.append(
                scoped(
                    tuple(r for r in records if r.family == family and r.migration == migration),
                    "family_migration",
                    family,
                    migration,
                )
            )
    return tuple(result)


def _records_digest(records: tuple[EvaluationRecord, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [r.model_dump(mode="json") for r in records],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _validate_inputs(records: tuple[EvaluationRecord, ...], config: EvaluationConfig) -> None:
    case_ids = tuple(r.case_id for r in records)
    pipelines = tuple(r.pipeline_sha256 for r in records if r.pipeline_sha256 is not None)
    if len(set(case_ids)) != len(case_ids) or len(set(pipelines)) != len(pipelines):
        raise ValueError("each case and captured execution must occur exactly once")
    scenarios: dict[str, tuple[str, Family]] = {}
    bundles: dict[str, Family] = {}
    for record in records:
        if record.freeze_sha256 != config.freeze_sha256:
            raise ValueError("records and configuration must bind the same freeze")
        if record.family not in config.expected_families:
            raise ValueError("record family is outside the declared evaluation scope")
        if config.expected_migrations and record.migration not in config.expected_migrations:
            raise ValueError("record migration is outside the declared evaluation scope")
        identity = (record.group_id, record.family)
        if scenarios.setdefault(record.scenario_id, identity) != identity:
            raise ValueError("a scenario cannot change dependency group or family")
        bundle = record.detector_bundle_sha256
        if bundle is not None and bundles.setdefault(bundle, record.family) != record.family:
            raise ValueError("a family-specific bundle cannot serve a different family")


def evaluate_records(
    records: tuple[EvaluationRecord, ...],
    config: EvaluationConfig,
) -> EvaluationReport:
    """Calculate paired metrics without detector access or unverified evidence IO."""
    config = EvaluationConfig.model_validate(config)
    if not isinstance(records, tuple):
        raise ValueError("records must be a tuple of strict EvaluationRecord instances")
    checked = tuple(EvaluationRecord.model_validate(record) for record in records)
    ordered = tuple(sorted(checked, key=lambda record: record.case_id))
    _validate_inputs(ordered, config)
    return EvaluationReport(
        scientific=config.mode == "final",
        config_sha256=digest(config),
        protocol_sha256=evaluation_protocol_sha256(config),
        records_sha256=_records_digest(ordered),
        config=config,
        records=ordered,
        strata=_strata(ordered, config),
    )
