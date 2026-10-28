"""Regenerate exact CSV tables from the bound evaluation, never from edited totals."""

import csv
import hashlib
import io
from pathlib import Path
from typing import Annotated

from equiframe._path_compat import is_junction
from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.evaluation import EvaluationReport, MetricValue
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import Digest, Document, Text, digest


class EvaluationTable(Document):
    filename: Text
    sha256: Digest
    size_bytes: Annotated[int, Field(ge=0)]
    rows: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def filename_only(self) -> Self:
        if Path(self.filename).name != self.filename or not self.filename.endswith(".csv"):
            raise ValueError("a table must have one local CSV filename")
        return self


class TableExport(Document):
    evaluation_sha256: Digest
    scientific: bool
    tables: tuple[EvaluationTable, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({t.filename for t in self.tables}) != len(self.tables):
            raise ValueError("duplicate table filenames")
        if tuple(t.filename for t in self.tables) != (
            "coverage.csv",
            "metrics.csv",
            "average_precision.csv",
            "incremental.csv",
            "bootstrap.csv",
            "cases.csv",
        ):
            raise ValueError("the complete table inventory is required")
        return self


def _csv(header: tuple[str, ...], rows: list[list[object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _value(metric: MetricValue) -> list[object]:
    return [metric.numerator, metric.denominator, metric.value, metric.reason]


def table_payloads(report: EvaluationReport) -> dict[str, tuple[bytes, int]]:
    """Return deterministic bytes and data-row counts, including undefined/empty strata."""
    return _validated_payloads(EvaluationReport.model_validate(report))


def _validated_payloads(report: EvaluationReport) -> dict[str, tuple[bytes, int]]:
    """Format a report already revalidated at the caller's public boundary.

    Keeping formatting separate avoids a second full deterministic bootstrap
    during write/read, without caching or trusting a caller-supplied instance.
    """
    coverage: list[list[object]] = []
    metrics: list[list[object]] = []
    ap: list[list[object]] = []
    incremental: list[list[object]] = []
    bootstrap: list[list[object]] = []
    cases: list[list[object]] = []
    scope_header = ("mode", "scope", "family", "migration")
    ratio_header = ("numerator", "denominator", "value", "undefined_reason")
    for stratum in report.strata:
        scope: list[object] = [
            report.config.mode,
            stratum.kind,
            stratum.family,
            stratum.migration,
        ]
        summary = stratum.coverage
        coverage.append(
            [
                *scope,
                summary.total_cases,
                summary.oracle_confirmed,
                summary.oracle_pending,
                summary.oracle_disagreement,
                summary.oracle_not_evaluable,
                len(summary.failed_case_ids),
                len(summary.principal_case_ids),
                len(summary.excluded_case_ids),
                *_value(summary.principal_coverage),
            ]
        )
        for method in stratum.methods:
            for support_name, confusion in (
                ("principal", method.principal),
                ("own_support", method.own_support),
            ):
                for metric_name in ("precision", "recall", "f1", "false_positive_rate"):
                    value = getattr(confusion, metric_name)
                    metrics.append(
                        [
                            *scope,
                            method.method,
                            support_name,
                            len(method.complete_case_ids),
                            len(method.own_case_ids),
                            len(method.partial_alert_case_ids),
                            len(method.unavailable_case_ids),
                            method.coverage.numerator,
                            method.coverage.denominator,
                            confusion.tp,
                            confusion.fp,
                            confusion.tn,
                            confusion.fn,
                            metric_name,
                            *_value(value),
                        ]
                    )
        for average in stratum.average_precision:
            for support_name, value, ids in (
                ("principal", average.principal, average.principal_case_ids),
                ("own_support", average.own_support, average.own_case_ids),
            ):
                ap.append([*scope, average.method, support_name, len(ids), *_value(value)])
        gain = stratum.incremental
        for name, ids, value in (
            (
                "additional_true_positives_H_vs_R",
                gain.additional_true_positive_case_ids,
                gain.additional_true_positive_rate,
            ),
            (
                "additional_false_positives_H_vs_R",
                gain.additional_false_positive_case_ids,
                gain.additional_false_positive_rate,
            ),
        ):
            incremental.append([*scope, name, len(ids), *_value(value)])
        interval = stratum.bootstrap
        for estimate in interval.intervals:
            bootstrap.append(
                [
                    *scope,
                    estimate.metric,
                    len(interval.group_ids),
                    interval.attempted_replicates,
                    estimate.defined_replicates,
                    estimate.undefined_replicates,
                    report.config.bootstrap.seed,
                    report.config.bootstrap.confidence,
                    interval.lower_rank,
                    interval.upper_rank,
                    estimate.lower,
                    estimate.upper,
                    estimate.reason,
                ]
            )
    for record in report.records:
        cases.append(
            [
                report.config.mode,
                record.case_id,
                record.scenario_id,
                record.group_id,
                record.family,
                record.migration,
                record.engine,
                record.oracle_state,
                record.oracle_label,
                record.r.decision,
                record.r.complete,
                record.m.decision,
                record.m.complete,
                record.b.decision,
                record.b.complete,
                record.h.decision,
                record.h.complete,
                record.m_score,
                record.b_score,
                record.failure_reason,
            ]
        )
    definitions = (
        (
            "coverage.csv",
            (
                *scope_header,
                "scheduled",
                "confirmed",
                "pending",
                "disagreement",
                "oracle_not_evaluable",
                "failed",
                "principal",
                "excluded",
                *ratio_header,
            ),
            coverage,
        ),
        (
            "metrics.csv",
            (
                *scope_header,
                "method",
                "support",
                "complete",
                "own",
                "partial_alert",
                "not_evaluable",
                "coverage_numerator",
                "coverage_denominator",
                "tp",
                "fp",
                "tn",
                "fn",
                "metric",
                *ratio_header,
            ),
            metrics,
        ),
        (
            "average_precision.csv",
            (*scope_header, "method", "support", "cases", *ratio_header),
            ap,
        ),
        (
            "incremental.csv",
            (*scope_header, "statistic", "additional_cases", *ratio_header),
            incremental,
        ),
        (
            "bootstrap.csv",
            (
                *scope_header,
                "statistic",
                "groups",
                "attempted",
                "defined",
                "undefined",
                "seed",
                "confidence",
                "lower_rank",
                "upper_rank",
                "lower",
                "upper",
                "reason",
            ),
            bootstrap,
        ),
        (
            "cases.csv",
            (
                "mode",
                "case_id",
                "scenario_id",
                "group_id",
                "family",
                "migration",
                "engine",
                "oracle_state",
                "label",
                "R",
                "R_complete",
                "M",
                "M_complete",
                "B",
                "B_complete",
                "H",
                "H_complete",
                "M_score",
                "B_score",
                "failure_reason",
            ),
            cases,
        ),
    )
    return {name: (_csv(header, rows), len(rows)) for name, header, rows in definitions}


def write_tables(report: EvaluationReport, directory: Path) -> TableExport:
    """Publish in a new directory; an interruption cannot leave a valid final receipt."""
    report = EvaluationReport.model_validate(report)
    payloads = _validated_payloads(report)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    tables: list[EvaluationTable] = []
    for filename, (data, rows) in payloads.items():
        with (directory / filename).open("xb") as stream:
            stream.write(data)
        tables.append(
            EvaluationTable(
                filename=filename,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                rows=rows,
            )
        )
    result = TableExport(
        evaluation_sha256=digest(report), scientific=report.scientific, tables=tuple(tables)
    )
    save_document(result, directory / "tables.json")
    return result


def read_tables(directory: Path, *, report: EvaluationReport) -> TableExport:
    """Verify every byte against regeneration and reject unlisted files or links."""
    report = EvaluationReport.model_validate(report)
    if directory.is_symlink() or is_junction(directory):
        raise ValueError("the table directory cannot be a filesystem link")
    directory = directory.resolve()
    manifest = directory / "tables.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 65536:
        raise ValueError("table receipt must be a bounded regular file")
    result = load_document(TableExport, manifest)
    expected = _validated_payloads(report)
    if result.evaluation_sha256 != digest(report) or result.scientific != report.scientific:
        raise ValueError("tables belong to a different evaluation")
    if {p.name for p in directory.iterdir()} != {*expected, "tables.json"}:
        raise ValueError("table directory inventory is not closed")
    for table in result.tables:
        path = directory / table.filename
        if path.is_symlink() or not path.is_file():
            raise ValueError("tables must be regular local files")
        payload, rows = expected[table.filename]
        if path.stat().st_size != len(payload):
            raise ValueError("table size differs from bound regeneration")
        data = path.read_bytes()
        if (
            data != payload
            or hashlib.sha256(data).hexdigest() != table.sha256
            or len(data) != table.size_bytes
            or rows != table.rows
        ):
            raise ValueError("table bytes or row counts differ from bound regeneration")
    return result
