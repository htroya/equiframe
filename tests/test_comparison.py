"""Independent small expectations and adversarial full-content comparisons."""

import importlib
import itertools
import json
import math
import sqlite3
from datetime import datetime
from decimal import Decimal, localcontext

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

import equiframe as ef

LOSSLESS = ef.ComparisonPolicy(
    physical_types="lossless", justification="Explicit lossless transport"
)


def column(name="value", kind=None, **overrides):
    kind = kind or ef.IntegerType(bits=64, signed=True)
    args = dict(
        name=name,
        logical_type=kind,
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
    )
    if kind.kind in ("integer", "float", "decimal"):
        args["numeric_policy"] = ef.NumericPolicy(
            comparison="exact", unit="USD" if kind.kind == "decimal" else "count"
        )
    if kind.kind == "float":
        args["nan_policy"] = ef.NaNPolicy(handling="distinct")
    if kind.kind == "date":
        args["temporal_policy"] = ef.DatePolicy(closed="both")
    if kind.kind == "timestamp":
        args["temporal_policy"] = ef.TimestampPolicy(
            granularity=kind.unit,
            timezone=kind.timezone,
            naive="reject" if kind.timezone else "preserve",
            comparison="instant" if kind.timezone else "wall_time",
            ambiguous="reject",
            closed="both",
        )
    return ef.ColumnSpec(**(args | overrides))


def contract(columns=None, keys=(), multiplicity="preserve", order=None, family="nulls_types"):
    schema = ef.TableSchema(
        columns=columns or (column(),),
        keys=keys,
        multiplicity=multiplicity,
        order=order or ef.IgnoredOrder(),
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="independent.test",
        revision=1,
        family=family,
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )


def key(columns=("id",), incomplete="reject", scope=None):
    return ef.KeySpec(
        name="primary",
        columns=columns,
        unique=True,
        incomplete=incomplete,
        scope=scope or ef.TableKeyScope(),
    )


def run(tmp_path, left, right, spec=None, **kwargs):
    left = ef.ArrowInput(left) if isinstance(left, pa.Table) else left
    right = ef.ArrowInput(right) if isinstance(right, pa.Table) else right
    result = ef.compare(left, right, contract=spec or contract(), work_dir=tmp_path, **kwargs)
    assert not list((tmp_path / result.comparison_id).glob("work.sqlite*"))
    assert ef.read_comparison(tmp_path / result.comparison_id / "comparison.json") == result
    return result


def codes(result):
    return [v.code for v in ef.iter_differences(result.differences)]


def test_swapped_money_conserves_total_and_localizes_key(tmp_path):
    spec = contract(
        (column("id", ef.StringType()), column("amount", ef.DecimalType(precision=18, scale=2))),
        keys=(key(),),
        family="aggregations",
    )

    def table(values):
        return pa.table(
            {
                "id": ["001", "002"],
                "amount": pa.array([Decimal(v) for v in values], type=pa.decimal128(18, 2)),
            }
        )

    result = run(tmp_path, table(["100.00", "200.00"]), table(["200.00", "100.00"]), spec)
    assert result.state == "different" and result.complete and result.strategy == "key"
    assert {v.key[0].value for v in result.examples} == {"001", "002"}
    assert {v.left[0].value for v in result.examples} == {"100.00", "200.00"}
    assert all(v.column == "amount" for v in result.examples)


