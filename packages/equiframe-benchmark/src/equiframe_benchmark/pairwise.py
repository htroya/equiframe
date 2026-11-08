"""Supplementary paired supports without changing an existing frozen evaluation.

Every contrast uses confirmed labels and complete decisions for both methods.
No training, scoring, ETL, new intervals or hypothesis tests occur here. A report
binds the original evaluation and protocol; adopting these supports as principal
scientific analyses requires a separately reviewed and frozen protocol.
"""

import hashlib
import json
from itertools import combinations
from typing import Annotated, Literal

from equiframe import Family
from equiframe._base import strict_bool_literal
from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.evaluation import (
    METHODS,
    ConfusionMetrics,
    EvaluationRecord,
    EvaluationReport,
    Method,
    MetricValue,
    NonNegativeInt,
    _component,
    _confusion,
    _ratio,
)
from equiframe_benchmark.models import Digest, Document, Text, digest

StratumKind = Literal["global", "family", "migration", "family_migration"]
ExclusionReason = Literal["oracle_unconfirmed", "left_incomplete", "right_incomplete"]
PAIRS: tuple[tuple[Method, Method], ...] = tuple(combinations(METHODS, 2))


def pairwise_policy_sha256() -> str:
    """Fingerprint this supplementary calculation, never the frozen protocol."""
    policy = {
        "schema_version": "1.0",
        "role": "supplementary_descriptive",
        "pairs": PAIRS,
        "support": "confirmed_O_and_both_methods_complete",
        "scope": "existing_evaluation_strata_including_declared_empty",
        "coverage": "paired_over_confirmed_and_paired_over_scheduled",
        "direction": "own_alert_other_no_alert_by_confirmed_class",
        "rates": "discordant_divergent_over_divergent_and_normal_over_normal",
        "exclusions": "all_applicable_reasons_oracle_left_right",
        "inference": "none",
    }
    return hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class PairwiseDirection(Document):
    """Alerts unique to one method on the shared complete, labelled support."""

    method: Method
    reference: Method
    additional_true_positive_case_ids: tuple[Text, ...]
    additional_false_positive_case_ids: tuple[Text, ...]
    additional_true_positive_rate: MetricValue
    additional_false_positive_rate: MetricValue


class PairwiseExclusion(Document):
    case_id: Text
    oracle_state: Literal["pending", "disagreement", "confirmed", "not_evaluable"]
    reasons: Annotated[tuple[ExclusionReason, ...], Field(min_length=1)]


class PairwiseComparison(Document):
    left_method: Method
    right_method: Method
    support_case_ids: tuple[Text, ...]
    group_ids: tuple[Text, ...]
    divergent_cases: NonNegativeInt
    normal_cases: NonNegativeInt
    coverage_confirmed: MetricValue
    coverage_scheduled: MetricValue
    left_metrics: ConfusionMetrics
    right_metrics: ConfusionMetrics
    left_only: PairwiseDirection
    right_only: PairwiseDirection
    exclusions: tuple[PairwiseExclusion, ...]
    left_partial_alert_case_ids: tuple[Text, ...]
    right_partial_alert_case_ids: tuple[Text, ...]


class PairwiseStratum(Document):
    kind: StratumKind
    family: Family | None
    migration: Text | None
    total_cases: NonNegativeInt
    oracle_confirmed: NonNegativeInt
    oracle_pending: NonNegativeInt
    oracle_disagreement: NonNegativeInt
    oracle_not_evaluable: NonNegativeInt
    common_case_ids: tuple[Text, ...]
    pairs: tuple[PairwiseComparison, ...]


class PairwiseReport(Document):
    """Self-contained supplementary report recalculated on JSON/model validation."""

    analysis_role: Literal["supplementary_descriptive"] = "supplementary_descriptive"
    scientific: Annotated[Literal[False], BeforeValidator(strict_bool_literal)] = False
    evaluation_sha256: Digest
    protocol_sha256: Digest
    analysis_policy_sha256: Digest
    evaluation: EvaluationReport
    strata: tuple[PairwiseStratum, ...]

    @model_validator(mode="after")
    def recalculate(self) -> Self:
        # Pydantic has already validated this nested field before the after-validator.
        # Document revalidates existing instances, including model_copy bypasses,
        # so validating again here only repeats the same full bootstrap.
        checked = self.evaluation
        if (
            self.evaluation_sha256 != digest(checked)
            or self.protocol_sha256 != checked.protocol_sha256
            or self.analysis_policy_sha256 != pairwise_policy_sha256()
            or self.strata != _strata(checked)
        ):
            raise ValueError(
                "pairwise report disagrees with bound evaluation or paired calculations"
            )
        return self


