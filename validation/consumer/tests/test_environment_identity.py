"""Synthetic metadata checks of the current consumer guard, without installation."""

import hashlib
import importlib.metadata
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

EVIDENCE = runpy.run_path(str(Path(__file__).parents[1] / "src/equiframe_consumer_lab/evidence.py"))
ConsumerError = EVIDENCE["ConsumerError"]


class EnvironmentIdentityTests(unittest.TestCase):
    def observed(self, core_version, consumer_version="0.1.19"):
        site = Path(sys.prefix) / "lib" / "site-packages"
        core = types.ModuleType("equiframe")
        core.__file__ = str(site / "equiframe" / "__init__.py")
        record = "synthetic-installed-file,sha256=fixture,1\n"
        distribution = types.SimpleNamespace(
            read_text=lambda field: record if field == "RECORD" else None
        )
        versions = {"equiframe": core_version, "equiframe-consumer-lab": consumer_version}
        environment = EVIDENCE["environment"]
        with (
            patch.dict(sys.modules, {"equiframe": core}),
            patch.dict(
                environment.__globals__,
                {"__file__": str(site / "equiframe_consumer_lab" / "evidence.py")},
            ),
            patch.object(importlib.metadata, "version", side_effect=versions.__getitem__),
            patch.object(importlib.metadata, "distribution", return_value=distribution),
        ):
            return environment(), record

    def test_current_release_accepted_with_record_and_unknown_git_identity(self):
        observed, record = self.observed("0.12.4")
        self.assertEqual(
            observed["core_distribution_record_sha256"], hashlib.sha256(record.encode()).hexdigest()
        )
        self.assertIsNone(observed["core_source_commit"])
        self.assertIsNone(observed["core_source_tree"])
        self.assertEqual(observed["isolated"], 1)

    def test_old_candidate_and_previous_release_are_rejected(self):
        for version in ("0.12.0a14", "0.12.1", "0.12.2", "0.12.3"):
            with (
                self.subTest(version=version),
                self.assertRaisesRegex(ConsumerError, "Wrong installed core version"),
            ):
                self.observed(version)

    def test_previous_consumer_cannot_claim_the_current_pairing(self):
        with self.assertRaisesRegex(ConsumerError, "Wrong installed consumer version"):
            self.observed("0.12.4", "0.1.18")


if __name__ == "__main__":
    unittest.main()
