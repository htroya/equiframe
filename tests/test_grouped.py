"""Independent reference values for arbitrary grouped numeric comparisons."""

import json
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

import equiframe as ef

pa = pytest.importorskip("pyarrow")


def table(keys, amounts, *, key="branch", column="sales", dtype=None):
    return pa.table({key: keys, column: pa.array(amounts, type=dtype or pa.int64())})


def test_composite_keys_independent_metrics_and_reference_order():
    expected = pa.table(
        {"entidad": ["A", "A", "B", "C", "D"], "moneda": ["USD"] * 5, "monto": [40, 60, 0, 50, 9]}
    )
    candidate = pa.table(
        {"entidad": ["A", "A", "B", "C", "E"], "moneda": ["USD"] * 5, "monto": [90, 60, 25, 50, 7]}
    )
    result = ef.compare_grouped(candidate, expected, by=("entidad", "moneda"), column="monto")
    assert result.complete is True
    assert (result.candidate_groups, result.expected_groups, result.union_groups) == (4, 4, 5)
    assert (result.common_groups, result.comparable_groups, result.modified_groups) == (3, 3, 2)
    assert result.modified_group_proportion == Fraction(2, 3)
    assert result.maximum_relative_difference == Fraction(1, 2)
    assert (result.zero_baseline_groups, result.changed_from_zero_groups) == (1, 1)
    assert result.changed_from_zero_proportion == 1
    assert result.group_coverage == result.comparison_coverage == Fraction(3, 5)
    assert result.reference_coverage == Fraction(3, 4)
    assert (result.added_groups, result.removed_groups) == (1, 1)
    assert [g.state for g in result.examples] == [
        "modified",
        "modified",
        "unchanged",
        "removed",
        "added",
    ]
    assert result.examples[0].candidate_total == 150
    assert result.examples[0].expected_total == 100
    assert result.examples[1].relative_difference is None
    assert result.examples[3].candidate_total is None
    assert result.examples_complete is True
    with pytest.raises(TypeError, match="no truth value"):
        bool(result)
    encoded = result.model_dump_json()
    assert json.loads(encoded)["modified_group_proportion"] == "2/3"
    assert ef.GroupedComparisonResult.model_validate_json(encoded) == result


@pytest.mark.parametrize(
    "key,column", [("branch", "sales"), ("warehouse", "stock"), ("department", "expense")]
)
def test_arbitrary_names_single_key_and_negative_reference(key, column):
    result = ef.compare_grouped(
        table(["x", "x", "y"], [-30, -30, 5], key=key, column=column),
        table(["x", "y"], [-40, 5], key=key, column=column),
        by=[key],
        column=column,
    )
    assert result.modified_group_proportion == Fraction(1, 2)
    assert result.maximum_relative_difference == Fraction(1, 2)
    assert result.group_coverage == result.comparison_coverage == 1


def test_decimal_sums_ignore_mutable_context_and_large_integers_are_exact():
    dtype = pa.decimal128(38, 2)
    with localcontext() as context:
        context.prec = 2
        context.traps.update({signal: True for signal in context.traps})
        result = ef.compare_grouped(
            table(["a", "a"], [Decimal("100000000000000000000.01"), Decimal("0.02")], dtype=dtype),
            table(["a"], [Decimal("100000000000000000000.02")], dtype=dtype),
            by=("branch",),
            column="sales",
        )
    assert result.examples[0].absolute_difference == Fraction(1, 100)
    assert result.maximum_relative_difference == Fraction(1, 10000000000000000000002)
    result = ef.compare_grouped(
        table([1, 1], [2**63 - 1, 2**63 - 1]),
        table([1], [2**63 - 1]),
        by=("branch",),
        column="sales",
    )
    assert result.examples[0].candidate_total == 2**64 - 2
    assert result.maximum_relative_difference == 1


def test_finite_float_sums_preserve_ieee_values_and_cancellation():
    result = ef.compare_grouped(
        table(["a"] * 3, [1e20, 1.0, -1e20], dtype=pa.float64()),
        table(["a"], [1.0], dtype=pa.float64()),
        by=("branch",),
        column="sales",
    )
    assert result.examples[0].candidate_total == 1
    assert result.modified_groups == 0
    result = ef.compare_grouped(
        table(["a", "a"], [0.1, 0.2], dtype=pa.float64()),
        table(["a"], [0.3], dtype=pa.float64()),
        by=("branch",),
        column="sales",
    )
    assert result.modified_groups == 1
    assert result.examples[0].absolute_difference == Fraction(1, 2**55)


