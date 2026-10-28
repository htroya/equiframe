import pytest
from conftest import at, change, document
from pydantic import ValidationError

from equiframe import ArtifactRef, ContractValidationError, validate_contract


def numeric_column(
    data: dict[str, object],
    path: tuple[str | int, ...],
    logical_type: dict[str, object],
    unit: str = "synthetic_unit",
) -> None:
    change(data, (*path, "logical_type"), logical_type)
    change(data, (*path, "allowed_values"), [])
    change(data, (*path, "numeric_policy"), {"comparison": "exact", "unit": unit})
    change(
        data,
        (*path, "nan_policy"),
        {"handling": "forbid"} if logical_type["kind"] == "float" else None,
    )


@pytest.mark.parametrize("function", ["sum", "min", "max"])
def test_numeric_aggregations_must_preserve_units(function: str) -> None:
    data = change(document("aggregations"), ("rules", 1, "specification", "function"), function)
    change(data, ("output", "schema_spec", "columns", 1, "numeric_policy", "unit"), "other_unit")
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    assert caught.value.issues[0].code == "aggregate_unit"
    assert caught.value.issues[0].path == "$.rules[1].specification.output_column"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ({"kind": "decimal", "precision": 38, "scale": 18}, {"kind": "float", "bits": 64}),
        ({"kind": "integer", "bits": 64, "signed": True}, {"kind": "float", "bits": 64}),
        ({"kind": "float", "bits": 64}, {"kind": "integer", "bits": 64, "signed": True}),
        (
            {"kind": "integer", "bits": 64, "signed": True},
            {"kind": "integer", "bits": 32, "signed": True},
        ),
        (
            {"kind": "integer", "bits": 64, "signed": True},
            {"kind": "integer", "bits": 64, "signed": False},
        ),
        (
            {"kind": "integer", "bits": 64, "signed": False},
            {"kind": "integer", "bits": 64, "signed": True},
        ),
        (
            {"kind": "decimal", "precision": 38, "scale": 18},
            {"kind": "decimal", "precision": 38, "scale": 17},
        ),
        (
            {"kind": "decimal", "precision": 38, "scale": 18},
            {"kind": "decimal", "precision": 38, "scale": 19},
        ),
        ({"kind": "float", "bits": 64}, {"kind": "float", "bits": 32}),
    ],
)
def test_sum_rejects_implicit_conversion_or_narrowing(
    source: dict[str, object], target: dict[str, object]
) -> None:
    data = document("aggregations")
    numeric_column(data, ("inputs", 0, "schema_spec", "columns", 1), source)
    numeric_column(data, ("output", "schema_spec", "columns", 1), target)
    with pytest.raises(ContractValidationError, match="aggregate_type"):
        validate_contract(data)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (
            {"kind": "integer", "bits": 32, "signed": True},
            {"kind": "integer", "bits": 64, "signed": True},
        ),
        (
            {"kind": "integer", "bits": 32, "signed": False},
            {"kind": "integer", "bits": 64, "signed": True},
        ),
        (
            {"kind": "decimal", "precision": 20, "scale": 4},
            {"kind": "decimal", "precision": 38, "scale": 18},
        ),
        ({"kind": "float", "bits": 32}, {"kind": "float", "bits": 64}),
    ],
)
def test_sum_allows_explicit_wider_types_without_changing_family_or_unit(
    source: dict[str, object], target: dict[str, object]
) -> None:
    data = document("aggregations")
    numeric_column(data, ("inputs", 0, "schema_spec", "columns", 1), source)
    numeric_column(data, ("output", "schema_spec", "columns", 1), target)
    assert validate_contract(data).rules[1].specification.kind == "aggregate"


def test_numeric_join_columns_require_matching_units() -> None:
    data = document("joins")
    kind = {"kind": "integer", "bits": 64, "signed": True}
    numeric_column(data, ("inputs", 0, "schema_spec", "columns", 1), kind, "unit_a")
    numeric_column(data, ("inputs", 1, "schema_spec", "columns", 0), kind, "unit_b")
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    assert caught.value.issues[0].code == "join_unit"
    assert caught.value.issues[0].path == "$.rules[1].specification.right_columns[0]"


