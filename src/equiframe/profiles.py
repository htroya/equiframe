"""Profiles of one captured execution, independent of rules, labels and other engines."""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from equiframe._document_io import read_document as _read_document
from equiframe._document_io import write_document as _write_document
from equiframe._regular_io import local_output_directory
from equiframe.comparison_types import ComparisonValue
from equiframe.contracts import ColumnSpec, Family, TimestampPolicy
from equiframe.errors import (
    ArtifactIntegrityError,
    CapabilityError,
    ExecutionCancelled,
    ExecutionTimeout,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken
from equiframe.execution_types import ExecutionResult
from equiframe.local import local_path
from equiframe.normalization import identity, normalize, number, physical_value
from equiframe.profile_types import (
    ConversionReceipt,
    FeatureObservation,
    FeatureSupport,
    ProfileFeature,
    ProfileMetadata,
    ProfileMetric,
    ProfileOptions,
    ProfileResult,
    ProfileSpec,
    ProfileVector,
    profile_digest,
    profile_spec_fingerprint,
)
from equiframe.tables import read_table
from equiframe.values import DateValue, TimestampValue

if TYPE_CHECKING:
    import pyarrow as pa

_FAMILIES: dict[ProfileMetric, tuple[Family, ...]] = {
    "log_filas": ("nulls_types", "joins", "duplicates_order", "aggregations", "dates"),
    "razon_salida_entrada": ("joins", "duplicates_order", "aggregations"),
    "tasa_nulos": ("nulls_types", "joins", "aggregations"),
    "tasa_nan": ("nulls_types",),
    "prop_duplicados": ("duplicates_order", "joins"),
    "cardinalidad_rel": ("joins", "duplicates_order", "aggregations"),
    "expansion_union": ("joins",),
    "claves_sin_pareja": ("joins",),
    "conversiones_fallidas": ("nulls_types", "dates"),
    "fechas_invalidas": ("dates",),
}


class _ProfileContext:
    def __init__(self, options: ProfileOptions, cancellation: CancellationToken) -> None:
        self.options, self.cancellation = options, cancellation
        self.started = time.perf_counter()
        self.work = 0
        self.tables: dict[str, pa.Table] = {}
        self.conversions: dict[str, ConversionReceipt] = {}
        self.hashes: dict[str, str] = {}
        self.output_sha256 = ""

    def checkpoint(self, cost: int = 1) -> None:
        self.work += cost
        if self.cancellation.cancelled:
            raise ExecutionCancelled("profile cancelled")
        if self.work > self.options.max_work:
            raise ResourceLimitError("profile max_work exhausted")
        limit = self.options.timeout_seconds
        if limit is not None and time.perf_counter() - self.started >= limit:
            raise ExecutionTimeout("cooperative profile timeout")

    def load(self, execution: ExecutionResult) -> None:
        self.checkpoint()
        if execution.state != "completed" or execution.output is None:
            raise CapabilityError("profile requires a completed captured execution")
        self.output_sha256 = execution.output.data.sha256
        total_bytes = actual_bytes = decoded_bytes = rows = 0
        for artifact in (*execution.inputs, execution.output):
            self.checkpoint()
            refs = (artifact.data,) + ((artifact.index,) if artifact.index else ())
            for ref in refs:
                total_bytes += ref.size_bytes
                actual_bytes += local_path(ref).stat().st_size
                if max(total_bytes, actual_bytes) > self.options.max_artifact_bytes:
                    raise ResourceLimitError("profile max_artifact_bytes exhausted")
                table = read_table(ref)
                decoded_bytes += table.nbytes
                rows += table.num_rows
                if decoded_bytes > self.options.max_artifact_bytes:
                    raise ResourceLimitError("profile decoded bytes exceeded")
                if rows > self.options.max_rows:
                    raise ResourceLimitError("profile max_rows exhausted")
                columns = artifact.columns if ref == artifact.data else artifact.index_columns
                if table.num_rows != artifact.row_count or tuple(table.column_names) != tuple(
                    c.name for c in columns
                ):
                    raise ArtifactIntegrityError("captured rows/columns differ from artifact")
                import pyarrow as pa
                import pyarrow.compute as pc

                for column in columns:
                    self.checkpoint()
                    array = table[column.name]
                    nan = (
                        int(pc.sum(pc.is_nan(array)).as_py() or 0)
                        if (pa.types.is_floating(array.type))
                        else 0
                    )
                    if (str(array.type), array.null_count, nan) != (
                        column.arrow_type,
                        column.null_count,
                        column.nan_count,
                    ):
                        raise ArtifactIntegrityError("captured physical metadata mismatch")
                if ref == artifact.data:
                    self.tables[artifact.name] = table
                    self.hashes[artifact.name] = ref.sha256
        self.checkpoint()

    def rows(self, table: str, columns: tuple[str, ...]) -> Iterator[tuple[ComparisonValue, ...]]:
        observed = self.tables[table]
        if not set(columns) <= set(observed.column_names):
            raise CapabilityError("profile column missing from captured table")
        for i in range(observed.num_rows):
            self.checkpoint(len(columns))
            yield tuple(physical_value(observed[c][i]) for c in columns)

    def insert(self, keys: set[tuple[object, ...]], key: tuple[object, ...]) -> None:
        keys.add(key)
        if len(keys) > self.options.max_distinct:
            raise ResourceLimitError("profile max_distinct exhausted")


def _validate_references(execution: ExecutionResult, spec: ProfileSpec) -> None:
    contract = execution.plan.contract
    if contract.family != spec.family:
        raise ValueError("profile family differs from execution contract")
    tables = {t.name: t for t in (*contract.inputs, contract.output)}
    inputs = {t.name for t in contract.inputs}
    for feature in spec.features:
        for name, columns in (
            (feature.table, feature.columns),
            (feature.right_table, feature.right_columns),
            (feature.denominator_table, ()),
        ):
            if name is not None and (
                name not in tables
                or not set(columns) <= {c.name for c in tables[name].schema_spec.columns}
            ):
                raise ValueError("profile references undeclared tables/columns")
        if (
            feature.metric
            in (
                "log_filas",
                "razon_salida_entrada",
                "expansion_union",
                "tasa_nulos",
                "tasa_nan",
                "prop_duplicados",
                "cardinalidad_rel",
            )
            and feature.table != contract.output.name
        ):
            raise ValueError("output formula must reference the captured output")
        if feature.denominator_table is not None and feature.denominator_table not in inputs:
            raise ValueError("row ratio denominator must be a captured input")
        if feature.metric == "claves_sin_pareja" and (
            feature.table not in inputs or feature.right_table not in inputs
        ):
            raise ValueError("unmatched rows require two captured inputs")
        if feature.metric == "conversiones_fallidas" and feature.table not in inputs:
            raise ValueError("conversion attempts must refer to captured source values")


def _ratio(
    feature: ProfileFeature, numerator: int, denominator: int, support: FeatureSupport
) -> FeatureObservation:
    return FeatureObservation(
        name=feature.name,
        state="available" if denominator else "undefined",
        value=numerator / denominator if denominator else None,
        numerator=numerator,
        denominator=denominator,
        reason=None if denominator else "empty_denominator",
        support=support,
    )


def _converted(value: ComparisonValue, target: ColumnSpec) -> ComparisonValue:
    """Parse temporal observations without changing the captured values."""
    kind = target.logical_type.kind
    if value.kind == kind:
        return value
    text = value.value
    if text is None:
        raise ValueError("non-finite or absent source")
    if kind == "date" and value.kind == "string":
        parsed = DateValue(value=text)
        return ComparisonValue(
            kind="date",
            unit="day",
            value=str(date.fromisoformat(parsed.value).toordinal() - date(1970, 1, 1).toordinal()),
        )
    if kind == "timestamp" and value.kind == "string":
        policy = target.temporal_policy
        if not (isinstance(policy, TimestampPolicy)):
            raise AssertionError("Internal invariant check failed.")
        parsed_stamp = TimestampValue(value=text)
        point = parsed_stamp.nanoseconds(instant=parsed_stamp.has_offset) - (
            date(1970, 1, 1).toordinal() * 86400 * 10**9
        )
        return ComparisonValue(
            kind="timestamp",
            unit="ns",
            value=str(point),
            timezone=(policy.timezone or "UTC") if parsed_stamp.has_offset else None,
        )
    raise ValueError("unsupported scalar conversion")


def _measure(feature: ProfileFeature, context: _ProfileContext) -> FeatureObservation:
    table = context.tables[feature.table]
    count = table.num_rows
    metric = feature.metric
    if metric == "conversiones_fallidas":
        receipt = context.conversions.get(feature.name)
        if receipt is None:
            raise CapabilityError("conversion receipt required; output NULL is insufficient")
        if (
            receipt.source_sha256 != context.hashes[feature.table]
            or receipt.source_column != feature.columns[0]
            or receipt.output_sha256 != context.output_sha256
            or receipt.target != feature.target
        ):
            raise ArtifactIntegrityError("conversion receipt does not match captured execution")
        missing = empty = nan = zeros = 0
        for index in receipt.attempted_rows:
            context.checkpoint()
            if index >= count:
                raise ArtifactIntegrityError("conversion attempt outside source rows")
            value = physical_value(table[feature.columns[0]][index])
            if value.kind == "null":
                raise ArtifactIntegrityError("conversion denominator must exclude absent values")
            empty += value.kind == "string" and value.value == ""
            nan += value.kind == "nan"
            zeros += value.kind in ("integer", "decimal", "float") and number(value) == 0
        missing = table[feature.columns[0]].null_count
        return _ratio(
            feature,
            len(receipt.failed_rows),
            len(receipt.attempted_rows),
            FeatureSupport(rows=count, missing=missing, empty_strings=empty, nan=nan, zeros=zeros),
        )
    if metric == "log_filas":
        return FeatureObservation(
            name=feature.name,
            state="available",
            value=math.log1p(count),
            numerator=count,
            support=FeatureSupport(rows=count),
        )
    if metric in ("razon_salida_entrada", "expansion_union"):
        if not (feature.denominator_table is not None):
            raise AssertionError("Internal invariant check failed.")
        return _ratio(
            feature,
            count,
            context.tables[feature.denominator_table].num_rows,
            FeatureSupport(rows=count),
        )
    if metric == "claves_sin_pareja":
        if not (feature.right_table is not None):
            raise AssertionError("Internal invariant check failed.")
        left_types = tuple(table.schema.field(c).type for c in feature.columns)
        right_types = tuple(
            context.tables[feature.right_table].schema.field(c).type for c in feature.right_columns
        )
        if left_types != right_types:
            raise CapabilityError("join key physical types differ; no implicit conversion")
        right_keys: set[tuple[object, ...]] = set()
        for row in context.rows(feature.right_table, feature.right_columns):
            if any(
                v.kind == "nan" or (v.kind == "null" and feature.null_matches == "never")
                for v in row
            ):
                continue
            context.insert(right_keys, tuple(identity(v) for v in row))
        unmatched = incomplete = 0
        for row in context.rows(feature.table, feature.columns):
            incomplete += any(v.kind in ("null", "nan") for v in row)
            unmatchable = any(
                v.kind == "nan" or (v.kind == "null" and feature.null_matches == "never")
                for v in row
            )
            unmatched += unmatchable or tuple(identity(v) for v in row) not in right_keys
        return _ratio(
            feature, unmatched, count, FeatureSupport(rows=count, incomplete_keys=incomplete)
        )
    if metric == "prop_duplicados":
        keys: set[tuple[object, ...]] = set()
        complete = 0
        for row in context.rows(feature.table, feature.columns):
            if any(v.kind in ("null", "nan") for v in row):
                continue
            complete += 1
            context.insert(keys, tuple(identity(v) for v in row))
        return _ratio(
            feature,
            complete - len(keys),
            complete,
            FeatureSupport(rows=count, incomplete_keys=count - complete),
        )
    if metric == "tasa_nan":
        import pyarrow as pa

        dtype = table.schema.field(feature.columns[0]).type
        if not (
            pa.types.is_integer(dtype) or pa.types.is_floating(dtype) or pa.types.is_decimal(dtype)
        ):
            return FeatureObservation(
                name=feature.name,
                state="not_applicable",
                reason="non_numeric_column",
                support=FeatureSupport(rows=count),
            )
    missing = nan = empty = zero = failed = present = 0
    distinct: set[tuple[object, ...]] = set()
    for (value,) in context.rows(feature.table, feature.columns):
        missing += value.kind == "null"
        nan += value.kind == "nan"
        empty += value.kind == "string" and value.value == ""
        zero += value.kind in ("integer", "decimal", "float") and number(value) == 0
        if metric == "cardinalidad_rel" and value.kind not in ("null", "nan"):
            context.insert(distinct, identity(value))
        if metric == "fechas_invalidas" and value.kind != "null":
            present += 1
            if not (feature.target is not None):
                raise AssertionError("Internal invariant check failed.")
            try:
                converted = _converted(value, feature.target)
                _, issues = normalize(converted, feature.target)
                failed += bool(issues)
            except (ValueError, OverflowError):
                failed += 1
    support = FeatureSupport(rows=count, missing=missing, nan=nan, empty_strings=empty, zeros=zero)
    if metric == "tasa_nulos":
        return _ratio(feature, missing, count, support)
    if metric == "tasa_nan":
        return _ratio(feature, nan, count, support)
    if metric == "cardinalidad_rel":
        return _ratio(feature, len(distinct), count - missing - nan, support)
    return _ratio(feature, failed, present, support)


def profile_execution(
    execution: ExecutionResult,
    *,
    spec: ProfileSpec,
    options: ProfileOptions | None = None,
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
    conversions: tuple[ConversionReceipt, ...] = (),
) -> ProfileResult:
    """Materialize the section 3.6 formulas with exact counts and explicit unavailable states."""
    execution = ExecutionResult.model_validate(execution)
    spec = ProfileSpec.model_validate(spec)
    options = ProfileOptions.model_validate(ProfileOptions() if options is None else options)
    _validate_references(execution, spec)
    conversions = tuple(ConversionReceipt.model_validate(c) for c in conversions)
    if len({c.feature for c in conversions}) != len(conversions) or not {
        c.feature for c in conversions
    } <= {f.name for f in spec.features if f.metric == "conversiones_fallidas"}:
        raise ValueError("conversion receipts must uniquely reference conversion features")
    identifier = "profile_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    context = _ProfileContext(options, cancellation or CancellationToken())
    context.conversions = {c.feature: c for c in conversions}
    failure: str | None = None
    try:
        context.load(execution)
    except Exception as error:
        failure = type(error).__name__ + ": captured execution unavailable"
    observations: list[FeatureObservation] = []
    for feature in spec.features:
        try:
            if failure:
                observation = FeatureObservation(
                    name=feature.name, state="not_evaluable", reason=failure
                )
            elif spec.family not in _FAMILIES[feature.metric]:
                observation = FeatureObservation(
                    name=feature.name, state="not_applicable", reason="family_not_applicable"
                )
            else:
                context.checkpoint()
                observation = _measure(feature, context)
        except Exception as error:
            observation = FeatureObservation(
                name=feature.name,
                state="not_evaluable",
                reason=type(error).__name__ + ": measurement unavailable",
            )
        observations.append(observation)
    result = ProfileResult(
        metadata=ProfileMetadata(
            profile_id=identifier,
            run_id=execution.run_id,
            execution_id=execution.execution_id,
            contract_sha256=execution.contract_sha256,
            execution_sha256=profile_digest(execution.model_dump(mode="json")),
            conversion_receipts=conversions,
            artifacts=tuple(
                ref
                for a in (*execution.inputs, *((execution.output,) if execution.output else ()))
                for ref in (a.data, *((a.index,) if a.index else ()))
            ),
        ),
        vector=ProfileVector(
            spec=spec, spec_sha256=profile_spec_fingerprint(spec), observations=tuple(observations)
        ),
        options=options,
        complete=all(o.state != "not_evaluable" for o in observations),
        elapsed_seconds=time.perf_counter() - context.started,
        work_units=context.work,
    )
    _write_document(directory / "profile.json", result.model_dump_json().encode("utf-8"))
    return result


def read_profile(path: Path) -> ProfileResult:
    """Validate saved measurements; artifacts remain available for independent verification."""
    return ProfileResult.model_validate_json(_read_document(path))
