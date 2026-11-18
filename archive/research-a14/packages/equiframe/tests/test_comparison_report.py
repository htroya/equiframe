"""Independent STEP3 expectations: disclosure never rewrites comparison semantics."""

import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe.comparison_report import comparison_report, write_comparison_report
from equiframe.report_types import ComparisonReport, ReportCount, ReportOptions


def column(name="value", *, nullable=True):
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )


def count(report, name, value, precision="exact", unit="rows"):
    found = {item.name: item for item in report.counts}
    assert name in found
    assert found[name] == ReportCount(name=name, value=value, precision=precision, unit=unit)


def root_for(result, directory):
    return directory / result.comparison_id


def views(report):
    return (
        report.model_dump_json(),
        report.to_text(),
        report.to_html(),
        report._repr_html_(),
    )


def scalar_values(report):
    return [
        value
        for witness in report.examples
        for value in (*witness.key, *witness.candidate, *witness.reference)
    ]


def test_public_report_exports_are_available():
    assert ef.comparison_report is comparison_report
    assert ef.write_comparison_report is write_comparison_report
    assert ef.ComparisonReport is ComparisonReport
    assert ef.ReportOptions is ReportOptions
    for name in (
        "comparison_report",
        "write_comparison_report",
        "ComparisonReport",
        "ReportOptions",
    ):
        assert name in ef.__all__


@pytest.mark.parametrize("link_kind", ["symlink", "junction"])
def test_report_publication_refuses_linked_roots_before_writing(tmp_path, link_kind):
    real = tmp_path / "external"
    real.mkdir()
    marker = real / "unchanged.bin"
    marker.write_bytes(b"external data")
    link = tmp_path / "linked"
    if link_kind == "junction":
        if os.name != "nt":
            pytest.skip("Windows directory junction")
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(real)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert made.returncode == 0, made.stderr
    else:
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:
            pytest.skip("Host does not permit directory symlinks")
    table = pa.table({"value": [1, 1, 2]})
    result = ef.diff(table, table, work_dir=tmp_path / "comparison")
    try:
        with pytest.raises(ef.ArtifactIntegrityError):
            write_comparison_report(result, link / "report")
        assert list(real.iterdir()) == [marker]
        assert marker.read_bytes() == b"external data"
    finally:
        if link_kind == "junction":
            link.rmdir()
        else:
            link.unlink()


def test_report_publication_accepts_ordinary_parent_navigation(tmp_path):
    traversed = tmp_path / "traversed"
    traversed.mkdir()
    table = pa.table({"value": [1, 1, 2]})
    result = ef.diff(table, table, work_dir=tmp_path / "comparison")
    report = write_comparison_report(result, traversed / ".." / "report")
    assert report.state == "equivalent" and report.complete
    assert ef.read_comparison_report(tmp_path / "report/report.json") == report
    assert not list(traversed.iterdir())


@pytest.mark.parametrize("reference", ["peer", "expected"])
def test_complete_equivalence_preserves_reference_and_exact_counts(tmp_path, reference):
    candidate = pa.table({"id": [2, 1], "value": [20, 10]})
    expected = pa.table({"id": [1, 2], "value": [10, 20]})
    result = ef.diff(candidate, expected, keys=["id"], reference=reference, work_dir=tmp_path)
    report = comparison_report(result)
    assert report.state == "equivalent"
    assert report.complete and report.coverage == "complete"
    assert report.reference == reference and report.strategy == "key"
    assert report.contract_sha256 == result.contract_sha256
    assert report.spec_sha256 == result.spec_sha256
    assert report.examples == ()
    assert report.evidence.inspection == "result_only"
    assert report.evidence.counts_final and report.evidence.display_complete
    assert report.evidence.acceptance == "satisfied"
    count(report, "candidate_rows", 2)
    count(report, "reference_rows", 2)
    count(report, "matched_rows", 2)
    count(report, "difference_records", 0, unit="records")
    count(report, "contract_violations", 0, unit="records")
    assert ComparisonReport.model_validate_json(report.model_dump_json()) == report
    assert all("equivalent" in rendered for rendered in views(report))