@pytest.mark.parametrize(
    "family", ["nulls_types", "joins", "duplicates_order", "aggregations", "dates"]
)
@settings(
    max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(values=st.lists(st.integers(-100, 100), max_size=15))
def test_permutation_and_multiplicity_property(tmp_path, family, values):
    # The expected cardinality and reversed values are constructed independently.
    dtype = pa.date32() if family == "dates" else pa.int64()
    logical = ef.DateType() if family == "dates" else ef.IntegerType(bits=64, signed=True)
    a = pa.table({"value": pa.array(values, type=dtype)})
    b = pa.table({"value": pa.array(list(reversed(values)), type=dtype)})
    result = run(tmp_path, a, b, contract((column(kind=logical),), family=family))
    assert result.state == "equivalent" and result.counts.matched_rows == len(values)
    c = pa.table({"value": pa.array([*values, 7], type=dtype)})
    changed = run(tmp_path, a, c, contract((column(kind=logical),), family=family))
    assert changed.state == "different" and changed.complete


def test_compound_scoped_and_incomplete_keys(tmp_path):
    columns = (column("tenant", ef.StringType()), column("id", ef.StringType()), column())
    scoped = key(("id",), scope=ef.ColumnKeyScope(columns=("tenant",)))
    a = pa.table({"tenant": ["a", "b"], "id": ["001", "001"], "value": [1, 2]})
    result = run(tmp_path, a, a.take([1, 0]), contract(columns, keys=(scoped,), family="joins"))
    assert result.state == "equivalent" and result.strategy == "key"
    bad = run(tmp_path, a, a, contract(columns, keys=(key(),)))
    assert bad.state == "different" and "duplicate_normalized_key_primary" in codes(bad)
    incomplete = pa.table(
        {"tenant": ["a", "b"], "id": pa.array([None, None], type=pa.string()), "value": [1, 2]}
    )
    permitted = run(
        tmp_path,
        incomplete,
        incomplete.take([1, 0]),
        contract(columns, keys=(key(incomplete="allow"),)),
    )
    assert permitted.state == "equivalent" and permitted.strategy == "multiset"
    rejected = run(tmp_path, incomplete, incomplete, contract(columns, keys=(key(),)))
    assert rejected.state == "different" and "incomplete_normalized_primary" in codes(rejected)


def test_normalization_cannot_hide_key_collision_or_distinct_violation(tmp_path):
    col = column(
        "id",
        ef.StringType(),
        null_policy=ef.NullPolicy(
            representations=("null", "empty_string"), justification="blank IDs absent"
        ),
    )
    a = pa.table({"id": ["", None, "001"]})
    result = run(
        tmp_path, a, a, contract((col,), keys=(key(incomplete="allow"),), multiplicity="distinct")
    )
    assert result.state == "different" and "duplicate_normalized_row" in codes(result)
    # Different physical timestamp units collapse only after authorized normalization.
    col = column("id", ef.TimestampType(unit="ns", timezone="UTC"))
    a = pa.table({"id": pa.array([0, 0], type=pa.timestamp("ms", "UTC"))})
    result = run(tmp_path, a, a, contract((col,), keys=(key(),)), policy=LOSSLESS)
    assert result.state == "different" and "duplicate_normalized_key_primary" in codes(result)


@pytest.mark.parametrize("ties", ["preserve", "reject"])
def test_sequence_ties_and_invalid_shared_order(tmp_path, ties):
    spec = contract(
        (column("position"), column("label", ef.StringType())),
        order=ef.SignificantOrder(
            by=(ef.SortSpec(column="position", direction="ascending", nulls="last"),), ties=ties
        ),
        family="duplicates_order",
    )
    a = pa.table({"position": [1, 1], "label": ["a", "b"]})
    result = run(tmp_path, a, a.take([1, 0]), spec)
    assert result.state == "different" and result.strategy == "sequence"
    assert ("order_tie" in codes(result)) == (ties == "reject")
    bad = pa.table({"position": [2, 1], "label": ["a", "b"]})
    invalid = run(tmp_path, bad, bad, spec)
    assert invalid.state == "different" and "order_violation" in codes(invalid)


@pytest.mark.parametrize(
    "kind,values", [("string", [None, "", "0", "001"]), ("float", [None, float("nan"), 0.0, 1.0])]
)
def test_absence_nan_empty_zero_are_distinct(tmp_path, kind, values):
    col = column(kind=ef.StringType() if kind == "string" else ef.FloatType(bits=64))
    dtype = pa.string() if kind == "string" else pa.float64()
    for a, b in itertools.combinations(values, 2):
        result = run(
            tmp_path,
            pa.table({"value": pa.array([a], type=dtype)}),
            pa.table({"value": pa.array([b], type=dtype)}),
            contract((col,)),
        )
        assert result.state == "different"


@pytest.mark.parametrize(
    "handling,state",
    [("forbid", "different"), ("distinct", "different"), ("as_null", "equivalent")],
)
def test_nan_policies(tmp_path, handling, state):
    col = column(
        kind=ef.FloatType(bits=64),
        nan_policy=ef.NaNPolicy(
            handling=handling, justification="sensor missing" if handling == "as_null" else None
        ),
    )
    a = pa.table({"value": [float("nan")]})
    b = pa.table({"value": pa.array([None], type=pa.float64())})
    result = run(tmp_path, a, b, contract((col,)))
    assert result.state == state
    same = run(tmp_path, a, a, contract((col,)))
    assert same.state == ("different" if handling == "forbid" else "equivalent")


@pytest.mark.parametrize(
    "dtype,logical,value,rep",
    [
        (pa.string(), ef.StringType(), "", "empty_string"),
        (pa.int64(), ef.IntegerType(bits=64, signed=True), 0, "zero"),
    ],
)
def test_authorized_absence(tmp_path, dtype, logical, value, rep):
    col = column(
        kind=logical,
        null_policy=ef.NullPolicy(representations=("null", rep), justification="source sentinel"),
    )
    result = run(
        tmp_path,
        pa.table({"value": pa.array([value], type=dtype)}),
        pa.table({"value": pa.array([None], type=dtype)}),
        contract((col,)),
    )
    assert result.state == "equivalent" and result.applied_policies


def test_schema_empty_columns_and_authorization(tmp_path):
    spec = contract((column("a"), column("b")))
    a = pa.table({"a": pa.array([], type=pa.int64()), "b": pa.array([], type=pa.int64())})
    assert run(tmp_path, a, a, spec).state == "equivalent"
    assert run(tmp_path, a, a.select(["b", "a"]), spec).state == "different"
    relaxed = ef.ComparisonPolicy(column_order="ignored", justification="named relation")
    assert run(tmp_path, a, a.select(["b", "a"]), spec, policy=relaxed).state == "equivalent"
    result = run(tmp_path, a.select(["a"]), a.select(["a"]), spec)
    assert result.state == "different" and "missing_column" in codes(result)
    extra = a.append_column("c", pa.array([], type=pa.int64()))
    assert "additional_column" in codes(run(tmp_path, extra, extra, spec))
    invalid = run(tmp_path, a.select(["a"]), a.select(["a"]), spec, reference="expected")
    assert invalid.state == "not_evaluable" and invalid.complete
    assert invalid.diagnostics[0].code == "invalid_expected"
    with pytest.raises(ValidationError):
        ef.ComparisonPolicy(physical_types="lossless")


def test_physical_mapping_is_lossless_and_explicit(tmp_path):
    a = pa.table({"value": pa.array([127], type=pa.int8())})
    b = pa.table({"value": pa.array([127], type=pa.int64())})
    spec = contract((column(kind=ef.IntegerType(bits=8, signed=True)),))
    assert run(tmp_path, a, b, spec).state == "different"
    assert run(tmp_path, a, b, spec, policy=LOSSLESS).state == "equivalent"
    overflow = pa.table({"value": [128]})
    assert "integer_range" in codes(run(tmp_path, overflow, overflow, spec, policy=LOSSLESS))
    wrong = pa.table({"value": [127.0]})
    assert run(tmp_path, wrong, wrong, spec, policy=LOSSLESS).state == "different"


@pytest.mark.parametrize("signed,values", [(True, [-(2**63), 2**63 - 1]), (False, [0, 2**64 - 1])])
def test_integer_extremes(tmp_path, signed, values):
    dtype = pa.int64() if signed else pa.uint64()
    a = pa.table({"value": pa.array(values, type=dtype)})
    assert (
        run(
            tmp_path,
            a,
            a.take([1, 0]),
            contract((column(kind=ef.IntegerType(bits=64, signed=signed)),)),
        ).state
        == "equivalent"
    )


def test_decimal_no_rounding_and_currency_preserved(tmp_path):
    col = column(
        "amount",
        ef.DecimalType(precision=76, scale=2),
        numeric_policy=ef.NumericPolicy(
            comparison="exact",
            unit="currency_units",
            rounding="ROUND_HALF_UP",
            rounding_justification="transformation only",
        ),
    )
    spec = contract((column("currency", ef.StringType()), col))
    huge = "9" * 74 + ".01"
    a = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal(huge)], type=pa.decimal256(76, 2))}
    )
    with localcontext() as _test_decimal_context:
        _test_decimal_context.prec = 3
        assert run(tmp_path, a, a, spec).state == "equivalent"
    b = pa.table(
        {"currency": ["EUR"], "amount": pa.array([Decimal(huge)], type=pa.decimal256(76, 2))}
    )
    assert run(tmp_path, a, b, spec).state == "different"
    narrow = contract((column(kind=ef.DecimalType(precision=8, scale=2)),))
    fractional = pa.table({"value": pa.array([Decimal("1.001")], type=pa.decimal128(9, 3))})
    assert "decimal_precision" in codes(
        run(tmp_path, fractional, fractional, narrow, policy=LOSSLESS)
    )


