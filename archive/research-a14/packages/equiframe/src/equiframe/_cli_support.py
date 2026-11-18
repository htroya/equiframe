"""Fixed-text CLI guidance, separate from semantic decisions and exit-code policy.

The caller owns its historical code and status. This helper never formats an
exception, cause, model error, path or user-supplied value into terminal output.
"""

import json

import typer
from pydantic import ValidationError
from typing_extensions import Never

from equiframe.errors import (
    ArtifactIntegrityError,
    ArtifactIOError,
    CapabilityError,
    ContractIOError,
    ContractValidationError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    MissingDependencyError,
    NativeEngineError,
    ResourceLimitError,
)


def failure_hint(error: Exception, *, input_validation: bool = True) -> tuple[str, str]:
    """Return a bounded category and actionable guidance without inspecting payloads."""
    if isinstance(error, (ArtifactIOError, ContractIOError)) and isinstance(
        error.__cause__,
        (
            FileNotFoundError,
            FileExistsError,
            PermissionError,
            IsADirectoryError,
            NotADirectoryError,
        ),
    ):
        # Inspect only the immediate OS error class, never its path or message.
        return failure_hint(error.__cause__, input_validation=input_validation)
    if isinstance(error, FileNotFoundError):
        return "missing_path", "Check that the requested input and its parent directory exist."
    if isinstance(error, FileExistsError):
        return "existing_output", "Choose a new output path; existing evidence is not overwritten."
    if isinstance(error, PermissionError):
        return "permission_denied", "Check read access to inputs and write access to the output."
    if isinstance(error, (IsADirectoryError, NotADirectoryError)):
        return "path_kind", "Check which arguments require files and which require directories."
    if isinstance(error, MissingDependencyError):
        return "optional_dependency", "Check the required extra in this interpreter's environment."
    if isinstance(error, ImportError):
        return "module_unavailable", "Check the selected module and its installed dependencies."
    if isinstance(error, ArtifactIntegrityError):
        return "evidence_integrity", "Restore the original evidence or rerun into a new directory."
    if isinstance(error, CapabilityError):
        return "unsupported_capability", "Check the documented engine and representation limits."
    if isinstance(error, ExecutionCancelled):
        return "cancelled", "Keep partial evidence; retry only when the operation is still needed."
    if isinstance(error, ExecutionTimeout):
        return "timeout", "Review the workload and explicit time budget before retrying."
    if isinstance(error, ResourceLimitError):
        return (
            "resource_limit",
            "Review the workload and explicit resource budgets before retrying.",
        )
    if isinstance(error, NativeEngineError):
        return "native_engine", "Inspect the recorded stage and the trusted native transformation."
    if isinstance(error, (OSError, ArtifactIOError, ContractIOError)):
        return "io_failure", "Check input availability, output access and available disk space."
    if isinstance(error, (json.JSONDecodeError, UnicodeDecodeError)):
        return "document_syntax", "Use a valid UTF-8 JSON document for the selected command."
    if isinstance(error, (ValidationError, ContractValidationError)):
        if isinstance(error, ContractValidationError) and any(
            issue.code == "duplicate_json_key" for issue in error.issues
        ):
            return (
                "duplicate_json_key",
                "Use one value per JSON member; duplicate keys are refused.",
            )
        return (
            (
                "document_validation",
                "Check the request's required fields, types and schema version.",
            )
            if input_validation
            else (
                "evidence_validation",
                "Check the evidence format and restore its original files.",
            )
        )
    if isinstance(error, (ValueError, InvalidExecutionInput)):
        return (
            ("input_configuration", "Check the command arguments and declared input constraints.")
            if input_validation
            else (
                "evidence_validation",
                "Check the evidence format and restore its original files.",
            )
        )
    return "operation_failure", "Inspect any retained evidence and prepare a minimal reproduction."


def write_failure(
    error: Exception,
    *,
    code: str,
    input_validation: bool = True,
) -> None:
    """Retain the original first-line code and add one fixed, human-readable hint."""
    category, hint = failure_hint(error, input_validation=input_validation)
    typer.echo(code, err=True)
    typer.echo(f"hint[{category}]: {hint}", err=True)


def exit_with_failure(
    error: Exception,
    *,
    code: str,
    exit_code: int,
    input_validation: bool = True,
) -> Never:
    """Write guidance and preserve the caller's existing Typer exit-code policy."""
    write_failure(error, code=code, input_validation=input_validation)
    raise typer.Exit(code=exit_code) from None
