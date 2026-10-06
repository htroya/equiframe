"""Old snapshot APIs are aliases, never a competing implementation or format."""

import hashlib
from pathlib import Path

import equiframe as ef
import equiframe.snapshot as core
import pytest
from equiframe._documents import Document, digest, save_document

import equiframe_benchmark as eb
import equiframe_benchmark.snapshot as legacy
from equiframe_benchmark import io, models


@pytest.mark.parametrize(
    "name",
    [
        "SnapshotClient",
        "SnapshotColumn",
        "SnapshotDataSource",
        "SnapshotManifest",
        "SnapshotTable",
        "snapshot_fingerprint",
    ],
)
def test_old_and_new_imports_are_the_same_objects(name):
    assert getattr(eb, name) is getattr(legacy, name) is getattr(core, name) is getattr(ef, name)


def test_shared_primitives_remain_compatibility_aliases():
    assert models.Document is Document
    assert models.digest is digest
    assert io.save_document is save_document
    assert issubclass(legacy.SnapshotManifest, models.Document)


def test_shipped_historical_manifest_schema_is_unchanged():
    path = Path(__file__).resolve().parents[1] / "schemas/SnapshotManifest-1.0.schema.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "213bd042e61f312908d8800bddb508c7aace554088c7d4875cfef6015099595f"
    )
