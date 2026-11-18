"""Audit a private four-artifact release pair offline; never upload or authorize."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import re
import stat
import sys
import tarfile
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_PAYLOAD = 64 * 1024 * 1024
MAX_MEMBERS = 2000
BINARY_SUFFIXES = {
    ".arrow",
    ".parquet",
    ".db",
    ".sqlite",
    ".duckdb",
    ".pkl",
    ".pickle",
    ".joblib",
    ".onnx",
}


def pairs(values: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in values:
        if name in result:
            raise ValueError("Duplicate JSON field: " + name)
        result[name] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON token: " + value)


def read_json(raw: bytes) -> dict:
    if len(raw) > 128 * 1024:
        raise ValueError("Preparation manifest exceeds limit")
    document = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    if not isinstance(document, dict):
        raise TypeError("Manifest must be an object")
    return document


def regular(path: Path) -> None:
    for parent in (*reversed(path.parents), path):
        mode = parent.lstat().st_mode
        if stat.S_ISLNK(mode) or bool(
            getattr(parent.lstat(), "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("Links/junctions are not preparation inputs")
    if not path.is_file():
        raise ValueError("Regular file required")


def verified_bytes(path: Path, sha256: str, size: int | None = None) -> bytes:
    regular(path)
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Trusted lowercase SHA-256 required")
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError("Artifact exceeds size limit")
    raw = path.read_bytes()
    if len(raw) > MAX_ARCHIVE or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("Artifact/manifest differs from trusted digest")
    if size is not None and (type(size) is not int or len(raw) != size):
        raise ValueError("Artifact size differs")
    return raw


def safe_member(name: str) -> PurePosixPath:
    if not name or "\\" in name or ":" in name or name.startswith("/"):
        raise ValueError("Unsafe archive path")
    path = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in name.rstrip("/").split("/")):
        raise ValueError("Unsafe archive path")
    return path


def sdist_payload(raw: bytes, stem: str) -> dict[str, bytes]:
    payload, names, size = {}, set(), 0
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
        decoded = compressed.read(MAX_PAYLOAD + 1)
    if len(decoded) > MAX_PAYLOAD:
        raise ValueError("Uncompressed tar container exceeds limit")
    with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as archive:
        for member in archive:
            path = safe_member(member.name)
            if path.parts[0] != stem or member.name in names:
                raise ValueError("Wrong sdist root or duplicate member")
            names.add(member.name)
            if len(names) > MAX_MEMBERS or not (member.isfile() or member.isdir()):
                raise ValueError("Unsupported/linked sdist member or inventory limit")
            if member.size < 0:
                raise ValueError("Invalid sdist member size")
            size += member.size
            if size > MAX_PAYLOAD:
                raise ValueError("Uncompressed sdist exceeds limit")
            if member.isfile():
                if len(path.parts) < 2:
                    raise ValueError("File cannot occupy sdist root")
                value = archive.extractfile(member).read()
                if len(value) != member.size:
                    raise ValueError("Truncated sdist member")
                payload[PurePosixPath(*path.parts[1:]).as_posix()] = value
    for name in payload:
        for parent in PurePosixPath(name).parents:
            if parent.as_posix() in payload:
                raise ValueError("File/directory collision in sdist")
    if not payload:
        raise ValueError("Empty sdist")
    return payload


def audit_contents(payload: dict[str, bytes], fixtures: dict[str, str]) -> list[dict]:
    reviewed = []
    observed_binary = set()
    for name, raw in payload.items():
        parts = PurePosixPath(name).parts
        if any(
            part in {".git", ".venv", "__pycache__", "credentials", ".ssh"}
            for part in parts
        ):
            raise ValueError("Private/environment path in distribution")
        if any(
            part == ".env" or part.startswith(".env.") for part in parts
        ) or PurePosixPath(name).suffix.lower() in {".key", ".pem", ".pfx", ".p12"}:
            raise ValueError("Credential-like path in distribution")
        if PurePosixPath(name).suffix.lower() in BINARY_SUFFIXES:
            observed_binary.add(name)
            if (
                not name.startswith("tests/fixtures/versioned/")
                or fixtures.get(name) != hashlib.sha256(raw).hexdigest()
            ):
                raise ValueError("Unreviewed binary fixture/data/model in distribution")
            reviewed.append({"file": name, "sha256": fixtures[name], "bytes": len(raw)})
    if observed_binary != set(fixtures):
        raise ValueError(
            "Approved fixture inventory differs from actual binary inventory"
        )
    return reviewed


def closed_policy(document: dict) -> None:
    if (
        document.get("schema_version") != "1.0"
        or document.get("publication_enabled") is not False
    ):
        raise ValueError("Preparation cannot enable public publication")
    pending = document.get("pending_decisions")
    if (
        not isinstance(pending, list)
        or not pending
        or any(not isinstance(x, str) or not x for x in pending)
    ):
        raise ValueError("Publication decisions must remain explicit")


def reconcile(expected: dict[str, str], observed: dict[str, str]) -> dict:
    """Diagnose supplied index observations; no upload, retry, deletion or approval."""
    if not expected:
        raise ValueError("Expected artifact inventory cannot be empty")
    conflicts = sorted(
        name for name, digest in observed.items() if expected.get(name) != digest
    )
    missing = sorted(set(expected) - set(observed))
    state = (
        "CONFLICT"
        if conflicts
        else "PARTIAL"
        if observed and missing
        else "ABSENT"
        if missing
        else "COMPLETE_OBSERVATION"
    )
    return {
        "state": state,
        "missing": missing,
        "conflicts": conflicts,
        "publication_authorized": False,
        "observation_authenticated": False,
    }


def prepare(manifest: dict, artifact_root: Path, release_policy: dict) -> dict:
    closed_policy(release_policy)
    if (
        set(manifest)
        != {
            "schema",
            "version",
            "artifact_code_cut",
            "test_code_cut",
            "artifacts",
            "binary_fixtures",
        }
        or manifest["schema"] != "pypi-preparation-v1"
    ):
        raise ValueError(
            "Unsupported preparation manifest; no approval fields accepted"
        )
    version = manifest["version"]
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:a[0-9]+|b[0-9]+|rc[0-9]+)?", version
    ):
        raise ValueError("Unsupported bounded version")
    for field in ("artifact_code_cut", "test_code_cut"):
        if not isinstance(manifest[field], str) or not re.fullmatch(
            r"[0-9a-f]{40}", manifest[field]
        ):
            raise ValueError("Exact source cuts are required")
    expected = {
        name.replace("-", "_") + "-" + version + suffix
        for name in ("equiframe", "equiframe-benchmark")
        for suffix in ("-py3-none-any.whl", ".tar.gz")
    }
    records = manifest["artifacts"]
    if (
        not isinstance(records, list)
        or len(records) != 4
        or any(
            not isinstance(x, dict)
            or set(x) != {"file", "bytes", "sha256"}
            or type(x["bytes"]) is not int
            or not 0 < x["bytes"] <= MAX_ARCHIVE
            for x in records
        )
    ):
        raise ValueError("Exactly four closed artifact records required")
    if {x["file"] for x in records} != expected:
        raise ValueError("Wrong/repeated/missing artifact names")
    raw_files = {
        item["file"]: verified_bytes(
            artifact_root / item["file"], item["sha256"], item["bytes"]
        )
        for item in records
    }
    fixtures = manifest["binary_fixtures"]
    if not isinstance(fixtures, dict) or set(fixtures) != {
        "equiframe",
        "equiframe-benchmark",
    }:
        raise ValueError("Explicit fixture inventories required for both sdists")
    for inventory in fixtures.values():
        if not isinstance(inventory, dict) or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not re.fullmatch(r"[0-9a-f]{64}", value)
            for key, value in inventory.items()
        ):
            raise ValueError("Fixture inventory requires explicit paths and SHA-256")
    auditor_path = ROOT / "packages/equiframe/tools/audit_wheel.py"
    spec = importlib.util.spec_from_file_location(
        "pypi_preparation_wheel_auditor", auditor_path
    )
    auditor = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = auditor
    spec.loader.exec_module(auditor)
    distributions = []
    for name in ("equiframe", "equiframe-benchmark"):
        stem = name.replace("-", "_") + "-" + version
        wheel_name, sdist_name = stem + "-py3-none-any.whl", stem + ".tar.gz"
        record = next(x for x in records if x["file"] == wheel_name)
        wheel_audit = auditor.audit(
            artifact_root / wheel_name, record["sha256"], name, version
        )
        if wheel_audit["status"] != "PASS":
            raise ValueError("Wheel integrity/navigation audit failed")
        with ZipFile(io.BytesIO(raw_files[wheel_name])) as archive:
            wheel = {key: archive.read(key) for key in archive.namelist()}
        metadata = wheel[stem + ".dist-info/METADATA"]
        source = sdist_payload(raw_files[sdist_name], stem)
        if (
            source.get("PKG-INFO") != metadata
            or "pyproject.toml" not in source
            or "README.md" not in source
        ):
            raise ValueError("Wheel/sdist metadata differ or source metadata missing")
        fixture_audit = audit_contents(source, fixtures[name])
        audit_contents(wheel, {})
        message = BytesParser(policy=policy.default).parsebytes(metadata)
        dependencies = message.get_all("Requires-Dist", [])
        if any(
            " @ " in value or "file:" in value.lower() or "git+" in value.lower()
            for value in dependencies
        ):
            raise ValueError("Non-index dependency in candidate metadata")
        if name == "equiframe-benchmark" and not any(
            re.fullmatch(r"equiframe\[arrow\]==" + re.escape(version), value)
            for value in dependencies
        ):
            raise ValueError("Benchmark does not pin the matching core")
        distributions.append(
            {
                "name": name,
                "version": version,
                "wheel": wheel_name,
                "sdist": sdist_name,
                "wheel_record_members": wheel_audit["record_members_verified"],
                "sdist_files": len(source),
                "sdist_inventory": [
                    {
                        "file": key,
                        "bytes": len(value),
                        "sha256": hashlib.sha256(value).hexdigest(),
                    }
                    for key, value in sorted(source.items())
                ],
                "binary_fixtures": fixture_audit,
                "requires_python": message.get("Requires-Python"),
                "dependencies": dependencies,
                "extras": message.get_all("Provides-Extra", []),
                "license_expression": message.get("License-Expression"),
                "license_files": message.get_all("License-File", []),
                "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
            }
        )
    return {
        "schema": "pypi-preparation-packet-v1",
        "artifacts_verified": True,
        "publication_ready": False,
        "published": False,
        "upload_available": False,
        "artifact_code_cut": manifest["artifact_code_cut"],
        "test_code_cut": manifest["test_code_cut"],
        "artifacts": records,
        "distributions": distributions,
        "pending_decisions": release_policy["pending_decisions"],
        "limitations": [
            "Local byte/inventory checks are not rights, name/account ownership or human approval",
            "No network, extraction, candidate-code execution, signing, token access or upload",
            "Filename inventory cannot prove absence of every embedded secret or private content",
            "Historical execution receipts must be separately reviewed; no new full-suite or TestPyPI result",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--sha256", required=True, help="Trusted preparation-manifest digest"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Receipt path already exists")
        manifest = read_json(verified_bytes(args.manifest.absolute(), args.sha256))
        release_policy = read_json(
            (ROOT / "packages/equiframe/tools/release-policy.json").read_bytes()
        )
        packet = prepare(manifest, args.artifact_root.absolute(), release_policy)
        packet["manifest_sha256"] = args.sha256
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(packet, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        EOFError,
        BadZipFile,
        tarfile.TarError,
    ) as error:
        parser.exit(2, f"Preparation rejected: {error}\n")
    print("PASS: exact four-artifact pair audited; public publication remains blocked")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
