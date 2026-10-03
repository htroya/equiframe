"""Execute candidate checks and retain command receipts without publication."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


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
    base = [args.uv, "run", "--locked", "--all-extras"]
    commands = [
        [args.uv, "sync", "--locked", "--all-extras", "--python", "3.12"],
        [*base, "ruff", "check", "."],
        [*base, "ruff", "format", "--check", "."],
        [*base, "mypy"],
        [*base, "python", "tools/generate_assets.py", "--check"],
        [*base, "pytest", "-q"],
        [*base, "python", "-m", "build", "--no-isolation"],
        [*base, "twine", "check", "--strict"],
        [*base, "python", "tools/verify_distribution.py", "--uv", args.uv],
    ]
    results = []
    for number, command in enumerate(commands):
        if "twine" in command:
            command += [str(path) for path in sorted((package / "dist").glob("*.whl"))]
            command += [str(path) for path in sorted((package / "dist").glob("*.tar.gz"))]
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
            }
        )
        output.write_text(
            json.dumps(
                {
                    "environment": {
                        "platform": platform.platform(),
                        "python_driver": platform.python_version(),
                        "uv": args.uv,
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


if __name__ == "__main__":
    main()
