"""Root installer command-contract tests; no package or OS changes are performed."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.name == "posix" and shutil.which("bash"),
    "the historical AlmaLinux installer requires a POSIX Bash environment",
)
class DevelopmentInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="equiframe installer ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / "checkout with spaces"
        self.package = self.checkout / "packages" / "equiframe"
        self.package.mkdir(parents=True)
        self.script = self.checkout / "install_deps_alma9.sh"
        original = Path(__file__).resolve().parents[1] / self.script.name
        shutil.copyfile(original, self.script)
        (self.package / "pyproject.toml").write_text("[project]\nname='equiframe'\n")
        (self.package / "uv.lock").write_text("version = 1\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "uv-arguments.json"
        self.python = self.bin / "selected python"
        self.python.write_text("#!/bin/sh\nexit 0\n")
        self.python.chmod(0o755)
        self.uv = self.bin / "uv"
        self.uv.write_text(
            "#!" + sys.executable + "\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['INSTALL_TEST_LOG']).write_text(json.dumps({"
            "'args':sys.argv[1:],'environment':os.environ['UV_PROJECT_ENVIRONMENT']}))\n"
            "sys.exit(int(os.environ.get('INSTALL_TEST_UV_EXIT', '0')))\n"
        )
        self.uv.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.defpath,
            "INSTALL_TEST_LOG": str(self.log),
            "UV_PROJECT_ENVIRONMENT": str(self.root / "unrelated-environment"),
        }

    def run_script(self, *arguments):
        return subprocess.run(
            [shutil.which("bash"), str(self.script), *arguments],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_help_never_installs(self):
        result = self.run_script("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("does not use sudo", result.stdout)
        self.assertFalse(self.log.exists())

    def test_dry_run_handles_paths_with_spaces_and_does_not_install(self):
        result = self.run_script("--python", str(self.python), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--locked --all-extras", result.stdout)
        self.assertFalse(self.log.exists())

    def test_install_uses_actual_core_package_and_isolated_environment(self):
        result = self.run_script("--python", str(self.python))
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(self.log.read_text())
        self.assertEqual(
            actual["args"],
            [
                "sync",
                "--locked",
                "--all-extras",
                "--no-editable",
                "--python",
                str(self.python),
                "--project",
                str(self.package),
            ],
        )
        self.assertEqual(actual["environment"], str(self.package / ".venv"))

    def test_unsupported_python_fails_before_sync(self):
        self.python.write_text("#!/bin/sh\nexit 2\n")
        result = self.run_script("--python", str(self.python))
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires Python 3.10, 3.11, 3.12 or 3.13", result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_python_fails_before_sync(self):
        result = self.run_script("--python", "equiframe-nonexistent-python")
        self.assertEqual(result.returncode, 2)
        self.assertIn("executable not found", result.stderr)
        self.assertFalse(self.log.exists())

    def test_incomplete_checkout_fails_before_sync(self):
        (self.package / "uv.lock").unlink()
        result = self.run_script("--python", str(self.python))
        self.assertEqual(result.returncode, 2)
        self.assertIn("intact authorized", result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_uv_fails_before_installation(self):
        self.uv.unlink()
        result = self.run_script("--python", str(self.python))
        self.assertEqual(result.returncode, 2)
        self.assertIn("uv is required", result.stderr)
        self.assertFalse(self.log.exists())

    def test_sync_failure_is_not_reported_as_ready(self):
        self.environment["INSTALL_TEST_UV_EXIT"] = "7"
        result = self.run_script("--python", str(self.python))
        self.assertEqual(result.returncode, 7)
        self.assertNotIn("environment ready", result.stdout)

    def test_invalid_arguments_fail_without_installing(self):
        for arguments in (("--python",), ("--python", ""), ("--unknown",)):
            with self.subTest(arguments=arguments):
                result = self.run_script(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
