import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import EXAMPLES, PACKAGE, change, document
from typer.testing import CliRunner

from equiframe import contract_fingerprint, read_contract
from equiframe.cli import app

runner = CliRunner()


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")))
def test_cli_validates_using_the_public_api(path: Path) -> None:
    result = runner.invoke(app, ["contract", "validate", str(path)])
    assert result.exit_code == 0, result.output
    contract = read_contract(path)
    assert contract.contract_id in result.stdout
    assert contract_fingerprint(contract) in result.stdout
    assert not result.stderr


def test_cli_invalid_contract_exits_2_with_location_and_code(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            change(document(), ("output", "schema_spec", "keys", 0, "columns"), ["missing"])
        ),
        "utf-8",
    )
    result = runner.invoke(app, ["contract", "validate", str(path)])
    assert result.exit_code == 2
    assert "$.output.schema_spec.keys[0].columns[0]" in result.stderr
    assert "[unknown_column]" in result.stderr
    assert not result.stdout


def test_cli_invalid_json_and_version_exit_2(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    for data in ("{", json.dumps(change(document(), ("schema_version",), "99.0"))):
        path.write_text(data, "utf-8")
        result = runner.invoke(app, ["contract", "validate", str(path)])
        assert result.exit_code == 2
        assert "Traceback" not in result.stderr


def test_cli_io_failure_exits_3(tmp_path: Path) -> None:
    result = runner.invoke(app, ["contract", "validate", str(tmp_path / "missing.json")])
    assert result.exit_code == 3
    assert "cannot read contract file" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_usage_and_help() -> None:
    assert runner.invoke(app, ["contract", "validate"]).exit_code == 2
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0 and "contract" in result.stdout


def test_module_entrypoint_is_functional() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "equiframe", "contract", "validate", str(EXAMPLES / "dates.json")],
        cwd=PACKAGE,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "synthetic.dates" in result.stdout


def test_import_blocks_any_attempt_to_import_engines_or_ml() -> None:
    code = """
import importlib.abc
import sys
blocked = {'pandas', 'polars', 'duckdb', 'sklearn', 'numpy', 'pyarrow'}
class RejectEngines(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            raise AssertionError('unexpected engine/ML import: ' + fullname)
sys.meta_path.insert(0, RejectEngines())
import equiframe
assert not (blocked & set(sys.modules))
print(equiframe.__version__)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=True, text=True, capture_output=True
    )
    assert result.stdout.strip() == "0.1.0"
