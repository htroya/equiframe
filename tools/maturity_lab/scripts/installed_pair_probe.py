#!/usr/bin/env python3
"""Bind actual installed package payloads to immutable candidate wheel bytes."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(wheel: Path, module_name: str) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("expected exactly one METADATA")
        meta = BytesParser().parsebytes(archive.read(metadata[0]))
        expected = {
            name: digest(archive.read(name))
            for name in names
            if name.startswith(module_name + "/") and not name.endswith("/")
        }
    if not expected:
        raise ValueError("wheel contains no expected package payload")
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        raise ValueError("package is unavailable: " + module_name)
    root = Path(spec.origin).parent
    if not root.resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("package is not installed inside the selected environment")
    found = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("linked installed package payload")
        if path.is_file() and not ("__pycache__" in path.parts and path.suffix == ".pyc"):
            found[module_name + "/" + path.relative_to(root).as_posix()] = digest(path.read_bytes())
    if found != expected:
        raise ValueError("actual package payload differs from candidate wheel")
    module = importlib.import_module(module_name)
    if Path(module.__file__).resolve() != (root / "__init__.py").resolve():
        raise ValueError("import location changed")
    if importlib.metadata.version(meta["Name"]) != meta["Version"]:
        raise ValueError("installed version differs from wheel metadata")
    return {
        "wheel_sha256": digest(wheel.read_bytes()),
        "distribution": meta["Name"],
        "version": meta["Version"],
        "origin": str(root),
        "payload": found,
        "verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--consumer", type=Path)
    parser.add_argument("--profile", choices=("base", "engines", "ml", "resources", "all"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.flags.isolated:
        raise ValueError("invoke this consumer with Python -I")
    result = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "system": platform.system(),
        "executable": sys.executable,
        "isolated": True,
        "packages": {},
    }
    for name, path in [
        ("equiframe", args.core),
        ("equiframe_benchmark", args.benchmark),
        ("equiframe_consumer_lab", args.consumer),
    ]:
        if path:
            result["packages"][name] = verify(path, name)
    if any(name in sys.modules for name in ("pyarrow", "pandas", "polars", "duckdb", "sklearn")):
        raise ValueError("public package import eagerly loaded optional engine or ML")
    if args.profile:
        expected = {
            "pyarrow": True,
            "pandas": args.profile in ("engines", "all"),
            "polars": args.profile in ("engines", "all"),
            "duckdb": args.profile in ("engines", "all"),
            "sklearn": args.profile in ("ml", "all"),
            "psutil": args.profile in ("resources", "all"),
        }
        actual = {name: importlib.util.find_spec(name) is not None for name in expected}
        if actual != expected:
            raise ValueError(f"profile {args.profile} dependencies differ: {actual}")
        result["profile_availability"] = actual
    result["installed_distributions"] = {
        dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
    }
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "python": result["python"],
                "machine": result["machine"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
