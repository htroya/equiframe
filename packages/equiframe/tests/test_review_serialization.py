import json
import os
import subprocess
import sys
from decimal import localcontext
from importlib.resources import files
from pathlib import Path

import pytest
from conftest import EXAMPLES, PACKAGE, document
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from typer.testing import CliRunner

from equiframe import (
    ContractIOError,
    ContractParseError,
    IntegerValue,
    canonical_contract_bytes,
    contract_fingerprint,
    read_contract,
    validate_contract,
    write_contract,
)
from equiframe.cli import app


@given(st.integers(1, 50), st.integers(0, 1), st.booleans())
@settings(max_examples=30, derandomize=True)
def test_decimal_context_cannot_change_canonical_bytes_or_hash(
    precision: int, capitals: int, clamp: bool
) -> None:
    with localcontext() as _test_decimal_context:
        _test_decimal_context.capitals = 1
        contract = read_contract(EXAMPLES / "aggregations.json")
        expected = canonical_contract_bytes(contract)
        fingerprint = contract_fingerprint(contract)
    with localcontext() as ctx:
        ctx.prec = precision
        ctx.capitals = capitals
        ctx.clamp = int(clamp)
        ctx.Emin = -9
        ctx.Emax = 9
        previous_flags = dict(ctx.flags)
        assert canonical_contract_bytes(contract) == expected
        assert contract_fingerprint(validate_contract(expected)) == fingerprint
        assert ctx.capitals == capitals and ctx.prec == precision
        assert ctx.flags == previous_flags
    assert b'"value":"-0E-18"' in expected


@pytest.mark.parametrize("operation", ["read", "write"])
def test_invalid_filesystem_paths_use_public_io_errors(operation: str) -> None:
    with pytest.raises(ContractIOError):
        if operation == "read":
            read_contract("invalid\x00path.json")
        else:
            write_contract(validate_contract(document()), "invalid\x00path.json")


@pytest.mark.parametrize("key", ["\ud800", "line\nbreak", 'quote"key'])
def test_duplicate_json_keys_have_localized_printable_errors(key: str, tmp_path: Path) -> None:
    encoded = json.dumps(key, ensure_ascii=True)
    raw = '{"nested":[{' + encoded + ":1," + encoded + ":2}]}"
    with pytest.raises(ContractParseError) as caught:
        validate_contract(raw)
    issue = caught.value.issues[0]
    assert issue.code == "duplicate_json_key"
    assert issue.location == ("nested", 0, key)
    assert str(caught.value).encode("utf-8")
    path = tmp_path / "duplicate.json"
    path.write_text(raw, encoding="utf-8")
    result = CliRunner().invoke(app, ["contract", "validate", str(path)])
    assert result.exit_code == 2
    assert "duplicate_json_key" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "data",
    [
        {"value": "private_synthetic_marker"},
        {"value": 1, "extra": "private_synthetic_marker"},
    ],
)
def test_direct_model_errors_do_not_dump_rejected_input(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as caught:
        IntegerValue.model_validate(data)
    assert "private_synthetic_marker" not in str(caught.value)


def test_timezone_validation_uses_locked_database_instead_of_host_tzpath(tmp_path: Path) -> None:
    # Host UTC deliberately lies: it has +09:00. EquiFrame must use package UTC (+00:00).
    (tmp_path / "UTC").write_bytes(files("tzdata.zoneinfo").joinpath("Etc", "GMT-9").read_bytes())
    code = """
from datetime import datetime
from zoneinfo import ZoneInfo
from equiframe import TimestampValue, TimestampPolicy
assert datetime(2000, 1, 1, tzinfo=ZoneInfo('UTC')).utcoffset().total_seconds() == 32400
value = TimestampValue(value='2000-01-01T00:00:00.123456789Z', zone='UTC')
TimestampPolicy(granularity='ns', timezone='UTC', naive='reject', comparison='instant',
                ambiguous='reject', closed='both', lower=value)
assert value.in_zone('UTC', fold=0).utcoffset().total_seconds() == 0
print('locked timezone validation passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PACKAGE,
        env=dict(os.environ, PYTHONTZPATH=str(tmp_path.resolve())),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "locked timezone validation passed"
