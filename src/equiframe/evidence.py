"""Exclusive evidence publication, chained events and verification without executing code."""

import hashlib
import json
import os
from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, Text
from equiframe._document_io import write_document as _write_document
from equiframe._regular_io import absolute_path, open_regular_file, regular_directory, regular_files
from equiframe.errors import ArtifactIntegrityError, ArtifactIOError, ResourceLimitError
from equiframe.local import local_path
from equiframe.pipeline_types import EvidenceFile, PipelineResult
from equiframe.types import ArtifactRef, Sha256

UTC = _timezone.utc
_ModelT = TypeVar("_ModelT", bound=BaseModel)

MAX_DOCUMENT_BYTES = 64 * 1024 * 1024


class _EnvironmentManifest(FrozenModel):
    """The persisted pipeline environment is versioned evidence, not opaque JSON.

    These fields were emitted by the original 1.0 writer. Reading checks their
    format, without requiring the reader's packages or platform to match them.
    """

    schema_version: Literal["1.0"]
    python: str
    system: str
    machine: str
    packages: dict[str, str]


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("nonstandard JSON number")


def parse_json(data: bytes) -> object:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)


def load_json(model: type[_ModelT], path: Path) -> _ModelT:
    with open_regular_file(path) as stream:
        data = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ResourceLimitError("JSON document exceeds the 64 MiB budget")
    parse_json(data)
    return model.model_validate_json(data)


def publish_json(value: BaseModel | dict[str, object], path: Path) -> None:
    if isinstance(value, BaseModel):
        value = type(value).model_validate(value).model_dump(mode="json")
    _write_document(path, canonical_bytes(value) + b"\n")


