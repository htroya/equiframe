"""Regressions for manual documentation checks, including dishonest PASS risks."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.check_documentation import anchors, audit, links
from tools.run_documentation_examples import prepare_examples, python_fences


class DocumentationToolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = {"scope": "fixture", "documents": ["index.md"]}

    def write(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_link_and_unicode_duplicate_anchors(self):
        self.write("index.md", "# Entry\n[Go](target.md#precisión-y-claves-1)\n")
        self.write("target.md", "# Precisión y claves\n## Precisión y claves\n")
        receipt = audit(self.root, self.manifest)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["local_anchors_checked"], 1)

    def test_missing_file_and_anchor_both_fail(self):
        self.write("index.md", "[File](missing.md)\n[Anchor](target.md#absent)\n")
        self.write("target.md", "# Actual\n")
        receipt = audit(self.root, self.manifest)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(
            {x["reason"] for x in receipt["failures"]},
            {"missing destination", "missing heading anchor"},
        )

    def test_escape_and_absolute_destinations_fail(self):
        for destination in (
            "../outside.md",
            "/absolute.md",
            "file:///secret.md",
            "%2e%2e/out.md",
        ):
            with self.subTest(destination=destination):
                self.write("index.md", f"[Go]({destination})\n")
                self.assertEqual(audit(self.root, self.manifest)["status"], "FAIL")

    def test_version_mismatch_does_not_pass(self):
        self.write("index.md", "# Version 0.12.0a7\n")
        self.write("package.toml", 'version = "0.12.0a13"\n')
        self.manifest["version_checks"] = [
            {
                "document": "index.md",
                "metadata": "package.toml",
                "pattern": r"Version ([0-9.a-z]+)",
            }
        ]
        self.assertEqual(audit(self.root, self.manifest)["status"], "FAIL")

    def test_remote_is_unverified_and_code_is_not_navigation(self):
        self.write(
            "index.md",
            "[Remote](https://example.invalid/no-request)\n"
            '```python\nprint("[Fake](missing.md)")\n```\n'
            "`[Inline](also-missing.md)`\n",
        )
        receipt = audit(self.root, self.manifest)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(len(receipt["remote_targets_not_fetched"]), 1)
        self.assertEqual(receipt["local_destinations_checked"], 0)

    def test_reference_links_and_undefined_reference(self):
        self.assertIn((1, "target.md"), links("[Read][target]\n[target]: target.md\n"))
        with self.assertRaisesRegex(ValueError, "Undefined reference"):
            links("[Read][missing]\n")

    def test_balanced_and_angle_destinations(self):
        self.assertEqual(
            links("[A](folder(a)/page.md)\n[B](<space name.md>)\n"),
            [(1, "folder(a)/page.md"), (2, "space name.md")],
        )

    def test_empty_document_scope_directory_cannot_silently_pass(self):
        self.write("index.md", "# Entry\n")
        self.manifest["directories"] = ["missing-handbook"]
        with self.assertRaisesRegex(ValueError, "Missing documentation directory"):
            audit(self.root, self.manifest)

    def test_atx_setext_and_explicit_html_ids(self):
        self.assertEqual(
            anchors('# One\nTwo\n---\n<a id="explicit"></a>\n'),
            {"one", "two", "explicit"},
        )

    def test_extract_only_selected_language_and_preserve_code(self):
        text = '```text\nnot code\n```\n```python\nprint("real")\n```\n'
        self.assertEqual(python_fences(text), ['print("real")\n'])

    def test_nested_python_marker_inside_text_is_not_executed(self):
        text = "~~~~text\n```python\nraise RuntimeError()\n```\n~~~~\n"
        self.assertEqual(python_fences(text), [])

    def test_unclosed_fence_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            python_fences('```python\nprint("incomplete")\n')

    def test_empty_registry_cannot_claim_examples_passed(self):
        with self.assertRaisesRegex(ValueError, "nonempty example"):
            prepare_examples(self.root, {"examples": []})

    def test_registry_cannot_escape_or_repeat_attempt_directory(self):
        self.write("index.md", '```python\nprint("OK")\n```\n')
        good = {
            "id": "example",
            "document": "index.md",
            "python_fence": 1,
            "expected_stdout": ["OK"],
        }
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            prepare_examples(self.root, {"examples": [good, good]})
        with self.assertRaisesRegex(ValueError, "Nonportable"):
            prepare_examples(self.root, {"examples": [{**good, "id": "../escape"}]})
        with self.assertRaisesRegex(ValueError, "outside checkout"):
            prepare_examples(
                self.root, {"examples": [{**good, "document": "../outside.md"}]}
            )

    def test_registry_requires_observable_expected_output(self):
        self.write("index.md", '```python\nprint("OK")\n```\n')
        bad = {
            "id": "example",
            "document": "index.md",
            "python_fence": 1,
            "expected_stdout": [],
        }
        with self.assertRaisesRegex(ValueError, "expected output markers"):
            prepare_examples(self.root, {"examples": [bad]})

    def test_cli_never_overwrites_receipt_under_optimization(self):
        self.write("index.md", "# Entry\n")
        manifest = self.root / "scope.json"
        manifest.write_text(json.dumps(self.manifest), encoding="utf-8")
        receipt = self.root / "receipt.json"
        receipt.write_text("KEEP ORIGINAL", encoding="utf-8")
        tool = Path(__file__).resolve().parents[1] / "tools/check_documentation.py"
        result = subprocess.run(
            [
                sys.executable,
                "-O",
                str(tool),
                "--root",
                str(self.root),
                "--manifest",
                str(manifest),
                "--output",
                str(receipt),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(receipt.read_text(encoding="utf-8"), "KEEP ORIGINAL")


if __name__ == "__main__":
    unittest.main()
