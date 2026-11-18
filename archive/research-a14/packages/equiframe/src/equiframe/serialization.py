"""Versioned canonical metadata bytes, strict JSON I/O, and SHA-256 fingerprints."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from equiframe.contracts import SCHEMA_VERSION, Contract
from equiframe.errors import (
    ContractIOError,
    ContractParseError,
    ContractValidationError,
    SchemaVersionError,
    ValidationIssue,
)

CANONICALIZATION = "equiframe-metadata-json-v1"


def _parse_issue(code: str, message: str) -> ContractParseError:
    return ContractParseError((ValidationIssue(code, (), message),))


@dataclass
class _JsonObject:
    pairs: list[tuple[str, object]]


def _unique_objects(value: object, location: tuple[str | int, ...] = ()) -> object:
    if isinstance(value, _JsonObject):
        result: dict[str, object] = {}
        for key, member in value.pairs:
            if key in result:
                raise ContractParseError(
                    (
                        ValidationIssue(
                            "duplicate_json_key",
                            (*location, key),
                            "duplicate JSON object key: " + json.dumps(key, ensure_ascii=True),
                        ),
                    )
                )
            result[key] = _unique_objects(member, (*location, key))
        return result
    if isinstance(value, list):
        return [_unique_objects(member, (*location, index)) for index, member in enumerate(value)]
    return value


def _constant(value: str) -> object:
    raise _parse_issue("nonstandard_json_number", "nonstandard JSON number: " + value)


def validate_contract(document: str | bytes | Mapping[str, object]) -> Contract:
    """Validate JSON text/UTF-8 bytes or a JSON-compatible mapping with identical semantics."""
    try:
        if isinstance(document, bytes):
            raw = document.decode("utf-8")
        elif isinstance(document, str):
            raw = document
        else:
            raw = json.dumps(dict(document), ensure_ascii=False, allow_nan=False)
        parsed = _unique_objects(
            json.loads(raw, object_pairs_hook=_JsonObject, parse_constant=_constant)
        )
    except (UnicodeError, TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc, json.JSONDecodeError):
            raise _parse_issue(
                "json_syntax", f"invalid JSON at line {exc.lineno}, column {exc.colno}"
            ) from exc
        raise _parse_issue("json_encoding", "expected a UTF-8, standard JSON document") from exc
    if not isinstance(parsed, dict):
        raise _parse_issue("json_object", "contract document must be an object")
    version: object = parsed.get("schema_version")
    if isinstance(version, str) and version != SCHEMA_VERSION:
        raise SchemaVersionError(
            (
                ValidationIssue(
                    "unsupported_schema_version",
                    ("schema_version",),
                    "supported schema_version is " + SCHEMA_VERSION,
                ),
            )
        )
    try:
        return Contract.model_validate_json(raw)
    except ValidationError as exc:
        raise ContractValidationError(
            tuple(
                ValidationIssue(item["type"], item["loc"], item["msg"])
                for item in exc.errors(include_url=False, include_input=False)
            )
        ) from exc


def canonical_contract_bytes(contract: Contract) -> bytes:
    """Canonical v1: all defaults/nulls, UTF-8, sorted keys, ordered arrays, no whitespace."""
    # Revalidate copies made with Pydantic's explicitly unvalidated model_copy/model_construct.
    try:
        validated = Contract.model_validate(contract)
    except ValidationError as exc:
        raise ContractValidationError(
            tuple(
                ValidationIssue(item["type"], item["loc"], item["msg"])
                for item in exc.errors(include_url=False, include_input=False)
            )
        ) from exc
    return json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def contract_fingerprint(contract: Contract) -> str:
    """Hash canonical contract metadata, including identity/revision; never prove table equality."""
    return hashlib.sha256(canonical_contract_bytes(contract)).hexdigest()


def read_contract(path: str | Path) -> Contract:
    from equiframe._regular_io import local_input_path, open_regular_file
    from equiframe.errors import ArtifactIOError, ResourceLimitError

    try:
        with open_regular_file(local_input_path(Path(path))) as stream:
            document = stream.read(64 * 1024 * 1024 + 1)
    except ArtifactIOError as exc:
        cause = exc.__cause__ if isinstance(exc.__cause__, OSError) else exc
        raise ContractIOError("cannot read contract file") from cause
    except (OSError, ValueError) as exc:
        raise ContractIOError("cannot read contract file") from exc
    if len(document) > 64 * 1024 * 1024:
        raise ResourceLimitError("contract exceeds the 64 MiB document budget")
    return validate_contract(document)


def write_contract(contract: Contract, path: str | Path) -> None:
    data = canonical_contract_bytes(contract)
    try:
        Path(path).write_bytes(data)
    except (OSError, ValueError) as exc:
        raise ContractIOError("cannot write contract file: " + ascii(str(path))) from exc


def contract_json_schema() -> dict[str, object]:
    """Structural JSON Schema; cross-table/type/timezone constraints use validate_contract."""
    return Contract.model_json_schema(mode="validation")
