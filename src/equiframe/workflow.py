"""Ordered ETL checkpoints over the existing native migration runner."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, Identifier, Text, _ExplicitOutcome, strict_bool_literal
from equiframe._regular_io import local_output_directory
from equiframe.errors import ArtifactIntegrityError, ResourceLimitError
from equiframe.evidence import inventory, load_json, publish_json, verify_files
from equiframe.execution import CancellationToken, RunContext
from equiframe.execution_types import ExecutionPlan, TableArtifact
from equiframe.local import LocalArtifactStore, local_path
from equiframe.migration.io import read_migration
from equiframe.migration.runner import migrate
from equiframe.migration.runner_types import MigrationResult, MigrationSpec
from equiframe.pipeline_types import EvidenceFile
from equiframe.ports import DataSource
from equiframe.tables import ArtifactInput, LoadedTable, capture_artifact
from equiframe.types import ArtifactRef


class InputBinding(FrozenModel):
    name: Text
    source: Text
    stage: Identifier | None = None
    output: Literal["source", "target"] = "target"


class WorkflowStage(FrozenModel):
    stage_id: Identifier
    migration: MigrationSpec
    inputs: tuple[InputBinding, ...]

    @model_validator(mode="after")
    def bindings(self) -> Self:
        names = tuple(binding.name for binding in self.inputs)
        if len(names) != len(set(names)) or set(names) != {
            t.name for t in self.migration.contract.inputs
        }:
            raise ValueError("stage bindings must cover exactly the stage contract inputs")
        return self


class WorkflowSpec(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: Identifier
    stages: tuple[WorkflowStage, ...] = Field(min_length=1, max_length=128)
    failure_policy: Literal["skip_dependents"] = "skip_dependents"
    resume: Annotated[Literal[False], BeforeValidator(strict_bool_literal)] = False
    timeout_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def dependencies(self) -> Self:
        prior: dict[str, WorkflowStage] = {}
        for stage in self.stages:
            if stage.stage_id in prior:
                raise ValueError("duplicate workflow stage")
            for binding in stage.inputs:
                if binding.stage is not None:
                    if binding.stage not in prior:
                        raise ValueError(
                            "stage dependencies must precede consumers; cycles rejected"
                        )
                    if binding.source != prior[binding.stage].migration.contract.output.name:
                        raise ValueError("binding source must identify the preceding output table")
            prior[stage.stage_id] = stage
        return self


class WorkflowCheckpoint(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .state and its migration decisions explicitly"

    stage_id: Identifier
    state: Literal["passed", "failed", "not_evaluable", "skipped"]
    code: Text
    migration: MigrationResult | None = None
    elapsed_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.state == "passed" and (self.migration is None or self.migration.exit_code != 0):
            raise ValueError("passed checkpoint requires an approved native migration")
        if self.state == "skipped" and self.migration is not None:
            raise ValueError("skipped checkpoint cannot have a successful fabricated execution")
        if self.migration is not None:
            expected = (
                "passed"
                if self.migration.exit_code == 0
                else ("failed" if self.migration.exit_code == 1 else "not_evaluable")
            )
            if self.state != expected:
                raise ValueError("checkpoint state contradicts native migration outcome")
        return self


class WorkflowResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .complete, .exit_code and the required checkpoints explicitly"

    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    spec: WorkflowSpec
    inputs: tuple[TableArtifact, ...]
    checkpoints: tuple[WorkflowCheckpoint, ...]
    first_divergent_stage: Identifier | None = None
    elapsed_seconds: float = Field(ge=0)
    evidence: tuple[EvidenceFile, ...]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if tuple(item.stage_id for item in self.checkpoints) != tuple(
            s.stage_id for s in self.spec.stages
        ):
            raise ValueError("workflow must record every stage in specification order")
        inputs = {table.name: table.data for table in self.inputs}
        if len(inputs) != len(self.inputs):
            raise ValueError("workflow external capture names must be unique")
        prior: dict[str, WorkflowCheckpoint] = {}
        for stage, checkpoint in zip(self.spec.stages, self.checkpoints, strict=True):
            migration = checkpoint.migration
            if migration is not None:
                declared_options = stage.migration.options
                actual_options = migration.spec.options
                options_match = actual_options == declared_options
                if self.spec.timeout_seconds is not None:
                    timeout = actual_options.timeout_seconds
                    options_match = (
                        actual_options.model_copy(
                            update={"timeout_seconds": declared_options.timeout_seconds}
                        )
                        == declared_options
                        and timeout is not None
                        and timeout <= self.spec.timeout_seconds
                        and (
                            declared_options.timeout_seconds is None
                            or timeout <= declared_options.timeout_seconds
                        )
                    )
                if (
                    not options_match
                    or migration.spec.model_copy(update={"options": declared_options})
                    != stage.migration
                ):
                    raise ValueError(
                        "workflow checkpoint migration differs from stage contract/plan/options"
                    )
                actual = {table.name: table.data.sha256 for table in migration.inputs}
                for binding in stage.inputs:
                    if binding.stage is None:
                        reference = inputs.get(binding.source)
                    else:
                        parent = prior[binding.stage]
                        if parent.state != "passed" or parent.migration is None:
                            raise ValueError(
                                "executed workflow checkpoint depends on an unapproved stage"
                            )
                        pipeline = (
                            parent.migration.source
                            if binding.output == "source"
                            else parent.migration.target
                        )
                        reference = (
                            pipeline.execution.output.data
                            if pipeline is not None
                            and pipeline.execution is not None
                            and pipeline.execution.output
                            else None
                        )
                    # A failed migration capture can retain only a prefix of
                    # inputs. MigrationResult already requires every input for
                    # a completed capture; bind all bytes actually retained.
                    if reference is None or (
                        binding.name in actual and actual[binding.name] != reference.sha256
                    ):
                        raise ValueError(
                            "workflow checkpoint input differs from fixed dependency capture"
                        )
            prior[stage.stage_id] = checkpoint
        divergent = next(
            (
                item.stage_id
                for item in self.checkpoints
                if item.migration is not None
                and (
                    item.migration.state == "different"
                    or item.migration.verification == "divergent"
                )
            ),
            None,
        )
        if self.first_divergent_stage != divergent:
            raise ValueError("first divergent stage contradicts checkpoint evidence")
        return self

    @property
    def complete(self) -> bool:
        return all(check.state == "passed" for check in self.checkpoints)

    @property
    def exit_code(self) -> int:
        if self.complete:
            return 0
        return 1 if any(check.state == "failed" for check in self.checkpoints) else 3

    @property
    def outputs(self) -> dict[str, ArtifactRef]:
        return {
            checkpoint.stage_id: checkpoint.migration.target.execution.output.data
            for checkpoint in self.checkpoints
            if checkpoint.state == "passed"
            and checkpoint.migration is not None
            and checkpoint.migration.target is not None
            and checkpoint.migration.target.execution is not None
            and checkpoint.migration.target.execution.output
        }


class _CapturedSource:
    """Replay fixed tables without discarding their separate index or provenance."""

    def __init__(self, inputs: Mapping[str, tuple[TableArtifact, bool]]) -> None:
        self._inputs = dict(inputs)

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._inputs)

    def resolve(self, name: str, *, context: RunContext) -> LoadedTable:
        artifact, meaningful_index = self._inputs[name]
        loaded = ArtifactInput(artifact.data).load(context)
        index = ArtifactInput(artifact.index).load(context).table if artifact.index else None
        return LoadedTable(
            loaded.table,
            native_types=tuple((column.name, column.engine_type) for column in artifact.columns),
            index=index,
            meaningful_index=meaningful_index,
            origin=artifact.data,
            notes=artifact.notes,
        )


def _capture_context(context: RunContext, consumers: tuple[WorkflowStage, ...]) -> RunContext:
    """Capture once up to the largest consumer budget; each stage enforces its own."""
    first = consumers[0].migration
    rows = []
    sizes = []
    for stage in consumers:
        execution = stage.migration.execution_options
        capture = stage.migration.options
        rows.append(
            min(execution.max_input_rows, capture.max_capture_rows)
            if execution.max_input_rows is not None
            else capture.max_capture_rows
        )
        sizes.append(execution.max_transport_bytes)
    # Transport limits can apply to serialized files as well as decoded tables.
    # A decoded migration capture limit must not become an IPC file-size limit.
    transport_bytes = None if None in sizes else max(size for size in sizes if size is not None)
    plan = ExecutionPlan(
        contract=first.contract,
        engine=first.source_engine,
        transformation_id="workflow_capture",
        options=first.execution_options.model_copy(
            update={"max_input_rows": max(rows), "max_transport_bytes": transport_bytes}
        ),
    )
    # Keep the workflow deadline, cancellation and captured-input inventory.
    return replace(context, plan=plan)


def run_workflow(
    spec: WorkflowSpec,
    *,
    source: DataSource,
    work_dir: Path,
    expected: Mapping[str, ArtifactRef] | None = None,
    cancellation: CancellationToken | None = None,
) -> WorkflowResult:
    """Fix external inputs once; downstream stages use verified checkpoint artifacts.

    Stage correspondences are explicit: each MigrationSpec compares one semantic
    output in two engines. Different internal relational DAGs may use registered
    compilers through migrate; arbitrary untrusted callbacks are not loaded here.
    Shared input capture uses the largest consuming stage's row/byte allowance;
    every migration subsequently enforces its own unchanged per-stage limits.
    """
    spec = WorkflowSpec.model_validate(spec)
    if expected is not None and not isinstance(expected, Mapping):
        raise TypeError("expected must be a mapping of stage identifiers to artifact references")
    expected = dict({} if expected is None else expected)
    unknown = set(expected) - {s.stage_id for s in spec.stages}
    if unknown:
        raise ValueError("expected references contain undeclared stage identifiers")
    start = time.perf_counter()
    directory = local_output_directory(work_dir) / ("workflow_" + uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    token = cancellation or CancellationToken()
    deadline = start + spec.timeout_seconds if spec.timeout_seconds else None
    first = spec.stages[0].migration
    store = LocalArtifactStore(directory / "artifacts")
    context = RunContext(
        directory.name,
        directory.name,
        ExecutionPlan(
            contract=first.contract,
            engine=first.source_engine,
            transformation_id="workflow_capture",
            options=first.execution_options,
        ),
        directory,
        store,
        token,
        deadline,
    )
    publish_json(spec, directory / "workflow-spec.json")
    external = sorted({b.source for s in spec.stages for b in s.inputs if b.stage is None})
    if not set(external) <= set(source.table_names):
        raise ValueError("workflow external bindings contain unavailable tables")
    captured: dict[str, tuple[TableArtifact, bool]] = {}
    capture_problems: dict[str, str] = {}
    expected_problems: dict[str, str] = {}
    for name in external:
        try:
            consumers = tuple(
                stage
                for stage in spec.stages
                if any(binding.stage is None and binding.source == name for binding in stage.inputs)
            )
            capture_context = _capture_context(context, consumers)
            capture_context.check()
            loaded = source.resolve(name, context=capture_context)
            capture_context.check_table(loaded.table, output=False)
            decoded_bytes = loaded.table.nbytes + (
                loaded.index.nbytes if loaded.index is not None else 0
            )
            if decoded_bytes > max(
                stage.migration.options.max_capture_bytes for stage in consumers
            ):
                raise ResourceLimitError("workflow input exceeds every consumer's capture budget")
            captured[name] = (
                capture_artifact(name, loaded, capture_context),
                loaded.meaningful_index,
            )
        except Exception as error:
            capture_problems[name] = type(error).__name__
    for expected_stage, reference in expected.items():
        try:
            context.check()
            temporary = directory / ("expected-" + expected_stage + "." + reference.format)
            store.get(reference, temporary)
            expected[expected_stage] = store.put(temporary, media_type=reference.media_type)
            temporary.unlink()
        except Exception as error:
            expected_problems[expected_stage] = type(error).__name__
    checkpoints: list[WorkflowCheckpoint] = []
    prior: dict[str, WorkflowCheckpoint] = {}
    for stage in spec.stages:
        stage_start = time.perf_counter()
        code = expected_problems.get(stage.stage_id) or next(
            (
                capture_problems[binding.source]
                for binding in stage.inputs
                if binding.stage is None and binding.source in capture_problems
            ),
            None,
        )
        if code is None:
            try:
                context.check()
            except Exception as error:
                code = type(error).__name__
        dependencies = tuple(b.stage for b in stage.inputs if b.stage is not None)
        if code or any(prior[dependency].state != "passed" for dependency in dependencies):
            checkpoint = WorkflowCheckpoint(
                stage_id=stage.stage_id,
                state="skipped",
                code=code or "dependency_not_approved",
                elapsed_seconds=time.perf_counter() - stage_start,
            )
        else:
            inputs = {}
            for binding in stage.inputs:
                if binding.stage is None:
                    inputs[binding.name] = captured[binding.source]
                else:
                    parent = prior[binding.stage].migration
                    if not (parent is not None):
                        raise AssertionError("Internal invariant check failed.")
                    pipeline = parent.source if binding.output == "source" else parent.target
                    if not (
                        pipeline is not None
                        and pipeline.execution is not None
                        and pipeline.execution.output is not None
                    ):
                        raise AssertionError("Internal invariant check failed.")
                    # Native migration checkpoints retain separate generated
                    # indexes. The next migration still enforces its own index
                    # policy rather than silently receiving only data bytes.
                    inputs[binding.name] = (pipeline.execution.output, False)
            try:
                migration_spec = stage.migration
                if deadline is not None:
                    remaining = deadline - time.perf_counter()
                    context.check()
                    timeout = migration_spec.options.timeout_seconds
                    options = migration_spec.options.model_copy(
                        update={
                            "timeout_seconds": min(remaining, timeout) if timeout else remaining
                        }
                    )
                    migration_spec = migration_spec.model_copy(update={"options": options})
                result = migrate(
                    migration_spec,
                    source=_CapturedSource(inputs),
                    work_dir=directory / stage.stage_id,
                    expected=expected.get(stage.stage_id),
                    cancellation=token,
                )
                state: Literal["passed", "failed", "not_evaluable", "skipped"] = (
                    "passed"
                    if result.exit_code == 0
                    else ("failed" if result.exit_code == 1 else "not_evaluable")
                )
                checkpoint = WorkflowCheckpoint(
                    stage_id=stage.stage_id,
                    state=state,
                    code="migration_" + str(result.exit_code),
                    migration=result,
                    elapsed_seconds=time.perf_counter() - stage_start,
                )
            except Exception as error:
                checkpoint = WorkflowCheckpoint(
                    stage_id=stage.stage_id,
                    state="not_evaluable",
                    code=type(error).__name__,
                    elapsed_seconds=time.perf_counter() - stage_start,
                )
        checkpoints.append(checkpoint)
        prior[stage.stage_id] = checkpoint
    workflow_result = WorkflowResult(
        run_id=directory.name,
        spec=spec,
        inputs=tuple(context.captured_inputs),
        checkpoints=tuple(checkpoints),
        first_divergent_stage=next(
            (
                c.stage_id
                for c in checkpoints
                if c.migration is not None
                and (c.migration.state == "different" or c.migration.verification == "divergent")
            ),
            None,
        ),
        elapsed_seconds=time.perf_counter() - start,
        evidence=inventory(directory),
    )
    publish_json(workflow_result, directory / "workflow.json")
    return workflow_result


def read_workflow(path: Path, *, verify: bool = True) -> WorkflowResult:
    """Read without running ETL; only explicit False skips inventory verification."""
    if type(verify) is not bool:
        raise TypeError("verify must be a bool; only explicit False skips integrity checks")
    path = path / "workflow.json" if path.is_dir() else path
    result = load_json(WorkflowResult, path)
    if not verify:
        return result
    directory = path.parent.resolve()
    verify_files(directory, result.evidence)
    actual = {
        item.relative_to(directory).as_posix()
        for item in directory.rglob("*")
        if item.is_file() and item.resolve() != path.resolve()
    }
    if actual != {item.path for item in result.evidence}:
        raise ArtifactIntegrityError("workflow files contradict the closed inventory")
    if load_json(WorkflowSpec, directory / "workflow-spec.json") != result.spec:
        raise ArtifactIntegrityError("workflow specification differs from evidence")
    listed = {item.path: item for item in result.evidence}
    for table in result.inputs:
        for reference in (table.data, *((table.index,) if table.index else ())):
            file = local_path(reference).resolve()
            if not file.is_relative_to(directory):
                raise ArtifactIntegrityError("workflow captured input escapes inventory")
            entry = listed.get(file.relative_to(directory).as_posix())
            if not entry or (reference.sha256, reference.size_bytes) != (
                entry.sha256,
                entry.size_bytes,
            ):
                raise ArtifactIntegrityError("workflow input reference differs from captured bytes")
    for checkpoint in result.checkpoints:
        if checkpoint.migration is not None:
            manifest = (
                directory
                / checkpoint.stage_id
                / checkpoint.migration.migration_id
                / "migration.json"
            )
            if read_migration(manifest) != checkpoint.migration:
                raise ArtifactIntegrityError("workflow checkpoint differs from migration evidence")
    return result
