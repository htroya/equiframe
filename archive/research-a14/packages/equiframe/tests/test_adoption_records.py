"""Consistency of synthetic pilot attestations is never human acceptance."""

import copy
import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "check_adoption.py"
M = runpy.run_path(str(TOOL))


def symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable on this host: {error}")


def attempt(repeat: bool = False, state: str = "equivalent") -> dict[str, Any]:
    outcome = {
        "state": state,
        "complete": state != "not_evaluable",
        "accepted": state == "equivalent",
    }
    return {
        "id": "repeat" if repeat else "first",
        "phase": "follow_up" if repeat else "initial",
        "occurred_at": f"2026-10-0{7 if repeat else 6}T12:00:00Z",
        "change_sha256": ("b" if repeat else "a") * 64,
        "package_version": "0.11.1",
        "wheel_sha256": "c" * 64,
        "dependency_lock_sha256": "d" * 64,
        "contract_sha256": "e" * 64,
        "contract_review_sha256": None,
        "python": "3.12.14",
        "os": "Linux",
        "architecture": "x86_64",
        "engines": {"pandas": "3.0.3"},
        "installation_seconds": None,
        "integration_seconds": None,
        "diagnosis_seconds": None,
        "help_received": "unknown",
        "expected": dict(outcome),
        "observed": dict(outcome),
        "usefulness": "useful",
        "integration_retained": repeat,
        "knows_reporting": True,
        "knows_upgrading": True,
        "evidence_sha256": "f" * 64,
        "issues": [],
    }


def pilot(human: bool = False) -> dict[str, Any]:
    return {
        "id": "record-one",
        "project_id": "project-one",
        "context": "refactor_python",
        "kind": "human_pilot" if human else "synthetic_replay",
        "independent": human,
        "consent": "recorded" if human else "synthetic_only",
        "consent_sha256": "0" * 64 if human else None,
        "attempts": [attempt(), attempt(True)],
    }


def registry(*pilots: dict[str, Any]) -> Any:
    return M["Registry"].model_validate_json(
        json.dumps({"schema": "equiframe-adoption-1", "pilots": pilots})
    )


def summary(*pilots: dict[str, Any]) -> Any:
    return M["summarize"](registry(*pilots))


def issue() -> dict[str, Any]:
    return {
        "id": "issue-one",
        "category": "semantics",
        "priority": "P0",
        "false_equivalent": True,
        "reproducer_sha256": "a" * 64,
        "expected_sha256": "b" * 64,
        "observed_sha256": "c" * 64,
        "data_permission": "synthetic_only",
        "status": "open",
        "regression_sha256": None,
        "consumer_confirmation_sha256": None,
        "support_seconds": None,
    }


def test_empty_registry_preserves_unknown_effort() -> None:
    result = M["summarize"](M["read_registry"](ROOT / "examples/adoption/empty-registry.json"))
    assert result["human_pilot_records"] == result["human_attempts"] == 0
    assert result["integration_seconds_total"] is None
    assert result["human_adoption_verified"] is False
    assert result["proposed_diversity_target_recorded"] is False


def test_synthetic_does_not_count_as_human() -> None:
    result = summary(pilot())
    assert result["synthetic_replay_records"] == 1
    assert result["retained_project_attestations"] == result["human_pilot_records"] == 0
    assert result["human_adoption_verified"] is False


@pytest.mark.parametrize("state", ["equivalent", "different", "not_evaluable"])
def test_correct_difference_or_abstention_can_be_useful(state: str) -> None:
    record = pilot(True)
    record["attempts"] = [attempt(state=state), attempt(True, state)]
    result = summary(record)
    assert result["retained_project_attestations"] == (0 if state == "not_evaluable" else 1)
    assert result["recorded_outcomes"][state] == 2
    assert result["human_adoption_verified"] is False


def test_diversity_requires_distinct_project_attestations() -> None:
    records = []
    for index, context in enumerate(("refactor_python", "sql_duckdb", "ci_regression")):
        record = pilot(True)
        record.update(id=f"record-{index}", project_id=f"project-{index}", context=context)
        records.append(record)
    assert summary(*records)["proposed_diversity_target_recorded"] is True
    assert summary(*records)["human_adoption_verified"] is False
    records[1]["project_id"] = records[0]["project_id"]
    assert summary(*records)["proposed_diversity_target_recorded"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("change_sha256", "a" * 64),
        ("integration_retained", False),
        ("knows_reporting", None),
        ("knows_upgrading", False),
        ("usefulness", "blocked"),
    ],
)
def test_retention_requires_actual_change_and_latest_usable_observation(
    field: str, value: Any
) -> None:
    record = pilot(True)
    record["attempts"][-1][field] = value
    assert summary(record)["retained_project_attestations"] == 0


