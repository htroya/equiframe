"""Typed summaries for reference-based comparison of grouped numeric sums."""

import re
from decimal import Decimal
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, WithJsonSchema, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, NonNegativeInt, PositiveInt, Text, _ExplicitOutcome
from equiframe.comparison_types import ComparisonValue
from equiframe.normalization import row_identity
from equiframe.values import ExactDecimal

_FRACTION_PATTERN = r"^-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?$"


def _bounded_fraction(value: object) -> object:
    # Reject compact scientific exponents before Fraction can expand them.
    # Actual admitted Arrow sums/ratios fit comfortably below these limits.
    if isinstance(value, str):
        if len(value) > 4096 or re.fullmatch(_FRACTION_PATTERN, value) is None:
            raise ValueError("group numbers require bounded integer or numerator/denominator text")
        value = Fraction(value)
    if not isinstance(value, Fraction):
        raise ValueError("group numbers require Fraction objects or exact fraction text")
    if (
        isinstance(value, Fraction)
        and max(value.numerator.bit_length(), value.denominator.bit_length()) > 6000
    ):
        raise ValueError("group numbers exceed the admitted exact representation")
    return value


_GroupedNumber = Annotated[
    Fraction,
    BeforeValidator(_bounded_fraction),
    WithJsonSchema({"type": "string", "pattern": _FRACTION_PATTERN, "maxLength": 4096}),
]


def _key_identity(key: tuple[ComparisonValue, ...]) -> bytes:
    for value in key:
        if value.kind in ("nan", "infinity"):
            raise ValueError("group keys must not contain NaN or infinity")
        if value.kind in ("integer", "decimal", "float", "date", "timestamp"):
            text = value.value or ""
            if len(text) > 4096:
                raise ValueError("group key numeric text exceeds admitted bounds")
            numeric = Decimal(text)
            parts = numeric.as_tuple()
            assert isinstance(parts.exponent, int)
            if max(len(parts.digits), abs(parts.exponent)) > 1000:
                raise ValueError("group key number exceeds admitted bounds")
            if value.kind == "decimal" and (
                len(parts.digits) > 76 or not -76 <= parts.exponent <= 0
            ):
                raise ValueError("group Decimal keys require admitted precision and scale")
    return row_identity(key)


class GroupedComparisonOptions(FrozenModel):
    """Exact tolerances, explicit NULL-key policy and cooperative work limits."""

    absolute_tolerance: Annotated[ExactDecimal, Field(ge=0)] = Decimal(0)
    relative_tolerance: Annotated[ExactDecimal, Field(ge=0)] = Decimal(0)
    null_keys: Literal["reject", "group"] = "reject"
    max_groups: PositiveInt = 100_000
    max_examples: NonNegativeInt = 20
    max_work: PositiveInt = 10_000_000
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def bounded_tolerances(self) -> Self:
        # Check compact exponents before Fraction can allocate a huge power of
        # ten. This covers much more than the admitted Decimal/IEEE data range.
        for value in (self.absolute_tolerance, self.relative_tolerance):
            parts = value.as_tuple()
            assert isinstance(parts.exponent, int)
            if max(max(0, len(parts.digits) + parts.exponent), -parts.exponent) > 1000:
                raise ValueError("tolerances must fit 1000 integer digits and 1000 decimal places")
        return self


class GroupedDifference(FrozenModel):
    """One group; absent, invalid and zero totals have different meanings."""

    key: tuple[ComparisonValue, ...]
    state: Literal["unchanged", "modified", "added", "removed", "not_evaluable"]
    candidate_rows: NonNegativeInt
    expected_rows: NonNegativeInt
    candidate_total: _GroupedNumber | None
    expected_total: _GroupedNumber | None
    absolute_difference: Annotated[_GroupedNumber, Field(ge=0)] | None
    relative_difference: Annotated[_GroupedNumber, Field(ge=0)] | None
    issues: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if not self.key or self.candidate_rows + self.expected_rows == 0:
            raise ValueError("group requires a key and observed rows")
        _key_identity(self.key)
        if len(set(self.issues)) != len(self.issues):
            raise ValueError("group issues must be unique")
        allowed = {
            side + "_" + kind
            for side in ("candidate", "expected")
            for kind in ("null", "nan", "infinity")
        }
        if not set(self.issues) <= allowed:
            raise ValueError("unknown group issue")
        for side, rows, total in (
            ("candidate", self.candidate_rows, self.candidate_total),
            ("expected", self.expected_rows, self.expected_total),
        ):
            invalid = any(issue.startswith(side + "_") for issue in self.issues)
            if (invalid and rows == 0) or ((total is None) != (invalid or rows == 0)):
                raise ValueError("group total must distinguish invalid and absent values")
        comparable = self.state in ("unchanged", "modified")
        if comparable:
            if (
                self.candidate_rows == 0
                or self.expected_rows == 0
                or self.candidate_total is None
                or self.expected_total is None
                or self.issues
            ):
                raise ValueError("comparable groups require two valid observed totals")
            delta = abs(self.candidate_total - self.expected_total)
            relative = delta / abs(self.expected_total) if self.expected_total else None
            if self.absolute_difference != delta or self.relative_difference != relative:
                raise ValueError("group differences contradict exact totals")
        elif self.absolute_difference is not None or self.relative_difference is not None:
            raise ValueError("unpaired or invalid groups have no numeric difference")
        if self.state == "added" and (self.candidate_rows == 0 or self.expected_rows != 0):
            raise ValueError("added group must be present only in candidate")
        if self.state == "removed" and (self.expected_rows == 0 or self.candidate_rows != 0):
            raise ValueError("removed group must be present only in expected")
        if self.state == "not_evaluable" and (
            not self.issues or self.candidate_rows == 0 or self.expected_rows == 0
        ):
            raise ValueError("not_evaluable group requires two present groups and issues")
        if (self.candidate_rows == 0 and self.candidate_total is not None) or (
            self.expected_rows == 0 and self.expected_total is not None
        ):
            raise ValueError("absent groups have no total")
        return self


