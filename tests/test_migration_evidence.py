"""Physical receipts reject internally rehashed contradictions; fixtures are synthetic."""

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from pydantic import BaseModel
from test_migration import run, spec

import equiframe as ef
from equiframe._comparison_io import file_ref
from equiframe.evidence import canonical_bytes, inventory, parse_json
from equiframe.execution_types import PhysicalColumn, TableArtifact
from equiframe.migration._physical import physical_size, verify_table_metadata


def captured(tmp_path, data, *, format_name="arrow", index=None):
    path = tmp_path / ("data." + format_name)
    if format_name == "arrow":
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, data.schema) as writer:
            writer.write_table(data, max_chunksize=3)
    else:
        pq.write_table(data, path, row_group_size=3)

    def columns(table):
        return tuple(
            PhysicalColumn(
                name=field.name,
                engine_type="Synthetic native provenance; not recoverable from Arrow",
                arrow_type=str(field.type),
                null_count=table[field.name].null_count,
                nan_count=(
                    int(pc.sum(pc.is_nan(table[field.name])).as_py() or 0)
                    if pa.types.is_floating(field.type)
                    else 0
                ),
            )
            for field in table.schema
        )

    idx = None
    if index is not None:
        ipath = tmp_path / "index.arrow"
        with pa.OSFile(str(ipath), "wb") as sink, pa.ipc.new_file(sink, index.schema) as writer:
            writer.write_table(index)
        idx = file_ref(ipath, "arrow")
    return TableArtifact(
        name="synthetic",
        data=file_ref(path, format_name),
        row_count=data.num_rows,
        columns=columns(data),
        index=idx,
        index_columns=columns(index) if index is not None else (),
    )


def data():
    return pa.table(
        {
            "x": pa.array([None, float("nan"), 1.0, -2.0, None, 5.0, 7.0], from_pandas=False),
            "label": ["a", None, "b", "c", "d", "e", "f"],
        }
    )


@pytest.mark.parametrize("format_name", ["arrow", "parquet"])
def test_physical_metadata_and_materialized_size_stream_batches(tmp_path, format_name):
    artifact = captured(tmp_path, data(), format_name=format_name)
    assert verify_table_metadata(artifact) is None
    materialized = ef.read_table(artifact.data)
    assert physical_size(artifact.data) == (materialized.num_rows, materialized.nbytes)
    assert artifact.data.size_bytes != materialized.nbytes


@pytest.mark.parametrize("format_name", ["arrow", "parquet"])
def test_empty_physical_table_preserves_schema(tmp_path, format_name):
    artifact = captured(tmp_path, data().slice(0, 0), format_name=format_name)
    verify_table_metadata(artifact)
    assert physical_size(artifact.data) == (0, 0)


@pytest.mark.parametrize("fault", ["rows", "name", "type", "nulls", "nans", "column_order"])
def test_metadata_corruption_rejected_even_with_valid_file_hash(tmp_path, fault):
    artifact = captured(tmp_path, data())
    columns = list(artifact.columns)
    if fault == "rows":
        artifact = artifact.model_copy(update={"row_count": 99})
    elif fault == "column_order":
        artifact = artifact.model_copy(update={"columns": tuple(reversed(columns))})
    else:
        field, value = {
            "name": ("name", "different"),
            "type": ("arrow_type", "float"),
            "nulls": ("null_count", 1),
            "nans": ("nan_count", 0),
        }[fault]
        columns[0] = columns[0].model_copy(update={field: value})
        artifact = artifact.model_copy(update={"columns": tuple(columns)})
    with pytest.raises(ef.ArtifactIntegrityError):
        verify_table_metadata(artifact)


def test_index_metadata_and_length_are_verified(tmp_path):
    artifact = captured(tmp_path, data(), index=pa.table({"position": list(range(7))}))
    verify_table_metadata(artifact)
    wrong = artifact.model_copy(
        update={"index_columns": (artifact.index_columns[0].model_copy(update={"null_count": 1}),)}
    )
    with pytest.raises(ef.ArtifactIntegrityError):
        verify_table_metadata(wrong)
    other = tmp_path / "other"
    other.mkdir()
    short = captured(other, data(), index=pa.table({"position": [0, 1]}))
    with pytest.raises(ef.ArtifactIntegrityError):
        verify_table_metadata(short)


@pytest.mark.parametrize("fault", ["hash", "missing", "corrupt", "unsupported_format"])
def test_physical_bytes_are_verified_before_decoding(tmp_path, fault):
    artifact = captured(tmp_path, data())
    ref = artifact.data
    if fault == "hash":
        ref = ref.model_copy(update={"sha256": "0" * 64})
    elif fault == "missing":
        (tmp_path / "data.arrow").unlink()
    elif fault == "corrupt":
        (tmp_path / "data.arrow").write_bytes(b"Not an Arrow IPC file")
        ref = file_ref(tmp_path / "data.arrow", "arrow")
    else:
        ref = ref.model_copy(update={"format": "json"})
    with pytest.raises(ef.ArtifactIntegrityError):
        physical_size(ref)


@pytest.mark.parametrize("problem", [ef.ExecutionCancelled, ef.ExecutionTimeout])
def test_physical_size_preserves_cooperative_interruption_before_batch_decode(tmp_path, problem):
    artifact = captured(tmp_path, data())
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        # Initial checkpoint and one verified file block consume the first three.
        # The next checkpoint occurs before decoding the first IPC batch.
        if calls == 4:
            raise problem("synthetic checkpoint interruption")

    with pytest.raises(problem, match="synthetic checkpoint interruption"):
        physical_size(artifact.data, check=check)
    assert calls == 4


def rewrite(path, value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    path.write_bytes(canonical_bytes(value) + b"\n")


def final_inventory(directory, result, manifest_name):
    return result.model_copy(
        update={
            "evidence": tuple(item for item in inventory(directory) if item.path != manifest_name)
        }
    )


def test_rehashed_root_capture_metadata_is_rejected(tmp_path):
    result = run(tmp_path, document=spec())
    directory = tmp_path / result.migration_id
    assert ef.read_migration(directory) == result
    captured_input = result.inputs[0].model_copy(update={"row_count": 999})
    result = result.model_copy(update={"inputs": (captured_input,)})
    receipt = parse_json((directory / "capture.json").read_bytes())
    receipt["inputs"] = [captured_input.model_dump(mode="json")]
    receipt["rows"] = 999
    rewrite(directory / "capture.json", receipt)
    result = final_inventory(directory, result, "migration.json")
    rewrite(directory / "migration.json", result)
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_migration(directory)


def test_rehashed_child_input_metadata_is_rejected(tmp_path):
    result = run(tmp_path, document=spec())
    directory = tmp_path / result.migration_id
    assert ef.read_migration(directory) == result
    pipeline = result.source
    execution = pipeline.execution
    modified = execution.inputs[0].model_copy(update={"row_count": 999})
    execution = execution.model_copy(update={"inputs": (modified,)})
    pipeline = pipeline.model_copy(update={"execution": execution})
    child = directory / pipeline.pipeline_id
    rewrite(next(child.rglob("run.json")), execution)
    pipeline = final_inventory(child, pipeline, "manifest.json")
    rewrite(child / "manifest.json", pipeline)
    comparison = result.comparison.model_copy(
        update={"left": result.comparison.left.model_copy(update={"execution": execution})}
    )
    rewrite(directory / comparison.comparison_id / "comparison.json", comparison)
    result = result.model_copy(update={"source": pipeline, "comparison": comparison})
    result = final_inventory(directory, result, "migration.json")
    rewrite(directory / "migration.json", result)
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_migration(directory)
