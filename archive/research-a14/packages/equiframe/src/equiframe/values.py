"""Lossless, tagged contract literals; these are metadata, not table encoders."""

import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    PlainSerializer,
    WithJsonSchema,
    model_validator,
)
from typing_extensions import Self

from equiframe._base import FrozenModel, Text, fail
from equiframe._timezones import timezone


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value
    ):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid decimal text") from exc
    else:
        raise ValueError("decimal requires a Decimal or exact decimal string; numbers are rejected")
    if not result.is_finite():
        raise ValueError("decimal must be finite; use tagged float special values")
    return result


def _decimal_text(value: Decimal) -> str:
    # str(Decimal) consults context.capitals even though it never rounds.
    with localcontext() as decimal_context:
        decimal_context.capitals = 1
        return str(value)


ExactDecimal = Annotated[
    Decimal,
    BeforeValidator(_decimal),
    PlainSerializer(_decimal_text, return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$",
        }
    ),
]


def _zone(value: str) -> str:
    timezone(value)
    return value


TimeZone = Annotated[Text, AfterValidator(_zone)]
TimeUnit = Literal["s", "ms", "us", "ns"]


class NullValue(FrozenModel):
    kind: Literal["null"] = "null"


class NaNValue(FrozenModel):
    kind: Literal["nan"] = "nan"


class InfinityValue(FrozenModel):
    kind: Literal["infinity"] = "infinity"
    sign: Literal["positive", "negative"]


class BooleanValue(FrozenModel):
    kind: Literal["boolean"] = "boolean"
    value: bool


class IntegerValue(FrozenModel):
    kind: Literal["integer"] = "integer"
    value: int


class StringValue(FrozenModel):
    kind: Literal["string"] = "string"
    value: str

    @model_validator(mode="after")
    def valid_unicode(self) -> Self:
        if any(0xD800 <= ord(char) <= 0xDFFF for char in self.value):
            fail("invalid_unicode", "string contains a surrogate code point", "value")
        return self


class DecimalValue(FrozenModel):
    kind: Literal["decimal"] = "decimal"
    value: ExactDecimal


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("float literal requires a JSON number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("float literal exceeds representable range") from exc
    if not math.isfinite(result):
        raise ValueError("nonfinite floats require a tagged special value")
    if isinstance(value, int) and int(result) != value:
        raise ValueError("integer cannot be represented as a float without loss")
    return result


class FloatValue(FrozenModel):
    kind: Literal["float"] = "float"
    value: Annotated[float, BeforeValidator(_float)]


class DateValue(FrozenModel):
    kind: Literal["date"] = "date"
    value: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @model_validator(mode="after")
    def valid_date(self) -> Self:
        try:
            date.fromisoformat(self.value)
        except ValueError:
            fail("invalid_date", "invalid calendar date", "value")
        return self


_TIMESTAMP = re.compile(
    r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})T"
    r"(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?P<fraction>\.[0-9]{1,9})?(?P<offset>Z|[+-][0-9]{2}:[0-9]{2})?"
)


def _timestamp_datetime(value: str) -> datetime:
    """Calendar/offset validation without relying on the Python 3.11 ISO parser.

    The declared literal grammar admits 1-9 fraction digits. datetime stores only
    microseconds; exact nanosecond ordering is calculated separately from the
    original unmodified literal by TimestampValue.nanoseconds.
    """
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        raise ValueError("invalid declared timestamp grammar")
    fraction = (match["fraction"] or "").removeprefix(".")
    microseconds = ("." + fraction[:6].ljust(6, "0")) if fraction else ""
    offset = "+00:00" if match["offset"] == "Z" else (match["offset"] or "")
    calendar = (
        f"{match['date']}T{match['hour']}:{match['minute']}:{match['second']}{microseconds}{offset}"
    )
    return datetime.fromisoformat(calendar)


class TimestampValue(FrozenModel):
    kind: Literal["timestamp"] = "timestamp"
    value: str
    zone: TimeZone | None = None

    @model_validator(mode="after")
    def valid_timestamp(self) -> Self:
        match = _TIMESTAMP.fullmatch(self.value)
        if match is None:
            fail(
                "invalid_timestamp",
                "expected ISO timestamp with at most 9 fractional digits",
                "value",
            )
        offset = match["offset"]
        if offset == "-00:00":
            fail(
                "unknown_offset", "-00:00 denotes an unknown offset and is not an instant", "value"
            )
        if offset not in (None, "Z") and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
            fail("invalid_offset", "invalid timestamp offset", "value")
        try:
            instant = _timestamp_datetime(self.value)
        except ValueError:
            fail("invalid_timestamp", "invalid calendar date or clock time", "value")
        if self.zone is not None:
            if instant.tzinfo is None:
                fail("missing_offset", "a zoned literal requires an explicit offset", "value")
            try:
                actual_offset = instant.astimezone(timezone(self.zone)).utcoffset()
            except (OverflowError, ValueError):
                fail("timestamp_range", "zoned instant exceeds supported calendar range", "value")
            if actual_offset != instant.utcoffset():
                fail("zone_offset_mismatch", "offset disagrees with the declared IANA zone", "zone")
        return self

    @property
    def has_offset(self) -> bool:
        return bool(re.search(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$", self.value))

    @property
    def fractional_digits(self) -> int:
        match = _TIMESTAMP.fullmatch(self.value)
        if not (match is not None):
            raise AssertionError("Internal invariant check failed.")
        return len((match["fraction"] or "")[1:])

    def nanoseconds(self, *, instant: bool) -> int:
        """Exact ordering key; no float timestamp or sub-microsecond truncation."""
        match = _TIMESTAMP.fullmatch(self.value)
        if not (match is not None):
            raise AssertionError("Internal invariant check failed.")
        day = date.fromisoformat(match["date"]).toordinal()
        seconds = day * 86400 + int(match["hour"]) * 3600
        seconds += int(match["minute"]) * 60 + int(match["second"])
        offset = match["offset"]
        if instant and not self.has_offset:
            raise ValueError("an instant ordering key requires an explicit offset")
        if instant and offset not in (None, "Z"):
            shift = int(offset[1:3]) * 3600 + int(offset[4:6]) * 60
            seconds -= shift if offset[0] == "+" else -shift
        return seconds * 10**9 + int((match["fraction"] or "")[1:].ljust(9, "0") or "0")

    def in_zone(self, zone: str, *, fold: int) -> datetime:
        """Used only to validate an explicitly declared naive-time policy."""
        return _timestamp_datetime(self.value).replace(tzinfo=timezone(zone), fold=fold)


ScalarValue = Annotated[
    NullValue
    | NaNValue
    | InfinityValue
    | BooleanValue
    | IntegerValue
    | StringValue
    | DecimalValue
    | FloatValue
    | DateValue
    | TimestampValue,
    Field(discriminator="kind"),
]


def offset_nanoseconds(offset: timedelta | None) -> int:
    if offset is None:
        raise ValueError("missing UTC offset")
    return (offset.days * 86400 + offset.seconds) * 10**9 + offset.microseconds * 1000
