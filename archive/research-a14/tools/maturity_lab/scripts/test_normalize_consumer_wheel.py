"""Verify the narrow ZIP-generation policy without changing expected artifacts."""

import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

from normalize_consumer_wheel import canonical_bytes, normalize
from validate_vm_receipts import Review, validate_normalization_paths


def archive(creator, payload=b"same literal code"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for name in ("package/main.py", "package-1.0.dist-info/METADATA"):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = creator
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            wheel.writestr(info, payload)
    return output.getvalue()


class CreatorFormatChecks(unittest.TestCase):
    def test_recorded_command_must_bind_each_actual_evidence_path(self):
        review = Review.__new__(Review)
        review.lab = PurePosixPath("/home/hernan/lab")
        record = {
            "raw_wheel": "build/raw.whl",
            "canonical_wheel": "canonical/final.whl",
            "receipt": "build/normalization.json",
        }
        command = [
            "python",
            "-I",
            "/home/hernan/kit/scripts/normalize_consumer_wheel.py",
            "--wheel",
            "/home/hernan/lab/build/raw.whl",
            "--output",
            "/home/hernan/lab/canonical/final.whl",
            "--receipt",
            "/home/hernan/lab/build/normalization.json",
        ]
        validate_normalization_paths(command, record, review.relative)
        for flag in ("--wheel", "--output", "--receipt"):
            with self.subTest(flag=flag):
                changed = list(command)
                changed[changed.index(flag) + 1] = "/home/hernan/lab/other-file"
                with self.assertRaises(ValueError):
                    validate_normalization_paths(changed, record, review.relative)
                with self.assertRaises(ValueError):
                    validate_normalization_paths(
                        command + [flag, "duplicate"], record, review.relative
                    )

    def test_only_declared_central_creator_bytes_change(self):
        raw = archive(3)
        expected = archive(0)
        result, positions, members = canonical_bytes(raw)
        self.assertEqual(result, expected)
        self.assertEqual(members, 2)
        self.assertEqual(len(positions), 2)
        self.assertEqual(
            [
                i
                for i, pair in enumerate(zip(raw, result, strict=True))
                if pair[0] != pair[1]
            ],
            positions,
        )
        with zipfile.ZipFile(io.BytesIO(result)) as wheel:
            self.assertEqual(wheel.read("package/main.py"), b"same literal code")

    def test_already_canonical_input_retains_every_byte(self):
        raw = archive(0)
        result, positions, members = canonical_bytes(raw)
        self.assertEqual(result, raw)
        self.assertEqual(positions, [])
        self.assertEqual(members, 2)

    def test_wrong_runtime_payload_cannot_be_normalized_into_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.whl"
            raw.write_bytes(archive(3, b"different code"))
            expected = hashlib.sha256(archive(0)).hexdigest()
            with self.assertRaises(ValueError):
                normalize(raw, expected, root / "canonical.whl", root / "receipt.json")
            self.assertFalse((root / "canonical.whl").exists())
            self.assertEqual(raw.read_bytes(), archive(3, b"different code"))

    def test_raw_build_and_prior_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.whl"
            raw.write_bytes(archive(3))
            expected = hashlib.sha256(archive(0)).hexdigest()
            result = normalize(
                raw, expected, root / "canonical.whl", root / "receipt.json"
            )
            self.assertEqual(raw.read_bytes(), archive(3))
            self.assertTrue(result["raw_wheel_preserved"])
            self.assertFalse(result["payload_or_other_header_bytes_changed"])
            with self.assertRaises(ValueError):
                normalize(raw, expected, root / "canonical.whl", root / "receipt.json")

    def test_truncated_or_commented_archives_are_not_admitted(self):
        with self.assertRaises(ValueError):
            canonical_bytes(archive(3)[:-1])
        with self.assertRaises(ValueError):
            canonical_bytes(archive(3) + b"unexpected trailing data")

    def test_unknown_creator_format_is_not_rewritten(self):
        with self.assertRaises(ValueError):
            canonical_bytes(archive(7))


if __name__ == "__main__":
    unittest.main()
