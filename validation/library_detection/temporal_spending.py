"""Test a recalibrated Isolation Forest on later months of the same public corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import tempfile
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import public_spending as study
from operational_replay import replay_case
from run import digest, metrics
from runtime_receipt import receipt

import equiframe as ef

ALPHA = "0.05"
SEED = 7
SUPPORT = 48
PERIODS = {
    "training": (1, 6),
    "calibration": (7, 9),
    "test_oct": (10, 10),
    "test_nov": (11, 11),
    "test_dec": (12, 12),
}
METHODS = ("exact_gate", "group_rule", "isolation_forest")


def select(csv_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    procedures, inventory = study.cohort(csv_dir)
    by_month: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    timezone = ZoneInfo("America/Guayaquil")
    with (csv_dir / "releases_2025.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            ocid = row["ocid"]
            if ocid in procedures:
                date = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
                by_month[date.astimezone(timezone).month][ocid] = procedures[ocid]

    cases = []
    selections = {}
    for period, (first, last) in PERIODS.items():
        pool = {
            ocid: rows for month in range(first, last + 1) for ocid, rows in by_month[month].items()
        }
        counts = dict(training=0, development=0, calibration=0, test=0, normal=0, shift=0)
        split = period if period in ("training", "calibration") else "test"
        counts[split] = SUPPORT
        if split == "test":
            counts.update(test=20, normal=8, shift=4)
        selected, audit = study.select_cases(pool, counts)
        selections[period] = {
            "first_month": first,
            "last_month": last,
            "eligible_procedures_before_hash_filter": len(pool),
            "selection": audit[split],
        }
        cases.extend({**case, "period": period} for case in selected)
    if len({case["source_sha256"] for case in cases}) != len(cases):
        raise ValueError("A batch was assigned to more than one experiment case")
    return cases, {"inventory": inventory, "periods": selections}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity = receipt(args.wheel)
    cases, selection = select(args.csv_dir)

    earlier: dict[str, list[ef.ProfileVector]] = defaultdict(list)
    holdout_profiles = []
    rows = []
    engine_runs = 0
    for case in cases:
        held_out = case["period"] not in ("training", "calibration")
        native = []
        for engine in study.ENGINES if held_out else ("pandas",):
            with tempfile.TemporaryDirectory(dir=args.output.parent) as scratch:
                native.append(replay_case(case, engine, Path(scratch)))
            engine_runs += 1
        divergent, exact, group, profile = native[0]
        if any(item != native[0] for item in native[1:]):
            raise RuntimeError("Native engines disagree on labels, checks or profiles")
        if not held_out:
            if divergent or exact != "equivalent":
                raise RuntimeError("Only verified normal batches may train or calibrate")
            earlier[case["period"]].append(profile)
            continue
        holdout_profiles.append(profile)
        rows.append(
            {
                "period": case["period"],
                "scenario": "shifted_normal" if case["split"] == "shifted_normal" else case["kind"],
                "batch_sha256": case["source_sha256"],
                "divergent": divergent,
                "exact_gate": {"equivalent": "no_alert", "different": "alert"}.get(
                    exact, "not_evaluable"
                ),
                "group_rule": group,
            }
        )

    fit = ef.fit_detectors(
        ef.NormalTrainingProfiles(
            purpose="normal_training",
            selection_manifest_sha256=digest(selection["periods"]["training"]),
            profiles=tuple(earlier["training"]),
        ),
        spec=study.specifications("1.1")[1],
        config=ef.IsolationForestConfig(n_estimators=200, max_samples=256, random_state=SEED),
        support=ef.DetectorSupport(
            min_training_rows=SUPPORT,
            min_calibration_rows=SUPPORT,
            rationale="Fixed support for a temporal engineering evaluation of one public corpus.",
        ),
    )
    bundle = ef.calibrate_detectors(
        fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration",
            selection_manifest_sha256=digest(selection["periods"]["calibration"]),
            profiles=tuple(earlier["calibration"]),
        ),
        alpha=ALPHA,
    )
    start = time.perf_counter()
    detections = ef.detect_component(bundle, tuple(holdout_profiles), method="isolation_forest")
    elapsed = time.perf_counter() - start
    for row, detection in zip(rows, detections.decisions, strict=True):
        row["isolation_forest"] = detection.result.decision

    report = {
        "schema_version": "1.0",
        "wheel_version": identity["version"],
        "wheel_sha256": identity["wheel_sha256"],
        "installed_package_files_verified": identity["files_checked"],
        "experiment_modules_sha256": {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in (
                "temporal_spending.py",
                "operational_replay.py",
                "public_spending.py",
                "run.py",
            )
        },
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("pandas", "polars", "duckdb", "pyarrow", "scikit-learn", "numpy")
        },
        "calendar": "Whole procedures grouped by SERCOP release month in America/Guayaquil.",
        "source_files_sha256": study.FILES,
        "selection": selection,
        "label": "Independent integer-cent oracle over public awards and controlled ETL faults.",
        "profile_version": "1.1",
        "detector": {
            "alpha": ALPHA,
            "seed": SEED,
            "trees": len(fit.m.trees),
            "max_samples_requested": 256,
            "training_batches": len(earlier["training"]),
            "calibration_batches": len(earlier["calibration"]),
            "bundle_sha256": ef.detector_fingerprint(bundle),
            "inference_seconds_for_full_holdout_batch": elapsed,
        },
        "holdout_engines": study.ENGINES,
        "native_executions": engine_runs,
        "overall": {method: metrics(rows, method) for method in METHODS},
        "by_month_and_scenario": {
            period: {
                scenario: {
                    method: metrics(
                        [
                            row
                            for row in rows
                            if row["period"] == period and row["scenario"] == scenario
                        ],
                        method,
                    )
                    for method in METHODS
                }
                for scenario in ("normal", "shifted_normal", *study.FAULTS)
            }
            for period in PERIODS
            if period.startswith("test_")
        },
        "holdout_batches": rows,
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