@pytest.mark.parametrize(
    "bad,issue",
    [
        (None, "null"),
        (float("nan"), "nan"),
        (float("inf"), "infinity"),
        (-float("inf"), "infinity"),
    ],
)
def test_invalid_measures_invalidate_whole_group_and_reduce_coverage(bad, issue):
    result = ef.compare_grouped(
        table(["a", "a", "b"], [10, bad, 20], dtype=pa.float64()),
        table(["a", "b"], [10, 20], dtype=pa.float64()),
        by=("branch",),
        column="sales",
    )
    assert result.complete is False
    assert (result.comparable_groups, result.unavailable_groups) == (1, 1)
    assert result.group_coverage == 1
    assert result.comparison_coverage == Fraction(1, 2)
    assert result.modified_group_proportion == result.maximum_relative_difference == 0
    group = result.examples[0]
    assert group.state == "not_evaluable"
    assert group.candidate_total is None
    assert group.expected_total == 10
    assert group.issues == ("candidate_" + issue,)


def test_zero_reference_undefined_relative_and_explicit_tolerance():
    result = ef.compare_grouped(
        table(["a", "b", "c"], [0, 5, -5]),
        table(["a", "b", "c"], [0, 0, 0]),
        by=("branch",),
        column="sales",
    )
    assert result.maximum_relative_difference is None
    assert result.changed_from_zero_groups == 2
    assert result.changed_from_zero_proportion == Fraction(2, 3)
    tolerance = ef.GroupedComparisonOptions(absolute_tolerance="5", relative_tolerance="0.1")
    result = ef.compare_grouped(
        table(["a", "b"], [5, 110]),
        table(["a", "b"], [0, 100]),
        by=("branch",),
        column="sales",
        options=tolerance,
    )
    assert result.modified_groups == result.changed_from_zero_groups == 0
    assert result.maximum_relative_difference == Fraction(1, 10)
    reverse = ef.compare_grouped(
        table(["a"], [100]),
        table(["a"], [110]),
        by=("branch",),
        column="sales",
    )
    assert reverse.maximum_relative_difference == Fraction(1, 11)


@pytest.mark.parametrize("left,right", [([], []), (["a"], []), ([], ["b"]), (["a"], ["b"])])
def test_empty_and_disjoint_groups_do_not_invent_measurements(left, right):
    result = ef.compare_grouped(
        table(left, [1] * len(left), dtype=pa.int64()).cast(
            pa.schema([("branch", pa.string()), ("sales", pa.int64())])
        ),
        table(right, [1] * len(right), dtype=pa.int64()).cast(
            pa.schema([("branch", pa.string()), ("sales", pa.int64())])
        ),
        by=("branch",),
        column="sales",
    )
    assert result.modified_group_proportion is None
    assert result.maximum_relative_difference is None
    assert result.changed_from_zero_proportion is None
    assert result.group_coverage == (0 if left or right else None)
    assert result.complete is True


def test_null_key_policy_and_nan_keys_remain_separate():
    frame = table([None, "a"], [1, 2])
    with pytest.raises(ef.CapabilityError, match="NULL grouping keys"):
        ef.compare_grouped(frame, frame, by=("branch",), column="sales")
    result = ef.compare_grouped(
        frame,
        frame,
        by=("branch",),
        column="sales",
        options=ef.GroupedComparisonOptions(null_keys="group"),
    )
    assert result.common_groups == 2
    assert result.examples[0].key[0].kind == "null"
    frame = table([float("nan")], [1])
    with pytest.raises(ef.CapabilityError, match="NaN or infinity"):
        ef.compare_grouped(frame, frame, by=("branch",), column="sales")


@pytest.mark.parametrize(
    "by,column",
    [
        ("branch", "sales"),
        ((), "sales"),
        (("branch", "branch"), "sales"),
        (("branch",), "branch"),
        (("",), "sales"),
        (("branch",), ""),
    ],
)
def test_invalid_configuration_fails_before_consumption(by, column):
    with pytest.raises(ValueError):
        ef.compare_grouped(object(), object(), by=by, column=column)


