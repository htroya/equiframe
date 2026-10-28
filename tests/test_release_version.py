"""Real temporary Git tags exercise dynamic metadata and Git-free sdist rebuilds."""

import json
import os
import runpy
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "release_version.py"))


def git(root: Path, *args: str) -> str:
    environment = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    process = subprocess.run(
        [
            "git",
            "-c",
            "user.name=synthetic-version-test",
            "-c",
            "user.email=synthetic-version@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.eol=lf",
            "-c",
            "core.hooksPath=" + str(root / ".git/no-hooks"),
            *args,
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout.strip()


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repository"
    package = root / "packages" / "sample"
    runtime = package / "src" / "sample"
    runtime.mkdir(parents=True)
    (runtime / "__init__.py").write_text("VALUE = 7\n", encoding="utf-8")
    (package / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires=["hatchling==1.28.0","hatch-vcs==0.5.0","setuptools-scm==10.3.4"]\n'
        'build-backend="hatchling.build"\n'
        '[project]\nname="equiframe-version-fixture"\ndynamic=["version"]\n'
        'requires-python=">=3.10"\n'
        '[tool.hatch.version]\nsource="vcs"\n'
        "tag-pattern='^v(?P<version>[0-9]+\\.[0-9]+\\.[0-9]+)$'\n"
        "[tool.hatch.version.raw-options]\nsearch_parent_directories=true\n"
        'version_scheme="no-guess-dev"\n'
        '[tool.hatch.build.targets.wheel]\npackages=["src/sample"]\n',
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("dist/\n", encoding="utf-8")
    git(root, "init", "--initial-branch=main")
    git(root, "add", ".")
    git(root, "commit", "-m", "Synthetic version fixture")
    return root, package


def test_exact_tag_resolves_nested_project_without_an_installed_distribution(
    source: tuple[Path, Path],
) -> None:
    root, package = source
    git(root, "tag", "v1.2.3")
    assert MODULE["project_version"](package, require_tag=True) == "1.2.3"
    assert not (package / "src/sample/_version.py").exists()


@pytest.mark.parametrize("tag", [None, "v01.2.3", "v1.2.3rc1", "release-1.2.3"])
def test_release_rejects_missing_or_non_semver_tag(
    source: tuple[Path, Path], tag: str | None
) -> None:
    root, package = source
    if tag is not None:
        git(root, "tag", tag)
    with pytest.raises(ValueError, match=r"exactly one vX\.Y\.Z"):
        MODULE["project_version"](package, require_tag=True)


def test_release_rejects_dirty_or_ambiguous_tagged_checkout(source: tuple[Path, Path]) -> None:
    root, package = source
    git(root, "tag", "v1.2.3")
    git(root, "tag", "v1.2.4")
    with pytest.raises(ValueError, match="exactly one"):
        MODULE["project_version"](package, require_tag=True)
    git(root, "tag", "-d", "v1.2.4")
    (package / "src/sample/__init__.py").write_text("VALUE = 8\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean Git"):
        MODULE["project_version"](package, require_tag=True)


def test_core_release_cannot_emit_an_older_detector_producer(source: tuple[Path, Path]) -> None:
    root, package = source
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text().replace('name="equiframe-version-fixture"', 'name="equiframe"')
    )
    producer = package / "src/equiframe/detector_types.py"
    producer.parent.mkdir()
    producer.write_text('class DetectorVersions:\n    equiframe: str = "1.2.3"\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "Synthetic explicit detector producer")
    git(root, "tag", "v1.2.4")
    with pytest.raises(ValueError, match="detector producer default differs"):
        MODULE["project_version"](package, require_tag=True)


@pytest.mark.parametrize(
    "key",
    [
        "SETUPTOOLS_SCM_PRETEND_VERSION",
        "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_SAMPLE",
        "SETUPTOOLS_SCM_OVERRIDES",
        "HATCH_BUILD_VERSION",
    ],
)
def test_release_rejects_environment_version_override(
    source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    root, package = source
    git(root, "tag", "v1.2.3")
    monkeypatch.setenv(key, "1.2.3")
    with pytest.raises(ValueError, match="overrides are forbidden"):
        MODULE["project_version"](package, require_tag=True)


def test_sdist_rebuild_without_git_keeps_the_exact_tagged_wheel(
    source: tuple[Path, Path], tmp_path: Path
) -> None:
    root, package = source
    git(root, "tag", "v1.2.3")
    environment = dict(os.environ, SOURCE_DATE_EPOCH="1704067200", PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-I", "-m", "build", "--no-isolation"]
    process = subprocess.run(command, cwd=package, env=environment, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    original = package / "dist/equiframe_version_fixture-1.2.3-py3-none-any.whl"
    wheel_bytes = original.read_bytes()
    with zipfile.ZipFile(original) as archive:
        metadata = BytesParser().parsebytes(
            archive.read("equiframe_version_fixture-1.2.3.dist-info/METADATA")
        )
        assert metadata["Version"] == "1.2.3"
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(package / "dist/equiframe_version_fixture-1.2.3.tar.gz") as archive:
        for member in archive.getmembers():
            destination = extracted / member.name
            assert destination.resolve().is_relative_to(extracted.resolve())
            assert not member.issym() and not member.islnk()
            if member.isfile():
                stream = archive.extractfile(member)
                assert stream is not None
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(stream.read())
    copied = extracted / "equiframe_version_fixture-1.2.3"
    assert not (copied / ".git").exists() and not (extracted / ".git").exists()
    assert MODULE["project_version"](copied) == "1.2.3"
    rebuilt = subprocess.run(
        [*command, "--wheel"], cwd=copied, env=environment, capture_output=True, text=True
    )
    assert rebuilt.returncode == 0, rebuilt.stderr
    assert (copied / "dist" / original.name).read_bytes() == wheel_bytes
    assert not list(copied.rglob("_version.py"))


def test_version_resolver_does_not_read_an_installed_distribution(
    source: tuple[Path, Path],
) -> None:
    _, package = source
    assert "equiframe-version-fixture" in (package / "pyproject.toml").read_text("utf-8")
    script = (
        "import json,runpy,importlib.metadata; "
        "importlib.metadata.version=lambda name: (_ for _ in ()).throw(AssertionError(name)); "
        "print(json.dumps(runpy.run_path(" + repr(MODULE["__file__"]) + ")['project_version']("
        "__import__('pathlib').Path(" + repr(str(package)) + "))))"
    )
    # This explicit override is only a metadata-resolution fixture; release mode rejects it.
    environment = dict(os.environ, SETUPTOOLS_SCM_PRETEND_VERSION="3.2.1")
    process = subprocess.run(
        [sys.executable, "-I", "-c", script], env=environment, capture_output=True, text=True
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == "3.2.1"
