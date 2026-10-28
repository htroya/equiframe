"""Closed native-to-Arrow admission shared by DuckDB execution and capture.

Arrow validation cannot prove native fidelity: DuckDB can export a UHUGEINT as
a valid decimal128 with a different value. Admit native types before export,
then require their exact Arrow representation and reject temporal sentinels.
Optional engines are imported only when a transport check actually runs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from equiframe.errors import CapabilityError
from equiframe.tables import check_arrow

if TYPE_CHECKING:
    import pyarrow as pa


def duckdb_parameters(parameters: Mapping[str, object]) -> dict[str, object]:
    """Bind admitted scalars without DuckDB's lossy Python Decimal inference.

    Decimal is rendered exactly (no context arithmetic), then explicitly typed
    before native execution. In particular, leading fractional zeros can make
    DuckDB's automatic Decimal inference exceed precision 38 and use DOUBLE.
    """
    import duckdb

    bound = {}
    for name, value in parameters.items():
        if value is None or type(value) in (bool, str, float):
            bound[name] = value
            continue
        if type(value) is int and -(2**63) <= value < 2**64:
            bound[name] = value
            continue
        if type(value) is Decimal:
            if not value.is_finite() or (value.is_zero() and value.is_signed()):
                raise CapabilityError("DuckDB parameters cannot retain this Decimal representation")
            digits = value.as_tuple()
            exponent = int(digits.exponent)
            precision = max(len(digits.digits), -exponent)
            if exponent <= 0 and precision <= 38:
                bound[name] = duckdb.Value(
                    format(value, "f"), duckdb.decimal_type(precision, -exponent)
                )
                continue
        raise CapabilityError(
            "DuckDB parameters admit plain NULL/bool/text/float, 64-bit integers and "
            "finite nonnegative-scale Decimal up to precision 38; use text with explicit "
            "SQL casts for temporal or other intentionally converted literals"
        )
    return bound


def duckdb_arrow_schema(native_types: tuple[tuple[str, str], ...], timezone: str) -> pa.Schema:
    """Return the exact admitted schema, without casting or erasing native types.

    The names are observed result names and types are DuckDB's canonical native
    descriptions, not user SQL aliases. DuckDB result fields are always nullable.
    HUGEINT, UHUGEINT and unknown/extended types deliberately have no mapping.
    """
    import pyarrow as pa

    if not isinstance(timezone, str) or not timezone:
        raise CapabilityError("DuckDB result transport requires its effective session timezone")
    if not native_types:
        raise CapabilityError("DuckDB result transport requires a nonempty native schema")
    scalar_types = {
        "BOOLEAN": pa.bool_(),
        "TINYINT": pa.int8(),
        "SMALLINT": pa.int16(),
        "INTEGER": pa.int32(),
        "BIGINT": pa.int64(),
        "UTINYINT": pa.uint8(),
        "USMALLINT": pa.uint16(),
        "UINTEGER": pa.uint32(),
        "UBIGINT": pa.uint64(),
        "FLOAT": pa.float32(),
        "DOUBLE": pa.float64(),
        "VARCHAR": pa.string(),
        "DATE": pa.date32(),
        "TIMESTAMP_S": pa.timestamp("s"),
        "TIMESTAMP_MS": pa.timestamp("ms"),
        "TIMESTAMP": pa.timestamp("us"),
        "TIMESTAMP_NS": pa.timestamp("ns"),
        "TIMESTAMP WITH TIME ZONE": pa.timestamp("us", tz=timezone),
    }
    fields = []
    names = set()
    for name, native_type in native_types:
        if not isinstance(name, str) or not name or name in names:
            raise CapabilityError("DuckDB result column names must be nonempty and unique")
        names.add(name)
        dtype = scalar_types.get(native_type)
        if dtype is None:
            decimal = re.fullmatch(r"DECIMAL\(([0-9]{1,2}),([0-9]{1,2})\)", native_type)
            if decimal is not None:
                precision, scale = (int(value) for value in decimal.groups())
                if 1 <= precision <= 38 and 0 <= scale <= precision:
                    dtype = pa.decimal128(precision, scale)
        if dtype is None:
            if native_type in {"HUGEINT", "UHUGEINT"}:
                raise CapabilityError(
                    "DuckDB HUGEINT/UHUGEINT results have no faithful admitted Arrow transport; "
                    "use an explicit checked BIGINT or DECIMAL cast in the caller's SQL "
                    "when its range and semantics permit it"
                )
            raise CapabilityError("unsupported faithful DuckDB native result type")
        fields.append(pa.field(name, dtype, nullable=True))
    return pa.schema(fields)


def duckdb_temporal_capabilities(table: pa.Table) -> None:
    """Reject native infinity markers that Arrow exposes as ordinary ticks."""
    import pyarrow as pa
    import pyarrow.compute as pc

    for field in table.schema:
        if pa.types.is_timestamp(field.type):
            bounds = pc.min_max(table[field.name].cast(pa.int64())).as_py()
            if bounds["min"] is not None and (
                bounds["min"] <= -(2**63 - 1) or bounds["max"] >= 2**63 - 1
            ):
                raise CapabilityError(
                    "DuckDB timestamp infinity/sentinel values cannot be represented "
                    "faithfully in Arrow"
                )
        elif pa.types.is_date32(field.type):
            values = table[field.name].cast(pa.int32())
            sentinels = pa.array([-(2**31 - 1), 2**31 - 1], type=pa.int32())
            if pc.any(pc.is_in(values, value_set=sentinels)).as_py():
                raise CapabilityError(
                    "DuckDB date infinity values cannot be represented faithfully in Arrow"
                )


def verify_duckdb_table(
    table: pa.Table, native_types: tuple[tuple[str, str], ...], timezone: str
) -> None:
    """Validate physical data, exact native mapping and finite temporal values."""
    expected = duckdb_arrow_schema(native_types, timezone)
    check_arrow(table)
    if not table.schema.equals(expected, check_metadata=True):
        raise CapabilityError("DuckDB Arrow result schema differs from its admitted native schema")
    duckdb_temporal_capabilities(table)
