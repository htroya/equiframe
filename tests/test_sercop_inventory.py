import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "sercop_inventory",
    Path(__file__).resolve().parents[1] / "tools/sercop_inventory.py",
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class StreamTests(unittest.TestCase):
    def test_tiny_chunks_preserve_decimal_and_unicode(self):
        value = '[{"amount":123456789012345.67,"text":"á\\nβ"}, {"amount":null}]'
        result = list(module.packages(io.StringIO(value), chunk_size=1))
        self.assertEqual(result[0]["amount"], Decimal("123456789012345.67"))
        self.assertEqual(result[0]["text"], "á\nβ")
        self.assertIsNone(result[1]["amount"])

    def test_empty_array(self):
        self.assertEqual(
            list(module.packages(io.StringIO(" [ ] \n"), chunk_size=1)), []
        )

    def test_reject_duplicate_nonfinite_truncated_and_trailing(self):
        for value in [
            '[{"a":1,"a":2}]',
            '[{"a":NaN}]',
            '[{"a":1}',
            "[{}] {}",
            "[{},]",
            "{}",
            "[1]",
        ]:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                list(module.packages(io.StringIO(value), chunk_size=1))

    def test_object_budget(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            list(module.packages(io.StringIO('[{"text":"abcdefghijklmnop"}]'), 1, 8))

    def test_occurrences_do_not_become_unique_awards_or_training_profiles(self):
        release = {
            "ocid": "ocid-test",
            "id": "version-1",
            "date": "2026-01-01T00:00:00Z",
            "awards": [
                {"id": "award-1", "value": {"currency": "USD", "amount": 1}},
                {"id": "award-2", "value": None},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "export.json",
                    json.dumps(
                        [{"license": "fixture", "releases": [release, release]}]
                    ),
                )
            output = module.inventory(path, module.file_sha256(path))
        self.assertEqual(output["counts"]["releases"], 2)
        self.assertEqual(output["counts"]["award_occurrences"], 4)
        self.assertEqual(output["unique_award_identities"], 2)
        self.assertEqual(output["unique_release_identities"], 1)
        self.assertEqual(output["counts"]["award_value_absent_or_invalid"], 2)
        self.assertEqual(output["release_date_years"], {"2026": 2})
        self.assertIsNone(output["effective_training_profiles_accredited"])
        self.assertEqual(output["independent_labels_accredited"], 0)

    def test_archive_identity_and_single_member_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("one.json", "[]")
                archive.writestr("two.json", "[]")
            with self.assertRaisesRegex(ValueError, "identity"):
                module.inventory(path, "0" * 64)
            with self.assertRaisesRegex(ValueError, "Exactly one"):
                module.inventory(path, module.file_sha256(path))


if __name__ == "__main__":
    unittest.main()
