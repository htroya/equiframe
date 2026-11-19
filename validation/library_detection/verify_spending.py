"""Reconcile recorded public-spending counts independently of the experiment runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def load(folder: Path, name: str) -> Any:
    return json.loads((folder / name).read_bytes())


def reconcile(records: list[dict[str, Any]], method: str, claimed: dict[str, Any]) -> None:
    counts = dict(tp=0, fp=0, tn=0, fn=0, unavailable=0)
    for record in records:
        decision = record[method]
        if decision == "not_evaluable":
            counts["unavailable"] += 1
        elif decision in ("alert", "no_alert"):
            label = (
                ("tp" if record["divergent"] else "fp")
                if decision == "alert"
                else ("fn" if record["divergent"] else "tn")
            )
            counts[label] += 1
        else:
            raise ValueError("Unknown decision")
    if claimed["cases"] != len(records) or any(claimed[k] != v for k, v in counts.items()):
        raise ValueError("Report counts disagree with the recorded decisions")
    for name, numerator, denominator in (
        ("recall", counts["tp"], counts["tp"] + counts["fn"]),
        ("false_positive_rate", counts["fp"], counts["fp"] + counts["tn"]),
    ):
        expected = numerator / denominator if denominator else None
        if claimed[name] != expected:
            raise ValueError("Metric denominator or value disagrees")


def verify_primary(
    primary: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    protocol = load(primary, "protocol.json")
    report, rows, native = (
        load(primary, n) for n in ("report.json", "scored-records.json", "native-records.json")
    )
    if (
        report["protocol_sha256"]
        != hashlib.sha256((primary / "protocol.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Primary protocol identity disagrees")
    versions = protocol["profile_versions"]
    if versions not in (["1.1"], ["1.1", "1.2"]):
        raise ValueError("Unexpected profile versions in the frozen experiment")
    expected_cells = {(v, seed) for v in versions for seed in (7, 23, 71)}
    if len(rows) != 1152 * len(expected_cells) or len(native) != 4032 or report["cases"] != 1728:
        raise ValueError("Unexpected frozen experiment size")
    unique = {(r["split"], r["index"], r["source_sha256"]) for r in rows}
    if len(unique) != 1152 or len({r["source_sha256"] for r in rows}) != 1152:
        raise ValueError("Test sample identity is duplicated")
    cells = [(summary["version"], summary["seed"]) for summary in report["summaries"]]
    if set(cells) != expected_cells or len(cells) != len(expected_cells):
        raise ValueError("Unexpected or repeated profile/seed cell")
    for summary in report["summaries"]:
        selected = [
            r for r in rows if (r["version"], r["seed"]) == (summary["version"], summary["seed"])
        ]
        if {(r["split"], r["index"], r["source_sha256"]) for r in selected} != unique or len(
            selected
        ) != len(unique):
            raise ValueError("Each profile/seed cell must cover the same test cases once")
        for section, split in (("main", "test"), ("shifted_normal", "shifted_normal")):
            subset = [r for r in selected if r["split"] == split]
            for method in ("r", "m", "b", "h"):
                reconcile(subset, method, summary[section][method])
        for fault, results in summary["per_fault"].items():
            subset = [r for r in selected if r["split"] == "test" and r["kind"] == fault]
            for method, claimed in results.items():
                reconcile(subset, method, claimed)
        for row in selected:
            if row["m"] != ("alert" if row["m_score"] > row["m_threshold"] else "no_alert"):
                raise ValueError("M decision does not follow the frozen strict threshold")
            expected_h = "alert" if "alert" in (row["r"], row["m"]) else "no_alert"
            if row["h"] != expected_h:
                raise ValueError("Hybrid decision disagrees")
    return report, rows, native


def verify(primary: Path, severity: Path) -> dict[str, Any]:
    report, rows, native = verify_primary(primary)
    extra, extra_rows, extra_native = (
        load(severity, n) for n in ("report.json", "records.json", "native-records.json")
    )
    if (
        extra["protocol_sha256"]
        != hashlib.sha256((severity / "protocol.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Severity protocol identity disagrees")
    if len(extra_rows) != 640 or len(extra_native) != 960:
        raise ValueError("Severity count disagrees")
    source_groups = {r["source_sha256"] for r in extra_rows}
    if len(source_groups) != 64 or source_groups & {r["source_sha256"] for r in native}:
        raise ValueError("Supplementary sources overlap or have the wrong support")
    for summary in extra["summaries"]:
        selected = [r for r in extra_rows if r["version"] == summary["version"]]
        primary_id = next(
            s["bundle_sha256"]
            for s in report["summaries"]
            if s["version"] == summary["version"] and s["seed"] == 7
        )
        if summary["bundle_sha256"] != primary_id:
            raise ValueError("Severity model was changed")
        for method in ("r_global", "r_group", "m", "b", "h_global"):
            reconcile(selected, method, summary["all"][method])
            for level, group in summary["per_level"].items():
                reconcile([r for r in selected if r["level"] == level], method, group[method])
    traces = load(severity, "tree-traces.json")
    if len(traces) != 10:
        raise ValueError("Missing prespecified traces")
    for trace in traces:
        if trace["trees_used"] != 200 or not math.isclose(
            trace["score_from_paths"], trace["score_from_api"], rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError("Actual tree traversal disagrees with the API")
    return {
        "passed": True,
        "primary_unique_test_cases": 1152,
        "severity_source_groups": 64,
        "scored_rows_reconciled": len(rows) + len(extra_rows),
        "actual_forest_traces": 10,
        "scope": (
            "Recorded counts, decisions and identities; source-procedure disjointness "
            "is enforced during extraction, not inferred from hashes alone."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--severity", type=Path)
    args = parser.parse_args()
    if args.severity is not None:
        result = verify(args.primary, args.severity)
    else:
        report, rows, native = verify_primary(args.primary)
        result = {
            "passed": True,
            "primary_unique_test_cases": report["unique_test_cases"],
            "primary_native_executions": len(native),
            "scored_rows_reconciled": len(rows),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
