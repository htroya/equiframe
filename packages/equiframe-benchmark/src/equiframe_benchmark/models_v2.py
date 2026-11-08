"""Strict schema-V2 documents without overriding the historical V1 literal."""

from typing import Literal

from pydantic import BaseModel

from equiframe_benchmark.models import Document


class DocumentV2(BaseModel):
    # Identical immutability/strictness; the V1 class and its readers stay intact.
    model_config = Document.model_config
    schema_version: Literal["2.0"] = "2.0"
