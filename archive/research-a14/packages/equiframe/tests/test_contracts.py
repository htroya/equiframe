from decimal import Decimal

import pytest
from conftest import EXAMPLES, at, change, document
from pydantic import ValidationError

from equiframe import (
    ArtifactRef,
    ColumnKeyScope,
    ContractValidationError,
    DecimalValue,
    FloatValue,
    KeySpec,
    SchemaVersionError,
    TableKeyScope,
    read_contract,
    validate_contract,
)


@pytest.mark.parametrize(
    "family", ["nulls_types", "joins", "duplicates_order", "aggregations", "dates"]
)
def test_synthetic_contracts_have_checked_references_and_distinct_tables(family: str) -> None:
    contract = read_contract(EXAMPLES / (family + ".json"))
    assert contract.family == family
    assert contract.contract_id == "synthetic." + family
    tables = {
        table.name: {column.name for column in table.schema_spec.columns}
        for table in (*contract.inputs, contract.output)
    }
    assert len(tables) == len(contract.inputs) + 1
    assert contract.rules[1].applicability == ("input_schema",)


@pytest.mark.parametrize(
    ("path", "value", "code"),
    [
        (("revision",), True, "int_type"),
        (("revision",), "1", "int_type"),
        (("revision",), 0, "greater_than"),
        (("family",), "unknown", "literal_error"),
        (("output", "schema_spec", "columns", 0, "nullable"), "false", "bool_type"),
        (("output", "schema_spec", "columns", 0, "name"), " ", "value_error"),
        (("output", "schema_spec", "columns", 0, "extra"), "ignored?", "extra_forbidden"),
        (("output", "schema_spec", "keys", 0, "columns"), ["missing"], "unknown_column"),
        (("output", "schema_spec", "keys", 0, "columns"), ["id", "id"], "duplicate_reference"),
        (
            ("output", "schema_spec", "keys", 0, "scope"),
            {"kind": "columns", "columns": ["missing"]},
            "unknown_column",
        ),
        (
            ("output", "schema_spec", "keys", 0, "scope"),
            {"kind": "columns", "columns": ["id"]},
            "key_scope_overlap",
        ),
        (("output", "schema_spec", "columns", 5, "logical_type", "scale"), 39, "decimal_scale"),
        (
            ("output", "schema_spec", "columns", 5, "logical_type", "precision"),
            0,
            "greater_than_equal",
        ),
        (
            ("output", "schema_spec", "columns", 5, "logical_type", "precision"),
            77,
            "less_than_equal",
        ),
        (
            ("output", "schema_spec", "columns", 5, "numeric_policy", "comparison"),
            "approximate",
            "missing_tolerance",
        ),
        (
            ("output", "schema_spec", "columns", 5, "numeric_policy", "rounding"),
            "ROUND_HALF_EVEN",
            "rounding_justification",
        ),
        (
            ("output", "schema_spec", "columns", 5, "nan_policy"),
            {"handling": "distinct"},
            "nan_type",
        ),
        (("output", "schema_spec", "columns", 2, "nan_policy"), None, "missing_nan_policy"),
        (
            ("output", "schema_spec", "columns", 2, "numeric_policy", "tolerance", "absolute"),
            0.001,
            "value_error",
        ),
        (
            ("output", "schema_spec", "columns", 2, "numeric_policy", "tolerance", "absolute"),
            "-0.01",
            "negative_tolerance",
        ),
        (
            ("output", "schema_spec", "columns", 2, "numeric_policy", "tolerance", "unit"),
            "other",
            "tolerance_unit",
        ),
        (
            ("output", "schema_spec", "columns", 2, "numeric_policy", "tolerance", "justification"),
            "",
            "string_too_short",
        ),
        (
            ("output", "schema_spec", "columns", 2, "numeric_policy", "tolerance"),
            {"unit": "synthetic_sensor", "justification": "test"},
            "empty_tolerance",
        ),
        (
            ("output", "schema_spec", "columns", 2, "numeric_policy", "rounding"),
            "ROUND_UP",
            "rounding_justification",
        ),
        (
            ("output", "schema_spec", "columns", 2, "nan_policy"),
            {"handling": "as_null"},
            "nan_justification",
        ),
        (
            ("output", "schema_spec", "columns", 0, "null_policy"),
            {"representations": ["null", "zero"], "justification": "test"},
            "nonnullable_equivalence",
        ),
        (
            ("output", "schema_spec", "columns", 1, "null_policy"),
            {"representations": ["null", "empty_string"]},
            "null_justification",
        ),
        (
            ("output", "schema_spec", "columns", 2, "null_policy"),
            {"representations": ["null", "empty_string"], "justification": "test"},
            "null_type",
        ),
        (
            ("output", "schema_spec", "columns", 1, "null_policy"),
            {"representations": ["null", "zero"], "justification": "test"},
            "null_type",
        ),
        (
            ("output", "schema_spec", "columns", 1, "null_policy"),
            {"representations": ["empty_string"]},
            "missing_null",
        ),
        (("rules", 0, "specification", "table"), "missing", "unknown_table"),
        (("rules", 1, "specification", "key"), "missing", "unknown_key"),
        (("rules", 1, "applicability"), ["missing"], "unknown_precondition"),
        (("rules", 0, "specification", "kind"), "python_expression", "union_tag_invalid"),
        (("rules", 0, "specification", "sql"), "DROP TABLE source", "extra_forbidden"),
        (("output", "name"), "source", "duplicate_table"),
    ],
)
def test_invalid_contracts_fail_with_specific_localized_errors(
    path: tuple[str | int, ...],
    value: object,
    code: str,
) -> None:
    data = change(document(), path, value)
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    issues = caught.value.issues
    assert any(issue.code == code for issue in issues), str(caught.value)
    assert all(issue.path.startswith("$.") for issue in issues)


