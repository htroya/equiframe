"""Predeclare constructor/native-row effects and count only disjoint executed IDs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import equiframe as ef
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
ENGINES = {
    "PandasTransformation": "pandas",
    "PolarsTransformation": "polars",
    "DuckDBTransformation": "duckdb",
}
ROWS = [{"id": 1}, {"id": 1}, {"id": 2}]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "Owned helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(pending):
    cases = []
    remaining = set(pending)

    def add(owner, name, updates, identifiers, error=None):
        links = sorted(set(identifiers) & remaining)
        remaining.difference_update(links)
        cases.append(
            {
                "id": owner + "." + name,
                "owner": owner,
                "updates": updates,
                "obligations": links,
                "expected_error": error,
                "expected_rows": None if error else ROWS,
            }
        )

    for owner, engine in ENGINES.items():
        prefix = "parameter:equiframe." + owner + ":"
        implementation = "sql" if engine == "duckdb" else "callback"
        add(
            owner,
            "defaults",
            {},
            [
                "api:equiframe." + owner,
                *[
                    prefix + p + ":class:0"
                    for p in ("transformation_id", "code_version", implementation)
                ],
                prefix + "revision:default",
                prefix + "engine:default",
            ],
        )
        add(
            owner,
            "explicit_revision_engine",
            {"revision": 2, "engine": engine},
            [
                prefix + "revision:class:0",
                prefix + "engine:value:" + json.dumps(engine),
            ],
        )
        bad = {
            "transformation_id": [(None, "class:1"), ("invalid identifier", "invalid")],
            "code_version": [(None, "class:1"), ("", "invalid")],
            "revision": [(None, "class:1"), (True, "invalid")],
            "engine": [("other", "invalid")],
            implementation: [(None, "class:1"), (0, "invalid")],
        }
        for parameter, values in bad.items():
            for value, suffix in values:
                add(
                    owner,
                    parameter + "_" + suffix.replace(":", "_"),
                    {parameter: value},
                    [prefix + parameter + ":" + suffix],
                    "InvalidExecutionInput"
                    if parameter in {"engine", implementation}
                    else "ValidationError",
                )
    return {
        "scope": "Built-in trusted transformation admission with actual native output, not scientific evidence",
        "fixture": ROWS,
        "cases": cases,
    }


def run_case(case, directory):
    import pyarrow as pa

    owner = case["owner"]
    engine = ENGINES[owner]
    calls = []

    def callback(inputs, context):
        calls.append(engine)
        return (
            inputs["source"].copy()
            if engine == "pandas"
            else inputs["source"].select("id")
        )

    kwargs = {
        "transformation_id": "admitted",
        "code_version": "owned-v1",
        **(
            {"sql": "  SELECT id FROM source\n"}
            if engine == "duckdb"
            else {"callback": callback}
        ),
        **case["updates"],
    }
    try:
        transform = getattr(ef, owner)(**kwargs)
    except (ValidationError, ef.InvalidExecutionInput) as error:
        return {
            "error": type(error).__name__,
            "callbacks": calls,
            "files": [],
        }, "EXPECTED_REJECTION" if type(error).__name__ == case[
            "expected_error"
        ] and not calls and not directory.exists() else "FAIL"
    if case["expected_error"] is not None:
        return {"error": None, "callbacks": calls}, "FAIL"
    column = ef.ColumnSpec(
        name="id",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    contract = ef.bag_contract((column,)).spec.contract
    registry = ef.TransformationRegistry()
    registry.register(transform)
    result = ef.execute(
        ef.ExecutionPlan(
            contract=contract,
            engine=engine,
            transformation_id=transform.transformation_id,
            transformation_revision=transform.revision,
        ),
        source=ef.LocalDataSource(
            {"source": ef.ArrowInput(pa.table({"id": [1, 1, 2]}))}
        ),
        registry=registry,
        work_dir=directory,
    )
    actual = {
        "state": result.state,
        "rows": ef.read_table(result.output.data).to_pylist()
        if result.output is not None
        else None,
        "identity": transform.transformation_id,
        "version": transform.code_version,
        "revision": transform.revision,
        "engine": transform.engine,
        "callback_count": len(calls),
    }
    expected = {
        "state": "completed",
        "rows": ROWS,
        "identity": "admitted",
        "version": "owned-v1",
        "revision": case["updates"].get("revision", 1),
        "engine": engine,
        "callback_count": 0 if engine == "duckdb" else 1,
    }
    return actual, "PASS" if actual == expected else "FAIL"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "exclude-covered", "binding", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--exclude-covered-sha256", required=True)
    args = parser.parse_args()
    require(sys.flags.isolated, "Isolated installed interpreter required")
    reader = helper(
        "owned_transformation_reader", ROOT / "tools/revalidate_root_contexts.py"
    )
    raw, baseline = reader.bounded_json(args.baseline)
    require(
        hashlib.sha256(raw).hexdigest() == args.baseline_sha256
        and baseline["total"] == 8438
        and baseline["optimized"] is (not __debug__),
        "Matching A14 baseline required",
    )
    raw, exclusion = reader.bounded_json(args.exclude_covered)
    require(
        hashlib.sha256(raw).hexdigest() == args.exclude_covered_sha256
        and exclusion["total"] == 9142,
        "Exclusion scope differs",
    )
    covered = {r["id"] for r in exclusion["rows"] if r["status"] != "NOT_RUN"}
    pending = {r["id"] for r in baseline["rows"] if r["status"] == "NOT_RUN"} - covered
    _, binding = reader.bounded_json(args.binding)
    require(
        binding["wheel_sha256"] == baseline["wheel_sha256"]
        and ef.__version__ == baseline["candidate"] == "0.12.0a14",
        "Candidate binding differs",
    )
    helper(
        "owned_transformation_binding",
        ROOT / "packages/equiframe/tools/compatibility_probe.py",
    ).runtime_binding(binding)
    reader.require_ordinary_parents(args.output.absolute().parent)
    require(
        not args.output.exists() and not args.output.absolute().is_relative_to(ROOT),
        "New private output required",
    )
    catalog = plan(pending)
    args.output.mkdir()
    frozen = (json.dumps(catalog, indent=2, allow_nan=False) + "\n").encode()
    (args.output / "catalog.json").write_bytes(frozen)
    tool_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    receipts = []
    for index, case in enumerate(catalog["cases"]):
        observation, status = run_case(
            case, args.output.absolute() / f"case-{index:03}"
        )
        receipts.append(
            {
                "case_id": case["id"],
                "status": status,
                "observed": observation,
                "obligations": case["obligations"],
            }
        )
    require(
        (args.output / "catalog.json").read_bytes() == frozen
        and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == tool_sha,
        "Frozen plan or tool changed",
    )
    result = {
        "source_commit": baseline["source_commit"],
        "wheel_sha256": baseline["wheel_sha256"],
        "optimized": not __debug__,
        "catalog_sha256": hashlib.sha256(frozen).hexdigest(),
        "tool_sha256": tool_sha,
        "baseline_sha256": args.baseline_sha256,
        "exclusion_scope_sha256": args.exclude_covered_sha256,
        "historical_counts_imported": False,
        "counts": dict(Counter(r["status"] for r in receipts)),
        "receipts": receipts,
        "scientific_credit": False,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "obligations": sum(len(c["obligations"]) for c in catalog["cases"]),
            }
        )
    )
    return int(bool(result["counts"].get("FAIL")))


if __name__ == "__main__":
    raise SystemExit(main())
