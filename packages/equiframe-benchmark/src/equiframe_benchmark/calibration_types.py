"""Reviewed calibration lineage and group support stay outside detector features."""

from typing import Literal

from equiframe import NormalCalibrationProfiles
from pydantic import model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text, digest
from equiframe_benchmark.training_types import TrainingRecord, TrainingSelection


class CalibrationManifest(Document):
    purpose: Literal["normal_calibration"] = "normal_calibration"
    catalog_sha256: Digest
    splits_sha256: Digest
    records: tuple[TrainingRecord, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if not self.records:
            raise ValueError("nonempty normal calibration selection required")
        for field in ("candidate_id", "execution_sha256", "profile_sha256"):
            if len({getattr(r, field) for r in self.records}) != len(self.records):
                raise ValueError("duplicate calibration evidence")
        return self


class CalibrationSelection(Document):
    manifest: CalibrationManifest
    calibration: NormalCalibrationProfiles

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if digest(self.manifest) != self.calibration.selection_manifest_sha256:
            raise ValueError("calibration manifest mismatch")
        if len(self.manifest.records) != len(self.calibration.profiles):
            raise ValueError("calibration selection size mismatch")
        if any(
            record.vector_sha256 != digest(vector)
            for record, vector in zip(self.manifest.records, self.calibration.profiles, strict=True)
        ):
            raise ValueError("calibration vectors do not match recorded evidence")
        return self


class DetectorSelectionAudit(Document):
    training_sha256: Digest
    calibration_sha256: Digest
    training_groups: int
    calibration_groups: int
    min_training_groups: int
    min_calibration_groups: int
    rationale: Text
    state: Literal["eligible", "not_estimable"]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if min(self.min_training_groups, self.min_calibration_groups) < 1:
            raise ValueError("explicit positive group minima required")
        if min(self.training_groups, self.calibration_groups) < 1:
            raise ValueError("selections must contain groups")
        eligible = (
            self.training_groups >= self.min_training_groups
            and self.calibration_groups >= self.min_calibration_groups
        )
        if (self.state == "eligible") != eligible:
            raise ValueError("audit state contradicts group support")
        return self


def audit_detector_selections(
    training: TrainingSelection,
    calibration: CalibrationSelection,
    *,
    min_training_groups: int,
    min_calibration_groups: int,
    rationale: str,
) -> DetectorSelectionAudit:
    """Check pair provenance/support before fitting; eligibility is not a power guarantee."""
    training = TrainingSelection.model_validate(training)
    calibration = CalibrationSelection.model_validate(calibration)
    t, c = training.manifest, calibration.manifest
    if t.catalog_sha256 != c.catalog_sha256 or t.splits_sha256 != c.splits_sha256:
        raise ValueError("training and calibration require the same catalog and split revision")
    if (
        len(
            {
                p.spec_sha256
                for p in (*training.training.profiles, *calibration.calibration.profiles)
            }
        )
        != 1
    ):
        raise ValueError("a detector pair requires one family and feature revision")
    for field in ("group_id", "scenario_id", "candidate_id", "execution_sha256", "profile_sha256"):
        if {getattr(r, field) for r in t.records} & {getattr(r, field) for r in c.records}:
            raise ValueError("training/calibration leakage in " + field)
    train_groups = len({r.group_id for r in t.records})
    calibration_groups = len({r.group_id for r in c.records})
    return DetectorSelectionAudit(
        training_sha256=digest(training),
        calibration_sha256=digest(calibration),
        training_groups=train_groups,
        calibration_groups=calibration_groups,
        min_training_groups=min_training_groups,
        min_calibration_groups=min_calibration_groups,
        rationale=rationale,
        state="eligible"
        if train_groups >= min_training_groups and calibration_groups >= min_calibration_groups
        else "not_estimable",
    )
