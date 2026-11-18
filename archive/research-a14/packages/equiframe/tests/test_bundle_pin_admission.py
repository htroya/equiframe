"""A supplied manifest pin must never be silently treated as absent."""

import hashlib
import json

import pytest
from test_migration import run

import equiframe as ef


@pytest.fixture(scope="module")
def portable(tmp_path_factory):
    root = tmp_path_factory.mktemp("manifest-pin-admission")
    result = run(root / "runs")
    destination = root / "portable"
    bundle = ef.export_bundle(root / "runs" / result.migration_id, destination)
    return destination, bundle


@pytest.mark.parametrize("pin", ["", 0, False, [], {}, 0.0, ()])
@pytest.mark.parametrize("operation", ["read", "inspect", "import"])
def test_falsey_supplied_manifest_pins_are_not_absent(portable, tmp_path, operation, pin):
    root, _ = portable
    with pytest.raises(ef.ArtifactIntegrityError, match="trusted SHA-256"):
        if operation == "read":
            ef.read_bundle(root, expected_sha256=pin)
        elif operation == "inspect":
            ef.inspect_bundle(root, expected_sha256=pin)
        else:
            ef.import_bundle(root, tmp_path / "imported", expected_sha256=pin)
    assert not (tmp_path / "imported").exists()


def test_only_none_omits_pin_and_correct_pin_is_enforced(portable):
    root, original = portable
    manifest = root / "bundle.json"
    before = manifest.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    assert ef.read_bundle(root, expected_sha256=digest) == original
    assert ef.read_bundle(root, expected_sha256=None) == original
    data = json.loads(before)
    data["producer_version"] = "0.11.1"
    try:
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ef.ArtifactIntegrityError, match="trusted SHA-256"):
            ef.read_bundle(root, expected_sha256=digest)
        changed_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        changed = ef.read_bundle(root, expected_sha256=changed_digest)
        assert changed.producer_version == "0.11.1"
        assert ef.read_bundle(root, expected_sha256=None) == changed
    finally:
        manifest.write_bytes(before)
