"""Reject duplicate cores, active Actions workflows and modified archived bytes."""

import hashlib
import json
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def layout_errors(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    duplicate = root / "packages/equiframe"
    if (duplicate / "pyproject.toml").exists() or (
        duplicate / "src/equiframe/__init__.py"
    ).exists():
        errors.append("duplicate active core at packages/equiframe")
    workflows = root / ".github/workflows"
    if workflows.is_dir() and any(
        path.suffix.lower() in (".yml", ".yaml") for path in workflows.iterdir()
    ):
        errors.append("active GitHub Actions workflow contradicts manual release policy")
    config = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))
    if "/archive/**" not in config["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]:
        errors.append("sdist must explicitly exclude historical archives")
    if "archive" not in config["tool"]["ruff"]["extend-exclude"]:
        errors.append("Ruff must keep historical archives outside the active source scope")
    archive = root / "archive/research-a14"
    inventory = archive / "inventory.json"
    if inventory.exists():
        if inventory.is_symlink() or inventory.stat().st_size > 2 * 1024**2:
            return [*errors, "invalid archive inventory"]
        entries = json.loads(inventory.read_text("utf-8"))["files"]
        for item in entries:
            path = root / item["archived"]
            if (
                not path.resolve().is_relative_to(archive.resolve())
                or path.is_symlink()
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
            ):
                errors.append("archived file missing, substituted or modified: " + item["original"])
    return errors


def main() -> None:
    errors = layout_errors(Path(__file__).resolve().parents[1])
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        raise SystemExit(1)
    print("Active repository layout checked; archives remain outside current distributions.")


if __name__ == "__main__":
    main()
