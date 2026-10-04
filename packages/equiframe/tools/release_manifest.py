"""Identify candidate artifacts and executed checks; never publish or assign a license."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECK_STAGES = (
    "locked_sync",
    "ruff_check",
    "ruff_format",
    "mypy",
    "assets",
    "pytest",
    "build",
    "twine",
    "distribution",
)


def source_snapshot(package: Path) -> dict[str, Any]:
    """Identify tested worktree bytes, including locally resolved dependencies."""
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    pending = [package.resolve()]
    visited: set[Path] = set()
    inventory: dict[str, str] = {}
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        if not current.is_relative_to(repository):
            raise SystemExit("local check dependencies must belong to the source repository")
        visited.add(current)
        relative = current.relative_to(repository).as_posix()
        paths = git_output(
            repository,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ":(literal)" + relative,
        ).split("\0")
        for name in paths:
            if not name:
                continue
            file = repository / name
            if file.is_symlink() or not file.is_file():
                raise SystemExit("check source must contain regular existing files: " + name)
            inventory[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        project = tomllib.loads((current / "pyproject.toml").read_text(encoding="utf-8"))
        sources = project.get("tool", {}).get("uv", {}).get("sources", {})
        for source in sources.values():
            if isinstance(source, list):
                raise SystemExit(
                    "conditional uv sources require explicit candidate binding support"
                )
            if isinstance(source, dict) and isinstance(source.get("path"), str):
                pending.append((current / source["path"]).resolve())
    encoded = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "algorithm": "sha256-git-worktree-v1",
        "packages": sorted(path.relative_to(repository).as_posix() for path in visited),
        "file_count": len(inventory),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def artifact_inventory(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    return [
        {
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in paths
        if path.is_file()
    ]


def dependency_artifacts(package: Path) -> tuple[Path, ...]:
    """Wheels consumed by installed tests for locally resolved dependencies."""
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    paths = []
    for relative in source_snapshot(package)["packages"]:
        dependency = repository / relative
        if dependency.resolve() == package.resolve():
            continue
        project = tomllib.loads((dependency / "pyproject.toml").read_text("utf-8"))["project"]
        stem = project["name"].replace("-", "_") + "-" + project["version"]
        paths.append(dependency / "dist" / (stem + "-py3-none-any.whl"))
    return tuple(paths)


def git_output(directory: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as error:
        raise SystemExit("Git source cannot be verified: git executable unavailable") from error
    if result.returncode:
        raise SystemExit("Git source cannot be verified: a tracked Git package is required")
    return result.stdout.strip()


def verified_source_commit(package: Path, requested: str | None) -> str:
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    head = git_output(package, "rev-parse", "--verify", "HEAD^{commit}")
    commit = requested if requested is not None else head
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise SystemExit("commit must be an exact 40-character source revision")
    if commit != head:
        raise SystemExit("commit must identify the verified package Git HEAD exactly")
    for relative in source_snapshot(package)["packages"]:
        project = (Path(relative) / "pyproject.toml").as_posix()
        git_output(repository, "ls-files", "--error-unmatch", "--", project)
        status = git_output(
            repository,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            ":(literal)" + relative,
        )
        if status:
            raise SystemExit(
                "verified package and local dependencies must have no tracked changes "
                "or untracked source files"
            )
    return commit


def command_parts(command: list[str], package: Path) -> tuple[str, list[str]] | None:
    program = Path(command[0]).name.lower().removesuffix(".exe")
    arguments = command[1:]
    if program == "uv":
        if arguments and arguments[0] == "sync":
            return "locked_sync", arguments[1:]
        if not arguments or arguments[0] != "run":
            return None
        arguments = arguments[1:]
        while arguments and arguments[0] in {"--locked", "--all-extras", "--frozen", "--no-sync"}:
            arguments = arguments[1:]
        if not arguments:
            return None
        program = Path(arguments[0]).name.lower().removesuffix(".exe")
        arguments = arguments[1:]
    if program in {"python", "python3", "python3.12"}:
        while arguments and arguments[0] in {"-I", "-B", "-u"}:
            arguments = arguments[1:]
        if len(arguments) >= 2 and arguments[0] == "-m":
            if arguments[1] in {"ruff", "mypy", "pytest", "build", "twine"}:
                return arguments[1], arguments[2:]
            return None
        if not arguments:
            return None
        script = (package / arguments[0]).resolve()
        for name, stage in (
            ("generate_assets.py", "assets"),
            ("verify_distribution.py", "distribution"),
        ):
            if script == (package / "tools" / name).resolve():
                return stage, arguments[1:]
        return None
    if program in {"ruff", "mypy", "pytest", "twine"}:
        return program, arguments
    return None


def whole_pytest(arguments: list[str]) -> bool:
    """Allow operational flags, never a selected test, marker or expression."""
    positional = []
    quiet = False
    index = 0
    switches = {"-q", "--quiet", "-ra", "-rA", "-x", "--exitfirst", "--disable-warnings", "-s"}
    valued = {"--basetemp", "--tb", "--color", "--capture"}
    while index < len(arguments):
        value = arguments[index]
        if value in switches:
            quiet = quiet or value in {"-q", "--quiet"}
        elif value in valued:
            index += 1
            if index >= len(arguments) or arguments[index].startswith("-"):
                return False
        elif any(value.startswith(option + "=") and value != option + "=" for option in valued):
            pass
        elif value == "-p":
            index += 1
            if index >= len(arguments) or arguments[index] != "no:cacheprovider":
                return False
        elif value in {".", "tests"}:
            positional.append(value)
        else:
            return False
        index += 1
    return quiet and len(positional) <= 1


def check_stage(command: list[str], package: Path, artifacts: tuple[Path, ...]) -> str | None:
    parts = command_parts(command, package)
    if parts is None:
        return None
    program, arguments = parts
    if program == "locked_sync":
        remaining = arguments.copy()
        if "--python" in remaining:
            index = remaining.index("--python")
            if index + 1 >= len(remaining) or remaining[index + 1].startswith("-"):
                return None
            del remaining[index : index + 2]
        if set(remaining) == {"--locked", "--all-extras"}:
            return "locked_sync"
    elif program == "ruff":
        if arguments == ["check", "."]:
            return "ruff_check"
        if arguments == ["format", "--check", "."]:
            return "ruff_format"
    elif program == "mypy":
        positional = [value for value in arguments if value not in {"--strict", "--no-incremental"}]
        if positional in ([], ["."]) or set(positional) == {"src", "tools"}:
            return "mypy"
    elif program == "assets" and arguments == ["--check"]:
        return "assets"
    elif program == "pytest" and whole_pytest(arguments):
        return "pytest"
    elif program == "build":
        if set(arguments) in ({"--no-isolation"}, {"--no-isolation", "--wheel", "--sdist"}):
            return "build"
    elif program == "twine" and arguments[:2] == ["check", "--strict"]:
        filenames = arguments[2:]
        if filenames and not any(value.startswith("-") for value in filenames):
            checked = {(package / value).resolve() for value in filenames}
            if set(artifacts).issubset(checked):
                return "twine"
    elif program == "distribution":
        if not arguments or (len(arguments) == 2 and arguments[0] == "--uv" and arguments[1]):
            return "distribution"
    return None


def read_check_receipts(
    paths: list[Path], package: Path, artifacts: tuple[Path, ...]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receipts = []
    successful: set[str] = set()
    bound: set[str] = set()
    current_source = source_snapshot(package)
    current_artifacts = artifact_inventory(artifacts)
    dependencies = dependency_artifacts(package)
    current_dependencies = artifact_inventory(dependencies)
    failed_commands = 0
    for path in paths:
        raw = path.read_bytes()
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise SystemExit("invalid check receipt")
        results = document.get("results")
        if not isinstance(results, list) or not results:
            raise SystemExit("check receipt requires executed commands")
        for check in results:
            if not isinstance(check, dict):
                raise SystemExit("invalid check receipt")
            command, exit_code, cwd = check.get("command"), check.get("exit_code"), check.get("cwd")
            if (
                type(exit_code) is not int
                or not isinstance(command, list)
                or not command
                or not all(isinstance(value, str) and value for value in command)
            ):
                raise SystemExit("invalid check receipt")
            if (
                not isinstance(cwd, str)
                or not Path(cwd).is_absolute()
                or Path(cwd).resolve() != package
            ):
                raise SystemExit("check receipt cwd must identify the verified package exactly")
            if exit_code:
                failed_commands += 1
            else:
                stage = check_stage(command, package, artifacts)
                if stage is not None:
                    successful.add(stage)
                    before, after = check.get("source_before"), check.get("source_after")
                    if (
                        before == current_source
                        and after == current_source
                        and (
                            stage not in {"build", "twine", "distribution"}
                            or check.get("artifacts") == current_artifacts
                        )
                        and (
                            stage not in {"twine", "distribution"}
                            or check.get("artifacts_before") == current_artifacts
                        )
                        and (
                            stage != "distribution"
                            or (
                                len(current_dependencies) == len(dependencies)
                                and check.get("dependency_artifacts") == current_dependencies
                                and check.get("dependency_artifacts_before") == current_dependencies
                            )
                        )
                    ):
                        bound.add(stage)
        receipts.append(
            {
                "file": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "results": results,
                "environment": document.get("environment"),
            }
        )
    completion = {
        "required_stages": list(REQUIRED_CHECK_STAGES),
        "successful_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage in successful],
        "missing_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage not in successful],
        "failed_commands": failed_commands,
        "source_snapshot": current_source,
        "dependency_artifacts": current_dependencies,
        "source_bound_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage in bound],
        "unbound_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage not in bound],
        "receipts_authenticated": False,
    }
    return receipts, completion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT)
    parser.add_argument("--checks", type=Path, action="append", default=[])
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    project = tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    name, version = project["name"], project["version"]
    stem = name.replace("-", "_")
    artifacts = (
        package / "dist" / f"{stem}-{version}-py3-none-any.whl",
        package / "dist" / f"{stem}-{version}.tar.gz",
    )
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("build the identified wheel and sdist first")
    commit = verified_source_commit(package, args.commit)
    receipts, completion = read_check_receipts(args.checks, package, artifacts)
    blockers = [
        "PyPI name ownership/Trusted Publisher not established",
        "public documentation/access decision pending",
        "publication requires a separate explicit task",
    ]
    if not project.get("license"):
        blockers.insert(0, "author-approved license and redistribution terms absent")
    if completion["missing_stages"]:
        blockers.append(
            "complete successful execution receipts absent; missing stages: "
            + ", ".join(completion["missing_stages"])
        )
    if completion["failed_commands"]:
        blockers.append("one or more supplied execution receipts records a failed command")
    if completion["unbound_stages"]:
        blockers.append(
            "checks are not bound to current source/artifact bytes; stages: "
            + ", ".join(completion["unbound_stages"])
        )
    tools = {tool: importlib.metadata.version(tool) for tool in ("build", "hatchling", "twine")}
    manifest = {
        "schema_version": "1.0",
        "distribution": name,
        "version": version,
        "source_commit": commit,
        "source_validation": {"git_head": commit, "package_clean": True, "project_tracked": True},
        "generated_at": datetime.now(UTC).isoformat(),
        "python_support": project["requires-python"],
        "environment": {"python": sys.version, "platform": platform.platform(), "tools": tools},
        "artifacts": artifact_inventory(artifacts),
        "checks": receipts,
        "check_completion": completion,
        "evidence_scope": {
            "source": "Git HEAD and clean package checked at manifest generation",
            "checks": "supplied command records; execution and identity are not authenticated",
            "artifacts": (
                "hashes and sizes identify current bytes; build origin is not authenticated"
            ),
        },
        "license": project.get("license"),
        "publication_blockers": blockers,
        "published": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "version": version,
                "artifacts": manifest["artifacts"],
                "publication_blockers": blockers,
            }
        )
    )


if __name__ == "__main__":
    main()
