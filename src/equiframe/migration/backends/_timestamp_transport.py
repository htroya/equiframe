"""Explicit timestamp tick encoding for trusted IR implementations.

This codec changes representation only. It never localizes a wall time, chooses
an offset, changes a tick, or converts a wrongly typed native result to fit a
contract. Each compiler remains responsible for its native computation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from equiframe.contracts import Contract, TimestampType
from equiframe.errors import CapabilityError
from equiframe.registry import DuckDBTransformation, PolarsTransformation
from equiframe.tables import LoadedTable, check_arrow

if TYPE_CHECKING:
    import pyarrow as pa

_TimestampColumns = tuple[tuple[str, TimestampType], ...]


def _view_columns(table: pa.Table, columns: _TimestampColumns, *, encode: bool) -> pa.Table:
    """Reinterpret exact 64-bit buffers, retaining values, masks and metadata."""
    import pyarrow as pa

    check_arrow(table)
    result: pa.Table = table
    for name, logical in columns:
        position = result.schema.get_field_index(name)
        if position < 0:
            raise CapabilityError("IR timestamp transport column is missing")
        field = result.schema.field(position)
        timestamp = pa.timestamp(logical.unit, tz=logical.timezone)
        required, target = (timestamp, pa.int64()) if encode else (pa.int64(), timestamp)
        if field.type != required:
            raise CapabilityError("IR timestamp transport received an unexpected physical type")
        array: pa.ChunkedArray = pa.chunked_array(
            [chunk.view(target) for chunk in result.column(position).chunks], type=target
        )
        result = result.set_column(
            position,
            pa.field(name, target, nullable=field.nullable, metadata=field.metadata),
            array,
        )
    check_arrow(result)
    return result


@dataclass(frozen=True)
class _TimestampCodec:
    inputs: tuple[tuple[str, _TimestampColumns], ...] = ()
    output: _TimestampColumns = ()

    @classmethod
    def for_contract(cls, contract: Contract) -> _TimestampCodec:
        """Describe the encoding only after the compiler validates its IR schema."""
        return cls(
            inputs=tuple(
                (
                    table.name,
                    tuple(
                        (column.name, column.logical_type)
                        for column in table.schema_spec.columns
                        if isinstance(column.logical_type, TimestampType)
                    ),
                )
                for table in contract.inputs
                if any(isinstance(c.logical_type, TimestampType) for c in table.schema_spec.columns)
            ),
            output=tuple(
                (column.name, column.logical_type)
                for column in contract.output.schema_spec.columns
                if isinstance(column.logical_type, TimestampType)
            ),
        )

    def encode_input(self, name: str, loaded: LoadedTable) -> LoadedTable:
        columns = dict(self.inputs).get(name, ())
        if not columns:
            return loaded
        return replace(
            loaded,
            table=_view_columns(loaded.table, columns, encode=True),
            native=None,
            native_types=(),
            notes=(*loaded.notes, "IR internal timestamp encoding: unchanged signed int64 ticks."),
        )

    def encode_inputs(self, inputs: Mapping[str, LoadedTable]) -> dict[str, LoadedTable]:
        descriptors = dict(self.inputs)
        if not descriptors.keys() <= inputs.keys():
            raise CapabilityError("IR timestamp transport input is missing")
        return {name: self.encode_input(name, loaded) for name, loaded in inputs.items()}

    def decode_output(self, table: pa.Table) -> pa.Table:
        return _view_columns(table, self.output, encode=False)


@dataclass(frozen=True)
class _TimestampDuckDBTransformation(DuckDBTransformation):
    timestamp_codec: _TimestampCodec | None = None


@dataclass(frozen=True)
class _TimestampPolarsTransformation(PolarsTransformation):
    timestamp_codec: _TimestampCodec | None = None
