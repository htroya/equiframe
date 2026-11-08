"""Version 1.0 diagnostics; independent of migration and verification formats."""

from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, Text, _ExplicitOutcome
from equiframe.types import Sha256

Name = Annotated[str, Field(min_length=1)]


class Source(FrozenModel):
    path: Text
    format: Literal["parquet", "csv", "arrow"] = "parquet"
    snapshot_id: Text
    expected_sha256: Sha256 | None = None
    expected_bytes: NonNegativeInt | None = None
    manifest_path: Text | None = None
    manifest_sha256: Sha256 | None = None
    delimiter: Annotated[str, Field(min_length=1, max_length=1)] = ","

    @model_validator(mode="after")
    def manifest_pair(self) -> Self:
        if (self.manifest_path is None) != (self.manifest_sha256 is None):
            raise ValueError("manifest path and externally trusted SHA-256 required together")
        return self


class Resources(FrozenModel):
    memory_mb: Annotated[int, Field(ge=16, le=65536)] = 512
    threads: Annotated[int, Field(ge=1, le=64)] = 1
    timeout_seconds: Annotated[float, Field(gt=0)] = 300.0
    temp_disk_mb: Annotated[int, Field(ge=1)] = 256
    max_input_bytes: Annotated[int, Field(gt=0)] = 512 * 1024 * 1024
    max_rows: Annotated[int, Field(ge=0)] = 10_000_000
    max_columns: Annotated[int, Field(ge=1, le=1000)] = 256
    max_groups: Annotated[int, Field(ge=1, le=1000)] = 100
    examples: Annotated[int, Field(ge=0, le=100)] = 10
    top_categories: Annotated[int, Field(ge=1, le=100)] = 10
    histogram_bins: Annotated[int, Field(ge=1, le=100)] = 20
    chart_rows: Annotated[int, Field(ge=0, le=1000)] = 200
    max_report_bytes: Annotated[int, Field(ge=1)] = 32 * 1024 * 1024


class Conversion(FrozenModel):
    column: Name
    target: Identifier
    kind: Literal["decimal", "integer", "date", "timestamp"]
    empty: Literal["invalid", "missing"] = "invalid"
    precision: Annotated[int, Field(ge=1, le=38)] = 38
    scale: Annotated[int, Field(ge=0, le=18)] = 6

    @model_validator(mode="after")
    def scale_fits(self) -> Self:
        if self.scale > self.precision:
            raise ValueError("scale exceeds precision")
        return self


class KeyRule(FrozenModel):
    columns: tuple[Name, ...]
    incomplete: Literal["exclude", "include", "reject"] = "exclude"
    empty_is_missing: bool = True
    require_unique: bool = False

    @model_validator(mode="after")
    def columns_unique(self) -> Self:
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("key requires distinct nonempty columns")
        return self


class NumericRule(FrozenModel):
    column: Name
    groups: tuple[Name, ...] = ()
    monetary: bool = False
    currency_column: Name | None = None
    unit: Text | None = None
    outliers: Literal["iqr", "mad", "none"] = "iqr"
    multiplier: Annotated[float, Field(gt=0)] = 1.5
    min_support: Annotated[int, Field(ge=2)] = 5

    @model_validator(mode="after")
    def monetary_groups(self) -> Self:
        if len(set(self.groups)) != len(self.groups):
            raise ValueError("group columns must be distinct")
        if self.monetary and (
            self.currency_column is None or self.currency_column not in self.groups
        ):
            raise ValueError("money requires explicit currency grouping")
        return self


