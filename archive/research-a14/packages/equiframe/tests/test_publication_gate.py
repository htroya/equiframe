"""Synthetic release records test local consistency, never authorization."""

import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "verify_publication.py"))
COMMIT = "1" * 40


def candidate(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    core_wheel: dict[str, Any] = {}
    for name, short in (("equiframe", "core"), ("equiframe-benchmark", "benchmark")):
        folder = root / name
        folder.mkdir(parents=True)
        stem = name.replace("-", "_") + "-0.11.1"
        artifacts = []
        for suffix in ("-py3-none-any.whl", ".tar.gz"):
            path = folder / (stem + suffix)
            path.write_bytes(b"synthetic test artifact " + path.name.encode())
            artifacts.append(MODULE["file_identity"](path, root))
        stages = sorted(MODULE["REQUIRED"])
        document = {
            "schema_version": "1.0",
            "distribution": name,
            "version": "0.11.1",
            "source_commit": COMMIT,
            "published": False,
            "source_validation": {
                "git_head": COMMIT,
                "package_clean": True,
                "project_tracked": True,
            },
            "check_completion": {
                "required_stages": stages,
                "successful_stages": stages,
                "source_bound_stages": stages,
                "local_dependency_runtime_bound_stages": stages,
                "missing_stages": [],
                "unbound_stages": [],
                "local_dependency_runtime_unbound_stages": [],
                "failed_commands": 0,
                "dependency_artifacts": [] if short == "core" else [core_wheel],
            },
            "artifacts": artifacts,
            "publication_blockers": ["synthetic owner decision missing"],
        }
        if short == "core":
            core_wheel = artifacts[0]
        path = folder / (short + "-manifest.json")
        path.write_text(json.dumps(document))
        files[short] = path
    return files


def edit(path: Path, key: str, value: Any, *, section: str | None = None) -> None:
    document = json.loads(path.read_text())
    (document if section is None else document[section])[key] = value
    path.write_text(json.dumps(document))


def test_identified_artifacts_still_cannot_publish(tmp_path: Path) -> None:
    candidate(tmp_path)
    report = MODULE["check_candidate"](tmp_path, COMMIT)
    assert report["artifacts_verified"] is True
    assert report["publication_ready"] is False and report["published"] is False
    assert len(report["pending_decisions"]) >= 6
    policy = Path(MODULE["POLICY"])
    assert report["policy"]["sha256"] == hashlib.sha256(policy.read_bytes()).hexdigest()


@pytest.mark.parametrize("value", ["", "1" * 39, "A" * 40, "../candidate", "1" * 41])
def test_exact_commit_required(tmp_path: Path, value: str) -> None:
    candidate(tmp_path)
    with pytest.raises(ValueError, match="exact lowercase"):
        MODULE["check_candidate"](tmp_path, value)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "99.0"),
        ("source_commit", "2" * 40),
        ("published", True),
        ("version", "../../outside"),
        ("distribution", "another"),
        ("publication_blockers", None),
        ("publication_blockers", [False]),
        (
            "source_validation",
            {"git_head": COMMIT, "package_clean": False, "project_tracked": True},
        ),
    ],
)
def test_invalid_manifest_rejected(tmp_path: Path, key: str, value: Any) -> None:
    files = candidate(tmp_path)
    edit(files["core"], key, value)
    with pytest.raises(ValueError):
        MODULE["check_candidate"](tmp_path, COMMIT)


@pytest.mark.parametrize(
    "key,value",
    [
        ("successful_stages", []),
        ("source_bound_stages", []),
        ("local_dependency_runtime_bound_stages", []),
        ("missing_stages", ["pytest"]),
        ("unbound_stages", ["pytest"]),
        ("local_dependency_runtime_unbound_stages", ["pytest"]),
        ("failed_commands", True),
        ("failed_commands", 1),
        ("dependency_artifacts", []),
    ],
)
def test_incomplete_stale_and_unbound_checks_rejected(tmp_path: Path, key: str, value: Any) -> None:
    files = candidate(tmp_path)
    edit(files["benchmark"], key, value, section="check_completion")
    with pytest.raises(ValueError):
        MODULE["check_candidate"](tmp_path, COMMIT)


def test_zero_reported_blockers_cannot_enable_publication(tmp_path: Path) -> None:
    files = candidate(tmp_path)
    for path in files.values():
        edit(path, "publication_blockers", [])
    assert MODULE["check_candidate"](tmp_path, COMMIT)["publication_ready"] is False


def test_substituted_artifact_rejected(tmp_path: Path) -> None:
    files = candidate(tmp_path)
    next(files["core"].parent.glob("*.whl")).write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        MODULE["check_candidate"](tmp_path, COMMIT)


def test_duplicate_artifact_rejected(tmp_path: Path) -> None:
    files = candidate(tmp_path)
    document = json.loads(files["core"].read_text())
    edit(files["core"], "artifacts", [document["artifacts"][0]] * 2)
    with pytest.raises(ValueError, match="repeated"):
        MODULE["check_candidate"](tmp_path, COMMIT)


def test_duplicate_json_member_rejected(tmp_path: Path) -> None:
    files = candidate(tmp_path)
    files["core"].write_text('{"schema_version":"1.0","schema_version":"99.0"}')
    with pytest.raises(ValueError, match="duplicate JSON"):
        MODULE["check_candidate"](tmp_path, COMMIT)


def test_symlink_artifact_rejected(tmp_path: Path) -> None:
    files = candidate(tmp_path)
    wheel = next(files["core"].parent.glob("*.whl"))
    target = tmp_path / "payload"
    target.write_bytes(wheel.read_bytes())
    wheel.unlink()
    try:
        wheel.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError, match="regular files"):
        MODULE["check_candidate"](tmp_path, COMMIT)


def test_extra_manifest_rejected(tmp_path: Path) -> None:
    candidate(tmp_path)
    (tmp_path / "extra-manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="exactly two"):
        MODULE["check_candidate"](tmp_path, COMMIT)
