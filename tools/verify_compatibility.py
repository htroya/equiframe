"""Verify exact wheel/sdist bytes across explicit interpreters and dependency endpoints.

Output must be a new directory outside the checkout. Every command and failure
is retained. A successful local cell is evidence only for that exact interpreter,
platform and solved dependency set, never every version in a declared range.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from datetime import timezone as _timezone
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

UTC = _timezone.utc

PROFILES = ("base", "arrow", "pandas", "polars", "duckdb", "engines", "ml", "all")
ENDPOINTS = ("minimum", "latest")
ROOT = Path(__file__).resolve().parents[1]
EXACT_RESOURCE_FILES = frozenset(
    {
        (
            "examples/eda_generic.py",
            "equiframe/examples/integrations/eda_generic.py",
        ),
        (
            "examples/integrations/outcome_gates.py",
            "equiframe/examples/integrations/outcome_gates.py",
        ),
        (
            "examples/integrations/sqlite_snapshot.py",
            "equiframe/examples/integrations/sqlite_snapshot.py",
        ),
        (
            "examples/integrations/sqlite_snapshot_demo.py",
            "equiframe/examples/integrations/sqlite_snapshot_demo.py",
        ),
        (
            "examples/integrations/universal_first_use.py",
            "equiframe/examples/integrations/universal_first_use.py",
        ),
        (
            "examples/journeys/README.md",
            "equiframe/examples/journeys/README.md",
        ),
        (
            "examples/journeys/__init__.py",
            "equiframe/examples/journeys/__init__.py",
        ),
        (
            "examples/journeys/a_pandas_refactor.py",
            "equiframe/examples/journeys/a_pandas_refactor.py",
        ),
        (
            "examples/journeys/b_native_migration.py",
            "equiframe/examples/journeys/b_native_migration.py",
        ),
        (
            "examples/journeys/c_retail_etl.py",
            "equiframe/examples/journeys/c_retail_etl.py",
        ),
        (
            "examples/journeys/common.py",
            "equiframe/examples/journeys/common.py",
        ),
        (
            "examples/journeys/d_financial_reconciliation.py",
            "equiframe/examples/journeys/d_financial_reconciliation.py",
        ),
        (
            "examples/journeys/e_telemetry.py",
            "equiframe/examples/journeys/e_telemetry.py",
        ),
        (
            "examples/journeys/f_data_science_preparation.py",
            "equiframe/examples/journeys/f_data_science_preparation.py",
        ),
        (
            "examples/journeys/g_external_snapshots.py",
            "equiframe/examples/journeys/g_external_snapshots.py",
        ),
        (
            "examples/journeys/h_portable_ci.py",
            "equiframe/examples/journeys/h_portable_ci.py",
        ),
        (
            "examples/journeys/requirements.lock",
            "equiframe/examples/journeys/requirements.lock",
        ),
        (
            "examples/journeys/verify_journeys.py",
            "equiframe/examples/journeys/verify_journeys.py",
        ),
        (
            "examples/load_convert_compare.py",
            "equiframe/examples/load_convert_compare.py",
        ),
        (
            "schemas/r-execution-binding-1.0.schema.json",
            "equiframe/schemas/r-execution-binding-1.0.schema.json",
        ),
        (
            "schemas/r-review-binding-1.0.schema.json",
            "equiframe/schemas/r-review-binding-1.0.schema.json",
        ),
        (
            "schemas/r-review-options-1.0.schema.json",
            "equiframe/schemas/r-review-options-1.0.schema.json",
        ),
        (
            "schemas/r-review-result-1.0.schema.json",
            "equiframe/schemas/r-review-result-1.0.schema.json",
        ),
        (
            "schemas/reviewed-decision-1.0.schema.json",
            "equiframe/schemas/reviewed-decision-1.0.schema.json",
        ),
    }
)
INTERPRETER_PROBE = r"""
import json, os, platform, sys
print(json.dumps({
    "executable": sys.executable, "version": platform.python_version(),
    "implementation_name": sys.implementation.name,
    "implementation_version": platform.python_version(),
    "os_name": os.name, "sys_platform": sys.platform,
    "platform_machine": platform.machine(), "platform_release": platform.release(),
    "platform_system": platform.system(), "platform_version": platform.version(),
    "platform_python_implementation": platform.python_implementation(),
    "python_full_version": platform.python_version(),
    "python_version": '.'.join(map(str, sys.version_info[:2])),
    "prefix": sys.prefix, "base_prefix": sys.base_prefix,
}))
"""


class CellBlocked(RuntimeError):
    """The requested environment could not be established; not compatibility."""


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def artifact_record(path: Path) -> dict[str, Any]:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("artifact is not a regular file: " + str(path))
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def ensure_artifacts(expected: dict[str, dict[str, Any]], paths: dict[str, Path]) -> None:
    if set(expected) != set(paths) or any(
        artifact_record(paths[name]) != record for name, record in expected.items()
    ):
        raise ValueError("candidate artifact bytes changed during compatibility verification")


def clean_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UV_", "PIP_", "PYTHON", "PYTEST_"))
        and key not in ("VIRTUAL_ENV", "CONDA_PREFIX")
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        UV_NO_CONFIG="1",
        UV_PYTHON_DOWNLOADS="never",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    return environment


def endpoint_resolution(endpoint: str) -> str:
    if endpoint == "minimum":
        return "lowest-direct"
    if endpoint == "latest":
        return "highest"
    raise ValueError("unknown dependency endpoint: " + endpoint)


def safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe archive member: " + name)
    return path


def wheel_metadata(wheel: Path) -> dict[str, Any]:
    artifact_record(wheel)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate wheel entries")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("expected one wheel METADATA")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if canonicalize_name(str(metadata.get("Name", ""))) != "equiframe":
            raise ValueError("wheel is not equiframe")
        runtime_files = {}
        for info in archive.infolist():
            safe_member(info.filename)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("wheel contains a symlink")
            if info.filename.startswith("equiframe/") and not info.is_dir():
                raw = archive.read(info)
                runtime_files[info.filename] = {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                }
        if not {"equiframe/__init__.py", "equiframe/py.typed"} <= set(runtime_files):
            raise ValueError("wheel lacks the public typed package")
        requires_python = str(metadata.get("Requires-Python", ""))
        if not requires_python or not metadata.get("Version"):
            raise ValueError("wheel lacks version or Requires-Python")
        SpecifierSet(requires_python)
        return {
            "name": "equiframe",
            "version": str(metadata["Version"]),
            "requires_python": requires_python,
            "requires_dist": metadata.get_all("Requires-Dist", []),
            "extras": sorted(str(extra) for extra in metadata.get_all("Provides-Extra", [])),
            "runtime_files": runtime_files,
        }


def profile_requirements(
    metadata: dict[str, Any], profile: str, marker_environment: dict[str, str]
) -> list[str]:
    if profile not in PROFILES:
        raise ValueError("unknown profile: " + profile)
    extras = set(metadata["extras"])
    selected = extras if profile == "all" else set() if profile == "base" else {profile}
    if not selected <= extras:
        raise ValueError("requested extra is absent from wheel metadata: " + profile)
    # all is a verifier profile, the union of every extra actually advertised.
    if profile == "all" and not set(PROFILES[1:-1]) <= extras:
        raise ValueError("all profile requires every public extra in wheel metadata")
    result = set()
    for raw in metadata["requires_dist"]:
        requirement = Requirement(raw)
        if canonicalize_name(requirement.name) == "equiframe":
            raise ValueError("wheel metadata must not depend on equiframe itself")
        if requirement.url is not None:
            raise ValueError("direct URL runtime requirements are not supported")
        if requirement.marker is not None and not any(
            requirement.marker.evaluate({**marker_environment, "extra": extra})
            for extra in ("", *sorted(selected))
        ):
            continue
        requirement.marker = None
        result.add(str(requirement))
    if not result:
        raise ValueError("wheel has no selected runtime requirements")
    return sorted(result)


def parse_lock(path: Path) -> dict[str, str]:
    """Accept only exact unconditional registry pins and SHA-256 hashes."""
    text = path.read_text("utf-8")
    logical = text.replace("\\\n", " ")
    result: dict[str, str] = {}
    for line in logical.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        requirement = Requirement(parts[0])
        specs = list(requirement.specifier)
        if (
            requirement.url is not None
            or requirement.marker is not None
            or requirement.extras
            or len(specs) != 1
            or specs[0].operator != "=="
            or "*" in specs[0].version
            or len(parts) < 2
            or any(re.fullmatch(r"--hash=sha256:[a-f0-9]{64}", item) is None for item in parts[1:])
        ):
            raise ValueError("dependency lock must contain exact pins with SHA-256 hashes")
        name = canonicalize_name(requirement.name)
        if name == "equiframe" or name in result:
            raise ValueError("dependency lock contains equiframe or duplicate package")
        result[name] = specs[0].version
    if not result:
        raise ValueError("empty dependency lock")
    return result


def extract_sdist(sdist: Path, destination: Path, wheel_files: dict[str, dict[str, Any]]) -> Path:
    destination.mkdir()
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("duplicate sdist members")
        for member in members:
            safe_member(member.name)
            if not (member.isdir() or member.isfile()):
                raise ValueError("sdist contains a link or special file")
        archive.extractall(destination, filter="data")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("sdist must have exactly one source root")
    source = roots[0]
    package = source / "src" / "equiframe"
    found = {
        "equiframe/" + path.relative_to(package).as_posix(): artifact_record(path)
        for path in package.rglob("*")
        if path.is_file()
    }
    config = tomllib.loads((source / "pyproject.toml").read_text("utf-8"))
    mapping = (
        config.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    for original, destination_name in mapping.items():
        if (original, destination_name) in {
            ("docs", "equiframe/docs"),
            ("tools/cyclonedx", "equiframe/_vendor/cyclonedx"),
        }:
            directory = source / original
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("packaged handbook source is absent or linked")
            paths = sorted(directory.rglob("*"))
            if any(path.is_symlink() for path in paths):
                raise ValueError("packaged handbook cannot contain symlinks")
            included = [
                (path, destination_name + "/" + path.relative_to(directory).as_posix())
                for path in paths
                if path.is_file()
            ]
            if not included:
                raise ValueError("packaged handbook is empty")
        elif (original, destination_name) in EXACT_RESOURCE_FILES:
            included = [(source / original, destination_name)]
        else:
            raise ValueError("unsupported wheel force-include mapping")
        for path, key in included:
            if path.is_symlink() or not path.is_file():
                raise ValueError("packaged handbook/example source is absent or linked")
            if key in found:
                raise ValueError("packaged handbook/examples shadow runtime payload")
            found[key] = artifact_record(path)
    if found != wheel_files:
        raise ValueError("sdist runtime payload does not match the provided wheel")
    for required in ("pyproject.toml", "tests", "examples", "tools"):
        if not (source / required).exists():
            raise ValueError("sdist missing " + required)
    return source


def core_skip_contract(system: str) -> set[tuple[str, str, str]]:
    if system == "Windows":
        return {
            (
                "tests.test_report_io",
                "test_special_evidence_file_rejected_before_open",
                "FIFO unavailable",
            )
        }
    if system in ("Linux", "Darwin"):
        return set()
    raise ValueError(f"unsupported core skip-contract system: {system}")


def skip_records(values: set[tuple[str, str, str]]) -> list[dict[str, str]]:
    return [
        {"class": classname, "name": name, "message": message}
        for classname, name, message in sorted(values)
    ]


def expected_test_identities(path: Path) -> tuple[set[tuple[str, str]], dict[str, Any]]:
    loaded: object = json.loads(path.read_text("utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("test manifest must be an object")
    tests = loaded.get("tests")
    if (
        loaded.get("schema") != "equiframe-test-manifest-1"
        or loaded.get("package") != "equiframe"
        or loaded.get("plugin_autoload_disabled") is not True
        or not isinstance(loaded.get("pytest_version"), str)
        or not isinstance(loaded.get("hypothesis_version"), str)
        or not isinstance(tests, list)
        or loaded.get("test_count") != len(tests)
        or not tests
    ):
        raise ValueError("core test manifest header differs")
    identities: list[tuple[str, str]] = []
    for item in tests:
        if not isinstance(item, dict):
            raise TypeError("core test manifest identity must be an object")
        classname, name = item.get("classname"), item.get("name")
        if not isinstance(classname, str) or not classname or not isinstance(name, str) or not name:
            raise ValueError("core test manifest contains an empty JUnit identity")
        identities.append((classname, name))
    if len(set(identities)) != len(identities):
        raise ValueError("core test manifest repeats a JUnit identity")
    encoded = json.dumps(sorted(identities), separators=(",", ":")).encode("utf-8")
    summary = {
        "test_count": len(identities),
        "junit_identities_sha256": hashlib.sha256(encoded).hexdigest(),
        "record": artifact_record(path),
        "pytest_version": loaded["pytest_version"],
        "hypothesis_version": loaded["hypothesis_version"],
    }
    return set(identities), summary


def inspect_junit(
    path: Path,
    expected_skips: set[tuple[str, str, str]] | None = None,
    expected_tests: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Accept only the exact declared native-platform skip contract."""
    expected_skips = set() if expected_skips is None else expected_skips
    root = ET.parse(path).getroot()
    if root.tag not in ("testsuite", "testsuites"):
        raise ValueError("invalid JUnit root")
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError("JUnit contains no executed test cases")
    result: dict[str, Any] = {
        "tests": len(cases),
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "xfail": 0,
        "cases": [],
    }
    observed_skips: list[tuple[str, str, str]] = []
    observed_tests: list[tuple[str, str]] = []
    for case in cases:
        identity = (case.get("classname", ""), case.get("name", ""))
        if expected_tests is not None and not all(identity):
            raise ValueError("JUnit testcase identity is incomplete")
        observed_tests.append(identity)
        outcomes = [child for child in case if child.tag in ("failure", "error", "skipped")]
        if len(outcomes) > 1:
            raise ValueError("contradictory JUnit testcase outcomes")
        outcome = outcomes[0] if outcomes else None
        status = outcome.tag if outcome is not None else "passed"
        if status != "passed":
            key = {"failure": "failures", "error": "errors", "skipped": "skipped"}[status]
            result[key] += 1
        if (
            outcome is not None
            and "xfail" in (outcome.get("type", "") + " " + outcome.get("message", "")).lower()
        ):
            result["xfail"] += 1
        if status == "skipped":
            classname, name, message = (
                case.get("classname"),
                case.get("name"),
                outcome.get("message") if outcome is not None else None,
            )
            if not classname or not name or message is None:
                raise ValueError("JUnit skip identity is incomplete")
            observed_skips.append((classname, name, message))
        result["cases"].append(
            {
                "name": case.get("name", ""),
                "class": case.get("classname", ""),
                "status": status,
                **(
                    {"message": outcome.get("message")}
                    if status == "skipped" and outcome is not None
                    else {}
                ),
            }
        )
    for suite in root.iter():
        if suite.tag not in ("testsuite", "testsuites"):
            continue
        children = list(suite.iter("testcase"))
        counts = {
            "tests": len(children),
            "failures": sum(case.find("failure") is not None for case in children),
            "errors": sum(case.find("error") is not None for case in children),
            "skipped": sum(case.find("skipped") is not None for case in children),
        }
        for key, actual in counts.items():
            if key in suite.attrib and int(suite.attrib[key]) != actual:
                raise ValueError("JUnit summary disagrees with testcase outcomes")
    result["expected_skips"] = skip_records(expected_skips)
    result["observed_skips"] = skip_records(set(observed_skips))
    encoded = json.dumps(sorted(observed_tests), separators=(",", ":")).encode("utf-8")
    result["junit_identities_sha256"] = hashlib.sha256(encoded).hexdigest()
    result["identity_contract_matches"] = len(observed_tests) == len(set(observed_tests)) and (
        expected_tests is None or set(observed_tests) == expected_tests
    )
    result["accepted"] = (
        result["failures"] == 0
        and result["errors"] == 0
        and result["xfail"] == 0
        and len(observed_skips) == len(set(observed_skips))
        and set(observed_skips) == expected_skips
        and result["identity_contract_matches"]
    )
    return result


