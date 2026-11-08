"""Publish scale receipts only when their strict reader can consume them."""

from pathlib import Path

from equiframe.errors import ResourceLimitError
from equiframe.evidence import MAX_DOCUMENT_BYTES, canonical_bytes

from equiframe_benchmark.io import save_document
from equiframe_benchmark.models import Document

MAX_SCALE_DOCUMENT_BYTES = MAX_DOCUMENT_BYTES


def save_scale_document(document: Document, path: Path) -> None:
    document = type(document).model_validate(document)
    size = len(canonical_bytes(document.model_dump(mode="json"))) + 1
    if size > MAX_SCALE_DOCUMENT_BYTES:
        raise ResourceLimitError("scale document exceeds its reader publication budget")
    save_document(document, path)
