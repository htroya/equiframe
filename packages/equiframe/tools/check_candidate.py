"""Execute candidate checks and retain command receipts without publication."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_manifest import (
    artifact_inventory,
    dependency_artifacts,
    local_dependency_names,
    local_dependency_sources,
    runtime_binding_matches,
    source_snapshot,
)

# Only names obtained from the repository's src packages are resolved/imported.
# No build backend, entry point, or plugin named by configuration is executed.
_RUNTIME_PROBE = r"""
import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path

resolved = []
for dependency in json.loads(sys.argv[1]):
    imports = []
    for source in dependency["imports"]:
        name = source["name"]
        spec = importlib.util.find_spec(name)
        if spec is None or spec.origin is None or spec.submodule_search_locations is None:
            raise RuntimeError("local dependency cannot resolve a regular package: " + name)
        origin = Path(spec.origin).resolve()
        root = origin.parent
        # Inspect every source file, not a version string or one added symbol.
        files = {}
        for relative in source["files"]:
            installed = root / relative
            if installed.is_symlink() or not installed.is_file():
                raise RuntimeError("local dependency runtime file missing: " + str(installed))
            files[relative] = hashlib.sha256(installed.read_bytes()).hexdigest()
        if files != source["files"]:
            raise RuntimeError("stale local dependency runtime bytes: " + name)
        # Reject obsolete Python modules left behind by an earlier installation.
        extra = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                       if path.is_file() and path.suffix in {".py", ".pyi", ".so", ".pyd"}
                       and path.relative_to(root).as_posix() not in source["files"])
        if extra:
            raise RuntimeError("unexpected local dependency runtime modules: " + str(extra))
        module = importlib.import_module(name)
        if (Path(module.__file__).resolve() != origin
                or [Path(value).resolve() for value in module.__path__] != [root]):
            raise RuntimeError("local dependency import changed its resolved package: " + name)
        imports.append({"name": name, "origin": str(origin), "root": str(root), "files": files})
    resolved.append({"distribution": dependency["distribution"], "imports": imports})
