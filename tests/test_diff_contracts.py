"""Public builder regressions with independent policy and provenance expectations."""

import json
from decimal import Decimal

import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef

OUTPUT = "/spec/contract/output/schema_spec"
INPUT = "/spec/contract/inputs/0/schema_spec"


def integer(name="id", *, nullable=True):
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )


def leaf_paths(value, path):
    """Independent JSON leaf enumeration, including null and empty containers."""
    if isinstance(value, dict) and value:
        result = set()
        for key, item in value.items():
            result |= leaf_paths(item, path + "/" + key.replace("~", "~0").replace("/", "~1"))
        return result
    if isinstance(value, list) and value:
        result = set()
        for index, item in enumerate(value):
            result |= leaf_paths(item, path + "/" + str(index))
        return result
    return {path}


@pytest.mark.parametrize("mode", ["bag", "key", "sequence", "inference", "existing"])
def test_all_policy_leaves_have_exactly_one_frozen_roundtrippable_explanation(mode):
    columns = [integer(), integer("a~/b")]
    if mode == "bag":
        contract = ef.bag_contract(columns)
    elif mode == "key":
        contract = ef.keyed_contract(columns, keys=["id"])
    elif mode == "sequence":
        contract = ef.sequence_contract(
            columns, by=[ef.SortSpec(column="id", direction="ascending", nulls="last")]
        )
    elif mode == "inference":
        contract = ef.infer_diff_contract(pa.schema([("id", pa.int64()), ("a~/b", pa.int64())]))
    else:
        contract = ef.DiffContract.from_contract(ef.bag_contract(columns).spec.contract)
    doc = json.loads(contract.model_dump_json())
    paths = [item.path for item in contract.provenance]
    assert set(paths) == leaf_paths(doc["spec"], "/spec") | {"/reference"}
    assert len(paths) == len(set(paths))
    assert "/spec/contract/rules" in paths
    assert OUTPUT + "/columns/0/allowed_values" in paths
    assert OUTPUT + "/columns/0/temporal_policy" in paths
    assert ef.DiffContract.model_validate_json(contract.model_dump_json()) == contract
    assert ef.DiffContract.model_validate(contract) == contract
    assert ef.ComparisonSpec.model_validate_json(contract.spec.model_dump_json()) == contract.spec
    with pytest.raises(ValidationError, match="frozen"):
        contract.reference = "peer"
    with pytest.raises(ValidationError, match="frozen"):
        contract.provenance[0].detail = "changed"
    with pytest.raises(KeyError):
        contract.provenance_for("/absent")


@pytest.mark.parametrize(
    "change, code",
    [
        ("missing", "missing_provenance"),
        ("duplicate", "duplicate_provenance"),
        ("unknown", "unknown_provenance"),
        ("parent", "unknown_provenance"),
        ("leading_index", "unknown_provenance"),
    ],
)
def test_provenance_tampering_is_rejected(change, code):
    doc = json.loads(ef.bag_contract([integer()]).model_dump_json())
    if change == "missing":
        doc["provenance"].pop()
    elif change == "duplicate":
        doc["provenance"].append(doc["provenance"][0])
    else:
        doc["provenance"][0]["path"] = {
            "unknown": "/spec/unknown",
            "parent": "/spec/contract",
            "leading_index": OUTPUT + "/columns/00/name",
        }[change]
    with pytest.raises(ValidationError, match=code):
        ef.DiffContract.model_validate_json(json.dumps(doc))


@pytest.mark.parametrize(
    "path", ["", "spec/contract", "#/spec", "/~", "/~2", "/bad~escape", " /spec"]
)
def test_provenance_requires_canonical_absolute_json_pointer(path):
    with pytest.raises(ValidationError):
        ef.PolicyProvenance(path=path, origin="user", detail="Chosen")
    valid = ef.PolicyProvenance(path="/a~0b/c~1d", origin="user", detail="Chosen")
    assert valid.path == "/a~0b/c~1d"


def test_direct_construction_revalidates_forged_frozen_instances():
    contract = ef.bag_contract([integer()])
    forged = contract.model_copy(update={"provenance": ()})
    with pytest.raises(ValidationError, match="missing_provenance"):
        ef.DiffContract.model_validate(forged)
    forged_policy = ef.ComparisonPolicy().model_copy(update={"index": "ignore"})
    with pytest.raises(ValidationError, match="comparison_authorization"):
        ef.bag_contract([integer()], policy=forged_policy)


