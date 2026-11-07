"""Shared document metadata cannot replace strict booleans/integers by equal numbers."""

import json

import pytest
from pydantic import ValidationError

import equiframe_benchmark as eb


def valid_protocol():
    return eb.CostProtocol(
        seed=0,
        cache_policy="fresh process",
        threads=1,
        concurrent_loads="shared test host",
        controls_rationale="bounded literal regression",
    )


@pytest.mark.parametrize("field,wrong", [("warmups", 1.0), ("warmups", True), ("repetitions", 5.0)])
@pytest.mark.parametrize("channel", ["python", "json", "copy", "construct"])
def test_document_numeric_literals_reject_equal_wrong_types(field, wrong, channel):
    valid = valid_protocol()
    payload = valid.model_dump(mode="json" if channel == "json" else "python")
    payload[field] = wrong
    with pytest.raises(ValidationError) as caught:
        if channel == "json":
            eb.CostProtocol.model_validate_json(json.dumps(payload))
        elif channel == "copy":
            eb.CostProtocol.model_validate(valid.model_copy(update={field: wrong}))
        elif channel == "construct":
            eb.CostProtocol.model_validate(eb.CostProtocol.model_construct(**payload))
        else:
            eb.CostProtocol.model_validate(payload)
    assert any(error["loc"][0] == field for error in caught.value.errors())


def test_valid_document_literal_values_and_historical_bytes_are_unchanged():
    value = valid_protocol()
    expected = {
        "schema_version": "1.0",
        "warmups": 1,
        "repetitions": 5,
        "seed": 0,
        "sample_interval_seconds": 0.01,
        "cache_policy": "fresh process",
        "threads": 1,
        "memory_budget_bytes": None,
        "concurrent_loads": "shared test host",
        "controls_rationale": "bounded literal regression",
    }
    assert value.model_dump(mode="json") == expected
    assert type(value.warmups) is int and type(value.repetitions) is int
    assert eb.CostProtocol.model_validate_json(json.dumps(expected)) == value


@pytest.mark.parametrize("wrong", [0, 0.0])
@pytest.mark.parametrize("channel", ["python", "json"])
def test_scientific_false_literal_is_not_numeric_zero(wrong, channel):
    spec = eb.AwardReconciliationSpec(
        domain_schema_revision="test-v1",
        award_keys=("id",),
        amount_column="amount",
        currency_column="currency",
    )
    valid = eb.AwardReconciliationResult(
        spec=spec,
        checks=(),
        currencies=(),
        expected_rows=0,
        observed_rows=0,
    )
    data = valid.model_dump(mode="python" if channel == "python" else "json")
    data["scientific_label_confirmed"] = wrong
    with pytest.raises(ValidationError) as caught:
        if channel == "json":
            eb.AwardReconciliationResult.model_validate_json(json.dumps(data))
        else:
            eb.AwardReconciliationResult.model_validate(data)
    assert any(error["loc"][0] == "scientific_label_confirmed" for error in caught.value.errors())
    assert valid.scientific_label_confirmed is False


def test_exported_document_numeric_literals_use_field_local_guards():
    from typing import Literal, get_args, get_origin

    from equiframe._base import strict_bool_literal, strict_int_literal
    from pydantic import BaseModel, BeforeValidator

    checked = []
    for name in eb.__all__:
        model = getattr(eb, name)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            continue
        for field_name, field in model.model_fields.items():
            values = get_args(field.annotation)
            if get_origin(field.annotation) is not Literal or not values:
                continue
            if not all(type(value) in (bool, int) for value in values):
                continue
            guard = strict_bool_literal if type(values[0]) is bool else strict_int_literal
            assert any(
                isinstance(m, BeforeValidator) and m.func is guard for m in field.metadata
            ), (name, field_name)
            checked.append((name, field_name))
    assert ("CostProtocol", "warmups") in checked
    assert ("AwardReconciliationResult", "scientific_label_confirmed") in checked
