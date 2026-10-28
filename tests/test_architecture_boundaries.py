"""Architectural ownership and byte-level compatibility of extracted primitives."""

import errno
import importlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from equiframe import _document_io, _physical, profiles
from equiframe.migration import _physical as old_physical

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def architecture_tool():
    spec = importlib.util.spec_from_file_location(
        "architecture_check", TOOLS / "check_architecture.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_primitives_keep_exact_legacy_alias_identity():
    assert profiles._write_document is _document_io.write_document
    assert profiles._read_document is _document_io.read_document
    assert old_physical.physical_size is _physical.physical_size
    assert old_physical.verify_table_metadata is _physical.verify_table_metadata
    for name in ("detectors", "evidence", "pipeline", "preprocessing", "reporting"):
        assert importlib.import_module("equiframe." + name)._write_document is (
            _document_io.write_document
        )


@given(st.binary(max_size=256))
@settings(max_examples=30, deadline=None)
def test_shared_writer_preserves_every_byte_and_does_not_overwrite(payload):
    # Serialization and newline policy remain the caller's responsibility.
    with TemporaryDirectory(prefix="equiframe-byte-contract-") as folder:
        path = Path(folder) / "document"
        _document_io.write_document(path, payload)
        assert path.read_bytes() == payload
        with pytest.raises(FileExistsError):
            _document_io.write_document(path, b"replacement")
        assert path.read_bytes() == payload
        assert list(Path(folder).iterdir()) == [path]


@pytest.mark.parametrize("payload", [b'{"text":"caf\\u00e9"}', '{"text":"café"}\n'.encode()])
def test_shared_reader_keeps_historical_encoding_and_newline(tmp_path, payload):
    path = tmp_path / "document.json"
    path.write_bytes(payload)
    assert _document_io.read_document(path) == payload
    assert json.loads(payload) == {"text": "café"}


def test_writer_propagates_bounded_simulated_no_space_without_final_file(tmp_path, monkeypatch):
    def no_space(_descriptor):
        raise OSError(errno.ENOSPC, "synthetic full device")

    monkeypatch.setattr(_document_io.os, "fsync", no_space)
    with pytest.raises(OSError) as failure:
        _document_io.write_document(tmp_path / "result.json", b"{}")
    assert failure.value.errno == errno.ENOSPC
    assert list(tmp_path.iterdir()) == []


def test_runtime_architecture_is_neutral_and_keeps_deliberate_lazy_cycles_visible():
    report = architecture_tool().inspect(TOOLS.parent / "src" / "equiframe")
    assert report["violations"] == []
    assert report["eager_cycles"] == []
    # Report all function/type-reference cycles rather than calling the full graph acyclic.
    assert report["runtime_cycles"]
    assert any(edge["target"] == "equiframe._document_io" for edge in report["edges"])


def test_architecture_gate_rejects_domain_and_specialized_primitive_dependencies(tmp_path):
    (tmp_path / "_document_io.py").write_text(
        "from equiframe.profiles import _write_document\nimport equiframe_benchmark\n"
    )
    result = architecture_tool().inspect(tmp_path)
    assert any("core imports equiframe_benchmark" in text for text in result["violations"])
    assert any("non-neutral dependency equiframe.profiles" in text for text in result["violations"])
    assert any("profile-owned generic I/O" in text for text in result["violations"])


def test_architecture_gate_reports_cycles_and_stable_sorted_edges(tmp_path):
    (tmp_path / "a.py").write_text("import equiframe.b\n")
    (tmp_path / "b.py").write_text("import equiframe.a\n")
    report = architecture_tool().inspect(tmp_path)
    assert report["eager_cycles"] == [["equiframe.a", "equiframe.b"]]
    assert report == architecture_tool().inspect(tmp_path)
    assert report["violations"]


def test_relative_imports_preserve_cycles_and_neutral_boundaries(tmp_path):
    (tmp_path / "a.py").write_text("from .b import value\n")
    (tmp_path / "b.py").write_text("from . import a\n")
    (tmp_path / "_document_io.py").write_text("from .profiles import _write_document\n")
    report = architecture_tool().inspect(tmp_path)
    assert report["eager_cycles"] == [["equiframe.a", "equiframe.b"]]
    assert any("profile-owned generic I/O" in item for item in report["violations"])
    assert any("non-neutral dependency" in item for item in report["violations"])


def test_relative_parent_and_package_initializers_resolve_to_actual_modules(tmp_path):
    package = tmp_path / "sub"
    package.mkdir()
    (package / "__init__.py").write_text("from . import child\n")
    (package / "child.py").write_text("from ..errors import Problem\n")
    (tmp_path / "errors.py").write_text("class Problem(Exception): pass\n")
    report = architecture_tool().inspect(tmp_path)
    assert {(item["source"], item["target"]) for item in report["edges"]} == {
        ("equiframe.sub", "equiframe.sub.child"),
        ("equiframe.sub.child", "equiframe.errors"),
    }
    assert report["violations"] == []
