"""Selection audit stays in the benchmark; only vectors cross into the library."""

from equiframe import NormalTrainingProfiles
from pydantic import model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text, digest


class TrainingRecord(Document):
    scenario_id: Text
    candidate_id: Text
    group_id: Digest
    candidate_sha256: Digest
    oracle_sha256: Digest
    profile_sha256: Digest
    vector_sha256: Digest
    execution_sha256: Digest


class TrainingManifest(Document):
    purpose: str = "normal_training"
    catalog_sha256: Digest
    splits_sha256: Digest
    records: tuple[TrainingRecord, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if self.purpose != "normal_training" or not self.records:
            raise ValueError("nonempty normal training selection required")
        for field in ("candidate_id", "execution_sha256", "profile_sha256"):
            if len({getattr(r, field) for r in self.records}) != len(self.records):
                raise ValueError("duplicate training evidence")
        return self


class TrainingSelection(Document):
    manifest: TrainingManifest
    training: NormalTrainingProfiles

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if digest(self.manifest) != self.training.selection_manifest_sha256:
            raise ValueError("selection manifest mismatch")
        if len(self.manifest.records) != len(self.training.profiles):
            raise ValueError("selection size mismatch")
        if any(
            record.vector_sha256 != digest(vector)
            for record, vector in zip(self.manifest.records, self.training.profiles, strict=True)
        ):
            raise ValueError("selected vectors do not match the recorded evidence")
        return self
