"""Counterexamples for copied mappings, exact nested types and list factories."""

import dataclasses
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "contexts",
    Path(__file__).parents[1] / "tools/option_context_constructor_followup.py",
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_nested_type_and_reference_substitutions_are_not_accepted():
    value = object()
    refs = {"@item": value}
    expected = {"input": tool.tuple_recipe("@item", 1)}
    assert tool.matches({"input": (value, 1)}, expected, refs)
    assert not tool.matches({"input": (value, True)}, expected, refs)
    assert not tool.matches({"input": (value, 1.0)}, expected, refs)
    assert not tool.matches({"input": (object(), 1)}, expected, refs)
    assert not tool.matches({"input": (value, 1), "extra": None}, expected, refs)


def test_factory_lists_are_empty_fresh_and_independent():
    @dataclasses.dataclass
    class Fixture:
        timings: list = dataclasses.field(default_factory=list)
        effective_configuration: list = dataclasses.field(default_factory=list)
        captured_inputs: list = dataclasses.field(default_factory=list)

    left, right = Fixture(), Fixture()
    assert tool.factory_proof(Fixture, left, right, set(tool.FACTORIES))
    right.timings = left.timings
    assert not tool.factory_proof(Fixture, left, right, set(tool.FACTORIES))
    right = Fixture()
    left.captured_inputs.append(None)
    assert not tool.factory_proof(Fixture, left, right, set(tool.FACTORIES))


def test_list_and_tuple_oracles_are_separate():
    assert tool.matches([1], tool.list_recipe(1), {})
    assert tool.matches((1,), tool.tuple_recipe(1), {})
    assert not tool.matches((1,), tool.list_recipe(1), {})
    assert not tool.matches([1], tool.tuple_recipe(1), {})


def test_json_model_lists_reject_nested_bool_and_float_substitutions():
    expected = {"fields": [{"revision": 1, "labels": [None, "x"]}]}
    assert tool.matches(expected, expected, {})
    for revision in (True, 1.0):
        observed = {"fields": [{"revision": revision, "labels": [None, "x"]}]}
        assert not tool.matches(observed, expected, {})
    assert not tool.matches(
        {"fields": ({"revision": 1, "labels": [None, "x"]},)}, expected, {}
    )
