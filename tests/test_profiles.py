"""Section 3.6 expectations computed independently, including unavailable evidence."""

import json
import math
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from rule_helpers import captured

import equiframe as ef


def column(name, dtype):
    extra = {}
    if pa.types.is_floating(dtype):
        logical = ef.FloatType(bits=64)
        extra = {"nan_policy": ef.NaNPolicy(handling="distinct")}
    elif pa.types.is_integer(dtype):
        logical = ef.IntegerType(bits=64, signed=True)
    elif pa.types.is_decimal(dtype):
        logical = ef.DecimalType(precision=dtype.precision, scale=dtype.scale)
    else:
        logical = ef.StringType()
    if logical.kind in ("integer", "float", "decimal"):
        extra["numeric_policy"] = ef.NumericPolicy(comparison="exact", unit="synthetic")
    return ef.ColumnSpec(
        name=name,
        logical_type=logical,
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        **extra,
    )


def make_run(tmp_path, family, output, inputs=None):
    inputs = inputs or {"source": output}

    def table(name, values):
        return ef.TableSpec(
            name=name,
            schema_spec=ef.TableSchema(
                columns=tuple(column(f.name, f.type) for f in values.schema),
                keys=(),
                multiplicity="preserve",
                order=ef.IgnoredOrder(),
            ),
        )

    contract = ef.Contract(
        schema_version="1.0",
        contract_id="synthetic.profile",
        revision=1,
        family=family,
        inputs=tuple(table(n, t) for n, t in inputs.items()),
        output=table("result", output),
        rules=(),
        preconditions=(),
    )
    return captured(contract, inputs, output, tmp_path)


def feature(metric, col=None, **kwargs):
    return ef.ProfileFeature(
        name=kwargs.pop("name", metric),
        metric=metric,
        table=kwargs.pop("table", "result"),
        columns=(col,) if col else (),
        **kwargs,
    )


def profile(tmp_path, run, *features, **kwargs):
    return ef.profile_execution(
        run,
        spec=ef.ProfileSpec(family=run.plan.contract.family, features=features),
        work_dir=tmp_path / "profiles",
        **kwargs,
    )


def test_null_nan_empty_zero_are_distinct_and_column_denominators(tmp_path):
    table = pa.table(
        {
            "x": pa.array([None, float("nan"), 0.0, 2.0], from_pandas=False),
            "text": ["", None, "0", "hello"],
        }
    )
    run = make_run(tmp_path / "run", "nulls_types", table)
    before = table.to_pydict()
    result = profile(
        tmp_path,
        run,
        feature("log_filas"),
        feature("tasa_nulos", "x"),
        feature("tasa_nan", "x"),
        feature("tasa_nulos", "text", name="text_null"),
    )
    logs, nulls, nan, text = result.vector.observations
    assert logs.value == math.log(5)
    assert (nulls.numerator, nulls.denominator, nulls.value) == (1, 4, 0.25)
    assert (nan.numerator, nan.denominator, nan.value) == (1, 4, 0.25)
    assert (nulls.support.missing, nulls.support.nan, nulls.support.zeros) == (1, 1, 1)
    assert (text.value, text.support.empty_strings) == (0.25, 1)
    assert table.to_pydict()["text"] == before["text"]
    assert result.complete
    saved = tmp_path / "profiles" / result.metadata.profile_id / "profile.json"
    assert ef.read_profile(saved) == result


def test_empty_log_is_zero_but_rates_undefined(tmp_path):
    run = make_run(tmp_path / "run", "nulls_types", pa.table({"x": pa.array([], pa.float64())}))
    result = profile(
        tmp_path, run, feature("log_filas"), feature("tasa_nulos", "x"), feature("tasa_nan", "x")
    )
    log, nulls, nan = result.vector.observations
    assert log.value == 0 and log.state == "available"
    for item in (nulls, nan):
        assert (item.state, item.value, item.numerator, item.denominator) == (
            "undefined",
            None,
            0,
            0,
        )


@pytest.mark.parametrize("family", ["joins", "duplicates_order", "aggregations"])
def test_output_input_ratio_and_empty_input(tmp_path, family):
    output = pa.table({"x": [1, 2, 3]})
    source = pa.table({"x": pa.array([], pa.int64())})
    run = make_run(tmp_path / "run", family, output, {"source": source})
    item = profile(tmp_path, run, feature("razon_salida_entrada", denominator_table="source"))
    observed = item.vector.observations[0]
    assert (observed.state, observed.numerator, observed.denominator) == ("undefined", 3, 0)


