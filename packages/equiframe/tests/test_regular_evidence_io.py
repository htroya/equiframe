"""Public evidence readers reject blocking files and linked ancestors."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from equiframe import read_contract
from equiframe._document_io import read_document
from equiframe.bundle import export_bundle, read_bundle
from equiframe.errors import ArtifactIntegrityError
from equiframe.evidence import EvidenceEvent, describe_file, load_json, verify_events

READERS = (
    "json",
    "events",
    "describe",
    "bundle",
    "export",
    "contract",
    "document",
    "comparison",
    "rules",
    "detector",
    "comparison_report",
)


def read(operation, root):
    if operation == "detector":
        from equiframe import read_detector_bundle

        return read_detector_bundle(root / "bundle.json")
    if operation == "comparison_report":
        from equiframe import read_comparison_report

        return read_comparison_report(root / "bundle.json")
    if operation == "comparison":
        from equiframe import read_comparison

        return read_comparison(root / "bundle.json")
    if operation == "rules":
        from equiframe import read_rule_evaluation

        return read_rule_evaluation(root / "bundle.json")
    if operation == "contract":
        return read_contract(root / "bundle.json")
    if operation == "document":
        return read_document(root / "bundle.json")
    if operation == "json":
        return load_json(EvidenceEvent, root / "bundle.json")
    if operation == "events":
        return verify_events(root / "bundle.json", operation_id="test")
    if operation == "describe":
        return describe_file(root / "bundle.json", root)
    if operation == "bundle":
        return read_bundle(root)
    return export_bundle(root, root.parent / "output")


@pytest.mark.parametrize("operation", READERS)
def test_special_directory_instead_of_manifest_is_rejected(tmp_path, operation):
    root = tmp_path / "input"
    root.mkdir()
    (root / "bundle.json").mkdir()
    # Export refuses the invalid operation before creating any output.
    expected = ValueError if operation == "export" else ArtifactIntegrityError
    with pytest.raises(expected):
        read(operation, root)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("operation", READERS)
def test_symlink_ancestor_is_rejected_before_resolution(tmp_path, operation):
    real = tmp_path / "real"
    real.mkdir()
    (real / "bundle.json").write_text("{}", encoding="utf8")
    link = tmp_path / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit directory symlinks")
    with pytest.raises(ArtifactIntegrityError):
        read(operation, link)
    assert (real / "bundle.json").read_bytes() == b"{}"
    assert not (tmp_path / "output").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
@pytest.mark.parametrize("operation", READERS)
def test_windows_junction_ancestor_is_rejected(tmp_path, operation):
    real = tmp_path / "real"
    real.mkdir()
    (real / "bundle.json").write_text("{}", encoding="utf8")
    link = tmp_path / "linked"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    try:
        with pytest.raises(ArtifactIntegrityError):
            read(operation, link)
        assert (real / "bundle.json").read_bytes() == b"{}"
        assert not (tmp_path / "output").exists()
    finally:
        link.rmdir()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO")
@pytest.mark.parametrize("operation", READERS)
def test_fifo_is_rejected_without_waiting_for_a_writer(tmp_path, operation):
    root = tmp_path / "input"
    root.mkdir()
    os.mkfifo(root / "bundle.json", 0o600)
    if operation == "export":
        (root / "migration.json").write_text("{}", encoding="utf8")
    # A regression must fail by timeout, rather than hang the entire test run.
    child = """
import json, sys
from pathlib import Path
import equiframe
from equiframe import read_contract
from equiframe._document_io import read_document
from equiframe.errors import ArtifactIntegrityError
from equiframe.bundle import read_bundle, export_bundle
from equiframe.evidence import EvidenceEvent, load_json, verify_events, describe_file
operation, root = sys.argv[1], Path(sys.argv[2])
try:
    if operation == 'json': load_json(EvidenceEvent, root / 'bundle.json')
    elif operation == 'contract': read_contract(root / 'bundle.json')
    elif operation == 'document': read_document(root / 'bundle.json')
    elif operation == 'comparison': equiframe.read_comparison(root / 'bundle.json')
    elif operation == 'rules': equiframe.read_rule_evaluation(root / 'bundle.json')
    elif operation == 'detector': equiframe.read_detector_bundle(root / 'bundle.json')
    elif operation == 'comparison_report': equiframe.read_comparison_report(root / 'bundle.json')
    elif operation == 'events': verify_events(root / 'bundle.json', operation_id='test')
    elif operation == 'describe': describe_file(root / 'bundle.json', root)
    elif operation == 'bundle': read_bundle(root)
    else: export_bundle(root, root.parent / 'output')
