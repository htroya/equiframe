"""Synthetic release records test local consistency, never authorization."""

import hashlib
import json
import runpy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "verify_publication.py"))
COMMIT = "1" * 40


def candidate(root: Path, version: str = "0.11.1") -> dict[str, Path]:
    files: dict[str, Path] = {}
    core_wheel: dict[str, Any] = {}
    for name, short in (("equiframe", "core"), ("equiframe-benchmark", "benchmark")):
        folder = root / name
        folder.mkdir(parents=True)
        stem = name.replace("-", "_") + "-" + version
        artifacts = []
        for suffix in ("-py3-none-any.whl", ".tar.gz"):
            path = folder / (stem + suffix)
            path.write_bytes(b"synthetic test artifact " + path.name.encode())
            artifacts.append(MODULE["file_identity"](path, root))
        stages = sorted(MODULE["REQUIRED"])
        document = {
            "schema_version": "1.0",
            "distribution": name,
            "version": version,
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
            "publication_blockers": (
                ["synthetic owner decision missing"] if version == "0.11.1" else []
            ),
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


def factual_packet(root: Path, *, target: str = "testpypi") -> tuple[Path, dict[str, Any]]:
    """Synthetic observations exercise consistency, never real release approval."""
    artifacts = [
        artifact
        for path in sorted(root.rglob("*-manifest.json"))
        for artifact in json.loads(path.read_bytes())["artifacts"]
    ]
    details = {
        "license_review": {
            "core_license": "MIT AND Apache-2.0",
            "benchmark_license": "MIT",
            "third_party_notices_verified": True,
            "rights_scope_verified": True,
        },
        "public_documentation": {
            "url": "https://documentation.example.invalid/",
            "unauthenticated": True,
            "http_status": 200,
        },
        "name_control": {
            "index": target,
            "projects": ["equiframe", "equiframe-benchmark"],
            "mode": "existing_projects",
            "authenticated_owner_verified": True,
        },
        "publisher_protection": {
            "index": target,
            "two_factor_verified": True,
            "publisher_roles_verified": True,
            "credential_handling": "interactive_hidden_prompt",
        },
        "dependency_security_review": {
            "review_complete": True,
            "unresolved_high_or_critical": 0,
            "unavailable_checks": 0,
        },
        "source_security_review": {
            "review_complete": True,
            "unresolved_high_or_critical": 0,
            "unavailable_checks": 0,
        },
        "independent_release_review": {"independent": True, "open_blocking_findings": 0},
        "owner_release_authorization": {
            "index": target,
            "explicit_instruction_verified": True,
        },
    }
    if target == "pypi":
        details.update(
            testpypi_artifact_identity={"index": "testpypi", "observed_artifacts": artifacts},
            testpypi_downloaded_consumer={
                "index": "testpypi",
                "downloaded_artifacts": artifacts,
                "pip_check": True,
                "installed_identity_verified": True,
                "functional_cases_passed": True,
            },
        )
    packet = {
        "schema_version": "2.0",
        "target": target,
        "version": "0.12.4",
        "source_commit": COMMIT,
        "artifacts": artifacts,
        "gates": [
            {
                "id": name,
                "state": "PASS",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "basis": "Synthetic unit-test observation; no actor or service was verified.",
                "details": value,
            }
            for name, value in details.items()
        ],
    }
    path = root / "gate-packet.json"
    path.write_text(json.dumps(packet))
    return path, packet


def save_packet(path: Path, packet: dict[str, Any]) -> None:
    path.write_text(json.dumps(packet))


@pytest.mark.parametrize("version", ["0.12.0", "0.12.1", "0.12.2", "0.12.3"])
def test_previous_testpypi_version_cannot_inherit_current_release_readiness(
    tmp_path: Path, version: str
) -> None:
    candidate(tmp_path, version)
    with pytest.raises(ValueError, match="historical candidates"):
        MODULE["check_candidate"](tmp_path, COMMIT, target="pypi")


def initial_upload_details(target: str) -> dict[str, Any]:
    return {
        "index": target,
        "projects": ["equiframe", "equiframe-benchmark"],
        "mode": "initial_upload_attempt",
        "authenticated_account_verified": True,
        "observations": [
            {"project": "equiframe", "http_status": 404},
            {"project": "equiframe-benchmark", "http_status": 404},
        ],
        "absence_is_not_reservation_ownership_or_acceptance": True,
    }


@pytest.mark.parametrize("target", ["testpypi", "pypi"])
def test_initial_upload_scope_never_claims_name_ownership(tmp_path: Path, target: str) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path, target=target)
    gate = next(item for item in packet["gates"] if item["id"] == "name_control")
    gate["details"] = initial_upload_details(target)
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target=target, gate_packet=path)
    assert report["publication_ready"] is True
    assert report["name_control_mode"] == "initial_upload_attempt"
    assert report["published"] is False and report["authorization_authenticated"] is False
    assert "initial upload attempt only" in report["readiness_scope"]
    assert "no reservation, ownership or admission" in report["readiness_scope"]
    assert "authenticated_owner_verified" not in gate["details"]
    assert len(report["gate_states"]) == (8 if target == "testpypi" else 10)