def test_later_failure_does_not_hide_behind_stale_success() -> None:
    record = pilot(True)
    latest = copy.deepcopy(record["attempts"][-1])
    latest.update(id="third", occurred_at="2026-10-08T12:00:00Z", usefulness="blocked")
    record["attempts"].append(latest)
    assert summary(record)["retained_project_attestations"] == 0


def test_first_failed_attempt_is_not_a_retained_integration() -> None:
    record = pilot(True)
    record["attempts"][0]["usefulness"] = "blocked"
    assert summary(record)["retained_project_attestations"] == 0


def test_unexpected_outcome_does_not_qualify() -> None:
    record = pilot(True)
    record["attempts"][-1]["observed"] = {"state": "different", "complete": True, "accepted": False}
    assert summary(record)["retained_project_attestations"] == 0


def test_consent_pending_cannot_include_human_observations() -> None:
    record = pilot(True)
    record.update(consent="not_recorded", consent_sha256=None)
    with pytest.raises(ValidationError):
        registry(record)
    record["attempts"] = []
    assert summary(record)["human_attempts"] == 0


@pytest.mark.parametrize(
    "field,value", [("independent", True), ("consent", "recorded"), ("consent_sha256", "a" * 64)]
)
def test_synthetic_cannot_assert_human_consent(field: str, value: Any) -> None:
    record = pilot()
    record[field] = value
    with pytest.raises(ValidationError):
        registry(record)


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "initial"),
        ("occurred_at", "2026-10-06T12:00:00Z"),
        ("occurred_at", "2026-10-07T12:00:00"),
        ("occurred_at", 1791288000),
        ("integration_seconds", -1),
        ("integration_seconds", True),
        ("integration_seconds", 2.5),
        ("wheel_sha256", "unknown"),
        ("package_version", "../private"),
        ("contract_sha256", None),
        ("contract_review_sha256", "a" * 64),
        ("unexpected_private_data", "do not store"),
    ],
)
def test_invalid_attempt_fields_fail_closed(field: str, value: Any) -> None:
    record = pilot()
    record["attempts"][-1][field] = value
    with pytest.raises(ValidationError):
        registry(record)


def test_changed_contract_requires_explicit_review() -> None:
    record = pilot()
    record["attempts"][-1]["contract_sha256"] = "1" * 64
    with pytest.raises(ValidationError):
        registry(record)
    record["attempts"][-1]["contract_review_sha256"] = "2" * 64
    registry(record)


@pytest.mark.parametrize(
    "outcome",
    [
        {"state": "different", "complete": True, "accepted": True},
        {"state": "not_evaluable", "complete": True, "accepted": True},
        {"state": "equivalent", "complete": False, "accepted": False},
        {"state": "equivalent", "complete": 1, "accepted": True},
    ],
)
def test_accepted_requires_complete_equivalence(outcome: dict[str, Any]) -> None:
    record = pilot()
    record["attempts"][0]["observed"] = outcome
    with pytest.raises(ValidationError):
        registry(record)


def test_zero_time_is_measured_but_null_is_unknown() -> None:
    record = pilot(True)
    record["attempts"][0]["integration_seconds"] = 0
    result = summary(record)
    assert result["integration_seconds_total"] == 0
    assert (
        result["integration_seconds_measured_attempts"]
        == result["integration_seconds_unknown_attempts"]
        == 1
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("priority", "P1"),
        ("category", "performance"),
        ("status", "regression_verified"),
        ("status", "consumer_confirmed"),
        ("regression_sha256", "a" * 64),
        ("consumer_confirmation_sha256", "a" * 64),
    ],
)
def test_critical_incident_and_resolution_evidence(field: str, value: Any) -> None:
    record = pilot()
    incident = issue()
    incident[field] = value
    record["attempts"][0]["issues"] = [incident]
    with pytest.raises(ValidationError):
        registry(record)


def test_consumer_confirmation_cannot_be_synthetic() -> None:
    record = pilot(True)
    incident = issue()
    incident.update(
        status="consumer_confirmed",
        regression_sha256="d" * 64,
        consumer_confirmation_sha256="e" * 64,
    )
    record["attempts"][0]["issues"] = [incident]
    registry(record)
    record.update(
        kind="synthetic_replay", independent=False, consent="synthetic_only", consent_sha256=None
    )
    with pytest.raises(ValidationError):
        registry(record)


