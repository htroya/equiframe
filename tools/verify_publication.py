"""Check identified release artifacts without granting or performing publication.

Historical STEP9 candidates remain closed. The manual v2 policy additionally
checks an external, exact-byte factual packet for a selected index. A packet
records claims for independent inspection: it cannot authenticate an account,
human approval, scanner execution or the index. This tool never uploads.
"""

import argparse
import hashlib
import json
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REQUIRED = frozenset(
    (
        "locked_sync",
        "ruff_check",
        "ruff_format",
        "mypy",
        "assets",
        "pytest",
        "build",
        "twine",
        "distribution",
    )
)
POLICY = Path(__file__).with_name("release-policy.json")
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
INDICES = {
    "testpypi": "https://test.pypi.org/legacy/",
    "pypi": "https://upload.pypi.org/legacy/",
}
MANUAL_GATES = frozenset(
    (
        "license_review",
        "public_documentation",
        "name_control",
        "publisher_protection",
        "dependency_security_review",
        "source_security_review",
        "independent_release_review",
        "owner_release_authorization",
    )
)
PROMOTION_GATES = frozenset(("testpypi_artifact_identity", "testpypi_downloaded_consumer"))
NAME_CONTROL_MODES = ("existing_projects", "initial_upload_attempt")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON member")
        document[key] = value
    return document


def regular(path: Path, root: Path) -> None:
    """Reject links and special files, including links in parent directories."""
    if not path.is_relative_to(root):
        raise ValueError("candidate path leaves the selected directory")
    for parent in reversed(root.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("candidate ancestors must be real directories")
    current = root
    info = current.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("candidate root must be a real directory")
    for part in path.relative_to(root).parts[:-1]:
        current /= part
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("candidate parent must be a real directory")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("candidate files must be regular files, not links")


def read_json(path: Path, root: Path) -> dict[str, Any]:
    regular(path, root)
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("release JSON exceeds the size limit")
    result = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_bad_constant)
    if not isinstance(result, dict):
        raise ValueError("release JSON must be an object")
    return result


def _bad_constant(value: str) -> None:
    raise ValueError("nonfinite JSON number: " + value)


def file_identity(path: Path, root: Path) -> dict[str, Any]:
    regular(path, root)
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise ValueError("release artifact exceeds the size limit")
    digest = hashlib.sha256()
    actual_size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            actual_size += len(chunk)
            if actual_size > MAX_ARTIFACT_BYTES:
                raise ValueError("release artifact exceeds the size limit")
            digest.update(chunk)
    if actual_size != size:
        raise ValueError("release artifact changed while reading")
    return {"file": path.name, "size_bytes": size, "sha256": digest.hexdigest()}


def _stages(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == len(REQUIRED)
        and all(isinstance(item, str) for item in value)
        and set(value) == REQUIRED
    )


def _legacy_pending(policy: dict[str, Any]) -> list[str]:
    if policy.get("schema_version") != "1.0" or policy.get("publication_enabled") is not False:
        raise ValueError("invalid historical closed publication policy")
    pending = policy.get("pending_decisions")
    if (
        not isinstance(pending, list)
        or not pending
        or not all(isinstance(value, str) and value for value in pending)
    ):
        raise ValueError("pending release decisions must remain explicit")
    return pending


