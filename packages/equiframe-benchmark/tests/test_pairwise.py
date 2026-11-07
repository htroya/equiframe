"""Hand-counted synthetic records; no scientific labels, models or reviews."""

import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from equiframe import ComponentDecision, Family
from pydantic import ValidationError

from equiframe_benchmark.evaluation import (
    BootstrapPlan,
    EvaluationConfig,
    EvaluationRecord,
    evaluate_records,
)
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import digest
from equiframe_benchmark.pairwise import (
    PairwiseReport,
    evaluate_pairwise,
    pairwise_policy_sha256,
)
from equiframe_benchmark.tables import table_payloads

UNAVAILABLE = ComponentDecision(
    decision="not_evaluable", complete=False, reason="synthetic_missing"
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def decision(alert: bool) -> ComponentDecision:
    return ComponentDecision(decision="alert" if alert else "no_alert", complete=True)


def record(
    number: int,
    positive: bool,
    *,
    r: bool = False,
    m: bool = False,
    b: bool = False,
    family: Family = "joins",
    migration: str = "pandas-polars",
) -> EvaluationRecord:
    return EvaluationRecord(
        case_id=f"synthetic-{number}",
        scenario_id=f"scenario-{number}",
        group_id=f"group-{number // 2}",
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
        m_score=0.5,
        b_score=0.5,
        detector_bundle_sha256=sha(f"bundle-{family}"),
        freeze_sha256=None,
    )


def config() -> EvaluationConfig:
    return EvaluationConfig(
        mode="pilot",
        freeze_sha256=None,
        bootstrap=BootstrapPlan(
            seed=17,
            repetitions=2,
            min_groups=2,
            independence_supported=False,
            rationale="Synthetic test records, no inferential independence claim",
        ),
        expected_families=("joins", "dates"),
        expected_migrations=("pandas-polars", "pandas-duckdb"),
    )


def cases() -> tuple[EvaluationRecord, ...]:
    # First four divergent, last four normal. R, M and B each have TP2/FP1;
    # H has TP3/FP2. R misses divergent #1 and H adds normal false alarm #5.
    alerts = (
        (True, True, False),
        (False, True, True),
        (False, False, True),
        (True, False, False),
        (True, False, True),
        (False, True, False),
        (False, False, False),
        (False, False, False),
    )
    return tuple(record(i, i < 4, r=r, m=m, b=b) for i, (r, m, b) in enumerate(alerts))


def get_pair(result, left: str, right: str):
    return next(
        p for p in result.strata[0].pairs if (p.left_method, p.right_method) == (left, right)
    )


def test_six_pairs_have_hand_counted_confusions_and_directional_discordance():
    source = evaluate_records(cases(), config())
    result = evaluate_pairwise(source)
    assert len(result.strata) == 9  # global + 2 families + 2 migrations + 4 crosses
    assert [(p.left_method, p.right_method) for p in result.strata[0].pairs] == [
        ("R", "M"),
        ("R", "B"),
        ("R", "H"),
        ("M", "B"),
        ("M", "H"),
        ("B", "H"),
    ]
    for pair in result.strata[0].pairs:
        assert pair.support_case_ids == tuple(f"synthetic-{i}" for i in range(8))
        assert pair.group_ids == ("group-0", "group-1", "group-2", "group-3")
        assert (pair.divergent_cases, pair.normal_cases) == (4, 4)
        assert pair.coverage_confirmed.value == pair.coverage_scheduled.value == 1.0
        for method, metrics in (
            (pair.left_method, pair.left_metrics),
            (pair.right_method, pair.right_metrics),
        ):
            expected = (3, 2, 1, 2) if method == "H" else (2, 1, 2, 3)
            assert (metrics.tp, metrics.fp, metrics.fn, metrics.tn) == expected
    rm = get_pair(result, "R", "M")
    assert rm.left_metrics.precision.value == float(Fraction(2, 3))
    assert rm.left_metrics.f1.value == float(Fraction(4, 7))
    assert rm.left_only.additional_true_positive_case_ids == ("synthetic-3",)
    assert rm.left_only.additional_false_positive_case_ids == ("synthetic-4",)
    assert rm.right_only.additional_true_positive_case_ids == ("synthetic-1",)
    assert rm.right_only.additional_false_positive_case_ids == ("synthetic-5",)
    rh = get_pair(result, "R", "H")
    assert rh.left_only.additional_true_positive_case_ids == ()
    assert rh.left_only.additional_false_positive_case_ids == ()
    assert rh.right_only.additional_true_positive_case_ids == ("synthetic-1",)
    assert rh.right_only.additional_false_positive_case_ids == ("synthetic-5",)
    assert rh.right_only.additional_true_positive_rate.value == 0.25
    assert rh.right_only.additional_false_positive_rate.value == 0.25
    assert rh.right_metrics.recall.value == 0.75
    assert rh.right_metrics.false_positive_rate.value == 0.5


def test_b_unavailable_does_not_empty_r_h_pair_while_common_support_is_empty():
    records = tuple(r.model_copy(update={"b": UNAVAILABLE, "b_score": None}) for r in cases())
    source = evaluate_records(records, config())
    assert source.strata[0].coverage.principal_case_ids == ()
    result = evaluate_pairwise(source)
    assert result.strata[0].common_case_ids == ()
    rh = get_pair(result, "R", "H")
    assert len(rh.support_case_ids) == 8
    assert rh.right_only.additional_true_positive_case_ids == ("synthetic-1",)
    rb = get_pair(result, "R", "B")
    assert rb.support_case_ids == ()
    assert rb.coverage_confirmed.value == 0.0
    assert rb.left_metrics.recall.value is None
    assert rb.right_only.additional_true_positive_rate.reason == "no_divergent_pair_support"
    assert all(e.reasons == ("right_incomplete",) for e in rb.exclusions)


def test_pending_disagreement_unavailable_and_partial_h_remain_excluded_with_all_reasons():
    good = record(0, True, m=True)
    pending = record(1, False).model_copy(update={"oracle_state": "pending", "oracle_label": None})
    disagreement = record(2, False).model_copy(
        update={"oracle_state": "disagreement", "oracle_label": None}
    )
    partial = record(3, True, r=True).model_copy(
        update={
            "m": UNAVAILABLE,
            "m_score": None,
            "h": ComponentDecision(
                decision="alert", complete=False, reason="incomplete_components"
            ),
        }
    )
    failed = record(4, False).model_copy(
        update={
            "oracle_state": "not_evaluable",
            "oracle_label": None,
            "r": UNAVAILABLE,
            "m": UNAVAILABLE,
            "b": UNAVAILABLE,
            "h": UNAVAILABLE,
            "m_score": None,
            "b_score": None,
            "pipeline_sha256": None,
            "detector_bundle_sha256": None,
            "failure_reason": "synthetic_execution_failure",
        }
    )
    result = evaluate_pairwise(
        evaluate_records((good, pending, disagreement, partial, failed), config())
    )
    rh = get_pair(result, "R", "H")
    assert rh.support_case_ids == ("synthetic-0",)
    assert rh.right_partial_alert_case_ids == ("synthetic-3",)
    assert (rh.divergent_cases, rh.normal_cases) == (1, 0)
    assert (rh.coverage_confirmed.numerator, rh.coverage_confirmed.denominator) == (1, 2)
    assert (rh.coverage_scheduled.numerator, rh.coverage_scheduled.denominator) == (1, 5)
    assert rh.right_only.additional_false_positive_rate.value is None
    assert rh.exclusions[-1].reasons == (
        "oracle_unconfirmed",
        "left_incomplete",
        "right_incomplete",
    )
    assert rh.exclusions[-1].oracle_state == "not_evaluable"
    assert rh.exclusions[-2].reasons == ("right_incomplete",)
    assert get_pair(result, "R", "B").support_case_ids == ("synthetic-0", "synthetic-3")


def test_declared_empty_scopes_and_no_labels_keep_explicit_undefined_denominators():
    pending = record(0, True).model_copy(update={"oracle_state": "pending", "oracle_label": None})
    result = evaluate_pairwise(evaluate_records((pending,), config()))
    rm = get_pair(result, "R", "M")
    assert rm.support_case_ids == ()
    assert rm.coverage_confirmed.reason == "no_confirmed_labels"
    assert rm.coverage_scheduled.value == 0.0
    empty = next(s for s in result.strata if s.kind == "family" and s.family == "dates")
    assert empty.total_cases == 0
    assert empty.pairs[0].coverage_scheduled.reason == "no_scheduled_cases"
    assert empty.pairs[0].left_metrics.precision.value is None
    assert evaluate_pairwise(evaluate_records((), config())).strata[0].total_cases == 0


def test_family_migration_scopes_do_not_pool_different_supports_or_groups():
    source = evaluate_records(
        (record(0, True, m=True), record(1, False, family="dates", migration="pandas-duckdb")),
        config(),
    )
    result = evaluate_pairwise(source)
    actual = {
        (s.family, s.migration): s.pairs[0].support_case_ids
        for s in result.strata
        if s.kind == "family_migration"
    }
    assert actual == {
        ("joins", "pandas-polars"): ("synthetic-0",),
        ("dates", "pandas-duckdb"): ("synthetic-1",),
        ("joins", "pandas-duckdb"): (),
        ("dates", "pandas-polars"): (),
    }


def test_permutation_determinism_and_original_protocol_six_csv_are_unchanged():
    source = evaluate_records(cases(), config())
    source_bytes = source.model_dump_json()
    original_tables = table_payloads(source)
    first = evaluate_pairwise(source)
    second = evaluate_pairwise(evaluate_records(tuple(reversed(cases())), config()))
    assert first == second
    assert first.evaluation_sha256 == digest(source)
    assert first.protocol_sha256 == source.protocol_sha256
    assert first.analysis_policy_sha256 == pairwise_policy_sha256()
    assert source.model_dump_json() == source_bytes
    assert table_payloads(source) == original_tables
    assert tuple(original_tables) == (
        "coverage.csv",
        "metrics.csv",
        "average_precision.csv",
        "incremental.csv",
        "bootstrap.csv",
        "cases.csv",
    )
    assert not first.scientific and first.analysis_role == "supplementary_descriptive"


def test_final_source_binding_never_promotes_supplementary_report_to_scientific():
    freeze = sha("synthetic-final-binding-not-an-approved-study")
    options = config().model_copy(update={"mode": "final", "freeze_sha256": freeze})
    source = evaluate_records(
        tuple(r.model_copy(update={"freeze_sha256": freeze}) for r in cases()), options
    )
    assert source.scientific
    result = evaluate_pairwise(source)
    assert result.evaluation.scientific and not result.scientific
    assert result.evaluation.config.freeze_sha256 == freeze


def test_modified_original_and_derived_counts_are_rejected_even_for_model_copy():
    source = evaluate_records(cases(), config())
    broken_metrics = source.strata[0].methods[0].principal.model_copy(update={"tp": 700})
    broken_method = source.strata[0].methods[0].model_copy(update={"principal": broken_metrics})
    broken_stratum = source.strata[0].model_copy(
        update={"methods": (broken_method, *source.strata[0].methods[1:])}
    )
    broken = source.model_copy(update={"strata": (broken_stratum, *source.strata[1:])})
    with pytest.raises(ValidationError, match="report disagrees"):
        evaluate_pairwise(broken)
    paired = evaluate_pairwise(source)
    payload = paired.model_dump(mode="json")
    payload["strata"][0]["pairs"][0]["left_metrics"]["tp"] = 700
    with pytest.raises(ValidationError, match="pairwise report disagrees"):
        PairwiseReport.model_validate_json(json.dumps(payload))
    with pytest.raises(ValidationError, match="pairwise report disagrees"):
        PairwiseReport.model_validate(paired.model_copy(update={"protocol_sha256": sha("other")}))


def test_explicit_json_export_and_example_from_installed_package(tmp_path: Path):
    source = evaluate_records(cases(), config())
    source_path = tmp_path / "evaluation.json"
    output = tmp_path / "paired.json"
    save_document(source, source_path)
    example = Path(__file__).parents[1] / "examples" / "pairwise_evaluation.py"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(example),
            "--evaluation",
            str(source_path),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    summary = json.loads(completed.stdout)
    assert summary["scientific"] is False
    assert summary["pairs"]["R-H"] == 8
    assert load_document(PairwiseReport, output) == evaluate_pairwise(source)
    with pytest.raises(FileExistsError):
        save_document(evaluate_pairwise(source), output)