def approximate(absolute="1", relative=None):
    return contract(
        (
            column(
                kind=ef.FloatType(bits=64),
                numeric_policy=ef.NumericPolicy(
                    comparison="approximate",
                    unit="count",
                    tolerance=ef.Tolerance(
                        absolute=absolute,
                        relative=relative,
                        unit="count",
                        justification="instrument resolution",
                    ),
                ),
            ),
        )
    )


@pytest.mark.parametrize(
    "a,b,state",
    [
        (0.0, 1.0, "equivalent"),
        (0.0, math.nextafter(1.0, math.inf), "different"),
        (-1.0, 0.0, "equivalent"),
        (math.inf, math.inf, "equivalent"),
        (math.inf, -math.inf, "different"),
        (math.inf, 1e300, "different"),
        (float("nan"), float("nan"), "equivalent"),
    ],
)
def test_tolerance_boundary_zero_infinity_nan(tmp_path, a, b, state):
    result = run(tmp_path, pa.table({"value": [a]}), pa.table({"value": [b]}), approximate())
    assert result.state == state


def test_maximum_matching_is_not_greedy_or_transitive(tmp_path):
    def t(v):
        return pa.table({"value": pa.array(v, type=pa.float64())})

    result = run(tmp_path, t([1, 0]), t([0, 2]), approximate())
    assert result.state == "equivalent" and result.counts.matched_rows == 2
    assert run(tmp_path, t([0]), t([1]), approximate()).state == "equivalent"
    assert run(tmp_path, t([1]), t([2]), approximate()).state == "equivalent"
    assert run(tmp_path, t([0]), t([2]), approximate()).state == "different"
    assert run(tmp_path, t([0, 0]), t([0, 2]), approximate()).state == "different"
    assert run(tmp_path, t([9]), t([10]), approximate("0", "0.1")).state == "equivalent"


