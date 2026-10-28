"""Base-install storage, registration and optional-dependency error behavior."""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import equiframe as ef


def test_local_store_hash_size_exclusive_publication_and_unchanged_source(tmp_path):
    original = tmp_path / "source.json"
    original.write_bytes(b'{"value":1}')
    store = ef.LocalArtifactStore(tmp_path / "store")
    first = store.put(original, media_type="application/json")
    second = store.put(original, media_type="application/json")
    assert first.uri != second.uri
    assert first.sha256 == hashlib.sha256(b'{"value":1}').hexdigest()
    assert first.size_bytes == 11
    copied = tmp_path / "copied.json"
    assert store.get(first, copied) == copied
    with pytest.raises(ef.ArtifactIOError):
        store.get(second, copied)
    assert copied.read_bytes() == original.read_bytes() == b'{"value":1}'
    assert not tuple(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("field,value", (("sha256", "0" * 64), ("size_bytes", 99)))
def test_declared_hash_and_size_are_verified(field, value, tmp_path):
    original = tmp_path / "source.json"
    original.write_bytes(b"{}")
    store = ef.LocalArtifactStore(tmp_path / "store")
    ref = store.put(original, media_type="application/json").model_copy(update={field: value})
    target = tmp_path / "copy.json"
    with pytest.raises(ef.ArtifactIntegrityError):
        store.get(ref, target)
    assert not target.exists() and not tuple(tmp_path.rglob("*.part"))


@pytest.mark.parametrize(
    "uri",
    (
        "https://example.org/table.arrow",
        "s3://bucket/table.arrow",
        "gs://bucket/table.arrow",
        "file://server/share/table.arrow",
        "file:////server/share/table.arrow",
    ),
)
def test_remote_uris_fail_without_downloading(uri, tmp_path):
    ref = ef.ArtifactRef(
        schema_version="1.0",
        uri=uri,
        sha256="0" * 64,
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        size_bytes=0,
    )
    with pytest.raises(ef.CapabilityError):
        ef.LocalArtifactStore(tmp_path / "store").get(ref, tmp_path / "copy.arrow")
    with pytest.raises(ef.CapabilityError):
        ef.read_table(ref)
    assert not (tmp_path / "copy.arrow").exists()


@pytest.mark.parametrize("engine", ("pandas", "polars", "duckdb"))
def test_missing_extra_reports_installation_guidance_in_fresh_process(engine, tmp_path):
    script = r"""
import importlib.abc, sys
from pathlib import Path
class MissingEngine(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pandas', 'polars', 'duckdb', 'pyarrow', 'numpy'}:
            raise ModuleNotFoundError('dependency deliberately unavailable')
sys.meta_path.insert(0, MissingEngine())
import equiframe as ef
contract=ef.read_contract(sys.argv[1])
engine=sys.argv[2]
registry=ef.TransformationRegistry()
if engine=='pandas':
    registry.register(ef.PandasTransformation('copy', lambda t,c: t['source'], 'test.v1'))
elif engine=='polars':
    registry.register(ef.PolarsTransformation('copy', lambda t,c: t['source'], 'test.v1'))
else: registry.register(ef.DuckDBTransformation('copy', 'SELECT * FROM source', 'test.v1'))
ref=ef.ArtifactRef(
    schema_version='1.0',uri=Path(sys.argv[1]).as_uri(),sha256='0'*64,
    format='json',media_type='application/json',size_bytes=0)
result=ef.execute(
    ef.ExecutionPlan(contract=contract, engine=engine, transformation_id='copy'),
    source=ef.LocalDataSource({t.name:ref for t in contract.inputs}),
    registry=registry, work_dir=Path(sys.argv[3]))
assert result.state=='invalid_input'
assert result.problem.code=='missing_optional_dependency'
assert 'equiframe['+engine+']' in result.problem.message
assert not result.inputs
"""
    fixture = Path(__file__).parents[1] / "examples" / "nulls_types.json"
    subprocess.run(
        [sys.executable, "-I", "-c", script, str(fixture.resolve()), engine, str(tmp_path)],
        check=True,
    )


def test_registry_is_instance_owned_and_does_not_overwrite():
    first, second = ef.TransformationRegistry(), ef.TransformationRegistry()
    transform = ef.DuckDBTransformation("query", "SELECT 1", "test.v1")
    first.register(transform)
    with pytest.raises(ef.InvalidExecutionInput):
        first.register(transform)
    fixture = Path(__file__).parents[1] / "examples" / "nulls_types.json"
    plan = ef.ExecutionPlan(
        contract=ef.read_contract(fixture), engine="duckdb", transformation_id="query"
    )
    assert first.resolve(plan) is transform
    with pytest.raises(ef.InvalidExecutionInput):
        second.resolve(plan)


@pytest.mark.parametrize("revision", (True, "1", 1.5))
def test_registry_revision_is_strict(revision):
    from pydantic import ValidationError

    registry = ef.TransformationRegistry()
    with pytest.raises(ValidationError):
        registry.register(
            ef.DuckDBTransformation("query", "SELECT 1", "test.v1", revision=revision)
        )
