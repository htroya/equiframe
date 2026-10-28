"""Portable kit integrity checks use synthetic payloads, never fake acceptance."""

import hashlib
import json
import runpy
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = runpy.run_path(str(ROOT / "tools" / "build_first_use_kit.py"))
VERIFY = runpy.run_path(str(ROOT / "examples" / "first_use" / "verify_kit.py"))


@pytest.fixture
def package(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    first = root / "examples" / "first_use"
    first.mkdir(parents=True)
    shutil.copyfile(ROOT / "uv.lock", root / "uv.lock")
    (root / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n', "utf-8")
    for name in BUILD["DOCUMENTS"]:
        if name == "requirements.lock":
            content = BUILD["locked_requirements"](root / "uv.lock")
        elif name == "verify_kit.py":
            content = (ROOT / "examples" / "first_use" / name).read_text("utf-8")
        else:
            content = "Synthetic packaging fixture; no human acceptance.\n"
        (first / name).write_text(content, "utf-8")
    for name in BUILD["RECIPES"]:
        (root / "examples" / name).write_text("# Synthetic packaging fixture\n", "utf-8")
    runtime = root / "src" / "equiframe"
    runtime.mkdir(parents=True)
    (runtime / "__init__.py").write_text('__version__ = "0.0.0"\n', "utf-8")
    (runtime / "py.typed").write_bytes(b"")
    dist = root / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "equiframe-0.0.0-py3-none-any.whl", "w") as archive:
        for path in runtime.iterdir():
            archive.write(path, "equiframe/" + path.name)
        archive.writestr("equiframe-0.0.0.dist-info/METADATA", "Name: equiframe\nVersion: 0.0.0\n")
    return root


@pytest.fixture
def kit(tmp_path: Path, package: Path) -> Path:
    destination = tmp_path / "kit"
    BUILD["build_kit"](destination, package=package)
    return destination


def symlink(path: Path, target: Path, *, directory: bool = False) -> None:
    try:
        path.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")


def rewrite_manifest(kit: Path, mutate: Any) -> None:
    path = kit / "manifest.json"
    value = json.loads(path.read_text("utf-8"))
    mutate(value)
    path.write_text(json.dumps(value), "utf-8")


def test_fresh_requirements_are_exactly_the_existing_lock_closure() -> None:
    expected = BUILD["locked_requirements"](ROOT / "uv.lock")
    assert (ROOT / "examples" / "first_use" / "requirements.lock").read_text("utf-8") == expected
    assert (ROOT / "examples" / "journeys" / "requirements.lock").read_text("utf-8") == expected
    for root in BUILD["ROOTS"]:
        assert f"\n{root}==" in expected
    assert "polars==" not in expected and "scikit-learn==" not in expected
    assert "--hash=sha256:" in expected


def test_kit_is_closed_portable_and_binds_exact_bytes(kit: Path, package: Path) -> None:
    manifest = VERIFY["verify_kit"](kit)
    assert manifest["schema"] == "equiframe-first-use-kit-1"
    wheel = kit / manifest["wheel"]
    assert wheel.read_bytes() == (package / "dist" / wheel.name).read_bytes()
    assert (
        manifest["files"][manifest["wheel"]]["sha256"]
        == hashlib.sha256(wheel.read_bytes()).hexdigest()
    )
    for name in BUILD["RECIPES"]:
        assert (kit / name).read_bytes() == (package / "examples" / name).read_bytes()
    assert manifest["runtime_payload"]["files"]["equiframe/py.typed"]["size_bytes"] == 0
    assert manifest["source_payload"]["sha256"] == BUILD["canonical_hash"](
        manifest["source_payload"]["files"]
    )
    relocated = kit.with_name("relocated")
    shutil.copytree(kit, relocated)
    assert VERIFY["verify_kit"](relocated) == manifest


def test_builder_never_overwrites_existing_output(kit: Path, package: Path) -> None:
    original = (kit / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        BUILD["build_kit"](kit, package=package)
    assert (kit / "manifest.json").read_bytes() == original


@pytest.mark.parametrize("name", ["README.md", "requirements.lock", "assertion_ci.py", "wheel"])
def test_tampered_payload_rejected(kit: Path, name: str) -> None:
    manifest = VERIFY["verify_kit"](kit)
    path = kit / (manifest["wheel"] if name == "wheel" else name)
    raw = path.read_bytes()
    path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with pytest.raises(VERIFY["KitError"], match="checksum"):
        VERIFY["verify_kit"](kit)


@pytest.mark.parametrize("kind", ["extra", "missing", "directory", "hidden", "extra-wheel"])
def test_inventory_rejects_missing_and_unexpected_entries(kit: Path, kind: str) -> None:
    if kind == "missing":
        (kit / "README.md").unlink()
    elif kind == "directory":
        (kit / "unexpected").mkdir()
    else:
        name = {"extra": "unlisted.py", "hidden": ".hidden", "extra-wheel": "wheels/extra.whl"}[
            kind
        ]
        (kit / name).write_bytes(b"not in the closed inventory")
    with pytest.raises(VERIFY["KitError"]):
        VERIFY["verify_kit"](kit)


@pytest.mark.parametrize("kind", ["file", "directory", "manifest", "root", "dangling"])
def test_inventory_rejects_symlinks(kit: Path, kind: str) -> None:
    if kind == "root":
        target = kit.with_name("root-link")
        symlink(target, kit, directory=True)
        kit = target
    elif kind == "directory":
        target = kit.with_name("real-wheels")
        (kit / "wheels").rename(target)
        symlink(kit / "wheels", target, directory=True)
    else:
        name = "manifest.json" if kind == "manifest" else "README.md"
        path = kit / name
        target = kit.with_name("external-" + name)
        path.rename(target)
        if kind == "dangling":
            target.unlink()
        symlink(path, target)
    with pytest.raises(VERIFY["KitError"]):
        VERIFY["verify_kit"](kit)


@pytest.mark.parametrize(
    "wheel", ["../outside.whl", "/outside.whl", "wheels/../outside.whl", "wheels\\a.whl"]
)
def test_manifest_rejects_unsafe_paths(kit: Path, wheel: str) -> None:
    rewrite_manifest(kit, lambda value: value.update(wheel=wheel))
    with pytest.raises(VERIFY["KitError"]):
        VERIFY["verify_kit"](kit)


@pytest.mark.parametrize("size", [True, -1, "12", 1.5])
def test_manifest_rejects_invalid_sizes(kit: Path, size: object) -> None:
    rewrite_manifest(kit, lambda value: value["files"]["README.md"].update(size_bytes=size))
    with pytest.raises(VERIFY["KitError"], match="digest or size"):
        VERIFY["verify_kit"](kit)


def test_manifest_cannot_add_a_new_trusted_script(kit: Path) -> None:
    (kit / "extra.py").write_text("# unlisted\n", "utf-8")
    rewrite_manifest(
        kit,
        lambda value: value["files"].update({"extra.py": BUILD["file_record"](kit / "extra.py")}),
    )
    with pytest.raises(VERIFY["KitError"], match="every required file"):
        VERIFY["verify_kit"](kit)


def test_manifest_duplicate_keys_rejected(kit: Path) -> None:
    path = kit / "manifest.json"
    content = path.read_text("utf-8")
    path.write_text(content.replace('"schema":', '"schema": "duplicate", "schema":', 1), "utf-8")
    with pytest.raises(VERIFY["KitError"], match="duplicate"):
        VERIFY["verify_kit"](kit)


def test_builder_rejects_stale_requirements(package: Path, tmp_path: Path) -> None:
    (package / "examples" / "first_use" / "requirements.lock").write_text("stale\n", "utf-8")
    output = tmp_path / "bad-kit"
    with pytest.raises(ValueError, match=r"requirements\.lock is stale"):
        BUILD["build_kit"](output, package=package)
    assert not output.exists()


def test_builder_rejects_changed_runtime_with_same_version(package: Path, tmp_path: Path) -> None:
    (package / "src" / "equiframe" / "__init__.py").write_text("# changed runtime\n", "utf-8")
    with pytest.raises(ValueError, match="runtime bytes differ"):
        BUILD["build_kit"](tmp_path / "bad-kit", package=package)


def test_builder_rejects_source_links(package: Path, tmp_path: Path) -> None:
    path = package / "examples" / "assertion_ci.py"
    path.unlink()
    symlink(path, package / "examples" / "test_assertion_recipe.py")
    with pytest.raises(ValueError, match="regular files"):
        BUILD["build_kit"](tmp_path / "bad-kit", package=package)


def test_lock_export_rejects_ambiguous_versions(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text('[[package]]\nname="pandas"\n[[package]]\nname="pandas"\n', "utf-8")
    with pytest.raises(ValueError, match="multiple locked resolutions"):
        BUILD["locked_requirements"](lock)


@pytest.mark.parametrize("mutation", ["none", "changed", "missing", "extra"])
def test_packaged_handbook_is_part_of_exact_wheel_binding(package: Path, mutation: str) -> None:
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text()
        + '\n[tool.hatch.build.targets.wheel.force-include]\n"docs" = "equiframe/docs"\n'
    )
    docs = package / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("Synthetic English handbook")
    wheel = package / "dist" / "equiframe-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "a") as archive:
        if mutation != "missing":
            archive.writestr(
                "equiframe/docs/index.md",
                "Changed" if mutation == "changed" else "Synthetic English handbook",
            )
        if mutation == "extra":
            archive.writestr("equiframe/docs/undeclared.md", "Unexpected")
    if mutation == "none":
        payload = BUILD["verify_wheel_source"](wheel, package, "0.0.0")
        assert "equiframe/docs/index.md" in payload
    else:
        with pytest.raises(ValueError, match=r"runtime (bytes|inventory)"):
            BUILD["verify_wheel_source"](wheel, package, "0.0.0")


@pytest.mark.parametrize(
    "mutation",
    ["none", "missing_schema", "changed_schema", "missing_notice", "changed_notice", "extra"],
)
def test_first_use_binds_r_schemas_and_vendored_notices(package: Path, mutation: str) -> None:
    schemas = (
        "r-review-options-1.0.schema.json",
        "r-review-binding-1.0.schema.json",
        "r-execution-binding-1.0.schema.json",
        "r-review-result-1.0.schema.json",
        "reviewed-decision-1.0.schema.json",
    )
    mappings = {"tools/cyclonedx": "equiframe/_vendor/cyclonedx"}
    mappings.update({"schemas/" + name: "equiframe/schemas/" + name for name in schemas})
    declared = BUILD["tomllib"].loads((ROOT / "pyproject.toml").read_text("utf-8"))
    actual = declared["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert all(actual[source] == destination for source, destination in mappings.items())
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text()
        + "\n[tool.hatch.build.targets.wheel.force-include]\n"
        + "".join(f'"{source}" = "{destination}"\n' for source, destination in mappings.items())
    )
    resources = {"schemas/" + name: b'{"fixture": "synthetic R schema"}' for name in schemas}
    resources.update(
        {
            "tools/cyclonedx/LICENSE": b"Synthetic notice; no license approval asserted.",
            "tools/cyclonedx/PROVENANCE.md": b"Synthetic origin record.",
            "tools/cyclonedx/bom-1.6.schema.json": b'{"fixture": "vendored schema"}',
        }
    )
    wheel = next((package / "dist").glob("*.whl"))
    for source, content in resources.items():
        path = package / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    with zipfile.ZipFile(wheel, "a") as archive:
        for source, content in resources.items():
            schema = source == "schemas/" + schemas[0]
            notice = source == "tools/cyclonedx/LICENSE"
            if (mutation == "missing_schema" and schema) or (
                mutation == "missing_notice" and notice
            ):
                continue
            if (mutation == "changed_schema" and schema) or (
                mutation == "changed_notice" and notice
            ):
                content = b"Substituted resource"
            key = "equiframe/" + source
            if source.startswith("tools/cyclonedx/"):
                key = source.replace("tools/cyclonedx/", "equiframe/_vendor/cyclonedx/", 1)
            archive.writestr(key, content)
        if mutation == "extra":
            archive.writestr("equiframe/_vendor/cyclonedx/unlisted.json", b"undeclared")
    if mutation == "none":
        payload = BUILD["verify_wheel_source"](wheel, package, "0.0.0")
        assert all("equiframe/schemas/" + name in payload for name in schemas)
        assert (
            payload["equiframe/_vendor/cyclonedx/LICENSE"]["sha256"]
            == hashlib.sha256(resources["tools/cyclonedx/LICENSE"]).hexdigest()
        )
    else:
        with pytest.raises(ValueError, match=r"runtime (inventory|bytes)"):
            BUILD["verify_wheel_source"](wheel, package, "0.0.0")


@pytest.mark.parametrize(
    "source,destination",
    [
        ("tools/cyclonedx", "equiframe/_vendor/other"),
        ("schemas/r-review-options-1.0.schema.json", "equiframe/options.json"),
        ("schemas/unreviewed.schema.json", "equiframe/schemas/unreviewed.schema.json"),
    ],
)
def test_first_use_rejects_undeclared_resource_mappings(package, source, destination):
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text()
        + f'\n[tool.hatch.build.targets.wheel.force-include]\n"{source}" = "{destination}"\n'
    )
    with pytest.raises(ValueError, match="unsupported wheel force-include mapping"):
        BUILD["verify_wheel_source"](next((package / "dist").glob("*.whl")), package, "0.0.0")


@pytest.mark.parametrize("kind", ["schema", "vendor"])
def test_first_use_rejects_linked_resource_ancestors(package, kind):
    external = package.parent / "external-resources"
    external.mkdir()
    if kind == "schema":
        source = "schemas/r-review-options-1.0.schema.json"
        destination = "equiframe/" + source
        (external / Path(source).name).write_bytes(b"external schema")
        symlink(package / "schemas", external, directory=True)
    else:
        source, destination = "tools/cyclonedx", "equiframe/_vendor/cyclonedx"
        (external / "cyclonedx").mkdir()
        (external / "cyclonedx/LICENSE").write_bytes(b"external notice")
        symlink(package / "tools", external, directory=True)
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text()
        + f'\n[tool.hatch.build.targets.wheel.force-include]\n"{source}" = "{destination}"\n'
    )
    with pytest.raises(ValueError, match="resource ancestors"):
        BUILD["verify_wheel_source"](next((package / "dist").glob("*.whl")), package, "0.0.0")


