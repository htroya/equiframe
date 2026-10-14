"""Adversarial input checks for the private root-trace revalidation tool."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

specification = importlib.util.spec_from_file_location(
    "root_context_input_safety",
    Path(__file__).parents[1] / "tools/revalidate_root_contexts.py",
)
checker = importlib.util.module_from_spec(specification)
specification.loader.exec_module(checker)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"evidence":1,"evidence":2}',
        b'{"score":NaN}',
        b'{"score":Infinity}',
        b'{"score":1e999}',
        b"\xff",
        b'{"missing":',
        b'{"tree":' + b"[" * 66 + b"0" + b"]" * 66 + b"}",
        b"[]",
    ],
)
def test_ambiguous_or_invalid_receipts_are_refused(tmp_path, payload):
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(payload)
    with pytest.raises(ValueError):
        checker.bounded_json(candidate)


def test_huge_receipt_is_refused_before_reading_its_contents(tmp_path):
    candidate = tmp_path / "huge.json"
    with candidate.open("wb") as stream:
        stream.truncate(64 * 1024**2 + 1)
    with pytest.raises(ValueError, match="file_budget_exceeded"):
        checker.bounded_json(candidate)


def test_excessive_tree_is_refused_within_the_byte_budget(tmp_path):
    candidate = tmp_path / "many.json"
    candidate.write_bytes(b'{"items":[' + b"0," * 750000 + b"0]}")
    with pytest.raises(ValueError, match="JSON structure budget"):
        checker.bounded_json(candidate)


def test_input_directory_link_is_refused_before_reading(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "candidate.json").write_bytes(b'{"safe":true}')
    link = tmp_path / "linked"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("platform lacks symlink permission")
    with pytest.raises(ValueError, match="ordinary directories"):
        checker.bounded_json(link / "candidate.json")


@pytest.mark.parametrize("digest", ["", "A" * 64, "0" * 63, "0" * 65, "../receipt"])
def test_malformed_external_baseline_identity_is_refused(digest):
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        checker.verify_baseline_digest(b'{"baseline":"fresh"}', digest)


def test_fresh_baseline_requires_explicit_trusted_identity():
    raw = b'{"baseline":"fresh"}'
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="trusted identity"):
        checker.verify_baseline_digest(raw)
    checker.verify_baseline_digest(raw, digest)
    with pytest.raises(ValueError, match="trusted identity"):
        checker.verify_baseline_digest(raw + b" ", digest)
