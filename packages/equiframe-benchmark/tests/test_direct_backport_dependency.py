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


def test_typing_extensions_is_declared_directly_and_locked(
    source_packages: dict[str, Path],
) -> None:
    root = source_packages["equiframe-benchmark"]
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
    modules = set()
    for source in (root / "src").rglob("*.py"):
        tree = ast.parse(source.read_text("utf-8"))
        if any(
            isinstance(node, ast.ImportFrom) and node.module == "typing_extensions"
            for node in ast.walk(tree)
        ):
            modules.add(source.relative_to(root / "src").as_posix())
    assert modules == {
        "equiframe_benchmark/calibration_types.py",
        "equiframe_benchmark/costs.py",
        "equiframe_benchmark/distribution.py",
        "equiframe_benchmark/evaluation.py",
        "equiframe_benchmark/evaluation_v2.py",
        "equiframe_benchmark/freeze.py",
        "equiframe_benchmark/freeze_v2.py",
        "equiframe_benchmark/integration.py",
        "equiframe_benchmark/models.py",
        "equiframe_benchmark/pairwise.py",
        "equiframe_benchmark/reconciliation.py",
        "equiframe_benchmark/reproduction.py",
        "equiframe_benchmark/scale_process.py",
        "equiframe_benchmark/scale_types.py",
        "equiframe_benchmark/scaling.py",
        "equiframe_benchmark/study.py",
        "equiframe_benchmark/study_v2.py",
        "equiframe_benchmark/tables.py",
        "equiframe_benchmark/tables_v2.py",
        "equiframe_benchmark/training_types.py",
    }
    lock = tomllib.loads((root / "uv.lock").read_text("utf-8"))
    package = next(p for p in lock["package"] if p["name"] == "equiframe-benchmark")
    assert any(p["name"] == "typing-extensions" for p in package["dependencies"])
    assert any(
        p["name"] == "typing-extensions" and p["specifier"] == ">=4.14,<5"
        for p in package["metadata"]["requires-dist"]
    )
