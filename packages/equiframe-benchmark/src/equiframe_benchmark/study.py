"""Run frozen held-out cases without fitting, fabricating labels or dropping failures."""

from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast
from uuid import uuid4

import equiframe as ef
from equiframe.evidence import inventory, verify_files
from equiframe.local import local_path
from pydantic import model_validator
from typing_extensions import Self

from equiframe_benchmark.evaluation import (
    Engine,
    EvaluationConfig,
    EvaluationRecord,
    EvaluationReport,
    evaluate_records,
)
from equiframe_benchmark.freeze import (
    FreezeAudit,
    FreezeManifest,
    FrozenFamilyModel,
    TestCaseDefinition,
    audit_freeze,
)
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import Digest, Document, Scenario, Text, digest, same_content
from equiframe_benchmark.reproduction import _bounded_json, _stream_file
from equiframe_benchmark.tables import TableExport, read_tables, write_tables

UTC = _timezone.utc


class StudyCaseResult(Document):
    case_id: Text
    pipeline_directory: Text | None
    pipeline: ef.PipelineResult | None
    output_replay: ef.ComparisonResult | None
    error: Text | None
    record: EvaluationRecord

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.case_id != self.record.case_id:
            raise ValueError("case result must preserve its declared case identity")
        if self.pipeline is None:
            if self.pipeline_directory is not None or self.error is None:
                raise ValueError("missing pipeline requires a recorded operation failure")
        elif self.pipeline_directory != self.pipeline.pipeline_id or self.error is not None:
            raise ValueError("pipeline directory and operation result must agree")
        return self


def _binding_reason(
    case: TestCaseDefinition,
    scenario: Scenario,
    pipeline: ef.PipelineResult | None,
    replay: ef.ComparisonResult | None,
) -> str | None:
    execution = pipeline.execution if pipeline is not None else None
    if execution is None or execution.state != "completed" or execution.output is None:
        return "native_execution_unavailable"
    if execution.implementation_version != case.candidate.implementation:
        return "implementation_version_changed"
    supplied = {table.name: table.data for table in execution.inputs}
    if set(supplied) != {item.name for item in scenario.inputs} or any(
        not same_content(item.artifact, supplied[item.name]) for item in scenario.inputs
    ):
        return "scenario_inputs_changed"
    if replay is None or replay.state != "equivalent" or not replay.complete:
        return "reviewed_output_not_reproduced"
    return None


def _unavailable(reason: str) -> ef.ComponentDecision:
    return ef.ComponentDecision(decision="not_evaluable", complete=False, reason=reason)


def _config(freeze: FreezeManifest, after: FreezeAudit) -> EvaluationConfig:
    # Changed sources cannot produce a scientific final report. Preserve the raw
    # failed run as a pilot report with its separately bound original freeze.
    final = freeze.definition.mode == "final" and after == freeze.audit and after.ready
    return EvaluationConfig.model_validate(
        freeze.definition.evaluation.model_copy(
            update={
                "mode": "final" if final else "pilot",
                "freeze_sha256": digest(freeze) if final else None,
            }
        )
    )


def _record(
    case: TestCaseDefinition,
    scenario: Scenario,
    group_id: str,
    model: FrozenFamilyModel,
    pipeline: ef.PipelineResult | None,
    replay: ef.ComparisonResult | None,
    error: str | None,
    config: EvaluationConfig,
) -> EvaluationRecord:
    if pipeline is not None and pipeline.spec != case.pipeline:
        raise ValueError("pipeline must use the exact frozen case configuration")
    if pipeline is not None and pipeline.detection_requested != (model.bundle is not None):
        raise ValueError("pipeline detector request must match the frozen family bundle")
    if (
        pipeline is not None
        and pipeline.detection is not None
        and (
            model.bundle is None
            or pipeline.detection.bundle_sha256 != ef.detector_fingerprint(model.bundle)
        )
    ):
        raise ValueError("pipeline detection must use the frozen family bundle")
    execution = pipeline.execution if pipeline is not None else None
    valid_execution = execution is not None and execution.state == "completed"
    reason = _binding_reason(case, scenario, pipeline, replay)
    oracle = case.oracle
    oracle_state = (
        oracle.status
        if oracle is not None and reason is None
        else ("pending" if oracle is None and reason is None else "not_evaluable")
    )
    label = cast(
        Literal["normal", "divergent"] | None,
        oracle.label if oracle is not None and oracle_state == "confirmed" else None,
    )
    failure = error or (
        "native_execution_unavailable"
        if not valid_execution
        else "pipeline_incomplete"
        if pipeline is not None and not pipeline.complete
        else reason
    )
    r = (
        pipeline.hybrid.r
        if valid_execution and pipeline is not None
        else _unavailable(failure or "pipeline_unavailable")
    )
    m = (
        pipeline.hybrid.m
        if valid_execution and pipeline is not None
        else _unavailable(failure or "pipeline_unavailable")
    )
    h = (
        pipeline.hybrid.result
        if valid_execution and pipeline is not None
        else _unavailable(failure or "pipeline_unavailable")
    )
    detection = pipeline.detection if valid_execution and pipeline is not None else None
    b = (
        detection.b[0].result
        if detection is not None
        else _unavailable(model.reason or "detector_unavailable")
    )
    return EvaluationRecord(
        case_id=case.case_id,
        scenario_id=case.scenario_id,
        group_id=group_id,
        family=scenario.family,
        migration=case.migration,
        engine=cast(Engine, case.pipeline.execution.engine),
        candidate_sha256=digest(case.candidate),
        pipeline_sha256=digest(pipeline) if pipeline is not None else None,
        oracle_sha256=digest(oracle) if oracle is not None else None,
        oracle_state=oracle_state,
        oracle_label=label,
        r=r,
        m=m,
        b=b,
        h=h,
        m_score=cast(float | None, detection.m[0].score) if detection is not None else None,
        b_score=detection.b[0].score if detection is not None else None,
        detector_bundle_sha256=ef.detector_fingerprint(model.bundle) if model.bundle else None,
        freeze_sha256=config.freeze_sha256,
        failure_reason=failure,
    )


