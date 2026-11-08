"""Private IANA loader: the locked tzdata package is authoritative on every host."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from itertools import pairwise
from typing import Literal
from zoneinfo import ZoneInfo

# This complete TZif resource has no transitions, one zero-offset type and the
# fixed <-00>0 continuation. Factory's declared name is retained by the timestamp
# codec; only the native localization kernel uses its equivalent UTC offset.
_FACTORY_FIXED_ZERO_SHA256 = "d32b579ed0a7427316bea260b9ee2675451046bd58c57c679c24f2671860af76"


def native_timezone_key(key: str) -> str:
    """Select a native kernel name, preserving the contract's timezone identity.

    Chrono/ICU need not recognize IANA's Factory name. Its exact installed TZif
    semantics can use their UTC kernel, without a Python row callback or a change
    to output metadata. A different resource must be reviewed before that mapping
    is used; other named zones always use their own native kernel.
    """
    if key != "Factory":
        return key
    resource = files("tzdata.zoneinfo").joinpath("Factory").read_bytes()
    if sha256(resource).hexdigest() != _FACTORY_FIXED_ZERO_SHA256:
        raise ValueError("Factory timezone resource differs from the verified fixed-zero TZif")
    return "UTC"


@lru_cache(maxsize=128)
def timezone(key: str) -> ZoneInfo:
    # Resolve only zone names, never arbitrary paths or other package resources.
    if re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", key) is None:
        raise ValueError("unknown IANA time zone: " + key)
    try:
        with files("tzdata.zoneinfo").joinpath(*key.split("/")).open("rb") as stream:
            return ZoneInfo.from_file(stream, key=key)
    except (OSError, ValueError) as exc:
        raise ValueError("unknown IANA time zone: " + key) from exc


@dataclass(frozen=True)
class _TimezoneRule:
    kind: Literal["M", "J", "N"]
    values: tuple[int, ...]
    seconds: int = 7200


@dataclass(frozen=True)
class _TimezoneContinuation:
    standard: int
    daylight: int | None = None
    start: _TimezoneRule | None = None
    end: _TimezoneRule | None = None


@dataclass(frozen=True)
class _TimezoneData:
    transitions: tuple[int, ...]
    interval_offsets: tuple[int, ...]
    offsets: tuple[int, ...]
    continuation: _TimezoneContinuation | None
    resource_sha256: str


def _require_tzif(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _tzif_clock(value: str, *, rule_clock: bool = False) -> int:
    match = re.fullmatch(r"([+-]?)([0-9]{1,3})(?::([0-9]{1,2})(?::([0-9]{1,2}))?)?", value)
    if match is None:
        raise ValueError("Invalid TZif POSIX clock or offset")
    sign, hours, minutes, seconds = match.groups()
    hour, minute, second = int(hours), int(minutes or 0), int(seconds or 0)
    _require_tzif(
        hour <= (167 if rule_clock else 24) and minute < 60 and second < 60,
        "TZif POSIX clock or offset exceeds supported bounds",
    )
    return (-1 if sign == "-" else 1) * (hour * 3600 + minute * 60 + second)


def _tzif_rule(value: str) -> _TimezoneRule:
    parts = value.split("/")
    _require_tzif(1 <= len(parts) <= 2, "Invalid TZif POSIX rule clock")
    day = parts[0]
    seconds = _tzif_clock(parts[1], rule_clock=True) if len(parts) == 2 else 7200
    if day.startswith("M"):
        match = re.fullmatch(r"M([0-9]{1,2})\.([1-5])\.([0-6])", day)
        if match is None:
            raise ValueError("Invalid TZif month/week/weekday rule")
        month, week, weekday = map(int, match.groups())
        _require_tzif(1 <= month <= 12, "Invalid TZif rule month")
        return _TimezoneRule("M", (month, week, weekday), seconds)
    if day.startswith("J"):
        _require_tzif(re.fullmatch(r"J[0-9]{1,3}", day) is not None, "Invalid TZif Julian rule")
        number = int(day[1:])
        _require_tzif(1 <= number <= 365, "Invalid TZif Julian day")
        return _TimezoneRule("J", (number,), seconds)
    _require_tzif(re.fullmatch(r"[0-9]{1,3}", day) is not None, "Invalid TZif Julian rule")
    number = int(day)
    _require_tzif(0 <= number <= 365, "Invalid TZif zero-based Julian day")
    return _TimezoneRule("N", (number,), seconds)


def _tzif_continuation(value: str) -> _TimezoneContinuation | None:
    if not value:
        return None
    abbreviation = r"(?:[A-Za-z]{3,}|<[-+A-Za-z0-9]{3,}>)"
    number = r"[+-]?[0-9]{1,3}(?::[0-9]{1,2}(?::[0-9]{1,2})?)?"
    pattern = rf"({abbreviation})({number})(?:({abbreviation})({number})?)?(?:,([^,]+),([^,]+))?"
    match = re.fullmatch(pattern, value)
    if match is None:
        raise ValueError("Invalid TZif POSIX continuation")
    _, standard_text, daylight_name, daylight_text, start, end = match.groups()
    standard = -_tzif_clock(standard_text)
    _require_tzif(abs(standard) <= 86400, "TZif UTC offset exceeds one day")
    if daylight_name is None:
        _require_tzif(start is None and end is None, "Fixed TZif continuation has transition rules")
        return _TimezoneContinuation(standard)
    if start is None or end is None:
        raise ValueError("TZif daylight continuation requires explicit rules")
    daylight = -_tzif_clock(daylight_text) if daylight_text is not None else standard + 3600
    _require_tzif(abs(daylight) <= 86400, "TZif UTC offset exceeds one day")
    return _TimezoneContinuation(standard, daylight, _tzif_rule(start), _tzif_rule(end))


@lru_cache(maxsize=128)
def _parse_timezone_data(raw: bytes) -> _TimezoneData:
    """Read bounded POSIX TZif metadata; never evaluate code from a resource."""
    _require_tzif(len(raw) <= 1024**2, "TZif metadata exceeds resource size limit")

    def header(position: int) -> tuple[int, tuple[int, int, int, int, int, int]]:
        _require_tzif(
            raw[position : position + 4] == b"TZif" and len(raw) >= position + 44,
            "Invalid or truncated TZif header",
        )
        version = raw[position + 4]
        _require_tzif(version in (0, ord("2"), ord("3"), ord("4")), "Unsupported TZif version")
        _require_tzif(
            not any(raw[position + 5 : position + 20]), "Nonzero TZif reserved header bytes"
        )
        ut, standard, leaps, times, types, chars = struct.unpack_from(">6I", raw, position + 20)
        counts = (int(ut), int(standard), int(leaps), int(times), int(types), int(chars))
        _require_tzif(
            1 <= types <= 256 and ut in (0, types) and standard in (0, types),
            "Invalid TZif type counts",
        )
        _require_tzif(leaps == 0, "Leap-adjusted TZif does not define POSIX timestamp metadata")
        return version, counts

    def block_size(counts: tuple[int, int, int, int, int, int], width: int) -> int:
        ut, standard, leaps, times, types, chars = counts
        return width * times + times + 6 * types + chars + (width + 4) * leaps + standard + ut

    version, counts = header(0)
    position, width = 44, 4
    if version:
        next_header = position + block_size(counts, width)
        second_version, counts = header(next_header)
        _require_tzif(second_version == version, "TZif header versions differ")
        position, width = next_header + 44, 8
    end = position + block_size(counts, width)
    _require_tzif(end <= len(raw), "Truncated TZif data block")
    ut, standard, _, times, types, chars = counts
    transitions = tuple(
        int(value)
        for value in struct.unpack_from(
            ">" + str(times) + ("q" if width == 8 else "l"), raw, position
        )
    )
    _require_tzif(
        all(first < second for first, second in pairwise(transitions)),
        "Unsorted TZif transitions",
    )
    position += width * times
    indices = raw[position : position + times]
    position += times
    records: list[tuple[int, int, int]] = []
    for index in range(types):
        offset, daylight, abbreviation = struct.unpack_from(">lBB", raw, position + 6 * index)
        records.append((int(offset), int(daylight), int(abbreviation)))
    _require_tzif(
        all(
            abs(offset) <= 86400 and daylight in (0, 1) and abbreviation < chars
            for offset, daylight, abbreviation in records
        ),
        "Invalid TZif offset or type record",
    )
    _require_tzif(all(index < types for index in indices), "TZif transition type outside table")
    abbreviations = raw[position + 6 * types : position + 6 * types + chars]
    _require_tzif(
        all(abbreviations.find(b"\x00", index) >= 0 for _, _, index in records),
        "Unterminated TZif designation",
    )
    indicators = position + 6 * types + chars
    standard_flags = raw[indicators : indicators + standard] if standard else bytes(types)
    ut_flags = raw[indicators + standard : indicators + standard + ut] if ut else bytes(types)
    _require_tzif(
        all(value in (0, 1) for value in (*standard_flags, *ut_flags))
        and all(
            not universal or wall_standard
            for universal, wall_standard in zip(ut_flags, standard_flags, strict=True)
        ),
        "Invalid TZif standard/UT indicators",
    )
    # RFC 9636 assigns time type 0 before the first transition. Explicit UTC
    # transition intervals retain historical second offsets and date-line jumps.
    offsets = (records[0][0], *(records[index][0] for index in indices))
    footer = raw[end:]
    if version:
        _require_tzif(
            footer.startswith(b"\n") and footer.endswith(b"\n") and footer.count(b"\n") == 2,
            "Invalid TZif continuation framing",
        )
        continuation = _tzif_continuation(footer[1:-1].decode("ascii"))
    else:
        _require_tzif(not footer, "Unexpected TZif v1 trailing data")
        continuation = None
    possible = set(offsets)
    if continuation is not None:
        possible.add(continuation.standard)
        if continuation.daylight is not None:
            possible.add(continuation.daylight)
    return _TimezoneData(
        transitions, offsets, tuple(sorted(possible)), continuation, sha256(raw).hexdigest()
    )


def _timezone_resource(key: str) -> bytes:
    if re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", key) is None:
        raise ValueError("unknown IANA time zone: " + key)
    try:
        return files("tzdata.zoneinfo").joinpath(*key.split("/")).read_bytes()
    except (OSError, ValueError) as exc:
        raise ValueError("unknown IANA time zone: " + key) from exc


def _timezone_data(key: str) -> _TimezoneData:
    # Keep the existing reviewed Factory resource condition. Other keys use
    # their complete installed data, including their own historical transitions.
    raw = _timezone_resource(key)
    if key == "Factory" and sha256(raw).hexdigest() != _FACTORY_FIXED_ZERO_SHA256:
        raise ValueError("Factory timezone resource differs from the verified fixed-zero TZif")
    return _parse_timezone_data(raw)


def _timezone_resource_hash(key: str) -> str:
    return sha256(_timezone_resource(key)).hexdigest()
