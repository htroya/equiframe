"""Independent counterexamples, preconditions and cooperative resource behavior."""

import hashlib
import json
from decimal import Decimal

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.errors import ArtifactIntegrityError


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
    assert ef.read_reduction(tmp_path / result.reduction_id) == result
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
        assert ef.read_reduction(tmp_path / result.reduction_id) == result


def test_callback_errors_never_become_accepted_and_secrets_not_recorded(tmp_path):
    def fail(_):
        raise RuntimeError("secret-do-not-log")

    result = reduce(tmp_path, predicate=fail)
    assert result.status == "evaluation_failed" and result.evaluations == 1
    assert not result.baseline_verified
    assert ef.read_reduction(tmp_path / result.reduction_id) == result
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
    assert ef.read_reduction(tmp_path / result.reduction_id) == result


def test_late_callback_and_nondeterministic_confirmation(tmp_path, monkeypatch):
    import equiframe.reduction as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])

    def slow(tables):
        clock[0] += 11.0
        return predicate(tables)

    result = reduce(tmp_path, predicate=slow, options=ef.ReductionOptions(timeout_seconds=10.0))
    assert result.status == "budget_exhausted" and not result.baseline_verified
    assert ef.read_reduction(tmp_path / result.reduction_id) == result
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
    assert ef.read_reduction(tmp_path / result.reduction_id) == result


def test_empty_counterexample_and_excess_input(tmp_path):
    result = reduce(
        tmp_path,
        predicate=lambda _: ef.ReductionObservation(
            preconditions="satisfied", failure_signature="duplicate.id"
        ),
    )
    assert result.minimality == "one_minimal"
    assert all(not t.retained_positions for t in result.tables)
    assert ef.read_reduction(tmp_path / result.reduction_id) == result
    with pytest.raises(ValueError, match="row budget"):
        reduce(tmp_path, options=ef.ReductionOptions(max_input_rows=1))


def _single_table_reduction(tmp_path):
    return ef.reduce_case(
        {"data": ef.ArrowInput(pa.table({"id": [1, 2, 3]}))},
        predicate=lambda tables: ef.ReductionObservation(
            preconditions="satisfied",
            failure_signature="target.failure"
            if 2 in tables["data"].table["id"].to_pylist()
            else None,
        ),
        predicate_version="synthetic.1",
        failure_signature="target.failure",
        work_dir=tmp_path,
    )


@pytest.mark.parametrize(
    "changed", ["signature", "options", "positions", "reduced_ref", "original_rows", "status"]
)
def test_reader_rejects_manifest_claims_unlinked_to_recorded_search(tmp_path, changed):
    result = _single_table_reduction(tmp_path)
    manifest = tmp_path / result.reduction_id / "reduction.json"
    value = json.loads(manifest.read_text("utf8"))
    if changed == "signature":
        value["failure_signature"] = "never.observed"
    elif changed == "options":
        value["options"]["max_evaluations"] += 1
    elif changed == "positions":
        value["tables"][0]["retained_positions"] = [0]
    elif changed == "reduced_ref":
        value["tables"][0]["reduced"] = value["tables"][0]["original"]
    elif changed == "original_rows":
        value["tables"][0]["original_rows"] += 1
    else:
        value["status"] = "unchanged"
    manifest.write_text(json.dumps(value), encoding="utf8")
    with pytest.raises(ArtifactIntegrityError):
        ef.read_reduction(manifest)


@pytest.mark.parametrize("changed", ["observation", "selection", "missing_inventory"])
def test_reader_links_attempt_contents_to_journal_and_final_rows(tmp_path, changed):
    result = _single_table_reduction(tmp_path)
    directory = tmp_path / result.reduction_id
    manifest = directory / "reduction.json"
    value = json.loads(manifest.read_text("utf8"))
    relative = (
        "attempt-000001/observation.json"
        if changed == "observation"
        else "attempt-000001/selection.json"
    )
    if changed == "missing_inventory":
        value["evidence"] = [item for item in value["evidence"] if item["path"] != relative]
    else:
        file = directory / relative
        content = json.loads(file.read_text("utf8"))
        if changed == "observation":
            content["failure_signature"] = None
        else:
            content["positions"]["data"] = [1]
        data = json.dumps(content).encode("utf8")
        file.write_bytes(data)
        for item in value["evidence"]:
            if item["path"] == relative:
                item["sha256"] = hashlib.sha256(data).hexdigest()
                item["size_bytes"] = len(data)
    manifest.write_text(json.dumps(value), encoding="utf8")
    with pytest.raises(ArtifactIntegrityError):
        ef.read_reduction(manifest)


def test_reader_rejects_external_artifact_even_with_matching_bytes(tmp_path):
    result = _single_table_reduction(tmp_path)
    directory = tmp_path / result.reduction_id
    manifest = directory / "reduction.json"
    value = json.loads(manifest.read_text("utf8"))
    external = tmp_path / "outside.arrow"
    external.write_bytes((directory / "data.reduced.arrow").read_bytes())
    value["tables"][0]["reduced"]["uri"] = external.as_uri()
    manifest.write_text(json.dumps(value), encoding="utf8")
    with pytest.raises(ArtifactIntegrityError, match="escapes"):
        ef.read_reduction(manifest)


def test_reader_accepts_unchanged_one_minimal_input_and_faithful_arrow_values(tmp_path):
    schema = pa.schema(
        [("id", pa.int64()), ("value", pa.float64()), ("nested", pa.struct([("x", pa.int64())]))],
        metadata={b"meaning": b"retain nulls, NaN and nested data"},
    )
    table = pa.Table.from_pylist(
        [{"id": 2, "value": float("nan"), "nested": {"x": None}}], schema=schema
    )
    calls = [0]

    def reproduce(tables):
        calls[0] += 1
        return ef.ReductionObservation(
            preconditions="satisfied",
            failure_signature="target.failure" if tables["data"].table.num_rows else None,
        )

    result = ef.reduce_case(
        {"data": ef.ArrowInput(table)},
        predicate=reproduce,
        predicate_version="synthetic.1",
        failure_signature="target.failure",
        work_dir=tmp_path,
    )
    assert result.status == "unchanged" and result.minimality == "one_minimal"
    observed_calls = calls[0]
    assert ef.read_reduction(tmp_path / result.reduction_id) == result
    assert calls[0] == observed_calls
