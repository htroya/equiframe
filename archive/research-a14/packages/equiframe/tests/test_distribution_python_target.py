"""The installed typed-consumer gate must follow its actual Python, never weaken strictness."""

import ast
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def command_builder(probe):
    # Compile only this stdlib helper: importing the full CLI would require tool-directory imports.
    source = Path(__file__).parents[1] / "tools/verify_distribution.py"
    module = ast.parse(source.read_text("utf-8"))
    helper = next(
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name == "typed_consumer_command"
    )
    namespace = {"Path": Path, "subprocess": SimpleNamespace(run=probe)}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["typed_consumer_command"]


@pytest.mark.parametrize("minor", ["3.10", "3.11", "3.12", "3.13"])
def test_installed_typed_consumer_uses_probed_minor_and_keeps_strict_config(minor):
    probe = Mock(return_value=SimpleNamespace(stdout=minor + "\n"))
    python, config, consumer = Path("venv/bin/python"), Path("pyproject.toml"), Path("consumer.py")
    command = command_builder(probe)(python, config, consumer)
    assert command == [
        str(python),
        "-I",
        "-m",
        "mypy",
        "--strict",
        "--python-version",
        minor,
        "--config-file",
        str(config),
        str(consumer),
    ]
    assert probe.call_args.args[0][:3] == [str(python), "-I", "-c"]
    assert probe.call_args.kwargs["check"] is True


def test_installed_typed_consumer_rejects_uncommitted_minor():
    probe = Mock(return_value=SimpleNamespace(stdout="3.14\n"))
    with pytest.raises(RuntimeError, match="outside the committed Python matrix"):
        command_builder(probe)(Path("python"), Path("config"), Path("consumer"))


def test_failed_interpreter_probe_cannot_make_a_type_check_command():
    probe = Mock(side_effect=subprocess.CalledProcessError(2, ["python", "-I", "-c"]))
    with pytest.raises(subprocess.CalledProcessError):
        command_builder(probe)(Path("python"), Path("config"), Path("consumer"))
