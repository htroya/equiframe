"""Independent grouped oracles across native engines and algebraic properties."""

import json
from contextlib import ExitStack
from datetime import date
from decimal import Decimal
from fractions import Fraction
from itertools import product

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

import equiframe as ef

pa = pytest.importorskip("pyarrow")


def native(frame, engine, stack):
    if engine == "arrow":
        return frame
    if engine == "pandas":
        pd = pytest.importorskip("pandas")
        return frame.to_pandas(types_mapper=pd.ArrowDtype)
    if engine == "polars":
        return pytest.importorskip("polars").from_arrow(frame)
    db = stack.enter_context(pytest.importorskip("duckdb").connect(":memory:"))
    return db.from_arrow(frame)


@pytest.mark.parametrize(
    "candidate_engine,expected_engine",
    tuple(product(("arrow", "pandas", "polars", "duckdb"), repeat=2)),
)
@pytest.mark.parametrize("kind", ("integer", "decimal", "null"))
def test_all_directed_engine_pairs(candidate_engine, expected_engine, kind):
    values_a, values_b = [90, 60, 25, 50, 7], [40, 60, 0, 50, 9]
    dtype = pa.int64()
    if kind == "decimal":
        values_a = [Decimal(value) / 100 for value in values_a]
        values_b = [Decimal(value) / 100 for value in values_b]
        dtype = pa.decimal128(12, 2)
    if kind == "null":
        values_a[2] = None
    candidate = pa.table(
        {
            "key": ["A", "A", "B", "C", "E"],
            "unit": ["USD"] * 5,
            "value": pa.array(values_a, type=dtype),
        }
    )
    expected = pa.table(
        {
            "key": ["A", "A", "B", "C", "D"],
            "unit": ["USD"] * 5,
            "value": pa.array(values_b, type=dtype),
        }
    )
    with ExitStack() as stack:
        result = ef.compare_grouped(
            native(candidate, candidate_engine, stack),
            native(expected, expected_engine, stack),
            by=("key", "unit"),
            column="value",
        )
        assert result.union_groups == 5
        assert result.added_groups == result.removed_groups == 1
        assert result.group_coverage == Fraction(3, 5)
        assert result.reference_coverage == Fraction(3, 4)
        assert result.maximum_relative_difference == Fraction(1, 2)
        assert result.comparable_groups == (2 if kind == "null" else 3)
        assert result.modified_group_proportion == (
            Fraction(1, 2) if kind == "null" else Fraction(2, 3)
        )
        assert result.unavailable_groups == (1 if kind == "null" else 0)
        assert result.changed_from_zero_groups == (0 if kind == "null" else 1)


@given(
    st.lists(st.tuples(st.integers(-1000, 1000), st.integers(-1000, 1000)), min_size=1, max_size=12)
)
@settings(max_examples=35, deadline=None)
def test_rename_duplication_swap_and_tolerance_properties(pairs):
    keys = list(range(len(pairs)))
    a = pa.table({"k": keys, "n": [x for x, _ in pairs]})
    b = pa.table({"k": keys, "n": [y for _, y in pairs]})
    result = ef.compare_grouped(a, b, by=("k",), column="n")
    modified = sum(x != y for x, y in pairs)
    finite = [Fraction(abs(x - y), abs(y)) for x, y in pairs if y]
    assert result.modified_group_proportion == Fraction(modified, len(pairs))
    assert result.maximum_relative_difference == (max(finite) if finite else None)
    renamed = ef.compare_grouped(
        a.rename_columns(["store", "sales"]),
        b.rename_columns(["store", "sales"]),
        by=("store",),
        column="sales",
    )
    doubled = ef.compare_grouped(
        pa.concat_tables([a, a]), pa.concat_tables([b, b]), by=("k",), column="n"
    )
    for other in (renamed, doubled):
        assert other.modified_group_proportion == result.modified_group_proportion
        assert other.maximum_relative_difference == result.maximum_relative_difference
        assert other.changed_from_zero_groups == result.changed_from_zero_groups
        assert other.group_coverage == result.group_coverage
    swapped = ef.compare_grouped(b, a, by=("k",), column="n")
    assert swapped.union_groups == result.union_groups
    assert swapped.modified_groups == modified
    tolerant = ef.compare_grouped(
        a,
        b,
        by=("k",),
        column="n",
        options=ef.GroupedComparisonOptions(absolute_tolerance="50", relative_tolerance="0.2"),
    )
    assert tolerant.modified_groups <= result.modified_groups
    assert tolerant.changed_from_zero_groups <= result.changed_from_zero_groups
    assert tolerant.maximum_relative_difference == result.maximum_relative_difference


@pytest.mark.parametrize("value", (True, False, 1, 0, 1.0, 0.5, "0.5", "1e0", " 1", "01"))
def test_fraction_reader_rejects_coercion(value):
    frame = pa.table({"k": ["a"], "n": [1]})
    result = ef.compare_grouped(frame, frame, by=("k",), column="n")
    payload = json.loads(result.model_dump_json())
    payload["examples"][0]["candidate_total"] = value
    with pytest.raises(ValidationError):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("wire,canonical", (("2/4", "1/2"), ("-0", "0"), ("0/99", "0")))
