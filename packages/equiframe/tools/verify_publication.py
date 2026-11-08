"""Check identified release artifacts without granting or performing publication.

The checked-in STEP9 policy is deliberately closed. JSON receipts identify bytes,
not human approval or trusted execution. There is no command-line bypass.
"""

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any

REQUIRED = frozenset(
    (
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
)
POLICY = Path(__file__).with_name("release-policy.json")
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON member")
        document[key] = value
    return document


def regular(path: Path, root: Path) -> None:
    """Reject links and special files, including links in parent directories."""
    if not path.is_relative_to(root):
        raise ValueError("candidate path leaves the selected directory")
    current = root
    if not stat.S_ISDIR(current.lstat().st_mode):
        raise ValueError("candidate root must be a real directory")
    for part in path.relative_to(root).parts[:-1]:
        current /= part
        if not stat.S_ISDIR(current.lstat().st_mode):
            raise ValueError("candidate parent must be a real directory")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("candidate files must be regular files, not links")


def read_json(path: Path, root: Path) -> dict[str, Any]:
    regular(path, root)
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("release JSON exceeds the size limit")
    result = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_bad_constant)
    if not isinstance(result, dict):
        raise ValueError("release JSON must be an object")
    return result


def _bad_constant(value: str) -> None:
    raise ValueError("nonfinite JSON number: " + value)


def file_identity(path: Path, root: Path) -> dict[str, Any]:
    regular(path, root)
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise ValueError("release artifact exceeds the size limit")
    digest = hashlib.sha256()
    actual_size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            actual_size += len(chunk)
            if actual_size > MAX_ARTIFACT_BYTES:
                raise ValueError("release artifact exceeds the size limit")
            digest.update(chunk)
    if actual_size != size:
        raise ValueError("release artifact changed while reading")
    return {"file": path.name, "size_bytes": size, "sha256": digest.hexdigest()}


def _stages(value: object) -> bool:
    return isinstance(value, list) and len(value) == len(REQUIRED) and set(value) == REQUIRED


def check_manifest(path: Path, root: Path, commit: str) -> dict[str, Any]:
    manifest = read_json(path, root)
    if manifest.get("schema_version") != "1.0":
        raise ValueError("unsupported release manifest version")
    name = manifest.get("distribution")
    if name not in {"equiframe", "equiframe-benchmark"}:
        raise ValueError("unexpected distribution")
    expected_name = "core-manifest.json" if name == "equiframe" else "benchmark-manifest.json"
    if path.name != expected_name:
        raise ValueError("distribution manifest filename mismatch")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[a-z0-9.]+)?", version
    ):
        raise ValueError("invalid bounded release version")
    if manifest.get("source_commit") != commit or manifest.get("published") is not False:
        raise ValueError("candidate does not identify the approved unpublished commit")
    source = manifest.get("source_validation", {})
    if source != {"git_head": commit, "package_clean": True, "project_tracked": True}:
        raise ValueError("candidate source is unverified")
    checks = manifest.get("check_completion", {})
    for field in (
        "required_stages",
        "successful_stages",
        "source_bound_stages",
        "local_dependency_runtime_bound_stages",
    ):
        if not _stages(checks.get(field)):
            raise ValueError("incomplete or unbound checks: " + field)
    for field in ("missing_stages", "unbound_stages", "local_dependency_runtime_unbound_stages"):
        if checks.get(field) != []:
            raise ValueError("incomplete or unbound checks: " + field)
    if type(checks.get("failed_commands")) is not int or checks["failed_commands"] != 0:
        raise ValueError("failed or malformed check count")
    artifacts = manifest.get("artifacts")
    stem = name.replace("-", "_") + "-" + version
    expected = {stem + "-py3-none-any.whl", stem + ".tar.gz"}
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ValueError("exact wheel and sdist inventory required")
    observed: list[dict[str, Any]] = []
    for item in artifacts:
        if not isinstance(item, dict) or item.get("file") not in expected:
            raise ValueError("unexpected artifact name")
        identity = file_identity(path.parent / item["file"], root)
        if item != identity:
            raise ValueError("artifact hash, size or metadata differs")
        observed.append(identity)
    if {item["file"] for item in observed} != expected:
        raise ValueError("repeated or missing artifact")
    blockers = manifest.get("publication_blockers")
    if not isinstance(blockers, list) or not all(
        isinstance(value, str) and value for value in blockers
    ):
        raise ValueError("publication blockers must be an explicit list")
    return {"distribution": name, "version": version, "artifacts": observed, "blockers": blockers}


def check_candidate(root: Path, commit: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("exact lowercase 40-character commit required")
    # abspath preserves a final symlink so regular() can reject it.
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("candidate root must be a real directory")
    manifests = sorted(root.rglob("*-manifest.json"))
    if len(manifests) != 2:
        raise ValueError("exactly two release manifests required")
    checked = [check_manifest(path, root, commit) for path in manifests]
    if {item["distribution"] for item in checked} != {"equiframe", "equiframe-benchmark"}:
        raise ValueError("both unique distributions are required")
    if len({item["version"] for item in checked}) != 1:
        raise ValueError("core and benchmark versions must match")
    core = next(item for item in checked if item["distribution"] == "equiframe")
    benchmark_path = next(path for path in manifests if path.name == "benchmark-manifest.json")
    benchmark = read_json(benchmark_path, root)
    dependencies = benchmark["check_completion"].get("dependency_artifacts")
    expected_core = [item for item in core["artifacts"] if item["file"].endswith(".whl")]
    if dependencies != expected_core:
        raise ValueError("benchmark checks must identify the exact core wheel")
    policy = read_json(POLICY, POLICY.parent)
    if policy.get("schema_version") != "1.0" or policy.get("publication_enabled") is not False:
        raise ValueError("this candidate does not support enabling publication")
    pending = policy.get("pending_decisions")
    if (
        not isinstance(pending, list)
        or not pending
        or not all(isinstance(value, str) and value for value in pending)
    ):
        raise ValueError("pending release decisions must remain explicit")
    return {
        "schema_version": "1.0",
        "source_commit": commit,
        "artifacts_verified": True,
        "publication_ready": False,
        "published": False,
        "policy": file_identity(POLICY, POLICY.parent),
        "pending_decisions": pending,
        "candidates": checked,
        "limitations": [
            "Receipts and hashes do not authenticate execution or human approval.",
            "Dependency and source-security reviews must be separately inspected.",
            "This tool performs no network requests, copies, upload or signing.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check_candidate(args.candidate_root, args.commit)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        raise SystemExit("Release candidate rejected: " + str(error)) from None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Artifact checks passed; public release remains blocked by recorded decisions.")
    raise SystemExit(3)


if __name__ == "__main__":
    main()
