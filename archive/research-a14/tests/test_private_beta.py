"""Artifact/version counterexamples for the offline private Beta installer."""

import base64
import csv
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "private_beta", Path(__file__).parents[1] / "tools/private_beta.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def fixture_wheel(path, name, version="0.12.0b1", code_version=None, core_pin=None):
    package = name.replace("-", "_")
    info = package + "-" + version + ".dist-info/"
    metadata = f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\nClassifier: Development Status :: 4 - Beta\n"
    if name == "equiframe-benchmark":
        pin = core_pin or version
        metadata += (
            "\n".join(
                f"Requires-Dist: equiframe[{extra}]=={pin}"
                for extra in ("arrow", "engines", "ml")
            )
            + "\n"
        )
    files = {
        package
        + "/__init__.py": f'__version__ = "{code_version or version}"\n'.encode(),
        info + "METADATA": metadata.encode(),
        info + "WHEEL": b"Wheel-Version: 1.0\n",
    }
    stream = io.StringIO()
    writer = csv.writer(stream)
    for member, data in files.items():
        sha = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            .rstrip(b"=")
            .decode()
        )
        writer.writerow([member, "sha256=" + sha, str(len(data))])
    writer.writerow([info + "RECORD", "", ""])
    files[info + "RECORD"] = stream.getvalue().encode()
    with zipfile.ZipFile(path, "x") as archive:
        for member, data in files.items():
            archive.writestr(member, data)


def candidate(directory, code_version=None, core_pin=None):
    records = []
    for name in ("equiframe", "equiframe-benchmark"):
        p = directory / (name + ".whl")
        fixture_wheel(
            p,
            name,
            code_version=code_version if name == "equiframe" else None,
            core_pin=core_pin,
        )
        records.append(
            {"file": p.name, "size_bytes": p.stat().st_size, "sha256": tool.digest(p)}
        )
    p = directory / "candidate.json"
    p.write_text(
        json.dumps(
            {
                "version": "0.12.0b1",
                "channel": "private",
                "public_publication_enabled": False,
                "wheels": records,
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    return p


def test_valid_pair_requires_independent_record_and_code_identity(tmp_path):
    _, result = tool.audit(candidate(tmp_path))
    assert result["status"] == "PASS"
    assert result["human_acceptance_or_scientific_approval"] is False


def test_matching_metadata_does_not_hide_old_code(tmp_path):
    with pytest.raises(ValueError, match="Code and distribution"):
        tool.audit(candidate(tmp_path, code_version="0.12.0a13"))


def test_benchmark_cannot_pin_alpha_under_beta_metadata(tmp_path):
    with pytest.raises(ValueError, match="pin all three"):
        tool.audit(candidate(tmp_path, core_pin="0.12.0a13"))


def test_payload_corruption_with_preserved_record_is_rejected(tmp_path):
    original = tmp_path / "good.whl"
    fixture_wheel(original, "equiframe")
    corrupted = tmp_path / "bad.whl"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(corrupted, "x") as target:
        for name in source.namelist():
            data = source.read(name)
            target.writestr(
                name, data + b"changed" if name.endswith("__init__.py") else data
            )
    with pytest.raises(ValueError, match="payload differs"):
        tool.wheel(corrupted)


def test_private_installation_does_not_accept_public_authorization(tmp_path):
    p = candidate(tmp_path)
    data = json.loads(p.read_text())
    data["public_publication_enabled"] = True
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="private channel"):
        tool.audit(p)
