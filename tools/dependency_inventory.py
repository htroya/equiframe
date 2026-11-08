"""Offline, artifact-bound dependency evidence; explicitly networked advisory snapshots.

This developer tool never installs packages, imports project code, extracts archives,
executes build backends, or selects/approves the project's license. See its README.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
import urllib.error
import urllib.request
import zipfile
from contextlib import suppress
from datetime import datetime, timedelta
from datetime import timezone as _timezone
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn
from urllib.parse import quote

from jsonschema import Draft7Validator  # type: ignore[import-untyped]
from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version
from referencing import Registry, Resource

UTC = _timezone.utc

FORMAT = "equiframe.dependencies/1.0"
AUDIT_FORMAT = "equiframe.advisories/1.0"
MAX_JSON = 16 * 1024 * 1024
SCHEMAS = {
    "bom-1.6.schema.json": "3e92dddbc30cf7f6a02b80f0942b1a4cfd4fb1c26f1dfc4310afa9d613cafb93",
    "spdx.schema.json": "baa9d3bd1ed57b6751b0887edead6b5063ff53ff7429cf85d476c6c94af0166e",
    "jsf-0.82.schema.json": "8bae002c25e723db7ee1f26afde680ae1a2b1a8f6b4b4b0fd65dc3becb090aae",
}
LIMITATIONS = [
    "Resolved profiles describe this marker environment and lock, not all platforms.",
    "Declared dependency ranges permit other versions and are not scanned as if resolved.",
    (
        "Installed metadata/license files are observed evidence, "
        "not legal clearance or provenance attestation."
    ),
    "Lock distribution hashes are resolver inputs, not proof that those bytes were installed.",
    (
        "Hashes identify bytes; unsigned receipts cannot authenticate a publisher "
        "or resist a fully rewritten evidence set."
    ),
    (
        "Python distribution inventory does not enumerate vendored native libraries, "
        "OS packages, or unknown vulnerabilities."
    ),
]


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_ref(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        fail(f"Expected regular non-symlink file: {path}")
    with path.open("rb") as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
        digest = hasher.hexdigest()
    return {"filename": path.name, "sha256": digest, "size_bytes": path.stat().st_size}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def strict_json(data: bytes) -> Any:
    if len(data) > MAX_JSON:
        fail("JSON size limit exceeded")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                fail(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda value: fail(f"Non-finite JSON number: {value}"),
    )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not (
        path.is_absolute()
        or "\\" in name
        or ".." in path.parts
        or ":" in name
        or any(part in {"", "."} for part in name.rstrip("/").split("/"))
    )


def artifact_metadata(path: Path) -> dict[str, Any]:
    """Read only one bounded metadata member; never extract anything."""
    file_ref(path)
    members: dict[str, bytes] = {}
    seen: set[str] = set()
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 30000:
                fail("Archive member limit exceeded")
            for info in infos:
                # ZipInfo.filename is platform-normalized (notably ``\\`` to ``/``
                # on Windows). Validate the raw archive name before that normalization.
                name = info.orig_filename
                if not safe_member(name) or name in seen:
                    fail("Unsafe or duplicate archive member")
                seen.add(name)
                if stat.S_ISLNK(info.external_attr >> 16):
                    fail("Archive links are forbidden")
                if name.endswith(".dist-info/METADATA") and len(PurePosixPath(name).parts) == 2:
                    if info.file_size > MAX_JSON:
                        fail("Metadata size limit exceeded")
                    members[name] = archive.read(info)
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for index, member in enumerate(archive):
                if index >= 30000:
                    fail("Archive member limit exceeded")
                if not safe_member(member.name) or member.name in seen:
                    fail("Unsafe or duplicate archive member")
                seen.add(member.name)
                if not (member.isdir() or member.isfile()):
                    fail("Archive links and special files are forbidden")
                if member.name.endswith("/PKG-INFO") and len(PurePosixPath(member.name).parts) == 2:
                    if member.size > MAX_JSON:
                        fail("Metadata size limit exceeded")
                    stream = archive.extractfile(member)
                    if stream is None:
                        fail("Missing metadata bytes")
                    else:
                        members[member.name] = stream.read(MAX_JSON + 1)
    else:
        fail("Expected wheel or .tar.gz sdist")
    if len(members) != 1:
        fail("Expected exactly one top-level distribution metadata file")
    member_name, data = next(iter(members.items()))
    metadata = BytesParser().parsebytes(data)
    for field in ["Name", "Version", "Requires-Python"]:
        if len(metadata.get_all(field, [])) != 1:
            fail(f"Missing or repeated {field} metadata")
    return {
        "name": canonicalize_name(str(metadata["Name"])),
        "version": str(metadata["Version"]),
        "requires_python": str(SpecifierSet(str(metadata["Requires-Python"]))),
        "requires_dist": sorted(
            str(Requirement(item)) for item in metadata.get_all("Requires-Dist", [])
        ),
        "provides_extra": sorted(metadata.get_all("Provides-Extra", [])),
        "license_expression": metadata.get("License-Expression"),
        "license": metadata.get("License"),
        "metadata_member": member_name,
        "metadata_sha256": sha(data),
    }


# The selected interpreter supplies metadata without importing dependencies or project code.
METADATA_PROBE = r"""
import hashlib, importlib.metadata as m, json, os, platform, sys
from pathlib import Path, PurePosixPath
out=[]
for d in m.distributions():
    files=[]
    declared=set(d.metadata.get_all('License-File',[]))
    for f in d.files or []:
        p=str(f)
        if (PurePosixPath(p).is_absolute() or '..' in PurePosixPath(p).parts
            or '\\' in p or ':' in p): continue
        if '.dist-info/' not in p: continue
        name=p.rsplit('/',1)[-1].lower()
        relative=p.split('.dist-info/',1)[1]
        if not (name.startswith(('license','licence','copying','notice','copyright'))
                or '/licenses/' in p or relative in declared
                or relative.removeprefix('licenses/') in declared): continue
        q=Path(d.locate_file(f))
        if q.is_symlink() or not q.is_file() or q.stat().st_size>16777216: continue
        b=q.read_bytes()
        files.append({'path':p,'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)})
    raw=d.read_text('METADATA')
    out.append({'name':d.metadata['Name'],'version':d.version,
        'metadata_sha256':hashlib.sha256((raw or '').encode()).hexdigest(),
        'license_expression':d.metadata.get('License-Expression'),
        'license':d.metadata.get('License'),
        'license_classifiers':[s for s in d.metadata.get_all('Classifier',[])
                               if s.startswith('License ::')],
        'license_files':sorted(files,key=lambda x:x['path'])})
v=platform.python_version()
env={'implementation_name':sys.implementation.name,'implementation_version':v,
'os_name':os.name,'platform_machine':platform.machine(),'platform_release':platform.release(),
'platform_system':platform.system(),'platform_version':platform.version(),
'python_full_version':v,'platform_python_implementation':platform.python_implementation(),
'python_version':'.'.join(v.split('.')[:2]),'sys_platform':sys.platform}
print(json.dumps({'environment':env,'distributions':out}))
"""


def installed_metadata(python: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    result = subprocess.run(
        [str(python), "-I", "-c", METADATA_PROBE],
        check=True,
        capture_output=True,
        env=environment,
        timeout=90,
    )
    document: dict[str, Any] = strict_json(result.stdout)
    return document


def license_evidence(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {"status": "unknown_not_installed", "expression": None, "evidence": None}
    declarations = []
    for value in [metadata.get("license_expression"), metadata.get("license")]:
        if isinstance(value, str) and value.strip() and len(value) < 1000:
            with suppress(InvalidLicenseExpression):
                declarations.append(str(canonicalize_license_expression(value)))
    expression = declarations[0] if declarations and len(set(declarations)) == 1 else None
    status = "declared_expression" if expression else "review_required"
    if len(set(declarations)) > 1:
        status = "conflicting_declarations"
    return {"status": status, "expression": expression, "evidence": metadata}


def lock_profiles(
    lock: dict[str, Any], project: dict[str, Any], environment: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Resolve the lock's recorded graph, not dependency ranges or a new solve."""
    packages: dict[str, dict[str, Any]] = {}
    name: str
    for package in lock["package"]:
        name = canonicalize_name(package["name"])
        markers = package.get("resolution-markers", [])
        if markers and not any(Marker(m).evaluate(environment) for m in markers):
            continue
        if name in packages:
            fail(f"Ambiguous locked version for environment: {name}")
        packages[name] = package
    root = canonicalize_name(project["name"])
    if root not in packages or packages[root]["version"] != project["version"]:
        fail("Lock root does not match project")
    extras = sorted(project.get("optional-dependencies", {}))
    specifications: list[tuple[str, list[str], str]] = [("base", [], "runtime")]
    specifications += [(f"extra:{extra}", [extra], "runtime") for extra in extras]
    specifications += [("all-extras", extras, "runtime"), ("development", extras, "development")]
    specifications += [("build", [], "build")]
    profiles = []
    for label, selected_extras, purpose in specifications:
        selected: dict[str, set[str]] = {}
        edges: dict[str, set[str]] = {}
        pending: list[tuple[str, list[str]]] = []
        if purpose == "build":
            for requirement in project["build_requires"]:
                req = Requirement(requirement)
                if req.marker is None or req.marker.evaluate(environment):
                    name = canonicalize_name(req.name)
                    if name not in packages or packages[name]["version"] not in req.specifier:
                        fail(f"Build requirement missing from lock: {requirement}")
                    pending.append((name, sorted(req.extras)))
        else:
            pending.append((root, selected_extras))
        while pending:
            name, requested_extras = pending.pop()
            prior = selected.get(name)
            added = set(requested_extras) - (prior or set())
            if prior is not None and not added:
                continue
            selected[name] = (prior or set()) | set(requested_extras)
            if name not in packages:
                fail(f"Dependency missing from lock: {name}")
            package = packages[name]
            dependencies = list(package.get("dependencies", []))
            for extra in selected[name]:
                if extra not in package.get("optional-dependencies", {}):
                    fail(f"Unknown locked extra: {name}[{extra}]")
                dependencies += package["optional-dependencies"][extra]
            if purpose == "development" and name == root:
                dependencies += package.get("dev-dependencies", {}).get("dev", [])
            for dependency in dependencies:
                if dependency.get("marker") and not Marker(dependency["marker"]).evaluate(
                    environment
                ):
                    continue
                dep = canonicalize_name(dependency["name"])
                if dep not in packages:
                    fail(f"Dependency missing from lock: {dep}")
                if dependency.get("version", packages[dep]["version"]) != packages[dep]["version"]:
                    fail(f"Dependency edge version mismatch: {dep}")
                edges.setdefault(name, set()).add(dep)
                pending.append((dep, dependency.get("extra", [])))
        profiles.append(
            {
                "name": label,
                "purpose": purpose,
                "selected_extras": selected_extras,
                "components": sorted(selected),
                "activated_extras": {n: sorted(e) for n, e in sorted(selected.items())},
                "dependencies": [
                    {"name": name, "depends_on": sorted(edges.get(name, set()))}
                    for name in sorted(selected)
                ],
            }
        )
    return profiles, packages


def validate_bom(bom: dict[str, Any]) -> None:
    directory = Path(__file__).with_name("cyclonedx")
    resources = []
    schemas = {}
    for filename, digest in SCHEMAS.items():
        raw = (directory / filename).read_bytes()
        if sha(raw) != digest:
            fail("CycloneDX schema integrity check failed")
        schema = strict_json(raw)
        schemas[filename] = schema
        resources.append(
            (f"http://cyclonedx.org/schema/{filename}", Resource.from_contents(schema))
        )
    registry: Registry[Any] = Registry().with_resources(resources)
    Draft7Validator(schemas["bom-1.6.schema.json"], registry=registry).validate(bom)


def create_bom(inventory: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    project = inventory["project"]
    root = project["name"]
    ref = f"artifact:sha256:{artifact['sha256']}"
    components = []
    for component in inventory["components"]:
        if component["name"] == root:
            continue
        name, version = component["name"], component["version"]
        scopes = [p["name"] for p in inventory["profiles"] if name in p["components"]]
        obj: dict[str, Any] = {
            "type": "library",
            "name": name,
            "version": version,
            "bom-ref": f"pkg:pypi/{name}@{version}",
            "purl": f"pkg:pypi/{name}@{version}",
            "scope": "required" if name in inventory["profiles"][0]["components"] else "optional",
            "properties": [
                {"name": "equiframe:profiles", "value": json.dumps(scopes)},
                {
                    "name": "equiframe:license-evidence-status",
                    "value": component["license"]["status"],
                },
                {
                    "name": "equiframe:resolution-source",
                    "value": "uv.lock; not embedded in artifact",
                },
            ],
        }
        if component["license"]["expression"]:
            obj["licenses"] = [{"expression": component["license"]["expression"]}]
        if component.get("local_artifact"):
            obj["hashes"] = [{"alg": "SHA-256", "content": component["local_artifact"]["sha256"]}]
            obj["properties"].append(
                {
                    "name": "equiframe:artifact-size-bytes",
                    "value": str(component["local_artifact"]["size_bytes"]),
                }
            )
        components.append(obj)
    refs = {c["name"]: c["bom-ref"] for c in components}
    refs[root] = ref
    edges: dict[str, set[str]] = {name: set() for name in refs}
    for profile in inventory["profiles"]:
        for edge in profile["dependencies"]:
            edges[edge["name"]].update(edge["depends_on"])
    bom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "library",
                "name": root,
                "version": project["version"],
                "bom-ref": ref,
                "hashes": [{"alg": "SHA-256", "content": artifact["sha256"]}],
            },
            "properties": [
                {"name": "equiframe:artifact-filename", "value": artifact["filename"]},
                {"name": "equiframe:artifact-size-bytes", "value": str(artifact["size_bytes"])},
                {"name": "equiframe:lock-sha256", "value": inventory["inputs"]["lock"]["sha256"]},
                {
                    "name": "equiframe:scope",
                    "value": (
                        "Resolved lock graph for environment; runtime/extras/build/dev union. "
                        "Dependencies are not embedded."
                    ),
                },
                {
                    "name": "equiframe:marker-environment",
                    "value": json.dumps(inventory["environment"], sort_keys=True),
                },
                {
                    "name": "equiframe:declared-ranges",
                    "value": json.dumps(project["declared"], sort_keys=True),
                },
            ],
        },
        "components": components,
        "dependencies": [
            {"ref": refs[name], "dependsOn": sorted(refs[d] for d in deps)}
            for name, deps in sorted(edges.items())
        ],
    }
    validate_bom(bom)
    return bom


