"""Inspect a trusted wheel offline before installation; never execute its contents.

The expected SHA-256 must come from a separately authenticated receipt. RECORD
integrity alone is not publisher authentication, a license approval or a sandbox.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 4096
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or path.is_absolute()
        or ".." in path.parts
        or ":" in name
        or path.as_posix() != name
    ):
        raise ValueError("unsafe or noncanonical archive path: " + name)
    return path


def local_target(document: str, link: str) -> str | None:
    value = urlsplit(unquote(link.strip("<>")))
    if value.scheme or value.netloc or not value.path:
        return None
    if value.path.startswith("/") or "\\" in value.path:
        raise ValueError("nonportable documentation link: " + document + ": " + link)
    parts = list(PurePosixPath(document).parent.parts)
    for part in value.path.split("/"):
        if part == "..":
            if not parts:
                raise ValueError("documentation link escapes wheel: " + document + ": " + link)
            parts.pop()
        elif part not in {"", "."}:
            parts.append(part)
    return PurePosixPath(*parts).as_posix()


def check_links(payload: dict[str, bytes]) -> dict[str, Any]:
    checked = 0
    external = 0
    unresolved: list[dict[str, str]] = []
    for name, raw in payload.items():
        if not name.endswith(".md") or ".dist-info/" in name:
            continue
        # Code samples are not navigation targets. Check inline Markdown links;
        # anchors and remote destinations are recorded as unverified, not fetched.
        text = re.sub(r"```.*?```", "", raw.decode("utf-8"), flags=re.DOTALL)
        for match in LINK.finditer(text):
            link = match.group(1)
            target = local_target(name, link)
            if target is None:
                external += 1
                continue
            checked += 1
            if target not in payload:
                unresolved.append({"document": name, "link": link, "target": target})
    return {
        "local_targets_checked": checked,
        "remote_or_anchor_targets_not_verified": external,
        "unresolved": unresolved,
        "scope": "Inline Markdown file destinations only; no remote requests or anchor validation",
    }


def audit(path: Path, expected_sha256: str, name: str, version: str) -> dict[str, Any]:
    if not SHA256.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal digits")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("wheel exceeds offline audit size limit")
    # Open the same immutable byte image used for hashing; never extract it.
    raw = path.read_bytes()
    observed = hashlib.sha256(raw).hexdigest()
    if observed != expected_sha256:
        raise ValueError("wheel differs from independently supplied SHA-256")
    with ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if not members or len(members) > MAX_MEMBERS:
            raise ValueError("invalid wheel member count")
        if sum(info.file_size for info in members) > MAX_PAYLOAD_BYTES:
            raise ValueError("wheel exceeds uncompressed audit size limit")
        names = [info.filename for info in members]
        if len(names) != len(set(names)):
            raise ValueError("duplicate wheel members")
        for info in members:
            member_path(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if info.is_dir() or mode not in {0, 0o100000} or info.flag_bits & 1:
                raise ValueError("wheel contains directory, special or encrypted member")
        payload = {info.filename: archive.read(info) for info in members}
    roots = {key.split("/")[0] for key in payload if ".dist-info/" in key}
    if len(roots) != 1:
        raise ValueError("wheel must contain exactly one dist-info directory")
    root = roots.pop()
    expected_root = normalized(name).replace("-", "_") + "-" + version + ".dist-info"
    if root != expected_root:
        raise ValueError("dist-info identity differs from expected distribution")
    metadata = BytesParser(policy=policy.default).parsebytes(payload[root + "/METADATA"])
    if metadata.get_all("Name") != [name] or metadata.get_all("Version") != [version]:
        raise ValueError("METADATA identity differs from expected distribution")
    if not metadata.get("Requires-Python"):
        raise ValueError("Requires-Python is missing")
    if not any(key.endswith("/py.typed") for key in payload):
        raise ValueError("typed package marker is missing")
    record = root + "/RECORD"
    rows = list(csv.reader(io.StringIO(payload[record].decode("utf-8"), newline="")))
    listed: set[str] = set()
    for row in rows:
        if len(row) != 3:
            raise ValueError("malformed RECORD entry")
        key, digest, size = row
        member_path(key)
        if key in listed or key not in payload:
            raise ValueError("RECORD contains duplicate or nonexistent entry")
        listed.add(key)
        if key == record:
            if digest or size:
                raise ValueError("RECORD must not hash itself")
        else:
            expected = "sha256=" + base64.urlsafe_b64encode(
                hashlib.sha256(payload[key]).digest()
            ).decode("ascii").rstrip("=")
            if digest != expected or size != str(len(payload[key])):
                raise ValueError("RECORD hash or size differs from payload: " + key)
    if listed != set(payload):
        raise ValueError("RECORD does not inventory every wheel member")
    links = check_links(payload)
    return {
        "schema_version": "equiframe.offline-wheel-audit/1.0",
        "status": "PASS" if not links["unresolved"] else "FAIL",
        "artifact": {"name": path.name, "sha256": observed, "bytes": len(raw)},
        "distribution": {
            "name": metadata["Name"],
            "version": metadata["Version"],
            "requires_python": metadata["Requires-Python"],
            "classifiers": metadata.get_all("Classifier", []),
            "requires_dist": metadata.get_all("Requires-Dist", []),
            "extras": metadata.get_all("Provides-Extra", []),
            "project_urls": metadata.get_all("Project-URL", []),
            "author": metadata.get("Author"),
            "license_expression": metadata.get("License-Expression"),
        },
        "record_members_verified": len(payload),
        "member_sha256": {key: hashlib.sha256(value).hexdigest() for key, value in payload.items()},
        "documentation": links,
        "code_executed": False,
        "network_used": False,
        "scope": "Artifact integrity and local Markdown destinations; not publisher "
        "authentication, license approval, vulnerability scan or execution compatibility",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        # Reserve before parsing the wheel so failed attempts retain their own
        # receipt, and a repeated command cannot replace earlier observations.
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            try:
                result = audit(args.wheel, args.sha256, args.name, args.version)
            except (ValueError, KeyError, OSError, BadZipFile, UnicodeError, csv.Error) as error:
                result = {"status": "FAIL", "error": str(error), "code_executed": False}
            json.dump(result, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
        print(json.dumps({"status": result["status"], "receipt": str(args.output)}))
        return 0 if result["status"] == "PASS" else 1
    except OSError as error:
        print("offline wheel audit: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
