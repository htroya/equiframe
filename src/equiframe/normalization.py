"""Authorized scalar normalization, exact arithmetic and physical/logical checks."""

from __future__ import annotations

import json
import math
import struct
from datetime import date, datetime, timedelta
from datetime import timezone as _timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import TYPE_CHECKING

from equiframe._timezones import timezone
from equiframe.comparison_types import ComparisonPolicy, ComparisonValue
from equiframe.contracts import ColumnSpec, DatePolicy, TimestampPolicy
from equiframe.errors import CapabilityError
from equiframe.values import ScalarValue, offset_nanoseconds

UTC = _timezone.utc

if TYPE_CHECKING:
    import pyarrow as pa

NS = {"s": 10**9, "ms": 10**6, "us": 1000, "ns": 1}
EPOCH = date(1970, 1, 1).toordinal()


def logical_signature(dtype: pa.DataType) -> tuple[object, ...]:
    import pyarrow as pa

    if pa.types.is_null(dtype):
        return ("null",)
    if pa.types.is_boolean(dtype):
        return ("boolean",)
    if pa.types.is_integer(dtype):
        return ("integer", dtype.bit_width, pa.types.is_signed_integer(dtype))
    if pa.types.is_floating(dtype) and dtype.bit_width in (32, 64):
        return ("float", dtype.bit_width)
    if any(
        f(dtype) for f in (pa.types.is_string, pa.types.is_large_string, pa.types.is_string_view)
    ):
        return ("string",)
    if pa.types.is_decimal(dtype):
        return ("decimal", dtype.precision, dtype.scale)
    if pa.types.is_date(dtype):
        return ("date",)
    if pa.types.is_timestamp(dtype):
        if dtype.tz is not None:
            try:
                timezone(dtype.tz)
            except (ValueError, KeyError) as error:
                raise CapabilityError("timestamp requires a supported IANA zone") from error
        return ("timestamp", dtype.unit, dtype.tz)
    raise CapabilityError(f"unsupported comparison type: {dtype}")


def schema_compatible(dtype: pa.DataType, column: ColumnSpec, policy: ComparisonPolicy) -> bool:
    observed = logical_signature(dtype)
    expected = tuple(column.logical_type.model_dump().values())
    if observed == expected:
        return True
    if policy.physical_types == "exact":
        return False
    if observed[0] == "null":
        return column.nullable
    if observed[0] != expected[0]:
        return False
    if observed[0] == "timestamp":
        temporal = column.temporal_policy
        if not (isinstance(temporal, TimestampPolicy)):
            raise AssertionError("Internal invariant check failed.")
        # Zone changes only preserve meaning for instant comparison. A naive
        # observation needs the separately authorized assume_zone policy.
        if observed[2] is None:
            return temporal.naive != "reject"
        return temporal.comparison == "instant" or observed[2] == expected[2]
    return observed[0] in ("integer", "float", "decimal")


def physical_value(scalar: pa.Scalar) -> ComparisonValue:
    dtype = scalar.type
    kind = logical_signature(dtype)[0]
    if not scalar.is_valid:
        return ComparisonValue(kind="null")
    if kind == "timestamp":
        return ComparisonValue(
            kind="timestamp", value=str(scalar.value), unit=dtype.unit, timezone=dtype.tz
        )
    if kind == "date":
        import pyarrow as pa

        return ComparisonValue(
            kind="date", value=str(scalar.value), unit="day" if pa.types.is_date32(dtype) else "ms"
        )
    value = scalar.as_py()
    if kind == "float":
        if math.isnan(value):
            return ComparisonValue(kind="nan")
        if math.isinf(value):
            return ComparisonValue(kind="infinity", value="positive" if value > 0 else "negative")
        return ComparisonValue(kind="float", value=repr(value))
    if kind == "boolean":
        return ComparisonValue(kind="boolean", value="true" if value else "false")
    if kind == "decimal":
        with localcontext() as decimal_context:
            decimal_context.capitals = 1
            return ComparisonValue(kind="decimal", value=str(value))
    if kind == "integer":
        return ComparisonValue(kind="integer", value=str(value))
    return ComparisonValue(kind="string", value=value)


def number(value: ComparisonValue) -> Fraction:
    if not (value.value is not None):
        raise AssertionError("Internal invariant check failed.")
    if value.kind == "float":
        return Fraction.from_float(float(value.value))
    return Fraction(Decimal(value.value))


