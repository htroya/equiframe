"""Read and verify migration evidence without executing ETL, compilers or plugins."""

from __future__ import annotations

from html import escape
from pathlib import Path

from equiframe.comparison import iter_differences, read_comparison
from equiframe.comparison_types import ComparisonResult
from equiframe.errors import ArtifactIntegrityError
from equiframe.evidence import (
    describe_file,
    load_json,
    parse_json,
    read_pipeline,
    verify_events,
    verify_files,
)
from equiframe.local import local_path
from equiframe.types import ArtifactRef

from ._physical import physical_size, verify_table_metadata
from .runner_types import MigrationResult, MigrationSpec


def _legacy_summary(result: MigrationResult) -> dict[str, object]:
    result = MigrationResult.model_validate(result)
    return {
        "schema_version": "1.0",
        "migration_id": result.migration_id,
        "source_engine": result.spec.source_engine,
        "target_engine": result.spec.target_engine,
        "complete": result.complete,
        "state": result.state,
        "independent_verification": result.verification,
        "expected_requested": result.expected_requested,
        "detection_requested": result.detection_requested,
        "rules_required": result.spec.require_rules,
        "exit_code": result.exit_code,
        "cancelled": result.cancelled,
        "stages": [s.model_dump(mode="json") for s in result.stages],
        "source_pipeline_id": result.source.pipeline_id if result.source else None,
        "target_pipeline_id": result.target.pipeline_id if result.target else None,
        "source_exit_code": result.source.exit_code if result.source else None,
        "target_exit_code": result.target.exit_code if result.target else None,
        "difference_records": result.comparison.counts.difference_records
        if result.comparison
        else None,
        "equivalence_is_independent_correctness": False,
    }


def _comparison_summary(result: ComparisonResult | None, *, requested: bool) -> dict[str, object]:
    return {
        "state": result.state if result else "not_evaluable" if requested else "not_requested",
        "complete": result.complete if result else False,
        "comparison_id": result.comparison_id if result else None,
        "difference_records": result.counts.difference_records if result else None,
    }


def migration_summary(result: MigrationResult) -> dict[str, object]:
    """Keep each comparison visible without attributing human validation to C."""
    result = MigrationResult.model_validate(result)
    return {
        **_legacy_summary(result),
        "expected_output_comparison": result.verification,
        "comparisons": {
            "source_target": _comparison_summary(result.comparison, requested=True),
            "source_expected": _comparison_summary(
                result.verification_source, requested=result.expected_requested
            ),
            "target_expected": _comparison_summary(
                result.verification_target, requested=result.expected_requested
            ),
        },
        "equiframe_verify": {
            "procedure": "EquiFrame Verify",
            "identifier": "O",
            "status": "not_established",
            "reason": (
                "Migration compares supplied expected content but does not establish "
                "independent expected authorship or collect two independent human reviews."
            ),
        },
    }


def _render_report(result: MigrationResult, *, legacy: bool = False) -> str:
    summary = migration_summary(result)
    rows = "".join(
        "<tr><td>"
        + escape(s.stage)
        + "</td><td>"
        + escape(s.state)
        + "</td><td>"
        + escape(s.code)
        + "</td></tr>"
        for s in result.stages
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>EquiFrame migration</title></head><body>"
        "<h1>EquiFrame migration</h1><p>"
        + escape(result.spec.source_engine)
        + " to "
        + escape(result.spec.target_engine)
        + "</p><p>Observed equivalence: "
        + escape(result.state)
        + (". Independent verification: " if legacy else ". Supplied expected comparison: ")
        + escape(result.verification)
        + ". Complete: "
        + str(summary["complete"])
        + ".</p>"
        "<p>Matching native outputs do not establish independent correctness.</p>"
        + (
            ""
            if legacy
            else "<p>EquiFrame Verify (O): not established. Comparing supplied expected "
            "content does not establish independent expected authorship or collect "
            "two independent human reviews.</p>"
        )
        + "<table><thead><tr><th>Stage</th><th>State</th><th>Code</th></tr></thead><tbody>"
        + rows
        + "</tbody></table></body></html>"
    )


def render_migration_report(result: MigrationResult) -> str:
    return _render_report(result)


