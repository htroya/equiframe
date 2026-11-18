"""Versioned scope shared by the existing lab and its strict offline reviewer."""

from __future__ import annotations

LEGACY_PYTHONS = ("3.10", "3.12")
UNIVERSALITY_PYTHONS = ("3.10", "3.11", "3.12", "3.13")
CANDIDATE_V1 = "equiframe-maturity-candidate-1"
CANDIDATE_V2 = "equiframe-maturity-candidate-2"
RECEIPT_V1 = "equiframe-maturity-vm-execution-1"
RECEIPT_V2 = "equiframe-maturity-vm-execution-2"


def required_pythons(candidate: dict) -> tuple[str, ...]:
    schema = candidate.get("schema")
    if schema == CANDIDATE_V1:
        expected = LEGACY_PYTHONS
    elif schema == CANDIDATE_V2:
        expected = UNIVERSALITY_PYTHONS
    else:
        raise ValueError("unsupported candidate schema")
    actual = candidate.get("required_python_versions")
    if candidate.get("scope_id") is not None and (
        schema != CANDIDATE_V1
        or candidate["scope_id"] != "M13-ARM-ORIGINAL-v1"
        or candidate.get("required_runtime_identity") is not True
        or actual != list(LEGACY_PYTHONS)
    ):
        raise ValueError(
            "new original M13 scope requires complete explicit runtime identity"
        )
    if (schema == CANDIDATE_V2 or actual is not None) and actual != list(expected):
        raise ValueError(
            "required Python scope cannot be omitted, reordered or reduced"
        )
    return expected


def requires_runtime_identity(candidate: dict) -> bool:
    required_pythons(candidate)
    return (
        candidate["schema"] == CANDIDATE_V2
        or candidate.get("scope_id") == "M13-ARM-ORIGINAL-v1"
    )


def receipt_schema(candidate: dict) -> str:
    required_pythons(candidate)
    return RECEIPT_V1 if candidate["schema"] == CANDIDATE_V1 else RECEIPT_V2


def validate_cell_scope(candidate: dict, receipt: dict) -> tuple[str, ...]:
    expected = required_pythons(candidate)
    if receipt.get("schema") != receipt_schema(candidate):
        raise ValueError("receipt schema differs from candidate scope")
    if candidate["schema"] == CANDIDATE_V2 and receipt.get(
        "required_python_versions"
    ) != list(expected):
        raise ValueError("receipt required Python scope differs")
    cells = receipt.get("python_cells", [])
    actual = [cell.get("minor") for cell in cells]
    if len(actual) != len(expected) or set(actual) != set(expected):
        raise ValueError("all required Python minors must occur exactly once")
    return expected
