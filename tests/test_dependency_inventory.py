"""Independent miniature distributions exercise release evidence, never real network."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import runpy
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timedelta
from datetime import timezone as _timezone
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError
from packaging.markers import default_environment

UTC = _timezone.utc

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "dependency_inventory.py"))


def test_metadata_probe_collects_declared_and_british_license_files(tmp_path: Path) -> None:
    site = tmp_path / "site"
    info = site / "sample-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "licenses").mkdir()
    contents = {
        "LICENCE.rst": b"British spelling license",
        "mit.LICENSE": b"Legacy declared license",
        "AUTHORS.rst": b"Declared attribution",
        "licenses/terms.txt": b"PEP 639 declared terms",
        "COPYRIGHT.txt": b"Copyright notice",
    }
    (info / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: sample\nVersion: 1.0\n"
        "License-File: mit.LICENSE\nLicense-File: AUTHORS.rst\n"
        "License-File: terms.txt\nLicense-File: ../outside.txt\n\n",
        encoding="utf-8",
    )
    for name, data in contents.items():
        (info / name).write_bytes(data)
    (site / "outside.txt").write_bytes(b"Outside metadata boundary")
    entries = [f"{info.name}/{name},," for name in ["METADATA", "RECORD", *contents]]
    entries.append("../outside.txt,,")
    (info / "RECORD").write_text("\n".join(entries) + "\n", encoding="utf-8")
    # A real isolated interpreter discovers only this on-disk distribution;
    # no dependency module is imported and no distribution enumeration is mocked.
    source = f"import sys; sys.path.insert(0, {str(site)!r});\n" + MODULE["METADATA_PROBE"]
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", source],
        check=True,
        capture_output=True,
        timeout=30,
    )
    distributions = json.loads(result.stdout)["distributions"]
    assert [item["name"] for item in distributions] == ["sample"]
    assert distributions[0]["license_files"] == sorted(
        [
            {
                "path": f"{info.name}/{name}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
            for name, data in contents.items()
        ],
        key=lambda item: item["path"],
    )


def wheel(path: Path, metadata: str, extra: str | None = None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("sample-1.0.dist-info/METADATA", metadata)
        if extra:
            if "\\" in extra:
                # ZipInfo.__init__ normalizes backslashes on Windows. Assigning the
                # raw member afterward creates the same hostile ZIP bytes everywhere.
                member = zipfile.ZipInfo("placeholder")
                member.filename = extra
                archive.writestr(member, "invalid")
            else:
                archive.writestr(extra, "invalid")


def sdist(path: Path, metadata: str, link: bool = False) -> None:
    with tarfile.open(path, "w:gz") as archive:
        data = metadata.encode()
        member = tarfile.TarInfo("sample-1.0/PKG-INFO")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
        if link:
            member = tarfile.TarInfo("sample-1.0/link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            archive.addfile(member)


@pytest.fixture
def sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    package = tmp_path / "package"
    package.mkdir()
    project = """[build-system]
requires = ["builder==1.0"]
[project]
name = "sample"
version = "1.0"
requires-python = ">=3.12,<3.14"
dependencies = ["dep>=2,<3"]
[project.optional-dependencies]
fast = ["fast>=3,<4"]
[dependency-groups]
dev = ["tester==1.0"]
"""
    (package / "pyproject.toml").write_text(project)
    locked = """version = 1
