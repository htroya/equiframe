import hashlib
import json
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from conftest import EXAMPLES, PACKAGE, change, document
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator

from equiframe import (
    ContractIOError,
    ContractParseError,
    ContractValidationError,
    DecimalValue,
    canonical_contract_bytes,
    contract_fingerprint,
    contract_json_schema,
    read_contract,
    validate_contract,
    write_contract,
)


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")))
def test_roundtrip_preserves_contract_and_fingerprint(path: Path, tmp_path: Path) -> None:
    before = read_contract(path)
    target = tmp_path / "roundtrip.json"
    write_contract(before, target)
    after = read_contract(target)
    assert before == after
    assert contract_fingerprint(before) == contract_fingerprint(after)
    assert target.read_bytes() == path.read_bytes()


def test_wire_decimal_is_text_and_exact_beyond_binary_float() -> None:
    before = read_contract(EXAMPLES / "aggregations.json")
    data = canonical_contract_bytes(before)
    assert b'"value":"12345678901234567890.123456789012345678"' in data
    assert b'"value":"-0E-18"' in data
    restored = validate_contract(data).output.schema_spec.columns[1].allowed_values
    assert isinstance(restored[0], DecimalValue)
    assert (
        restored[0].value.as_tuple()
        == Decimal("12345678901234567890.123456789012345678").as_tuple()
    )
    assert isinstance(restored[1], DecimalValue) and restored[1].value.is_signed()


def test_fingerprint_has_an_independent_byte_encoding_reference() -> None:
    data = document()
    contract = validate_contract(data)
    # Fixtures include every model default and optional field; compare to stdlib-only encoding.
    expected = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    assert canonical_contract_bytes(contract) == expected
    assert contract_fingerprint(contract) == hashlib.sha256(expected).hexdigest()


def test_hash_changes_for_revision_policy_or_decimal_scale() -> None:
    original = contract_fingerprint(validate_contract(document()))
    alternatives = [
        change(document(), ("revision",), 2),
        change(document(), ("output", "schema_spec", "multiplicity"), "distinct"),
        change(
            document(),
            ("output", "schema_spec", "columns", 5, "allowed_values", 1, "value"),
            "-0.000",
        ),
    ]
    assert all(contract_fingerprint(validate_contract(data)) != original for data in alternatives)


@given(st.permutations(list(document().keys())), st.integers(min_value=0, max_value=8))
@settings(max_examples=35, derandomize=True)
def test_json_member_order_and_whitespace_do_not_change_hash(keys: list[str], indent: int) -> None:
    original = document()
    reordered = {key: original[key] for key in keys}
    transformed = json.dumps(reordered, indent=indent, ensure_ascii=True)
    assert contract_fingerprint(validate_contract(transformed)) == contract_fingerprint(
        validate_contract(original)
    )


@given(st.integers(min_value=-(10**18), max_value=10**18), st.integers(min_value=0, max_value=18))
@settings(max_examples=60, derandomize=True)
def test_decimal_sign_and_exponent_survive_json(coefficient: int, scale: int) -> None:
    text = ("-" if coefficient < 0 else "") + str(abs(coefficient)) + "e-" + str(scale)
    original = DecimalValue(value=Decimal(text))
    with localcontext() as context:
        context.prec = 3  # Serialization must not depend on the process decimal context.
        restored = DecimalValue.model_validate_json(original.model_dump_json())
    assert original.value.as_tuple() == restored.value.as_tuple()


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "[]",
        "null",
        '{"schema_version":"1.0","schema_version":"2.0"}',
        '{"nested":{"x":1,"x":2}}',
        '{"value":NaN}',
        '{"value":Infinity}',
        b"\xff\xfe{}",
    ],
)
def test_ambiguous_nonstandard_or_non_utf8_json_is_rejected(raw: str | bytes) -> None:
    with pytest.raises(ContractParseError) as caught:
        validate_contract(raw)
    issue = caught.value.issues[0]
    if issue.code == "duplicate_json_key":
        assert issue.path in ("$.schema_version", "$.nested.x")
    else:
        assert issue.path == "$"


def test_lone_surrogates_are_rejected_as_values() -> None:
    data = change(
        document(), ("output", "schema_spec", "columns", 1, "allowed_values", 0, "value"), "\ud800"
    )
    with pytest.raises(ContractValidationError):
        validate_contract(json.dumps(data))


def test_unvalidated_model_copy_cannot_bypass_serialization_validation() -> None:
    bad = validate_contract(document()).model_copy(update={"revision": -1})
    with pytest.raises(ContractValidationError):
        canonical_contract_bytes(bad)


def test_io_failures_have_specific_errors(tmp_path: Path) -> None:
    with pytest.raises(ContractIOError):
        read_contract(tmp_path / "missing.json")
    with pytest.raises(ContractIOError):
        write_contract(validate_contract(document()), tmp_path / "missing_dir" / "contract.json")


def test_generated_schema_validates_examples_but_semantic_checks_still_use_api() -> None:
    schema = contract_json_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for path in EXAMPLES.glob("*.json"):
        validator.validate(json.loads(path.read_text("utf-8")))
    data = change(document(), ("output", "schema_spec", "keys", 0, "columns"), ["nonexistent"])
    validator.validate(data)  # JSON Schema cannot resolve cross-table references.
    with pytest.raises(ContractValidationError):
        validate_contract(data)


def test_committed_generated_assets_are_current() -> None:
    subprocess.run([sys.executable, "tools/generate_assets.py", "--check"], cwd=PACKAGE, check=True)


def test_hash_does_not_depend_on_python_hash_seed() -> None:
    import os

    hashes = []
    for seed in ("1", "987654"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from equiframe import read_contract,contract_fingerprint;"
                "print(contract_fingerprint(read_contract('examples/nulls_types.json')))",
            ],
            cwd=PACKAGE,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        hashes.append(result.stdout.strip())
    assert hashes[0] == hashes[1]
