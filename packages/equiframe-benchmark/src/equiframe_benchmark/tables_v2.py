"""Exact V2 paired tables, with exclusions, denominators and common-support appendix."""

import hashlib
from pathlib import Path
from typing import Literal

from equiframe._path_compat import is_junction
from pydantic import model_validator
from typing_extensions import Self

from equiframe_benchmark.evaluation_v2 import EvaluationReportV2, SignedMetricV2
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import Digest, digest
from equiframe_benchmark.models_v2 import DocumentV2 as Document
from equiframe_benchmark.tables import EvaluationTable, _csv

TABLES_V2 = (
    "coverage.csv",
    "metrics.csv",
    "bootstrap.csv",
    "exclusions.csv",
    "common_metrics.csv",
    "common_bootstrap.csv",
    "cases.csv",
)


class TableExportV2(Document):
    schema_version: Literal["2.0"] = "2.0"
    evaluation_sha256: Digest
    scientific: bool
    tables: tuple[EvaluationTable, ...]

    @model_validator(mode="after")
    def inventory(self) -> Self:
        if tuple(table.filename for table in self.tables) != TABLES_V2:
            raise ValueError("V2 requires its complete ordered seven-table inventory")
        return self


def _value(value: SignedMetricV2) -> list[object]:
    return [value.numerator, value.denominator, value.value, value.reason]


def _validated_payloads(report: EvaluationReportV2) -> dict[str, tuple[bytes, int]]:
    rows: dict[str, list[list[object]]] = {name: [] for name in TABLES_V2}
    scope_header = ("mode", "scope", "family", "migration")
    pair_header = (*scope_header, "left_method", "right_method")
    ratio = ("numerator", "denominator", "value", "undefined_reason")
    for stratum in report.strata:
        scope: list[object] = [
            report.config.mode,
            stratum.kind,
            stratum.family,
            stratum.migration,
        ]
        for contrast in stratum.principal:
            pair = contrast.comparison
            identity = [*scope, pair.left_method, pair.right_method]
            rows["coverage.csv"].append(
                [
                    *identity,
                    stratum.total_cases,
                    stratum.oracle_confirmed,
                    len(pair.support_case_ids),
                    len(pair.group_ids),
                    pair.divergent_cases,
                    pair.normal_cases,
                    pair.coverage_confirmed.numerator,
                    pair.coverage_confirmed.denominator,
                    pair.coverage_confirmed.value,
                    pair.coverage_confirmed.reason,
                    pair.coverage_scheduled.numerator,
                    pair.coverage_scheduled.denominator,
                    pair.coverage_scheduled.value,
                    pair.coverage_scheduled.reason,
                    len(pair.exclusions),
                    len(pair.left_partial_alert_case_ids),
                    len(pair.right_partial_alert_case_ids),
                ]
            )
            for estimate in contrast.estimates:
                rows["metrics.csv"].append(
                    [
                        *identity,
                        estimate.name,
                        *_value(estimate.estimate),
                    ]
                )
            for interval in contrast.bootstrap.intervals:
                rows["bootstrap.csv"].append(
                    [
                        *identity,
                        interval.metric,
                        len(contrast.bootstrap.group_ids),
                        contrast.bootstrap.attempted_replicates,
                        contrast.bootstrap.lower_rank,
                        contrast.bootstrap.upper_rank,
                        interval.lower,
                        interval.upper,
                        interval.defined_replicates,
                        interval.undefined_replicates,
                        interval.reason,
                    ]
                )
            for exclusion in pair.exclusions:
                for reason in exclusion.reasons:
                    rows["exclusions.csv"].append(
                        [
                            *identity,
                            exclusion.case_id,
                            exclusion.oracle_state,
                            reason,
                        ]
                    )
        for method in stratum.common.methods:
            confusion = method.metrics
            values = [
                (metric, getattr(confusion, metric))
                for metric in ("precision", "recall", "f1", "false_positive_rate")
            ]
            if method.average_precision is not None:
                values.append(("average_precision", method.average_precision))
            for name, value in values:
                rows["common_metrics.csv"].append(
                    [
                        *scope,
                        stratum.common.role,
                        len(stratum.common.case_ids),
                        method.method,
                        confusion.tp,
                        confusion.fp,
                        confusion.fn,
                        confusion.tn,
                        name,
                        value.numerator,
                        value.denominator,
                        value.value,
                        value.reason,
                    ]
                )
        for interval in stratum.common.bootstrap.intervals:
            bootstrap = stratum.common.bootstrap
            rows["common_bootstrap.csv"].append(
                [
                    *scope,
                    stratum.common.role,
                    interval.metric,
                    len(bootstrap.group_ids),
                    bootstrap.attempted_replicates,
                    bootstrap.lower_rank,
                    bootstrap.upper_rank,
                    interval.lower,
                    interval.upper,
                    interval.defined_replicates,
                    interval.undefined_replicates,
                    interval.reason,
                ]
            )
    for record in report.records:
        decisions: list[object] = []
        for component in (record.r, record.m, record.b, record.h):
            decisions.extend((component.decision, component.complete, component.reason))
        rows["cases.csv"].append(
            [
                record.case_id,
                record.scenario_id,
                record.group_id,
                record.family,
                record.migration,
                record.engine,
                record.oracle_state,
                record.oracle_label,
                *decisions,
                record.m_score,
                record.b_score,
                record.candidate_sha256,
                record.pipeline_sha256,
                record.oracle_sha256,
                record.detector_bundle_sha256,
                record.freeze_sha256,
                record.failure_reason,
            ]
        )
    headers = {
        "coverage.csv": (
            *pair_header,
            "scheduled",
            "confirmed",
            "paired",
            "groups",
            "divergent",
            "normal",
            "confirmed_numerator",
            "confirmed_denominator",
            "confirmed_coverage",
            "confirmed_undefined",
            "scheduled_numerator",
            "scheduled_denominator",
            "scheduled_coverage",
            "scheduled_undefined",
            "excluded",
            "left_partial_alerts",
            "right_partial_alerts",
        ),
        "metrics.csv": (*pair_header, "metric", *ratio),
        "bootstrap.csv": (
            *pair_header,
            "metric",
            "groups",
            "attempted",
            "lower_rank",
            "upper_rank",
            "lower",
            "upper",
            "defined",
            "undefined",
            "reason",
        ),
        "exclusions.csv": (*pair_header, "case_id", "oracle_state", "reason"),
        "common_metrics.csv": (
            *scope_header,
            "role",
            "common_support",
            "method",
            "tp",
            "fp",
            "fn",
            "tn",
            "metric",
            *ratio,
        ),
        "common_bootstrap.csv": (
            *scope_header,
            "role",
            "metric",
            "groups",
            "attempted",
            "lower_rank",
            "upper_rank",
            "lower",
            "upper",
            "defined",
            "undefined",
            "reason",
        ),
        "cases.csv": (
            "case_id",
            "scenario_id",
            "group_id",
            "family",
            "migration",
            "engine",
            "oracle_state",
            "oracle_label",
            "R",
            "R_complete",
            "R_reason",
            "M",
            "M_complete",
            "M_reason",
            "B",
            "B_complete",
            "B_reason",
            "H",
            "H_complete",
            "H_reason",
            "M_score",
            "B_score",
            "candidate_sha256",
            "pipeline_sha256",
            "oracle_sha256",
            "bundle_sha256",
            "freeze_sha256",
            "failure_reason",
        ),
    }
    return {name: (_csv(headers[name], rows[name]), len(rows[name])) for name in TABLES_V2}


