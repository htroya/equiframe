"""Public direct-diff acceptance: independent expectations and kernel parity.

These tests deliberately construct small expected answers without consulting
inference, the comparator, or another native engine. Core parity is an additional
check, never the oracle for whether a case should pass.
"""

import itertools
import json
import math
import os
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

import equiframe as ef

NATIVE_KINDS = ("arrow", "pandas", "polars")


def native(table, kind):
    if kind == "arrow":
        return table
    if kind == "pandas":
        # Arrow-backed dtypes preserve NULL independently of IEEE NaN.
        return table.to_pandas(types_mapper=pd.ArrowDtype)
    return pl.from_arrow(table)


def column(name="value", kind=None, **overrides):
    kind = kind or ef.IntegerType(bits=64, signed=True)
    fields = dict(
        name=name,
        logical_type=kind,
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
    )
    if kind.kind in ("integer", "float", "decimal"):
        fields["numeric_policy"] = ef.NumericPolicy(comparison="exact", unit="unspecified")
    if kind.kind == "float":
        fields["nan_policy"] = ef.NaNPolicy(handling="distinct")
    if kind.kind == "date":
        fields["temporal_policy"] = ef.DatePolicy(closed="both")
    if kind.kind == "timestamp":
        fields["temporal_policy"] = ef.TimestampPolicy(
            granularity=kind.unit,
            timezone=kind.timezone,
            naive="reject" if kind.timezone else "preserve",
            comparison="instant" if kind.timezone else "wall_time",
            ambiguous="reject",
            closed="both",
        )
    return ef.ColumnSpec(**(fields | overrides))


def values(items, dtype=None):
    return pa.table({"value": pa.array(items, type=dtype or pa.int64())})


def differences(result):
    return tuple(ef.iter_differences(result.differences))


def codes(result):
    return {item.code for item in differences(result)}


def semantic_result(result):
    """Exclude only run identity, physical provenance, clock and resource measurements."""
    return dict(
        spec=result.spec,
        contract_sha256=result.contract_sha256,
        spec_sha256=result.spec_sha256,
        state=result.state,
        complete=result.complete,
        reference=result.reference,
        strategy=result.strategy,
        selected_key=result.selected_key,
        counts=result.counts,
        options=result.options,
        applied_policies=result.applied_policies,
        diagnostics=result.diagnostics,
        examples=result.examples,
        differences=differences(result),
    )


def assert_persisted(result, directory):
    assert ef.read_comparison(directory / result.comparison_id / "comparison.json") == result
    declaration = ef.read_diff_contract(result)
    assert declaration.spec == result.spec
    assert declaration.reference == result.reference
    assert not list(directory.rglob("work.sqlite*"))
    assert not list(directory.rglob("*.part"))
    return declaration


def assert_parity(result, left, right, directory):
    left = ef.ArrowInput(left) if isinstance(left, pa.Table) else left
    right = ef.ArrowInput(right) if isinstance(right, pa.Table) else right
    comparison = ef.compare(
        left,
        right,
        contract=result.spec.contract,
        policy=result.spec.policy,
        reference=result.reference,
        options=result.options,
        work_dir=directory,
    )
    assert semantic_result(result) == semantic_result(comparison)
    assert not list(directory.rglob("work.sqlite*"))


@pytest.mark.parametrize("left_kind,right_kind", tuple(itertools.product(NATIVE_KINDS, repeat=2)))
@pytest.mark.parametrize("changed", (False, True))
def test_native_cross_product_has_independent_keyed_money_expectation(
    tmp_path, left_kind, right_kind, changed
):
    schema = pa.schema(
        [
            ("tenant", pa.int64()),
            ("id", pa.int64()),
            ("amount", pa.decimal128(18, 2)),
            ("at", pa.timestamp("ns", "UTC")),
        ]
    )
    left = pa.Table.from_pylist(
        [
            {"tenant": 1, "id": 7, "amount": Decimal("999.00" if changed else "10.00"), "at": 1},
            {"tenant": 2, "id": 7, "amount": Decimal("20.00"), "at": 2},
            {"tenant": 1, "id": 8, "amount": None, "at": None},
        ],
        schema=schema,
    )
    right = pa.Table.from_pylist(
        [
            {"tenant": 1, "id": 8, "amount": None, "at": None},
            {"tenant": 1, "id": 7, "amount": Decimal("10.00"), "at": 1},
            {"tenant": 2, "id": 7, "amount": Decimal("20.00"), "at": 2},
        ],
        schema=schema,
    )
    result = ef.diff(
        native(left, left_kind),
        native(right, right_kind),
        keys=["tenant", "id"],
        options=ef.ComparisonOptions(batch_rows=1),
        work_dir=tmp_path / "direct",
    )
    assert result.reference == "expected"
    assert result.state == ("different" if changed else "equivalent")
    assert result.complete and result.counts.final and result.strategy == "key"
    assert result.counts.left_rows == result.counts.right_rows == 3
    assert result.counts.contract_violations == 0
    assert result.counts.difference_records == int(changed)
    if changed:
        (difference,) = differences(result)
        assert difference.code == "cell_value" and difference.column == "amount"
        assert [item.value for item in difference.key] == ["1", "7"]
        assert [item.value for item in difference.left] == ["999.00"]
        assert [item.value for item in difference.right] == ["10.00"]
    else:
        assert result.counts.matched_rows == 3
    assert_persisted(result, tmp_path / "direct")
    assert_parity(result, left, right, tmp_path / "core")


