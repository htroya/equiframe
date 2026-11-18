"""Preparation regressions; simulated index states never imply a real upload."""

import base64
import csv
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZIP_DEFLATED, ZipFile

from tools import prepare_pypi as prep
from tools.probe_pypi_names import observe


class PyPIPreparationTests(unittest.TestCase):
    def candidate(self, root, *, bad_pin=False, bad_sdist=False, corrupt_record=False):
        version = "1.2.3"
        records = []
        for name in ("equiframe", "equiframe-benchmark"):
            stem = name.replace("-", "_") + "-" + version
            metadata = f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\nRequires-Python: >=3.10\n"
            if name == "equiframe-benchmark":
                metadata += (
                    "Requires-Dist: equiframe[arrow]=="
                    + ("9.9.9" if bad_pin else version)
                    + "\n"
                )
            metadata += "\nSynthetic test metadata. Not a public release.\n"
            raw_metadata = metadata.encode("utf-8")
            payload = {
                name.replace("-", "_") + "/py.typed": b"",
                stem + ".dist-info/METADATA": raw_metadata,
                stem
                + ".dist-info/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            }
            record_name = stem + ".dist-info/RECORD"
            inventory = io.StringIO(newline="")
            writer = csv.writer(inventory)
            for member, raw in payload.items():
                digest = (
                    base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
                    .rstrip(b"=")
                    .decode("ascii")
                )
                writer.writerow([member, "sha256=" + digest, len(raw)])
            writer.writerow([record_name, "", ""])
            payload[record_name] = inventory.getvalue().encode("utf-8")
            if corrupt_record:
                payload[stem + ".dist-info/WHEEL"] += b"UNREVIEWED CHANGE"
            wheel = root / (stem + "-py3-none-any.whl")
            with ZipFile(wheel, "w", ZIP_DEFLATED) as archive:
                for member, raw in payload.items():
                    archive.writestr(member, raw)
            source_metadata = raw_metadata + (b"CHANGED" if bad_sdist else b"")
            source = self.tar(
                [
                    (stem + "/PKG-INFO", source_metadata, tarfile.REGTYPE),
                    (
                        stem + "/pyproject.toml",
                        b"# synthetic fixture\n",
                        tarfile.REGTYPE,
                    ),
                    (stem + "/README.md", b"Synthetic fixture\n", tarfile.REGTYPE),
                ]
            )
            sdist = root / (stem + ".tar.gz")
            sdist.write_bytes(source)
            for path in (wheel, sdist):
                raw = path.read_bytes()
                records.append(
                    {
                        "file": path.name,
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
        manifest = {
            "schema": "pypi-preparation-v1",
            "version": version,
            "artifact_code_cut": "1" * 40,
            "test_code_cut": "2" * 40,
            "artifacts": records,
            "binary_fixtures": {"equiframe": {}, "equiframe-benchmark": {}},
        }
        closed = {
            "schema_version": "1.0",
            "publication_enabled": False,
            "pending_decisions": ["license"],
        }
        return manifest, closed

    def tar(self, members):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name, raw, kind in members:
                info = tarfile.TarInfo(name)
                info.type = kind
                if kind == tarfile.REGTYPE:
                    info.size = len(raw)
                    archive.addfile(info, io.BytesIO(raw))
                else:
                    info.linkname = "../outside"
                    archive.addfile(info)
        return output.getvalue()

    def test_tar_normal_inventory_is_read_without_extraction(self):
        raw = self.tar([("equiframe-1.2.3/PKG-INFO", b"metadata", tarfile.REGTYPE)])
        self.assertEqual(
            prep.sdist_payload(raw, "equiframe-1.2.3"), {"PKG-INFO": b"metadata"}
        )

    def test_tar_traversal_absolute_wrong_root_duplicates_and_links_fail(self):
        bad = [
            [("equiframe-1.2.3/../secret", b"data", tarfile.REGTYPE)],
            [("/equiframe-1.2.3/secret", b"data", tarfile.REGTYPE)],
            [("other-1.2.3/file", b"data", tarfile.REGTYPE)],
            [
                ("equiframe-1.2.3/file", b"one", tarfile.REGTYPE),
                ("equiframe-1.2.3/file", b"two", tarfile.REGTYPE),
            ],
            [("equiframe-1.2.3/link", b"", tarfile.SYMTYPE)],
            [("equiframe-1.2.3/link", b"", tarfile.LNKTYPE)],
            [("equiframe-1.2.3/device", b"", tarfile.CHRTYPE)],
        ]
        for members in bad:
            with self.subTest(members=members), self.assertRaises(ValueError):
                prep.sdist_payload(self.tar(members), "equiframe-1.2.3")

    def test_tar_file_directory_collision_fails(self):
        raw = self.tar(
            [
                ("equiframe-1.2.3/dir", b"x", tarfile.REGTYPE),
                ("equiframe-1.2.3/dir/file", b"y", tarfile.REGTYPE),
            ]
        )
        with self.assertRaisesRegex(ValueError, "collision"):
            prep.sdist_payload(raw, "equiframe-1.2.3")

    def test_tar_uncompressed_budget_fails(self):
        raw = self.tar([("equiframe-1.2.3/file", b"a" * 64, tarfile.REGTYPE)])
        with (
            patch.object(prep, "MAX_PAYLOAD", 32),
            self.assertRaisesRegex(ValueError, "limit"),
        ):
            prep.sdist_payload(raw, "equiframe-1.2.3")

    def test_sensitive_paths_and_unreviewed_models_fail(self):
        for name in (
            ".env",
            "keys/private.pem",
            ".venv/config",
            "model.pkl",
            "data.arrow",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                prep.audit_contents({name: b"synthetic"}, {})

    def test_fixture_exception_is_exact_path_and_hash(self):
        name, raw = "tests/fixtures/versioned/reviewed.arrow", b"SYNTHETIC"
        expected = {name: hashlib.sha256(raw).hexdigest()}
        self.assertEqual(len(prep.audit_contents({name: raw}, expected)), 1)
        with self.assertRaises(ValueError):
            prep.audit_contents({name: raw + b"corruption"}, expected)
        with self.assertRaises(ValueError):
            prep.audit_contents({}, expected)
        with self.assertRaises(ValueError):
            prep.audit_contents({"data.arrow": raw}, {"data.arrow": expected[name]})

    def test_unsafe_archive_path_variants_fail(self):
        for name in (
            "root//file",
            "root/./file",
            "root/../file",
            "C:/file",
            "root\\file",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                prep.safe_member(name)

    def test_forged_policy_and_boolean_substitutes_never_enable_upload(self):
        closed = {
            "schema_version": "1.0",
            "publication_enabled": False,
            "pending_decisions": ["license"],
        }
        prep.closed_policy(closed)
        for value in (True, 0, None, "false"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prep.closed_policy({**closed, "publication_enabled": value})
        with self.assertRaises(ValueError):
            prep.closed_policy({**closed, "pending_decisions": []})

    def test_duplicate_fields_and_nonfinite_tokens_rejected(self):
        for raw in (b'{"artifacts": [], "artifacts": []}', b'{"size": NaN}', b"[]"):
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                prep.read_json(raw)

    def test_hash_and_size_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifact"
            path.write_bytes(b"original")
            correct = hashlib.sha256(b"original").hexdigest()
            self.assertEqual(prep.verified_bytes(path, correct, 8), b"original")
            for digest, size in (("0" * 64, 8), (correct, 9), (correct, True)):
                with (
                    self.subTest(digest=digest, size=size),
                    self.assertRaises(ValueError),
                ):
                    prep.verified_bytes(path, digest, size)

    def test_partial_upload_is_never_complete_or_authorized(self):
        expected = {
            "core.whl": "a",
            "core.tar.gz": "b",
            "bench.whl": "c",
            "bench.tar.gz": "d",
        }
        result = prep.reconcile(expected, {"core.whl": "a"})
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(len(result["missing"]), 3)
        self.assertFalse(result["publication_authorized"])

    def test_duplicate_release_observation_checks_digest_and_does_not_retry(self):
        expected = {"core.whl": "a", "core.tar.gz": "b"}
        result = prep.reconcile(expected, expected)
        self.assertEqual(result["state"], "COMPLETE_OBSERVATION")
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["observation_authenticated"])
        self.assertEqual(
            prep.reconcile(expected, {"core.whl": "wrong"})["state"], "CONFLICT"
        )
        self.assertEqual(
            prep.reconcile(expected, {"unexpected": "a"})["state"], "CONFLICT"
        )
        self.assertEqual(prep.reconcile(expected, {})["state"], "ABSENT")
        with self.assertRaises(ValueError):
            prep.reconcile({}, {})

    def test_manifest_size_cannot_be_null_boolean_or_nonpositive(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            manifest, release_policy = self.candidate(folder)
            for invalid in (None, True, 0, -1, "100"):
                manifest["artifacts"][0]["bytes"] = invalid
                with self.subTest(size=invalid), self.assertRaises(ValueError):
                    prep.prepare(manifest, folder, release_policy)

    def test_local_withdrawal_drill_preserves_expected_release_inventory(self):
        expected = {
            "core.whl": "a",
            "core.tar.gz": "b",
            "bench.whl": "c",
            "bench.tar.gz": "d",
        }
        original_receipt = expected.copy()
        observations = [expected.copy(), {"core.whl": "a"}, {}]
        states = []
        for observed in observations:
            receipt = prep.reconcile(expected, observed)
            states.append(receipt["state"])
            self.assertFalse(receipt["publication_authorized"])
            self.assertFalse(receipt["observation_authenticated"])
        self.assertEqual(states, ["COMPLETE_OBSERVATION", "PARTIAL", "ABSENT"])
        self.assertEqual(expected, original_receipt)
        self.assertEqual(observations[0], original_receipt)

    def test_invalid_preflight_prevents_packet_creation_under_optimization(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            manifest = folder / "manifest.json"
            manifest.write_bytes(b'{"schema": "wrong"}')
            output = folder / "packet.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-O",
                    str(Path(prep.__file__)),
                    "--artifact-root",
                    str(folder),
                    "--manifest",
                    str(manifest),
                    "--sha256",
                    hashlib.sha256(manifest.read_bytes()).hexdigest(),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_occupied_receipt_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            output = folder / "packet.json"
            output.write_text("KEEP ORIGINAL", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(prep.__file__)),
                    "--artifact-root",
                    str(folder),
                    "--manifest",
                    str(folder / "missing.json"),
                    "--sha256",
                    "0" * 64,
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "KEEP ORIGINAL")

    def test_index_404_is_not_ownership_or_reserved_availability(self):
        error = HTTPError(
            "https://pypi.org/pypi/equiframe/json", 404, "Not Found", None, None
        )
        with patch("tools.probe_pypi_names.urlopen", side_effect=error):
            result = observe("pypi.org", "equiframe")
        self.assertEqual(result["status"], "NOT_VISIBLE")
        self.assertFalse(result["ownership_verified"])
        self.assertFalse(result["availability_reserved"])

    def test_index_auth_failure_is_unknown_not_available(self):
        error = HTTPError(
            "https://pypi.org/pypi/equiframe/json", 403, "Forbidden", None, None
        )
        with patch("tools.probe_pypi_names.urlopen", side_effect=error):
            self.assertEqual(observe("pypi.org", "equiframe")["status"], "UNKNOWN")

    def test_valid_pair_is_integrity_only_and_never_publication_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, closed = self.candidate(root)
            packet = prep.prepare(manifest, root, closed)
            self.assertTrue(packet["artifacts_verified"])
            self.assertFalse(packet["publication_ready"])
            self.assertFalse(packet["published"])
            self.assertFalse(packet["upload_available"])

    def test_sdist_metadata_pin_and_record_corruption_fail_even_with_new_outer_hash(
        self,
    ):
        for options, reason in (
            ({"bad_sdist": True}, "metadata differ"),
            ({"bad_pin": True}, "pin the matching core"),
            ({"corrupt_record": True}, "RECORD"),
        ):
            with (
                self.subTest(options=options),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                manifest, closed = self.candidate(root, **options)
                with self.assertRaisesRegex(ValueError, reason):
                    prep.prepare(manifest, root, closed)

    def test_approval_field_and_repeated_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, closed = self.candidate(root)
            with self.assertRaisesRegex(ValueError, "no approval fields"):
                prep.prepare({**manifest, "approved": True}, root, closed)
            broken = json.loads(json.dumps(manifest))
            broken["artifacts"][-1] = broken["artifacts"][0]
            with self.assertRaisesRegex(ValueError, "artifact names"):
                prep.prepare(broken, root, closed)

    def test_valid_cli_returns_blocked_three_under_optimization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, _ = self.candidate(root)
            source = root / "manifest.json"
            source.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "packet.json"
            outcome = subprocess.run(
                [
                    sys.executable,
                    "-O",
                    str(Path(prep.__file__)),
                    "--artifact-root",
                    str(root),
                    "--manifest",
                    str(source),
                    "--sha256",
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(outcome.returncode, 3)
            self.assertFalse(
                json.loads(output.read_text(encoding="utf-8"))["publication_ready"]
            )


if __name__ == "__main__":
    unittest.main()