def test_missing_nonnumeric_duplicate_columns_and_key_type_drift_fail():
    frame = table(["a"], [1])
    for bad in (
        pa.table({"branch": ["a"]}),
        pa.table({"branch": ["a"], "sales": ["1"]}),
        table([1], [1]),
    ):
        with pytest.raises(ef.CapabilityError):
            ef.compare_grouped(bad, frame, by=("branch",), column="sales")
    duplicate = pa.table([["a"], [1], [1]], names=["branch", "sales", "sales"])
    with pytest.raises((ef.CapabilityError, ef.InvalidExecutionInput)):
        ef.compare_grouped(duplicate, frame, by=("branch",), column="sales")


def test_examples_do_not_limit_metrics_and_budget_failures_never_return_partial_results():
    frame = table(["a", "b"], [1, 2])
    result = ef.compare_grouped(
        frame,
        frame,
        by=("branch",),
        column="sales",
        options=ef.GroupedComparisonOptions(max_examples=0),
    )
    assert result.examples == () and result.examples_complete is False
    assert result.common_groups == 2 and result.comparison_coverage == 1
    for options in (
        ef.GroupedComparisonOptions(max_groups=1),
        ef.GroupedComparisonOptions(max_work=1),
    ):
        with pytest.raises(ef.ResourceLimitError):
            ef.compare_grouped(frame, frame, by=("branch",), column="sales", options=options)
    with pytest.raises(ef.ResourceLimitError, match="union"):
        ef.compare_grouped(
            table(["a"], [1]),
            table(["b"], [1]),
            by=("branch",),
            column="sales",
            options=ef.GroupedComparisonOptions(max_groups=1),
        )
    with pytest.raises(ef.ResourceLimitError):
        ef.compare_grouped(
            frame,
            frame,
            by=("branch",),
            column="sales",
            capture_options=ef.DiffCaptureOptions(max_rows=1),
        )
    token = ef.CancellationToken()
    token.cancel()
    with pytest.raises(ef.ExecutionCancelled):
        ef.compare_grouped(frame, frame, by=("branch",), column="sales", cancellation=token)


def test_elapsed_timeout_and_strict_options(monkeypatch):
    import equiframe.grouped as module

    ticks = iter([0.0, 2.0])
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(ticks))
    with pytest.raises(ef.ExecutionTimeout):
        ef.compare_grouped(
            object(),
            object(),
            by=("k",),
            column="v",
            options=ef.GroupedComparisonOptions(timeout_seconds=1.0),
        )
    for changes in (
        {"absolute_tolerance": -1},
        {"relative_tolerance": "-0.1"},
        {"max_groups": True},
        {"unknown": 1},
    ):
        with pytest.raises(ValidationError):
            ef.GroupedComparisonOptions(**changes)


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb", "arrow_input"])
def test_native_engine_routes_and_legacy_diff_are_compatible(engine, tmp_path):
    source = table(["a", "a", "b"], [10, 20, 40])
    if engine == "pandas":
        pytest.importorskip("pandas")
        native = source.to_pandas()
    elif engine == "polars":
        native = pytest.importorskip("polars").from_arrow(source)
    elif engine == "duckdb":
        db = pytest.importorskip("duckdb").connect(":memory:")
        native = db.from_arrow(source)
    else:
        native = ef.ArrowInput(source)
    try:
        result = ef.compare_grouped(native, source, by=("branch",), column="sales")
        assert result.modified_groups == 0
        assert result.examples[0].candidate_total == 30
        assert result.comparison_coverage == 1
        comparison = ef.diff(native, source, work_dir=tmp_path / "old-diff")
        ef.assert_equivalent(comparison)
    finally:
        if engine == "duckdb":
            assert db.execute("SELECT 1").fetchone() == (1,)
            db.close()


def test_equal_group_sums_do_not_change_row_equivalence(tmp_path):
    a, b = table(["a", "a"], [10, 20]), table(["a", "a"], [15, 15])
    assert ef.compare_grouped(a, b, by=("branch",), column="sales").modified_groups == 0
    result = ef.diff(a, b, work_dir=tmp_path / "different-rows")
    assert result.state == "different"
    with pytest.raises(ef.EquivalenceDifferentError):
        ef.assert_equivalent(result)


