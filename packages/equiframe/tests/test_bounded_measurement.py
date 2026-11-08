"""Small independently expected monetary workload and ordinary interrupted-write handling."""

import errno
import json
import runpy
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.errors import ExecutionCancelled


@pytest.fixture
def measurement():
    return runpy.run_path(str(Path(__file__).parents[1] / "tools/measure_bounded.py"))


def test_decimal_fixture_preserves_exact_cents_and_independent_last_difference(measurement):
    candidate, expected = measurement["decimal_tables"](8)
    assert expected["amount"].to_pylist() == [Decimal(f"0.0{n}") for n in range(8)]
    assert candidate["amount"].to_pylist() == [Decimal(f"0.0{n}") for n in range(7)] + [
        Decimal("0.08")
    ]
    assert candidate.schema == expected.schema
    assert candidate.schema.field("amount").type == pa.decimal128(18, 2)
    assert candidate["currency"].to_pylist() == expected["currency"].to_pylist() == ["USD"] * 8


def test_decimal_trial_measures_full_evidence_with_explicit_stage_boundaries(measurement, tmp_path):
    trial = measurement["decimal_trial"](tmp_path / "trial", 8, 0)
    assert trial["complete"] is True
    assert trial["state"] == "different"
    assert trial["difference_records"] == 1
    assert trial["rows_per_side"] == 8
    assert [stage["name"] for stage in trial["stages"]] == [
        "generate",
        "convert",
        "capture",
        "hash",
        "compare",
        "serialize",
        "persist",
        "report",
        "verify",
    ]
    assert sum(stage["wall_seconds"] for stage in trial["stages"]) <= trial["end_to_end_seconds"]
    assert trial["retained_apparent_bytes"] > 0
    assert set(trial["capture_sha256"]) == {"candidate.arrow", "expected.arrow"}
    assert "includes its own capture again" in trial["stages"][1]["scope"]
    persisted = ef.read_comparison(tmp_path / "trial/serialized-comparison.json")
    assert persisted.complete and persisted.state == "different"
    with pytest.raises(ef.EquivalenceDifferentError):
        ef.assert_equivalent(persisted)


def test_pre_cancelled_decimal_comparison_is_not_accepted(measurement, tmp_path):
    candidate, expected = measurement["decimal_tables"](8)
    token = ef.CancellationToken()
    token.cancel()
    with pytest.raises(ExecutionCancelled, match="cancelled before reference capture"):
        ef.diff(candidate, expected, keys=["id"], cancellation=token, work_dir=tmp_path)
    assert not list(tmp_path.rglob("comparison.json"))


@pytest.mark.parametrize(
    "error", [KeyboardInterrupt(), OSError(errno.ENOSPC, "synthetic disk full")]
)
def test_interrupted_trial_preserves_earlier_receipt_without_completion(
    measurement, tmp_path, monkeypatch, error
):
    worker = measurement["decimal_worker"]
    calls = []

    def trial(directory, rows, repetition):
        calls.append(repetition)
        if repetition == 1:
            raise error
        directory.mkdir()
        return {"complete": True, "repetition": repetition}

    monkeypatch.setitem(worker.__globals__, "decimal_trial", trial)
    with pytest.raises(type(error)):
        worker(tmp_path, 8, 3)
    assert calls == [0, 1]
    assert json.loads((tmp_path / "trial-000.json").read_text()) == {
        "complete": True,
        "repetition": 0,
    }
    assert not (tmp_path / "completed.json").exists()


def test_exclusive_write_retains_old_bytes(measurement, tmp_path):
    target = tmp_path / "retained.json"
    target.write_bytes(b"old")
    with pytest.raises(FileExistsError):
        measurement["publish_bytes"](target, b"new")
    assert target.read_bytes() == b"old"


@pytest.mark.parametrize("rows,repetitions", [(7, 3), (2049, 3), (8, 1), (8, 6)])
def test_suite_admission_rejects_expansion_before_creating_output(
    measurement, tmp_path, rows, repetitions
):
    output = tmp_path / "suite"
    with pytest.raises(ValueError, match=r"8\.\.2048 rows"):
        measurement["measure_suite"](output, rows, repetitions)
    assert not output.exists()


def test_full_trial_injected_no_space_does_not_publish_worker_completion(
    measurement, tmp_path, monkeypatch
):
    worker = measurement["decimal_worker"]
    original = measurement["publish_bytes"]

    def publish(path, payload):
        if path.name == "serialized-comparison.json":
            raise OSError(errno.ENOSPC, "synthetic ordinary publication failure")
        return original(path, payload)

    monkeypatch.setitem(worker.__globals__, "publish_bytes", publish)
    with pytest.raises(OSError) as caught:
        worker(tmp_path, 8, 2)
    assert caught.value.errno == errno.ENOSPC
    # A valid child comparison cannot stand in for the missing measurement receipt.
    comparison = next(tmp_path.rglob("comparison.json"))
    assert ef.read_comparison(comparison).complete
    assert not (tmp_path / "completed.json").exists()
    assert not (tmp_path / "trial-000.json").exists()
