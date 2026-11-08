"""Stable API error codes and printable JSON paths; issues omit rejected inputs."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    location: tuple[str | int, ...]
    message: str

    @property
    def path(self) -> str:
        path = "$"
        for part in self.location:
            if isinstance(part, int):
                path += f"[{part}]"
            elif part.isidentifier():
                path += "." + part
            else:
                path += "[" + json.dumps(part, ensure_ascii=True) + "]"
        return path


class EquiFrameError(Exception):
    code = "equiframe_error"


class ContractValidationError(EquiFrameError):
    code = "invalid_contract"

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"{item.path}: {item.message} [{item.code}]" for item in issues))


class SchemaVersionError(ContractValidationError):
    code = "unsupported_schema_version"


class ContractParseError(ContractValidationError):
    code = "invalid_json"


class ContractIOError(EquiFrameError):
    code = "contract_io_error"


class InvalidExecutionInput(EquiFrameError):
    code = "invalid_execution_input"


class CapabilityError(InvalidExecutionInput):
    code = "unsupported_capability"


class MissingDependencyError(CapabilityError):
    code = "missing_optional_dependency"


class ArtifactIntegrityError(InvalidExecutionInput):
    code = "artifact_integrity_error"


class ArtifactIOError(EquiFrameError):
    code = "artifact_io_error"


class ExecutionCancelled(EquiFrameError):
    code = "execution_cancelled"


class ExecutionTimeout(EquiFrameError):
    code = "execution_timeout"


class ResourceLimitError(EquiFrameError):
    code = "resource_limit"


class NativeEngineError(EquiFrameError):
    code = "native_engine_error"