@settings(
    max_examples=35, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    left=st.lists(st.integers(-3, 3), max_size=5), right=st.lists(st.integers(-3, 3), max_size=5)
)
def test_matching_against_independent_exhaustive_permutations(tmp_path, left, right):
    expected = len(left) == len(right) and any(
        all(abs(a - b) <= 1 for a, b in zip(left, p, strict=True))
        for p in itertools.permutations(right)
    )
    result = run(
        tmp_path,
        pa.table({"value": pa.array(left, type=pa.float64())}),
        pa.table({"value": pa.array(right, type=pa.float64())}),
        approximate(),
    )
    assert (result.state == "equivalent") == expected


def test_nanosecond_precision_and_time_units(tmp_path):
    spec = contract((column(kind=ef.TimestampType(unit="ns", timezone="UTC")),), family="dates")
    a = pa.table({"value": pa.array([0, 1, 2**63 - 1], type=pa.timestamp("ns", "UTC"))})
    b = pa.table({"value": pa.array([0, 2, 2**63 - 1], type=pa.timestamp("ns", "UTC"))})
    assert run(tmp_path, a, b, spec).state == "different"
    assert run(tmp_path, a, a, spec).state == "equivalent"
    ms = pa.table({"value": pa.array([1], type=pa.timestamp("ms", "UTC"))})
    ns = pa.table({"value": pa.array([1000000], type=pa.timestamp("ns", "UTC"))})
    assert run(tmp_path, ms, ns, spec, policy=LOSSLESS).state == "equivalent"
    narrow = contract((column(kind=ef.TimestampType(unit="ms", timezone="UTC")),))
    assert "timestamp_granularity" in codes(run(tmp_path, a, a, narrow, policy=LOSSLESS))


