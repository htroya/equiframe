"""Counterexamples for trace attribution; synthetic tooling fixtures earn no IDs."""

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "test_calls_followup",
    Path(__file__).parents[1] / "tools/option_test_calls_followup.py",
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def test_partial_dictionary_does_not_become_complete_by_missing_attributes():
    assert not tool.complete_return("equiframe.inspect_evidence", {"exit_code": 3})
    assert not tool.complete_return(
        "equiframe.migration_summary", {"state": "not_evaluable"}
    )


def test_verification_requires_both_operation_and_actual_coverage():
    for state, complete in (
        ("failed", True),
        ("passed", False),
        ("not_requested", True),
    ):
        result = SimpleNamespace(
            operational_state=state, coverage=SimpleNamespace(complete=complete)
        )
        assert not tool.complete_return("equiframe.verify", result)
    result = SimpleNamespace(
        operational_state="passed", coverage=SimpleNamespace(complete=True)
    )
    assert tool.complete_return("equiframe.verify", result)


def test_unknown_detector_contract_does_not_infer_completeness():
    result = SimpleNamespace(result=SimpleNamespace(complete=False, decision="alert"))
    assert not tool.complete_return("equiframe.combine_decisions", result)
    assert not tool.complete_return(
        "equiframe.score_detectors",
        SimpleNamespace(m=SimpleNamespace(state="not_estimable")),
    )


def test_complete_comparison_requires_the_actual_flag_and_admitted_state():
    for state, complete in (
        ("not_evaluable", True),
        ("equivalent", False),
        ("equivalent", None),
    ):
        assert not tool.complete_return(
            "equiframe.compare", SimpleNamespace(state=state, complete=complete)
        )
    assert tool.complete_return(
        "equiframe.compare", SimpleNamespace(state="different", complete=True)
    )


def test_original_tuple_oracle_survives_json_freezing():
    tree = ast.parse(
        "def test_example():\n    result = api()\n    assert result.columns == ('id', 'value')\n"
    )
    checks = json.loads(json.dumps(tool.checks_for(tree.body[0], "result")))
    assert ast.literal_eval(checks[0]["expected_expression"]) == ("id", "value")


def test_negative_complete_oracle_is_not_selected_as_positive():
    tree = ast.parse(
        "def test_example():\n    result = api()\n    assert result.complete is False\n"
    )
    assert tool.checks_for(tree.body[0], "result") == []


def test_negated_and_alternative_oracles_are_not_mined_as_required_values():
    for expression in (
        "not result.complete is True",
        "result.state == 'different' or result.state == 'equivalent'",
    ):
        tree = ast.parse(
            "def test_example():\n    result = api()\n    assert " + expression + "\n"
        )
        assert tool.checks_for(tree.body[0], "result") == []


def test_unresolved_return_does_not_block_a_resolved_parameter():
    def declared(value: "int") -> "absent_type_checking_module.Table":  # noqa: F821 - intentional missing TYPE_CHECKING return
        return value

    assert tool.annotation_for(declared, "value") is int


def test_profile_and_trace_are_restored_when_test_body_raises(tmp_path):
    def api(value):
        return value

    case = {
        "api": "equiframe.api",
        "test_file": "test_original.py",
        "test_node": "test_original.py::test_example",
        "call_lines": [1, 1],
    }
    observer = tool.Calls({"cases": [case]}, tmp_path, SimpleNamespace(api=api), set())
    original_profile, original_trace = sys.getprofile(), sys.gettrace()
    hook = observer.call_hook(SimpleNamespace(nodeid=case["test_node"]))
    next(hook)
    with pytest.raises(RuntimeError, match="actual test body failure"):
        hook.throw(RuntimeError("actual test body failure"))
    assert sys.getprofile() is original_profile
    assert sys.gettrace() is original_trace


def test_structurally_equal_foreign_code_is_not_a_public_call(tmp_path):
    source = "def api(value):\n    return value\n"
    namespaces = [{}, {}]
    for namespace in namespaces:
        exec(compile(source, "synthetic.py", "exec"), namespace)  # noqa: S102 - controlled literal code identity counterexample
    actual, foreign = [n["api"] for n in namespaces]
    assert actual.__code__ == foreign.__code__
    assert actual.__code__ is not foreign.__code__
    case = {
        "api": "equiframe.api",
        "test_file": "test_original.py",
        "test_node": "test_original.py::test_example",
        "call_lines": [1, 1],
    }
    observer = tool.Calls(
        {"cases": [case]}, tmp_path, SimpleNamespace(api=actual), set()
    )
    observer.active, observer.node = True, case["test_node"]
    caller = SimpleNamespace(
        f_code=SimpleNamespace(co_filename=str(tmp_path / case["test_file"])),
        f_lineno=1,
    )
    frame = SimpleNamespace(
        f_code=foreign.__code__, f_back=caller, f_locals={"value": 1}
    )
    observer.profile(frame, "call", None)
    assert observer.frames == {}