def test_explicit_default_valued_selections_are_not_reported_as_inferred_defaults():
    implicit = ef.bag_contract([integer()])
    explicit = ef.bag_contract(
        [integer()],
        policy=ef.ComparisonPolicy(),
        multiplicity="preserve",
        reference="expected",
        contract_id="diff",
        revision=1,
    )
    assert implicit.spec == explicit.spec
    for path in (
        "/reference",
        OUTPUT + "/multiplicity",
        "/spec/contract/contract_id",
        "/spec/contract/revision",
        "/spec/policy/index",
    ):
        assert implicit.provenance_for(path).origin == "default"
        assert explicit.provenance_for(path).origin == "user"
    for prefix in (OUTPUT + "/columns", INPUT + "/columns"):
        assert all(
            item.origin == "user"
            for item in implicit.provenance
            if item.path.startswith(prefix + "/")
        )
    assert implicit.provenance_for("/spec/contract/family").origin == "default"
    assert implicit.spec.contract.inputs[0].name == "source"
    assert implicit.spec.contract.output.name == "result"
    assert implicit.spec.contract.inputs[0].schema_spec == implicit.spec.contract.output.schema_spec
    assert implicit.spec.contract.preconditions == implicit.spec.contract.rules == ()


def test_existing_contract_preserves_exact_contract_and_explicit_policy():
    base = ef.keyed_contract(
        [integer()], keys=["id"], incomplete="allow", contract_id="original", revision=3
    )
    policy = ef.ComparisonPolicy(index="ignore", justification="Index has no domain meaning")
    wrapped = ef.DiffContract.from_contract(base.spec.contract, policy=policy, reference="peer")
    assert wrapped.spec.contract == base.spec.contract
    assert wrapped.spec.policy == policy
    assert wrapped.reference == "peer"
    assert all(
        item.origin == "user"
        for item in wrapped.provenance
        if item.path.startswith("/spec/contract/")
    )
    assert wrapped.provenance_for("/spec/policy/index").origin == "user"
    assert wrapped.provenance_for("/reference").origin == "user"
    assert (
        ef.DiffContract.from_contract(base.spec.contract).provenance_for("/reference").origin
        == "default"
    )


@pytest.mark.parametrize(
    "keys,code",
    [([], "too_short"), (["id", "id"], "duplicate_reference"), (["missing"], "unknown_column")],
)
def test_key_builder_reuses_existing_validation(keys, code):
    with pytest.raises(ValidationError, match=code):
        ef.keyed_contract([integer()], keys=keys)
    with pytest.raises(ValidationError, match=code):
        ef.infer_diff_contract(pa.schema([("id", pa.int64())]), keys=keys)


def test_key_string_is_not_silently_split_into_column_names():
    with pytest.raises(ef.InvalidExecutionInput, match="not a string"):
        ef.keyed_contract([integer("i"), integer("d")], keys="id")


def test_key_and_sequence_policies_preserve_caller_values_and_sources():
    contract = ef.keyed_contract([integer()], keys=["id"], incomplete="allow")
    key = contract.spec.contract.output.schema_spec.keys[0]
    assert key.columns == ("id",)
    assert key.unique is True
    assert key.incomplete == "allow"
    assert key.scope == ef.TableKeyScope()
    assert contract.provenance_for(OUTPUT + "/keys/0/incomplete").origin == "user"
    default = ef.keyed_contract([integer()], keys=["id"])
    assert default.provenance_for(OUTPUT + "/keys/0/incomplete").origin == "default"
    order = [ef.SortSpec(column="id", direction="descending", nulls="first")]
    sequence = ef.sequence_contract([integer()], by=order, ties="preserve", multiplicity="distinct")
    assert sequence.spec.contract.output.schema_spec.order == ef.SignificantOrder(
        by=tuple(order), ties="preserve"
    )
    assert sequence.spec.contract.output.schema_spec.multiplicity == "distinct"
    assert sequence.provenance_for(OUTPUT + "/order/ties").origin == "user"
    assert (
        ef.sequence_contract([integer()], by=order).provenance_for(OUTPUT + "/order/ties").origin
        == "default"
    )
    with pytest.raises(ValidationError, match="unknown_column"):
        ef.sequence_contract(
            [integer()], by=[ef.SortSpec(column="absent", direction="ascending", nulls="first")]
        )
    with pytest.raises(ValidationError, match="too_short"):
        ef.sequence_contract([integer()], by=[])