@given(st.lists(st.integers(min_value=-(10**12), max_value=10**12), min_size=1, max_size=40))
@settings(max_examples=30, deadline=None)
def test_sum_is_invariant_to_row_partition_and_order(amounts):
    reference = table(["store"], [sum(amounts)])
    candidate = table(["store"] * len(amounts), amounts[::-1])
    result = ef.compare_grouped(candidate, reference, by=("branch",), column="sales")
    assert result.modified_groups == 0
    assert result.maximum_relative_difference == (0 if sum(amounts) else None)


def test_composite_key_does_not_combine_different_currencies():
    expected = pa.table({"entity": ["a", "a"], "currency": ["USD", "EUR"], "amount": [10, 20]})
    candidate = pa.table({"entity": ["a", "a"], "currency": ["USD", "EUR"], "amount": [20, 10]})
    result = ef.compare_grouped(candidate, expected, by=("entity", "currency"), column="amount")
    assert result.common_groups == result.modified_groups == 2
    assert result.maximum_relative_difference == 1
    assert result.examples[1].relative_difference == Fraction(1, 2)


def test_timestamp_keys_preserve_nanosecond_identity():
    expected = pa.table({"at": pa.array([1, 2], type=pa.timestamp("ns")), "n": [10, 20]})
    candidate = pa.table({"at": pa.array([2, 1], type=pa.timestamp("ns")), "n": [20, 10]})
    result = ef.compare_grouped(candidate, expected, by=("at",), column="n")
    assert result.common_groups == 2 and result.modified_groups == 0
    assert result.examples[0].key[0].value == "1"
    assert result.examples[1].key[0].value == "2"


def test_numeric_families_compare_exact_values_without_coercing_keys():
    result = ef.compare_grouped(
        table(["a"], [Decimal("3.00")], dtype=pa.decimal128(8, 2)),
        table(["a"], [3]),
        by=("branch",),
        column="sales",
    )
    assert result.modified_groups == 0
    date32 = pa.table({"day": pa.array([0], type=pa.date32()), "n": [1]})
    date64 = pa.table({"day": pa.array([0], type=pa.date64()), "n": [1]})
    with pytest.raises(ef.CapabilityError, match="type signatures"):
        ef.compare_grouped(date32, date64, by=("day",), column="n")


def test_all_null_and_invalid_reference_groups_have_no_comparable_metrics():
    invalid = table(["a", "a"], [None, None])
    result = ef.compare_grouped(
        table(["a"], [0]),
        invalid,
        by=("branch",),
        column="sales",
    )
    assert result.complete is False
    assert result.modified_group_proportion is None
    assert result.maximum_relative_difference is None
    assert result.comparison_coverage == 0
    assert result.examples[0].expected_total is None
    assert result.examples[0].issues == ("expected_null",)


def test_missing_group_never_becomes_zero_even_with_invalid_measure():
    result = ef.compare_grouped(
        table(["a"], [None]),
        table(["b"], [0]),
        by=("branch",),
        column="sales",
    )
    assert result.changed_from_zero_groups == result.comparable_groups == 0
    assert result.modified_group_proportion is None
    assert result.group_coverage == 0
    assert result.examples[1].state == "added"
    assert result.examples[1].issues == ("candidate_null",)


@pytest.mark.parametrize(
    "changes",
    [
        {"modified_groups": 0},
        {"group_coverage": Fraction(1, 2)},
        {"maximum_relative_difference": Fraction(2)},
        {"complete": False},
        {"examples_complete": False},
        {"zero_baseline_groups": 1},
    ],
)
def test_result_models_reject_inconsistent_serialized_summary(changes):
    result = ef.compare_grouped(
        table(["a"], [20]),
        table(["a"], [10]),
        by=("branch",),
        column="sales",
    )
    original = result.model_dump_json()
    assert ef.GroupedComparisonResult.model_validate_json(original) == result
    payload = json.loads(original)
    payload.update(
        {
            name: str(value) if isinstance(value, Fraction) else value
            for name, value in changes.items()
        }
    )
    with pytest.raises(ValidationError):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