def test_top_level_unknown_fields_are_rejected(valid_document: dict[str, object]) -> None:
    valid_document["callback"] = "__import__('os').system('echo BAD')"
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(valid_document)
    assert caught.value.issues[0].path == "$.callback"
    assert caught.value.issues[0].code == "extra_forbidden"


def test_unsupported_versions_have_a_dedicated_error() -> None:
    with pytest.raises(SchemaVersionError) as caught:
        validate_contract(change(document(), ("schema_version",), "2.0"))
    assert caught.value.issues[0].path == "$.schema_version"
    data = document()
    del data["schema_version"]
    with pytest.raises(ContractValidationError) as missing:
        validate_contract(data)
    assert missing.value.issues[0].code == "missing"


def test_duplicate_names_are_localized_to_the_second_column() -> None:
    data = document()
    change(data, ("output", "schema_spec", "columns", 1, "name"), "id")
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    assert caught.value.issues[0].path == "$.output.schema_spec.columns[1].name"
    assert caught.value.issues[0].code == "duplicate_column"


@pytest.mark.parametrize(
    ("family", "path", "value", "code"),
    [
        (
            "joins",
            ("rules", 1, "specification", "right_columns"),
            ["supplier_id", "name"],
            "join_arity",
        ),
        ("joins", ("rules", 1, "specification", "right_columns"), ["missing"], "unknown_column"),
        (
            "joins",
            ("inputs", 1, "schema_spec", "columns", 0, "logical_type"),
            {"kind": "boolean"},
            "join_type",
        ),
        (
            "duplicates_order",
            ("output", "schema_spec", "order", "by", 0, "column"),
            "missing",
            "unknown_column",
        ),
        (
            "duplicates_order",
            ("rules", 1, "specification", "columns"),
            ["missing"],
            "unknown_column",
        ),
        ("aggregations", ("rules", 1, "specification", "measure"), "missing", "unknown_column"),
        ("aggregations", ("rules", 1, "specification", "measure"), "currency", "aggregate_type"),
        ("aggregations", ("rules", 1, "specification", "group_by"), ["missing"], "unknown_column"),
        ("aggregations", ("rules", 1, "specification", "function"), "count", "aggregate_type"),
        ("dates", ("rules", 1, "specification", "maximum"), -1, "greater_than_equal"),
    ],
)
def test_declarative_rule_cross_references(
    family: str,
    path: tuple[str | int, ...],
    value: object,
    code: str,
) -> None:
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(change(document(family), path, value))
    assert any(issue.code == code for issue in caught.value.issues), str(caught.value)


def test_configuration_is_recursively_immutable() -> None:
    contract = validate_contract(document())
    with pytest.raises(ValidationError, match="frozen"):
        contract.revision = 2
    with pytest.raises(ValidationError, match="frozen"):
        contract.output.schema_spec.columns[0].nullable = True
    assert isinstance(contract.inputs, tuple)
    assert isinstance(contract.output.schema_spec.columns, tuple)
    assert isinstance(contract.output.schema_spec.columns[0].allowed_values, tuple)