def _validate_replay(
    case: TestCaseDefinition,
    scenario: Scenario,
    pipeline: ef.PipelineResult | None,
    replay: ef.ComparisonResult | None,
) -> None:
    if replay is None:
        return
    execution = pipeline.execution if pipeline is not None else None
    if execution is None or execution.output is None or execution.state != "completed":
        raise ValueError("output replay requires an actual completed captured output")
    if (
        replay.spec != scenario.comparison
        or replay.reference != "peer"
        or replay.options != case.pipeline.comparison_options
        or (
            replay.left is not None
            and (
                replay.left.table != execution.output
                or not same_content(replay.left.data, execution.output.data)
            )
        )
        or (replay.right is not None and not same_content(replay.right.data, case.candidate.output))
    ):
        raise ValueError("output replay must bind the fresh output and reviewed candidate")


class StudyResult(Document):
    study_id: Text
    freeze: FreezeManifest
    freeze_sha256: Digest
    audit_before: FreezeAudit
    audit_after: FreezeAudit
    started_at: Text
    finished_at: Text
    cases: tuple[StudyCaseResult, ...]
    evaluation: EvaluationReport
    tables: TableExport
    evidence: tuple[ef.EvidenceFile, ...]

    @model_validator(mode="after")
    def bindings(self) -> Self:
        if self.freeze_sha256 != digest(self.freeze) or self.audit_before != self.freeze.audit:
            raise ValueError("study must start from its exact verified frozen manifest")
        if self.audit_after.definition_sha256 != self.freeze.definition_sha256:
            raise ValueError("after-run audit must inspect the same frozen definition")
        definitions = self.freeze.definition.cases
        if tuple(c.case_id for c in self.cases) != tuple(c.case_id for c in definitions):
            raise ValueError("study must retain each scheduled case exactly once")
        config = _config(self.freeze, self.audit_after)
        scenarios = {s.scenario_id: s for s in self.freeze.definition.catalog.scenarios}
        groups = {a.scenario_id: a.group_id for a in self.freeze.definition.splits.assignments}
        models = {m.family: m for m in self.freeze.definition.models}
        records = []
        for definition, result in zip(definitions, self.cases, strict=True):
            scenario = scenarios[definition.scenario_id]
            _validate_replay(definition, scenario, result.pipeline, result.output_replay)
            expected = _record(
                definition,
                scenario,
                groups[scenario.scenario_id],
                models[scenario.family],
                result.pipeline,
                result.output_replay,
                result.error,
                config,
            )
            if result.record != expected:
                raise ValueError(
                    "evaluation record differs from its original frozen case and pipeline"
                )
            records.append(expected)
        if self.evaluation != evaluate_records(tuple(records), config):
            raise ValueError("evaluation must regenerate from every original case result")
        if (
            self.tables.evaluation_sha256 != digest(self.evaluation)
            or self.tables.scientific != self.evaluation.scientific
        ):
            raise ValueError("table export must bind the exact derived evaluation")
        if len({e.path for e in self.evidence}) != len(self.evidence):
            raise ValueError("study evidence paths must be unique")
        return self

    @property
    def complete(self) -> bool:
        scenarios = {s.scenario_id: s for s in self.freeze.definition.catalog.scenarios}
        return bool(self.cases) and (
            self.audit_after == self.audit_before
            and self.audit_after.ready
            and all(
                c.pipeline is not None
                and c.pipeline.complete
                and _binding_reason(d, scenarios[d.scenario_id], c.pipeline, c.output_replay)
                is None
                for d, c in zip(self.freeze.definition.cases, self.cases, strict=True)
            )
        )

    @property
    def scientific(self) -> bool:
        return self.complete and self.evaluation.scientific

    @property
    def exit_code(self) -> int:
        if not self.complete:
            return 3
        return int(any(c.pipeline is not None and c.pipeline.exit_code == 1 for c in self.cases))