def _manual_policy(policy: dict[str, Any]) -> None:
    """Reject policies that silently drop a technical or factual gate."""
    if (
        policy.get("schema_version") != "2.0"
        or policy.get("publication_enabled") is not False
        or policy.get("publication_mode") != "manual"
        or policy.get("indices") != INDICES
        or policy.get("distributions") != ["equiframe", "equiframe-benchmark"]
        or policy.get("name_control_modes") != list(NAME_CONTROL_MODES)
        or not isinstance(policy.get("target_version"), str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", policy["target_version"])
        or not _stages(policy.get("required_technical_stages"))
        or type(policy.get("maximum_observation_age_days")) is not int
        or not 1 <= policy["maximum_observation_age_days"] <= 7
    ):
        raise ValueError("invalid manual publication policy")
    required = policy.get("required_gates")
    if not isinstance(required, dict) or set(required) != set(INDICES):
        raise ValueError("both index gate sets are required")
    for target, expected in (
        ("testpypi", MANUAL_GATES),
        ("pypi", MANUAL_GATES | PROMOTION_GATES),
    ):
        actual = required[target]
        if (
            not isinstance(actual, list)
            or len(actual) != len(expected)
            or not all(isinstance(value, str) for value in actual)
            or set(actual) != expected
        ):
            raise ValueError("manual publication gates cannot be weakened")
    _legacy_pending(policy.get("legacy_policy", {}))


def _inventory_equal(value: object, expected: list[dict[str, Any]]) -> bool:
    return (
        isinstance(value, list)
        and len(value) == len(expected)
        and all(
            isinstance(item, dict)
            and set(item) == {"file", "size_bytes", "sha256"}
            and isinstance(item["file"], str)
            and type(item["size_bytes"]) is int
            and item["size_bytes"] >= 0
            and isinstance(item["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None
            for item in value
        )
        and sorted(value, key=lambda item: str(item.get("file")))
        == sorted(expected, key=lambda item: item["file"])
    )


def _zero(value: object) -> bool:
    return type(value) is int and value == 0


def _name_control_pass(details: dict[str, Any], target: str) -> bool:
    """Distinguish an existing ownership claim from a first-upload attempt.

    Public 404 observations establish no reservation, ownership or admission.
    Both routes still depend on the independent account and owner-task gates.
    No claim supplied here is authenticated by this offline inspector.
    """
    if details.get("index") != target or details.get("projects") != [
        "equiframe",
        "equiframe-benchmark",
    ]:
        return False
    common = {"index", "projects", "mode"}
    if details.get("mode") == "existing_projects":
        return (
            set(details) == common | {"authenticated_owner_verified"}
            and details["authenticated_owner_verified"] is True
        )
    if details.get("mode") != "initial_upload_attempt":
        return False
    if (
        set(details)
        != common
        | {
            "authenticated_account_verified",
            "observations",
            "absence_is_not_reservation_ownership_or_acceptance",
        }
        or details["authenticated_account_verified"] is not True
        or details["absence_is_not_reservation_ownership_or_acceptance"] is not True
    ):
        return False
    observations = details["observations"]
    return (
        isinstance(observations, list)
        and len(observations) == 2
        and all(
            isinstance(item, dict)
            and set(item) == {"project", "http_status"}
            and isinstance(item["project"], str)
            and item["project"] in details["projects"]
            and type(item["http_status"]) is int
            and item["http_status"] == 404
            for item in observations
        )
        and {item["project"] for item in observations} == set(details["projects"])
    )


def _details_pass(
    gate: str, details: dict[str, Any], target: str, artifacts: list[dict[str, Any]]
) -> bool:
    if gate == "license_review":
        return (
            details.get("core_license") == "MIT AND Apache-2.0"
            and details.get("benchmark_license") == "MIT"
            and details.get("third_party_notices_verified") is True
            and details.get("rights_scope_verified") is True
        )
    if gate == "public_documentation":
        url = details.get("url")
        if not isinstance(url, str):
            return False
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and details.get("unauthenticated") is True
            and type(details.get("http_status")) is int
            and details["http_status"] == 200
        )
    if gate == "name_control":
        return _name_control_pass(details, target)
    if gate == "publisher_protection":
        return (
            details.get("index") == target
            and details.get("two_factor_verified") is True
            and details.get("publisher_roles_verified") is True
            and details.get("credential_handling")
            in ("local_secret_store", "interactive_hidden_prompt")
        )
    if gate in ("dependency_security_review", "source_security_review"):
        return (
            details.get("review_complete") is True
            and _zero(details.get("unresolved_high_or_critical"))
            and _zero(details.get("unavailable_checks"))
        )
    if gate == "independent_release_review":
        return details.get("independent") is True and _zero(details.get("open_blocking_findings"))
    if gate == "owner_release_authorization":
        return (
            details.get("index") == target and details.get("explicit_instruction_verified") is True
        )
    if gate == "testpypi_artifact_identity":
        return details.get("index") == "testpypi" and _inventory_equal(
            details.get("observed_artifacts"), artifacts
        )
    if gate == "testpypi_downloaded_consumer":
        return (
            details.get("index") == "testpypi"
            and details.get("pip_check") is True
            and details.get("installed_identity_verified") is True
            and details.get("functional_cases_passed") is True
            and _inventory_equal(details.get("downloaded_artifacts"), artifacts)
        )
    return False


def check_gate_packet(
    path: Path | None,
    *,
    policy: dict[str, Any],
    target: str,
    commit: str,
    artifacts: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, str]], dict[str, Any] | None]:
    """Check factual consistency; a matching packet never authenticates its claims."""
    required = policy["required_gates"][target]
    if path is None:
        return ["Factual gate packet is absent."], [], None
    path = path.absolute()
    packet = read_json(path, path.parent)
    if (
        set(packet)
        != {"schema_version", "target", "version", "source_commit", "artifacts", "gates"}
        or packet.get("schema_version") != "2.0"
        or packet.get("target") != target
        or packet.get("version") != policy["target_version"]
        or packet.get("source_commit") != commit
        or not _inventory_equal(packet.get("artifacts"), artifacts)
    ):
        raise ValueError("factual packet does not identify the exact index, source and artifacts")
    gates = packet.get("gates")
    if not isinstance(gates, list) or len(gates) > len(required):
        raise ValueError("invalid factual gate inventory")
    observed: dict[str, dict[str, Any]] = {}
    for gate in gates:
        if (
            not isinstance(gate, dict)
            or set(gate) != {"id", "state", "observed_at", "basis", "details"}
            or not isinstance(gate.get("id"), str)
            or gate["id"] not in required
            or gate["id"] in observed
            or gate.get("state") not in ("PASS", "FAIL", "UNKNOWN")
            or not isinstance(gate.get("basis"), str)
            or not 1 <= len(gate["basis"].strip()) <= 2000
            or not isinstance(gate.get("details"), dict)
        ):
            raise ValueError("invalid or repeated factual gate")
        observed[gate["id"]] = gate
    blockers: list[str] = []
    states: list[dict[str, str]] = []
    now = datetime.now(timezone.utc)
    for name in required:
        gate = observed.get(name)
        state = "MISSING" if gate is None else gate["state"]
        reason = ""
        if gate is not None:
            try:
                value = gate["observed_at"]
                stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("timezone required")
                age = now - stamp.astimezone(timezone.utc)
                if (
                    not -timedelta(minutes=5)
                    <= age
                    <= timedelta(days=policy["maximum_observation_age_days"])
                ):
                    reason = "observation is stale or in the future"
            except (ValueError, TypeError, AttributeError):
                reason = "valid dated observation is absent"
            if state == "PASS" and not _details_pass(name, gate["details"], target, artifacts):
                reason = "required factual details do not establish this gate"
        if state != "PASS" or reason:
            blockers.append(name + ": " + (reason or state))
        record = {"id": name, "state": state, "blocking_reason": reason}
        if name == "name_control" and gate is not None:
            mode = gate["details"].get("mode")
            if mode in NAME_CONTROL_MODES:
                record["name_control_mode"] = mode
        states.append(record)
    return blockers, states, file_identity(path, path.parent)