@pytest.mark.parametrize(
    "ambiguous,state", [("reject", "different"), ("earlier", "equivalent"), ("later", "different")]
)
def test_dst_naive_policy(tmp_path, ambiguous, state):
    policy = ef.TimestampPolicy(
        granularity="ns",
        timezone="Europe/Madrid",
        naive="assume_zone",
        comparison="instant",
        ambiguous=ambiguous,
        closed="both",
    )
    spec = contract(
        (
            column(
                kind=ef.TimestampType(unit="ns", timezone="Europe/Madrid"), temporal_policy=policy
            ),
        ),
        family="dates",
    )
    a = pa.table({"value": pa.array([datetime(2024, 10, 27, 2, 30)], type=pa.timestamp("ns"))})
    b = pa.table(
        {
            "value": pa.array(
                [datetime.fromisoformat("2024-10-27T02:30:00+02:00")],
                type=pa.timestamp("ns", "Europe/Madrid"),
            )
        }
    )
    assert run(tmp_path, a, b, spec, policy=LOSSLESS).state == state
    gap = pa.table({"value": pa.array([datetime(2024, 3, 31, 2, 30)], type=pa.timestamp("ns"))})
    result = run(tmp_path, gap, gap, spec, policy=LOSSLESS)
    assert result.state == "different" and "nonexistent_time" in codes(result)


def test_zones_instant_wall_time_and_transport_range(tmp_path):
    a = pa.table({"value": pa.array([0], type=pa.timestamp("ns", "UTC"))})
    b = pa.table({"value": pa.array([0], type=pa.timestamp("ns", "America/Guayaquil"))})
    spec = contract((column(kind=ef.TimestampType(unit="ns", timezone="UTC")),))
    assert run(tmp_path, a, b, spec).state == "different"
    assert run(tmp_path, a, b, spec, policy=LOSSLESS).state == "equivalent"
    wall = ef.TimestampPolicy(
        granularity="ns",
        timezone="UTC",
        naive="reject",
        comparison="wall_time",
        ambiguous="reject",
        closed="both",
    )
    assert (
        run(
            tmp_path,
            a,
            b,
            contract(
                (column(kind=ef.TimestampType(unit="ns", timezone="UTC"), temporal_policy=wall),)
            ),
            policy=LOSSLESS,
        ).state
        == "different"
    )
    extreme = pa.table({"value": pa.array([2**63 - 1], type=pa.timestamp("s"))})
    assert (
        run(
            tmp_path,
            extreme,
            extreme,
            contract((column(kind=ef.TimestampType(unit="s", timezone=None)),)),
        ).state
        == "equivalent"
    )