@pytest.mark.parametrize("level", ["pilot", "attempt", "issue"])
def test_duplicate_identifiers_rejected(level: str) -> None:
    record = pilot()
    records = [record]
    if level == "pilot":
        records.append(copy.deepcopy(record))
    elif level == "attempt":
        record["attempts"][-1]["id"] = record["attempts"][0]["id"]
    else:
        record["attempts"][0]["issues"] = [issue(), issue()]
    with pytest.raises(ValidationError):
        registry(*records)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema":"equiframe-adoption-1","pilots":[],"pilots":[]}',
        b'{"schema":"equiframe-adoption-1","pilots":NaN}',
        b"\xff",
        b"[]",
        b'{"schema":"future","pilots":[]}',
        b"{}",
        b"[" * 2000,
    ],
)
def test_invalid_json_does_not_echo_private_values(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "private-name.json"
    path.write_bytes(payload)
    completed = subprocess.run(
        [sys.executable, str(TOOL), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 2
    assert completed.stdout == "Adoption record invalid or unreadable; no acceptance established\n"
    assert completed.stderr == ""


def test_reader_rejects_directory_and_oversized_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        M["read_registry"](tmp_path)
    path = tmp_path / "large.json"
    path.write_bytes(b" " * (M["MAX_BYTES"] + 1))
    with pytest.raises(ValueError):
        M["read_registry"](path)


def test_reader_rejects_links(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text("{}", encoding="utf-8")
    link = tmp_path / "linked.json"
    symlink_or_skip(link, path)
    with pytest.raises(ValueError):
        M["read_registry"](link)


def test_schema_output_has_closed_fields_and_version() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--schema"], capture_output=True, text=True
    )
    assert completed.returncode == 0
    schema = json.loads(completed.stdout)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema"]["const"] == "equiframe-adoption-1"


@pytest.mark.parametrize("second_context", ["refactor_python", "sql_duckdb"])
def test_one_history_per_project_context(second_context: str) -> None:
    first, second = pilot(True), pilot(True)
    second.update(id="record-two", context=second_context)
    second["attempts"][-1].update(usefulness="blocked", integration_retained=False)
    if second_context == "refactor_python":
        with pytest.raises(ValidationError):
            registry(first, second)
    else:
        assert summary(first, second)["independent_project_attestations"] == 1


@pytest.mark.parametrize("where", ["initial", "latest", "both"])
def test_open_critical_issue_cannot_be_hidden_or_count_as_retained(where: str) -> None:
    record = pilot(True)
    for index in [0] if where == "initial" else [1] if where == "latest" else [0, 1]:
        record["attempts"][index]["issues"] = [issue()]
    assert summary(record)["retained_project_attestations"] == 0
    assert summary(record)["human_attempts"] == 2


@pytest.mark.parametrize(
    "status", ["open", "fix_proposed", "regression_verified", "consumer_confirmed"]
)
def test_critical_resolution_requires_affected_consumer(status: str) -> None:
    record = pilot(True)
    record["attempts"][0]["issues"] = [issue()]
    later = issue()
    later.update(
        status=status,
        regression_sha256="d" * 64
        if status in {"regression_verified", "consumer_confirmed"}
        else None,
        consumer_confirmation_sha256="e" * 64 if status == "consumer_confirmed" else None,
    )
    record["attempts"][1]["issues"] = [later]
    assert summary(record)["retained_project_attestations"] == int(status == "consumer_confirmed")


def test_later_safe_abstention_can_retain_already_completed_integration() -> None:
    record = pilot(True)
    record["attempts"][1] = attempt(True, "not_evaluable")
    assert summary(record)["retained_project_attestations"] == 1


def test_downgraded_priority_cannot_clear_known_critical_incident() -> None:
    record = pilot(True)
    record["attempts"][0]["issues"] = [issue()]
    later = issue()
    later.update(false_equivalent=False, priority="P3")
    record["attempts"][1]["issues"] = [later]
    assert summary(record)["retained_project_attestations"] == 0


def test_partial_difference_does_not_establish_initial_integration() -> None:
    record = pilot(True)
    record["attempts"][0] = attempt(state="different")
    record["attempts"][0]["expected"]["complete"] = False
    record["attempts"][0]["observed"]["complete"] = False
    assert summary(record)["retained_project_attestations"] == 0


@pytest.mark.parametrize("include_later_change", [False, True])
def test_failed_install_does_not_penalize_honest_later_retention(
    include_later_change: bool,
) -> None:
    record = pilot(True)
    record["attempts"][0].update(
        observed=None, expected=None, contract_sha256=None, usefulness="blocked"
    )
    record["attempts"][1].update(integration_retained=False)
    if include_later_change:
        later = copy.deepcopy(record["attempts"][1])
        later.update(
            id="third",
            occurred_at="2026-10-08T12:00:00Z",
            change_sha256="3" * 64,
            integration_retained=True,
        )
        record["attempts"].append(later)
    result = summary(record)
    assert result["human_attempts"] == 3 if include_later_change else result["human_attempts"] == 2
    assert result["retained_project_attestations"] == int(include_later_change)


def test_change_after_failed_install_is_not_change_after_integration() -> None:
    record = pilot(True)
    record["attempts"][0].update(usefulness="blocked")
    later = copy.deepcopy(record["attempts"][1])
    later.update(id="third", occurred_at="2026-10-08T12:00:00Z")
    record["attempts"].append(later)
    assert summary(record)["retained_project_attestations"] == 0
