"""Frozen persisted report layouts for evidence schema 1.0.

Readers bind these functions to a validated 1.0 result, never to public/current
presentation functions. Do not restyle or extend these implementations in place:
a new persisted layout requires an explicit format/reader compatibility decision.

Migration 1.0 has two historically emitted closed layouts. The reader selects
legacy only when the stored JSON equals migration_legacy_summary_v1 exactly;
otherwise the complete migration_summary_v1 and its HTML must match exactly.
These checks complement closed inventories and hashes, not replace them.
"""

from __future__ import annotations

import html
import json
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from equiframe.comparison_types import ComparisonResult
    from equiframe.migration.runner_types import MigrationResult
    from equiframe.pipeline_types import PipelineResult
    from equiframe.verify_types import VerificationResult


def pipeline_summary_v1(result: PipelineResult) -> dict[str, object]:
    from equiframe.pipeline_types import PipelineResult

    result = PipelineResult.model_validate(result)
    return {
        "schema_version": "1.0",
        "pipeline_id": result.pipeline_id,
        "contract_sha256": result.execution.contract_sha256
        if result.execution is not None
        else None,
        "spec_sha256": result.spec_sha256,
        "engine": result.spec.execution.engine,
        "family": result.spec.execution.contract.family,
        "complete": result.complete,
        "cancelled": result.cancelled,
        "exit_code": result.exit_code,
        "elapsed_seconds": result.elapsed_seconds,
        "execution_state": result.execution.state
        if result.execution is not None
        else "unavailable",
        "stages": [stage.model_dump(mode="json") for stage in result.stages],
        "R": {"decision": result.hybrid.r.decision, "complete": result.hybrid.r.complete},
        "M": {"decision": result.hybrid.m.decision, "complete": result.hybrid.m.complete},
        "B": {
            "decision": result.detection.b[0].result.decision,
            "complete": result.detection.b[0].result.complete,
        }
        if result.detection is not None
        else None,
        "H": {"decision": result.hybrid.result.decision, "complete": result.hybrid.result.complete},
        "comparison": {
            "state": result.comparison.state,
            "complete": result.comparison.complete,
            "reference": result.spec.comparison_reference,
        }
        if result.comparison is not None
        else None,
        "detector_bundle_sha256": result.detection.bundle_sha256
        if result.detection is not None
        else None,
        "scientific_equivalence_confirmed": False,
        "scope": "Operational evidence only; no oracle review or scientific label.",
    }


def pipeline_html_v1(summary: dict[str, object]) -> str:
    """No scripts, remote assets, user URLs or raw HTML; every supplied value is escaped."""
    body = html.escape(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2))
    rows = ""
    for name in ("R", "M", "B", "H"):
        component = summary.get(name)
        if isinstance(component, dict):
            decision = html.escape(str(component.get("decision", "unavailable")))
            complete = html.escape(str(component.get("complete", False)))
        else:
            decision, complete = "not requested / unavailable", "False"
        rows += f"<tr><th scope='row'>{name}</th><td>{decision}</td><td>{complete}</td></tr>"
    stage_rows = ""
    stages = summary.get("stages")
    if isinstance(stages, list):
        for stage in stages:
            if isinstance(stage, dict):
                stage_rows += (
                    "<tr>"
                    + "".join(
                        "<td>" + html.escape(str(stage.get(key, ""))) + "</td>"
                        for key in ("stage", "state", "code", "elapsed_seconds")
                    )
                    + "</tr>"
                )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>EquiFrame evidence</title>"
        "<style>body{max-width:1000px;margin:3rem auto;padding:0 1rem;"
        "font:16px system-ui;color:#172b3a;background:#f6f8fa}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:1.5rem;"
        "border:1px solid #ccd5df;border-radius:8px}h1{color:#174b57}"
        "table{width:100%;border-collapse:collapse;background:white;margin:1rem 0 2rem}"
        "th,td{padding:.7rem;border-bottom:1px solid #ccd5df;text-align:left}"
        "caption{text-align:left;font-weight:bold;padding:.5rem 0}"
        "@media print{body{margin:0;background:white}details{display:block}}</style>"
        "<h1>EquiFrame · Operational evidence</h1>"
        "<p>Completion, alerts and equivalence are separate results. "
        "An unavailable component never means absence of alert.</p>"
        "<table><caption>Independent decisions</caption><thead><tr><th>Method</th>"
        "<th>Decision</th><th>Complete</th></tr></thead><tbody>" + rows + "</tbody></table>"
        "<table><caption>Stage trace</caption><thead><tr><th>Stage</th><th>State</th>"
        "<th>Code</th><th>Seconds</th></tr></thead><tbody>" + stage_rows + "</tbody></table>"
        "<details open><summary>Full operational summary</summary><pre>"
        + body
        + "</pre></details></html>"
    )