def test_partial_examples_still_constrain_summary_counts():
    result = ef.compare_grouped(
        table(["a", "b"], [20, 30]),
        table(["a", "b"], [10, 30]),
        by=("branch",),
        column="sales",
        options=ef.GroupedComparisonOptions(max_examples=1, absolute_tolerance="1"),
    )
    assert result.examples_complete is False and result.examples[0].state == "modified"
    original = result.model_dump_json()
    assert ef.GroupedComparisonResult.model_validate_json(original) == result
    payload = json.loads(original)
    payload.update(modified_groups=0, modified_group_proportion="0")
    with pytest.raises(ValidationError, match="examples contradict"):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("value", ["1e1000000", "1e-1000000", "9" * 1001])
@pytest.mark.parametrize("field", ["absolute_tolerance", "relative_tolerance"])
def test_tolerance_rejects_excessive_precision_before_rational_allocation(value, field):
    with pytest.raises(ValidationError, match="1000"):
        ef.GroupedComparisonOptions(**{field: value})


@pytest.mark.parametrize("value", ["1e999", "1e-1000", "9" * 1000, "9." + "9" * 1000])
def test_tolerance_admits_documented_precision_boundary(value):
    options = ef.GroupedComparisonOptions(absolute_tolerance=value)
    assert options.absolute_tolerance == Decimal(value)


def test_partial_nonzero_examples_constrain_zero_baseline_count():
    result = ef.compare_grouped(
        table(["a", "b", "c"], [10, 10, 10]),
        table(["a", "b", "c"], [10, 10, 10]),
        by=("branch",),
        column="sales",
        options=ef.GroupedComparisonOptions(max_examples=2),
    )
    payload = json.loads(result.model_dump_json())
    payload.update(zero_baseline_groups=2, changed_from_zero_proportion="0")
    with pytest.raises(ValidationError, match="examples contradict"):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


def test_summary_zero_modified_counts_must_have_a_possible_joint_distribution():
    result = ef.compare_grouped(
        table(["a", "b"], [1, 1]),
        table(["a", "b"], [0, 0]),
        by=("branch",),
        column="sales",
        options=ef.GroupedComparisonOptions(max_examples=0),
    )
    payload = json.loads(result.model_dump_json())
    payload.update(changed_from_zero_groups=1, changed_from_zero_proportion="1/2")
    with pytest.raises(ValidationError, match="inconsistent group counts"):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


def test_unretained_groups_still_require_observed_rows():
    frame = table(["a"] * 5 + ["b", "c"], [1] * 7)
    result = ef.compare_grouped(
        frame,
        frame,
        by=("branch",),
        column="sales",
        options=ef.GroupedComparisonOptions(max_examples=1),
    )
    payload = json.loads(result.model_dump_json())
    payload["candidate_rows"] = 5
    with pytest.raises(ValidationError, match="remaining groups require"):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("value", ["1e1000000", "1e-1000000", "1/0", "9" * 4097, "1/" + "9" * 2000])
def test_result_json_rejects_unbounded_or_noncanonical_fraction_text(value):
    result = ef.compare_grouped(
        table(["a"], [20]),
        table(["a"], [10]),
        by=("branch",),
        column="sales",
    )
    payload = json.loads(result.model_dump_json())
    payload["examples"][0]["candidate_total"] = value
    with pytest.raises(ValidationError):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("scale", [-5000, -1, 39])
@pytest.mark.parametrize("name", ["branch", "sales"])
def test_unadmitted_arrow_decimal_scale_has_a_typed_error(scale, name):
    value = pa.Array.from_buffers(
        pa.decimal128(38, scale),
        1,
        [None, pa.py_buffer((1).to_bytes(16, "little", signed=True))],
    )
    frame = pa.table({"branch": [1], "sales": [1]}).set_column(
        0 if name == "branch" else 1, name, value
    )
    with pytest.raises(ef.CapabilityError, match="Decimal scale"):
        ef.compare_grouped(frame, frame, by=("branch",), column="sales")


