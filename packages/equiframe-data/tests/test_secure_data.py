"""Regressions for hostile inputs, independent writers and failed publication."""

import json
import multiprocessing
import os
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_manager import COMPLETED, FAILED, IN_PROGRESS, JobManager, WriterBusyError
from safe_io import MAX_MANIFEST_BYTES, confined, read_json
from snapshot_client import SnapshotClient


def publish(root, sid="v1", content=b"id,value\n1,100\n"):
    source = root / "input.csv"
    source.write_bytes(content)
    manager = JobManager(root / "state")
    job = manager.submit_job("load", sid, "key-" + sid)
    manager.run_job(job.job_id, {"table": source})
    return manager, job


@pytest.mark.parametrize(
    "value", ["../escape", "/tmp", "C:\\escape", "a/b", "a\\b", "..", "a\n", "x" * 129, 7, ""]
)
def test_snapshot_id_cannot_escape(tmp_path, value):
    with pytest.raises(ValueError):
        SnapshotClient(tmp_path).get_snapshot(value)
    with pytest.raises(ValueError):
        JobManager(tmp_path / "state").submit_job("load", value, "key")


@pytest.mark.parametrize(
    "value",
    [
        "../secret.csv",
        "/secret.csv",
        "C:/secret.csv",
        "a\\b.csv",
        "NUL.csv",
        "sub/../x",
        "x:stream",
        "x.csv.",
    ],
)
def test_confined_path_rejects_nonportable_or_escaping_names(tmp_path, value):
    with pytest.raises(ValueError):
        confined(tmp_path, value)


def test_manifest_is_immutable_and_pinned(tmp_path):
    manager, _ = publish(tmp_path)
    client = SnapshotClient(manager.snaps_dir)
    manifest = client.get_snapshot("v1")
    with pytest.raises(FrozenInstanceError):
        manifest.version = "changed"
    with pytest.raises(FrozenInstanceError):
        manifest.artifacts[0].sha256 = "0" * 64
    (manager.snaps_dir / "v1/manifest.json").write_text("{}")
    assert client.get_snapshot("v1") is manifest
    with pytest.raises(ValueError):
        SnapshotClient(manager.snaps_dir).get_snapshot("v1")


@pytest.mark.parametrize(
    "change",
    [
        {"snapshot_id": "another"},
        {"artifacts": []},
        {"timestamp": "2026-10-13"},
        {"source": "bad\nsource"},
        {"unexpected": True},
    ],
)
def test_invalid_manifest_rejected(tmp_path, change):
    manager, _ = publish(tmp_path)
    path = manager.snaps_dir / "v1/manifest.json"
    document = json.loads(path.read_text())
    document.update(change)
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        SnapshotClient(manager.snaps_dir).get_snapshot("v1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("size_bytes", True),
        ("size_bytes", -1),
        ("size_bytes", 2**64),
        ("sha256", "oops"),
        ("row_count", -1),
        ("version", "foreign"),
        ("file_path", "../secret.csv"),
    ],
)
def test_invalid_manifest_artifact_rejected(tmp_path, field, value):
    manager, _ = publish(tmp_path)
    path = manager.snaps_dir / "v1/manifest.json"
    document = json.loads(path.read_text())
    document["artifacts"][0][field] = value
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        SnapshotClient(manager.snaps_dir).get_snapshot("v1")


def test_duplicate_keys_and_oversized_json_rejected(tmp_path):
    path = tmp_path / "document.json"
    for value in ['{"x":1,"x":2}', '{"x":NaN}', " " * (MAX_MANIFEST_BYTES + 1)]:
        path.write_text(value)
        with pytest.raises(ValueError):
            read_json(path)


def test_existing_download_survives_corruption(tmp_path):
    manager, _ = publish(tmp_path)
    client = SnapshotClient(manager.snaps_dir)
    ref = client.get_snapshot("v1").artifacts[0]
    dest = tmp_path / "downloads"
    first = client.download_artifact(ref, dest)
    expected = first.read_bytes()
    (manager.snaps_dir / "v1" / ref.file_path).write_bytes(b"corrupt")
    assert client.download_artifact(ref, dest).read_bytes() == expected
    with pytest.raises(ValueError):
        client.download_artifact(ref, tmp_path / "other")
    assert list((tmp_path / "other").iterdir()) == []


