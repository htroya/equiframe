"""Link original literal test oracles to actual installed public API calls.

A call-frame hit alone earns nothing. Frozen literal return checks and the
whole original test must pass, with a complete outcome. Arguments are observed
before the API body. Defaults, explicit finite values and validated admitted
representatives have separate proofs; rejected or incomplete calls earn none.
Required omissions execute the real Python callable with one required argument
absent and require its binding error. No invalid-type coverage is inferred.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import platform
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints

_spec = importlib.util.spec_from_file_location(
    "trace_operations", Path(__file__).with_name("option_operations.py")
)
if _spec is None or _spec.loader is None:
    raise ValueError("Identity verifier unavailable")
op = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(op)
WHEEL = "c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23"
INVENTORY = "556a3534dcc204c16742fe30ca32843438cb46782e91bb566054a2a0d32014d3"
BASELINE = "2b8691cb9c3d0633d309a95fa471ca7df0414af2a3c31f203c60a12cdbe419b2"
PRIOR = (
    (
        "avance_95_20261011/operations-normal/result.json",
        "4c7702cd398d4c0196ec163820b51a115734f59f3c73e21bb140de793bae1b0c",
    ),
    (
        "metas_90_80_85_50_20261011/boundaries-final-normal-strict-fields/result.json",
        "2692f3b9605b7334fd2a439d3022808c64b817cc35a5d0ff5973f59043c9c476",
    ),
    (
        "metas_90_80_85_50_20261011/methods-normal/result.json",
        "65ac2fb9e7804bc8aa9a49c8cea46d89564e8745a59c5cdf5f8a1ecf537c6978",
    ),
    (
        "metas_90_80_85_50_20261011/literal-fields-normal/result.json",
        "fd00b46c4507bd15c114d3728be74df6ce12af43b9668254493ef33e9e4bf4f5",
    ),
    (
        "trace85_20261011/public-types-normal/result.json",
        "bcbe5ef7c0ebcf8e0b78fb08157e75ca5d988db5423affec524e6b92b2873a5c",
    ),
    (
        "trace85_20261011/seed-bounds-normal/result.json",
        "54cf08ad5f0630465aade2056c7cda1b4cd4d3f1df73204e6a52b1662a2b5772",
    ),
    (
        "trace85_20261011/configuration-v2-normal/result.json",
        "d22dfc865013ed0cfe50093353e965e3f3967cea82ca2a6ea7f50fbf7570546c",
    ),
    (
        "trace85_20261011/properties-normal/result.json",
        "8c04f8a4dc05b0269418f4726ed09cc0027f5fe3a21264fc919ad55df88666df",
    ),
)
INCOMPLETE = {
    "not_evaluable",
    "not_estimable",
    "failed",
    "invalid_input",
    "pending",
    "pending_review",
    "cancelled",
}
ALLOWED_APIS = {
    "equiframe.get_compatibility_policy",
    "equiframe.read_contract",
    "equiframe.bag_contract",
    "equiframe.sequence_contract",
    "equiframe.infer_diff_contract",
    "equiframe.verify",
    "equiframe.diff",
    "equiframe.compare",
    "equiframe.read_comparison",
    "equiframe.migrate",
    "equiframe.evaluate_rules",
    "equiframe.reduce_case",
    "equiframe.run_workflow",
}


def source_fixture(tests, workspace):
    """Bind all original helpers/examples, including files imported indirectly."""
    archive = (
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13.tar.gz"
    )
    op.require(
        op.digest(archive)
        == "164b70270344343094dc0a688bf8dbfe20a27112f7227e2f7fe318f085b71935",
        "Original source archive differs",
    )
    files = {}
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            parts = Path(member.name).parts
            if (
                len(parts) < 3
                or parts[1] not in ("tests", "examples")
                or member.isdir()
            ):
                continue
            op.require(
                member.isfile() and ".." not in parts,
                "Expected original regular fixture",
            )
            stream = source.extractfile(member)
            content = stream.read()
            relative = Path(*parts[1:])
            actual = tests.parent / relative
            op.require(
                actual.is_file()
                and not actual.is_symlink()
                and actual.read_bytes() == content,
                "Original helper/example differs: " + str(relative),
            )
            files[relative.as_posix()] = {
                "sha256": op.digest(actual),
                "size_bytes": len(content),
            }
    op.require(
        files and "tests/conftest.py" in files, "Original fixture set is incomplete"
    )
    return files


def literal_observation(result, check):
    value = result
    for step in check["path"]:
        value = (
            getattr(value, step["attribute"])
            if "attribute" in step
            else value[step["item"]]
        )
    expected = ast.literal_eval(check["expected_expression"])
    correct = value is expected if check["operator"] == "is" else value == expected
    return type(correct) is bool and correct


def annotation_for(function, parameter):
    """An unresolved TYPE_CHECKING return must not block other annotations."""
    raw = inspect.get_annotations(function, eval_str=False)
    if parameter not in raw:
        return None
    holder = SimpleNamespace(__annotations__={parameter: raw[parameter]})
    return get_type_hints(
        holder, globalns=dict(function.__globals__), include_extras=True
    )[parameter]


def complete_return(api, result):
    """Require an explicitly reviewed outcome contract, never absence of a flag."""
    if result is None:
        return False
    if api in {
        "equiframe.get_compatibility_policy",
        "equiframe.read_contract",
        "equiframe.bag_contract",
        "equiframe.sequence_contract",
        "equiframe.infer_diff_contract",
    }:
        return True  # Pure validated declarations; no runtime operation claimed.
    if api == "equiframe.verify":
        return (
            getattr(result, "operational_state", None) == "passed"
            and getattr(getattr(result, "coverage", None), "complete", None) is True
        )
    if api not in {
        "equiframe.diff",
        "equiframe.compare",
        "equiframe.read_comparison",
        "equiframe.ingest_file",
        "equiframe.migrate",
        "equiframe.evaluate_rules",
        "equiframe.reduce_case",
        "equiframe.run_workflow",
        "equiframe.import_bundle",
    }:
        return False
    return (
        getattr(result, "complete", None) is True
        and getattr(result, "state", None) not in INCOMPLETE
    )


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def load_inputs(workspace):
    inventory_path = workspace / "revision_95_20261011/trace_inputs/inventory.json"
    baseline_path = workspace / "revision_95_20261011/trace-normal/result.json"
    op.require(
        op.digest(inventory_path) == INVENTORY and op.digest(baseline_path) == BASELINE,
        "Frozen input differs",
    )
    inventory, baseline = op.read(inventory_path), op.read(baseline_path)
    op.baseline_identity(baseline, WHEEL)
    done = {row["id"] for row in baseline["rows"] if row["status"] != "NOT_RUN"}
    for name, digest in PRIOR:
        path = workspace / name
        op.require(op.digest(path) == digest, "Prior receipt differs: " + name)
        previous = op.read(path)
        op.require(previous["package"]["wheel_sha256"] == WHEEL, "Prior wheel differs")
        done.update(i for r in previous["receipts"] for i in r["obligations"])
    op.require(len(done) == 5974, "Prior union differs")
    return inventory, baseline, done


def access_path(node, variable):
    if isinstance(node, ast.Name) and node.id == variable:
        return []
    if isinstance(node, ast.Attribute):
        parent = access_path(node.value, variable)
        return None if parent is None else parent + [{"attribute": node.attr}]
    if isinstance(node, ast.Subscript):
        parent = access_path(node.value, variable)
        try:
            key = ast.literal_eval(node.slice)
        except (ValueError, TypeError):
            return None
        if parent is not None and type(key) in (str, int):
            return parent + [{"item": key}]
    return None


def checks_for(function, variable):
    result = []
    for statement in function.body:
        if not isinstance(statement, ast.Assert):
            continue
        terms = [statement.test]
        # Only necessary positive conjuncts; never mine an OR or negation.
        while any(
            isinstance(term, ast.BoolOp) and isinstance(term.op, ast.And)
            for term in terms
        ):
            terms = [
                child
                for term in terms
                for child in (
                    term.values
                    if isinstance(term, ast.BoolOp) and isinstance(term.op, ast.And)
                    else [term]
                )
            ]
        for node in terms:
            if (
                not isinstance(node, ast.Compare)
                or len(node.ops) != 1
                or not isinstance(node.ops[0], (ast.Eq, ast.Is))
            ):
                continue
            for observed, expected in (
                (node.left, node.comparators[0]),
                (node.comparators[0], node.left),
            ):
                path = access_path(observed, variable)
                try:
                    value = ast.literal_eval(expected)
                    canonical(value)
                except (ValueError, TypeError, SyntaxError):
                    continue
                if (
                    path is None
                    or value is None
                    or (isinstance(value, str) and value in INCOMPLETE)
                ):
                    continue
                # A false completeness flag is a negative oracle, not a complete call.
                if path == [{"attribute": "complete"}] and value is False:
                    continue
                result.append(
                    {
                        "path": path,
                        "expected": value,
                        "expected_expression": ast.unparse(expected),
                        "operator": "is" if isinstance(node.ops[0], ast.Is) else "eq",
                        "assertion": ast.unparse(node),
                        "line": statement.lineno,
                    }
                )
    return result


def plan(tests, inventory, workspace):
    exports = {
        r["name"].split(".")[-1]: r
        for r in inventory["exports"]
        if r["kind"] == "function" and not r["alias_of"]
    }
    cases = []
    for path in sorted(tests.glob("test_*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        imports = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for item in node.names:
                    if item.name == "equiframe":
                        imports[item.asname or item.name] = "module"
            elif isinstance(node, ast.ImportFrom) and node.module == "equiframe":
                for item in node.names:
                    if item.name in exports:
                        imports[item.asname or item.name] = item.name
        for function in tree.body:
            if not isinstance(
                function, ast.FunctionDef
            ) or not function.name.startswith("test_"):
                continue
            if any(
                isinstance(node, ast.Name)
                and node.id in {"monkeypatch", "mocker", "mock", "patch"}
                for node in ast.walk(function)
            ):
                continue
            assignments = {}
            for node in ast.walk(function):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assignments[target.id] = assignments.get(target.id, 0) + 1
            for node in function.body:
                if (
                    not isinstance(node, ast.Assign)
                    or len(node.targets) != 1
                    or not isinstance(node.targets[0], ast.Name)
                    or not isinstance(node.value, ast.Call)
                ):
                    continue
                variable, call = node.targets[0].id, node.value
                checks = checks_for(function, variable)
                if (
                    assignments[variable] != 1
                    or not checks
                    or any(isinstance(a, ast.Starred) for a in call.args)
                    or any(k.arg is None for k in call.keywords)
                ):
                    continue
                name = None
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and imports.get(call.func.value.id) == "module"
                ):
                    name = call.func.attr
                elif isinstance(call.func, ast.Name):
                    name = imports.get(call.func.id)
                if name not in exports:
                    continue
                if "equiframe." + name not in ALLOWED_APIS:
                    continue
                cases.append(
                    {
                        "case_id": f"literal-api.{path.stem}.{function.name}.{call.lineno}",
                        "test_node": path.name + "::" + function.name,
                        "test_file": path.name,
                        "test_sha256": op.digest(path),
                        "call_lines": [call.lineno, call.end_lineno],
                        "api": "equiframe." + name,
                        "parameters": exports[name]["parameters"],
                        "positional_count": len(call.args),
                        "keyword_names": [k.arg for k in call.keywords],
                        "checks": checks,
                        "result_variable": variable,
                    }
                )
    return {
        "schema": "equiframe.literal-api-catalog.v1",
        "inventory_sha256": INVENTORY,
        "sdk_executed": False,
        "cases": cases,
        "source_fixture": source_fixture(tests, workspace),
    }


class Calls:
    def __init__(self, catalog, tests, module, pending):
        import pytest

        self.catalog, self.tests, self.module, self.pending = (
            catalog,
            tests,
            module,
            pending,
        )
        self.receipts, self.frames, self.observations = [], {}, []
        self.active, self.node = False, None
        self.functions = {
            r["api"]: getattr(module, r["api"].split(".")[-1]) for r in catalog["cases"]
        }
        self.codes = {
            id(function.__code__): (function.__code__, api)
            for api, function in self.functions.items()
            if hasattr(function, "__code__")
        }
        self.previous_profile, self.previous_trace = None, None
        self.reached = {}
        self.test_functions = {}
        for case in catalog["cases"]:
            self.test_functions.setdefault(str(tests / case["test_file"]), set()).add(
                case["test_node"].split("::")[-1]
            )

        def hook(item):
            yield from self.call_hook(item)

        self.pytest_runtest_call = pytest.hookimpl(hookwrapper=True)(hook)

    def profile(self, frame, event, result):
        if not self.active:
            return
        code = self.codes.get(id(frame.f_code))
        if (
            event == "call"
            and code is not None
            and frame.f_code is code[0]
            and frame.f_back is not None
        ):
            caller = frame.f_back
            matches = [
                r
                for r in self.catalog["cases"]
                if r["api"] == code[1]
                and str((self.tests / r["test_file"]).resolve())
                == str(Path(caller.f_code.co_filename).resolve())
                and r["call_lines"][0] <= caller.f_lineno <= r["call_lines"][1]
                and self.node.split("[", 1)[0].endswith(r["test_node"])
            ]
            if len(matches) == 1:
                self.frames[id(frame)] = (matches[0], dict(frame.f_locals))
        elif event == "return" and id(frame) in self.frames:
            case, arguments = self.frames.pop(id(frame))
            try:
                valid = complete_return(case["api"], result) and all(
                    literal_observation(result, check) for check in case["checks"]
                )
            except (AttributeError, KeyError, IndexError, TypeError, ValueError):
                valid = False
            self.observations.append((case, arguments, result, valid))

    def trace(self, frame, event, argument):
        if event == "call" and frame.f_code.co_name in self.test_functions.get(
            frame.f_code.co_filename, ()
        ):
            return self.trace_line
        return None

    def trace_line(self, frame, event, argument):
        if event == "line":
            for case, _, result, valid in self.observations:
                if (
                    not valid
                    or frame.f_locals.get(case["result_variable"]) is not result
                ):
                    continue
                for check in case["checks"]:
                    if frame.f_lineno == check["line"]:
                        try:
                            correct = literal_observation(result, check)
                        except (
                            AttributeError,
                            KeyError,
                            IndexError,
                            TypeError,
                            ValueError,
                        ):
                            correct = False
                        if correct:
                            self.reached.setdefault(case["case_id"], set()).add(
                                check["line"]
                            )
        return self.trace_line

    def call_hook(self, item):
        self.node, self.active, self.observations, self.frames = (
            item.nodeid,
            True,
            [],
            {},
        )
        self.previous_profile = sys.getprofile()
        self.previous_trace = sys.gettrace()
        self.reached = {}
        sys.setprofile(self.profile)
        sys.settrace(self.trace)
        try:
            outcome = yield
        finally:
            sys.setprofile(self.previous_profile)
            sys.settrace(self.previous_trace)
            self.active = False
        if outcome.excinfo is not None:
            self.receipts.append(
                {"case_id": item.nodeid, "status": "FAIL", "obligations": []}
            )
            return
        observed = set()
        for case, arguments, result, valid in self.observations:
            observed.add(case["case_id"])
            lines = {check["line"] for check in case["checks"]}
            if not valid or not lines <= self.reached.get(case["case_id"], set()):
                self.receipts.append(
                    {
                        "case_id": case["case_id"] + "::" + item.nodeid,
                        "status": "EXCLUDED_ORACLE",
                        "obligations": [],
                        "assertion_lines_reached": sorted(
                            self.reached.get(case["case_id"], set())
                        ),
                    }
                )
                continue
            records = self.prove(case, arguments, result, item.nodeid)
            for record in records:
                record["assertion_lines_reached"] = sorted(lines)
                record["return_bound_by_identity"] = True
            self.receipts.extend(records)
        for case in self.catalog["cases"]:
            if (
                item.nodeid.split("[", 1)[0].endswith(case["test_node"])
                and case["case_id"] not in observed
            ):
                self.receipts.append(
                    {
                        "case_id": case["case_id"] + "::" + item.nodeid,
                        "status": "NOT_OBSERVED",
                        "obligations": [],
                    }
                )

    def prove(self, case, arguments, result, node):
        from pydantic import TypeAdapter

        record = {
            "case_id": case["case_id"] + "::" + node,
            "api": case["api"],
            "status": "PASS",
            "obligations": [],
            "checks": [],
            "parameter_proofs": [],
        }
        omissions = []
        if not complete_return(case["api"], result):
            record.update(
                status="EXCLUDED_INCOMPLETE", reason="No complete actual return"
            )
            return [record]
        for check in case["checks"]:
            value = result
            for step in check["path"]:
                value = (
                    getattr(value, step["attribute"])
                    if "attribute" in step
                    else value[step["item"]]
                )
            expected = ast.literal_eval(check["expected_expression"])
            correct = (
                value is expected if check["operator"] == "is" else value == expected
            )
            op.require(
                type(correct) is bool and correct,
                "Frozen literal return expectation failed",
            )
            record["checks"].append(check)
        links = ["api:" + case["api"]]
        function = self.functions[case["api"]]
        op.require(
            getattr(self.module, case["api"].split(".")[-1]) is function,
            "Public callable identity changed during the original test",
        )
        signature = inspect.signature(function)
        positional = [
            n
            for n, p in signature.parameters.items()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        explicit = set(case["keyword_names"]) | set(
            positional[: case["positional_count"]]
        )
        for declaration in case["parameters"]:
            name = declaration["id"].split(":")[-1]
            if name not in arguments:
                continue
            value, prefix = arguments[name], declaration["id"]
            proof = {
                "parameter": name,
                "explicit": name in explicit,
                "python_type": type(value).__module__ + "." + type(value).__qualname__,
                "obligations": [],
            }
            try:
                literal = canonical(value)
                if len(literal) <= 16384:
                    proof["observed_literal"] = json.loads(literal)
            except (TypeError, ValueError):
                pass
            if name not in explicit and not declaration["required"]:
                try:
                    equal = canonical(value) == canonical(declaration["default"])
                except (TypeError, ValueError):
                    equal = False
                if equal:
                    proof["obligations"].append(prefix + ":default")
            if name in explicit:
                for finite in declaration["finite_values"]:
                    try:
                        if canonical(value) == canonical(finite):
                            proof["obligations"].append(
                                prefix + ":value:" + canonical(finite)
                            )
                    except (TypeError, ValueError):
                        pass
                if "admitted representative" in declaration["continuous_classes"]:
                    try:
                        annotation = annotation_for(function, name)
                        if annotation is None:
                            raise ValueError("Parameter has no evaluable annotation")
                        TypeAdapter(annotation).validate_python(value, strict=True)
                    except Exception as error:  # noqa: BLE001 - unsupported or rejected annotations earn no credit
                        proof["annotation_not_credited"] = type(error).__name__
                    else:
                        index = declaration["continuous_classes"].index(
                            "admitted representative"
                        )
                        proof["obligations"].append(prefix + ":class:" + str(index))
            links.extend(proof["obligations"])
            record["parameter_proofs"].append(proof)
            if (
                declaration["required"]
                and prefix + ":required_omission" in self.pending
                and inspect.signature(function, follow_wrapped=False) == signature
                and all(
                    p.kind not in (p.POSITIONAL_ONLY, p.VAR_POSITIONAL, p.VAR_KEYWORD)
                    for p in signature.parameters.values()
                )
            ):
                kwargs = {
                    n: arguments[n]
                    for n in signature.parameters
                    if n != name and n in arguments
                }
                try:
                    function(**kwargs)
                except TypeError as error:
                    message = str(error)
                    if (
                        "missing" in message
                        and "required" in message
                        and repr(name) in message
                    ):
                        link = prefix + ":required_omission"
                        omissions.append(
                            {
                                "case_id": record["case_id"] + ".omit." + name,
                                "status": "EXPECTED_REJECTION",
                                "api": case["api"],
                                "parameter": name,
                                "error_type": "TypeError",
                                "error": message,
                                "obligations": [link] if link in self.pending else [],
                            }
                        )
                else:
                    raise ValueError("Required omission unexpectedly admitted")
        record["obligations"] = sorted(set(links) & self.pending)
        return [record, *omissions]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in ("workspace", "tests", "catalog", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    inventory, baseline, done = load_inputs(args.workspace.resolve())
    if args.mode == "plan":
        catalog = plan(args.tests.resolve(), inventory, args.workspace.resolve())
        write(args.catalog, catalog)
        print(
            json.dumps(
                {
                    "planned_cases": len(catalog["cases"]),
                    "sdk_executed": False,
                    "catalog_sha256": op.digest(args.catalog),
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256 and op.digest(args.catalog) == args.catalog_sha256,
        "Catalog changed",
    )
    catalog = op.read(args.catalog)
    op.require(
        canonical(catalog)
        == canonical(plan(args.tests.resolve(), inventory, args.workspace.resolve())),
        "Original tests or frozen oracles changed",
    )
    op.require(not args.output.exists(), "Preserve earlier runs")
    args.output.mkdir(parents=True)
    import equiframe as ef
    import pytest

    package = op.identity(
        args.workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl",
        WHEEL,
        Path(__file__).parents[1],
    )
    tool_sha_before = op.digest(Path(__file__))
    pending = {row["id"] for row in baseline["rows"]} - done
    plugin = Calls(catalog, args.tests.resolve(), ef, pending)
    pytest.register_assert_rewrite(
        *(path.stem for path in args.tests.glob("test_*.py"))
    )
    nodes = sorted(
        {str(args.tests.resolve() / r["test_node"]) for r in catalog["cases"]}
    )
    exit_code = int(
        pytest.main(
            [
                "--import-mode=prepend",
                "--assert=rewrite",
                "-q",
                "-x",
                "-o",
                "addopts=",
                "-o",
                "pythonpath=",
                "-o",
                "cache_dir=" + str(args.output.resolve() / "pytest-cache"),
                "--basetemp=" + str(args.output.resolve() / "pytest-tmp"),
                "--junitxml=" + str(args.output.resolve() / "junit.xml"),
                *nodes,
            ],
            plugins=[plugin],
        )
    )
    for case in catalog["cases"]:
        op.require(
            op.digest(args.tests / case["test_file"]) == case["test_sha256"],
            "Test changed during execution",
        )
    op.require(
        source_fixture(args.tests.resolve(), args.workspace.resolve())
        == catalog["source_fixture"],
        "Original helpers/examples changed during execution",
    )
    op.identity(
        args.workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl",
        WHEEL,
        Path(__file__).parents[1],
    )
    op.require(
        op.digest(Path(__file__)) == tool_sha_before,
        "Verifier source changed during execution",
    )
    verified = {
        i
        for r in plugin.receipts
        if r["status"] in ("PASS", "EXPECTED_REJECTION")
        for i in r["obligations"]
    }
    # A failing suite rejects the entire new increment, even if some calls passed.
    counted = verified if exit_code == 0 else set()
    if exit_code != 0:
        for record in plugin.receipts:
            record["uncredited_obligations"] = record["obligations"]
            record["obligations"] = []
    result = {
        "schema": "equiframe.literal-api-result.v1",
        "package": package,
        "catalog_sha256": op.digest(args.catalog),
        "tool_sha256": tool_sha_before,
        "prior_result_hashes": [digest for _, digest in PRIOR],
        "optimized": bool(sys.flags.optimize),
        "python": platform.python_version(),
        "pytest_exit_code": exit_code,
        "human_review": False,
        "receipts": plugin.receipts,
        "new_verified_obligations": len(counted),
        "verified": len(done | counted),
        "total": 8385,
        "percent": 100 * len(done | counted) / 8385,
        "scope": "Original literal semantic tests, actual public arguments and Python binding; not exhaustive API semantics or scientific acceptance",
    }
    write(args.output / "result.json", result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "pytest_exit_code",
                    "new_verified_obligations",
                    "verified",
                    "total",
                    "percent",
                )
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