def check_manifest(path: Path, root: Path, commit: str) -> dict[str, Any]:
    manifest = read_json(path, root)
    if manifest.get("schema_version") != "1.0":
        raise ValueError("unsupported release manifest version")
    name = manifest.get("distribution")
    if name not in {"equiframe", "equiframe-benchmark"}:
        raise ValueError("unexpected distribution")
    expected_name = "core-manifest.json" if name == "equiframe" else "benchmark-manifest.json"
    if path.name != expected_name:
        raise ValueError("distribution manifest filename mismatch")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[a-z0-9.]+)?", version
    ):
        raise ValueError("invalid bounded release version")
    if manifest.get("source_commit") != commit or manifest.get("published") is not False:
        raise ValueError("candidate does not identify the approved unpublished commit")
    source = manifest.get("source_validation", {})
    if (
        not isinstance(source, dict)
        or set(source) != {"git_head", "package_clean", "project_tracked"}
        or source["git_head"] != commit
        or source["package_clean"] is not True
        or source["project_tracked"] is not True
    ):
        raise ValueError("candidate source is unverified")
    checks = manifest.get("check_completion", {})
    for field in (
        "required_stages",
        "successful_stages",
        "source_bound_stages",
        "local_dependency_runtime_bound_stages",
    ):
        if not _stages(checks.get(field)):
            raise ValueError("incomplete or unbound checks: " + field)
    for field in ("missing_stages", "unbound_stages", "local_dependency_runtime_unbound_stages"):
        if checks.get(field) != []:
            raise ValueError("incomplete or unbound checks: " + field)
    if type(checks.get("failed_commands")) is not int or checks["failed_commands"] != 0:
        raise ValueError("failed or malformed check count")
    artifacts = manifest.get("artifacts")
    stem = name.replace("-", "_") + "-" + version
    expected = {stem + "-py3-none-any.whl", stem + ".tar.gz"}
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ValueError("exact wheel and sdist inventory required")
    observed: list[dict[str, Any]] = []
    for item in artifacts:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("file"), str)
            or item["file"] not in expected
            or type(item.get("size_bytes")) is not int
        ):
            raise ValueError("unexpected artifact name")
        identity = file_identity(path.parent / item["file"], root)
        if item != identity:
            raise ValueError("artifact hash, size or metadata differs")
        observed.append(identity)
    if {item["file"] for item in observed} != expected:
        raise ValueError("repeated or missing artifact")
    blockers = manifest.get("publication_blockers")
    if not isinstance(blockers, list) or not all(
        isinstance(value, str) and value for value in blockers
    ):
        raise ValueError("publication blockers must be an explicit list")
    return {"distribution": name, "version": version, "artifacts": observed, "blockers": blockers}