def test_null_nan_empty_and_zero_remain_independent() -> None:
    contract = validate_contract(document())
    text = contract.output.schema_spec.columns[1]
    signal = contract.output.schema_spec.columns[2]
    assert text.null_policy.representations == ("null",)
    assert [(value.kind, getattr(value, "value", None)) for value in text.allowed_values] == [
        ("string", ""),
        ("string", "0"),
        ("null", None),
    ]
    assert [value.kind for value in signal.allowed_values] == ["float", "nan", "null"]
    assert signal.nan_policy is not None and signal.nan_policy.handling == "distinct"


def test_explicit_justified_absence_equivalence_is_allowed() -> None:
    data = change(
        document(),
        ("output", "schema_spec", "columns", 1, "null_policy"),
        {
            "representations": ["null", "empty_string"],
            "justification": "Synthetic explicit equivalence",
        },
    )
    assert validate_contract(data).output.schema_spec.columns[1].null_policy.representations == (
        "null",
        "empty_string",
    )


@pytest.mark.parametrize("value", [1, 0.1, True, "NaN", "Infinity", " 1.0 "])
def test_decimals_never_coerce_numbers_or_nonfinite_text(value: object) -> None:
    with pytest.raises(ValidationError):
        DecimalValue.model_validate({"value": value})


def test_decimal_precision_and_scale_are_checked_without_float_conversion() -> None:
    data = document()
    path = ("output", "schema_spec", "columns", 5, "allowed_values", 0, "value")
    with pytest.raises(ContractValidationError, match="decimal_literal_precision"):
        validate_contract(change(data, path, "123456789012345678901.000000000000000000"))
    with pytest.raises(ContractValidationError, match="decimal_literal_scale"):
        validate_contract(change(data, path, "0.0000000000000000001"))
    exact = DecimalValue(value=Decimal("-0.000000000000000000"))
    assert exact.value.as_tuple().sign == 1
    assert exact.value.as_tuple().exponent == -18


def test_integer_width_and_lossy_float_coercion_are_rejected() -> None:
    data = change(document(), ("output", "schema_spec", "columns", 4, "logical_type", "bits"), 8)
    change(data, ("output", "schema_spec", "columns", 4, "allowed_values", 0, "value"), 128)
    with pytest.raises(ContractValidationError, match="integer_range"):
        validate_contract(data)
    with pytest.raises(ValidationError, match="without loss"):
        FloatValue.model_validate({"value": 2**53 + 1})


@pytest.mark.parametrize(
    "uri",
    [
        "https://user:password@example.invalid/x",
        "https://example.invalid/x?token=hidden",
        "https://example.invalid/x#secret",
        "http://example.invalid/x",
        "relative/file.json",
        "file:relative.json",
        "https://example.invalid/a b",
        "https:///missing-host",
    ],
)
def test_artifact_references_reject_secret_bearing_or_invalid_uris(uri: str) -> None:
    with pytest.raises(ValidationError):
        ArtifactRef(
            schema_version="1.0",
            uri=uri,
            sha256="a" * 64,
            format="json",
            media_type="application/json",
            size_bytes=0,
        )


def test_artifact_metadata_roundtrip_and_schema_version() -> None:
    ref = ArtifactRef(
        schema_version="1.0",
        uri="file:///C:/synthetic/contract.json",
        sha256="a" * 64,
        format="json",
        media_type="application/json",
        size_bytes=42,
    )
    assert ArtifactRef.model_validate_json(ref.model_dump_json()) == ref
    with pytest.raises(ValidationError):
        ArtifactRef.model_validate_json(ref.model_dump_json().replace('"1.0"', '"2.0"'))


def test_key_scope_can_reference_a_separate_existing_column() -> None:
    data = change(
        document(),
        ("output", "schema_spec", "keys", 0, "scope"),
        {"kind": "columns", "columns": ["count"]},
    )
    result = validate_contract(data).output.schema_spec.keys[0]
    assert isinstance(result.scope, ColumnKeyScope)
    assert result.scope.columns == ("count",)
    assert (
        KeySpec(
            name="key", columns=("id",), unique=True, incomplete="allow", scope=TableKeyScope()
        ).incomplete
        == "allow"
    )


def test_no_sql_or_python_is_executed(tmp_path) -> None:
    marker = tmp_path / "must_not_exist.txt"
    data = document()
    data["python"] = f"open({str(marker)!r}, 'w').write('bad')"
    with pytest.raises(ContractValidationError):
        validate_contract(data)
    assert not marker.exists()
    assert at(data, "python") is not None
