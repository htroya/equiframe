"""Fake distributions/name observations; no publication, ownership or license decision."""

import hashlib
import json
import runpy
import stat
import subprocess
import sys
from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from pydantic import ValidationError

from equiframe_benchmark import distribution as module
from equiframe_benchmark.distribution import DistributionReadiness, NameCheck, inspect_distribution

UTC = _timezone.utc

PROJECT = """[project]
name = "unit-pkg"
version = "0.10.0"
requires-python = ">=3.12,<3.13"
readme = "README.md"
classifiers = ["Programming Language :: Python :: 3.12", "Typing :: Typed"]
dependencies = ["pydantic>=2.12,<3", "equiframe[arrow]==0.9.0"]
[project.optional-dependencies]
ml = ["equiframe[ml]==0.9.0"]
[project.urls]
Repository = "https://example.invalid/unit-source"
"""
METADATA = """Metadata-Version: 2.4
Name: UNIT.PKG
Version: 0.10.0
Requires-Python: <3.13,>=3.12
Requires-Dist: EquiFrame[arrow] == 0.9.0
Requires-Dist: pydantic<3,>=2.12
Requires-Dist: equiframe[ml]==0.9.0; extra == 'ml'
Provides-Extra: ml
Classifier: Programming Language :: Python :: 3.12
Classifier: Typing :: Typed
Project-URL: Repository, https://example.invalid/unit-source

Invented unit README, never an actual published package.
"""
WHEEL = """Wheel-Version: 1.0
Generator: invented-unit-fixture
Root-Is-Purelib: true
Tag: py3-none-any
"""
PREFIX = "unit_pkg-0.10.0.dist-info/"


def test_installed_test_staging_runs_the_delivered_asset_command(tmp_path):
    package = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(package / "tools" / "verify_distribution.py"))
    work = tmp_path / "installed-tests"
    work.mkdir()
    namespace["stage_installed_test_inputs"](package, work)
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(work / "tools" / "generate_assets.py"), "--check"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "58 benchmark schemas verified"
    assert not result.stderr.strip()


