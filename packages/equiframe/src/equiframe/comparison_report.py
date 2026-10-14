"""Build and publish conservative comparison views without rerunning sources."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Literal, cast

from equiframe._regular_io import local_input_path, local_output_directory, open_regular_file
from equiframe.comparison_types import ComparisonDifference, ComparisonResult, ComparisonValue
from equiframe.contracts import ColumnKeyScope
from equiframe.diff_contracts import DiffContract
from equiframe.errors import ArtifactIntegrityError, ArtifactIOError, ResourceLimitError
from equiframe.evidence import canonical_bytes
from equiframe.report_types import (
    ComparisonReport,
    CountPrecision,
    ReportCount,
    ReportEvidenceManifest,
    ReportOptions,
    ReportPolicy,
    ReportPublicationManifest,
    ReportValue,
    ReportViewPolicy,
    ReportWitness,
)

_REASONS = {
    "cell_value": "Aligned values differ under the declared policy",
    "row_multiplicity": "Unmatched row occurrences; multiplicity is preserved",
    "missing_column": "A declared column is missing",
    "additional_column": "An undeclared column is present",
    "column_order": "Physical column order violates the declared policy",
    "logical_type": "An observed type violates the declared type policy",
    "order_violation": "Rows violate the declared sort order",
    "order_tie": "A forbidden ordering tie was observed",
    "nan_forbidden": "NaN violates the declared policy",
    "null_forbidden": "NULL violates the declared policy",
    "integer_range": "An integer lies outside the declared range",
    "float_precision": "A value violates declared floating-point precision",
    "decimal_precision": "A Decimal violates the declared precision or scale",
    "date_granularity": "A date violates the declared granularity",
    "timestamp_granularity": "A timestamp violates the declared granularity",
    "temporal_interval": "A temporal value lies outside the declared interval",
    "allowed_values": "A value is outside the declared allowed values",
    "duplicate_key": "Duplicate key or row occurrences violate the contract",
    "incomplete_key": "An incomplete key violates the contract",
    "contract_violation": "A declared contract condition was violated",
    "resource_exhausted": "Evaluation stopped at a resource budget",
    "cancelled": "Evaluation was cancelled",
    "timeout": "Evaluation exceeded its cooperative timeout",
    "invalid_artifact": "An input artifact failed integrity verification",
    "unsupported_capability": "The requested capability is not supported",
    "missing_optional_dependency": "A required optional dependency is unavailable",
    "evaluation_failed": "Evaluation failed; inspect the original private diagnostic",
    "invalid_expected": "The expected reference violates the declared contract",
}


def _code(code: str) -> str:
    if code in _REASONS:
        return code
    if code.startswith("duplicate_"):
        return "duplicate_key"
    if code.startswith("incomplete_"):
        return "incomplete_key"
    return "contract_violation"


def _bounded(value: str, options: ReportOptions) -> str:
    return value if len(value) <= options.max_value_chars else "[omitted]"


def _column(name: str, result: ComparisonResult, options: ReportOptions) -> str:
    if options.include_metadata:
        return _bounded(name, options)
    names = [column.name for column in result.spec.contract.output.schema_spec.columns]
    return f"column_{names.index(name) + 1}" if name in names else "[undeclared column]"


def _representation(value: ComparisonValue) -> str:
    if value.kind == "null":
        return "NULL"
    if value.kind == "nan":
        return "NaN"
    if value.kind == "decimal":
        return f"Decimal({json.dumps(value.value)})"
    if value.kind in ("date", "timestamp"):
        return (
            f"{value.kind}(epoch={value.value}, unit={value.unit}, "
            f"timezone={json.dumps(value.timezone)})"
        )
    if value.kind == "string":
        return json.dumps(value.value, ensure_ascii=False)
    if value.kind == "infinity":
        return f"{value.value} infinity"
    return f"{value.kind}({value.value})"


def _value(
    value: ComparisonValue,
    name: str | None,
    side: Literal["left", "right"],
    result: ComparisonResult,
    options: ReportOptions,
) -> ReportValue:
    source = result.left if side == "left" else result.right
    native_type = physical_type = None
    if name is not None and source is not None:
        physical_type = dict(source.observed_schema).get(name)
        if source.table:
            native_type = next(
                (column.engine_type for column in source.table.columns if column.name == name),
                None,
            )
    if name is not None and source is not None and name not in dict(source.observed_schema):
        # The kernel's aligned tuple may contain a NULL placeholder for a missing
        # column. It is not an observed NULL scalar in the original table.
        return ReportValue(disclosure="omitted", kind="absent_column", representation="[omitted]")
    # Producer-supplied dtype text is metadata too; it can contain free-form text.
    if not options.include_metadata:
        native_type = physical_type = None
    else:
        native_type = _bounded(native_type, options) if native_type is not None else None
        physical_type = _bounded(physical_type, options) if physical_type is not None else None
    withheld = not options.include_values or name in options.redact_columns
    if name is None and options.redact_columns:
        withheld = True  # Ambiguous contract witnesses cannot bypass column redaction.
    representation = _representation(value)
    disclosure: Literal["visible", "redacted", "omitted"] = (
        "redacted"
        if withheld
        else "omitted"
        if len(representation) > options.max_value_chars
        else "visible"
    )
    return ReportValue(
        disclosure=disclosure,
        kind=value.kind,
        representation=representation if disclosure == "visible" else f"[{disclosure}]",
        native_type=native_type,
        physical_type=physical_type,
        value=value if disclosure == "visible" else None,
    )


def _witness(
    difference: ComparisonDifference, result: ComparisonResult, options: ReportOptions
) -> ReportWitness:
    schema = result.spec.contract.output.schema_spec
    names = tuple(column.name for column in schema.columns)
    key = next((key for key in schema.keys if key.name == result.selected_key), None)

    def key_columns(key: object) -> tuple[str, ...]:
        from equiframe.contracts import KeySpec

        if not (isinstance(key, KeySpec)):
            raise AssertionError("Internal invariant check failed.")
        return (
            (*key.scope.columns, *key.columns)
            if isinstance(key.scope, ColumnKeyScope)
            else key.columns
        )

    key_names = key_columns(key) if key else ()
    violation_columns: tuple[str, ...] | None = None
    for declared_key in schema.keys:
        if difference.code in {
            f"{prefix}_{phase}_{name}"
            for prefix, name in (
                ("duplicate", "key_" + declared_key.name),
                ("incomplete", declared_key.name),
            )
            for phase in ("raw", "normalized")
        }:
            violation_columns = key_columns(declared_key)
            break

    def values(
        raw: tuple[ComparisonValue, ...], side: Literal["left", "right"]
    ) -> tuple[ReportValue, ...]:
        columns = (
            violation_columns
            if violation_columns is not None and len(raw) == len(violation_columns)
            else (difference.column,)
            if difference.column is not None and len(raw) == 1
            else names
            if len(raw) == len(names)
            else ()
        )
        return tuple(
            _value(value, columns[index] if columns else None, side, result, options)
            for index, value in enumerate(raw)
        )

    code = _code(difference.code)
    return ReportWitness(
        category=difference.category,
        code=code,
        reason=_REASONS[code],
        position=difference.position if difference.side != "right" else None,
        other_position=difference.position
        if difference.side == "right"
        else difference.other_position,
        column=_column(difference.column, result, options)
        if difference.column is not None
        else None,
        columns=tuple(_column(name, result, options) for name in (violation_columns or names)),
        key_columns=tuple(_column(name, result, options) for name in key_names),
        key=tuple(
            _value(
                value, key_names[index] if index < len(key_names) else None, "left", result, options
            )
            for index, value in enumerate(difference.key)
        ),
        candidate=values(difference.left, "left"),
        reference=values(difference.right, "right"),
        candidate_count=difference.left_count if difference.category == "content" else None,
        reference_count=difference.right_count if difference.category == "content" else None,
    )


def _policies(
    result: ComparisonResult, options: ReportOptions, declaration: DiffContract | None
) -> tuple[ReportPolicy, ...]:
    schema = result.spec.contract.output.schema_spec
    policies = [
        ReportPolicy(name="column_order", value=result.spec.policy.column_order),
        ReportPolicy(name="physical_types", value=result.spec.policy.physical_types),
        ReportPolicy(name="index", value=result.spec.policy.index),
        ReportPolicy(name="multiplicity", value=schema.multiplicity),
        ReportPolicy(name="row_order", value=schema.order.kind),
        ReportPolicy(name="alignment", value=result.strategy),
        ReportPolicy(
            name="key_validation",
            value="globally validated"
            if result.strategy == "key"
            else "no validated key alignment",
        ),
    ]
    from equiframe.contracts import SignificantOrder

    if isinstance(schema.order, SignificantOrder):
        order = {
            "ties": schema.order.ties,
            "by": [
                {
                    "column": _column(item.column, result, options),
                    "direction": item.direction,
                    "nulls": item.nulls,
                }
                for item in schema.order.by
            ],
        }
        policies.append(
            ReportPolicy(name="order_policy", value=_bounded(json.dumps(order), options))
        )
    for index, key in enumerate(schema.keys):
        policies.append(
            ReportPolicy(
                name=f"declared_key_{index + 1}",
                value=_bounded(
                    json.dumps(
                        {
                            "columns": [_column(name, result, options) for name in key.columns],
                            "scope_columns": [
                                _column(name, result, options) for name in key.scope.columns
                            ]
                            if isinstance(key.scope, ColumnKeyScope)
                            else [],
                            "unique": key.unique,
                            "incomplete": key.incomplete,
                            "selected": key.name == result.selected_key,
                        }
                    ),
                    options,
                ),
            )
        )
    for column in schema.columns:
        name = _column(column.name, result, options)
        dtype = column.logical_type.model_dump(mode="json")
        if not options.include_metadata and "timezone" in dtype:
            dtype["timezone"] = "[redacted]"
        settings: dict[str, object] = {
            "logical_type": dtype,
            "nullable": column.nullable,
            "null_policy": column.null_policy.model_dump(mode="json", exclude={"justification"}),
            "allowed_values_count": len(column.allowed_values),
        }
        if column.nan_policy:
            settings["nan_policy"] = column.nan_policy.model_dump(
                mode="json", exclude={"justification"}
            )
        if column.numeric_policy:
            numeric = column.numeric_policy.model_dump(
                mode="json",
                exclude={"rounding_justification": True, "tolerance": {"justification"}},
            )
            if isinstance(numeric.get("tolerance"), dict) and not options.include_metadata:
                numeric["tolerance"]["unit"] = "[redacted]"
            if not options.include_metadata:
                numeric["unit"] = "[redacted]"
            settings["numeric_policy"] = numeric
        if column.temporal_policy:
            temporal = column.temporal_policy.model_dump(mode="json")
            # Bounds are contract values. Disclose them only with value opt-in.
            if not options.include_values or column.name in options.redact_columns:
                for field in ("lower", "upper"):
                    if field in temporal and temporal[field] is not None:
                        temporal[field] = "[redacted]"
            if not options.include_metadata and "timezone" in temporal:
                temporal["timezone"] = "[redacted]"
            settings["temporal_policy"] = temporal
        policies.append(
            ReportPolicy(
                name=name,
                value=_bounded(json.dumps(settings, ensure_ascii=False, sort_keys=True), options),
            )
        )
    if declaration is not None:
        origins = Counter(item.origin for item in declaration.provenance)
        policies.append(
            ReportPolicy(
                name="declared_policy_origins", value=json.dumps(dict(sorted(origins.items())))
            )
        )
    return tuple(policies)


def _derived(differences: tuple[ComparisonDifference, ...], strategy: str) -> tuple[int, int, int]:
    added = removed = 0
    modified: set[tuple[int | None, int | None]] = set()
    for difference in differences:
        if difference.category != "content":
            continue
        if difference.code == "cell_value" and strategy in ("key", "sequence"):
            modified.add((difference.position, difference.other_position))
        if difference.code == "row_multiplicity":
            added += max(0, difference.left_count - difference.right_count)
            removed += max(0, difference.right_count - difference.left_count)
    return added, removed, len(modified)


def comparison_report(
    result: ComparisonResult,
    *,
    options: ReportOptions | None = None,
    evidence_root: Path | None = None,
    declaration: DiffContract | None = None,
) -> ComparisonReport:
    """Build one detached, privacy-filtered report of an existing comparison.

    The default reads only the validated in-memory result and its examples.
    An explicit evidence_root allows bounded inspection of the comparison's own
    manifest and differences. It never reads original inputs or executes code.
    Inspection failure is explicit; budget exhaustion records unmet evidence
    requirements without changing the comparison verdict.
    """
    result = ComparisonResult.model_validate(result)
    options = ReportOptions.model_validate(ReportOptions() if options is None else options)
    names = {column.name for column in result.spec.contract.output.schema_spec.columns}
    if not set(options.redact_columns) <= names:
        raise ValueError("redacted columns must exist in the declared output schema")
    if declaration is not None:
        declaration = DiffContract.model_validate(declaration)
        if declaration.spec != result.spec or declaration.reference != result.reference:
            raise ArtifactIntegrityError("policy provenance does not match the comparison")
    differences = result.examples
    inspected = False
    unmet: list[str] = []
    added, removed, modified = _derived(differences, result.strategy)
    code_counts = Counter(_code(item.code) for item in differences)
    if evidence_root is not None:
        from equiframe._report_io import inspect_evidence

        try:
            inspection = inspect_evidence(
                result,
                evidence_root,
                max_bytes=options.max_evidence_bytes,
                max_records=options.max_records,
                max_examples=options.max_examples,
            )
        except ResourceLimitError:
            unmet.append("evidence_verification_budget_exceeded")
        else:
            inspected = True
            differences = inspection.examples
            added = inspection.candidate_excess
            removed = inspection.reference_excess
            modified = inspection.modified or 0
            code_counts = Counter()
            for code, count in inspection.code_counts:
                code_counts[_code(code)] += count
    all_records = inspected or len(differences) == result.counts.difference_records
    precision: CountPrecision = "exact" if result.counts.final else "lower_bound"
    counts = [
        ReportCount(
            name=name,
            value=None if result.strategy == "pending" and value == 0 and unit == "rows" else value,
            precision="unknown"
            if result.strategy == "pending" and value == 0 and unit == "rows"
            else precision,
            unit=cast(Literal["rows", "records", "occurrences"], unit),
        )
        for name, value, unit in (
            ("candidate_rows", result.counts.left_rows, "rows"),
            ("reference_rows", result.counts.right_rows, "rows"),
            ("matched_rows", result.counts.matched_rows, "rows"),
            ("difference_records", result.counts.difference_records, "records"),
            ("contract_violations", result.counts.contract_violations, "records"),
        )
    ]
    for name, value, applicable, unit in (
        ("added_rows", added, result.strategy in ("key", "sequence"), "rows"),
        ("removed_rows", removed, result.strategy in ("key", "sequence"), "rows"),
        ("modified_rows", modified, result.strategy in ("key", "sequence"), "rows"),
        (
            "candidate_excess_occurrences",
            added,
            result.strategy in ("multiset", "matching"),
            "occurrences",
        ),
        (
            "reference_excess_occurrences",
            removed,
            result.strategy in ("multiset", "matching"),
            "occurrences",
        ),
    ):
        known = applicable and (all_records or value > 0)
        derived_precision: CountPrecision = (
            "exact" if all_records and result.complete else "lower_bound"
        )
        counts.append(
            ReportCount(
                name=name,
                value=value if known else None,
                precision=derived_precision if known else "unknown",
                unit=cast(Literal["rows", "records", "occurrences"], unit),
            )
        )
    examples = tuple(
        _witness(item, result, options) for item in differences[: options.max_examples]
    )
    if options.mode == "detail" and not inspected:
        unmet.append("detail_evidence_not_verified")
    if options.require_exhaustive:
        if not result.complete:
            unmet.append("evaluation_incomplete_original_evidence_not_exhaustive")
        if not inspected:
            unmet.append("exhaustive_original_evidence_not_verified")
    if options.mode == "reproduction":
        unmet.append("reproduction_requires_successful_verified_export")
    reasons = tuple(
        dict.fromkeys(
            [f"{_code(item.code)}: {_REASONS[_code(item.code)]}" for item in result.diagnostics]
            + [f"{code}: {_REASONS[code]}" for code in sorted(code_counts)]
        )
    )
    if result.state == "equivalent":
        next_action = (
            "No differences within the evaluated scope; "
            "review the contract before accepting outside that scope"
        )
    elif result.state == "different":
        next_action = (
            "Review the witnesses and declared policies, "
            "then correct the candidate or explicitly revise the contract"
        )
    else:
        next_action = "Resolve the diagnostic and rerun the comparison before accepting equivalence"
    withheld = any(
        value.disclosure != "visible"
        for example in examples
        for value in (*example.key, *example.candidate, *example.reference)
    )
    policies = _policies(result, options, declaration)
    metadata_omitted = any(
        "[omitted]" in item.name or "[omitted]" in item.value for item in policies
    )
    metadata_omitted = metadata_omitted or any(
        "[omitted]" in text
        for example in examples
        for text in (
            example.column or "",
            *example.columns,
            *example.key_columns,
            *(
                value.native_type or ""
                for value in (*example.key, *example.candidate, *example.reference)
            ),
            *(
                value.physical_type or ""
                for value in (*example.key, *example.candidate, *example.reference)
            ),
        )
    )
    report = ComparisonReport(
        state=result.state,
        complete=result.complete,
        scope=result.scope,
        reference=result.reference,
        strategy=result.strategy,
        coverage="complete" if result.complete else "partial",
        contract_sha256=result.contract_sha256,
        spec_sha256=result.spec_sha256,
        counts=tuple(counts),
        reasons=reasons,
        next_action=next_action,
        policies=policies,
        examples=examples,
        evidence=ReportEvidenceManifest(
            mode=options.mode,
            inspection="verified_differences" if inspected else "result_only",
            evaluation_complete=result.complete,
            counts_final=result.counts.final,
            available_records=result.counts.difference_records,
            included_examples=len(examples),
            display_complete=len(examples) == result.counts.difference_records,
            values_withheld=withheld or not options.include_values,
            metadata_withheld=not options.include_metadata or metadata_omitted,
            required_exhaustive=options.require_exhaustive,
            acceptance="not_satisfied" if unmet else "satisfied",
            unmet_requirements=tuple(unmet),
            reproduction="requires_verified_export"
            if options.mode == "reproduction"
            else "not_requested",
        ),
        options=ReportViewPolicy(
            mode=options.mode,
            include_values=options.include_values,
            include_metadata=options.include_metadata,
            redacted_column_count=len(options.redact_columns),
            max_examples=options.max_examples,
            max_value_chars=options.max_value_chars,
            max_report_bytes=options.max_report_bytes,
            require_exhaustive=options.require_exhaustive,
        ),
    )
    if len(report.model_dump_json().encode("utf-8")) > options.max_report_bytes:
        raise ResourceLimitError("comparison report exceeds max_report_bytes")
    return report


def read_comparison_report(path: Path, *, max_bytes: int = 2 * 1024 * 1024) -> ComparisonReport:
    """Read a detached report only; never follow artifact paths or execute inputs."""
    from equiframe.evidence import parse_json

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    try:
        with open_regular_file(local_input_path(path)) as source:
            raw = source.read(max_bytes + 1)
    except ArtifactIOError as error:
        cause = error.__cause__
        if isinstance(cause, OSError):
            raise type(cause)(cause.errno, "comparison report cannot be read") from None
        raise
    if len(raw) > max_bytes:
        raise ResourceLimitError("comparison report exceeds reader budget")
    parse_json(raw)
    report = ComparisonReport.model_validate_json(raw)
    if len(raw) > report.options.max_report_bytes:
        raise ResourceLimitError("comparison report exceeds its declared budget")
    return report


def _write(path: Path, content: bytes) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def write_comparison_report(
    result: ComparisonResult,
    directory: Path,
    *,
    options: ReportOptions | None = None,
    evidence_root: Path | None = None,
    declaration: DiffContract | None = None,
) -> ComparisonReport:
    """Publish a new private local report, writing the success manifest last.

    Failures raise, leave no success manifest, and may leave partial files for
    caller cleanup. Originals are never deleted. Reproduction exports contain
    sensitive raw captures and require explicit values/metadata opt-ins.
    """
    options = ReportOptions.model_validate(ReportOptions() if options is None else options)
    directory = local_output_directory(directory)
    report = comparison_report(
        result, options=options, evidence_root=evidence_root, declaration=declaration
    )
    documents = {
        "report.json": report.model_dump_json(indent=2).encode("utf-8") + b"\n",
        "report.txt": report.to_text().encode("utf-8"),
        "report.html": report.to_html().encode("utf-8"),
    }
    if any(len(content) > options.max_report_bytes for content in documents.values()):
        raise ResourceLimitError("comparison report output exceeds max_report_bytes")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    if options.mode == "reproduction":
        if evidence_root is None:
            raise ValueError("reproduction requires an explicit evidence_root")
        from equiframe._report_io import export_reproduction

        export_reproduction(
            result,
            evidence_root,
            directory / "reproduction",
            max_bytes=options.max_evidence_bytes,
            max_records=options.max_records,
        )
        evidence = report.evidence.model_dump(mode="python")
        evidence["reproduction"] = "exported_materialized_inputs"
        evidence["unmet_requirements"] = tuple(
            item
            for item in report.evidence.unmet_requirements
            if item != "reproduction_requires_successful_verified_export"
        )
        evidence["acceptance"] = "not_satisfied" if evidence["unmet_requirements"] else "satisfied"
        report = ComparisonReport.model_validate(
            {
                **report.model_dump(mode="python"),
                "evidence": ReportEvidenceManifest.model_validate(evidence),
            }
        )
        documents = {
            "report.json": report.model_dump_json(indent=2).encode("utf-8") + b"\n",
            "report.txt": report.to_text().encode("utf-8"),
            "report.html": report.to_html().encode("utf-8"),
        }
        if any(len(content) > options.max_report_bytes for content in documents.values()):
            raise ResourceLimitError("comparison report output exceeds max_report_bytes")
    for name, content in documents.items():
        _write(directory / name, content)
    from equiframe.evidence import inventory

    manifest = ReportPublicationManifest(
        report_evidence=report.evidence,
        files=inventory(directory),
    )
    temporary = directory / ".evidence-manifest.part"
    final = directory / "evidence-manifest.json"
    linked = False
    try:
        _write(temporary, canonical_bytes(manifest.model_dump(mode="json")) + b"\n")
        os.link(temporary, final)
        linked = True
        temporary.unlink()
    except BaseException:
        if linked:
            final.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        raise
    return report
