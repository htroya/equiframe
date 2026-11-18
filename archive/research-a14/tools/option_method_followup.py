"""Check pending A13 validator/serializer methods against frozen literal models.

This driver observes exact Python method calls and normal returns. Construction
alone never establishes method coverage. Complete JSON output must also match a
previously reviewed literal oracle. No branches, native operations, parameter
classes, scientific observations or human approvals are inferred.
"""

from __future__ import annotations

import argparse
import copy
import dis
import hashlib
import importlib.util
import inspect
import json
import platform
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "option_boundary_followup", Path(__file__).with_name("option_boundary_followup.py")
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Boundary verifier unavailable")
boundary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boundary)
op = boundary.op
INVENTORY = "556a3534dcc204c16742fe30ca32843438cb46782e91bb566054a2a0d32014d3"
OPERATIONS = "4c7702cd398d4c0196ec163820b51a115734f59f3c73e21bb140de793bae1b0c"
BOUNDARY_RESULT = "2692f3b9605b7334fd2a439d3022808c64b817cc35a5d0ff5973f59043c9c476"
GROUPS = (
    "model_validators",
    "field_validators",
    "model_serializers",
    "field_serializers",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def method_identity(model, name):
    descriptor = inspect.getattr_static(model, name)
    if isinstance(descriptor, classmethod):
        function, kind = descriptor.__func__, "class"
    elif isinstance(descriptor, staticmethod):
        function, kind = descriptor.__func__, "static"
    else:
        function, kind = descriptor, "instance"
    op.require(inspect.isfunction(function), "Only Python methods can be traced")
    op.require(
        function.__module__.startswith("equiframe.")
        and function.__qualname__.split(".")[0] == model.__name__,
        "Method must be defined on this exact SDK model",
    )
    op.require(
        not inspect.isgeneratorfunction(function)
        and not inspect.iscoroutinefunction(function)
        and not inspect.isasyncgenfunction(function),
        "Suspension is not a normal method return",
    )
    return function, {
        "name": name,
        "module": function.__module__,
        "qualname": function.__qualname__,
        "binding": kind,
        "source_sha256": hashlib.sha256(
            inspect.getsource(function).encode()
        ).hexdigest(),
    }


def prepare(inventory, baseline, seeds, previous, ef):
    closed = {row["id"] for row in baseline["rows"] if row["status"] != "NOT_RUN"} | {
        identifier for receipt in previous for identifier in receipt["obligations"]
    }
    fixtures = {
        name: copy.deepcopy(seed["input"]) for name, seed in seeds["seeds"].items()
    }
    fixtures.update(boundary.literal_seeds())
    expected = {
        case["model"]: copy.deepcopy(case["expected"])
        for case in seeds["cases"]
        if case["operation"] == "model"
    }
    expected.update(boundary.literal_seeds())
    cases = []
    for record in inventory["exports"]:
        if record["kind"] != "model" or record["alias_of"]:
            continue
        name = record["name"].split(".")[-1]
        if name not in fixtures or name not in expected:
            continue
        model = getattr(ef, name)
        decorators = model.__pydantic_decorators__
        decorated = {key for group in GROUPS for key in getattr(decorators, group)}
        methods = []
        for declaration in record.get("methods", []):
            short = declaration["name"]
            identifier = "method:" + record["name"] + "." + short
            if identifier in closed or short not in decorated:
                continue
            _, identity = method_identity(model, short)
            if (
                short in decorators.model_validators
                and decorators.model_validators[short].info.mode == "after"
                and identity["binding"] == "instance"
            ):
                rule = "same_root_instance"
            elif (
                short in decorators.model_serializers
                and decorators.model_serializers[short].info.mode == "wrap"
                and identity["binding"] == "instance"
            ):
                rule = "complete_literal_json"
            else:
                # Other callback signatures require their own return oracle.
                continue
            methods.append({"id": identifier, **identity, "return_rule": rule})
        if methods:
            cases.append(
                {
                    "case_id": f"methods.{name}.frozen-literal",
                    "model": name,
                    "input": fixtures[name],
                    "expected": expected[name],
                    "methods": methods,
                    "obligations": [m["id"] for m in methods],
                    "basis": "Complete pre-existing literal model oracle plus exact owned method entry and normal return",
                }
            )
    return {
        "schema": "equiframe.option-method-catalog.v1",
        "wheel_sha256": boundary.WHEEL,
        "baseline_sha256": boundary.BASELINE,
        "seed_catalog_sha256": boundary.SEEDS,
        "inventory_sha256": INVENTORY,
        "operations_sha256": OPERATIONS,
        "boundary_result_sha256": BOUNDARY_RESULT,
        "obligation_ids_sha256": seeds["obligation_ids_sha256"],
        "cases": cases,
        "scope": "Owned validator/serializer methods on literal synthetic models; no branch, native, parameter or scientific coverage",
    }


def trace_call(operation, targets, on_return=None):
    """Run once and retain only exact-owner calls ending at a RETURN opcode.

    A Python exception also generates a trace 'return' event with None. Its
    offset is not RETURN_VALUE/RETURN_CONST, so it cannot establish completion.
    The previous tracing hook is restored even when the operation fails.
    """
    records = {identifier: {"calls": 0, "normal_returns": 0} for identifier in targets}
    by_code = {}
    for identifier, (function, owner, kind) in targets.items():
        returns = {
            instruction.offset
            for instruction in dis.get_instructions(function)
            if instruction.opname in ("RETURN_VALUE", "RETURN_CONST")
        }
        by_code.setdefault(id(function.__code__), []).append(
            (identifier, function.__code__, owner, kind, returns)
        )
    active = {}

    def trace(frame, event, arg):
        if event == "call" and id(frame.f_code) in by_code:
            accepted = []
            for identifier, code, owner, kind, offsets in by_code[id(frame.f_code)]:
                first = (
                    frame.f_locals.get(frame.f_code.co_varnames[0])
                    if frame.f_code.co_argcount or frame.f_code.co_posonlyargcount
                    else None
                )
                if frame.f_code is code and (
                    kind == "static"
                    or (kind == "class" and first is owner)
                    or (kind == "instance" and type(first) is owner)
                ):
                    records[identifier]["calls"] += 1
                    accepted.append((identifier, offsets))
            if accepted:
                active[id(frame)] = accepted
        elif event == "return":
            for identifier, offsets in active.pop(id(frame), []):
                if frame.f_lasti in offsets:
                    records[identifier]["normal_returns"] += 1
                    if on_return is not None:
                        on_return(identifier, frame, arg)
        return trace

    saved = sys.gettrace()
    try:
        sys.settrace(trace)
        output = operation()
    finally:
        sys.settrace(saved)
    return output, records


def execute(case, ef):
    try:
        model = getattr(ef, case["model"])
        targets = {}
        returns = {}
        op.require(
            len(case["methods"]) > 0
            and [m["id"] for m in case["methods"]] == case["obligations"],
            "Every claimed method requires a trace target",
        )
        for declaration in case["methods"]:
            function, identity = method_identity(model, declaration["name"])
            op.require(
                declaration
                == {
                    "id": declaration["id"],
                    **identity,
                    "return_rule": declaration["return_rule"],
                }
                and declaration["id"]
                == f"method:equiframe.{case['model']}.{declaration['name']}",
                "Frozen method identity differs",
            )
            targets[declaration["id"]] = (function, model, identity["binding"])
            op.require(
                identity["binding"] == "instance"
                and declaration["return_rule"]
                in (
                    "same_root_instance",
                    "complete_literal_json",
                ),
                "A reviewed instance method return rule is required",
            )
            returns[declaration["id"]] = []

        instance = None
        rules = {m["id"]: m["return_rule"] for m in case["methods"]}

        def capture(identifier, frame, value):
            owner = frame.f_locals.get(frame.f_code.co_varnames[0])
            # Snapshot the return now. A caller may mutate a serializer's dict
            # after this event; later output must not hide the incorrect return.
            observed_return = (
                value is owner
                if rules[identifier] == "same_root_instance"
                else canonical(value)
                if type(value) is dict
                else None
            )
            returns[identifier].append((owner, observed_return))

        def operation():
            nonlocal instance
            instance = model.model_validate_json(canonical(case["input"]))
            return instance.model_dump(mode="json")

        output, traces = trace_call(operation, targets, capture)
        matched = canonical(output) == canonical(case["expected"])
        return_matches = {}
        for declaration in case["methods"]:
            identifier = declaration["id"]
            return_matches[identifier] = bool(returns[identifier]) and all(
                owner is instance
                and (
                    value is True
                    if declaration["return_rule"] == "same_root_instance"
                    else value == canonical(case["expected"])
                )
                for owner, value in returns[identifier]
            )
        observed = {
            "output": output,
            "output_matches": matched,
            "methods": traces,
            "return_oracles_match": return_matches,
        }
        completed = all(
            record["calls"] > 0 and record["normal_returns"] == record["calls"]
            for record in traces.values()
        )
        status = (
            "PASS" if matched and completed and all(return_matches.values()) else "FAIL"
        )
    except Exception as error:  # noqa: BLE001 - unexpected errors never earn credit
        observed, status = {"unexpected_exception": type(error).__name__}, "FAIL"
    return {**case, "observed": observed, "status": status}


def inputs(args):
    expected = {
        "baseline": boundary.BASELINE,
        "inventory": INVENTORY,
        "seed_catalog": boundary.SEEDS,
        "operations": OPERATIONS,
        "boundary_result": BOUNDARY_RESULT,
    }
    for key, digest in expected.items():
        op.require(
            op.digest(getattr(args, key)) == digest, "Input identity changed: " + key
        )
    baseline = op.read(args.baseline)
    op.baseline_identity(baseline, boundary.WHEEL)
    previous = []
    for key in ("operations", "boundary_result"):
        result = op.read(getattr(args, key))
        op.require(
            result["package"]["wheel_sha256"] == boundary.WHEEL,
            "Previous result belongs to another wheel",
        )
        previous.extend(result["receipts"])
    summary = boundary.aggregate(baseline, previous, [])
    op.require(summary["verified"] == 5516, "Previous closed union changed")
    return baseline, op.read(args.inventory), op.read(args.seed_catalog), previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for key in (
        "wheel",
        "baseline",
        "inventory",
        "seed-catalog",
        "operations",
        "boundary-result",
        "catalog",
        "output",
    ):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    baseline, inventory, seeds, previous = inputs(args)
    import equiframe as ef

    package = op.identity(
        args.wheel, boundary.WHEEL, Path(__file__).resolve().parents[1]
    )
    if args.mode == "plan":
        catalog = prepare(inventory, baseline, seeds, previous, ef)
        boundary.aggregate(
            baseline,
            previous,
            [{**case, "status": "PASS"} for case in catalog["cases"]],
        )
        boundary.write(args.catalog, catalog)
        print(
            canonical(
                {
                    "planned_cases": len(catalog["cases"]),
                    "planned_obligations": sum(
                        len(c["obligations"]) for c in catalog["cases"]
                    ),
                    "catalog_sha256": op.digest(args.catalog),
                    "executed": False,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256 and op.digest(args.catalog) == args.catalog_sha256,
        "Execution requires the unchanged frozen catalog",
    )
    catalog = op.read(args.catalog)
    expected = prepare(inventory, baseline, seeds, previous, ef)
    op.require(
        canonical(catalog) == canonical(expected), "Catalog differs from literal inputs"
    )
    boundary.aggregate(
        baseline, previous, [{**case, "status": "PASS"} for case in catalog["cases"]]
    )
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = [execute(case, ef) for case in catalog["cases"]]
    summary = boundary.aggregate(baseline, previous, receipts)
    result = {
        "schema": "equiframe.option-method-result.v1",
        "candidate": "0.12.0a13",
        "package": package,
        "catalog_sha256": args.catalog_sha256,
        "tool_sha256": op.digest(Path(__file__)),
        "dependencies": {
            "boundary_tool_sha256": op.digest(Path(boundary.__file__)),
            "operations_tool_sha256": op.digest(Path(op.__file__)),
        },
        "input_sha256": {
            key: op.digest(getattr(args, key))
            for key in (
                "baseline",
                "inventory",
                "seed_catalog",
                "operations",
                "boundary_result",
            )
        },
        "obligation_ids_sha256": seeds["obligation_ids_sha256"],
        "python": sys.version,
        "platform": platform.platform(),
        "optimized": bool(sys.flags.optimize),
        "human_review": False,
        "summary": summary,
        "receipts": receipts,
        "scope": catalog["scope"],
    }
    boundary.write(args.output / "result.json", result)
    print(
        canonical(
            {
                key: value
                for key, value in summary.items()
                if key != "linked_obligations"
            }
        )
    )
    return 1 if summary["case_counts"].get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
