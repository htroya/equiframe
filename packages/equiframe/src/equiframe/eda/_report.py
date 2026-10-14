"""Portable local HTML. Values are escaped; plots embed JS, never a remote CDN."""

from __future__ import annotations

import html
import importlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from equiframe.evidence import publish_json

from .models import EdaConfig, EdaManifest, EdaResult, ResultFile


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    return (
        '<div class="scroll"><table><thead><tr>'
        + "".join("<th>" + html.escape(h) + "</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join("<td>" + html.escape(str(cell)) + "</td>" for cell in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )


def _charts(result: EdaResult, checkpoint: Callable[[], None], max_bytes: int) -> str:
    checkpoint()
    go = importlib.import_module("plotly.graph_objects")
    io = importlib.import_module("plotly.io")
    charts = []
    quality = go.Figure()
    for key, label in (
        ("nulls", "NULL"),
        ("nan", "NaN"),
        ("empty", "Empty string"),
        ("zero", "Numeric zero"),
    ):
        quality.add_bar(
            name=label,
            x=[html.escape(c.name) for c in result.columns],
            y=[getattr(c, key) for c in result.columns],
        )
    quality.update_layout(
        title="Raw quality counts · categories may overlap",
        barmode="group",
        template="plotly_white",
    )
    charts.append(quality)
    for col in result.columns:
        freq = col.frequencies
        if freq:
            fig = go.Figure(
                go.Bar(x=[html.escape(str(f["value"])) for f in freq], y=[f["count"] for f in freq])
            )
            fig.update_layout(
                title=html.escape(col.name) + " · bounded top categories, full counts",
                template="plotly_white",
            )
            charts.append(fig)
    for document in result.numeric:
        numeric = cast("dict[str, Any]", document)
        for group in numeric.get("groups", []):
            title = html.escape(str(numeric["rule"]["column"]) + " " + str(group["group"]))
            if "histogram" in group:
                hist = group["histogram"]
                fig = go.Figure(go.Bar(x=[h["bin"] for h in hist], y=[h["count"] for h in hist]))
                fig.update_layout(
                    title=title + " · full distribution, approximate bin bounds",
                    template="plotly_white",
                )
                charts.append(fig)
            sample = group.get("chart_sample", [])
            if sample:
                ys = [float(s["value"]) for s in sample]
                box = go.Figure(go.Box(y=ys, boxpoints="all", name="First finite rows"))
                box.update_layout(
                    title=title + " · sampled box; not population quartiles",
                    template="plotly_white",
                )
                charts.append(box)
                scatter = go.Figure(go.Scatter(x=[s["row"] for s in sample], y=ys, mode="markers"))
                scatter.update_layout(
                    title=title + " · sample by snapshot row, no causal interpretation",
                    template="plotly_white",
                )
                charts.append(scatter)
    rendered = []
    size = 0
    for i, fig in enumerate(charts):
        checkpoint()
        block = io.to_html(
            fig,
            full_html=False,
            include_plotlyjs=i == 0,
            div_id=f"eda-chart-{i}",
            config={"responsive": True},
        )
        size += len(block.encode("utf8"))
        if size > max_bytes:
            from .api import _Unavailable

            raise _Unavailable("report_bytes_budget_exhausted")
        rendered.append(block)
        checkpoint()
    return "".join(rendered)


def publish_report(
    result: EdaResult,
    *,
    config: EdaConfig,
    output: Path,
    checkpoint: Callable[[], None],
    started: float,
) -> EdaResult:
    from .api import _Cancelled, _sha, _Unavailable

    chart_html = ""
    chart_note = "Plotly charts not requested. Full calculations and tables remain available."
    if config.charts and result.rows is not None and result.state not in ("failed", "cancelled"):
        try:
            chart_html = _charts(result, checkpoint, config.resources.max_report_bytes)
            chart_note = (
                "Charts embed Plotly locally; no network needed. Samples and approximate "
                "visualization conversions are declared per group."
            )
            import plotly

            result = result.model_copy(
                update={
                    "environment": {**result.environment, "plotly": plotly.__version__},
                    "chart_state": "completed",
                }
            )
        except Exception as error:
            from equiframe._error_reporting import report_failure

            chart_note = "Requested charts unavailable."
            chart_state = (
                "failed" if isinstance(error, (ValueError, TypeError)) else "not_evaluable"
            )
            chart_reason = report_failure(error, "requested_charts_unavailable")
            result = result.model_copy(
                update={"chart_state": chart_state, "chart_reason": chart_reason}
            )
            if isinstance(error, _Cancelled):
                result = result.model_copy(
                    update={"state": "cancelled", "reason": "cancellation_requested"}
                )
            if result.state == "completed":
                result = result.model_copy(
                    update={
                        "state": "not_evaluable",
                        "reason": chart_reason,
                    }
                )
    elif config.charts:
        chart_note = "Requested charts not evaluated because source/calculation is unavailable."
        result = result.model_copy(
            update={"chart_state": "not_evaluable", "chart_reason": chart_note}
        )
    raw = _table(
        ["Column", "Type", "Rows", "NULL", "NaN", "Empty", "Zero", "Distinct present"],
        [
            [c.name, c.physical_type, c.rows, c.nulls, c.nan, c.empty, c.zero, c.distinct_present]
            for c in result.columns
        ],
    )
    dup = _table(
        [
            "Columns",
            "Denominator",
            "Incomplete",
            "Repeated groups",
            "Rows involved",
            "Excess",
            "Policy",
        ],
        [
            [
                ", ".join(d.columns),
                d.denominator,
                d.incomplete_rows,
                d.repeated_groups,
                d.involved_rows,
                d.excess_rows,
                d.policy,
            ]
            for d in result.duplicates
        ],
    )
    findings = _table(
        ["Finding", "Severity", "Column", "Count", "Denominator", "Reason"],
        [[f.code, f.severity, f.column, f.count, f.denominator, f.reason] for f in result.findings],
    )
    details = html.escape(
        json.dumps(
            {
                "conversions": result.conversions,
                "numeric": result.numeric,
                "evidence_links": result.evidence_links,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>EquiFrame EDA</title>
<style>body{{font:16px
system-ui;color:#193343;background:#eef3f6;margin:0}}main{{max-width:1180px;margin:auto;padding:32px}}
h1{{font-size:34px;margin:0 0 10px}}.card{{background:white;border:1px solid
#d5e0e7;border-radius:12px;padding:22px;margin:20px 0}}
.badge{{padding:6px
12px;background:#e5edf4;border-radius:6px}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:9px;border-bottom:1px
solid #dde5eb}}
th{{background:#eef4f7}}.scroll{{overflow:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}li{{margin:8px
0}}
.meta{{overflow-wrap:anywhere;color:#415969}}.plotly-graph-div{{max-width:100%}}</style></head><body><main>
<h1>EquiFrame · dataset diagnostics</h1><p class="badge">{html.escape(result.state)}</p>
<p class="meta">Snapshot: {html.escape(result.snapshot_id)}<br>Source SHA-256:
{html.escape(str(result.source_sha256))}<br>
Run: {result.run_id} · Alpha {result.producer_version} · Rows: {result.rows}</p>
<p>EDA observations are cases to investigate. They establish neither equivalence, independent
correctness nor authorization to publish a DW.</p>
<div class="card"><h2>Raw quality</h2><p>Counts and rates use each column's row denominator.
NULL, NaN, empty string and numeric zero stay distinct.
Text “0” is text, not a numeric zero. Distinct present excludes NULL/NaN; empty strings remain
present. Valid excludes NULL/NaN/empty/nonfinite.</p>{raw}</div>
<div class="card"><h2>Repetitions</h2><p>No rows removed. Group examples are bounded; all groups
contribute to counts.</p>{dup}</div>
<div class="card"><h2>Findings and unavailable checks</h2>{findings}</div>
<div class="card"><h2>Distributions and
charts</h2><p>{html.escape(chart_note)}</p>{chart_html}</div>
<div class="card"><h2>Explicit conversion and numeric details</h2><pre>{details}</pre></div>
<div class="card"><h2>Scope and limits</h2><ul>{
        "".join("<li>" + html.escape(t) + "</li>" for t in result.limits)
    }</ul>
<p>Rules: {html.escape(config.rules_id)} revision {config.rules_revision}; SHA-256
{result.config_sha256}.
Reason: {html.escape(str(result.reason))}. Source unchanged:
{result.source_unchanged}.</p></div></main></body></html>"""
    try:
        checkpoint()
        if len(body.encode("utf8")) > config.resources.max_report_bytes:
            raise _Unavailable("report_bytes_budget_exhausted")
    except (_Unavailable, _Cancelled) as error:
        result = result.model_copy(
            update={
                "state": "cancelled" if isinstance(error, _Cancelled) else "not_evaluable",
                "reason": str(error),
                "chart_state": "not_evaluable",
                "chart_reason": str(error),
            }
        )
        body = "<!doctype html><p>Report unavailable; see verified summary.json.</p>"
        if len(body.encode("utf8")) > config.resources.max_report_bytes:
            body = ""  # No report within budget; explicit unavailable reason is in JSON.
    with (output / "report.html").open("x", encoding="utf8", newline="\n") as stream:
        stream.write(body)
    result = result.model_copy(update={"elapsed_seconds": time.monotonic() - started})
    publish_json(
        {
            "schema_version": "1.0",
            "kind": "equiframe.eda.findings",
            "run_id": result.run_id,
            "items": [f.model_dump(mode="json") for f in result.findings],
        },
        output / "findings.json",
    )
    # Manifest is the commit marker. Rendering/I/O failures before here cannot
    # leave a readable completed run; read_result always requires a closed manifest.
    publish_json(result, output / "summary.json")
    inventory = [
        {"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": _sha(p)}
        for p in sorted(output.rglob("*"))
        if p.is_file()
    ]
    publish_json(
        EdaManifest(
            run_id=result.run_id,
            state=result.state,
            files=tuple(ResultFile.model_validate(f) for f in inventory),
        ),
        output / "manifest.json",
    )
    return result