@pytest.mark.parametrize("mutation", ["none", "missing", "changed", "cache"])
def test_packaged_journey_sources_are_exact_and_exclude_generated_cache(package, mutation):
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text()
        + (
            "\n[tool.hatch.build.targets.wheel.force-include]\n"
            '"examples/journeys/a_pandas_refactor.py" = '
            '"equiframe/examples/journeys/a_pandas_refactor.py"\n'
        )
    )
    example = package / "examples/journeys/a_pandas_refactor.py"
    example.parent.mkdir()
    example.write_bytes(b'EXPECTED = "synthetic"\n')
    wheel = next((package / "dist").glob("*.whl"))
    with zipfile.ZipFile(wheel, "a") as archive:
        if mutation != "missing":
            archive.writestr(
                "equiframe/examples/journeys/a_pandas_refactor.py",
                b"stale" if mutation == "changed" else example.read_bytes(),
            )
        if mutation == "cache":
            archive.writestr(
                "equiframe/examples/journeys/__pycache__/a_pandas_refactor.pyc", b"stale"
            )
    if mutation == "none":
        files = BUILD["verify_wheel_source"](wheel, package, "0.0.0")
        assert files["equiframe/examples/journeys/a_pandas_refactor.py"]["sha256"] == (
            hashlib.sha256(example.read_bytes()).hexdigest()
        )
    else:
        with pytest.raises(ValueError, match=r"runtime (inventory|bytes)"):
            BUILD["verify_wheel_source"](wheel, package, "0.0.0")


