"""Link exact pending boundaries to complete, original A13 literal fixtures.

This establishes constructor admission and serialization. Twenty-two existing
fixtures carry forty-two new assertions; they are not new independent inputs.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import platform
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "option_public_types_followup",
    Path(__file__).with_name("option_public_types_followup.py"),
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Prior verifier unavailable")
types = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(types)
boundary, op = types.boundary, types.op
PUBLIC_RESULT = "bcbe5ef7c0ebcf8e0b78fb08157e75ca5d988db5423affec524e6b92b2873a5c"
INVENTORY = "556a3534dcc204c16742fe30ca32843438cb46782e91bb566054a2a0d32014d3"
HELPER_HASHES = {
    "option_public_types_followup.py": "020141dfc629c9286741e3909f24c99c862fd570b9505aec8f409955170045d7",
    "option_boundary_followup.py": "56822972540c405a1a5c05315575d4b87b21e5919ee0910747c9680564ed1bff",
    "option_operations.py": "56663cd649fd0be9234f274ffa828d7714c2e546b870fa678c9bdd919e448e60",
}
# Reviewed against the original literal catalog before any execution.
LOWERS = {
    "CheckResult": ("violation_count:2",),
    "ColumnKeyScope": ("columns:2",),
    "Contract": ("inputs:2",),
    "Deduplicate": ("node_id:2", "source:2", "keys:6"),
    "DetectorModel": ("deviations:2",),
    "FeatureObservation": ("numerator:2", "denominator:2"),
    "FeatureSupport": (
        "rows:2",
        "missing:2",
        "nan:2",
        "empty_strings:2",
        "zeros:2",
        "incomplete_keys:2",
    ),
    "FieldMapping": ("path:2",),
    "IngestionResult": ("accepted_records:2",),
    "JoinCheck": ("left_columns:2", "right_columns:2"),
    "KeySpec": ("columns:2",),
    "NullPolicy": ("representations:2",),
    "OrderCheck": ("columns:2",),
    "ProfileFeature": ("columns:2",),
    "ProfileSpec": ("features:2",),
    "ReducedTable": ("retained_positions:2",),
    "ReportEvidenceManifest": ("available_records:2", "included_examples:2"),
    "SignificantOrder": ("by:2",),
    "SnapshotManifest": ("provenance:2", "tables:2"),
    "SnapshotTable": ("columns:2",),
    "WindowMeasure": ("column:2", "offset:2"),
}
MEMBERS = {
    "EngineCapabilities": {
        "timestamp_units": ("s", "ms", "us", "ns"),
        "zoned_timestamp_units": ("s", "ms", "us", "ns"),
    },
    "NullPolicy": {"representations": ("null",)},
}


def lower_proof(value, declaration, index):
    label = declaration["continuous_classes"][index]
    boundary_label = (
        label.split(" ", 1)[1] if label.startswith(("member:", "union:")) else label
    )
    op.require(
        boundary_label == "declared lower boundary",
        "Selection is not an exact lower boundary",
    )
    limits = declaration["bounds"]
    values = [value]
    if label.startswith(("member:", "union:")):
        prefix = label.split(" ", 1)[0]
        branches = [branch for branch in limits["branches"] if branch["path"] == prefix]
        op.require(len(branches) == 1, "Boundary branch differs")
        limits = branches[0]["bounds"]
        if prefix.startswith("member:"):
            op.require(
                prefix == "member:0" and isinstance(value, list),
                "Unsupported typed collection slot",
            )
            values = value
    if "min_length" in limits:
        matched = any(
            isinstance(item, (str, list, dict)) and len(item) == limits["min_length"]
            for item in values
        )
    elif "ge" in limits:
        matched = any(
            type(item) in (int, float) and item == limits["ge"] for item in values
        )
    else:
        matched = False
    op.require(matched, "Original literal does not exercise the declared boundary")
    return {"label": label, "limits": limits, "literal": value}


def prepare(seeds, inventory, baseline, previous):
    closed = {row["id"] for row in baseline["rows"] if row["status"] != "NOT_RUN"}
    closed.update(
        identifier for receipt in previous for identifier in receipt["obligations"]
    )
    pending = {row["id"] for row in baseline["rows"]} - closed
    declarations = {
        row["name"].split(".")[-1]: row
        for row in inventory["exports"]
        if row["kind"] == "model" and not row["alias_of"]
    }
    original = {case["id"]: case for case in seeds["cases"]}
    cases = []
    for model in sorted(set(LOWERS) | set(MEMBERS)):
        fixture = original[model + ".construction"]
        input_data = copy.deepcopy(seeds["seeds"][model]["input"])
        expected = copy.deepcopy(fixture["expected"])
        fields = {
            row["id"].split(":")[-1]: row for row in declarations[model]["fields"]
        }
        links, proofs = [], []
        for selected in LOWERS.get(model, ()):
            field, number = selected.split(":")
            identifier = f"field:equiframe.{model}:{field}:class:{number}"
            op.require(identifier in pending, "Selection is not pending")
            op.require(
                types.canonical(input_data[field]) == types.canonical(expected[field]),
                "Original input/output literal differs",
            )
            proof = lower_proof(expected[field], fields[field], int(number))
            links.append(identifier)
            proofs.append({"id": identifier, **proof})
        for field, values in MEMBERS.get(model, {}).items():
            declaration = fields[field]
            for value in values:
                identifier = (
                    f"field:equiframe.{model}:{field}:member:0:"
                    + types.canonical(value)
                )
                op.require(
                    identifier in pending
                    and value in input_data[field]
                    and value in expected[field],
                    "Member is not an explicit pending literal",
                )
                op.require(
                    any(
                        v["member_index"] == 0 and value in v["values"]
                        for v in declaration["collection_member_values"]
                    ),
                    "Typed collection member differs",
                )
                links.append(identifier)
                proofs.append(
                    {
                        "id": identifier,
                        "literal": value,
                        "slot": "member:0",
                        "runtime_position_not_fixed": True,
                    }
                )
        cases.append(
            {
                "case_id": "seed-boundaries." + model,
                "original_fixture_case_id": fixture["id"],
                "model": model,
                "input": input_data,
                "expected": expected,
                "obligations": links,
                "proofs": proofs,
            }
        )
    op.require(
        len(cases) == 22 and sum(len(c["obligations"]) for c in cases) == 42,
        "Frozen selection cardinality differs",
    )
    return {
        "schema": "equiframe.seed-boundaries-catalog.v1",
        "wheel_sha256": boundary.WHEEL,
        "baseline_sha256": boundary.BASELINE,
        "seed_catalog_sha256": boundary.SEEDS,
        "inventory_sha256": INVENTORY,
        "cases": cases,
        "scope": "Full literal constructor JSON and exact selected boundaries; existing fixtures, no native behavior or scientific claims",
    }


def execute(case, ef):
    try:
        observed = (
            getattr(ef, case["model"])
            .model_validate_json(types.canonical(case["input"]))
            .model_dump(mode="json")
        )
        status = (
            "PASS"
            if types.canonical(observed) == types.canonical(case["expected"])
            else "FAIL"
        )
    except Exception as error:  # noqa: BLE001 - unexpected errors must remain failures
        observed, status = {"unexpected_exception": type(error).__name__}, "FAIL"
    return {**case, "observed": observed, "status": status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in (
        "wheel",
        "baseline",
        "seed-catalog",
        "inventory",
        "public-result",
        "catalog",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prior-result", type=Path, action="append", required=True)
    parser.add_argument("--prior-sha256", action="append", required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    helper_hashes = {
        name: op.digest(Path(__file__).with_name(name)) for name in HELPER_HASHES
    }
    op.require(helper_hashes == HELPER_HASHES, "Loaded verifier helper source differs")
    baseline, previous, prior_hashes = types.load_inputs(args)
    op.require(
        op.digest(args.public_result) == PUBLIC_RESULT
        and op.digest(args.seed_catalog) == boundary.SEEDS
        and op.digest(args.inventory) == INVENTORY,
        "Frozen input identity differs",
    )
    previous.extend(op.read(args.public_result)["receipts"])
    op.require(
        boundary.aggregate(baseline, previous, [])["verified"] == 5860,
        "Prior union differs",
    )
    package = op.identity(
        args.wheel, boundary.WHEEL, Path(__file__).resolve().parents[1]
    )
    catalog = prepare(
        op.read(args.seed_catalog), op.read(args.inventory), baseline, previous
    )
    if args.mode == "plan":
        boundary.write(args.catalog, catalog)
        print(
            types.canonical(
                {
                    "cases": 22,
                    "planned_obligations": 42,
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
        "Frozen execution catalog differs",
    )
    import equiframe as ef

    receipts = [execute(case, ef) for case in catalog["cases"]]
    args.output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": "equiframe.seed-boundaries-result.v1",
        "package": package,
        "tool_sha256": op.digest(Path(__file__)),
        "helper_source_sha256": helper_hashes,
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "optimization": sys.flags.optimize,
        },
        "catalog_sha256": args.catalog_sha256,
        "prior_result_sha256": prior_hashes + [PUBLIC_RESULT],
        "receipts": receipts,
        "summary": boundary.aggregate(baseline, previous, receipts),
        "new_independent_input_fixtures": 0,
        "reused_original_fixtures": 22,
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
