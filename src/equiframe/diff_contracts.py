"""Small, inspectable builders over the existing immutable comparison contract.

Inference reads only an Arrow schema supplied by the caller. It never inspects
rows, invents a key, converts values, or derives domain constraints from samples.
The ``unspecified`` numeric unit is an exact scalar-equality label, not an
inferred physical unit. Declare ColumnSpec explicitly for units or tolerances.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, TypeVar, cast

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Text, fail
from equiframe._timezones import timezone
from equiframe.comparison_types import ComparisonPolicy, ComparisonSpec
from equiframe.contracts import (
    BooleanType,
    ColumnSpec,
    Contract,
    DatePolicy,
    DateType,
    DecimalType,
    FloatType,
    IgnoredOrder,
    IntegerType,
    KeySpec,
    LogicalType,
    Multiplicity,
    NaNPolicy,
    NullPolicy,
    NumericPolicy,
    OrderPolicy,
    SignificantOrder,
    SortSpec,
    StringType,
    TableKeyScope,
    TableSchema,
    TableSpec,
    TimestampPolicy,
    TimestampType,
)
from equiframe.errors import CapabilityError, InvalidExecutionInput
from equiframe.tables import require_dependency
from equiframe.values import TimeUnit

_T = TypeVar("_T")

if TYPE_CHECKING:
    import pyarrow as pa

Origin = Literal["user", "metadata", "reference", "default"]
Reference = Literal["peer", "expected"]
Incomplete = Literal["reject", "allow"]
Ties = Literal["preserve", "reject"]
_Source = tuple[Origin, str]


class _DefaultText(str):
    """Keep readable defaults while distinguishing an explicitly passed value."""


class _DefaultRevision(int):
    pass


_DEFAULT_REFERENCE = cast(Reference, _DefaultText("expected"))
_DEFAULT_MULTIPLICITY = cast(Multiplicity, _DefaultText("preserve"))
_DEFAULT_INCOMPLETE = cast(Incomplete, _DefaultText("reject"))
_DEFAULT_TIES = cast(Ties, _DefaultText("preserve"))
_DEFAULT_ID = _DefaultText("diff")
_DEFAULT_REVISION = _DefaultRevision(1)
_DEFAULT: _Source = ("default", "Builder default; no observed values were used")
_USER: _Source = ("user", "Explicit caller selection")
_COLUMN: _Source = ("user", "Caller-supplied ColumnSpec, including its declared defaults")
_METADATA: _Source = ("metadata", "Declared Arrow reference field name or physical type")
_SCHEMA_PATHS = ("/spec/contract/inputs/0/schema_spec", "/spec/contract/output/schema_spec")


def _leaf_paths(value: object, path: str) -> tuple[str, ...]:
    if isinstance(value, dict) and value:
        return tuple(
            leaf
            for name, item in value.items()
            for leaf in _leaf_paths(
                item, path + "/" + str(name).replace("~", "~0").replace("/", "~1")
            )
        )
    if isinstance(value, (tuple, list)) and value:
        return tuple(
            leaf
            for index, item in enumerate(value)
            for leaf in _leaf_paths(item, path + "/" + str(index))
        )
    # None and empty containers are policy decisions too.
    return (path,)


class PolicyProvenance(FrozenModel):
    """A nonsecret explanation for one canonical absolute JSON-pointer leaf.

    Explanations are supplied by the caller or generated without row values or
    arbitrary Arrow metadata. Do not put secrets in a custom ``detail``.
    """

    path: Text = Field(pattern=r"^(?:/(?:[^~/]|~[01])*)+$")
    origin: Origin
    detail: Text = Field(description="Nonsecret explanation; do not include row values or secrets")


class DiffContract(FrozenModel):
    """Versioned comparison spec and complete, immutable policy provenance.

    Coverage validates the declared explanation, not its historical authenticity.
    An author can supply a new explanation; provenance is not a signature.
    """

    schema_version: Literal["1.0"] = "1.0"
    spec: ComparisonSpec
    reference: Reference = "expected"
    provenance: tuple[PolicyProvenance, ...]

    @model_validator(mode="after")
    def complete_provenance(self) -> Self:
        expected = set(_leaf_paths(self.spec.model_dump(mode="json"), "/spec")) | {"/reference"}
        seen: set[str] = set()
        for index, item in enumerate(self.provenance):
            if item.path in seen:
                fail("duplicate_provenance", "provenance paths must be unique", "provenance", index)
            if item.path not in expected:
                fail(
                    "unknown_provenance",
                    "provenance path is not a policy leaf",
                    "provenance",
                    index,
                )
            seen.add(item.path)
        if seen != expected:
            fail(
                "missing_provenance",
                "every spec and reference leaf requires provenance",
                "provenance",
            )
        return self

    def provenance_for(self, path: str) -> PolicyProvenance:
        """Return the exact leaf explanation; raise KeyError for unknown paths."""
        for item in self.provenance:
            if item.path == path:
                return item
        raise KeyError(path)

    @classmethod
    def from_contract(
        cls,
        contract: Contract,
        *,
        policy: ComparisonPolicy | None = None,
        reference: Reference = _DEFAULT_REFERENCE,
    ) -> Self:
        """Wrap an existing contract unchanged; its entire declaration is user-origin."""
        spec = ComparisonSpec(
            contract=contract, policy=policy if policy is not None else ComparisonPolicy()
        )
        sources = {
            path: _USER
            for path in _leaf_paths(spec.contract.model_dump(mode="json"), "/spec/contract")
        }
        _policy_sources(spec, policy, sources)
        chosen_reference, source = _choice(reference, _DEFAULT_REFERENCE, "expected")
        sources["/reference"] = source
        return cls(spec=spec, reference=chosen_reference, provenance=_provenance(spec, sources))


def _choice(value: _T, marker: _T, default: _T) -> tuple[_T, _Source]:
    return (default, _DEFAULT) if value is marker else (value, _USER)


def _provenance(spec: ComparisonSpec, sources: dict[str, _Source]) -> tuple[PolicyProvenance, ...]:
    paths = (*_leaf_paths(spec.model_dump(mode="json"), "/spec"), "/reference")
    return tuple(
        PolicyProvenance(
            path=path, origin=sources.get(path, _DEFAULT)[0], detail=sources.get(path, _DEFAULT)[1]
        )
        for path in paths
    )


def _mark(sources: dict[str, _Source], value: object, path: str, source: _Source) -> None:
    sources.update(dict.fromkeys(_leaf_paths(value, path), source))


def _policy_sources(
    spec: ComparisonSpec, policy: ComparisonPolicy | None, sources: dict[str, _Source]
) -> None:
    if policy is not None:
        _mark(sources, spec.policy.model_dump(mode="json"), "/spec/policy", _USER)


def _build(
    columns: Sequence[ColumnSpec],
    *,
    keys: tuple[KeySpec, ...],
    order: OrderPolicy,
    schema_sources: dict[str, _Source],
    policy: ComparisonPolicy | None,
    multiplicity: Multiplicity,
    reference: Reference,
    contract_id: str,
    revision: int,
) -> DiffContract:
    chosen_multiplicity, multiplicity_source = _choice(
        multiplicity, _DEFAULT_MULTIPLICITY, "preserve"
    )
    chosen_reference, reference_source = _choice(reference, _DEFAULT_REFERENCE, "expected")
    chosen_id, id_source = _choice(contract_id, _DEFAULT_ID, "diff")
    chosen_revision, revision_source = _choice(revision, _DEFAULT_REVISION, 1)
    schema = TableSchema(
        columns=tuple(columns), keys=keys, multiplicity=chosen_multiplicity, order=order
    )
    contract = Contract(
        schema_version="1.0",
        contract_id=chosen_id,
        revision=chosen_revision,
        family="nulls_types",
        inputs=(TableSpec(name="source", schema_spec=schema),),
        output=TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    spec = ComparisonSpec(
        contract=contract, policy=policy if policy is not None else ComparisonPolicy()
    )
    sources: dict[str, _Source] = {
        "/spec/contract/contract_id": id_source,
        "/spec/contract/revision": revision_source,
        "/reference": reference_source,
        "/spec/contract/family": (
            "default",
            "Required contract bookkeeping family; no domain was inferred",
        ),
    }
    for path in _SCHEMA_PATHS:
        _mark(sources, schema.model_dump(mode="json")["columns"], path + "/columns", _COLUMN)
        sources[path + "/multiplicity"] = multiplicity_source
        sources.update({path + suffix: source for suffix, source in schema_sources.items()})
    _policy_sources(spec, policy, sources)
    return DiffContract(
        spec=spec, reference=chosen_reference, provenance=_provenance(spec, sources)
    )


def bag_contract(
    columns: Sequence[ColumnSpec],
    *,
    policy: ComparisonPolicy | None = None,
    multiplicity: Multiplicity = _DEFAULT_MULTIPLICITY,
    reference: Reference = _DEFAULT_REFERENCE,
    contract_id: str = _DEFAULT_ID,
    revision: int = _DEFAULT_REVISION,
) -> DiffContract:
    """Declare an unordered bag, preserving all occurrences by default."""
    return _build(
        columns,
        keys=(),
        order=IgnoredOrder(),
        schema_sources={"/order/kind": ("user", "Selected unordered bag constructor")},
        policy=policy,
        multiplicity=multiplicity,
        reference=reference,
        contract_id=contract_id,
        revision=revision,
    )


def keyed_contract(
    columns: Sequence[ColumnSpec],
    *,
    keys: Sequence[str],
    incomplete: Incomplete = _DEFAULT_INCOMPLETE,
    policy: ComparisonPolicy | None = None,
    multiplicity: Multiplicity = _DEFAULT_MULTIPLICITY,
    reference: Reference = _DEFAULT_REFERENCE,
    contract_id: str = _DEFAULT_ID,
    revision: int = _DEFAULT_REVISION,
) -> DiffContract:
    """Declare a unique table key; the existing kernel verifies it and owns fallback.

    Incomplete keys are rejected by default. ``incomplete='allow'`` retains the
    kernel's bag fallback; neither path assumes uniqueness from sampled rows.
    """
    if isinstance(keys, (str, bytes)):
        raise InvalidExecutionInput("keys must be a sequence of column names, not a string")
    chosen_incomplete, incomplete_source = _choice(incomplete, _DEFAULT_INCOMPLETE, "reject")
    key = KeySpec(
        name="diff_key",
        columns=tuple(keys),
        unique=True,
        incomplete=chosen_incomplete,
        scope=TableKeyScope(),
    )
    sources: dict[str, _Source] = {
        "/order/kind": ("user", "Selected keyed constructor with unordered fallback"),
        "/keys/0/unique": (
            "user",
            "Selected keyed constructor; uniqueness must be verified by the kernel",
        ),
        "/keys/0/incomplete": incomplete_source,
    }
    _mark(sources, key.columns, "/keys/0/columns", _USER)
    return _build(
        columns,
        keys=(key,),
        order=IgnoredOrder(),
        schema_sources=sources,
        policy=policy,
        multiplicity=multiplicity,
        reference=reference,
        contract_id=contract_id,
        revision=revision,
    )


def sequence_contract(
    columns: Sequence[ColumnSpec],
    *,
    by: Sequence[SortSpec],
    ties: Ties = _DEFAULT_TIES,
    policy: ComparisonPolicy | None = None,
    multiplicity: Multiplicity = _DEFAULT_MULTIPLICITY,
    reference: Reference = _DEFAULT_REFERENCE,
    contract_id: str = _DEFAULT_ID,
    revision: int = _DEFAULT_REVISION,
) -> DiffContract:
    """Declare existing significant-order semantics without sorting either input."""
    chosen_ties, ties_source = _choice(ties, _DEFAULT_TIES, "preserve")
    order = SignificantOrder(by=tuple(by), ties=chosen_ties)
    sources: dict[str, _Source] = {
        "/order/kind": ("user", "Selected significant sequence constructor"),
        "/order/ties": ties_source,
    }
    _mark(sources, order.model_dump(mode="json")["by"], "/order/by", _USER)
    return _build(
        columns,
        keys=(),
        order=order,
        schema_sources=sources,
        policy=policy,
        multiplicity=multiplicity,
        reference=reference,
        contract_id=contract_id,
        revision=revision,
    )


def _infer_column(field: pa.Field) -> ColumnSpec:
    import pyarrow as pa

    dtype = field.type
    logical: LogicalType
    if pa.types.is_integer(dtype):
        logical = IntegerType(bits=dtype.bit_width, signed=pa.types.is_signed_integer(dtype))
    elif pa.types.is_floating(dtype) and dtype.bit_width in (32, 64):
        logical = FloatType(bits=dtype.bit_width)
    elif pa.types.is_boolean(dtype):
        logical = BooleanType()
    elif (
        pa.types.is_string(dtype)
        or pa.types.is_large_string(dtype)
        or pa.types.is_string_view(dtype)
    ):
        logical = StringType()
    elif pa.types.is_decimal128(dtype) or pa.types.is_decimal256(dtype):
        if dtype.scale < 0 or dtype.scale > dtype.precision:
            raise CapabilityError(
                "reference decimal scale is unsupported; no implicit rescaling is allowed"
            )
        logical = DecimalType(precision=dtype.precision, scale=dtype.scale)
    elif pa.types.is_date(dtype):
        logical = DateType()
    elif pa.types.is_timestamp(dtype):
        if dtype.tz is not None:
            try:
                timezone(dtype.tz)
            except ValueError as error:
                raise CapabilityError(
                    "reference timestamp has an unsupported zone; an IANA zone is required "
                    "without guessing or converting a zone"
                ) from error
        logical = TimestampType(unit=cast(TimeUnit, dtype.unit), timezone=dtype.tz)
    elif pa.types.is_null(dtype):
        raise CapabilityError(
            "null-only reference type is ambiguous; supply an explicit ColumnSpec"
        )
    else:
        raise CapabilityError(
            "unsupported reference schema type; supply an explicit ColumnSpec only "
            "when the existing transport supports that physical type"
        )
    temporal: DatePolicy | TimestampPolicy | None = None
    if isinstance(logical, DateType):
        temporal = DatePolicy(closed="both")
    elif isinstance(logical, TimestampType):
        temporal = TimestampPolicy(
            granularity=logical.unit,
            timezone=logical.timezone,
            naive="preserve" if logical.timezone is None else "reject",
            comparison="wall_time" if logical.timezone is None else "instant",
            ambiguous="reject",
            closed="both",
        )
    return ColumnSpec(
        name=field.name,
        logical_type=logical,
        nullable=True,
        null_policy=NullPolicy(representations=("null",)),
        nan_policy=NaNPolicy(handling="distinct") if isinstance(logical, FloatType) else None,
        numeric_policy=NumericPolicy(comparison="exact", unit="unspecified")
        if isinstance(logical, (IntegerType, FloatType, DecimalType))
        else None,
        temporal_policy=temporal,
    )


def infer_diff_contract(
    reference_schema: pa.Schema,
    *,
    keys: Sequence[str] | None = None,
    column_overrides: Sequence[ColumnSpec] = (),
    policy: ComparisonPolicy | None = None,
    reference: Reference = _DEFAULT_REFERENCE,
) -> DiffContract:
    """Infer supported physical types from reference metadata, never from values.

    Nullability remains True even for a nonnullable Arrow field: a transported
    schema is not a verified domain constraint. Custom schema/field metadata is
    rejected rather than silently interpreted as keys, units, tolerances, casts,
    or domain restrictions. Use an explicit builder for such domains.
    Null-only fields require an explicit ColumnSpec; unsupported physical types
    still cannot be transported by declaring a different logical type.
    """
    require_dependency("pyarrow", "arrow")
    import pyarrow as pa

    if not isinstance(reference_schema, pa.Schema):
        raise InvalidExecutionInput(
            "reference_schema must be an Arrow Schema; rows are not accepted"
        )
    if reference_schema.metadata or any(field.metadata for field in reference_schema):
        raise CapabilityError(
            "Arrow schema or field metadata requires an explicit contract; "
            "use bag_contract, keyed_contract, or sequence_contract with explicit ColumnSpec"
        )
    names = reference_schema.names
    if (
        not names
        or len(set(names)) != len(names)
        or any(not name.strip() or name != name.strip() for name in names)
    ):
        raise InvalidExecutionInput("reference schema must have nonempty, unique column names")
    overrides: dict[str, ColumnSpec] = {}
    for column in column_overrides:
        column = ColumnSpec.model_validate(column)
        if column.name not in names:
            raise InvalidExecutionInput("column override must name an existing reference column")
        if column.name in overrides:
            raise InvalidExecutionInput("column overrides must not repeat a reference column")
        overrides[column.name] = column
    selected: list[ColumnSpec] = []
    for field in reference_schema:
        override = overrides.get(field.name)
        # Null is transportable but has no logical domain without an override.
        # Other unsupported physical types cannot be enabled by a declaration.
        if override is not None and pa.types.is_null(field.type):
            selected.append(override)
        else:
            inferred = _infer_column(field)
            selected.append(override if override is not None else inferred)
    columns = tuple(selected)
    result = (
        bag_contract(columns, policy=policy, reference=reference)
        if keys is None
        else keyed_contract(columns, keys=keys, policy=policy, reference=reference)
    )
    sources = {item.path: (item.origin, item.detail) for item in result.provenance}
    for path in _SCHEMA_PATHS:
        if keys is None:
            sources[path + "/order/kind"] = (
                "default",
                "Unordered comparison default; no order or key inferred from rows",
            )
        for index, column in enumerate(columns):
            if column.name in overrides:
                continue
            prefix = path + "/columns/" + str(index)
            _mark(sources, column.model_dump(mode="json"), prefix, _DEFAULT)
            sources[prefix + "/name"] = _METADATA
            _mark(
                sources,
                column.logical_type.model_dump(mode="json"),
                prefix + "/logical_type",
                _METADATA,
            )
            sources[prefix + "/nullable"] = (
                "default",
                "Nullable domain retained; transported schema or absent observed NULLs "
                "do not prove nonnullability",
            )
            if column.numeric_policy is not None:
                sources[prefix + "/numeric_policy/unit"] = (
                    "default",
                    "Unspecified exact scalar-equality label; "
                    "no physical unit inferred or converted",
                )
            if isinstance(column.temporal_policy, TimestampPolicy):
                for field_name in ("granularity", "timezone"):
                    sources[prefix + "/temporal_policy/" + field_name] = _METADATA
    return DiffContract(
        spec=result.spec, reference=result.reference, provenance=_provenance(result.spec, sources)
    )
