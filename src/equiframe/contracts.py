"""Strict declarative semantic contracts. No table processing or rule execution."""

import struct
from datetime import date
from datetime import timezone as _timezone
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, ValidationError, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    Text,
    fail,
    strict_int_literal,
    unique,
)
from equiframe._timezones import timezone
from equiframe.values import (
    DateValue,
    ExactDecimal,
    ScalarValue,
    TimestampValue,
    TimeUnit,
    TimeZone,
    _timestamp_datetime,
    offset_nanoseconds,
)

UTC = _timezone.utc

SCHEMA_VERSION = "1.0"
Family = Literal["nulls_types", "joins", "duplicates_order", "aggregations", "dates"]


class BooleanType(FrozenModel):
    kind: Literal["boolean"] = "boolean"


class IntegerType(FrozenModel):
    kind: Literal["integer"] = "integer"
    bits: Annotated[Literal[8, 16, 32, 64], BeforeValidator(strict_int_literal)]
    signed: bool


class StringType(FrozenModel):
    kind: Literal["string"] = "string"


class DecimalType(FrozenModel):
    kind: Literal["decimal"] = "decimal"
    precision: Annotated[int, Field(ge=1, le=76)]
    scale: NonNegativeInt

    @model_validator(mode="after")
    def valid_scale(self) -> Self:
        if self.scale > self.precision:
            fail("decimal_scale", "scale must not exceed precision", "scale")
        return self


class FloatType(FrozenModel):
    kind: Literal["float"] = "float"
    bits: Annotated[Literal[32, 64], BeforeValidator(strict_int_literal)]


class DateType(FrozenModel):
    kind: Literal["date"] = "date"


class TimestampType(FrozenModel):
    kind: Literal["timestamp"] = "timestamp"
    unit: TimeUnit
    timezone: TimeZone | None


LogicalType = Annotated[
    BooleanType | IntegerType | StringType | DecimalType | FloatType | DateType | TimestampType,
    Field(discriminator="kind"),
]


class NullPolicy(FrozenModel):
    representations: Annotated[
        tuple[Literal["null", "empty_string", "zero"], ...], Field(min_length=1)
    ]
    justification: Text | None = None

    @model_validator(mode="after")
    def explicit_equivalences(self) -> Self:
        unique(self.representations, "representations")
        if "null" not in self.representations:
            fail("missing_null", "logical absence must include null", "representations")
        if len(self.representations) > 1 and self.justification is None:
            fail(
                "null_justification", "absence equivalences require justification", "justification"
            )
        return self


class NaNPolicy(FrozenModel):
    handling: Literal["forbid", "distinct", "as_null"]
    justification: Text | None = None

    @model_validator(mode="after")
    def explicit_equivalence(self) -> Self:
        if self.handling == "as_null" and self.justification is None:
            fail("nan_justification", "NaN as absence requires justification", "justification")
        return self


class Tolerance(FrozenModel):
    absolute: ExactDecimal | None = None
    relative: ExactDecimal | None = None
    unit: Text
    justification: Text

    @model_validator(mode="after")
    def nonnegative_bounds(self) -> Self:
        if self.absolute is None and self.relative is None:
            fail("empty_tolerance", "declare absolute or relative tolerance", "absolute")
        for field, value in (("absolute", self.absolute), ("relative", self.relative)):
            if value is not None and value < 0:
                fail("negative_tolerance", "tolerance must be nonnegative", field)
        return self


class NumericPolicy(FrozenModel):
    comparison: Literal["exact", "approximate"]
    unit: Text
    rounding: (
        Literal[
            "ROUND_DOWN",
            "ROUND_UP",
            "ROUND_CEILING",
            "ROUND_FLOOR",
            "ROUND_HALF_UP",
            "ROUND_HALF_DOWN",
            "ROUND_HALF_EVEN",
            "ROUND_05UP",
        ]
        | None
    ) = None
    rounding_justification: Text | None = None
    tolerance: Tolerance | None = None

    @model_validator(mode="after")
    def consistent_comparison(self) -> Self:
        if self.comparison == "exact" and self.tolerance is not None:
            fail("exact_tolerance", "exact comparison cannot have a tolerance", "tolerance")
        if self.comparison == "approximate" and self.tolerance is None:
            fail("missing_tolerance", "approximate comparison requires tolerance", "tolerance")
        if self.tolerance is not None and self.tolerance.unit != self.unit:
            fail("tolerance_unit", "tolerance unit must match the column unit", "tolerance", "unit")
        if (self.rounding is None) != (self.rounding_justification is None):
            fail(
                "rounding_justification",
                "rounding requires an explicit mode and justification",
                "rounding",
            )
        return self