def test_allowed_values_intervals_and_nonnullable(tmp_path):
    a = pa.table({"value": [2, None]})
    col = column(nullable=False, allowed_values=(ef.IntegerValue(value=1),))
    result = run(tmp_path, a, a, contract((col,)))
    assert result.state == "different" and {"null_forbidden", "allowed_values"} <= set(
        codes(result)
    )
    col = column(
        kind=ef.DateType(),
        temporal_policy=ef.DatePolicy(
            closed="left",
            lower=ef.DateValue(value="1970-01-01"),
            upper=ef.DateValue(value="1970-01-02"),
        ),
    )
    dates = pa.table({"value": pa.array([0, 1], type=pa.date32())})
    assert "temporal_interval" in codes(run(tmp_path, dates, dates, contract((col,))))


def test_spill_hash_collisions_batches_partitions_and_summary(tmp_path, monkeypatch):
    module = importlib.import_module("equiframe.comparison")
    monkeypatch.setattr(module, "_partition", lambda value, count: 0)
    a = pa.table({"value": list(range(31)) + [0] * 100})
    b = pa.table({"value": list(range(30)) + [0] * 101})
    reference = None
    for batch, parts in [(1, 1), (5, 7), (1000, 16)]:
        result = run(
            tmp_path,
            a,
            b,
            options=ef.ComparisonOptions(
                batch_rows=batch, partitions=parts, sqlite_cache_kib=1, max_examples=1
            ),
        )
        assert result.state == "different" and result.complete
        assert len(result.examples) == 1 and result.counts.difference_records == 2
        full = list(ef.iter_differences(result.differences))
        comparison = [(v.left, v.right, v.left_count, v.right_count) for v in full]
        if reference is not None:
            assert comparison == reference
        reference = comparison


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
def test_budget_exhaustion_never_equivalent(tmp_path, options):
    a = pa.table({"value": [0.0, 1.0]})
    b = pa.table({"value": [3.0, 4.0]})
    result = run(tmp_path, a, b, approximate(), options=options)
    assert result.state == "not_evaluable" and not result.complete and not result.counts.final
    assert result.diagnostics[0].code == "resource_exhausted"


def test_partial_differences_retained_on_resource_limit(tmp_path):
    a = pa.table({"value": [None, None, None]})
    # Explicit physical dtype prevents schema-only failure.
    a = pa.table({"value": pa.array([None, None, None], type=pa.int64())})
    result = run(
        tmp_path,
        a,
        a,
        contract((column(nullable=False),)),
        options=ef.ComparisonOptions(max_rows=2),
    )
    assert result.state == "not_evaluable" and not result.complete
    assert (
        result.counts.difference_records == 2
        and len(list(ef.iter_differences(result.differences))) == 2
    )


def test_cancel_timeout_and_unsupported(tmp_path, monkeypatch):
    a = pa.table({"value": [1]})
    token = ef.CancellationToken()
    token.cancel()
    assert run(tmp_path, a, a, cancellation=token).diagnostics[0].code == "cancelled"
    module = importlib.import_module("equiframe.comparison")
    from types import SimpleNamespace

    ticks = iter([0.0, 2.0])
    monkeypatch.setattr(module, "time", SimpleNamespace(perf_counter=lambda: next(ticks, 2.0)))
    assert (
        run(tmp_path, a, a, options=ef.ComparisonOptions(timeout_seconds=1.0)).diagnostics[0].code
        == "timeout"
    )
    nested = pa.table({"value": [[1]]})
    assert run(tmp_path, nested, nested).diagnostics[0].code == "unsupported_capability"


