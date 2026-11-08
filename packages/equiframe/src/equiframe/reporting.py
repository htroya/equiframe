"""Reports expose selected operational facts, never parameter values or exception messages."""

from pathlib import Path

from equiframe._document_io import write_document as _write_document
from equiframe._report_format_v1 import pipeline_html_v1, pipeline_summary_v1
from equiframe.evidence import publish_json
from equiframe.pipeline_types import PipelineResult


def pipeline_summary(result: PipelineResult) -> dict[str, object]:
    """Current operational summary; persisted format 1.0 is separately frozen."""
    return pipeline_summary_v1(result)


def render_report(summary: dict[str, object]) -> str:
    """Current presentation; escape values and preserve the existing 1.0 layout."""
    return pipeline_html_v1(summary)


def write_report(result: PipelineResult, directory: Path) -> None:
    """Publish a new report directory; existing reports are never replaced."""
    summary = pipeline_summary(result)
    directory.mkdir(parents=True, exist_ok=False)
    publish_json(summary, directory / "report.json")
    _write_document(directory / "report.html", render_report(summary).encode("utf-8"))