def identity(value: ComparisonValue) -> tuple[object, ...]:
    if value.kind in ("integer", "decimal", "float"):
        n = number(value)
        return value.kind, str(n.numerator), str(n.denominator)
    return value.kind, value.value, value.unit, value.timezone


def row_identity(row: tuple[ComparisonValue, ...]) -> bytes:
    return json.dumps([identity(v) for v in row], ensure_ascii=True, separators=(",", ":")).encode(
        "ascii"
    )


def temporal_point(value: ComparisonValue, policy: TimestampPolicy) -> int:
    if not (value.value is not None and value.unit in NS):
        raise AssertionError("Internal invariant check failed.")
    ns = int(value.value) * NS[value.unit]
    if value.timezone is None:
        if policy.naive == "reject":
            raise ValueError("naive_timestamp")
        if policy.naive == "preserve":
            return ns
        if not (policy.timezone is not None):
            raise AssertionError("Internal invariant check failed.")
        wall = _datetime(ns)
        choices = [wall.replace(tzinfo=timezone(policy.timezone), fold=fold) for fold in (0, 1)]
        valid = [
            v
            for v in choices
            if v.astimezone(UTC).astimezone(v.tzinfo).replace(tzinfo=None) == wall
        ]
        if not valid:
            raise ValueError("nonexistent_time")
        offsets = {offset_nanoseconds(v.utcoffset()) for v in valid}
        if len(offsets) > 1 and policy.ambiguous == "reject":
            raise ValueError("ambiguous_time")
        if policy.comparison == "wall_time":
            return ns
        choices_ns = [ns - offset for offset in offsets]
        return max(choices_ns) if policy.ambiguous == "later" else min(choices_ns)
    if policy.comparison == "instant":
        return ns
    try:
        local = _datetime(ns).replace(tzinfo=UTC).astimezone(timezone(value.timezone))
    except (OverflowError, ValueError) as error:
        raise CapabilityError("zoned timestamp exceeds supported calendar range") from error
    return ns + offset_nanoseconds(local.utcoffset())


