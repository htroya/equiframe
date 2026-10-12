"""An admitted value or unrelated exception cannot count as expected rejection."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pydantic
import pytest

SPEC = importlib.util.spec_from_file_location(
    "public_types_followup",
    Path(__file__).parents[1] / "tools/option_public_types_followup.py",
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def rejection():
    return {
        "case_id": "guardrail",
        "operation": "alias_rejection",
        "name": "Example",
        "input": "invalid",
        "expected": "literal_error",
        "obligations": [],
    }


def test_admission_cannot_pass_a_rejection_case_even_when_value_matches_error_name(
    monkeypatch,
):
    class AdmittingAdapter:
        def __init__(self, annotation):
            pass

        def validate_json(self, data, *, strict):
            return "literal_error"

        def dump_json(self, value):
            return b'"literal_error"'

    monkeypatch.setattr(pydantic, "TypeAdapter", AdmittingAdapter)
    receipt = tool.execute(rejection(), SimpleNamespace(Example=str))
    assert receipt["status"] == "FAIL"
    assert receipt["obligations"] == []


def test_actual_literal_rejection_is_a_guardrail_with_no_coverage_credit():
    receipt = tool.execute(rejection(), SimpleNamespace(Example=Literal["allowed"]))
    assert receipt["status"] == "EXPECTED_REJECTION"
    assert receipt["observed"] == [{"loc": [], "type": "literal_error"}]
    assert receipt["obligations"] == []


@pytest.mark.parametrize(
    "case",
    [
        {"operation": "constant", "name": "Example", "expected": "correct"},
        {
            "operation": "alias",
            "name": "Example",
            "input": "incorrect",
            "expected": "correct",
        },
    ],
)
def test_drift_from_the_independent_literal_expectation_fails(case):
    sdk = SimpleNamespace(
        Example="incorrect" if case["operation"] == "constant" else Literal["correct"]
    )
    receipt = tool.execute(
        {"case_id": "drift", "obligations": ["pending"], **case}, sdk
    )
    assert receipt["status"] == "FAIL"
