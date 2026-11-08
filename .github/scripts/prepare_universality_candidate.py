#!/usr/bin/env python3
"""Freeze one workflow candidate from exact source and frozen-data commits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - workflow assembler uses Python 3.12
    import tomli as tomllib

SHA256 = re.compile(r"[0-9a-f]{64}")
GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
REPOSITORY_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def portable_path(value: str, *, directory: bool = False) -> PurePosixPath:
    raw = value[:-1] if directory and value.endswith("/") else value
    if not raw or raw.startswith("/") or "\\" in raw or "\0" in raw:
        raise ValueError(f"nonportable archive path: {value}")
    parts = raw.split("/")
    for part in parts:
        normalized = unicodedata.normalize("NFC", part)
        stem = normalized.split(".", 1)[0].casefold()
        if (
            not part
            or part in (".", "..")
            or part.startswith(".")
            or normalized != part
            or part.endswith((".", " "))
            or ":" in part
            or any(ord(character) < 32 for character in part)
            or stem in WINDOWS_RESERVED
        ):
            raise ValueError(f"nonportable archive path component: {value}")
    return PurePosixPath(*parts)


def unique_portable_paths(values: list[tuple[str, bool]], label: str) -> None:
    seen: set[str] = set()
    for value, directory in values:
        path = portable_path(value, directory=directory)
        key = "/".join(part.casefold() for part in path.parts)
        if key in seen:
            raise ValueError(f"{label} has a normalized/case-fold path collision: {value}")
        seen.add(key)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, object]:
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError(f"candidate member is not a regular file: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repository), *arguments], text=True, encoding="utf-8"
    ).strip()


def require_tracked_file(repository: Path, path: Path, label: str) -> None:
    resolved_repository = repository.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(resolved_repository):
        raise ValueError(f"{label} is outside its Git checkout")
    relative = resolved_path.relative_to(resolved_repository).as_posix()
    try:
        observed = subprocess.check_output(
            [
                "git",
                "-C",
                str(resolved_repository),
                "ls-files",
                "-z",
                "--error-unmatch",
                "--",
                relative,
            ]
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(f"{label} is not tracked by the declared commit: {relative}") from error
    if observed != relative.encode("utf-8") + b"\0":
        raise ValueError(f"{label} has an ambiguous Git path: {relative}")


def checked_commit(
    repository: Path, expected: str, repository_name: str, label: str
) -> dict[str, str]:
    if GIT_COMMIT.fullmatch(expected) is None:
        raise ValueError(f"{label} must be an immutable 40-character lowercase commit SHA")
    if REPOSITORY_NAME.fullmatch(repository_name) is None:
        raise ValueError(f"{label} repository must use the owner/name form")
    actual = git(repository, "rev-parse", "HEAD")
    if actual != expected:
        raise ValueError(f"{label} checkout differs: expected {expected}, observed {actual}")
    if git(repository, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError(f"{label} worktree is not an exact clean checkout")
    return {
        "repository": repository_name,
        "commit": actual,
        "tree": git(repository, "rev-parse", "HEAD^{tree}"),
    }


def one_artifact(directory: Path, pattern: str, label: str) -> Path:
    matches = [path for path in directory.glob(pattern) if path.is_file() and not path.is_symlink()]
    if len(matches) != 1:
        raise ValueError(f"{label} requires exactly one {pattern} artifact; found {len(matches)}")
    return matches[0]


def wheel_identity(path: Path) -> tuple[str, str]:
    file_record(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f"wheel contains duplicate members: {path.name}")
        unique_portable_paths(
            [(info.filename, info.is_dir()) for info in archive.infolist()], "wheel"
        )
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"wheel must contain one METADATA member: {path.name}")
        for info in archive.infolist():
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"wheel contains a symbolic link: {info.filename}")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
    name, version = str(metadata.get("Name", "")), str(metadata.get("Version", ""))
    if not name or not version:
        raise ValueError(f"wheel lacks name/version metadata: {path.name}")
    return name, version


def sdist_identity(path: Path) -> tuple[str, str]:
    file_record(path)
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if not members or len({member.name for member in members}) != len(members):
            raise ValueError(f"sdist is empty or contains duplicate members: {path.name}")
        unique_portable_paths([(member.name, member.isdir()) for member in members], "sdist")
        roots: set[str] = set()
        pkg_info = []
        for member in members:
            member_path = portable_path(member.name, directory=member.isdir())
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"sdist contains a link or special member: {member.name}")
            if member_path.parts:
                roots.add(member_path.parts[0])
            if member.isfile() and len(member_path.parts) == 2 and member_path.name == "PKG-INFO":
                pkg_info.append(member)
        if len(roots) != 1 or len(pkg_info) != 1:
            raise ValueError(f"sdist must have one root and one root PKG-INFO: {path.name}")
        stream = archive.extractfile(pkg_info[0])
        if stream is None:
            raise ValueError(f"cannot read sdist PKG-INFO: {path.name}")
        metadata = BytesParser().parsebytes(stream.read())
    distribution_name = str(metadata.get("Name", ""))
    version = str(metadata.get("Version", ""))
    if not distribution_name or not version:
        raise ValueError(f"sdist lacks name/version metadata: {path.name}")
    return distribution_name, version


def compare_runtime_payloads(
    wheel: Path,
    sdist: Path,
    module: str,
    allowed_wheel_prefixes: tuple[str, ...] = (),
    expected_source_files: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    wheel_prefix = module + "/"
    with zipfile.ZipFile(wheel) as archive:
        wheel_files = {
            name: {
                "sha256": hashlib.sha256(archive.read(name)).hexdigest(),
                "size_bytes": len(archive.read(name)),
            }
            for name in archive.namelist()
            if name.startswith(wheel_prefix) and not name.endswith("/")
        }
    with tarfile.open(sdist, "r:gz") as archive:
        roots = {PurePosixPath(member.name).parts[0] for member in archive.getmembers()}
        if len(roots) != 1:
            raise ValueError(f"sdist must have one root: {sdist.name}")
        source_prefix = next(iter(roots)) + "/src/" + module + "/"
        source_files = {}
        for member in archive.getmembers():
            if not member.isfile() or not member.name.startswith(source_prefix):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot read runtime sdist member: {member.name}")
            raw = stream.read()
            destination = module + "/" + member.name.removeprefix(source_prefix)
            source_files[destination] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
    if not source_files or any(
        wheel_files.get(name) != item for name, item in source_files.items()
    ):
        raise ValueError(f"{module} wheel payload differs from its sdist source payload")
    if expected_source_files is not None and wheel_files != expected_source_files:
        raise ValueError(f"{module} wheel runtime payload differs from its clean Git source")
    unexplained = set(wheel_files).difference(source_files)
    if any(not name.startswith(allowed_wheel_prefixes) for name in unexplained):
        raise ValueError(f"{module} wheel contains runtime files absent from its sdist source")
    encoded = json.dumps(source_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "source_file_count": len(source_files),
        "source_payload_sha256": hashlib.sha256(encoded).hexdigest(),
        "additional_declared_wheel_files": len(unexplained),
    }


def source_runtime_inventory(
    source: Path, module: str, allowed_wheel_prefixes: tuple[str, ...]
) -> dict[str, dict[str, object]]:
    package = source / "src" / module
    if package.is_symlink() or not package.is_dir():
        raise ValueError(f"runtime package source is absent or linked: {module}")
    result: dict[str, dict[str, object]] = {}

    def add_file(path: Path, destination: str) -> None:
        portable = portable_path(destination).as_posix()
        if path.is_symlink() or not path.is_file() or portable in result:
            raise ValueError(
                f"runtime source member is linked, absent or duplicated: {destination}"
            )
        result[portable] = file_record(path)

    for path in sorted(package.rglob("*")):
        if path.is_file() or path.is_symlink():
            add_file(path, module + "/" + path.relative_to(package).as_posix())
    configuration = tomllib.loads((source / "pyproject.toml").read_text("utf-8"))
    force_include = (
        configuration.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    if not isinstance(force_include, dict):
        raise TypeError("wheel force-include mapping must be an object")
    for original, destination in force_include.items():
        if not isinstance(original, str) or not isinstance(destination, str):
            raise TypeError("wheel force-include paths must be strings")
        if not destination.startswith(allowed_wheel_prefixes):
            raise ValueError(f"undeclared wheel force-include target: {destination}")
        origin = source / safe_relative(original, "wheel force-include source")
        if origin.is_dir() and not origin.is_symlink():
            for path in sorted(origin.rglob("*")):
                if path.is_file() or path.is_symlink():
                    relative = path.relative_to(origin).as_posix()
                    add_file(path, destination.rstrip("/") + "/" + relative)
        else:
            add_file(origin, destination)
    if not result:
        raise ValueError(f"runtime source inventory is empty: {module}")
    unique_portable_paths([(name, False) for name in result], "runtime source")
    return result


def copy_artifacts(
    label: str,
    directory: Path,
    output: Path,
    module: str,
    source: Path,
    allowed_wheel_prefixes: tuple[str, ...] = (),
) -> dict[str, object]:
    wheel = one_artifact(directory, "*.whl", label)
    sdist = one_artifact(directory, "*.tar.gz", label)
    wheel_name, wheel_version = wheel_identity(wheel)
    sdist_name, sdist_version = sdist_identity(sdist)
    if (wheel_name.lower().replace("_", "-"), wheel_version) != (
        sdist_name.lower().replace("_", "-"),
        sdist_version,
    ):
        raise ValueError(f"{label} wheel and sdist metadata identities differ")
    payload = compare_runtime_payloads(
        wheel,
        sdist,
        module,
        allowed_wheel_prefixes,
        source_runtime_inventory(source, module, allowed_wheel_prefixes),
    )
    target = output / "artifacts"
    target.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {
        "name": wheel_name,
        "version": wheel_version,
        "runtime_payload": payload,
    }
    for kind, artifact_path in (("wheel", wheel), ("sdist", sdist)):
        destination = target / artifact_path.name
        shutil.copyfile(artifact_path, destination)
        result[kind] = destination.relative_to(output).as_posix()
        result[kind + "_record"] = file_record(destination)
    return result


def source_test_inventory(source: Path) -> dict[str, dict[str, object]]:
    tests = source / "tests"
    if tests.is_symlink() or not tests.is_dir():
        raise ValueError(f"test source directory is absent or linked: {source}")
    result: dict[str, dict[str, object]] = {}
    seen: set[str] = set()
    for path in sorted(tests.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"test source contains a symbolic link: {path}")
        if not path.is_file() or "__pycache__" in path.relative_to(source).parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(source).as_posix()
        portable = portable_path(relative).as_posix()
        key = portable.casefold()
        if key in seen:
            raise ValueError(f"test source has a portable-path collision: {relative}")
        seen.add(key)
        result[portable] = file_record(path)
    if not result:
        raise ValueError(f"test source inventory is empty: {source}")
    return result


def sdist_test_inventory(sdist: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    total = 0
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        roots = {PurePosixPath(member.name).parts[0] for member in members if member.name}
        if len(roots) != 1:
            raise ValueError(f"sdist must contain one source root: {sdist.name}")
        root = next(iter(roots))
        prefix = root + "/tests/"
        for member in members:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            relative = "tests/" + member.name.removeprefix(prefix)
            pure = PurePosixPath(relative)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in member.name
                or "__pycache__" in pure.parts
                or pure.suffix in {".pyc", ".pyo"}
            ):
                raise ValueError(f"sdist has a nonportable test member: {member.name}")
            if relative in result:
                raise ValueError(f"sdist repeats a test member: {relative}")
            total += member.size
            if len(result) >= 10_000 or total > 128 * 1024**2:
                raise ValueError("sdist test inventory exceeds its fixed bounds")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot read sdist test member: {member.name}")
            digest = hashlib.sha256()
            observed_size = 0
            while block := stream.read(1024 * 1024):
                digest.update(block)
                observed_size += len(block)
            if observed_size != member.size:
                raise ValueError(f"sdist test member size changed while reading: {member.name}")
            result[relative] = {
                "sha256": digest.hexdigest(),
                "size_bytes": observed_size,
            }
    if not result:
        raise ValueError(f"sdist test inventory is empty: {sdist.name}")
    return result


def copy_test_manifest(
    path: Path,
    *,
    package: str,
    source: Path,
    sdist: Path,
    output: Path,
) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024**2:
        raise ValueError(f"test manifest is absent, linked or oversized: {package}")
    loaded: object = json.loads(path.read_text("utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"test manifest must be an object: {package}")
    files = loaded.get("files")
    tests = loaded.get("tests")
    if (
        loaded.get("schema") != "equiframe-test-manifest-1"
        or loaded.get("package") != package
        or not isinstance(loaded.get("pytest_version"), str)
        or not isinstance(loaded.get("hypothesis_version"), str)
        or loaded.get("plugin_autoload_disabled") is not True
        or not isinstance(files, dict)
        or not isinstance(tests, list)
        or loaded.get("test_count") != len(tests)
        or not tests
    ):
        raise ValueError(f"test manifest header differs: {package}")
    if files != source_test_inventory(source) or files != sdist_test_inventory(sdist):
        raise ValueError(f"test manifest files differ from source/sdist: {package}")
    identities: list[tuple[str, str]] = []
    nodeids: list[str] = []
    for item in tests:
        if not isinstance(item, dict) or set(item) != {"nodeid", "classname", "name"}:
            raise ValueError(f"test manifest identity is malformed: {package}")
        if not all(isinstance(item[name], str) and item[name] for name in item):
            raise ValueError(f"test manifest identity is empty: {package}")
        identities.append((item["classname"], item["name"]))
        nodeids.append(item["nodeid"])
    if len(set(identities)) != len(identities) or len(set(nodeids)) != len(nodeids):
        raise ValueError(f"test manifest identities are duplicated: {package}")
    destination = output / "test-manifests" / (package + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
    encoded_identities = json.dumps(sorted(identities), separators=(",", ":")).encode("utf-8")
    return {
        "path": destination.relative_to(output).as_posix(),
        "record": file_record(destination),
        "test_count": len(tests),
        "junit_identities_sha256": hashlib.sha256(encoded_identities).hexdigest(),
        "pytest_version": loaded["pytest_version"],
        "hypothesis_version": loaded["hypothesis_version"],
    }


def safe_relative(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid {label} path")
    if value == "." and label == "data root":
        return Path(".")
    try:
        pure = portable_path(value)
    except ValueError as error:
        raise ValueError(f"unsafe {label} path: {value}") from error
    return Path(*pure.parts)


def unlinked_path(root: Path, relative: Path, label: str) -> Path:
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} contains a symbolic-link component")
    return current


def copy_frozen_data(repository: Path, relative: str, output: Path) -> dict[str, object]:
    repository = repository.resolve()
    root = unlinked_path(
        repository, safe_relative(relative or ".", "data root"), "data root"
    ).resolve()
    if not root.is_relative_to(repository) or not root.is_dir():
        raise ValueError("frozen data root is absent, linked or outside its checkout")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("frozen data manifest.json is absent or linked")
    require_tracked_file(repository, manifest_path, "frozen data manifest")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    files = manifest.get("files")
    if manifest.get("status") != "FROZEN" or not isinstance(files, list) or not files:
        raise ValueError("consumer data manifest must be nonempty and FROZEN")
    destination = output / "consumer-data"
    destination.mkdir()
    seen: set[str] = set()
    copied = []
    for item in files:
        if not isinstance(item, dict):
            raise TypeError("frozen data file record must be an object")
        relative_path = safe_relative(item.get("path"), "frozen data member")
        portable = PurePosixPath(*relative_path.parts).as_posix()
        portable_key = portable.casefold()
        if portable_key in seen or portable_key == "manifest.json":
            raise ValueError(f"duplicate/reserved frozen data path: {portable}")
        seen.add(portable_key)
        source = unlinked_path(root, relative_path, "frozen data member").resolve()
        if (
            not source.is_relative_to(root)
            or not source.is_file()
            or SHA256.fullmatch(str(item.get("sha256", ""))) is None
            or type(item.get("size_bytes")) is not int
            or item["size_bytes"] < 0
        ):
            raise ValueError(f"invalid frozen data member: {portable}")
        observed = file_record(source)
        require_tracked_file(repository, source, "frozen data member")
        if observed != {"sha256": item["sha256"], "size_bytes": item["size_bytes"]}:
            raise ValueError(f"frozen data bytes differ from manifest: {portable}")
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append({"path": portable, **observed})
    shutil.copyfile(manifest_path, destination / "manifest.json")
    return {
        "manifest": "consumer-data/manifest.json",
        "manifest_record": file_record(destination / "manifest.json"),
        "members": copied,
    }


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--repository-name", required=True)
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--consumer-repository", type=Path, required=True)
    parser.add_argument("--consumer-repository-name", required=True)
    parser.add_argument("--consumer-commit", required=True)
    parser.add_argument("--data-repository", type=Path, required=True)
    parser.add_argument("--data-repository-name", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--data-path", default=".")
    parser.add_argument("--core-dist", type=Path, required=True)
    parser.add_argument("--benchmark-dist", type=Path, required=True)
    parser.add_argument("--consumer-dist", type=Path, required=True)
    parser.add_argument("--core-source", type=Path, required=True)
    parser.add_argument("--benchmark-source", type=Path, required=True)
    parser.add_argument("--consumer-source", type=Path, required=True)
    parser.add_argument("--core-test-manifest", type=Path, required=True)
    parser.add_argument("--benchmark-test-manifest", type=Path, required=True)
    parser.add_argument("--consumer-test-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-run-attempt", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--github-workflow-ref", required=True)
    parser.add_argument("--github-workflow-sha", required=True)
    args = parser.parse_args()

    workflow_execution = {
        "provider": "github-actions",
        "run_id": args.github_run_id,
        "run_attempt": args.github_run_attempt,
        "repository": args.github_repository,
        "workflow_ref": args.github_workflow_ref,
        "workflow_sha": args.github_workflow_sha,
    }
    if (
        not args.github_run_id.isdigit()
        or not args.github_run_attempt.isdigit()
        or int(args.github_run_id) <= 0
        or int(args.github_run_attempt) <= 0
        or REPOSITORY_NAME.fullmatch(args.github_repository) is None
        or GIT_COMMIT.fullmatch(args.github_workflow_sha) is None
        or not args.github_workflow_ref
    ):
        raise ValueError("GitHub Actions candidate execution identity is malformed")
    expected_environment = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ID": args.github_run_id,
        "GITHUB_RUN_ATTEMPT": args.github_run_attempt,
        "GITHUB_REPOSITORY": args.github_repository,
        "GITHUB_WORKFLOW_REF": args.github_workflow_ref,
        "GITHUB_WORKFLOW_SHA": args.github_workflow_sha,
    }
    if any(os.environ.get(name) != value for name, value in expected_environment.items()):
        raise ValueError("GitHub Actions environment differs from the candidate declaration")

    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        parser.error("output must be a new path")
    repository = args.repository.resolve()
    consumer = args.consumer_repository.resolve()
    data = args.data_repository.resolve()
    sources = {
        "equiframe": checked_commit(
            repository, args.repository_commit, args.repository_name, "equiframe commit"
        ),
        "consumer": checked_commit(
            consumer,
            args.consumer_commit,
            args.consumer_repository_name,
            "consumer commit",
        ),
        "consumer_data": checked_commit(
            data, args.data_commit, args.data_repository_name, "consumer data commit"
        ),
    }
    if (
        workflow_execution["repository"] != sources["equiframe"]["repository"]
        or workflow_execution["workflow_sha"] != sources["equiframe"]["commit"]
    ):
        raise ValueError("workflow execution differs from the candidate source identity")
    core_source = args.core_source.resolve()
    benchmark_source = args.benchmark_source.resolve()
    consumer_source = args.consumer_source.resolve()
    if (
        not core_source.is_relative_to(repository)
        or not benchmark_source.is_relative_to(repository)
        or not consumer_source.is_relative_to(consumer)
    ):
        raise ValueError("declared package sources differ from their checked-out repositories")
    output.mkdir(parents=True)
    artifacts = {
        "core": copy_artifacts(
            "core",
            args.core_dist.resolve(),
            output,
            "equiframe",
            core_source,
            ("equiframe/docs/", "equiframe/examples/"),
        ),
        "benchmark": copy_artifacts(
            "benchmark",
            args.benchmark_dist.resolve(),
            output,
            "equiframe_benchmark",
            benchmark_source,
        ),
        "consumer": copy_artifacts(
            "consumer",
            args.consumer_dist.resolve(),
            output,
            "equiframe_consumer_lab",
            consumer_source,
        ),
    }
    if str(artifacts["core"]["name"]).lower().replace("_", "-") != "equiframe":
        raise ValueError("core artifact has the wrong distribution name")
    if str(artifacts["benchmark"]["name"]).lower().replace("_", "-") != "equiframe-benchmark":
        raise ValueError("benchmark artifact has the wrong distribution name")
    if str(artifacts["consumer"]["name"]).lower().replace("_", "-") != "equiframe-consumer-lab":
        raise ValueError("consumer artifact has the wrong distribution name")
    test_manifests = {
        "core": copy_test_manifest(
            args.core_test_manifest.resolve(),
            package="equiframe",
            source=core_source,
            sdist=output / str(artifacts["core"]["sdist"]),
            output=output,
        ),
        "benchmark": copy_test_manifest(
            args.benchmark_test_manifest.resolve(),
            package="equiframe-benchmark",
            source=benchmark_source,
            sdist=output / str(artifacts["benchmark"]["sdist"]),
            output=output,
        ),
        "consumer": copy_test_manifest(
            args.consumer_test_manifest.resolve(),
            package="equiframe-consumer-lab",
            source=consumer_source,
            sdist=output / str(artifacts["consumer"]["sdist"]),
            output=output,
        ),
    }
    frozen_data = copy_frozen_data(data, args.data_path, output)
    files = {
        path.relative_to(output).as_posix(): file_record(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    document = {
        "schema": "equiframe-universality-actions-candidate-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": sources,
        "workflow_execution": workflow_execution,
        "artifacts": artifacts,
        "test_manifests": test_manifests,
        "consumer_data": frozen_data,
        "files": files,
        "required_python_versions": ["3.10", "3.11", "3.12", "3.13"],
        "required_native_platforms": [
            {"system": "Linux", "architecture": "x64"},
            {"system": "Linux", "architecture": "arm64"},
            {"system": "Windows", "architecture": "x64"},
            {"system": "Darwin", "architecture": "x64"},
            {"system": "Darwin", "architecture": "arm64"},
        ],
        "scope": "Exact private candidate for manual native Actions validation; never publication",
        "credentials_included": False,
        "results_included": False,
    }
    write_json(output / "candidate.json", document)
    print(json.dumps({"candidate": str(output), "files": len(files), "source": sources}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