@pytest.mark.parametrize("left_kind,right_kind", tuple(itertools.product(NATIVE_KINDS, repeat=2)))
def test_typed_empty_native_cross_product(tmp_path, left_kind, right_kind):
    empty = pa.table(
        {
            "value": pa.array([], type=pa.int32()),
            "amount": pa.array([], type=pa.decimal128(12, 2)),
            "at": pa.array([], type=pa.timestamp("ns", "UTC")),
        }
    )
    result = ef.diff(native(empty, left_kind), native(empty, right_kind), work_dir=tmp_path)
    assert result.state == "equivalent" and result.complete
    assert result.counts == ef.ComparisonCounts(final=True)
    assert result.strategy == "multiset"
    assert_parity(result, empty, empty, tmp_path / "core")


def test_schema_only_inference_preserves_types_and_declares_conservative_defaults():
    schema = pa.schema(
        [
            pa.field("id", pa.uint32(), nullable=False),
            pa.field("amount", pa.decimal128(18, 4), nullable=False),
            pa.field("ratio", pa.float32(), nullable=False),
            pa.field("label", pa.string(), nullable=False),
            pa.field("day", pa.date32(), nullable=False),
            pa.field("local", pa.timestamp("us"), nullable=False),
            pa.field("instant", pa.timestamp("ns", "America/Guayaquil"), nullable=False),
        ]
    )
    declaration = ef.infer_diff_contract(schema)
    output = declaration.spec.contract.output.schema_spec
    assert output.columns == (
        column("id", ef.IntegerType(bits=32, signed=False)),
        column("amount", ef.DecimalType(precision=18, scale=4)),
        column("ratio", ef.FloatType(bits=32)),
        column("label", ef.StringType()),
        column("day", ef.DateType()),
        column("local", ef.TimestampType(unit="us", timezone=None)),
        column("instant", ef.TimestampType(unit="ns", timezone="America/Guayaquil")),
    )
    assert declaration.reference == "expected"
    assert output.keys == () and output.multiplicity == "preserve"
    assert output.order == ef.IgnoredOrder()
    assert declaration.spec.policy == ef.ComparisonPolicy()
    assert (
        declaration.provenance_for(
            "/spec/contract/output/schema_spec/columns/0/logical_type/kind"
        ).origin
        == "metadata"
    )
    assert (
        declaration.provenance_for("/spec/contract/output/schema_spec/columns/0/nullable").origin
        == "default"
    )
    assert declaration.provenance_for("/spec/policy/index").origin == "default"
    assert all(item.path.startswith("/") and item.detail for item in declaration.provenance)
    assert len({item.path for item in declaration.provenance}) == len(declaration.provenance)


def test_inference_uses_expected_schema_only_and_never_infers_keys_from_unique_rows(tmp_path):
    expected = values([1, 2], pa.int32())
    candidate = values([1, 2], pa.int64())
    result = ef.diff(candidate, expected, work_dir=tmp_path)
    schema = result.spec.contract.output.schema_spec
    assert schema.columns[0].logical_type == ef.IntegerType(bits=32, signed=True)
    assert schema.keys == () and schema.columns[0].nullable
    assert result.state == "different" and result.complete
    assert "logical_type" in codes(result)
    other = ef.diff(values([99, None], pa.int64()), expected, work_dir=tmp_path)
    assert other.spec == result.spec
    assert ef.read_diff_contract(other) == ef.read_diff_contract(result)
    assert_parity(result, candidate, expected, tmp_path / "core")


def test_typed_override_is_explicit_and_preserves_other_inference():
    override = column(
        "amount",
        ef.DecimalType(precision=18, scale=2),
        nullable=False,
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
    )
    declaration = ef.infer_diff_contract(
        pa.schema([("id", pa.int64()), ("amount", pa.decimal128(18, 2))]),
        keys=["id"],
        column_overrides=[override],
    )
    schema = declaration.spec.contract.output.schema_spec
    assert schema.columns[1] == override
    assert schema.columns[0] == column("id")
    assert schema.keys[0].columns == ("id",)
    assert (
        declaration.provenance_for(
            "/spec/contract/output/schema_spec/columns/1/numeric_policy/unit"
        ).origin
        == "user"
    )
    assert (
        declaration.provenance_for("/spec/contract/output/schema_spec/keys/0/columns/0").origin
        == "user"
    )
    with pytest.raises((TypeError, ValueError, ValidationError)):
        ef.infer_diff_contract(pa.schema([("id", pa.int64())]), column_overrides=[{"name": "id"}])
    with pytest.raises(ef.InvalidExecutionInput):
        ef.infer_diff_contract(pa.schema([("id", pa.int64())]), column_overrides=[override])


@pytest.mark.parametrize("builder", ("bag", "keyed", "sequence"))
def test_explicit_builders_roundtrip_contract_and_policy_without_hidden_relaxation(builder):
    columns = [column("id"), column("value")]
    policy = ef.ComparisonPolicy(column_order="ignored", justification="named output relation")
    if builder == "bag":
        declaration = ef.bag_contract(columns, policy=policy, reference="peer")
    elif builder == "keyed":
        declaration = ef.keyed_contract(columns, keys=["id"], policy=policy, reference="peer")
    else:
        declaration = ef.sequence_contract(
            columns,
            by=[ef.SortSpec(column="id", direction="ascending", nulls="last")],
            policy=policy,
            reference="peer",
        )
    assert declaration.reference == "peer" and declaration.spec.policy == policy
    schema = declaration.spec.contract.output.schema_spec
    assert schema.columns == tuple(columns) and schema.multiplicity == "preserve"
    assert declaration.spec.contract.rules == declaration.spec.contract.preconditions == ()
    assert ef.DiffContract.model_validate_json(declaration.model_dump_json()) == declaration
    assert ef.validate_contract(ef.canonical_contract_bytes(declaration.spec.contract)) == (
        declaration.spec.contract
    )
    assert (
        declaration.provenance_for("/spec/contract/output/schema_spec/columns/0/nullable").origin
        == "user"
    )
    if builder == "keyed":
        assert schema.keys[0].incomplete == "reject" and schema.keys[0].unique
    if builder == "sequence":
        assert schema.order.ties == "preserve"