IntervalClosure = Literal["both", "left", "right", "neither"]


class DatePolicy(FrozenModel):
    kind: Literal["date"] = "date"
    granularity: Literal["day"] = "day"
    lower: DateValue | None = None
    upper: DateValue | None = None
    closed: IntervalClosure

    @model_validator(mode="after")
    def ordered_interval(self) -> Self:
        if self.lower is not None and self.upper is not None:
            if self.lower.value > self.upper.value:
                fail("temporal_interval", "lower bound exceeds upper bound", "upper")
            if self.lower.value == self.upper.value and self.closed != "both":
                fail("empty_interval", "equal bounds require both endpoints included", "closed")
        return self


class TimestampPolicy(FrozenModel):
    kind: Literal["timestamp"] = "timestamp"
    granularity: TimeUnit
    timezone: TimeZone | None
    naive: Literal["reject", "preserve", "assume_zone"]
    comparison: Literal["instant", "wall_time"]
    ambiguous: Literal["reject", "earlier", "later"]
    nonexistent: Literal["reject"] = "reject"
    lower: TimestampValue | None = None
    upper: TimestampValue | None = None
    closed: IntervalClosure

    def _bound(self, value: TimestampValue, field: str) -> int:
        max_digits = {"s": 0, "ms": 3, "us": 6, "ns": 9}[self.granularity]
        if value.fractional_digits > max_digits:
            fail("temporal_precision", "bound exceeds declared granularity", field, "value")
        if value.zone is not None and value.zone != self.timezone:
            fail("temporal_zone", "bound zone must match policy zone", field, "zone")
        if value.has_offset:
            if self.timezone is not None:
                stamp = _timestamp_datetime(value.value)
                try:
                    actual_offset = stamp.astimezone(timezone(self.timezone)).utcoffset()
                except (OverflowError, ValueError):
                    fail("timestamp_range", "zoned instant exceeds calendar range", field, "value")
                if actual_offset != stamp.utcoffset():
                    fail(
                        "zone_offset_mismatch",
                        "bound offset disagrees with policy zone",
                        field,
                        "value",
                    )
            return value.nanoseconds(instant=self.comparison == "instant")
        if self.naive == "reject":
            fail("naive_timestamp", "policy rejects timestamps without offset", field, "value")
        if self.naive == "preserve":
            return value.nanoseconds(instant=False)
        if not (self.timezone is not None):
            raise AssertionError("Internal invariant check failed.")
        choices = [value.in_zone(self.timezone, fold=fold) for fold in (0, 1)]
        try:
            valid = [
                choice
                for choice in choices
                if choice.astimezone(UTC).astimezone(choice.tzinfo).replace(tzinfo=None)
                == choice.replace(tzinfo=None)
            ]
        except (OverflowError, ValueError):
            fail("timestamp_range", "zoned instant exceeds calendar range", field, "value")
        if not valid:
            fail("nonexistent_time", "local timestamp falls in a DST gap", field, "value")
        offsets = {offset_nanoseconds(choice.utcoffset()) for choice in valid}
        if len(offsets) > 1 and self.ambiguous == "reject":
            fail("ambiguous_time", "local timestamp has two possible UTC offsets", field, "value")
        result = value.nanoseconds(instant=False)
        if self.comparison == "wall_time":
            return result
        instants = [result - offset for offset in offsets]
        return max(instants) if self.ambiguous == "later" else min(instants)

    @model_validator(mode="after")
    def consistent_time(self) -> Self:
        if self.naive == "assume_zone" and self.timezone is None:
            fail("missing_timezone", "assume_zone requires an IANA time zone", "timezone")
        if self.naive == "preserve" and (
            self.comparison != "wall_time" or self.timezone is not None
        ):
            fail("naive_policy", "preserved naive time requires wall_time and no zone", "naive")
        if self.naive != "assume_zone" and self.ambiguous != "reject":
            fail("ambiguous_policy", "DST resolution applies only to assume_zone", "ambiguous")
        lower = self._bound(self.lower, "lower") if self.lower is not None else None
        upper = self._bound(self.upper, "upper") if self.upper is not None else None
        if (
            self.naive == "preserve"
            and self.lower is not None
            and self.upper is not None
            and self.lower.has_offset != self.upper.has_offset
        ):
            fail(
                "mixed_temporal_bounds",
                "bounds must both be naive or both have offsets",
                "upper",
            )
        if lower is not None and upper is not None:
            if lower > upper:
                fail("temporal_interval", "lower bound exceeds upper bound", "upper")
            if lower == upper and self.closed != "both":
                fail("empty_interval", "equal bounds require both endpoints included", "closed")
        return self