@pytest.mark.parametrize(
    "dtype",
    [
        pa.int8(),
        pa.int16(),
        pa.int32(),
        pa.int64(),
        pa.uint8(),
        pa.uint16(),
        pa.uint32(),
        pa.uint64(),
    ],
)
def test_integer_inference_preserves_width_signedness_and_nullable_domain(dtype):
    contract = ef.infer_diff_contract(pa.schema([pa.field("id", dtype, nullable=False)]))
    column = contract.spec.contract.output.schema_spec.columns[0]
    assert column.logical_type == ef.IntegerType(
        bits=dtype.bit_width, signed=pa.types.is_signed_integer(dtype)
    )
    assert column.nullable is True
    assert column.numeric_policy == ef.NumericPolicy(comparison="exact", unit="unspecified")
    assert column.null_policy == ef.NullPolicy(representations=("null",))
    assert contract.provenance_for(OUTPUT + "/columns/0/logical_type/bits").origin == "metadata"
    assert contract.provenance_for(OUTPUT + "/columns/0/nullable").origin == "default"
    assert contract.provenance_for(OUTPUT + "/columns/0/numeric_policy/unit").origin == "default"
    assert contract.provenance_for(OUTPUT + "/order/kind").origin == "default"
    assert contract.provenance_for("/reference").origin == "default"
    assert contract.spec.contract.output.schema_spec.keys == ()


@pytest.mark.parametrize("dtype", [pa.float32(), pa.float64()])
def test_float_inference_is_exact_and_nan_remains_distinct(dtype):
    column = ef.infer_diff_contract(
        pa.schema([("x", dtype)])
    ).spec.contract.output.schema_spec.columns[0]
    assert column.logical_type == ef.FloatType(bits=dtype.bit_width)
    assert column.nan_policy == ef.NaNPolicy(handling="distinct")
    assert column.numeric_policy.comparison == "exact"
    assert column.numeric_policy.tolerance is None
    assert column.null_policy.representations == ("null",)


@pytest.mark.parametrize(
    "dtype,logical",
    [
        (pa.bool_(), ef.BooleanType()),
        (pa.string(), ef.StringType()),
        (pa.large_string(), ef.StringType()),
        (pa.string_view(), ef.StringType()),
        (pa.date32(), ef.DateType()),
        (pa.date64(), ef.DateType()),
        (pa.decimal128(19, 7), ef.DecimalType(precision=19, scale=7)),
        (pa.decimal256(76, 38), ef.DecimalType(precision=76, scale=38)),
    ],
)
def test_supported_schema_only_inference_retains_types(dtype, logical):
    column = ef.infer_diff_contract(
        pa.schema([("x", dtype)])
    ).spec.contract.output.schema_spec.columns[0]
    assert column.logical_type == logical
    if isinstance(logical, ef.DateType):
        assert column.temporal_policy == ef.DatePolicy(closed="both")


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "UTC", "America/Guayaquil"])
def test_timestamp_inference_preserves_metadata_without_guessing(unit, zone):
    result = ef.infer_diff_contract(pa.schema([("ts", pa.timestamp(unit, zone))]))
    column = result.spec.contract.output.schema_spec.columns[0]
    assert column.logical_type == ef.TimestampType(unit=unit, timezone=zone)
    policy = column.temporal_policy
    assert policy.timezone == zone
    assert policy.granularity == unit
    assert policy.naive == ("preserve" if zone is None else "reject")
    assert policy.comparison == ("wall_time" if zone is None else "instant")
    assert policy.ambiguous == policy.nonexistent == "reject"
    assert (
        result.provenance_for(OUTPUT + "/columns/0/temporal_policy/timezone").origin == "metadata"
    )
    assert result.provenance_for(OUTPUT + "/columns/0/temporal_policy/naive").origin == "default"


@pytest.mark.parametrize(
    "dtype",
    [
        pa.null(),
        pa.binary(),
        pa.list_(pa.int64()),
        pa.struct([("x", pa.string())]),
        pa.dictionary(pa.int8(), pa.string()),
        pa.float16(),
        pa.duration("ns"),
        pa.decimal128(10, -2),
        pa.decimal128(10, 12),
        pa.timestamp("us", "+03:00"),
    ],
)
def test_ambiguous_or_unsupported_reference_types_fail_without_casts(dtype):
    with pytest.raises(ef.CapabilityError):
        ef.infer_diff_contract(pa.schema([("x", dtype)]))