@pytest.mark.parametrize(
    "left,right,state", [([1, 2, 2], [2, 1, 2], "equivalent"), ([1, 2], [1, 2, 2], "different")]
)
def test_default_bag_preserves_multiplicity(tmp_path, left, right, state):
    result = ef.diff(values(left), values(right), work_dir=tmp_path)
    assert result.state == state and result.strategy == "multiset" and result.complete
    if state == "different":
        (item,) = differences(result)
        assert item.code == "row_multiplicity"
        assert item.left_count == 1 and item.right_count == 2
    assert_parity(result, values(left), values(right), tmp_path / "core")


@pytest.mark.parametrize("kind", NATIVE_KINDS)
@pytest.mark.parametrize(
    "left,right,state",
    [
        ([None], [math.nan], "different"),
        ([math.nan], [math.nan], "equivalent"),
        ([math.inf], [math.inf], "equivalent"),
        ([math.inf], [-math.inf], "different"),
        ([0.0], [-0.0], "equivalent"),
        ([None, math.nan, 0.0, math.inf], [math.inf, 0.0, math.nan, None], "equivalent"),
    ],
)
def test_float_specials_remain_distinct_in_native_capture(tmp_path, kind, left, right, state):
    candidate, expected = values(left, pa.float64()), values(right, pa.float64())
    result = ef.diff(native(candidate, kind), native(expected, kind), work_dir=tmp_path)
    assert result.state == state and result.complete
    assert_parity(result, candidate, expected, tmp_path / "core")
    if result.left is not None:
        capture = ef.read_table(result.left.data)["value"]
        assert capture.null_count == sum(value is None for value in left)
        assert sum(math.isnan(v) for v in capture.to_pylist() if v is not None) == sum(
            isinstance(v, float) and math.isnan(v) for v in left
        )


def test_pandas_nullable_float_independent_validity_mask(tmp_path):
    array = pd.arrays.FloatingArray(
        np.array([math.nan, math.nan, 0.0, -0.0]), np.array([False, True, False, False])
    )
    candidate = pd.DataFrame({"value": array})
    expected = values([math.nan, None, 0.0, -0.0], pa.float64())
    result = ef.diff(candidate, expected, work_dir=tmp_path)
    assert result.state == "equivalent" and result.counts.matched_rows == 4
    assert result.left.table.columns[0].null_count == 1
    assert result.left.table.columns[0].nan_count == 1
    captured = ef.read_table(result.left.data)["value"].to_pylist()
    assert math.isnan(captured[0]) and captured[1] is None
    assert math.copysign(1, captured[2]) == 1 and math.copysign(1, captured[3]) == -1


def test_decimal_precision_does_not_use_float_or_global_decimal_context(tmp_path):
    huge = "1234567890123456789012345678901234567890.01"
    left = values([Decimal(huge)], pa.decimal256(50, 2))
    right = values([Decimal("1234567890123456789012345678901234567890.02")], pa.decimal256(50, 2))
    with localcontext() as _test_decimal_context:
        _test_decimal_context.prec = 3
        result = ef.diff(left, right, work_dir=tmp_path)
    assert result.state == "different" and result.complete
    assert {v.value for d in differences(result) for v in (*d.left, *d.right)} == {
        huge,
        "1234567890123456789012345678901234567890.02",
    }
    assert_parity(result, left, right, tmp_path / "core")


def test_time_zone_and_nanosecond_difference_require_explicit_policy(tmp_path):
    left = values([1], pa.timestamp("ns", "America/Guayaquil"))
    right = values([1], pa.timestamp("ns", "UTC"))
    strict = ef.diff(left, right, work_dir=tmp_path / "strict")
    assert strict.state == "different" and "logical_type" in codes(strict)
    policy = ef.ComparisonPolicy(physical_types="lossless", justification="compare UTC instants")
    relaxed = ef.diff(left, right, policy=policy, work_dir=tmp_path / "relaxed")
    assert relaxed.state == "equivalent" and relaxed.applied_policies
    assert_parity(relaxed, left, right, tmp_path / "core")
    later = ef.diff(values([2], pa.timestamp("ns", "UTC")), right, work_dir=tmp_path / "later")
    assert later.state == "different"


@pytest.mark.parametrize("reference,state", [("expected", "not_evaluable"), ("peer", "different")])
def test_composite_key_duplicate_in_later_batch_is_invalid_and_falls_back(
    tmp_path, reference, state
):
    table = pa.table({"tenant": [1, 2, 3, 1], "id": [7, 7, 7, 7], "value": [10, 20, 30, 10]})
    declaration = ef.keyed_contract(
        [column("tenant"), column("id"), column()], keys=["tenant", "id"], reference=reference
    )
    result = ef.diff(
        table,
        table,
        contract=declaration,
        options=ef.ComparisonOptions(batch_rows=1),
        work_dir=tmp_path,
    )
    assert result.state == state and result.complete and result.counts.final
    assert result.strategy == "multiset" and result.selected_key is None
    name = declaration.spec.contract.output.schema_spec.keys[0].name
    assert {f"duplicate_raw_key_{name}", f"duplicate_normalized_key_{name}"} <= codes(result)
    assert all(item.position == 3 for item in differences(result))
    assert result.counts.contract_violations == result.counts.difference_records == 4
    assert ("invalid_expected" in {d.code for d in result.diagnostics}) == (reference == "expected")
    assert_parity(result, table, table, tmp_path / "core")


