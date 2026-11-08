"""TZif metadata validation and cache identity are independent of native rows."""

import struct
from hashlib import sha256
from importlib.resources import files

import pytest

from equiframe import _timezones as tz


def resource(*, offset=0, transitions=(), indices=None, footer="UTC0", version=b"2"):
    if indices is None:
        indices = bytes(len(transitions))
    counts = (0, 0, 0, len(transitions), 1, 4)
    header = b"TZif" + version + bytes(15) + struct.pack(">6I", *counts)

    def block(width):
        return (
            struct.pack(">" + str(len(transitions)) + ("q" if width == 8 else "l"), *transitions)
            + indices
            + struct.pack(">lBB", offset, 0, 0)
            + b"UTC\0"
        )

    if version == b"\0":
        return header + block(4)
    return header + block(4) + header + block(8) + b"\n" + footer.encode() + b"\n"


def test_tzif_byte_cache_never_reuses_different_resource_semantics():
    zero = tz._parse_timezone_data(resource())
    shifted = tz._parse_timezone_data(resource(offset=3600, footer="CET-1"))
    assert zero.offsets == (0,)
    assert shifted.offsets == (3600,)
    assert zero.resource_sha256 != shifted.resource_sha256
    assert tz._parse_timezone_data(resource()) is zero


@pytest.mark.parametrize("version", (b"\0", b"2", b"3", b"4"))
def test_valid_tzif_version_retains_historical_seconds_and_type_zero(version):
    data = tz._parse_timezone_data(
        resource(offset=-17776, transitions=(-100, 100), version=version)
    )
    assert data.transitions == (-100, 100)
    assert data.interval_offsets == (-17776, -17776, -17776)
    assert -17776 in data.offsets


@pytest.mark.parametrize(
    "raw,reason",
    (
        (b"", "header"),
        (b"TZif2", "header"),
        (resource(version=b"5"), "version"),
        (resource()[:-1], "framing"),
        (resource()[:-6] + b"\nBAD\n", "continuation"),
        (resource(indices=b"\1", transitions=(0,)), "outside table"),
        (resource(transitions=(1, 1)), "Unsorted"),
        (resource(transitions=(2, 1)), "Unsorted"),
        (resource(offset=86401), "offset"),
        (resource(version=b"\0") + b"extra", "trailing"),
        (resource()[:44], "header"),
        (b"TZif2" + bytes(15) + struct.pack(">6I", 0, 0, 1, 0, 1, 4), "Leap-adjusted"),
        (b"TZif2" + bytes(15) + struct.pack(">6I", 0, 0, 0, 0, 0, 4), "type counts"),
    ),
)
def test_invalid_metadata_is_rejected_specifically(raw, reason):
    with pytest.raises(ValueError, match=reason):
        tz._parse_timezone_data(raw)


@pytest.mark.parametrize(
    "rule,kind,values,seconds",
    (
        ("M3.5.0/-1", "M", (3, 5, 0), -3600),
        ("M10.1.0/50", "M", (10, 1, 0), 180000),
        ("J60", "J", (60,), 7200),
        ("365/167:59:59", "N", (365,), 604799),
    ),
)
def test_posix_rule_variants_and_signed_extended_clocks(rule, kind, values, seconds):
    assert tz._tzif_rule(rule) == tz._TimezoneRule(kind, values, seconds)


@pytest.mark.parametrize("rule", ("M13.1.0", "M2.0.0", "J0", "J366", "366", "M3.5.0/168", "1/1/1"))
def test_invalid_posix_rule_is_not_silently_normalized(rule):
    with pytest.raises(ValueError):
        tz._tzif_rule(rule)


def test_negative_dst_and_fractional_offsets_are_metadata_not_assumptions():
    ireland = tz._tzif_continuation("IST-1GMT0,M10.5.0,M3.5.0/1")
    assert ireland.standard == 3600
    assert ireland.daylight == 0
    nepal = tz._tzif_continuation("<+0545>-5:45")
    assert nepal.standard == 20700
    assert nepal.daylight is None


@pytest.mark.parametrize("key", ("../UTC", "/UTC", "America//Bogota", "UTC\\extra", "tzdata.zi"))
def test_resource_loader_rejects_paths_and_non_zone_resources(key):
    with pytest.raises(ValueError, match="unknown IANA"):
        tz._timezone_resource(key)


def test_factory_guard_and_parser_use_the_same_single_resource_capture(monkeypatch):
    original = files("tzdata.zoneinfo").joinpath("Factory").read_bytes()
    assert sha256(original).hexdigest() == tz._FACTORY_FIXED_ZERO_SHA256
    calls = []

    def alternating_resource(key):
        assert key == "Factory"
        calls.append(key)
        return original if len(calls) == 1 else resource(offset=3600, footer="CET-1")

    monkeypatch.setattr(tz, "_timezone_resource", alternating_resource)
    data = tz._timezone_data("Factory")
    assert data.resource_sha256 == sha256(original).hexdigest()
    assert data.offsets == (0,)
    assert calls == ["Factory"]
    with pytest.raises(ValueError, match="verified fixed-zero TZif"):
        tz._timezone_data("Factory")


@pytest.mark.parametrize("standard,universal", ((2, 0), (0, 2), (0, 1)))
def test_tzif_indicators_are_boolean_and_ut_requires_standard(standard, universal):
    header = b"TZif2" + bytes(15) + struct.pack(">6I", 1, 1, 0, 0, 1, 4)
    block = struct.pack(">lBB", 0, 0, 0) + b"UTC\0" + bytes((standard, universal))
    with pytest.raises(ValueError, match="standard/UT indicators"):
        tz._parse_timezone_data(header + block + header + block + b"\nUTC0\n")


def test_tzif_reserved_header_bytes_are_not_ignored():
    raw = bytearray(resource())
    raw[5] = 1
    with pytest.raises(ValueError, match="reserved header"):
        tz._parse_timezone_data(bytes(raw))