def test_numeric_grouping_must_preserve_units() -> None:
    data = document("aggregations")
    kind = {"kind": "integer", "bits": 64, "signed": True}
    numeric_column(data, ("inputs", 0, "schema_spec", "columns", 0), kind, "unit_a")
    numeric_column(data, ("output", "schema_spec", "columns", 0), kind, "unit_b")
    with pytest.raises(ContractValidationError, match="aggregate_group_unit"):
        validate_contract(data)


@pytest.mark.parametrize(
    "order",
    [
        {"kind": "ignored"},
        {
            "kind": "significant",
            "by": [{"column": "id", "direction": "descending", "nulls": "first"}],
            "ties": "preserve",
        },
    ],
)
def test_order_check_requires_matching_declared_order_policy(order: dict[str, object]) -> None:
    data = change(document("duplicates_order"), ("output", "schema_spec", "order"), order)
    with pytest.raises(ContractValidationError, match="order_policy"):
        validate_contract(data)


@pytest.mark.parametrize("value", [0.1, 1e-50])
def test_exact_float32_literals_cannot_require_rounding_or_underflow(value: float) -> None:
    data = document()
    path = ("output", "schema_spec", "columns", 2)
    numeric_column(data, path, {"kind": "float", "bits": 32})
    change(data, (*path, "allowed_values"), [{"kind": "float", "value": value}])
    with pytest.raises(ContractValidationError, match="float_precision"):
        validate_contract(data)


@pytest.mark.parametrize("value", [-0.0, 0.5, 2**24])
def test_exact_float32_accepts_representable_literals(value: float) -> None:
    data = document()
    path = ("output", "schema_spec", "columns", 2)
    numeric_column(data, path, {"kind": "float", "bits": 32})
    change(data, (*path, "allowed_values"), [{"kind": "float", "value": value}])
    assert validate_contract(data).output.schema_spec.columns[2].allowed_values[0].kind == "float"


def test_temporal_literal_errors_preserve_the_actual_code_and_location() -> None:
    data = document("dates")
    path = ("output", "schema_spec", "columns", 2)
    change(data, (*path, "allowed_values"), [{"kind": "timestamp", "value": "2000-02-29T12:00:00"}])
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    assert caught.value.issues[0].code == "naive_timestamp"
    assert caught.value.issues[0].path == "$.output.schema_spec.columns[2].allowed_values[0].value"


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.invalid:notaport/x",
        "https://example.invalid:99999/x",
        "https://example.invalid:-1/x",
        "https://example.invalid\\wrong/x",
        "https://example.invalid/x%zz",
        "https://example.invalid/x%0",
        "https://example.invalid/x%",
        "s3://bucket:443/object",
        "gs://bucket:443/object",
        "file://host:443/absolute.json",
    ],
)
def test_artifact_uri_syntax_rejects_invalid_ports_and_escapes(uri: str) -> None:
    with pytest.raises(ValidationError, match="artifact_uri"):
        ArtifactRef(
            schema_version="1.0",
            uri=uri,
            sha256="a" * 64,
            format="json",
            media_type="application/json",
            size_bytes=0,
        )


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.invalid:8443/x",
        "https://[::1]:443/x",
        "file:///C:/some%20folder/x.json",
        "s3://synthetic-bucket/x",
        "gs://synthetic-bucket/x",
    ],
)
def test_artifact_uri_accepts_valid_ports_ipv6_and_encoded_paths(uri: str) -> None:
    ref = ArtifactRef(
        schema_version="1.0",
        uri=uri,
        sha256="a" * 64,
        format="json",
        media_type="application/json",
        size_bytes=0,
    )
    assert ref.uri == uri


def test_preconditions_receive_the_same_cross_validation_as_rules() -> None:
    data = document("aggregations")
    specification = at(data, "rules", 1, "specification")
    change(data, ("preconditions", 0, "requirement"), specification)
    change(data, ("output", "schema_spec", "columns", 1, "numeric_policy", "unit"), "other_unit")
    with pytest.raises(ContractValidationError) as caught:
        validate_contract(data)
    assert caught.value.issues[0].code == "aggregate_unit"
    assert caught.value.issues[0].path == "$.preconditions[0].requirement.output_column"