@pytest.mark.parametrize("incomplete,state", [("reject", "not_evaluable"), ("allow", "equivalent")])
def test_incomplete_composite_keys_keep_core_bag_fallback(tmp_path, incomplete, state):
    left = pa.table(
        {"tenant": [1, 1, 2], "id": pa.array([None, None, 7], pa.int64()), "value": [10, 10, 20]}
    )
    right = pa.table(
        {"tenant": [2, 1, 1], "id": pa.array([7, None, None], pa.int64()), "value": [20, 10, 10]}
    )
    declaration = ef.keyed_contract(
        [column("tenant"), column("id"), column()], keys=["tenant", "id"], incomplete=incomplete
    )
    result = ef.diff(left, right, contract=declaration, work_dir=tmp_path)
    assert result.state == state and result.complete and result.strategy == "multiset"
    assert result.selected_key is None
    if incomplete == "allow":
        assert result.counts.matched_rows == 3 and not differences(result)
    else:
        name = declaration.spec.contract.output.schema_spec.keys[0].name
        assert f"incomplete_normalized_{name}" in codes(result)
    assert_parity(result, left, right, tmp_path / "core")


def test_missing_key_column_is_a_difference_and_not_an_implicit_key_change(tmp_path):
    declaration = ef.keyed_contract(
        [column("tenant"), column("id"), column()], keys=["tenant", "id"]
    )
    left = pa.table({"tenant": [1], "value": [10]})
    right = pa.table({"tenant": [1], "id": [7], "value": [10]})
    result = ef.diff(left, right, contract=declaration, work_dir=tmp_path)
    assert result.state == "different" and result.complete and result.strategy == "multiset"
    assert any(
        d.code == "missing_column" and d.column == "id" and d.side == "left"
        for d in differences(result)
    )
    assert_parity(result, left, right, tmp_path / "core")


def test_normalized_key_collision_is_reported_separately_from_raw_duplicates(tmp_path):
    time = column(
        "time",
        ef.TimestampType(unit="s", timezone="Europe/Madrid"),
        temporal_policy=ef.TimestampPolicy(
            granularity="s",
            timezone="Europe/Madrid",
            naive="reject",
            comparison="wall_time",
            ambiguous="reject",
            closed="both",
        ),
    )
    declaration = ef.keyed_contract([time], keys=["time"])
    # Distinct instants both read 02:30 at Madrid's autumn clock change.
    table = pa.table(
        {"time": pa.array([1729989000, 1729992600], pa.timestamp("s", "Europe/Madrid"))}
    )
    result = ef.diff(
        table,
        table,
        contract=declaration,
        options=ef.ComparisonOptions(batch_rows=1),
        work_dir=tmp_path,
    )
    name = declaration.spec.contract.output.schema_spec.keys[0].name
    assert result.state == "not_evaluable" and result.complete and result.strategy == "multiset"
    assert f"duplicate_normalized_key_{name}" in codes(result)
    assert f"duplicate_raw_key_{name}" not in codes(result)
    assert_parity(result, table, table, tmp_path / "core")


def approximate_contract():
    return ef.bag_contract(
        [
            column(
                kind=ef.FloatType(bits=64),
                numeric_policy=ef.NumericPolicy(
                    comparison="approximate",
                    unit="count",
                    tolerance=ef.Tolerance(
                        absolute="1", unit="count", justification="instrument resolution"
                    ),
                ),
            ),
        ]
    )


@pytest.mark.parametrize("batch_rows", [1, 2, 100])
@pytest.mark.parametrize(
    "left,right,state",
    [
        ([1.0, 0.0], [0.0, 2.0], "equivalent"),
        ([0.0, 0.0], [0.0, 2.0], "different"),
        ([0.0], [2.0], "different"),
    ],
)
def test_approximate_bag_uses_global_maximum_matching_across_batches(
    tmp_path, batch_rows, left, right, state
):
    candidate, expected = values(left, pa.float64()), values(right, pa.float64())
    result = ef.diff(
        candidate,
        expected,
        contract=approximate_contract(),
        options=ef.ComparisonOptions(batch_rows=batch_rows, partitions=7, sqlite_cache_kib=1),
        work_dir=tmp_path,
    )
    independently_matchable = any(
        all(abs(a - b) <= 1 for a, b in zip(left, permutation, strict=True))
        for permutation in itertools.permutations(right)
    )
    assert independently_matchable == (state == "equivalent")
    assert result.state == state and result.complete and result.strategy == "matching"
    assert result.counts.matched_rows == (
        len(left) if independently_matchable else (1 if len(left) == 2 else 0)
    )
    assert_parity(result, candidate, expected, tmp_path / "core")
    assert_persisted(result, tmp_path)


@pytest.mark.parametrize("reference,state", [("expected", "not_evaluable"), ("peer", "different")])
def test_shared_invalid_sequence_never_passes(tmp_path, reference, state):
    declaration = ef.sequence_contract(
        [column("position"), column()],
        by=[ef.SortSpec(column="position", direction="ascending", nulls="last")],
        reference=reference,
    )
    table = pa.table({"position": [2, 1], "value": [20, 10]})
    result = ef.diff(table, table, contract=declaration, work_dir=tmp_path)
    assert result.state == state and result.complete and result.strategy == "sequence"
    assert "order_violation" in codes(result)
    assert_parity(result, table, table, tmp_path / "core")


@pytest.mark.parametrize("ties,state", [("preserve", "different"), ("reject", "not_evaluable")])
def test_sequence_equal_sort_keys_do_not_permit_reordering_values(tmp_path, ties, state):
    declaration = ef.sequence_contract(
        [column("position"), column()],
        by=[ef.SortSpec(column="position", direction="ascending", nulls="last")],
        ties=ties,
    )
    left = pa.table({"position": [1, 1], "value": [10, 20]})
    right = pa.table({"position": [1, 1], "value": [20, 10]})
    result = ef.diff(left, right, contract=declaration, work_dir=tmp_path)
    assert result.state == state and result.complete and result.strategy == "sequence"
    assert ("order_tie" in codes(result)) == (ties == "reject")
    assert_parity(result, left, right, tmp_path / "core")


