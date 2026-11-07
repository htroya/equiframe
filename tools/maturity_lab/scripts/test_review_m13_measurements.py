"""Reject misleading supplemental summaries; these are not SDK test receipts."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from review_m13_measurements import (
    METRICS,
    check_environment,
    check_faults,
    check_measurements,
    check_scale_receipts,
)
from validate_vm_receipts import Review, sha


def complete_fixture():
    protocol = {
        "rows": [100, 1000],
        "width": 2,
        "repetitions": 3,
        "rss_budget_bytes": 512 * 1024**2,
        "disk_budget_bytes": 64 * 1024**2,
        "timeout_seconds": 120,
        "threads_per_engine": 1,
        "expected_state": "different",
        "storage": "disk",
        "slo_accepted": False,
        "filesystem_observation": {"storage": "disk"},
    }
    result = {
        "complete": True,
        "resource_measurement_complete": True,
        "issues": [],
        "resource_quality": ["complete"] * 3,
        "requested_repetitions": 3,
        "observed_repetitions": 3,
        "correct_complete_repetitions": 3,
        "unsuccessful_or_missing_repetitions": 0,
        "resource_measurement_contract": {
            "id": "equiframe_process_resources_v1",
            "platform": "linux",
            "metrics": [
                {"metric": m, "state": "observed", "source": "fixture", "reason": None}
                for m in METRICS
            ],
        },
        "process": {
            "termination_reason": "exited",
            "exit_code": 0,
            "monitoring_errors": [],
            "cleanup_reaped": True,
            "sample_count": 10,
            **dict.fromkeys(METRICS, 1),
        },
    }
    result["process"].update(
        measurement_contract="equiframe_process_resources_v1",
        measurement_platform="linux",
        metric_coverage=copy.deepcopy(
            result["resource_measurement_contract"]["metrics"]
        ),
        wall_seconds=1.0,
    )
    results = [
        {**copy.deepcopy(result), "case_id": "maturity-" + str(size)}
        for size in (100, 1000)
    ]
    return {"protocol": protocol, "results": results}, {
        "state": "not_evaluable",
        "complete": False,
    }


class SupplementalContraChecks(unittest.TestCase):
    def test_actual_scale_files_bind_all_trials_and_summary_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            summary, _ = complete_fixture()
            environment = {
                "python": "3.12.15",
                "machine": "aarch64",
                "system": "Linux",
                "equiframe": "0.12.0a13",
                "equiframe-benchmark": "0.12.0a13",
            }

            def write(name, value):
                path = evidence / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
                return {
                    "path": path.name,
                    "sha256": sha(path),
                    "size_bytes": path.stat().st_size,
                }

            for result, rows in zip(summary["results"], (100, 1000), strict=True):
                result["run_id"] = "verified-run"
                root = PurePosixPath("measurements") / f"rows-{rows}" / "verified-run"
                options = {
                    "max_rows": 2000,
                    "max_disk_bytes": 32 * 1024**2,
                    "timeout_seconds": 60,
                }
                spec = {
                    "case_id": result["case_id"],
                    "rows": rows,
                    "repetitions": 3,
                    "width": 2,
                    "difference_last": True,
                    "timeout_seconds": 120,
                    "rss_budget_bytes": 512 * 1024**2,
                    "disk_budget_bytes": 64 * 1024**2,
                    "comparison_options": options,
                }
                digest = hashlib.sha256(
                    json.dumps(
                        spec,
                        sort_keys=True,
                        ensure_ascii=True,
                        allow_nan=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                spec_record = write(root / "spec.json", spec)
                trials = [
                    {
                        "case_sha256": digest,
                        "repetition": n,
                        "comparison": {
                            "complete": True,
                            "state": "different",
                            "counts": {"left_rows": rows, "right_rows": rows},
                            "options": options,
                        },
                        "resources": {"state": "complete"},
                    }
                    for n in range(3)
                ]
                records = [
                    write(root / "worker" / f"trial-{n:03d}.json", trial)
                    for n, trial in enumerate(trials)
                ]
                write(
                    root / "worker/worker-completed.json",
                    {
                        "case_sha256": digest,
                        "environment": environment,
                        "trial_files": records,
                    },
                )
                raw_record = write(
                    root / "scale.json",
                    {
                        "run_id": "verified-run",
                        "spec": spec,
                        "spec_sha256": digest,
                        "process": result["process"],
                        "issues": [],
                        "worker_finalized": True,
                        "environment_origin": "worker",
                        "producer_runtime_matches_parent": True,
                        "environment": environment,
                        "evidence": [spec_record],
                        "trials": trials,
                    },
                )
                write(root / "finished.json", {"complete": True, "result": raw_record})
            verifier = Review.__new__(Review)
            verifier.evidence = evidence
            verifier.inventory = {
                p.relative_to(evidence).as_posix(): {
                    "sha256": sha(p),
                    "size_bytes": p.stat().st_size,
                }
                for p in evidence.rglob("*")
                if p.is_file()
            }
            check_scale_receipts(
                verifier, PurePosixPath("measurements"), summary, "3.12"
            )
            changed = copy.deepcopy(summary)
            changed["results"][0]["process"]["sample_count"] += 1
            with self.assertRaises(ValueError):
                check_scale_receipts(
                    verifier, PurePosixPath("measurements"), changed, "3.12"
                )
            with self.assertRaises(ValueError):
                check_scale_receipts(
                    verifier, PurePosixPath("measurements"), summary, "3.10"
                )
            (
                evidence / "measurements/rows-100/verified-run/worker/trial-002.json"
            ).unlink()
            with self.assertRaises(ValueError):
                check_scale_receipts(
                    verifier, PurePosixPath("measurements"), summary, "3.12"
                )

    def test_consumer_environment_requires_actual_optimized_versions(self):
        environment = {
            "python": "3.12.15",
            "machine": "aarch64",
            "isolated": 1,
            "optimized": 1,
            "dependencies": {
                "equiframe": "0.12.0a13",
                "equiframe_consumer_lab": "0.1.15",
            },
        }
        check_environment(environment, "3.12", consumer=True)
        for key, value in (("isolated", True), ("optimized", 0), ("machine", "x86_64")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_environment({**environment, key: value}, "3.12", consumer=True)

    def test_complete_flag_cannot_hide_one_missing_repetition(self):
        summary, bounded = complete_fixture()
        summary["results"][0]["observed_repetitions"] = 2
        with self.assertRaises(ValueError):
            check_measurements(summary, bounded)

    def test_linux_platform_cannot_excuse_one_unobserved_counter(self):
        summary, bounded = complete_fixture()
        summary["results"][0]["resource_measurement_contract"]["metrics"][0].update(
            state="unavailable_on_platform", source=None, reason="fixture"
        )
        with self.assertRaises(ValueError):
            check_measurements(summary, bounded)

    def test_named_nine_metrics_cannot_hide_duplicate_and_omission(self):
        summary, bounded = complete_fixture()
        metrics = summary["results"][0]["resource_measurement_contract"]["metrics"]
        metrics[-1] = copy.deepcopy(metrics[0])
        with self.assertRaises(ValueError):
            check_measurements(summary, bounded)

    def test_bool_cannot_be_numeric_counter(self):
        summary, bounded = complete_fixture()
        summary["results"][0]["process"][METRICS[0]] = True
        with self.assertRaises(ValueError):
            check_measurements(summary, bounded)

    def test_complete_flag_cannot_hide_limit_converted_to_equivalence(self):
        summary, bounded = complete_fixture()
        bounded["state"] = "equivalent"
        with self.assertRaises(ValueError):
            check_measurements(summary, bounded)

    def test_pass_cannot_hide_missing_fault_checks(self):
        with self.assertRaises(ValueError):
            check_faults({"status": "PASS", "synthetic_fixture": True, "checks": []})

    def test_summary_cannot_replace_different_process_coverage(self):
        summary, bounded = complete_fixture()
        summary["results"][0]["process"]["measurement_platform"] = "windows"
        with self.assertRaises(ValueError):
            check_measurements(summary, bounded)

    def test_complete_flag_cannot_hide_observed_budget_overshoot(self):
        for metric, value in (
            ("sampled_rss_peak_bytes", 512 * 1024**2 + 1),
            ("disk_apparent_peak_bytes", 64 * 1024**2 + 1),
            ("disk_allocated_peak_bytes", 64 * 1024**2 + 1),
            ("wall_seconds", 121),
        ):
            with self.subTest(metric=metric):
                summary, bounded = complete_fixture()
                summary["results"][0]["process"][metric] = value
                with self.assertRaises(ValueError):
                    check_measurements(summary, bounded)


if __name__ == "__main__":
    unittest.main()
