"""Private strict document primitives shared with the experimental package.

This preserves the historical ASCII-escaped JSON v1 encoding exactly. It is
intentionally distinct from contract canonicalization; do not silently switch
encodings or normalize existing fingerprints when refactoring consumers.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from equiframe.types import ArtifactRef


def canonical_text(value: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError("text and identities must be canonical, without surrounding whitespace")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("invalid Unicode scalar")
    return value


Text = Annotated[str, StringConstraints(min_length=1), AfterValidator(canonical_text)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Document(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        revalidate_instances="always",
        validate_default=True,
    )
    schema_version: Literal["1.0"] = "1.0"


def canonical_document_bytes(document: BaseModel) -> bytes:
    """Preserve the historical document encoding; callers revalidate their model."""
    return json.dumps(
        document.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def digest(document: BaseModel) -> str:
    return hashlib.sha256(canonical_document_bytes(document)).hexdigest()


def checked_artifact(ref: ArtifactRef) -> ArtifactRef:
    if not ref.sha256 or ref.size_bytes is None or ref.format not in ("arrow", "parquet"):
        raise ValueError("tabular evidence requires SHA-256, size and Arrow/Parquet format")
    return ref


Evidence = Annotated[ArtifactRef, AfterValidator(checked_artifact)]


def save_document(document: BaseModel, path: Path) -> None:
    document = type(document).model_validate(document)
    data = canonical_document_bytes(document)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with temporary.open("xb") as stream:
            stream.write(data + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