def validate_profile_requirements(
    requirements: list[str],
    name: str,
    profiles: list[dict[str, Any]],
    packages: dict[str, dict[str, Any]],
    environment: dict[str, str],
    purpose: str = "runtime",
) -> None:
    """Reject stale lock closures and direct pins inconsistent with artifact metadata."""
    for profile in profiles:
        if name not in profile["components"] or profile["purpose"] != purpose:
            continue
        extras = ["", *profile["activated_extras"][name]]
        expected = set()
        for value in requirements:
            requirement = Requirement(value)
            active = requirement.marker is None or any(
                requirement.marker.evaluate({**environment, "extra": extra}) for extra in extras
            )
            if not active:
                continue
            dependency = canonicalize_name(requirement.name)
            if requirement.url:
                fail("Direct URL requirements need explicit provenance review")
            if (
                dependency not in packages
                or packages[dependency]["version"] not in requirement.specifier
            ):
                fail(f"Locked version violates artifact declaration: {value}")
            if not requirement.extras.issubset(profile["activated_extras"].get(dependency, [])):
                fail(f"Lock omits requested dependency extras: {value}")
            expected.add(dependency)
        actual = next(
            edge["depends_on"] for edge in profile["dependencies"] if edge["name"] == name
        )
        if set(actual) != expected:
            fail(
                f"Locked dependency graph violates artifact declarations: {name}/{profile['name']}"
            )


