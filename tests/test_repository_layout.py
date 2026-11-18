"""Prevent the historical-tree integration regressions without reactivating CI."""

import hashlib
import json
import runpy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
check = runpy.run_path(str(ROOT / "tools/check_repository_layout.py"))["layout_errors"]


@pytest.fixture
def repository(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.hatch.build.targets.sdist]\nexclude=["/archive/**"]\n'
        '[tool.ruff]\nextend-exclude=["archive"]\n',
        encoding="utf-8",
    )
    return tmp_path


def test_current_tree_has_one_active_core_and_no_actions():
    assert check(ROOT) == []


def test_duplicate_core_is_rejected(repository):
    (repository / "packages/equiframe").mkdir(parents=True)
    (repository / "packages/equiframe/pyproject.toml").write_text(
        '[project]\nname="equiframe"\n', encoding="utf-8"
    )
    assert "duplicate active core" in check(repository)[0]


def test_empty_untracked_directories_are_not_an_active_core(repository):
    (repository / "packages/equiframe/src/equiframe/__pycache__").mkdir(parents=True)
    assert check(repository) == []


@pytest.mark.parametrize("name", ["ci.yml", "publish.yaml"])
def test_active_workflows_are_rejected(repository, name):
    workflow = repository / ".github/workflows" / name
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: forbidden-active-workflow\n", encoding="utf-8")
    assert "active GitHub Actions" in check(repository)[0]


def test_disabled_workflow_examples_are_permitted(repository):
    workflow = repository / ".github/disabled-workflows/ci.yml.example"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: historical-example\n", encoding="utf-8")
    assert check(repository) == []


@pytest.mark.parametrize("operation", ["modify", "remove"])
def test_archived_bytes_are_preserved(repository, operation):
    archive = repository / "archive/research-a14"
    archive.mkdir(parents=True)
    member = archive / "historical.txt"
    member.write_bytes(b"historical-result\n")
    (archive / "inventory.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "original": "old.txt",
                        "archived": "archive/research-a14/historical.txt",
                        "sha256": hashlib.sha256(member.read_bytes()).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert check(repository) == []
    if operation == "modify":
        member.write_bytes(b"rewritten-result\n")
    else:
        member.unlink()
    assert "archived file missing, substituted or modified" in check(repository)[0]


def test_archive_inventory_cannot_inspect_outside_archive(repository):
    archive = repository / "archive/research-a14"
    archive.mkdir(parents=True)
    (archive / "inventory.json").write_text(
        json.dumps(
            {"files": [{"original": "old.txt", "archived": "outside.txt", "sha256": "0" * 64}]}
        ),
        encoding="utf-8",
    )
    assert "substituted" in check(repository)[0]


def test_git_archive_bytes_are_checked_beyond_the_working_copy(repository):
    archive = repository / "archive/research-a14"
    archive.mkdir(parents=True)
    member = archive / "historical.txt"
    member.write_bytes(b"original-result\n")

    def inventory():
        (archive / "inventory.json").write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "original": "historical.txt",
                            "archived": "archive/research-a14/historical.txt",
                            "sha256": hashlib.sha256(member.read_bytes()).hexdigest(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    inventory()
    subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "core.autocrlf=false", "add", "archive"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=synthetic-layout-test",
            "-c",
            "user.email=layout@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Preserve synthetic archive",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    assert check(repository) == []
    member.write_bytes(b"changed-result\n")
    inventory()
    assert "archive Git bytes contradict inventory" in check(repository)[0]