def test_fraction_reader_normalizes_admitted_text(wire, canonical):
    frame = pa.table({"k": ["a"], "n": [0.5 if canonical == "1/2" else 0.0]})
    result = ef.compare_grouped(frame, frame, by=("k",), column="n")
    payload = json.loads(result.model_dump_json())
    payload["examples"][0]["candidate_total"] = wire
    restored = ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))
    assert json.loads(restored.model_dump_json())["examples"][0]["candidate_total"] == canonical


def test_chunked_capture_and_consumer_ownership():
    chunked = pa.table(
        {"k": pa.chunked_array([["a"], ["a", "b"]]), "n": pa.chunked_array([[10], [20, 40]])}
    )
    result = ef.compare_grouped(
        ef.ArrowInput(chunked), chunked.combine_chunks(), by=("k",), column="n"
    )
    assert result.modified_groups == 0
    assert [group.candidate_total for group in result.examples] == [30, 40]
    assert chunked["n"].num_chunks == 2


@pytest.mark.parametrize(
    "key",
    (
        {"kind": "nan"},
        {"kind": "infinity", "value": "positive"},
        {"kind": "null"},
        {"kind": "decimal", "value": "1e999999999"},
    ),
)
def test_reader_rejects_unadmitted_keys(key):
    frame = pa.table({"k": ["a", "b"], "n": [1, 1]})
    result = ef.compare_grouped(frame, frame, by=("k",), column="n")
    payload = json.loads(result.model_dump_json())
    payload["examples"][0]["key"] = [key]
    with pytest.raises(ValidationError):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "kind,first,second", (("decimal", "1.0", "1.00"), ("float", "0.0", "-0.0"))
)
def test_reader_rejects_canonical_key_collisions(kind, first, second):
    frame = pa.table({"k": ["a", "b"], "n": [1, 1]})
    result = ef.compare_grouped(frame, frame, by=("k",), column="n")
    payload = json.loads(result.model_dump_json())
    for example, value in zip(payload["examples"], (first, second), strict=True):
        example["key"] = [{"kind": kind, "value": value}]
    with pytest.raises(ValidationError, match="unique"):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("candidate,maximum", ((2, "0"), (1, "1")))
def test_hidden_examples_cannot_contradict_maximum(candidate, maximum):
    result = ef.compare_grouped(
        pa.table({"k": ["a"], "n": [candidate]}),
        pa.table({"k": ["a"], "n": [1]}),
        by=("k",),
        column="n",
        options=ef.GroupedComparisonOptions(max_examples=0),
    )
    payload = json.loads(result.model_dump_json())
    payload["maximum_relative_difference"] = maximum
    with pytest.raises(ValidationError):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


def test_partial_examples_reconstruct_all_nonzero_comparable_groups():
    result = ef.compare_grouped(
        pa.table({"k": ["a", "b"], "n": [1, 3]}),
        pa.table({"k": ["a"], "n": [1]}),
        by=("k",),
        column="n",
        options=ef.GroupedComparisonOptions(max_examples=1, absolute_tolerance="2"),
    )
    payload = json.loads(result.model_dump_json())
    payload["maximum_relative_difference"] = "1"
    with pytest.raises(ValidationError, match="maximum"):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


def test_ieee_subnormal_signed_zero_and_extreme_cancellation():
    tiny = float.fromhex("0x0.0000000000001p-1022")
    frame = pa.table({"k": ["a"] * 3 + ["b", "c"], "n": [1e308, tiny, -1e308, -0.0, 0.0]})
    expected = pa.table({"k": ["a", "b", "c"], "n": [tiny, 0.0, -0.0]})
    result = ef.compare_grouped(frame, expected, by=("k",), column="n")
    assert result.modified_groups == 0
    assert result.zero_baseline_groups == 2
    assert result.examples[0].candidate_total == Fraction.from_float(tiny)


def test_cancellation_during_aggregation_never_returns_partial(monkeypatch):
    from equiframe import grouped

    token = ef.CancellationToken()
    original = grouped._Budget.check
    calls = 0

    def check(budget, cost=1):
        nonlocal calls
        calls += 1
        if calls == 12:
            token.cancel()
        return original(budget, cost)

    monkeypatch.setattr(grouped._Budget, "check", check)
    frame = pa.table({"k": ["a"] * 100, "n": [1] * 100})
    with pytest.raises(ef.ExecutionCancelled):
        ef.compare_grouped(frame, frame, by=("k",), column="n", cancellation=token)


def test_unicode_boolean_and_date_key_distinctions_survive_grouping():
    frame = pa.table(
        {
            "site": ["é", "e\u0301", "é", "é"],
            "active": [True, True, False, True],
            "day": pa.array([date(2026, 1, 1)] * 3 + [date(2026, 1, 2)], type=pa.date32()),
            "n": [1, 2, 3, 4],
        }
    )
    result = ef.compare_grouped(
        frame.take(pa.array([3, 2, 1, 0])),
        frame,
        by=("site", "active", "day"),
        column="n",
    )
    assert result.union_groups == result.common_groups == 4
    assert result.modified_groups == 0
    assert [example.candidate_total for example in result.examples] == [1, 2, 3, 4]
    assert [value.kind for value in result.examples[0].key] == ["string", "boolean", "date"]


def test_grouped_date_key_units_require_explicit_matching_schema():
    day = date(2026, 1, 1)
    a = pa.table({"k": pa.array([day], type=pa.date32()), "n": [1]})
    b = pa.table({"k": pa.array([day], type=pa.date64()), "n": [1]})
    with pytest.raises(ef.CapabilityError, match="signatures"):
        ef.compare_grouped(a, b, by=("k",), column="n")
