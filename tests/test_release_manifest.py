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


def test_root_package_snapshot_binds_git_root_and_rejects_changed_bytes(tmp_path: Path) -> None:
    repository = tmp_path / "root-project"
    synthetic_package(repository)
    (repository / ".gitignore").write_text("dist/\n", encoding="utf-8")
    git(repository, "init", "-q")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "synthetic root package")
    assert MODULE["repository_root"](repository) == repository.resolve()
    before = MODULE["source_snapshot"](repository)
    assert before["packages"] == ["."]
    assert before["file_count"] == 3
    MODULE["require_canonical_git_bytes"](repository)
    (repository / "README.md").write_text("Changed root source.\n", encoding="utf-8")
    assert MODULE["source_snapshot"](repository)["sha256"] != before["sha256"]
    with pytest.raises(SystemExit, match="raw worktree bytes differ"):
        MODULE["require_canonical_git_bytes"](repository)


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
    bound: bool = True,
) -> Path:
    results = [
        {"command": command, "exit_code": 1 if index == failed else 0, "cwd": str(cwd or package)}
        for index, command in enumerate(commands)
    ]
    if bound:
        snapshot = MODULE["source_snapshot"](package)
        artifacts = MODULE["artifact_inventory"](tuple(sorted((package / "dist").iterdir())))
        dependencies = MODULE["artifact_inventory"](MODULE["dependency_artifacts"](package))
        for result in results:
            result.update(
                source_before=snapshot,
                source_after=snapshot,
                artifacts=artifacts,
                artifacts_before=artifacts,
                dependency_artifacts=dependencies,
                dependency_artifacts_before=dependencies,
            )
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
    assert result["check_completion"]["source_bound_stages"] == list(STAGES)
    assert result["check_completion"]["unbound_stages"] == []
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


def test_manifest_cannot_overwrite_an_artifact(
    package: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = next((package / "dist").glob("*.whl"))
    original = artifact.read_bytes()
    with pytest.raises(SystemExit) as stopped:
        manifest(monkeypatch, package, artifact)
    assert stopped.value.code == 2
    assert artifact.read_bytes() == original
    captured = capsys.readouterr()
    assert "new writable file" in captured.err and not captured.out


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ([], "distribution"),
        (["--uv", "uv"], "distribution"),
        (["--uv", "uv", "--qa-workspace", "/temporary/qa"], "distribution"),
        (["--qa-workspace", "--skip-tests"], None),
        (["--uv", "uv", "--skip-tests"], None),
        (["--qa-workspace", "/temporary/qa", "--qa-workspace", "/other"], None),
    ],
)
def test_distribution_operational_workspace_never_selects_or_skips_checks(
    package: Path, arguments: list[str], expected: str | None
) -> None:
    artifacts = tuple(sorted((package / "dist").iterdir()))
    command = ["python", "tools/verify_distribution.py", *arguments]
    assert MODULE["check_stage"](command, package, artifacts) == expected


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


def test_legacy_receipts_remain_readable_without_claiming_current_source_validation(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package), bound=False)
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["successful_stages"] == list(STAGES)
    assert result["check_completion"]["source_bound_stages"] == []
    assert result["check_completion"]["unbound_stages"] == list(STAGES)
    assert any("not bound to current" in value for value in result["publication_blockers"])