@pytest.mark.parametrize("strategy", ["key", "sequence"])
def test_two_changed_cells_count_as_one_modified_row(tmp_path, strategy):
    columns = (column("id"), column("a"), column("b"))
    declaration = (
        ef.keyed_contract(columns, keys=["id"])
        if strategy == "key"
        else ef.sequence_contract(
            columns, by=[ef.SortSpec(column="id", direction="ascending", nulls="last")]
        )
    )
    result = ef.diff(
        pa.table({"id": [1, 2], "a": [91, 20], "b": [92, 200]}),
        pa.table({"id": [1, 2], "a": [10, 20], "b": [100, 200]}),
        contract=declaration,
        work_dir=tmp_path,
    )
    assert result.state == "different" and result.counts.difference_records == 2
    report = comparison_report(result, evidence_root=root_for(result, tmp_path))
    assert report.state == "different" and report.strategy == strategy and report.complete
    count(report, "modified_rows", 1)
    count(report, "added_rows", 0)
    count(report, "removed_rows", 0)
    count(report, "matched_rows", 1)
    count(report, "difference_records", 2, unit="records")
    assert report.evidence.inspection == "verified_differences"


def test_keyed_added_removed_and_modified_are_independent_counts(tmp_path):
    result = ef.diff(
        pa.table({"id": [1, 2, 4], "value": [11, 20, 40]}),
        pa.table({"id": [1, 2, 3], "value": [10, 20, 30]}),
        keys=["id"],
        work_dir=tmp_path,
    )
    report = comparison_report(result, evidence_root=root_for(result, tmp_path))
    count(report, "candidate_rows", 3)
    count(report, "reference_rows", 3)
    count(report, "matched_rows", 1)
    count(report, "modified_rows", 1)
    count(report, "added_rows", 1)
    count(report, "removed_rows", 1)
    count(report, "difference_records", 3, unit="records")


def test_bag_multiplicity_is_occurrences_not_invented_modified_rows(tmp_path):
    result = ef.diff(
        pa.table({"value": [7, 7, 7, 9]}),
        pa.table({"value": [7, 9, 9]}),
        work_dir=tmp_path,
    )
    report = comparison_report(result, evidence_root=root_for(result, tmp_path))
    assert report.strategy == "multiset" and report.state == "different"
    count(report, "candidate_rows", 4)
    count(report, "reference_rows", 3)
    count(report, "matched_rows", 2)
    count(report, "difference_records", 2, unit="records")
    count(report, "candidate_excess_occurrences", 2, unit="occurrences")
    count(report, "reference_excess_occurrences", 1, unit="occurrences")
    count(report, "modified_rows", None, "unknown")
    assert sorted((w.candidate_count, w.reference_count) for w in report.examples) == [
        (1, 2),
        (3, 1),
    ]


def test_duplicate_declared_keys_preserve_fallback_and_contract_violations(tmp_path):
    table = pa.table({"id": [1, 1], "value": [7, 8]})
    result = ef.diff(table, table, keys=["id"], reference="peer", work_dir=tmp_path)
    report = comparison_report(result, evidence_root=root_for(result, tmp_path))
    assert report.state == "different" and report.complete
    assert report.strategy == "multiset"
    assert any(w.category == "contract" for w in report.examples)
    # One duplicate beyond the first occurrence, raw and normalized, on each side.
    count(report, "contract_violations", 4, unit="records")
    count(report, "modified_rows", None, "unknown")
    count(report, "candidate_excess_occurrences", 0, unit="occurrences")
    count(report, "reference_excess_occurrences", 0, unit="occurrences")


def test_invalid_expected_is_not_evaluable_even_when_complete(tmp_path):
    declaration = ef.bag_contract((column(nullable=False),))
    result = ef.diff(
        pa.table({"value": [1]}),
        pa.table({"value": pa.array([None], type=pa.int64())}),
        contract=declaration,
        work_dir=tmp_path,
    )
    assert result.complete and result.state == "not_evaluable"
    report = comparison_report(result)
    assert report.state == "not_evaluable" and report.complete
    assert report.coverage == "complete" and report.evidence.counts_final
    assert any("expected reference violates" in reason.lower() for reason in report.reasons)
    assert report.next_action
    for rendered in views(report):
        assert "not_evaluable" in rendered


def test_partial_evaluation_retains_evidence_without_fabricating_totals(tmp_path):
    table = pa.table({"value": pa.array([None, None, None], type=pa.int64())})
    declaration = ef.bag_contract((column(nullable=False),))
    result = ef.diff(
        table,
        table,
        contract=declaration,
        options=ef.ComparisonOptions(max_rows=2),
        work_dir=tmp_path,
    )
    assert not result.complete and result.counts.difference_records == 2
    report = comparison_report(result)
    assert report.state == "not_evaluable" and not report.complete
    assert report.coverage == "partial" and not report.evidence.counts_final
    count(report, "candidate_rows", 2, "lower_bound")
    count(report, "reference_rows", None, "unknown")
    count(report, "matched_rows", None, "unknown")
    count(report, "difference_records", 2, "lower_bound", unit="records")
    count(report, "contract_violations", 2, "lower_bound", unit="records")
    assert len(report.examples) == 2