def run_study(
    manifest: FreezeManifest,
    *,
    registry: ef.TransformationRegistry,
    rule_registry: ef.RuleRegistry | None = None,
    work_dir: Path | None = None,
    cancellation: ef.CancellationToken | None = None,
) -> StudyResult:
    """Consume an existing seal; run each native case once, never train or review.

    Pilot execution preserves every declared scientific blocker. A failed after
    audit keeps raw evidence but cannot produce a scientific final report.
    Cancellation is cooperative and keeps all remaining scheduled case records.
    """
    manifest = FreezeManifest.model_validate(manifest)
    if any(
        c.pipeline.execution.engine not in ("pandas", "polars", "duckdb")
        for c in manifest.definition.cases
    ):
        raise ValueError("study cases require one of the three declared native engines")
    before = audit_freeze(manifest.definition, rule_registry=rule_registry)
    if before != manifest.audit or not before.ready:
        raise ValueError("frozen sources or gate changed before the study")
    identifier = "study_" + uuid4().hex
    directory = (work_dir or Path.cwd() / "equiframe-studies").resolve() / identifier
    directory.mkdir(parents=True, exist_ok=False)
    save_document(manifest, directory / "freeze.json")
    save_document(before, directory / "audit-before.json")
    started = datetime.now(UTC).isoformat()
    token = cancellation if cancellation is not None else ef.CancellationToken()
    scenarios = {s.scenario_id: s for s in manifest.definition.catalog.scenarios}
    models = {m.family: m for m in manifest.definition.models}
    groups = {a.scenario_id: a.group_id for a in manifest.definition.splits.assignments}
    produced: list[tuple[ef.PipelineResult | None, ef.ComparisonResult | None, str | None]] = []
    for position, case in enumerate(manifest.definition.cases):
        scenario = scenarios[case.scenario_id]
        model = models[scenario.family]
        folder = directory / f"case-{position}"
        folder.mkdir()
        pipeline = None
        replay = None
        error = None
        try:
            pipeline = ef.run_pipeline(
                case.pipeline,
                source=ef.LocalDataSource({i.name: i.artifact for i in scenario.inputs}),
                registry=registry,
                rule_registry=rule_registry,
                detector_bundle=model.bundle,
                comparison=scenario.expected,
                cancellation=token,
                work_dir=folder,
            )
        except Exception as exc:
            error = "pipeline_operation_failed:" + type(exc).__name__
        execution = pipeline.execution if pipeline is not None else None
        if (
            execution is not None
            and execution.state == "completed"
            and execution.output is not None
        ):
            try:
                replay = ef.compare(
                    execution.output,
                    case.candidate.output,
                    contract=scenario.comparison.contract,
                    policy=scenario.comparison.policy,
                    options=case.pipeline.comparison_options,
                    reference="peer",
                    cancellation=token,
                    work_dir=folder / "replay",
                )
            except Exception:
                # Its partial files remain inventoried. No replay means no label reuse.
                replay = None
        produced.append((pipeline, replay, error))
    after = audit_freeze(manifest.definition, rule_registry=rule_registry)
    save_document(after, directory / "audit-after.json")
    config = _config(manifest, after)
    results = []
    for case, (pipeline, replay, error) in zip(manifest.definition.cases, produced, strict=True):
        scenario = scenarios[case.scenario_id]
        record = _record(
            case,
            scenario,
            groups[scenario.scenario_id],
            models[scenario.family],
            pipeline,
            replay,
            error,
            config,
        )
        case_result = StudyCaseResult(
            case_id=case.case_id,
            pipeline_directory=pipeline.pipeline_id if pipeline is not None else None,
            pipeline=pipeline,
            output_replay=replay,
            error=error,
            record=record,
        )
        results.append(case_result)
    evaluation = evaluate_records(tuple(r.record for r in results), config)
    save_document(evaluation, directory / "evaluation.json")
    tables = write_tables(evaluation, directory / "tables")
    for position, result in enumerate(results):
        save_document(result, directory / f"case-{position}" / "case.json")
    study_result = StudyResult(
        study_id=identifier,
        freeze=manifest,
        freeze_sha256=digest(manifest),
        audit_before=before,
        audit_after=after,
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
        cases=tuple(results),
        evaluation=evaluation,
        tables=tables,
        evidence=inventory(directory),
    )
    save_document(study_result, directory / "study.json")
    return study_result