[[package]]
name = "sample"
version = "1.0"
source = {editable = "."}
dependencies = [{name = "dep"}]
[package.optional-dependencies]
fast = [{name = "fast"}]
[package.dev-dependencies]
dev = [{name = "tester"}]
"""
    for name, version in [("dep", "2.0"), ("fast", "3.0"), ("tester", "1.0"), ("builder", "1.0")]:
        locked += f'''\n[[package]]
name = "{name}"
version = "{version}"
source = {{registry = "https://pypi.org/simple"}}
'''
    (package / "uv.lock").write_text(locked)
    metadata = (
        "Metadata-Version: 2.4\nName: sample\nVersion: 1.0\n"
        "Requires-Python: >=3.12,<3.14\nRequires-Dist: dep>=2,<3\n"
        "Requires-Dist: fast>=3,<4; extra == 'fast'\nProvides-Extra: fast\n\n"
    )
    whl, tar = package / "sample-1.0-py3-none-any.whl", package / "sample-1.0.tar.gz"
    wheel(whl, metadata)
    sdist(tar, metadata)
    environment = dict(default_environment(), python_version="3.12", python_full_version="3.12.12")
    distributions = [
        {
            "name": n,
            "version": v,
            "license_expression": "MIT",
            "license": None,
            "license_classifiers": [],
            "license_files": [],
            "metadata_sha256": "a" * 64,
        }
        for n, v in [
            ("sample", "1.0"),
            ("dep", "2.0"),
            ("fast", "3.0"),
            ("tester", "1.0"),
            ("builder", "1.0"),
        ]
    ]
    snapshot = {"environment": environment, "distributions": distributions}
    for method in ["generate", "verify_inventory"]:
        monkeypatch.setitem(MODULE[method].__globals__, "installed_metadata", lambda _: snapshot)
    result = {
        "package": package,
        "artifacts": [whl, tar],
        "snapshot": snapshot,
        "metadata": metadata,
        "output": tmp_path / "evidence",
    }
    return result


def generate(sample: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = MODULE["generate"](
        sample["package"], sample["artifacts"], [], Path("unused"), sample["output"]
    )
    return result


def verify(sample: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = MODULE["verify_inventory"](
        sample["output"] / "inventory.json",
        sample["package"],
        sample["artifacts"],
        [],
        Path("unused"),
    )
    return result


def test_exact_artifact_boms_and_disjoint_profiles(sample: dict[str, Any]) -> None:
    inventory = generate(sample)
    assert verify(sample) == inventory
    profiles = {p["name"]: p for p in inventory["profiles"]}
    assert profiles["base"]["components"] == ["dep", "sample"]
    assert profiles["extra:fast"]["components"] == ["dep", "fast", "sample"]
    assert profiles["build"]["components"] == ["builder"]
    assert profiles["development"]["components"] == ["dep", "fast", "sample", "tester"]
    assert inventory["project"]["declared"]["runtime"] == ["dep>=2,<3"]
    for artifact in inventory["artifacts"]:
        bom = json.loads((sample["output"] / (artifact["filename"] + ".cdx.json")).read_text())
        assert bom["specVersion"] == "1.6"
        assert bom["metadata"]["component"]["hashes"][0]["content"] == artifact["sha256"]
        MODULE["validate_bom"](bom)


def test_dynamic_project_is_bound_to_artifacts_without_running_a_backend(
    sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    package = sample["package"]
    project = package / "pyproject.toml"
    project.write_text(project.read_text().replace('version = "1.0"', 'dynamic = ["version"]'))
    lock = package / "uv.lock"
    lock.write_text(lock.read_text().replace('name = "sample"\nversion = "1.0"', 'name = "sample"'))

    def unexpected_execution(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("inventory must not execute backend, Git or project code")

    monkeypatch.setattr(MODULE["subprocess"], "run", unexpected_execution)
    inventory = generate(sample)
    assert inventory["project"]["version"] == "1.0"
    assert verify(sample) == inventory
    assert all(a["metadata"]["version"] == "1.0" for a in inventory["artifacts"])


def test_dynamic_project_rejects_disagreeing_wheel_and_sdist_versions(
    sample: dict[str, Any],
) -> None:
    project = sample["package"] / "pyproject.toml"
    project.write_text(project.read_text().replace('version = "1.0"', 'dynamic = ["version"]'))
    wheel(sample["artifacts"][0], sample["metadata"].replace("Version: 1.0", "Version: 1.1"))
    with pytest.raises(ValueError, match="concordant identified artifact versions"):
        generate(sample)


@pytest.mark.parametrize("mutation", ["artifact", "lock", "metadata", "inventory", "sbom"])
def test_verifier_rederives_instead_of_trusting_claims(
    sample: dict[str, Any], mutation: str
) -> None:
    generate(sample)
    if mutation == "artifact":
        wheel(sample["artifacts"][0], sample["metadata"], "extra.txt")
    elif mutation == "lock":
        with (sample["package"] / "uv.lock").open("a") as stream:
            stream.write("\n# changed lock bytes\n")
    elif mutation == "metadata":
        sample["snapshot"]["distributions"][0]["license_expression"] = "BSD-3-Clause"
    elif mutation == "inventory":
        path = sample["output"] / "inventory.json"
        data = json.loads(path.read_text())
        data["components"] = []
        MODULE["write_json"](path, data)
    else:
        path = next(sample["output"].glob("*.cdx.json"))
        data = json.loads(path.read_text())
        data["components"] = []
        MODULE["write_json"](path, data)
    with pytest.raises(ValueError, match="differs"):
        verify(sample)


@pytest.mark.parametrize("member", ["../escape", "/escape", "C:/escape", "a\\escape", "a/./escape"])
def test_archive_paths_rejected_without_extraction(sample: dict[str, Any], member: str) -> None:
    wheel(sample["artifacts"][0], sample["metadata"], member)
    with pytest.raises(ValueError, match="Unsafe"):
        generate(sample)
    assert not (sample["package"].parent / "escape").exists()


def test_archive_symlinks_rejected(sample: dict[str, Any]) -> None:
    sdist(sample["artifacts"][1], sample["metadata"], link=True)
    with pytest.raises(ValueError, match="links"):
        generate(sample)


def test_duplicate_metadata_rejected(sample: dict[str, Any]) -> None:
    with zipfile.ZipFile(sample["artifacts"][0], "a") as archive:
        archive.writestr("another-1.0.dist-info/METADATA", sample["metadata"])
    with pytest.raises(ValueError, match="exactly one"):
        generate(sample)


def test_stale_artifact_declaration_rejected(sample: dict[str, Any]) -> None:
    wheel(sample["artifacts"][0], sample["metadata"].replace("dep>=2,<3", "dep>=1"))
    with pytest.raises(ValueError, match="does not match"):
        generate(sample)


def test_stale_lock_direct_requirement_rejected(sample: dict[str, Any]) -> None:
    path = sample["package"] / "uv.lock"
    path.write_text(path.read_text().replace('version = "2.0"', 'version = "1.0"'))
    sample["snapshot"]["distributions"][1]["version"] = "1.0"
    with pytest.raises(ValueError, match="violates artifact declaration"):
        generate(sample)


def test_lock_omission_rejected(sample: dict[str, Any]) -> None:
    path = sample["package"] / "uv.lock"
    path.write_text(
        path.read_text().replace('dependencies = [{name = "dep"}]', "dependencies = []")
    )
    with pytest.raises(ValueError, match="graph violates"):
        generate(sample)


def test_installed_mismatch_rejected_and_missing_is_unknown(sample: dict[str, Any]) -> None:
    sample["snapshot"]["distributions"][1]["version"] = "999"
    with pytest.raises(ValueError, match="disagrees"):
        generate(sample)
    sample["snapshot"]["distributions"].pop(1)
    inventory = generate(sample)
    component = next(c for c in inventory["components"] if c["name"] == "dep")
    assert component["license"]["status"] == "unknown_not_installed"
    assert component["installed_version_verified"] is False


def test_ambiguous_license_not_invented() -> None:
    evidence = MODULE["license_evidence"](
        {
            "license": "BSD License",
            "license_expression": None,
            "license_classifiers": ["License :: BSD"],
        }
    )
    assert evidence["expression"] is None
    assert evidence["status"] == "review_required"


def test_official_schema_enforced(sample: dict[str, Any]) -> None:
    inventory = generate(sample)
    bom = MODULE["create_bom"](inventory, inventory["artifacts"][0])
    bom["components"][0]["type"] = "made-up-type"
    with pytest.raises(ValidationError):
        MODULE["validate_bom"](bom)


def snapshot(name: str, version: str, provider: str) -> dict[str, Any]:
    body = (
        {"info": {"name": name, "version": version}, "vulnerabilities": []}
        if provider == "pypi"
        else {}
    )
    raw = json.dumps(body)
    return {
        "provider": provider,
        "name": name,
        "version": version,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "url": f"https://pypi.org/pypi/{name}/{version}/json"
        if provider == "pypi"
        else "https://api.osv.dev/v1/query",
        "status": "complete",
        "pages": [
            {
                "request": None
                if provider == "pypi"
                else {"package": {"name": name, "ecosystem": "PyPI"}, "version": version},
                "response": body,
                "response_raw_utf8": raw,
                "response_sha256": MODULE["sha"](raw.encode()),
            }
        ],
    }


def replace_response(value: dict[str, Any], body: dict[str, Any]) -> None:
    page = value["pages"][0]
    page["response"] = body
    page["response_raw_utf8"] = json.dumps(body)
    page["response_sha256"] = MODULE["sha"](page["response_raw_utf8"].encode())


def audit(sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    generate(sample)
    monkeypatch.setitem(MODULE["scan"].__globals__, "fetch_snapshot", snapshot)
    inventory = sample["output"] / "inventory.json"
    output = sample["output"] / "audit"
    allowlist = sample["output"] / "public-allowlist.json"
    components = json.loads(inventory.read_text())["components"]
    allowlist.write_text(
        json.dumps(
            [
                {"name": c["name"], "version": c["version"]}
                for c in components
                if c["source"] == {"registry": "https://pypi.org/simple"}
            ]
        )
    )
    plan = sample["output"] / "request-plan.json"
    plan.write_text(json.dumps(MODULE["prepare_scan"](inventory, allowlist)))
    report = MODULE["scan"](inventory, output, allowlist, plan)
    assert report["summary"]["status"] == "no_known_advisories"
    return inventory, output / "advisories.json"


def test_advisory_evidence_validates(
    sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory, report = audit(sample, monkeypatch)
    assert MODULE["verify_scan"](inventory, report)["status"] == "no_known_advisories"


@pytest.mark.parametrize(
    "mutation",
    ["stale", "future", "missing", "summary", "bytes", "identity", "traversal", "duplicate"],
)
def test_advisory_tampering_fails_closed(
    sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    inventory, path = audit(sample, monkeypatch)
    report = json.loads(path.read_text())
    reference = report["snapshots"][0]
    raw_path = path.parent / reference["filename"]
    raw = json.loads(raw_path.read_text())
    if mutation in {"stale", "future", "identity"}:
        if mutation == "identity":
            raw["pages"][0]["request"]["version"] = "wrong"
        else:
            delta = timedelta(days=-2 if mutation == "stale" else 2)
            raw["retrieved_at"] = (datetime.now(UTC) + delta).isoformat()
        MODULE["write_json"](raw_path, raw)
        report["snapshots"][0] = MODULE["file_ref"](raw_path)
    elif mutation == "bytes":
        raw_path.write_text("{}")
    elif mutation == "missing":
        report["snapshots"].pop()
    elif mutation == "summary":
        report["summary"]["queries"] = []
    elif mutation == "traversal":
        reference["filename"] = "../outside.json"
    elif mutation == "duplicate":
        report["snapshots"].append(copy.deepcopy(reference))
    MODULE["write_json"](path, report)
    with pytest.raises(ValueError):
        MODULE["verify_scan"](inventory, path)


def test_network_error_stays_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_: Any) -> None:
        raise OSError("network unavailable")

    monkeypatch.setitem(MODULE["fetch_snapshot"].__globals__, "request_json", blocked)
    result = MODULE["fetch_snapshot"]("sample", "1.0", "osv")
    summary = MODULE["summarize_snapshots"]([result])
    assert summary["status"] == "unknown"
    assert summary["queries"][0]["advisory_ids"] is None


def test_findings_ghsa_alias_and_withdrawal_preserved() -> None:
    value = snapshot("sample", "1.0", "osv")
    replace_response(
        value,
        {
            "vulns": [
                {"id": "PYSEC-2026-1", "aliases": ["GHSA-aaaa-bbbb-cccc"]},
                {"id": "withdrawn", "withdrawn": "2026-10-05T00:00:00Z"},
            ]
        },
    )
    result = MODULE["summarize_snapshots"]([value])
    assert result["status"] == "findings"
    assert result["queries"][0]["ghsa_ids"] == ["GHSA-aaaa-bbbb-cccc"]
    assert result["queries"][0]["advisory_ids"] == ["PYSEC-2026-1"]


def test_osv_pagination_cannot_be_reported_complete() -> None:
    value = snapshot("sample", "1.0", "osv")
    replace_response(value, {"next_page_token": "more"})
    with pytest.raises(ValueError, match="Incomplete"):
        MODULE["parse_snapshot"](value)


def test_duplicate_json_key_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        MODULE["strict_json"](b'{"status":"unknown", "status":"complete"}')


@pytest.mark.parametrize("dynamic", [False, True])
def test_local_dependency_requires_exact_wheel(sample: dict[str, Any], dynamic: bool) -> None:
    path = sample["package"] / "uv.lock"
    path.write_text(
        path.read_text().replace(
            'name = "dep"\nversion = "2.0"\nsource = {registry = "https://pypi.org/simple"}',
            'name = "dep"\nversion = "2.0"\nsource = {directory = "../dep"}',
        )
    )
    if dynamic:
        path.write_text(path.read_text().replace('name = "dep"\nversion = "2.0"', 'name = "dep"'))
    with pytest.raises(ValueError, match="requires matching --local-artifact"):
        generate(sample)
    local_wheel = sample["package"] / "dep-2.0-py3-none-any.whl"
    local_metadata = "Metadata-Version: 2.4\nName: dep\nVersion: 2.0\nRequires-Python: >=3.12\n\n"
    wheel(local_wheel, local_metadata)
    result = MODULE["generate"](
        sample["package"], sample["artifacts"], [local_wheel], Path("unused"), sample["output"]
    )
    component = next(c for c in result["components"] if c["name"] == "dep")
    assert component["local_artifact"]["sha256"] == MODULE["file_ref"](local_wheel)["sha256"]
    wheel(local_wheel, local_metadata, "changed.txt")
    with pytest.raises(ValueError, match="differs"):
        MODULE["verify_inventory"](
            sample["output"] / "inventory.json",
            sample["package"],
            sample["artifacts"],
            [local_wheel],
            Path("unused"),
        )


def test_metadata_bombs_and_duplicate_archive_members(sample: dict[str, Any]) -> None:
    path = sample["artifacts"][0]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample-1.0.dist-info/METADATA", "A" * (MODULE["MAX_JSON"] + 1))
    with pytest.raises(ValueError, match="size limit"):
        generate(sample)
    wheel(path, sample["metadata"])
    with pytest.warns(UserWarning), zipfile.ZipFile(path, "a") as archive:
        archive.writestr("sample-1.0.dist-info/METADATA", sample["metadata"])
    with pytest.raises(ValueError, match="duplicate archive"):
        generate(sample)


def test_archive_symlink_member_in_wheel(sample: dict[str, Any]) -> None:
    wheel(sample["artifacts"][0], sample["metadata"])
    with zipfile.ZipFile(sample["artifacts"][0], "a") as archive:
        link = zipfile.ZipInfo("sample/link")
        link.external_attr = 0o120777 << 16
        archive.writestr(link, "/etc/passwd")
    with pytest.raises(ValueError, match="links"):
        generate(sample)


def test_malformed_upstream_response_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        MODULE["fetch_snapshot"].__globals__,
        "request_json",
        lambda *_: ({"vulns": None}, '{"vulns": null}'),
    )
    result = MODULE["fetch_snapshot"]("sample", "1.0", "osv")
    assert result["status"] == "unknown"
    assert MODULE["summarize_snapshots"]([result])["status"] == "unknown"


def test_invalid_provider_aliases_rejected() -> None:
    value = snapshot("sample", "1.0", "osv")
    replace_response(value, {"vulns": [{"id": "test", "aliases": None}]})
    with pytest.raises(ValueError, match="aliases"):
        MODULE["parse_snapshot"](value)


def test_require_clean_without_advisories_fails(
    sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    generate(sample)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dependency_inventory.py",
            "verify",
            "--package",
            str(sample["package"]),
            "--artifact",
            str(sample["artifacts"][0]),
            "--artifact",
            str(sample["artifacts"][1]),
            "--inventory",
            str(sample["output"] / "inventory.json"),
            "--require-clean",
        ],
    )
    assert MODULE["main"]() == 1


@pytest.mark.parametrize("value", ["../../outside", "a/b", "MixedCase", "dep..name"])
def test_untrusted_component_names_never_reach_network_or_filesystem(
    sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    generate(sample)
    path = sample["output"] / "inventory.json"
    inventory = json.loads(path.read_text())
    inventory["components"][0]["name"] = value
    MODULE["write_json"](path, inventory)
    called = []
    monkeypatch.setitem(MODULE["scan"].__globals__, "fetch_snapshot", lambda *a: called.append(a))
    output = sample["output"] / "scan"
    with pytest.raises(ValueError, match="identity"):
        MODULE["scan"](path, output)
    assert not output.exists()
    assert not called


def test_raw_response_bytes_are_checked_before_claiming_empty() -> None:
    value = snapshot("dep", "2.0", "osv")
    value["pages"][0]["response_raw_utf8"] = '{"vulns":[{"id":"GHSA-aaaa-bbbb-cccc"}]}'
    with pytest.raises(ValueError, match="bytes disagree"):
        MODULE["parse_snapshot"](value)


def test_schema_bytes_are_pinned(sample: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = generate(sample)
    validate = MODULE["validate_bom"]
    actual = validate.__globals__["SCHEMAS"]
    monkeypatch.setitem(
        validate.__globals__, "SCHEMAS", {**actual, "bom-1.6.schema.json": "0" * 64}
    )
    with pytest.raises(ValueError, match="schema integrity"):
        MODULE["create_bom"](inventory, inventory["artifacts"][0])


def test_stale_development_lock_rejected(sample: dict[str, Any]) -> None:
    path = sample["package"] / "pyproject.toml"
    path.write_text(path.read_text().replace('"tester==1.0"', '"tester==2.0"'))
    with pytest.raises(ValueError, match="violates artifact declaration"):
        generate(sample)


def test_non_finite_json_rejected() -> None:
    with pytest.raises(ValueError, match="Non-finite"):
        MODULE["strict_json"](b'{"size":NaN}')


def test_conflicting_license_declarations_do_not_gain_clearance() -> None:
    result = MODULE["license_evidence"]({"license_expression": "MIT", "license": "GPL-3.0-only"})
    assert result["status"] == "conflicting_declarations"
    assert result["expression"] is None


@pytest.mark.parametrize(
    "name",
    [
        "equiframe",
        "equiframe-benchmark",
        "equiframe-consumer-lab",
        "private-forecast",
        "internal-helper",
        "consumer-private",
    ],
)
def test_public_preview_rejects_private_names_even_with_public_registry(name: str) -> None:
    with pytest.raises(ValueError, match="public package"):
        MODULE["request_preview"](
            "https://api.osv.dev/v1/query",
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": "1.0"},
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.osv.dev/v1/query",
        "https://api.osv.dev.attacker.invalid/v1/query",
        "https://pypi.org/pypi/numpy/2.0/json?private=value",
        "https://user:password@pypi.org/pypi/numpy/2.0/json",
    ],
)
def test_public_preview_rejects_unapproved_url_surface(url: str) -> None:
    with pytest.raises(ValueError):
        MODULE["request_preview"](url)


def test_public_preview_has_no_private_headers_or_payload() -> None:
    body = {"package": {"name": "numpy", "ecosystem": "PyPI"}, "version": "2.0.0"}
    value = MODULE["request_preview"]("https://api.osv.dev/v1/query", body)
    assert value["headers"] == {"Accept": "application/json", "Content-Type": "application/json"}
    assert value["body"] == body
    body["project"] = "private-name"
    with pytest.raises(ValueError):
        MODULE["request_preview"]("https://api.osv.dev/v1/query", body)


def test_redirect_cannot_send_even_public_payload_elsewhere() -> None:
    with pytest.raises(ValueError, match="redirects"):
        MODULE["NoAdvisoryRedirect"]().redirect_request(
            None, None, 302, "found", {}, "https://elsewhere.invalid/"
        )


def test_ambiguous_public_provenance_cannot_leave(sample: dict[str, Any]) -> None:
    generate(sample)
    path = sample["output"] / "inventory.json"
    inventory = json.loads(path.read_text())
    component = next(c for c in inventory["components"] if c["name"] == "dep")
    allowlist = [{"name": "dep", "version": "2.0"}]
    component["source"]["directory"] = "/private/path"
    with pytest.raises(ValueError, match="provenance"):
        MODULE["selected_public_components"](inventory, allowlist)


def test_unlisted_private_component_mislabeled_public_is_excluded(sample: dict[str, Any]) -> None:
    generate(sample)
    inventory = json.loads((sample["output"] / "inventory.json").read_text())
    inventory["components"].append(
        {
            "name": "secret-forecast",
            "version": "1.0",
            "source": {"registry": "https://pypi.org/simple"},
        }
    )
    selected = MODULE["selected_public_components"](inventory, [{"name": "dep", "version": "2.0"}])
    assert [c["name"] for c in selected] == ["dep"]


def test_real_transport_surface_uses_no_automatic_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def geturl(self):
            return "https://api.osv.dev/v1/query"

        def read(self, limit):
            return b"{}"

    class Opener:
        def __init__(self):
            self.addheaders = [("User-Agent", "synthetic default")]

        def open(self, request, timeout):
            seen.update(
                url=request.full_url,
                headers=dict(request.header_items()),
                body=json.loads(request.data),
                automatic=self.addheaders,
            )
            return Response()

    monkeypatch.setattr(MODULE["urllib"].request, "build_opener", lambda *_: Opener())
    body = {"package": {"name": "numpy", "ecosystem": "PyPI"}, "version": "2.0.0"}
    MODULE["request_json"]("https://api.osv.dev/v1/query", body)
    assert seen == {
        "url": "https://api.osv.dev/v1/query",
        "headers": {"Accept": "application/json", "Content-type": "application/json"},
        "body": body,
        "automatic": [],
    }