def read_migration(path: Path, *, verify: bool = True) -> MigrationResult:
    """Check a closed bundle. Integrity is distinct from semantic correctness."""
    path = path / "migration.json" if path.is_dir() else path
    result = load_json(MigrationResult, path)
    if not verify:
        return result
    directory = path.parent.resolve()
    listed = {i.path: i for i in result.evidence}
    verify_files(directory, result.evidence)

    def bind(ref: ArtifactRef) -> None:
        ref_path = local_path(ref).resolve()
        if not ref_path.is_relative_to(directory):
            raise ArtifactIntegrityError("migration artifact escapes its operation")
        item = listed.get(ref_path.relative_to(directory).as_posix())
        if item is None or (item.sha256, item.size_bytes) != (ref.sha256, ref.size_bytes):
            raise ArtifactIntegrityError("migration artifact contradicts its inventory")

    actual = {
        p.relative_to(directory).as_posix()
        for p in directory.rglob("*")
        if p.is_file() and p != path.resolve()
    }
    if actual != set(listed):
        raise ArtifactIntegrityError("migration files contradict its closed inventory")
    for name in ("events.jsonl", "spec.json", "report.json", "report.html"):
        if name not in listed:
            raise ArtifactIntegrityError("required migration evidence is missing")
    if load_json(MigrationSpec, directory / "spec.json") != result.spec:
        raise ArtifactIntegrityError("migration configuration contradicts the manifest")
    events = verify_events(directory / "events.jsonl", operation_id=result.migration_id)
    if (
        not events
        or len(events) != result.event_count
        or events[-1].sha256 != result.event_head_sha256
        or (events[0].stage, events[0].state) != ("migration", "started")
        or (events[-1].stage, events[-1].state) != ("migration", "finished")
    ):
        raise ArtifactIntegrityError("migration journal contradicts its manifest")
    terminal = tuple(
        (e.stage, e.state, e.code)
        for e in events
        if e.stage != "migration" and e.state != "started"
    )
    if terminal != tuple((s.stage, s.state, s.code) for s in result.stages):
        raise ArtifactIntegrityError("migration stage outcomes contradict its journal")
    refs = []
    for table in result.inputs:
        bind(table.data)
        if table.index:
            bind(table.index)
        verify_table_metadata(table)
        refs.append(table.data)
        if table.index:
            refs.append(table.index)
    if result.expected:
        bind(result.expected)
        refs.append(result.expected)
    if result.stages[1].state == "completed":
        if "capture.json" not in listed:
            raise ArtifactIntegrityError("complete capture receipt is missing")
        captured = parse_json((directory / "capture.json").read_bytes())
        if (
            not isinstance(captured, dict)
            or set(captured)
            != {
                "schema_version",
                "inputs",
                "expected",
                "rows",
                "arrow_buffer_bytes",
            }
            or (
                captured.get("schema_version") != "1.0"
                or captured.get("inputs") != [t.model_dump(mode="json") for t in result.inputs]
                or captured.get("expected")
                != (result.expected.model_dump(mode="json") if result.expected else None)
            )
        ):
            raise ArtifactIntegrityError("capture receipt contradicts fixed inputs")
        sizes = [physical_size(t.data) for t in result.inputs]
        expected_size = physical_size(result.expected) if result.expected else (0, 0)
        observed_rows = sum(n for n, _ in sizes) + expected_size[0]
        observed_bytes = sum(n for _, n in sizes) + expected_size[1]
        observed_bytes += sum(physical_size(t.index)[1] for t in result.inputs if t.index)
        if (
            type(captured.get("rows")) is not int
            or type(captured.get("arrow_buffer_bytes")) is not int
            or captured.get("rows") != observed_rows
            or captured.get("arrow_buffer_bytes") != observed_bytes
            or observed_rows > result.spec.options.max_capture_rows
            or observed_bytes > result.spec.options.max_capture_bytes
        ):
            raise ArtifactIntegrityError("capture physical statistics contradict the receipt")
    for p in (result.source, result.target):
        if p is not None and read_pipeline(directory / p.pipeline_id) != p:
            raise ArtifactIntegrityError("native pipeline contradicts migration manifest")
        if p and p.execution:
            for t in (*p.execution.inputs, *((p.execution.output,) if p.execution.output else ())):
                bind(t.data)
                if t.index:
                    bind(t.index)
                verify_table_metadata(t)
    for c in (result.comparison, result.verification_source, result.verification_target):
        if c is None:
            continue
        if read_comparison(directory / c.comparison_id / "comparison.json") != c:
            raise ArtifactIntegrityError("comparison contradicts migration manifest")
        bind(c.differences)
        count = violations = 0
        for difference in iter_differences(c.differences):
            if count < len(c.examples) and difference != c.examples[count]:
                raise ArtifactIntegrityError("comparison examples contradict complete differences")
            count += 1
            violations += int(difference.category in ("contract", "schema"))
        if count != c.counts.difference_records or violations != c.counts.contract_violations:
            raise ArtifactIntegrityError("comparison differences contradict recorded counts")
        if len(c.examples) != min(count, c.options.max_examples):
            raise ArtifactIntegrityError("comparison example count contradicts configured budget")
        refs.append(c.differences)
        refs.extend(s.data for s in (c.left, c.right) if s is not None)
    for ref in refs:
        ref_path = local_path(ref).resolve()
        if not ref_path.is_relative_to(directory):
            raise ArtifactIntegrityError("migration artifact escapes its operation")
        item = listed.get(ref_path.relative_to(directory).as_posix())
        if item is None or (item.sha256, item.size_bytes) != (ref.sha256, ref.size_bytes):
            raise ArtifactIntegrityError("migration artifact contradicts its inventory")
        if describe_file(ref_path, directory) != item:
            raise ArtifactIntegrityError("migration artifact changed")
    stored_summary = parse_json((directory / "report.json").read_bytes())
    legacy = stored_summary == _legacy_summary(result)
    if not legacy and stored_summary != migration_summary(result):
        raise ArtifactIntegrityError("migration report contradicts its manifest")
    if (directory / "report.html").read_bytes() != _render_report(result, legacy=legacy).encode(
        "utf-8"
    ):
        raise ArtifactIntegrityError("migration HTML contradicts its manifest")
    if result.detection_requested:
        from equiframe.detector_types import DetectorBundle

        if "detector-bundle.json" not in listed:
            raise ArtifactIntegrityError("migration detector bundle is missing")
        bundle = load_json(DetectorBundle, directory / "detector-bundle.json")
        for p in (result.source, result.target):
            if (
                p
                and load_json(DetectorBundle, directory / p.pipeline_id / "detector-bundle.json")
                != bundle
            ):
                raise ArtifactIntegrityError("native pipelines used different detector bundles")
    return result
