"""Identify an installed experimental package by comparing it with its local wheel."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import equiframe as ef


def receipt(wheel: Path) -> dict[str, Any]:
    package = Path(ef.__file__).resolve().parent
    files = []
    with zipfile.ZipFile(wheel) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith("equiframe/") or name.endswith("/"):
                continue
            relative = PurePosixPath(name).relative_to("equiframe")
            target = package.joinpath(*relative.parts)
            if ".." in relative.parts or not target.resolve().is_relative_to(package):
                raise ValueError("Invalid package path")
            if target.is_symlink() or target.read_bytes() != archive.read(name):
                raise ValueError("Installed package bytes differ from the supplied wheel")
            files.append({"path": name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    if not files:
        raise ValueError("No package files found")
    return {
        "version": importlib.metadata.version("equiframe"),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "files_checked": len(files),
        "all_package_files_equal": True,
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    print(json.dumps(receipt(args.wheel), indent=2))


if __name__ == "__main__":
    main()