def test_previous_source_receipts_do_not_validate_new_clean_commit(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    (package / "README.md").write_text("Changed after all recorded checks.\n", encoding="utf-8")
    git(package, "add", "README.md")
    git(package, "commit", "-qm", "new unchecked source")
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["unbound_stages"] == list(STAGES)


def test_source_changed_during_command_does_not_validate_its_stage(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    document = json.loads(checks.read_bytes())
    document["results"][5]["source_after"]["sha256"] = "0" * 64
    checks.write_text(json.dumps(document), encoding="utf-8")
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["unbound_stages"] == ["pytest"]


@pytest.mark.parametrize("changed", ["*.whl", "*.tar.gz"])
def test_replaced_artifact_invalidates_build_metadata_and_installation_receipts(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    next((package / "dist").glob(changed)).write_bytes(b"replacement not previously checked")
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["unbound_stages"] == ["build", "twine", "distribution"]


def test_local_dependency_worktree_is_included_in_tested_source(package: Path) -> None:
    dependency = package.parent / "dependency"
    synthetic_package(dependency)
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8")
        + '\n[tool.uv.sources]\ndependency = { path = "../dependency" }\n',
        encoding="utf-8",
    )
    git(package, "add", "..")
    git(package, "commit", "-qm", "local dependency")
    before = MODULE["source_snapshot"](package)
    (dependency / "README.md").write_text("Changed dependency.\n", encoding="utf-8")
    after = MODULE["source_snapshot"](package)
    assert before["packages"] == ["packages/dependency", "packages/synthetic"]
    assert before["sha256"] != after["sha256"]
    assert before["file_count"] == after["file_count"]


def test_new_source_file_changes_snapshot_but_ignored_runtime_does_not(package: Path) -> None:
    before = MODULE["source_snapshot"](package)
    (package / ".venv" / "runtime.txt").write_text("different runtime", encoding="utf-8")
    assert MODULE["source_snapshot"](package) == before
    (package / "new_module.py").write_text("pass\n", encoding="utf-8")
    after = MODULE["source_snapshot"](package)
    assert after["sha256"] != before["sha256"]
    assert after["file_count"] == before["file_count"] + 1


def with_local_dependency(package: Path) -> Path:
    dependency = package.parent / "dependency"
    synthetic_package(dependency)
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8")
        + '\n[tool.uv.sources]\ndependency={path="../dependency"}\n',
        encoding="utf-8",
    )
    git(package, "add", "..")
    git(package, "commit", "-qm", "local dependency")
    return dependency


@pytest.mark.parametrize("scope", ["package", "local_dependency"])
def test_clean_autocrlf_clone_cannot_identify_translated_bytes_as_git_head(
    package: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate_driver: dict[str, Any],
    scope: str,
) -> None:
    repository = package.parents[1]
    dependency = with_local_dependency(package)
    target = package if scope == "package" else dependency
    git(repository, "config", "core.autocrlf", "false")
    (repository / ".gitattributes").write_bytes(b"* -text\n*.R text=auto\n")
    fixture = target / "review fixture.R"
    canonical = b"value <- 1\nstopifnot(value == 1)\n"
    fixture.write_bytes(canonical)
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "canonical synthetic R bytes")
    translated = tmp_path / "translated-clone"
    git(
        repository,
        "clone",
        "-q",
        "--no-local",
        "--config",
        "core.autocrlf=true",
        str(repository),
        str(translated),
    )
    translated_package = translated / package.relative_to(repository)
    translated_fixture = translated / fixture.relative_to(repository)
    assert translated_fixture.read_bytes() == canonical.replace(b"\n", b"\r\n")
    assert git(translated, "status", "--porcelain", "--untracked-files=all") == ""
    with pytest.raises(SystemExit, match="raw worktree bytes differ from Git HEAD blob"):
        MODULE["require_canonical_git_bytes"](translated_package)
    with pytest.raises(SystemExit, match="raw worktree bytes differ from Git HEAD blob"):
        MODULE["verified_source_commit"](translated_package, None)
    receipt_path = tmp_path / "must-not-start.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_candidate.py",
            "--package",
            str(translated_package),
            "--uv",
            "never-run-uv",
            "--output",
            str(receipt_path),
        ],
    )
    with pytest.raises(SystemExit, match="raw worktree bytes differ from Git HEAD blob"):
        candidate_driver["main"]()
    assert not receipt_path.exists()
    exact = tmp_path / "canonical-clone"
    git(
        repository,
        "clone",
        "-q",
        "--no-local",
        "--config",
        "core.autocrlf=false",
        "--config",
        "core.eol=lf",
        str(repository),
        str(exact),
    )
    exact_package = exact / package.relative_to(repository)
    assert (exact / fixture.relative_to(repository)).read_bytes() == canonical
    assert git(exact, "status", "--porcelain", "--untracked-files=all") == ""
    MODULE["require_canonical_git_bytes"](exact_package)
    assert MODULE["verified_source_commit"](exact_package, None) == git(exact, "rev-parse", "HEAD")


