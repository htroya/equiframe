"""Execute contract factories against authored expectations and pending IDs.

The plan is frozen before execution. It checks declared schema, policies and
provenance; it does not infer native execution or scientific acceptance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import equiframe as ef
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
POLICY = {
    "column_order": "significant",
    "physical_types": "exact",
    "index": "reject",
    "justification": None,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def base_expected(owner):
    return {
        "class": "DiffContract",
        "columns": [
            {
                "name": "id",
                "kind": "integer",
                "bits": 64,
                "signed": True,
                "nullable": False,
                "unit": "count",
            }
        ],
        "same_input_schema": True,
        "input_name": "source",
        "output_name": "result",
        "family": "nulls_types",
        "rules": 0,
        "preconditions": 0,
        "multiplicity": "preserve",
        "reference": "expected",
        "contract_id": "diff",
        "revision": 1,
        "policy": copy.deepcopy(POLICY),
        "keys": [{"columns": ["id"], "unique": True, "incomplete": "reject"}]
        if owner == "keyed_contract"
        else [],
        "order": {"kind": "significant", "by": ["id"], "ties": "preserve"}
        if owner == "sequence_contract"
        else {"kind": "ignored"},
        "origins": {
            "/spec/contract/contract_id": "default",
            "/spec/contract/revision": "default",
            "/reference": "default",
            "/spec/policy/index": "default",
        },
    }


def plan():
    cases = []
    for owner in ("bag_contract", "keyed_contract", "sequence_contract"):
        prefix = "parameter:equiframe." + owner + ":"
        additional = (
            "keys"
            if owner == "keyed_contract"
            else ("by" if owner == "sequence_contract" else None)
        )
        choice = (
            "incomplete"
            if owner == "keyed_contract"
            else ("ties" if owner == "sequence_contract" else None)
        )
        parameters = [
            "columns",
            "policy",
            "multiplicity",
            "reference",
            "contract_id",
            "revision",
        ]
        if additional:
            parameters.append(additional)
        if choice:
            parameters.append(choice)
        links = ["api:equiframe." + owner, prefix + "columns:class:0"]
        if additional:
            links.append(prefix + additional + ":class:0")
        links.extend(
            prefix + p + ":default"
            for p in parameters
            if p not in ("columns", additional)
        )
        cases.append(
            {
                "id": owner + ".defaults",
                "owner": owner,
                "kwargs": {},
                "expected": base_expected(owner),
                "obligations": links,
            }
        )
        variants = [
            ("policy", None, ["value:null"], None),
            (
                "policy",
                {
                    **POLICY,
                    "index": "ignore",
                    "justification": "Explicit fixture policy",
                },
                ["class:0"],
                "policy",
            ),
            ("contract_id", "reviewed_id", ["class:0"], "contract_id"),
            ("revision", 2, ["class:0"], "revision"),
            ("multiplicity", "preserve", ['value:"preserve"'], "multiplicity"),
            ("multiplicity", "distinct", ['value:"distinct"'], "multiplicity"),
            ("reference", "peer", ['value:"peer"'], "reference"),
            ("reference", "expected", ['value:"expected"'], "reference"),
        ]
        if choice:
            variants.extend(
                (choice, value, ["value:" + json.dumps(value)], choice)
                for value in (
                    ("reject", "allow")
                    if choice == "incomplete"
                    else ("preserve", "reject")
                )
            )
        for position, (parameter, value, suffixes, expected_field) in enumerate(
            variants
        ):
            expected = base_expected(owner)
            if expected_field == "incomplete":
                expected["keys"][0]["incomplete"] = value
            elif expected_field == "ties":
                expected["order"]["ties"] = value
            elif expected_field:
                expected[expected_field] = value
            origin_paths = {
                "policy": "/spec/policy/index",
                "contract_id": "/spec/contract/contract_id",
                "revision": "/spec/contract/revision",
                "reference": "/reference",
            }
            if parameter in origin_paths and value is not None:
                expected["origins"][origin_paths[parameter]] = "user"
            cases.append(
                {
                    "id": owner + f".explicit.{position:02}",
                    "owner": owner,
                    "kwargs": {parameter: value},
                    "expected": expected,
                    "obligations": [prefix + parameter + ":" + s for s in suffixes],
                }
            )
        for parameter in parameters:
            values = [
                (
                    "invalid",
                    None
                    if parameter in ("columns", additional, "revision")
                    else (
                        "unsupported"
                        if parameter in ("multiplicity", "reference", choice)
                        else 42
                    ),
                )
            ]
            if parameter in (
                "columns",
                additional,
                "policy",
                "contract_id",
                "revision",
            ):
                values.append(
                    ("class:1", 42 if parameter in ("columns", additional) else [])
                )
            for suffix, value in values:
                cases.append(
                    {
                        "id": owner + ".reject." + parameter + "." + suffix,
                        "owner": owner,
                        "kwargs": {parameter: value},
                        "expected_error": "TypeError"
                        if parameter in ("columns", additional)
                        else "ValidationError",
                        "obligations": [prefix + parameter + ":" + suffix],
                    }
                )
    return {
        "scope": "Contract factory API/parameters; authored semantic and provenance expectations",
        "scientific_credit": False,
        "cases": cases,
    }


def execute(case):
    columns = (
        ef.ColumnSpec(
            name="id",
            logical_type=ef.IntegerType(bits=64, signed=True),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
        ),
    )
    owner = case["owner"]
    kwargs = {"columns": columns}
    if owner == "keyed_contract":
        kwargs["keys"] = ("id",)
    if owner == "sequence_contract":
        kwargs["by"] = (ef.SortSpec(column="id", direction="ascending", nulls="last"),)
    kwargs.update(case["kwargs"])
    if isinstance(kwargs.get("policy"), dict):
        kwargs["policy"] = ef.ComparisonPolicy.model_validate(kwargs["policy"])
    result = getattr(ef, owner)(**kwargs)
    schema = result.spec.contract.output.schema_spec
    expected = case.get("expected", base_expected(owner))
    return {
        "class": type(result).__name__,
        "columns": [
            {
                "name": c.name,
                "kind": c.logical_type.kind,
                "bits": c.logical_type.bits,
                "signed": c.logical_type.signed,
                "nullable": c.nullable,
                "unit": c.numeric_policy.unit,
            }
            for c in schema.columns
        ],
        "same_input_schema": result.spec.contract.inputs[0].schema_spec == schema,
        "input_name": result.spec.contract.inputs[0].name,
        "output_name": result.spec.contract.output.name,
        "family": result.spec.contract.family,
        "rules": len(result.spec.contract.rules),
        "preconditions": len(result.spec.contract.preconditions),
        "multiplicity": schema.multiplicity,
        "reference": result.reference,
        "contract_id": result.spec.contract.contract_id,
        "revision": result.spec.contract.revision,
        "policy": result.spec.policy.model_dump(mode="json"),
        "keys": [
            {"columns": list(k.columns), "unique": k.unique, "incomplete": k.incomplete}
            for k in schema.keys
        ],
        "order": {
            "kind": schema.order.kind,
            "by": [s.column for s in schema.order.by],
            "ties": schema.order.ties,
        }
        if schema.order.kind == "significant"
        else {"kind": schema.order.kind},
        "origins": {
            path: result.provenance_for(path).origin for path in expected["origins"]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(sys.flags.isolated, "Use an isolated installed interpreter")
    spec = importlib.util.spec_from_file_location(
        "owned_contract_inputs", ROOT / "tools/revalidate_root_contexts.py"
    )
    require(
        spec is not None and spec.loader is not None, "Protected input reader missing"
    )
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    raw, baseline = reader.bounded_json(args.baseline)
    require(
        hashlib.sha256(raw).hexdigest() == args.baseline_sha256,
        "Baseline identity differs",
    )
    require(
        baseline["candidate"] == ef.__version__ == "0.12.0a14"
        and baseline["total"] == 8438
        and baseline["optimized"] is (not __debug__),
        "Full A14 baseline and matching mode required",
    )
    reader.require_ordinary_parents(args.output.absolute().parent)
    require(
        not args.output.exists() and not args.output.absolute().is_relative_to(ROOT),
        "New private output required",
    )
    spec = importlib.util.spec_from_file_location(
        "owned_contract_binding",
        ROOT / "packages/equiframe/tools/compatibility_probe.py",
    )
    require(spec is not None and spec.loader is not None, "Binding tool missing")
    binding_tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(binding_tool)
    _, binding = reader.bounded_json(args.binding)
    require(
        binding["wheel_sha256"] == baseline["wheel_sha256"],
        "Binding and baseline differ",
    )
    binding_tool.runtime_binding(binding)
    planned = plan()
    pending = {r["id"] for r in baseline["rows"] if r["status"] == "NOT_RUN"}
    selected = [
        identifier for case in planned["cases"] for identifier in case["obligations"]
    ]
    require(
        len(selected) == len(set(selected)) and set(selected) <= pending,
        "IDs overlap or lack pending baseline obligations",
    )
    args.output.mkdir()
    frozen = (json.dumps(planned, indent=2, allow_nan=False) + "\n").encode()
    (args.output / "catalog.json").write_bytes(frozen)
    receipts = []
    for case in planned["cases"]:
        observed = error = None
        try:
            observed = execute(case)
            status = "PASS" if observed == case.get("expected") else "FAIL"
        except (TypeError, ValidationError) as failure:
            error = type(failure).__name__
            status = (
                "EXPECTED_REJECTION" if error == case.get("expected_error") else "FAIL"
            )
        except (
            ef.InvalidExecutionInput,
            ValueError,
            AttributeError,
            KeyError,
            RuntimeError,
        ) as failure:
            error = type(failure).__name__
            status = "FAIL"
        receipts.append(
            {
                "case_id": case["id"],
                "status": status,
                "observed": observed,
                "error": error,
                "obligations": case["obligations"],
            }
        )
    require(
        (args.output / "catalog.json").read_bytes() == frozen,
        "Expected catalogue changed",
    )
    result = {
        "source_commit": baseline["source_commit"],
        "wheel_sha256": baseline["wheel_sha256"],
        "baseline_sha256": args.baseline_sha256,
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(frozen).hexdigest(),
        "optimized": not __debug__,
        "counts": dict(Counter(r["status"] for r in receipts)),
        "receipts": receipts,
        "scientific_credit": False,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"counts": result["counts"], "obligations": len(selected)}))
    return int(bool(result["counts"].get("FAIL")))


if __name__ == "__main__":
    raise SystemExit(main())