def test_failure_before_ingestion_exposes_unknown_counts_not_zero(tmp_path):
    declaration = ef.bag_contract((column(),))
    result = ef.compare(
        tmp_path / "private-source-secret.arrow",
        ef.ArrowInput(pa.table({"value": [1]})),
        contract=declaration.spec.contract,
        work_dir=tmp_path,
    )
    report = comparison_report(result)
    assert report.state == "not_evaluable" and report.strategy == "pending"
    for name in ("candidate_rows", "reference_rows", "matched_rows", "modified_rows"):
        count(report, name, None, "unknown")
    assert all("private-source-secret" not in rendered for rendered in views(report))


def test_difference_at_last_row_cannot_be_hidden_by_display_budget(tmp_path):
    expected = pa.table({"id": list(range(100)), "value": list(range(100))})
    candidate = pa.table({"id": list(range(100)), "value": [*range(99), 999]})
    result = ef.diff(
        candidate,
        expected,
        keys=["id"],
        options=ef.ComparisonOptions(max_examples=0),
        work_dir=tmp_path,
    )
    assert result.state == "different" and result.examples == ()
    report = comparison_report(result, options=ReportOptions(max_examples=0))
    assert report.state == "different" and report.complete and not report.examples
    count(report, "candidate_rows", 100)
    count(report, "matched_rows", 99)
    count(report, "difference_records", 1, unit="records")
    assert not report.evidence.display_complete
    verified = comparison_report(
        result,
        options=ReportOptions(max_examples=1, include_values=True),
        evidence_root=root_for(result, tmp_path),
    )
    assert verified.state == report.state and verified.complete == report.complete
    count(verified, "modified_rows", 1)
    assert verified.examples[0].position == 99
    assert verified.examples[0].candidate[0].value == ef.ComparisonValue(
        kind="integer", value="999"
    )


def test_display_limit_does_not_limit_verified_totals_or_exhaustiveness(tmp_path):
    result = ef.diff(
        pa.table({"id": [1, 2, 3], "value": [11, 22, 33]}),
        pa.table({"id": [1, 2, 3], "value": [10, 20, 30]}),
        keys=["id"],
        options=ef.ComparisonOptions(max_examples=1),
        work_dir=tmp_path,
    )
    limited = comparison_report(result, options=ReportOptions(max_examples=1))
    count(limited, "modified_rows", 1, "lower_bound")
    reports = [
        comparison_report(
            result,
            evidence_root=root_for(result, tmp_path),
            options=ReportOptions(max_examples=limit, require_exhaustive=True),
        )
        for limit in (0, 1, 20)
    ]
    for report, expected_examples in zip(reports, (0, 1, 3), strict=True):
        assert report.state == "different" and report.complete
        assert len(report.examples) == expected_examples
        count(report, "modified_rows", 3)
        count(report, "difference_records", 3, unit="records")
        assert report.evidence.available_records == 3
        assert report.evidence.acceptance == "satisfied"
    assert reports[0].counts == reports[1].counts == reports[2].counts


def test_value_and_metadata_disclosures_are_separate_opt_ins(tmp_path):
    secret_name, secret_value = "private_employee_identifier", "SECRET_ROW_VALUE_93841"
    result = ef.diff(
        pa.table({"id": [1], secret_name: [secret_value]}),
        pa.table({"id": [1], secret_name: ["expected_public_placeholder"]}),
        keys=["id"],
        work_dir=tmp_path / "private-path-77561",
    )
    default = comparison_report(result)
    value_only = comparison_report(result, options=ReportOptions(include_values=True))
    metadata_only = comparison_report(result, options=ReportOptions(include_metadata=True))
    for rendered in views(default):
        for secret in (secret_name, secret_value, "private-path-77561", str(tmp_path)):
            assert secret not in rendered
    assert all(value.disclosure == "redacted" for value in scalar_values(default))
    for rendered in views(value_only):
        assert secret_value in rendered and secret_name not in rendered
    for rendered in views(metadata_only):
        assert secret_name in rendered and secret_value not in rendered
    assert all(value.value is None for value in scalar_values(metadata_only))