@pytest.mark.parametrize("minor", ["3.10", "3.11", "3.12", "3.13"])
def test_first_use_lock_selects_python_branch_without_changing_hashes(minor):
    text = BUILD["locked_requirements"](ROOT / "uv.lock", python_minor=minor)
    assert f"# Python {minor};" in text
    name = BUILD["requirement_name"](minor)
    assert (ROOT / "examples" / "first_use" / name).read_text("utf-8") == text
    assert len([line for line in text.splitlines() if line.startswith("numpy==")]) == 1
    assert ("exceptiongroup==" in text) == (minor == "3.10")


@pytest.mark.parametrize("namespace", ["journeys", "integrations"])
def test_first_use_rejects_coherent_undeclared_example_mappings(package, namespace):
    original = f"examples/{namespace}/arbitrary.py"
    destination = "equiframe/" + original
    project = package / "pyproject.toml"
    project.write_text(
        project.read_text("utf-8")
        + f'\n[tool.hatch.build.targets.wheel.force-include]\n"{original}"="{destination}"\n',
        encoding="utf-8",
    )
    example = package / original
    example.parent.mkdir(parents=True)
    content = b'EXAMPLE = "coherent but undeclared"\n'
    example.write_bytes(content)
    wheel = next((package / "dist").glob("*.whl"))
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(destination, content)
    with pytest.raises(ValueError, match="unsupported wheel force-include mapping"):
        BUILD["verify_wheel_source"](wheel, package, "0.0.0")


