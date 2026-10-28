"""Versioned, closed profile formulas and numeric-only preprocessing formats."""

import hashlib
import json
import math
from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    Text,
    _ExplicitOutcome,
    unique,
)
from equiframe.contracts import ColumnSpec, Family
from equiframe.types import ArtifactRef, Sha256

ProfileMetric = Literal[
    "log_filas",
    "razon_salida_entrada",
    "tasa_nulos",
    "tasa_nan",
    "prop_duplicados",
    "cardinalidad_rel",
    "expansion_union",
    "claves_sin_pareja",
    "conversiones_fallidas",
    "fechas_invalidas",
]
FeatureState = Literal["available", "undefined", "not_applicable", "not_evaluable"]


def profile_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")
    ).hexdigest()


class ProfileFeature(FrozenModel):
    """A semantic slot, never an arbitrary numeric value or metadata expression."""

    name: Identifier
    metric: ProfileMetric
    table: Identifier
    columns: tuple[Text, ...] = ()
    denominator_table: Identifier | None = None
    right_table: Identifier | None = None
    right_columns: tuple[Text, ...] = ()
    null_matches: Literal["never"] | None = None
    target: ColumnSpec | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        unique(self.columns, "columns")
        unique(self.right_columns, "right_columns")
        rows = self.metric in ("log_filas", "razon_salida_entrada", "expansion_union")
        multiple = self.metric in ("prop_duplicados", "claves_sin_pareja")
        if (rows and self.columns) or (not rows and not self.columns):
            raise ValueError("formula has an invalid column selection")
        if not rows and not multiple and len(self.columns) != 1:
            raise ValueError("column rates require exactly one column")
        ratio = self.metric in ("razon_salida_entrada", "expansion_union")
        if ratio != (self.denominator_table is not None):
            raise ValueError("only row ratios require a denominator table")
        join = self.metric == "claves_sin_pareja"
        if join:
            if (
                not self.right_table
                or len(self.columns) != len(self.right_columns)
                or self.null_matches is None
            ):
                raise ValueError("join requires paired columns and an explicit NULL policy")
        elif self.right_table or self.right_columns or self.null_matches is not None:
            raise ValueError("right side and NULL matching are only valid for joins")
        conversion = self.metric in ("conversiones_fallidas", "fechas_invalidas")
        if conversion != (self.target is not None):
            raise ValueError("conversion/date formulas require an explicit target column policy")
        if (
            self.metric == "fechas_invalidas"
            and self.target is not None
            and self.target.logical_type.kind not in ("date", "timestamp")
        ):
            raise ValueError("date validity requires a temporal target")
        return self