def table_payloads_v2(report: EvaluationReportV2) -> dict[str, tuple[bytes, int]]:
    return _validated_payloads(EvaluationReportV2.model_validate(report))


def write_tables_v2(report: EvaluationReportV2, directory: Path) -> TableExportV2:
    checked = EvaluationReportV2.model_validate(report)
    payloads = _validated_payloads(checked)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    tables = []
    for name, (payload, rows) in payloads.items():
        with (directory / name).open("xb") as output:
            output.write(payload)
        tables.append(
            EvaluationTable(
                filename=name,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                rows=rows,
            )
        )
    receipt = TableExportV2(
        evaluation_sha256=digest(checked),
        scientific=checked.scientific,
        tables=tuple(tables),
    )
    save_document(receipt, directory / "tables.json")
    return receipt


def read_tables_v2(directory: Path, *, report: EvaluationReportV2) -> TableExportV2:
    checked = EvaluationReportV2.model_validate(report)
    if directory.is_symlink() or is_junction(directory):
        raise ValueError("V2 table directory must not be a filesystem link")
    directory = directory.resolve()
    path = directory / "tables.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("V2 table receipt must be a bounded regular file")
    receipt = load_document(TableExportV2, path)
    expected = _validated_payloads(checked)
    if receipt.evaluation_sha256 != digest(checked) or receipt.scientific != checked.scientific:
        raise ValueError("V2 tables belong to a different paired evaluation")
    if {entry.name for entry in directory.iterdir()} != {*expected, "tables.json"}:
        raise ValueError("V2 table inventory must be closed")
    for table in receipt.tables:
        target = directory / table.filename
        if target.is_symlink() or is_junction(target) or not target.is_file():
            raise ValueError("V2 tables must be regular local files")
        payload, rows = expected[table.filename]
        if target.stat().st_size != len(payload):
            raise ValueError("V2 table size differs from regeneration")
        data = target.read_bytes()
        if (
            data != payload
            or hashlib.sha256(data).hexdigest() != table.sha256
            or len(data) != table.size_bytes
            or rows != table.rows
        ):
            raise ValueError("V2 table bytes or counts differ from captured decisions")
    return receipt
