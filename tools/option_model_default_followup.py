"""Observe twelve field defaults against complete original literal model oracles."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "contexts", Path(__file__).with_name("option_context_constructor_followup.py")
)
contexts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contexts)
op = contexts.op
CONTEXT_RESULT = "4a81e1aefbb4c47e152025251168af312dc5f05b05ec651f6cab4b289d9246e7"
FIELDS = {
    "Arithmetic": ("rounding",),
    "Deduplicate": ("by", "ties"),
    "EquiJoin": ("cardinality",),
    "ComparisonSpec": ("policy",),
    "ExecutionPlan": ("options",),
    "MigrationSpec": (
        "execution_options",
        "comparison_options",
        "rule_options",
        "profile_options",
        "options",
    ),
    "ComparisonPolicy": ("justification",),
}
UNSERIALIZED = {
    ("Arithmetic", "rounding"): "exact",
    ("Deduplicate", "by"): contexts.tuple_recipe(),
    ("Deduplicate", "ties"): "reject",
    ("EquiJoin", "cardinality"): "many_to_many",
}
FACTORY_TYPES = {
    ("ComparisonSpec", "policy"): "ComparisonPolicy",
    ("ExecutionPlan", "options"): "ExecutionOptions",
    ("MigrationSpec", "execution_options"): "ExecutionOptions",
    ("MigrationSpec", "comparison_options"): "ComparisonOptions",
    ("MigrationSpec", "rule_options"): "RuleOptions",
    ("MigrationSpec", "profile_options"): "ProfileOptions",
    ("MigrationSpec", "options"): "MigrationOptions",
}


def inputs(workspace):
    inventory, baseline, done, seed = contexts.inputs(workspace)
    path = workspace / "trace85_20261011/context-constructor-normal-v2/result.json"
    op.require(op.digest(path) == CONTEXT_RESULT, "Prior context receipt differs")
    done.update(i for row in op.read(path)["receipts"] for i in row["obligations"])
    op.require(len(done) == 6254, "Prior unique union differs")
    return inventory, baseline, done, seed


def plan(inventory, pending, seed):
    declarations = {row["name"].split(".")[-1]: row for row in inventory["exports"]}
    cases = {row["id"]: row for row in seed["cases"]}
    result = []
    for name, fields in FIELDS.items():
        declaration = declarations[name]
        op.require(
            declaration["kind"] == "model",
            "Only model field defaults belong in this lot",
        )
        if name == "ComparisonPolicy":
            expected = cases["ComparisonSpec.construction"]["expected"]["policy"]
            original = expected
        else:
            expected = cases[name + ".construction"]["expected"]
            original = seed["seeds"][name]["input"]
        metadata = {
            field["id"].split(":")[-1]: field for field in declaration["fields"]
        }
        for field in fields:
            descriptor = metadata[field]
            identity = descriptor["id"] + ":default"
            op.require(
                identity in pending and not descriptor["required"],
                "Known pending non-required default only",
            )
            data = copy.deepcopy(original)
            data.pop(field, None)
            field_expected = UNSERIALIZED.get((name, field), expected.get(field))
            factory_type = FACTORY_TYPES.get((name, field))
            op.require(
                bool(descriptor["default_factory"]) is bool(factory_type),
                "Factory declaration differs",
            )
            result.append(
                {
                    "case_id": name + "." + field + ".omitted",
                    "model": name,
                    "field": field,
                    "input": data,
                    "expected_model_json": copy.deepcopy(expected),
                    "expected_field": copy.deepcopy(field_expected),
                    "factory_type": factory_type,
                    "declaration": descriptor,
                    "obligations": [identity],
                }
            )
    return {
        "schema": "equiframe.model-default-catalog.v1",
        "cases": result,
        "seed_catalog_sha256": contexts.SEED_CATALOG,
        "prior_context_sha256": CONTEXT_RESULT,
        "scope": "Original complete literal JSON plus exact attribute oracle; root JSON validation observed, target field absent from supplied JSON and model_fields_set; actual default/factory declaration checked; no constructor parameter or API IDs",
    }


def field_matches(value, case):
    import equiframe as ef

    if case["factory_type"]:
        cls = getattr(ef, case["factory_type"])
        return type(value) is cls and contexts.matches(
            value.model_dump(mode="json"), case["expected_field"], {}
        )
    return contexts.matches(value, case["expected_field"], {})


def execute(case):
    import equiframe as ef

    cls, field = getattr(ef, case["model"]), case["field"]
    text = json.dumps(case["input"], ensure_ascii=False, allow_nan=False)
    op.require(
        field not in json.loads(text), "Target must be absent from actual JSON input"
    )
    code = cls.model_validate_json.__func__.__code__
    observed = []

    def profile(frame, event, _):
        if (
            event == "call"
            and frame.f_code is code
            and frame.f_locals["cls"] is cls
            and frame.f_back.f_code is execute.__code__
        ):
            observed.append(frame.f_locals["json_data"])

    saved = sys.getprofile()
    try:
        sys.setprofile(profile)
        model = cls.model_validate_json(text)
    finally:
        sys.setprofile(saved)
    descriptor = cls.model_fields[field]
    passed = (
        len(observed) == 1
        and observed[0] == text
        and field not in model.model_fields_set
        and contexts.matches(
            model.model_dump(mode="json"), case["expected_model_json"], {}
        )
        and field_matches(getattr(model, field), case)
    )
    factory_proof = None
    if case["factory_type"]:
        factory_cls = getattr(ef, case["factory_type"])
        second = cls.model_validate_json(text)
        factory_proof = (
            descriptor.default_factory is factory_cls
            and getattr(model, field) is not getattr(second, field)
            and field_matches(getattr(second, field), case)
            and field not in second.model_fields_set
            and contexts.matches(
                second.model_dump(mode="json"), case["expected_model_json"], {}
            )
        )
        passed = passed and factory_proof
    else:
        passed = (
            passed
            and descriptor.default_factory is None
            and contexts.matches(descriptor.default, case["expected_field"], {})
        )
    return {
        "case_id": case["case_id"],
        "status": "PASS" if passed else "FAIL",
        "root_json_validation_entries": len(observed),
        "input_field_absent": field not in case["input"],
        "model_fields_set": sorted(model.model_fields_set),
        "whole_model_json_matches": contexts.matches(
            model.model_dump(mode="json"), case["expected_model_json"], {}
        ),
        "actual_attribute_matches": field_matches(getattr(model, field), case),
        "independent_factory_proof": factory_proof,
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
                    "planned_new_ids": 12,
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
        "Frozen default catalog differs",
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
    receipts = [execute(case) for case in catalog["cases"]]
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
            "schema": "equiframe.model-default-result.v1",
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
