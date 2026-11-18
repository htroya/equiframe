"""Supplement the frozen M13 review with actual measurement and fault results.

This is an offline review of the exact evidence inventory. It changes no kit,
execution expectations, resources, SDK or maturity rubric; it grants no point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

from manifest_scope import required_pythons
from validate_vm_receipts import Review, sha

METRICS = (
    "sampled_rss_peak_bytes",
    "cpu_user_seconds",
    "cpu_system_seconds",
    "io_read_bytes",
    "io_write_bytes",
    "io_read_chars",
    "io_write_chars",
    "disk_apparent_peak_bytes",
    "disk_allocated_peak_bytes",
)
FAULT_CASES = (
    "accept",
    "compensated_reject",
    "budget_reject",
    "rejected_input",
    "write_fault",
    "report_corruption",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_measurements(summary, bounded):
    protocol = summary["protocol"]
    require(
        protocol["rows"] == [100, 1000]
        and protocol["width"] == 2
        and protocol["repetitions"] == 3
        and protocol["rss_budget_bytes"] == 512 * 1024**2
        and protocol["disk_budget_bytes"] == 64 * 1024**2
        and protocol["timeout_seconds"] == 120
        and protocol["threads_per_engine"] == 1
        and protocol["expected_state"] == "different"
        and protocol["storage"] == "disk"
        and protocol["slo_accepted"] is False,
        "Original bounded measurement protocol differs",
    )
    require(
        protocol["filesystem_observation"]["storage"] == "disk",
        "Recorded filesystem observation differs",
    )
    results = summary["results"]
    require(
        len(results) == 2
        and [r["case_id"] for r in results] == ["maturity-100", "maturity-1000"],
        "Measurement sizes are missing or repeated",
    )
    observations = []
    for result in results:
        require(
            result["complete"] is True
            and result["resource_measurement_complete"] is True,
            "A partial measurement cannot close the review",
        )
        require(
            result["issues"] == [] and result["resource_quality"] == ["complete"] * 3,
            "Measurement issues or incomplete trial resources remain",
        )
        require(
            (
                result["requested_repetitions"],
                result["observed_repetitions"],
                result["correct_complete_repetitions"],
                result["unsuccessful_or_missing_repetitions"],
            )
            == (3, 3, 3, 0),
            "Measurement repetitions or expected outcomes differ",
        )
        contract = result["resource_measurement_contract"]
        require(
            contract["id"] == "equiframe_process_resources_v1"
            and contract["platform"] == "linux",
            "Linux resource contract differs",
        )
        metrics = contract["metrics"]
        require(
            len(metrics) == 9 and {m["metric"] for m in metrics} == set(METRICS),
            "The nine Linux counters are missing or repeated",
        )
        require(
            all(
                m["state"] == "observed" and m["reason"] is None and m["source"]
                for m in metrics
            ),
            "An unavailable or failed Linux counter cannot close the review",
        )
        process = result["process"]
        require(
            process["measurement_contract"] == contract["id"]
            and process["measurement_platform"] == contract["platform"]
            and process["metric_coverage"] == metrics,
            "Summary coverage differs from the actual process observations",
        )
        require(
            process["termination_reason"] == "exited"
            and process["exit_code"] == 0
            and process["monitoring_errors"] == []
            and process["cleanup_reaped"] is True
            and type(process["sample_count"]) is int
            and process["sample_count"] > 0,
            "Actual measurement process is incomplete",
        )
        for name in METRICS:
            value = process[name]
            require(
                type(value) in (int, float) and math.isfinite(value) and value >= 0,
                "Metric value is absent or invalid: " + name,
            )
        require(
            process["sampled_rss_peak_bytes"] <= protocol["rss_budget_bytes"]
            and max(
                process["disk_apparent_peak_bytes"],
                process["disk_allocated_peak_bytes"],
            )
            <= protocol["disk_budget_bytes"],
            "Observed resource budget exceeded",
        )
        wall = process["wall_seconds"]
        require(
            type(wall) in (int, float)
            and math.isfinite(wall)
            and 0 <= wall <= protocol["timeout_seconds"],
            "Observed process duration exceeds the protocol",
        )
        observations.append(
            {
                "case_id": result["case_id"],
                "repetitions": 3,
                "metric_count": 9,
                "sample_count": process["sample_count"],
                "sampled_rss_peak_bytes": process["sampled_rss_peak_bytes"],
            }
        )
    require(
        bounded["state"] == "not_evaluable" and bounded["complete"] is False,
        "The deliberately bounded case did not preserve not_evaluable",
    )
    return observations


def check_faults(faults):
    require(
        faults["status"] == "PASS" and faults["synthetic_fixture"] is True,
        "Consumer recovery results are incomplete",
    )
    checks = faults["checks"]
    require(
        len(checks) == 6 and [c["case"] for c in checks] == list(FAULT_CASES),
        "Consumer recovery cases are missing or repeated",
    )
    for record, expected in zip(
        checks[:3],
        (
            ("equivalent", True, None),
            ("different", False, "EquivalenceDifferentError"),
            ("not_evaluable", False, "EquivalenceNotEvaluableError"),
        ),
        strict=True,
    ):
        require(
            (record["state"], record["accepted"], record["error"]) == expected
            and type(record["accepted"]) is bool,
            "Explicit consumer acceptance/rejection differs",
        )
    require(
        all(
            c["prior_publication_preserved"] is True and c["staging_clean"] is True
            for c in checks[3:5]
        ),
        "Fault changed prior publication or retained staging",
    )
    require(checks[5]["rejected"] is True, "Changed report was admitted")
    return {"cases": 6, "synthetic_fixture": True, "all_expected_results": True}


def check_environment(environment, minor, *, consumer=False):
    require(
        environment["python"].startswith(minor + ".")
        and environment["machine"] == "aarch64",
        "Measured environment differs from the required actual ARM64 Python",
    )
    if consumer:
        require(
            type(environment["isolated"]) is int
            and environment["isolated"] == 1
            and type(environment["optimized"]) is int
            and environment["optimized"] == 1,
            "Consumer recovery must use the actual isolated optimized interpreter",
        )
        dependencies = {
            name.lower().replace("_", "-"): version
            for name, version in environment["dependencies"].items()
        }
        require(
            dependencies.get("equiframe") == "0.12.0a13"
            and dependencies.get("equiframe-consumer-lab") == "0.1.15",
            "Consumer recovery used different installed distributions",
        )
    else:
        require(
            environment["system"] == "Linux"
            and environment.get("equiframe") == "0.12.0a13"
            and environment.get("equiframe-benchmark") == "0.12.0a13",
            "Scale worker is not the required Linux A13 runtime",
        )


def check_scale_receipts(verifier, measurements, summary, minor):
    """Verify raw worker files rather than relying on a summary's pass flags."""
    for result, rows in zip(summary["results"], (100, 1000), strict=True):
        run_id = result["run_id"]
        require(
            isinstance(run_id, str)
            and run_id not in ("", ".", "..")
            and "/" not in run_id
            and "\\" not in run_id,
            "Scale run identity must be one directory component",
        )
        root = measurements / f"rows-{rows}" / run_id
        raw = verifier.json(str(root / "scale.json"))
        final = verifier.json(str(root / "finished.json"))
        spec = verifier.json(str(root / "spec.json"))
        digest = hashlib.sha256(
            json.dumps(
                spec,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        require(
            raw["run_id"] == run_id
            and raw["spec"] == spec
            and raw["spec_sha256"] == digest
            and spec["case_id"] == result["case_id"]
            and spec["rows"] == rows
            and spec["repetitions"] == 3
            and spec["width"] == 2
            and spec["difference_last"] is True
            and spec["timeout_seconds"] == 120
            and spec["rss_budget_bytes"] == 512 * 1024**2
            and spec["disk_budget_bytes"] == 64 * 1024**2
            and spec["comparison_options"]["max_rows"] == 2000
            and spec["comparison_options"]["max_disk_bytes"] == 32 * 1024**2
            and spec["comparison_options"]["timeout_seconds"] == 60,
            "Raw scale specification or run identity differs",
        )
        require(
            raw["process"] == result["process"]
            and raw["issues"] == result["issues"] == []
            and raw["worker_finalized"] is True
            and raw["environment_origin"] == "worker"
            and raw["producer_runtime_matches_parent"] is True,
            "Scale summary differs from the finalized worker observation",
        )
        check_environment(raw["environment"], minor)
        require(
            final["complete"] is True and final["result"]["path"] == "scale.json",
            "Atomic scale finalization is incomplete",
        )
        for record in [final["result"], *raw["evidence"]]:
            path = PurePosixPath(record["path"])
            require(
                not path.is_absolute()
                and ".." not in path.parts
                and "\\" not in record["path"],
                "Scale evidence path is not relative",
            )
            actual = verifier.file(str(root / path), record["sha256"])
            require(
                actual.stat().st_size == record["size_bytes"], "Scale file size differs"
            )
        worker = root / "worker"
        completion = verifier.json(str(worker / "worker-completed.json"))
        names = [f"trial-{n:03d}.json" for n in range(3)]
        require(
            completion["case_sha256"] == digest
            and completion["environment"] == raw["environment"]
            and [r["path"] for r in completion["trial_files"]] == names
            and len(raw["trials"]) == 3,
            "Worker completion does not bind all three actual trials",
        )
        for repetition, record in enumerate(completion["trial_files"]):
            path = worker / record["path"]
            actual = verifier.file(str(path), record["sha256"])
            require(
                actual.stat().st_size == record["size_bytes"],
                "Worker trial size differs",
            )
            trial = verifier.json(str(path), record["sha256"])
            require(
                trial == raw["trials"][repetition]
                and trial["case_sha256"] == digest
                and trial["repetition"] == repetition
                and trial["comparison"]["complete"] is True
                and trial["comparison"]["state"] == "different"
                and trial["comparison"]["counts"]["left_rows"] == rows
                and trial["comparison"]["counts"]["right_rows"] == rows
                and trial["comparison"]["options"] == spec["comparison_options"]
                and trial["resources"]["state"] == "complete",
                "Raw trial is missing, reordered, incomplete or differs from its summary",
            )


def review(kit, evidence):
    verifier = Review(kit, evidence)
    require(
        verifier.candidate.get("scope_id") == "M13-ARM-ORIGINAL-v1"
        and verifier.candidate.get("required_runtime_identity") is True
        and tuple(required_pythons(verifier.candidate)) == ("3.10", "3.12"),
        "This supplemental review requires the exact original M13 scope",
    )
    core_review = verifier.validate()
    require(
        core_review["technical_receipts_consistent"] is True,
        "Frozen full review did not pass",
    )
    cells = []
    for minor in required_pythons(verifier.candidate):
        base = PurePosixPath(f"py{minor}-all-latest/python-1-all-latest")
        measurements = base / "measurements"
        summary = verifier.json(str(measurements / "summary.json"))
        protocol = verifier.json(str(measurements / "protocol.json"))
        require(
            summary["protocol"] == protocol,
            "Measurement summary embeds a different protocol",
        )
        bounded = verifier.json(str(measurements / "bounded-limit.json"))
        observations = check_measurements(summary, bounded)
        require(
            protocol["python"].startswith(minor + ".")
            and protocol["machine"] == "aarch64",
            "Measurement protocol records another actual interpreter",
        )
        require(
            protocol["resource_measurement_contract"]["platform"] == "linux",
            "Measurement protocol did not declare the Linux resource contract",
        )
        check_scale_receipts(verifier, measurements, summary, minor)
        faults_base = base / "consumer-faults"
        faults = verifier.json(str(faults_base / "fault-checks.json"))
        fault_result = check_faults(faults)
        check_environment(faults["environment"], minor, consumer=True)
        app = verifier.json(str(faults_base / "app-manifest.json"))
        require(
            app["status"] == "PASS" and isinstance(app["files"], list) and app["files"],
            "Consumer fault file inventory is missing",
        )
        names = [r["path"] for r in app["files"]]
        require(
            len(names) == len(set(names)), "Consumer fault inventory repeats a file"
        )
        for record in app["files"]:
            name = PurePosixPath(record["path"])
            require(
                not name.is_absolute()
                and ".." not in name.parts
                and "\\" not in record["path"],
                "Consumer fault inventory path differs",
            )
            path = verifier.file(str(faults_base / name), record["sha256"])
            require(
                path.stat().st_size == record["size_bytes"],
                "Consumer fault file size differs",
            )
        cells.append(
            {
                "minor": minor,
                "measurements": observations,
                "fault_checks": fault_result,
                "fault_inventory_files_verified": len(app["files"]),
            }
        )
    return {
        "schema": "equiframe.m13-supplemental-review.v1",
        "technical_receipts_consistent": True,
        "frozen_review": core_review,
        "python_cells": cells,
        "review_tool_sha256": sha(Path(__file__)),
        "candidate_manifest_sha256": sha(kit / "candidate.json"),
        "measurement_trials": 12,
        "consumer_fault_cases": 12,
        "criteria_automatically_closed": [],
        "independent_human_acceptance": False,
        "scope": "Offline exact inventory, original bounded measurements and synthetic consumer recovery; no new runtime execution, SLO or scientific acceptance",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kit", "evidence", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Preserve earlier supplemental reviews")
    try:
        result, code = review(args.kit.resolve(), args.evidence.resolve()), 0
    except Exception as error:  # noqa: BLE001 - failures never become closure
        result, code = (
            {
                "technical_receipts_consistent": False,
                "error": type(error).__name__,
                "reason": str(error),
                "criteria_automatically_closed": [],
            },
            1,
        )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
