"""The first documented comparison handles its deliberate regression explicitly."""

import subprocess
import sys
from pathlib import Path


def test_readme_comparison_rejects_regression_without_unhandled_error(tmp_path: Path) -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    example = readme.split("```python\n", 1)[1].split("```", 1)[0]
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
    assert "different True" in result.stdout
    assert "Expected regression: equivalence rejected" in result.stdout
    assert "Traceback" not in result.stderr
