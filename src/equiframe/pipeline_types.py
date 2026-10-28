"""Versioned orchestration contracts; technical completion is distinct from alerts."""

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, Text, _ExplicitOutcome
from equiframe.comparison_types import ComparisonOptions, ComparisonPolicy, ComparisonResult
from equiframe.decision import combine_decisions
from equiframe.detector_types import ComponentDecision, DetectionResult, HybridDecision
from equiframe.execution_types import ExecutionPlan, ExecutionResult
from equiframe.profile_types import ProfileOptions, ProfileResult, ProfileSpec, profile_digest
from equiframe.rule_types import RuleEvaluation, RuleOptions
from equiframe.types import ArtifactRef, Sha256

StageName = Literal["execution", "rules", "profile", "detection", "comparison", "hybrid"]
StageState = Literal["completed", "not_evaluable", "failed", "skipped"]
STAGES: tuple[StageName, ...] = (
    "execution",
    "rules",
    "profile",
    "detection",
    "comparison",
    "hybrid",
)


class PipelineSpec(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    execution: ExecutionPlan
    profile: ProfileSpec | None = None
    rule_options: RuleOptions = RuleOptions()
    profile_options: ProfileOptions = ProfileOptions()
    comparison_policy: ComparisonPolicy = ComparisonPolicy()
    comparison_options: ComparisonOptions = ComparisonOptions()
    comparison_reference: Literal["peer", "expected"] = "peer"

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.profile and self.profile.family != self.execution.contract.family:
            raise ValueError("profile and execution families must agree")
        # Authentication belongs in the injected provider, never in persisted ETL parameters.
        forbidden = {"password", "passwd", "secret", "token", "authorization", "credentials"}
        for parameter in self.execution.parameters:
            name = parameter.name.lower().replace("-", "_").replace(".", "_")
            if forbidden.intersection(name.split("_")) or name in {"api_key", "access_key"}:
                raise ValueError("credential parameters must be supplied outside the pipeline plan")
        return self


class PipelineInput(FrozenModel):
    name: Identifier
    artifact: ArtifactRef


class PipelineRequest(FrozenModel):
    """CLI data/configuration only. Executable registrations are supplied separately."""

    schema_version: Literal["1.0"] = "1.0"
    spec: PipelineSpec
    inputs: tuple[PipelineInput, ...]
    comparison: ArtifactRef | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        names = tuple(item.name for item in self.inputs)
        if len(set(names)) != len(names) or set(names) != {
            item.name for item in self.spec.execution.contract.inputs
        }:
            raise ValueError("input bindings must cover exactly the declared tables")
        if any(item.artifact.format not in ("arrow", "parquet") for item in self.inputs):
            raise ValueError("pipeline inputs require Arrow or Parquet")
        if self.comparison and self.comparison.format not in ("arrow", "parquet"):
            raise ValueError("comparison requires Arrow or Parquet")
        return self


class StageRecord(FrozenModel):
    stage: StageName
    state: StageState
    elapsed_seconds: Annotated[float, Field(ge=0)]
    code: Identifier


class EvidenceFile(FrozenModel):
    path: Text
    sha256: Sha256
    size_bytes: NonNegativeInt

    @model_validator(mode="after")
    def local_relative(self) -> Self:
        path = PurePosixPath(self.path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or ":" in self.path
            or "\\" in self.path
            or path.as_posix() != self.path
            or self.path == "."
        ):
            raise ValueError("evidence path must be a normalized relative file path")
        return self


class PipelineResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = (
        "inspect .complete, .exit_code and the requested component decisions explicitly"
    )

    schema_version: Literal["1.0"] = "1.0"
    pipeline_id: Identifier
    spec: PipelineSpec
    spec_sha256: Sha256
    started_at: Text
    finished_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    detection_requested: bool
    comparison_requested: bool
    cancelled: bool
    stages: tuple[StageRecord, ...]
    execution: ExecutionResult | None
    rules: RuleEvaluation | None
    profile: ProfileResult | None
    detection: DetectionResult | None
    comparison: ComparisonResult | None
    hybrid: HybridDecision
    evidence: tuple[EvidenceFile, ...]
    event_count: Annotated[int, Field(ge=2)]
    event_head_sha256: Sha256

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.spec_sha256 != profile_digest(self.spec.model_dump(mode="json")):
            raise ValueError("pipeline specification fingerprint mismatch")
        if tuple(stage.stage for stage in self.stages) != STAGES:
            raise ValueError("pipeline must record each stage exactly once in order")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate evidence paths")
        if self.execution is not None and self.execution.plan != self.spec.execution:
            raise ValueError("execution does not belong to this pipeline plan")
        if self.rules is not None:
            if self.execution is None or (
                self.rules.execution_id != self.execution.execution_id
                or self.rules.contract_sha256 != self.execution.contract_sha256
                or self.rules.run_id != self.execution.run_id
                or self.rules.options != self.spec.rule_options
            ):
                raise ValueError("rules do not belong to this execution")
            if self.hybrid.r != combine_decisions(self.rules, self.hybrid.m).r:
                raise ValueError("hybrid must preserve the rule decision")
        elif self.hybrid.r.decision != "not_evaluable":
            raise ValueError("missing rules cannot produce a rule decision")
        if self.profile is not None and (
            self.execution is None
            or self.profile.vector.spec != self.spec.profile
            or self.profile.metadata.execution_id != self.execution.execution_id
            or self.profile.metadata.run_id != self.execution.run_id
            or self.profile.metadata.contract_sha256 != self.execution.contract_sha256
            or self.profile.metadata.artifacts
            != tuple(
                reference
                for table in (
                    *self.execution.inputs,
                    *((self.execution.output,) if self.execution.output else ()),
                )
                for reference in (table.data, *((table.index,) if table.index else ()))
            )
            or self.profile.metadata.execution_sha256
            != profile_digest(self.execution.model_dump(mode="json"))
            or self.profile.options != self.spec.profile_options
        ):
            raise ValueError("profile does not belong to the declared execution/features")
        if self.detection is not None:
            if not self.detection_requested or self.profile is None or not self.profile.complete:
                raise ValueError("detection requires a requested, complete profile")
            if len(self.detection.m) != 1 or self.hybrid.m != self.detection.m[0].result:
                raise ValueError("detection and hybrid must describe one identical profile")
        elif self.hybrid.m.decision != "not_evaluable":
            raise ValueError("missing detector cannot produce an M decision")
        if self.comparison is not None and not self.comparison_requested:
            raise ValueError("unexpected comparison")
        if self.comparison is not None and (
            self.comparison.spec.contract != self.spec.execution.contract
            or self.comparison.spec.policy != self.spec.comparison_policy
            or self.comparison.options != self.spec.comparison_options
            or self.comparison.reference != self.spec.comparison_reference
            or (
                self.comparison.left is not None
                and self.comparison.left.execution != self.execution
            )
        ):
            raise ValueError("comparison does not belong to the configured execution/policy")
        values = (self.execution, self.rules, self.profile, self.detection, self.comparison)
        for stage, value in zip(self.stages[:5], values, strict=True):
            if stage.state == "completed" and value is None:
                raise ValueError("completed stage requires its result")
            if stage.state in ("failed", "skipped") and value is not None:
                raise ValueError("failed/skipped stage cannot claim a result")
        if self.execution is not None and (self.stages[0].state == "completed") != (
            self.execution.state == "completed"
        ):
            raise ValueError("execution stage contradicts its result")
        for stage, value in ((self.stages[1], self.rules), (self.stages[2], self.profile)):
            if value is not None and (stage.state == "completed") != value.complete:
                raise ValueError("stage completeness contradicts its result")
        if self.detection is not None and (self.stages[3].state == "completed") != all(
            d.result.complete for d in (*self.detection.m, *self.detection.b)
        ):
            raise ValueError("detector stage completeness contradicts its result")
        if (
            self.comparison is not None
            and (self.stages[4].state == "completed") != self.comparison.complete
        ):
            raise ValueError("comparison stage completeness contradicts its result")
        if (self.stages[5].state == "completed") != self.hybrid.result.complete:
            raise ValueError("hybrid stage completeness contradicts its result")
        return self

    @property
    def complete(self) -> bool:
        required: set[StageName] = {"execution", "rules"}
        if self.spec.profile:
            required.add("profile")
        if self.detection_requested:
            required.update(("detection", "hybrid"))
        if self.comparison_requested:
            required.add("comparison")
        return not self.cancelled and all(
            stage.state == "completed" for stage in self.stages if stage.stage in required
        )

    @property
    def exit_code(self) -> int:
        if self.execution is not None and self.execution.state == "invalid_input":
            return 2
        if not self.complete:
            return 3
        alert = self.hybrid.r.decision == "alert" or self.hybrid.result.decision == "alert"
        if self.detection is not None:
            alert |= any(d.result.decision == "alert" for d in self.detection.b)
        return int(alert or (self.comparison is not None and self.comparison.state == "different"))


def unavailable(reason: str) -> ComponentDecision:
    return ComponentDecision(decision="not_evaluable", complete=False, reason=reason)