def test_capture_rejects_meaningful_index_metadata_and_small_byte_limit():
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"branch": ["a"], "sales": [1]}, index=pd.Index(["row"], name="id"))
    with pytest.raises(ef.CapabilityError, match="indices"):
        ef.compare_grouped(frame, frame, by=("branch",), column="sales")
    arrow = table(["a"], [1])
    with pytest.raises(ef.ResourceLimitError):
        ef.compare_grouped(
            arrow,
            arrow,
            by=("branch",),
            column="sales",
            capture_options=ef.DiffCaptureOptions(max_bytes=1),
        )
    decorated = arrow.replace_schema_metadata({"unit": "USD"})
    with pytest.raises(ef.CapabilityError, match="metadata"):
        ef.compare_grouped(decorated, arrow, by=("branch",), column="sales")


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"key": []}, id="empty-key"),
        pytest.param({"candidate_rows": 0, "expected_rows": 0}, id="no-observed-rows"),
        pytest.param({"issues": ["candidate_null", "candidate_null"]}, id="duplicate-issues"),
        pytest.param({"issues": ["candidate_invalid"]}, id="unknown-issue"),
        pytest.param({"candidate_rows": 0}, id="total-on-absent-side"),
        pytest.param({"candidate_total": None}, id="missing-valid-total"),
        pytest.param(
            {"candidate_total": None, "issues": ["candidate_null"]},
            id="invalid-group-claims-comparability",
        ),
        pytest.param({"absolute_difference": "0"}, id="false-exact-difference"),
        pytest.param({"state": "added"}, id="unpaired-group-claims-numeric-difference"),
        pytest.param(
            {"state": "added", "absolute_difference": None, "relative_difference": None},
            id="added-group-present-in-reference",
        ),
        pytest.param(
            {"state": "removed", "absolute_difference": None, "relative_difference": None},
            id="removed-group-present-in-candidate",
        ),
        pytest.param(
            {"state": "not_evaluable", "absolute_difference": None, "relative_difference": None},
            id="unavailable-group-without-invalid-measure",
        ),
        pytest.param({"key": [{"kind": "integer", "value": "9" * 4097}]}, id="key-text-limit"),
        pytest.param({"key": [{"kind": "decimal", "value": "9" * 77}]}, id="key-precision-limit"),
        pytest.param(
            {"key": [{"kind": "decimal", "value": "0." + "1" * 77}]}, id="key-scale-limit"
        ),
    ],
)
def test_standalone_group_reader_rejects_impossible_presence_and_measure_evidence(changes):
    # A hand-written valid group: candidate 2, reference 1, exact delta and ratio 1.
    payload = {
        "key": [{"kind": "string", "value": "a"}],
        "state": "modified",
        "candidate_rows": 1,
        "expected_rows": 1,
        "candidate_total": "2",
        "expected_total": "1",
        "absolute_difference": "1",
        "relative_difference": "1",
        "issues": [],
    }
    valid = ef.GroupedDifference.model_validate_json(json.dumps(payload))
    assert valid.candidate_total == 2 and valid.expected_total == valid.absolute_difference == 1
    payload.update(changes)
    with pytest.raises(ValidationError):
        ef.GroupedDifference.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate-grouping-column",
        "measure-is-grouping-column",
        "missing-supported-maximum",
        "example-bound",
        "key-width",
        "mixed-key-types",
        "classification-vs-tolerance",
        "example-above-maximum",
    ],
)
def test_summary_reader_rejects_contradictory_structure_and_retained_metrics(mutation):
    result = ef.compare_grouped(
        table(["a", "b"], [2, 2]), table(["a", "b"], [1, 1]), by=("branch",), column="sales"
    )
    assert result.common_groups == result.modified_groups == 2
    assert result.maximum_relative_difference == 1
    payload = json.loads(result.model_dump_json())
    if mutation == "duplicate-grouping-column":
        payload["by"] = ["branch", "branch"]
    elif mutation == "measure-is-grouping-column":
        payload["column"] = "branch"
    elif mutation == "missing-supported-maximum":
        payload["maximum_relative_difference"] = None
    elif mutation == "example-bound":
        payload["options"]["max_examples"] = 1
    elif mutation == "key-width":
        payload["examples"][0]["key"].append({"kind": "string", "value": "extra"})
    elif mutation == "mixed-key-types":
        payload["examples"][1]["key"] = [{"kind": "integer", "value": "2"}]
    elif mutation == "classification-vs-tolerance":
        payload["examples"][0]["state"] = "unchanged"
    else:
        payload["maximum_relative_difference"] = "1/2"
    with pytest.raises(ValidationError):
        ef.GroupedComparisonResult.model_validate_json(json.dumps(payload))