class EdaConfig(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    rules_id: Identifier = "generic"
    rules_revision: Annotated[int, Field(ge=1)] = 1
    identifiers: tuple[Name, ...] = ()
    conversions: tuple[Conversion, ...] = ()
    keys: tuple[KeyRule, ...] = ()
    numeric: tuple[NumericRule, ...] = ()
    percentiles: tuple[Annotated[float, Field(ge=0, le=1)], ...] = (0.25, 0.5, 0.75)
    stddev: Literal["population", "sample"] = "population"
    charts: bool = False
    resources: Resources = Field(default_factory=Resources)

    @model_validator(mode="after")
    def conversions_unique(self) -> Self:
        if len({c.column for c in self.conversions}) != len(self.conversions):
            raise ValueError("one explicit conversion per source column")
        if len({c.target.casefold() for c in self.conversions}) != len(self.conversions):
            raise ValueError("derived column names must be distinct")
        if {i.casefold() for i in self.identifiers} & {
            c.column.casefold() for c in self.conversions
        }:
            raise ValueError("identifiers retain their original representation")
        if len(set(self.percentiles)) != len(self.percentiles):
            raise ValueError("percentiles must be distinct")
        return self


class ColumnProfile(FrozenModel):
    name: Name
    physical_type: Text
    rows: NonNegativeInt
    nulls: NonNegativeInt
    nan: NonNegativeInt
    empty: NonNegativeInt
    zero: NonNegativeInt
    nonfinite: NonNegativeInt
    valid: NonNegativeInt
    distinct_present: NonNegativeInt
    null_rate: float | None
    empty_rate: float | None
    nan_rate: float | None
    frequencies: tuple[dict[str, object], ...]


class DuplicateProfile(FrozenModel):
    columns: tuple[Name, ...]
    denominator: NonNegativeInt
    incomplete_rows: NonNegativeInt = 0
    policy: Text
    repeated_groups: NonNegativeInt
    involved_rows: NonNegativeInt
    excess_rows: NonNegativeInt
    excess_rate: float | None
    examples: tuple[dict[str, object], ...]


class Finding(FrozenModel):
    code: Identifier
    severity: Literal["observation", "rule_violation", "not_evaluable"]
    column: str | None = None
    count: NonNegativeInt | None = None
    denominator: NonNegativeInt | None = None
    reason: Text
    examples: tuple[dict[str, object], ...] = ()


class EdaResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .state; EDA never establishes equivalence or publication"
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    producer_version: Text
    snapshot_id: Text
    state: Literal["completed", "not_evaluable", "failed", "cancelled"]
    reason: Text | None
    elapsed_seconds: Annotated[float, Field(ge=0)]
    calculation_elapsed_seconds: Annotated[float, Field(ge=0)] = 0.0
    chart_state: Literal["completed", "not_requested", "not_evaluable", "failed"] = "not_requested"
    chart_reason: str | None = None
    source: Source
    source_sha256: Sha256 | None
    source_unchanged: bool | None
    snapshot_complete: bool = False
    config_sha256: Sha256
    rows: NonNegativeInt | None
    columns: tuple[ColumnProfile, ...] = ()
    duplicates: tuple[DuplicateProfile, ...] = ()
    conversions: tuple[dict[str, object], ...] = ()
    numeric: tuple[dict[str, object], ...] = ()
    findings: tuple[Finding, ...] = ()
    environment: dict[str, str]
    limits: tuple[Text, ...]
    evidence_links: tuple[dict[str, str], ...] = ()

    @model_validator(mode="after")
    def completed_capture(self) -> Self:
        if self.state == "completed" and (
            not self.snapshot_complete
            or self.rows is None
            or self.source_sha256 is None
            or self.source_unchanged is not True
        ):
            raise ValueError("completed diagnostics require full verified unchanged capture")
        return self


class ResultFile(FrozenModel):
    path: Name
    bytes: NonNegativeInt
    sha256: Sha256

    @model_validator(mode="after")
    def relative_member(self) -> Self:
        if (
            self.path.startswith("/")
            or "\\" in self.path
            or ":" in self.path
            or any(p in ("", ".", "..") for p in self.path.split("/"))
        ):
            raise ValueError("result member must be a normalized relative path")
        return self


class EdaManifest(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["equiframe.eda"] = "equiframe.eda"
    run_id: Identifier
    state: Literal["completed", "not_evaluable", "failed", "cancelled"]
    files: tuple[ResultFile, ...]

    @model_validator(mode="after")
    def closed_names(self) -> Self:
        names = [f.path for f in self.files]
        if len(set(names)) != len(names) or "manifest.json" in names:
            raise ValueError("manifest must list unique members and exclude itself")
        if not {
            "summary.json",
            "source.json",
            "config.json",
            "findings.json",
            "report.html",
        } <= set(names):
            raise ValueError("EDA manifest lacks required diagnostic documents")
        return self
