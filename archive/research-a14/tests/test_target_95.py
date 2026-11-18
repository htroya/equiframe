"""Protect source-bound percentages against score inflation and stale identities."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "target_95", Path(__file__).resolve().parents[1] / "tools/target_95.py"
)
assert SPEC is not None and SPEC.loader is not None
target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target)


class TargetGapTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "receipt.json"
        self.write_source()
        self.metric = {
            "key": "option_traceability",
            "aspect": "Options",
            "rubric": "FIXED",
            "numerator": 4298,
            "denominator": 8385,
            "percent": 4298 / 8385 * 100,
            "assessed_candidate": "0.12.0a13",
            "record_targets_current_a13": True,
            "source": "receipt.json",
            "source_sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
        }
        self.matrix = {
            "schema": "equiframe.project-status-matrix.v1",
            "overall_percentage": None,
            "current_package_versions": {"equiframe": "0.12.0a13"},
            "metrics": [self.metric]
            + [
                {
                    "key": key,
                    "aspect": key,
                    "percent": None,
                    "numerator": None,
                    "denominator": None,
                }
                for key in sorted(target.AREA_KEYS - {"option_traceability"})
            ],
        }

    def write_source(self, candidate="0.12.0a13", n=4298, d=8385):
        counts = {"verified": n, "total": d}
        self.source.write_text(
            json.dumps(
                {
                    "candidate": candidate,
                    "current_option_traceability": {
                        "normal": counts,
                        "optimized": counts,
                    },
                }
            ),
            encoding="utf-8",
        )

    def assess(self, threshold=Decimal(95)):
        path = self.root / "matrix.json"
        path.write_text(json.dumps(self.matrix), encoding="utf-8")
        return target.assess(self.root, path, threshold)

    def test_95_requires_7966_obligations_without_rounding_down(self):
        result = self.assess()
        row = result["metrics"][0]
        self.assertEqual(row["required_numerator"], 7966)
        self.assertEqual(row["additional_obligations"], 3668)
        self.assertFalse(result["all_targets_met"])

    def test_history_does_not_pass_current_candidate_gate(self):
        self.metric.update(
            numerator=12,
            denominator=12,
            percent=100,
            assessed_candidate="0.12.0a12",
            record_targets_current_a13=False,
        )
        self.write_source("0.12.0a12", 12, 12)
        self.metric["source_sha256"] = hashlib.sha256(
            self.source.read_bytes()
        ).hexdigest()
        row = self.assess()["metrics"][0]
        self.assertEqual(row["last_recorded_percent"], 100)
        self.assertIsNone(row["current_candidate_percent"])
        self.assertFalse(row["target_met"])

    def test_missing_measurement_is_neither_zero_nor_target(self):
        self.metric.update(numerator=None, denominator=None, percent=None)
        row = self.assess()["metrics"][0]
        self.assertIsNone(row["last_recorded_percent"])
        self.assertIsNone(row["required_numerator"])
        self.assertFalse(row["target_met"])

    def test_tampered_source_is_rejected(self):
        self.source.write_text('{"candidate":"modified"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            self.assess()

    def test_wrong_arithmetic_is_rejected(self):
        self.metric["percent"] = 95
        with self.assertRaisesRegex(ValueError, "disagrees"):
            self.assess()

    def test_duplicate_metric_is_rejected(self):
        self.matrix["metrics"].append(self.metric)
        with self.assertRaisesRegex(ValueError, "duplicate metric"):
            self.assess()

    def test_outside_evidence_is_rejected(self):
        self.metric["source"] = "../receipt.json"
        with self.assertRaisesRegex(ValueError, "outside repository"):
            self.assess()

    def test_false_current_version_is_rejected(self):
        self.matrix["current_package_versions"]["equiframe"] = "0.12.0a14"
        with self.assertRaisesRegex(ValueError, "Historical candidate"):
            self.assess()

    def test_pair_identity_requires_both_candidates(self):
        versions = {"equiframe": "0.12.0a13", "equiframe-benchmark": "0.12.0a13"}
        self.matrix["current_package_versions"] = versions
        for benchmark, accepted in [("0.12.0a13", True), ("0.12.0a12", False)]:
            self.write_source(
                {"equiframe": "0.12.0a13", "equiframe-benchmark": benchmark}
            )
            self.metric["source_sha256"] = hashlib.sha256(
                self.source.read_bytes()
            ).hexdigest()
            if accepted:
                self.assertEqual(self.assess()["metrics"][0]["candidate"], "0.12.0a13")
            else:
                with self.assertRaisesRegex(ValueError, "Candidate pair"):
                    self.assess()

    def test_consistent_but_invented_matrix_score_is_rejected(self):
        self.metric.update(numerator=8385, percent=100)
        with self.assertRaisesRegex(ValueError, "Counts differ"):
            self.assess()

    def test_source_without_candidate_cannot_prove_a_current_score(self):
        source = json.loads(self.source.read_text(encoding="utf-8"))
        del source["candidate"]
        self.source.write_text(json.dumps(source), encoding="utf-8")
        self.metric["source_sha256"] = hashlib.sha256(
            self.source.read_bytes()
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "missing a candidate"):
            self.assess()

    def test_removing_an_unmeasured_area_is_rejected(self):
        self.matrix["metrics"].pop()
        with self.assertRaisesRegex(ValueError, "nine original"):
            self.assess()

    def test_fabricated_global_average_is_rejected(self):
        self.matrix["overall_percentage"] = 95
        with self.assertRaisesRegex(ValueError, "aggregate rubric"):
            self.assess()

    def test_invalid_counts_are_rejected(self):
        for n, d in [(True, 20), (2, 0), (21, 20), (-1, 20), (1, None)]:
            with self.subTest(n=n, d=d):
                self.metric.update(numerator=n, denominator=d)
                with self.assertRaisesRegex(ValueError, "Invalid counts"):
                    self.assess()

    def test_invalid_target_is_rejected(self):
        for value in ("NaN", "Infinity", "0", "101"):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "Target"),
            ):
                self.assess(Decimal(value))

    def test_duplicate_json_and_nonfinite_are_rejected(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}'):
            self.source.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                target._read(self.source)


if __name__ == "__main__":
    unittest.main()
