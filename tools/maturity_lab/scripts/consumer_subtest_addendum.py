"""Narrow offline interpretation for pytest 9.1.1's frozen consumer subtests.

Never changes a kit, XML, log or original receipt. The original complete
review remains the authority for every other contract and file hash.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

import validate_vm_receipts as frozen
from frozen_tests import verify_linux_junit

CONSUMER_SDIST = "ebecd34b85d9922bc015421842f64ff980329660f33b41af1a93e7408f087393"
CONSUMER_MANIFEST = "5e6846208e489598424825228276233fcefcb2af2e6246d1691e6b0ebed0e081"
PARENTS = {
    ("tests.test_domain_checks.DomainChecks", "test_three_domains_preserve_negative_meaning_and_publication"): 9,
    ("tests.test_external_extension.ExternalExtensionTests", "test_external_native_projection_good_difference_and_invalid"): 3,
    ("tests.test_external_extension.ExternalExtensionTests", "test_sqlite_existing_native_producer_runs_outside_checkout"): 3,
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def interpret(root, manifest, log, provenance):
    require(provenance == {"scope": "consumer", "pytest": "9.1.1", "consumer_sdist_sha256": CONSUMER_SDIST, "consumer_manifest_sha256": CONSUMER_MANIFEST, "plugin_autoload_disabled": True}, "Subtest provenance differs")
    require(manifest["pytest_version"] == "9.1.1" and manifest["test_count"] == 19, "Frozen producer/count differs")
    cases = list(root.iter("testcase"))
    observed = {(case.get("classname"), case.get("name")) for case in cases}
    require(len(cases) == 19 and set(PARENTS).issubset(observed), "Frozen subtest parents absent")
    require(root.tag == "testsuites" and len(root) == 1 and next(iter(root)).tag == "testsuite", "Require exact pytest single-suite envelope")
    suite = next(iter(root))
    require({key: suite.get(key) for key in ("tests", "failures", "errors", "skipped")} == {"tests": "34", "failures": "0", "errors": "0", "skipped": "0"}, "Require exactly 19 parents plus 15 passing subtest events")
    require(len(re.findall(r"^19 passed, 15 subtests passed in [0-9.]+s\s*$", log, re.MULTILINE)) == 1, "Actual pytest subtest summary differs")
    require(not re.search(r"\b[1-9][0-9]* (?:failed|error|errors|skipped|xfailed|xpassed|subtests failed|subtests skipped)\b", log), "Nonpassing pytest outcomes cannot be hidden")
    normalized = copy.deepcopy(root)
    next(iter(normalized)).set("tests", "19")
    verify_linux_junit(normalized, manifest, "consumer")
    return {"raw_declared_tests": 34, "unique_testcase_parents": 19, "passing_subtest_events": 15, "pytest_version": "9.1.1", "source_parents": [{"classname": key[0], "name": key[1], "events": value} for key, value in sorted(PARENTS.items())], "original_xml_unchanged": True}


class AddendumReview(frozen.Review):
    def __init__(self, kit, evidence):
        super().__init__(kit, evidence)
        self.addenda = []

    def junit(self, path, minimum, label=None):
        try:
            return super().junit(path, minimum, label)
        except ValueError as error:
            if label != "consumer" or str(error) != "JUnit summary differs from testcase outcomes":
                raise
        binding = self.candidate["test_manifests"]["consumer"]
        require(self.candidate["artifact_hashes"]["consumer_sdist"] == CONSUMER_SDIST and binding["sha256"] == CONSUMER_MANIFEST, "Require frozen original consumer")
        entries = [entry for entry in self.receipt["commands"] if entry["label"].startswith("consumer-suite-") and "--junitxml" in entry["command"] and self.relative(entry["command"][entry["command"].index("--junitxml") + 1]) == path]
        require(len(entries) == 1, "JUnit must match one original consumer-suite command")
        entry = entries[0]
        command = entry["command"]
        require(entry["status"] == "passed" and entry["exit_code"] == entry["expected_exit"] == 0, "Actual producer command failed")
        frozen.require_command_contract(command, ("-m", "pytest"), flags=("-I", "-q"), pairs=(("-p", "_hypothesis_pytestplugin"),), forbidden=("-n", "--numprocesses", "--dist"))
        lock_name = str(PurePosixPath(path).parent / "test-tools.lock")
        lock = self.file(lock_name)
        require(re.search(r"^pytest==9\.1\.1(?:\s|$)", lock.read_text("utf-8"), re.MULTILINE), "Actual pytest lock differs")
        log_path = self.file(entry["log"], entry["log_sha256"])
        xml = self.file(path)
        result = interpret(ET.parse(xml).getroot(), self.test_manifests["consumer"], log_path.read_text("utf-8"), {"scope": "consumer", "pytest": "9.1.1", "consumer_sdist_sha256": CONSUMER_SDIST, "consumer_manifest_sha256": CONSUMER_MANIFEST, "plugin_autoload_disabled": self.test_manifests["consumer"]["plugin_autoload_disabled"]})
        self.addenda.append({**result, "xml": path, "xml_sha256": frozen.sha(xml), "log": entry["log"], "log_sha256": frozen.sha(log_path), "tool_lock": lock_name, "tool_lock_sha256": frozen.sha(lock), "command": command, "consumer_manifest_sha256": binding["sha256"], "consumer_sdist_sha256": CONSUMER_SDIST})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Preserve prior receipt reviews")
    code = 0
    try:
        review = AddendumReview(args.kit.resolve(), args.evidence.resolve())
        result = review.validate()
        result.update(schema="equiframe.consumer-pytest-subtests-addendum.v1", subtest_interpretations=review.addenda, original_kit_and_receipts_unchanged=True, addendum_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    except Exception as error:  # noqa: BLE001 - any unexpected error rejects this offline review
        result, code = {"technical_receipts_consistent": False, "error": type(error).__name__, "reason": str(error), "criteria_automatically_closed": []}, 1
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
