"""Synthetic unit fixtures for the handoff tooling, never observations from the VM."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from check_benchmark_profile import requirements
from run_vm_lab import Recorder, sha, verify_kit
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


if __name__ == "__main__":
    unittest.main()