def write_json(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", "utf-8")
    temporary.replace(path)


class CellRunner:
    def __init__(
        self, directory: Path, receipt: dict[str, Any], artifacts: dict[str, Path], timeout: int
    ) -> None:
        self.directory = directory
        self.receipt = receipt
        self.artifacts = artifacts
        self.expected = {name: artifact_record(path) for name, path in artifacts.items()}
        self.environment = clean_environment()
        self.timeout = timeout

    def save(self) -> None:
        write_json(self.directory / "receipt.json", self.receipt)

    def run(
        self,
        command: list[str],
        *,
        stage: str,
        cwd: Path | None = None,
        expected_exit: int = 0,
        blocked: bool = False,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        ensure_artifacts(self.expected, self.artifacts)
        working = cwd or self.directory
        started = time.monotonic()
        index = len(self.receipt["commands"])
        output = self.directory / f"{index:03d}-{stage}.stdout.log"
        error = self.directory / f"{index:03d}-{stage}.stderr.log"
        entry: dict[str, Any] = {
            "command": command,
            "cwd": str(working),
            "stage": stage,
            "started_at": timestamp(),
            "expected_exit_code": expected_exit,
            "stdout": str(output),
            "stderr": str(error),
        }
        self.receipt["commands"].append(entry)
        self.save()
        try:
            completed = subprocess.run(
                command,
                cwd=working,
                env=self.environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=self.timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            entry.update(error=str(exc), exit_code=None, finished_at=timestamp())
            entry["duration_seconds"] = time.monotonic() - started
            output.write_text(str(getattr(exc, "stdout", "") or ""), "utf-8")
            error.write_text(str(getattr(exc, "stderr", "") or exc), "utf-8")
            self.save()
            if blocked:
                raise CellBlocked(f"{stage}: {exc}") from exc
            raise RuntimeError(f"{stage}: {exc}") from exc
        output.write_text(completed.stdout, "utf-8")
        error.write_text(completed.stderr, "utf-8")
        entry.update(
            exit_code=completed.returncode,
            finished_at=timestamp(),
            duration_seconds=time.monotonic() - started,
            stdout_artifact=artifact_record(output),
            stderr_artifact=artifact_record(error),
        )
        self.save()
        ensure_artifacts(self.expected, self.artifacts)
        if completed.returncode != expected_exit and not allow_failure:
            message = (
                f"{stage} exited {completed.returncode}; expected {expected_exit}; see {error}"
            )
            if blocked:
                raise CellBlocked(message)
            raise RuntimeError(message)
        return completed


def compile_command(
    uv: list[str], python: Path, inputs: list[Path], output: Path, endpoint: str
) -> list[str]:
    return [
        *uv,
        "pip",
        "compile",
        *(str(path) for path in inputs),
        "--python",
        str(python),
        "--resolution",
        endpoint_resolution(endpoint),
        "--upgrade",
        "--refresh",
        "--generate-hashes",
        "--only-binary",
        ":all:",
        "--no-header",
        "--no-annotate",
        "--output-file",
        str(output),
    ]


def install_exact_wheel_command(uv: list[str], python: Path, wheel: Path) -> list[str]:
    """Install the already-resolved candidate without resolving its dependencies again."""
    return [
        *uv,
        "pip",
        "install",
        "--python",
        str(python),
        "--no-index",
        "--no-deps",
        "--reinstall",
        "--link-mode",
        "copy",
        str(wheel),
    ]


def verify_versions(expected: dict[str, str], binding: dict[str, Any]) -> None:
    versions = binding["versions"]
    if any(versions.get(name) != version for name, version in expected.items()):
        raise ValueError("installed runtime versions differ from the exact dependency lock")


def probe_command(
    python: Path, probe: Path, manifest: Path, profile: str, output: Path, source: Path | None
) -> list[str]:
    command = [
        str(python),
        "-I",
        "-B",
        "-X",
        "pycache_prefix=" + str(output.parent / "bytecode"),
        str(probe),
        "--manifest",
        str(manifest),
        "--profile",
        profile,
        "--output",
        str(output),
    ]
    return command + (["--binding-only"] if source is None else ["--source", str(source)])


def exercise_examples(runner: CellRunner, python: Path, source: Path, profile: str) -> None:
    examples = source / "examples"
    base = [
        str(python),
        "-I",
        "-B",
        "-X",
        "pycache_prefix=" + str(runner.directory / "bytecode"),
    ]
    runner.run([*base, "-m", "equiframe", "--help"], stage="cli-help")
    for fixture in sorted(examples.glob("*.json")):
        runner.run(
            [*base, "-m", "equiframe", "contract", "validate", str(fixture)],
            stage="cli-contract-" + fixture.stem,
        )
    invalid = runner.directory / "invalid-contract.json"
    invalid.write_text('{"schema_version":"invalid"}\n', "utf-8")
    negative = runner.run(
        [*base, "-m", "equiframe", "contract", "validate", str(invalid)],
        stage="cli-invalid-contract",
        expected_exit=2,
    )
    if "Traceback" in negative.stdout + negative.stderr:
        raise ValueError("CLI exposed traceback for invalid contract")
    if profile in ("base", "ml"):
        if profile == "ml":
            runner.run(
                [
                    *base,
                    str(examples / "detectors_local.py"),
                    "--bundle",
                    str(runner.directory / "detectors.json"),
                ],
                stage="ml-fit-calibrate-detect",
            )
        return
    cli = runner.directory / "public-api" / "cli"
    for state, left, right, code in (
        ("equivalent", "expected", "expected", 0),
        ("different", "different", "expected", 1),
        ("not_evaluable", "expected", "invalid-reference", 3),
    ):
        completed = runner.run(
            [
                *base,
                "-m",
                "equiframe",
                "compare",
                str(cli / "spec.json"),
                str(cli / (left + ".arrow")),
                str(cli / (right + ".arrow")),
                "--expected",
                "--output",
                str(runner.directory / ("cli-" + state)),
            ],
            stage="cli-compare-" + state,
            expected_exit=code,
        )
        verdict = json.loads(completed.stdout)
        if verdict["state"] != state or verdict["accepted"] != (state == "equivalent"):
            raise ValueError("CLI comparison returned the wrong verdict")
        if verdict["evidence_status"] != "verified":
            raise ValueError("CLI comparison evidence was not verified")
        if "Traceback" in completed.stdout + completed.stderr:
            raise ValueError("CLI comparison exposed traceback")
    if profile in ("duckdb", "engines", "all"):
        runner.run(
            [
                *base,
                str(examples / "capture_duckdb.py"),
                "--output",
                str(runner.directory / "duckdb-capture-report"),
            ],
            stage="duckdb-detached-capture",
        )
    engines = (
        ("pandas", "polars", "duckdb")
        if profile in ("engines", "all")
        else ((profile,) if profile in ("pandas", "polars", "duckdb") else ())
    )
    for engine in ("arrow", *engines):
        for state, code in (("equivalent", 0), ("different", 1), ("not_evaluable", 3)):
            destination = runner.directory / f"assertion-{engine}-{state}"
            result = runner.run(
                [
                    *base,
                    str(examples / "assertion_ci.py"),
                    "--engine",
                    engine,
                    "--case",
                    state,
                    "--output",
                    str(destination),
                    "--work-dir",
                    str(runner.directory / f"private-{engine}-{state}"),
                ],
                stage=f"assertion-{engine}-{state}",
                expected_exit=code,
            )
            if "Traceback" in result.stdout + result.stderr:
                raise ValueError("assertion CLI exposed traceback")
    for engine in engines:
        runner.run(
            [
                *base,
                str(examples / "execute_native.py"),
                "--engine",
                engine,
                "--work-dir",
                str(runner.directory / ("native-" + engine)),
            ],
            stage="native-execution-" + engine,
        )
    if profile in ("engines", "all"):
        runner.run(
            [
                *base,
                str(examples / "migrate_native.py"),
                "--output",
                str(runner.directory / "six-migrations"),
            ],
            stage="native-migration-six-directions",
        )
    if profile == "all":
        runner.run(
            [
                *base,
                str(examples / "detectors_local.py"),
                "--bundle",
                str(runner.directory / "detectors.json"),
            ],
            stage="ml-fit-calibrate-detect",
        )


def run_suite(
    runner: CellRunner,
    uv: list[str],
    python: Path,
    source: Path,
    lock: Path,
    runtime: dict[str, str],
    probe: Path,
    manifest: Path,
    expected_tests: set[tuple[str, str]],
    test_manifest_summary: dict[str, Any],
) -> None:
    config = tomllib.loads((source / "pyproject.toml").read_text("utf-8"))
    requirements = config.get("dependency-groups", {}).get("dev", [])
    if not requirements or not all(isinstance(value, str) for value in requirements):
        raise ValueError("sdist must declare a flat test/development dependency group")
    development = runner.directory / "test-tools.in"
    requirements = [
        *requirements,
        f"pytest=={test_manifest_summary['pytest_version']}",
        f"hypothesis=={test_manifest_summary['hypothesis_version']}",
    ]
    development.write_text("\n".join(requirements) + "\n", "utf-8")
    test_lock = runner.directory / "test-tools.lock"
    command = compile_command(uv, python, [lock, development], test_lock, "latest")
    command += ["--constraint", str(lock)]
    runner.run(command, stage="resolve-test-tools", blocked=True)
    solved = parse_lock(test_lock)
    if any(solved.get(name) != version for name, version in runtime.items()):
        raise ValueError("test-tool resolution changed a runtime dependency")
    runner.receipt["test_tools_lock"] = artifact_record(test_lock)
    runner.run(
        [
            *uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--require-hashes",
            "--only-binary",
            ":all:",
            "--link-mode",
            "copy",
            "-r",
            str(test_lock),
        ],
        stage="install-test-tools",
        blocked=True,
    )
    runner.run([*uv, "pip", "check", "--python", str(python)], stage="test-tools-pip-check")
    before = runner.directory / "suite-runtime-before.json"
    runner.run(
        probe_command(python, probe, manifest, "all", before, None), stage="suite-binding-before"
    )
    verify_versions(runtime, json.loads(before.read_text("utf-8")))
    junit = runner.directory / "pytest.xml"
    completed = runner.run(
        [
            str(python),
            "-I",
            "-B",
            "-X",
            "pycache_prefix=" + str(runner.directory / "bytecode"),
            "-m",
            "pytest",
            "-p",
            "_hypothesis_pytestplugin",
            "-q",
            "--junitxml",
            str(junit),
            "-o",
            "xfail_strict=true",
            "--basetemp",
            str(runner.directory / "pytest-tmp"),
        ],
        stage="full-installed-suite",
        cwd=source,
        allow_failure=True,
    )
    if not junit.is_file():
        raise ValueError("installed suite produced no JUnit receipt")
    summary = inspect_junit(junit, core_skip_contract(platform.system()), expected_tests)
    runner.receipt["suite"] = summary
    runner.receipt["suite_junit"] = artifact_record(junit)
    after = runner.directory / "suite-runtime-after.json"
    runner.run(
        probe_command(python, probe, manifest, "all", after, None), stage="suite-binding-after"
    )
    verify_versions(runtime, json.loads(after.read_text("utf-8")))
    if completed.returncode != 0 or not summary["accepted"]:
        raise ValueError("installed suite failed or its exact skip contract differed")


def execute_cell(
    directory: Path,
    *,
    interpreter: str,
    profile: str,
    endpoint: str,
    uv_path: str,
    artifacts: dict[str, Path],
    metadata: dict[str, Any],
    probe: Path,
    timeout: int,
    cache: Path,
    expected_tests: set[tuple[str, str]],
    test_manifest_summary: dict[str, Any],
) -> dict[str, Any]:
    directory.mkdir()
    receipt: dict[str, Any] = {
        "schema": "equiframe-compatibility-cell-1",
        "status": "running",
        "profile": profile,
        "endpoint": endpoint,
        "resolution": endpoint_resolution(endpoint),
        "endpoint_scope": "lowest solvable direct requirements; latest permitted transitives"
        if endpoint == "minimum"
        else "highest permitted refreshed solution",
        "requested_python": interpreter,
        "started_at": timestamp(),
        "commands": [],
        "artifacts": {name: artifact_record(path) for name, path in artifacts.items()},
        "receipts_authenticated": False,
        "remote_ci": False,
        "skips": [],
        "blockers": [],
        "test_manifest": test_manifest_summary,
    }
    runner = CellRunner(directory, receipt, artifacts, timeout)
    runner.save()
    uv = [uv_path, "--no-config", "--cache-dir", str(cache)]
    try:
        version = runner.run([uv_path, "--no-config", "--version"], stage="uv-version")
        receipt["uv_version"] = version.stdout.strip()
        executable = shutil.which(interpreter)
        if executable is None:
            raise CellBlocked("provided Python executable is unavailable: " + interpreter)
        information = runner.run(
            [executable, "-I", "-c", INTERPRETER_PROBE], stage="interpreter", blocked=True
        )
        info: dict[str, str] = json.loads(information.stdout)
        receipt["interpreter"] = info
        if info["version"] not in SpecifierSet(metadata["requires_python"]):
            raise CellBlocked("actual interpreter is excluded by wheel Requires-Python")
        source = extract_sdist(artifacts["sdist"], directory / "sdist", metadata["runtime_files"])
        requirements = profile_requirements(metadata, profile, info)
        selected = directory / "runtime.in"
        selected.write_text("\n".join(requirements) + "\n", "utf-8")
        receipt["selected_requirements"] = requirements
        lock = directory / "runtime.lock"
        runner.run(
            compile_command(uv, Path(executable), [selected], lock, endpoint),
            stage="resolve-runtime",
            blocked=True,
        )
        runtime = parse_lock(lock)
        receipt.update(runtime_versions=runtime, runtime_lock=artifact_record(lock))
        venv = directory / "venv"
        runner.run(
            [*uv, "venv", "--python", executable, "--no-python-downloads", str(venv)],
            stage="create-clean-venv",
            blocked=True,
        )
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        runner.run(
            [
                *uv,
                "pip",
                "sync",
                "--python",
                str(python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--link-mode",
                "copy",
                str(lock),
            ],
            stage="sync-runtime",
            blocked=True,
        )
        runner.run(
            install_exact_wheel_command(uv, python, artifacts["wheel"]),
            stage="install-exact-wheel",
            blocked=True,
        )
        runner.run([*uv, "pip", "check", "--python", str(python)], stage="runtime-pip-check")
        manifest = directory / "wheel-payload.json"
        write_json(manifest, {**metadata, "checkout": str(ROOT)})
        binding = directory / "runtime-binding.json"
        runner.run(
            probe_command(python, probe, manifest, profile, binding, source), stage="public-api"
        )
        loaded = json.loads(binding.read_text("utf-8"))
        verify_versions(runtime, loaded)
        receipt["runtime_binding"] = loaded
        exercise_examples(runner, python, source, profile)
        if profile == "all":
            run_suite(
                runner,
                uv,
                python,
                source,
                lock,
                runtime,
                probe,
                manifest,
                expected_tests,
                test_manifest_summary,
            )
        after = directory / "runtime-binding-after.json"
        runner.run(
            probe_command(python, probe, manifest, profile, after, None), stage="binding-after"
        )
        verify_versions(runtime, json.loads(after.read_text("utf-8")))
        ensure_artifacts(runner.expected, artifacts)
        receipt["status"] = "passed"
    except CellBlocked as exc:
        receipt["status"] = "blocked"
        receipt["blockers"].append(str(exc))
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if receipt.get("suite", {}).get("skipped", 0):
            receipt["skips"] = [
                case for case in receipt["suite"]["cases"] if case["status"] == "skipped"
            ]
        receipt["finished_at"] = timestamp()
        runner.save()
    return receipt


def platform_gaps(
    interpreters: list[str], profiles: list[str], endpoints: list[str]
) -> list[dict[str, Any]]:
    machine = platform.machine().lower()
    aliases = {"amd64": "x86_64", "arm64": "aarch64"}
    actual = (platform.system(), aliases.get(machine, machine))
    targets = (
        ("Linux", "x86_64"),
        ("Linux", "aarch64"),
        ("Windows", "x86_64"),
        ("Darwin", "x86_64"),
        ("Darwin", "aarch64"),
    )
    return [
        {
            "system": system,
            "architecture": architecture,
            "python": interpreter,
            "profile": profile,
            "endpoint": endpoint,
            "status": "not_verified",
            "reason": "No runner executed on this OS/architecture",
            "remote_ci": False,
        }
        for system, architecture in targets
        if (system, architecture) != actual
        for interpreter in interpreters
        for profile in profiles
        for endpoint in endpoints
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New external output directory")
    parser.add_argument("--python", action="append", required=True, help="Actual Python executable")
    parser.add_argument("--profile", choices=PROFILES, action="append")
    parser.add_argument("--endpoint", choices=ENDPOINTS, action="append")
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--timeout", type=int, default=1800, help="Per-command timeout in seconds")
    args = parser.parse_args()
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        parser.error("output already exists; preserve failed receipts and choose a new output")
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True
    )
    checkout = Path(probe.stdout.strip()).resolve() if probe.returncode == 0 else ROOT.resolve()
    if output.resolve().is_relative_to(checkout):
        parser.error("output must be outside the checkout")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    uv = shutil.which(args.uv)
    if uv is None:
        parser.error("uv executable is unavailable")
    inputs = {
        "wheel": args.wheel.absolute(),
        "sdist": args.sdist.absolute(),
        "test_manifest": args.test_manifest.absolute(),
    }
    expected = {name: artifact_record(path) for name, path in inputs.items()}
    metadata = wheel_metadata(inputs["wheel"])
    output.mkdir(parents=True)
    stored = output / "artifacts"
    stored.mkdir()
    artifacts = {}
    for name, path in inputs.items():
        destination = stored / path.name
        shutil.copyfile(path, destination)
        artifacts[name] = destination
    ensure_artifacts(expected, artifacts)
    expected_tests, test_manifest_summary = expected_test_identities(artifacts["test_manifest"])
    probe = output / "compatibility_probe.py"
    shutil.copyfile(Path(__file__).with_name("compatibility_probe.py"), probe)
    profiles = list(dict.fromkeys(args.profile or PROFILES))
    endpoints = list(dict.fromkeys(args.endpoint or ENDPOINTS))
    interpreters = list(dict.fromkeys(args.python))
    matrix: dict[str, Any] = {
        "schema": "equiframe-compatibility-matrix-1",
        "status": "running",
        "started_at": timestamp(),
        "artifacts": expected,
        "wheel_metadata": metadata,
        "controller": {"system": platform.platform(), "python": platform.python_version()},
        "tooling": {"runner": artifact_record(Path(__file__)), "probe": artifact_record(probe)},
        "cells": [],
        "not_verified": platform_gaps(interpreters, profiles, endpoints),
        "receipts_authenticated": False,
        "remote_ci": False,
        "scope": "Only the exact supplied artifacts and observed solved environment cells",
    }
    write_json(output / "matrix.json", matrix)
    for index, interpreter in enumerate(interpreters):
        for profile in profiles:
            for endpoint in endpoints:
                directory = output / f"python-{index + 1}-{profile}-{endpoint}"
                receipt = execute_cell(
                    directory,
                    interpreter=interpreter,
                    profile=profile,
                    endpoint=endpoint,
                    uv_path=uv,
                    artifacts=artifacts,
                    metadata=metadata,
                    probe=probe,
                    timeout=args.timeout,
                    cache=output / "uv-cache",
                    expected_tests=expected_tests,
                    test_manifest_summary=test_manifest_summary,
                )
                matrix["cells"].append(
                    {
                        "python": interpreter,
                        "profile": profile,
                        "endpoint": endpoint,
                        "status": receipt["status"],
                        "receipt": str(directory / "receipt.json"),
                        "receipt_artifact": artifact_record(directory / "receipt.json"),
                    }
                )
                write_json(output / "matrix.json", matrix)
                print(f"{interpreter} {profile} {endpoint}: {receipt['status']}", flush=True)
    matrix["status"] = (
        "passed" if all(cell["status"] == "passed" for cell in matrix["cells"]) else "failed"
    )
    matrix["finished_at"] = timestamp()
    matrix["counts"] = {
        status: sum(cell["status"] == status for cell in matrix["cells"])
        for status in ("passed", "failed", "blocked")
    }
    ensure_artifacts(expected, inputs)
    ensure_artifacts(expected, artifacts)
    write_json(output / "matrix.json", matrix)
    raise SystemExit(0 if matrix["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