@pytest.mark.parametrize(
    "options",
    [
        ef.ComparisonOptions(max_rows=1),
        ef.ComparisonOptions(max_work=1),
        ef.ComparisonOptions(max_disk_bytes=1),
        ef.ComparisonOptions(max_batch_bytes=1),
        ef.ComparisonOptions(max_row_bytes=1),
        ef.ComparisonOptions(max_evidence_bytes=1),
        ef.ComparisonOptions(max_matching_rows=1),
        ef.ComparisonOptions(max_matching_bytes=1),
        ef.ComparisonOptions(max_pair_checks=1),
    ],
)
def test_comparison_resource_limits_never_claim_equivalence_and_cleanup_sqlite(tmp_path, options):
    result = ef.diff(
        values([0.0, 1.0], pa.float64()),
        values([3.0, 4.0], pa.float64()),
        contract=approximate_contract(),
        options=options,
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable" and not result.complete and not result.counts.final
    assert result.diagnostics[0].code == "resource_exhausted"
    assert_persisted(result, tmp_path)


def test_partial_differences_survive_limit_without_becoming_final_counts(tmp_path):
    declaration = ef.bag_contract([column(nullable=False)])
    result = ef.diff(
        values([None, None, None]),
        values([1, 2, 3]),
        contract=declaration,
        options=ef.ComparisonOptions(max_rows=2, batch_rows=1),
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable" and not result.complete and not result.counts.final
    assert result.counts.difference_records == len(differences(result)) == 2
    assert codes(result) == {"null_forbidden"}
    assert_persisted(result, tmp_path)


def test_sqlite_spill_is_used_and_removed_on_exhaustion(tmp_path):
    table = values(list(range(1000)))
    result = ef.diff(
        table,
        table,
        options=ef.ComparisonOptions(batch_rows=7, sqlite_cache_kib=1, max_disk_bytes=150000),
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable" and result.diagnostics[0].code == "resource_exhausted"
    assert 0 < result.counts.left_rows < 1000
    assert result.peak_disk_bytes > 0 and not result.complete
    assert_persisted(result, tmp_path)


@pytest.mark.parametrize("kind", NATIVE_KINDS)
@pytest.mark.parametrize("limit", ["max_rows", "max_bytes"])
def test_native_capture_limits_are_distinct_from_comparison_limits(tmp_path, kind, limit):
    table = native(values([1, 2]), kind)
    capture = ef.DiffCaptureOptions(**{limit: 1})
    with pytest.raises(ef.ResourceLimitError):
        ef.diff(table, table, capture_options=capture, work_dir=tmp_path / "unconfigured")
    result = ef.diff(
        table,
        table,
        contract=ef.bag_contract([column()]),
        capture_options=capture,
        work_dir=tmp_path / "configured",
    )
    assert result.state == "not_evaluable" and result.diagnostics[0].code == "resource_exhausted"
    assert not result.complete
    assert_persisted(result, tmp_path / "configured")


def test_last_row_mismatch_is_not_hidden_by_example_budget(tmp_path):
    left = values([*range(2048), 999999])
    right = values([*range(2048), 2048])
    result = ef.diff(
        left,
        right,
        options=ef.ComparisonOptions(batch_rows=17, max_examples=0, sqlite_cache_kib=1),
        work_dir=tmp_path,
    )
    assert result.state == "different" and result.complete and result.examples == ()
    assert result.counts.left_rows == result.counts.right_rows == 2049
    assert result.counts.matched_rows == 2048
    assert result.counts.difference_records == len(differences(result)) == 2
    assert {v.value for d in differences(result) for v in (*d.left, *d.right)} == {"999999", "2048"}
    assert_persisted(result, tmp_path)


@pytest.mark.parametrize("kind", NATIVE_KINDS)
def test_captures_survive_input_mutation_and_independent_repeated_runs(tmp_path, kind):
    buffer = np.array([1, 2, 3], dtype=np.int64)
    source = native(pa.table({"value": buffer}), kind)
    expected = values([1, 2, 3])
    first = ef.diff(source, expected, work_dir=tmp_path)
    assert first.state == "equivalent"
    if kind == "pandas":
        source.loc[2, "value"] = 99
    elif kind == "polars":
        source[2, "value"] = 99
    else:
        buffer[2] = 99
    second = ef.diff(source, expected, work_dir=tmp_path)
    assert second.state == "different"
    assert first.comparison_id != second.comparison_id
    assert ef.read_table(first.left.data)["value"].to_pylist() == [1, 2, 3]
    assert ef.read_table(second.left.data)["value"].to_pylist() == [1, 2, 99]
    assert ef.read_table(first.right.data)["value"].to_pylist() == [1, 2, 3]
    assert_persisted(first, tmp_path)


@pytest.mark.parametrize(
    "index",
    [
        pd.Index(["a", "b"], name="account"),
        pd.RangeIndex(1, 3),
        pd.RangeIndex(2, name="row"),
        pd.MultiIndex.from_tuples([("x", 1), ("y", 2)], names=["tenant", "id"]),
    ],
)
def test_meaningful_pandas_index_needs_explicit_ignore_and_is_captured_separately(tmp_path, index):
    frame = pd.DataFrame({"value": [10, 20]}, index=index)
    expected = values([10, 20])
    rejected = ef.diff(frame, expected, work_dir=tmp_path / "reject")
    assert rejected.state == "not_evaluable" and not rejected.complete
    assert rejected.diagnostics[0].code == "unsupported_capability"
    policy = ef.ComparisonPolicy(
        index="ignore", justification="index is outside this output contract"
    )
    accepted = ef.diff(frame, expected, policy=policy, work_dir=tmp_path / "ignore")
    assert accepted.state == "equivalent" and accepted.complete
    assert accepted.left.table.index is not None
    assert ef.read_table(accepted.left.data).column_names == ["value"]
    assert ef.read_table(accepted.left.table.index).num_rows == 2
    assert (
        ef.AppliedPolicy(side="left", operation="ignore_captured_index", count=2)
        in accepted.applied_policies
    )
    assert_parity(accepted, accepted.left.table, ef.ArrowInput(expected), tmp_path / "core")


def test_default_unnamed_range_index_does_not_create_keys_or_require_ignore(tmp_path):
    frame = pd.DataFrame({"value": [2, 1]})
    result = ef.diff(frame, values([1, 2]), work_dir=tmp_path)
    assert result.state == "equivalent" and result.strategy == "multiset"
    assert result.spec.policy.index == "reject" and not result.applied_policies
    assert result.spec.contract.output.schema_spec.keys == ()
    assert result.left.table.index is None


def unsupported_inputs():
    category = pd.DataFrame(
        {"value": pd.Categorical(["a"], categories=["a", "unused"], ordered=True)}
    )
    named_columns = pd.DataFrame({"value": [1]})
    named_columns.columns.name = "measurement"
    return [
        pytest.param(pa.table({"value": [[1]]}), id="nested-arrow"),
        pytest.param(
            pa.table({"value": pa.array(["a"]).dictionary_encode()}), id="dictionary-arrow"
        ),
        pytest.param(values([1]).replace_schema_metadata({b"units": b"USD"}), id="schema-metadata"),
        pytest.param(
            pa.Table.from_arrays(
                [pa.array([1])],
                schema=pa.schema([pa.field("value", pa.int64(), metadata={b"units": b"USD"})]),
            ),
            id="field-metadata",
        ),
        pytest.param(category, id="pandas-category"),
        pytest.param(named_columns, id="pandas-named-column-axis"),
        pytest.param(pl.DataFrame({"value": [[1]]}), id="nested-polars"),
    ]


@pytest.mark.parametrize("unsupported", unsupported_inputs())
def test_unsupported_semantics_fail_closed_before_inference_or_as_configured_result(
    tmp_path, unsupported
):
    with pytest.raises(ef.CapabilityError):
        ef.diff(unsupported, unsupported, work_dir=tmp_path / "inference")
    configured = ef.diff(
        unsupported,
        unsupported,
        contract=ef.bag_contract([column()]),
        work_dir=tmp_path / "configured",
    )
    assert configured.state == "not_evaluable" and not configured.complete
    assert configured.diagnostics[0].code == "unsupported_capability"
    assert_persisted(configured, tmp_path / "configured")
    # A valid expected side can establish the contract, but must not coerce the candidate.
    candidate = ef.diff(unsupported, values([1]), work_dir=tmp_path / "candidate")
    assert candidate.state == "not_evaluable" and not candidate.complete
    assert candidate.diagnostics[0].code == "unsupported_capability"


def test_null_only_inference_requires_typed_override():
    schema = pa.schema([("value", pa.null())])
    with pytest.raises(ef.CapabilityError):
        ef.infer_diff_contract(schema)
    declaration = ef.infer_diff_contract(schema, column_overrides=[column()])
    assert declaration.spec.contract.output.schema_spec.columns == (column(),)
    assert (
        declaration.provenance_for(
            "/spec/contract/output/schema_spec/columns/0/logical_type/kind"
        ).origin
        == "user"
    )


def test_polars_lazy_plan_is_never_collected(tmp_path, monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("collect")
        raise AssertionError("diff must not execute a LazyFrame")

    lazy = pl.DataFrame({"value": [1]}).lazy()
    monkeypatch.setattr(pl.LazyFrame, "collect", forbidden)
    with pytest.raises(ef.CapabilityError):
        ef.diff(lazy, lazy, work_dir=tmp_path / "unconfigured")
    result = ef.diff(
        lazy, lazy, contract=ef.bag_contract([column()]), work_dir=tmp_path / "configured"
    )
    assert (
        result.state == "not_evaluable" and result.diagnostics[0].code == "unsupported_capability"
    )
    assert calls == []


def test_explicit_duckdb_relation_is_consumed_once_per_input(tmp_path):
    calls = []

    def native_identity(value: int) -> int:
        calls.append(value)
        return value

    with duckdb.connect(":memory:") as connection:
        connection.create_function("native_identity", native_identity, side_effects=True)
        relation = connection.sql("SELECT native_identity(i) AS value FROM range(30000) AS t(i)")
        assert calls == []
        result = ef.diff(
            relation,
            relation,
            contract=ef.bag_contract([column()]),
            work_dir=tmp_path / "configured",
        )
        assert result.complete and result.state == "equivalent"
        assert result.counts.left_rows == result.counts.right_rows == 30000
        assert len(calls) == 60000
        assert sorted(calls) == [value for value in range(30000) for _ in range(2)]


@pytest.mark.parametrize("container", ["arrow_input", "arrow_path", "parquet_path", "artifact"])
def test_existing_materialized_inputs_keep_compare_semantics_with_explicit_contract(
    tmp_path, container
):
    table = values([1, 2, 2])
    if container == "arrow_input":
        source = ef.ArrowInput(table)
    elif container == "parquet_path":
        source = tmp_path / "input.parquet"
        pq.write_table(table, source)
    else:
        path = tmp_path / "input.arrow"
        with path.open("wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table, max_chunksize=1)
        source = (
            path
            if container == "arrow_path"
            else ef.LocalArtifactStore(tmp_path / "store").put(
                path, media_type="application/vnd.apache.arrow.file"
            )
        )
    declaration = ef.bag_contract([column()])
    result = ef.diff(source, source, contract=declaration.spec.contract, work_dir=tmp_path / "diff")
    assert result.state == "equivalent" and result.reference == "expected"
    assert result.counts.matched_rows == 3
    assert_parity(result, source, source, tmp_path / "core")
    if container != "arrow_input":
        with pytest.raises(ef.CapabilityError):
            ef.diff(source, source, work_dir=tmp_path / "no-contract")


@pytest.mark.parametrize("state", ["completed", "failed", "cancelled"])
def test_execution_results_are_not_rerun_and_failures_remain_not_evaluable(tmp_path, state):
    contract = ef.bag_contract([column()]).spec.contract
    input_name = contract.inputs[0].name
    calls = []

    def transformation(tables, context):
        calls.append("executed")
        if state == "failed":
            raise RuntimeError("independent test failure")
        return tables[input_name].clone()

    registry = ef.TransformationRegistry()
    registry.register(ef.PolarsTransformation("test.identity", transformation, "test.v1"))
    token = ef.CancellationToken()
    if state == "cancelled":
        token.cancel()
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract, engine="polars", transformation_id="test.identity"),
        source=ef.LocalDataSource({input_name: ef.ArrowInput(values([1, 2]))}),
        registry=registry,
        work_dir=tmp_path / "execution",
        cancellation=token,
    )
    assert execution.state == state
    before = tuple(calls)
    result = ef.diff(execution, values([1, 2]), contract=contract, work_dir=tmp_path / "diff")
    assert tuple(calls) == before
    assert result.state == ("equivalent" if state == "completed" else "not_evaluable")
    assert result.complete == (state == "completed")
    assert_parity(result, execution, values([1, 2]), tmp_path / "core")
    if state == "completed":
        artifact = ef.diff(
            execution.output, values([1, 2]), contract=contract, work_dir=tmp_path / "table"
        )
        assert artifact.state == "equivalent"


def test_cancellation_boundary_before_and_after_valid_contract(tmp_path):
    token = ef.CancellationToken()
    token.cancel()
    with pytest.raises(ef.ExecutionCancelled):
        ef.diff(values([1]), values([1]), cancellation=token, work_dir=tmp_path / "unconfigured")
    result = ef.diff(
        values([1]),
        values([1]),
        contract=ef.bag_contract([column()]),
        cancellation=token,
        work_dir=tmp_path / "configured",
    )
    assert result.state == "not_evaluable" and not result.complete and not result.counts.final
    assert result.diagnostics[0].code == "cancelled"
    assert_persisted(result, tmp_path / "configured")


@pytest.mark.parametrize("override", ["keys", "policy", "reference"])
def test_diff_contract_cannot_be_silently_overridden(tmp_path, override):
    declaration = ef.bag_contract([column()])
    value = {"keys": ["value"], "policy": ef.ComparisonPolicy(), "reference": "peer"}[override]
    with pytest.raises(ValueError):
        ef.diff(
            values([1]), values([1]), contract=declaration, **{override: value}, work_dir=tmp_path
        )
    assert not list(tmp_path.rglob("comparison.json"))


def test_invalid_capture_options_and_unwritable_evidence_raise_without_false_result(tmp_path):
    with pytest.raises(ValidationError):
        ef.DiffCaptureOptions(max_rows=0)
    with pytest.raises(ValidationError):
        ef.DiffCaptureOptions(max_bytes=-1)
    blocked = tmp_path / "occupied"
    blocked.write_bytes(b"existing content")
    with pytest.raises(OSError):
        ef.diff(values([1]), values([1]), work_dir=blocked)
    assert blocked.read_bytes() == b"existing content"


@pytest.mark.parametrize("argument", ["options", "capture_options"])
@pytest.mark.parametrize("invalid", [False, 0, [], ()])
def test_falsey_invalid_options_are_rejected_before_capture(tmp_path, argument, invalid):
    with pytest.raises(ValidationError):
        ef.diff(values([1]), values([1]), **{argument: invalid}, work_dir=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("argument", ["options", "capture_options"])
@pytest.mark.parametrize("selected", [None, {}])
def test_none_and_valid_empty_option_mappings_preserve_defaults(tmp_path, argument, selected):
    # Pydantic's existing strict mapping route remains valid. Unlike a false
    # scalar/list, an empty mapping is a complete all-default options document.
    result = ef.diff(values([1]), values([1]), **{argument: selected}, work_dir=tmp_path)
    assert result.state == "equivalent"
    assert result.options == ef.ComparisonOptions()
    receipt = json.loads((tmp_path / result.comparison_id / "diff-contract.json").read_text())
    assert receipt["capture_options"] == ef.DiffCaptureOptions().model_dump(mode="json")


@pytest.mark.parametrize(
    "argument,invalid", [("options", {"max_work": "1"}), ("capture_options", {"max_rows": "1"})]
)
def test_option_mappings_do_not_coerce_numeric_text(tmp_path, argument, invalid):
    with pytest.raises(ValidationError):
        ef.diff(values([1]), values([1]), **{argument: invalid}, work_dir=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("field", ["comparison_id", "spec_sha256"])
def test_sidecar_is_bound_to_exact_comparison_result(tmp_path, field):
    result = ef.diff(values([1]), values([1]), work_dir=tmp_path)
    sidecar = tmp_path / result.comparison_id / "diff-contract.json"
    receipt = json.loads(sidecar.read_text())
    receipt[field] = "different-comparison" if field == "comparison_id" else "0" * 64
    sidecar.write_text(json.dumps(receipt))
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_diff_contract(result)


def test_sidecar_cannot_be_swapped_between_identically_configured_runs(tmp_path):
    first = ef.diff(values([1]), values([1]), work_dir=tmp_path)
    second = ef.diff(values([2]), values([2]), work_dir=tmp_path)
    assert first.spec_sha256 == second.spec_sha256
    first_path = tmp_path / first.comparison_id / "diff-contract.json"
    second_path = tmp_path / second.comparison_id / "diff-contract.json"
    first_path.write_bytes(second_path.read_bytes())
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_diff_contract(first)
    assert ef.read_diff_contract(second).spec == second.spec


def test_sidecar_rejects_duplicate_json_and_missing_receipt_is_not_invented(tmp_path):
    result = ef.diff(values([1]), values([1]), work_dir=tmp_path)
    sidecar = tmp_path / result.comparison_id / "diff-contract.json"
    raw = sidecar.read_text()
    sidecar.write_text('{"schema_version":"1.0",' + raw.lstrip()[1:])
    with pytest.raises(ef.ContractParseError):
        ef.read_diff_contract(result)
    direct_core = ef.compare(
        ef.ArrowInput(values([1])),
        ef.ArrowInput(values([1])),
        contract=result.spec.contract,
        work_dir=tmp_path / "core",
    )
    with pytest.raises(FileNotFoundError):
        ef.read_diff_contract(direct_core)


@pytest.mark.parametrize("sentinel", ["blank", "zero", "nan"])
def test_authorized_absence_override_matches_core_and_records_applied_policy(tmp_path, sentinel):
    if sentinel == "blank":
        dtype, item = pa.string(), ""
        spec = column(
            kind=ef.StringType(),
            null_policy=ef.NullPolicy(
                representations=("null", "empty_string"),
                justification="documented missing sentinel",
            ),
        )
    elif sentinel == "zero":
        dtype, item = pa.int64(), 0
        spec = column(
            null_policy=ef.NullPolicy(
                representations=("null", "zero"), justification="documented missing sentinel"
            )
        )
    else:
        dtype, item = pa.float64(), math.nan
        spec = column(
            kind=ef.FloatType(bits=64),
            nan_policy=ef.NaNPolicy(
                handling="as_null", justification="documented missing sentinel"
            ),
        )
    left, right = values([item], dtype), values([None], dtype)
    strict = ef.diff(left, right, work_dir=tmp_path / "strict")
    assert strict.state == "different"
    declared = ef.infer_diff_contract(right.schema, column_overrides=[spec])
    relaxed = ef.diff(left, right, contract=declared, work_dir=tmp_path / "relaxed")
    assert relaxed.state == "equivalent" and relaxed.applied_policies
    assert_parity(relaxed, left, right, tmp_path / "core")


def test_exact_float_default_has_no_implicit_tolerance(tmp_path):
    left = values([1.0], pa.float64())
    right = values([math.nextafter(1.0, math.inf)], pa.float64())
    result = ef.diff(left, right, work_dir=tmp_path)
    assert result.state == "different" and result.complete
    policy = result.spec.contract.output.schema_spec.columns[0].numeric_policy
    assert policy.comparison == "exact" and policy.tolerance is None
    assert_parity(result, left, right, tmp_path / "core")


def test_timeout_is_incomplete_and_cleans_persisted_workspace(tmp_path):
    result = ef.diff(
        values([1]),
        values([1]),
        contract=ef.bag_contract([column()]),
        options=ef.ComparisonOptions(timeout_seconds=1e-12),
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable" and not result.complete
    assert result.diagnostics[0].code == "timeout"
    assert_persisted(result, tmp_path)


def test_cooperative_cancellation_retains_observed_difference_and_cleans_sqlite(tmp_path):
    class CancelAfterDifference(ef.CancellationToken):
        @property
        def cancelled(self):
            if any(path.stat().st_size for path in tmp_path.glob("*/differences.jsonl")):
                self.cancel()
            return super().cancelled

    result = ef.diff(
        values([1]),
        values([2]),
        contract=ef.bag_contract([column()]),
        cancellation=CancelAfterDifference(),
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable" and not result.complete and not result.counts.final
    assert result.diagnostics[0].code == "cancelled"
    assert result.counts.difference_records == len(differences(result)) == 1
    assert result.counts.matched_rows == 0
    assert_persisted(result, tmp_path)


def test_core_compare_does_not_implicitly_gain_native_input_behavior(tmp_path):
    result = ef.compare(
        pd.DataFrame({"value": [1]}),
        ef.ArrowInput(values([1])),
        contract=ef.bag_contract([column()]).spec.contract,
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable" and not result.complete
    assert result.diagnostics[0].exception_type == "TypeError"


def test_sidecar_publication_error_raises_and_removes_only_temporary_file(tmp_path, monkeypatch):
    original_link = os.link

    def fail_receipt_publish(source, destination, *args, **kwargs):
        if Path(destination).name == "diff-contract.json":
            raise OSError("independent test publication failure")
        return original_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "link", fail_receipt_publish)
    with pytest.raises(OSError, match="independent test publication failure"):
        ef.diff(values([1]), values([1]), work_dir=tmp_path)
    assert not list(tmp_path.rglob("*.part"))
    assert not list(tmp_path.rglob("work.sqlite*"))
    assert not list(tmp_path.rglob("diff-contract.json"))
    (manifest,) = tmp_path.glob("*/comparison.json")
    completed_core = ef.read_comparison(manifest)
    assert completed_core.state == "equivalent" and completed_core.complete
    assert not differences(completed_core)
    with pytest.raises(FileNotFoundError):
        ef.read_diff_contract(completed_core)


def test_public_diff_input_alias_can_be_inspected_without_loading_engines():
    script = """
import sys
import equiframe as ef
runtime_type = ef.DiffInput.__value__
assert runtime_type is not None
assert callable(ef.diff) and callable(ef.infer_diff_contract)
assert not {'pandas', 'polars', 'duckdb', 'pyarrow', 'numpy', 'sklearn'}.intersection(sys.modules)
"""
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
