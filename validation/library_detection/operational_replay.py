"""Replay exact ETL acceptance and a frozen Isolation Forest on the public corpus."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import public_spending as study
from run import metrics
from runtime_receipt import receipt

import equiframe as ef


def replay_case(
    case: dict[str, Any], engine: str, folder: Path
) -> tuple[bool, str, str, ef.ProfileVector]:
    record, vectors = study.execute_case(case, engine, folder, profile=True, versions=("1.1",))
    (manifest,) = (folder / "comparison").glob("*/comparison.json")
    comparison = ef.read_comparison(manifest)
    decision = ef.equivalence_decision(
        comparison, policy=ef.EquivalencePolicy(required_reference="expected")
    )
    if comparison.left is None or comparison.right is None:
        raise ValueError("Required captures are absent")
    grouped = ef.compare_grouped(
        ef.read_table(comparison.left.data),
        ef.read_table(comparison.right.data),
        by=("buyer", "currency"),
        column="total",
    )
    if not grouped.complete:
        group_state = "not_evaluable"
    elif grouped.added_groups or grouped.removed_groups or grouped.modified_groups:
        group_state = "alert"
    else:
        group_state = "no_alert"
    return record["divergent"], decision.code, group_state, vectors["1.1"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--primary-protocol", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity = receipt(args.wheel)
    protocol = json.loads(args.primary_protocol.read_bytes())
    procedures, _ = study.cohort(args.csv_dir)
    cases, selection = study.select_cases(procedures, protocol["counts"])
    if selection != protocol["selection"] or protocol["profile_versions"] != ["1.1"]:
        raise ValueError("The original feature 1.1 selection was not reproduced")
    bundle = ef.read_detector_bundle(args.model, expected_sha256=args.model_sha256)

    limits = {("test", "normal"): 64, ("shifted_normal", "normal"): 16}
    limits.update({("test", fault): 16 for fault in study.FAULTS})
    selected: Counter[tuple[str, str]] = Counter()
    rows: list[dict[str, Any]] = []
    profiles = []
    gate_labels = {"equivalent": "no_alert", "different": "alert"}
    for case in cases:
        key = case["split"], case["kind"]
        if key not in limits or selected[key] >= limits[key]:
            continue
        engine_results = []
        for engine in study.ENGINES:
            with tempfile.TemporaryDirectory(prefix="equiframe-operational-") as scratch:
                engine_results.append(replay_case(case, engine, Path(scratch)))
        reference = engine_results[0]
        if any(result != reference for result in engine_results[1:]):
            raise ValueError("Native engines disagree on reference labels, checks or profiles")
        divergent, code, group, profile = reference
        rows.append(
            {
                "source_sha256": case["source_sha256"],
                "split": key[0],
                "kind": key[1],
                "divergent": divergent,
                "exact_gate": gate_labels.get(code, "not_evaluable"),
                "group_rule": group,
            }
        )
        profiles.append(profile)
        selected[key] += 1
    if dict(selected) != limits:
        raise ValueError("The predetermined quotas were not satisfied")

    detection = ef.detect_component(bundle, tuple(profiles), method="isolation_forest")
    for row, result in zip(rows, detection.decisions, strict=True):
        row["isolation_forest"] = result.result.decision
    report = {
        "version": identity["version"],
        "wheel_sha256": identity["wheel_sha256"],
        "installed_package_files_verified": identity["files_checked"],
        "frozen_bundle_sha256": args.model_sha256,
        "native_engines": study.ENGINES,
        "native_executions": len(rows) * len(study.ENGINES),
        "selection": "First predetermined quota per split and fault of the original 1.1 protocol",
        "metrics": {
            name: metrics(rows, name) for name in ("isolation_forest", "group_rule", "exact_gate")
        },
        "rows": rows,
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
