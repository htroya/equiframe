"""Run a selected acceptance command and require an explicit approval for CI."""

import argparse
import json
import subprocess
import sys

COMMANDS = {"verify": ("verify", "accept"), "sercop": ("sercop", "accept-execution")}


def approved(exit_code: int, report: str) -> bool:
    if exit_code != 0:
        return False
    try:
        result = json.loads(report)
    except ValueError:
        return False
    return isinstance(result, dict) and result.get("publishable") is True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", choices=tuple(COMMANDS))
    parser.add_argument("acceptance_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    result = subprocess.run(
        [sys.executable, "-I", "-m", "equiframe", *COMMANDS[args.workflow], *args.acceptance_args],
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if not approved(result.returncode, result.stdout):
        raise SystemExit(result.returncode or 3)


if __name__ == "__main__":
    main()
