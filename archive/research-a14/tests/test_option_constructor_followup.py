"""False-credit counterexamples for complete plain constructor observations."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "constructors", Path(__file__).parents[1] / "tools/option_constructor_followup.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_full_attribute_oracle_rejects_omission_extra_type_and_reference_change():
    item = object()
    refs = {"@arrow": item}
    expected = {"table": "@arrow", "revision": 1, "notes": []}
    observed = {"table": item, "revision": 1, "notes": ()}
    assert tool.attributes_match(observed, expected, refs)
    assert not tool.attributes_match({"table": item, "revision": 1}, expected, refs)
    assert not tool.attributes_match({**observed, "extra": None}, expected, refs)
    assert not tool.attributes_match({**observed, "revision": True}, expected, refs)
    assert not tool.attributes_match({**observed, "table": object()}, expected, refs)


def test_admission_is_strict_and_no_unknown_annotation_or_rejection_credit():
    assert tool.admitted("int", 1, {})
    assert not tool.admitted("int", True, {})
    assert tool.admitted("location", ("records", 2), {})
    assert not tool.admitted("location", ("records", True), {})
    assert tool.admitted("pairs", (("a", "int64"),), {})
    assert not tool.admitted("pairs", (["a", "int64"],), {})
    assert not tool.admitted("unknown", object(), {})


def test_stored_tuple_members_preserve_recursive_types():
    expected = {"location": ["records", 2, "amount"]}
    assert tool.attributes_match({"location": ("records", 2, "amount")}, expected, {})
    assert not tool.attributes_match(
        {"location": ("records", 2.0, "amount")}, expected, {}
    )
    assert not tool.attributes_match(
        {"location": ("records", True, "amount")},
        {"location": ["records", 1, "amount"]},
        {},
    )
    assert not tool.strict_equal((("x", 1),), (("x", True),))