def test_composite_duplicates_exclude_incomplete_keys_and_preserve_decimal(tmp_path):
    table = pa.table(
        {
            "a": ["01", "01", "1", None, "01"],
            "b": pa.array(
                [Decimal("0.01"), Decimal("0.01"), Decimal("0.01"), Decimal("0.01"), None],
                pa.decimal128(30, 2),
            ),
        }
    )
    run = make_run(tmp_path / "run", "duplicates_order", table)
    dup = ef.ProfileFeature(
        name="dup", metric="prop_duplicados", table="result", columns=("a", "b")
    )
    result = profile(tmp_path, run, dup, feature("cardinalidad_rel", "b"))
    duplication, cardinality = result.vector.observations
    assert (duplication.numerator, duplication.denominator, duplication.value) == (1, 3, 1 / 3)
    assert duplication.support.incomplete_keys == 2
    assert (cardinality.numerator, cardinality.denominator) == (1, 4)


@pytest.mark.parametrize("matches,expected", [("never", 3)])
def test_unmatched_join_counts_rows_not_distinct_keys(tmp_path, matches, expected):
    left = pa.table({"key": ["a", "x", "x", None]})
    right = pa.table({"key": ["a", "a", None]})
    run = make_run(tmp_path / "run", "joins", left, {"left": left, "right": right})
    result = profile(
        tmp_path,
        run,
        feature(
            "claves_sin_pareja",
            "key",
            table="left",
            right_table="right",
            right_columns=("key",),
            null_matches=matches,
        ),
        feature("expansion_union", denominator_table="left"),
    )
    unmatched, expansion = result.vector.observations
    assert (unmatched.numerator, unmatched.denominator) == (expected, 4)
    assert unmatched.support.incomplete_keys == 1
    assert expansion.value == 1


def test_duplicate_expansion_ratio_rejected_without_data(tmp_path):
    with pytest.raises(ValidationError, match="duplicate formula"):
        ef.ProfileSpec(
            family="joins",
            features=(
                feature("expansion_union", denominator_table="source"),
                feature("razon_salida_entrada", denominator_table="source"),
            ),
        )


def test_conversion_receipt_has_real_attempt_denominator(tmp_path):
    table = pa.table({"raw": [None, "", "0", "1.2", "bad"]})
    run = make_run(tmp_path / "run", "nulls_types", table)
    target = column("amount", pa.decimal128(10, 2))
    definition = feature("conversiones_fallidas", "raw", table="source", target=target)
    receipt = ef.ConversionReceipt(
        feature=definition.name,
        source_sha256=run.inputs[0].data.sha256,
        source_column="raw",
        output_sha256=run.output.data.sha256,
        target=target,
        attempted_rows=(1, 2, 3, 4),
        failed_rows=(1, 4),
        producer_version="synthetic.instrumented-1",
    )
    result = profile(tmp_path, run, definition, conversions=(receipt,))
    item = result.vector.observations[0]
    assert (item.value, item.numerator, item.denominator) == (0.5, 2, 4)
    assert (item.support.missing, item.support.empty_strings) == (1, 1)
    assert result.metadata.conversion_receipts == (receipt,)
    missing = profile(tmp_path, run, definition)
    assert not missing.complete and missing.vector.observations[0].state == "not_evaluable"
    bad = receipt.model_copy(update={"source_sha256": "0" * 64})
    assert not profile(tmp_path, run, definition, conversions=(bad,)).complete
    bad_null = receipt.model_copy(update={"attempted_rows": (0, 1, 2, 3, 4)})
    assert not profile(tmp_path, run, definition, conversions=(bad_null,)).complete


def test_date_invalidity_is_not_cohort_membership(tmp_path):
    table = pa.table({"day": [None, "", "2025-02-29", "2025-01-01", "2026-01-01"]})
    run = make_run(tmp_path / "run", "dates", table)
    target = ef.ColumnSpec(
        name="day",
        logical_type=ef.DateType(),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        temporal_policy=ef.DatePolicy(closed="both"),
    )
    item = profile(tmp_path, run, feature("fechas_invalidas", "day", target=target))
    assert (item.vector.observations[0].numerator, item.vector.observations[0].denominator) == (
        2,
        4,
    )
    bounded = target.model_copy(
        update={
            "temporal_policy": ef.DatePolicy(
                lower=ef.DateValue(value="2025-01-01"),
                upper=ef.DateValue(value="2026-01-01"),
                closed="left",
            )
        }
    )
    item = profile(tmp_path, run, feature("fechas_invalidas", "day", target=bounded))
    assert item.vector.observations[0].numerator == 3


