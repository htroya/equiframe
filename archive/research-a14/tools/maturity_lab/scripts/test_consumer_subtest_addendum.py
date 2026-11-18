"""Counterexamples for the narrowly scoped subtest interpretation, not SDK coverage."""

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from consumer_subtest_addendum import CONSUMER_MANIFEST, CONSUMER_SDIST, interpret


class ConsumerSubtestInterpretation(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(Path(__file__).with_name("consumer-subtests-manifest.json").read_text("utf-8"))
        self.root = ET.Element("testsuites")
        self.suite = ET.SubElement(self.root, "testsuite", tests="34", failures="0", errors="0", skipped="0")
        for item in self.manifest["tests"]:
            ET.SubElement(self.suite, "testcase", **item)
        self.provenance = {"scope": "consumer", "pytest": "9.1.1", "consumer_sdist_sha256": CONSUMER_SDIST, "consumer_manifest_sha256": CONSUMER_MANIFEST, "plugin_autoload_disabled": True}
        self.log = "................... [100%]\n19 passed, 15 subtests passed in 9.30s\n"

    def run_interpretation(self):
        return interpret(self.root, self.manifest, self.log, self.provenance)

    def test_explained_events_preserve_original_xml(self):
        before = ET.tostring(self.root)
        result = self.run_interpretation()
        self.assertEqual(result["unique_testcase_parents"], 19)
        self.assertEqual(result["passing_subtest_events"], 15)
        self.assertEqual(ET.tostring(self.root), before)

    def test_arbitrary_count_delta_is_rejected(self):
        self.suite.set("tests", "35")
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.run_interpretation()

    def test_missing_original_case_is_rejected(self):
        self.suite.remove(self.suite[-1])
        with self.assertRaises(ValueError):
            self.run_interpretation()

    def test_substituted_or_repeated_identity_is_rejected(self):
        self.suite[-1].set("name", self.suite[-2].get("name"))
        with self.assertRaisesRegex(ValueError, "identities"):
            self.run_interpretation()

    def test_actual_failure_cannot_hide_behind_zero_summary(self):
        ET.SubElement(self.suite[-1], "failure", message="regression")
        with self.assertRaises(ValueError):
            self.run_interpretation()

    def test_missing_or_negative_subtest_log_is_rejected(self):
        for log in ("19 passed in 9.3s", "19 passed, 15 subtests passed in 9.3s\n1 subtests failed"):
            with self.subTest(log=log):
                self.log = log
                with self.assertRaises(ValueError):
                    self.run_interpretation()

    def test_unknown_source_or_producer_is_rejected(self):
        for key, value in (("scope", "benchmark"), ("pytest", "9.0.2"), ("consumer_sdist_sha256", "0" * 64), ("plugin_autoload_disabled", False)):
            with self.subTest(key=key):
                original = self.provenance[key]
                self.provenance[key] = value
                with self.assertRaises(ValueError):
                    self.run_interpretation()
                self.provenance[key] = original


if __name__ == "__main__":
    unittest.main()
