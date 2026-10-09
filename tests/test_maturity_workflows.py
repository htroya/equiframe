"""Declarative workflow contracts; none of these tests triggers GitHub Actions."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MaturityWorkflowTests(unittest.TestCase):
    def test_full_matrix_preserves_platforms_and_required_python_minors(self):
        text = (ROOT / '.github/workflows/equiframe.yml').read_text()
        cells = set(re.findall(r'- os: ([^\n]+)\n\s+architecture: ([^\n]+)\n\s+python: \'([^\']+)\'', text))
        expected = {(os, arch, minor)
                    for os, arch in (("ubuntu-24.04", "x64"), ("ubuntu-24.04-arm", "arm64"),
                                     ("windows-2022", "x64"), ("macos-15-intel", "x64"),
                                     ("macos-15", "arm64"))
                    for minor in ("3.10", "3.11", "3.12", "3.13")}
        self.assertEqual(cells, expected)
        self.assertIn('python-version: ${{ matrix.python }}', text)
        self.assertEqual(text.count('mypy --python-version ${{ matrix.python }}'), 2)
        self.assertEqual(text.count('uv sync --locked --all-extras --no-editable --python ${{ matrix.python }}'), 2)
        self.assertIn('workflow_dispatch:', text)
        self.assertIn('default: false', text)
        self.assertNotRegex(text, r'(?m)^\s*(push|pull_request|schedule):')
        self.assertIn('contents: read', text)
        self.assertNotIn('id-token:', text)

    def test_release_workflow_artifact_names_match_current_pair(self):
        text = (ROOT / '.github/workflows/release-candidate.yml').read_text()
        for package in ('equiframe','equiframe-benchmark'):
            project = (ROOT / 'packages' / package / 'pyproject.toml').read_text()
            version = re.search(r'^version = "([^"]+)"', project, re.M).group(1)
            stem = package.replace('-', '_') + '-' + version
            self.assertIn(stem + '-py3-none-any.whl', text)
            self.assertIn(stem + '.tar.gz', text)
        self.assertIn('--python 3.12', text)
        self.assertNotIn('--no-deps', text)
        self.assertNotRegex(text, r'(?m)^\s*(push|pull_request|schedule):')