@pytest.mark.parametrize("action", ["replace", "remove"])
def test_dependency_wheel_replacement_invalidates_installed_checks_only(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    dependency = with_local_dependency(package)
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    before = MODULE["source_snapshot"](package)
    wheel = next((dependency / "dist").glob("*.whl"))
    if action == "remove":
        wheel.unlink()
    else:
        wheel.write_bytes(b"untested dependency wheel")
    assert MODULE["source_snapshot"](package) == before
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["unbound_stages"] == ["distribution"]


def test_absent_dependency_wheel_cannot_bind_installed_checks(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency = with_local_dependency(package)
    next((dependency / "dist").glob("*.whl")).unlink()
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    assert result["check_completion"]["unbound_stages"] == ["distribution"]


def test_dirty_dependency_cannot_be_attributed_to_clean_parent_commit(
    package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency = with_local_dependency(package)
    (dependency / "README.md").write_text("Uncommitted dependency.\n", encoding="utf-8")
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    with pytest.raises(SystemExit, match="local dependencies must have no tracked changes"):
        manifest(monkeypatch, package, tmp_path / "manifest.json", checks)


def test_conditional_local_sources_are_rejected_instead_of_omitting_dependency_bytes(
    package: Path,
) -> None:
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8")
        + '\n[tool.uv.sources]\ndependency=[{path="../dependency"}]\n',
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="conditional uv sources"):
        MODULE["source_snapshot"](package)


@pytest.fixture
def candidate_driver(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    tools = Path(__file__).parents[1] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    return runpy.run_path(str(tools / "check_candidate.py"))


@pytest.fixture
def local_runtime(package: Path, tmp_path: Path) -> tuple[Path, Path, Path]:
    """A real isolated interpreter with synthetic dependency bytes, no downloads."""
    import shutil

    dependency = with_local_dependency(package)
    project = dependency / "pyproject.toml"
    project.write_text(
        project.read_text().replace("synthetic-release-check", "runtime-dependency"),
        encoding="utf-8",
    )
    for artifact in (dependency / "dist").iterdir():
        artifact.rename(
            artifact.with_name(
                artifact.name.replace("synthetic_release_check", "runtime_dependency")
            )
        )
    source = dependency / "src" / "candidate_dependency"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(
        "from .implementation import VERSION\n"
        'if VERSION != "new":\n    raise RuntimeError("stale bytecode loaded")\n',
        encoding="utf-8",
    )
    (source / "implementation.py").write_text('VERSION = "new"\n', encoding="utf-8")
    (source / "py.typed").write_text("", encoding="utf-8")
    environment = tmp_path / "isolated-runtime"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(environment)], check=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    library = Path(
        subprocess.check_output(
            [str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True,
        ).strip()
    )
    installed = library / source.name
    shutil.copytree(source, installed)
    return python, source, installed


def test_local_runtime_binding_records_exact_installed_source_bytes(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
) -> None:
    python, source, installed = local_runtime
    binding = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "fresh-bytecode"
    )
    assert binding["verified"] is True
    assert MODULE["runtime_binding_matches"](binding, package)
    imported = binding["resolved_dependencies"][0]["imports"][0]
    assert imported["origin"] == str(installed / "__init__.py")
    assert imported["root"] != str(source)
    assert imported["files"] == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source.iterdir()
    }
    binding["resolved_dependencies"][0]["imports"][0]["files"]["implementation.py"] = "0" * 64
    assert not MODULE["runtime_binding_matches"](binding, package)


@pytest.mark.parametrize("kind", ["stale", "missing", "extra"])
def test_source_snapshot_cannot_conceal_stale_local_runtime(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
    kind: str,
) -> None:
    python, source, installed = local_runtime
    before = MODULE["source_snapshot"](package)
    project_bytes = (source.parents[1] / "pyproject.toml").read_bytes()
    if kind == "stale":
        # uv's metadata cache can leave an old private module while the current
        # worktree snapshot and the public package/version continue looking valid.
        (source / "implementation.py").write_text('VERSION = "newer"\n', encoding="utf-8")
        assert MODULE["source_snapshot"](package) != before
    elif kind == "missing":
        (installed / "implementation.py").unlink()
    else:
        (installed / "obsolete.py").write_text("pass\n", encoding="utf-8")
    assert (source.parents[1] / "pyproject.toml").read_bytes() == project_bytes
    binding = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "fresh-bytecode"
    )
    assert binding["verified"] is False
    assert "local dependency runtime" in binding["error"]