@pytest.mark.parametrize(
    "field,value",
    [
        ("index", "pypi"),
        ("mode", "available_name"),
        ("projects", ["equiframe", "unrelated-project"]),
        ("authenticated_account_verified", False),
        ("absence_is_not_reservation_ownership_or_acceptance", False),
        ("authenticated_owner_verified", True),
        ("reserved", True),
        ("observations", []),
        ("observations", [{"project": "equiframe", "http_status": 404}]),
        (
            "observations",
            [{"project": "equiframe", "http_status": 404}] * 2,
        ),
        (
            "observations",
            [
                {"project": "equiframe", "http_status": 404},
                {"project": "equiframe-benchmark", "http_status": 200},
            ],
        ),
        (
            "observations",
            [
                {"project": "equiframe", "http_status": 404},
                {"project": "equiframe-benchmark", "http_status": 503},
            ],
        ),
        (
            "observations",
            [
                {"project": "equiframe", "http_status": 404.0},
                {"project": "equiframe-benchmark", "http_status": 404},
            ],
        ),
    ],
)
def test_initial_upload_rejects_unverified_mixed_or_ownership_claims(
    tmp_path: Path, field: str, value: Any
) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    gate = next(item for item in packet["gates"] if item["id"] == "name_control")
    gate["details"] = initial_upload_details("testpypi")
    gate["details"][field] = value
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    assert not report["publication_ready"]
    assert any("name_control" in reason for reason in report["pending_decisions"])


@pytest.mark.parametrize("gate_name", ["publisher_protection", "owner_release_authorization"])
def test_initial_upload_still_requires_account_protection_and_owner_task(
    tmp_path: Path, gate_name: str
) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    next(item for item in packet["gates"] if item["id"] == "name_control")["details"] = (
        initial_upload_details("testpypi")
    )
    packet["gates"] = [item for item in packet["gates"] if item["id"] != gate_name]
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    assert not report["publication_ready"]
    assert any(gate_name in reason for reason in report["pending_decisions"])


@pytest.mark.parametrize("mode", [None, "initial_upload_attempt"])
def test_existing_project_ownership_cannot_be_inferred_from_404(
    tmp_path: Path, mode: str | None
) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    details = next(item for item in packet["gates"] if item["id"] == "name_control")["details"]
    if mode is None:
        details.pop("mode")
    else:
        details["mode"] = mode
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    assert not report["publication_ready"]


@pytest.mark.parametrize("target", ["testpypi", "pypi"])
def test_v2_exact_complete_packet_checks_consistency_only(tmp_path: Path, target: str) -> None:
    candidate(tmp_path, "0.12.4")
    path, _ = factual_packet(tmp_path, target=target)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target=target, gate_packet=path)
    assert report["publication_ready"] is True
    assert report["published"] is False and report["authorization_authenticated"] is False
    assert report["pending_decisions"] == []
    assert report["endpoint"] == MODULE["INDICES"][target]
    assert len(report["gate_states"]) == (8 if target == "testpypi" else 10)
    assert report["gate_packet"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_v2_absent_packet_and_unspecified_index_remain_blocked(tmp_path: Path) -> None:
    candidate(tmp_path, "0.12.4")
    for options in ({}, {"target": "testpypi"}):
        report = MODULE["check_candidate"](tmp_path, COMMIT, **options)
        assert not report["publication_ready"] and report["pending_decisions"]


@pytest.mark.parametrize("state", ["FAIL", "UNKNOWN", "MISSING"])
def test_v2_failed_unknown_or_missing_gate_blocks(tmp_path: Path, state: str) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    if state == "MISSING":
        packet["gates"] = packet["gates"][1:]
    else:
        packet["gates"][0]["state"] = state
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    assert not report["publication_ready"]
    assert any("license_review" in value for value in report["pending_decisions"])


@pytest.mark.parametrize(
    "gate,field,value",
    [
        ("public_documentation", "unauthenticated", False),
        ("public_documentation", "http_status", 401),
        ("public_documentation", "url", "https://user:secret@example.invalid/docs"),
        ("name_control", "index", "pypi"),
        ("name_control", "authenticated_owner_verified", False),
        ("publisher_protection", "two_factor_verified", False),
        ("publisher_protection", "credential_handling", "command_line_token"),
        ("source_security_review", "unresolved_high_or_critical", 1),
        ("dependency_security_review", "unavailable_checks", 1),
        ("dependency_security_review", "unavailable_checks", False),
        ("independent_release_review", "independent", False),
        ("owner_release_authorization", "explicit_instruction_verified", False),
    ],
)
def test_v2_pass_word_cannot_replace_required_facts(
    tmp_path: Path, gate: str, field: str, value: Any
) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    next(item for item in packet["gates"] if item["id"] == gate)["details"][field] = value
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    assert not report["publication_ready"]
    assert any(gate in reason for reason in report["pending_decisions"])


@pytest.mark.parametrize("offset", [timedelta(days=-8), timedelta(minutes=10)])
def test_v2_stale_or_future_observations_block(tmp_path: Path, offset: timedelta) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    packet["gates"][0]["observed_at"] = (datetime.now(timezone.utc) + offset).isoformat()
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    assert not report["publication_ready"]
    assert "stale or in the future" in report["pending_decisions"][0]


@pytest.mark.parametrize(
    "field,value",
    [("target", "pypi"), ("source_commit", "2" * 40), ("version", "99.0.0"), ("artifacts", [])],
)
def test_v2_packet_is_bound_to_exact_source_bytes_and_index(
    tmp_path: Path, field: str, value: Any
) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    assert packet[field] != value, "The negative case must actually change the packet"
    packet[field] = value
    save_packet(path, packet)
    with pytest.raises(ValueError, match="exact index, source and artifacts"):
        MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)