def test_selected_column_redaction_applies_to_keys_and_full_row_witnesses(tmp_path):
    secret = "PRIVATE_IDENTIFIER_73494"
    result = ef.diff(
        pa.table({"secret_id": [secret], "public_value": [10]}),
        pa.table({"secret_id": ["other"], "public_value": [20]}),
        keys=["secret_id"],
        work_dir=tmp_path,
    )
    report = comparison_report(
        result,
        options=ReportOptions(
            include_values=True, include_metadata=True, redact_columns=("secret_id",)
        ),
    )
    assert report.options.redacted_column_count == 1
    assert all(secret not in rendered for rendered in views(report))
    witnesses = report.examples
    assert all(w.candidate[0].disclosure == "redacted" for w in witnesses if w.candidate)
    assert all(w.reference[0].disclosure == "redacted" for w in witnesses if w.reference)
    assert any(value.disclosure == "visible" for value in scalar_values(report))


def test_redacted_selector_names_do_not_leak_when_metadata_is_disabled(tmp_path):
    name = "confidential_column_98462"
    result = ef.diff(pa.table({name: [1]}), pa.table({name: [2]}), work_dir=tmp_path)
    report = comparison_report(
        result, options=ReportOptions(include_values=True, redact_columns=(name,))
    )
    assert report.options.redacted_column_count == 1
    assert all(name not in rendered for rendered in views(report))


def test_exact_decimal_date_timestamp_null_nan_and_integer_tags_survive(tmp_path):
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("money", pa.decimal128(38, 9)),
            ("date", pa.date32()),
            ("instant", pa.timestamp("ns", "UTC")),
            ("missing", pa.float64()),
            ("large_integer", pa.int64()),
        ]
    )
    candidate = pa.Table.from_pylist(
        [
            {
                "id": 1,
                "money": Decimal("12345678901234567890123456789.123456789"),
                "date": 1,
                "instant": 1,
                "missing": float("nan"),
                "large_integer": 9223372036854775807,
            }
        ],
        schema=schema,
    )
    expected = pa.Table.from_pylist(
        [
            {
                "id": 1,
                "money": Decimal("12345678901234567890123456789.123456788"),
                "date": 2,
                "instant": 2,
                "missing": None,
                "large_integer": 9223372036854775806,
            }
        ],
        schema=schema,
    )
    result = ef.diff(candidate, expected, keys=["id"], work_dir=tmp_path)
    report = comparison_report(
        result, options=ReportOptions(include_values=True, include_metadata=True)
    )
    witnesses = {w.column: w for w in report.examples}
    anticipated = {
        "money": ef.ComparisonValue(
            kind="decimal", value="12345678901234567890123456789.123456789"
        ),
        "date": ef.ComparisonValue(kind="date", value="1", unit="day"),
        "instant": ef.ComparisonValue(kind="timestamp", value="1", unit="ns", timezone="UTC"),
        "missing": ef.ComparisonValue(kind="nan"),
        "large_integer": ef.ComparisonValue(kind="integer", value="9223372036854775807"),
    }
    for name, value in anticipated.items():
        assert witnesses[name].candidate[0].value == value
        assert witnesses[name].candidate[0].disclosure == "visible"
        assert witnesses[name].candidate[0].physical_type
    assert witnesses["missing"].reference[0].value == ef.ComparisonValue(kind="null")
    for rendered in views(report):
        assert "12345678901234567890123456789.123456789" in rendered
        assert "9223372036854775807" in rendered
        assert "nan" in rendered.lower() and "null" in rendered.lower()


def test_oversize_numeric_evidence_is_omitted_not_truncated(tmp_path):
    result = ef.diff(
        pa.table({"id": [1], "value": [9223372036854775807]}),
        pa.table({"id": [1], "value": [9223372036854775806]}),
        keys=["id"],
        work_dir=tmp_path,
    )
    report = comparison_report(
        result, options=ReportOptions(include_values=True, max_value_chars=16)
    )
    assert report.state == "different" and report.complete
    witness = report.examples[0]
    for value in (*witness.candidate, *witness.reference):
        assert value.disclosure == "omitted" and value.value is None
        assert value.representation == "[omitted]"
    assert all("9223372036854775" not in rendered for rendered in views(report))


