"""Read public getters against frozen literal metadata and state transitions.

No getter reading proves native execution, scientific independence, or CLI
exit-code binding. Existing complex result fixtures remain synthetic metadata.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import inspect
import platform
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "configuration_followup",
    Path(__file__).with_name("option_configuration_followup.py"),
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Prior verifier unavailable")
configuration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configuration)
seed, types, boundary, op = (
    configuration.seed,
    configuration.types,
    configuration.boundary,
    configuration.op,
)
CONFIGURATION_TOOL = "6f1209899f8b2e73e79ac30a799a5b70780bc14995889658e6857f1ce410efba"
CONFIGURATION_RESULT = (
    "d22dfc865013ed0cfe50093353e965e3f3967cea82ca2a6ea7f50fbf7570546c"
)
SOURCE_HASHES = {
    "execution.py": "78a2fa928ac88cde64a5ca2c838d68e745e81c5d47c4a2237dc8bae41043175a",
    "values.py": "5cc0a70e42422e150b81827ca81db3a9805cb2c2a2f0a883d2c8c99ddd324219",
    "verify_types.py": "82da0cabf1afbe29b729e2061c628d28adb6cfb1cc04244a4993c8bc49357959",
    "profile_types.py": "9b8794c3f96130b3b0863c2f547c5840f9720f86af9a5c2c5338d91d39fd7b91",
    "pipeline_types.py": "ba4961094863e697e4024df64fbb8760a97af69ba3a044a116a1c5d2b04de100",
    "workflow.py": "87db4cd42aaacd12b8650bb0ebebf30f20a4e173024140c27a107e65bdca422e",
    "detector_types.py": "55d7be9a48f23ddaf9034a0769665ebd520787dc29344fc1c8d8b46e0dd5b903",
    "migration/runner_types.py": "37528529dd12be5405abdb935cdad6eba6281c05fac8f80d60223f387a200481",
}
# Explicit expectations reviewed before SDK execution. No exit_code ID is used:
# the original inventory requires documented interface binding for those IDs.
GETTERS = {
    "ExpectedProvenance": {"independently_constructed": (True, "bool")},
    "TimestampValue": {"has_offset": (True, "bool"), "fractional_digits": (0, "int")},
    "PreprocessorBundle": {
        "columns": (
            ["null_rate", "null_rate.undefined", "null_rate.not_applicable"],
            "tuple",
        )
    },
    "MigrationResult": {
        "complete": (True, "bool"),
        "state": ("equivalent", "str"),
        "verification": ("correct", "str"),
    },
    "PipelineResult": {"complete": (True, "bool")},
    "VerificationResult": {
        "operational_state": ("passed", "str"),
        "publishable": (True, "bool"),
    },
    "WorkflowResult": {"complete": (True, "bool")},
}


def prepare(catalog, inventory, baseline, previous):
    done = {r["id"] for r in baseline["rows"] if r["status"] != "NOT_RUN"}
    done.update(i for r in previous for i in r["obligations"])
    pending = {r["id"] for r in baseline["rows"]} - done
    declarations = {
        p["id"]: p
        for e in inventory["exports"]
        if not e["alias_of"]
        for p in e.get("properties", [])
    }
    original = {r["id"]: r for r in catalog["cases"]}
    cases = []

    def add(model, suffix, input_data, expected_json, getters, operation="model"):
        checks, links = [], []
        for name, (expected, python_type) in getters.items():
            identifier = f"property:equiframe.{model}.{name}"
            declaration = declarations[identifier]
            candidates = [identifier]
            if declaration["finite_values"]:
                op.require(
                    any(
                        types.canonical(v) == types.canonical(expected)
                        for v in declaration["finite_values"]
                    ),
                    "Expected property alternative is undeclared",
                )
                candidates.append(identifier + ":value:" + types.canonical(expected))
            else:
                op.require(
                    declaration["output_classes"][0] == "valid declared output"
                    and not declaration["documented_exit_codes_require_binding"],
                    "Getter needs a separately reviewed interface proof",
                )
                candidates.append(identifier + ":class:0")
            selected = [i for i in candidates if i in pending]
            pending.difference_update(selected)
            links.extend(selected)
            checks.append(
                {"name": name, "expected": expected, "python_type": python_type}
            )
        cases.append(
            {
                "case_id": f"properties.{model}.{suffix}",
                "model": model,
                "operation": operation,
                "input": copy.deepcopy(input_data),
                "expected_json": copy.deepcopy(expected_json),
                "checks": checks,
                "obligations": links,
                "basis": "Frozen literal metadata and reviewed public getter contract; no native execution or human attestation",
            }
        )

    for model, getters in GETTERS.items():
        fixture = original[model + ".construction"]
        input_data = catalog["seeds"][model]["input"]
        expected_json = fixture["expected"]
        if model == "WorkflowResult":
            # Copy literal output artifacts from the original independent JSON
            # oracle, never by reading WorkflowResult.outputs during planning.
            getters = dict(getters)
            getters["outputs"] = (
                {
                    c["stage_id"]: c["migration"]["target"]["execution"]["output"][
                        "data"
                    ]
                    for c in expected_json["checkpoints"]
                },
                "dict",
            )
        add(model, "original", input_data, expected_json, getters)
    provenance = catalog["seeds"]["ExpectedProvenance"]["input"]
    for suffix, change in (
        ("not_declared", {"independence_declared": False}),
        ("overlapping_author", {"implementation_authors": ["expected_author"]}),
        ("engine_derived", {"derived_from_engines": ["pandas"]}),
    ):
        input_data = {**copy.deepcopy(provenance), **change}
        add(
            "ExpectedProvenance",
            suffix,
            input_data,
            input_data,
            {"independently_constructed": (False, "bool")},
        )
    for suffix, value, has_offset, digits in (
        ("naive_fraction", "2025-01-01T00:00:00.123", False, 3),
        ("utc_nanosecond", "2025-01-01T00:00:00.123456789Z", True, 9),
    ):
        input_data = {"kind": "timestamp", "value": value, "zone": None}
        add(
            "TimestampValue",
            suffix,
            input_data,
            input_data,
            {"has_offset": (has_offset, "bool"), "fractional_digits": (digits, "int")},
        )
    component = boundary.literal_seeds()["ComponentDetectionResult"]
    add(
        "ComponentDetectionResult",
        "complete",
        component,
        component,
        {"complete": (True, "bool")},
    )
    component = copy.deepcopy(component)
    component["decisions"][0]["result"] = {
        "decision": "not_evaluable",
        "complete": False,
        "reason": "Synthetic unavailable calibration",
    }
    component["decisions"][0]["threshold"] = None
    add(
        "ComponentDetectionResult",
        "incomplete",
        component,
        component,
        {"complete": (False, "bool")},
    )
    for cancelled in (False, True):
        add(
            "CancellationToken",
            "cancelled" if cancelled else "initial",
            cancelled,
            None,
            {"cancelled": (cancelled, "bool")},
            "cancellation",
        )
    op.require(
        len(cases) == 16 and sum(len(c["obligations"]) for c in cases) == 32,
        "Frozen property selection cardinality differs",
    )
    return {
        "schema": "equiframe.public-properties-catalog.v1",
        "wheel_sha256": boundary.WHEEL,
        "seed_catalog_sha256": boundary.SEEDS,
        "inventory_sha256": seed.INVENTORY,
        "reviewed_source_sha256": SOURCE_HASHES,
        "cases": cases,
        "scope": "Exact getter values/types, whole literal model JSON, and cancellation state; no protocol stubs, unavailable output classes, exit-code binding, native execution or scientific acceptance",
    }


def observed_property(instance, check):
    descriptor = inspect.getattr_static(type(instance), check["name"])
    op.require(isinstance(descriptor, property), "Selected attribute is not a getter")
    value = getattr(instance, check["name"])
    declared_type = {
        "bool": bool,
        "int": int,
        "str": str,
        "tuple": tuple,
        "dict": dict,
    }[check["python_type"]]
    op.require(type(value) is declared_type, "Getter Python type differs")
    if isinstance(value, dict):
        value = {
            k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
            for k, v in value.items()
        }
    return value


def execute(case, ef):
    try:
        if case["operation"] == "cancellation":
            instance = ef.CancellationToken()
            initial = instance.cancelled
            op.require(
                type(initial) is bool and initial is False,
                "Fresh cancellation token differs",
            )
            if case["input"]:
                instance.cancel()
            construction = None
        else:
            instance = getattr(ef, case["model"]).model_validate_json(
                types.canonical(case["input"])
            )
            construction = instance.model_dump(mode="json")
            op.require(
                types.canonical(construction) == types.canonical(case["expected_json"]),
                "Full constructor JSON differs before getter readings",
            )
        observed = {c["name"]: observed_property(instance, c) for c in case["checks"]}
        expected = {c["name"]: c["expected"] for c in case["checks"]}
        status = (
            "PASS" if types.canonical(observed) == types.canonical(expected) else "FAIL"
        )
    except Exception as error:  # noqa: BLE001 - no unexpected error receives credit
        construction, observed, status = (
            None,
            {"unexpected_exception": type(error).__name__, "message": str(error)},
            "FAIL",
        )
    return {
        **case,
        "observed_json": construction,
        "observed": observed,
        "status": status,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in (
        "wheel",
        "baseline",
        "seed-catalog",
        "inventory",
        "public-result",
        "seed-result",
        "configuration-result",
        "catalog",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prior-result", action="append", type=Path, required=True)
    parser.add_argument("--prior-sha256", action="append", required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    baseline, previous, prior_hashes = types.load_inputs(args)
    op.require(
        op.digest(Path(__file__).with_name("option_configuration_followup.py"))
        == CONFIGURATION_TOOL,
        "Configuration verifier differs",
    )
    op.require(
        {n: op.digest(Path(__file__).with_name(n)) for n in seed.HELPER_HASHES}
        == seed.HELPER_HASHES,
        "Loaded helper differs",
    )
    op.require(
        op.digest(Path(__file__).with_name("option_seed_bounds_followup.py"))
        == configuration.SEED_TOOL,
        "Seed verifier differs",
    )
    for path, pin in (
        (args.public_result, seed.PUBLIC_RESULT),
        (args.seed_result, configuration.SEED_RESULT),
        (args.configuration_result, CONFIGURATION_RESULT),
    ):
        op.require(op.digest(path) == pin, "Prior receipt differs")
        previous.extend(op.read(path)["receipts"])
        prior_hashes.append(pin)
    op.require(
        boundary.aggregate(baseline, previous, [])["verified"] == 5942,
        "Prior union differs",
    )
    op.require(
        op.digest(args.seed_catalog) == boundary.SEEDS
        and op.digest(args.inventory) == seed.INVENTORY,
        "Frozen fixture/inventory differs",
    )
    package = op.identity(
        args.wheel, boundary.WHEEL, Path(__file__).resolve().parents[1]
    )
    import equiframe as ef

    package_root = Path(ef.__file__).resolve().parent
    op.require(
        {n: op.digest(package_root / n) for n in SOURCE_HASHES} == SOURCE_HASHES,
        "Reviewed getter sources differ",
    )
    catalog = prepare(
        op.read(args.seed_catalog), op.read(args.inventory), baseline, previous
    )
    if args.mode == "plan":
        boundary.write(args.catalog, catalog)
        print(
            types.canonical(
                {
                    "cases": 16,
                    "planned_obligations": 32,
                    "catalog_sha256": op.digest(args.catalog),
                    "executed": False,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256
        and op.digest(args.catalog) == args.catalog_sha256
        and types.canonical(op.read(args.catalog)) == types.canonical(catalog),
        "Frozen catalog differs",
    )
    receipts = [execute(c, ef) for c in catalog["cases"]]
    args.output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": "equiframe.public-properties-result.v1",
        "package": package,
        "tool_sha256": op.digest(Path(__file__)),
        "catalog_sha256": args.catalog_sha256,
        "prior_result_sha256": prior_hashes,
        "reviewed_source_sha256": SOURCE_HASHES,
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "optimization": sys.flags.optimize,
        },
        "receipts": receipts,
        "summary": boundary.aggregate(baseline, previous, receipts),
        "scope": catalog["scope"],
        "all_expected_results": all(r["status"] == "PASS" for r in receipts),
    }
    boundary.write(args.output / "result.json", result)
    print(
        types.canonical(
            {
                "all_expected_results": result["all_expected_results"],
                "verified": result["summary"]["verified"],
                "percent": result["summary"]["percent"],
                "result_sha256": op.digest(args.output / "result.json"),
            }
        )
    )
    return 0 if result["all_expected_results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
