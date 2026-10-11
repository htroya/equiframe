"""Run reviewed synthetic option cases against an identified installed core wheel.

Metadata construction receipts do not establish downstream engine behavior.
The catalog is trusted, reviewable test data, not executable plugins or Python.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


def read_json(path: Path) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON member: {key}")
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError(f"Nonfinite JSON token: {value}")

    return json.loads(path.read_text("utf-8"), object_pairs_hook=unique, parse_constant=reject)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def same(left: Any, right: Any) -> bool:
    # JSON identity distinguishes True from 1 and None from a missing member.
    return digest(left) == digest(right)


def validate_catalog(catalog: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if catalog.get("schema_version") != "equiframe.option-cases/1.0":
        raise ValueError("Unsupported case catalog schema")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids) or catalog["obligation_ids_sha256"] != digest(sorted(ids)):
        raise ValueError("Obligation denominator differs from frozen catalog")
    index = {r["id"]: r for r in rows}
    cases: set[str] = set()
    for case in catalog["cases"]:
        if case["id"] in cases or not case.get("basis") or not case["obligations"]:
            raise ValueError("Duplicate, ungrounded or unlinked case")
        cases.add(case["id"])
        if case["model"] not in catalog["seeds"]:
            raise ValueError("Missing synthetic seed")
        prefix = "field:equiframe." + case["model"] + ":" + case.get("field", "")
        operation = case["operation"]
        for identifier in case["obligations"]:
            if identifier not in index:
                raise ValueError("Unknown obligation: " + identifier)
            row = index[identifier]
            valid = False
            if operation == "model":
                valid = identifier == "api:equiframe." + case["model"]
            elif identifier.startswith(prefix + ":"):
                suffix = identifier[len(prefix) + 1 :]
                if operation == "required_omission":
                    valid = suffix == "required_omission"
                elif operation == "default":
                    valid = suffix == "default" and same(case["expected"], row["default"])
                elif operation == "invalid":
                    valid = suffix == "invalid" or (
                        suffix.startswith("class:")
                        and row["option_value_or_class"] == "wrong Python/JSON type"
                    )
                elif operation == "field_value":
                    valid = (
                        suffix.startswith("value:")
                        and same(case["expected"], row["option_value_or_class"])
                    ) or (
                        suffix.startswith("class:")
                        and row["option_value_or_class"] == "admitted representative"
                    )
            if not valid:
                raise ValueError(f"Case {case['id']} cannot prove {identifier}")
        if operation not in {"model", "field_value", "default", "invalid", "required_omission"}:
            raise ValueError("Unknown case operation")


def execute_case(case: dict[str, Any], seeds: dict[str, Any], module: Any) -> dict[str, Any]:
    model = getattr(module, case["model"], None)
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise ValueError("Case target must be a declared core model")
    if case["model"] not in module.__all__:
        raise ValueError("Case target must be a public core export")
    data = copy.deepcopy(seeds[case["model"]]["input"])
    field: Any = case.get("field")
    operation = case["operation"]
    if operation in {"default", "required_omission"}:
        data.pop(field, None)
    elif "value" in case:
        data[field] = case["value"]
    rejection = operation in {"invalid", "required_omission"}
    try:
        output = model.model_validate_json(json.dumps(data, allow_nan=False)).model_dump(
            mode="json"
        )
        observed: Any = (
            output
            if operation == "model"
            else {"present": field in output, "value": output.get(field)}
        )
        expected = case["expected"]
        matched = not rejection and (
            same(observed, expected)
            if operation == "model"
            else observed["present"] and same(observed["value"], expected)
        )
        status = "PASS" if matched else "FAIL"
    except ValidationError as error:
        observed = [{"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()]
        expected = case["expected"]
        matched = rejection and any(
            e["loc"] and e["loc"][0] == field and e["type"] in expected["error_codes"]
            for e in observed
        )
        status = "EXPECTED_REJECTION" if matched else "FAIL"
    except Exception as error:
        # A programming/I/O error is never relabeled as an expected input rejection.
        observed = {"unexpected_exception": type(error).__name__}
        expected = case["expected"]
        status = "FAIL"
    return {
        "case_id": case["id"],
        "obligations": case["obligations"],
        "status": status,
        "independent_expected": expected,
        "observed": observed,
        "basis": case["basis"],
        "input_sha256": digest(data),
        "scope": "metadata construction/serialization/rejection",
    }


def aggregate(rows: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, list[dict[str, Any]]] = {r["id"]: [] for r in rows}
    seen: set[str] = set()
    for receipt in receipts:
        if receipt["case_id"] in seen:
            raise ValueError("Duplicate execution receipt")
        seen.add(receipt["case_id"])
        if receipt["status"] not in {"PASS", "EXPECTED_REJECTION", "FAIL"}:
            raise ValueError("Invalid execution status")
        for identifier in receipt["obligations"]:
            if identifier not in by_id:
                raise ValueError("Receipt references unknown obligation")
            by_id[identifier].append(receipt)
    result = []
    for row in rows:
        matches = by_id[row["id"]]
        statuses = {r["status"] for r in matches}
        status = (
            "FAIL"
            if "FAIL" in statuses
            else (
                "PASS"
                if "PASS" in statuses
                else ("EXPECTED_REJECTION" if "EXPECTED_REJECTION" in statuses else "NOT_RUN")
            )
        )
        result.append(
            {"id": row["id"], "status": status, "case_ids": [r["case_id"] for r in matches]}
        )
    counts = dict(Counter(r["status"] for r in result))
    verified = counts.get("PASS", 0) + counts.get("EXPECTED_REJECTION", 0)
    return {
        "rows": result,
        "counts": counts,
        "total": len(rows),
        "verified": verified,
        "percent": 100 * verified / len(rows) if rows else None,
        "unique_cases": len(seen),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory", "matrix", "catalog", "wheel", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--minimum-percent", type=float, default=50)
    args = parser.parse_args()
    if not 0 <= args.minimum_percent <= 100:
        parser.error("minimum percent must be between 0 and 100")
    if args.output.exists():
        parser.error("Output directory already exists; preserve the previous run")
    args.output.mkdir(parents=True, exist_ok=False)
    inventory = read_json(args.inventory)
    matrix = read_json(args.matrix)
    catalog = read_json(args.catalog)
    wheel_sha = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    if wheel_sha != inventory["wheel_sha256"] or wheel_sha != catalog["wheel_sha256"]:
        raise ValueError("Candidate wheel identity mismatch")
    if inventory["commit"] != catalog["source_commit"]:
        raise ValueError("Candidate source identity mismatch")
    spec = importlib.util.spec_from_file_location(
        "option_inventory", Path(__file__).with_name("option_inventory.py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("Inventory tool unavailable")
    discovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discovery)
    import equiframe as ef

    identity = discovery.installed_identity(ef, "equiframe", args.wheel)
    fresh = {
        **inventory,
        "exports": discovery.inspect_exports(ef, {}),
        "cli": discovery.inspect_cli("equiframe.cli", "equiframe"),
        "distributions": [identity],
    }
    fresh_rows = discovery.obligations(fresh)
    if sorted(r["id"] for r in fresh_rows) != sorted(r["id"] for r in matrix["rows"]):
        raise ValueError("Current installed inventory differs from supplied matrix")
    if any(r["status"] != "NOT_RUN" for r in matrix["rows"]):
        raise ValueError("Input discovery matrix must contain only NOT_RUN obligations")
    validate_catalog(catalog, fresh_rows)
    receipts = [execute_case(c, catalog["seeds"], ef) for c in catalog["cases"]]
    result = aggregate(fresh_rows, receipts)
    result.update(
        {
            "schema_version": "equiframe.option-trace/1.0",
            "wheel_sha256": wheel_sha,
            "source_commit": inventory["commit"],
            "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
            "obligation_ids_sha256": catalog["obligation_ids_sha256"],
            "tool_sha256": {
                name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("option_trace.py", "option_inventory.py")
            },
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
                "machine": platform.machine(),
                "executable": sys.executable,
                "dependencies": dict(
                    sorted(
                        (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
                    )
                ),
                "installed": identity,
            },
            "case_counts": dict(Counter(r["status"] for r in receipts)),
            "scope": (
                "Core inventory only; metadata receipts do not prove "
                "native execution or interactions"
            ),
        }
    )
    result["surface_counts"] = {
        surface: dict(
            Counter(r["status"] for r in result["rows"] if r["id"].split(":")[0] == surface)
        )
        for surface in sorted({r["id"].split(":")[0] for r in result["rows"]})
    }
    for name, document in (("receipts.json", receipts), ("result.json", result)):
        with (args.output / name).open("x", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("total", "verified", "percent", "counts", "case_counts", "unique_cases")
            }
        )
    )
    return (
        0 if not result["counts"].get("FAIL") and result["percent"] >= args.minimum_percent else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
