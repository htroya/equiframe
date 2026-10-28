"""Portable study bytes and deterministic report regeneration from captured decisions.

This reproduces tables from recorded executions. It does not rerun ETL, authenticate
reviewers or attest that another researcher independently repeated the experiment.
Original manifests are copied verbatim; their absolute provenance is not rewritten.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory

import equiframe as ef
from equiframe.evidence import parse_json, verify_events
from equiframe.local import local_path
from pydantic import BaseModel

from equiframe_benchmark.evaluation import EvaluationRecord
from equiframe_benchmark.evaluation_v2 import (
    EvaluationConfigV2 as EvaluationConfig,
)
from equiframe_benchmark.evaluation_v2 import (
    evaluate_records_v2 as evaluate_records,
)
from equiframe_benchmark.io import save_document
from equiframe_benchmark.models import digest
from equiframe_benchmark.reproduction import (
    BundleFile,
    BundleLimits,
    ComparisonReceipt,
    ReproductionBundle,
    ReproductionRecord,
    _bounded_json,
    create_bundle,
    make_reproduction_record,
    read_bundle,
    reproduce_bundle,
)
from equiframe_benchmark.tables_v2 import table_payloads_v2 as table_payloads


def _original_uri(path: str) -> str:
    """Preserve the producer's path syntax without resolving it on another OS."""
    windows = PureWindowsPath(path)
    if windows.is_absolute():
        return windows.as_uri()
    posix = PurePosixPath(path)
    if posix.is_absolute():
        return posix.as_uri()
    raise ValueError("producer paths must have an absolute declared syntax")


def _portable_artifact(
    original: ef.ArtifactRef, directory: Path, by_source: dict[str | None, BundleFile]
) -> ef.ArtifactRef:
    copied = by_source.get(original.uri)
    if copied is None or (copied.sha256, copied.size_bytes, copied.artifact_format) != (
        original.sha256,
        original.size_bytes,
        original.format,
    ):
        raise ValueError("portable artifact contradicts its original content binding")
    return ef.ArtifactRef.model_validate(
        {
            **original.model_dump(mode="python"),
            "uri": (directory.absolute() / copied.path).as_uri(),
        }
    )


def _check_document(path: Path, expected: BaseModel, item: BundleFile) -> None:
    maximum = BundleLimits().max_record_bytes
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum or (hashlib.sha256(data).hexdigest(), len(data)) != (
        item.sha256,
        item.size_bytes,
    ):
        raise ValueError("portable document exceeds its budget or changed during verification")
    parse_json(data)
    if type(expected).model_validate_json(data) != expected:
        raise ValueError("portable source document contradicts its captured study")


def _labels(records: tuple[EvaluationRecord, ...]) -> list[dict[str, object]]:
    return [
        {
            "case_id": r.case_id,
            "oracle_sha256": r.oracle_sha256,
            "state": r.oracle_state,
            "label": r.oracle_label,
        }
        for r in records
    ]


