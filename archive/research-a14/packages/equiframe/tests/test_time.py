from pathlib import Path

import pytest
from conftest import change, document
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from equiframe import (
    ContractValidationError,
    DateValue,
    TimestampPolicy,
    TimestampValue,
    canonical_contract_bytes,
    validate_contract,
    write_contract,
)


@pytest.mark.parametrize(
    ("path", "value", "code"),
    [
        (("logical_type", "timezone"), "Invalid/Zone", "value_error"),
        (("temporal_policy", "timezone"), "UTC", "temporal_zone"),
        (("temporal_policy", "granularity"), "us", "temporal_precision"),
        (("temporal_policy", "lower", "value"), "2000-02-29T00:00:00.000000001", "missing_offset"),
        (
            ("temporal_policy", "lower", "value"),
            "2000-02-29T00:00:00.000000001Z",
            "zone_offset_mismatch",
        ),
        (
            ("temporal_policy", "upper", "value"),
            "2000-02-28T23:59:59.999999999-05:00",
            "temporal_interval",
        ),
        (("temporal_policy", "kind"), "date", "extra_forbidden"),
    ],
)
def test_timestamp_type_policy_and_bounds_are_validated(
    path: tuple[str | int, ...],
    value: object,
    code: str,
) -> None:
    full_path = ("output", "schema_spec", "columns", 2, *path)
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(change(document("dates"), full_path, value))
    assert any(issue.code == code for issue in caught.value.issues), str(caught.value)


@pytest.mark.parametrize(
    "value",
    [
        "2001-02-29",
        "2000-2-29",
        "2000-02-29T00:00:00",
        "0000-01-01",
        "2000-13-01",
    ],
)
def test_date_literals_require_real_calendar_days(value: str) -> None:
    with pytest.raises(ValidationError):
        DateValue(value=value)


@pytest.mark.parametrize(
    "value",
    [
        "2001-02-29T12:00:00Z",
        "2000-02-29 12:00:00Z",
        "2000-02-29T24:00:00Z",
        "2000-02-29T12:00:60Z",
        "2000-02-29T12:00:00.1234567890Z",
        "2000-02-29T12:00:00+24:00",
        "2000-02-29T12:00:00+00:60",
        "2000-02-29T12:00:00-00:00",
    ],
)
def test_timestamp_literals_reject_invalid_or_ambiguous_encoding(value: str) -> None:
    with pytest.raises(ValidationError):
        TimestampValue(value=value)


def test_timestamp_ns_zone_offset_and_text_are_preserved(tmp_path: Path) -> None:
    contract = validate_contract(document("dates"))
    text = "2000-02-29T12:00:00.123456789-05:00"
    wire = canonical_contract_bytes(contract)
    assert text.encode() in wire
    assert b'"zone":"America/Guayaquil"' in wire
    path = tmp_path / "time.json"
    write_contract(contract, path)
    value = validate_contract(path.read_bytes()).output.schema_spec.columns[2].allowed_values[0]
    assert isinstance(value, TimestampValue)
    assert value.value == text
    assert value.zone == "America/Guayaquil"


@given(st.integers(min_value=0, max_value=999_999_998))
@settings(max_examples=40, derandomize=True)
def test_nanosecond_ordering_and_offset_equivalence_are_exact(fraction: int) -> None:
    local = TimestampValue(value=f"2000-02-29T00:00:00.{fraction:09d}-05:00")
    utc = TimestampValue(value=f"2000-02-29T05:00:00.{fraction:09d}Z")
    following = TimestampValue(value=f"2000-02-29T05:00:00.{fraction + 1:09d}Z")
    assert local.nanoseconds(instant=True) == utc.nanoseconds(instant=True)
    assert following.nanoseconds(instant=True) - utc.nanoseconds(instant=True) == 1
    restored = TimestampValue.model_validate_json(local.model_dump_json())
    assert restored.value == local.value


def policy(**updates: object) -> TimestampPolicy:
    data = {
        "granularity": "ns",
        "timezone": "America/New_York",
        "naive": "assume_zone",
        "comparison": "instant",
        "ambiguous": "reject",
        "closed": "both",
    }
    data.update(updates)
    return TimestampPolicy.model_validate(data)


def test_naive_timestamps_require_an_explicit_consistent_policy() -> None:
    with pytest.raises(ValidationError, match="missing_timezone"):
        policy(timezone=None)
    with pytest.raises(ValidationError, match="naive_policy"):
        policy(naive="preserve")
    with pytest.raises(ValidationError, match="naive_timestamp"):
        policy(naive="reject", lower=TimestampValue(value="2000-01-01T00:00:00"))
    valid = policy(
        timezone=None,
        naive="preserve",
        comparison="wall_time",
        lower=TimestampValue(value="2000-01-01T00:00:00"),
    )
    assert valid.lower is not None and not valid.lower.has_offset


def test_dst_gap_and_fold_do_not_get_silent_normalization() -> None:
    gap = TimestampValue(value="2024-03-10T02:30:00")
    fold = TimestampValue(value="2024-11-03T01:30:00")
    with pytest.raises(ValidationError, match="nonexistent_time"):
        policy(lower=gap)
    with pytest.raises(ValidationError, match="ambiguous_time"):
        policy(lower=fold)
    assert policy(lower=fold, ambiguous="earlier").lower == fold
    assert policy(lower=fold, ambiguous="later").lower == fold
    # Declared earlier fold is before 06:00Z; later fold is after it.
    upper = TimestampValue(value="2024-11-03T01:00:00-05:00")
    assert policy(lower=fold, upper=upper, ambiguous="earlier").upper == upper
    with pytest.raises(ValidationError, match="temporal_interval"):
        policy(lower=fold, upper=upper, ambiguous="later")


def test_equal_excluded_and_reversed_date_intervals_are_rejected() -> None:
    path = ("output", "schema_spec", "columns", 1, "temporal_policy", "upper", "value")
    with pytest.raises(ContractValidationError, match="empty_interval"):
        validate_contract(change(document("dates"), path, "2000-02-01"))
    with pytest.raises(ContractValidationError, match="temporal_interval"):
        validate_contract(change(document("dates"), path, "2000-01-31"))
