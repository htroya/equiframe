#!/usr/bin/env python3
"""Assemble immutable private artifacts and public frozen inputs, excluding all credentials."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_vm_lab import sha, verify_kit, write


def git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(repository), *arguments], text=True).strip()


def copy(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError("expected a regular source member: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--consumer", type=Path, required=True)
    parser.add_argument("--consumer-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core-tests", type=int, required=True)
    parser.add_argument("--benchmark-tests", type=int, required=True)
    parser.add_argument("--consumer-tests", type=int, required=True)
    args = parser.parse_args()
    repository, consumer, data, output = (
        path.resolve() for path in (args.repository, args.consumer, args.consumer_data, args.output)
    )
    if output.exists():
        raise ValueError("choose a new output; retain previous candidate identity")
    if any(count <= 0 for count in (args.core_tests, args.benchmark_tests, args.consumer_tests)):
        raise ValueError("freeze actual required suite counts, never zero")
    for project in (repository, consumer):
        if git(project, "status", "--porcelain"):
            raise ValueError("commit reviewed source changes before assembling the kit")
    output.mkdir(parents=True, mode=0o700)
    source = {}
    for label, project in (("equiframe", repository), ("consumer", consumer)):
        source[label] = {
            "commit": git(project, "rev-parse", "HEAD"),
            "tree": git(project, "rev-parse", "HEAD^{tree}"),
            "branch": git(project, "branch", "--show-current"),
            "worktree_clean": True,
            "history": "local isolated review branch; no remote main merge",
        }
        bundle = output / "source" / (label + ".bundle")
        bundle.parent.mkdir(exist_ok=True)
        subprocess.run(
            ["git", "-C", str(project), "bundle", "create", str(bundle), "HEAD"], check=True
        )
        subprocess.run(["git", "-C", str(project), "bundle", "verify", str(bundle)], check=True)
    source["verified_remote_baseline"] = {
        "repository": "htroya/equiframe",
        "commit": "876033ce111fd38123799db4e4c40bd0202ec8df",
        "tree": "3a8ec2c938ccc716d33b4d0954ca00d56f83bebc",
        "note": "Recovered local baseline has the identical tree and different local history",
    }
    artifacts, hashes = {}, {}
    for label, package in (
        ("core", repository / "packages/equiframe"),
        ("benchmark", repository / "packages/equiframe-benchmark"),
        ("consumer", consumer),
    ):
        for suffix, pattern in (("_wheel", "*.whl"), ("_sdist", "*.tar.gz")):
            found = list((package / "dist").glob(pattern))
            if len(found) != 1:
                raise ValueError("exactly one current artifact of each kind is required")
            path = found[0]
            relative = "artifacts/" + path.name
            copy(path, output / relative)
            artifacts[label + suffix], hashes[label + suffix] = relative, sha(path)
    prepared = Path(__file__).resolve().parents[1]
    for path in sorted((prepared / "scripts").glob("*.py")):
        copy(path, output / "scripts" / path.name)
    for path in sorted((prepared / "locks").iterdir()):
        if path.is_file():
            copy(path, output / "locks" / path.name)
    for name in ("README_VM_ES.md", "OPERATOR_RECEIPT_TEMPLATE.json"):
        copy(prepared / name, output / name)
    # The data inventory is a frozen explicit list, never a recursive copy of private input.
    frozen = json.loads((data / "manifest.json").read_text("utf-8"))
    for item in frozen["files"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid frozen data member")
        path = data / relative
        if sha(path) != item["sha256"] or path.stat().st_size != item["size_bytes"]:
            raise ValueError("frozen public dataset changed: " + str(relative))
        copy(path, output / "consumer-data" / relative)
    copy(data / "manifest.json", output / "consumer-data/manifest.json")
    files = {
        path.relative_to(output).as_posix(): {
            "sha256": sha(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "schema": "equiframe-maturity-candidate-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "artifacts": artifacts,
        "artifact_hashes": hashes,
        "files": files,
        "suite_minimums": {
            "core": args.core_tests,
            "benchmark": args.benchmark_tests,
            "consumer": args.consumer_tests,
        },
        "scope": "Private candidate for reproducible testing and review, never a public release",
        "vm_execution_status": "PENDING_REAL_RECEIPTS_AND_REVIEW",
        "criteria_automatically_closed": [],
        "private_credentials_included": False,
    }
    write(output / "candidate.json", manifest)
    verify_kit(output)
    print(
        json.dumps(
            {
                "output": str(output),
                "candidate_manifest_sha256": sha(output / "candidate.json"),
                "source": source,
                "artifact_hashes": hashes,
                "files": len(files),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