def test_default_build_and_render_are_detached_without_optional_imports_or_io(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    script = r"""
import builtins
import importlib.abc
import os
import pathlib
import sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'pyarrow', 'pandas', 'polars', 'duckdb', 'numpy', 'IPython', 'ipykernel', 'nbformat'
        }:
            raise AssertionError('optional dependency imported: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
import equiframe as ef
from equiframe.comparison_report import comparison_report
result = ef.ComparisonResult.model_validate_json(sys.stdin.read())
def no_io(*args, **kwargs):
    raise AssertionError('report attempted filesystem access')
pathlib.Path.open = no_io
builtins.open = no_io
os.open = no_io
report = comparison_report(result)
rendered_views = (
    report.model_dump_json(), report.to_text(), report.to_html(), report._repr_html_()
)
for rendered in rendered_views:
    assert 'different' in rendered
print('detached report verified')
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        input=result.model_dump_json(),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "detached report verified"


def test_verifying_differences_does_not_require_original_tables(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    for source in (result.left, result.right):
        assert source is not None
        path = Path(url2pathname(urlsplit(source.data.uri).path))
        assert path.is_relative_to(tmp_path)
        path.unlink()
    report = comparison_report(result, evidence_root=root_for(result, tmp_path))
    assert report.evidence.inspection == "verified_differences"
    assert report.state == "different" and report.complete


@pytest.mark.parametrize("max_records,max_evidence_bytes", [(1, 1048576), (100, 1)])
def test_inspection_budget_never_claims_exhaustive_evidence(
    tmp_path, max_records, max_evidence_bytes
):
    result = ef.diff(
        pa.table({"id": [1, 2], "value": [11, 22]}),
        pa.table({"id": [1, 2], "value": [10, 20]}),
        keys=["id"],
        work_dir=tmp_path,
    )
    report = comparison_report(
        result,
        evidence_root=root_for(result, tmp_path),
        options=ReportOptions(
            require_exhaustive=True,
            max_records=max_records,
            max_evidence_bytes=max_evidence_bytes,
        ),
    )
    assert report.state == "different" and report.complete
    assert report.evidence.acceptance == "not_satisfied"
    assert report.evidence.unmet_requirements
    assert report.evidence.inspection == "result_only"


def test_exhaustive_request_requires_verified_original_evidence(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    report = comparison_report(result, options=ReportOptions(require_exhaustive=True))
    assert report.state == "different" and report.complete
    assert report.evidence.acceptance == "not_satisfied"
    assert report.evidence.unmet_requirements
    assert report.evidence.inspection == "result_only"


@pytest.mark.parametrize("filename", ["comparison.json", "differences.jsonl"])
def test_damaged_evidence_does_not_change_verdict_or_claim_verified_report(tmp_path, filename):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    root = root_for(result, tmp_path)
    (root / filename).write_bytes(b'{"forged":true}\n')
    detached = comparison_report(result)
    assert detached.state == "different" and detached.evidence.inspection == "result_only"
    with pytest.raises(ef.ArtifactIntegrityError):
        comparison_report(
            result, evidence_root=root, options=ReportOptions(require_exhaustive=True)
        )
    assert result.state == "different" and result.complete


def test_report_byte_budget_raises_instead_of_truncating_to_false_success(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    with pytest.raises(ef.ResourceLimitError):
        comparison_report(result, options=ReportOptions(max_report_bytes=16))


@pytest.mark.parametrize(
    "options",
    [
        {"mode": "reproduction"},
        {"mode": "reproduction", "include_values": True},
        {
            "mode": "reproduction",
            "include_values": True,
            "include_metadata": True,
            "redact_columns": ("value",),
        },
        {"redact_columns": ("value", "value")},
        {"max_examples": -1},
    ],
)
def test_invalid_disclosure_and_budget_options_are_rejected(options):
    with pytest.raises(ValidationError):
        ReportOptions(**options)


def test_reproduction_view_needs_explicit_verified_export(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path)
    report = comparison_report(
        result,
        evidence_root=root_for(result, tmp_path),
        options=ReportOptions(mode="reproduction", include_values=True, include_metadata=True),
    )
    assert report.evidence.reproduction == "requires_verified_export"
    assert report.evidence.acceptance == "not_satisfied"
    assert report.state == "different" and report.complete


def test_writer_publishes_same_sanitized_model_in_private_exclusive_directory(tmp_path):
    result = ef.diff(
        pa.table({"private_column": ["secret-record-value"]}),
        pa.table({"private_column": ["other"]}),
        work_dir=tmp_path / "raw",
    )
    destination = tmp_path / "report"
    report = write_comparison_report(result, destination)
    assert set(path.name for path in destination.iterdir()) == {
        "report.json",
        "report.html",
        "report.txt",
        "evidence-manifest.json",
    }
    assert (
        ComparisonReport.model_validate_json((destination / "report.json").read_bytes()) == report
    )
    assert (destination / "report.html").read_text() == report.to_html()
    assert (destination / "report.txt").read_text() == report.to_text()
    for path in destination.iterdir():
        data = path.read_bytes()
        assert b"secret-record-value" not in data and b"private_column" not in data
    if os.name == "posix":
        assert destination.stat().st_mode & 0o077 == 0
        assert all(path.stat().st_mode & 0o077 == 0 for path in destination.iterdir())
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.iterdir()
    }
    with pytest.raises(FileExistsError):
        write_comparison_report(result, destination)
    after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.iterdir()
    }
    assert before == after
    manifest = json.loads((destination / "evidence-manifest.json").read_text())
    assert manifest["publication_complete"] is True
    assert manifest["report_evidence"] == report.evidence.model_dump(mode="json")
    assert {item["path"] for item in manifest["files"]} == {
        "report.json",
        "report.html",
        "report.txt",
    }
    for item in manifest["files"]:
        payload = (destination / item["path"]).read_bytes()
        assert item["size_bytes"] == len(payload)
        assert item["sha256"] == hashlib.sha256(payload).hexdigest()


def test_writer_budget_failure_does_not_publish_success_manifest(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path / "raw")
    destination = tmp_path / "failed-report"
    with pytest.raises(ef.ResourceLimitError):
        write_comparison_report(result, destination, options=ReportOptions(max_report_bytes=16))
    assert not (destination / "evidence-manifest.json").exists()
    assert not (destination / "report.json").exists()


def test_untrusted_producer_errors_and_codes_never_become_default_report_text(tmp_path):
    declaration = ef.bag_contract((column(),))
    result = ef.compare(
        tmp_path / "absent.arrow",
        ef.ArrowInput(pa.table({"value": [1]})),
        contract=declaration.spec.contract,
        work_dir=tmp_path,
    )
    data = result.model_dump(mode="python")
    data["diagnostics"] = (
        ef.ComparisonDiagnostic(
            code="PRIVATE_PRODUCER_CODE_43234",
            message="password=PRIVATE_PRODUCER_MESSAGE_65445",
            exception_type="PRIVATE_PRODUCER_TYPE_94531",
        ),
    )
    poisoned = ef.ComparisonResult.model_validate(data)
    report = comparison_report(poisoned)
    assert report.state == "not_evaluable" and not report.complete
    assert all("PRIVATE_PRODUCER" not in rendered for rendered in views(report))


def test_selected_key_value_redaction_keeps_other_cell_values_visible(tmp_path):
    result = ef.diff(
        pa.table({"secret_id": ["PRIVATE_KEY_VALUE_43842"], "value": [11]}),
        pa.table({"secret_id": ["PRIVATE_KEY_VALUE_43842"], "value": [10]}),
        keys=["secret_id"],
        work_dir=tmp_path,
    )
    report = comparison_report(
        result,
        options=ReportOptions(include_values=True, redact_columns=("secret_id",)),
    )
    witness = report.examples[0]
    assert witness.key[0].disclosure == "redacted" and witness.key[0].value is None
    assert witness.candidate[0].value == ef.ComparisonValue(kind="integer", value="11")
    assert witness.reference[0].value == ef.ComparisonValue(kind="integer", value="10")
    assert all("PRIVATE_KEY_VALUE_43842" not in rendered for rendered in views(report))


def test_export_reproduction_inventory_covers_every_file_and_actual_bytes(tmp_path):
    result = ef.diff(
        pa.table({"id": [1, 2], "value": [11, 20]}),
        pa.table({"id": [1, 2], "value": [10, 20]}),
        keys=["id"],
        work_dir=tmp_path / "raw",
    )
    directory = tmp_path / "export"
    report = write_comparison_report(
        result,
        directory,
        evidence_root=root_for(result, tmp_path / "raw"),
        options=ReportOptions(
            mode="reproduction",
            include_values=True,
            include_metadata=True,
            require_exhaustive=True,
            max_examples=0,
        ),
    )
    assert report.state == "different" and report.complete
    assert report.evidence.reproduction == "exported_materialized_inputs"
    assert report.evidence.acceptance == "satisfied" and report.examples == ()
    manifest = json.loads((directory / "evidence-manifest.json").read_text())
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != directory / "evidence-manifest.json"
    }
    assert {item["path"] for item in manifest["files"]} == actual
    assert any(path.startswith("reproduction/") for path in actual)
    for item in manifest["files"]:
        payload = (directory / item["path"]).read_bytes()
        assert item["sha256"] == hashlib.sha256(payload).hexdigest()
        assert item["size_bytes"] == len(payload)
    assert manifest["report_evidence"] == report.evidence.model_dump(mode="json")


def test_damaged_source_blocks_reproduction_without_publishing_success(tmp_path):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path / "raw")
    assert result.left is not None
    snapshot = Path(url2pathname(urlsplit(result.left.data.uri).path))
    assert snapshot.is_relative_to(tmp_path)
    snapshot.write_bytes(b"not the recorded snapshot")
    destination = tmp_path / "export"
    with pytest.raises(ef.ArtifactIntegrityError):
        write_comparison_report(
            result,
            destination,
            evidence_root=root_for(result, tmp_path / "raw"),
            options=ReportOptions(mode="reproduction", include_values=True, include_metadata=True),
        )
    assert not (destination / "evidence-manifest.json").exists()
    assert not (destination / "report.json").exists()


def test_write_io_failure_never_publishes_success_receipt(tmp_path, monkeypatch):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path / "raw")
    destination = tmp_path / "failed-export"

    def fail_sync(descriptor):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(os, "fsync", fail_sync)
    with pytest.raises(OSError, match="synthetic fsync failure"):
        write_comparison_report(result, destination)
    assert not (destination / "evidence-manifest.json").exists()


def scoped_declaration(columns):
    base = ef.bag_contract(columns, reference="peer").spec.contract
    schema = base.output.schema_spec.model_copy(
        update={
            "keys": (
                ef.KeySpec(
                    name="tenant_key",
                    columns=("id",),
                    unique=True,
                    incomplete="reject",
                    scope=ef.ColumnKeyScope(columns=("tenant",)),
                ),
            )
        }
    )
    document = base.model_dump(mode="python")
    document["inputs"] = (ef.TableSpec(name="source", schema_spec=schema),)
    document["output"] = ef.TableSpec(name="result", schema_spec=schema)
    return ef.DiffContract.from_contract(ef.Contract.model_validate(document), reference="peer")


def string_column(name):
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.StringType(),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
    )


def test_scoped_key_labels_and_redaction_follow_scope_then_key_order(tmp_path):
    declaration = scoped_declaration((column("id"), string_column("tenant"), column("value")))
    result = ef.diff(
        pa.table({"id": [7], "tenant": ["PRIVATE_TENANT_95515"], "value": [11]}),
        pa.table({"id": [7], "tenant": ["PRIVATE_TENANT_95515"], "value": [10]}),
        contract=declaration,
        work_dir=tmp_path,
    )
    report = comparison_report(
        result,
        options=ReportOptions(
            include_values=True, include_metadata=True, redact_columns=("tenant",)
        ),
    )
    witness = report.examples[0]
    assert witness.key_columns == ("tenant", "id")
    assert witness.key[0].disclosure == "redacted" and witness.key[0].value is None
    assert witness.key[1].value == ef.ComparisonValue(kind="integer", value="7")
    assert all("PRIVATE_TENANT_95515" not in rendered for rendered in views(report))


def test_full_width_key_violation_does_not_mistake_key_order_for_schema_order(tmp_path):
    declaration = scoped_declaration((column("id"), string_column("tenant")))
    table = pa.table({"id": [7, 7], "tenant": ["PRIVATE_SCOPE_85541", "PRIVATE_SCOPE_85541"]})
    result = ef.diff(table, table, contract=declaration, work_dir=tmp_path)
    assert result.state == "different" and result.strategy == "multiset"
    report = comparison_report(
        result,
        options=ReportOptions(
            include_values=True, include_metadata=True, redact_columns=("tenant",)
        ),
    )
    assert report.examples and all(w.category == "contract" for w in report.examples)
    for witness in report.examples:
        assert witness.columns == ("tenant", "id")
        assert witness.candidate_count is None and witness.reference_count is None
        for values in (witness.candidate, witness.reference):
            if values:
                assert values[0].disclosure == "redacted" and values[0].value is None
                assert values[1].value == ef.ComparisonValue(kind="integer", value="7")
    assert all("PRIVATE_SCOPE_85541" not in rendered for rendered in views(report))


@pytest.mark.parametrize(
    "mutation",
    [
        "false_equivalent",
        "counts_final",
        "missing_count",
        "record_count",
        "example_count",
        "hidden_values",
        "hidden_metadata",
    ],
)
def test_detached_report_rejects_inconsistent_or_false_success_documents(tmp_path, mutation):
    result = ef.diff(
        pa.table({"id": [1], "value": [11]}),
        pa.table({"id": [1], "value": [10]}),
        keys=["id"],
        work_dir=tmp_path,
    )
    report = comparison_report(
        result, options=ReportOptions(include_values=True, include_metadata=True)
    )
    document = json.loads(report.model_dump_json())
    if mutation == "false_equivalent":
        document["state"] = "equivalent"
    elif mutation == "counts_final":
        document["evidence"]["counts_final"] = False
    elif mutation == "missing_count":
        document["counts"] = [c for c in document["counts"] if c["name"] != "matched_rows"]
    elif mutation == "record_count":
        document["evidence"]["available_records"] += 1
        document["evidence"]["display_complete"] = False
    elif mutation == "example_count":
        document["examples"] = []
    elif mutation == "hidden_values":
        document["options"]["include_values"] = False
    elif mutation == "hidden_metadata":
        document["options"]["include_metadata"] = False
    with pytest.raises(ValidationError):
        ComparisonReport.model_validate_json(json.dumps(document))


def test_equivalent_report_cannot_claim_full_match_using_three_unknown_counts(tmp_path):
    table = pa.table({"value": [1]})
    result = ef.diff(table, table, work_dir=tmp_path)
    document = json.loads(comparison_report(result).model_dump_json())
    for item in document["counts"]:
        if item["name"] in {"candidate_rows", "reference_rows", "matched_rows"}:
            item["value"] = None
            item["precision"] = "unknown"
    with pytest.raises(ValidationError):
        ComparisonReport.model_validate_json(json.dumps(document))


def test_tolerance_matching_preserves_excess_occurrences_without_row_pair_fiction(tmp_path):
    declaration = ef.bag_contract(
        (
            ef.ColumnSpec(
                name="value",
                logical_type=ef.FloatType(bits=64),
                nullable=True,
                null_policy=ef.NullPolicy(representations=("null",)),
                nan_policy=ef.NaNPolicy(handling="distinct"),
                numeric_policy=ef.NumericPolicy(
                    comparison="approximate",
                    unit="count",
                    tolerance=ef.Tolerance(
                        absolute="0.1", unit="count", justification="Declared sensor precision"
                    ),
                ),
            ),
        )
    )
    result = ef.diff(
        pa.table({"value": [1.0, 1.0, 5.0]}),
        pa.table({"value": [1.05, 5.05]}),
        contract=declaration,
        work_dir=tmp_path,
    )
    report = comparison_report(result, evidence_root=root_for(result, tmp_path))
    assert report.state == "different" and report.strategy == "matching" and report.complete
    count(report, "matched_rows", 2)
    count(report, "candidate_excess_occurrences", 1, unit="occurrences")
    count(report, "reference_excess_occurrences", 0, unit="occurrences")
    count(report, "modified_rows", None, "unknown")
    count(report, "added_rows", None, "unknown")
    count(report, "removed_rows", None, "unknown")


@pytest.mark.parametrize("failure", ["manifest_fsync", "manifest_link"])
def test_final_manifest_failure_leaves_neither_success_marker_nor_temporary(
    tmp_path, monkeypatch, failure
):
    result = ef.diff(pa.table({"value": [1]}), pa.table({"value": [2]}), work_dir=tmp_path / "raw")
    destination = tmp_path / "failed-publication"
    calls = []
    original_sync = os.fsync

    def fail_fourth_sync(descriptor):
        calls.append(descriptor)
        if len(calls) == 4:
            assert (destination / ".evidence-manifest.part").is_file()
            assert not (destination / "evidence-manifest.json").exists()
            raise OSError("synthetic final manifest fsync failure")
        return original_sync(descriptor)

    def fail_link(source, target, *args, **kwargs):
        assert Path(source) == destination / ".evidence-manifest.part"
        assert Path(target) == destination / "evidence-manifest.json"
        assert Path(source).is_file()
        assert not Path(target).exists()
        calls.append((source, target))
        raise OSError("synthetic final manifest link failure")

    if failure == "manifest_fsync":
        monkeypatch.setattr(os, "fsync", fail_fourth_sync)
    else:
        monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(OSError, match="synthetic final manifest"):
        write_comparison_report(result, destination)
    assert len(calls) == (4 if failure == "manifest_fsync" else 1)
    assert not (destination / "evidence-manifest.json").exists()
    assert not (destination / ".evidence-manifest.part").exists()
    assert not tuple(destination.glob("*.part"))
    assert {path.name for path in destination.iterdir()} == {
        "report.json",
        "report.html",
        "report.txt",
    }
