"""Strict artifact-only ETL requests; no callback or plugin imports in JSON."""

from pydantic import model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier
from equiframe.pipeline_types import PipelineInput
from equiframe.types import ArtifactRef
from equiframe.workflow import WorkflowSpec


class WorkflowExpected(FrozenModel):
    stage_id: Identifier
    artifact: ArtifactRef


class WorkflowRequest(FrozenModel):
    spec: WorkflowSpec
    inputs: tuple[PipelineInput, ...]
    expected: tuple[WorkflowExpected, ...] = ()

    @model_validator(mode="after")
    def names(self) -> Self:
        external = {
            binding.source
            for stage in self.spec.stages
            for binding in stage.inputs
            if binding.stage is None
        }
        if len({item.name for item in self.inputs}) != len(self.inputs):
            raise ValueError("workflow input names must be unique")
        if {item.name for item in self.inputs} != external:
            raise ValueError("workflow request must bind exactly its external inputs")
        if len({item.stage_id for item in self.expected}) != len(self.expected):
            raise ValueError("workflow expected stages must be unique")
        if not {item.stage_id for item in self.expected} <= {s.stage_id for s in self.spec.stages}:
            raise ValueError("workflow expected references contain undeclared stages")
        return self