@pytest.mark.parametrize("format_name", ["arrow", "parquet"])
def test_local_files_integrity_and_evidence_tampering(tmp_path, format_name):
    a = pa.table({"value": [1, 2, 2]})
    path = tmp_path / ("input." + format_name)
    if format_name == "arrow":
        with path.open("wb") as out, pa.ipc.new_file(out, a.schema) as writer:
            writer.write_table(a, max_chunksize=1)
    else:
        pq.write_table(a, path, row_group_size=1)
    ref = ef.LocalArtifactStore(tmp_path / "store").put(path, media_type="application/octet-stream")
    result = run(tmp_path, ref, a)
    assert result.state == "equivalent"
    assert run(tmp_path, path, a).state == "equivalent"
    assert path.read_bytes()
    broken = ref.model_copy(update={"sha256": "0" * 64})
    assert run(tmp_path, broken, a).diagnostics[0].code == "invalid_artifact"
    diff_path = tmp_path / result.comparison_id / "differences.jsonl"
    diff_path.write_bytes(b"{}\n")
    with pytest.raises(ef.ArtifactIntegrityError):
        list(ef.iter_differences(result.differences))


def test_invalid_inputs_and_formats(tmp_path):
    a = pa.table({"value": [1]})
    assert run(tmp_path, object(), a).state == "not_evaluable"
    assert run(tmp_path, tmp_path / "missing.arrow", a).state == "not_evaluable"
    result = run(tmp_path, a, a)
    document = json.loads(result.model_dump_json())
    document["schema_version"] = "99.0"
    with pytest.raises(ValidationError):
        ef.ComparisonResult.model_validate_json(json.dumps(document))
    document = json.loads(result.model_dump_json())
    document["complete"] = False
    with pytest.raises(ValidationError):
        ef.ComparisonResult.model_validate_json(json.dumps(document))


def test_repeated_runs_preserve_contract_and_do_not_overwrite(tmp_path):
    spec = contract()
    original = ef.canonical_contract_bytes(spec)
    table = pa.table({"value": [1, 1, 2]})
    before = table.to_pylist()
    a = run(tmp_path, table, table, spec)
    b = run(tmp_path, table, table, spec)
    assert a.comparison_id != b.comparison_id and table.to_pylist() == before
    assert ef.canonical_contract_bytes(spec) == original
    assert a.spec_sha256 == b.spec_sha256


def test_real_partition_changes_preserve_complete_differences(tmp_path):
    a = pa.table({"value": [*range(21), 1, 1]})
    b = pa.table({"value": [*range(18), 2, 2]})
    evidence = []
    for rows, partitions in ((1, 1), (7, 5), (100, 31)):
        result = run(
            tmp_path, a, b, options=ef.ComparisonOptions(batch_rows=rows, partitions=partitions)
        )
        assert result.complete and result.state == "different"
        evidence.append(
            (
                result.counts,
                sorted(v.model_dump_json() for v in ef.iter_differences(result.differences)),
            )
        )
    assert evidence[0] == evidence[1] == evidence[2]


def test_cancel_after_observed_difference_and_spill_cleanup(tmp_path, monkeypatch):
    module = importlib.import_module("equiframe.comparison")
    original = module._Work.check
    observed_database = []

    def checkpoint(work, cost=1):
        observed_database.append((work.directory / "work.sqlite").is_file())
        if work.differences >= 1:
            work.cancellation.cancel()
        original(work, cost)

    monkeypatch.setattr(module._Work, "check", checkpoint)
    result = run(tmp_path, pa.table({"value": [1]}), pa.table({"value": [2]}))
    assert result.state == "not_evaluable" and result.diagnostics[0].code == "cancelled"
    assert (
        result.counts.difference_records == 1
        and len(list(ef.iter_differences(result.differences))) == 1
    )
    assert all(observed_database)


def test_sqlite_disk_limit_during_ingestion(tmp_path):
    table = pa.table({"value": list(range(1000))})
    result = run(tmp_path, table, table, options=ef.ComparisonOptions(max_disk_bytes=150000))
    assert result.state == "not_evaluable" and result.diagnostics[0].code == "resource_exhausted"
    assert 0 < result.counts.left_rows < 1000


