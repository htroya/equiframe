"""Unsupported expected inputs fail consistently without changing valid evidence."""

import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

import equiframe as ef


@pytest.mark.parametrize(
    "unsupported", [object(), 0, "", []], ids=["object", "zero", "text", "list"]
)
def test_unsupported_expected_capture_is_nonpublishable(tmp_path, unsupported):
    column = ef.ColumnSpec(
        name="x",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    contract = ef.bag_contract([column]).spec.contract
    artifact = ef.capture_duckdb(
        "SELECT * FROM (VALUES (7::BIGINT),(3::BIGINT)) t(x)", work_dir=tmp_path / "capture"
    ).data
    path = Path(url2pathname(urlparse(artifact.uri).path))
    original = path.read_bytes()
    baseline = ef.verify(
        {"result": artifact}, contract=contract, expected=artifact, work_dir=tmp_path / "valid"
    )
    assert baseline.operational_state == "passed" and baseline.publishable
    preserved = (tmp_path / "valid" / baseline.verification_id / "verification.json").read_bytes()
    result = ef.verify(
        {"result": artifact}, contract=contract, expected=unsupported, work_dir=tmp_path / "bad"
    )
    assert result.operational_state == "failed" and not result.publishable and result.exit_code == 1
    assert result.integrity.state == "failed" and result.expected[0].state == "not_evaluable"
    assert not result.coverage.complete
    assert result.coverage.outputs_requested == result.coverage.outputs_inspected == 1
    assert result.coverage.comparisons_requested == 2
    assert result.coverage.comparisons_completed == 1
    assert result.expected_artifact is None
    assert result.outputs[0][1].sha256 == artifact.sha256
    assert ef.read_verification(tmp_path / "bad" / result.verification_id) == result
    assert path.read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == artifact.sha256
    assert (
        tmp_path / "valid" / baseline.verification_id / "verification.json"
    ).read_bytes() == preserved
