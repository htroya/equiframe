"""Regression guards for metadata disclosure and report-only contracts."""

import json
from pathlib import Path

import jsonschema
import pyarrow as pa
import pytest

import equiframe as ef


def test_missing_column_placeholder_is_not_reported_as_observed_null(tmp_path):
    declaration = ef.infer_diff_contract(
        pa.schema([("id", pa.int64()), ("value", pa.int64())]), keys=["id"]
    )
    result = ef.diff(
        pa.table({"id": [1]}),
        pa.table({"id": [1], "value": [2]}),
        contract=declaration,
        work_dir=tmp_path,
    )
    report = ef.comparison_report(
        result, options=ef.ReportOptions(include_values=True, include_metadata=True)
    )
    values = [value for witness in report.examples for value in witness.candidate]
    assert any(value.kind == "absent_column" and value.value is None for value in values)
    assert not any(value.kind == "null" and value.disclosure == "visible" for value in values)


def test_policy_free_text_and_temporal_bounds_are_not_disclosed_by_default(tmp_path):
    sentinel = "private-policy-contact@example.test"
    column = ef.ColumnSpec(
        name="value",
        logical_type=ef.FloatType(bits=64),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null", "zero"), justification=sentinel),
        nan_policy=ef.NaNPolicy(handling="as_null", justification=sentinel),
        numeric_policy=ef.NumericPolicy(
            comparison="approximate",
            unit=sentinel,
            tolerance=ef.Tolerance(absolute="0.1", unit=sentinel, justification=sentinel),
        ),
    )
    result = ef.diff(
        pa.table({"value": [1.0]}),
        pa.table({"value": [2.0]}),
        contract=ef.bag_contract((column,)),
        work_dir=tmp_path,
    )
    report = ef.comparison_report(result)
    assert sentinel not in report.model_dump_json()
    assert "approximate" in report.to_text() and "0.1" in report.to_text()
    disclosed = ef.comparison_report(result, options=ef.ReportOptions(include_metadata=True))
    assert sentinel in disclosed.model_dump_json()  # Authorized unit metadata, not free messages.


def test_new_report_and_publication_validate_their_json_schemas(tmp_path):
    result = ef.diff(
        pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path / "input"
    )
    report = ef.write_comparison_report(result, tmp_path / "output")
    root = Path(__file__).resolve().parents[1] / "schemas"
    for name, data in (
        ("comparison-report", report.model_dump(mode="json")),
        ("report-options", ef.ReportOptions().model_dump(mode="json")),
        ("report-evidence-manifest", report.evidence.model_dump(mode="json")),
        (
            "report-publication-manifest",
            json.loads((tmp_path / "output/evidence-manifest.json").read_text()),
        ),
    ):
        jsonschema.validate(data, json.loads((root / f"{name}-1.0.schema.json").read_text()))


@pytest.mark.parametrize("mode", ["detail", "reproduction"])
def test_mode_cannot_claim_verification_without_an_authorized_root(tmp_path, mode):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    options = ef.ReportOptions(
        mode=mode, include_metadata=mode == "reproduction", include_values=mode == "reproduction"
    )
    report = ef.comparison_report(result, options=options)
    assert report.state == "different" and report.evidence.acceptance == "not_satisfied"
    assert report.evidence.inspection == "result_only"
