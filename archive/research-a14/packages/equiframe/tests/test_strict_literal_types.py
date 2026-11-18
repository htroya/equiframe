"""Numerically equal JSON/Python values must not bypass strict metadata types."""

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

import equiframe as ef

CASES = [
    (ef.CompatibilityPolicy, {}, "applies_during_zero_major", 1),
    (ef.CompatibilityPolicy, {}, "applies_during_zero_major", 1.0),
    (ef.CompatibilityPolicy, {}, "stable_notice_minor_releases", 2.0),
    (ef.CompatibilityPolicy, {}, "stable_notice_days", 90.0),
    (ef.FloatType, {"bits": 32}, "bits", 32.0),
    (ef.FloatType, {"bits": 64}, "bits", 64.0),
    *[
        (ef.IntegerType, {"bits": bit, "signed": True}, "bits", float(bit))
        for bit in (8, 16, 32, 64)
    ],
]


@pytest.mark.parametrize("model,valid,field,wrong", CASES)
@pytest.mark.parametrize("channel", ["python", "json"])
def test_equal_numeric_wrong_type_is_rejected(model, valid, field, wrong, channel):
    good = model.model_validate(valid)
    document = good.model_dump(mode="python" if channel == "python" else "json")
    document[field] = wrong
    with pytest.raises(ValidationError) as caught:
        if channel == "python":
            model.model_validate(document)
        else:
            model.model_validate_json(json.dumps(document))
    assert any(error["loc"][0] == field for error in caught.value.errors())
    # Rejection must not change the original valid object or its canonical type.
    assert type(getattr(good, field)) is type(model.model_validate(valid).__dict__[field])


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
@pytest.mark.parametrize("signed", [False, True])
def test_valid_integer_metadata_retains_exact_type_and_bytes(bits, signed):
    model = ef.IntegerType(bits=bits, signed=signed)
    expected = {"kind": "integer", "bits": bits, "signed": signed}
    assert model.model_dump(mode="json") == expected
    assert ef.IntegerType.model_validate_json(json.dumps(expected)) == model
    assert type(model.bits) is int
    assert type(model.signed) is bool


@pytest.mark.parametrize("wrong", [Decimal("32"), 32.0])
def test_constructed_invalid_instance_is_revalidated_without_literal_coercion(wrong):
    forged = ef.FloatType.model_construct(bits=wrong)
    with pytest.raises(ValidationError):
        ef.FloatType.model_validate(forged)


def test_nested_type_literal_rejects_wrong_numeric_json_type():
    document = {
        "name": "quantity",
        "logical_type": {"kind": "integer", "bits": 8.0, "signed": True},
        "nullable": False,
        "null_policy": {"representations": ["null"]},
        "numeric_policy": {"comparison": "exact", "unit": "count"},
    }
    with pytest.raises(ValidationError):
        ef.ColumnSpec.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("wrong", [1, 1.0])
def test_copied_invalid_instance_is_revalidated_without_boolean_literal_coercion(wrong):
    original = ef.CompatibilityPolicy()
    changed = original.model_copy(update={"applies_during_zero_major": wrong})
    with pytest.raises(ValidationError):
        ef.CompatibilityPolicy.model_validate(changed)
    assert original.applies_during_zero_major is True


def test_all_exported_numeric_literal_fields_have_local_strict_guards():
    """Static guard complements behavioral regressions; it is not an API-use test."""
    from typing import Literal, get_args, get_origin

    from pydantic import BaseModel, BeforeValidator

    from equiframe._base import strict_bool_literal, strict_int_literal

    checked = []
    for name in ef.__all__:
        model = getattr(ef, name)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            continue
        for field_name, field in model.model_fields.items():
            if get_origin(field.annotation) is not Literal:
                continue
            values = get_args(field.annotation)
            if not values or not all(type(value) in (bool, int) for value in values):
                continue
            guard = strict_bool_literal if type(values[0]) is bool else strict_int_literal
            assert any(
                isinstance(m, BeforeValidator) and m.func is guard for m in field.metadata
            ), (name, field_name)
            checked.append((name, field_name))
    assert ("FloatType", "bits") in checked
    assert ("CompatibilityPolicy", "applies_during_zero_major") in checked
