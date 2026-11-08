"""Compose existing independent components without re-execution, fitting or oracle access."""

import platform
import time
from collections.abc import Callable
from datetime import datetime
from datetime import timezone as _timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TypeVar, cast
from uuid import uuid4

from pydantic import BaseModel

from equiframe._document_io import write_document as _write_document
from equiframe._regular_io import local_output_directory
from equiframe.comparison import ComparisonInput, compare
from equiframe.decision import combine_decisions
from equiframe.detector_types import DetectorBundle
from equiframe.detectors import detect
from equiframe.evidence import EventJournal, inventory, publish_json
from equiframe.execution import CancellationToken, execute
from equiframe.execution_types import ExecutionResult
from equiframe.pipeline_types import (
    PipelineResult,
    PipelineSpec,
    StageName,
    StageRecord,
    unavailable,
)
from equiframe.ports import DataSource, EngineAdapter
from equiframe.profile_types import ConversionReceipt, profile_digest
from equiframe.profiles import profile_execution
from equiframe.registry import TransformationRegistry
from equiframe.reporting import pipeline_summary, render_report
from equiframe.rules import RuleRegistry, evaluate_rules

UTC = _timezone.utc
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_T = TypeVar("_T")


def _environment() -> dict[str, object]:
    packages: dict[str, str] = {}
    for name in ("equiframe", "pydantic", "pyarrow", "pandas", "polars", "duckdb", "scikit-learn"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not-installed"
    # No environment variables, argv, host/user names, directories or authentication data.
    return {
        "schema_version": "1.0",
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": packages,
    }


class _Stages:
    def __init__(self, journal: EventJournal, cancellation: CancellationToken) -> None:
        self.journal = journal
        self.cancellation = cancellation
        self.records: list[StageRecord] = []

    def run(
        self,
        name: StageName,
        action: Callable[[], _ModelT],
        complete: Callable[[_ModelT], bool],
        *,
        skip: str | None = None,
        always: bool = False,
    ) -> _ModelT | None:
        if self.cancellation.cancelled and not always:
            skip = "cancelled"
        start = time.perf_counter()
        result: _ModelT | None = None
        if skip:
            record = StageRecord(stage=name, state="skipped", code=skip, elapsed_seconds=0.0)
        else:
            self.journal.emit(name, "started", "stage_started")
            try:
                result = action()
                succeeded = complete(result)
                record = StageRecord(
                    stage=name,
                    state="completed" if succeeded else "not_evaluable",
                    code="stage_completed" if succeeded else "component_unavailable",
                    elapsed_seconds=time.perf_counter() - start,
                )
            except Exception:
                # Exception text/type can contain SQL, values, tokens or paths from plugins.
                # Other independent stages can still produce evidence.
                result = None
                record = StageRecord(
                    stage=name,
                    state="failed",
                    code="operation_failed",
                    elapsed_seconds=time.perf_counter() - start,
                )
        self.records.append(record)
        self.journal.emit(name, record.state, record.code)
        return result


def run_pipeline(
    spec: PipelineSpec,
    *,
    source: DataSource,
    registry: TransformationRegistry,
    work_dir: Path | None = None,
    adapter: EngineAdapter | None = None,
    rule_registry: RuleRegistry | None = None,
    detector_bundle: DetectorBundle | None = None,
    comparison: ComparisonInput | None = None,
    cancellation: CancellationToken | None = None,
    conversion_provider: Callable[[ExecutionResult], tuple[ConversionReceipt, ...]] | None = None,
) -> PipelineResult:
    """Persist one isolated operation; failures/incompleteness never become no-alert.

    A manifest is published only after reports and journal are durable. Invalid
    top-level specs and publication failures raise; partial evidence remains.
    Callbacks are trusted, synchronous and cooperatively cancellable. No retries.
    """
    spec = PipelineSpec.model_validate(spec)
    if detector_bundle is not None:
        detector_bundle = DetectorBundle.model_validate(detector_bundle)
        if spec.profile is None:
            raise ValueError("detectors require an explicit profile specification")
    identifier = "pipeline_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    token = cancellation if cancellation is not None else CancellationToken()
    started_at = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    journal = EventJournal(directory, identifier)
    journal.emit("pipeline", "started", "pipeline_started")
    publish_json(spec, directory / "pipeline.json")
    publish_json(_environment(), directory / "environment.json")
    if detector_bundle is not None:
        publish_json(detector_bundle, directory / "detector-bundle.json")
    stages = _Stages(journal, token)
    execution = stages.run(
        "execution",
        lambda: execute(
            spec.execution,
            source=source,
            registry=registry,
            adapter=adapter,
            work_dir=directory,
            cancellation=token,
        ),
        lambda value: value.state == "completed",
    )
    rules = stages.run(
        "rules",
        lambda: evaluate_rules(
            _present(execution),
            registry=rule_registry,
            options=spec.rule_options,
            work_dir=directory,
            cancellation=token,
        ),
        lambda value: value.complete,
        skip="execution_unavailable" if execution is None else None,
    )
    profile = stages.run(
        "profile",
        lambda: profile_execution(
            _present(execution),
            spec=_present(spec.profile),
            options=spec.profile_options,
            work_dir=directory,
            cancellation=token,
            conversions=conversion_provider(_present(execution)) if conversion_provider else (),
        ),
        lambda value: value.complete,
        skip="not_requested"
        if spec.profile is None
        else "execution_unavailable"
        if execution is None
        else None,
    )
    detection = stages.run(
        "detection",
        lambda: detect(_present(detector_bundle), (_present(profile).vector,)),
        lambda value: all(d.result.complete for d in (*value.m, *value.b)),
        skip="not_requested"
        if detector_bundle is None
        else "profile_unavailable"
        if profile is None or not profile.complete
        else None,
    )
    compared = stages.run(
        "comparison",
        lambda: compare(
            _present(execution),
            cast(ComparisonInput, comparison),
            contract=spec.execution.contract,
            policy=spec.comparison_policy,
            options=spec.comparison_options,
            reference=spec.comparison_reference,
            work_dir=directory,
            cancellation=token,
        ),
        lambda value: value.complete,
        skip="not_requested"
        if comparison is None
        else "execution_unavailable"
        if execution is None
        else None,
    )
    hybrid = stages.run(
        "hybrid",
        lambda: combine_decisions(
            rules if rules is not None else unavailable("rules_unavailable"),
            detection.m[0].result if detection is not None else unavailable("detector_unavailable"),
        ),
        lambda value: value.result.complete,
        always=True,
    )
    if hybrid is None:
        raise RuntimeError("cannot persist a pipeline without a valid hybrid decision")
    # Self-contained typed results are independently addressable in addition to child manifests.
    for name, value in (
        ("execution", execution),
        ("rules", rules),
        ("profile", profile),
        ("detection", detection),
        ("comparison", compared),
        ("hybrid", hybrid),
    ):
        if value is not None:
            publish_json(value, directory / (name + ".json"))
    journal.emit("pipeline", "finished", "pipeline_finished")
    result = PipelineResult(
        pipeline_id=identifier,
        spec=spec,
        spec_sha256=profile_digest(spec.model_dump(mode="json")),
        started_at=started_at,
        finished_at=datetime.now(UTC).isoformat(),
        elapsed_seconds=time.perf_counter() - start,
        detection_requested=detector_bundle is not None,
        comparison_requested=comparison is not None,
        cancelled=token.cancelled,
        stages=tuple(stages.records),
        execution=execution,
        rules=rules,
        profile=profile,
        detection=detection,
        comparison=compared,
        hybrid=hybrid,
        evidence=(),
        event_count=journal.count,
        event_head_sha256=journal.head,
    )
    summary = pipeline_summary(result)
    publish_json(summary, directory / "report.json")
    _write_document(directory / "report.html", render_report(summary).encode("utf-8"))
    result = PipelineResult.model_validate(
        {**result.model_dump(), "evidence": inventory(directory)}
    )
    publish_json(result, directory / "manifest.json")
    return result


def _present(value: _T | None) -> _T:
    if value is None:
        raise ValueError("required component unavailable")
    return value
