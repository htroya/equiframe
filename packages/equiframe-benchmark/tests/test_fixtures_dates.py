"""UTC date fixture preserves boundaries and NULL through native Pandas."""

from datetime import date, datetime

import equiframe as ef
import pyarrow as pa
import pytest

from equiframe_benchmark.fixtures import cases, registry


@pytest.mark.parametrize("empty", [False, True])
def test_dates_pandas_preserves_utc_boundaries_nulls_and_duplicates(tmp_path, empty):
    case = next(case for case in cases() if case.contract.family == "dates")
    rows = (
        []
        if empty
        else [
            {"sensor_id": "0007", "recorded_at": datetime.fromisoformat(value)}
            for value in (
                "1969-12-31T23:59:59.999999+00:00",
                "2024-02-29T23:59:59.999999+00:00",
                "2024-03-01T00:00:00.000000+00:00",
                "2024-02-29T23:59:59.999999+00:00",
            )
        ]
    )
    if not empty:
        rows.insert(2, {"sensor_id": "0008", "recorded_at": None})
    inputs = pa.Table.from_pylist(rows, schema=case.inputs["readings"].schema)
    result = ef.run_pipeline(
        ef.PipelineSpec(
            execution=ef.ExecutionPlan(
                contract=case.contract, engine="pandas", transformation_id="dates"
            )
        ),
        source=ef.LocalDataSource({"readings": ef.ArrowInput(inputs)}),
        registry=registry(),
        work_dir=tmp_path,
    )
    assert result.execution.state == "completed"
    assert result.execution.output is not None
    actual = ef.read_table(result.execution.output.data)
    assert actual.schema == pa.schema([("sensor_id", pa.string()), ("day", pa.date32())])
    expected = (
        []
        if empty
        else [
            {"sensor_id": "0007", "day": date(1969, 12, 31)},
            {"sensor_id": "0007", "day": date(2024, 2, 29)},
            {"sensor_id": "0008", "day": None},
            {"sensor_id": "0007", "day": date(2024, 3, 1)},
            {"sensor_id": "0007", "day": date(2024, 2, 29)},
        ]
    )
    assert actual.to_pylist() == expected
