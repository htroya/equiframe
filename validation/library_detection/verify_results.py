"""Reconcile published case records, independent denominators and frozen inputs."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def verify(directory: Path, *, source: Path | None = None) -> dict[str, Any]:
    plan = json.loads((directory / "protocol.json").read_bytes())
    report = json.loads((directory / "report.json").read_bytes())
    assert report["purpose"] == plan["purpose"] == "evaluation"
    assert report["protocol_sha256"] == digest(plan)
    csv_path = directory / "cases.csv"
    csv_bytes = (
        csv_path.read_bytes()
        if csv_path.exists()
        else gzip.decompress((directory / "cases.csv.gz").read_bytes())
    )
    assert report["case_records_sha256"] == hashlib.sha256(csv_bytes).hexdigest()
    if source is not None:
        assert hashlib.sha256(source.read_bytes()).hexdigest() == plan["code_sha256"]
    records = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"), newline="")))
    seeds = [str(plan["primary_forest_seed"]), *map(str, plan["sensitivity_forest_seeds"])]
    test_count = plan["test_normal"] + plan["shifted_normal"] + 4 * plan["test_per_fault"]
    expected_executions = len(plan["workloads"]) * (
        plan["training"] + plan["calibration"] + test_count
    )
    assert report["unique_source_cases"] == expected_executions == 2304
    assert len(records) == len(seeds) * len(plan["workloads"]) * test_count == 3840
    for row in records:
        # This checks the captured exact outputs, not just the fault name.
        assert row["divergent"] in ("True", "False")
        assert (row["actual_sha256"] != row["expected_sha256"]) == (row["divergent"] == "True")
        assert all(
            math.isfinite(float(row[k])) and float(row[k]) >= 0
            for k in ("execution_seconds", "profile_seconds", "oracle_seconds")
        )
    for workload in report["workloads"]:
        name = workload["workload"]
        assert workload["generated_executions"] == expected_executions // 2
        assert [str(m["seed"]) for m in workload["models"]] == seeds
        primary = [r for r in records if r["workload"] == name and r["forest_seed"] == seeds[0]]
        assert len({r["source_sha256"] for r in primary}) == test_count
        for model in workload["models"]:
            rows = [
                r
                for r in records
                if r["workload"] == name and r["forest_seed"] == str(model["seed"])
            ]
            assert [r["source_sha256"] for r in rows] == [r["source_sha256"] for r in primary]
            assert model["batch_inference_cases"] == test_count
            for partition, methods in model["results"].items():
                if partition == "in_distribution":
                    selected = [r for r in rows if r["split"] != "shifted_normal"]
                elif partition == "shifted_correct":
                    selected = [r for r in rows if r["split"] == "shifted_normal"]
                else:
                    selected = [r for r in rows if r["fault"] == partition]
                for method, result in methods.items():
                    counts = Counter((r["divergent"], r[method]) for r in selected)
                    expected = {
                        "tp": counts[("True", "alert")],
                        "fn": counts[("True", "no_alert")],
                        "fp": counts[("False", "alert")],
                        "tn": counts[("False", "no_alert")],
                    }
                    assert all(result[k] == v for k, v in expected.items())
                    assert result["cases"] == len(selected)
                    assert result["unavailable"] == len(selected) - sum(expected.values())
                    positives = expected["tp"] + expected["fn"]
                    negatives = expected["fp"] + expected["tn"]
                    assert result["recall"] == (expected["tp"] / positives if positives else None)
                    assert result["false_positive_rate"] == (
                        expected["fp"] / negatives if negatives else None
                    )
    return {
        "verified": True,
        "native_executions": expected_executions,
        "unique_test_cases": len(plan["workloads"]) * test_count,
        "scored_rows": len(records),
        "model_seeds": seeds,
        "source_hash_verified": source is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, source=args.source)))


if __name__ == "__main__":
    main()
