"""Exercise the public consumer scripts with bounded, explicitly synthetic sources."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_retail_complete_installed_consumer(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(EXAMPLES / "retail_etl.py"), "--output", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["complete"] and summary["idempotent"] and summary["portable_bundle_verified"]
    assert summary["ingested_rows"] == 3
    assert summary["checkpoints"] == ["passed", "passed"]


def test_sercop_offline_bridge_does_not_multiply_amounts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(EXAMPLES / "sercop_etl.py"),
            "--snapshot",
            str(EXAMPLES / "sercop_offline"),
            "--expected",
            str(EXAMPLES / "sercop_offline/expected.json"),
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["synthetic"]
    assert summary["rows"] == {"awards": 2, "suppliers": 3, "items": 3, "procedures": 1}
    assert len(summary["migrations"]) == 6
    assert summary["subset_reconciliation"]["state"] == "equivalent"
    assert summary["scientific_O"] == "not_established"
    assert summary["idempotent"] and summary["portable_bundle_verified"]


@pytest.mark.parametrize("relation", ["suppliers", "items"])
def test_sercop_partial_relation_absence_cannot_silently_drop_valid_links(tmp_path, relation):
    payload = json.loads((EXAMPLES / "sercop_offline/record-0.json").read_bytes())
    assert payload["releases"][0]["awards"][0][relation]
    payload["releases"][0]["awards"][1].pop(relation)
    source = tmp_path / "partial.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    consumer = runpy.run_path(str(EXAMPLES / "sercop_etl.py"))
    with pytest.raises(ValueError, match="partially absent relation arrays"):
        consumer["extract"](source, tmp_path)


def test_sercop_uses_captured_verified_bytes_if_original_changes(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    for name in ("record-0.json", "snapshot.json", "expected.json"):
        (snapshot / name).write_bytes((EXAMPLES / "sercop_offline" / name).read_bytes())
    original = snapshot / "record-0.json"
    verified = original.read_bytes()
    consumer = runpy.run_path(str(EXAMPLES / "sercop_etl.py"))
    run = consumer["run"]

    def changed_source(captured, output):
        original.write_bytes(b"corrupted after verification")
        assert captured != original and captured.read_bytes() == verified
        raise ValueError("captured verified payload inspected")

    monkeypatch.setitem(run.__globals__, "extract", changed_source)
    with pytest.raises(ValueError, match="captured verified payload inspected"):
        run(snapshot, snapshot / "expected.json", tmp_path / "output")


def test_sercop_mixed_package_grains_are_rejected(tmp_path):
    payload = json.loads((EXAMPLES / "sercop_offline/record-0.json").read_bytes())
    payload["records"] = []
    source = tmp_path / "mixed.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    consumer = runpy.run_path(str(EXAMPLES / "sercop_etl.py"))
    with pytest.raises(ValueError, match="records packages require"):
        consumer["extract"](source, tmp_path)
