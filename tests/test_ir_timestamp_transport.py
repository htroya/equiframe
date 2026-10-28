"""Tick transport rejects coercion and retains the actual native buffers."""

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.migration.backends._timestamp_transport import _TimestampCodec
from equiframe.tables import LoadedTable


@pytest.mark.parametrize("unit", ("s", "ms", "us", "ns"))
@pytest.mark.parametrize("zone", (None, "UTC", "America/New_York"))
def test_tick_codec_preserves_extremes_chunks_nulls_and_metadata(unit, zone):
    logical = ef.TimestampType(unit=unit, timezone=zone)
    dtype = pa.timestamp(unit, tz=zone)
    ticks = [-(2**63), -1, 0, 1, 2**63 - 1, None, 1]
    array = pa.chunked_array([pa.array(ticks[:3], type=dtype), pa.array(ticks[3:], type=dtype)])
    field = pa.field("t", dtype, metadata={b"source": b"synthetic transport fixture"})
    source = pa.Table.from_arrays(
        [array], schema=pa.schema([field], metadata={b"table": b"fixture"})
    )
    loaded = LoadedTable(source, native=object(), notes=("original",))
    codec = _TimestampCodec(inputs=(("input", (("t", logical),)),), output=(("t", logical),))
    encoded = codec.encode_inputs({"input": loaded})["input"]
    assert encoded.native is None and source.equals(loaded.table, check_metadata=True)
    assert encoded.table.column("t").type == pa.int64()
    assert encoded.table.column("t").to_pylist() == ticks
    restored = codec.decode_output(encoded.table)
    assert restored.equals(source, check_metadata=True)
    for before, after in zip(source.column("t").chunks, restored.column("t").chunks, strict=True):
        assert [None if value is None else value.address for value in before.buffers()] == [
            None if value is None else value.address for value in after.buffers()
        ]


@pytest.mark.parametrize(
    "native_type", (pa.float64(), pa.uint64(), pa.string(), pa.timestamp("us"))
)
def test_tick_codec_rejects_wrong_native_output_instead_of_casting(native_type):
    codec = _TimestampCodec(output=(("t", ef.TimestampType(unit="ns", timezone="UTC")),))
    source = pa.table({"t": pa.array([], type=native_type)})
    with pytest.raises(ef.CapabilityError, match="physical type"):
        codec.decode_output(source)


def test_tick_codec_rejects_wrong_input_unit_and_missing_column():
    logical = ef.TimestampType(unit="s", timezone="UTC")
    codec = _TimestampCodec(inputs=(("input", (("t", logical),)),))
    for source in (
        pa.table({"t": pa.array([], type=pa.timestamp("ms", tz="UTC"))}),
        pa.table({"other": pa.array([], type=pa.timestamp("s", tz="UTC"))}),
    ):
        with pytest.raises(ef.CapabilityError):
            codec.encode_inputs({"input": LoadedTable(source)})