TemporalPolicy = Annotated[DatePolicy | TimestampPolicy, Field(discriminator="kind")]


class ColumnSpec(FrozenModel):
    name: Text
    logical_type: LogicalType
    nullable: bool
    null_policy: NullPolicy
    nan_policy: NaNPolicy | None = None
    numeric_policy: NumericPolicy | None = None
    temporal_policy: TemporalPolicy | None = None
    allowed_values: tuple[ScalarValue, ...] = ()

    @model_validator(mode="after")
    def compatible_policies(self) -> Self:
        kind = self.logical_type.kind
        representations = self.null_policy.representations
        if len(representations) > 1 and not self.nullable:
            fail(
                "nonnullable_equivalence",
                "absence equivalences require a nullable column",
                "null_policy",
            )
        if "empty_string" in representations and kind != "string":
            fail("null_type", "empty_string absence is only valid for strings", "null_policy")
        if "zero" in representations and kind not in ("integer", "decimal", "float"):
            fail("null_type", "zero absence is only valid for numeric columns", "null_policy")
        if kind == "float":
            if self.nan_policy is None:
                fail("missing_nan_policy", "float requires an explicit NaN policy", "nan_policy")
            if self.nan_policy.handling == "as_null" and not self.nullable:
                fail("nan_nullable", "NaN as absence requires a nullable column", "nan_policy")
        elif self.nan_policy is not None:
            fail("nan_type", "NaN policy is only valid for floats", "nan_policy")
        if kind in ("integer", "decimal", "float"):
            if self.numeric_policy is None:
                fail(
                    "missing_numeric_policy",
                    "numeric columns require an explicit numeric policy",
                    "numeric_policy",
                )
            if self.numeric_policy.rounding is not None and kind != "decimal":
                fail(
                    "rounding_type",
                    "decimal rounding is only valid for decimal columns",
                    "numeric_policy",
                    "rounding",
                )
            if kind == "decimal" and self.numeric_policy.comparison != "exact":
                fail(
                    "decimal_exact",
                    "decimal columns require exact comparison",
                    "numeric_policy",
                    "comparison",
                )
        elif self.numeric_policy is not None:
            fail("numeric_type", "numeric policy requires a numeric type", "numeric_policy")
        if kind in ("date", "timestamp"):
            if self.temporal_policy is None or self.temporal_policy.kind != kind:
                fail(
                    "temporal_type",
                    "temporal policy must match the logical type",
                    "temporal_policy",
                )
            if isinstance(self.logical_type, TimestampType):
                if not (isinstance(self.temporal_policy, TimestampPolicy)):
                    raise AssertionError("Internal invariant check failed.")
                if self.logical_type.timezone != self.temporal_policy.timezone:
                    fail(
                        "temporal_zone",
                        "type and policy zones must match",
                        "temporal_policy",
                        "timezone",
                    )
                if self.logical_type.unit != self.temporal_policy.granularity:
                    fail(
                        "temporal_unit",
                        "type and policy granularities must match",
                        "temporal_policy",
                        "granularity",
                    )
        elif self.temporal_policy is not None:
            fail("temporal_type", "temporal policy requires a date or timestamp", "temporal_policy")
        for index, value in enumerate(self.allowed_values):
            self._literal(value, index)
        return self

    def _literal(self, value: ScalarValue, index: int) -> None:
        location: tuple[str | int, ...] = ("allowed_values", index)
        kind = self.logical_type.kind
        if value.kind == "null":
            if not self.nullable:
                fail("literal_null", "null is not allowed in a nonnullable column", *location)
            return
        if value.kind in ("nan", "infinity"):
            if kind != "float":
                fail("literal_type", "special float value requires a float column", *location)
            if (
                value.kind == "nan"
                and self.nan_policy is not None
                and self.nan_policy.handling == "forbid"
            ):
                fail("literal_nan", "NaN is forbidden by the column policy", *location)
            return
        if value.kind != kind:
            fail("literal_type", "literal kind must match column kind", *location)
        if isinstance(self.logical_type, IntegerType) and value.kind == "integer":
            bits = self.logical_type.bits
            lower = -(2 ** (bits - 1)) if self.logical_type.signed else 0
            upper = 2 ** (bits - (1 if self.logical_type.signed else 0)) - 1
            if not lower <= value.value <= upper:
                fail("integer_range", "literal exceeds integer width/sign", *location, "value")
        if isinstance(self.logical_type, DecimalType) and value.kind == "decimal":
            parts = value.value.as_tuple()
            if not (isinstance(parts.exponent, int)):
                raise AssertionError("Internal invariant check failed.")
            if parts.exponent < -self.logical_type.scale:
                fail(
                    "decimal_literal_scale",
                    "literal would lose fractional scale",
                    *location,
                    "value",
                )
            integer_digits = max(len(parts.digits) + parts.exponent, 0) if value.value != 0 else 0
            if integer_digits > self.logical_type.precision - self.logical_type.scale:
                fail(
                    "decimal_literal_precision",
                    "literal exceeds decimal precision",
                    *location,
                    "value",
                )
        if (
            isinstance(self.logical_type, FloatType)
            and value.kind == "float"
            and self.logical_type.bits == 32
        ):
            try:
                represented = struct.unpack("!f", struct.pack("!f", value.value))[0]
            except OverflowError:
                fail("float_range", "literal exceeds float32 range", *location, "value")
            if (
                self.numeric_policy is not None
                and self.numeric_policy.comparison == "exact"
                and represented != value.value
            ):
                fail(
                    "float_precision",
                    "exact float32 literal would require rounding or underflow",
                    *location,
                    "value",
                )
        if isinstance(self.temporal_policy, DatePolicy) and value.kind == "date":
            policy = self.temporal_policy
            lower = date.fromisoformat(policy.lower.value).toordinal() if policy.lower else None
            upper = date.fromisoformat(policy.upper.value).toordinal() if policy.upper else None
            self._interval(
                date.fromisoformat(value.value).toordinal(), lower, upper, policy.closed, index
            )
        if isinstance(self.temporal_policy, TimestampPolicy) and value.kind == "timestamp":
            try:
                stamp_policy = self.temporal_policy
                point = stamp_policy._bound(value, "value")
                lower = (
                    stamp_policy._bound(stamp_policy.lower, "lower") if stamp_policy.lower else None
                )
                upper = (
                    stamp_policy._bound(stamp_policy.upper, "upper") if stamp_policy.upper else None
                )
            except ValidationError as exc:
                issue = exc.errors(include_url=False, include_input=False)[0]
                fail(issue["type"], issue["msg"], *location, *issue["loc"][1:])
            self._interval(point, lower, upper, stamp_policy.closed, index)

    @staticmethod
    def _interval(
        point: int, lower: int | None, upper: int | None, closed: IntervalClosure, index: int
    ) -> None:
        before = lower is not None and (
            point < lower or (point == lower and closed not in ("both", "left"))
        )
        after = upper is not None and (
            point > upper or (point == upper and closed not in ("both", "right"))
        )
        if before or after:
            fail(
                "temporal_literal_bounds",
                "allowed literal falls outside the declared interval",
                "allowed_values",
                index,
                "value",
            )


