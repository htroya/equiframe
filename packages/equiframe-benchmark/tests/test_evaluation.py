"""Invented unit records exercise mathematics; none are human/scientific approvals."""

import hashlib
import json
from fractions import Fraction

import pytest
from equiframe import ComponentDecision
from pydantic import ValidationError

from equiframe_benchmark.evaluation import (
    BootstrapPlan,
    EvaluationConfig,
    EvaluationRecord,
    EvaluationReport,
    evaluate_records,
    evaluation_protocol_sha256,
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def decision(alert: bool) -> ComponentDecision:
    return ComponentDecision(decision="alert" if alert else "no_alert", complete=True)


UNAVAILABLE = ComponentDecision(decision="not_evaluable", complete=False, reason="unit_missing")


def record(
    number: int,
    positive: bool,
    *,
    r: bool = False,
    m: bool = False,
    b: bool = False,
    group: str | None = None,
    family: str = "joins",
    migration: str = "pandas-polars",
    m_score: float = 0.5,
    b_score: float | str = 0.5,
) -> EvaluationRecord:
    return EvaluationRecord(
        case_id=f"unit-{number:03d}",
        scenario_id=f"unit-scenario-{number}",
        group_id=group or f"unit-group-{number}",
        family=family,
        migration=migration,
        engine="polars",
        candidate_sha256=sha(f"candidate-{number}"),
        pipeline_sha256=sha(f"pipeline-{number}"),
        oracle_sha256=sha(f"oracle-{number}"),
        oracle_state="confirmed",
        oracle_label="divergent" if positive else "normal",
        r=decision(r),
        m=decision(m),
        b=decision(b),
        h=decision(r or m),
        m_score=m_score,
        b_score=b_score,
        detector_bundle_sha256=sha(f"bundle-{family}"),
        freeze_sha256=None,
    )


def config(
    *,
    repetitions: int = 20,
    min_groups: int = 2,
    independent: bool = False,
    seed: int = 17,
    confidence: str = "0.95",
) -> EvaluationConfig:
    return EvaluationConfig(
        mode="pilot",
        freeze_sha256=None,
        bootstrap=BootstrapPlan(
            seed=seed,
            repetitions=repetitions,
            confidence=confidence,
            min_groups=min_groups,
            independence_supported=independent,
            rationale="Invented unit-group support, not an experimental independence decision.",
        ),
    )


def cases() -> tuple[EvaluationRecord, ...]:
    alerts = (
        (1, 1, 0),
        (0, 1, 1),
        (0, 0, 1),
        (1, 0, 0),
        (1, 0, 1),
        (0, 1, 0),
        (0, 0, 0),
        (0, 0, 0),
    )
    m_scores = (0.9, 0.8, 0.4, 0.2, 0.7, 0.6, 0.3, 0.1)
    b_scores = (0.5, 0.9, "+infinity", 0.3, "+infinity", 0.8, 0.4, 0.1)
    return tuple(
        record(
            i,
            i < 4,
            r=bool(a[0]),
            m=bool(a[1]),
            b=bool(a[2]),
            group=f"unit-group-{i % 4}",
            m_score=m_scores[i],
            b_score=b_scores[i],
        )
        for i, a in enumerate(alerts)
    )


def global_result(records: tuple[EvaluationRecord, ...], **options):
    return evaluate_records(records, config(**options)).strata[0]


def interval(stratum, name: str):
    return next(i for i in stratum.bootstrap.intervals if i.metric == name)


def test_hand_counted_paired_confusions_and_incremental_detection():
    result = global_result(cases())
    assert result.coverage.principal_case_ids == tuple(f"unit-{i:03d}" for i in range(8))
    for method in result.methods[:3]:
        counts = method.principal
        assert (counts.tp, counts.fp, counts.fn, counts.tn) == (2, 1, 2, 3)
        assert counts.precision.value == float(Fraction(2, 3))
        assert counts.recall.value == 0.5
        assert counts.f1.value == float(Fraction(4, 7))
        assert counts.false_positive_rate.value == 0.25
    hybrid = result.methods[3].principal
    assert (hybrid.tp, hybrid.fp, hybrid.fn, hybrid.tn) == (3, 2, 1, 2)
    assert hybrid.precision.value == 0.6
    assert hybrid.recall.value == 0.75
    assert hybrid.f1.value == float(Fraction(2, 3))
    assert hybrid.false_positive_rate.value == 0.5
    additional = result.incremental
    assert additional.additional_true_positive_case_ids == ("unit-001",)
    assert additional.additional_false_positive_case_ids == ("unit-005",)
    assert additional.additional_true_positive_rate.value == 0.25
    assert additional.additional_false_positive_rate.value == 0.25


def test_hand_ranked_ap_includes_tied_positive_infinity_without_order_bias():
    result = global_result(cases())
    assert result.average_precision[0].principal.value == float(Fraction(111, 140))
    assert result.average_precision[1].principal.value == float(Fraction(491, 840))
    # The first two tied MAD scores are one threshold: arbitrary case order cannot
    # put the positive before the negative and falsely improve AP.
    tied = (record(0, True, b_score="+infinity"), record(1, False, b_score="+infinity"))
    assert global_result(tied).average_precision[1].principal.value == 0.5
    assert global_result(tuple(reversed(tied))).average_precision[1].principal.value == 0.5


def test_principal_intersection_own_support_and_partial_h_alert_are_distinct():
    unavailable_b = cases()[0].model_copy(update={"b": UNAVAILABLE, "b_score": None})
    partial_r = ComponentDecision(decision="alert", complete=False, reason="unit_partial_rules")
    partial_h = ComponentDecision(decision="alert", complete=False, reason="incomplete_components")
    partial = record(20, True).model_copy(
        update={
            "r": partial_r,
            "m": UNAVAILABLE,
            "m_score": None,
            "h": partial_h,
        }
    )
    pending = record(21, False).model_copy(update={"oracle_state": "pending", "oracle_label": None})
    result = global_result((unavailable_b, cases()[1], partial, pending))
    assert result.coverage.oracle_confirmed == 3
    assert result.coverage.oracle_pending == 1
    assert result.coverage.principal_case_ids == ("unit-001",)
    assert result.coverage.principal_coverage.value == float(Fraction(1, 3))
    rule, model, baseline, hybrid = result.methods
    assert rule.own_case_ids == ("unit-000", "unit-001")
    assert rule.complete_case_ids == ("unit-000", "unit-001", "unit-021")
    assert model.own_case_ids == ("unit-000", "unit-001")
    assert baseline.own_case_ids == ("unit-001", "unit-020")
    assert hybrid.partial_alert_case_ids == ("unit-020",)
    assert hybrid.own_case_ids == ("unit-000", "unit-001")
    assert hybrid.principal.tp == 1 and hybrid.own_support.tp == 2
    assert rule.partial_alert_case_ids == ("unit-020",)


def test_empty_pending_failed_and_disagreement_records_do_not_become_negatives():
    source = record(0, True)
    failed = source.model_copy(
        update={
            "r": UNAVAILABLE,
            "m": UNAVAILABLE,
            "b": UNAVAILABLE,
            "h": UNAVAILABLE,
            "m_score": None,
            "b_score": None,
            "detector_bundle_sha256": None,
            "pipeline_sha256": None,
            "failure_reason": "unit_pre_execution_failure",
            "oracle_state": "not_evaluable",
            "oracle_label": None,
        }
    )
    pending = record(1, False).model_copy(update={"oracle_state": "pending", "oracle_label": None})
    disagreement = record(2, False).model_copy(
        update={
            "oracle_state": "disagreement",
            "oracle_label": None,
        }
    )
    result = global_result((failed, pending, disagreement))
    assert result.coverage.total_cases == 3
    assert result.coverage.oracle_confirmed == 0
    assert result.coverage.oracle_not_evaluable == 1
    assert result.coverage.oracle_disagreement == 1
    assert result.coverage.failed_case_ids == ("unit-000",)
    assert result.coverage.principal_coverage.reason == "no_confirmed_labels"
    assert all(m.principal.tn == 0 and m.principal.f1.value is None for m in result.methods)
    assert global_result(()).coverage.total_cases == 0


def test_f1_is_direct_and_zero_denominators_remain_undefined():
    positive = global_result((record(0, True),)).methods[0].principal
    assert positive.precision.value is None
    assert positive.recall.value == 0.0
    assert positive.f1.value == 0.0  # harmonic calculation from undefined precision is wrong
    assert positive.false_positive_rate.value is None
    negative = global_result((record(0, False),)).methods[0].principal
    assert negative.precision.reason == "zero_denominator"
    assert negative.recall.reason == "zero_denominator"
    assert negative.f1.reason == "zero_denominator"
    assert negative.false_positive_rate.value == 0.0


@pytest.mark.parametrize("positive", [True, False])
def test_average_precision_is_undefined_for_either_single_class(positive):
    result = global_result((record(0, positive), record(1, positive)))
    assert all(
        ap.principal.reason == "average_precision_requires_two_classes"
        for ap in result.average_precision
    )


def test_strata_and_homogeneous_model_score_requirement():
    records = (
        record(0, True),
        record(1, False),
        record(2, True, family="dates", migration="pandas-duckdb"),
        record(3, False, family="dates", migration="pandas-duckdb"),
    )
    report = evaluate_records(records, config())
    assert sum(s.kind == "family" for s in report.strata) == 5
    assert sum(s.kind == "migration" for s in report.strata) == 2
    assert sum(s.kind == "family_migration" for s in report.strata) == 10
    assert report.strata[0].average_precision[0].principal.reason == (
        "not_defined_heterogeneous_model_scores"
    )
    assert all(
        ap.principal.value == 0.5
        for s in report.strata[1:]
        if s.coverage.total_cases
        for ap in s.average_precision
    )
    different_bundle = records[1].model_copy(update={"detector_bundle_sha256": sha("other-model")})
    assert global_result((records[0], different_bundle)).average_precision[0].principal.reason == (
        "not_defined_heterogeneous_model_scores"
    )


def test_support_and_independence_gate_intervals_but_keep_descriptions():
    result = global_result(cases(), independent=False)
    assert result.bootstrap.attempted_replicates == 0
    assert interval(result, "R.recall").reason == "independence_not_supported"
    assert result.methods[0].principal.recall.value == 0.5
    result = global_result(cases(), independent=True, min_groups=5)
    assert result.bootstrap.group_ids == tuple(f"unit-group-{i}" for i in range(4))
    assert interval(result, "R.recall").reason == "insufficient_groups"
    assert result.bootstrap.lower_rank is None


def test_undefined_replicates_are_counted_and_never_omitted_from_an_interval():
    # Every group has both classes, so recall/AP stay defined. Only group A
    # predicts any R alerts: resampling B twice makes precision undefined.
    records = (
        record(0, True, group="A", r=True),
        record(1, False, group="A"),
        record(2, True, group="B"),
        record(3, False, group="B"),
    )
    result = global_result(records, independent=True, repetitions=30)
    precision = interval(result, "R.precision")
    assert precision.defined_replicates + precision.undefined_replicates == 30
    assert precision.undefined_replicates > 0
    assert precision.reason == "undefined_bootstrap_replicates"
    assert precision.lower is None and precision.upper is None
    recall = interval(result, "R.recall")
    assert recall.undefined_replicates == 0 and recall.reason is None
    assert recall.lower == 0.0 and recall.upper == 1.0


def test_group_resampling_preserves_duplicates_and_weights_each_execution():
    # Group A: 3 positives / 4 executions; group B: 1 / 3. With two draws,
    # the only precision estimates are 3/4, 4/7 and 1/3 (not group mean 13/24).
    records = tuple(record(i, i < 3, group="A", r=True, m=True, b=True) for i in range(4))
    records += tuple(record(i + 4, i == 0, group="B", r=True, m=True, b=True) for i in range(3))
    result = global_result(records, independent=True, repetitions=10, confidence="0.8", seed=17)
    estimate = interval(result, "R.precision")
    assert result.methods[0].principal.precision.value == float(Fraction(4, 7))
    assert result.bootstrap.lower_rank == 1 and result.bootstrap.upper_rank == 9
    assert estimate.lower == float(Fraction(1, 3))
    assert estimate.upper == 0.75
    assert estimate.defined_replicates == 10 and estimate.undefined_replicates == 0


def test_exact_decimal_percentile_rank_avoids_binary_rounding_and_interpolation():
    records = (
        record(0, True, r=True, group="A"),
        record(1, False, r=True, group="A"),
        record(2, True, r=True, group="B"),
        record(3, False, r=True, group="B"),
    )
    result = global_result(records, independent=True, repetitions=100, confidence="0.94")
    assert result.bootstrap.lower_rank == 3  # float (1-.94)/2*100 rounds above 3
    assert result.bootstrap.upper_rank == 97


def test_default_two_thousand_whole_group_replicates_and_nearest_percentiles():
    records = (
        record(0, True, r=True, m=True, b=True, group="A"),
        record(1, False, r=True, m=True, b=True, group="A"),
        record(2, True, r=True, m=True, b=True, group="B"),
        record(3, False, r=True, m=True, b=True, group="B"),
    )
    plan = BootstrapPlan(
        seed=5,
        min_groups=2,
        independence_supported=True,
        rationale="Unit support only; no experimental approval.",
    )
    result = evaluate_records(
        records,
        EvaluationConfig(
            mode="pilot",
            freeze_sha256=None,
            bootstrap=plan,
        ),
    ).strata[0]
    assert result.bootstrap.attempted_replicates == 2000
    assert result.bootstrap.lower_rank == 50 and result.bootstrap.upper_rank == 1950
    assert interval(result, "R.precision").lower == 0.5
    assert interval(result, "R.precision").upper == 0.5
    assert all(
        i.defined_replicates == 2000 and i.undefined_replicates == 0
        for i in result.bootstrap.intervals
    )


def test_result_is_deterministic_canonical_and_revalidated_after_json_roundtrip():
    options = config(repetitions=12, independent=True)
    report = evaluate_records(cases(), options)
    reordered = evaluate_records(tuple(reversed(cases())), options)
    assert reordered == report
    assert report.scientific is False
    assert EvaluationReport.model_validate_json(report.model_dump_json()) == report
    assert EvaluationReport.model_validate(report) == report


@pytest.mark.parametrize("part", ["count", "interval", "coverage", "support", "hash", "scientific"])
def test_corrupt_derived_report_is_rejected_after_recalculation(part):
    report = evaluate_records(cases(), config(repetitions=6, independent=True))
    payload = json.loads(report.model_dump_json())
    if part == "count":
        payload["strata"][0]["methods"][0]["principal"]["tp"] = 42
    elif part == "interval":
        payload["strata"][0]["bootstrap"]["intervals"][1]["lower"] = 0.123
    elif part == "coverage":
        payload["strata"][0]["coverage"]["oracle_pending"] = 10
    elif part == "support":
        payload["strata"][0]["methods"][0]["own_case_ids"] = []
    elif part == "hash":
        payload["records_sha256"] = sha("corrupt")
    else:
        payload["scientific"] = True
    with pytest.raises(ValidationError, match="report disagrees"):
        EvaluationReport.model_validate_json(json.dumps(payload))


def test_final_freeze_binding_is_integrity_not_authentication():
    frozen = sha("unit-fake-freeze-not-a-real-scientific-approval")
    options = EvaluationConfig(mode="final", freeze_sha256=frozen, bootstrap=config().bootstrap)
    final_records = tuple(r.model_copy(update={"freeze_sha256": frozen}) for r in cases())
    report = evaluate_records(final_records, options)
    assert report.scientific is True
    assert report.protocol_sha256 == evaluation_protocol_sha256(config())
    with pytest.raises(ValueError, match="same freeze"):
        evaluate_records(cases(), options)
    with pytest.raises(ValidationError, match="final evaluation requires"):
        EvaluationConfig(mode="final", freeze_sha256=None, bootstrap=config().bootstrap)


@pytest.mark.parametrize(
    "change",
    [
        {"m_score": "0.5"},
        {"m_score": True},
        {"m_score": float("nan")},
        {"m_score": float("inf")},
        {"b_score": float("inf")},
        {"b_score": -1.0},
        {"b_score": True},
        {"m_score": None},
        {"detector_bundle_sha256": None},
        {"oracle_state": "pending"},
        {"oracle_sha256": None},
        {"h": decision(False)},
        {"engine": "spark"},
        {"unexpected": 1},
    ],
)
def test_record_rejects_coercion_invalid_scores_missing_evidence_and_false_h(change):
    values = record(0, True, r=True).model_dump()
    values.update(change)
    with pytest.raises(ValidationError):
        EvaluationRecord.model_validate(values)


def test_missing_pipeline_with_complete_decisions_is_rejected():
    with pytest.raises(ValidationError, match="missing pipeline"):
        EvaluationRecord.model_validate(
            record(0, True).model_copy(update={"pipeline_sha256": None})
        )


def test_duplicate_execution_evidence_cannot_inflate_other_migrations():
    first = record(0, True)
    duplicate = record(1, False, migration="polars-duckdb").model_copy(
        update={
            "pipeline_sha256": first.pipeline_sha256,
        }
    )
    with pytest.raises(ValueError, match="exactly once"):
        evaluate_records((first, duplicate), config())
    with pytest.raises(ValueError, match="exactly once"):
        evaluate_records((first, first), config())
    identical_output = record(1, False).model_copy(
        update={"candidate_sha256": first.candidate_sha256}
    )
    assert global_result((first, identical_output)).coverage.total_cases == 2


def test_group_and_model_family_provenance_cannot_shift():
    first = record(0, True)
    other = record(1, False).model_copy(update={"scenario_id": first.scenario_id})
    with pytest.raises(ValueError, match="scenario cannot change"):
        evaluate_records((first, other), config())
    other = record(1, False, family="dates").model_copy(
        update={
            "detector_bundle_sha256": first.detector_bundle_sha256,
        }
    )
    with pytest.raises(ValueError, match="family-specific bundle"):
        evaluate_records((first, other), config())


def test_declared_families_and_migrations_include_empty_support_and_bind_protocol():
    options = config()
    declared = options.model_copy(
        update={"expected_migrations": ("pandas-polars", "polars-duckdb")}
    )
    report = evaluate_records((record(0, True), record(1, False)), declared)
    empty_dates = next(s for s in report.strata if s.kind == "family" and s.family == "dates")
    assert empty_dates.coverage.total_cases == 0
    assert empty_dates.coverage.principal_case_ids == ()
    assert empty_dates.methods[0].principal.recall.reason == "zero_denominator"
    assert empty_dates.average_precision[0].principal.reason == "no_score_support"
    empty_migration = next(
        s for s in report.strata if s.kind == "migration" and s.migration == "polars-duckdb"
    )
    assert empty_migration.coverage.total_cases == 0
    assert evaluation_protocol_sha256(options) != evaluation_protocol_sha256(declared)
    with pytest.raises(ValueError, match="migration is outside"):
        evaluate_records((record(2, True, migration="isolated"),), declared)
    limited = options.model_copy(update={"expected_families": ("joins",)})
    with pytest.raises(ValueError, match="family is outside"):
        evaluate_records((record(2, True, family="dates"),), limited)


@pytest.mark.parametrize(
    "change",
    [
        {"expected_families": ()},
        {"expected_families": ("joins", "joins")},
        {"expected_migrations": ("same", "same")},
    ],
)
def test_scope_declarations_are_nonempty_for_families_and_unique(change):
    with pytest.raises(ValidationError):
        EvaluationConfig.model_validate(config().model_copy(update=change))


@pytest.mark.parametrize(
    "options",
    [
        {"repetitions": 0},
        {"repetitions": "20"},
        {"seed": True},
        {"min_groups": 0},
        {"confidence": "0"},
        {"confidence": "1.0"},
        {"confidence": "0.0"},
        {"confidence": 0.95},
        {"independence_supported": "yes"},
    ],
)
def test_bootstrap_protocol_is_strict_and_explicit(options):
    values = config().bootstrap.model_dump()
    values.update(options)
    with pytest.raises(ValidationError):
        BootstrapPlan.model_validate(values)
