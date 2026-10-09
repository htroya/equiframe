"""Public states and minimal immutable artifact metadata (no execution results yet)."""

import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, PositiveInt, Text, fail

ExecutionState = Literal[
    "completed", "invalid_input", "failed", "timeout", "resource_exhausted", "cancelled"
]
DecisionState = Literal["alert", "no_alert", "not_evaluable"]
ComparisonState = Literal["equivalent", "different", "not_evaluable"]
OracleState = Literal["correct", "divergent", "pending", "not_evaluable"]
FitState = Literal["ready", "not_estimable", "incompatible"]
JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SchemaRef(FrozenModel):
    schema_id: Identifier
    revision: PositiveInt
    sha256: Sha256


class ArtifactRef(FrozenModel):
    schema_version: Literal["1.0"]
    uri: Text
    sha256: Sha256
    format: Literal["json", "jsonl", "arrow", "parquet"]
    media_type: Text
    size_bytes: NonNegativeInt
    schema_ref: SchemaRef | None = None

    @model_validator(mode="after")
    def reference_without_credentials(self) -> Self:
        try:
            parts = urlsplit(self.uri)
            host = parts.hostname
            port = parts.port
        except ValueError:
            fail("artifact_uri", "invalid artifact URI", "uri")
        if parts.scheme not in ("https", "file", "s3", "gs"):
            fail("artifact_uri", "allowed URI schemes: https, file, s3, gs", "uri")
        if (
            parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
        ):
            fail(
                "artifact_uri_secret",
                "artifact URI must not contain credentials, query or fragment",
                "uri",
            )
        if re.search(r"[\x00-\x20\x7f]", self.uri):
            fail(
                "artifact_uri", "artifact URI must not contain whitespace/control characters", "uri"
            )
        if "\\" in self.uri or re.search(r"%(?![0-9a-fA-F]{2})", self.uri):
            fail("artifact_uri", "artifact URI has an invalid separator or percent escape", "uri")
        if parts.scheme != "https" and port is not None:
            fail("artifact_uri", "only HTTPS artifact URIs may declare a port", "uri")
        if parts.scheme != "file" and not host:
            fail("artifact_uri", "remote artifact URI requires a host/bucket", "uri")
        if parts.scheme == "file" and not parts.path.startswith("/"):
            fail("artifact_uri", "file URI requires an absolute path", "uri")
        return self