@pytest.mark.parametrize(
    ("message", "result_code", "expected_code"),
    [
        ("database or disk is full", None, "resource_exhausted"),
        ("database is locked", None, "evaluation_failed"),
        ("external database or disk is full text", None, "evaluation_failed"),
        ("database or disk is full", 1, "evaluation_failed"),
        ("localized SQLite diagnostic", 13, "resource_exhausted"),
    ],
)
def test_sqlite_error_without_result_code_keeps_specific_failure(
    tmp_path, monkeypatch, message, result_code, expected_code
):
    comparison_module = importlib.import_module("equiframe.comparison")
    error = sqlite3.OperationalError(message)
    if result_code is not None:
        error.sqlite_errorcode = result_code

    def fail_ingestion(self, source, side):
        raise error

    monkeypatch.setattr(comparison_module._Work, "ingest", fail_ingestion)
    table = pa.table({"value": [1, 1, 2]})
    result = run(tmp_path, table, table)
    assert result.state == "not_evaluable"
    assert result.complete is False and result.counts.final is False
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == expected_code
    assert message not in result.diagnostics[0].message


def test_untrusted_numeric_expansion_is_budgeted(tmp_path):
    result = run(
        tmp_path, pa.table({"value": [1.0]}), pa.table({"value": [2.0]}), approximate("1e10000000")
    )
    assert result.state == "not_evaluable" and result.diagnostics[0].code == "resource_exhausted"


def test_unknown_zone_and_duplicate_json_are_rejected(tmp_path):
    table = pa.table({"value": pa.array([0], type=pa.timestamp("ns", "Unknown/Zone"))})
    result = run(
        tmp_path,
        table,
        table,
        contract((column(kind=ef.TimestampType(unit="ns", timezone="UTC")),)),
        policy=LOSSLESS,
    )
    assert (
        result.state == "not_evaluable" and result.diagnostics[0].code == "unsupported_capability"
    )
    manifest = tmp_path / result.comparison_id / "comparison.json"
    raw = manifest.read_text(encoding="utf-8")
    manifest.write_text('{"state":"equivalent",' + raw[1:], encoding="utf-8")
    with pytest.raises(ef.ContractParseError):
        ef.read_comparison(manifest)


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "integer", "value": "1.5"},
        {"kind": "float", "value": "NaN"},
        {"kind": "infinity", "value": "0"},
        {"kind": "timestamp", "value": "5"},
    ],
)
def test_evidence_scalars_reject_invalid_tags(value):
    with pytest.raises(ValidationError):
        ef.ComparisonValue.model_validate(value)


@pytest.mark.parametrize("sentinel", ["blank", "zero", "nan"])
def test_authorized_missing_key_repetitions_are_incomplete_not_duplicate(tmp_path, sentinel):
    if sentinel == "blank":
        col = column(
            "id",
            ef.StringType(),
            null_policy=ef.NullPolicy(
                representations=("null", "empty_string"), justification="blank keys absent"
            ),
        )
        ids = pa.array(["", ""], type=pa.string())
    elif sentinel == "zero":
        col = column(
            "id",
            null_policy=ef.NullPolicy(
                representations=("null", "zero"), justification="zero keys absent"
            ),
        )
        ids = pa.array([0, 0], type=pa.int64())
    else:
        col = column(
            "id",
            ef.FloatType(bits=64),
            nan_policy=ef.NaNPolicy(handling="as_null", justification="NaN keys absent"),
        )
        ids = pa.array([float("nan"), float("nan")], type=pa.float64())
    table = pa.table({"id": ids, "value": [1, 2]})
    spec = contract((col, column()), keys=(key(incomplete="allow"),))
    result = run(tmp_path, table, table.take([1, 0]), spec)
    assert result.state == "equivalent" and result.strategy == "multiset"
    assert result.counts.matched_rows == 2 and not result.counts.contract_violations
