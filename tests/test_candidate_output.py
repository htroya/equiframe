"""Candidate retries never erase an earlier receipt, log or pytest evidence."""

import json
import runpy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


@pytest.fixture
def driver(monkeypatch):
    tools = Path(__file__).parents[1] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    return runpy.run_path(str(tools / "check_candidate.py"))


@pytest.mark.parametrize("existing", ["receipt", "log", "pytest"])
def test_reused_output_is_rejected_before_any_command(driver, tmp_path, monkeypatch, existing):
    output = tmp_path / "checks.json"
    if existing == "receipt":
        retained = output
    elif existing == "log":
        retained = tmp_path / "checks-04.log"
    else:
        directory = tmp_path / "checks-pytest-tmp"
        directory.mkdir()
        retained = directory / "evidence.txt"
    retained.write_bytes(b"previous attempt must survive")
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_candidate.py", "--package", str(tmp_path), "--uv", "uv", "--output", str(output)],
    )

    def must_not_run(*args, **kwargs):
        raise AssertionError("reused output must be rejected before running any command")

    monkeypatch.setattr(subprocess, "run", must_not_run)
    with pytest.raises(SystemExit, match="already exist"):
        driver["main"]()
    assert retained.read_bytes() == b"previous attempt must survive"
    if existing != "receipt":
        assert not output.exists()


def test_output_reservation_is_exclusive_for_concurrent_runs(driver, tmp_path):
    output = tmp_path / "checks.json"

    def reserve():
        try:
            driver["reserve_output"](output)
        except SystemExit:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: reserve(), range(8))) == 1
    assert json.loads(output.read_text()) == {"environment": {}, "results": []}


def test_unrelated_prefix_log_does_not_block_a_fresh_output(driver, tmp_path):
    retained = tmp_path / "checks-other-00.log"
    retained.write_text("different run", encoding="utf-8")
    output = tmp_path / "checks.json"
    driver["reserve_output"](output)
    assert output.is_file() and retained.read_text(encoding="utf-8") == "different run"


def test_failed_command_receipt_is_retained_and_cannot_be_reused(driver, tmp_path, monkeypatch):
    output = tmp_path / "checks.json"
    execute = driver["run_checks"]
    snapshot = {"sha256": "synthetic-fixed-source"}
    monkeypatch.setitem(execute.__globals__, "source_snapshot", lambda _: snapshot)
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        kwargs["stdout"].write("retained failed-command output\n")
        return subprocess.CompletedProcess(command, 17)

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(driver["platform"], "platform", lambda: "synthetic-test-platform")
    arguments = (
        tmp_path,
        output,
        snapshot,
        (),
        (),
        [["synthetic-command"]],
        [sys.executable],
        tmp_path / "bytecode",
        {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(tmp_path / "bytecode")},
    )
    with pytest.raises(SystemExit) as first:
        execute(*arguments)
    assert first.value.code == 17 and calls == [["synthetic-command"]]
    prior = output.read_bytes()
    document = json.loads(prior)
    assert set(document) == {"environment", "results"}
    assert document["results"][0]["exit_code"] == 17
    log = tmp_path / "checks-00.log"
    prior_log = log.read_bytes()
    with pytest.raises(SystemExit, match="already exist"):
        execute(*arguments)
    assert calls == [["synthetic-command"]]
    assert output.read_bytes() == prior and log.read_bytes() == prior_log


def test_log_created_after_reservation_is_not_overwritten(driver, tmp_path, monkeypatch):
    output = tmp_path / "checks.json"
    execute = driver["run_checks"]
    snapshot = {"sha256": "synthetic-fixed-source"}
    log = tmp_path / "checks-00.log"

    def source_snapshot(_):
        log.write_bytes(b"another retained log")
        return snapshot

    monkeypatch.setitem(execute.__globals__, "source_snapshot", source_snapshot)

    def must_not_run(*args, **kwargs):
        raise AssertionError("existing log must not be overwritten or command executed")

    monkeypatch.setattr(subprocess, "run", must_not_run)
    with pytest.raises(FileExistsError):
        execute(
            tmp_path,
            output,
            snapshot,
            (),
            (),
            [["synthetic-command"]],
            [sys.executable],
            tmp_path / "bytecode",
            {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(tmp_path / "bytecode")},
        )
    assert log.read_bytes() == b"another retained log"
    assert json.loads(output.read_text())["results"] == []


def test_driver_propagates_the_requested_interpreter_to_every_python_gate(
    driver, tmp_path, monkeypatch
):
    main = driver["main"]
    globals_ = main.__globals__
    (tmp_path / "pyproject.toml").write_text('[project]\nname="synthetic"\nversion="0.0.0"\n')
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_candidate.py",
            "--package",
            str(tmp_path),
            "--uv",
            "uv",
            "--output",
            str(tmp_path / "checks.json"),
            "--python",
            "3.10",
        ],
    )
    monkeypatch.setitem(globals_, "source_snapshot", lambda _: {})
    canonical_checks = []
    monkeypatch.setitem(globals_, "require_canonical_git_bytes", canonical_checks.append)
    monkeypatch.setitem(globals_, "dependency_artifacts", lambda _: ())
    monkeypatch.setitem(globals_, "local_dependency_names", lambda _: ())
    captured = []
    monkeypatch.setitem(globals_, "run_checks", lambda *args: captured.append(args))
    main()
    assert canonical_checks == [tmp_path]
    commands = captured[0][5]
    offset = commands[0].index("--python")
    assert commands[0][offset : offset + 2] == ["--python", "3.10"]
    assert commands[0][-2:] == ["--reinstall-package", "synthetic"]
    assert "--no-editable" in commands[0]
    for command in commands[1:]:
        assert command[command.index("--python") + 1] == "3.10"
    assert captured[0][6][-3:] == ["--python", "3.10", "python"]


def test_interpreter_identity_observes_the_actual_executable(driver, tmp_path):
    environment = driver["candidate_environment"](tmp_path / "bytecode")
    identity = driver["interpreter_identity"]([sys.executable], tmp_path, environment)
    assert identity["python"] == driver["platform"].python_version()
    assert Path(identity["executable"]).resolve() == Path(sys.executable).resolve()
