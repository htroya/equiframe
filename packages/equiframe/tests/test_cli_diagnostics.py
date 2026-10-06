"""Ordinary input/configuration failures remain concise and actionable."""

import json

import pytest
import typer
from pydantic import ValidationError
from typer.testing import CliRunner

from equiframe._cli_support import exit_with_failure, failure_hint
from equiframe.cli import app
from equiframe.errors import (
    ArtifactIntegrityError,
    ArtifactIOError,
    CapabilityError,
    ContractIOError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    MissingDependencyError,
    NativeEngineError,
    ResourceLimitError,
)
from equiframe.verification_request import VerificationRequest


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (FileNotFoundError("private-path"), "missing_path"),
        (FileExistsError("private-path"), "existing_output"),
        (PermissionError("private-path"), "permission_denied"),
        (IsADirectoryError("private-path"), "path_kind"),
        (NotADirectoryError("private-path"), "path_kind"),
        (MissingDependencyError("private-data"), "optional_dependency"),
        (ModuleNotFoundError("private-module"), "module_unavailable"),
        (ArtifactIntegrityError("private-data"), "evidence_integrity"),
        (CapabilityError("private-data"), "unsupported_capability"),
        (ExecutionCancelled("private-data"), "cancelled"),
        (ExecutionTimeout("private-data"), "timeout"),
        (ResourceLimitError("private-data"), "resource_limit"),
        (NativeEngineError("private-data"), "native_engine"),
        (OSError("private-path"), "io_failure"),
        (ArtifactIOError("private-path"), "io_failure"),
        (ContractIOError("private-path"), "io_failure"),
        (json.JSONDecodeError("private-data", "private-document", 0), "document_syntax"),
        (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "private-data"), "document_syntax"),
        (ValueError("private-data"), "input_configuration"),
        (InvalidExecutionInput("private-data"), "input_configuration"),
        (RuntimeError("private-data"), "operation_failure"),
    ],
)
def test_categories_keep_fixed_hints_and_caller_exit_policy(error, category):
    command = typer.Typer()

    @command.command()
    def fail():
        exit_with_failure(error, code="operation_failed", exit_code=3)

    result = CliRunner().invoke(command, [])
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr.splitlines()[0] == "operation_failed"
    assert result.stderr.splitlines()[1].startswith(f"hint[{category}]: ")
    assert len(result.stderr.splitlines()) == 2
    assert "private-" not in result.stderr and "Traceback" not in result.stderr


def test_validation_hint_distinguishes_request_from_stored_evidence():
    with pytest.raises(ValidationError) as caught:
        VerificationRequest.model_validate_json("{}")
    assert failure_hint(caught.value)[0] == "document_validation"
    assert failure_hint(caught.value, input_validation=False)[0] == "evidence_validation"
    assert failure_hint(ValueError("private-data"), input_validation=False)[0] == (
        "evidence_validation"
    )


@pytest.mark.parametrize(
    ("contents", "category"), [("{}", "document_validation"), ("{", "document_syntax")]
)
def test_invalid_request_guides_consumer_without_changing_exit(tmp_path, contents, category):
    source = tmp_path / "request.json"
    source.write_text(contents, encoding="utf-8")
    result = CliRunner().invoke(app, ["verify", "validate", str(source)])
    assert result.exit_code == 2 and not result.stdout
    assert result.stderr.splitlines()[0] == "invalid_input"
    assert f"hint[{category}]" in result.stderr
    assert str(tmp_path) not in result.stderr


def test_missing_request_guides_consumer_without_changing_exit(tmp_path):
    result = CliRunner().invoke(app, ["verify", "validate", str(tmp_path / "missing.json")])
    assert result.exit_code == 3 and not result.stdout
    assert result.stderr.splitlines()[0] == "operation_failed"
    assert "hint[missing_path]" in result.stderr


def test_unexpected_exception_is_not_formatted():
    class UnprintableError(Exception):
        def __str__(self):
            raise AssertionError("diagnostic must not format arbitrary exceptions")

    assert failure_hint(UnprintableError())[0] == "operation_failure"
