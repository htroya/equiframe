"""Check a first-use kit's closed inventory before installing or running it.

Hashes identify received bytes, not a signature or proof of a trusted author.
Obtain the ZIP and its SHA-256 through the team's trusted delivery channel.
Keep environments and generated results outside this immutable kit directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "equiframe-first-use-kit-1"
MANIFEST = "manifest.json"
PAYLOAD = frozenset(
    {
        "README.md",
        "INTERPRETATION.md",
        "OBSERVATION.md",
        "requirements.lock",
        "verify_kit.py",
        "refactor_comparison.py",
        "migrate_duckdb_recipe.py",
        "assertion_ci.py",
        "test_assertion_recipe.py",
    }
)


class KitError(ValueError):
    """The received kit cannot be verified; do not install or execute it."""


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
        return hasher.hexdigest()


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise KitError("duplicate manifest key")
        result[key] = value
    return result


def _regular(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise KitError("kit entries must be regular files")


def _relative(value: object) -> str:
    if not isinstance(value, str):
        raise KitError("invalid inventory path")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(part in {".", ".."} for part in value.split("/"))
        or path.as_posix() != value
    ):
        raise KitError("unsafe inventory path")
    return value


def verify_kit(directory: Path) -> dict[str, Any]:
    """Verify exact filenames, regular files, SHA-256 and byte counts.

    Fail closed on links (including directory links), extra/omitted files,
    malformed manifests and changes to the wheel or any recipe. This is an
    integrity check in a trusted local directory, not a concurrent-write sandbox.
    """
    if directory.is_symlink() or not directory.is_dir():
        raise KitError("kit root must be a regular directory")
    directory = directory.resolve()
    try:
        manifest_path = directory / MANIFEST
        _regular(manifest_path)
        manifest = json.loads(manifest_path.read_text("utf-8"), object_pairs_hook=_object)
        if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
            raise KitError("unsupported kit manifest")
        wheel = _relative(manifest.get("wheel"))
        if (
            len(PurePosixPath(wheel).parts) != 2
            or not wheel.startswith("wheels/")
            or re.fullmatch(r"equiframe-[A-Za-z0-9_.+-]+\.whl", Path(wheel).name) is None
        ):
            raise KitError("invalid wheel inventory entry")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != PAYLOAD | {wheel}:
            raise KitError("kit inventory must identify every required file exactly")
        expected = set(files) | {MANIFEST}
        actual = set()
        for path in directory.rglob("*"):
            mode = path.lstat().st_mode
            relative = path.relative_to(directory).as_posix()
            if stat.S_ISDIR(mode):
                if relative != "wheels":
                    raise KitError("unexpected kit directory")
                continue
            _regular(path)
            actual.add(relative)
        if actual != expected:
            raise KitError("kit contains missing or unexpected files")
        for name, record in files.items():
            _relative(name)
            if not isinstance(record, dict) or set(record) != {"sha256", "size_bytes"}:
                raise KitError("invalid file record")
            digest, size = record["sha256"], record["size_bytes"]
            if (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or type(size) is not int
                or size < 0
            ):
                raise KitError("invalid file digest or size")
            path = directory / name
            if path.stat().st_size != size or sha256(path) != digest:
                raise KitError("kit file checksum or size mismatch: " + name)
        return manifest
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise KitError("kit manifest or payload cannot be read") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).parent)
    args = parser.parse_args()
    try:
        manifest = verify_kit(args.directory)
    except KitError as error:
        print("Kit verification failed: " + str(error))
        return 1
    print("Kit inventory and SHA-256 verified: " + manifest["wheel"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
