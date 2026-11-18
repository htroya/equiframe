"""Pinned migration inputs retain provider-native observations and their origin."""

import pandas as pd
import pyarrow as pa
from test_migration import spec

import equiframe as ef
from equiframe.tables import pandas_capture


def test_pandas_provenance_survives_capture_and_both_pinned_native_inputs(tmp_path):
    frame = pd.DataFrame(
        {
            "id": pd.Series([1, 2, 3], dtype="Int64"),
            "value": pd.Series(["a", None, "c"], dtype="string"),
        }
    )
    original = frame.copy(deep=True)
    observations = pandas_capture(frame)
    result = ef.migrate(
        spec(),
        source=ef.LocalDataSource({"input": ef.PandasInput(frame)}),
        work_dir=tmp_path,
    )
    assert result.complete
    assert result.state == "equivalent"
    captured = result.inputs[0]
    observed_types = tuple((column.name, column.engine_type) for column in captured.columns)
    assert observed_types == observations.native_types
    assert observed_types[0] == ("id", "Int64")
    assert captured.notes == observations.notes
    assert ef.read_table(captured.data).equals(observations.table)
    assert captured.index is not None
    assert ef.read_table(captured.index).equals(observations.index)
    for pipeline in (result.source, result.target):
        child = pipeline.execution.inputs[0]
        assert (
            tuple((column.name, column.engine_type) for column in child.columns) == observed_types
        )
        assert child.notes[:-1] == captured.notes
        assert child.origin == captured.data
        assert child.notes[-1] == "Fixed migration snapshot; original provider is not called again."
        assert ef.read_table(child.data).equals(observations.table)
    pd.testing.assert_frame_equal(frame, original)
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_custom_provider_origin_and_notes_survive_detachment(tmp_path):
    source_table = pa.table({"id": [1, 2, 3], "value": ["a", None, "c"]})
    path = tmp_path / "source.arrow"
    with path.open("wb") as sink, pa.ipc.new_file(sink, source_table.schema) as writer:
        writer.write_table(source_table)
    origin = ef.LocalArtifactStore(tmp_path / "provider").put(
        path, media_type="application/vnd.apache.arrow.file"
    )

    class Provider:
        table_names = ("input",)

        def resolve(self, name, *, context):
            return ef.LoadedTable(
                source_table,
                native_types=(("id", "provider integer"), ("value", "provider text")),
                origin=origin,
                notes=("Provider capture revision 7; source NULL mask preserved.",),
            )

    result = ef.migrate(spec(), source=Provider(), work_dir=tmp_path / "runs")
    assert result.complete
    assert result.inputs[0].origin == origin
    assert result.inputs[0].columns[0].engine_type == "provider integer"
    assert result.source.execution.inputs[0].notes[0] == result.inputs[0].notes[0]
    assert result.target.execution.inputs[0].notes[0] == result.inputs[0].notes[0]
