#!/usr/bin/env python3
"""Assemble immutable private artifacts and public frozen inputs, excluding all credentials."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from frozen_tests import (
    PACKAGES,
    candidate_manifests,
    read_manifest,
    verify_sdist_tests,
)
from manifest_scope import (
    CANDIDATE_V1,
    CANDIDATE_V2,
    LEGACY_PYTHONS,
    UNIVERSALITY_PYTHONS,
)
from normalize_consumer_wheel import POLICY as CONSUMER_REBUILD_POLICY
from run_vm_lab import sha, verify_kit, write


def git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repository), *arguments], text=True
    ).strip()


def copy(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError("expected a regular source member: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def candidate_scope(scope: str) -> dict:
    """Keep the full matrix as default; name the original M13-only expedition."""
    if scope == "universality":
        return {
            "schema": CANDIDATE_V2,
            "required_python_versions": list(UNIVERSALITY_PYTHONS),
            "scope_basis": "Universality handoff: all four Python minors remain required",
            "criteria_automatically_closed": [],
        }
    if scope == "original-m13-arm":
        return {
            "schema": CANDIDATE_V1,
            "required_python_versions": list(LEGACY_PYTHONS),
            "scope_basis": "Original MATURITY_MATRIX M13: standalone ARM64 CPython3.10/3.12 laboratory",
            "scope_id": "M13-ARM-ORIGINAL-v1",
            "required_runtime_identity": True,
            "universality_matrix_reduced": False,
            "other_platforms_and_python_minors_closed": False,
            "criteria_automatically_closed": [],
        }
    raise ValueError("unsupported candidate scope")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--consumer", type=Path, required=True)
    parser.add_argument("--consumer-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scope",
        choices=("universality", "original-m13-arm"),
        default="universality",
        help="Default preserves four minors. Original M13 is a separate two-minor ARM expedition, not universality closure.",
    )
    parser.add_argument("--core-tests", type=int, required=True)
    parser.add_argument("--benchmark-tests", type=int, required=True)
    parser.add_argument("--consumer-tests", type=int, required=True)
    parser.add_argument(
        "--consumer-wheel-rebuild-policy",
        choices=(CONSUMER_REBUILD_POLICY,),
        help="Explicit ZIP creator-format policy; preserves all artifact bytes and raw builds.",
    )
    for label in PACKAGES:
        parser.add_argument("--" + label + "-test-manifest", type=Path, required=True)
    parser.add_argument(
        "--verified-base",
        required=True,
        help="Observed remote main commit; must be an ancestor",
    )
    parser.add_argument(
        "--tooling-repository",
        type=Path,
        help="Separate committed tooling checkout, when applicable",
    )
    args = parser.parse_args()
    repository, consumer, data, output = (
        path.resolve()
        for path in (args.repository, args.consumer, args.consumer_data, args.output)
    )
    if output.exists():
        raise ValueError("choose a new output; retain previous candidate identity")
    if any(
        count <= 0
        for count in (args.core_tests, args.benchmark_tests, args.consumer_tests)
    ):
        raise ValueError("freeze actual required suite counts, never zero")
    for project in (repository, consumer, data):
        if git(project, "status", "--porcelain"):
            raise ValueError("commit reviewed source changes before assembling the kit")
    base = git(repository, "rev-parse", args.verified_base + "^{commit}")
    subprocess.run(
        ["git", "-C", str(repository), "merge-base", "--is-ancestor", base, "HEAD"],
        check=True,
    )
    tooling = (args.tooling_repository or repository).resolve()
    if git(tooling, "status", "--porcelain"):
        raise ValueError("commit tooling changes before assembling")
    output.mkdir(parents=True, mode=0o700)
    source = {}
    for label, project in (("equiframe", repository), ("consumer", consumer)):
        source[label] = {
            "commit": git(project, "rev-parse", "HEAD"),
            "tree": git(project, "rev-parse", "HEAD^{tree}"),
            "branch": git(project, "branch", "--show-current"),
            "worktree_clean": True,
            "history": "observed committed source; integration status is recorded separately",
        }
        bundle = output / "source" / (label + ".bundle")
        bundle.parent.mkdir(exist_ok=True)
        subprocess.run(
            ["git", "-C", str(project), "bundle", "create", str(bundle), "HEAD"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(project), "bundle", "verify", str(bundle)], check=True
        )
    source["consumer_data"] = {
        "commit": git(data, "rev-parse", "HEAD"),
        "tree": git(data, "rev-parse", "HEAD^{tree}"),
        "branch": git(data, "branch", "--show-current"),
        "worktree_clean": True,
        "history": "observed committed frozen-data source; no remote publication implied",
    }
    source["verified_remote_baseline"] = {
        "repository": "htroya/equiframe",
        "commit": base,
        "tree": git(repository, "rev-parse", base + "^{tree}"),
        "note": (
            "Caller-observed remote main; source is a verified descendant, "
            "not a claim of final integration"
        ),
    }
    tooling_source = {
        "commit": git(tooling, "rev-parse", "HEAD"),
        "tree": git(tooling, "rev-parse", "HEAD^{tree}"),
        "worktree_clean": True,
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
                raise ValueError(
                    "exactly one current artifact of each kind is required"
                )
            path = found[0]
            relative = "artifacts/" + path.name
            copy(path, output / relative)
            artifacts[label + suffix], hashes[label + suffix] = relative, sha(path)
    test_manifests = {}
    for label in PACKAGES:
        path = getattr(args, label + "_test_manifest").resolve()
        frozen_tests = read_manifest(path, label, getattr(args, label + "_tests"))
        verify_sdist_tests(output / artifacts[label + "_sdist"], frozen_tests)
        relative = "test-manifests/" + label + ".json"
        copy(path, output / relative)
        test_manifests[label] = {
            "path": relative,
            "sha256": sha(path),
            "size_bytes": path.stat().st_size,
        }
    prepared = tooling / "tools/maturity_lab"
    for path in sorted((prepared / "scripts").glob("*.py")):
        copy(path, output / "scripts" / path.name)
    for path in sorted((prepared / "locks").iterdir()):
        if path.is_file():
            copy(path, output / "locks" / path.name)
    for name in (
        "README_VM_ES.md",
        "OPERATOR_RECEIPT_TEMPLATE.json",
        "run_from_windows.ps1",
    ):
        copy(prepared / name, output / name)
    # The data inventory is a frozen explicit list, never a recursive copy of private input.
    frozen = json.loads((data / "manifest.json").read_text("utf-8"))
    tracked_data = set(git(data, "ls-files").splitlines())
    required_data = {"manifest.json", *(item["path"] for item in frozen["files"])}
    if not required_data <= tracked_data:
        raise ValueError("frozen data members must belong to the committed data source")
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
        **candidate_scope(args.scope),
        "tooling_source": tooling_source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "artifacts": artifacts,
        "artifact_hashes": hashes,
        "test_manifests": test_manifests,
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
    candidate_manifests(output, manifest, required=True)
    if args.consumer_wheel_rebuild_policy:
        manifest["consumer_wheel_rebuild_policy"] = args.consumer_wheel_rebuild_policy
    write(output / "candidate.json", manifest)
    (output / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {name}\n" for name, item in sorted(files.items()))
        + f"{sha(output / 'candidate.json')}  candidate.json\n",
        encoding="utf-8",
        newline="\n",
    )
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