def regenerate_study_record_v2(record: ReproductionRecord) -> ReproductionRecord:
    """Recalculate every metric/CSV; retain the declared configuration and split."""
    configuration = json.loads(record.configuration)
    if configuration.get("protocol_version") != "2.0":
        raise ValueError("V2 regeneration requires an explicitly versioned paired record")
    config = EvaluationConfig.model_validate_json(json.dumps(configuration["evaluation"]))
    records = tuple(
        EvaluationRecord.model_validate_json(json.dumps(item))
        for item in json.loads(record.decisions)
    )
    report = evaluate_records(records, config)
    if (
        configuration["splits_sha256"]
        != hashlib.sha256(
            json.dumps(
                json.loads(record.splits),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
    ):
        raise ValueError("recorded splits must match the sealed configuration")
    return make_reproduction_record(
        configuration=configuration,
        splits=json.loads(record.splits),
        labels=_labels(report.records),
        decisions=[r.model_dump(mode="json") for r in report.records],
        tables={
            "evaluation_sha256": digest(report),
            "csv": {
                name: data.decode("utf-8") for name, (data, _) in table_payloads(report).items()
            },
        },
    )


def _references(value: object) -> tuple[ef.ArtifactRef, ...]:
    result: list[ef.ArtifactRef] = []
    if isinstance(value, dict):
        if {"uri", "sha256", "size_bytes", "format", "media_type"} <= value.keys():
            result.append(ef.ArtifactRef.model_validate_json(json.dumps(value)))
        else:
            for child in value.values():
                result.extend(_references(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_references(child))
    return tuple(result)


def bundle_study_v2(directory: Path, *, output: Path) -> ReproductionBundle:
    """Copy closed study evidence, original captures and all frozen source files."""
    from equiframe_benchmark.study_v2 import read_study_v2 as read_study

    study = read_study(directory)
    directory = directory.absolute()
    output = output.absolute()
    if output.is_relative_to(directory):
        raise ValueError("portable bundle must be outside its source study")
    files = {
        "study/" + path.relative_to(directory).as_posix(): path
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
    by_uri = {path.absolute().as_uri(): name for name, path in files.items()}
    artifacts: dict[str, ef.ArtifactRef] = {}
    expected_files = {"study/" + i.path: (i.sha256, i.size_bytes) for i in study.evidence}
    for ref in _references(study.model_dump(mode="json")):
        if ref.sha256 is None or ref.size_bytes is None:
            raise ValueError("portable source artifacts require hash and size")
        if ref.uri not in by_uri:
            name = "sources/" + hashlib.sha256(ref.uri.encode()).hexdigest() + "." + ref.format
            files[name] = local_path(ref)
            by_uri[ref.uri] = name
        name = by_uri[ref.uri]
        if name in artifacts and artifacts[name] != ref:
            raise ValueError("one original URI must identify exactly one artifact")
        artifacts[name] = ref
    for source in study.freeze.definition.files:
        path = Path(source.path)
        if path.absolute().as_uri() not in by_uri:
            name = (
                "frozen/" + hashlib.sha256(path.absolute().as_uri().encode()).hexdigest() + ".bin"
            )
            files[name] = path
            by_uri[path.absolute().as_uri()] = name
        name = by_uri[path.absolute().as_uri()]
        identity = (source.sha256, source.size_bytes)
        if name in expected_files and expected_files[name] != identity:
            raise ValueError("frozen input contradicts the closed study evidence")
        expected_files[name] = identity
    report = study.evaluation
    record = make_reproduction_record(
        configuration={
            "protocol_version": "2.0",
            "scope": "captured_decisions_and_full_csv_regeneration",
            "freeze": study.freeze.model_dump(mode="json"),
            "evaluation": report.config.model_dump(mode="json"),
            "splits_sha256": digest(study.freeze.definition.splits),
        },
        splits=study.freeze.definition.splits.model_dump(mode="json"),
        labels=_labels(report.records),
        decisions=[r.model_dump(mode="json") for r in report.records],
        tables={
            "evaluation_sha256": digest(report),
            "csv": {
                name: data.decode("utf-8") for name, (data, _) in table_payloads(report).items()
            },
        },
    )
    if regenerate_study_record_v2(record) != record:
        raise ValueError("study tables must be reproducible before portable publication")
    with TemporaryDirectory(prefix="study-record-", dir=output.parent) as temporary:
        path = Path(temporary) / "record.json"
        save_document(record, path)
        files["record.json"] = path
        bundle = create_bundle(
            files,
            directory=output,
            bundle_id=study.study_id,
            artifacts=artifacts,
            expected_files=expected_files,
            record_path="record.json",
        )
    by_source = {item.source_uri: item for item in bundle.files}
    for source in study.freeze.definition.files:
        copied = by_source[_original_uri(source.path)]
        if (copied.sha256, copied.size_bytes) != (source.sha256, source.size_bytes):
            raise ValueError("a frozen source changed during portable copying")
    return bundle


def reproduce_study_bundle_v2(
    directory: Path, *, expected_sha256: str | None = None
) -> ComparisonReceipt:
    """Verify portable bytes and regenerate the V2 seven CSV from captured decisions."""
    bundle = read_bundle(directory, expected_sha256=expected_sha256)
    if bundle.record_path != "record.json":
        raise ValueError("study bundle requires its declared full reproduction record")
    from equiframe_benchmark.freeze_v2 import FreezeManifestV2 as FreezeManifest
    from equiframe_benchmark.study_v2 import StudyResultV2 as StudyResult
    from equiframe_benchmark.tables_v2 import read_tables_v2 as read_tables

    record, record_sha256 = _bounded_json(
        ReproductionRecord, directory / bundle.record_path, BundleLimits().max_record_bytes
    )
    if next(i.sha256 for i in bundle.files if i.path == bundle.record_path) != record_sha256:
        raise ValueError("portable record changed after its inventory was verified")
    configuration = json.loads(record.configuration)
    frozen = FreezeManifest.model_validate_json(json.dumps(configuration["freeze"]))
    captured, _ = _bounded_json(
        StudyResult, directory / "study" / "study.json", BundleLimits().max_record_bytes
    )
    if captured.freeze != frozen or (
        configuration["evaluation"] != captured.evaluation.config.model_dump(mode="json")
        or json.loads(record.decisions)
        != [r.model_dump(mode="json") for r in captured.evaluation.records]
    ):
        raise ValueError("portable logical record must match its captured study")
    by_name = {item.path: item for item in bundle.files}
    by_source = {item.source_uri: item for item in bundle.files}
    copied: BundleFile | None
    expected_study = {"study/study.json", *("study/" + i.path for i in captured.evidence)}
    if {name for name in by_name if name.startswith("study/")} != expected_study:
        raise ValueError("portable study evidence inventory is not closed")
    for item in captured.evidence:
        copied = by_name["study/" + item.path]
        if (copied.sha256, copied.size_bytes) != (item.sha256, item.size_bytes):
            raise ValueError("portable study bytes differ from the original study inventory")
    for name, source_document in (
        ("freeze.json", captured.freeze),
        ("audit-before.json", captured.audit_before),
        ("audit-after.json", captured.audit_after),
        ("evaluation.json", captured.evaluation),
    ):
        name = "study/" + name
        _check_document(directory / name, source_document, by_name[name])
    for position, case in enumerate(captured.cases):
        prefix = f"study/case-{position}/"
        name = prefix + "case.json"
        _check_document(directory / name, case, by_name[name])
        if case.pipeline is not None:
            pipeline = case.pipeline
            folder = prefix + pipeline.pipeline_id + "/"
            for name, pipeline_document in (
                ("manifest.json", pipeline),
                ("pipeline.json", pipeline.spec),
                ("execution.json", pipeline.execution),
                ("rules.json", pipeline.rules),
                ("profile.json", pipeline.profile),
                ("detection.json", pipeline.detection),
                ("comparison.json", pipeline.comparison),
                ("hybrid.json", pipeline.hybrid),
            ):
                if pipeline_document is not None:
                    name = folder + name
                    _check_document(directory / name, pipeline_document, by_name[name])
            for item in pipeline.evidence:
                copied = by_name.get(folder + item.path)
                if copied is None or (copied.sha256, copied.size_bytes) != (
                    item.sha256,
                    item.size_bytes,
                ):
                    raise ValueError("portable pipeline evidence contradicts its manifest")
            events = verify_events(
                directory / folder / "events.jsonl", operation_id=pipeline.pipeline_id
            )
            if (
                len(events) != pipeline.event_count
                or events[-1].sha256 != pipeline.event_head_sha256
            ):
                raise ValueError("portable pipeline journal differs from its captured head")
        if case.output_replay is not None:
            uri = case.output_replay.differences.uri.rsplit("/", 1)[0] + "/comparison.json"
            copied = by_source.get(uri)
            if copied is None:
                raise ValueError("portable replay source manifest is missing")
            _check_document(directory / copied.path, case.output_replay, copied)
    if read_tables(directory / "study" / "tables", report=captured.evaluation) != captured.tables:
        raise ValueError("portable CSV must reproduce its original full report")
    if digest(frozen.definition.splits) != configuration["splits_sha256"] or json.loads(
        record.splits
    ) != frozen.definition.splits.model_dump(mode="json"):
        raise ValueError("portable split must equal the sealed split")
    for ref in _references(frozen.model_dump(mode="json")):
        copied = by_source.get(ref.uri)
        if copied is None or (copied.sha256, copied.size_bytes, copied.artifact_format) != (
            ref.sha256,
            ref.size_bytes,
            ref.format,
        ):
            raise ValueError("portable input must preserve its original artifact binding")
    for source in frozen.definition.files:
        copied = by_source.get(_original_uri(source.path))
        if copied is None or (copied.sha256, copied.size_bytes) != (
            source.sha256,
            source.size_bytes,
        ):
            raise ValueError("portable frozen source differs from its declared content")
    definitions = {case.case_id: case for case in frozen.definition.cases}
    scenarios = {scenario.scenario_id: scenario for scenario in frozen.definition.catalog.scenarios}
    for case in captured.cases:
        if case.record.oracle_state != "confirmed":
            continue
        declared = definitions[case.case_id]
        if (
            case.pipeline is None
            or case.pipeline.execution is None
            or (case.pipeline.execution.output is None)
            or case.output_replay is None
        ):
            raise ValueError("a confirmed replay requires an actual captured output")
        original = case.pipeline.execution.output
        # An ephemeral TableArtifact retains index and physical metadata. Original
        # serialized manifests and their fingerprints remain unchanged in the bundle.
        rebased = ef.TableArtifact.model_validate(
            {
                **original.model_dump(mode="python"),
                "data": _portable_artifact(original.data, directory, by_source),
                "index": _portable_artifact(original.index, directory, by_source)
                if original.index
                else None,
            }
        )
        scenario = scenarios[declared.scenario_id]
        with TemporaryDirectory(prefix="portable-replay-") as temporary:
            replay = ef.compare(
                rebased,
                _portable_artifact(declared.candidate.output, directory, by_source),
                contract=scenario.comparison.contract,
                policy=scenario.comparison.policy,
                options=declared.pipeline.comparison_options,
                reference="peer",
                work_dir=Path(temporary),
            )
        if not replay.complete or replay.state != "equivalent":
            raise ValueError("confirmed portable label requires equivalent actual captured rows")
        if (
            replay.counts,
            replay.strategy,
            replay.selected_key,
        ) != (
            case.output_replay.counts,
            case.output_replay.strategy,
            case.output_replay.selected_key,
        ):
            raise ValueError("portable replay observations differ from actual captured rows")
    return reproduce_bundle(
        directory, regenerator=regenerate_study_record_v2, expected_sha256=expected_sha256
    )
