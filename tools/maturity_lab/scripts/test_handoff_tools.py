"""Synthetic unit fixtures for the handoff tooling, never observations from the VM."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from check_benchmark_profile import requirements
from measure_maturity import observed_filesystem
from run_vm_lab import Recorder, sha, verify_kit, write_runtime_constraints
from validate_vm_receipts import Review, member


class HandoffToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def file(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def review(self):
        review = Review.__new__(Review)
        review.evidence = self.root
        review.inventory = {
            p.relative_to(self.root).as_posix(): {"sha256": sha(p), "size_bytes": p.stat().st_size}
            for p in self.root.rglob("*")
            if p.is_file()
        }
        return review

    def test_member_rejects_traversal_even_when_target_exists(self):
        self.file("nested/value", "synthetic")
        with self.assertRaises(ValueError):
            member(self.root, "nested/../nested/value")

    def test_member_rejects_absolute_member(self):
        path = self.file("value", "synthetic")
        with self.assertRaises(ValueError):
            member(self.root, str(path))

    def test_member_accepts_inventory_file(self):
        path = self.file("value", "synthetic")
        self.assertEqual(member(self.root, "value"), path)

    def test_required_file_must_be_in_inventory(self):
        self.file("value", "synthetic")
        review = self.review()
        self.file("late-file", "unrecorded")
        with self.assertRaisesRegex(ValueError, "not inventoried"):
            review.file("late-file")

    def test_inventory_detects_changed_bytes(self):
        path = self.file("value", "original")
        review = self.review()
        path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "differs"):
            review.file("value")

    def test_independent_receipt_hash_is_checked(self):
        self.file("value", "original")
        with self.assertRaisesRegex(ValueError, "digest differs"):
            self.review().file("value", "0" * 64)

    def test_absent_commands_do_not_establish_a_pass(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            self.review().commands([], {"install"})

    def test_duplicate_command_labels_do_not_establish_a_pass(self):
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.review().commands([{"label": "install"}, {"label": "install"}], {"install"})

    def test_timeout_cannot_pass_even_with_null_expected_exit(self):
        with self.assertRaisesRegex(ValueError, "timed-out"):
            self.review().commands(
                [
                    {
                        "label": "install",
                        "status": "timeout",
                        "exit_code": None,
                        "expected_exit": None,
                    }
                ],
                {"install"},
            )

    def test_junit_cannot_hide_a_skip(self):
        self.file(
            "suite.xml",
            '<testsuite tests="1"><testcase name="synthetic"><skipped/></testcase></testsuite>',
        )
        with self.assertRaisesRegex(ValueError, "skipped"):
            self.review().junit("suite.xml", 1)

    def test_junit_cannot_hide_missing_cases(self):
        self.file("suite.xml", '<testsuite tests="1"><testcase name="synthetic"/></testsuite>')
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.review().junit("suite.xml", 2)

    def test_junit_rejects_declared_count_drift(self):
        self.file("suite.xml", '<testsuite tests="2"><testcase name="synthetic"/></testsuite>')
        with self.assertRaisesRegex(ValueError, "count"):
            self.review().junit("suite.xml", 1)

    def test_junit_accepts_complete_synthetic_fixture_without_claiming_vm(self):
        self.file("suite.xml", '<testsuite tests="1"><testcase name="synthetic"/></testsuite>')
        self.review().junit("suite.xml", 1)

    def test_candidate_changed_member_is_rejected(self):
        path = self.file("payload", "initial")
        manifest = {
            "schema": "equiframe-maturity-candidate-1",
            "files": {"payload": {"sha256": sha(path), "size_bytes": path.stat().st_size}},
        }
        self.file("candidate.json", json.dumps(manifest))
        path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash/size"):
            verify_kit(self.root)

    def test_recorder_retains_expected_nonzero(self):
        receipt = {"commands": []}
        record = Recorder(self.root, receipt)
        record.run(
            "synthetic-rejection", [sys.executable, "-I", "-c", "raise SystemExit(3)"], expected=3
        )
        self.assertEqual(receipt["commands"][0]["exit_code"], 3)
        self.assertEqual(receipt["commands"][0]["status"], "passed")
        self.assertEqual(
            sha(self.root / receipt["commands"][0]["log"]), receipt["commands"][0]["log_sha256"]
        )

    def test_recorder_retains_unexpected_nonzero(self):
        receipt = {"commands": []}
        record = Recorder(self.root, receipt)
        with self.assertRaises(RuntimeError):
            record.run("synthetic-failure", [sys.executable, "-I", "-c", "raise SystemExit(2)"])
        self.assertEqual(receipt["commands"][0]["status"], "failed")
        self.assertEqual(receipt["commands"][0]["exit_code"], 2)

    def test_recorder_retains_timeout_as_unknown_exit(self):
        receipt = {"commands": []}
        record = Recorder(self.root, receipt)
        with self.assertRaises(subprocess.TimeoutExpired):
            record.run(
                "synthetic-timeout",
                [sys.executable, "-I", "-c", "import time; time.sleep(30)"],
                timeout=0.05,
            )
        self.assertEqual(receipt["commands"][0]["status"], "timeout")
        self.assertIsNone(receipt["commands"][0]["exit_code"])

    def wheel(self, name, metadata):
        path = self.root / (name + ".whl")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(name + ".dist-info/METADATA", metadata)
        return path

    def test_benchmark_runtime_markers_follow_actual_target(self):
        core = self.wheel(
            "core",
            "Name: equiframe\nVersion: 0.12.0a8\n"
            'Requires-Dist: pyarrow>=20; extra == "arrow"\n'
            'Requires-Dist: scikit-learn>=1.7; extra == "ml"\n\n',
        )
        benchmark = self.wheel(
            "benchmark",
            "Name: equiframe-benchmark\nVersion: 0.12.0a8\n"
            "Requires-Dist: equiframe[arrow]==0.12.0a8\n"
            'Requires-Dist: equiframe[ml]==0.12.0a8; extra == "ml"\n'
            'Requires-Dist: tomli>=2.2; python_version < "3.11"\n\n',
        )
        self.assertEqual(
            requirements(core, benchmark, "ml", {"python_version": "3.10"}),
            ["pyarrow>=20", "scikit-learn>=1.7", "tomli>=2.2"],
        )
        self.assertEqual(
            requirements(core, benchmark, "base", {"python_version": "3.12"}), ["pyarrow>=20"]
        )

    def test_cloud_validation_receipt_is_never_vm_evidence(self):
        review = self.review()
        review.candidate = {}
        review.receipt = {
            "schema": "equiframe-maturity-vm-execution-1",
            "cloud_validation_only": True,
        }
        with self.assertRaisesRegex(ValueError, "not evidence"):
            review.validate()

    def test_different_candidate_receipt_is_rejected(self):
        self.file("candidate.json", "{}")
        review = self.review()
        review.kit = self.root
        review.candidate = {}
        review.receipt = {
            "schema": "equiframe-maturity-vm-execution-1",
            "cloud_validation_only": False,
            "candidate_manifest_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(ValueError, "another candidate"):
            review.validate()

    def test_runtime_constraints_keep_pins_without_implicit_hash_mode(self):
        path = self.root / "constraints.txt"
        write_runtime_constraints(path, {"typing-extensions": "4.15.0", "numpy": "2.2.6"})
        self.assertEqual(path.read_text(), "numpy==2.2.6\ntyping-extensions==4.15.0\n")
        self.assertNotIn("--hash", path.read_text())

    def test_runtime_constraints_reject_non_version_input(self):
        with self.assertRaises(ValueError):
            write_runtime_constraints(self.root / "constraints", {"numpy": "2.2.6\nother==1"})

    def test_runtime_constraints_reject_empty_resolution(self):
        with self.assertRaises(ValueError):
            write_runtime_constraints(self.root / "constraints", {})

    def test_measurement_uses_deepest_observed_mount(self):
        mounts = "1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /tmp rw - tmpfs tmpfs rw\n"
        with patch.object(Path, "read_text", return_value=mounts):
            self.assertEqual(observed_filesystem(Path("/tmp/measurement")), "tmpfs")
            self.assertEqual(observed_filesystem(Path("/workspace/measurement")), "overlay")

    def test_measurement_decodes_mount_path_escapes(self):
        mounts = (
            "1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /test\\040path rw - tmpfs tmpfs rw\n"
        )
        with patch.object(Path, "read_text", return_value=mounts):
            self.assertEqual(observed_filesystem(Path("/test path/measurement")), "tmpfs")

    def test_unknown_measurement_mount_fails_closed(self):
        with (
            patch.object(Path, "read_text", return_value="unusable mount line\n"),
            self.assertRaisesRegex(RuntimeError, "not found"),
        ):
            observed_filesystem(self.root)

    def test_unreadable_measurement_mount_fails_closed(self):
        with (
            patch.object(Path, "read_text", side_effect=PermissionError("synthetic denial")),
            self.assertRaisesRegex(RuntimeError, "Cannot observe"),
        ):
            observed_filesystem(self.root)

    def synthetic_consumer_case(self):
        # Deliberately fabricated UNIT DATA; never a VM execution receipt.
        return {
            "synthetic_unit_fixture": True,
            "program": "reconciliation",
            "variant": "good",
            "direction": "pandas->duckdb",
            "observed_exit_code": 0,
            "expected_exit_code": 0,
            "status": "PASS",
            "accepted": True,
            "published": True,
            "evidence_integrity_verified": True,
            "portable_verified_without_native_origin": True,
            "frozen_data_unchanged": True,
            "native_execution_count_complete": True,
            "dataset_manifest_sha256": "a" * 64,
            "native_result": {"executions": [{"engine": "pandas"}, {"engine": "duckdb"}]},
            "environment": {
                "python": "3.10.0 synthetic fixture",
                "machine": "aarch64",
                "isolated": 1,
                "optimized": 1,
            },
        }

    def case_review(self, case):
        self.file("case.json", json.dumps(case))
        review = self.review()
        review.candidate = {"files": {"consumer-data/manifest.json": {"sha256": "a" * 64}}}
        return review

    def test_synthetic_case_validator_checks_positive_structure_only(self):
        review = self.case_review(self.synthetic_consumer_case())
        review.consumer_case(
            "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb", optimized=True
        )

    def test_consumer_unknown_native_count_cannot_pass(self):
        case = self.synthetic_consumer_case()
        case["native_execution_count_complete"] = False
        with self.assertRaisesRegex(ValueError, "coverage missing"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )

    def test_consumer_peer_is_not_an_independent_second_engine(self):
        case = self.synthetic_consumer_case()
        case["native_result"]["executions"] = [{"engine": "pandas"}, {"engine": "pandas"}]
        with self.assertRaisesRegex(ValueError, "independent native"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )

    def test_consumer_different_dataset_cannot_pass(self):
        case = self.synthetic_consumer_case()
        case["dataset_manifest_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "different frozen dataset"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )

    def test_consumer_optimized_flag_must_be_observed(self):
        case = self.synthetic_consumer_case()
        case["environment"]["optimized"] = 0
        with self.assertRaisesRegex(ValueError, "optimized"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb", optimized=True
            )

    def test_consumer_expected_rejections_remain_rejections(self):
        for variant, expected in (("defect", 1), ("not_evaluable", 3)):
            with self.subTest(variant=variant):
                case = self.synthetic_consumer_case()
                case.update(
                    variant=variant,
                    observed_exit_code=expected,
                    expected_exit_code=expected,
                    status="EXPECTED_REJECTION",
                    accepted=False,
                    published=False,
                )
                self.case_review(case).consumer_case(
                    "case.json", "3.10", "reconciliation", variant, "pandas", "duckdb"
                )
                case["published"] = True
                with self.assertRaisesRegex(ValueError, "acceptance/publication"):
                    self.case_review(case).consumer_case(
                        "case.json", "3.10", "reconciliation", variant, "pandas", "duckdb"
                    )

    def test_consumer_x64_cannot_establish_arm64_pass(self):
        case = self.synthetic_consumer_case()
        case["environment"]["machine"] = "x86_64"
        with self.assertRaisesRegex(ValueError, "Python/platform/isolation"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )


if __name__ == "__main__":
    unittest.main()