def test_timestamp_offset_day_boundary_and_nanoseconds(tmp_path):
    table = pa.table(
        {
            "stamp": [
                "2025-01-01T04:59:59.999999999Z",
                "2025-01-01T05:00:00Z",
                "2025-01-01T00:00:00",
                None,
                "bad",
            ]
        }
    )
    run = make_run(tmp_path / "run", "dates", table)
    target = ef.ColumnSpec(
        name="instant",
        logical_type=ef.TimestampType(unit="ns", timezone="America/Guayaquil"),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        temporal_policy=ef.TimestampPolicy(
            timezone="America/Guayaquil",
            granularity="ns",
            naive="reject",
            comparison="instant",
            ambiguous="reject",
            lower=ef.TimestampValue(value="2025-01-01T00:00:00-05:00"),
            closed="left",
        ),
    )
    result = profile(tmp_path, run, feature("fechas_invalidas", "stamp", target=target))
    assert (result.vector.observations[0].numerator, result.vector.observations[0].denominator) == (
        3,
        4,
    )


@pytest.mark.parametrize(
    "options",
    [
        ef.ProfileOptions(max_rows=1),
        ef.ProfileOptions(max_work=1),
        ef.ProfileOptions(max_artifact_bytes=1),
        ef.ProfileOptions(max_distinct=1),
    ],
)
def test_resource_limits_never_become_zero_or_imputable_missing(tmp_path, options):
    run = make_run(tmp_path / "run", "duplicates_order", pa.table({"x": [1, 2, 3]}))
    result = profile(tmp_path, run, feature("cardinalidad_rel", "x"), options=options)
    assert not result.complete
    assert result.vector.observations[0].state == "not_evaluable"


def test_cancel_and_corrupt_artifact_are_not_evaluable(tmp_path):
    run = make_run(tmp_path / "run", "nulls_types", pa.table({"x": [1, 2]}))
    token = ef.CancellationToken()
    token.cancel()
    assert not profile(tmp_path, run, feature("log_filas"), cancellation=token).complete
    from equiframe.local import local_path

    local_path(run.inputs[0].data).write_bytes(b"corrupt")
    assert not profile(tmp_path, run, feature("log_filas")).complete


def test_family_non_applicability_is_explicit(tmp_path):
    run = make_run(tmp_path / "run", "dates", pa.table({"x": [1, 2]}))
    result = profile(tmp_path, run, feature("tasa_nan", "x"))
    assert result.complete
    item = result.vector.observations[0]
    assert (item.state, item.value, item.reason) == (
        "not_applicable",
        None,
        "family_not_applicable",
    )


def test_metadata_never_changes_vector_and_unknown_features_rejected(tmp_path):
    run = make_run(tmp_path / "run", "nulls_types", pa.table({"x": [1, 2]}))
    a = profile(tmp_path, run, feature("log_filas"))
    changed = run.model_copy(
        update={"run_id": "other", "execution_id": "other", "implementation_version": "another"}
    )
    b = profile(tmp_path, changed, feature("log_filas"))
    assert a.vector == b.vector and a.metadata != b.metadata
    for forbidden in ("engine", "mutation", "oracle_label", "partition", "scenario_id"):
        data = feature("log_filas").model_dump(mode="json") | {"metric": forbidden}
        with pytest.raises(ValidationError):
            ef.ProfileFeature.model_validate_json(json.dumps(data))
    with pytest.raises(ValidationError):
        ef.ProfileVector.model_validate_json(a.vector.model_dump_json()[:-1] + ',"label":1}')


@given(st.lists(st.one_of(st.none(), st.integers(-3, 3)), max_size=30))
@settings(max_examples=30, deadline=None)
def test_duplicate_formula_permutation_property(values):
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        table = pa.table({"x": pa.array(values, pa.int64())})
        run = make_run(root / "a", "duplicates_order", table)
        other = make_run(
            root / "b",
            "duplicates_order",
            table.take(pa.array(list(reversed(range(len(values)))), pa.int64())),
        )
        a = profile(root, run, feature("prop_duplicados", "x")).vector.observations[0]
        b = profile(root, other, feature("prop_duplicados", "x")).vector.observations[0]
        assert a == b
        present = [v for v in values if v is not None]
        assert a.denominator == len(present)
        assert a.numerator == len(present) - len(set(present))
