"""Keep the small documented entry route executable and connected to current APIs."""

import ast
import re
import runpy
from pathlib import Path

import equiframe as ef

ROOT = Path(__file__).resolve().parents[1]


def test_spanish_entry_executes_both_decisions_and_is_repeatable(tmp_path, monkeypatch):
    text = (ROOT / "docs" / "inicio.md").read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)
    assert len(snippets) == 1
    script = tmp_path / "inicio.py"
    script.write_text(snippets[0], encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for _ in range(2):
        result = runpy.run_path(str(script))
        assert result["result"].state == "different"
        assert result["corrected"].state == "equivalent"
    roots = list(tmp_path.glob("revision-*"))
    assert len(roots) == 2
    for root in roots:
        report = ef.read_comparison_report(root / "report" / "report.json")
        assert report.state == "different"
        assert not report.options.include_values
        assert not report.options.include_metadata


def test_quick_discoverability_keeps_the_existing_exports_and_complete_code():
    names = (
        "diff",
        "read_diff_contract",
        "comparison_report",
        "write_comparison_report",
        "assert_equivalent",
    )
    text = (ROOT / "docs" / "inicio.md").read_text(encoding="utf-8")
    for name in names:
        assert name in ef.__all__
        assert callable(getattr(ef, name))
        assert f"`{name}(" in text
    for block in re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL):
        ast.parse(block)
    assert "completed" in ef.__doc__ and "bool(result)" in ef.__doc__


def test_progressive_docs_have_local_resolvable_links():
    for name in ("inicio.md", "choosing-api.md"):
        source = ROOT / "docs" / name
        for target in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
            assert not target.startswith(("http:", "https:"))
            assert (source.parent / target.split("#", 1)[0]).is_file(), target
