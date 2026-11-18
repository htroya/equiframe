"""Contrapruebas del acreditador; no son resultados de la biblioteca."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "seed_bounds",
    Path(__file__).resolve().parents[1] / "tools/option_seed_bounds_followup.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_upper_or_outside_class_cannot_claim_exact_lower_boundary():
    declaration = {
        "continuous_classes": ["just outside declared lower boundary"],
        "bounds": {"ge": 0},
    }
    with pytest.raises(ValueError):
        module.lower_proof(0, declaration, 0)


def test_bool_cannot_claim_numeric_zero_boundary():
    declaration = {
        "continuous_classes": ["declared lower boundary"],
        "bounds": {"ge": 0},
    }
    with pytest.raises(ValueError):
        module.lower_proof(False, declaration, 0)


def test_typed_member_boundary_can_be_later_in_homogeneous_tuple():
    declaration = {
        "continuous_classes": ["member:0 declared lower boundary"],
        "bounds": {"branches": [{"path": "member:0", "bounds": {"min_length": 1}}]},
    }
    module.lower_proof(["long", "n"], declaration, 0)
    with pytest.raises(ValueError):
        module.lower_proof(["long", "longer"], declaration, 0)


def test_full_json_mismatch_is_failure_even_if_selected_field_matches():
    class Model:
        @staticmethod
        def model_validate_json(data):
            return SimpleNamespace(
                model_dump=lambda **kwargs: {"selected": 0, "other": 99}
            )

    case = {
        "model": "Model",
        "input": {"selected": 0, "other": 1},
        "expected": {"selected": 0, "other": 1},
        "obligations": ["pending"],
    }
    assert module.execute(case, SimpleNamespace(Model=Model))["status"] == "FAIL"


def test_unexpected_exception_does_not_become_expected_rejection():
    class Model:
        @staticmethod
        def model_validate_json(data):
            raise ValueError("No expected admission")

    case = {"model": "Model", "input": {}, "expected": {}, "obligations": ["pending"]}
    assert module.execute(case, SimpleNamespace(Model=Model))["status"] == "FAIL"
