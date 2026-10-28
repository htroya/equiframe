"""Installed external implementation and genuine SQLite producer, with literal expectations."""

import importlib.resources
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import equiframe as ef
from equiframe_consumer_lab import external_extension as extension


class ExternalExtensionTests(unittest.TestCase):
    def test_external_native_projection_good_difference_and_invalid(self):
        for variant in ("good", "different", "invalid"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                result, captures, calls = extension.run(Path(temporary) / "run", variant)
                self.assertEqual(captures, 1)
                if variant == "invalid":
                    self.assertEqual(calls, 0)
                    self.assertNotEqual(result.state, "equivalent")
                else:
                    self.assertEqual(calls, 1)
                    self.assertEqual(result.state, "equivalent")
                    self.assertEqual(
                        result.verification, "correct" if variant == "good" else "divergent"
                    )
                    self.assertIsNotNone(result.source)
                    self.assertIsNotNone(result.target)
                    self.assertEqual(result.source.execution.state, "completed")
                    self.assertEqual(result.target.execution.state, "completed")

    def test_unsupported_ir_is_rejected_before_any_input(self):
        contract, _plan = extension.declarations()
        plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="result", table="sales"),), output="result")
        check = extension.ProjectionCompiler().check(plan, contract)
        self.assertFalse(check.supported)
        with self.assertRaises(ef.CapabilityError):
            extension.ProjectionCompiler().compile(plan, contract)

    def test_sqlite_existing_native_producer_runs_outside_checkout(self):
        examples = importlib.resources.files("equiframe").joinpath("examples/integrations")
        for case, expected in (("good", 0), ("different", 1), ("corrupt", 3)):
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory(prefix="external-sqlite-") as temporary,
            ):
                root = Path(temporary)
                for name in ("sqlite_snapshot.py", "sqlite_snapshot_demo.py"):
                    (root / name).write_bytes(examples.joinpath(name).read_bytes())
                env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
                result = subprocess.run(
                    [
                        sys.executable,
                        str(root / "sqlite_snapshot_demo.py"),
                        "--case",
                        case,
                        "--output",
                        str(root / "result"),
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
