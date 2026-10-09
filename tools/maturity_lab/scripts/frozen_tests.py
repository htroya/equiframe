"""Bind frozen test identities to delivered sdists and exact Linux suite outcomes."""

from __future__ import annotations

import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

PACKAGES = {
    "core": "equiframe",
    "benchmark": "equiframe-benchmark",
    "consumer": "equiframe-consumer-lab",
}


def identities(manifest: dict) -> set[tuple[str, str]]:
    records = [(item["classname"], item["name"]) for item in manifest["tests"]]
    if not records or any(not all(item) for item in records) or len(set(records)) != len(records):
        raise ValueError("frozen test identities are empty or repeated")
    return set(records)


def identity_sha256(manifest: dict) -> str:
    encoded = json.dumps(sorted(identities(manifest)), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_manifest(path: Path, label: str, count: int) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("test manifest must be a regular file")
    value = json.loads(path.read_text("utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema") != "equiframe-test-manifest-1"
        or value.get("package") != PACKAGES[label]
        or value.get("plugin_autoload_disabled") is not True
        or not isinstance(value.get("files"), dict)
        or not value["files"]
        or not isinstance(value.get("tests"), list)
        or value.get("test_count") != count
        or len(value["tests"]) != count
        or any(
            not isinstance(value.get(key), str) or not value[key]
            for key in ("pytest_version", "hypothesis_version")
        )
    ):
        raise ValueError("frozen test manifest header/count differs")
    identities(value)
    return value


def verify_sdist_tests(sdist: Path, manifest: dict) -> None:
    observed = {}
    roots = set()
    with tarfile.open(sdist, "r:gz") as archive:
        for item in archive.getmembers():
            path = PurePosixPath(item.name)
            if path.is_absolute() or ".." in path.parts or "\\" in item.name:
                raise ValueError("sdist member is not portable")
            roots.add(path.parts[0])
            if len(path.parts) < 2 or path.parts[1] != "tests" or item.isdir():
                continue
            if not item.isfile():
                raise ValueError("sdist test member is not regular")
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if relative in observed:
                raise ValueError("sdist repeats a test member")
            stream = archive.extractfile(item)
            if stream is None:
                raise ValueError("sdist test member cannot be read")
            with stream:
                content = stream.read()
            observed[relative] = {
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
    if len(roots) != 1 or observed != manifest["files"]:
        raise ValueError("sdist test files differ from the frozen manifest")


def candidate_manifests(kit: Path, candidate: dict, *, required: bool = False) -> dict:
    bindings = candidate.get("test_manifests")
    if bindings is None and not required:
        return {}  # Historic kits retain their original strict no-skip review.
    if not isinstance(bindings, dict) or set(bindings) != set(PACKAGES):
        raise ValueError("execution requires all three frozen test manifests")
    result = {}
    for label, binding in bindings.items():
        relative = binding["path"]
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in relative
            or not path.parts
            or path.parts[0] != "test-manifests"
            or candidate["files"].get(relative)
            != {"sha256": binding["sha256"], "size_bytes": binding["size_bytes"]}
        ):
            raise ValueError("test manifest binding differs from kit inventory")
        member = kit / relative
        content = member.read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != binding["sha256"]
            or len(content) != binding["size_bytes"]
        ):
            raise ValueError("test manifest bytes differ")
        manifest = read_manifest(member, label, candidate["suite_minimums"][label])
        verify_sdist_tests(kit / candidate["artifacts"][label + "_sdist"], manifest)
        result[label] = manifest
    if len({(item["pytest_version"], item["hypothesis_version"]) for item in result.values()}) != 1:
        raise ValueError("paired suites require the same frozen test-tool versions")
    return result


def linux_skips(label: str) -> set[tuple[str, str, str]]:
    if label not in PACKAGES:
        raise ValueError("unknown suite")
    if label != "benchmark":
        return set()
    return {
        (
            "tests.test_scale_process",
            "test_windows_venv_redirector_runs_real_interpreter_as_owned_child",
            "Windows CPython venv redirector",
        ),
        (
            "tests.test_scale_process",
            "test_windows_venv_redirect_bypass_replaces_all_launcher_variable_casings",
            "Windows environment names are case-insensitive",
        ),
    }


def verify_linux_junit(root: ET.Element, manifest: dict, label: str) -> None:
    cases = list(root.iter("testcase"))
    observed = [(case.get("classname", ""), case.get("name", "")) for case in cases]
    if len(observed) != len(set(observed)) or set(observed) != identities(manifest):
        raise ValueError("JUnit identities differ from the exact frozen suite")
    skipped = []
    for case in cases:
        outcomes = [item for item in case if item.tag in ("failure", "error", "skipped")]
        if len(outcomes) > 1 or any(item.tag != "skipped" for item in outcomes):
            raise ValueError("JUnit suite failed or has contradictory outcomes")
        if outcomes:
            item = outcomes[0]
            if "xfail" in (item.get("type", "") + " " + item.get("message", "")).lower():
                raise ValueError("JUnit xfail cannot close the frozen suite")
            skipped.append(
                (
                    case.get("classname", ""),
                    case.get("name", ""),
                    item.get("message", ""),
                )
            )
    if len(skipped) != len(set(skipped)) or set(skipped) != linux_skips(label):
        raise ValueError("JUnit skips differ from the exact Linux platform contract")
    for suite in root.iter():
        if suite.tag not in ("testsuite", "testsuites"):
            continue
        members = list(suite.iter("testcase"))
        counts = {
            "tests": len(members),
            "failures": sum(case.find("failure") is not None for case in members),
            "errors": sum(case.find("error") is not None for case in members),
            "skipped": sum(case.find("skipped") is not None for case in members),
        }
        if any(
            key in suite.attrib and int(suite.attrib[key]) != count for key, count in counts.items()
        ):
            raise ValueError("JUnit summary differs from testcase outcomes")
