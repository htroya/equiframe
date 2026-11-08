"""Reject false coverage and prevent operational calls in binding-only probes."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).parents[1] / "tools" / "option_boundary_followup.py"
SPEC = importlib.util.spec_from_file_location("boundary_followup", PATH)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_binding_probe_uses_real_call_and_never_enters_body():
    calls = []

    def operation(first, second):
        calls.append((first, second))
        raise AssertionError("Must not execute")

    case = {
        "case_id": "binding-example",
        "driver": "binding",
        "target": "equiframe.operation",
        "omitted": "second",
        "expected": {
            "exception": "TypeError",
            "missing_argument": "second",
            "entered_body": False,
        },
        "obligations": ["parameter:equiframe.operation:second:required_omission"],
    }
    result = tool.execute(case, SimpleNamespace(operation=operation))
    assert result["status"] == "EXPECTED_REJECTION"
    assert result["observed"] == case["expected"]
    assert calls == []


def test_binding_guard_blocks_wrong_catalog_instead_of_running_operation():
    calls = []

    def operation(first=None):
        calls.append(first)

    case = {
        "case_id": "wrong-binding-example",
        "driver": "binding",
        "target": "equiframe.operation",
        "omitted": "first",
        "expected": {
            "exception": "TypeError",
            "missing_argument": "first",
            "entered_body": False,
        },
        "obligations": [],
    }
    result = tool.execute(case, SimpleNamespace(operation=operation))
    assert result["status"] == "FAIL"
    assert result["observed"]["entered_body"] is True
    assert calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "already_verified",
        "duplicate_case",
        "duplicate_obligation",
        "invalid_state",
    ],
)
def test_coverage_union_rejects_forged_or_repeated_claims(mutation):
    baseline = {
        "rows": [
            {"id": "first", "status": "PASS"},
            {"id": "pending", "status": "NOT_RUN"},
        ]
    }
    receipt = {"case_id": "case-one", "status": "PASS", "obligations": ["pending"]}
    receipts = [receipt]
    if mutation == "unknown":
        receipt["obligations"] = ["unknown"]
    elif mutation == "already_verified":
        receipt["obligations"] = ["first"]
    elif mutation == "duplicate_case":
        receipts.append(dict(receipt))
    elif mutation == "duplicate_obligation":
        receipts.append({**receipt, "case_id": "case-two"})
    else:
        receipt["status"] = "NOT_RUN"
    with pytest.raises(ValueError):
        tool.aggregate(baseline, [], receipts)


def test_failed_execution_remains_failed_and_does_not_increase_verified_count():
    baseline = {
        "rows": [
            {"id": "first", "status": "PASS"},
            {"id": "pending", "status": "NOT_RUN"},
        ]
    }
    result = tool.aggregate(
        baseline,
        [],
        [{"case_id": "contradiction", "status": "FAIL", "obligations": ["pending"]}],
    )
    assert result["verified"] == 1
    assert result["counts"]["FAIL"] == 1
    assert result["linked_obligations"]["pending"] == "FAIL"


def test_programming_error_is_not_an_expected_rejection():
    class BrokenModel:
        @staticmethod
        def model_validate_json(value):
            raise RuntimeError("Unexpected implementation failure")

    case = {
        "driver": "field",
        "model": "Broken",
        "field": "value",
        "input": {"value": -1},
        "expected": {
            "admitted": False,
            "field": "value",
            "error_codes": ["greater_than_equal"],
        },
    }
    result = tool.execute(case, SimpleNamespace(Broken=BrokenModel))
    assert result["status"] == "FAIL"
    assert result["observed"] == {"unexpected_exception": "RuntimeError"}


def test_model_oracle_does_not_confuse_boolean_and_integer():
    class IncorrectModel:
        @staticmethod
        def model_validate_json(value):
            return SimpleNamespace(model_dump=lambda **kwargs: {"value": False})

    case = {
        "driver": "model",
        "model": "Incorrect",
        "input": {"value": 0},
        "expected": {"value": 0},
    }
    result = tool.execute(case, SimpleNamespace(Incorrect=IncorrectModel))
    assert result["status"] == "FAIL"


def test_field_rejection_does_not_hide_an_invalid_fixture_in_another_field():
    from pydantic import ValidationError

    class InvalidFixture:
        @staticmethod
        def model_validate_json(value):
            raise ValidationError.from_exception_data(
                "InvalidFixture",
                [
                    {"type": "int_type", "loc": ("value",), "input": False},
                    {"type": "int_type", "loc": ("other",), "input": "invalid"},
                ],
            )

    case = {
        "driver": "field",
        "model": "Invalid",
        "field": "value",
        "input": {"value": False, "other": "invalid"},
        "expected": {"admitted": False, "field": "value", "error_codes": ["int_type"]},
    }
    result = tool.execute(case, SimpleNamespace(Invalid=InvalidFixture))
    assert result["status"] == "FAIL"
