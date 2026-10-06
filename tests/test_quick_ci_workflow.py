"""The quick CI workflow is JSON/YAML so its execution contract needs no YAML dependency."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/equiframe-quick.yml"


class QuickWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))

    def test_only_explicit_manual_dispatch_can_start_the_workflow(self):
        self.assertEqual(self.workflow["on"], {"workflow_dispatch": {}})
        for event in (
            "push",
            "pull_request",
            "pull_request_target",
            "schedule",
            "workflow_run",
        ):
            self.assertNotIn(event, self.workflow["on"])

    def test_minimal_permissions_and_existing_pinned_actions(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        job = self.workflow["jobs"]["quick"]
        self.assertEqual(set(self.workflow["jobs"]), {"quick"})
        self.assertNotIn("permissions", job)
        self.assertNotIn("strategy", job)
        self.assertEqual(job["runs-on"], "ubuntu-24.04")
        self.assertLessEqual(job["timeout-minutes"], 15)
        uses = [step for step in job["steps"] if "uses" in step]
        self.assertEqual(len(uses), 2)
        existing = (ROOT / ".github/workflows/equiframe.yml").read_text(
            encoding="utf-8"
        )
        for step in uses:
            self.assertRegex(
                step["uses"], r"^actions/(checkout|setup-python)@[0-9a-f]{40}$"
            )
            self.assertIn(step["uses"], existing)
        self.assertFalse(uses[0]["with"]["persist-credentials"])
        self.assertEqual(uses[1]["with"]["python-version"], "3.12")

    def test_locked_local_driver_is_the_only_check_selection(self):
        steps = self.workflow["jobs"]["quick"]["steps"]
        run = [step["run"] for step in steps if "run" in step]
        sync = [command for command in run if command.startswith("uv sync")]
        self.assertEqual(len(sync), 2)
        self.assertTrue(
            all("--locked" in command and "--all-extras" in command for command in sync)
        )
        self.assertIn("--reinstall-package equiframe", sync[1])
        checks = [command for command in run if "quick_check.py" in command]
        self.assertEqual(len(checks), 2)
        self.assertTrue(
            all(
                command.startswith("uv run --locked --all-extras") for command in checks
            )
        )
        self.assertIn("--package core", checks[0])
        self.assertIn("--package benchmark", checks[1])
        for command in run:
            self.assertNotRegex(
                command.lower(), r"twine upload|uv publish|pip.*equiframe|curl|wget"
            )
            self.assertNotIn("${{", command)
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("secrets.", raw)
        self.assertNotIn("id-token", raw)
        self.assertNotIn("upload-artifact", raw)

    def test_costly_workflows_remain_manual(self):
        for name in ("equiframe.yml", "release-candidate.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", text)
            self.assertFalse(
                re.search(
                    r"^\s*(push|pull_request|pull_request_target):", text, re.MULTILINE
                )
            )


if __name__ == "__main__":
    unittest.main()
