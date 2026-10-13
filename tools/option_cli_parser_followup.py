"""Bind frozen A13 CLI parser obligations to actual help and rejection runs.

Parser-only cases never establish native command completion or callback defaults.
They preserve the original inventory, installed SDK and actual Typer parser.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from collections import Counter
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "literal_calls", Path(__file__).with_name("option_test_calls_followup.py")
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Prior identity verifier unavailable")
calls = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(calls)
op = calls.op
SEMANTIC_RESULT = "5f3f3ccc156120c55ccd2bbf479242204c9f3739185d9e6b0ebd574e5714b1e0"


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(
            value, output, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        output.write("\n")


def inputs(workspace):
    inventory, baseline, done = calls.load_inputs(workspace)
    path = workspace / "trace85_20261011/test-calls-normal-v6/result.json"
    op.require(op.digest(path) == SEMANTIC_RESULT, "Previous semantic receipt differs")
    done.update(i for row in op.read(path)["receipts"] for i in row["obligations"])
    op.require(len(done) == 6045, "Prior unique union differs")
    return inventory, baseline, done


def command_for(tree, tokens):
    command = tree
    for token in tokens:
        command = command.commands[token]
    return command


def placeholder(parameter):
    value_type = parameter.type
    choices = getattr(value_type, "choices", None)
    if choices:
        return str(choices[0])
    if hasattr(value_type, "path_type") or "path" in type(value_type).__name__.lower():
        return (
            "@directory" if getattr(value_type, "file_okay", True) is False else "@file"
        )
    minimum = getattr(value_type, "min", None)
    if (
        "int" in type(value_type).__name__.lower()
        or "float" in type(value_type).__name__.lower()
    ):
        return str(max(1, minimum) if minimum is not None else 1)
    return "probe"


def plan(inventory, pending, tree):
    cases = []
    for record in inventory["cli"]:
        tokens = record["name"].split()[1:]
        command = command_for(tree, tokens)
        parameters = {p.name: p for p in command.params}
        for parameter in record["parameters"]:
            prefix = parameter["id"]
            if parameter["name"] == "help":
                for suffix, kind, argv, code, diagnostic in (
                    (":value:true", "help_true", [*tokens, "--help"], 0, None),
                    (
                        ":invalid",
                        "help_invalid",
                        [*tokens, "--help=probe"],
                        2,
                        "Option '--help' does not take a value.",
                    ),
                ):
                    identifier = prefix + suffix
                    if identifier in pending:
                        cases.append(
                            {
                                "case_id": "cli-parser." + identifier,
                                "kind": kind,
                                "command": record["name"],
                                "tokens": tokens,
                                "argv": argv,
                                "expected_exit": code,
                                "diagnostic": diagnostic,
                                "usage": "Usage: " + record["name"],
                                "obligations": [identifier],
                            }
                        )
            identifier = prefix + ":required_omission"
            if identifier not in pending or not parameter["required"]:
                continue
            target = parameters[parameter["name"]]
            argv = list(tokens)
            target_is_option = bool(target.opts and target.opts[0].startswith("-"))
            skipped_positionals = []
            after_target = False
            for other in command.params:
                is_option = bool(
                    getattr(other, "opts", None) and other.opts[0].startswith("-")
                )
                if other.name == target.name:
                    after_target = not target_is_option
                    continue
                if not other.required:
                    continue
                if after_target and not is_option:
                    skipped_positionals.append(other.name)
                    continue
                if is_option:
                    argv.append(other.opts[0])
                    if not getattr(other, "is_flag", False):
                        argv.append(placeholder(other))
                else:
                    argv.append(placeholder(other))
            if not target_is_option:
                argv.append("--")
            name = target.opts[0] if target_is_option else target.name
            diagnostic = (
                f"Missing {'option' if target_is_option else 'argument'} '{name}'"
            )
            cases.append(
                {
                    "case_id": "cli-parser." + identifier,
                    "kind": "required_omission",
                    "command": record["name"],
                    "tokens": tokens,
                    "argv": argv,
                    "omitted": target.name,
                    "later_positionals_also_absent": skipped_positionals,
                    "expected_exit": 2,
                    "diagnostic": diagnostic,
                    "usage": "Usage: " + record["name"],
                    "obligations": [identifier],
                }
            )
    ids = [i for case in cases for i in case["obligations"]]
    op.require(
        len(ids) == len(set(ids)) and set(ids) <= pending,
        "Duplicate or nonpending plan ID",
    )
    return {
        "schema": "equiframe.cli-parser-catalog.v2",
        "sdk_native_executed": False,
        "inventory_sha256": calls.INVENTORY,
        "previous_semantic_receipt_sha256": SEMANTIC_RESULT,
        "cases": cases,
        "scope": "Explicit help:true, help invalid-value and attributed required omission only; no native command or default inference",
    }


def matches(case, exit_code, output, callback_entered, observations):
    normalized = " ".join(output.split())
    context = case["command"]
    if case["kind"] == "help_true":
        attributed = context in observations["help_contexts"]
        rendered = case["usage"] in normalized and "--help" in normalized
    else:
        expected_class = (
            "BadOptionUsage" if case["kind"] == "help_invalid" else "MissingParameter"
        )
        attributed = any(
            row["class"] == expected_class
            and row["command_path"] == context
            and (
                row["option"] == "--help"
                if case["kind"] == "help_invalid"
                else row["parameter"] == case["omitted"]
            )
            for row in observations["parser_errors"]
        )
        rendered = case["diagnostic"] in normalized
    return (
        not callback_entered
        and exit_code == case["expected_exit"]
        and attributed
        and rendered
    )


def execute(case, app, tree, runner, fixtures):
    from typer._click import core as click_core
    from typer._click import parser as click_parser
    from typer._click.exceptions import BadOptionUsage, MissingParameter

    command = command_for(tree, case["tokens"])
    callback = (
        inspect.unwrap(command.callback) if command.callback is not None else None
    )
    code = getattr(callback, "__code__", None)
    entered = False
    observations = {"parser_errors": [], "help_contexts": []}
    argument_code = click_core.Parameter.process_value.__code__
    option_code = click_parser._OptionParser._match_long_opt.__code__
    exit_code = click_core.Context.exit.__code__

    def trace(frame, event, arg):
        if (
            event == "call"
            and frame.f_code is exit_code
            and frame.f_locals.get("code") == 0
        ):
            observations["help_contexts"].append(frame.f_locals["self"].command_path)
        if event == "exception" and (
            frame.f_code is argument_code or frame.f_code is option_code
        ):
            error = arg[1]
            if isinstance(error, (BadOptionUsage, MissingParameter)):
                ctx = error.ctx
                if ctx is None and frame.f_code is option_code:
                    ctx = frame.f_locals["self"].ctx
                if ctx is not None:
                    observations["parser_errors"].append(
                        {
                            "class": type(error).__name__,
                            "command_path": ctx.command_path,
                            "parameter": getattr(
                                getattr(error, "param", None), "name", None
                            ),
                            "option": getattr(error, "option_name", None),
                        }
                    )
        return trace

    def profile(frame, event, _):
        nonlocal entered
        if event == "call" and code is not None and frame.f_code is code:
            entered = True

    argv = [
        str(fixtures[token]) if token in fixtures else token for token in case["argv"]
    ]
    saved = sys.getprofile()
    saved_trace = sys.gettrace()
    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        result = runner.invoke(
            app,
            argv,
            prog_name="equiframe",
            color=False,
            env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"},
        )
    finally:
        sys.setprofile(saved)
        sys.settrace(saved_trace)
    success = matches(case, result.exit_code, result.output, entered, observations)
    return {
        "case_id": case["case_id"],
        "kind": case["kind"],
        "command": case["command"],
        "argv": argv,
        "exit_code": result.exit_code,
        "output": result.output,
        "callback_entered": entered,
        "parser_observations": observations,
        "status": ("PASS" if case["kind"] == "help_true" else "EXPECTED_REJECTION")
        if success
        else "FAIL",
        "obligations": case["obligations"] if success else [],
        "expected": {
            key: case[key] for key in ("expected_exit", "diagnostic", "usage")
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in ("workspace", "catalog", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    inventory, baseline, done = inputs(workspace)
    pending = {row["id"] for row in baseline["rows"]} - done
    import typer
    from equiframe.cli import app
    from typer.main import get_command
    from typer.testing import CliRunner

    package = op.identity(
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl",
        calls.WHEEL,
        Path(__file__).parents[1],
    )
    tree = get_command(app)
    catalog = plan(inventory, pending, tree)
    if args.mode == "plan":
        write(args.catalog, catalog)
        print(
            json.dumps(
                {
                    "planned_cases": len(catalog["cases"]),
                    "catalog_sha256": op.digest(args.catalog),
                    "counts": dict(Counter(c["kind"] for c in catalog["cases"])),
                    "new_verified_ids": 0,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256 and op.digest(args.catalog) == args.catalog_sha256,
        "Frozen catalog differs",
    )
    op.require(
        op.read(args.catalog) == catalog,
        "Actual command declarations or oracles differ",
    )
    args.output.mkdir(parents=True, exist_ok=False)
    fixture_directory = args.output / "parser-fixtures"
    fixture_directory.mkdir()
    fixture_file = fixture_directory / "existing.json"
    fixture_file.write_text("{}\n", encoding="utf-8")
    tool_sha = op.digest(Path(__file__))
    parser_module = __import__("typer._click.parser", fromlist=["__file__"])
    core_module = __import__("typer._click.core", fromlist=["__file__"])
    dependency = {
        "version": typer.__version__,
        "parser_sha256": op.digest(Path(parser_module.__file__)),
        "parser_module": parser_module.__name__,
        "core_sha256": op.digest(Path(core_module.__file__)),
    }
    receipts = [
        execute(
            c,
            app,
            tree,
            CliRunner(),
            {"@file": fixture_file, "@directory": fixture_directory},
        )
        for c in catalog["cases"]
    ]
    passed = all(r["status"] != "FAIL" for r in receipts)
    if not passed:
        for row in receipts:
            row["uncredited_obligations"] = row["obligations"]
            row["obligations"] = []
    verified = {i for row in receipts for i in row["obligations"]}
    op.require(op.digest(Path(__file__)) == tool_sha, "Tool changed during execution")
    op.require(
        op.digest(Path(parser_module.__file__)) == dependency["parser_sha256"],
        "Parser changed during execution",
    )
    op.require(
        op.digest(Path(core_module.__file__)) == dependency["core_sha256"],
        "Argument processing changed during execution",
    )
    op.identity(
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl",
        calls.WHEEL,
        Path(__file__).parents[1],
    )
    result = {
        "schema": "equiframe.cli-parser-result.v1",
        "candidate": "0.12.0a13",
        "package": package,
        "catalog_sha256": op.digest(args.catalog),
        "tool_sha256": tool_sha,
        "typer": dependency,
        "python": sys.version,
        "optimized": bool(sys.flags.optimize),
        "all_expected": passed,
        "receipts": receipts,
        "new_verified_ids": len(verified),
        "verified": len(done | verified),
        "denominator": 8385,
        "human_review": False,
        "scope": catalog["scope"],
    }
    write(args.output / "result.json", result)
    print(
        json.dumps(
            {
                "all_expected": passed,
                "cases": len(receipts),
                "new_verified_ids": len(verified),
                "verified": result["verified"],
                "failures": [r["case_id"] for r in receipts if r["status"] == "FAIL"],
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