def migration_legacy_summary_v1(result: MigrationResult) -> dict[str, object]:
    from equiframe.migration.runner_types import MigrationResult

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
        "source_pipeline_id": result.source.pipeline_id if result.source is not None else None,
        "target_pipeline_id": result.target.pipeline_id if result.target is not None else None,
        "source_exit_code": result.source.exit_code if result.source is not None else None,
        "target_exit_code": result.target.exit_code if result.target is not None else None,
        "difference_records": result.comparison.counts.difference_records
        if result.comparison is not None
        else None,
        "equivalence_is_independent_correctness": False,
    }


def _comparison_summary_v1(
    result: ComparisonResult | None, *, requested: bool
) -> dict[str, object]:
    return {
        "state": result.state
        if result is not None
        else "not_evaluable"
        if requested
        else "not_requested",
        "complete": result.complete if result is not None else False,
        "comparison_id": result.comparison_id if result is not None else None,
        "difference_records": result.counts.difference_records if result is not None else None,
    }


def migration_summary_v1(result: MigrationResult) -> dict[str, object]:
    """Keep each comparison visible without attributing human validation to C."""
    from equiframe.migration.runner_types import MigrationResult

    result = MigrationResult.model_validate(result)
    return {
        **migration_legacy_summary_v1(result),
        "expected_output_comparison": result.verification,
        "comparisons": {
            "source_target": _comparison_summary_v1(result.comparison, requested=True),
            "source_expected": _comparison_summary_v1(
                result.verification_source, requested=result.expected_requested
            ),
            "target_expected": _comparison_summary_v1(
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


def migration_html_v1(result: MigrationResult, *, legacy: bool = False) -> str:
    summary = migration_summary_v1(result)
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


def verification_summary_v1(result: VerificationResult) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "verification_id": result.verification_id,
        "operational_state": result.operational_state,
        "publishable": result.publishable,
        "exit_code": result.exit_code,
        "contract_sha256": result.binding.contract_sha256,
        "binding": result.binding.model_dump(mode="json"),
        "dimensions": {
            name: getattr(result, name).model_dump(mode="json")
            for name in ("inputs", "technical", "integrity", "agreement", "independent_review")
        },
        "expected": [c.model_dump(mode="json") for c in result.expected],
        "rules": [c.model_dump(mode="json") for c in result.rules],
        "rule_evaluations": [r.model_dump(mode="json") for r in result.rule_evaluations],
        "coverage": result.coverage.model_dump(mode="json"),
        "provenance": result.provenance.model_dump(mode="json") if result.provenance else None,
        "expected_source_engine": result.expected_source_engine,
        "elapsed_seconds": result.elapsed_seconds,
        "engines": [
            {
                "output": name,
                "engine": e.plan.engine,
                "versions": [v.model_dump(mode="json") for v in e.versions],
            }
            for name, e in result.executions
        ],
        "comparisons": [
            {
                "comparison_id": c.comparison_id,
                "state": c.state,
                "reference": c.reference,
                "counts": c.counts.model_dump(mode="json"),
                "examples": [d.model_dump(mode="json") for d in c.examples],
                "examples_truncated": c.counts.difference_records > len(c.examples),
                "policy": c.spec.policy.model_dump(mode="json"),
                "differences": c.differences.model_dump(mode="json"),
            }
            for c in (*result.comparisons, *result.input_comparisons)
        ],
        "identity_authentication": (
            "Declared identities are not authenticated; hashes prove integrity"
        ),
    }


def verification_html_v1(result: VerificationResult) -> str:
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>EquiFrame Verify</title>'
        "<h1>EquiFrame Verify</h1><pre>"
        + escape(
            json.dumps(
                verification_summary_v1(result),
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            )
        )
        + "</pre></html>"
    )
