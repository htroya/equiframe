"""Behavioral regressions for the declared Python 3.10-3.13 contract."""

from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe import _path_compat
from equiframe.comparison import ComparisonInput
from equiframe.normalization import literal
from equiframe.values import _timestamp_datetime


@pytest.mark.parametrize("digits", range(1, 10))
def test_fractional_timestamp_preserves_exact_nanoseconds_and_original_text(digits):
    fraction = "123456789"[:digits]
    text = "2024-02-29T23:59:59." + fraction + "Z"
    value = ef.TimestampValue(value=text, zone="UTC")
    expected = (date(2024, 2, 29).toordinal() * 86400 + 86399) * 10**9
    expected += int(fraction.ljust(9, "0"))
    assert value.nanoseconds(instant=True) == expected
    assert value.value == text
    assert ef.TimestampValue.model_validate_json(value.model_dump_json()) == value
    assert _timestamp_datetime(text).microsecond == int(fraction[:6].ljust(6, "0"))


@pytest.mark.parametrize(
    "text", ["2023-02-29T00:00:00Z", "2024-01-01T24:00:00Z", "2024-01-01T00:00:00-00:00"]
)
def test_timestamp_compatibility_does_not_relax_invalid_literal_admission(text):
    with pytest.raises(ValidationError):
        ef.TimestampValue(value=text)


def test_decimal_capitals_are_local_and_do_not_round_or_change_consumer_context():
    with localcontext() as context:
        context.capitals = 0
        context.prec = 2
        before = context.copy()
        value = ef.DecimalValue(value=Decimal("123456789E+30"))
        assert value.model_dump(mode="json")["value"] == "1.23456789E+38"
        assert literal(value).value == "1.23456789E+38"
        assert context.capitals == before.capitals and context.prec == before.prec
        assert context.flags == before.flags and context.traps == before.traps


def test_named_input_alias_keeps_introspection_without_loading_optional_engines():
    assert ComparisonInput.__name__ == "ComparisonInput"
    assert set(get_args(ComparisonInput.__value__)) == {
        ef.ArrowInput,
        ef.ArtifactRef,
        ef.TableArtifact,
        ef.ExecutionResult,
        Path,
    }


@pytest.mark.parametrize("tag, expected", [(0xA0000003, True), (0xA000000C, False), (0, False)])
def test_legacy_windows_junction_branch_inspects_real_reparse_tag_contract(
    monkeypatch, tag, expected
):
    # This branch unit test is deliberately not reported as an actual Windows run.
    monkeypatch.setattr(_path_compat, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        _path_compat, "stat", SimpleNamespace(IO_REPARSE_TAG_MOUNT_POINT=0xA0000003)
    )
    path = Mock(spec=Path)
    path.lstat.return_value = SimpleNamespace(st_reparse_tag=tag)
    assert _path_compat.is_junction(path) is expected
    path.lstat.assert_called_once_with()


def test_junction_io_failure_is_not_silently_false(monkeypatch):
    monkeypatch.setattr(_path_compat, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        _path_compat, "stat", SimpleNamespace(IO_REPARSE_TAG_MOUNT_POINT=0xA0000003)
    )
    path = Mock(spec=Path)
    path.lstat.side_effect = PermissionError("synthetic inaccessible path")
    with pytest.raises(PermissionError):
        _path_compat.is_junction(path)