def test_null_only_override_is_explicit_without_relabeling_it_as_metadata():
    explicit = integer("x", nullable=False)
    result = ef.infer_diff_contract(pa.schema([("x", pa.null())]), column_overrides=[explicit])
    assert result.spec.contract.output.schema_spec.columns == (explicit,)
    assert all(
        item.origin == "user"
        for item in result.provenance
        if item.path.startswith(OUTPUT + "/columns/0/")
    )
    with pytest.raises(ef.CapabilityError):
        ef.infer_diff_contract(
            pa.schema([("x", pa.list_(pa.int64()))]), column_overrides=[explicit]
        )


def test_explicit_tolerance_and_units_are_retained_without_row_inference():
    column = ef.ColumnSpec(
        name="x",
        logical_type=ef.FloatType(bits=64),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        nan_policy=ef.NaNPolicy(handling="distinct"),
        numeric_policy=ef.NumericPolicy(
            comparison="approximate",
            unit="metre",
            tolerance=ef.Tolerance(
                absolute=Decimal("0.01"), unit="metre", justification="Fixed instrument accuracy"
            ),
        ),
    )
    schema = pa.schema([("x", pa.float64())])
    result = ef.infer_diff_contract(schema, column_overrides=[column])
    assert result.spec.contract.output.schema_spec.columns == (column,)
    assert (
        result.provenance_for(OUTPUT + "/columns/0/numeric_policy/tolerance/absolute").origin
        == "user"
    )
    assert (
        ef.infer_diff_contract(schema)
        .spec.contract.output.schema_spec.columns[0]
        .numeric_policy.unit
        == "unspecified"
    )
    assert ef.DiffContract.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("overrides", [[integer("unknown")], [integer(), integer()]])
def test_inference_rejects_unknown_and_duplicate_overrides(overrides):
    with pytest.raises(ef.InvalidExecutionInput):
        ef.infer_diff_contract(pa.schema([("id", pa.int64())]), column_overrides=overrides)


@pytest.mark.parametrize(
    "schema",
    [
        pa.schema([]),
        pa.schema([("id", pa.int64()), ("id", pa.int64())]),
        pa.schema([(" ", pa.int64())]),
        pa.schema([(" id", pa.int64())]),
    ],
)
def test_inference_rejects_empty_or_ambiguous_names(schema):
    with pytest.raises(ef.InvalidExecutionInput):
        ef.infer_diff_contract(schema)


def test_inference_accepts_only_schema_not_table_rows():
    with pytest.raises(ef.InvalidExecutionInput, match="rows are not accepted"):
        ef.infer_diff_contract(pa.table({"id": [1, 2]}))


@pytest.mark.parametrize(
    "schema",
    [
        pa.schema([("x", pa.int64())], metadata={b"unit": b"private-domain-unit"}),
        pa.schema([pa.field("x", pa.int64(), metadata={b"unit": b"private-domain-unit"})]),
    ],
)
def test_custom_arrow_metadata_is_not_silently_dropped(schema):
    for overrides in ((), (integer("x"),)):
        with pytest.raises(ef.CapabilityError, match="explicit contract") as error:
            ef.infer_diff_contract(schema, column_overrides=overrides)
        assert "private-domain-unit" not in str(error.value)


def test_empty_arrow_metadata_does_not_require_a_domain_decision():
    schema = pa.schema([pa.field("x", pa.int64(), metadata={})], metadata={})
    result = ef.infer_diff_contract(schema)
    assert result.spec.contract.output.schema_spec.columns[0].name == "x"


def test_builder_inputs_are_detached_from_mutable_containers():
    columns = [integer()]
    keys = ["id"]
    result = ef.keyed_contract(columns, keys=keys)
    before = result.model_dump_json()
    columns.append(integer("other"))
    keys.append("other")
    assert result.model_dump_json() == before


def test_json_schema_describes_pointer_syntax_and_strict_version():
    import jsonschema

    schema = ef.DiffContract.model_json_schema()
    doc = json.loads(ef.bag_contract([integer()]).model_dump_json())
    jsonschema.validate(doc, schema)
    doc["provenance"][0]["path"] = "not-an-absolute-pointer"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)
    doc = json.loads(ef.bag_contract([integer()]).model_dump_json())
    doc["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        ef.DiffContract.model_validate_json(json.dumps(doc))
