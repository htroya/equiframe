"""Real rejection boundaries for the private experiment's file and JSON inputs."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def tool(name):
    path = Path(__file__).parents[1] / "tools" / (name + ".py")
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


files = tool("thesis_packet_io")
checker = tool("check_thesis_packet")


@pytest.mark.parametrize("count", [0, 33, True, 1.0])
def test_preparation_rejects_unsealable_or_invalid_unit_count(tmp_path, count):
    preparation = tool("prepare_sercop_experiment")
    output = tmp_path / "packet"
    with pytest.raises(ValueError, match="integer units"):
        preparation.prepare(tmp_path / "unused.zip", output, count)
    assert not output.exists()


@pytest.mark.parametrize(
    "relative",
    [
        "../outside",
        "/outside",
        "C:/outside",
        "a\\b",
        "a//b",
        "CON.txt",
        "a.",
        "a/../../b",
        "",
        "bad\x00name",
    ],
)
def test_nonportable_and_escaping_paths_are_rejected(tmp_path, relative):
    with pytest.raises((ValueError, OSError)):
        files.local_path(tmp_path, relative)


def test_json_and_file_reads_enforce_byte_budgets(tmp_path):
    (tmp_path / "file.json").write_bytes(b"1234")
    with pytest.raises(ValueError, match="file_budget_exceeded"):
        files.read_bytes(tmp_path, "file.json", limit=3)
    assert files.read_bytes(tmp_path, "file.json", limit=4) == b"1234"


@pytest.mark.parametrize(
    "payload",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":1e999}',
        b"\xff",
        b'{"a":',
        b"[" * 66 + b"0" + b"]" * 66,
    ],
)
def test_ambiguous_nonfinite_or_oversized_structures_are_rejected(tmp_path, payload):
    (tmp_path / "file.json").write_bytes(payload)
    with pytest.raises(ValueError):
        files.read_json(tmp_path, "file.json")


def seal(directory):
    document = {
        "schema": "equiframe.private-packet-integrity.v1",
        "files": files.inventory(directory),
    }
    (directory / "integrity-manifest.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    return document


def test_inventory_rejects_modified_and_undeclared_files(tmp_path):
    (tmp_path / "evidence.txt").write_bytes(b"approved fixture")
    original = seal(tmp_path)
    assert files.verify_inventory(tmp_path) == original
    (tmp_path / "evidence.txt").write_bytes(b"modified fixture")
    with pytest.raises(ValueError, match="packet_inventory_mismatch"):
        files.verify_inventory(tmp_path)
    (tmp_path / "evidence.txt").write_bytes(b"approved fixture")
    (tmp_path / "extra.txt").write_bytes(b"undeclared")
    with pytest.raises(ValueError, match="packet_inventory_mismatch"):
        files.verify_inventory(tmp_path)


def test_symlink_is_rejected_before_read(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.write_bytes(b"private fixture")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("platform lacks symlink permission")
    with pytest.raises(ValueError, match="linked_path"):
        files.read_bytes(tmp_path, "link.txt")


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.invalid/private.arrow",
        "file://server/share/private.arrow",
        "file:///outside.arrow?token=example",
        "file:///outside.arrow#fragment",
    ],
)
def test_artifact_references_never_fetch_remote_or_ambiguous_uris(tmp_path, uri):
    reference = SimpleNamespace(uri=uri, sha256="0" * 64, size_bytes=0)
    with pytest.raises(ValueError, match="nonlocal_artifact_uri"):
        files.verify_reference(tmp_path, reference)


def test_artifact_cannot_read_outside_packet_or_claim_wrong_hash(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside.arrow")
    outside.write_bytes(b"outside fixture")
    ref = SimpleNamespace(
        uri=outside.as_uri(),
        sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
        size_bytes=outside.stat().st_size,
    )
    with pytest.raises(ValueError, match="artifact_outside_packet"):
        files.verify_reference(tmp_path, ref)
    local = tmp_path / "file.arrow"
    local.write_bytes(b"inside fixture")
    ref.uri, ref.size_bytes = local.as_uri(), local.stat().st_size
    with pytest.raises(ValueError, match="artifact_identity_mismatch"):
        files.verify_reference(tmp_path, ref)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scientific_ready", True),
        ("human_review_complete", True),
        ("confirmed_normal_profiles", 1),
        ("confirmed_normal_profiles", False),
    ],
)
def test_resealed_metadata_cannot_accredit_unreviewed_science(tmp_path, field, value):
    root = tmp_path / "packet"
    root.mkdir()
    document = {
        "schema": "equiframe.sercop-experiment-preparation.v1",
        "source_sha256": checker.SOURCE_SHA256,
        "candidate": "0.12.0a14",
        "scientific_ready": False,
        "human_review_complete": False,
        "confirmed_normal_profiles": 0,
    }
    document[field] = value
    (root / "preparation-manifest.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    seal(root)
    output = tmp_path / "verifier"
    with pytest.raises(ValueError, match="unconfirmed_scientific_claim"):
        checker.check(root, output)
    assert not output.exists()


def test_strict_json_models_accept_arrays_but_reject_coerced_scalars():
    import equiframe as ef

    assert checker.model_from_json(
        ef.ProfileFeature,
        {
            "name": "missing",
            "metric": "tasa_nulos",
            "table": "result",
            "columns": ["amount"],
        },
    ).columns == ("amount",)
    with pytest.raises(ValueError):
        checker.model_from_json(
            ef.IntegerType, {"kind": "integer", "bits": "64", "signed": True}
        )