class EvidenceEvent(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    sequence: NonNegativeInt
    timestamp: Text
    operation_id: Identifier
    stage: Identifier
    state: Identifier
    code: Identifier
    previous_sha256: Sha256
    sha256: Sha256


class EventJournal:
    """One writer per unique operation; each event is flushed before work continues."""

    def __init__(self, directory: Path, operation_id: str) -> None:
        self.path = directory / "events.jsonl"
        self.operation_id = operation_id
        self.count = 0
        self.head = "0" * 64
        with self.path.open("xb"):
            pass

    def emit(self, stage: str, state: str, code: str) -> None:
        payload = {
            "schema_version": "1.0",
            "sequence": self.count,
            "timestamp": datetime.now(UTC).isoformat(),
            "operation_id": self.operation_id,
            "stage": stage,
            "state": state,
            "code": code,
            "previous_sha256": self.head,
        }
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        event = EvidenceEvent.model_validate({**payload, "sha256": digest})
        with self.path.open("ab") as stream:
            stream.write(canonical_bytes(event.model_dump(mode="json")) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.head = digest
        self.count += 1


def verify_events(path: Path, *, operation_id: str) -> tuple[EvidenceEvent, ...]:
    head = "0" * 64
    events: list[EvidenceEvent] = []
    with open_regular_file(path) as stream:
        total = 0
        while raw := stream.readline(1024 * 1024 + 1):
            total += len(raw)
            if len(raw) > 1024 * 1024 or total > MAX_DOCUMENT_BYTES:
                raise ResourceLimitError("event journal exceeds verification budget")
            if not raw.endswith(b"\n"):
                raise ArtifactIntegrityError("truncated evidence event")
            parse_json(raw)
            event = EvidenceEvent.model_validate_json(raw)
            payload = event.model_dump(mode="json", exclude={"sha256"})
            if (
                event.sequence != len(events)
                or event.previous_sha256 != head
                or event.operation_id != operation_id
                or hashlib.sha256(canonical_bytes(payload)).hexdigest() != event.sha256
            ):
                raise ArtifactIntegrityError("event chain integrity mismatch")
            head = event.sha256
            events.append(event)
    return tuple(events)


def describe_file(path: Path, directory: Path) -> EvidenceFile:
    path = absolute_path(path)
    root = regular_directory(directory).resolve()
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ArtifactIntegrityError("evidence file escapes its operation directory")
    digest = hashlib.sha256()
    size = 0
    with open_regular_file(path) as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return EvidenceFile(
        path=path.relative_to(root).as_posix(), sha256=digest.hexdigest(), size_bytes=size
    )


def inventory(directory: Path) -> tuple[EvidenceFile, ...]:
    return tuple(describe_file(path, directory) for path in regular_files(directory))


def verify_files(directory: Path, files: tuple[EvidenceFile, ...]) -> None:
    for item in files:
        path = directory / item.path
        try:
            observed = describe_file(path, directory)
        except (OSError, ArtifactIOError) as error:
            raise ArtifactIntegrityError("evidence file is missing or unreadable") from error
        if observed != item:
            raise ArtifactIntegrityError("evidence SHA-256 or size mismatch")


def _verify_pipeline_artifacts(directory: Path, result: PipelineResult) -> None:
    """Bind captured artifact references to the verified operation inventory.

    Comparison sources keep the original table/execution as provenance, which
    may belong to another operation. Their captured ``data`` snapshots, rather
    than those external original references, are the evidence owned here.
    """
    root = directory.resolve()
    listed = {item.path: item for item in result.evidence}
    references: list[ArtifactRef] = []
    if result.execution is not None:
        for table in (
            *result.execution.inputs,
            *((result.execution.output,) if result.execution.output else ()),
        ):
            references.append(table.data)
            if table.index:
                references.append(table.index)
    if result.rules is not None:
        references.extend(
            check.findings
            for check in (*result.rules.preconditions, *result.rules.rules)
            if check.findings is not None
        )
    if result.profile is not None:
        references.extend(result.profile.metadata.artifacts)
    if result.comparison is not None:
        references.append(result.comparison.differences)
        references.extend(
            source.data
            for source in (result.comparison.left, result.comparison.right)
            if source is not None
        )
    for reference in references:
        try:
            artifact = local_path(reference).resolve()
        except Exception as error:
            raise ArtifactIntegrityError("captured evidence requires a local artifact") from error
        if not artifact.is_relative_to(root):
            raise ArtifactIntegrityError("captured artifact escapes its operation directory")
        item = listed.get(artifact.relative_to(root).as_posix())
        if item is None:
            raise ArtifactIntegrityError("captured artifact is missing from the evidence inventory")
        if (reference.sha256, reference.size_bytes) != (item.sha256, item.size_bytes):
            raise ArtifactIntegrityError("captured artifact reference contradicts its inventory")


def read_pipeline(path: Path, *, verify: bool = True) -> PipelineResult:
    """Read a manifest; only explicit False skips byte and journal verification."""
    if type(verify) is not bool:
        raise TypeError("verify must be a bool; only explicit False skips integrity checks")
    path = path / "manifest.json" if path.is_dir() else path
    result = load_json(PipelineResult, path)
    if verify:
        directory = path.parent
        verify_files(directory, result.evidence)
        actual = {
            item.relative_to(directory).as_posix()
            for item in directory.rglob("*")
            if item.is_file() and item != path
        }
        if actual != {item.path for item in result.evidence}:
            raise ArtifactIntegrityError("operation files contradict the final evidence inventory")
        _verify_pipeline_artifacts(directory, result)
        required = {
            "events.jsonl",
            "pipeline.json",
            "environment.json",
            "report.json",
            "report.html",
        }
        if not required <= {item.path for item in result.evidence}:
            raise ArtifactIntegrityError("final manifest is missing required evidence")
        load_json(_EnvironmentManifest, directory / "environment.json")
        events = verify_events(directory / "events.jsonl", operation_id=result.pipeline_id)
        if (
            len(events) != result.event_count
            or not events
            or events[-1].sha256 != result.event_head_sha256
            or events[0].stage != "pipeline"
            or events[0].state != "started"
            or events[-1].stage != "pipeline"
            or events[-1].state != "finished"
        ):
            raise ArtifactIntegrityError("final journal does not match its manifest")
        if load_json(type(result.spec), directory / "pipeline.json") != result.spec:
            raise ArtifactIntegrityError("persisted pipeline configuration mismatch")
        terminal = tuple(
            (event.stage, event.state, event.code)
            for event in events
            if event.stage != "pipeline" and event.state != "started"
        )
        if terminal != tuple((stage.stage, stage.state, stage.code) for stage in result.stages):
            raise ArtifactIntegrityError("journal stage outcomes contradict the final result")
        listed = {item.path for item in result.evidence}
        for name, value in (
            ("execution", result.execution),
            ("rules", result.rules),
            ("profile", result.profile),
            ("detection", result.detection),
            ("comparison", result.comparison),
            ("hybrid", result.hybrid),
        ):
            if value is not None and (
                name + ".json" not in listed
                or load_json(type(value), directory / (name + ".json")) != value
            ):
                raise ArtifactIntegrityError("persisted component contradicts the final result")
        if result.detection_requested:
            from equiframe.detector_types import DetectorBundle, detector_fingerprint

            if "detector-bundle.json" not in listed:
                raise ArtifactIntegrityError("requested detector bundle is missing")
            bundle = load_json(DetectorBundle, directory / "detector-bundle.json")
            if (
                result.detection is not None
                and result.detection.bundle_sha256 != detector_fingerprint(bundle)
            ):
                raise ArtifactIntegrityError("detector bundle does not match the scored bundle")
            if result.detection is not None:
                from equiframe.preprocessing import transform_profiles
                from equiframe.profile_types import profile_digest

                if result.detection.scores.fit_sha256 != detector_fingerprint(bundle.fit):
                    raise ArtifactIntegrityError("scored fit fingerprint mismatch")
                if result.detection.scores.matrix_sha256 is not None:
                    if not (result.profile is not None):
                        raise AssertionError("Internal invariant check failed.")
                    matrix = transform_profiles(bundle.fit.preprocessor, (result.profile.vector,))
                    if result.detection.scores.matrix_sha256 != profile_digest(
                        matrix.model_dump(mode="json")
                    ):
                        raise ArtifactIntegrityError("scored matrix does not belong to the profile")
        from equiframe._report_format_v1 import pipeline_html_v1, pipeline_summary_v1

        summary = pipeline_summary_v1(result)
        if parse_json((directory / "report.json").read_bytes()) != summary or (
            (directory / "report.html").read_bytes() != pipeline_html_v1(summary).encode("utf8")
        ):
            raise ArtifactIntegrityError("report contradicts the final result")
    return result


def inspect_evidence(directory: Path) -> dict[str, object]:
    """An interrupted operation remains inspectable but can never claim completion."""
    if (directory / "migration.json").exists():
        from equiframe.migration import migration_summary, read_migration

        migrated = read_migration(directory)
        return {
            **migration_summary(migrated),
            "finalized": True,
            "events": migrated.event_count,
            "files": len(migrated.evidence),
        }
    if (directory / "reduction.json").exists():
        from equiframe.reduction import read_reduction

        reduced = read_reduction(directory)
        return {
            "reduction_id": reduced.reduction_id,
            "finalized": True,
            "complete": reduced.status in ("reduced", "unchanged"),
            "status": reduced.status,
            "evaluations": reduced.evaluations,
            "minimality": reduced.minimality,
            "files": len(reduced.evidence),
        }
    if (directory / "manifest.json").exists():
        result = read_pipeline(directory)
        return {
            "pipeline_id": result.pipeline_id,
            "finalized": True,
            "complete": result.complete,
            "exit_code": result.exit_code,
            "events": result.event_count,
            "files": len(result.evidence),
        }
    events = verify_events(directory / "events.jsonl", operation_id=directory.name)
    if directory.name.startswith("migration_"):
        return {
            "migration_id": directory.name,
            "finalized": False,
            "complete": False,
            "exit_code": 3,
            "events": len(events),
            "last_stage": events[-1].stage if events else None,
        }
    return {
        "pipeline_id": directory.name,
        "finalized": False,
        "complete": False,
        "exit_code": 3,
        "events": len(events),
        "last_stage": events[-1].stage if events else None,
    }