class GlobalKeyScope(FrozenModel):
    kind: Literal["global"] = "global"


class TableKeyScope(FrozenModel):
    kind: Literal["table"] = "table"


class ColumnKeyScope(FrozenModel):
    kind: Literal["columns"] = "columns"
    columns: Annotated[tuple[Text, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_columns(self) -> Self:
        unique(self.columns, "columns")
        return self


KeyScope = Annotated[GlobalKeyScope | TableKeyScope | ColumnKeyScope, Field(discriminator="kind")]


class KeySpec(FrozenModel):
    name: Identifier
    columns: Annotated[tuple[Text, ...], Field(min_length=1)]
    unique: bool
    incomplete: Literal["reject", "allow"]
    scope: KeyScope

    @model_validator(mode="after")
    def unique_columns(self) -> Self:
        unique(self.columns, "columns")
        if isinstance(self.scope, ColumnKeyScope) and set(self.scope.columns) & set(self.columns):
            fail(
                "key_scope_overlap",
                "scope columns must be separate from key columns",
                "scope",
                "columns",
            )
        return self


class SortSpec(FrozenModel):
    column: Text
    direction: Literal["ascending", "descending"]
    nulls: Literal["first", "last"]


class IgnoredOrder(FrozenModel):
    kind: Literal["ignored"] = "ignored"


class SignificantOrder(FrozenModel):
    kind: Literal["significant"] = "significant"
    by: Annotated[tuple[SortSpec, ...], Field(min_length=1)]
    ties: Literal["preserve", "reject"]

    @model_validator(mode="after")
    def unique_columns(self) -> Self:
        unique(tuple(item.column for item in self.by), "by")
        return self


OrderPolicy = Annotated[IgnoredOrder | SignificantOrder, Field(discriminator="kind")]
Multiplicity = Literal["preserve", "distinct"]


class TableSchema(FrozenModel):
    columns: Annotated[tuple[ColumnSpec, ...], Field(min_length=1)]
    keys: tuple[KeySpec, ...]
    multiplicity: Multiplicity
    order: OrderPolicy

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        names = tuple(column.name for column in self.columns)
        for index, name in enumerate(names):
            if name in names[:index]:
                fail("duplicate_column", "column names must be unique", "columns", index, "name")
        key_names = tuple(key.name for key in self.keys)
        for index, name in enumerate(key_names):
            if name in key_names[:index]:
                fail("duplicate_key", "key names must be unique", "keys", index, "name")
        for index, key in enumerate(self.keys):
            scope_columns = key.scope.columns if isinstance(key.scope, ColumnKeyScope) else ()
            for path, values in (
                (("columns",), key.columns),
                (("scope", "columns"), scope_columns),
            ):
                for ref_index, ref in enumerate(values):
                    if ref not in names:
                        fail(
                            "unknown_column",
                            "unknown key column: " + ref,
                            "keys",
                            index,
                            *path,
                            ref_index,
                        )
        if isinstance(self.order, SignificantOrder):
            for index, item in enumerate(self.order.by):
                if item.column not in names:
                    fail(
                        "unknown_column",
                        "unknown order column: " + item.column,
                        "order",
                        "by",
                        index,
                        "column",
                    )
        return self


class TableSpec(FrozenModel):
    name: Identifier
    schema_spec: TableSchema


class SchemaCheck(FrozenModel):
    kind: Literal["schema"] = "schema"
    table: Identifier


class KeyCheck(FrozenModel):
    kind: Literal["key"] = "key"
    table: Identifier
    key: Identifier


class CardinalityCheck(FrozenModel):
    kind: Literal["cardinality"] = "cardinality"
    table: Identifier
    minimum: NonNegativeInt
    maximum: NonNegativeInt | None = None

    @model_validator(mode="after")
    def consistent_bounds(self) -> Self:
        if self.maximum is not None and self.maximum < self.minimum:
            fail("cardinality_bounds", "maximum must be at least minimum", "maximum")
        return self


class JoinCheck(FrozenModel):
    kind: Literal["join"] = "join"
    left_table: Identifier
    right_table: Identifier
    left_columns: Annotated[tuple[Text, ...], Field(min_length=1)]
    right_columns: Annotated[tuple[Text, ...], Field(min_length=1)]
    relationship: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    unmatched: Literal["allow", "reject"]

    @model_validator(mode="after")
    def paired_columns(self) -> Self:
        unique(self.left_columns, "left_columns")
        unique(self.right_columns, "right_columns")
        if len(self.left_columns) != len(self.right_columns):
            fail("join_arity", "join column lists must have equal length", "right_columns")
        return self


class OrderCheck(FrozenModel):
    kind: Literal["order"] = "order"
    table: Identifier
    columns: Annotated[tuple[Text, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_columns(self) -> Self:
        unique(self.columns, "columns")
        return self


class AggregateCheck(FrozenModel):
    kind: Literal["aggregate"] = "aggregate"
    table: Identifier
    group_by: tuple[Text, ...]
    measure: Text | None
    function: Literal["sum", "count", "min", "max"]
    output_table: Identifier
    output_column: Text

    @model_validator(mode="after")
    def compatible_measure(self) -> Self:
        unique(self.group_by, "group_by")
        if self.function != "count" and self.measure is None:
            fail("missing_measure", "this aggregation requires a measure", "measure")
        return self


RuleDefinition = Annotated[
    SchemaCheck | KeyCheck | CardinalityCheck | JoinCheck | OrderCheck | AggregateCheck,
    Field(discriminator="kind"),
]


class PreconditionSpec(FrozenModel):
    precondition_id: Identifier
    requirement: RuleDefinition


class RuleSpec(FrozenModel):
    rule_id: Identifier
    revision: PositiveInt
    specification: RuleDefinition
    severity: Literal["info", "warning", "error"]
    required: bool
    applicability: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def unique_preconditions(self) -> Self:
        unique(self.applicability, "applicability")
        return self


class Contract(FrozenModel):
    schema_version: Literal["1.0"]
    contract_id: Identifier
    revision: PositiveInt
    family: Family
    inputs: Annotated[tuple[TableSpec, ...], Field(min_length=1)]
    output: TableSpec
    preconditions: tuple[PreconditionSpec, ...]
    rules: tuple[RuleSpec, ...]

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        tables = (*self.inputs, self.output)
        input_names = tuple(table.name for table in self.inputs)
        for index, name in enumerate(input_names):
            if name in input_names[:index]:
                fail("duplicate_table", "table names must be unique", "inputs", index, "name")
        if self.output.name in input_names:
            fail("duplicate_table", "output name must differ from input names", "output", "name")
        unique(tuple(item.precondition_id for item in self.preconditions), "preconditions")
        unique(tuple(item.rule_id for item in self.rules), "rules")
        catalog = {table.name: table.schema_spec for table in tables}
        preconditions = {item.precondition_id for item in self.preconditions}
        for index, item in enumerate(self.preconditions):
            self._definition(item.requirement, catalog, ("preconditions", index, "requirement"))
        for index, rule in enumerate(self.rules):
            self._definition(rule.specification, catalog, ("rules", index, "specification"))
            for ref_index, ref in enumerate(rule.applicability):
                if ref not in preconditions:
                    fail(
                        "unknown_precondition",
                        "unknown precondition: " + ref,
                        "rules",
                        index,
                        "applicability",
                        ref_index,
                    )
        return self

    @staticmethod
    def _definition(
        definition: RuleDefinition,
        catalog: dict[str, TableSchema],
        location: tuple[str | int, ...],
    ) -> None:
        def table(name: str, field: str) -> TableSchema:
            if name not in catalog:
                fail("unknown_table", "unknown table: " + name, *location, field)
            return catalog[name]

        def columns(name: str, refs: tuple[str, ...], field: str) -> None:
            names = {column.name for column in catalog[name].columns}
            for index, ref in enumerate(refs):
                if ref not in names:
                    suffix: tuple[str | int, ...] = (
                        (field,) if field in ("measure", "output_column") else (field, index)
                    )
                    fail("unknown_column", "unknown column: " + ref, *location, *suffix)

        if isinstance(definition, JoinCheck):
            left = table(definition.left_table, "left_table")
            right = table(definition.right_table, "right_table")
            columns(definition.left_table, definition.left_columns, "left_columns")
            columns(definition.right_table, definition.right_columns, "right_columns")
            left_columns = {col.name: col for col in left.columns}
            right_columns = {col.name: col for col in right.columns}
            for index, (lcol, rcol) in enumerate(
                zip(definition.left_columns, definition.right_columns, strict=True)
            ):
                if left_columns[lcol].logical_type != right_columns[rcol].logical_type:
                    fail(
                        "join_type",
                        "join columns require identical logical types",
                        *location,
                        "right_columns",
                        index,
                    )
                if not _same_units(left_columns[lcol], right_columns[rcol]):
                    fail(
                        "join_unit",
                        "join columns require identical numeric units",
                        *location,
                        "right_columns",
                        index,
                    )
            return
        schema = table(definition.table, "table")
        if isinstance(definition, KeyCheck):
            if definition.key not in {key.name for key in schema.keys}:
                fail("unknown_key", "unknown key: " + definition.key, *location, "key")
        elif isinstance(definition, OrderCheck):
            columns(definition.table, definition.columns, "columns")
            if not isinstance(schema.order, SignificantOrder) or definition.columns != tuple(
                item.column for item in schema.order.by
            ):
                fail(
                    "order_policy",
                    "order check must reference the complete declared significant order",
                    *location,
                    "columns",
                )
        elif isinstance(definition, AggregateCheck):
            output = table(definition.output_table, "output_table")
            columns(definition.table, definition.group_by, "group_by")
            columns(definition.output_table, definition.group_by, "group_by")
            columns(definition.output_table, (definition.output_column,), "output_column")
            source = {col.name: col for col in schema.columns}
            target = {col.name: col for col in output.columns}
            for index, name in enumerate(definition.group_by):
                if source[name].logical_type != target[name].logical_type:
                    fail(
                        "aggregate_group_type",
                        "grouping types must be preserved",
                        *location,
                        "group_by",
                        index,
                    )
                if not _same_units(source[name], target[name]):
                    fail(
                        "aggregate_group_unit",
                        "grouping units must be preserved",
                        *location,
                        "group_by",
                        index,
                    )
            if definition.measure is not None:
                columns(definition.table, (definition.measure,), "measure")
            if definition.function == "sum" and definition.measure is not None:
                if source[definition.measure].logical_type.kind not in (
                    "integer",
                    "decimal",
                    "float",
                ):
                    fail("aggregate_type", "sum requires a numeric measure", *location, "measure")
                if not _sum_type(
                    source[definition.measure].logical_type,
                    target[definition.output_column].logical_type,
                ):
                    fail(
                        "aggregate_type",
                        "sum must preserve numeric family without narrowing its value domain",
                        *location,
                        "output_column",
                    )
            if (
                definition.function == "count"
                and target[definition.output_column].logical_type.kind != "integer"
            ):
                fail("aggregate_type", "count output must be integer", *location, "output_column")
            if (
                definition.function in ("min", "max")
                and definition.measure is not None
                and source[definition.measure].logical_type
                != target[definition.output_column].logical_type
            ):
                fail(
                    "aggregate_type",
                    "min/max must preserve the logical type",
                    *location,
                    "output_column",
                )
            if (
                definition.function in ("sum", "min", "max")
                and definition.measure is not None
                and not _same_units(source[definition.measure], target[definition.output_column])
            ):
                fail(
                    "aggregate_unit",
                    "sum/min/max must preserve numeric units",
                    *location,
                    "output_column",
                )


def _same_units(source: ColumnSpec, target: ColumnSpec) -> bool:
    return (
        source.numeric_policy is None
        or target.numeric_policy is None
        or source.numeric_policy.unit == target.numeric_policy.unit
    )


def _sum_type(source: LogicalType, target: LogicalType) -> bool:
    if isinstance(source, IntegerType) and isinstance(target, IntegerType):
        source_lower = -(2 ** (source.bits - 1)) if source.signed else 0
        target_lower = -(2 ** (target.bits - 1)) if target.signed else 0
        source_upper = 2 ** (source.bits - int(source.signed)) - 1
        target_upper = 2 ** (target.bits - int(target.signed)) - 1
        return target_lower <= source_lower and target_upper >= source_upper
    if isinstance(source, DecimalType) and isinstance(target, DecimalType):
        return (
            target.scale >= source.scale
            and target.precision - target.scale >= source.precision - source.scale
        )
    if isinstance(source, FloatType) and isinstance(target, FloatType):
        return target.bits >= source.bits
    return False
