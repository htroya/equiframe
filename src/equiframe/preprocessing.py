"""Fit once on explicitly selected normal training profiles; one matrix for M and B."""

from pathlib import Path
from statistics import median
from typing import Literal

from equiframe._document_io import read_document as _read_document
from equiframe._document_io import write_document as _write_document
from equiframe.profile_types import (
    FeatureFit,
    FeatureMatrix,
    NormalTrainingProfiles,
    PreprocessorBundle,
    ProfileSpec,
    ProfileVector,
    profile_digest,
    profile_spec_fingerprint,
)


def _compatible(profile: ProfileVector, spec: ProfileSpec) -> ProfileVector:
    profile = ProfileVector.model_validate(profile)
    if profile.spec_sha256 != profile_spec_fingerprint(spec):
        raise ValueError("incompatible family, feature version, definitions or order")
    if any(o.state == "not_evaluable" for o in profile.observations):
        raise ValueError("failed measurements cannot be imputed as undefined values")
    return profile


def fit_preprocessor(
    training: NormalTrainingProfiles,
    *,
    spec: ProfileSpec,
    empty_policy: Literal["drop", "not_estimable"] = "drop",
) -> PreprocessorBundle:
    """The caller must supply normal TRAINING selection, backed by its external manifest."""
    training = NormalTrainingProfiles.model_validate(training)
    spec = ProfileSpec.model_validate(spec)
    profiles = tuple(_compatible(p, spec) for p in training.profiles)
    fits: list[FeatureFit] = []
    for index, feature in enumerate(spec.features):
        observations = [p.observations[index] for p in profiles]
        valid = [o.value for o in observations if o.value is not None]
        reason: Literal["no_valid_training_values", "not_applicable"] | None = None
        if not valid:
            reason = (
                "not_applicable"
                if observations and all(o.state == "not_applicable" for o in observations)
                else "no_valid_training_values"
            )
        fits.append(
            FeatureFit(
                name=feature.name,
                valid_count=len(valid),
                median=float(median(valid)) if valid else None,
                reason=reason,
            )
        )
    ready = any(f.median is not None for f in fits) and not (
        empty_policy == "not_estimable"
        and any(f.reason == "no_valid_training_values" for f in fits)
    )
    return PreprocessorBundle(
        spec=spec,
        spec_sha256=profile_spec_fingerprint(spec),
        selection_manifest_sha256=training.selection_manifest_sha256,
        training_sha256=profile_digest([p.model_dump(mode="json") for p in profiles]),
        training_rows=len(profiles),
        empty_policy=empty_policy,
        features=tuple(fits),
        state="ready" if ready else "not_estimable",
    )


def transform_profiles(
    bundle: PreprocessorBundle, profiles: tuple[ProfileVector, ...]
) -> FeatureMatrix:
    """No fit, labels, partitions or engine metadata enter this numeric matrix."""
    bundle = PreprocessorBundle.model_validate(bundle)
    if bundle.state != "ready":
        raise ValueError("preprocessor is not estimable")
    rows: list[tuple[float, ...]] = []
    for profile in profiles:
        profile = _compatible(profile, bundle.spec)
        row: list[float] = []
        for fitted, observed in zip(bundle.features, profile.observations, strict=True):
            if fitted.median is None:
                continue
            row.extend(
                (
                    fitted.median if observed.value is None else observed.value,
                    float(observed.state == "undefined"),
                    float(observed.state == "not_applicable"),
                )
            )
        rows.append(tuple(row))
    return FeatureMatrix(
        preprocessor_sha256=profile_digest(bundle.model_dump(mode="json")),
        columns=bundle.columns,
        values=tuple(rows),
    )


def write_preprocessor(bundle: PreprocessorBundle, path: Path) -> None:
    bundle = PreprocessorBundle.model_validate(bundle)
    _write_document(path, bundle.model_dump_json().encode("utf-8"))


def read_preprocessor(path: Path) -> PreprocessorBundle:
    return PreprocessorBundle.model_validate_json(_read_document(path))