def test_forged_ref_rejected(tmp_path):
    manager, _ = publish(tmp_path)
    client = SnapshotClient(manager.snaps_dir)
    ref = client.get_snapshot("v1").artifacts[0]
    with pytest.raises(ValueError):
        client.download_artifact(replace(ref, table_name="other"), tmp_path / "out")


def test_same_snapshot_is_never_replaced(tmp_path):
    manager, original = publish(tmp_path)
    manifest = manager.snaps_dir / "v1/manifest.json"
    before = manifest.read_bytes()
    next_job = manager.submit_job("load", "v1", "different-key")
    with pytest.raises(ValueError):
        manager.run_job(next_job.job_id, {"table": tmp_path / "input.csv"})
    assert manifest.read_bytes() == before
    assert manager.get_job(original.job_id).state == COMPLETED
    assert manager.get_job(next_job.job_id).state == FAILED


def _hold_lock(root, ready, release):
    manager = JobManager(root)
    assert manager._acquire_lock()
    ready.set()
    release.wait(15)
    manager._release_lock()


def test_os_lock_excludes_an_independent_process(tmp_path):
    root = tmp_path / "state"
    manager = JobManager(root)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_lock, args=(root, ready, release))
    process.start()
    try:
        assert ready.wait(10)
        assert manager._acquire_lock() is False
        with pytest.raises(WriterBusyError):
            manager.run_job("unused", {})
    finally:
        release.set()
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join()
    assert process.exitcode == 0
    assert manager._acquire_lock()
    manager._release_lock()


def test_recover_interrupted_job(tmp_path):
    manager = JobManager(tmp_path / "state")
    job = manager.submit_job("load", "v1", "key")
    job.state = IN_PROGRESS
    manager._save_job(job)
    staging = manager._staging(job)
    staging.mkdir()
    (staging / "incomplete.csv").write_text("partial")
    reopened = JobManager(manager.base_dir)
    assert reopened.get_job(job.job_id).state == FAILED
    assert reopened.get_job(job.job_id).error == "LOAD_INTERRUPTED"
    assert not staging.exists()


def test_recover_committed_snapshot_after_receipt_failure(tmp_path):
    manager, job = publish(tmp_path)
    job.state = IN_PROGRESS
    manager._save_job(job)
    recovered = JobManager(manager.base_dir).get_job(job.job_id)
    assert recovered.state == COMPLETED
    assert recovered.result_snapshot_id == "v1"


def test_input_root_and_bytes_limit(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "table.csv").write_text("too large")
    manager = JobManager(tmp_path / "state", input_dir=source, max_bytes=2)
    for name in ("../secret.csv", str(source / "table.csv"), "table.csv"):
        job = manager.submit_job("load", "v" + str(len(manager.list_jobs())), name)
        with pytest.raises(ValueError):
            manager.run_job(job.job_id, {"table": name})
        assert manager.get_job(job.job_id).state == FAILED


def test_failed_job_and_logs_hide_input_paths(tmp_path, caplog):
    manager = JobManager(tmp_path / "state")
    job = manager.submit_job("load", "v1", "do-not-leak-this-key")
    missing = tmp_path / "confidential-person.csv"
    with pytest.raises(FileNotFoundError):
        manager.run_job(job.job_id, {"table": missing})
    receipt = manager.get_job(job.job_id).to_dict()
    assert receipt["error"] == "LOAD_FAILED"
    assert "confidential-person" not in str(receipt) + caplog.text
    assert "do-not-leak-this-key" not in str(receipt) + caplog.text


def test_legacy_error_is_redacted_when_a_receipt_is_loaded(tmp_path):
    manager, job = publish(tmp_path)
    job.state = FAILED
    job.error = "Password=private-value; /private/customer.csv"
    manager._save_job(job)
    receipt = JobManager(manager.base_dir).get_job(job.job_id).to_dict()
    assert receipt["error"] == "LOAD_FAILED"
    assert "private-value" not in str(receipt)
    assert "customer.csv" not in str(receipt)


@pytest.mark.skipif(
    os.name == "nt",
    reason="Symlinks require a Windows privilege; POSIX must execute this regression",
)
def test_symlink_escape_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        confined(root, "link/secret.csv")