class ProfileSpec(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    feature_version: Literal["1.0"] = "1.0"
    family: Family
    features: Annotated[tuple[ProfileFeature, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        unique(tuple(f.name for f in self.features), "features")
        unique(
            tuple(
                name
                for f in self.features
                for name in (f.name, f.name + ".undefined", f.name + ".not_applicable")
            ),
            "matrix_columns",
        )
        formulas: set[str] = set()
        for feature in self.features:
            formula = feature.model_dump(mode="json", exclude={"name"})
            if feature.metric == "expansion_union":
                formula["metric"] = "razon_salida_entrada"
            fingerprint = profile_digest(formula)
            if fingerprint in formulas:
                raise ValueError("duplicate formula (including expansion/row ratio alias)")
            formulas.add(fingerprint)
        return self


def profile_spec_fingerprint(spec: ProfileSpec) -> str:
    return profile_digest(ProfileSpec.model_validate(spec).model_dump(mode="json"))


class ProfileOptions(FrozenModel):
    max_rows: PositiveInt = 1_000_000
    max_artifact_bytes: PositiveInt = 128 * 1024 * 1024
    max_work: PositiveInt = 10_000_000
    max_distinct: PositiveInt = 1_000_000
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None


class ConversionReceipt(FrozenModel):
    """Instrumented attempts from the same transformation; NULL output is not a receipt."""

    schema_version: Literal["1.0"] = "1.0"
    feature: Identifier
    source_sha256: Sha256
    source_column: Text
    output_sha256: Sha256
    target: ColumnSpec
    attempted_rows: tuple[NonNegativeInt, ...]
    failed_rows: tuple[NonNegativeInt, ...]
    producer_version: Text

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(set(self.attempted_rows)) != len(self.attempted_rows):
            raise ValueError("conversion attempts must identify unique source rows")
        if len(set(self.failed_rows)) != len(self.failed_rows):
            raise ValueError("conversion failures must identify unique source rows")
        if not set(self.failed_rows) <= set(self.attempted_rows):
            raise ValueError("failed rows must be attempted rows")
        return self


class FeatureSupport(FrozenModel):
    rows: NonNegativeInt = 0
    missing: NonNegativeInt = 0
    nan: NonNegativeInt = 0
    empty_strings: NonNegativeInt = 0
    zeros: NonNegativeInt = 0
    incomplete_keys: NonNegativeInt = 0

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.missing + self.nan + self.empty_strings + self.zeros > self.rows:
            raise ValueError("disjoint scalar support counts exceed rows")
        if self.incomplete_keys > self.rows:
            raise ValueError("incomplete keys exceed rows")
        return self


class FeatureObservation(FrozenModel):
    name: Identifier
    state: FeatureState
    value: Annotated[float, Field(ge=0)] | None = None
    numerator: NonNegativeInt | None = None
    denominator: NonNegativeInt | None = None
    reason: Text | None = None
    support: FeatureSupport = FeatureSupport()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.state == "available":
            if self.value is None or self.reason is not None or self.numerator is None:
                raise ValueError("available measurement requires value and numerator, no reason")
            if self.denominator is not None and (
                self.denominator == 0 or self.value != self.numerator / self.denominator
            ):
                raise ValueError("value must equal its documented ratio")
        elif self.value is not None or self.reason is None:
            raise ValueError("unavailable measurement requires reason and no value")
        if self.state == "undefined" and (
            self.denominator != 0 or self.numerator is None or self.reason != "empty_denominator"
        ):
            raise ValueError("undefined formula must preserve its empty denominator")
        if self.state in ("not_applicable", "not_evaluable") and (
            self.numerator is not None or self.denominator is not None
        ):
            raise ValueError("no partial counts for unavailable formulas")
        return self


class ProfileVector(FrozenModel):
    """Statistical input: formulas and measurements, no run metadata or labels."""

    schema_version: Literal["1.0"] = "1.0"
    spec: ProfileSpec
    spec_sha256: Sha256
    observations: tuple[FeatureObservation, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.spec_sha256 != profile_spec_fingerprint(self.spec):
            raise ValueError("profile feature fingerprint mismatch")
        if tuple(o.name for o in self.observations) != tuple(f.name for f in self.spec.features):
            raise ValueError("profile observations must match the fixed feature order")
        for feature, observation in zip(self.spec.features, self.observations, strict=True):
            if observation.state == "available":
                if feature.metric == "log_filas":
                    if observation.denominator is not None or observation.value != math.log1p(
                        observation.numerator or 0
                    ):
                        raise ValueError("invalid log_filas measurement")
                elif observation.denominator is None:
                    raise ValueError("rate must retain its denominator")
                elif (
                    feature.metric not in ("razon_salida_entrada", "expansion_union")
                    and (observation.numerator or 0) > observation.denominator
                ):
                    raise ValueError("proportion cannot exceed one")
        return self


class ProfileMetadata(FrozenModel):
    profile_id: Identifier
    run_id: Identifier
    execution_id: Identifier
    contract_sha256: Sha256
    execution_sha256: Sha256
    artifacts: tuple[ArtifactRef, ...]
    conversion_receipts: tuple[ConversionReceipt, ...] = ()
    implementation_version: Literal["equiframe-profiles-1.0"] = "equiframe-profiles-1.0"


class ProfileResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .complete and feature availability explicitly; a profile is not a decision"
    )

    schema_version: Literal["1.0"] = "1.0"
    metadata: ProfileMetadata
    vector: ProfileVector
    options: ProfileOptions
    complete: bool
    elapsed_seconds: Annotated[float, Field(ge=0)]
    work_units: NonNegativeInt

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.complete != all(o.state != "not_evaluable" for o in self.vector.observations):
            raise ValueError("profile completeness contradicts observations")
        return self


class NormalTrainingProfiles(FrozenModel):
    """Caller selection boundary; the external manifest proves eligibility, not this type."""

    purpose: Literal["normal_training"]
    selection_manifest_sha256: Sha256
    profiles: tuple[ProfileVector, ...]


class FeatureFit(FrozenModel):
    name: Identifier
    valid_count: NonNegativeInt
    median: Annotated[float, Field(ge=0)] | None
    reason: Literal["no_valid_training_values", "not_applicable"] | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.valid_count == 0:
            if self.median is not None or self.reason is None:
                raise ValueError("unsupported feature needs a documented removal")
        elif self.median is None or self.reason is not None:
            raise ValueError("supported feature requires its fitted median")
        return self


class PreprocessorBundle(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    algorithm: Literal["family-median-with-indicators-1.0"] = "family-median-with-indicators-1.0"
    spec: ProfileSpec
    spec_sha256: Sha256
    selection_manifest_sha256: Sha256
    training_sha256: Sha256
    training_rows: NonNegativeInt
    empty_policy: Literal["drop", "not_estimable"]
    features: tuple[FeatureFit, ...]
    state: Literal["ready", "not_estimable"]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.spec_sha256 != profile_spec_fingerprint(self.spec):
            raise ValueError("bundle feature fingerprint mismatch")
        if tuple(f.name for f in self.features) != tuple(f.name for f in self.spec.features):
            raise ValueError("bundle order mismatch")
        if any(f.valid_count > self.training_rows for f in self.features):
            raise ValueError("feature support exceeds training rows")
        usable = any(f.median is not None for f in self.features)
        unsupported = any(f.reason == "no_valid_training_values" for f in self.features)
        ready = usable and not (unsupported and self.empty_policy == "not_estimable")
        if (self.state == "ready") != ready:
            raise ValueError("bundle state contradicts training support")
        return self

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(
            name
            for f in self.features
            if f.median is not None
            for name in (f.name, f.name + ".undefined", f.name + ".not_applicable")
        )


class FeatureMatrix(FrozenModel):
    """The sole matrix for both M and B. Row metadata is deliberately absent."""

    schema_version: Literal["1.0"] = "1.0"
    preprocessor_sha256: Sha256
    columns: tuple[Text, ...]
    values: tuple[tuple[float, ...], ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        unique(self.columns, "columns")
        if not self.columns or any(len(row) != len(self.columns) for row in self.values):
            raise ValueError("matrix requires a nonempty schema and equal-width numeric rows")
        return self
