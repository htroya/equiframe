import pytest
from conftest import change, document
from pydantic import TypeAdapter, ValidationError

from equiframe import (
    ContractValidationError,
    DecisionState,
    OracleState,
    TimestampPolicy,
    TimestampValue,
    validate_contract,
)


def test_extreme_zoned_dates_fail_with_validation_errors_instead_of_overflow() -> None:
    with pytest.raises(ValidationError, match="timestamp_range"):
        TimestampValue(value="0001-01-01T00:00:00+01:00", zone="UTC")
    with pytest.raises(ValidationError, match="timestamp_range"):
        TimestampPolicy(
            granularity="s",
            timezone="UTC",
            naive="reject",
            comparison="instant",
            ambiguous="reject",
            closed="both",
            lower=TimestampValue(value="9999-12-31T23:59:59-01:00"),
        )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        (1, "2000-03-01"),  # Upper endpoint excluded by date policy.
        (1, "2000-01-31"),
        (2, "2000-02-28T23:59:59.999999999-05:00"),
        (2, "2000-03-01T00:00:00.000000001-05:00"),
    ],
)
def test_allowed_temporal_literals_cannot_contradict_declared_intervals(
    column: int, value: str
) -> None:
    data = change(
        document("dates"),
        ("output", "schema_spec", "columns", column, "allowed_values", 0, "value"),
        value,
    )
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    assert caught.value.issues[0].code == "temporal_literal_bounds"
    assert caught.value.issues[0].path.endswith(".allowed_values[0].value")


def test_float32_literals_cannot_exceed_their_declared_range() -> None:
    data = change(document(), ("output", "schema_spec", "columns", 2, "logical_type", "bits"), 32)
    change(data, ("output", "schema_spec", "columns", 2, "allowed_values", 0, "value"), 1e100)
    with pytest.raises(ContractValidationError, match="float_range"):
        validate_contract(data)


@pytest.mark.parametrize("encoded", ["false", "null", '"failed"', '"no-alert"'])
def test_detector_state_does_not_coerce_failure_false_or_absence(encoded: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(DecisionState).validate_json(encoded, strict=True)


def test_decision_and_oracle_states_remain_independent_and_roundtrip() -> None:
    decision = TypeAdapter(DecisionState)
    oracle = TypeAdapter(OracleState)
    assert decision.validate_json(decision.dump_json("not_evaluable")) == "not_evaluable"
    assert oracle.validate_json(oracle.dump_json("pending")) == "pending"
    with pytest.raises(ValidationError):
        oracle.validate_json(decision.dump_json("no_alert"))
