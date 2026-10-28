"""The fast check plan is fixed, fail-closed and shared with local invocation."""

import json
import runpy
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def driver():
    return runpy.run_path(str(Path(__file__).parents[1] / "tools/quick_check.py"))


@pytest.mark.parametrize("package", ["core", "benchmark"])
def test_fixed_selection_is_real_and_nonempty(driver, tmp_path, package):
    # Planning is a pure operation and must also be testable from an sdist.
    # Cross-package file existence is checked by root workflow contract tests.
    root = tmp_path / "synthetic-repository"
    checks = driver["plan"](root, package, tmp_path)
    assert {"ruff", "format", "mypy", "generated", "semantic-smoke"} <= {x.name for x in checks}
    smoke = next(check for check in checks if check.name == "semantic-smoke")
    selected = [argument for argument in smoke.command if argument.startswith("tests/")]
    assert selected and len(selected) == len(set(selected))
    expected_package = root if package == "core" else root / "packages/equiframe-benchmark"
    assert smoke.directory == expected_package
    assert all(test.endswith(".py") for test in selected)
    if package == "core":
        package_root = Path(__file__).resolve().parents[1]
        assert all((package_root / test).is_file() for test in selected)
    assert all("--basetemp=" + str(tmp_path / "pytest") in check.command for check in (smoke,))
    # Interpreter and output paths can contain these words without invoking them.
    forbidden_commands = {"build", "twine", "publish", "upload", "deploy"}
    assert all(
        argument not in forbidden_commands for check in checks for argument in check.command[1:]
    )


def test_source_environment_replaces_ambient_paths(driver, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "unrelated-source")
    monkeypatch.setenv("PYTHONHOME", "unrelated-runtime")
    env = driver["environment"](tmp_path)
    assert "PYTHONHOME" not in env
    assert "unrelated-source" not in env["PYTHONPATH"]
    assert env["PYTHONDONTWRITEBYTECODE"] == env["PYTHONNOUSERSITE"] == "1"
    assert str(tmp_path / "src") in env["PYTHONPATH"]


def test_existing_output_rejected_without_commands(driver, tmp_path, monkeypatch):
    output = tmp_path / "retained"
    output.mkdir()
    (output / "receipt.json").write_text("old")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kw: pytest.fail("must not run"))
    with pytest.raises(FileExistsError):
        driver["run_checks"](tmp_path, "core", output)
    assert (output / "receipt.json").read_text() == "old"


@pytest.mark.parametrize("exit_code", [0, 7, -9])
def test_receipt_tracks_actual_commands_and_stops_on_failure(
    driver, tmp_path, monkeypatch, exit_code
):
    run = driver["run_checks"]
    check = driver["Check"]
    monkeypatch.setitem(run.__globals__, "identity", lambda *args: {"commit": "synthetic"})
    monkeypatch.setitem(
        run.__globals__,
        "plan",
        lambda *args: (
            check("one", ("test-command",), tmp_path),
            check("two", ("test-command",), tmp_path),
        ),
    )
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        kwargs["stdout"].write("retained output\n")
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(subprocess, "run", execute)
    output = tmp_path / "run"
    expected = 0 if exit_code == 0 else max(exit_code, 1)
    assert run(tmp_path, "core", output) == expected
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["complete"] is (exit_code == 0)
    assert len(calls) == len(receipt["results"]) == (2 if exit_code == 0 else 1)
    assert receipt["results"][0]["exit_code"] == exit_code
    assert (output / "one.log").read_text() == "retained output\n"


@pytest.mark.parametrize("minor", [10, 11, 12, 13])
def test_quick_typing_targets_actual_interpreter_without_narrowing_scope(
    driver, tmp_path, monkeypatch, minor
):
    from types import SimpleNamespace

    planner = driver["plan"]
    monkeypatch.setitem(
        planner.__globals__,
        "sys",
        SimpleNamespace(executable="chosen-python", version_info=(3, minor)),
    )
    checks = planner(tmp_path, "core", tmp_path / "receipts")
    typing = next(check for check in checks if check.name == "mypy")
    assert typing.command == ("chosen-python", "-m", "mypy", "--python-version", f"3.{minor}")
    assert typing.directory == tmp_path
