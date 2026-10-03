"""Release declarations cannot turn incomplete checks into verified execution.

These fixtures use synthetic distribution bytes and declared command records.
They exercise manifest validation, never authenticate a build or a human actor.
Only temporary Git repositories are created and committed.
"""

import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "release_manifest.py"))
STAGES = MODULE["REQUIRED_CHECK_STAGES"]


def git(directory: Path, *arguments: str) -> str:
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=synthetic-test-actor",
            "-c",
            "user.email=synthetic-test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=" + str(directory / ".git" / "no-hooks"),
            *arguments,
        ],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def synthetic_package(package: Path) -> tuple[Path, Path]:
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        '[project]\nname="synthetic-release-check"\nversion="0.0.0"\n'
        'requires-python=">=3.12,<3.13"\n',
        encoding="utf-8",
    )
    (package / "README.md").write_text("Synthetic manifest test.\n", encoding="utf-8")
    dist = package / "dist"
    dist.mkdir()
    artifacts = (
        dist / "synthetic_release_check-0.0.0-py3-none-any.whl",
        dist / "synthetic_release_check-0.0.0.tar.gz",
    )
    for artifact in artifacts:
        artifact.write_bytes(
            b"synthetic bytes; not a built distribution: " + artifact.name.encode()
        )
    return artifacts


@pytest.fixture
def package(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    root = repository / "packages" / "synthetic"
    synthetic_package(root)
    (repository / ".gitignore").write_text("dist/\n.venv/\n", encoding="utf-8")
    git(repository, "init", "-q")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "synthetic source declaration")
    ignored = root / ".venv" / "runtime.txt"
    ignored.parent.mkdir()
    ignored.write_text("ignored synthetic runtime", encoding="utf-8")
    return root


def declared_commands(package: Path) -> list[list[str]]:
    """All nine declarations; no command in this list is executed by these tests."""
    base = ["uv", "run", "--locked", "--all-extras"]
    artifacts = sorted((package / "dist").iterdir())
    return [
        ["uv", "sync", "--locked", "--all-extras", "--python", "3.12"],
        [*base, "ruff", "check", "."],
        [*base, "ruff", "format", "--check", "."],
        [*base, "mypy"],
        [*base, "python", "tools/generate_assets.py", "--check"],
        [*base, "pytest", "-q"],
        [*base, "python", "-m", "build", "--no-isolation"],
        [*base, "twine", "check", "--strict", *(str(path) for path in artifacts)],
        [*base, "python", "tools/verify_distribution.py", "--uv", "uv"],
    ]


def receipt(
    path: Path,
    package: Path,
    commands: list[list[str]],
    *,
    failed: int | None = None,
    cwd: Path | None = None,
) -> Path:
    results = [
        {"command": command, "exit_code": 1 if index == failed else 0, "cwd": str(cwd or package)}
        for index, command in enumerate(commands)
    ]
    path.write_text(
        json.dumps(
            {
                "environment": {"purpose": "synthetic declarations, execution not authenticated"},
                "results": results,
            }
        ),
        encoding="utf-8",
    )
    return path


