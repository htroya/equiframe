"""Observe local exception contracts with complete literal messages and state."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import inspect
import json
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "defaults", Path(__file__).with_name("option_model_default_followup.py")
)
defaults = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(defaults)
contexts, op = defaults.contexts, defaults.op
PRIOR_RESULT = "f26f749f4e13f84edb9eea17f526c53e6b4316a5968b27e76c92555c4dea3a81"
CODES = {
    "EquiFrameError": "equiframe_error",
    "ContractIOError": "contract_io_error",
    "InvalidExecutionInput": "invalid_execution_input",
    "CapabilityError": "unsupported_capability",
    "MissingDependencyError": "missing_optional_dependency",
    "ArtifactIntegrityError": "artifact_integrity_error",
    "ArtifactIOError": "artifact_io_error",
    "ExecutionCancelled": "execution_cancelled",
    "ExecutionTimeout": "execution_timeout",
    "ResourceLimitError": "resource_limit",
    "NativeEngineError": "native_engine_error",
    "EquivalenceInputError": "invalid_assertion_input",
}
CONTRACT_CODES = {
    "ContractValidationError": "invalid_contract",
    "ContractParseError": "invalid_json",
    "SchemaVersionError": "unsupported_schema_version",
}
ASSERTION_KIND = {
    "EquivalenceAssertionError": "different",
    "EquivalenceDifferentError": "different",
    "EquivalenceNotEvaluableError": "not_evaluable",
    "EquivalenceGuaranteeError": "guarantee_mismatch",
    "EquivalenceEvidenceError": "evidence_missing",
}
MESSAGES = {
    "different": "[different] Comparison differs; review the report and declared policies (reason: cell_value)",
    "not_evaluable": "[not_evaluable] Comparison is not evaluable; resolve the diagnostic and rerun (reason: resource_exhausted)",
    "guarantee_mismatch": "[guarantee_mismatch] Required comparison context differs; review policy pins",
    "evidence_missing": "[evidence_missing] Required evidence is missing; restore finalized comparison files",
}
ISSUES_MESSAGE = '$.records[2].amount: manual literal [fixture_code]\n$["odd key"]: second literal [other_code]'


def mro_names(name):
    suffix = ["Exception", "BaseException", "object"]
    if name == "EquiFrameError":
        return [name, *suffix]
    if name in CONTRACT_CODES:
        return [
            name,
            *([] if name == "ContractValidationError" else ["ContractValidationError"]),
            "EquiFrameError",
            *suffix,
        ]
    if name in ASSERTION_KIND:
        return [
            name,
            *(
                []
                if name == "EquivalenceAssertionError"
                else ["EquivalenceAssertionError"]
            ),
            "AssertionError",
            "EquiFrameError",
            *suffix,
        ]
    chain = {
        "CapabilityError": ["InvalidExecutionInput"],
        "MissingDependencyError": ["CapabilityError", "InvalidExecutionInput"],
        "ArtifactIntegrityError": ["InvalidExecutionInput"],
        "EquivalenceInputError": ["ValueError"],
    }
    return [name, *chain.get(name, []), "EquiFrameError", *suffix]


def inputs(workspace):
    inventory, baseline, done, seed = defaults.inputs(workspace)
    path = workspace / "trace85_20261011/model-default-normal-v1/result.json"
    op.require(op.digest(path) == PRIOR_RESULT, "Prior field-default receipt differs")
    done.update(
        identity for row in op.read(path)["receipts"] for identity in row["obligations"]
    )
    op.require(len(done) == 6266, "Prior unique union differs")
    return inventory, baseline, done, seed


def decisions(seed):
    original = next(
        case["expected"]
        for case in seed["cases"]
        if case["id"] == "EquivalenceDecision.construction"
    )
    result = {}
    for kind in MESSAGES:
        value = copy.deepcopy(original)
        value.update(
            accepted=False,
            code=kind,
            state="different"
            if kind == "different"
            else "not_evaluable"
            if kind == "not_evaluable"
            else "equivalent",
            complete=kind != "not_evaluable",
            counts_final=kind != "not_evaluable",
            guarantee_conforms=True,
            guarantee_failures=[],
            evidence_status="not_requested",
            evidence_code=None,
            safe_reason_code=None,
        )
        if kind == "different":
            value["safe_reason_code"] = "cell_value"
        elif kind == "not_evaluable":
            value["safe_reason_code"] = "resource_exhausted"
        elif kind == "guarantee_mismatch":
            value.update(
                guarantee_conforms=False, guarantee_failures=["required_reference"]
            )
        else:
            value.update(evidence_status="missing", evidence_code="evidence_missing")
        result[kind] = value
    return result


def plan(inventory, pending, seed):
    declarations = {row["name"].split(".")[-1]: row for row in inventory["exports"]}
    cases = []
    for name in (*CODES, *CONTRACT_CODES, *ASSERTION_KIND):
        declaration = declarations[name]
        api = "api:" + declaration["name"]
        op.require(api in pending, "Exception API must be a known pending ID")
        parameters = {
            parameter["id"].split(":")[-1]: parameter
            for parameter in declaration["parameters"]
        }
        variants = (
            ("default", "explicit-null", "explicit-path")
            if name in ASSERTION_KIND
            else ("default",)
        )
        for variant in variants:
            ids = [api]
            kwargs, args = {}, []
            if name in CODES:
                op.require(
                    not parameters, "No C constructor parameter IDs may be invented"
                )
                args = ["constructor fixture"]
                attributes, message, code = {}, "constructor fixture", CODES[name]
            elif name in CONTRACT_CODES:
                kwargs = {"issues": "@issues"}
                ids.append(parameters["issues"]["id"] + ":class:0")
                attributes, message, code = (
                    {"issues": "@issues"},
                    ISSUES_MESSAGE,
                    CONTRACT_CODES[name],
                )
            else:
                kind = ASSERTION_KIND[name]
                kwargs = {"decision": "@" + kind}
                ids.append(parameters["decision"]["id"] + ":class:0")
                parameter = parameters["report_path"]
                if variant == "default":
                    ids.append(parameter["id"] + ":default")
                elif variant == "explicit-null":
                    kwargs["report_path"] = None
                    op.require(
                        None in parameter["finite_values"],
                        "Explicit null must be declared",
                    )
                    ids.append(parameter["id"] + ":value:null")
                else:
                    kwargs["report_path"] = "@report_path"
                    ids.append(parameter["id"] + ":class:0")
                attributes, message, code = (
                    {"decision": "@" + kind, "code": kind},
                    MESSAGES[kind],
                    kind,
                )
                if variant == "explicit-path":
                    message += '; report: "report.html"'
            for parameter in parameters.values():
                if parameter["id"] + ":class:0" in ids:
                    op.require(
                        parameter["continuous_classes"][0] == "admitted representative",
                        "Only declared admitted class supported",
                    )
            op.require(
                set(ids) <= pending, "No unknown, already credited or inferred IDs"
            )
            cases.append(
                {
                    "case_id": name + "." + variant,
                    "class": name,
                    "args": args,
                    "kwargs": kwargs,
                    "expected_attributes": attributes,
                    "expected_message": message,
                    "expected_code": code,
                    "expected_mro": mro_names(name),
                    "initializer_kind": "C/inherited" if name in CODES else "Python",
                    "parameters": declaration["parameters"],
                    "obligations": ids,
                }
            )
    return {
        "schema": "equiframe.exception-catalog.v1",
        "cases": cases,
        "decisions": decisions(seed),
        "seed_catalog_sha256": contexts.SEED_CATALOG,
        "prior_default_sha256": PRIOR_RESULT,
        "scope": "Complete local exception instance, literal message/args/code/MRO, actual Python initializer binding or controlled C invocation, same-object raise/catch; synthetic decision fixtures, not real IO/engine/comparison failures",
    }


def fixtures(catalog):
    import equiframe as ef

    issues = (
        ef.ValidationIssue("fixture_code", ("records", 2, "amount"), "manual literal"),
        ef.ValidationIssue("other_code", ("odd key",), "second literal"),
    )
    expected = (
        {
            "code": "fixture_code",
            "location": contexts.tuple_recipe("records", 2, "amount"),
            "message": "manual literal",
        },
        {
            "code": "other_code",
            "location": contexts.tuple_recipe("odd key"),
            "message": "second literal",
        },
    )
    op.require(
        all(
            type(issue) is ef.ValidationIssue
            and contexts.matches(vars(issue), value, {})
            for issue, value in zip(issues, expected, strict=True)
        ),
        "Literal issue fixtures differ",
    )
    op.require(
        [issue.path for issue in issues] == ["$.records[2].amount", '$["odd key"]'],
        "Literal path fixtures differ",
    )
    references = {"@issues": issues, "@report_path": Path("report.html")}
    for kind, value in catalog["decisions"].items():
        decision = ef.EquivalenceDecision.model_validate_json(json.dumps(value))
        op.require(
            type(decision) is ef.EquivalenceDecision
            and contexts.matches(decision.model_dump(mode="json"), value, {}),
            "Complete literal decision fixture differs",
        )
        references["@" + kind] = decision
    return references


def controlled_construct(cls, args, kwargs):
    return cls(*args, **kwargs)


def execute(case, references):
    import builtins

    import equiframe as ef

    cls = getattr(ef, case["class"])
    args = tuple(case["args"])
    kwargs = {
        name: contexts.resolve(value, references)
        for name, value in case["kwargs"].items()
    }
    observed, default_proof = [], None
    if case["initializer_kind"] == "Python":
        bound = inspect.signature(cls).bind(*args, **kwargs)
        bound.apply_defaults()
        names = [parameter["id"].split(":")[-1] for parameter in case["parameters"]]
        code = cls.__init__.__code__

        def profile(frame, event, _):
            if (
                event == "call"
                and frame.f_code is code
                and type(frame.f_locals["self"]) is cls
                and frame.f_back.f_code is controlled_construct.__code__
            ):
                observed.append({name: frame.f_locals[name] for name in names})

        saved = sys.getprofile()
        try:
            sys.setprofile(profile)
            error = controlled_construct(cls, args, kwargs)
        finally:
            sys.setprofile(saved)
        binding = len(observed) == 1 and all(
            observed[0][name] is bound.arguments[name] for name in names
        )
        if "report_path" in names and "report_path" not in kwargs:
            default_proof = (
                bound.arguments["report_path"] is None
                and observed[0]["report_path"] is None
            )
            binding = binding and default_proof
    else:
        op.require(
            not hasattr(cls.__init__, "__code__"),
            "C initializer must be classified honestly",
        )
        error = controlled_construct(cls, args, kwargs)
        binding = True
    passed = (
        binding
        and getattr(ef, case["class"]) is cls
        and type(error) is cls
        and type(error.args) is tuple
        and error.args == (case["expected_message"],)
        and type(error.args[0]) is str
        and str(error) == case["expected_message"]
        and type(error.code) is str
        and error.code == case["expected_code"]
        and contexts.matches(vars(error), case["expected_attributes"], references)
        and [base.__name__ for base in cls.__mro__] == case["expected_mro"]
    )
    catches = []
    for name in case["expected_mro"][:-1]:
        base = getattr(ef, name, getattr(builtins, name, None))
        op.require(
            isinstance(base, type) and issubclass(base, BaseException),
            "Expected exception base differs",
        )
        try:
            raise error
        except base as caught:
            catches.append({"base": name, "same_object": caught is error})
    passed = (
        passed
        and all(row["same_object"] for row in catches)
        and contexts.matches(vars(error), case["expected_attributes"], references)
    )
    return {
        "case_id": case["case_id"],
        "status": "PASS" if passed else "FAIL",
        "initializer_kind": case["initializer_kind"],
        "actual_python_initializer_entries": len(observed),
        "binding_verified": binding,
        "omitted_report_path_default": default_proof,
        "whole_attributes_match": contexts.matches(
            vars(error), case["expected_attributes"], references
        ),
        "literal_message_args_code_match": error.args == (case["expected_message"],)
        and str(error) == case["expected_message"]
        and error.code == case["expected_code"],
        "same_object_catches": catches,
        "c_initializer_body_observed": False,
        "obligations": case["obligations"] if passed else [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in ("workspace", "catalog", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    inventory, baseline, done, seed = inputs(workspace)
    catalog = plan(inventory, {row["id"] for row in baseline["rows"]} - done, seed)
    if args.mode == "plan":
        contexts.prior.previous.write(args.catalog, catalog)
        print(
            json.dumps(
                {
                    "planned_cases": len(catalog["cases"]),
                    "planned_new_ids": len(
                        {
                            identity
                            for case in catalog["cases"]
                            for identity in case["obligations"]
                        }
                    ),
                    "catalog_sha256": op.digest(args.catalog),
                    "new_verified_ids": 0,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256
        and op.digest(args.catalog) == args.catalog_sha256
        and op.read(args.catalog) == catalog,
        "Frozen exception catalog differs",
    )
    wheel = (
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl"
    )
    package = op.identity(
        wheel, contexts.prior.previous.calls.WHEEL, Path(__file__).parents[1]
    )
    tool_sha = op.digest(Path(__file__))
    args.output.mkdir(parents=True, exist_ok=False)
    references = fixtures(catalog)
    receipts = [execute(case, references) for case in catalog["cases"]]
    passed = all(row["status"] == "PASS" for row in receipts)
    if not passed:
        for row in receipts:
            row["uncredited_obligations"], row["obligations"] = row["obligations"], []
    current = {identity for row in receipts for identity in row["obligations"]}
    op.require(op.digest(Path(__file__)) == tool_sha, "Tool changed during run")
    op.identity(wheel, contexts.prior.previous.calls.WHEEL, Path(__file__).parents[1])
    contexts.prior.previous.write(
        args.output / "result.json",
        {
            "schema": "equiframe.exception-result.v1",
            "candidate": "0.12.0a13",
            "package": package,
            "tool_sha256": tool_sha,
            "catalog_sha256": op.digest(args.catalog),
            "python": sys.version,
            "optimized": bool(sys.flags.optimize),
            "all_expected": passed,
            "receipts": receipts,
            "new_verified_ids": len(current),
            "verified": len(done | current),
            "denominator": 8385,
            "human_review": False,
            "scope": catalog["scope"],
        },
    )
    print(
        json.dumps(
            {
                "all_expected": passed,
                "cases": len(receipts),
                "new_verified_ids": len(current),
                "verified": len(done | current),
                "failures": [
                    row["case_id"] for row in receipts if row["status"] != "PASS"
                ],
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
