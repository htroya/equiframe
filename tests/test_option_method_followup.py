"""Prevent construction, exception returns and borrowed owners earning credit."""

import importlib.util
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).parents[1] / "tools" / "option_method_followup.py"
SPEC = importlib.util.spec_from_file_location("method_followup", PATH)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_only_exact_code_and_owner_with_normal_return_is_observed():
    class Model:
        def validate(self):
            return self

    class Other(Model):
        pass

    instance = Model()
    targets = {"method": (Model.validate, Model, "instance")}
    _, observations = tool.trace_call(lambda: instance.validate(), targets)
    assert observations == {"method": {"calls": 1, "normal_returns": 1}}
    _, observations = tool.trace_call(lambda: Other().validate(), targets)
    assert observations == {"method": {"calls": 0, "normal_returns": 0}}
    _, observations = tool.trace_call(lambda: instance, targets)
    assert observations == {"method": {"calls": 0, "normal_returns": 0}}


def test_exception_return_none_is_not_normal_completion():
    class Model:
        def validate(self):
            raise ValueError("Deliberate failure")

    def operation():
        try:
            Model().validate()
        except ValueError:
            pass

    output, observations = tool.trace_call(
        operation, {"method": (Model.validate, Model, "instance")}
    )
    assert output is None
    assert observations == {"method": {"calls": 1, "normal_returns": 0}}


@pytest.mark.parametrize("fails", [False, True])
def test_preexisting_trace_restored_after_success_or_failure(fails):
    def old_trace(frame, event, arg):
        return old_trace

    def operation():
        if fails:
            raise RuntimeError("Failure")
        return 1

    saved = sys.gettrace()
    try:
        sys.settrace(old_trace)
        if fails:
            with pytest.raises(RuntimeError):
                tool.trace_call(operation, {})
        else:
            assert tool.trace_call(operation, {}) == (1, {})
        assert sys.gettrace() is old_trace
    finally:
        sys.settrace(saved)


def test_class_method_owner_and_successful_none_return():
    class Model:
        @classmethod
        def validate(cls):
            return None

    output, observations = tool.trace_call(
        Model.validate, {"method": (Model.validate.__func__, Model, "class")}
    )
    assert output is None
    assert observations == {"method": {"calls": 1, "normal_returns": 1}}


def test_literal_oracle_keeps_boolean_distinct_from_integer():
    assert tool.canonical({"value": False}) != tool.canonical({"value": 0})


def test_structurally_equal_code_objects_are_not_the_exact_target():
    from types import FunctionType, MethodType

    class Model:
        def validate(self):
            return self

    copied = Model.validate.__code__.replace()
    assert copied == Model.validate.__code__
    assert copied is not Model.validate.__code__
    duplicate = FunctionType(copied, globals())
    instance = Model()
    output, observations = tool.trace_call(
        MethodType(duplicate, instance),
        {"method": (Model.validate, Model, "instance")},
    )
    assert output is instance
    assert observations == {"method": {"calls": 0, "normal_returns": 0}}


def test_serializer_return_is_snapshotted_before_later_mutation(monkeypatch):
    from types import SimpleNamespace

    class Model:
        @classmethod
        def model_validate_json(cls, value):
            return cls()

        def serialize(self):
            return {"value": False}

        def model_dump(self, **kwargs):
            result = self.serialize()
            result["value"] = 0
            return result

    identity = {
        "name": "serialize",
        "module": "equiframe.fixture",
        "qualname": "Model.serialize",
        "binding": "instance",
        "source_sha256": "test",
    }
    monkeypatch.setattr(
        tool, "method_identity", lambda model, name: (Model.serialize, identity)
    )
    identifier = "method:equiframe.Model.serialize"
    case = {
        "model": "Model",
        "input": {"value": 0},
        "expected": {"value": 0},
        "methods": [
            {"id": identifier, **identity, "return_rule": "complete_literal_json"}
        ],
        "obligations": [identifier],
    }
    result = tool.execute(case, SimpleNamespace(Model=Model))
    assert result["observed"]["output_matches"] is True
    assert result["observed"]["return_oracles_match"][identifier] is False
    assert result["status"] == "FAIL"


@pytest.mark.parametrize(
    "mutation", ["wrong_return", "nested_owner", "never_called", "wrong_output"]
)
def test_complete_output_cannot_hide_wrong_method_behavior(monkeypatch, mutation):
    from types import SimpleNamespace

    class Model:
        def validate(self):
            return Model() if mutation == "wrong_return" else self

        @classmethod
        def model_validate_json(cls, value):
            instance = cls()
            if mutation == "nested_owner":
                cls().validate()
            elif mutation != "never_called":
                instance.validate()
            return instance

        def model_dump(self, **kwargs):
            return {"value": False if mutation == "wrong_output" else 0}

    identity = {
        "name": "validate",
        "module": "equiframe.fixture",
        "qualname": "Model.validate",
        "binding": "instance",
        "source_sha256": "test",
    }
    monkeypatch.setattr(
        tool, "method_identity", lambda model, name: (Model.validate, identity)
    )
    identifier = "method:equiframe.Model.validate"
    case = {
        "model": "Model",
        "input": {"value": 0},
        "expected": {"value": 0},
        "methods": [
            {"id": identifier, **identity, "return_rule": "same_root_instance"}
        ],
        "obligations": [identifier],
    }
    result = tool.execute(case, SimpleNamespace(Model=Model))
    assert result["status"] == "FAIL"
    assert result["observed"].get("unexpected_exception") is None
