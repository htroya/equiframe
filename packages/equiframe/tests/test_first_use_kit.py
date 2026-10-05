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
