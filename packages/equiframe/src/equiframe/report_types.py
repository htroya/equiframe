"""Versioned, detached comparison views; disclosure never changes evaluation."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    NonNegativeInt,
    PositiveInt,
    _ExplicitOutcome,
    strict_bool_literal,
)
from equiframe.comparison_types import ComparisonValue
from equiframe.pipeline_types import EvidenceFile
from equiframe.types import ComparisonState, Sha256

EvidenceMode = Literal["diagnostic", "detail", "reproduction"]
CountPrecision = Literal["exact", "lower_bound", "estimate", "unknown"]


class ReportOptions(FrozenModel):
    """Separate disclosure/inspection budgets; existing raw capture is unchanged.

    Values, names and free-form producer text are withheld by default. Reproduction
    exports require both disclosure opt-ins and cannot redact selected columns.
    No setting grants operating-system permissions or deletes original evidence.
    """

    schema_version: Literal["1.0"] = "1.0"
    mode: EvidenceMode = "diagnostic"
    include_values: bool = False
    include_metadata: bool = False
    redact_columns: tuple[str, ...] = ()
    max_examples: Annotated[int, Field(ge=0, le=10000)] = 20
    max_value_chars: Annotated[int, Field(ge=16, le=1048576)] = 4096
    max_report_bytes: PositiveInt = 2 * 1024 * 1024
    max_evidence_bytes: PositiveInt = 64 * 1024 * 1024
    max_records: Annotated[int, Field(gt=0, le=1000000)] = 100000
    require_exhaustive: bool = False

    @model_validator(mode="after")
    def valid_disclosure(self) -> Self:
        if len(set(self.redact_columns)) != len(self.redact_columns):
            raise ValueError("redacted columns must be unique")
        if self.mode == "reproduction" and (
            not self.include_values or not self.include_metadata or self.redact_columns
        ):
            raise ValueError("reproduction requires values and metadata without column redaction")
        return self


class ReportViewPolicy(FrozenModel):
    """Safe publication policy: column-redaction selectors never leave the builder."""

    mode: EvidenceMode
    include_values: bool
    include_metadata: bool
    redacted_column_count: NonNegativeInt
    max_examples: NonNegativeInt
    max_value_chars: PositiveInt
    max_report_bytes: PositiveInt
    require_exhaustive: bool


class ReportCount(FrozenModel):
    name: str
    value: NonNegativeInt | None
    precision: CountPrecision
    unit: Literal["rows", "records", "occurrences"]

    @model_validator(mode="after")
    def known(self) -> Self:
        if (self.value is None) != (self.precision == "unknown"):
            raise ValueError("unknown counts omit their value; known counts require a value")
        return self


class ReportPolicy(FrozenModel):
    name: str
    value: str


class ReportValue(FrozenModel):
    disclosure: Literal["visible", "redacted", "omitted"]
    kind: str
    representation: str
    native_type: str | None = None
    physical_type: str | None = None
    value: ComparisonValue | None = None

    @model_validator(mode="after")
    def visible_only(self) -> Self:
        if (self.disclosure == "visible") != (self.value is not None):
            raise ValueError("only visible values contain scalar evidence")
        if self.disclosure != "visible" and self.representation != f"[{self.disclosure}]":
            raise ValueError("withheld values require a fixed non-disclosing representation")
        return self


class ReportWitness(FrozenModel):
    category: Literal["contract", "content", "schema"]
    code: str
    reason: str
    position: NonNegativeInt | None
    other_position: NonNegativeInt | None
    column: str | None
    columns: tuple[str, ...]
    key_columns: tuple[str, ...]
    key: tuple[ReportValue, ...]
    candidate: tuple[ReportValue, ...]
    reference: tuple[ReportValue, ...]
    candidate_count: NonNegativeInt | None
    reference_count: NonNegativeInt | None

    @model_validator(mode="after")
    def occurrence_counts(self) -> Self:
        if self.category != "content" and (
            self.candidate_count is not None or self.reference_count is not None
        ):
            raise ValueError("contract/schema records do not calculate occurrence counts")
        if self.category == "content" and (
            self.candidate_count is None or self.reference_count is None
        ):
            raise ValueError("content witnesses require recorded occurrence counts")
        return self


class ReportEvidenceManifest(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    mode: EvidenceMode
    inspection: Literal["result_only", "verified_differences"]
    evaluation_complete: bool
    counts_final: bool
    available_records: NonNegativeInt
    included_examples: NonNegativeInt
    display_complete: bool
    values_withheld: bool
    metadata_withheld: bool
    raw_retention: Literal["unchanged_in_original_comparison"] = "unchanged_in_original_comparison"
    report_retention: Literal["until_caller_deletes"] = "until_caller_deletes"
    access: Literal["caller_managed_local_storage_no_encryption"] = (
        "caller_managed_local_storage_no_encryption"
    )
    required_exhaustive: bool
    acceptance: Literal["satisfied", "not_satisfied"]
    unmet_requirements: tuple[str, ...]
    reproduction: Literal[
        "not_requested", "requires_verified_export", "exported_materialized_inputs"
    ]
    reproduction_scope: Literal["materialized_comparison_only_no_transform_reexecution"] = (
        "materialized_comparison_only_no_transform_reexecution"
    )

    @model_validator(mode="after")
    def accepted(self) -> Self:
        if (self.acceptance == "satisfied") != (not self.unmet_requirements):
            raise ValueError("evidence acceptance must describe unmet requirements")
        if self.included_examples > self.available_records:
            raise ValueError("display examples exceed available records")
        if self.display_complete != (self.included_examples == self.available_records):
            raise ValueError("display completeness must agree with its record counts")
        return self


class ComparisonReport(_ExplicitOutcome, FrozenModel):
    """One sanitized source for JSON, console, standalone HTML and notebooks.

    Formatting this object performs no file IO, imports no notebook framework and
    never evaluates a source. JSON is a view, not a serialized ComparisonResult.
    """

    _truth_value_guidance = (
        "use assert_equivalent on the original ComparisonResult; a generated report is not approval"
    )

    schema_version: Literal["1.0"] = "1.0"
    state: ComparisonState
    complete: bool
    scope: Literal["output_schema"] = "output_schema"
    reference: Literal["peer", "expected"]
    strategy: Literal["pending", "sequence", "key", "multiset", "matching"]
    coverage: Literal["complete", "partial"]
    contract_sha256: Sha256
    spec_sha256: Sha256
    counts: tuple[ReportCount, ...]
    reasons: tuple[str, ...]
    next_action: str
    policies: tuple[ReportPolicy, ...]
    examples: tuple[ReportWitness, ...]
    evidence: ReportEvidenceManifest
    options: ReportViewPolicy

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.coverage == "complete") != self.complete:
            raise ValueError("coverage must preserve comparison completeness")
        if self.state in ("equivalent", "different") and not self.complete:
            raise ValueError("an interrupted comparison cannot have a final verdict")
        if self.evidence.evaluation_complete != self.complete:
            raise ValueError("evidence must preserve evaluation completeness")
        if self.evidence.counts_final != self.complete:
            raise ValueError("count completeness must preserve evaluation completeness")
        if self.evidence.mode != self.options.mode:
            raise ValueError("evidence mode must agree with the view policy")
        if self.evidence.required_exhaustive != self.options.require_exhaustive:
            raise ValueError("evidence requirement must agree with the view policy")
        counts = {count.name: count for count in self.counts}
        if set(counts) != {
            "candidate_rows",
            "reference_rows",
            "matched_rows",
            "difference_records",
            "contract_violations",
            "added_rows",
            "removed_rows",
            "modified_rows",
            "candidate_excess_occurrences",
            "reference_excess_occurrences",
        }:
            raise ValueError("report requires the complete set of named counts")
        if counts["difference_records"].value != self.evidence.available_records:
            raise ValueError("record count must agree with the evidence manifest")
        if self.state == "equivalent" and any(
            counts[name].precision != "exact" or counts[name].value is None
            for name in ("candidate_rows", "reference_rows", "matched_rows")
        ):
            raise ValueError("equivalent report requires known exact row counts")
        if self.state == "equivalent" and (
            self.evidence.available_records
            or self.examples
            or self.reasons
            or counts["candidate_rows"].value != counts["reference_rows"].value
            or counts["matched_rows"].value != counts["candidate_rows"].value
        ):
            raise ValueError("equivalent report requires complete matching without differences")
        if self.state == "different" and not self.evidence.available_records:
            raise ValueError("different report requires recorded differences")
        if not self.complete and any(count.precision == "exact" for count in self.counts):
            raise ValueError("partial evaluation cannot claim final exact counts")
        if self.evidence.included_examples != len(self.examples):
            raise ValueError("manifest must describe the actual displayed examples")
        if len({count.name for count in self.counts}) != len(self.counts):
            raise ValueError("count names must be unique")
        for witness in self.examples:
            if not self.options.include_metadata and any(
                value.native_type is not None or value.physical_type is not None
                for value in (*witness.key, *witness.candidate, *witness.reference)
            ):
                raise ValueError("disclosure policy forbids producer type metadata")
            if not self.options.include_values and any(
                value.disclosure == "visible"
                for value in (*witness.key, *witness.candidate, *witness.reference)
            ):
                raise ValueError("disclosure policy forbids visible values")
        return self

    def to_text(self) -> str:
        from equiframe.report_rendering import render_comparison_text

        return render_comparison_text(self)

    def to_html(self) -> str:
        from equiframe.report_rendering import render_comparison_html

        return render_comparison_html(self)

    def _repr_html_(self) -> str:
        from equiframe.report_rendering import render_comparison_notebook

        return render_comparison_notebook(self)


class ReportPublicationManifest(FrozenModel):
    """Last-written success receipt for a closed report export inventory."""

    schema_version: Literal["1.0"] = "1.0"
    publication_complete: Annotated[Literal[True], BeforeValidator(strict_bool_literal)] = True
    report_evidence: ReportEvidenceManifest
    files: tuple[EvidenceFile, ...]

    @model_validator(mode="after")
    def unique_files(self) -> Self:
        names = [item.path for item in self.files]
        if len(names) != len(set(names)):
            raise ValueError("report inventory paths must be unique")
        if not {"report.json", "report.html", "report.txt"} <= set(names):
            raise ValueError("report publication requires JSON, HTML and text")
        if "evidence-manifest.json" in names:
            raise ValueError("publication inventory must not include itself")
        return self