except (ArtifactIntegrityError, ValueError):
    print(json.dumps({'rejected': True, 'reader': operation, 'sdk': equiframe.__file__}))
else:
    raise AssertionError('Special file was accepted')
"""
    completed = subprocess.run(
        [sys.executable, "-c", child, operation, str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["rejected"] is True and receipt["reader"] == operation
    assert Path(receipt["sdk"]).resolve() == Path(sys.modules["equiframe"].__file__).resolve()
    assert not (tmp_path / "output").exists()


def test_regular_file_description_preserves_hash_size_and_relative_path(tmp_path):
    import hashlib

    data = b"unchanged evidence\x00\xff"
    path = tmp_path / "document.bin"
    path.write_bytes(data)
    result = describe_file(path, tmp_path)
    assert result.path == "document.bin"
    assert result.size_bytes == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert path.read_bytes() == data


def test_relative_inventory_and_file_descriptions_preserve_the_same_bytes(tmp_path, monkeypatch):
    from equiframe.evidence import inventory

    monkeypatch.chdir(tmp_path)
    directory = Path("relative-output")
    directory.mkdir()
    path = directory / "document.json"
    path.write_bytes(b"{}\n")
    relative = describe_file(path, directory)
    absolute = describe_file(path.absolute(), directory.absolute())
    assert relative == absolute
    assert relative.path == "document.json" and relative.size_bytes == 3
    assert inventory(directory) == inventory(directory.absolute()) == (relative,)
    assert path.read_bytes() == b"{}\n"


@pytest.mark.parametrize("operation", ["contract", "document", "comparison", "rules"])
def test_documents_over_the_byte_budget_are_refused_before_parsing(tmp_path, operation):
    from equiframe.errors import ResourceLimitError

    with (tmp_path / "bundle.json").open("wb") as stream:
        stream.truncate(64 * 1024 * 1024 + 1)
    with pytest.raises(ResourceLimitError, match="64 MiB"):
        read(operation, tmp_path)


def test_missing_generic_document_keeps_os_error_without_disclosing_its_path(tmp_path):
    marker = "SYNTHETIC_PRIVATE_PATH_3921"
    with pytest.raises(FileNotFoundError) as caught:
        read_document(tmp_path / marker)
    assert caught.value.errno == 2
    assert caught.value.filename is None and caught.value.filename2 is None
    assert marker not in str(caught.value)


def test_contract_parent_navigation_checks_directories_before_normalizing(tmp_path):
    from conftest import EXAMPLES

    expected = read_contract(EXAMPLES / "nulls_types.json")
    path = tmp_path / "contract.json"
    path.write_bytes((EXAMPLES / "nulls_types.json").read_bytes())
    child = tmp_path / "child"
    child.mkdir()
    assert read_contract(child / ".." / "contract.json") == expected
    # Parent navigation is specific to explicitly selected contract inputs;
    # evidence/document readers keep their existing confinement policy.
    with pytest.raises(ArtifactIntegrityError, match="parent traversal"):
        read_document(child / ".." / "contract.json")


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_parent_navigation_cannot_hide_a_windows_junction(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0
    try:
        with pytest.raises(ArtifactIntegrityError, match="reparse"):
            read_contract(link / ".." / "contract.json")
        assert list(real.iterdir()) == []
    finally:
        link.rmdir()


def test_parent_navigation_cannot_hide_a_posix_directory_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit directory symlinks")
    with pytest.raises(ArtifactIntegrityError, match="symlinks"):
        read_contract(link / ".." / "contract.json")
    assert list(real.iterdir()) == []
