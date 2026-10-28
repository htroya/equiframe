"""Optional standalone diagnostics; no migration, detector or approval gate."""

from .api import analyze, analyze_artifact, analyze_migration, read_result
from .models import (
    ColumnProfile,
    Conversion,
    DuplicateProfile,
    EdaConfig,
    EdaManifest,
    EdaResult,
    Finding,
    KeyRule,
    NumericRule,
    Resources,
    ResultFile,
    Source,
)

__all__ = [
    "ColumnProfile",
    "Conversion",
    "DuplicateProfile",
    "EdaConfig",
    "EdaManifest",
    "EdaResult",
    "Finding",
    "KeyRule",
    "NumericRule",
    "Resources",
    "ResultFile",
    "Source",
    "analyze",
    "analyze_artifact",
    "analyze_migration",
    "read_result",
]