def source(tmp_path: Path, project: str = PROJECT) -> Path:
    package = tmp_path / "source"
    package.mkdir()
    (package / "pyproject.toml").write_text(project, encoding="utf-8")
    (package / "README.md").write_text("# Fake unit package\n", encoding="utf-8")
    (package / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    code = package / "src" / "unit_pkg"
    code.mkdir(parents=True)
    (code / "py.typed").write_bytes(b"")
    (code / "__init__.py").write_text(
        "raise RuntimeError('inventory must not execute me')\n", encoding="utf-8"
    )
    return package


def wheel(
    tmp_path: Path,
    metadata: str = METADATA,
    wheel_metadata: str = WHEEL,
    *,
    extra: dict[str, bytes] | None = None,
    typing: bool = True,
) -> Path:
    path = tmp_path / "unit_pkg-0.10.0-py3-none-any.whl"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(PREFIX + "METADATA", metadata)
        archive.writestr(PREFIX + "WHEEL", wheel_metadata)
        archive.writestr(PREFIX + "RECORD", "")
        archive.writestr("unit_pkg/__init__.py", "raise RuntimeError('must not import')")
        if typing:
            archive.writestr("unit_pkg/py.typed", "")
        for name, payload in (extra or {}).items():
            archive.writestr(name, payload)
    return path


def observation(
    *,
    status: str = "unknown",
    http_status: int | None = None,
    controlled: bool = False,
    evidence: str | None = None,
) -> NameCheck:
    return NameCheck(
        name="unit-pkg",
        query_url="https://pypi.org/pypi/unit-pkg/json",
        fetched_at=datetime(2026, 10, 2, tzinfo=UTC) if http_status is not None else None,
        http_status=http_status,
        status=status,
        controlled=controlled,
        control_evidence=evidence,
    )


def test_local_inventory_records_actual_hashes_without_publication_claim(tmp_path):
    package = source(tmp_path)
    result = inspect_distribution(package)
    assert result.project.name == "unit-pkg"
    assert result.project.requires_python == "<3.13,>=3.12"
    assert result.project.dependencies == ("equiframe[arrow]==0.9.0", "pydantic<3,>=2.12")
    assert result.project.typed_markers == ("src/unit_pkg/py.typed",)
    assert result.source_available and result.technical_inventory_complete
    assert not result.publication_ready and not result.build_install_verified
    assert not result.wheel_metadata_verified
    assert result.name_check.status == "unknown"
    assert "pending_license" in result.pending_conditions
    assert "pending_pypi_name_control" in result.pending_conditions
    assert "pending_current_release_platform_matrix" in result.pending_conditions
    assert "pending_build_install_verification" in result.pending_conditions
    for item in result.source_files:
        data = package.joinpath(item.relative_path).read_bytes()
        assert item.sha256 == hashlib.sha256(data).hexdigest()
        assert item.size_bytes == len(data)
    assert DistributionReadiness.model_validate_json(result.model_dump_json()) == result
    assert inspect_distribution(package) == result


def test_wheel_matches_normalized_name_versions_specifier_order_and_optional_extras(tmp_path):
    result = inspect_distribution(source(tmp_path), wheel(tmp_path))
    assert result.wheel is not None and result.wheel_metadata_verified
    assert result.wheel.canonical_name == "unit-pkg"
    assert result.wheel.version == "0.10.0"
    assert result.wheel.extras == ("ml",)
    assert result.wheel.tags == ("py3-none-any",)
    assert "pending_wheel_metadata" not in result.pending_conditions
    assert result.publication_ready is False and result.build_install_verified is False


@pytest.mark.parametrize("status,code", [("not_found", 404), ("exists", 200), ("unknown", 503)])
def test_http_responses_do_not_reserve_or_control_a_name(tmp_path, status, code):
    result = inspect_distribution(
        source(tmp_path), name_check=observation(status=status, http_status=code)
    )
    assert result.name_check.controlled is False
    assert "pending_pypi_name_control" in result.pending_conditions
    assert result.publication_ready is False


def test_asserted_control_requires_separate_declared_evidence_but_not_release_approval(tmp_path):
    check = observation(
        status="exists",
        http_status=200,
        controlled=True,
        evidence="Fake unit evidence, not a real PyPI account/control proof.",
    )
    result = inspect_distribution(source(tmp_path), name_check=check)
    assert "pending_pypi_name_control" not in result.pending_conditions
    assert "pending_license" in result.pending_conditions
    assert "pending_current_release_platform_matrix" in result.pending_conditions
    assert not result.publication_ready
    with pytest.raises(ValidationError, match="separate evidence"):
        observation(status="not_found", http_status=404, controlled=True, evidence="unit")
    with pytest.raises(ValidationError, match="separate evidence"):
        observation(status="exists", http_status=200, controlled=True)


@pytest.mark.parametrize(
    "changes",
    [
        {"query_url": "https://pypi.org/project/other/"},
        {"query_url": "https://evil.invalid/pypi/unit-pkg/json"},
        {"query_url": "https://user:secret@pypi.org/pypi/unit-pkg/json"},
        {"http_status": "404"},
        {"controlled": "yes"},
        {"status": "exists"},
        {"fetched_at": datetime(2026, 10, 2)},
    ],
)
def test_name_observation_schema_rejects_coercion_wrong_url_and_missing_evidence(changes):
    data = observation().model_dump()
    data.update(changes)
    with pytest.raises(ValidationError):
        NameCheck.model_validate(data)


def test_name_observation_from_another_project_is_rejected(tmp_path):
    check = NameCheck(
        name="other",
        query_url="https://pypi.org/pypi/other/json",
        fetched_at=None,
        http_status=None,
        status="unknown",
    )
    with pytest.raises(ValidationError, match="different distribution"):
        inspect_distribution(source(tmp_path), name_check=check)


@pytest.mark.parametrize(
    "old,new",
    [
        ("Name: UNIT.PKG", "Name: wrong-project"),
        ("Version: 0.10.0", "Version: 0.11.0"),
        ("equiframe[arrow]==0.9.0", "equiframe[arrow]==0.8.1"),
        ("equiframe[ml]==0.9.0", "equiframe[engines]==0.9.0"),
        ("pydantic<3,>=2.12", "pydantic<3,>=2.11"),
        ("Requires-Python: <3.13,>=3.12", "Requires-Python: >=3.8"),
        ("Provides-Extra: ml", "Provides-Extra: resources"),
        ("Programming Language :: Python :: 3.12", "Programming Language :: Python :: 3.13"),
        ("https://example.invalid/unit-source", "https://example.invalid/forged-source"),
    ],
)
def test_forged_wheel_metadata_dependencies_python_support_and_identity_fail(tmp_path, old, new):
    # Match both spaced and canonical requirement spelling in hand-written metadata.
    altered = METADATA.replace("EquiFrame[arrow] == 0.9.0", "equiframe[arrow]==0.9.0")
    assert old in altered
    with pytest.raises(ValueError):
        inspect_distribution(source(tmp_path), wheel(tmp_path, altered.replace(old, new)))


def test_missing_wheel_typing_marker_fails_even_if_classifier_claims_typed(tmp_path):
    with pytest.raises(ValueError, match="typing markers"):
        inspect_distribution(source(tmp_path), wheel(tmp_path, typing=False))


@pytest.mark.parametrize(
    "metadata",
    [
        METADATA.replace("Metadata-Version: 2.4", "Metadata-Version: 3.0"),
        METADATA.replace("Version: 0.10.0", "Version: 0.10.0\nVersion: 0.10.0"),
        METADATA.replace("Name: UNIT.PKG\n", ""),
        METADATA.replace("Requires-Dist: pydantic<3,>=2.12", "Requires-Dist: ???"),
        METADATA.replace("Requires-Python: <3.13,>=3.12", "Requires-Python: potato"),
    ],
)
def test_invalid_metadata_schema_rejected(tmp_path, metadata):
    with pytest.raises(ValueError):
        inspect_distribution(source(tmp_path), wheel(tmp_path, metadata))


@pytest.mark.parametrize(
    "payload",
    [
        WHEEL.replace("1.0", "2.0"),
        WHEEL.replace("Root-Is-Purelib: true", "Root-Is-Purelib: yes"),
        WHEEL.replace("py3-none-any", "cp312-none-win_amd64"),
        WHEEL.replace("Tag: py3-none-any\n", ""),
    ],
)
def test_wheel_schema_and_filename_tag_disagreements_are_rejected(tmp_path, payload):
    with pytest.raises(ValueError):
        inspect_distribution(source(tmp_path), wheel(tmp_path, wheel_metadata=payload))


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "/absolute.py",
        "C:/drive.py",
        "unit_pkg\\backslash.py",
        "unit_pkg//ambiguous.py",
    ],
)
def test_zip_unsafe_member_paths_fail_without_extracting(tmp_path, path):
    package = source(tmp_path)
    archive = wheel(tmp_path, extra={path: b"never execute"})
    if "\\" in path:
        # ZipFile's writer normalizes Windows separators. Forge the local and
        # central header spelling explicitly to test the hostile archive itself.
        archive.write_bytes(
            archive.read_bytes().replace(
                path.replace("\\", "/").encode(),
                path.encode(),
            )
        )
    with pytest.raises(ValueError, match="inside their source/archive root"):
        inspect_distribution(package, archive)
    assert not (tmp_path / "outside.py").exists()