def test_v2_pypi_requires_actual_testpypi_download_inventory(tmp_path: Path) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path, target="pypi")
    gate = next(g for g in packet["gates"] if g["id"] == "testpypi_downloaded_consumer")
    gate["details"]["downloaded_artifacts"] = []
    save_packet(path, packet)
    report = MODULE["check_candidate"](tmp_path, COMMIT, target="pypi", gate_packet=path)
    assert not report["publication_ready"]


def test_v2_duplicate_gate_and_dropped_policy_gate_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate(tmp_path, "0.12.4")
    path, packet = factual_packet(tmp_path)
    packet["gates"][-1] = packet["gates"][0]
    save_packet(path, packet)
    with pytest.raises(ValueError, match="repeated"):
        MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)
    policy = json.loads(Path(MODULE["POLICY"]).read_bytes())
    policy["required_gates"]["testpypi"] = policy["required_gates"]["testpypi"][1:]
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setitem(MODULE["check_candidate"].__globals__, "POLICY", policy_path)
    with pytest.raises(ValueError, match="cannot be weakened"):
        MODULE["check_candidate"](tmp_path, COMMIT)


def test_historical_candidate_cannot_enter_new_route(tmp_path: Path) -> None:
    candidate(tmp_path)
    with pytest.raises(ValueError, match="historical candidates"):
        MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi")


def test_v2_cli_exit_zero_is_consistency_not_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate(tmp_path, "0.12.4")
    path, _ = factual_packet(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_publication.py",
            "--candidate-root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--target",
            "testpypi",
            "--gate-packet",
            str(path),
            "--output",
            str(tmp_path / "readiness.json"),
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        MODULE["main"]()
    assert stopped.value.code == 0
    captured = capsys.readouterr()
    assert "no upload or authorization" in captured.out and not captured.err


def test_historical_cli_still_exits_three(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_publication.py",
            "--candidate-root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--output",
            str(tmp_path / "readiness.json"),
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        MODULE["main"]()
    assert stopped.value.code == 3


def test_standalone_v1_policy_remains_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate(tmp_path)
    policy = json.loads(Path(MODULE["POLICY"]).read_bytes())["legacy_policy"]
    path = tmp_path / "historical-policy.json"
    path.write_text(json.dumps(policy))
    monkeypatch.setitem(MODULE["check_candidate"].__globals__, "POLICY", path)
    report = MODULE["check_candidate"](tmp_path, COMMIT)
    assert report["schema_version"] == "1.0" and not report["publication_ready"]


def test_v2_all_nine_technical_gates_remain_mandatory(tmp_path: Path) -> None:
    files = candidate(tmp_path, "0.12.4")
    path, _ = factual_packet(tmp_path)
    edit(files["core"], "successful_stages", [], section="check_completion")
    with pytest.raises(ValueError, match="incomplete or unbound"):
        MODULE["check_candidate"](tmp_path, COMMIT, target="testpypi", gate_packet=path)


def test_readiness_cannot_overwrite_an_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    files = candidate(tmp_path)
    artifact = next(files["core"].parent.glob("*.whl"))
    original = artifact.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_publication.py",
            "--candidate-root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--output",
            str(artifact),
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        MODULE["main"]()
    assert stopped.value.code == 2
    assert artifact.read_bytes() == original
    captured = capsys.readouterr()
    assert "new writable file" in captured.err and not captured.out
