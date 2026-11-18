"""Reusable grouped SUM comparison over faithful, bounded native captures."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, Literal

from typing_extensions import TypeAliasType

from equiframe._diff_capture import DiffCaptureOptions, capture_native
from equiframe.comparison_types import ComparisonValue
from equiframe.errors import (
    CapabilityError,
    ExecutionCancelled,
    ExecutionTimeout,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken
from equiframe.grouped_types import (
    GroupedComparisonOptions,
    GroupedComparisonResult,
    GroupedDifference,
)
from equiframe.normalization import logical_signature, physical_value, row_identity
from equiframe.tables import ArrowInput

if TYPE_CHECKING:
    import duckdb
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    GroupedComparisonInput = TypeAliasType(
        "GroupedComparisonInput",
        ArrowInput | pd.DataFrame | pl.DataFrame | pa.Table | duckdb.DuckDBPyRelation,
    )
else:
    # Actual class admission is performed by capture_native without eager imports.
    GroupedComparisonInput = TypeAliasType("GroupedComparisonInput", ArrowInput | object)


@dataclass
class _Group:
    key: tuple[ComparisonValue, ...]
    rows: int = 0
    total: Fraction = Fraction(0)
    issues: set[str] = field(default_factory=set)


class _Budget:
    def __init__(self, options: GroupedComparisonOptions, cancellation: CancellationToken) -> None:
        self.options, self.cancellation = options, cancellation
        self.start = time.perf_counter()
        self.work = 0

    def check(self, cost: int = 1) -> None:
        self.work += cost
        if self.cancellation.cancelled:
            raise ExecutionCancelled("grouped comparison cancelled")
        if self.work > self.options.max_work:
            raise ResourceLimitError("grouped comparison max_work exhausted")
        limit = self.options.timeout_seconds
        if limit is not None and time.perf_counter() - self.start >= limit:
            raise ExecutionTimeout("cooperative grouped comparison timeout")


def _capture(
    value: GroupedComparisonInput, capture: DiffCaptureOptions, budget: _Budget
) -> pa.Table:
    budget.check()
    loaded = capture_native(
        value.table if isinstance(value, ArrowInput) else value,
        capture,
        cancellation=budget.cancellation,
    )
    if loaded.meaningful_index:
        raise CapabilityError("grouped comparison requires meaningful indices as explicit columns")
    budget.check()
    return loaded.table


def _sum_groups(
    table: pa.Table, by: tuple[str, ...], column: str, budget: _Budget
) -> dict[bytes, _Group]:
    groups: dict[bytes, _Group] = {}
    selected = table.select((*by, column))
    for batch in selected.to_batches(max_chunksize=4096):
        budget.check()
        for row in range(batch.num_rows):
            budget.check(len(by) + 1)
            key = tuple(physical_value(batch.column(i)[row]) for i in range(len(by)))
            if any(value.kind in ("nan", "infinity") for value in key):
                raise CapabilityError("grouping keys must not contain NaN or infinity")
            if budget.options.null_keys == "reject" and any(value.kind == "null" for value in key):
                raise CapabilityError("NULL grouping keys require null_keys='group'")
            encoded = row_identity(key)
            group = groups.get(encoded)
            if group is None:
                if len(groups) >= budget.options.max_groups:
                    raise ResourceLimitError("grouped comparison max_groups exhausted")
                group = groups[encoded] = _Group(key)
            group.rows += 1
            value = batch.column(len(by))[row].as_py()
            if value is None:
                group.issues.add("null")
            elif isinstance(value, float) and not (-float("inf") < value < float("inf")):
                group.issues.add("nan" if value != value else "infinity")
            else:
                group.total += Fraction(value)
    budget.check()
    return groups


def _ratio(numerator: int, denominator: int) -> Fraction | None:
    return Fraction(numerator, denominator) if denominator else None


def _key_signature(table: pa.Table, name: str) -> tuple[object, ...]:
    dtype = table.schema.field(name).type
    signature = logical_signature(dtype)
    # Capture engines use different Arrow string buffer layouts. Their scalar
    # labels share one string family, while date units are retained in keys.
    return (*signature, str(dtype)) if signature[0] == "date" else signature


def _check_decimal(table: pa.Table, name: str) -> None:
    dtype = table.schema.field(name).type
    signature = logical_signature(dtype)
    if signature[0] == "decimal" and not (0 <= dtype.scale <= dtype.precision <= 76):
        raise CapabilityError(
            "grouped comparison requires Decimal scale between zero and precision"
        )


def compare_grouped(
    candidate: GroupedComparisonInput,
    expected: GroupedComparisonInput,
    *,
    by: Sequence[str],
    column: str,
    options: GroupedComparisonOptions | None = None,
    capture_options: DiffCaptureOptions | None = None,
    cancellation: CancellationToken | None = None,
) -> GroupedComparisonResult:
    """Compare exact sums for arbitrary group keys and a numeric column.

    The right side is the reference. A common, valid group is modified when
    abs(candidate_sum - expected_sum) > max(absolute_tolerance,
    relative_tolerance * abs(expected_sum)). Missing/NaN/infinite numeric values
    invalidate their group rather than becoming zero or being skipped. NULL
    keys require explicit opt-in. Keys retain their physical type signatures.

    Modified proportion uses comparable common groups. Relative differences use
    nonzero reference sums; changes from zero are counted separately. Coverage
    reports common/union, comparable/union and common/reference groups. Empty
    denominators are None. Fractions preserve exact integer, Decimal and finite
    IEEE values and serialize as JSON strings. Examples never limit evaluation.

    This aggregate description is independent of diff/equivalence, profiles,
    detectors and rules. Equal sums do not prove row-level equivalence. Capture,
    capability, cancellation and resource errors raise without a partial result.
    Limits are cooperative, including native first-fetch limitations.
    """
    checked = GroupedComparisonOptions.model_validate(
        GroupedComparisonOptions() if options is None else options
    )
    capture = DiffCaptureOptions.model_validate(
        DiffCaptureOptions() if capture_options is None else capture_options
    )
    if isinstance(by, (str, bytes)) or not isinstance(by, Sequence):
        raise ValueError("by must be a nonempty sequence of unique column names")
    keys = tuple(by)
    if (
        not keys
        or any(not isinstance(key, str) or not key.strip() or key != key.strip() for key in keys)
        or len(set(keys)) != len(keys)
        or not isinstance(column, str)
        or not column.strip()
        or column != column.strip()
        or column in keys
    ):
        raise ValueError("group keys must be unique, nonempty and exclude the numeric column")
    budget = _Budget(checked, CancellationToken() if cancellation is None else cancellation)
    left = _capture(candidate, capture, budget)
    right = _capture(expected, capture, budget)
    for table in (left, right):
        if not set((*keys, column)) <= set(table.column_names):
            raise CapabilityError("grouping or numeric column is missing")
        for name in (*keys, column):
            _check_decimal(table, name)
        if logical_signature(table.schema.field(column).type)[0] not in (
            "integer",
            "float",
            "decimal",
        ):
            raise CapabilityError("grouped sum requires an integer, float or Decimal column")
    if any(_key_signature(left, key) != _key_signature(right, key) for key in keys):
        raise CapabilityError("grouping key type signatures must match exactly")
    lhs = _sum_groups(left, keys, column, budget)
    rhs = _sum_groups(right, keys, column, budget)
    # Retain reference first-observed order, followed by candidate-only groups.
    common = comparable = modified = zeros = from_zero = 0
    maximum: Fraction | None = None
    examples: list[GroupedDifference] = []
    absolute, relative = Fraction(checked.absolute_tolerance), Fraction(checked.relative_tolerance)
    union = len(lhs.keys() | rhs.keys())
    if union > checked.max_groups:
        raise ResourceLimitError("grouped comparison union exceeds max_groups")
    for encoded in (*rhs, *(key for key in lhs if key not in rhs)):
        budget.check()
        a, b = lhs.get(encoded), rhs.get(encoded)
        issues = tuple(
            side + "_" + issue
            for side, group in (("candidate", a), ("expected", b))
            if group is not None
            for issue in sorted(group.issues)
        )
        delta = rel = None
        state: Literal["unchanged", "modified", "added", "removed", "not_evaluable"]
        if a is None:
            state = "removed"
        elif b is None:
            state = "added"
        else:
            common += 1
            if issues:
                state = "not_evaluable"
            else:
                comparable += 1
                delta = abs(a.total - b.total)
                changed = delta > max(absolute, relative * abs(b.total))
                state = "modified" if changed else "unchanged"
                modified += changed
                if b.total == 0:
                    zeros += 1
                    from_zero += changed
                else:
                    rel = delta / abs(b.total)
                    maximum = rel if maximum is None else max(maximum, rel)
        if len(examples) < checked.max_examples:
            group = a if a is not None else b
            assert group is not None
            examples.append(
                GroupedDifference(
                    key=group.key,
                    state=state,
                    candidate_rows=a.rows if a is not None else 0,
                    expected_rows=b.rows if b is not None else 0,
                    candidate_total=a.total if a is not None and not a.issues else None,
                    expected_total=b.total if b is not None and not b.issues else None,
                    absolute_difference=delta,
                    relative_difference=rel,
                    issues=issues,
                )
            )
    budget.check()
    return GroupedComparisonResult(
        by=keys,
        column=column,
        options=checked,
        candidate_rows=left.num_rows,
        expected_rows=right.num_rows,
        candidate_groups=len(lhs),
        expected_groups=len(rhs),
        common_groups=common,
        union_groups=union,
        comparable_groups=comparable,
        modified_groups=modified,
        added_groups=len(lhs) - common,
        removed_groups=len(rhs) - common,
        unavailable_groups=common - comparable,
        zero_baseline_groups=zeros,
        changed_from_zero_groups=from_zero,
        modified_group_proportion=_ratio(modified, comparable),
        maximum_relative_difference=maximum,
        changed_from_zero_proportion=_ratio(from_zero, zeros),
        group_coverage=_ratio(common, union),
        comparison_coverage=_ratio(comparable, union),
        reference_coverage=_ratio(common, len(rhs)),
        complete=common == comparable,
        examples=tuple(examples),
        examples_complete=len(examples) == union,
    )