def generate_inventory(
    package: Path, artifacts: list[Path], local_artifacts: list[Path], snapshot: dict[str, Any]
) -> dict[str, Any]:
    project_data = tomllib.loads((package / "pyproject.toml").read_text())
    project = dict(project_data["project"])
    project["name"] = canonicalize_name(project["name"])
    project["build_requires"] = project_data["build-system"]["requires"]
    lock = tomllib.loads((package / "uv.lock").read_text())
    # uv deliberately omits versions for dynamic local projects. Bind only those
    # entries to the supplied exact-artifact metadata; never execute a backend
    # or substitute an installed distribution's potentially stale version.
    if "version" not in project:
        identified = [artifact_metadata(path) for path in artifacts]
        if (
            "version" not in project.get("dynamic", [])
            or len(identified) != 2
            or any(item["name"] != project["name"] for item in identified)
            or len({item["version"] for item in identified}) != 1
        ):
            fail("Dynamic project requires two concordant identified artifact versions")
        project["version"] = identified[0]["version"]
    local_versions = {project["name"]: project["version"]}
    for path in local_artifacts:
        if path.suffix != ".whl":
            fail("Local dependency artifact must be a wheel")
        metadata = artifact_metadata(path)
        if metadata["name"] in local_versions:
            fail("Duplicate local dependency artifact")
        local_versions[metadata["name"]] = metadata["version"]
    for entry in lock["package"]:
        if "version" in entry:
            continue
        name = canonicalize_name(entry["name"])
        source = entry["source"]
        if (
            set(source) not in ({"directory"}, {"editable"})
            or not all(isinstance(value, str) and value for value in source.values())
            or name not in local_versions
            or (name == project["name"] and "version" not in project.get("dynamic", []))
        ):
            fail(f"Unversioned local dependency requires matching --local-artifact: {name}")
        entry["version"] = local_versions[name]
    environment = snapshot["environment"]
    if environment["python_full_version"] not in SpecifierSet(project["requires-python"]):
        fail("Marker environment is outside Requires-Python")
    profiles, packages = lock_profiles(lock, project, environment)
    distributions: dict[str, Any] = {}
    for dist in snapshot["distributions"]:
        name = canonicalize_name(dist["name"])
        if name in distributions:
            fail(f"Ambiguous installed metadata: {name}")
        distributions[name] = dist
    local = {}
    for path in local_artifacts:
        if path.suffix != ".whl":
            fail("Local dependency artifact must be a wheel")
        metadata = artifact_metadata(path)
        if metadata["name"] in local:
            fail("Duplicate local dependency artifact")
        local[metadata["name"]] = {**file_ref(path), "metadata": metadata}
    records = []
    for name in sorted({name for profile in profiles for name in profile["components"]}):
        locked = packages[name]
        observed = distributions.get(name)
        if observed and observed["version"] != locked["version"]:
            fail(f"Installed version disagrees with lock: {name}")
        source = locked["source"]
        record = {
            "name": name,
            "version": locked["version"],
            "source": source,
            "license": license_evidence(observed),
            "installed_version_verified": observed is not None,
            "locked_distributions": [locked["sdist"]] if "sdist" in locked else [],
        }
        record["locked_distributions"] += locked.get("wheels", [])
        if name != project["name"] and "registry" not in source:
            if name not in local or local[name]["metadata"]["version"] != locked["version"]:
                fail(f"Local dependency requires matching --local-artifact: {name}")
            record["local_artifact"] = local[name]
        records.append(record)
    if set(local) != {c["name"] for c in records if "local_artifact" in c}:
        fail("Unreferenced local dependency artifact")
    declared = {
        "runtime": project.get("dependencies", []),
        "extras": project.get("optional-dependencies", {}),
        "development": project_data.get("dependency-groups", {}),
        "build": project["build_requires"],
    }
    expected_requirements = list(project.get("dependencies", []))
    for extra, requirements in project.get("optional-dependencies", {}).items():
        for value in requirements:
            req = Requirement(value)
            marker = (
                f"({req.marker}) and extra == '{extra}'" if req.marker else f"extra == '{extra}'"
            )
            req.marker = Marker(marker)
            expected_requirements.append(str(req))
    expected_requirements = sorted(str(Requirement(r)) for r in expected_requirements)
    validate_profile_requirements(
        expected_requirements, project["name"], profiles, packages, environment
    )
    dev_requirements = project_data.get("dependency-groups", {}).get("dev", [])
    if not all(isinstance(requirement, str) for requirement in dev_requirements):
        fail("Nested development dependency groups need explicit resolution support")
    validate_profile_requirements(
        [*expected_requirements, *dev_requirements],
        project["name"],
        profiles,
        packages,
        environment,
        purpose="development",
    )
    for name, local_artifact in local.items():
        validate_profile_requirements(
            local_artifact["metadata"]["requires_dist"], name, profiles, packages, environment
        )
    bound_artifacts = []
    for path in sorted(artifacts):
        metadata = artifact_metadata(path)
        if (
            metadata["name"] != project["name"]
            or metadata["version"] != project["version"]
            or metadata["requires_python"] != str(SpecifierSet(project["requires-python"]))
            or metadata["provides_extra"] != sorted(project.get("optional-dependencies", {}))
            or metadata["requires_dist"] != expected_requirements
        ):
            fail(f"Artifact declaration does not match project: {path.name}")
        bound_artifacts.append({**file_ref(path), "metadata": metadata})
    if (
        len(bound_artifacts) != 2
        or sum(a["filename"].endswith(".whl") for a in bound_artifacts) != 1
    ):
        fail("Exactly one wheel and one sdist are required")
    return {
        "schema_version": FORMAT,
        "project": {"name": project["name"], "version": project["version"], "declared": declared},
        "inputs": {
            "project": file_ref(package / "pyproject.toml"),
            "lock": file_ref(package / "uv.lock"),
        },
        "environment": environment,
        "artifacts": bound_artifacts,
        "profiles": profiles,
        "components": records,
        "limitations": LIMITATIONS,
        "license_clearance": (
            "not_granted; owner license decision and redistribution review required"
        ),
    }