def _direction(
    records: tuple[EvaluationRecord, ...], method: Method, reference: Method
) -> PairwiseDirection:
    unique_alerts = tuple(
        record
        for record in records
        if _component(record, method).decision == "alert"
        and _component(record, reference).decision == "no_alert"
    )
    true = tuple(r.case_id for r in unique_alerts if r.oracle_label == "divergent")
    false = tuple(r.case_id for r in unique_alerts if r.oracle_label == "normal")
    divergent = sum(r.oracle_label == "divergent" for r in records)
    return PairwiseDirection(
        method=method,
        reference=reference,
        additional_true_positive_case_ids=true,
        additional_false_positive_case_ids=false,
        additional_true_positive_rate=_ratio(len(true), divergent, "no_divergent_pair_support"),
        additional_false_positive_rate=_ratio(
            len(false), len(records) - divergent, "no_normal_pair_support"
        ),
    )


def _pair(records: tuple[EvaluationRecord, ...], left: Method, right: Method) -> PairwiseComparison:
    support: list[EvaluationRecord] = []
    exclusions: list[PairwiseExclusion] = []
    for record in records:
        reasons: list[ExclusionReason] = []
        if record.oracle_state != "confirmed":
            reasons.append("oracle_unconfirmed")
        if not _component(record, left).complete:
            reasons.append("left_incomplete")
        if not _component(record, right).complete:
            reasons.append("right_incomplete")
        if reasons:
            exclusions.append(
                PairwiseExclusion(
                    case_id=record.case_id, oracle_state=record.oracle_state, reasons=tuple(reasons)
                )
            )
        else:
            support.append(record)
    paired = tuple(support)
    confirmed = sum(r.oracle_state == "confirmed" for r in records)
    divergent = sum(r.oracle_label == "divergent" for r in paired)
    return PairwiseComparison(
        left_method=left,
        right_method=right,
        support_case_ids=tuple(r.case_id for r in paired),
        group_ids=tuple(sorted({r.group_id for r in paired})),
        divergent_cases=divergent,
        normal_cases=len(paired) - divergent,
        coverage_confirmed=_ratio(len(paired), confirmed, "no_confirmed_labels"),
        coverage_scheduled=_ratio(len(paired), len(records), "no_scheduled_cases"),
        left_metrics=_confusion(paired, left),
        right_metrics=_confusion(paired, right),
        left_only=_direction(paired, left, right),
        right_only=_direction(paired, right, left),
        exclusions=tuple(exclusions),
        left_partial_alert_case_ids=tuple(
            r.case_id
            for r in records
            if not _component(r, left).complete and _component(r, left).decision == "alert"
        ),
        right_partial_alert_case_ids=tuple(
            r.case_id
            for r in records
            if not _component(r, right).complete and _component(r, right).decision == "alert"
        ),
    )


def _strata(report: EvaluationReport) -> tuple[PairwiseStratum, ...]:
    strata: list[PairwiseStratum] = []
    for original in report.strata:
        selected = tuple(
            r
            for r in report.records
            if (original.family is None or r.family == original.family)
            and (original.migration is None or r.migration == original.migration)
        )
        coverage = original.coverage
        strata.append(
            PairwiseStratum(
                kind=original.kind,
                family=original.family,
                migration=original.migration,
                total_cases=coverage.total_cases,
                oracle_confirmed=coverage.oracle_confirmed,
                oracle_pending=coverage.oracle_pending,
                oracle_disagreement=coverage.oracle_disagreement,
                oracle_not_evaluable=coverage.oracle_not_evaluable,
                common_case_ids=coverage.principal_case_ids,
                pairs=tuple(_pair(selected, left, right) for left, right in PAIRS),
            )
        )
    return tuple(strata)


def evaluate_pairwise(report: EvaluationReport) -> PairwiseReport:
    """Derive descriptive contrasts from an existing strictly validated evaluation.

    The source's protocol, scientific flag and six historical CSV stay unchanged.
    This new report is always supplementary, including when the source is final.
    Persist explicitly with save_document; no files are written by this function.
    """
    checked = EvaluationReport.model_validate(report)
    return PairwiseReport(
        evaluation_sha256=digest(checked),
        protocol_sha256=checked.protocol_sha256,
        analysis_policy_sha256=pairwise_policy_sha256(),
        evaluation=checked,
        strata=_strata(checked),
    )
