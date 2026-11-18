"""The installed README gate executes every published example with real expectations."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def readme_script(readme: str) -> str:
    source = ROOT / "tools/verify_distribution.py"
    module = ast.parse(source.read_text("utf-8"))
    helper = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "readme_consumer_script"
    )
    namespace = {}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["readme_consumer_script"](readme)


def test_every_literal_readme_example_executes_with_independent_expected_results(
    tmp_path, monkeypatch
):
    pytest.importorskip("pyarrow")
    pytest.importorskip("pandas")
    pytest.importorskip("polars")
    pytest.importorskip("duckdb")
    monkeypatch.chdir(tmp_path)
    script = readme_script((ROOT / "README.en.md").read_text("utf-8"))
    exec(compile(script, "installed-readme-example.py", "exec"), {})


@pytest.mark.parametrize("mutation", ["missing_grouped", "extra_block", "wrong_grouped_api"])
def test_unreviewed_readme_shape_is_rejected(mutation):
    readme = (ROOT / "README.en.md").read_text("utf-8")
    if mutation == "missing_grouped":
        readme = readme.rsplit("```python\n", 1)[0]
    elif mutation == "extra_block":
        readme += "\n```python\nprint('unreviewed example')\n```\n"
    else:
        readme = readme.replace("summary = ef.compare_grouped(", "summary = ef.diff(")
    with pytest.raises(RuntimeError, match="README examples changed"):
        readme_script(readme)


def test_changed_grouped_input_cannot_pass_the_installed_readme_gate(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    pytest.importorskip("pandas")
    pytest.importorskip("polars")
    pytest.importorskip("duckdb")
    readme = (ROOT / "README.en.md").read_text("utf-8")
    assert '"sales": [90, 60, 25, 50, 7]' in readme
    readme = readme.replace('"sales": [90, 60, 25, 50, 7]', '"sales": [40, 60, 25, 50, 7]')
    monkeypatch.chdir(tmp_path)
    with pytest.raises(AssertionError):
        exec(compile(readme_script(readme), "changed-readme-example.py", "exec"), {})
