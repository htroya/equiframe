"""Version 2: principal paired supports; the four-method intersection is additional.

V1 documents and fingerprints are deliberately unchanged. This module consumes
captured decisions only: no training, labels, scores or native runs are generated.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from fractions import Fraction
from math import ceil
from typing import Annotated, Literal, cast

from equiframe import Family
from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.evaluation import (
    METHODS,
    BootstrapPlan,
    ConfusionMetrics,
    EvaluationConfig,
    EvaluationRecord,
    GroupBootstrapResult,
    IntervalEstimate,
    Method,
    MetricValue,
    _ap,
    _bootstrap,
    _component,
    _confusion,
    _principal,
    _records_digest,
    _validate_inputs,
)
from equiframe_benchmark.models import Digest, Text, digest
from equiframe_benchmark.models_v2 import DocumentV2 as Document
from equiframe_benchmark.pairwise import PairwiseComparison, StratumKind, _direction, _pair

PRIMARY_FAMILIES: tuple[Family, ...] = ("nulls_types", "joins", "aggregations")
MigrationPairV2 = Literal["pandas-polars", "pandas-duckdb", "polars-duckdb"]
PRIMARY_MIGRATIONS: tuple[MigrationPairV2, ...] = (
    "pandas-polars",
    "pandas-duckdb",
    "polars-duckdb",
)


class ContrastSpecV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    left: Method
    right: Method

    @model_validator(mode="after")
    def distinct(self) -> Self:
        if self.left == self.right:
            raise ValueError("a paired contrast requires two distinct methods")
        return self


class EvaluationConfigV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    protocol: Literal["paired-principal-2.0"] = "paired-principal-2.0"
    mode: Literal["pilot", "final"]
    freeze_sha256: Digest | None
    bootstrap: BootstrapPlan
    contrasts: Annotated[tuple[ContrastSpecV2, ...], Field(min_length=1, max_length=6)]
    expected_families: tuple[Family, ...] = PRIMARY_FAMILIES
    expected_migrations: tuple[MigrationPairV2, ...] = PRIMARY_MIGRATIONS

    @model_validator(mode="after")
    def binding(self) -> Self:
        if (self.mode == "final") != (self.freeze_sha256 is not None):
            raise ValueError("final V2 evaluation requires its own frozen manifest")
        if self.expected_families != PRIMARY_FAMILIES:
            raise ValueError("V2 requires the three primary families in canonical order")
        if self.expected_migrations != PRIMARY_MIGRATIONS:
            raise ValueError("V2 requires all three engine pairs in canonical order")
        pairs = [frozenset((pair.left, pair.right)) for pair in self.contrasts]
        if len(set(pairs)) != len(pairs):
            raise ValueError("a method contrast cannot be repeated or reversed")
        return self


def evaluation_protocol_sha256_v2(config: EvaluationConfigV2) -> str:
    checked = EvaluationConfigV2.model_validate(config)
    payload = {
        "schema_version": "2.0",
        "protocol": checked.protocol,
        "bootstrap": checked.bootstrap.model_dump(mode="json"),
        "contrasts": [pair.model_dump(mode="json") for pair in checked.contrasts],
        "expected_families": checked.expected_families,
        "expected_migrations": checked.expected_migrations,
        "principal": "confirmed_O_and_both_contrasted_methods_complete",
        "additional": "confirmed_O_and_complete_R_M_B_H",
        "uncertainty": "same_resampled_whole_groups_for_both_methods_and_differences",
        "undefined": "explicit_denominators_no_undefined_replicate_omission",
        "average_precision": "tied_thresholds_two_classes_homogeneous_family_and_bundle",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class SignedMetricV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    numerator: int
    denominator: Annotated[int, Field(ge=0)]
    value: float | None
    reason: Text | None

    @model_validator(mode="after")
    def arithmetic(self) -> Self:
        if self.denominator == 0:
            if self.numerator != 0 or self.value is not None or self.reason is None:
                raise ValueError("undefined contrast requires zero counts and a reason")
        elif self.reason is not None or self.value != float(
            Fraction(self.numerator, self.denominator)
        ):
            raise ValueError("contrast value must match its exact rational value")
        return self


class PairedEstimateV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    name: Text
    estimate: SignedMetricV2


class PrincipalContrastV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    comparison: PairwiseComparison
    estimates: tuple[PairedEstimateV2, ...]
    bootstrap: GroupBootstrapResult


class CommonMethodV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    method: Method
    metrics: ConfusionMetrics
    average_precision: MetricValue | None


class CommonSupportV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    role: Literal["additional_common_R_M_B_H"] = "additional_common_R_M_B_H"
    case_ids: tuple[Text, ...]
    methods: tuple[CommonMethodV2, ...]
    bootstrap: GroupBootstrapResult


class EvaluationStratumV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    kind: StratumKind
    family: Family | None
    migration: MigrationPairV2 | None
    total_cases: Annotated[int, Field(ge=0)]
    oracle_confirmed: Annotated[int, Field(ge=0)]
    principal: tuple[PrincipalContrastV2, ...]
    common: CommonSupportV2


def _signed(value: MetricValue) -> SignedMetricV2:
    return SignedMetricV2(
        numerator=value.numerator,
        denominator=value.denominator,
        value=value.value,
        reason=value.reason,
    )


def _difference(left: MetricValue, right: MetricValue) -> SignedMetricV2:
    if left.value is None or right.value is None:
        return SignedMetricV2(
            numerator=0, denominator=0, value=None, reason="undefined_contrasted_metric"
        )
    difference = Fraction(left.numerator, left.denominator) - Fraction(
        right.numerator, right.denominator
    )
    return SignedMetricV2(
        numerator=difference.numerator,
        denominator=difference.denominator,
        value=float(difference),
        reason=None,
    )


def _estimates_v2(
    records: tuple[EvaluationRecord, ...],
    contrast: ContrastSpecV2,
) -> dict[str, SignedMetricV2]:
    left = _confusion(records, contrast.left)
    right = _confusion(records, contrast.right)
    result: dict[str, SignedMetricV2] = {}
    for metric in ("precision", "recall", "f1", "false_positive_rate"):
        a, b = getattr(left, metric), getattr(right, metric)
        result[f"{contrast.left}.{metric}"] = _signed(a)
        result[f"{contrast.right}.{metric}"] = _signed(b)
        result[f"difference.{contrast.left}-{contrast.right}.{metric}"] = _difference(a, b)
    for method in (contrast.left, contrast.right):
        if method in ("M", "B"):
            result[f"{method}.average_precision"] = _signed(_ap(records, method))
    for direction in (
        _direction(records, contrast.left, contrast.right),
        _direction(records, contrast.right, contrast.left),
    ):
        prefix = f"{direction.method}_only_vs_{direction.reference}"
        result[prefix + ".true_positive_rate"] = _signed(direction.additional_true_positive_rate)
        result[prefix + ".false_positive_rate"] = _signed(direction.additional_false_positive_rate)
    return result


def _paired_bootstrap(
    records: tuple[EvaluationRecord, ...],
    contrast: ContrastSpecV2,
    plan: BootstrapPlan,
) -> GroupBootstrapResult:
    groups: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for record in records:
        groups[record.group_id].append(record)
    identifiers = tuple(sorted(groups))
    points = _estimates_v2(records, contrast)
    reason = (
        "independence_not_supported"
        if not plan.independence_supported
        else "insufficient_groups"
        if len(identifiers) < plan.min_groups
        else None
    )
    if reason is not None:
        return GroupBootstrapResult(
            group_ids=identifiers,
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
    rng = random.Random(plan.seed)
    samples: dict[str, list[Fraction]] = {name: [] for name in points}
    undefined = dict.fromkeys(points, 0)
    for _ in range(plan.repetitions):
        # One draw of complete dependency groups serves both contrasted methods.
        selected = tuple(
            record
            for _ in identifiers
            for record in groups[identifiers[rng.randrange(len(identifiers))]]
        )
        for name, estimate in _estimates_v2(selected, contrast).items():
            if estimate.value is None:
                undefined[name] += 1
            else:
                samples[name].append(Fraction(estimate.numerator, estimate.denominator))
    tail = (1 - Fraction(plan.confidence)) / 2
    lower = max(1, ceil(tail * plan.repetitions))
    upper = ceil((1 - tail) * plan.repetitions)
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
                lower=float(values[lower - 1]) if failure is None else None,
                upper=float(values[upper - 1]) if failure is None else None,
                defined_replicates=len(values),
                undefined_replicates=undefined[name],
                reason=failure,
            )
        )
    return GroupBootstrapResult(
        group_ids=identifiers,
        attempted_replicates=plan.repetitions,
        lower_rank=lower,
        upper_rank=upper,
        intervals=tuple(intervals),
    )


def _strata_v2(
    records: tuple[EvaluationRecord, ...],
    config: EvaluationConfigV2,
) -> tuple[EvaluationStratumV2, ...]:
    scopes: list[tuple[StratumKind, Family | None, MigrationPairV2 | None]] = [
        ("global", None, None)
    ]
    scopes.extend(("family", family, None) for family in config.expected_families)
    scopes.extend(("migration", None, migration) for migration in config.expected_migrations)
    scopes.extend(
        ("family_migration", family, migration)
        for family in config.expected_families
        for migration in config.expected_migrations
    )
    result = []
    cache: dict[tuple[str, ...], tuple[tuple[PrincipalContrastV2, ...], CommonSupportV2]] = {}
    for kind, family, migration in scopes:
        selected = tuple(
            record
            for record in records
            if (family is None or record.family == family)
            and (migration is None or record.migration == migration)
        )
        key = tuple(record.case_id for record in selected)
        if key not in cache:
            principal = []
            for contrast in config.contrasts:
                paired = tuple(
                    record
                    for record in selected
                    if record.oracle_state == "confirmed"
                    and _component(record, contrast.left).complete
                    and _component(record, contrast.right).complete
                )
                principal.append(
                    PrincipalContrastV2(
                        comparison=_pair(selected, contrast.left, contrast.right),
                        estimates=tuple(
                            PairedEstimateV2(name=name, estimate=value)
                            for name, value in _estimates_v2(paired, contrast).items()
                        ),
                        bootstrap=_paired_bootstrap(paired, contrast, config.bootstrap),
                    )
                )
            common = tuple(record for record in selected if _principal(record))
            additional = CommonSupportV2(
                case_ids=tuple(record.case_id for record in common),
                methods=tuple(
                    CommonMethodV2(
                        method=method,
                        metrics=_confusion(common, method),
                        average_precision=(_ap(common, method) if method in ("M", "B") else None),
                    )
                    for method in METHODS
                ),
                bootstrap=_bootstrap(common, config.bootstrap),
            )
            cache[key] = (tuple(principal), additional)
        contrasts, common_support = cache[key]
        result.append(
            EvaluationStratumV2(
                kind=kind,
                family=family,
                migration=migration,
                total_cases=len(selected),
                oracle_confirmed=sum(record.oracle_state == "confirmed" for record in selected),
                principal=contrasts,
                common=common_support,
            )
        )
    return tuple(result)


class EvaluationReportV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    analysis_role: Literal["principal_paired"] = "principal_paired"
    scientific: bool
    config_sha256: Digest
    protocol_sha256: Digest
    records_sha256: Digest
    config: EvaluationConfigV2
    records: tuple[EvaluationRecord, ...]
    strata: tuple[EvaluationStratumV2, ...]

    @model_validator(mode="after")
    def recalculate(self) -> Self:
        _validate_v2(self.records, self.config)
        if self.records != tuple(sorted(self.records, key=lambda record: record.case_id)):
            raise ValueError("V2 records require canonical case order")
        if (
            self.scientific != (self.config.mode == "final")
            or self.config_sha256 != digest(self.config)
            or self.protocol_sha256 != evaluation_protocol_sha256_v2(self.config)
            or self.records_sha256 != _records_digest(self.records)
            or self.strata != _strata_v2(self.records, self.config)
        ):
            raise ValueError("V2 report differs from captured records and frozen paired protocol")
        return self


def _validate_v2(records: tuple[EvaluationRecord, ...], config: EvaluationConfigV2) -> None:
    # Shared validation reads identity/scope fields only; no V1 config is created.
    _validate_inputs(records, cast(EvaluationConfig, config))
    for record in records:
        if record.engine not in record.migration.split("-"):
            raise ValueError("native engine must belong to its declared V2 migration pair")


def evaluate_records_v2(
    records: tuple[EvaluationRecord, ...],
    config: EvaluationConfigV2,
) -> EvaluationReportV2:
    checked_config = EvaluationConfigV2.model_validate(config)
    if not isinstance(records, tuple):
        raise ValueError("V2 records require an explicit tuple")
    checked = tuple(
        sorted(
            (EvaluationRecord.model_validate(record) for record in records),
            key=lambda record: record.case_id,
        )
    )
    _validate_v2(checked, checked_config)
    return EvaluationReportV2(
        scientific=checked_config.mode == "final",
        config_sha256=digest(checked_config),
        protocol_sha256=evaluation_protocol_sha256_v2(checked_config),
        records_sha256=_records_digest(checked),
        config=checked_config,
        records=checked,
        strata=_strata_v2(checked, checked_config),
    )
