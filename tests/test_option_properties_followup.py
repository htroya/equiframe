"""Guard against getter credit from mismatched fixtures and Python types."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location(
    "properties_followup",
    Path(__file__).resolve().parents[1] / "tools/option_properties_followup.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def case():
    return {
        "operation": "model",
        "model": "Model",
        "input": {"n": 1},
        "expected_json": {"n": 1},
        "checks": [{"name": "complete", "expected": True, "python_type": "bool"}],
        "obligations": ["pending"],
    }


class Model:
    @classmethod
    def model_validate_json(cls, value):
        return cls()

    def model_dump(self, **kwargs):
        return {"n": 1}

    @property
    def complete(self):
        return True


def test_full_constructor_mismatch_cannot_credit_correct_getter():
    class WrongFixture(Model):
        def model_dump(self, **kwargs):
            return {"n": 99}

    assert (
        module.execute(case(), SimpleNamespace(Model=WrongFixture))["status"] == "FAIL"
    )


def test_integer_one_cannot_credit_boolean_true():
    class WrongType(Model):
        @property
        def complete(self):
            return 1

    assert module.execute(case(), SimpleNamespace(Model=WrongType))["status"] == "FAIL"


def test_plain_class_attribute_cannot_credit_getter():
    class PlainAttribute(Model):
        complete = True

    assert (
        module.execute(case(), SimpleNamespace(Model=PlainAttribute))["status"]
        == "FAIL"
    )


def test_getter_exception_cannot_become_expected_rejection():
    class BrokenGetter(Model):
        @property
        def complete(self):
            raise ValueError("unavailable")

    assert (
        module.execute(case(), SimpleNamespace(Model=BrokenGetter))["status"] == "FAIL"
    )


def test_wrong_value_with_correct_type_fails():
    class WrongValue(Model):
        @property
        def complete(self):
            return False

    assert module.execute(case(), SimpleNamespace(Model=WrongValue))["status"] == "FAIL"


def test_named_builtin_subtype_cannot_claim_exact_type():
    imitation = type("int", (int,), {})

    class NamedSubtype(Model):
        @property
        def complete(self):
            return imitation(1)

    selected = case()
    selected["checks"] = [{"name": "complete", "expected": 1, "python_type": "int"}]
    assert (
        module.execute(selected, SimpleNamespace(Model=NamedSubtype))["status"]
        == "FAIL"
    )