print(json.dumps(resolved, sort_keys=True))
"""


def local_dependency_runtime_binding(
    package: Path,
    python_command: list[str],
    bytecode_directory: Path,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve installed imports with the candidate interpreter and compare bytes.

    A fresh bytecode prefix prevents timestamp-valid stale .pyc files from
    supplying code whose adjacent .py happens to match the current source.
    """
    sources = local_dependency_sources(package)
    binding: dict[str, Any] = {
        "algorithm": "sha256-imported-local-source-v1",
        "source_snapshot": source_snapshot(package),
        "source_dependencies": sources,
        "resolved_dependencies": [],
        "verified": False,
    }
    if not sources:
        binding["verified"] = True
        return binding
    command = [
        *python_command,
        "-I",
        "-B",
        "-X",
        "pycache_prefix=" + str(bytecode_directory),
        "-c",
        _RUNTIME_PROBE,
        json.dumps(sources),
    ]
    completed = subprocess.run(
        command,
        cwd=package,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    binding["command"] = command
    binding["exit_code"] = completed.returncode
    if completed.returncode:
        binding["error"] = completed.stderr.strip()
        return binding
    try:
        binding["resolved_dependencies"] = json.loads(completed.stdout)
    except json.JSONDecodeError:
        binding["error"] = "runtime probe did not return its JSON inventory"
        return binding
    binding["verified"] = True
    binding["verified"] = runtime_binding_matches(binding, package)
    return binding


def candidate_environment(bytecode_directory: Path) -> dict[str, str]:
    """Use the same isolated import inputs for probes and source controls."""
    environment = dict(os.environ)
    for variable in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(variable, None)
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONPYCACHEPREFIX=str(bytecode_directory),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--uv", default=shutil.which("uv"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.uv:
        raise SystemExit("an available uv executable is required")
    package = args.package.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    initial_source = source_snapshot(package)
    project = tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    stem = project["name"].replace("-", "_") + "-" + project["version"]
    artifacts = (
        package / "dist" / (stem + "-py3-none-any.whl"),
        package / "dist" / (stem + ".tar.gz"),
    )
    dependencies = dependency_artifacts(package)
    base = [args.uv, "run", "--locked", "--all-extras", "--no-sync"]
    sync = [args.uv, "sync", "--locked", "--all-extras", "--python", "3.12"]
    for name in local_dependency_names(package):
        sync += ["--reinstall-package", name]
    commands = [
        sync,
        [*base, "ruff", "check", "."],
        [*base, "ruff", "format", "--check", "."],
        [*base, "mypy"],
        [*base, "python", "tools/generate_assets.py", "--check"],
        [*base, "pytest", "-q", "--basetemp", str(output.parent / (output.stem + "-pytest-tmp"))],
        [*base, "python", "-m", "build", "--no-isolation"],
        [*base, "twine", "check", "--strict"],
        [*base, "python", "tools/verify_distribution.py", "--uv", args.uv],
    ]
    # Neither the probe nor subsequent Python checks may reuse old bytecode.
    with tempfile.TemporaryDirectory(prefix="equiframe-candidate-bytecode-") as directory:
        check_environment = candidate_environment(Path(directory))
        run_checks(
            package,
            output,
            initial_source,
            artifacts,
            dependencies,
            commands,
            [*base, "python"],
            Path(directory),
            check_environment,
        )


def run_checks(
    package: Path,
    output: Path,
    initial_source: dict[str, Any],
    artifacts: tuple[Path, ...],
    dependencies: tuple[Path, ...],
    commands: list[list[str]],
    python_command: list[str],
    bytecode_directory: Path,
    environment: dict[str, str],
) -> None:
    results = []
    for number, command in enumerate(commands):
        binding = None
        if number:
            binding = local_dependency_runtime_binding(
                package, python_command, bytecode_directory, environment
            )
            if not binding["verified"]:
                raise SystemExit("local dependency runtime binding failed: " + str(binding))
        before = source_snapshot(package)
        if before != initial_source:
            raise SystemExit("source changed between candidate checks; restart against fixed bytes")
        if "twine" in command:
            command += [str(path) for path in artifacts]
        artifacts_before = artifact_inventory(artifacts)
        dependencies_before = artifact_inventory(dependencies)
        started_at = datetime.now(UTC).isoformat()
        tick = time.monotonic()
        log = output.parent / f"{output.stem}-{number:02d}.log"
        print("Executing", " ".join(command), flush=True)
        with log.open("w", encoding="utf-8") as stream:
            completed = subprocess.run(
                command,
                cwd=package,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if number == 0 and completed.returncode == 0:
            binding = local_dependency_runtime_binding(
                package, python_command, bytecode_directory, environment
            )
        results.append(
            {
                "command": command,
                "cwd": str(package),
                "started_at": started_at,
                "seconds": time.monotonic() - tick,
                "exit_code": completed.returncode,
                "log": log.name,
                "source_before": before,
                "source_after": source_snapshot(package),
                "artifacts": artifact_inventory(artifacts),
                "artifacts_before": artifacts_before,
                "dependency_artifacts_before": dependencies_before,
                "dependency_artifacts": artifact_inventory(dependencies),
                "local_dependency_runtime_binding": binding,
            }
        )
        output.write_text(
            json.dumps(
                {
                    "environment": {
                        "platform": platform.platform(),
                        "python_driver": platform.python_version(),
                        "uv": commands[0][0],
                        "PYTHONDONTWRITEBYTECODE": environment["PYTHONDONTWRITEBYTECODE"],
                        "PYTHONPYCACHEPREFIX": environment["PYTHONPYCACHEPREFIX"],
                        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR"),
                        "PYTHONUTF8": os.environ.get("PYTHONUTF8"),
                    },
                    "results": results,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode:
            raise SystemExit(completed.returncode)
        if binding is None or not binding["verified"]:
            raise SystemExit("local dependency runtime binding failed; inspect the receipt")
        if results[-1]["source_after"] != initial_source:
            raise SystemExit("source changed during candidate check; its result cannot validate it")
        if number in {7, 8} and results[-1]["artifacts"] != artifacts_before:
            raise SystemExit("artifacts changed during candidate check; restart with fixed bytes")
        if number == 8 and results[-1]["dependency_artifacts"] != dependencies_before:
            raise SystemExit("dependency wheels changed during installed candidate checks")


if __name__ == "__main__":
    main()
