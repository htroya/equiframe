"""Synthetic local transports. These tests never connect to SSH or establish a native pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from transport_vm import digest, extract_zip, inspect_zip, ssh_options, transport


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="transport test spaces ")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def kit(self, extra=None):
        content = b"synthetic private artifact"
        files = {
            "artifacts/example.whl": {
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        }
        manifest = json.dumps({"schema": "equiframe-maturity-candidate-2", "files": files}).encode()
        sums = (
            f"{files['artifacts/example.whl']['sha256']}  artifacts/example.whl\n"
            f"{hashlib.sha256(manifest).hexdigest()}  candidate.json\n"
        )
        path = self.root / "candidate kit.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("artifacts/example.whl", content)
            archive.writestr("candidate.json", manifest)
            archive.writestr("SHA256SUMS", sums)
            if extra is not None:
                archive.writestr(*extra)
        return path

    def test_zip_paths_with_spaces_verified_before_extract(self):
        kit = self.kit()
        destination = self.root / "extract with spaces"
        extract_zip(kit, digest(kit), destination)
        self.assertEqual(
            (destination / "artifacts/example.whl").read_bytes(),
            b"synthetic private artifact",
        )

    def test_wrong_outer_hash_never_extracts(self):
        kit = self.kit()
        destination = self.root / "missing"
        with self.assertRaises(ValueError):
            extract_zip(kit, "0" * 64, destination)
        self.assertFalse(destination.exists())

    def test_unexpected_member_rejected(self):
        kit = self.kit(("secret.pem", "synthetic"))
        with self.assertRaisesRegex(ValueError, "unexpected"):
            inspect_zip(kit, digest(kit))

    def test_traversal_and_absolute_and_windows_escape_rejected(self):
        for name in ("../escape", "/escape", "C:/escape", "a\\escape", "a/../escape"):
            kit = self.kit((name, "synthetic"))
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_zip(kit, digest(kit))

    def test_symlink_rejected(self):
        info = zipfile.ZipInfo("symlink")
        info.external_attr = 0o120777 << 16
        kit = self.kit((info, "artifacts/example.whl"))
        with self.assertRaisesRegex(ValueError, "regular"):
            inspect_zip(kit, digest(kit))

    def test_known_hosts_and_key_are_distinct_local_argv(self):
        key = self.root / "existing secret key.pem"
        hosts = self.root / "public known hosts"
        options = ssh_options(key, hosts)
        self.assertEqual(options[1], str(key))
        self.assertIn('UserKnownHostsFile="' + hosts.as_posix() + '"', options)
        self.assertIn("StrictHostKeyChecking=yes", options)
        self.assertIn("ForwardAgent=no", options)
        self.assertIn("IdentitiesOnly=yes", options)

    def arguments(self):
        kit = self.kit()
        key = self.root / "local key.pem"
        hosts = self.root / "known hosts"
        key.write_text("synthetic non-key")
        hosts.write_text("synthetic non-host")
        return argparse.Namespace(
            kit=kit,
            key=key,
            known_hosts=hosts,
            output=self.root / "returned evidence",
            sha256=digest(kit),
            host="synthetic.invalid",
            user="hernan",
            operator="synthetic test operator",
            timeout=60,
        )

    def test_upload_failure_stops_execution_and_preserves_receipt(self):
        args = self.arguments()
        calls = []

        def fake(command, **kwargs):
            calls.append(command)
            if command[0] == "scp":
                raise RuntimeError("synthetic failed upload")
            return subprocess.CompletedProcess(
                command, 0, "/home/hernan/equiframe-universality-transfer-unit\n", ""
            )

        with (
            patch("transport_vm.pinned_hosts"),
            patch("transport_vm.run_local", side_effect=fake),
        ):
            self.assertEqual(transport(args), 1)
        self.assertEqual(len(calls), 2)
        receipt = (args.output / "transport.json").read_text()
        self.assertEqual(json.loads(receipt)["status"], "failed")
        self.assertNotIn(str(args.key), receipt)
        self.assertNotIn(args.key.read_text(), receipt)
        self.assertTrue(all(str(args.key) != c[-2] for c in calls if c[0] == "scp"))

    def test_nonzero_remote_tests_still_collect_results(self):
        args = self.arguments()
        calls = []

        def fake(command, **kwargs):
            calls.append(command)
            if command[0] == "scp" and command[-2].endswith("/work/result.json"):
                Path(command[-1]).write_text(
                    json.dumps({"status": "failed", "evidence_archive": None})
                )
            return subprocess.CompletedProcess(
                command, 0, "/home/hernan/equiframe-universality-transfer-unit\n", ""
            )

        with (
            patch("transport_vm.pinned_hosts"),
            patch("transport_vm.run_local", side_effect=fake),
            patch(
                "transport_vm.subprocess.run",
                return_value=subprocess.CompletedProcess([], 1, "synthetic negative test", ""),
            ),
        ):
            self.assertEqual(transport(args), 1)
        self.assertTrue((args.output / "result.json").is_file())
        self.assertEqual(
            json.loads((args.output / "transport.json").read_text())["status"],
            "failed_collected",
        )

    def test_zero_transport_exit_without_product_evidence_fails_closed(self):
        args = self.arguments()

        def fake(command, **kwargs):
            if command[0] == "scp" and command[-2].endswith("/work/result.json"):
                Path(command[-1]).write_text(
                    json.dumps({"status": "completed", "exit_code": 0, "evidence_archive": None})
                )
            return subprocess.CompletedProcess(
                command, 0, "/home/hernan/equiframe-universality-transfer-unit\n", ""
            )

        with (
            patch("transport_vm.pinned_hosts"),
            patch("transport_vm.run_local", side_effect=fake),
            patch(
                "transport_vm.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "", ""),
            ),
        ):
            self.assertEqual(transport(args), 1)
        self.assertEqual(
            json.loads((args.output / "transport.json").read_text())["status"], "failed_collected"
        )

    def test_remote_timeout_still_attempts_collection(self):
        args = self.arguments()
        collected = []

        def fake(command, **kwargs):
            if command[0] == "scp" and command[-2].endswith("/work/result.json"):
                collected.append(command)
                Path(command[-1]).write_text(
                    json.dumps({"status": "failed", "evidence_archive": None})
                )
            return subprocess.CompletedProcess(
                command, 0, "/home/hernan/equiframe-universality-transfer-unit\n", ""
            )

        with (
            patch("transport_vm.pinned_hosts"),
            patch("transport_vm.run_local", side_effect=fake),
            patch(
                "transport_vm.subprocess.run",
                side_effect=subprocess.TimeoutExpired([], 1, output=b"partial"),
            ),
        ):
            self.assertEqual(transport(args), 1)
        self.assertEqual(len(collected), 1)
        self.assertTrue(
            json.loads((args.output / "transport.json").read_text())["remote_timed_out"]
        )


if __name__ == "__main__":
    unittest.main()
