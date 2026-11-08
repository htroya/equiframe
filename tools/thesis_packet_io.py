"""Bounded, local-only I/O for private experimental packets; no executable input."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import url2pathname

MAX_FILE = 64 * 1024**2
MAX_JSON = 16 * 1024**2
MAX_FILES = 30000
MAX_TOTAL = 2 * 1024**3
_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def _ordinary(info):
    require(
        not stat.S_ISLNK(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400,
        "linked_path",
    )


def root_path(path):
    _ordinary(path.lstat())
    require(path.is_dir(), "packet_root_not_directory")
    return path.resolve(strict=True)


def local_path(root, relative):
    require(isinstance(relative, str), "invalid_relative_path")
    parsed = PurePosixPath(relative)
    require(
        not parsed.is_absolute()
        and parsed.as_posix() == relative
        and 0 < len(parsed.parts) <= 64,
        "invalid_relative_path",
    )
    current = root
    for index, part in enumerate(parsed.parts):
        require(
            _PART.fullmatch(part) is not None
            and not part.endswith((".", " "))
            and part.split(".", 1)[0].upper() not in _RESERVED,
            "invalid_path_component",
        )
        current = current / part
        info = current.lstat()
        _ordinary(info)
        require(
            stat.S_ISDIR(info.st_mode)
            if index < len(parsed.parts) - 1
            else stat.S_ISREG(info.st_mode),
            "unexpected_file_type",
        )
    require(current.resolve(strict=True).is_relative_to(root), "path_escaped_packet")
    return current


def read_bytes(root, relative, limit=MAX_FILE):
    require(type(limit) is int and 0 < limit <= MAX_FILE, "invalid_read_budget")
    path = local_path(root, relative)
    before = path.lstat()
    require(before.st_size <= limit, "file_budget_exceeded")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(opened.st_mode)
            and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
            "file_changed_before_read",
        )
        payload = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(
        len(payload) <= limit
        and (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "file_changed_during_read",
    )
    final = path.lstat()
    _ordinary(final)
    require(
        (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "file_replaced_during_read",
    )
    return payload


def read_json(root, relative):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    def constant(_value):
        raise ValueError("nonfinite_json")

    try:
        value = json.loads(
            read_bytes(root, relative, MAX_JSON).decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=constant,
        )
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("invalid_json") from error
    pending, nodes = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(depth <= 64 and nodes <= 500000, "json_structure_budget_exceeded")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, float):
            import math

            require(math.isfinite(item), "nonfinite_json")
    return value


def file_entry(root, relative):
    payload = read_bytes(root, relative)
    return {
        "path": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def inventory(root):
    entries, total, visited = [], 0, 0
    for path in root.rglob("*"):
        visited += 1
        require(visited <= MAX_FILES * 2, "directory_count_budget_exceeded")
        _ordinary(path.lstat())
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "integrity-manifest.json":
            continue
        require(len(entries) < MAX_FILES, "file_count_budget_exceeded")
        entry = file_entry(root, relative)
        total += entry["size_bytes"]
        require(total <= MAX_TOTAL, "packet_byte_budget_exceeded")
        entries.append(entry)
    return sorted(entries, key=lambda entry: entry["path"])


def verify_inventory(root):
    document = read_json(root, "integrity-manifest.json")
    require(
        isinstance(document, dict)
        and document.get("schema") == "equiframe.private-packet-integrity.v1",
        "invalid_integrity_manifest",
    )
    declared = document.get("files")
    require(
        isinstance(declared, list) and 0 < len(declared) <= MAX_FILES,
        "invalid_file_inventory",
    )
    seen = set()
    for entry in declared:
        require(
            isinstance(entry, dict) and set(entry) == {"path", "sha256", "size_bytes"},
            "invalid_inventory_entry",
        )
        require(
            isinstance(entry["sha256"], str)
            and _SHA.fullmatch(entry["sha256"]) is not None
            and type(entry["size_bytes"]) is int
            and 0 <= entry["size_bytes"] <= MAX_FILE,
            "invalid_file_identity",
        )
        path = local_path(root, entry["path"])
        require(entry["path"] not in seen, "duplicate_inventory_path")
        seen.add(entry["path"])
        require(path.stat().st_size == entry["size_bytes"], "file_size_mismatch")
    observed = inventory(root)
    require(observed == declared, "packet_inventory_mismatch")
    return document


def verify_reference(root, reference):
    require(
        reference.sha256 is not None
        and _SHA.fullmatch(reference.sha256) is not None
        and type(reference.size_bytes) is int
        and 0 <= reference.size_bytes <= MAX_FILE,
        "missing_artifact_identity",
    )
    parsed = urlsplit(reference.uri)
    require(
        parsed.scheme == "file"
        and not parsed.netloc
        and not parsed.query
        and not parsed.fragment,
        "nonlocal_artifact_uri",
    )
    path = Path(url2pathname(parsed.path)).absolute()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("artifact_outside_packet") from error
    observed = file_entry(root, relative)
    require(
        observed["sha256"] == reference.sha256
        and observed["size_bytes"] == reference.size_bytes,
        "artifact_identity_mismatch",
    )
    return relative
