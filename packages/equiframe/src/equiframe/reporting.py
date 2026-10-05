"""Reports expose selected operational facts, never parameter values or exception messages."""

import html
import json
from pathlib import Path

from equiframe.evidence import publish_json
from equiframe.pipeline_types import PipelineResult
from equiframe.profiles import _write_document


def pipeline_summary(result: PipelineResult) -> dict[str, object]:
    result = PipelineResult.model_validate(result)
    return {
        "schema_version": "1.0",
        "pipeline_id": result.pipeline_id,
        "contract_sha256": result.execution.contract_sha256 if result.execution else None,
        "spec_sha256": result.spec_sha256,
        "engine": result.spec.execution.engine,
        "family": result.spec.execution.contract.family,
        "complete": result.complete,
        "cancelled": result.cancelled,
        "exit_code": result.exit_code,
        "elapsed_seconds": result.elapsed_seconds,
        "execution_state": result.execution.state if result.execution else "unavailable",
        "stages": [stage.model_dump(mode="json") for stage in result.stages],
        "R": {"decision": result.hybrid.r.decision, "complete": result.hybrid.r.complete},
        "M": {"decision": result.hybrid.m.decision, "complete": result.hybrid.m.complete},
        "B": {
            "decision": result.detection.b[0].result.decision,
            "complete": result.detection.b[0].result.complete,
        }
        if result.detection
        else None,
        "H": {"decision": result.hybrid.result.decision, "complete": result.hybrid.result.complete},
        "comparison": {
            "state": result.comparison.state,
            "complete": result.comparison.complete,
            "reference": result.spec.comparison_reference,
        }
        if result.comparison is not None
        else None,
        "detector_bundle_sha256": result.detection.bundle_sha256 if result.detection else None,
        "scientific_equivalence_confirmed": False,
        "scope": "Operational evidence only; no oracle review or scientific label.",
    }


def render_report(summary: dict[str, object]) -> str:
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


def write_report(result: PipelineResult, directory: Path) -> None:
    """Publish a new report directory; existing reports are never replaced."""
    summary = pipeline_summary(result)
    directory.mkdir(parents=True, exist_ok=False)
    publish_json(summary, directory / "report.json")
    _write_document(directory / "report.html", render_report(summary).encode("utf-8"))
