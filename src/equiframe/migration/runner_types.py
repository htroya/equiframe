"""Strict migration configuration and evidence; comparisons remain independent of R/M/B/H."""

from __future__ import annotations

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
)
from equiframe.comparison_types import ComparisonOptions, ComparisonPolicy, ComparisonResult
from equiframe.contracts import Contract
from equiframe.execution_types import ExecutionOptions, TableArtifact
from equiframe.pipeline_types import EvidenceFile, PipelineInput, PipelineResult, StageState
from equiframe.profile_types import ProfileOptions, ProfileSpec, profile_digest
from equiframe.rule_types import RuleOptions
from equiframe.serialization import contract_fingerprint
from equiframe.types import ArtifactRef, Sha256

from .types import CompilationCheck, RelationalPlan
from .validation import ir_fingerprint

MigrationStageName = Literal[
    "preflight",
    "capture",
    "source",
    "target",
    "comparison",
    "verification_source",
    "verification_target",
]
MIGRATION_STAGES: tuple[MigrationStageName, ...] = (
    "preflight",
    "capture",
    "source",
    "target",
    "comparison",
    "verification_source",
    "verification_target",
)


class MigrationOptions(FrozenModel):
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None
    max_capture_rows: NonNegativeInt = 10_000_000
    max_capture_bytes: PositiveInt = 512 * 1024 * 1024