def generate(
    package: Path, artifacts: list[Path], local_artifacts: list[Path], python: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        fail("Output must be new; preserve earlier evidence")
    inventory = generate_inventory(package, artifacts, local_artifacts, installed_metadata(python))
    output.mkdir(parents=True)
    for artifact in inventory["artifacts"]:
        write_json(output / (artifact["filename"] + ".cdx.json"), create_bom(inventory, artifact))
    inventory["sboms"] = [file_ref(p) for p in sorted(output.glob("*.cdx.json"))]
    write_json(output / "inventory.json", inventory)
    return inventory


def verify_inventory(
    path: Path, package: Path, artifacts: list[Path], local_artifacts: list[Path], python: Path
) -> dict[str, Any]:
    saved = strict_json(path.read_bytes())
    fresh = generate_inventory(package, artifacts, local_artifacts, installed_metadata(python))
    sboms = []
    for artifact in fresh["artifacts"]:
        bom_path = path.parent / (artifact["filename"] + ".cdx.json")
        bom = strict_json(bom_path.read_bytes())
        if bom != create_bom(fresh, artifact):
            fail("SBOM differs from rederived artifact inventory")
        sboms.append(file_ref(bom_path))
    fresh["sboms"] = sorted(sboms, key=lambda item: item["filename"])
    if saved != fresh:
        fail("Inventory differs from artifact, lock, project, or installed evidence")
    return fresh


ANONYMOUS_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def public_identity(name: str, version: str) -> None:
    if (
        re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None
        or name.startswith(("equiframe", "private-", "internal-", "consumer-"))
        or re.fullmatch(r"[A-Za-z0-9.!_-]+", version) is None
        or Version(version).local is not None
    ):
        fail("Only reviewed public package identities may leave this process")


def request_preview(url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the entire outbound surface, before constructing an HTTP request."""
    if url == "https://api.osv.dev/v1/query":
        if not isinstance(body, dict) or set(body) not in (
            {"package", "version"},
            {"package", "version", "page_token"},
        ):
            fail("OSV request must contain only public package/version and provider pagination")
        package = body["package"]
        if (
            not isinstance(package, dict)
            or set(package) != {"name", "ecosystem"}
            or package["ecosystem"] != "PyPI"
        ):
            fail("OSV package fields differ from the public-only contract")
        public_identity(package["name"], body["version"])
        if "page_token" in body and (
            not isinstance(body["page_token"], str)
            or not body["page_token"]
            or len(body["page_token"]) > 4096
            or not body["page_token"].isprintable()
        ):
            fail("Invalid provider pagination token")
    else:
        matched = re.fullmatch(r"https://pypi\.org/pypi/([a-z0-9-]+)/([A-Za-z0-9.!_-]+)/json", url)
        if matched is None or body is not None:
            fail("URL/body outside the public advisory destinations")
        public_identity(*matched.groups())
    return {
        "url": url,
        "method": "POST" if body is not None else "GET",
        "headers": dict(ANONYMOUS_HEADERS),
        "body": body,
    }


class NoAdvisoryRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> NoReturn:
        fail("Advisory redirects are not permitted; coverage remains unknown")


def request_json(url: str, body: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    preview = request_preview(url, body)
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers=preview["headers"],
    )
    opener = urllib.request.build_opener(NoAdvisoryRedirect())
    opener.addheaders = []  # No project-identifying User-Agent, referer, cookie or authorization.
    with opener.open(request, timeout=30) as response:
        if response.geturl() != url:
            fail("Unexpected advisory response destination")
        data = response.read(MAX_JSON + 1)
    result: dict[str, Any] = strict_json(data)
    if not isinstance(result, dict):
        fail("Advisory response must be a JSON object")
    return result, data.decode("utf-8")


def fetch_snapshot(name: str, version: str, provider: str) -> dict[str, Any]:
    public_identity(name, version)
    if provider not in {"pypi", "osv"}:
        fail("Unsupported advisory provider")
    url = (
        f"https://pypi.org/pypi/{quote(name)}/{quote(version)}/json"
        if provider == "pypi"
        else "https://api.osv.dev/v1/query"
    )
    query = (
        None
        if provider == "pypi"
        else {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
    )
    snapshot: dict[str, Any] = {
        "provider": provider,
        "name": name,
        "version": version,
        "url": url,
        "retrieved_at": utc_now(),
        "pages": [],
    }
    try:
        for _ in range(100):
            body, raw = request_json(url, query)
            snapshot["pages"].append(
                {
                    "request": query,
                    "response": body,
                    "response_raw_utf8": raw,
                    "response_sha256": sha(raw.encode("utf-8")),
                }
            )
            token = body.get("next_page_token") if provider == "osv" else None
            if not token:
                break
            query = {**(query or {}), "page_token": token}
        else:
            fail("OSV pagination limit reached")
        snapshot["status"] = "complete"
        parse_snapshot(snapshot)
    except (OSError, ValueError, KeyError, TypeError) as error:
        snapshot["status"] = "unknown"
        snapshot["error"] = f"{type(error).__name__}: {error}"
    return snapshot


def parse_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]] | None:
    if snapshot["status"] == "unknown":
        if not snapshot.get("error"):
            fail("Unknown advisory query requires failure evidence")
        return None
    if snapshot["status"] != "complete" or not snapshot["pages"]:
        fail("Invalid advisory snapshot status/pages")
    name, version, provider = snapshot["name"], snapshot["version"], snapshot["provider"]
    expected_url = (
        f"https://pypi.org/pypi/{quote(name)}/{quote(version)}/json"
        if provider == "pypi"
        else "https://api.osv.dev/v1/query"
    )
    if provider not in {"pypi", "osv"} or snapshot["url"] != expected_url:
        fail("Advisory provider or URL mismatch")
    records = []
    token = None
    if provider == "pypi" and len(snapshot["pages"]) != 1:
        fail("Invalid PyPI pages")
    for page in snapshot["pages"]:
        body = page["response"]
        raw = page["response_raw_utf8"].encode("utf-8")
        if sha(raw) != page["response_sha256"] or strict_json(raw) != body:
            fail("Advisory response bytes disagree with parsed snapshot")
        if not isinstance(body, dict):
            fail("Invalid advisory response object")
        if provider == "pypi":
            info = body["info"]
            if (
                canonicalize_name(info["name"]) != name
                or info["version"] != version
                or page["request"] is not None
            ):
                fail("PyPI response identity mismatch")
            vulnerabilities = body["vulnerabilities"]
        else:
            expected_query: dict[str, Any] = {
                "package": {"name": name, "ecosystem": "PyPI"},
                "version": version,
            }
            if token:
                expected_query["page_token"] = token
            if page["request"] != expected_query:
                fail("OSV request binding mismatch")
            if "error" in body:
                fail("OSV returned error response")
            vulnerabilities = body.get("vulns", [])
            token = body.get("next_page_token")
        if not isinstance(vulnerabilities, list):
            fail("Malformed advisory list")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get("id"), str):
                fail("Malformed advisory record")
            aliases = vulnerability.get("aliases", [])
            if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
                fail("Malformed advisory aliases")
            if vulnerability.get("withdrawn"):
                continue
            records.append(vulnerability)
    if token:
        fail("Incomplete OSV pagination")
    return records


def summarize_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    queries = []
    for snapshot in snapshots:
        records = parse_snapshot(snapshot)
        queries.append(
            {
                "name": snapshot["name"],
                "version": snapshot["version"],
                "provider": snapshot["provider"],
                "status": snapshot["status"],
                "advisory_ids": sorted({v["id"] for v in records}) if records is not None else None,
                "ghsa_ids": sorted(
                    {
                        a
                        for v in records
                        for a in [v["id"], *v.get("aliases", [])]
                        if a.startswith("GHSA-")
                    }
                )
                if records is not None
                else None,
            }
        )
    queries.sort(key=lambda q: (q["name"], q["version"], q["provider"]))
    unknown = sum(q["status"] != "complete" for q in queries)
    found = sum(bool(q["advisory_ids"]) for q in queries)
    return {
        "status": "findings" if found else "unknown" if unknown else "no_known_advisories",
        "queries": queries,
        "unknown_queries": unknown,
        "queries_with_findings": found,
    }


def audit_components(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate externally loaded identifiers before URLs or snapshot paths exist."""
    if inventory.get("schema_version") != FORMAT:
        fail("Unsupported inventory schema")
    components = inventory["components"]
    if not isinstance(components, list) or not components:
        fail("Missing inventory components")
    seen = set()
    for component in components:
        name, version = component["name"], component["version"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or name in seen
            or not isinstance(version, str)
        ):
            fail("Invalid or duplicate inventory component identity")
        Version(version)
        if not re.fullmatch(r"[A-Za-z0-9.!+_-]+", version):
            fail("Unsafe component version")
        if not isinstance(component["source"], dict):
            fail("Invalid component source")
        seen.add(name)
    return list(components)


def selected_public_components(
    inventory: dict[str, Any], allowlist: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """A registry label alone never authorizes transmitting an internal package name."""
    components = audit_components(inventory)
    allowed: set[tuple[str, str]] = set()
    for item in allowlist:
        if not isinstance(item, dict) or set(item) != {"name", "version"}:
            fail("Allowlist admits only exact public name/version pairs")
        public_identity(item["name"], item["version"])
        pair = (item["name"], item["version"])
        if pair in allowed:
            fail("Duplicate public allowlist identity")
        allowed.add(pair)
    root = inventory["project"]["name"]
    selected = [
        c
        for c in components
        if (c["name"], c["version"]) in allowed
        and c["name"] != root
        and c["source"] == {"registry": "https://pypi.org/simple"}
        and not c.get("local_artifact")
    ]
    if {(c["name"], c["version"]) for c in selected} != allowed:
        fail("Allowlist identity lacks unambiguous public provenance in this inventory")
    return selected


def scan_coverage(inventory: dict[str, Any], allowlist: list[dict[str, str]]) -> dict[str, Any]:
    selected = {c["name"] for c in selected_public_components(inventory, allowlist)}
    return {
        "providers": ["PyPI release JSON", "OSV query including its GHSA/PYSEC sources"],
        "excluded_components": [
            c["name"] for c in audit_components(inventory) if c["name"] not in selected
        ],
        "unqueried_public_components": [
            c["name"]
            for c in audit_components(inventory)
            if c["source"].get("registry") == "https://pypi.org/simple"
            and c["name"] != inventory["project"]["name"]
            and c["name"] not in selected
        ],
        "limitations": [
            "Point-in-time, exact explicitly allowed public versions, recorded environment only.",
            "Excluded, unqueried or ambiguously sourced dependencies remain unassessed.",
            "No direct GHSA API query; GHSA content is preserved through OSV/PyPI.",
            "Failures and missing provider coverage remain unknown, never clean.",
            *LIMITATIONS,
        ],
    }


def covered_summary(snapshots: list[dict[str, Any]], coverage: dict[str, Any]) -> dict[str, Any]:
    summary = summarize_snapshots(snapshots)
    if coverage["unqueried_public_components"] and summary["status"] == "no_known_advisories":
        summary["status"] = "unknown"
    return summary


def prepare_scan(inventory_path: Path, allowlist_path: Path) -> dict[str, Any]:
    inventory = strict_json(inventory_path.read_bytes())
    allowlist = strict_json(allowlist_path.read_bytes())
    if not isinstance(allowlist, list) or not allowlist:
        fail("A reviewed nonempty public allowlist is required")
    components = selected_public_components(inventory, allowlist)
    requests = []
    for c in components:
        name, version = c["name"], c["version"]
        requests.append(request_preview(f"https://pypi.org/pypi/{name}/{version}/json"))
        requests.append(
            request_preview(
                "https://api.osv.dev/v1/query",
                {"package": {"name": name, "ecosystem": "PyPI"}, "version": version},
            )
        )
    return {
        "schema": "public-dependency-request-plan-1",
        "inventory_sha256": file_ref(inventory_path)["sha256"],
        "public_allowlist": allowlist,
        "requests": requests,
        "coverage": scan_coverage(inventory, allowlist),
        "network_executed": False,
    }


def scan(
    inventory_path: Path,
    output: Path,
    allowlist_path: Path | None = None,
    request_plan: Path | None = None,
) -> dict[str, Any]:
    inventory = strict_json(inventory_path.read_bytes())
    audit_components(inventory)
    if allowlist_path is None or request_plan is None:
        fail("Prepare and inspect a public allowlist/request plan before a network scan")
    plan = prepare_scan(inventory_path, allowlist_path)
    if strict_json(request_plan.read_bytes()) != plan:
        fail("Inspected request plan differs; prepare and review again")
    selected = selected_public_components(inventory, plan["public_allowlist"])
    if output.exists():
        fail("Audit output must be new; preserve earlier snapshot")
    output.mkdir(parents=True)
    queries = [
        (c["name"], c["version"], provider) for c in selected for provider in ["pypi", "osv"]
    ]
    snapshots = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_snapshot, *q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            snapshots.append(future.result())
    references = []
    for snapshot in sorted(snapshots, key=lambda s: (s["name"], s["version"], s["provider"])):
        filename = f"{snapshot['name']}-{snapshot['version']}.{snapshot['provider']}.json"
        write_json(output / filename, snapshot)
        references.append(file_ref(output / filename))
    report = {
        "schema_version": AUDIT_FORMAT,
        "created_at": utc_now(),
        "inventory": file_ref(inventory_path),
        "snapshots": references,
        "summary": covered_summary(snapshots, plan["coverage"]),
        "coverage": plan["coverage"],
        "public_allowlist": plan["public_allowlist"],
        "request_plan_sha256": file_ref(request_plan)["sha256"],
    }
    write_json(output / "advisories.json", report)
    return report


def verify_scan(
    inventory_path: Path, report_path: Path, max_age_hours: float = 24
) -> dict[str, Any]:
    inventory = strict_json(inventory_path.read_bytes())
    report = strict_json(report_path.read_bytes())
    if report.get("schema_version") != AUDIT_FORMAT or report.get("inventory") != file_ref(
        inventory_path
    ):
        fail("Advisory inventory binding mismatch")
    if not 0 < max_age_hours <= 168:
        fail("Freshness bound must be >0 and <=168 hours")
    now = datetime.now(UTC)
    snapshots = []
    seen = set()
    for reference in report["snapshots"]:
        filename = reference["filename"]
        if not safe_member(filename) or len(PurePosixPath(filename).parts) != 1:
            fail("Unsafe snapshot filename")
        path = report_path.parent / filename
        if reference != file_ref(path):
            fail("Advisory snapshot hash/size mismatch")
        snapshot = strict_json(path.read_bytes())
        instant = datetime.fromisoformat(snapshot["retrieved_at"])
        if (
            instant.tzinfo is None
            or instant > now + timedelta(minutes=5)
            or now - instant > timedelta(hours=max_age_hours)
        ):
            fail("Stale, future, or unzoned advisory snapshot")
        key = (snapshot["name"], snapshot["version"], snapshot["provider"])
        if key in seen:
            fail("Duplicate advisory snapshot")
        seen.add(key)
        snapshots.append(snapshot)
    expected = {
        (c["name"], c["version"], provider)
        for c in selected_public_components(inventory, report["public_allowlist"])
        for provider in ["pypi", "osv"]
    }
    if (
        seen != expected
        or report["summary"] != covered_summary(snapshots, report["coverage"])
        or report["coverage"] != scan_coverage(inventory, report["public_allowlist"])
    ):
        fail("Advisory coverage or summary mismatch")
    return dict(report["summary"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["generate", "verify"]:
        command = commands.add_parser(name)
        command.add_argument("--package", type=Path, required=True)
        command.add_argument("--artifact", type=Path, action="append", required=True)
        command.add_argument("--local-artifact", type=Path, action="append", default=[])
        command.add_argument("--environment-python", type=Path, default=Path(sys.executable))
        command.add_argument(
            "--output" if name == "generate" else "--inventory", type=Path, required=True
        )
        if name == "verify":
            command.add_argument("--advisories", type=Path)
            command.add_argument("--max-age-hours", type=float, default=24)
            command.add_argument("--require-clean", action="store_true")
    command = commands.add_parser("scan", help="Explicitly networked PyPI/OSV scan")
    command.add_argument("--inventory", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--public-allowlist", type=Path, required=True)
    command.add_argument("--request-plan", type=Path, required=True)
    command = commands.add_parser(
        "prepare-scan", help="Offline inspectable public-only request plan"
    )
    command.add_argument("--inventory", type=Path, required=True)
    command.add_argument("--public-allowlist", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            result = generate(
                args.package,
                args.artifact,
                args.local_artifact,
                args.environment_python,
                args.output,
            )
            print(
                json.dumps(
                    {
                        "inventory": str(args.output / "inventory.json"),
                        "components": len(result["components"]),
                    }
                )
            )
        elif args.command == "prepare-scan":
            if args.output.exists():
                fail("Preserve earlier request plans; choose a new output")
            result = prepare_scan(args.inventory, args.public_allowlist)
            write_json(args.output, result)
            print(json.dumps({"network_executed": False, "requests": len(result["requests"])}))
        elif args.command == "scan":
            result = scan(args.inventory, args.output, args.public_allowlist, args.request_plan)
            print(json.dumps(result["summary"]))
            return 0 if result["summary"]["status"] == "no_known_advisories" else 2
        else:
            verify_inventory(
                args.inventory,
                args.package,
                args.artifact,
                args.local_artifact,
                args.environment_python,
            )
            summary = (
                verify_scan(args.inventory, args.advisories, args.max_age_hours)
                if args.advisories
                else None
            )
            if args.require_clean and (
                summary is None or summary["status"] != "no_known_advisories"
            ):
                fail("Fresh complete advisory coverage with no known findings required")
            print(json.dumps({"inventory_verified": True, "advisories": summary}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"dependency evidence failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
