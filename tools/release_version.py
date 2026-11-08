"""Resolve project versions through the build backend, never an older installation."""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from hatchling.builders.wheel import WheelBuilder

RELEASE_TAG = re.compile(r"v((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))")


def project_version(package: Path, *, require_tag: bool = False) -> str:
    """Read static legacy metadata or the configured Hatch VCS version.

    Release checks require one exact SemVer tag at a clean Git HEAD and reject
    environment overrides. An extracted sdist resolves through its PKG-INFO via
    Hatch; it does not require Git or a generated, untracked Python version file.
    """
    config = tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    if "version" in project:
        value = project["version"]
        if not isinstance(value, str) or not value:
            raise ValueError("static project version must be nonempty text")
        return value
    if (
        "version" not in project.get("dynamic", [])
        or config.get("tool", {}).get("hatch", {}).get("version", {}).get("source") != "vcs"
    ):
        raise ValueError("project version must use the declared Hatch VCS source")
    tagged = None
    if require_tag:
        if any(
            key.startswith("SETUPTOOLS_SCM_") or key == "HATCH_BUILD_VERSION" for key in os.environ
        ):
            raise ValueError("release version overrides are forbidden")
        root = Path(_git(package, "rev-parse", "--show-toplevel"))
        if _git(root, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("release version requires a clean Git checkout")
        tags = [
            match[1]
            for tag in _git(root, "tag", "--points-at", "HEAD").splitlines()
            if (match := RELEASE_TAG.fullmatch(tag)) is not None
        ]
        if len(tags) != 1:
            raise ValueError("release version requires exactly one vX.Y.Z tag at Git HEAD")
        tagged = tags[0]
    value = WheelBuilder(str(package)).metadata.version
    if not isinstance(value, str) or not value:
        raise ValueError("build backend returned an invalid version")
    if tagged is not None and value != tagged:
        raise ValueError("build backend version differs from the exact Git release tag")
    if require_tag and project.get("name") == "equiframe":
        source = package / "src" / "equiframe" / "detector_types.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        producers = [
            field.value.value
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "DetectorVersions"
            for field in node.body
            if isinstance(field, ast.AnnAssign)
            and isinstance(field.target, ast.Name)
            and field.target.id == "equiframe"
            and isinstance(field.value, ast.Constant)
            and isinstance(field.value.value, str)
        ]
        if producers != [value]:
            raise ValueError("detector producer default differs from the exact Git release version")
    return value


def _git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=directory, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise ValueError("release version requires a real Git checkout")
    return result.stdout.strip()
