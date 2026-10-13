"""Counterexamples for CLI attribution; these fixtures earn no inventory IDs."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location(
    "cli_parser_followup",
    Path(__file__).parents[1] / "tools/option_cli_parser_followup.py",
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def proof(command, error=None, parameter=None, option=None):
    return {
        "help_contexts": [command],
        "parser_errors": [
            {
                "class": error,
                "command_path": command,
                "parameter": parameter,
                "option": option,
            }
        ],
    }


def test_wrong_missing_parameter_or_context_is_not_attributed():
    c = {
        "kind": "required_omission",
        "expected_exit": 2,
        "command": "equiframe compare",
        "omitted": "spec",
        "usage": "Usage: equiframe compare",
        "diagnostic": "Missing argument 'spec'",
    }
    o = "Usage: equiframe compare Missing argument 'spec'."
    assert not tool.matches(
        c, 2, o, False, proof(c["command"], "MissingParameter", "left")
    )
    assert not tool.matches(
        c, 2, o, False, proof("equiframe run", "MissingParameter", "spec")
    )
    assert tool.matches(c, 2, o, False, proof(c["command"], "MissingParameter", "spec"))


def test_early_error_without_usage_requires_real_parser_context_and_exit():
    c = {
        "kind": "help_invalid",
        "expected_exit": 2,
        "command": "equiframe doctor",
        "usage": "Usage: equiframe doctor",
        "diagnostic": "Option '--help' does not take a value.",
    }
    o = "Error: Option '--help' does not take a value."
    p = proof(c["command"], "BadOptionUsage", option="--help")
    assert not tool.matches(c, 0, o, False, p)
    assert not tool.matches(c, 2, o, True, p)
    assert not tool.matches(
        c, 2, o, False, proof("equiframe compare", "BadOptionUsage", option="--help")
    )
    assert not tool.matches(
        c, 2, o, False, proof(c["command"], "BadOptionUsage", option="--extra")
    )
    assert tool.matches(c, 2, o, False, p)


def test_help_requires_exit_context_and_rendered_option():
    c = {
        "kind": "help_true",
        "expected_exit": 0,
        "command": "equiframe doctor",
        "usage": "Usage: equiframe doctor",
        "diagnostic": None,
    }
    assert not tool.matches(
        c, 0, "Usage: equiframe compare --help", False, proof(c["command"])
    )
    assert not tool.matches(c, 0, "Usage: equiframe doctor", False, proof(c["command"]))
    assert not tool.matches(
        c, 0, "Usage: equiframe doctor --help", False, proof("equiframe compare")
    )
    assert tool.matches(
        c, 0, "Usage: equiframe doctor [OPTIONS] --help", False, proof(c["command"])
    )


def test_positional_omission_does_not_shift_a_later_argument():
    a = SimpleNamespace(
        name="source", required=True, opts=["source"], type=SimpleNamespace()
    )
    b = SimpleNamespace(
        name="destination", required=True, opts=["destination"], type=SimpleNamespace()
    )
    tree = SimpleNamespace(
        commands={
            "bundle": SimpleNamespace(
                commands={"export": SimpleNamespace(params=[a, b])}
            )
        }
    )
    p = {
        "name": "source",
        "id": "cli-option:equiframe bundle export:source",
        "required": True,
    }
    identifier = p["id"] + ":required_omission"
    case = tool.plan(
        {"cli": [{"name": "equiframe bundle export", "parameters": [p]}]},
        {identifier},
        tree,
    )["cases"][0]
    assert case["argv"] == ["bundle", "export", "--"]
    assert case["later_positionals_also_absent"] == ["destination"]
    assert case["obligations"] == [identifier]
