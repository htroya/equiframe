"""Independent stdlib checks of consumed-input integrity; no installed core needed."""

import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path

EVIDENCE = runpy.run_path(str(Path(__file__).parents[1] / "src/equiframe_consumer_lab/evidence.py"))
ConsumerError = EVIDENCE["ConsumerError"]


class FrozenInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="consumer-frozen-unit-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.consumed = "raw/treasury.json"
        (self.root / "raw").mkdir()
        (self.root / self.consumed).write_bytes(b"before")
        (self.root / "notes.txt").write_bytes(b"metadata")

    def entry(self, name):
        raw = (self.root / name).read_bytes()
        return {
            "path": name,
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def manifest(self, entries):
        raw = json.dumps({"status": "FROZEN", "files": entries}).encode("utf-8")
        (self.root / "manifest.json").write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def verify(self, digest):
        return EVIDENCE["verify_frozen"](
            self.root,
            required_paths=(self.consumed,),
            expected_manifest_sha256=digest,
        )

    def test_empty_inventory_rejected_even_when_consumed_file_exists(self):
        digest = self.manifest([])
        with self.assertRaisesRegex(ConsumerError, "inventory must not be empty"):
            self.verify(digest)

    def test_omitted_consumed_file_rejected_with_valid_other_member(self):
        digest = self.manifest([self.entry("notes.txt")])
        with self.assertRaisesRegex(ConsumerError, "Consumed input is missing"):
            self.verify(digest)

    def test_valid_inventory_verifies_consumed_file_before_and_after(self):
        digest = self.manifest([self.entry(self.consumed), self.entry("notes.txt")])
        self.assertEqual(self.verify(digest)["status"], "FROZEN")
        self.assertEqual(self.verify(digest)["status"], "FROZEN")
        self.assertEqual(EVIDENCE["frozen_manifest_sha256"](self.root), digest)

    def test_same_size_change_to_consumed_file_is_rejected(self):
        digest = self.manifest([self.entry(self.consumed)])
        self.verify(digest)
        (self.root / self.consumed).write_bytes(b"after!")
        with self.assertRaisesRegex(ConsumerError, "data SHA-256 differs"):
            self.verify(digest)

    def test_rewriting_input_and_manifest_does_not_replace_original_identity(self):
        digest = self.manifest([self.entry(self.consumed)])
        self.verify(digest)
        (self.root / self.consumed).write_bytes(b"after!")
        replacement = self.manifest([self.entry(self.consumed)])
        self.assertNotEqual(digest, replacement)
        with self.assertRaisesRegex(ConsumerError, "manifest SHA-256 differs"):
            self.verify(digest)

    def test_duplicate_member_cannot_hide_an_inventory_substitution(self):
        entry = self.entry(self.consumed)
        digest = self.manifest([entry, entry])
        with self.assertRaisesRegex(ConsumerError, "Duplicate frozen member path"):
            self.verify(digest)

    def test_noncanonical_or_parent_member_paths_rejected(self):
        for path in (
            "../outside",
            "raw/../treasury.json",
            "raw//treasury.json",
            "raw\\treasury.json",
        ):
            with self.subTest(path=path):
                digest = self.manifest([{"path": path, "size_bytes": 0, "sha256": "0" * 64}])
                with self.assertRaisesRegex(ConsumerError, "Invalid frozen member path"):
                    self.verify(digest)


if __name__ == "__main__":
    unittest.main()
