"""The compatibility gate must reject incomplete or substituted evidence.

All artifacts here are synthetic temporary files. These fast unit tests do not
resolve dependencies, contact an index, install packages, or run the matrix.
"""

from __future__ import annotations

import hashlib
import io
import json
import runpy
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

TOOLS = Path(__file__).parents[1] / "tools"
RUNTIME = {
    "equiframe/__init__.py": b'__version__ = "0.0.0"\n',
    "equiframe/py.typed": b"",
    "equiframe/resources/policy.json": b'{"schema_version":"1.0"}\n',
}
HASH = "a" * 64


@pytest.fixture(scope="module")
def runner() -> dict[str, Any]:
    return runpy.run_path(str(TOOLS / "verify_compatibility.py"))


@pytest.fixture(scope="module")
def probe() -> dict[str, Any]:
    return runpy.run_path(str(TOOLS / "compatibility_probe.py"))


def records(files: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    return {
        name: {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
        for name, raw in files.items()
    }


def make_wheel(tmp_path: Path, *, metadata: str | None = None) -> Path:
    wheel = tmp_path / "equiframe-0.0.0-py3-none-any.whl"
    if metadata is None:
        metadata = (
            "Metadata-Version: 2.3\n"
            "Name: equiframe\n"
            "Version: 0.0.0\n"
            "Requires-Python: >=3.12,<3.13\n"
            "Provides-Extra: arrow\n"
            "Provides-Extra: pandas\n"
            "Provides-Extra: polars\n"
            "Provides-Extra: duckdb\n"
            "Provides-Extra: engines\n"
            "Provides-Extra: ml\n"
            "Requires-Dist: pydantic>=2.12,<3\n"
            'Requires-Dist: tzdata>=2025.2; sys_platform == "win32"\n'
            'Requires-Dist: pyarrow>=20,<26; extra == "arrow" or extra == "pandas"\n'
            'Requires-Dist: pandas>=2.2,<4; extra == "pandas" and python_version >= "3.12"\n'
            'Requires-Dist: numpy>=2,<3; extra == "ml"\n'
            "\nSynthetic wheel metadata, not a distributable candidate.\n"
        )
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, raw in RUNTIME.items():
            archive.writestr(name, raw)
        archive.writestr("equiframe-0.0.0.dist-info/METADATA", metadata)
    return wheel


def make_sdist(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
    sdist = tmp_path / "equiframe-0.0.0.tar.gz"
    payload = {
        "equiframe-0.0.0/pyproject.toml": b'[project]\nname="equiframe"\nversion="0.0.0"\n',
        "equiframe-0.0.0/tests/test_synthetic.py": b"def test_synthetic(): assert True\n",
        **{"equiframe-0.0.0/src/" + name: raw for name, raw in RUNTIME.items()},
    }
    if files is not None:
        payload = files
    payload.update(
        {
            "equiframe-0.0.0/examples/synthetic.json": b"{}\n",
            "equiframe-0.0.0/tools/synthetic.py": b"pass\n",
        }
    )
    with tarfile.open(sdist, "w:gz") as archive:
        for name, raw in payload.items():
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return sdist


def junit(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "pytest.xml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "endpoint,resolution", [("minimum", "lowest-direct"), ("latest", "highest")]
)
def test_resolution_endpoints_are_explicit(runner, endpoint, resolution):
    assert runner["endpoint_resolution"](endpoint) == resolution


@pytest.mark.parametrize("endpoint", ["", "locked", "minimums", "Latest", "highest"])
def test_unknown_endpoint_cannot_silently_select_another_resolution(runner, endpoint):
    with pytest.raises(ValueError):
        runner["endpoint_resolution"](endpoint)


def test_exact_wheel_reinstall_reuses_the_hash_locked_runtime(runner, tmp_path):
    command = runner["install_exact_wheel_command"](
        ["uv", "--no-config", "--cache-dir", "cache"],
        tmp_path / "venv" / "python",
        tmp_path / "candidate.whl",
    )
    assert command[:5] == ["uv", "--no-config", "--cache-dir", "cache", "pip"]
    assert command[5:9] == ["install", "--python", str(tmp_path / "venv" / "python"), "--no-index"]
    assert command.count("--no-deps") == 1
    assert command.count("--reinstall") == 1
    assert command[-3:] == ["--link-mode", "copy", str(tmp_path / "candidate.whl")]


def test_matrix_processes_do_not_inherit_import_or_dependency_overrides(runner, monkeypatch):
    pollution = (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONPYCACHEPREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_INDEX_URL",
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "VIRTUAL_ENV",
    )
    for name in pollution:
        monkeypatch.setenv(name, "synthetic-untrusted-override")
    monkeypatch.setenv("PATH", "synthetic-system-path")
    environment = runner["clean_environment"]()
    assert all(name not in environment for name in pollution)
    assert environment["PATH"] == "synthetic-system-path"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"


def test_wheel_metadata_binds_every_runtime_file_including_resources(runner, tmp_path):
    metadata = runner["wheel_metadata"](make_wheel(tmp_path))
    assert metadata["version"] == "0.0.0"
    assert metadata["requires_python"] == ">=3.12,<3.13"
    assert set(metadata["extras"]) == {"arrow", "pandas", "polars", "duckdb", "engines", "ml"}
    assert len(metadata["requires_dist"]) == 5
    assert metadata["runtime_files"] == records(RUNTIME)


@pytest.mark.parametrize(
    "profile,platform,python,expected",
    [
        ("base", "linux", "3.12", {"pydantic"}),
        ("base", "win32", "3.12", {"pydantic", "tzdata"}),
        ("arrow", "linux", "3.12", {"pydantic", "pyarrow"}),
        ("pandas", "linux", "3.12", {"pydantic", "pyarrow", "pandas"}),
        ("pandas", "win32", "3.12", {"pydantic", "tzdata", "pyarrow", "pandas"}),
        ("pandas", "linux", "3.11", {"pydantic", "pyarrow"}),
        ("ml", "linux", "3.12", {"pydantic", "numpy"}),
        ("all", "linux", "3.12", {"pydantic", "pyarrow", "pandas", "numpy"}),
    ],
)
def test_profile_requirements_evaluate_extra_and_target_environment_markers(
    runner, tmp_path, profile, platform, python, expected
):
    metadata = runner["wheel_metadata"](make_wheel(tmp_path))
    environment = default_environment()
    environment.update(sys_platform=platform, python_version=python)
    original = dict(environment)
    requirements = [
        Requirement(value)
        for value in runner["profile_requirements"](metadata, profile, environment)
    ]
    assert {canonicalize_name(value.name) for value in requirements} == expected
    assert len(requirements) == len(expected)
    assert all(value.marker is None for value in requirements)
    assert environment == original
    pydantic = next(value for value in requirements if value.name == "pydantic")
    assert str(pydantic.specifier) == "<3,>=2.12"


def test_unknown_profile_is_rejected_instead_of_installing_base(runner, tmp_path):
    metadata = runner["wheel_metadata"](make_wheel(tmp_path))
    with pytest.raises(ValueError):
        runner["profile_requirements"](metadata, "not-declared", default_environment())


def test_junit_success_counts_actual_cases_in_multiple_suites(runner, tmp_path):
    path = junit(
        tmp_path,
        '<testsuites tests="2" failures="0" errors="0" skipped="0">'
        '<testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="contracts" name="test_roundtrip"/>'
        "</testsuite>"
        '<testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="evidence" name="test_hash"/>'
        "</testsuite></testsuites>",
    )
    result = runner["inspect_junit"](path)
    assert result["accepted"] is True
    assert {name: result[name] for name in ("tests", "failures", "errors", "skipped", "xfail")} == {
        "tests": 2,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "xfail": 0,
    }
    assert len(result["cases"]) == 2


def test_junit_must_match_the_exact_frozen_test_identity_set(runner, tmp_path):
    path = junit(
        tmp_path,
        '<testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="contracts" name="test_roundtrip"/>'
        "</testsuite>",
    )
    expected = {("contracts", "test_roundtrip"), ("evidence", "test_hash")}
    result = runner["inspect_junit"](path, set(), expected)
    assert result["tests"] == 1
    assert result["identity_contract_matches"] is False
    assert result["accepted"] is False


@pytest.mark.parametrize(
    "child,counts,expected",
    [
        ('<failure message="regression"/>', (1, 0, 0), (1, 0, 0, 0)),
        ('<error message="collection error"/>', (0, 1, 0), (0, 1, 0, 0)),
        ('<skipped message="dependency unavailable"/>', (0, 0, 1), (0, 0, 1, 0)),
        (
            '<skipped type="pytest.xfail" message="known failure"/>',
            (0, 0, 1),
            (0, 0, 1, 1),
        ),
    ],
)
def test_junit_nonpassing_outcomes_never_establish_compatibility(
    runner, tmp_path, child, counts, expected
):
    failures, errors, skipped = counts
    path = junit(
        tmp_path,
        f'<testsuite tests="1" failures="{failures}" errors="{errors}" skipped="{skipped}">'
        f'<testcase classname="compatibility" name="test_behavior">{child}</testcase>'
        "</testsuite>",
    )
    result = runner["inspect_junit"](path)
    assert result["accepted"] is False
    assert tuple(result[name] for name in ("failures", "errors", "skipped", "xfail")) == expected


@pytest.mark.parametrize(
    "xml",
    [
        "",
        "<testsuite>",
        '<testsuite tests="0" failures="0" errors="0" skipped="0"/>',
        '<testsuite tests="1" failures="0" errors="0" skipped="0"/>',
        '<testsuite tests="2"><testcase name="only-one"/></testsuite>',
        '<testsuite tests="1" failures="0">'
        '<testcase name="failure"><failure/></testcase></testsuite>',
        '<testsuite tests="1" skipped="0"><testcase name="skip"><skipped/></testcase></testsuite>',
        '<testsuites tests="9"><testsuite tests="1"><testcase name="a"/></testsuite></testsuites>',
        '<testsuite tests="-1"><testcase name="a"/></testsuite>',
        '<testsuite tests="one"><testcase name="a"/></testsuite>',
        '<unrelated tests="1"><testcase name="a"/></unrelated>',
    ],
)
def test_junit_malformed_empty_or_contradictory_receipts_are_rejected(runner, tmp_path, xml):
    with pytest.raises((ValueError, ET.ParseError)):
        runner["inspect_junit"](junit(tmp_path, xml))


def test_artifact_record_is_bound_to_exact_bytes(runner, tmp_path):
    path = tmp_path / "candidate.whl"
    raw = b"synthetic exact candidate bytes"
    path.write_bytes(raw)
    result = runner["artifact_record"](path)
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["size_bytes"] == len(raw)
    runner["ensure_artifacts"]({"wheel": result}, {"wheel": path})


@pytest.mark.parametrize("mutation", ["same-size", "truncated", "missing"])
def test_postcheck_artifact_substitution_is_not_accepted(runner, tmp_path, mutation):
    path = tmp_path / "candidate.whl"
    path.write_bytes(b"original")
    expected = {"wheel": runner["artifact_record"](path)}
    if mutation == "missing":
        path.unlink()
    else:
        path.write_bytes(b"replaced" if mutation == "same-size" else b"short")
    with pytest.raises((ValueError, FileNotFoundError)):
        runner["ensure_artifacts"](expected, {"wheel": path})


def test_hash_locked_resolution_has_exact_normalized_versions(runner, tmp_path):
    path = tmp_path / "requirements.txt"
    path.write_text(
        "# synthetic lock, no downloaded artifacts\n"
        f"Pydantic_Core==2.41.1 \\\n    --hash=sha256:{HASH} \\\n"
        f"    --hash=sha256:{'b' * 64}\n"
        f"packaging==25.0 --hash=sha256:{HASH}\n",
        encoding="utf-8",
    )
    assert runner["parse_lock"](path) == {"pydantic-core": "2.41.1", "packaging": "25.0"}


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# only a comment\n",
        "pydantic==2.12.0\n",
        f"pydantic>=2.12 --hash=sha256:{HASH}\n",
        f"pydantic --hash=sha256:{HASH}\n",
        f"pydantic==2.* --hash=sha256:{HASH}\n",
        "pydantic==2.12.0 --hash=sha256:not-a-hash\n",
        f"equiframe==0.11.1 --hash=sha256:{HASH}\n",
        f"EquiFrame==0.11.1 --hash=sha256:{HASH}\n",
        "pydantic==2.12.0\n" + f"packaging==25.0 --hash=sha256:{HASH}\n",
        f"pydantic==2.12.0 --hash=sha256:{HASH}\n" + f"pydantic==2.12.1 --hash=sha256:{HASH}\n",
        f"pydantic_core==2.41.0 --hash=sha256:{HASH}\n"
        + f"pydantic-core==2.41.1 --hash=sha256:{HASH}\n",
        f"-e ./checkout --hash=sha256:{HASH}\n",
    ],
)
def test_incomplete_unpinned_or_candidate_contaminated_locks_are_rejected(runner, tmp_path, text):
    path = tmp_path / "requirements.txt"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        runner["parse_lock"](path)


def test_sdist_reconstruction_is_bound_to_wheel_runtime_payload(runner, tmp_path):
    destination = tmp_path / "extracted"
    source = runner["extract_sdist"](make_sdist(tmp_path), destination, records(RUNTIME))
    assert source.is_relative_to(destination)
    assert (source / "pyproject.toml").is_file()
    for name, raw in RUNTIME.items():
        assert (source / "src" / name).read_bytes() == raw
    assert (source / "tests" / "test_synthetic.py").is_file()


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra"])
def test_sdist_payload_cannot_differ_from_wheel_with_same_version(runner, tmp_path, mutation):
    files = {"equiframe-0.0.0/src/" + name: raw for name, raw in RUNTIME.items()}
    files["equiframe-0.0.0/pyproject.toml"] = b'[project]\nname="equiframe"\n'
    files["equiframe-0.0.0/tests/test_synthetic.py"] = b"def test_ok(): assert True\n"
    target = "equiframe-0.0.0/src/equiframe/__init__.py"
    if mutation == "changed":
        files[target] = b'__version__ = "0.0.0"\nUNTESTED = True\n'
    elif mutation == "missing":
        del files[target]
    else:
        files["equiframe-0.0.0/src/equiframe/obsolete.py"] = b"UNTESTED = True\n"
    with pytest.raises(ValueError):
        runner["extract_sdist"](make_sdist(tmp_path, files), tmp_path / "out", records(RUNTIME))


@pytest.mark.parametrize("attack", ["parent", "absolute", "symlink", "hardlink"])
def test_unsafe_sdist_members_are_rejected_before_runtime_is_accepted(runner, tmp_path, attack):
    archive = make_sdist(tmp_path)
    with tarfile.open(archive, "r:gz") as original:
        members = [(member, original.extractfile(member).read()) for member in original]
    with tarfile.open(archive, "w:gz") as replacement:
        for member, raw in members:
            replacement.addfile(member, io.BytesIO(raw))
        name = "../outside.py" if attack == "parent" else "equiframe-0.0.0/unsafe.py"
        if attack == "absolute":
            name = str(tmp_path / "outside.py")
        member = tarfile.TarInfo(name)
        if attack in ("symlink", "hardlink"):
            member.type = tarfile.SYMTYPE if attack == "symlink" else tarfile.LNKTYPE
            member.linkname = "../../outside.py"
            replacement.addfile(member)
        else:
            member.size = 4
            replacement.addfile(member, io.BytesIO(b"pass"))
    with pytest.raises(ValueError):
        runner["extract_sdist"](archive, tmp_path / "out", records(RUNTIME))
    assert not (tmp_path / "outside.py").exists()


@pytest.fixture
def installed(tmp_path):
    package = tmp_path / "installed" / "equiframe"
    for name, raw in RUNTIME.items():
        path = package.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return package


def test_installed_runtime_requires_complete_hash_and_size_inventory(probe, installed):
    expected = records(RUNTIME)
    result = probe["check_runtime_files"](installed, expected)
    assert result["verified"] is True
    assert result["files"] == expected
    assert Path(result["root"]) == installed.resolve()


@pytest.mark.parametrize("mutation", ["same-size", "missing", "extra", "hash", "size"])
def test_installed_runtime_substitution_cannot_pass_on_version_alone(probe, installed, mutation):
    expected = records(RUNTIME)
    if mutation == "same-size":
        (installed / "__init__.py").write_bytes(
            RUNTIME["equiframe/__init__.py"].replace(b"0", b"9")
        )
    elif mutation == "missing":
        (installed / "py.typed").unlink()
    elif mutation == "extra":
        (installed / "unrecorded.json").write_text("{}", encoding="utf-8")
    elif mutation == "hash":
        expected["equiframe/__init__.py"]["sha256"] = "0" * 64
    else:
        expected["equiframe/__init__.py"]["size_bytes"] += 1
    with pytest.raises(ValueError):
        probe["check_runtime_files"](installed, expected)


def test_only_bytecode_inside_pycache_is_ignored(probe, installed):
    cache = installed / "__pycache__"
    cache.mkdir()
    (cache / "__init__.cpython-312.pyc").write_bytes(b"synthetic compiled cache")
    assert probe["check_runtime_files"](installed, records(RUNTIME))["verified"] is True
    (cache / "unrecorded.py").write_text("UNTESTED = True\n", encoding="utf-8")
    with pytest.raises(ValueError):
        probe["check_runtime_files"](installed, records(RUNTIME))


def test_top_level_sourceless_bytecode_is_not_hidden_from_inventory(probe, installed):
    (installed / "unrecorded.pyc").write_bytes(b"synthetic sourceless payload")
    with pytest.raises(ValueError):
        probe["check_runtime_files"](installed, records(RUNTIME))


@pytest.mark.parametrize("target", ["__init__.py", "resources", "__pycache__"])
def test_runtime_symlinks_cannot_bypass_payload_comparison(probe, installed, tmp_path, target):
    linked = installed / target
    if linked.is_file():
        raw = linked.read_bytes()
        linked.unlink()
        outside = tmp_path / "outside.py"
        outside.write_bytes(raw)
    else:
        if linked.exists():
            (linked / "policy.json").unlink()
            linked.rmdir()
        outside = tmp_path / "outside"
        outside.mkdir()
    try:
        linked.symlink_to(outside, target_is_directory=outside.is_dir())
    except OSError as error:
        pytest.skip(f"host cannot create a symlink: {error}")
    with pytest.raises(ValueError):
        probe["check_runtime_files"](installed, records(RUNTIME))


@pytest.mark.parametrize("mutation", ["missing", "unexpected"])
def test_artifact_inventory_cannot_be_narrowed_or_expanded(runner, tmp_path, mutation):
    path = tmp_path / "candidate.whl"
    path.write_bytes(b"synthetic candidate")
    expected = {"wheel": runner["artifact_record"](path)}
    paths = {"wheel": path}
    if mutation == "missing":
        del paths["wheel"]
    else:
        paths["extra"] = path
    with pytest.raises(ValueError):
        runner["ensure_artifacts"](expected, paths)


@pytest.mark.parametrize(
    "requirement",
    [
        "equiframe>=0.11.1",
        "EquiFrame==0.11.1",
        "pydantic @ https://packages.example.invalid/pydantic.whl",
        "not a valid requirement!",
    ],
)
def test_dependency_metadata_cannot_replace_exact_candidate_or_supply_direct_urls(
    runner, tmp_path, requirement
):
    metadata = runner["wheel_metadata"](make_wheel(tmp_path))
    metadata["requires_dist"].append(requirement)
    with pytest.raises(ValueError):
        runner["profile_requirements"](metadata, "base", default_environment())


def test_all_profile_requires_the_complete_public_extra_surface(runner, tmp_path):
    metadata = runner["wheel_metadata"](make_wheel(tmp_path))
    metadata["extras"].remove("ml")
    with pytest.raises(ValueError):
        runner["profile_requirements"](metadata, "all", default_environment())


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_one_passing_case_does_not_hide_an_unexecuted_or_failing_case(runner, tmp_path, outcome):
    testcase_attributes = ' classname="compatibility"' if outcome == "skipped" else ""
    outcome_xml = (
        '<skipped message="unexpected skip"/>' if outcome == "skipped" else f"<{outcome}/>"
    )
    path = junit(
        tmp_path,
        '<testsuite tests="2"><testcase name="passed"/>'
        f'<testcase name="incomplete"{testcase_attributes}>{outcome_xml}'
        "</testcase></testsuite>",
    )
    result = runner["inspect_junit"](path)
    assert result["tests"] == 2
    assert result["accepted"] is False


def test_junit_testcase_cannot_have_conflicting_outcomes(runner, tmp_path):
    path = junit(
        tmp_path,
        '<testsuite tests="1"><testcase name="ambiguous">'
        "<skipped/><failure/></testcase></testsuite>",
    )
    with pytest.raises(ValueError):
        runner["inspect_junit"](path)


@pytest.mark.parametrize("versions", [{}, {"pydantic": "2.12.1"}])
def test_installed_dependency_version_drift_is_rejected(runner, versions):
    with pytest.raises(ValueError):
        runner["verify_versions"]({"pydantic": "2.12.0"}, {"versions": versions})


@pytest.fixture
def cell(runner, tmp_path):
    directory = tmp_path / "cell"
    directory.mkdir()
    artifact = tmp_path / "candidate.whl"
    artifact.write_bytes(b"synthetic candidate bytes")
    return runner["CellRunner"](directory, {"commands": []}, {"wheel": artifact}, timeout=3)


@pytest.mark.parametrize("expected_exit", [0, 1, 3])
def test_command_receipt_preserves_expected_semantic_exit_and_exact_logs(
    runner, cell, monkeypatch, expected_exit
):
    calls = []

    def execute(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, expected_exit, "synthetic stdout\n", "")

    monkeypatch.setattr(subprocess, "run", execute)
    command = ["synthetic-not-executed-python", "-I", "-m", "equiframe"]
    completed = cell.run(command, stage="semantic-case", expected_exit=expected_exit)
    assert completed.returncode == expected_exit
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 3
    assert calls[0][1]["env"]["PYTHONNOUSERSITE"] == "1"
    receipt = json.loads((cell.directory / "receipt.json").read_bytes())
    (entry,) = receipt["commands"]
    assert entry["command"] == command
    assert entry["exit_code"] == entry["expected_exit_code"] == expected_exit
    assert entry["stdout_artifact"] == runner["artifact_record"](Path(entry["stdout"]))
    assert Path(entry["stdout"]).read_text() == "synthetic stdout\n"
    assert entry["stderr_artifact"] == runner["artifact_record"](Path(entry["stderr"]))


@pytest.mark.parametrize("blocked", [False, True])
def test_failed_command_is_retained_before_failure_propagates(runner, cell, monkeypatch, blocked):
    def execute(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "partial progress\n", "synthetic failure\n")

    monkeypatch.setattr(subprocess, "run", execute)
    error = runner["CellBlocked"] if blocked else RuntimeError
    with pytest.raises(error, match="exited 1"):
        cell.run(["not-executed"], stage="synthetic-failure", blocked=blocked)
    receipt = json.loads((cell.directory / "receipt.json").read_bytes())
    (entry,) = receipt["commands"]
    assert entry["exit_code"] == 1
    assert Path(entry["stderr"]).read_text() == "synthetic failure\n"
    assert Path(entry["stdout"]).read_text() == "partial progress\n"
    assert entry["finished_at"]


def test_timeout_is_retained_as_no_exit_code_instead_of_success(cell, monkeypatch):
    def execute(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 3, output="partial progress", stderr="timed out")

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(RuntimeError, match="timed out"):
        cell.run(["not-executed"], stage="synthetic-timeout")
    receipt = json.loads((cell.directory / "receipt.json").read_bytes())
    (entry,) = receipt["commands"]
    assert entry["exit_code"] is None
    assert "error" in entry
    assert Path(entry["stdout"]).read_text() == "partial progress"
    assert Path(entry["stderr"]).read_text() == "timed out"


def test_successful_subprocess_cannot_hide_artifact_change_during_its_execution(cell, monkeypatch):
    def execute(command, **kwargs):
        cell.artifacts["wheel"].write_bytes(b"substituted candidate bytes")
        return subprocess.CompletedProcess(command, 0, "command completed\n", "")

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(ValueError, match="artifact bytes changed"):
        cell.run(["not-executed"], stage="synthetic-substitution")
    receipt = json.loads((cell.directory / "receipt.json").read_bytes())
    (entry,) = receipt["commands"]
    assert entry["exit_code"] == 0
    assert Path(entry["stdout"]).read_text() == "command completed\n"


@pytest.mark.parametrize("mutation", ["none", "changed", "missing", "extra"])
@pytest.mark.parametrize(
    "original,destination",
    [("docs", "equiframe/docs"), ("tools/cyclonedx", "equiframe/_vendor/cyclonedx")],
)
def test_sdist_resource_directory_is_compared_with_exact_wheel_payload(
    runner, tmp_path, mutation, original, destination
):
    config = (
        b'[project]\nname="equiframe"\n'
        + f'[tool.hatch.build.targets.wheel.force-include]\n"{original}"="{destination}"\n'.encode()
    )
    files = {"equiframe-0.0.0/src/" + name: raw for name, raw in RUNTIME.items()}
    files["equiframe-0.0.0/pyproject.toml"] = config
    files["equiframe-0.0.0/tests/test_synthetic.py"] = b"def test_ok(): assert True\n"
    if mutation != "missing":
        files[f"equiframe-0.0.0/{original}/index.md"] = (
            b"Changed" if mutation == "changed" else b"Handbook"
        )
    if mutation == "extra":
        files[f"equiframe-0.0.0/{original}/extra.md"] = b"Unexpected"
    wheel = records({**RUNTIME, destination + "/index.md": b"Handbook"})
    if mutation == "none":
        source = runner["extract_sdist"](make_sdist(tmp_path, files), tmp_path / "out", wheel)
        assert (source / original / "index.md").read_bytes() == b"Handbook"
    else:
        with pytest.raises(ValueError, match=r"handbook|runtime payload"):
            runner["extract_sdist"](make_sdist(tmp_path, files), tmp_path / "out", wheel)


@pytest.mark.parametrize("mutation", ["none", "missing", "changed"])
def test_sdist_journey_binding_matches_exact_installed_wheel_bytes(runner, tmp_path, mutation):
    project = (
        b'[project]\nname="equiframe"\nversion="0.0.0"\n'
        b"[tool.hatch.build.targets.wheel.force-include]\n"
        b'"examples/journeys/a_pandas_refactor.py" = '
        b'"equiframe/examples/journeys/a_pandas_refactor.py"\n'
    )
    payload = {
        "equiframe-0.0.0/pyproject.toml": project,
        "equiframe-0.0.0/tests/test_synthetic.py": b"def test_synthetic(): assert True\n",
        **{"equiframe-0.0.0/src/" + name: raw for name, raw in RUNTIME.items()},
    }
    original = b'EXPECTED = "synthetic"\n'
    if mutation != "missing":
        payload["equiframe-0.0.0/examples/journeys/a_pandas_refactor.py"] = (
            b"stale" if mutation == "changed" else original
        )
    expected = records({**RUNTIME, "equiframe/examples/journeys/a_pandas_refactor.py": original})
    if mutation == "none":
        source = runner["extract_sdist"](make_sdist(tmp_path, payload), tmp_path / "out", expected)
        assert (source / "examples/journeys/a_pandas_refactor.py").read_bytes() == original
    else:
        with pytest.raises(ValueError, match=r"source is absent|runtime payload"):
            runner["extract_sdist"](make_sdist(tmp_path, payload), tmp_path / "out", expected)


@pytest.mark.parametrize(
    "original,destination",
    [
        (
            "schemas/r-review-options-1.0.schema.json",
            "equiframe/schemas/r-review-options-1.0.schema.json",
        ),
        (
            "schemas/r-review-binding-1.0.schema.json",
            "equiframe/schemas/r-review-binding-1.0.schema.json",
        ),
        (
            "schemas/r-execution-binding-1.0.schema.json",
            "equiframe/schemas/r-execution-binding-1.0.schema.json",
        ),
        (
            "schemas/r-review-result-1.0.schema.json",
            "equiframe/schemas/r-review-result-1.0.schema.json",
        ),
        (
            "schemas/reviewed-decision-1.0.schema.json",
            "equiframe/schemas/reviewed-decision-1.0.schema.json",
        ),
        ("examples/eda_generic.py", "equiframe/examples/integrations/eda_generic.py"),
        ("examples/load_convert_compare.py", "equiframe/examples/load_convert_compare.py"),
    ],
)
@pytest.mark.parametrize("mutation", ["none", "missing", "changed", "extra", "remapped"])
def test_sdist_binds_only_exact_declared_resource_files(
    runner, tmp_path, original, destination, mutation
):
    declared = runner["tomllib"].loads((TOOLS.parent / "pyproject.toml").read_text("utf-8"))
    assert (
        declared["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"][original]
        == destination
    )
    mapped = destination if mutation != "remapped" else destination + ".remapped"
    project = (
        '[project]\nname="equiframe"\nversion="0.0.0"\n'
        f'[tool.hatch.build.targets.wheel.force-include]\n"{original}"="{mapped}"\n'
    ).encode()
    files = {
        "equiframe-0.0.0/pyproject.toml": project,
        "equiframe-0.0.0/tests/test_synthetic.py": b"def test_synthetic(): assert True\n",
        **{"equiframe-0.0.0/src/" + name: raw for name, raw in RUNTIME.items()},
    }
    content = b'{"kind":"fixture"}\n' if original.endswith(".json") else b'VALUE="fixture"\n'
    if mutation != "missing":
        files["equiframe-0.0.0/" + original] = b"stale" if mutation == "changed" else content
    wheel = records({**RUNTIME, mapped: content})
    if mutation == "extra":
        wheel.update(records({"equiframe/__pycache__/unexpected.pyc": b"cache"}))
    if mutation == "none":
        source = runner["extract_sdist"](make_sdist(tmp_path, files), tmp_path / "out", wheel)
        assert (source / original).read_bytes() == content
    else:
        message = (
            "unsupported wheel force-include mapping"
            if mutation == "remapped"
            else r"source is absent|runtime payload"
        )
        with pytest.raises(ValueError, match=message):
            runner["extract_sdist"](make_sdist(tmp_path, files), tmp_path / "out", wheel)


@pytest.mark.parametrize("namespace", ["journeys", "integrations"])
def test_sdist_rejects_coherent_undeclared_example_mappings(runner, tmp_path, namespace):
    original = f"examples/{namespace}/arbitrary.py"
    destination = "equiframe/" + original
    project = (
        '[project]\nname="equiframe"\nversion="0.0.0"\n'
        f'[tool.hatch.build.targets.wheel.force-include]\n"{original}"="{destination}"\n'
    ).encode()
    content = b'EXAMPLE = "coherent but undeclared"\n'
    files = {
        "equiframe-0.0.0/pyproject.toml": project,
        "equiframe-0.0.0/tests/test_synthetic.py": b"def test_synthetic(): assert True\n",
        "equiframe-0.0.0/" + original: content,
        **{"equiframe-0.0.0/src/" + name: raw for name, raw in RUNTIME.items()},
    }
    wheel = records({**RUNTIME, destination: content})
    with pytest.raises(ValueError, match="unsupported wheel force-include mapping"):
        runner["extract_sdist"](make_sdist(tmp_path, files), tmp_path / "out", wheel)