def check_candidate(
    root: Path, commit: str, *, target: str | None = None, gate_packet: Path | None = None
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("exact lowercase 40-character commit required")
    # abspath preserves a final symlink so regular() can reject it.
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("candidate root must be a real directory")
    manifests = sorted(root.rglob("*-manifest.json"))
    if len(manifests) != 2:
        raise ValueError("exactly two release manifests required")
    checked = [check_manifest(path, root, commit) for path in manifests]
    if {item["distribution"] for item in checked} != {"equiframe", "equiframe-benchmark"}:
        raise ValueError("both unique distributions are required")
    if len({item["version"] for item in checked}) != 1:
        raise ValueError("core and benchmark versions must match")
    core = next(item for item in checked if item["distribution"] == "equiframe")
    benchmark_path = next(path for path in manifests if path.name == "benchmark-manifest.json")
    benchmark = read_json(benchmark_path, root)
    dependencies = benchmark["check_completion"].get("dependency_artifacts")
    expected_core = [item for item in core["artifacts"] if item["file"].endswith(".whl")]
    if dependencies != expected_core:
        raise ValueError("benchmark checks must identify the exact core wheel")
    policy = read_json(POLICY, POLICY.parent)
    legacy = policy.get("schema_version") == "1.0"
    if not legacy:
        _manual_policy(policy)
    historical = legacy or core["version"] != policy["target_version"]
    pending: list[str]
    states: list[dict[str, str]] = []
    packet_identity = None
    if historical:
        if target is not None or gate_packet is not None:
            raise ValueError("historical candidates cannot enter the manual publication route")
        pending = _legacy_pending(policy if legacy else policy["legacy_policy"])
    elif target is None:
        if gate_packet is not None:
            raise ValueError("the factual packet requires an explicit target index")
        pending = ["An explicit target index and its factual gate packet are required."]
    else:
        if target not in INDICES:
            raise ValueError("unsupported publication target")
        artifacts = [artifact for item in checked for artifact in item["artifacts"]]
        pending, states, packet_identity = check_gate_packet(
            gate_packet, policy=policy, target=target, commit=commit, artifacts=artifacts
        )
        pending.extend(blocker for item in checked for blocker in item["blockers"])
    report: dict[str, Any] = {
        "schema_version": "1.0" if historical else "2.0",
        "source_commit": commit,
        "artifacts_verified": True,
        "publication_ready": not pending,
        "published": False,
        "policy": file_identity(POLICY, POLICY.parent),
        "pending_decisions": pending,
        "candidates": checked,
        "limitations": [
            "Receipts and hashes do not authenticate execution or human approval.",
            "Dependency and source-security reviews must be separately inspected.",
            "This tool performs no network requests, copies, upload or signing.",
        ],
    }
    if not historical:
        name_control_mode = next(
            (item.get("name_control_mode") for item in states if item["id"] == "name_control"),
            None,
        )
        report.update(
            target=target,
            endpoint=INDICES.get(target) if target is not None else None,
            gate_packet=packet_identity,
            gate_states=states,
            authorization_authenticated=False,
            name_control_mode=name_control_mode,
            readiness_scope=(
                "Local consistency for an authorized initial upload attempt only; "
                "404 establishes no reservation, ownership or admission. "
                "Index acceptance must be observed after upload."
                if name_control_mode == "initial_upload_attempt"
                else "Local consistency only; independently inspect every factual claim."
            ),
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(INDICES))
    parser.add_argument("--gate-packet", type=Path)
    args = parser.parse_args()
    try:
        result = check_candidate(
            args.candidate_root, args.commit, target=args.target, gate_packet=args.gate_packet
        )
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        raise SystemExit("Release candidate rejected: " + str(error)) from None
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    except OSError:
        parser.exit(2, "Readiness output requires a new writable file.\n")
    if result["publication_ready"]:
        if result.get("name_control_mode") == "initial_upload_attempt":
            print(
                "Initial upload attempt checks passed; 404 establishes no reservation, "
                "ownership or admission. No upload or authorization was performed."
            )
        else:
            print("Candidate consistency checks passed; no upload or authorization was performed.")
        raise SystemExit(0)
    print("Artifact checks passed; public release remains blocked by recorded decisions.")
    raise SystemExit(3)


if __name__ == "__main__":
    main()
