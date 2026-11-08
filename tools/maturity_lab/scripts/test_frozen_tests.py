"""Synthetic rejection tests; these fixtures never count as native execution evidence."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from frozen_tests import (
    candidate_manifests,
    linux_skips,
    read_manifest,
    verify_sdist_tests,
)
from run_vm_lab import sha
from validate_vm_receipts import Review


class FrozenTestsContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        content = b"# synthetic fixture\n"
        self.manifest = {
            "schema": "equiframe-test-manifest-1",
            "package": "equiframe",
            "plugin_autoload_disabled": True,
            "pytest_version": "9.1.1",
            "hypothesis_version": "6.168.3",
            "test_count": 2,
            "tests": [{"classname": "tests.test_sample", "name": name} for name in ("one", "two")],
            "files": {
                "tests/test_sample.py": {
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            },
        }
        self.sdist = self.root / "synthetic.tar.gz"
        with tarfile.open(self.sdist, "w:gz") as archive:
            item = tarfile.TarInfo("synthetic/tests/test_sample.py")
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))

    def tearDown(self):
        self.temporary.cleanup()

    def manifest_file(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return path

    def test_sdist_is_bound_to_all_frozen_test_bytes(self):
        manifest = read_manifest(self.manifest_file(), "core", 2)
        verify_sdist_tests(self.sdist, manifest)
        manifest["files"]["tests/test_sample.py"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "files differ"):
            verify_sdist_tests(self.sdist, manifest)

    def test_sdist_cannot_omit_a_frozen_test_file(self):
        self.manifest["files"]["tests/missing.py"] = {
            "sha256": "0" * 64,
            "size_bytes": 1,
        }
        with self.assertRaisesRegex(ValueError, "files differ"):
            verify_sdist_tests(self.sdist, self.manifest)

    def test_manifest_cannot_use_a_count_with_repeated_identities(self):
        self.manifest["tests"][1] = self.manifest["tests"][0]
        with self.assertRaisesRegex(ValueError, "repeated"):
            read_manifest(self.manifest_file(), "core", 2)

    def test_execution_requires_all_three_manifests_while_historic_review_is_preserved(
        self,
    ):
        self.assertEqual(candidate_manifests(self.root, {}), {})
        with self.assertRaisesRegex(ValueError, "all three"):
            candidate_manifests(self.root, {}, required=True)

    def review_junit(self, root, label, manifest):
        path = self.root / "suite.xml"
        ET.ElementTree(root).write(path)
        review = Review.__new__(Review)
        review.evidence = self.root
        review.inventory = {"suite.xml": {"sha256": sha(path), "size_bytes": path.stat().st_size}}
        review.test_manifests = {label: manifest}
        review.junit("suite.xml", manifest["test_count"], label)

    def test_core_exact_identities_reject_substitution_and_duplicates(self):
        root = ET.Element("testsuite", tests="2")
        for item in self.manifest["tests"]:
            ET.SubElement(root, "testcase", **item)
        self.review_junit(root, "core", self.manifest)
        for changed in ("other", "one"):
            with self.subTest(changed=changed):
                root[1].set("name", changed)
                with self.assertRaisesRegex(ValueError, "identities"):
                    self.review_junit(root, "core", self.manifest)

    def test_benchmark_requires_exact_linux_skip_identities_and_reasons(self):
        tests = [
            {"classname": classname, "name": name}
            for classname, name, _ in sorted(linux_skips("benchmark"))
        ]
        tests.append({"classname": "tests.test_sample", "name": "native"})
        manifest = {**self.manifest, "tests": tests, "test_count": len(tests)}
        root = ET.Element("testsuite", tests="3", skipped="2", failures="0", errors="0")
        for classname, name, reason in sorted(linux_skips("benchmark")):
            case = ET.SubElement(root, "testcase", classname=classname, name=name)
            ET.SubElement(case, "skipped", message=reason)
        ET.SubElement(root, "testcase", **tests[-1])
        self.review_junit(root, "benchmark", manifest)
        root[0][0].set("message", "arbitrary unavailable capability")
        with self.assertRaisesRegex(ValueError, "skips differ"):
            self.review_junit(root, "benchmark", manifest)

    def test_linux_contract_cannot_hide_failure_or_xfail(self):
        root = ET.Element("testsuite", tests="2")
        for item in self.manifest["tests"]:
            ET.SubElement(root, "testcase", **item)
        for outcome in ("failure", "error", "skipped"):
            with self.subTest(outcome=outcome):
                node = ET.SubElement(root[0], outcome, message="xfail")
                with self.assertRaises(ValueError):
                    self.review_junit(root, "core", self.manifest)
                root[0].remove(node)

    def test_linux_summary_cannot_hide_actual_outcomes(self):
        root = ET.Element("testsuite", tests="2", failures="1")
        for item in self.manifest["tests"]:
            ET.SubElement(root, "testcase", **item)
        with self.assertRaisesRegex(ValueError, "summary"):
            self.review_junit(root, "core", self.manifest)


if __name__ == "__main__":
    unittest.main()
