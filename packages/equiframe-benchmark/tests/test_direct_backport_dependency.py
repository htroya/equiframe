"""The runtime's direct typing_extensions imports require a direct dependency."""

from __future__ import annotations

import ast
import importlib.metadata
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def test_typing_extensions_is_declared_directly_and_locked(source_packages: Path) -> None:
    root = source_packages / "equiframe-benchmark"
    installed = [
        Requirement(value) for value in importlib.metadata.requires("equiframe-benchmark") or []
    ]
    assert any(
        canonicalize_name(req.name) == "typing-extensions" and req.marker is None
        for req in installed
    )
    project = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]
    requirements = [Requirement(value) for value in project["dependencies"]]
    direct = [req for req in requirements if canonicalize_name(req.name) == "typing-extensions"]
    assert len(direct) == 1 and direct[0].marker is None
    assert "4.14.0" in direct[0].specifier and "5.0.0" not in direct[0].specifier
    modules = []
    for source in (root / "src").rglob("*.py"):
        tree = ast.parse(source.read_text("utf-8"))
        if any(
            isinstance(node, ast.ImportFrom) and node.module == "typing_extensions"
            for node in ast.walk(tree)
        ):
            modules.append(source.name)
    assert len(modules) == 16
    lock = tomllib.loads((root / "uv.lock").read_text("utf-8"))
    package = next(p for p in lock["package"] if p["name"] == "equiframe-benchmark")
    assert any(p["name"] == "typing-extensions" for p in package["dependencies"])
    assert any(
        p["name"] == "typing-extensions" and p["specifier"] == ">=4.14,<5"
        for p in package["metadata"]["requires-dist"]
    )