class MigrationSpec(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    ir: RelationalPlan
    contract: Contract
    source_engine: Identifier
    target_engine: Identifier
    require_rules: bool = True
    execution_options: ExecutionOptions = Field(default_factory=ExecutionOptions)
    comparison_policy: ComparisonPolicy = Field(default_factory=ComparisonPolicy)
    comparison_options: ComparisonOptions = Field(default_factory=ComparisonOptions)
    rule_options: RuleOptions = Field(default_factory=RuleOptions)
    profile: ProfileSpec | None = None
    profile_options: ProfileOptions = Field(default_factory=ProfileOptions)
    options: MigrationOptions = Field(default_factory=MigrationOptions)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.source_engine == self.target_engine:
            raise ValueError("migration requires two distinct engines")
        if self.profile and self.profile.family != self.contract.family:
            raise ValueError("migration profile family must match the contract")
        return self


class MigrationRequest(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    spec: MigrationSpec
    inputs: tuple[PipelineInput, ...]
    expected: ArtifactRef | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        names = tuple(i.name for i in self.inputs)
        if len(set(names)) != len(names) or set(names) != {
            t.name for t in self.spec.contract.inputs
        }:
            raise ValueError("migration inputs must exactly cover declared tables")
        if any(i.artifact.format not in ("arrow", "parquet") for i in self.inputs):
            raise ValueError("migration inputs require Arrow or Parquet")
        if self.expected and self.expected.format not in ("arrow", "parquet"):
            raise ValueError("migration expected requires Arrow or Parquet")
        return self


class CompilerRecord(FrozenModel):
    engine: Identifier
    transformation_id: Identifier
    revision: PositiveInt
    code_version: Text
    ir_sha256: Sha256
    contract_sha256: Sha256
    check: CompilationCheck


def pipeline_complete(spec: MigrationSpec, result: PipelineResult) -> bool:
    """Completion of explicitly required components; optional R never implies no-alert."""
    if spec.require_rules:
        return result.complete
    required = {"execution"}
    if spec.profile is not None:
        required.add("profile")
    if result.detection_requested:
        required.add("detection")
    return not result.cancelled and all(
        s.state == "completed" for s in result.stages if s.stage in required
    )


class MigrationStage(FrozenModel):
    stage: MigrationStageName
    state: StageState
    code: Identifier
    elapsed_seconds: Annotated[float, Field(ge=0)]


def _identity(t: TableArtifact) -> tuple[object, ...]:
    return (
        t.name,
        t.data.sha256,
        t.data.size_bytes,
        (t.index.sha256, t.index.size_bytes) if t.index else None,
    )


class MigrationResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .state, .verification, .complete and .exit_code explicitly"

    schema_version: Literal["1.0"] = "1.0"
    migration_id: Identifier
    spec: MigrationSpec
    spec_sha256: Sha256
    started_at: Text
    finished_at: Text
    elapsed_seconds: Annotated[float, Field(ge=0)]
    stages: tuple[MigrationStage, ...]
    compilers: tuple[CompilerRecord, ...]
    inputs: tuple[TableArtifact, ...]
    expected_requested: bool
    expected: ArtifactRef | None
    detection_requested: bool
    source: PipelineResult | None
    target: PipelineResult | None
    comparison: ComparisonResult | None
    verification_source: ComparisonResult | None
    verification_target: ComparisonResult | None
    cancelled: bool
    evidence: tuple[EvidenceFile, ...]
    event_count: Annotated[int, Field(ge=2)]
    event_head_sha256: Sha256

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.spec_sha256 != profile_digest(self.spec.model_dump(mode="json")):
            raise ValueError("migration specification fingerprint mismatch")
        if tuple(s.stage for s in self.stages) != MIGRATION_STAGES:
            raise ValueError("migration stages must occur once in the declared order")
        if len({f.path for f in self.evidence}) != len(self.evidence):
            raise ValueError("migration evidence paths must be unique")
        if self.expected and (
            not self.expected_requested or self.expected.format not in ("arrow", "parquet")
        ):
            raise ValueError("unexpected or invalid expected reference")
        if self.detection_requested and self.spec.profile is None:
            raise ValueError("migration detection requires an explicit profile")
        names = tuple(t.name for t in self.inputs)
        declared = {t.name for t in self.spec.contract.inputs}
        if len(set(names)) != len(names) or not set(names) <= declared:
            raise ValueError("migration captured inputs must be unique declared tables")
        if self.stages[1].state == "completed" and (
            self.stages[0].state != "completed"
            or set(names) != declared
            or (self.expected_requested and self.expected is None)
        ):
            raise ValueError("complete capture requires all requested data")
        if self.compilers and tuple(c.engine for c in self.compilers) != (
            self.spec.source_engine,
            self.spec.target_engine,
        ):
            raise ValueError("compiler records must bind the configured engine pair")
        if self.stages[0].state == "completed" and len(self.compilers) != 2:
            raise ValueError("preflight requires both compiler records")
        for c in self.compilers:
            if (
                not c.check.supported
                or c.check.engine != c.engine
                or c.ir_sha256 != ir_fingerprint(self.spec.ir)
                or c.contract_sha256 != contract_fingerprint(self.spec.contract)
            ):
                raise ValueError("compiler record contradicts the plan")
        children = (self.source, self.target)
        for n, p in enumerate(children):
            stage = self.stages[n + 2]
            if p is None:
                if stage.state in ("completed", "not_evaluable"):
                    raise ValueError("migration stage requires its pipeline")
                continue
            if len(self.compilers) != 2 or self.stages[1].state != "completed":
                raise ValueError("pipeline requires preflight and fixed capture")
            record = self.compilers[n]
            e = p.spec.execution
            opts = e.options.model_copy(
                update={
                    "timeout_seconds": self.spec.execution_options.timeout_seconds,
                }
            )
            if (
                e.contract != self.spec.contract
                or e.engine != record.engine
                or e.transformation_id != record.transformation_id
                or e.transformation_revision != record.revision
                or e.parameters
                or opts != self.spec.execution_options
                or p.spec.profile != self.spec.profile
                or p.spec.rule_options != self.spec.rule_options
                or p.spec.profile_options != self.spec.profile_options
                or p.detection_requested != self.detection_requested
                or p.comparison_requested
                or p.spec.comparison_policy != self.spec.comparison_policy
                or p.spec.comparison_options != self.spec.comparison_options
            ):
                raise ValueError("pipeline contradicts the migration configuration")
            timeout = e.options.timeout_seconds
            declared_timeout = self.spec.execution_options.timeout_seconds
            if timeout is None and (
                declared_timeout is not None or self.spec.options.timeout_seconds is not None
            ):
                raise ValueError("effective execution must retain the declared timeout")
            if timeout is not None and (
                timeout <= 0
                or (declared_timeout is not None and timeout > declared_timeout)
                or (
                    self.spec.options.timeout_seconds is not None
                    and timeout > self.spec.options.timeout_seconds
                )
            ):
                raise ValueError("effective execution timeout exceeds its declared budget")
            if (stage.state == "completed") != pipeline_complete(self.spec, p):
                raise ValueError("migration stage contradicts pipeline completion")
            if stage.state in ("skipped", "failed"):
                raise ValueError("failed or skipped stage cannot claim a pipeline")
            if p.execution is not None:
                if (
                    p.execution.implementation_version is not None
                    and p.execution.implementation_version != record.code_version
                ):
                    raise ValueError("execution compiler version mismatch")
                if p.execution.state == "completed" and sorted(
                    (_identity(t) for t in p.execution.inputs), key=lambda x: str(x[0])
                ) != sorted((_identity(t) for t in self.inputs), key=lambda x: str(x[0])):
                    raise ValueError("pipeline inputs differ from the single fixed capture")
        comparisons = (self.comparison, self.verification_source, self.verification_target)
        for n, cmp in enumerate(comparisons):
            stage = self.stages[n + 4]
            if cmp is None:
                if stage.state in ("completed", "not_evaluable"):
                    raise ValueError("comparison stage requires its result")
                continue
            if stage.state in ("skipped", "failed"):
                raise ValueError("failed or skipped stage cannot claim a comparison")
            if (stage.state == "completed") != (cmp.complete and cmp.state != "not_evaluable"):
                raise ValueError("comparison stage contradicts evaluability")
            if (
                cmp.spec.contract != self.spec.contract
                or cmp.spec.policy != self.spec.comparison_policy
                or cmp.options.model_copy(
                    update={
                        "timeout_seconds": self.spec.comparison_options.timeout_seconds,
                    }
                )
                != self.spec.comparison_options
            ):
                raise ValueError("migration comparison configuration mismatch")
            timeout = cmp.options.timeout_seconds
            declared_timeout = self.spec.comparison_options.timeout_seconds
            if timeout is None and (
                declared_timeout is not None or self.spec.options.timeout_seconds is not None
            ):
                raise ValueError("effective comparison must retain the declared timeout")
            if timeout is not None and (
                (declared_timeout is not None and timeout > declared_timeout)
                or (
                    self.spec.options.timeout_seconds is not None
                    and timeout > self.spec.options.timeout_seconds
                )
            ):
                raise ValueError("effective comparison exceeds its declared timeout")
            left = self.source if n != 2 else self.target
            if (
                left is None
                or left.execution is None
                or (cmp.complete and cmp.left is None)
                or (cmp.left is not None and cmp.left.execution != left.execution)
            ):
                raise ValueError("migration comparison left execution mismatch")
            if cmp.left is not None and (
                cmp.left.table != left.execution.output
                or left.execution.output is None
                or (cmp.left.data.sha256, cmp.left.data.size_bytes, cmp.left.data.format)
                != (
                    left.execution.output.data.sha256,
                    left.execution.output.data.size_bytes,
                    left.execution.output.data.format,
                )
            ):
                raise ValueError("comparison snapshot differs from the native output")
            if n == 0:
                if (
                    cmp.reference != "peer"
                    or self.target is None
                    or self.target.execution is None
                    or (cmp.complete and cmp.right is None)
                    or (cmp.right is not None and cmp.right.execution != self.target.execution)
                ):
                    raise ValueError("peer comparison must bind both native executions")
                if cmp.right is not None and (
                    cmp.right.table != self.target.execution.output
                    or self.target.execution.output is None
                    or (cmp.right.data.sha256, cmp.right.data.size_bytes, cmp.right.data.format)
                    != (
                        self.target.execution.output.data.sha256,
                        self.target.execution.output.data.size_bytes,
                        self.target.execution.output.data.format,
                    )
                ):
                    raise ValueError("peer snapshot differs from the native output")
            elif (
                not self.expected_requested
                or self.expected is None
                or cmp.reference != "expected"
                or (cmp.complete and cmp.right is None)
                or (
                    cmp.right is not None
                    and (cmp.right.data.sha256, cmp.right.data.size_bytes, cmp.right.data.format)
                    != (self.expected.sha256, self.expected.size_bytes, self.expected.format)
                )
            ):
                raise ValueError("verification must bind the one captured expected")
        return self

    @property
    def complete(self) -> bool:
        required = set(MIGRATION_STAGES[:5])
        if self.expected_requested:
            required.update(MIGRATION_STAGES[5:])
        return not self.cancelled and all(
            s.state == "completed" for s in self.stages if s.stage in required
        )

    @property
    def state(self) -> Literal["equivalent", "different", "not_evaluable"]:
        return self.comparison.state if self.comparison is not None else "not_evaluable"

    @property
    def verification(self) -> Literal["correct", "divergent", "not_evaluable", "not_requested"]:
        if not self.expected_requested:
            return "not_requested"
        checks = (self.verification_source, self.verification_target)
        if any(c is None or not c.complete or c.state == "not_evaluable" for c in checks):
            return "not_evaluable"
        return (
            "divergent"
            if any(c is not None and c.state == "different" for c in checks)
            else "correct"
        )

    @property
    def exit_code(self) -> int:
        if any(
            s.code in ("invalid_input", "unsupported_capability", "missing_dependency")
            for s in self.stages[:2]
        ):
            return 2
        if not self.complete:
            return 3
        return int(
            self.state == "different"
            or self.verification == "divergent"
            or any(
                p is not None
                and (
                    p.hybrid.r.decision == "alert"
                    or p.hybrid.result.decision == "alert"
                    or (
                        p.detection is not None
                        and any(d.result.decision == "alert" for d in p.detection.b)
                    )
                )
                for p in (self.source, self.target)
            )
        )
