#!/usr/bin/env python3
"""Collect one package's exact test files and pytest/JUnit identities."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_files(source: Path) -> dict[str, dict[str, object]]:
    tests = source / "tests"
    if tests.is_symlink() or not tests.is_dir():
        raise ValueError("package tests directory is absent or linked")
    files: dict[str, dict[str, object]] = {}
    for path in sorted(tests.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"test source contains a symbolic link: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if "__pycache__" in path.relative_to(source).parts or path.suffix in {
            ".pyc",
            ".pyo",
        }:
            continue
        if "\\" in relative or ".." in Path(relative).parts:
            raise ValueError(f"test source has a nonportable path: {relative}")
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"test source is not a regular file: {relative}")
        files[relative] = {"sha256": sha256(path), "size_bytes": path.stat().st_size}
    if not files:
        raise ValueError("package test source is empty")
    return files


class Collector:
    def __init__(self) -> None:
        self.identities: list[dict[str, str]] = []

    def pytest_collection_finish(self, session: Any) -> None:
        from _pytest.junitxml import mangle_test_address

        for item in session.items:
            address = mangle_test_address(item.nodeid)
            if len(address) < 2:
                raise ValueError(f"pytest node ID cannot form a JUnit identity: {item.nodeid}")
            self.identities.append(
                {
                    "nodeid": item.nodeid,
                    "classname": ".".join(address[:-1]),
                    "name": address[-1],
                }
            )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        parser.error("output must be a new file")
    if not args.package or any(character.isspace() for character in args.package):
        parser.error("package identity is malformed")

    import pytest

    collector = Collector()
    collected_stdout = io.StringIO()
    collected_stderr = io.StringIO()
    previous = Path.cwd()
    previous_dont_write_bytecode = sys.dont_write_bytecode
    previous_plugin_autoload = os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    source_files = test_files(source)
    try:
        os.chdir(source)
        sys.dont_write_bytecode = True
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        with (
            contextlib.redirect_stdout(collected_stdout),
            contextlib.redirect_stderr(collected_stderr),
        ):
            result = pytest.main(
                [
                    "--collect-only",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-p",
                    "no:stepwise",
                    "-p",
                    "_hypothesis_pytestplugin",
                    "tests",
                ],
                plugins=[collector],
            )
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
        if previous_plugin_autoload is None:
            os.environ.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
        else:
            os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = previous_plugin_autoload
        os.chdir(previous)
    if result != pytest.ExitCode.OK:
        raise RuntimeError(
            "pytest collection failed with exit code "
            f"{int(result)}: {(collected_stderr.getvalue() or collected_stdout.getvalue())[-2000:]}"
        )
    identities = sorted(collector.identities, key=lambda item: item["nodeid"])
    if not identities or len({item["nodeid"] for item in identities}) != len(identities):
        raise ValueError("pytest test identities are empty or duplicated")
    if test_files(source) != source_files:
        raise ValueError("pytest collection changed the package test source")
    junit = [(item["classname"], item["name"]) for item in identities]
    if len(set(junit)) != len(junit):
        raise ValueError("pytest tests do not have unique JUnit identities")
    write_json(
        output,
        {
            "schema": "equiframe-test-manifest-1",
            "package": args.package,
            "pytest_version": pytest.__version__,
            "hypothesis_version": importlib.metadata.version("hypothesis"),
            "plugin_autoload_disabled": True,
            "files": source_files,
            "tests": identities,
            "test_count": len(identities),
        },
    )
    print(json.dumps({"package": args.package, "tests": len(identities)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
