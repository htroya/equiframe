"""Versioned source and content identities for the convenience file reader."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, cast

from equiframe.errors import InvalidExecutionInput


def _digest(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("A lowercase SHA-256 identity is required")


@dataclass(frozen=True)
class DatasetSource:
    """Identity of the exact bytes consumed, plus the effective reader options."""

    uri: str
    format: str
    sha256: str
    size_bytes: int
    read_options_json: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _digest(self.sha256)
        if self.schema_version != "1.0" or not self.uri:
            raise ValueError("Unknown dataset source version or missing URI")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("Source size must be a nonnegative integer")
        if not isinstance(json.loads(self.read_options_json), dict):
            raise ValueError("Reader options must be an object")

    @property
    def read_options(self) -> dict[str, Any]:
        # Return a new object so a caller cannot mutate the recorded options.
        return cast("dict[str, Any]", json.loads(self.read_options_json))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["read_options"] = result.pop("read_options_json")
        result["read_options"] = self.read_options
        return result


@dataclass(frozen=True)
class DatasetProvenance:
    """One source snapshot -> original Pandas snapshot -> native destination."""

    source: DatasetSource
    pandas_sha256: str
    target: str
    target_sha256: str
    fingerprint_version: str = "equiframe-dataset-content-1.0"

    def __post_init__(self) -> None:
        _digest(self.pandas_sha256)
        _digest(self.target_sha256)
        if self.target not in ("pandas", "polars", "duckdb"):
            raise ValueError("Unknown dataset destination")
        if self.fingerprint_version != "equiframe-dataset-content-1.0":
            raise ValueError("Unknown dataset fingerprint version")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "pandas_sha256": self.pandas_sha256,
            "target": self.target,
            "target_sha256": self.target_sha256,
            "fingerprint_version": self.fingerprint_version,
        }


def _value(value: Any, pandas: Any) -> Any:
    if value is None:
        return ["null"]
    if value is pandas.NA:
        return ["pandas_na"]
    if value is pandas.NaT:
        return ["pandas_nat"]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, float):
        return ["float", "nan" if math.isnan(value) else value.hex()]
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, bytes):
        return ["binary", value.hex()]
    if isinstance(value, datetime):
        return ["timestamp", value.isoformat(), value.fold]
    if isinstance(value, (date, time)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, pandas.Timedelta):
        return ["duration_ns", str(value.value)]
    if isinstance(value, timedelta):
        return ["duration", value.days, value.seconds, value.microseconds]
    if isinstance(value, Mapping):
        return [
            "object",
            [[_value(key, pandas), _value(item, pandas)] for key, item in value.items()],
        ]
    if isinstance(value, (list, tuple)):
        return ["array", [_value(item, pandas) for item in value]]
    raise InvalidExecutionInput("Dataset values cannot be fingerprinted without conversion")


def _update(digest: Any, value: Any) -> None:
    digest.update(
        json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    )
    digest.update(b"\n")


def pandas_fingerprint(frame: Any, pandas: Any) -> str:
    """Identify every observed value and native dtype, without sampling."""
    digest = hashlib.sha256()
    _update(digest, ["equiframe-dataset-content-1.0", "pandas", len(frame)])
    for name in frame.columns:
        _update(digest, [name, str(frame[name].dtype)])
        for value in frame[name].tolist():
            _update(digest, _value(value, pandas))
    return digest.hexdigest()


def arrow_fingerprint(table: Any, pandas: Any) -> str:
    digest = hashlib.sha256()
    _update(digest, ["equiframe-dataset-content-1.0", "arrow", table.num_rows])
    for field, column in zip(table.schema, table.columns, strict=False):
        _update(digest, [field.name, str(field.type), field.nullable])
        for chunk in column.chunks:
            for scalar in chunk:
                _update(digest, _value(scalar.as_py(), pandas))
    return digest.hexdigest()
