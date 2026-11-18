"""Reject source repairs, signed-zero loss and decimal-context rounding."""

import importlib.util
import io
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

PATH = Path(__file__).parents[1] / "tools/sercop_validation_workload.py"
SPEC = importlib.util.spec_from_file_location("sercop_workload", PATH)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_stream_retains_exact_fraction_and_negative_integer_zero():
    [value] = list(
        tool.packages(
            io.StringIO('[{"amount":0.12345678901234567890123456789,"zero":-0}]'),
            chunk_size=4,
        )
    )
    assert str(value["amount"]) == "0.12345678901234567890123456789"
    assert value["zero"].is_zero() and value["zero"].is_signed()


@pytest.mark.parametrize(
    "text", ['[{"a":1,"a":2}]', '[{"a":NaN}]', "[{},]", "[{}] trailing", "[{", "[1]"]
)
def test_ambiguous_invalid_or_nonobject_streams_are_rejected(text):
    with pytest.raises(ValueError):
        list(tool.packages(io.StringIO(text), chunk_size=3))


def test_absent_and_null_values_remain_distinct():
    absent = tool.award_value({})
    null = tool.award_value({"value": None})
    assert absent["value_state"] == "missing"
    assert null["value_state"] == "null"
    assert absent["amount"] is null["amount"] is None


@pytest.mark.parametrize("value", [False, "invalid", [], 1])
def test_invalid_value_shape_is_not_repaired_to_null(value):
    with pytest.raises(ValueError):
        tool.award_value({"value": value})


@pytest.mark.parametrize("value", [True, 1.5, Decimal("-0"), Decimal("NaN")])
def test_unsupported_monetary_values_are_rejected(value):
    with pytest.raises(ValueError):
        tool.award_value({"value": {"currency": "USD", "amount": value}})


def test_rescaled_coefficient_budget_is_exact_with_small_caller_context():
    with localcontext() as context:
        context.prec = 5
        assert tool.scaled_digits(Decimal(12345678901234567890123456789), 0) == 29
        assert tool.scaled_digits(Decimal(12345678901234567890123456789), 10) == 39
        assert tool.scaled_digits(Decimal(0), 38) == 1
        with pytest.raises(ValueError):
            tool.scaled_digits(Decimal("0.001"), 2)


def test_json_package_size_budget_is_not_silently_ignored():
    with pytest.raises(ValueError):
        list(
            tool.packages(
                io.StringIO('[{"value":"too large"}]'), chunk_size=3, max_item_chars=5
            )
        )


@pytest.mark.parametrize(
    "right_value,expected_state", [(1, "equivalent"), (2, "different")]
)
def test_readback_resolves_actual_manifest_and_verifies_evidence_bytes(
    tmp_path, right_value, expected_state
):
    import equiframe as ef
    import pyarrow as pa
    from equiframe.local import local_path

    result = ef.diff(
        pa.table({"value": [1]}), pa.table({"value": [right_value]}), work_dir=tmp_path
    )
    assert result.state == expected_state and result.complete
    assert tool.readback(ef, tmp_path, result) == result.counts.difference_records
    local_path(result.differences).write_bytes(b"changed evidence\n")
    with pytest.raises(ef.ArtifactIntegrityError):
        tool.readback(ef, tmp_path, result)


def test_native_operations_preserve_source_flags_and_only_deliberate_changes():
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    rows = [
        {
            "ocid": "a",
            "award_id": "1",
            "currency": "USD",
            "amount": Decimal("0.123456"),
            "value_state": "present",
            "currency_state": "present",
            "amount_state": "present",
        },
        {
            "ocid": "a",
            "award_id": "2",
            "currency": None,
            "amount": None,
            "value_state": "missing",
            "currency_state": "not_applicable",
            "amount_state": "not_applicable",
        },
        {
            "ocid": "b",
            "award_id": "1",
            "currency": None,
            "amount": None,
            "value_state": "null",
            "currency_state": "not_applicable",
            "amount_state": "not_applicable",
        },
    ]
    releases = [
        {"ocid": "a", "release_date": "2025-01-01", "release_date_state": "present"},
        {"ocid": "b", "release_date": None, "release_date_state": "null"},
    ]
    awards = pa.Table.from_pylist(
        rows,
        schema=pa.schema(
            [
                (key, pa.decimal128(38, 6) if key == "amount" else pa.string())
                for key in tool.AWARD_COLUMNS
            ]
        ),
    )
    release_table = pa.Table.from_pylist(releases)
    expected = {
        "nulls_types": rows,
        "joins": [
            {**rows[0], "release_date": "2025-01-01", "release_date_state": "present"},
            {**rows[1], "release_date": "2025-01-01", "release_date_state": "present"},
            {**rows[2], "release_date": None, "release_date_state": "null"},
        ],
        "aggregations": [
            {"currency": "USD", "award_count": 1},
            {"currency": None, "award_count": 2},
        ],
    }

    def sorted_rows(frame):
        if isinstance(frame, pd.DataFrame):
            frame = pa.Table.from_pandas(frame, preserve_index=False)
        elif isinstance(frame, pl.DataFrame):
            frame = frame.to_arrow()
        return sorted(
            frame.to_pylist(),
            key=lambda row: (
                str(row.get("currency"))
                if "award_id" not in row
                else (row["ocid"], row["award_id"])
            ),
        )

    positive, _ = tool.native_outputs(awards, release_table, rows[0])
    negative, _ = tool.native_outputs(awards, release_table, rows[0], corrupt=True)
    changed = {
        "nulls_types": [{**rows[0], "amount": Decimal("1.123456")}, rows[1], rows[2]],
        "joins": [
            {**expected["joins"][0], "release_date": "0001-01-01"},
            *expected["joins"][1:],
        ],
        "aggregations": [
            {"currency": "USD", "award_count": 2},
            {"currency": None, "award_count": 2},
        ],
    }
    for family in tool.FAMILIES:
        sort_key = lambda row: (
            str(row.get("currency"))
            if "award_id" not in row
            else (row["ocid"], row["award_id"])
        )
        for engine in tool.ENGINES:
            assert sorted_rows(positive[family][engine]) == sorted(
                expected[family], key=sort_key
            )
            assert sorted_rows(negative[family][engine]) == sorted(
                changed[family], key=sort_key
            )
