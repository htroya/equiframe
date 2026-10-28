"""Bind existing semantic-support declarations to exact recorded test executions.

Rows without matching observations remain NOT_RUN. No fuzzy name matching,
historical execution label, skipped test or absent oracle becomes a current pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def canonical_node(nodeid: str) -> str:
    """Remove only an exact package-root prefix, preserving parameter identities."""
    marker = "tests/"
    index = nodeid.find(marker)
    return nodeid[index:] if index >= 0 else nodeid


def bind(register: dict[str, Any], receipt: dict[str, Any], log: str) -> dict[str, Any]:
    observations = {canonical_node(case["nodeid"]): case for case in receipt["cases"]}
    rows = []
    for declaration in register["rows"]:
        declared_node = declaration.get("pytest_node")
        matches = []
        if declared_node:
            requested = canonical_node(declared_node)
            matches = [
                case
                for name, case in observations.items()
                if name == requested or ("[" not in requested and name.startswith(requested + "["))
            ]
        expected = declaration.get("expected")
        status = (
            "FAIL"
            if any(case["status"] == "FAIL" for case in matches)
            else "NOT_RUN"
            if not matches or any(case["status"] != "PASS" for case in matches)
            else "EXPECTED_REJECTION"
            if declaration["status"] == "rejected"
            else "PASS"
        )
        semantic_key = {
            key: declaration.get(key)
            for key in (
                "category",
                "operation",
                "type",
                "engine",
                "direction",
                "policy",
                "pytest_node",
            )
        }
        identifier = hashlib.sha256(json.dumps(semantic_key, sort_keys=True).encode()).hexdigest()[
            :20
        ]
        rows.append(
            {
                "id": "semantic:" + identifier,
                "api_cli": declaration["operation"],
                "option_value_or_class": declaration["type"],
                "preconditions": declaration.get("conditions", ""),
                "engine": declaration["engine"],
                "direction": declaration["direction"],
                "format": declaration.get("stage", "declared source fixture"),
                "policy": declaration["policy"],
                "independent_expected": expected,
                "expectation_source": (
                    "Existing SEMANTIC_SUPPORT test declaration; "
                    "inspect its test for literal oracle"
                ),
                "test_program": declared_node,
                "observed": [
                    {"nodeid": case["nodeid"], "status": case["status"]} for case in matches
                ],
                "status": status,
                "log": log,
                "environment": receipt["environment"],
                "commit": receipt["commit"],
                "wheel_sha256": receipt["wheel"]["sha256"],
                "historical_execution": declaration.get("execution"),
            }
        )
    return {
        "schema_version": "equiframe.semantic-executions/1.0",
        "rows": rows,
        "denominators": {
            "declaration_rows": len(rows),
            "execution_statuses": dict(Counter(row["status"] for row in rows)),
            "distinct_tests_in_receipt": len(receipt["cases"]),
            "distinct_matched_test_nodes": len(
                {case["nodeid"] for row in rows for case in row["observed"]}
            ),
        },
        "scope": (
            "Extends the existing semantic-support register with one exact candidate/environment; "
            "repeated declaration rows are not independent tests or exhaustive option coverage"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not arguments.log.is_file():
        raise FileNotFoundError(arguments.log)
    register = json.loads(arguments.register.read_text("utf-8"))
    receipt = json.loads(arguments.receipt.read_text("utf-8"))
    result = bind(register, receipt, str(arguments.log))
    result["input_hashes"] = {
        "register": hashlib.sha256(arguments.register.read_bytes()).hexdigest(),
        "receipt": hashlib.sha256(arguments.receipt.read_bytes()).hexdigest(),
        "log": hashlib.sha256(arguments.log.read_bytes()).hexdigest(),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result["denominators"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
