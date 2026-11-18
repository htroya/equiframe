"""Public artifact reads fail explicitly and give a usable extra-install route."""

import hashlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import equiframe as ef
from equiframe import tables


@pytest.mark.parametrize("kind", ["arrow", "parquet"])
def test_missing_arrow_extra_preserves_input_and_typed_failure(tmp_path, monkeypatch, kind):
    source = tmp_path / ("input." + kind)
    data = pa.table({"id": ["001", "002"], "amount": [10, 20]})
    if kind == "arrow":
        with pa.ipc.new_file(source, data.schema) as writer:
            writer.write_table(data)
    else:
        pq.write_table(data, source)
    original = source.read_bytes()
    ref = ef.ArtifactRef(
        schema_version="1.0",
        uri=source.as_uri(),
        sha256=hashlib.sha256(original).hexdigest(),
        format=kind,
        media_type="application/octet-stream",
        size_bytes=len(original),
    )
    real_import = tables.import_module

    def unavailable(name):
        if name == "pyarrow":
            raise ImportError("simulated optional dependency unavailable")
        return real_import(name)

    monkeypatch.setattr(tables, "import_module", unavailable)
    with pytest.raises(ef.MissingDependencyError) as failure:
        ef.read_table(ref)
    message = str(failure.value)
    assert "python -m pip install 'equiframe[arrow]'" in message
    assert "pinned EquiFrame requirement" in message
    assert "pending" not in message and "simulated" not in message
    assert isinstance(failure.value.__cause__, ImportError)
    assert source.read_bytes() == original
