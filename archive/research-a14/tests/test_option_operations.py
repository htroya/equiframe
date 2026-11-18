import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "option_operations",
    Path(__file__).resolve().parents[1] / "tools/option_operations.py",
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def baseline():
    # Preserve the frozen cardinality/status arithmetic without importing private evidence.
    return [
        {"id": f"fixture-{i}", "status": "PASS" if i < 4298 else "NOT_RUN"}
        for i in range(8385)
    ]


class CoverageTests(unittest.TestCase):
    def test_existing_or_repeated_obligations_cannot_inflate_counts(self):
        rows = baseline()
        existing = {
            "case_id": "existing",
            "status": "PASS",
            "obligations": ["fixture-0"],
        }
        with self.assertRaisesRegex(ValueError, "previously unverified"):
            module.summarize(rows, [existing])
        new = {
            "case_id": "new",
            "status": "EXPECTED_REJECTION",
            "obligations": ["fixture-4298"],
        }
        repeated = {**new, "case_id": "another"}
        with self.assertRaisesRegex(ValueError, "Repeated obligation"):
            module.summarize(rows, [new, repeated])
        with self.assertRaisesRegex(ValueError, "Repeated case"):
            module.summarize(rows, [new, new])

    def test_regression_repetitions_add_no_coverage(self):
        receipt = {"case_id": "regression", "status": "PASS", "obligations": []}
        output = module.summarize(baseline(), [receipt])
        self.assertEqual(output["verified"], 4298)
        self.assertEqual(output["new_verified_obligations"], 0)
        self.assertEqual(output["regression_cases"], 1)

    def test_json_rejects_ambiguous_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text in ['{"sha":"a","sha":"b"}', '{"value":NaN}']:
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    module.read(path)

    def test_wheel_mixture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "another wheel"):
            module.baseline_identity({"rows": [], "wheel_sha256": "other"}, "trusted")


if __name__ == "__main__":
    unittest.main()
