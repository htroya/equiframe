"""A valid selected value must not hide a wrong complete model output."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

PATH = Path(__file__).parents[1] / "tools" / "option_literal_field_followup.py"
SPEC = importlib.util.spec_from_file_location("literal_field_followup", PATH)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_correct_selected_value_does_not_hide_other_wrong_fields():
    class Model:
        @staticmethod
        def model_validate_json(value):
            return SimpleNamespace(
                model_dump=lambda **kwargs: {"selected": "a", "other": False}
            )

    case = {
        "model": "Model",
        "field": "selected",
        "input": {"selected": "a", "other": 0},
        "expected": {"admitted": True, "output": {"selected": "a", "other": 0}},
    }
    assert tool.execute(case, SimpleNamespace(Model=Model))["status"] == "FAIL"


def test_foreign_field_error_prevents_expected_rejection():
    class Model:
        @staticmethod
        def model_validate_json(value):
            raise ValidationError.from_exception_data(
                "Model",
                [
                    {"type": "int_type", "loc": ("selected",), "input": False},
                    {"type": "int_type", "loc": ("other",), "input": False},
                ],
            )

    case = {
        "model": "Model",
        "input": {},
        "expected": {
            "admitted": False,
            "field": "selected",
            "error_codes": ["int_type"],
        },
    }
    assert tool.execute(case, SimpleNamespace(Model=Model))["status"] == "FAIL"


def test_unexpected_error_code_is_not_expected_rejection():
    class Model:
        @staticmethod
        def model_validate_json(value):
            raise ValidationError.from_exception_data(
                "Model",
                [
                    {"type": "int_type", "loc": ("selected",), "input": False},
                ],
            )

    case = {
        "model": "Model",
        "input": {},
        "expected": {
            "admitted": False,
            "field": "selected",
            "error_codes": ["missing"],
        },
    }
    assert tool.execute(case, SimpleNamespace(Model=Model))["status"] == "FAIL"
