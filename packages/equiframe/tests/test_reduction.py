"""Independent counterexamples, preconditions and cooperative resource behavior."""

from decimal import Decimal

import pyarrow as pa
import pytest

import equiframe as ef


def inputs():
    return {
        "orders": ef.ArrowInput(pa.table({"id": [1, 2, 3, 2, 4], "amount": [Decimal("1.10")] * 5})),
        "dimension": ef.ArrowInput(pa.table({"id": [1, 2, 3, 4]})),
    }


def predicate(tables):
    keys = tables["orders"].table["id"].to_pylist()
    dimension = tables["dimension"].table["id"].to_pylist()
    if not set(keys) <= set(dimension):
        return ef.ReductionObservation(preconditions="violated")
    return ef.ReductionObservation(
        preconditions="satisfied", failure_signature="duplicate.id" if keys.count(2) >= 2 else None
    )


def reduce(tmp_path, **kwargs):
    return ef.reduce_case(
        inputs(),
        predicate=kwargs.pop("predicate", predicate),
        predicate_version="synthetic.1",
        failure_signature="duplicate.id",
        work_dir=tmp_path,
        **kwargs,
    )


def test_multitable_reduction_preserves_preconditions_decimals_and_duplicates(tmp_path):
    original = inputs()
    result = reduce(tmp_path)
    assert result.status == "reduced" and result.minimality == "one_minimal"
    assert result.baseline_verified and not result.global_minimum_claimed
    reduced = {t.name: ef.ArrowInput(ef.read_table(t.reduced)) for t in result.tables}
    assert predicate(reduced).failure_signature == "duplicate.id"
    assert reduced["orders"].table.to_pylist() == [
        {"id": 2, "amount": Decimal("1.10")},
        {"id": 2, "amount": Decimal("1.10")},
    ]
    assert reduced["dimension"].table.to_pylist() == [{"id": 2}]
    assert reduced["orders"].table.schema == original["orders"].table.schema
    assert original["orders"].table.num_rows == 5
    assert ef.read_reduction(tmp_path / result.reduction_id) == result
    for item in result.tables:
        rows = reduced[item.name].table
        for index in range(rows.num_rows):
            probe = dict(reduced)
            probe[item.name] = ef.ArrowInput(
                rows.take(
                    pa.array([i for i in range(rows.num_rows) if i != index], type=pa.int64())
                )
            )
            assert predicate(probe).failure_signature != "duplicate.id"


@pytest.mark.parametrize("budget", [1, 2, 3, 7])
def test_budget_is_exact_and_never_claims_minimum(tmp_path, budget):
    result = reduce(tmp_path, options=ef.ReductionOptions(max_evaluations=budget))
    assert result.status == "budget_exhausted" and result.evaluations == budget
    assert result.minimality == "not_established"
    assert not result.global_minimum_claimed
    if result.baseline_verified:
        assert (
            predicate(
                {t.name: ef.ArrowInput(ef.read_table(t.reduced)) for t in result.tables}
            ).failure_signature
            == "duplicate.id"
        )


def test_invalid_baseline_wrong_failure_and_unavailable_preconditions(tmp_path):
    for observation in (
        ef.ReductionObservation(preconditions="not_evaluable"),
        ef.ReductionObservation(preconditions="satisfied", failure_signature="other"),
    ):
        result = reduce(tmp_path, predicate=lambda _, observation=observation: observation)
        assert result.status == "invalid_baseline" and not result.baseline_verified
        assert result.accepted_candidates == 0 and result.minimality == "not_established"


def test_callback_errors_never_become_accepted_and_secrets_not_recorded(tmp_path):
    def fail(_):
        raise RuntimeError("secret-do-not-log")

    result = reduce(tmp_path, predicate=fail)
    assert result.status == "evaluation_failed" and result.evaluations == 1
    assert not result.baseline_verified
    for path in (tmp_path / result.reduction_id).rglob("*.json*"):
        assert "secret-do-not-log" not in path.read_text("utf8")


def test_cancellation_during_callback_rejects_candidate(tmp_path):
    token = ef.CancellationToken()

    def cancel(tables):
        token.cancel()
        return predicate(tables)

    result = reduce(tmp_path, predicate=cancel, cancellation=token)
    assert result.status == "cancelled" and result.evaluations == 1
    assert not result.baseline_verified and not result.accepted_candidates


def test_late_callback_and_nondeterministic_confirmation(tmp_path, monkeypatch):
    import equiframe.reduction as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])

    def slow(tables):
        clock[0] += 11.0
        return predicate(tables)

    result = reduce(tmp_path, predicate=slow, options=ef.ReductionOptions(timeout_seconds=10.0))
    assert result.status == "budget_exhausted" and not result.baseline_verified
    calls = [0]

    def flaky(tables):
        calls[0] += 1
        return (
            predicate(tables)
            if calls[0] % 2
            else ef.ReductionObservation(preconditions="satisfied")
        )

    result = reduce(tmp_path, predicate=flaky)
    assert result.status == "invalid_baseline" and result.evaluations == 2


def test_empty_counterexample_and_excess_input(tmp_path):
    result = reduce(
        tmp_path,
        predicate=lambda _: ef.ReductionObservation(
            preconditions="satisfied", failure_signature="duplicate.id"
        ),
    )
    assert result.minimality == "one_minimal"
    assert all(not t.retained_positions for t in result.tables)
    with pytest.raises(ValueError, match="row budget"):
        reduce(tmp_path, options=ef.ReductionOptions(max_input_rows=1))
