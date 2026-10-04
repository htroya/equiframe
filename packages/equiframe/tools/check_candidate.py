"""Execute candidate checks and retain command receipts without publication."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from release_manifest import artifact_inventory, dependency_artifacts, source_snapshot


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
    base = [args.uv, "run", "--locked", "--all-extras"]
    commands = [
        [args.uv, "sync", "--locked", "--all-extras", "--python", "3.12"],
        [*base, "ruff", "check", "."],
        [*base, "ruff", "format", "--check", "."],
        [*base, "mypy"],
        [*base, "python", "tools/generate_assets.py", "--check"],
        [*base, "pytest", "-q", "--basetemp", str(output.parent / (output.stem + "-pytest-tmp"))],
        [*base, "python", "-m", "build", "--no-isolation"],
        [*base, "twine", "check", "--strict"],
        [*base, "python", "tools/verify_distribution.py", "--uv", args.uv],
    ]
    results = []
    for number, command in enumerate(commands):
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
                command, cwd=package, stdout=stream, stderr=subprocess.STDOUT, check=False
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
            }
        )
        output.write_text(
            json.dumps(
                {
                    "environment": {
                        "platform": platform.platform(),
                        "python_driver": platform.python_version(),
                        "uv": args.uv,
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
        if results[-1]["source_after"] != initial_source:
            raise SystemExit("source changed during candidate check; its result cannot validate it")
        if number in {7, 8} and results[-1]["artifacts"] != artifacts_before:
            raise SystemExit("artifacts changed during candidate check; restart with fixed bytes")
        if number == 8 and results[-1]["dependency_artifacts"] != dependencies_before:
            raise SystemExit("dependency wheels changed during installed candidate checks")


if __name__ == "__main__":
    main()