def _owned(directory: Path, reference: ef.ArtifactRef, listed: dict[str, ef.EvidenceFile]) -> None:
    path = local_path(reference).resolve()
    if not path.is_relative_to(directory):
        raise ef.ArtifactIntegrityError("study comparison evidence escapes its operation")
    item = listed.get(path.relative_to(directory).as_posix())
    if item is None or (item.sha256, item.size_bytes) != (reference.sha256, reference.size_bytes):
        raise ef.ArtifactIntegrityError("study comparison artifact contradicts its inventory")


def _recheck_confirmed_replay(
    definition: TestCaseDefinition,
    scenario: Scenario,
    case: StudyCaseResult,
) -> None:
    """Recheck captured rows that authorize reuse of a confirmed review label."""
    if case.record.oracle_state != "confirmed":
        return
    execution = case.pipeline.execution if case.pipeline is not None else None
    replay = case.output_replay
    if (
        execution is None
        or execution.state != "completed"
        or execution.output is None
        or replay is None
        or not replay.complete
        or replay.state != "equivalent"
    ):
        raise ef.ArtifactIntegrityError("confirmed label requires a complete output replay")
    try:
        with TemporaryDirectory(prefix="equiframe-study-recheck-") as temporary:
            observed = ef.compare(
                execution.output,
                definition.candidate.output,
                contract=scenario.comparison.contract,
                policy=scenario.comparison.policy,
                options=definition.pipeline.comparison_options,
                reference="peer",
                work_dir=Path(temporary),
            )
    except Exception as exc:
        raise ef.ArtifactIntegrityError("confirmed replay physical verification failed") from exc
    if not observed.complete or observed.state != "equivalent" or observed.counts != replay.counts:
        raise ef.ArtifactIntegrityError(
            "confirmed label requires the physically reproduced reviewed output"
        )


def read_study(
    directory: Path,
    *,
    rule_registry: ef.RuleRegistry | None = None,
    max_bytes: int = 64 * 1024**2,
) -> StudyResult:
    """Verify raw cases, pipeline evidence and regenerated tables without native ETL."""
    path = directory / "study.json" if directory.is_dir() else directory
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("study JSON byte budget must be a positive integer")
    result, original_sha256 = _bounded_json(StudyResult, path, max_bytes)
    directory = path.parent.resolve()
    verify_files(directory, result.evidence)
    listed = {item.path: item for item in result.evidence}
    actual = {
        p.relative_to(directory).as_posix()
        for p in directory.rglob("*")
        if p.is_file() and p != path.resolve()
    }
    if actual != set(listed):
        raise ef.ArtifactIntegrityError("study operation inventory is not closed")
    for name, model, expected in (
        ("freeze.json", FreezeManifest, result.freeze),
        ("audit-before.json", FreezeAudit, result.audit_before),
        ("audit-after.json", FreezeAudit, result.audit_after),
        ("evaluation.json", EvaluationReport, result.evaluation),
    ):
        if name not in listed or load_document(model, directory / name) != expected:
            raise ef.ArtifactIntegrityError("study source manifest contradicts final evidence")
    scenarios = {s.scenario_id: s for s in result.freeze.definition.catalog.scenarios}
    for position, case in enumerate(result.cases):
        folder = directory / f"case-{position}"
        if load_document(StudyCaseResult, folder / "case.json") != case:
            raise ef.ArtifactIntegrityError("case receipt contradicts the final study")
        if (
            case.pipeline is not None
            and ef.read_pipeline(folder / case.pipeline.pipeline_id) != case.pipeline
        ):
            raise ef.ArtifactIntegrityError("pipeline evidence contradicts its study case")
        if case.output_replay is not None:
            replay = case.output_replay
            for ref in (replay.differences, *(s.data for s in (replay.left, replay.right) if s)):
                _owned(directory, ref, listed)
            manifest_path = local_path(replay.differences).parent / "comparison.json"
            if ef.read_comparison(manifest_path) != replay:
                raise ef.ArtifactIntegrityError("output replay differs from its original manifest")
            if (
                len(tuple(ef.iter_differences(replay.differences)))
                != replay.counts.difference_records
            ):
                raise ef.ArtifactIntegrityError(
                    "output replay count differs from its actual evidence"
                )
        definition = result.freeze.definition.cases[position]
        _recheck_confirmed_replay(definition, scenarios[definition.scenario_id], case)
    if read_tables(directory / "tables", report=result.evaluation) != result.tables:
        raise ef.ArtifactIntegrityError("tables contradict the study evaluation")
    observed = audit_freeze(result.freeze.definition, rule_registry=rule_registry)
    if observed != result.audit_after:
        raise ef.ArtifactIntegrityError("frozen sources no longer match the after-study audit")
    if _stream_file(path, max_bytes)[0] != original_sha256:
        raise ef.ArtifactIntegrityError("study manifest changed during verification")
    return result