def test_fresh_bytecode_prefix_prevents_valid_timestamp_stale_pyc(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
) -> None:
    python, _source, installed = local_runtime
    implementation = installed / "implementation.py"
    implementation.write_text('VERSION = "old"\n', encoding="utf-8")
    original = implementation.stat()
    compiled = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import py_compile,sys;print(py_compile.compile(sys.argv[1],doraise=True,"
            "invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))",
            str(implementation),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    # SOURCE_DATE_EPOCH defaults py_compile to checked-hash mode. This regression
    # needs a real timestamp cache that remains valid after an equal-size edit.
    cache = Path(compiled.stdout.strip())
    header = cache.read_bytes()[:16]
    assert len(header) == 16 and int.from_bytes(header[4:8], "little") == 0
    assert int.from_bytes(header[8:12], "little") == int(original.st_mtime) & 0xFFFFFFFF
    assert int.from_bytes(header[12:16], "little") == implementation.stat().st_size
    implementation.write_text('VERSION = "new"\n', encoding="utf-8")
    os.utime(implementation, ns=(original.st_atime_ns, original.st_mtime_ns))
    stale = subprocess.run(
        [str(python), "-I", "-c", "import candidate_dependency"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert stale.returncode != 0 and "stale bytecode loaded" in stale.stderr
    binding = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "fresh-bytecode"
    )
    assert binding["verified"] is True


def test_runtime_mismatch_stops_driver_after_sync_before_any_source_controls(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python, _source, installed = local_runtime
    (installed / "implementation.py").write_text('VERSION = "old"\n', encoding="utf-8")
    binding = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "fresh-bytecode"
    )
    calls = []
    run = candidate_driver["run_checks"]
    monkeypatch.setitem(run.__globals__, "local_dependency_runtime_binding", lambda *_: binding)

    def execute(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", execute)
    # The command stub is not an OS probe: Windows platform.platform may itself
    # invoke subprocess.run and would otherwise consume the synthetic result.
    monkeypatch.setattr(candidate_driver["platform"], "platform", lambda: "synthetic test platform")
    # Snapshot calls use git/subprocess too, so freeze those independently.
    snapshot = binding["source_snapshot"]
    monkeypatch.setitem(run.__globals__, "source_snapshot", lambda _: snapshot)
    output = tmp_path / "driver.json"
    with pytest.raises(SystemExit, match="runtime binding failed"):
        run(
            package,
            output,
            snapshot,
            (),
            (),
            declared_commands(package),
            [str(python)],
            tmp_path / "fresh-bytecode",
            {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(tmp_path)},
        )
    assert calls == [declared_commands(package)[0]]
    document = json.loads(output.read_bytes())
    assert len(document["results"]) == 1
    assert document["results"][0]["local_dependency_runtime_binding"]["verified"] is False


def test_driver_reinstalls_local_closure_and_holds_sync(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Candidate startup requires the synthetic fixture to be committed, too.
    git(package, "add", "..")
    git(package, "commit", "-qm", "canonical local runtime fixture")
    main = candidate_driver["main"]
    captured = []
    monkeypatch.setitem(main.__globals__, "run_checks", lambda *args: captured.append(args))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_candidate.py",
            "--package",
            str(package),
            "--uv",
            "uv",
            "--output",
            str(tmp_path / "checks.json"),
        ],
    )
    main()
    commands = captured[0][5]
    assert commands[0][-4:] == [
        "--reinstall-package",
        "synthetic-release-check",
        "--reinstall-package",
        "runtime-dependency",
    ]
    assert all("--no-sync" in command for command in commands[1:])
    artifacts = tuple(sorted((package / "dist").iterdir()))
    commands[7] += [str(path) for path in artifacts]
    assert [MODULE["check_stage"](command, package, artifacts) for command in commands] == list(
        STAGES
    )


@pytest.mark.parametrize(
    "extra",
    [
        ["--reinstall-package"],
        ["--reinstall-package", "--locked"],
        ["--reinstall-package", "undeclared-package"],
        ["--reinstall-package", "runtime-dependency", "--reinstall-package", "runtime-dependency"],
        ["--reinstall"],
        ["--reinstall-package=runtime-dependency"],
        ["--python", "3.12", "--python", "3.12"],
        ["--locked"],
    ],
)
def test_locked_sync_rejects_unbounded_or_malformed_reinstall_options(
    package: Path,
    local_runtime: tuple[Path, Path, Path],
    extra: list[str],
) -> None:
    assert (
        MODULE["check_stage"](["uv", "sync", "--locked", "--all-extras", *extra], package, ())
        is None
    )


def test_legacy_source_binding_does_not_claim_dependency_runtime_proof(
    package: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_local_dependency(package)
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    result = manifest(monkeypatch, package, tmp_path / "manifest.json", checks)
    completion = result["check_completion"]
    assert completion["source_bound_stages"] == list(STAGES)
    assert completion["local_dependency_runtime_bound_stages"] == []
    assert completion["local_dependency_runtime_unbound_stages"] == list(STAGES)
    assert any("imported bytes" in reason for reason in result["publication_blockers"])


@pytest.mark.parametrize("tamper", [None, "hash", "path", "missing", "type"])
def test_only_complete_matching_runtime_inventory_binds_receipts(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
    tamper: str | None,
) -> None:
    python, _source, _installed = local_runtime
    binding = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "fresh-bytecode"
    )
    checks = receipt(tmp_path / "checks.json", package, declared_commands(package))
    document = json.loads(checks.read_bytes())
    for result in document["results"]:
        result["local_dependency_runtime_binding"] = json.loads(json.dumps(binding))
    altered = document["results"][5]["local_dependency_runtime_binding"]
    imported = altered["resolved_dependencies"][0]["imports"][0]
    if tamper == "hash":
        imported["files"]["implementation.py"] = "0" * 64
    elif tamper == "path":
        imported["root"] = None
    elif tamper == "missing":
        altered["resolved_dependencies"] = []
    elif tamper == "type":
        altered["resolved_dependencies"] = [None]
    checks.write_text(json.dumps(document), encoding="utf-8")
    _, completion = MODULE["read_check_receipts"](
        [checks], package, tuple(sorted((package / "dist").iterdir()))
    )
    assert completion["local_dependency_runtime_unbound_stages"] == (
        [] if tamper is None else ["pytest"]
    )
    assert completion["source_bound_stages"] == list(STAGES)


def test_transitive_dependency_names_are_reinstalled_and_recognized(package: Path) -> None:
    dependency = with_local_dependency(package)
    transitive = package.parent / "transitive"
    synthetic_package(transitive)
    project = transitive / "pyproject.toml"
    project.write_text(project.read_text().replace("synthetic-release-check", "transitive"))
    project = dependency / "pyproject.toml"
    project.write_text(
        project.read_text() + '\n[tool.uv.sources]\ntransitive={path="../transitive"}\n'
    )
    assert MODULE["local_dependency_names"](package) == ["synthetic-release-check", "transitive"]
    command = [
        "uv",
        "sync",
        "--locked",
        "--all-extras",
        "--reinstall-package",
        "synthetic-release-check",
        "--reinstall-package",
        "transitive",
    ]
    assert MODULE["check_stage"](command, package, ()) == "locked_sync"


def test_probe_and_source_controls_share_sanitized_import_environment(
    package: Path,
    tmp_path: Path,
    candidate_driver: dict[str, Any],
    local_runtime: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python, _source, _installed = local_runtime
    shadow = tmp_path / "shadow" / "candidate_dependency"
    shadow.mkdir(parents=True)
    (shadow / "__init__.py").write_text('raise RuntimeError("shadowed dependency")\n')
    monkeypatch.setenv("PYTHONPATH", str(shadow.parent))
    polluted = subprocess.run(
        [str(python), "-c", "import candidate_dependency"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert polluted.returncode != 0 and "shadowed dependency" in polluted.stderr
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "wrong-python-home"))
    environment = candidate_driver["candidate_environment"](tmp_path / "fresh-bytecode")
    assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert (
        candidate_driver["local_dependency_runtime_binding"](
            package, [str(python)], tmp_path / "fresh-bytecode", environment
        )["verified"]
        is True
    )
    subprocess.run(
        [str(python), "-c", "import candidate_dependency"], env=environment, cwd=package, check=True
    )


@pytest.mark.parametrize("mapping_kind", ["file", "directory"])
def test_installed_examples_are_part_of_exact_runtime_binding(
    package, tmp_path, candidate_driver, local_runtime, mapping_kind
):
    python, source, installed = local_runtime
    dependency = source.parents[1]
    examples = dependency / "examples"
    examples.mkdir()
    script = examples / "journey.py"
    script.write_text('EXPECTED = "synthetic"\n', encoding="utf-8")
    origin = "examples/journey.py" if mapping_kind == "file" else "examples"
    target = (
        "candidate_dependency/examples/journey.py"
        if mapping_kind == "file"
        else ("candidate_dependency/examples")
    )
    project = dependency / "pyproject.toml"
    project.write_text(
        project.read_text()
        + (f'\n[tool.hatch.build.targets.wheel.force-include]\n"{origin}" = "{target}"\n')
    )
    (installed / "examples").mkdir()
    copied = installed / "examples" / "journey.py"
    copied.write_bytes(script.read_bytes())
    binding = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "with-example"
    )
    assert binding["verified"] is True
    assert MODULE["runtime_binding_matches"](binding, package)
    copied.write_text('EXPECTED = "old"\n', encoding="utf-8")
    stale = candidate_driver["local_dependency_runtime_binding"](
        package, [str(python)], tmp_path / "stale-example"
    )
    assert stale["verified"] is False


@pytest.mark.parametrize("minor", ["3.10", "3.11", "3.12", "3.13"])
def test_strict_type_gate_can_identify_the_tested_python_minor(package, minor):
    assert (
        MODULE["check_stage"](
            [
                "uv",
                "run",
                "--locked",
                "--all-extras",
                "--python",
                minor,
                "mypy",
                "--python-version",
                minor,
            ],
            package,
            (),
        )
        == "mypy"
    )
    assert MODULE["check_stage"](["mypy", "--python-version", minor, "src"], package, ()) is None


@pytest.mark.parametrize(
    "arguments",
    [
        ["--python-version", "3.9"],
        ["--python-version", "3.14"],
        ["--python-version", "3.10", "--python-version", "3.11"],
        ["--python-version"],
    ],
)
def test_type_gate_rejects_unknown_or_conflicting_python_targets(package, arguments):
    assert MODULE["check_stage"](["mypy", *arguments], package, ()) is None
