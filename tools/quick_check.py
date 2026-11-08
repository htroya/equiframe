"""Small deterministic source-check layer; never builds, publishes or claims release readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as _timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

UTC = _timezone.utc

Package = Literal["core", "benchmark"]
CORE_TESTS = (
    "test_contracts.py",
    "test_architecture_boundaries.py",
    "test_progressive_docs.py",
    "test_sqlite_snapshot_example.py",
    "test_product_journeys.py",
    "test_result_truthiness.py",
    "test_operational_truthiness.py",
    "test_optional_configuration.py",
    "test_assertions.py",
    "test_diff_contracts.py",
    "test_compatibility_register.py",
    "test_snapshot_core.py",
    "test_versioned_compatibility.py",
    "test_migration_semantic_directions.py",
    "test_cli_diagnostics.py",
    "test_quick_check.py",
    "test_bounded_measurement.py",
)
BENCHMARK_TESTS = (
    "test_snapshot_core_aliases.py",
    "test_splits.py",
    "test_selection.py",
    "test_evaluation_boundaries.py",
    "test_verify_bridge.py",
    "test_cli_diagnostics.py",
)


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    directory: Path


def plan(repository: Path, package: Package, output: Path) -> tuple[Check, ...]:
    """Use the same explicit selection locally and in CI, independent of git diff heuristics."""
    directory = repository if package == "core" else repository / "packages/equiframe-benchmark"
    python = sys.executable
    tests = CORE_TESTS if package == "core" else BENCHMARK_TESTS
    checks = [
        Check("ruff", (python, "-m", "ruff", "check", "."), directory),
        Check("format", (python, "-m", "ruff", "format", "--check", "."), directory),
        Check(
            "mypy",
            (python, "-m", "mypy", "--python-version", ".".join(map(str, sys.version_info[:2]))),
            directory,
        ),
        Check("generated", (python, "tools/generate_assets.py", "--check"), directory),
        Check(
            "semantic-smoke",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "--basetemp=" + str(output / "pytest"),
                *("tests/" + name for name in tests),
            ),
            directory,
        ),
    ]
    if package == "core":
        checks.insert(
            0, Check("architecture", (python, "tools/check_architecture.py", "--check"), directory)
        )
    return tuple(checks)


def environment(repository: Path) -> dict[str, str]:
    """Check source deliberately, including the current matching core in benchmark checks."""
    result = dict(os.environ)
    result.pop("PYTHONHOME", None)
    result.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(
            str(source)
            for source in (repository / "src", repository / "packages/equiframe-benchmark/src")
        ),
    )
    return result


def identity(repository: Path, package: Package) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, capture_output=True, text=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repository, capture_output=True, text=True, check=True
    ).stdout.strip()
    directory = repository if package == "core" else repository / "packages/equiframe-benchmark"
    versions = {}
    for name in ("equiframe", "equiframe-benchmark", "ruff", "mypy", "pytest", "pyarrow"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "not_installed"
    return {
        "commit": commit,
        "worktree_status": status,
        "lock_sha256": hashlib.sha256((directory / "uv.lock").read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "versions": versions,
        "scope": "source smoke only; not an artifact-bound release or compatibility receipt",
    }


def run_checks(repository: Path, package: Package, output: Path) -> int:
    """Retain each attempted command and stop on failure; never erase an earlier run."""
    output.mkdir(parents=True, exist_ok=False)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "package": package,
        "identity": identity(repository, package),
        "complete": False,
        "results": [],
    }
    receipt_path = output / "receipt.json"

    def save() -> None:
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    save()
    for check in plan(repository, package, output):
        started = time.perf_counter()
        print(check.name + ": " + " ".join(check.command), flush=True)
        with (output / (check.name + ".log")).open("x", encoding="utf-8") as log:
            result = subprocess.run(
                check.command,
                cwd=check.directory,
                env=environment(repository),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        receipt["results"].append(
            {
                "name": check.name,
                "command": list(check.command),
                "exit_code": result.returncode,
                "wall_seconds": time.perf_counter() - started,
            }
        )
        save()
        print((output / (check.name + ".log")).read_text(encoding="utf-8"), end="", flush=True)
        if result.returncode:
            return result.returncode if result.returncode > 0 else 1
    receipt["complete"] = True
    save()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", choices=("core", "benchmark"), default="core")
    parser.add_argument("--output", type=Path, help="new retained receipt/log directory")
    parser.add_argument("--list", action="store_true", help="print commands without executing")
    args = parser.parse_args()
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode:
        parser.error("quick checks require the repository checkout, not an installed wheel/sdist")
    repository = Path(probe.stdout.strip()).resolve()
    if not (repository / "src/equiframe").is_dir():
        parser.error("quick checks require the root EquiFrame source layout")
    output = (args.output or repository / ".cache" / ("quick-" + uuid4().hex)).resolve()
    if args.list:
        for check in plan(repository, args.package, output):
            print(check.name + ": " + " ".join(check.command))
        return
    try:
        code = run_checks(repository, args.package, output)
    except FileExistsError:
        parser.error("output already exists; choose a new --output directory")
    print("Retained source-check receipt: " + str(output / "receipt.json"))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
