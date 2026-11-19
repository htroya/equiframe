"""Independent negative/denominator checks for the generated benchmark."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "library_detection_run", Path(__file__).with_name("run.py")
)
assert SPEC is not None and SPEC.loader is not None
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def test_oracle_preserves_multiplicity_and_null_vs_zero():
    source = [{"id": 1, "amount": None}, {"id": 2, "amount": 0}]
    correct = evaluation.expected_rows("identity", source)
    assert not evaluation.oracle("identity", source, correct[::-1])
    assert evaluation.oracle("identity", source, correct + correct[:1])
    assert evaluation.oracle("identity", source, [{"id": 1, "amount": 0}, correct[1]])


def test_keyed_permutation_is_wrong_even_with_identical_univariate_statistics():
    source = [{"id": 1, "amount": 100}, {"id": 2, "amount": 200}]
    swapped = [{"id": 1, "amount": 200}, {"id": 2, "amount": 100}]
    assert sum(r["amount"] for r in source) == sum(r["amount"] for r in swapped)
    assert evaluation.oracle("identity", source, swapped)


def test_exact_integer_discount_oracle_rounds_per_row_before_sum():
    source = [{"department": "a", "amount": 101, "discount_bp": 1000}] * 2
    assert evaluation.expected_rows("discount_aggregation", source) == [
        {"department": "a", "total": 180}
    ]
    assert evaluation.oracle("discount_aggregation", source, [{"department": "a", "total": 181}])


def test_partition_seeds_and_sources_are_disjoint_and_repeatable():
    generated = evaluation.generated
    hashes = {
        evaluation.digest(generated("identity", split, i))
        for split in ("training", "calibration", "test_normal", "fill_null")
        for i in range(3)
    }
    assert len(hashes) == 12
    assert generated("identity", "training", 1) == generated("identity", "training", 1)


def test_unavailable_is_neither_negative_nor_true_negative():
    records = [
        {"divergent": True, "m": "alert"},
        {"divergent": True, "m": "no_alert"},
        {"divergent": False, "m": "alert"},
        {"divergent": False, "m": "no_alert"},
        {"divergent": False, "m": "not_evaluable"},
    ]
    metrics = evaluation.metrics(records, "m")
    assert (metrics["tp"], metrics["fn"], metrics["fp"], metrics["tn"], metrics["unavailable"]) == (
        1,
        1,
        1,
        1,
        1,
    )
    assert metrics["coverage"] == 0.8
    assert metrics["recall"] == metrics["false_positive_rate"] == 0.5
    assert evaluation.metrics([], "m")["recall"] is None


@pytest.mark.parametrize("successes,trials", [(0, 64), (64, 64), (3, 100)])
def test_wilson_interval_contains_observed_fraction(successes, trials):
    low, high = evaluation.wilson(successes, trials)
    assert 0 <= low <= successes / trials <= high <= 1


def test_full_plan_is_fixed_and_smoke_is_explicitly_separate():
    full = evaluation.protocol(False)
    assert (full["training"], full["calibration"], full["test_normal"], full["test_per_fault"]) == (
        256,
        256,
        256,
        64,
    )
    assert full["alpha"] == "0.05"
    assert full["primary_forest_seed"] == 7
    assert full["sensitivity_forest_seeds"] == [23, 71]
    assert evaluation.protocol(True)["purpose"] == "smoke"
