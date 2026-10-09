#!/usr/bin/env python3
"""Bounded offline A7 -> candidate -> A7 test; never publish or change a shared environment."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

from run_vm_lab import PROBE, Recorder, now, python_at, sha, verify_kit, write_runtime_constraints

OLD_HASHES = {
    "core": "abab950c4bdbaf38056f493ca4efc97148b0d85d8d34322d2725437c9f2b42c9",
    "benchmark": "e7d5546f4b177fee234ba50a17113cd1564c1645a6485b117c4f11783737237c",
    "consumer": "760db03975a15d327406a0baafb84da085bcc9ddc6fff924b04cb11b54635e02",
}


def files(directory: Path) -> dict:
    return {
        path.relative_to(directory).as_posix(): sha(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def install(record: Recorder, python: str, label: str, wheels: dict, wheelhouse: Path) -> None:
    fresh = label in {"baseline", "fresh-recovery"}
    reserve = 2 * 1024**3 if fresh else 1024**3 + 64 * 1024**2
    if shutil.disk_usage(record.directory).free < reserve:
        raise RuntimeError("Insufficient predeclared reserve for this local installation stage")
    command = [
        python,
        "-m",
        "pip",
        "--isolated",
        "install",
        "--no-cache-dir",
        "--no-index",
        "--only-binary=:all:",
        "--find-links",
        str(wheelhouse),
        "--report",
        str(record.directory / (label + "-install.json")),
    ]
    if not fresh:
        # In-place phases keep the already installed public closure unchanged.
        probe = (
            "import importlib.metadata as m,json; print(json.dumps({"
            "d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()}))"
        )
        installed = json.loads(
            record.run(label + "-dependency-pins", [python, "-I", "-c", probe]).stdout
        )
        pins = {
            key: version
            for key, version in installed.items()
            if key not in {"equiframe", "equiframe-benchmark", "equiframe-consumer-lab"}
        }
        constraints = record.directory / (label + "-public-dependencies.txt")
        write_runtime_constraints(constraints, pins)
        command += ["--constraint", str(constraints)]
    command += [
        str(wheels["core"]) + "[engines]",
        str(wheels["benchmark"]) + "[engines]",
        str(wheels["consumer"]),
    ]
    record.run(label + "-install", command, timeout=600)
    record.run(label + "-pip-check", [python, "-m", "pip", "check"])


def exercise(record: Recorder, python: str, label: str, wheels: dict) -> Path:
    output = record.directory / label
    output.mkdir()
    record.run(
        label + "-binding",
        [
            python,
            "-I",
            str(Path(__file__).with_name("installed_pair_probe.py")),
            "--core",
            str(wheels["core"]),
            "--benchmark",
            str(wheels["benchmark"]),
            "--consumer",
            str(wheels["consumer"]),
            "--output",
            str(output / "runtime-binding.json"),
        ],
    )
    for case, expected in [("good", 0), ("different", 1), ("not_evaluable", 3), ("error", 2)]:
        record.run(
            label + "-H-" + case,
            [
                python,
                "-I",
                "-O",
                "-m",
                "equiframe.examples.journeys.h_portable_ci",
                "--case",
                case,
                "--output",
                str(output / ("H-" + case)),
            ],
            expected=expected,
            timeout=120,
        )
    record.run(
        label + "-recovery",
        [
            python,
            "-I",
            "-O",
            "-m",
            "equiframe_consumer_lab",
            "fault-checks",
            "--output",
            str(output / "recovery"),
        ],
        timeout=120,
    )
    record.run(label + "-benchmark-cli", [python, "-I", "-m", "equiframe_benchmark", "--help"])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--python", required=True)
    parser.add_argument("--old-core", required=True, type=Path)
    parser.add_argument("--old-benchmark", required=True, type=Path)
    parser.add_argument("--old-consumer", required=True, type=Path)
    parser.add_argument(
        "--wheelhouse",
        required=True,
        type=Path,
        help="Reviewed local public dependency wheels; no registry requests",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    kit, wheelhouse, output = args.kit.resolve(), args.wheelhouse.resolve(), args.output.resolve()
    candidate = verify_kit(kit)
    old = {
        "core": args.old_core.resolve(),
        "benchmark": args.old_benchmark.resolve(),
        "consumer": args.old_consumer.resolve(),
    }
    for name, path in old.items():
        if path.is_symlink() or not path.is_file() or sha(path) != OLD_HASHES[name]:
            raise ValueError("baseline must match the exact identified historical artifact")
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise ValueError("reviewed local wheelhouse directory required")
    if output.exists():
        raise ValueError("choose a new output; preserve failures")
    output.mkdir(parents=True)
    new = {name: kit / candidate["artifacts"][name + "_wheel"] for name in old}
    receipt = {
        "schema": "equiframe-maturity-upgrade-1",
        "status": "running",
        "started_at": now(),
        "candidate_manifest_sha256": sha(kit / "candidate.json"),
        "source": candidate["source"],
        "baseline_artifact_hashes": OLD_HASHES,
        "candidate_artifact_hashes": candidate["artifact_hashes"],
        "commands": [],
        "errors": [],
        "created_environments": [],
        "removed_environments": [],
        "network_requests_permitted": False,
        "reserve_bytes": {"fresh_install": 2 * 1024**3, "in_place": 1024**3 + 64 * 1024**2},
        "global_environment_changed": False,
        "legacy_consumer_git_fields_authoritative": False,
        "baseline_identity_note": (
            "Outer wheel hashes identify the baseline; "
            "old consumer hard-coded Git fields are not reused as authority"
        ),
        "wheelhouse": {
            p.name: {"sha256": sha(p), "size_bytes": p.stat().st_size}
            for p in sorted(wheelhouse.glob("*.whl"))
        },
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "controller_python": sys.version,
        },
    }
    record = Recorder(output, receipt)
    try:
        info = json.loads(record.run("actual-python", [args.python, "-I", "-c", PROBE]).stdout)
        if ".".join(info["python"].split(".")[:2]) not in {"3.12", "3.13"}:
            raise ValueError("A7 must retain its real Python3.12/3.13 admission")
        receipt["interpreter"] = info
        environment = output / "upgrade-environment"
        record.run("create-upgrade-environment", [args.python, "-m", "venv", str(environment)])
        receipt["created_environments"].append(str(environment))
        python = python_at(environment)
        record.run("pip-version", [python, "-m", "pip", "--version"])
        install(record, python, "baseline", old, wheelhouse)
        baseline_evidence = exercise(record, python, "baseline", old)
        prior = files(baseline_evidence)
        install(record, python, "upgrade", new, wheelhouse)
        exercise(record, python, "upgrade", new)
        if files(baseline_evidence) != prior:
            raise ValueError("upgrade modified previous evidence")
        install(record, python, "rollback", old, wheelhouse)
        exercise(record, python, "rollback", old)
        if files(baseline_evidence) != prior:
            raise ValueError("rollback modified previous evidence")
        # Retire only this fully exercised, reconstructible new venv before a fresh recovery.
        shutil.rmtree(environment)
        receipt["removed_environments"].append(str(environment))
        recovery = output / "fresh-recovery-environment"
        record.run("create-fresh-recovery", [args.python, "-m", "venv", str(recovery)])
        receipt["created_environments"].append(str(recovery))
        rp = python_at(recovery)
        install(record, rp, "fresh-recovery", old, wheelhouse)
        exercise(record, rp, "fresh-recovery", old)
        shutil.rmtree(recovery)
        receipt["removed_environments"].append(str(recovery))
        receipt.update(
            status="passed",
            prior_evidence_unchanged=True,
            old_evidence_inventory=prior,
            public_release_authorized=False,
        )
    except Exception as error:
        receipt["status"] = "failed"
        receipt["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        receipt["finished_at"] = now()
        record.save()
    print(
        json.dumps(
            {"status": receipt["status"], "output": str(output), "public_release_authorized": False}
        )
    )
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
