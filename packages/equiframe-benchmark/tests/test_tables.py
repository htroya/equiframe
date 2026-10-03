"""Analytic fixtures: these records are not human reviews or scientific results."""

import csv
import io
import json

import pytest
from equiframe import ComponentDecision

from equiframe_benchmark.evaluation import (
    BootstrapPlan,
    EvaluationConfig,
    EvaluationRecord,
    evaluate_records,
)
from equiframe_benchmark.tables import read_tables, table_payloads, write_tables


def _report():
    records = []
    for index, (label, r, m, b, ms, bs) in enumerate(
        (
            ("divergent", True, True, True, 0.9, 2.0),
            ("divergent", False, True, False, 0.8, 0.1),
            ("normal", False, False, False, 0.1, 0.1),
            ("normal", False, True, True, 0.7, 1.8),
        ),
        start=1,
    ):

        def decision(alert):
            return ComponentDecision(decision="alert" if alert else "no_alert", complete=True)

        records.append(
            EvaluationRecord(
                case_id=f"analytic.{index}",
                scenario_id=f"scenario.{index}",
                group_id=f"group.{(index - 1) // 2}",
                family="nulls_types",
                migration="pandas-duckdb",
                engine="duckdb",
                candidate_sha256=f"{index:064x}",
                pipeline_sha256=f"{index + 10:064x}",
                oracle_sha256=f"{index + 20:064x}",
                oracle_state="confirmed",
                oracle_label=label,
                r=decision(r),
                m=decision(m),
                b=decision(b),
                h=decision(r or m),
                m_score=ms,
                b_score=bs,
                detector_bundle_sha256="a" * 64,
                freeze_sha256=None,
            )
        )
    return evaluate_records(
        tuple(records),
        EvaluationConfig(
            mode="pilot",
            freeze_sha256=None,
            bootstrap=BootstrapPlan(
                seed=11,
                repetitions=20,
                min_groups=3,
                independence_supported=False,
                rationale="Analytic unit fixture, no population inference",
            ),
            expected_migrations=("pandas-duckdb",),
        ),
    )


def _rows(payload):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def test_export_known_paired_counts_and_undefined_families(tmp_path):
    report = _report()
    result = write_tables(report, tmp_path / "tables")
    assert not result.scientific
    rows = _rows((tmp_path / "tables" / "metrics.csv").read_bytes())
    selected = [
        row
        for row in rows
        if row["scope"] == "global" and row["support"] == "principal" and row["metric"] == "f1"
    ]
    r = next(row for row in selected if row["method"] == "R")
    h = next(row for row in selected if row["method"] == "H")
    assert (r["tp"], r["fp"], r["tn"], r["fn"]) == ("1", "0", "2", "1")
    assert (r["numerator"], r["denominator"]) == ("2", "3")
    assert (h["tp"], h["fp"], h["tn"], h["fn"]) == ("2", "1", "1", "0")
    assert (h["numerator"], h["denominator"]) == ("4", "5")
    empty = next(
        row
        for row in rows
        if row["scope"] == "family" and row["family"] == "joins" and row["method"] == "R"
    )
    assert empty["denominator"] == "0" and empty["value"] == ""
    assert empty["undefined_reason"]
    gains = _rows((tmp_path / "tables" / "incremental.csv").read_bytes())
    global_gains = [row for row in gains if row["scope"] == "global"]
    assert len(global_gains) == 2
    assert all(
        (row["additional_cases"], row["numerator"], row["denominator"]) == ("1", "1", "2")
        for row in global_gains
    )
    assert read_tables(tmp_path / "tables", report=report) == result


def test_table_edit_cannot_change_a_result_even_with_rehashed_manifest(tmp_path):
    report = _report()
    root = tmp_path / "tables"
    write_tables(report, root)
    path = root / "metrics.csv"
    data = path.read_bytes()
    changed = data.replace(b",4,5,0.8,", b",4,5,0.9,", 1)
    assert changed != data and len(changed) == len(data)
    path.write_bytes(changed)
    import hashlib

    document = json.loads((root / "tables.json").read_text())
    entry = next(t for t in document["tables"] if t["filename"] == "metrics.csv")
    entry["sha256"] = hashlib.sha256(changed).hexdigest()
    (root / "tables.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="regeneration"):
        read_tables(root, report=report)


def test_no_unlisted_tables_or_edited_row_counts(tmp_path):
    report = _report()
    root = tmp_path / "tables"
    write_tables(report, root)
    document = json.loads((root / "tables.json").read_text())
    document["tables"][0]["rows"] += 1
    (root / "tables.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="row counts"):
        read_tables(root, report=report)
    (root / "unlisted.csv").write_bytes(b"invented,result\n")
    with pytest.raises(ValueError, match="inventory"):
        read_tables(root, report=report)


def test_exclusive_directory_preserves_previous_tables(tmp_path):
    report = _report()
    root = tmp_path / "tables"
    previous = write_tables(report, root)
    with pytest.raises(FileExistsError):
        write_tables(report, root)
    assert read_tables(root, report=report) == previous


def test_interruption_does_not_publish_a_valid_receipt(tmp_path, monkeypatch):
    from equiframe_benchmark import tables

    def interrupted(*args):
        raise OSError("unit fault injection")

    monkeypatch.setattr(tables, "save_document", interrupted)
    report = _report()
    with pytest.raises(OSError):
        write_tables(report, tmp_path / "incomplete")
    assert not (tmp_path / "incomplete" / "tables.json").exists()
    with pytest.raises(ValueError, match="bounded regular"):
        read_tables(tmp_path / "incomplete", report=report)


def test_csv_bytes_are_deterministic_and_keep_case_decisions():
    report = _report()
    first = table_payloads(report)
    assert first == table_payloads(report)
    rows = _rows(first["cases.csv"][0])
    assert len(rows) == 4 and all(row["mode"] == "pilot" for row in rows)
    assert rows[1]["R"] == "no_alert" and rows[1]["H"] == "alert"
    assert rows[3]["label"] == "normal" and rows[3]["H"] == "alert"
