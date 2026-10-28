"""Validation stays at every public boundary, without repeating it in formatters."""

import hashlib
import json

import pytest
from pydantic import ValidationError
from test_evaluation import cases, config

import equiframe_benchmark.evaluation as evaluation
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.pairwise import PairwiseReport, evaluate_pairwise
from equiframe_benchmark.tables import read_tables, table_payloads, write_tables


@pytest.fixture
def report():
    return evaluation.evaluate_records(cases(), config(repetitions=8, independent=True))


def test_historical_evaluation_pairwise_and_six_csv_bytes_are_unchanged(report, tmp_path):
    # Recorded before this refactor from the existing hand-counted eight-case
    # fixture. This supplements its independently expected arithmetic tests.
    assert hashlib.sha256(report.model_dump_json().encode()).hexdigest() == (
        "526f2f4cbdcef4a82365e9fdac2158be1727cc16c6f72bd72f4bbbda8fe642c2"
    )
    assert hashlib.sha256(evaluate_pairwise(report).model_dump_json().encode()).hexdigest() == (
        "43b39b875469a172a0f739c0dd07d633bdacc51b4041fe913ab5aac188d4ec06"
    )
    expected = {
        "average_precision.csv": (
            "04c6a33a91698830fd131b0d13cb994bdfff5697dad5fc42328fcb4e79080e59",
            48,
        ),
        "bootstrap.csv": (
            "cfccb6dee21062aad1416a26a3c1eadf0cec3d1f443b03722666b2a80ff69bf6",
            240,
        ),
        "cases.csv": (
            "73e0e170524cd853ae01ca946566a98b1345efc07ea8888a183c4cc83b49105f",
            8,
        ),
        "coverage.csv": (
            "ab9b9dbb3c2d21a1956ed109d4e06aff9da2fb219a2cfe5e8e2f9359c60b2b93",
            12,
        ),
        "incremental.csv": (
            "2cbe885bdcba13d58f1d47b24d724a9e56e638b889adced8547c1e9af07a18ba",
            24,
        ),
        "metrics.csv": (
            "85bf3adafe07d0dfa01561d1947cf6a0e96feb3d166bae3e37ba1591981fff22",
            384,
        ),
    }
    payloads = table_payloads(report)
    assert {
        name: (hashlib.sha256(data).hexdigest(), rows) for name, (data, rows) in payloads.items()
    } == (expected)
    output = tmp_path / "tables"
    receipt = write_tables(report, output)
    assert read_tables(output, report=report) == receipt
    for name, (data, _) in payloads.items():
        assert (output / name).read_bytes() == data


@pytest.mark.parametrize("boundary", ["payloads", "write", "read", "pairwise"])
def test_public_functions_perform_only_required_recalculation(
    report, tmp_path, monkeypatch, boundary
):
    output = tmp_path / "tables"
    if boundary == "read":
        write_tables(report, output)
    original = evaluation._strata
    calls = []

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(evaluation, "_strata", counted)
    if boundary == "payloads":
        table_payloads(report)
    elif boundary == "write":
        write_tables(report, output)
    elif boundary == "read":
        read_tables(output, report=report)
    else:
        evaluate_pairwise(report)
    # Pairwise explicitly checks the input and constructs a new enclosing model,
    # whose nested field validates once. Its after-validator must not do it again.
    assert len(calls) == (2 if boundary == "pairwise" else 1)


@pytest.mark.parametrize("boundary", ["model", "json", "save", "load"])
def test_pairwise_documents_revalidate_nested_evaluation_once(
    report, tmp_path, monkeypatch, boundary
):
    paired = evaluate_pairwise(report)
    path = tmp_path / "pairwise.json"
    if boundary == "load":
        save_document(paired, path)
    original = evaluation._strata
    calls = []

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(evaluation, "_strata", counted)
    if boundary == "model":
        PairwiseReport.model_validate(paired)
    elif boundary == "json":
        PairwiseReport.model_validate_json(paired.model_dump_json())
    elif boundary == "save":
        save_document(paired, path)
    else:
        load_document(PairwiseReport, path)
    assert len(calls) == 1


@pytest.mark.parametrize("boundary", ["payloads", "write", "read", "pairwise"])
def test_mutated_evaluation_rejected_at_every_function_boundary(report, tmp_path, boundary):
    output = tmp_path / "tables"
    if boundary == "read":
        write_tables(report, output)
    invalid = report.model_copy(update={"strata": ()})
    with pytest.raises(ValidationError):
        if boundary == "payloads":
            table_payloads(invalid)
        elif boundary == "write":
            write_tables(invalid, output)
        elif boundary == "read":
            read_tables(output, report=invalid)
        else:
            evaluate_pairwise(invalid)
    if boundary == "write":
        assert not output.exists()


@pytest.mark.parametrize("boundary", ["model", "json", "save", "load"])
@pytest.mark.parametrize("part", ["evaluation", "paired_strata"])
def test_mutated_pairwise_and_json_rejected_at_every_document_boundary(
    report, tmp_path, boundary, part
):
    paired = evaluate_pairwise(report)
    invalid = paired.model_copy(
        update={"evaluation": report.model_copy(update={"strata": ()})}
        if part == "evaluation"
        else {"strata": ()}
    )
    path = tmp_path / "invalid.json"
    raw = json.dumps(invalid.model_dump(mode="json"))
    if boundary == "load":
        path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValidationError):
        if boundary == "model":
            PairwiseReport.model_validate(invalid)
        elif boundary == "json":
            PairwiseReport.model_validate_json(raw)
        elif boundary == "save":
            save_document(invalid, path)
        else:
            load_document(PairwiseReport, path)
    if boundary == "save":
        assert not path.exists()
