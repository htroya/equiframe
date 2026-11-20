"""Data-only requests for verification of explicitly supplied external artifacts."""

from pydantic import model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier
from equiframe.comparison_types import ComparisonOptions, ComparisonPolicy
from equiframe.contracts import Contract
from equiframe.execution_types import ExecutionResult
from equiframe.pipeline_types import PipelineInput
from equiframe.types import ArtifactRef, Sha256
from equiframe.verify_types import (
    ExpectedProvenance,
    IndependentReviewEvidence,
    VerificationBinding,
)


class ReferenceBinding(VerificationBinding):
    comparison_spec_sha256: Sha256 | None = None


class VerificationRequest(FrozenModel):
    contract: Contract
    outputs: tuple[PipelineInput, ...]
    expected: ArtifactRef | None = None
    provenance: ExpectedProvenance | None = None
    reviews: tuple[IndependentReviewEvidence, ...] = ()
    snapshots: tuple[PipelineInput, ...] = ()
    plan_sha256: Sha256 | None = None
    policy: ComparisonPolicy = ComparisonPolicy()
    options: ComparisonOptions = ComparisonOptions()
    require_expected: bool = False
    require_rules: bool = False
    request_review: bool = False
    executions: tuple[tuple[Identifier, ExecutionResult], ...] = ()

    @model_validator(mode="after")
    def names(self) -> Self:
        if not self.outputs:
            raise ValueError("at least one output is required")
        for entries in (self.outputs, self.snapshots):
            if len({item.name for item in entries}) != len(entries):
                raise ValueError("artifact binding names must be unique")
        names = tuple(name for name, _ in self.executions)
        if names and (
            len(set(names)) != len(names) or set(names) != {item.name for item in self.outputs}
        ):
            raise ValueError("execution evidence must cover every output exactly once")
        return self
