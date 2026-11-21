"""Input/output grouped features; no peer-engine or expected-output argument."""

from __future__ import annotations

import time
from fractions import Fraction
from typing import TYPE_CHECKING

from equiframe._diff_capture import DiffCaptureOptions
from equiframe.errors import CapabilityError, ExecutionTimeout
from equiframe.grouped import compare_grouped
from equiframe.grouped_types import GroupedComparisonOptions
from equiframe.profile_types import FeatureObservation, FeatureSupport, GroupedProfileFeature

if TYPE_CHECKING:
    from equiframe.profiles import _ProfileContext


def measure_grouped(feature: GroupedProfileFeature, context: _ProfileContext) -> FeatureObservation:
    """Charge one conservative work bound per distinct grouped aggregation.

    Extraction is cached only within the current profile context. Group keys
    identify sums in this calculation; entity labels never become matrix inputs.
    """
    key = feature.model_dump_json(exclude={"name", "metric"})
    summary = context.grouped.get(key)
    output = context.tables[feature.table]
    reference = context.tables[feature.reference_table]
    if summary is None:
        # This exceeds the grouped kernel's counted capture/batch/row/group work.
        # Charge it before evaluation and bound the kernel independently as well.
        bound = 10 + (output.num_rows + reference.num_rows) * (len(feature.by) + 3)
        context.checkpoint(bound)
        timeout = context.options.timeout_seconds
        remaining = None if timeout is None else timeout - (time.perf_counter() - context.started)
        if remaining is not None and remaining <= 0:
            raise ExecutionTimeout("grouped profile timeout before evaluation")
        aliases = tuple(f"key_{index}" for index in range(len(feature.by)))
        left = output.select((*feature.by, feature.column)).rename_columns((*aliases, "measure"))
        right = reference.select((*feature.by, feature.reference_column)).rename_columns(
            (*aliases, "measure")
        )
        if (
            context.grouped_nullable_reference
            == (feature.reference_table, feature.reference_column)
            and right["measure"].null_count
        ):
            # Only the workflow's grouped reference excludes absent amounts.
            # Captures and features such as the input row count keep those rows.
            import pyarrow.compute as pc

            context.checkpoint(reference.num_rows)
            right = right.filter(pc.is_valid(right["measure"]))
        summary = compare_grouped(
            left,
            right,
            by=aliases,
            column="measure",
            options=GroupedComparisonOptions(
                absolute_tolerance=feature.absolute_tolerance,
                relative_tolerance=feature.relative_tolerance,
                null_keys=feature.null_keys,
                max_groups=context.options.max_distinct,
                max_examples=0,
                max_work=bound,
                timeout_seconds=remaining,
            ),
            capture_options=DiffCaptureOptions(
                max_rows=context.options.max_rows,
                max_bytes=context.options.max_artifact_bytes,
            ),
            cancellation=context.cancellation,
        )
        context.checkpoint()
        context.grouped[key] = summary
    if not summary.complete:
        raise CapabilityError("invalid common-group measures cannot become model values")
    if feature.metric == "prop_grupos_suma_modificada":
        numerator, denominator = summary.modified_groups, summary.comparable_groups
    elif feature.metric == "prop_grupos_cambio_desde_cero":
        numerator, denominator = summary.changed_from_zero_groups, summary.zero_baseline_groups
    elif feature.metric == "cobertura_grupos":
        numerator, denominator = summary.common_groups, summary.union_groups
    else:
        ratio = summary.maximum_relative_difference
        numerator, denominator = (0, 0) if ratio is None else (ratio.numerator, ratio.denominator)
    # Float conversion is the explicit boundary for the numeric model matrix.
    # Overflow is caught by the profile extractor as not_evaluable, never imputed.
    value = float(Fraction(numerator, denominator)) if denominator else None
    return FeatureObservation(
        name=feature.name,
        state="available" if denominator else "undefined",
        value=value,
        numerator=numerator,
        denominator=denominator,
        reason=None if denominator else "empty_denominator",
        support=FeatureSupport(rows=output.num_rows),
    )
