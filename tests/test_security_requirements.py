"""Security audit export keeps platform alternatives and rejects unsafe inputs."""

import runpy
from pathlib import Path

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "security_requirements.py"))


def lock(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "uv.lock"
    path.write_text(content, encoding="utf-8")
    return path


def test_preserves_alternative_pins_without_duplicate_names(tmp_path: Path) -> None:
    path = lock(
        tmp_path,
        "\n".join(
            f'[[package]]\nname = "{name}"\nversion = "{version}"\n'
            'source = {registry = "https://pypi.org/simple"}\n'
            for name, version in (("numpy", "2.2.6"), ("numpy", "2.4.6"), ("pydantic", "2.12.0"))
        ),
    )
    assert MODULE["audit_batches"]([path, path]) == [
        ["numpy==2.2.6", "pydantic==2.12.0"],
        ["numpy==2.4.6"],
    ]
    output = tmp_path / "audit"
    result = MODULE["export"]([path], output)
    assert result["public_pairs"] == 3
    assert (output / "requirements-1.txt").read_bytes() == b"numpy==2.4.6\n"
    with pytest.raises(FileExistsError):
        MODULE["export"]([path], output)


@pytest.mark.parametrize(
    "source",
    [
        '{registry = "https://unreviewed.invalid/simple"}',
        '{git = "https://unreviewed.invalid/repo"}',
        '{directory = "../unreviewed"}',
    ],
)
def test_rejects_unreviewed_dependency_sources(tmp_path: Path, source: str) -> None:
    path = lock(tmp_path, f'[[package]]\nname = "example"\nversion = "1.0"\nsource = {source}\n')
    with pytest.raises(ValueError, match="reviewed PyPI pins"):
        MODULE["audit_batches"]([path])


def test_requirement_injection_rejected_before_writing(tmp_path: Path) -> None:
    path = lock(
        tmp_path,
        '[[package]]\nname = "example"\nversion = "1.0 --index-url=x"\n'
        'source = {registry = "https://pypi.org/simple"}\n',
    )
    output = tmp_path / "audit"
    with pytest.raises(ValueError, match="invalid locked project identity"):
        MODULE["export"]([path], output)
    assert not output.exists()


def test_dynamic_local_project_does_not_require_a_registry_version(tmp_path: Path) -> None:
    path = lock(
        tmp_path,
        '[[package]]\nname = "equiframe"\nsource = {editable = "."}\n'
        '[[package]]\nname = "numpy"\nversion = "2.4.6"\n'
        'source = {registry = "https://pypi.org/simple"}\n',
    )
    assert MODULE["audit_batches"]([path]) == [["numpy==2.4.6"]]