def test_first_use_lock_rejects_unsupported_python_instead_of_reusing_312():
    with pytest.raises(ValueError, match="unsupported first-use Python"):
        BUILD["locked_requirements"](ROOT / "uv.lock", python_minor="3.9")


@pytest.mark.parametrize("mutation", ["none", "missing", "changed", "cache", "remapped"])
@pytest.mark.parametrize(
    "original,destination",
    [
        ("examples/eda_generic.py", "equiframe/examples/integrations/eda_generic.py"),
        ("examples/load_convert_compare.py", "equiframe/examples/load_convert_compare.py"),
    ],
)
def test_first_use_kit_binds_only_the_declared_example_mappings(
    package, tmp_path, mutation, original, destination
):
    configured = BUILD["tomllib"].loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert (
        configured["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"][original]
        == destination
    )
    project = package / "pyproject.toml"
    mapped = (
        destination
        if mutation != "remapped"
        else "equiframe/examples/other/" + Path(destination).name
    )
    project.write_text(
        project.read_text("utf-8")
        + f'\n[tool.hatch.build.targets.wheel.force-include]\n"{original}" = "{mapped}"\n',
        encoding="utf-8",
    )
    content = b'EXAMPLE = "synthetic packaged source"\n'
    (package / original).write_bytes(content)
    wheel = next((package / "dist").glob("*.whl"))
    with zipfile.ZipFile(wheel, "a") as archive:
        if mutation != "missing":
            archive.writestr(mapped, b"stale source" if mutation == "changed" else content)
        if mutation == "cache":
            cached = Path(destination).parent / "__pycache__" / (Path(destination).stem + ".pyc")
            archive.writestr(cached.as_posix(), b"cache")
    if mutation == "none":
        kit = tmp_path / "example-kit"
        manifest = BUILD["build_kit"](kit, package=package)
        assert VERIFY["verify_kit"](kit) == manifest
        assert manifest["runtime_payload"]["files"][destination] == {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    else:
        message = (
            "unsupported wheel force-include mapping"
            if mutation == "remapped"
            else (r"runtime (inventory|bytes)")
        )
        with pytest.raises(ValueError, match=message):
            BUILD["verify_wheel_source"](wheel, package, "0.0.0")
