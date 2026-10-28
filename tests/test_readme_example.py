"""The documented comparison detects its deliberate value regression."""

import subprocess
import sys
from pathlib import Path


def test_readme_comparison_rejects_regression_without_unhandled_error(tmp_path: Path) -> None:
    readme = (Path(__file__).parents[1] / "README.en.md").read_text(encoding="utf-8")
    comparisons = [
        section.split("```", 1)[0]
        for section in readme.split("```python\n")[1:]
        if "ef.diff(" in section.split("```", 1)[0]
    ]
    assert len(comparisons) == 1, "README must contain one identifiable comparison example"
    example = (
        comparisons[0]
        + """
assert result.state == "different" and result.complete
changes = tuple(ef.iter_differences(result.differences))
assert len(changes) == 1 and changes[0].column == "amount"
assert changes[0].key[0].value == "2"
assert changes[0].left[0].value == "200" and changes[0].right[0].value == "201"
try:
    ef.assert_equivalent(result)
except ef.EquivalenceAssertionError as error:
    assert error.code == "different"
    print("Expected regression: equivalence rejected")
else:
    raise AssertionError("README regression was accepted")
"""
    )
    script = tmp_path / "readme_example.py"
    script.write_text(example, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[:2] == ["different", "True"]
    assert "Expected regression: equivalence rejected" in result.stdout
    assert "Traceback" not in result.stderr
