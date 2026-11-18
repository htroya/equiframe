"""Reject falsely identified or corrupted artifacts before executing package code."""

import base64
import csv
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_wheel.py"
SPEC = importlib.util.spec_from_file_location("offline_wheel_audit", TOOL)
assert SPEC is not None and SPEC.loader is not None
audit_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_tool)
DIST = "demo-1.0.dist-info"


def wheel(tmp_path, *, payload=None, records=None, extra=None):
    files = {
        "demo/__init__.py": b"raise RuntimeError('Must never execute archive code')\n",
        "demo/py.typed": b"",
        "demo/docs/index.md": b"[Guide](guide.md) [Remote](https://example.test/)\n",
        "demo/docs/guide.md": b"[Index](index.md#introduction)\n",
        DIST + "/METADATA": (
            "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\nRequires-Python: >=3.10\n"
            "Author: Hernán\n\nPrivate test\n"
        ).encode(),
        DIST + "/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    files.update(payload or {})
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    rows = []
    for name, raw in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        rows.append([name, "sha256=" + digest, str(len(raw))])
    rows.append([DIST + "/RECORD", "", ""])
    if records:
        records(rows)
    writer.writerows(rows)
    files[DIST + "/RECORD"] = output.getvalue().encode()
    path = tmp_path / "demo-1.0-py3-none-any.whl"
    with ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
        if extra:
            for name, raw in extra:
                archive.writestr(name, raw)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_reads_unicode_and_checks_all_records_without_executing(tmp_path):
    path, digest = wheel(tmp_path)
    result = audit_tool.audit(path, digest, "demo", "1.0")
    assert result["status"] == "PASS"
    assert result["distribution"]["author"] == "Hernán"
    assert result["record_members_verified"] == 7
    assert result["documentation"]["local_targets_checked"] == 2
    assert not result["code_executed"] and not result["network_used"]
    json.dumps(result)


def test_expected_sha_is_checked_before_zip_parser(tmp_path, monkeypatch):
    path, _ = wheel(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("archive was opened before hash validation")

    monkeypatch.setattr(audit_tool, "ZipFile", forbidden)
    with pytest.raises(ValueError, match="independently supplied"):
        audit_tool.audit(path, "0" * 64, "demo", "1.0")


@pytest.mark.parametrize("name", ["../escape", "/absolute", "demo\\bad", "demo//bad", "C:/bad"])
def test_rejects_paths_even_with_valid_record_hashes(tmp_path, name):
    path, digest = wheel(tmp_path, payload={name: b"value"})
    with pytest.raises(ValueError, match="archive path"):
        audit_tool.audit(path, digest, "demo", "1.0")


def test_rejects_duplicate_zip_member(tmp_path):
    with pytest.warns(UserWarning, match="Duplicate"):
        path, digest = wheel(tmp_path, extra=[("demo/py.typed", b"wrong")])
    with pytest.raises(ValueError, match="duplicate wheel"):
        audit_tool.audit(path, digest, "demo", "1.0")


def test_rejects_uninventoried_payload(tmp_path):
    path, digest = wheel(tmp_path, extra=[("demo/extra.py", b"malicious")])
    with pytest.raises(ValueError, match="inventory every"):
        audit_tool.audit(path, digest, "demo", "1.0")


@pytest.mark.parametrize("column,value", [(1, "sha256=wrong"), (2, "999"), (1, "")])
def test_rejects_record_hash_and_size_mismatches(tmp_path, column, value):
    path, digest = wheel(tmp_path, records=lambda rows: rows[0].__setitem__(column, value))
    with pytest.raises(ValueError, match="hash or size"):
        audit_tool.audit(path, digest, "demo", "1.0")


def test_rejects_duplicate_record_entry(tmp_path):
    path, digest = wheel(tmp_path, records=lambda rows: rows.append(rows[0]))
    with pytest.raises(ValueError, match="duplicate or nonexistent"):
        audit_tool.audit(path, digest, "demo", "1.0")


@pytest.mark.parametrize("name,version", [("unrelated", "1.0"), ("demo", "2.0")])
def test_rejects_expected_distribution_mismatch(tmp_path, name, version):
    path, digest = wheel(tmp_path)
    with pytest.raises(ValueError, match="identity"):
        audit_tool.audit(path, digest, name, version)


def test_rejects_metadata_identity_mismatch(tmp_path):
    path, digest = wheel(tmp_path, payload={DIST + "/METADATA": b"Name: other\nVersion: 1.0\n"})
    with pytest.raises(ValueError, match="identity"):
        audit_tool.audit(path, digest, "demo", "1.0")


def test_broken_local_link_fails_without_network(tmp_path):
    path, digest = wheel(tmp_path, payload={"demo/docs/index.md": b"[Missing](absent.md)"})
    result = audit_tool.audit(path, digest, "demo", "1.0")
    assert result["status"] == "FAIL"
    assert result["documentation"]["unresolved"][0]["target"] == "demo/docs/absent.md"


def test_link_escapes_wheel(tmp_path):
    path, digest = wheel(tmp_path, payload={"demo/docs/index.md": b"[Escapes](../../../private)"})
    with pytest.raises(ValueError, match="escapes wheel"):
        audit_tool.audit(path, digest, "demo", "1.0")


def test_cli_keeps_failure_and_refuses_replacing_receipt_under_optimized_python(tmp_path):
    path, _ = wheel(tmp_path)
    output = tmp_path / "failure.json"
    command = [
        sys.executable,
        "-O",
        str(TOOL),
        str(path),
        "--sha256",
        "0" * 64,
        "--name",
        "demo",
        "--version",
        "1.0",
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    raw = output.read_bytes()
    assert json.loads(raw)["status"] == "FAIL"
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert output.read_bytes() == raw


def test_invalid_hash_and_archive_size_limits(tmp_path, monkeypatch):
    path, digest = wheel(tmp_path)
    with pytest.raises(ValueError, match="64 lowercase"):
        audit_tool.audit(path, "not-a-hash", "demo", "1.0")
    monkeypatch.setattr(audit_tool, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="size limit"):
        audit_tool.audit(path, digest, "demo", "1.0")


def test_uncompressed_size_limit(tmp_path, monkeypatch):
    path, digest = wheel(tmp_path)
    monkeypatch.setattr(audit_tool, "MAX_PAYLOAD_BYTES", 1)
    with pytest.raises(ValueError, match="uncompressed"):
        audit_tool.audit(path, digest, "demo", "1.0")