def _datetime(ns: int) -> datetime:
    try:
        return datetime(1970, 1, 1) + timedelta(seconds=ns // 10**9)
    except OverflowError as error:
        raise CapabilityError("zone/DST computation requires calendar years 1..9999") from error


def normalize(
    value: ComparisonValue, column: ColumnSpec
) -> tuple[ComparisonValue, tuple[str, ...]]:
    """Return normalized value and observable violations; never repair a value."""
    issues: list[str] = []
    out = value
    if value.kind == "nan":
        if column.nan_policy and column.nan_policy.handling == "forbid":
            issues.append("nan_forbidden")
        if column.nan_policy and column.nan_policy.handling == "as_null":
            out = ComparisonValue(kind="null")
    if (
        value.kind == "string"
        and value.value == ""
        and "empty_string" in column.null_policy.representations
    ):
        out = ComparisonValue(kind="null")
    if (
        value.kind in ("integer", "decimal", "float")
        and "zero" in column.null_policy.representations
        and number(value) == 0
    ):
        out = ComparisonValue(kind="null")
    if out.kind == "null":
        if not column.nullable:
            issues.append("null_forbidden")
    elif value.kind == column.logical_type.kind:
        dtype = column.logical_type
        if dtype.kind == "integer":
            n = number(value)
            if (
                not -(2 ** (dtype.bits - 1)) * int(dtype.signed)
                <= n
                < 2 ** (dtype.bits - int(dtype.signed))
            ):
                issues.append("integer_range")
        elif dtype.kind == "float" and dtype.bits == 32:
            try:
                represented = struct.unpack("!f", struct.pack("!f", float(value.value or "0")))[0]
                if Fraction.from_float(represented) != number(value):
                    issues.append("float_precision")
            except (OverflowError, ValueError):
                issues.append("float_precision")
        elif dtype.kind == "decimal":
            n = number(value)
            scaled = n * 10**dtype.scale
            if scaled.denominator != 1 or abs(scaled) >= 10**dtype.precision:
                issues.append("decimal_precision")
        elif dtype.kind == "date":
            if not (value.value is not None):
                raise AssertionError("Internal invariant check failed.")
            days = int(value.value)
            if value.unit == "ms":
                if days % 86400000:
                    issues.append("date_granularity")
                days //= 86400000
            out = ComparisonValue(kind="date", value=str(days), unit="day")
            policy = column.temporal_policy
            if not (isinstance(policy, DatePolicy)):
                raise AssertionError("Internal invariant check failed.")
            lower = (
                date.fromisoformat(policy.lower.value).toordinal() - EPOCH if policy.lower else None
            )
            upper = (
                date.fromisoformat(policy.upper.value).toordinal() - EPOCH if policy.upper else None
            )
            if not in_interval(days, lower, upper, policy.closed):
                issues.append("temporal_interval")
        elif dtype.kind == "timestamp":
            stamp = column.temporal_policy
            if not (isinstance(stamp, TimestampPolicy)):
                raise AssertionError("Internal invariant check failed.")
            try:
                point = temporal_point(value, stamp)
            except ValueError as error:
                issues.append(str(error))
            else:
                if point % NS[stamp.granularity]:
                    issues.append("timestamp_granularity")
                out = ComparisonValue(
                    kind="timestamp",
                    value=str(point),
                    unit="ns",
                    timezone="UTC" if stamp.comparison == "instant" else None,
                )
                lower = (
                    stamp._bound(stamp.lower, "lower") - EPOCH * 86400 * 10**9
                    if stamp.lower
                    else None
                )
                upper = (
                    stamp._bound(stamp.upper, "upper") - EPOCH * 86400 * 10**9
                    if stamp.upper
                    else None
                )
                if not in_interval(point, lower, upper, stamp.closed):
                    issues.append("temporal_interval")
    if column.allowed_values:
        allowed_column = column.model_copy(update={"allowed_values": ()})
        allowed = (allowed_value(v, allowed_column) for v in column.allowed_values)
        if not any(identity(out) == identity(v) for v in allowed):
            issues.append("allowed_values")
    return out, tuple(issues)


def allowed_value(value: ScalarValue, column: ColumnSpec) -> ComparisonValue:
    policy = column.temporal_policy
    if value.kind == "timestamp" and isinstance(policy, TimestampPolicy):
        return ComparisonValue(
            kind="timestamp",
            unit="ns",
            timezone="UTC" if policy.comparison == "instant" else None,
            value=str(policy._bound(value, "allowed_values") - EPOCH * 86400 * 10**9),
        )
    return normalize(literal(value), column)[0]


def in_interval(point: int, lower: int | None, upper: int | None, closed: str) -> bool:
    return not (
        (
            lower is not None
            and (point < lower or (point == lower and closed not in ("both", "left")))
        )
        or (
            upper is not None
            and (point > upper or (point == upper and closed not in ("both", "right")))
        )
    )


def literal(value: ScalarValue) -> ComparisonValue:
    if value.kind == "null" or value.kind == "nan":
        return ComparisonValue(kind=value.kind)
    if value.kind == "infinity":
        return ComparisonValue(kind="infinity", value=value.sign)
    if value.kind == "date":
        return ComparisonValue(
            kind="date", value=str(date.fromisoformat(value.value).toordinal() - EPOCH), unit="day"
        )
    if value.kind == "timestamp":
        return ComparisonValue(
            kind="timestamp",
            unit="ns",
            timezone="UTC" if value.has_offset else None,
            value=str(value.nanoseconds(instant=value.has_offset) - EPOCH * 86400 * 10**9),
        )
    if value.kind == "boolean":
        return ComparisonValue(kind="boolean", value="true" if value.value else "false")
    with localcontext() as decimal_context:
        decimal_context.capitals = 1
        return ComparisonValue(kind=value.kind, value=str(value.value))


def equal(left: ComparisonValue, right: ComparisonValue, column: ColumnSpec) -> bool:
    if identity(left) == identity(right):
        return True
    policy = column.numeric_policy
    if (
        not policy
        or not policy.tolerance
        or left.kind != right.kind
        or left.kind not in ("integer", "float")
    ):
        return False
    a, b = number(left), number(right)
    tolerance = policy.tolerance
    return abs(a - b) <= max(
        Fraction(tolerance.absolute or 0), Fraction(tolerance.relative or 0) * max(abs(a), abs(b))
    )


def order_value(value: ComparisonValue) -> tuple[int, Fraction | str]:
    if value.kind == "nan":
        return 3, ""
    if value.kind == "infinity":
        return (0 if value.value == "negative" else 2), ""
    if value.kind in ("integer", "float", "decimal"):
        return 1, number(value)
    if value.kind in ("date", "timestamp"):
        return 1, Fraction(int(value.value or "0"))
    return 1, value.value or ""
