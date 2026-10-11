"""Validate reviewed independent field variations against complete literal JSON.

The frozen review selection excludes model serializers, dynamic self access,
fields read by AFTER validators and unknown callbacks. Selected declarations
are constructor metadata; they establish no native engine or scientific result.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import importlib.util
import inspect
import json
import platform
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "option_method_followup", Path(__file__).with_name("option_method_followup.py")
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Method verifier unavailable")
method = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(method)
boundary, op = method.boundary, method.op
SELECTION = "cd1b80e5e05ce67dc8ac7fa6d699b8a1a1623301e6dba2404cca085e20f1dbd3"
METHOD_RESULT = "65ac2fb9e7804bc8aa9a49c8cea46d89564e8745a59c5cdf5f8a1ecf537c6978"
IDENTITY_CALLBACKS = {
    "equiframe._base._text",
    "equiframe._documents.canonical_text",
}


def prepare(selection, inventory, baseline, seeds, previous, ef):
    remaining = {
        row["id"]: row for row in baseline["rows"] if row["status"] == "NOT_RUN"
    }
    closed = {
        identifier for receipt in previous for identifier in receipt["obligations"]
    }
    fixtures = {
        name: copy.deepcopy(seed["input"]) for name, seed in seeds["seeds"].items()
    }
    fixtures.update(boundary.literal_seeds())
    literals = {
        case["model"]: copy.deepcopy(case["expected"])
        for case in seeds["cases"]
        if case["operation"] == "model"
    }
    literals.update(boundary.literal_seeds())
    fields = {
        field["id"]: field
        for record in inventory["exports"]
        if record["kind"] == "model" and not record["alias_of"]
        for field in record["fields"]
    }
    cases = []
    for row in selection["rows"]:
        identifier, name, key = row["id"], row["model"], row["field"]
        op.require(
            identifier in remaining and identifier not in closed,
            "Only pending IDs may be planned",
        )
        proof = row["dependency_proof"]
        op.require(
            proof["selected_field_is_not_read"]
            and key not in proof["fields_read_directly_or_transitively"]
            and not proof["whole_self_or_dynamic_access_detected"]
            and not proof["serializers_present"]
            and all(v["mode"] == "after" for v in proof["model_validators"]),
            "Cross-field or serializer variation requires another reviewed fixture",
        )
        model = getattr(ef, name)
        source = importlib.import_module(row["source"]["module"])
        op.require(
            op.digest(Path(source.__file__)) == row["source"]["sha256"],
            "Reviewed source differs",
        )
        for callback in proof["callbacks"]:
            qualified = callback["qualified_name"]
            op.require(qualified in IDENTITY_CALLBACKS, "Unreviewed callback")
            module_name, function_name = qualified.rsplit(".", 1)
            module = importlib.import_module(module_name)
            function = getattr(module, function_name)
            op.require(
                inspect.isfunction(function)
                and function.__module__ + "." + function.__name__ == qualified
                and op.digest(Path(module.__file__)) == callback["source_sha256"],
                "Exact reviewed callback source is required",
            )
        field_id = f"field:equiframe.{name}:{key}"
        declaration = fields[field_id]
        declared = model.model_fields[key]
        op.require(declaration["bounds"] == row["bounds"], "Declared bounds changed")
        input_data = copy.deepcopy(fixtures[name])
        expected_data = copy.deepcopy(literals[name])
        op.require(key in expected_data, "Missing complete field serialization oracle")
        if row["kind"] == "boundary":
            label = row["option_value_or_class"]
            number = declaration["continuous_classes"].index(label)
            op.require(
                identifier == field_id + f":class:{number}", "Boundary ID differs"
            )
            variation = boundary.boundary(
                declared.annotation, declaration["bounds"], label, input_data.get(key)
            )
            normalized = boundary.boundary(
                declared.annotation, declaration["bounds"], label, expected_data[key]
            )
            op.require(
                variation is not None and normalized is not None,
                "Unsupported declared shape",
            )
            value, admitted, code = variation
            op.require(admitted == normalized[1], "Admission oracles differ")
            expected_value = normalized[0]
        else:
            op.require(row["kind"] == "finite_or_null", "Unsupported selection")
            value = row["option_value_or_class"]
            suffix = json.dumps(
                value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
            )
            op.require(identifier == field_id + ":value:" + suffix, "Finite ID differs")
            op.require(
                any(
                    method.canonical(value) == method.canonical(v)
                    for v in declaration["finite_values"]
                ),
                "Value is not declared finite",
            )
            expected_value, admitted, code = value, True, None
        input_data[key] = copy.deepcopy(value)
        expected_data[key] = copy.deepcopy(expected_value)
        cases.append(
            {
                "case_id": "literal-field." + identifier,
                "model": name,
                "field": key,
                "input": input_data,
                "obligations": [identifier],
                "expected": {"admitted": True, "output": expected_data}
                if admitted
                else {"admitted": False, "field": key, "error_codes": [code]},
                "basis": row,
            }
        )
    return {
        "schema": "equiframe.option-literal-field-catalog.v1",
        "wheel_sha256": boundary.WHEEL,
        "baseline_sha256": boundary.BASELINE,
        "seed_catalog_sha256": boundary.SEEDS,
        "selection_sha256": SELECTION,
        "method_result_sha256": METHOD_RESULT,
        "obligation_ids_sha256": seeds["obligation_ids_sha256"],
        "cases": cases,
        "scope": "Independent reviewed constructor field variations with full literal JSON; no native, branch or scientific claims",
    }


def execute(case, ef):
    from pydantic import ValidationError

    expected = case["expected"]
    try:
        output = (
            getattr(ef, case["model"])
            .model_validate_json(method.canonical(case["input"]))
            .model_dump(mode="json")
        )
        observed = {"admitted": True, "output": output}
        matched = method.canonical(observed) == method.canonical(expected)
        status = "PASS" if matched else "FAIL"
    except ValidationError as error:
        errors = [{"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()]
        observed = {"admitted": False, "errors": errors}
        matched = (
            expected["admitted"] is False
            and bool(errors)
            and all(
                e["loc"]
                and e["loc"][0] == expected["field"]
                and e["type"] in expected["error_codes"]
                for e in errors
            )
        )
        status = "EXPECTED_REJECTION" if matched else "FAIL"
    except Exception as error:  # noqa: BLE001 - unexpected errors remain FAIL
        observed, status = {"unexpected_exception": type(error).__name__}, "FAIL"
    return {**case, "observed": observed, "status": status}


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
        "methods-result",
        "selection",
        "catalog",
        "output",
    ):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    baseline, inventory, seeds, previous = method.inputs(args)
    op.require(
        op.digest(args.selection) == SELECTION, "Frozen review selection differs"
    )
    op.require(op.digest(args.methods_result) == METHOD_RESULT, "Method result differs")
    previous.extend(op.read(args.methods_result)["receipts"])
    op.require(
        boundary.aggregate(baseline, previous, [])["verified"] == 5613,
        "Prior union changed",
    )
    import equiframe as ef

    package = op.identity(
        args.wheel, boundary.WHEEL, Path(__file__).resolve().parents[1]
    )
    catalog = prepare(op.read(args.selection), inventory, baseline, seeds, previous, ef)
    boundary.aggregate(
        baseline, previous, [{**c, "status": "PASS"} for c in catalog["cases"]]
    )
    if args.mode == "plan":
        boundary.write(args.catalog, catalog)
        print(
            method.canonical(
                {
                    "planned_cases": len(catalog["cases"]),
                    "planned_obligations": len(catalog["cases"]),
                    "catalog_sha256": op.digest(args.catalog),
                    "executed": False,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256
        and op.digest(args.catalog) == args.catalog_sha256
        and method.canonical(op.read(args.catalog)) == method.canonical(catalog),
        "Frozen execution catalog differs",
    )
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = [execute(case, ef) for case in catalog["cases"]]
    summary = boundary.aggregate(baseline, previous, receipts)
    result = {
        "schema": "equiframe.option-literal-field-result.v1",
        "candidate": "0.12.0a13",
        "package": package,
        "catalog_sha256": args.catalog_sha256,
        "tool_sha256": op.digest(Path(__file__)),
        "input_sha256": {
            key: op.digest(getattr(args, key))
            for key in (
                "baseline",
                "inventory",
                "seed_catalog",
                "operations",
                "boundary_result",
                "methods_result",
                "selection",
            )
        },
        "dependencies": {
            "method_tool_sha256": op.digest(Path(method.__file__)),
            "boundary_tool_sha256": op.digest(Path(boundary.__file__)),
            "operations_tool_sha256": op.digest(Path(op.__file__)),
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
        method.canonical(
            {k: v for k, v in summary.items() if k != "linked_obligations"}
        )
    )
    return 1 if summary["case_counts"].get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