class GroupedComparisonResult(_ExplicitOutcome, FrozenModel):
    """Descriptive aggregate metrics, never a row-equivalence acceptance gate.

    Ratios are exact Fractions (JSON strings). None denotes an empty denominator.
    Examples are bounded independently of the full summary evaluation.
    """

    _truth_value_guidance = "inspect .complete and the explicit metrics and coverage"

    schema_version: Literal["1.0"] = "1.0"
    aggregation: Literal["sum"] = "sum"
    by: Annotated[tuple[Text, ...], Field(min_length=1)]
    column: Text
    options: GroupedComparisonOptions
    candidate_rows: NonNegativeInt
    expected_rows: NonNegativeInt
    candidate_groups: NonNegativeInt
    expected_groups: NonNegativeInt
    common_groups: NonNegativeInt
    union_groups: NonNegativeInt
    comparable_groups: NonNegativeInt
    modified_groups: NonNegativeInt
    added_groups: NonNegativeInt
    removed_groups: NonNegativeInt
    unavailable_groups: NonNegativeInt
    zero_baseline_groups: NonNegativeInt
    changed_from_zero_groups: NonNegativeInt
    modified_group_proportion: _GroupedNumber | None
    maximum_relative_difference: _GroupedNumber | None
    changed_from_zero_proportion: _GroupedNumber | None
    group_coverage: _GroupedNumber | None
    comparison_coverage: _GroupedNumber | None
    reference_coverage: _GroupedNumber | None
    complete: bool
    examples: tuple[GroupedDifference, ...]
    examples_complete: bool

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(set(self.by)) != len(self.by) or self.column in self.by:
            raise ValueError("group keys must be unique and exclude the numeric column")
        if (
            self.union_groups != self.candidate_groups + self.expected_groups - self.common_groups
            or self.added_groups != self.candidate_groups - self.common_groups
            or self.removed_groups != self.expected_groups - self.common_groups
            or self.comparable_groups + self.unavailable_groups != self.common_groups
            or self.modified_groups > self.comparable_groups
            or self.zero_baseline_groups > self.comparable_groups
            or self.changed_from_zero_groups > min(self.zero_baseline_groups, self.modified_groups)
            or self.comparable_groups
            - self.zero_baseline_groups
            - self.modified_groups
            + self.changed_from_zero_groups
            < 0
            or self.candidate_groups > self.candidate_rows
            or self.expected_groups > self.expected_rows
            or (self.candidate_groups == 0) != (self.candidate_rows == 0)
            or (self.expected_groups == 0) != (self.expected_rows == 0)
            or self.union_groups > self.options.max_groups
        ):
            raise ValueError("inconsistent group counts")
        for observed, numerator, denominator in (
            (self.modified_group_proportion, self.modified_groups, self.comparable_groups),
            (
                self.changed_from_zero_proportion,
                self.changed_from_zero_groups,
                self.zero_baseline_groups,
            ),
            (self.group_coverage, self.common_groups, self.union_groups),
            (self.comparison_coverage, self.comparable_groups, self.union_groups),
            (self.reference_coverage, self.common_groups, self.expected_groups),
        ):
            if observed != (Fraction(numerator, denominator) if denominator else None):
                raise ValueError("metric contradicts its documented denominator")
        nonzero = self.comparable_groups - self.zero_baseline_groups
        if (self.maximum_relative_difference is None) != (nonzero == 0) or (
            self.maximum_relative_difference is not None and self.maximum_relative_difference < 0
        ):
            raise ValueError("maximum relative difference requires nonzero reference support")
        if self.complete != (self.unavailable_groups == 0):
            raise ValueError("completeness contradicts unavailable common groups")
        modified_nonzero = self.modified_groups - self.changed_from_zero_groups
        maximum = self.maximum_relative_difference
        if maximum is not None and (
            (modified_nonzero > 0 and maximum <= Fraction(self.options.relative_tolerance))
            or (
                modified_nonzero == 0
                and self.options.absolute_tolerance == 0
                and maximum > Fraction(self.options.relative_tolerance)
            )
        ):
            raise ValueError(
                "maximum relative difference contradicts modified groups and tolerances"
            )
        if len(self.examples) > min(self.options.max_examples, self.union_groups):
            raise ValueError("group examples exceed declared bounds")
        if self.examples_complete != (len(self.examples) == self.union_groups):
            raise ValueError("example completeness contradicts group coverage")
        if any(len(example.key) != len(self.by) for example in self.examples):
            raise ValueError("example key must match declared grouping columns")
        if len({_key_identity(example.key) for example in self.examples}) != len(self.examples):
            raise ValueError("example keys must be unique")
        signatures: dict[int, tuple[str, str | None, str | None]] = {}
        for example in self.examples:
            for position, value in enumerate(example.key):
                if value.kind == "null":
                    if self.options.null_keys == "reject":
                        raise ValueError("NULL group keys require null_keys='group'")
                    continue
                signature = (value.kind, value.unit, value.timezone)
                if signatures.setdefault(position, signature) != signature:
                    raise ValueError("example key type signatures must match")
            if example.state in ("unchanged", "modified"):
                assert example.expected_total is not None
                assert example.absolute_difference is not None
                threshold = max(
                    Fraction(self.options.absolute_tolerance),
                    Fraction(self.options.relative_tolerance) * abs(example.expected_total),
                )
                if (example.state == "modified") != (example.absolute_difference > threshold):
                    raise ValueError("example state contradicts the declared tolerances")
            if example.relative_difference is not None and (
                self.maximum_relative_difference is None
                or example.relative_difference > self.maximum_relative_difference
            ):
                raise ValueError("example exceeds maximum relative difference")
        comparable = [e for e in self.examples if e.state in ("unchanged", "modified")]
        zero = [e for e in comparable if e.expected_total == 0]
        nonzero_examples = [e for e in comparable if e.expected_total != 0]
        for count, retained in (
            (self.candidate_rows, sum(e.candidate_rows for e in self.examples)),
            (self.expected_rows, sum(e.expected_rows for e in self.examples)),
            (self.candidate_groups, sum(e.candidate_rows > 0 for e in self.examples)),
            (self.expected_groups, sum(e.expected_rows > 0 for e in self.examples)),
            (
                self.common_groups,
                sum(e.candidate_rows > 0 and e.expected_rows > 0 for e in self.examples),
            ),
            (self.comparable_groups, len(comparable)),
            (self.modified_groups, sum(e.state == "modified" for e in comparable)),
            (
                self.comparable_groups - self.modified_groups,
                sum(e.state == "unchanged" for e in comparable),
            ),
            (self.added_groups, sum(e.state == "added" for e in self.examples)),
            (self.removed_groups, sum(e.state == "removed" for e in self.examples)),
            (self.unavailable_groups, sum(e.state == "not_evaluable" for e in self.examples)),
            (self.zero_baseline_groups, len(zero)),
            (self.comparable_groups - self.zero_baseline_groups, len(comparable) - len(zero)),
            (self.changed_from_zero_groups, sum(e.state == "modified" for e in zero)),
            (
                self.modified_groups - self.changed_from_zero_groups,
                sum(e.state == "modified" for e in nonzero_examples),
            ),
            (
                self.comparable_groups
                - self.zero_baseline_groups
                - self.modified_groups
                + self.changed_from_zero_groups,
                sum(e.state == "unchanged" for e in nonzero_examples),
            ),
            (
                self.zero_baseline_groups - self.changed_from_zero_groups,
                sum(e.state == "unchanged" for e in zero),
            ),
        ):
            if retained > count or (self.examples_complete and retained != count):
                raise ValueError("retained group examples contradict summary counts")
        for rows, groups, retained_rows, retained_groups in (
            (
                self.candidate_rows,
                self.candidate_groups,
                sum(e.candidate_rows for e in self.examples),
                sum(e.candidate_rows > 0 for e in self.examples),
            ),
            (
                self.expected_rows,
                self.expected_groups,
                sum(e.expected_rows for e in self.examples),
                sum(e.expected_rows > 0 for e in self.examples),
            ),
        ):
            if rows - retained_rows < groups - retained_groups:
                raise ValueError("remaining groups require at least one row each")
        if len(nonzero_examples) == nonzero:
            maximum = max(
                (e.relative_difference for e in comparable if e.relative_difference is not None),
                default=None,
            )
            if self.maximum_relative_difference != maximum:
                raise ValueError("full group examples contradict maximum relative difference")
        return self
