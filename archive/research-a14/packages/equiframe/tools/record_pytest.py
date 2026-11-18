"""Run installed-distribution tests and preserve every node outcome, including setup errors.

This harness records observations only. It does not infer independent expectations
from a passing test, classify rejected application data as accepted, or alter tests.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import sysconfig
import time
from pathlib import Path
from typing import Any

import pytest


class Recorder:
    def __init__(self) -> None:
        self.collected: list[str] = []
        self.reports: list[dict[str, Any]] = []
        self.collection_errors: list[str] = []

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        self.collected = [item.nodeid for item in items]

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.collection_errors.append(str(report.longrepr))

    def pytest_runtest_logreport(self, report: Any) -> None:
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "phase": report.when,
                "outcome": report.outcome,
                "duration_seconds": report.duration,
                "wasxfail": getattr(report, "wasxfail", None),
                "diagnostic": str(report.longrepr) if report.failed or report.skipped else None,
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    import equiframe

    path = Path(equiframe.__file__).resolve()
    purelib = Path(sysconfig.get_paths()["purelib"]).resolve()
    if not path.is_relative_to(purelib):
        raise ValueError("Installed test run refuses EquiFrame imported outside site-packages")
    if arguments.output.exists():
        raise FileExistsError(arguments.output)
    recorder = Recorder()
    argv = arguments.pytest_args
    if argv[:1] == ["--"]:
        argv = argv[1:]
    started = time.time()
    code = int(pytest.main(argv, plugins=[recorder]))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for report in recorder.reports:
        grouped.setdefault(report["nodeid"], []).append(report)
    cases = []
    for nodeid in recorder.collected:
        observations = grouped.get(nodeid, [])
        status = (
            "FAIL"
            if any(r["outcome"] == "failed" for r in observations)
            else "NOT_RUN"
            if any(r["outcome"] == "skipped" or r["wasxfail"] for r in observations)
            else "PASS"
            if {r["phase"] for r in observations if r["outcome"] == "passed"}
            == {"setup", "call", "teardown"}
            else "NOT_RUN"
        )
        cases.append(
            {
                "id": "pytest:" + nodeid,
                "nodeid": nodeid,
                "status": status,
                "observations": observations,
            }
        )
    document = {
        "schema_version": "equiframe.pytest-observations/1.0",
        "commit": arguments.commit,
        "wheel": {
            "name": arguments.wheel.name,
            "sha256": hashlib.sha256(arguments.wheel.read_bytes()).hexdigest(),
        },
        "environment": {
            "executable": sys.executable,
            "python": sys.version,
            "platform": platform.platform(),
            "equiframe_file": str(path),
            "equiframe_version": importlib.metadata.version("equiframe"),
            "dependencies": dict(
                sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
            ),
        },
        "argv": argv,
        "started_unix_seconds": started,
        "finished_unix_seconds": time.time(),
        "pytest_exit_code": code,
        "collection_errors": recorder.collection_errors,
        "cases": cases,
        "scope": "Executed test outcomes, not an assertion of per-option semantic coverage",
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