def manifest(
    monkeypatch: pytest.MonkeyPatch,
    package: Path,
    output: Path,
    checks: Path | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    arguments = ["release_manifest.py", "--package", str(package), "--output", str(output)]
    if checks is not None:
        arguments += ["--checks", str(checks)]
    if commit is not None:
        arguments += ["--commit", commit]
    monkeypatch.setattr(sys, "argv", arguments)
    MODULE["main"]()
    return json.loads(output.read_bytes())


def test_clean_git_head_and_complete_declarations_identify_current_bytes(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    # Ignored artifacts/runtime do not make the source package dirty.
    assert git(package, "status", "--porcelain", "--untracked-files=all") == ""
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["source_commit"] == git(package, "rev-parse", "HEAD")
    assert result["source_validation"] == {
        "git_head": result["source_commit"],
        "package_clean": True,
        "project_tracked": True,
    }
    assert result["check_completion"]["successful_stages"] == list(STAGES)
    assert result["check_completion"]["missing_stages"] == []
    assert not result["check_completion"]["receipts_authenticated"]
    assert result["published"] is False and result["publication_blockers"]
    assert "not authenticated" in result["evidence_scope"]["artifacts"]
    for item in result["artifacts"]:
        raw = (package / "dist" / item["file"]).read_bytes()
        assert item["sha256"] == hashlib.sha256(raw).hexdigest()
        assert item["size_bytes"] == len(raw)


def test_nonexistent_commit_cannot_identify_artifacts(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit, match="Git HEAD exactly"):
        manifest(monkeypatch, package, tmp_path / "manifest.json", commit="0" * 40)
    assert not (tmp_path / "manifest.json").exists()


def test_real_previous_commit_cannot_identify_current_head(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = git(package, "rev-parse", "HEAD")
    (package / "README.md").write_text("New synthetic source.\n", encoding="utf-8")
    git(package, "add", "README.md")
    git(package, "commit", "-qm", "changed source declaration")
    with pytest.raises(SystemExit, match="Git HEAD exactly"):
        manifest(monkeypatch, package, tmp_path / "manifest.json", commit=previous)


@pytest.mark.parametrize("kind", ["tracked", "untracked"])
def test_changed_package_is_rejected(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    changed = package / ("README.md" if kind == "tracked" else "new-source.py")
    changed.write_text("changed synthetic source\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="tracked changes or untracked source"):
        manifest(monkeypatch, package, tmp_path / "manifest.json")


def test_package_outside_git_is_explicitly_unverified_and_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "not-in-git"
    synthetic_package(package)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with pytest.raises(SystemExit, match="Git source cannot be verified"):
        manifest(monkeypatch, package, tmp_path / "manifest.json")


def test_one_successful_unrelated_command_does_not_satisfy_release_checks(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(tmp_path / "checks.json", package, [["python", "--version"]])
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == list(STAGES)
    assert any("missing stages:" in blocker for blocker in result["publication_blockers"])
    assert not result["published"]


def test_receipt_from_another_package_cannot_be_reused(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(
        tmp_path / "checks.json", package, declared_commands(package), cwd=package.parent
    )
    with pytest.raises(SystemExit, match="cwd must identify the verified package exactly"):
        manifest(monkeypatch, package, tmp_path / "manifest.json", checks)


@pytest.mark.parametrize("omitted", range(9), ids=STAGES)
def test_each_missing_release_stage_remains_a_publication_blocker(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, omitted: int
) -> None:
    commands = declared_commands(package)
    commands.pop(omitted)
    checks = receipt(tmp_path / "checks.json", package, commands)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == [STAGES[omitted]]
    assert any(
        "missing stages: " + STAGES[omitted] in blocker
        for blocker in result["publication_blockers"]
    )


@pytest.mark.parametrize(
    "selection",
    [
        ["tests/test_only_one_file.py"],
        ["-k", "only_some_cases"],
        ["-m", "unit"],
        ["--collect-only"],
        ["--ignore", "tests/test_large_part.py"],
        ["--lf"],
    ],
)
def test_selected_or_unexecuted_pytest_does_not_count_as_the_whole_suite(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: list[str]
) -> None:
    commands = declared_commands(package)
    commands[5] += selection
    checks = receipt(tmp_path / "checks.json", package, commands)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == ["pytest"]


def test_operational_pytest_flags_and_python_module_still_cover_the_whole_suite(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands = declared_commands(package)
    commands[5] = [
        sys.executable,
        "-I",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(tmp_path / "separate-pytest"),
        "--tb=short",
        "-x",
        "tests",
    ]
    checks = receipt(tmp_path / "checks.json", package, commands)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == []


def test_twine_must_cover_both_identified_artifacts(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands = declared_commands(package)
    commands[7].pop()
    checks = receipt(tmp_path / "checks.json", package, commands)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == ["twine"]


def test_failed_command_does_not_become_a_successful_stage(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package), failed=5)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == ["pytest"]
    assert result["check_completion"]["failed_commands"] == 1
    assert any("failed command" in blocker for blocker in result["publication_blockers"])


def test_partial_checks_do_not_satisfy_the_declared_full_release_stages(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = ["uv", "run", "--locked", "--all-extras"]
    commands = declared_commands(package)
    commands[0] = ["uv", "sync", "--frozen", "--all-extras"]
    commands[1] = [*base, "ruff", "check", "src"]
    commands[2] = [*base, "ruff", "format", "."]
    commands[3] = [*base, "mypy", "src"]
    commands[4] = [*base, "python", "tools/generate_assets.py"]
    commands[6] = [*base, "python", "-m", "build", "--no-isolation", "--wheel"]
    commands[7].remove("--strict")
    commands[8] = [*base, "python", "other-package/tools/verify_distribution.py"]
    checks = receipt(tmp_path / "checks.json", package, commands)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["successful_stages"] == ["pytest"]
    assert result["check_completion"]["missing_stages"] == [x for x in STAGES if x != "pytest"]


def test_internal_stage_names_cannot_replace_the_actual_tools(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands = declared_commands(package)
    commands[0] = ["python", "-m", "locked_sync", "--locked", "--all-extras"]
    commands[4] = ["assets", "--check"]
    commands[8] = ["distribution"]
    checks = receipt(tmp_path / "checks.json", package, commands)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["missing_stages"] == ["locked_sync", "assets", "distribution"]


@pytest.mark.parametrize("artifact", ["*.whl", "*.tar.gz"])
def test_missing_identified_artifact_is_rejected(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    next((package / "dist").glob(artifact)).unlink()
    with pytest.raises(SystemExit, match="build the identified wheel and sdist first"):
        manifest(monkeypatch, package, tmp_path / "manifest.json")