def test_zip_duplicate_and_symlink_entries_fail(tmp_path):
    package = source(tmp_path)
    path = wheel(tmp_path)
    with ZipFile(path, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
        archive.writestr("unit_pkg/py.typed", "")
    with pytest.raises(ValueError, match="duplicate paths"):
        inspect_distribution(package, path)


def test_zip_raw_nul_spelling_is_not_hidden_by_zipinfo_truncation(tmp_path):
    package = source(tmp_path)
    path = wheel(tmp_path, extra={"unit_pkg/nulx.py": b"never execute"})
    path.write_bytes(path.read_bytes().replace(b"unit_pkg/nulx.py", b"unit_pkg/nu\x00x.py"))
    with pytest.raises(ValueError, match="inside their source/archive root"):
        inspect_distribution(package, path)


def test_source_total_budget_prevents_hashing_beyond_its_remaining_limit(tmp_path, monkeypatch):
    package = source(tmp_path)
    monkeypatch.setattr(module, "MAX_SOURCE_TOTAL", 64)
    with pytest.raises(ValueError, match="size limit"):
        inspect_distribution(package)


def test_zip_symlink_entry_is_rejected(tmp_path):
    package = source(tmp_path)
    path = wheel(tmp_path)
    entry = ZipInfo("unit_pkg/link")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(path, "a") as archive:
        archive.writestr(entry, "../outside")
    with pytest.raises(ValueError, match="symlink"):
        inspect_distribution(package, path)


def test_zip_entry_count_and_expanded_size_limits_are_checked_before_reading_code(
    tmp_path, monkeypatch
):
    package = source(tmp_path)
    path = wheel(tmp_path, extra={f"unit_pkg/file{i}": b"x" for i in range(10)})
    monkeypatch.setattr(module, "MAX_MEMBERS", 8)
    with pytest.raises(ValueError, match="member count"):
        inspect_distribution(package, path)
    monkeypatch.setattr(module, "MAX_MEMBERS", 10000)
    monkeypatch.setattr(module, "MAX_ARCHIVE_EXPANDED", 25)
    with pytest.raises(ValueError, match="expanded size"):
        inspect_distribution(package, path)


def test_oversized_wheel_metadata_is_rejected_without_loading_payload(tmp_path):
    metadata = METADATA + ("x" * (module.MAX_METADATA_BYTES + 1))
    with pytest.raises(ValueError, match="metadata exceeds"):
        inspect_distribution(source(tmp_path), wheel(tmp_path, metadata))


def test_missing_readme_lock_and_typing_are_real_pending_conditions(tmp_path):
    package = source(tmp_path)
    (package / "README.md").unlink()
    (package / "uv.lock").unlink()
    (package / "src/unit_pkg/py.typed").unlink()
    result = inspect_distribution(package)
    assert not result.technical_inventory_complete
    assert result.lock_sha256 is None
    assert {"pending_readme", "pending_lock", "pending_typing_marker"} <= set(
        result.pending_conditions
    )


def test_license_inventory_checks_regular_files_but_does_not_choose_project_license(tmp_path):
    project = PROJECT.replace(
        'readme = "README.md"', 'readme = "README.md"\nlicense = "MIT"\nlicense-files = ["LICENSE"]'
    )
    package = source(tmp_path, project)
    result = inspect_distribution(package)
    assert result.project.license.expression == "MIT"
    assert "pending_license" in result.pending_conditions
    (package / "LICENSE").mkdir()
    with pytest.raises(ValueError, match="regular files"):
        inspect_distribution(package)
    (package / "LICENSE").rmdir()
    (package / "LICENSE").write_text("Invented test text, not a license granted for EquiFrame.\n")
    result = inspect_distribution(package)
    assert result.project.license_files == ("LICENSE",)
    assert "pending_license" not in result.pending_conditions
    assert result.publication_ready is False


@pytest.mark.parametrize(
    "change",
    [
        "name = 1",
        "version = 1",
        "requires-python = 3.12",
        "dependencies = [1]",
        'readme = "../README.md"',
        'license-files = ["../LICENSE"]',
    ],
)
def test_invalid_source_schema_and_paths_are_rejected(tmp_path, change):
    key = change.split(" = ", 1)[0]
    lines = [line for line in PROJECT.splitlines() if not line.startswith(key + " = ")]
    lines.insert(1, change)
    with pytest.raises(ValueError):
        inspect_distribution(source(tmp_path, "\n".join(lines)))


def test_dynamic_metadata_is_not_executed_or_presented_as_verified(tmp_path):
    project = PROJECT.replace('version = "0.10.0"', 'dynamic = ["version"]')
    with pytest.raises(ValueError, match="without executing a backend"):
        inspect_distribution(source(tmp_path, project))


@pytest.mark.parametrize(
    ("identified_by", "newline"),
    [
        pytest.param("wheel", "\n", id="wheel"),
        pytest.param("pkg_info", "\n", id="pkg-info-lf"),
        pytest.param("pkg_info", "\r\n", id="pkg-info-crlf"),
        pytest.param("both", "\n", id="both-lf"),
        pytest.param("both", "\r\n", id="both-crlf"),
    ],
)
def test_dynamic_version_uses_identified_passive_metadata_without_executing_code(
    tmp_path, identified_by, newline
):
    project = PROJECT.replace('version = "0.10.0"', 'dynamic = ["version"]')
    package = source(tmp_path, project)
    metadata_bytes = METADATA.replace("\n", newline).encode("utf-8")
    if identified_by in {"pkg_info", "both"}:
        (package / "PKG-INFO").write_bytes(metadata_bytes)
    identified = wheel(tmp_path) if identified_by in {"wheel", "both"} else None
    result = inspect_distribution(package, identified)
    assert result.project.version == "0.10.0"
    assert result.wheel_metadata_verified is (identified is not None)
    assert result.publication_ready is False and result.build_install_verified is False
    assert "pending_build_install_verification" in result.pending_conditions
    if identified_by in {"pkg_info", "both"}:
        record = next(item for item in result.source_files if item.relative_path == "PKG-INFO")
        assert record.sha256 == hashlib.sha256(metadata_bytes).hexdigest()
        assert record.size_bytes == len(metadata_bytes)
        if newline == "\r\n":
            assert record.sha256 != hashlib.sha256(METADATA.encode("utf-8")).hexdigest()
    if identified is None:
        assert "pending_wheel_metadata" in result.pending_conditions


@pytest.mark.parametrize(
    "old,new",
    [
        ("Name: UNIT.PKG", "Name: other-name"),
        ("Version: 0.10.0", "Version: 0.11.0"),
        ("Version: 0.10.0", "Version: 0.10.0\nVersion: 0.10.0"),
        ("Requires-Python: <3.13,>=3.12", "Requires-Python: >=3.13"),
        ("pydantic<3,>=2.12", "pydantic>=3"),
        ("Metadata-Version: 2.4", "Metadata-Version: 99.0"),
        ("Metadata-Version: 2.4", "Metadata-Version: 2.4\nDynamic: Version"),
    ],
)
def test_dynamic_version_rejects_conflicting_or_unresolved_passive_metadata(tmp_path, old, new):
    project = PROJECT.replace('version = "0.10.0"', 'dynamic = ["version"]')
    package = source(tmp_path, project)
    (package / "PKG-INFO").write_text(METADATA.replace(old, new), encoding="utf-8")
    with pytest.raises(ValueError):
        inspect_distribution(package, wheel(tmp_path))


def test_dynamic_version_rejects_an_identified_wheel_for_another_project(tmp_path):
    project = PROJECT.replace('version = "0.10.0"', 'dynamic = ["version"]').replace(
        'name = "unit-pkg"', 'name = "other-pkg"'
    )
    with pytest.raises(ValueError, match="wheel name disagrees"):
        inspect_distribution(source(tmp_path, project), wheel(tmp_path))


def test_dynamic_sdist_does_not_claim_an_unverified_legacy_license_text(tmp_path):
    project = PROJECT.replace('version = "0.10.0"', 'dynamic = ["version"]').replace(
        'readme = "README.md"', 'readme = "README.md"\nlicense = {file = "LICENSE"}'
    )
    package = source(tmp_path, project)
    (package / "LICENSE").write_text("Declared fixture license text.\n", encoding="utf-8")
    metadata = METADATA.replace(
        "Metadata-Version: 2.4",
        "Metadata-Version: 2.4\nLicense-File: LICENSE\nLicense: Unverified different text",
    )
    (package / "PKG-INFO").write_text(metadata, encoding="utf-8")
    with pytest.raises(ValueError, match="sdist license metadata disagrees"):
        inspect_distribution(package)


@pytest.mark.parametrize(
    "part",
    ["source_hash", "lock_hash", "pending", "publication", "build", "readme_schema", "wheel_name"],
)
def test_corrupted_or_overclaiming_inventory_json_is_rejected(tmp_path, part):
    result = inspect_distribution(source(tmp_path), wheel(tmp_path))
    data = json.loads(result.model_dump_json())
    if part == "source_hash":
        data["source_manifest_sha256"] = "0" * 64
    elif part == "lock_hash":
        data["lock_sha256"] = "0" * 64
    elif part == "pending":
        data["pending_conditions"] = []
    elif part == "publication":
        data["publication_ready"] = True
    elif part == "readme_schema":
        data["project"]["readme"]["file"] = None
    elif part == "wheel_name":
        data["wheel"]["name"] = "invented-forgery"
    else:
        data["build_install_verified"] = True
    with pytest.raises(ValidationError):
        DistributionReadiness.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("package_name", ["equiframe", "equiframe-benchmark"])
def test_actual_repository_inventory_reports_pending_publication_without_importing_it(
    package_name, source_packages
):
    package = source_packages[package_name]
    before = (package / "pyproject.toml").read_bytes()
    if 'dynamic = ["version"]' in before.decode("utf-8"):
        # A source checkout alone cannot attest a dynamic release identity.
        with pytest.raises(ValueError, match="dynamic version requires identified wheel"):
            inspect_distribution(package)
        assert (package / "pyproject.toml").read_bytes() == before
        return
    result = inspect_distribution(package)
    assert result.project.canonical_name == package_name
    assert result.project.license is not None
    assert result.project.license.expression == (
        "MIT AND Apache-2.0" if package_name == "equiframe" else "MIT"
    )
    assert {"LICENSE", "THIRD_PARTY_NOTICES.md"}.issubset(result.project.license_files)
    assert "pending_license" not in result.pending_conditions
    assert "pending_pypi_name_control" in result.pending_conditions
    assert "pending_current_release_platform_matrix" in result.pending_conditions
    assert result.publication_ready is False
    assert (package / "pyproject.toml").read_bytes() == before
