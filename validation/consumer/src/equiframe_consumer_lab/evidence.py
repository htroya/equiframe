"""Application-level evidence and fail-closed local publication, not core internals."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import sys
import uuid
from collections.abc import Callable, Collection
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, TypeAlias, TypedDict, cast

if TYPE_CHECKING:
    import pyarrow as pa

# Open JSON objects retain the producer's heterogeneous evidence fields. Their
# existing runtime validation remains authoritative at deserialization boundaries.
JsonObject: TypeAlias = dict[str, Any]


class InventoryMember(TypedDict):
    path: str
    size_bytes: int
    sha256: str


class PublicationReceipt(TypedDict):
    version: str
    sha256: str
    rows: int
    guarantee: str


class ConsumerError(RuntimeError):
    pass


class PublicationCommittedError(ConsumerError):
    """The pointer commit succeeded, but postcommit confirmation failed."""

    def __init__(self, receipt: PublicationReceipt, cause: Exception):
        self.receipt = dict(receipt)
        super().__init__("Publication committed; confirmation failed: " + type(cause).__name__)


def require(condition: bool, message: str) -> None:
    # Deliberately independent of Python assert; remains active under python -O.
    if not condition:
        raise ConsumerError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False, allow_nan=False, default=str)
        stream.write("\n")


def _frozen_path(name: object) -> str:
    if not isinstance(name, str) or not name:
        raise ConsumerError("Invalid frozen member path")
    path = PurePosixPath(name)
    require(
        not path.is_absolute()
        and path.as_posix() == name
        and ".." not in path.parts
        and name != "."
        and not any(character in name for character in ("\\", ":", "\x00")),
        "Invalid frozen member path",
    )
    return name


def _frozen_regular_file(data: Path, name: str) -> Path:
    """Require ordinary files and parents in an operator-controlled dataset root.

    This is not a sandbox against a concurrent hostile filesystem writer.
    """
    path = data
    parts = PurePosixPath(_frozen_path(name)).parts
    for index, part in enumerate(parts):
        path = path / part
        metadata = path.lstat()
        require(
            not stat.S_ISLNK(metadata.st_mode)
            and not getattr(metadata, "st_file_attributes", 0) & 0x400,
            "Frozen member links are not allowed",
        )
        require(
            stat.S_ISREG(metadata.st_mode)
            if index == len(parts) - 1
            else stat.S_ISDIR(metadata.st_mode),
            "Frozen member must be a regular file with ordinary parents",
        )
    return path


def _frozen_manifest_bytes(data: Path) -> bytes:
    path = _frozen_regular_file(data, "manifest.json")
    limit = 4 * 1024 * 1024
    require(path.stat().st_size <= limit, "Frozen manifest exceeds 4MiB")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Frozen manifest exceeds 4MiB")
    return raw


def frozen_manifest_sha256(data: Path) -> str:
    """Capture the local manifest identity before any frozen inputs are read."""
    return hashlib.sha256(_frozen_manifest_bytes(data)).hexdigest()


def verify_frozen(
    data: Path,
    *,
    required_paths: Collection[str],
    expected_manifest_sha256: str,
) -> JsonObject:
    """Verify every listed member and bind all consumed inputs to one manifest."""
    require(bool(required_paths), "Consumer must declare its frozen input paths")
    required = {_frozen_path(name) for name in required_paths}
    require(
        isinstance(expected_manifest_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is not None,
        "Invalid expected frozen manifest SHA-256",
    )
    raw = _frozen_manifest_bytes(data)
    require(
        hashlib.sha256(raw).hexdigest() == expected_manifest_sha256,
        "Frozen manifest SHA-256 differs",
    )

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate frozen manifest JSON member")
            result[key] = value
        return result

    document = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(document, dict), "Dataset manifest must be an object")
    require(document.get("status") == "FROZEN", "Dataset manifest must be FROZEN")
    files = document.get("files")
    require(isinstance(files, list) and bool(files), "Frozen file inventory must not be empty")
    members = {}
    for item in files:
        require(isinstance(item, dict), "Invalid frozen file entry")
        name = _frozen_path(item.get("path"))
        require(name not in members, "Duplicate frozen member path")
        size, digest = item.get("size_bytes"), item.get("sha256")
        require(type(size) is int and size >= 0, "Invalid frozen member size")
        require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "Invalid frozen member SHA-256",
        )
        members[name] = item
    require(required <= members.keys(), "Consumed input is missing from frozen inventory")
    for name, item in members.items():
        path = _frozen_regular_file(data, name)
        require(path.stat().st_size == item["size_bytes"], "Frozen data size differs")
        require(sha256(path) == item["sha256"], "Frozen data SHA-256 differs")
    return cast(JsonObject, document)


def environment() -> JsonObject:
    import equiframe as ef

    require(importlib.metadata.version("equiframe") == "0.12.4", "Wrong installed core version")
    require(
        importlib.metadata.version("equiframe-consumer-lab") == "0.1.19",
        "Wrong installed consumer version",
    )
    package = Path(ef.__file__).resolve()
    require(
        package.is_relative_to(Path(sys.prefix).resolve()) and "site-packages" in package.parts,
        "Core import is not from installed environment",
    )
    own = Path(__file__).resolve()
    require(
        own.is_relative_to(Path(sys.prefix).resolve()) and "site-packages" in own.parts,
        "Consumer import is not installed",
    )
    require(sys.flags.isolated == 1, "Run this consumer with python -I")
    installed_record = importlib.metadata.distribution("equiframe").read_text("RECORD")
    if installed_record is None:
        raise ConsumerError("Installed core distribution RECORD is missing")
    return {
        "python": sys.version,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "isolated": sys.flags.isolated,
        "optimized": sys.flags.optimize,
        "equiframe_file": str(package),
        "consumer_file": str(own),
        "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "core_source_commit": None,
        "core_source_tree": None,
        "core_distribution_record_sha256": hashlib.sha256(
            installed_record.encode("utf-8")
        ).hexdigest(),
        "core_source_identity_note": (
            "Git identity is not inferred from a version string. The external candidate/install "
            "manifest binds this execution to exact wheel bytes and source."
        ),
    }


def verify_report(root: Path) -> None:
    import equiframe as ef

    names = {"report.json", "report.txt", "report.html", "evidence-manifest.json"}
    require({p.name for p in root.iterdir()} == names, "Report inventory differs")
    manifest = ef.ReportPublicationManifest.model_validate_json(
        (root / "evidence-manifest.json").read_bytes()
    )
    require(
        {f.path for f in manifest.files} == names - {"evidence-manifest.json"},
        "Report manifest inventory differs",
    )
    for item in manifest.files:
        p = root / item.path
        require(
            p.is_file()
            and not p.is_symlink()
            and p.stat().st_size == item.size_bytes
            and sha256(p) == item.sha256,
            "Report bytes differ",
        )
    report = ef.read_comparison_report(root / "report.json")
    require(
        not report.options.include_values and not report.options.include_metadata,
        "Report must remain redacted",
    )


def publish(
    table: pa.Table,
    destination: Path,
    *,
    accepted: bool,
    fault: str | None = None,
    precommit: Callable[[PublicationReceipt], None] | None = None,
) -> PublicationReceipt:
    """Local app publication: single-writer atomic pointer, never permits a failed gate."""
    require(accepted is True, "Publication requires explicit successful acceptance")
    import pyarrow.parquet as pq

    destination.mkdir(parents=True, exist_ok=True)
    run_id = "version-" + uuid.uuid4().hex
    stage = destination / (".staging-" + run_id)
    stage.mkdir()
    committed = False
    receipt: PublicationReceipt | None = None
    try:
        pq.write_table(table, stage / "data.parquet")
        receipt = {
            "version": run_id,
            "sha256": sha256(stage / "data.parquet"),
            "rows": table.num_rows,
            "guarantee": "single_writer_local_atomic_pointer",
        }
        write_json(stage / "receipt.json", receipt)
        require(
            pq.read_table(stage / "data.parquet").equals(table), "Published data readback differs"
        )
        if precommit is not None:
            precommit(receipt)
        if fault == "before_commit":
            raise ConsumerError("Controlled publication failure before visibility commit")
        versions = destination / "versions"
        versions.mkdir(exist_ok=True)
        stage.rename(versions / run_id)
        pointer = destination / (".pointer-" + run_id + ".json")
        write_json(pointer, receipt)
        os.replace(pointer, destination / "current.json")
        committed = True
        require(
            json.loads((destination / "current.json").read_text()) == receipt,
            "Publication pointer readback differs",
        )
        return receipt
    except Exception as error:
        if committed:
            raise PublicationCommittedError(cast(PublicationReceipt, receipt), error) from error
        raise
    finally:
        if not committed and stage.exists():
            shutil.rmtree(stage)


def inventory(root: Path) -> list[InventoryMember]:
    return [
        {
            "path": p.relative_to(root).as_posix(),
            "size_bytes": p.stat().st_size,
            "sha256": sha256(p),
        }
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "app-manifest.json"
    ]


def replace_owned_json(path: Path, obj: object) -> None:
    """Rewrite only a receipt owned by the current fresh operation, atomically."""
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        write_json(temporary, obj)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
