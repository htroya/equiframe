"""The eight synthetic product journeys have executable, independently checked gates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal

import pytest
from conftest import EXAMPLES

import equiframe as ef

SCRIPTS = {
    "A": "a_pandas_refactor.py",
    "B": "b_native_migration.py",
    "C": "c_retail_etl.py",
    "D": "d_financial_reconciliation.py",
    "E": "e_telemetry.py",
    "F": "f_data_science_preparation.py",
    "G": "g_external_snapshots.py",
    "H": "h_portable_ci.py",
}
# These are distinct behavior paths, not repeated platform runs counted as tests.
CASES = [
    (journey, case, 0 if case == "good" else 1 if case == "different" else code)
    for journey, failure, code in (
        ("A", "not_evaluable", 3),
        ("B", "not_evaluable", 3),
        ("C", "error", 2),
        ("D", "not_evaluable", 3),
        ("E", "not_evaluable", 3),
        ("F", "not_evaluable", 3),
        ("G", "error", 2),
        ("H", "not_evaluable", 3),
    )
    for case in ("good", "different", failure)
] + [
    ("A", "duplicate", 1),
    ("E", "null_nan", 1),
    ("E", "duplicate_loss", 1),
    ("F", "dropped_row", 1),
    ("F", "changed_id", 1),
    ("G", "schema_error", 2),
    ("H", "error", 2),
]


@pytest.fixture
def copied_journeys(tmp_path):
    copied = tmp_path / "consumer" / "journeys"
    shutil.copytree(EXAMPLES / "journeys", copied, ignore=shutil.ignore_patterns("__pycache__"))
    return copied


def read_comparisons(output):
    return [
        ef.read_comparison(path)
        for path in sorted((output / "private").glob("comparison-*/comparison.json"))
    ]


def check_reports(output):
    for parent in ("reports", "public_reports"):
        for report_path in (output / parent).rglob("report.json"):
            report = ef.read_comparison_report(report_path)
            assert report.evidence.values_withheld
            assert report.evidence.metadata_withheld
            assert not report.options.include_values
            assert not report.options.include_metadata
            folder = report_path.parent
            manifest = ef.ReportPublicationManifest.model_validate_json(
                (folder / "evidence-manifest.json").read_bytes()
            )
            assert manifest.publication_complete
            assert {item.path for item in manifest.files} == {
                "report.json",
                "report.html",
                "report.txt",
            }
            for item in manifest.files:
                raw = (folder / item.path).read_bytes()
                assert len(raw) == item.size_bytes
                assert hashlib.sha256(raw).hexdigest() == item.sha256
                assert b"SECRET_SYNTH" not in raw
                assert b"file://" not in raw
                assert str(output).encode() not in raw


@pytest.mark.parametrize("journey,scenario,expected_exit", CASES)
def test_copied_journey_acceptance(tmp_path, copied_journeys, journey, scenario, expected_exit):
    output = tmp_path / "evidence"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    response = subprocess.run(
        [
            sys.executable,
            str(copied_journeys / SCRIPTS[journey]),
            "--case",
            scenario,
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert response.returncode == expected_exit, response.stdout + response.stderr
    assert "Traceback" not in response.stderr
    summary = json.loads((output / "summary.json").read_text())
    assert summary["journey"] == journey and summary["synthetic"] is True
    assert summary["scenario"] == scenario
    assert summary["exit_code"] == expected_exit
    assert summary["accepted"] is (expected_exit == 0)
    environment = json.loads((output / "environment.json").read_text())
    assert environment["dependencies"]["equiframe"] == ef.__version__
    assert (
        environment["journey_scripts_sha256"][SCRIPTS[journey]]
        == hashlib.sha256((copied_journeys / SCRIPTS[journey]).read_bytes()).hexdigest()
    )
    check_reports(output)
    if journey in {"A", "D", "E", "F"}:
        comparisons = read_comparisons(output)
        assert len(comparisons) == 1
        result = comparisons[0]
        if expected_exit == 0:
            ef.assert_equivalent(result)
        else:
            error = (
                ef.EquivalenceDifferentError
                if expected_exit == 1
                else ef.EquivalenceNotEvaluableError
            )
            with pytest.raises(error):
                ef.assert_equivalent(result)
        with pytest.raises(TypeError):
            bool(result)
        if scenario == "not_evaluable":
            assert not result.complete and not result.counts.final
        if journey == "A" and scenario == "different":
            differences = list(ef.iter_differences(result.differences))
            assert len(differences) == 1
            assert differences[0].column == "total_cents"
            assert [value.value for value in differences[0].key] == ["002", "1"]
            assert differences[0].left[0].value == "301"
            assert differences[0].right[0].value == "300"
        if journey == "D":
            assert summary["per_currency_totals_match"] is True
            if scenario == "different":
                differences = list(ef.iter_differences(result.differences))
                assert len(differences) == 2
                assert {difference.column for difference in differences} == {"amount"}
                assert {difference.key[1].value for difference in differences} == {"USD"}
        if journey == "E":
            assert all(not check["supported"] for check in summary["migration_preflight"])
            if scenario == "good":
                assert ef.read_table(result.right.data)["at"].type.unit == "ns"
                assert ef.read_table(result.right.data).num_rows == 4
        if journey == "F":
            assert summary["anomaly_detection"] == "not_requested"
            if scenario == "good":
                assert ef.read_table(result.left.data).to_pylist()[-1] == {
                    "sample_id": "0004",
                    "duration_s": 1000.0,
                    "events": 99,
                }
    if journey == "B":
        assert summary["source_resolutions"] == 1
        assert summary["same_input_sha256"] is True
        assert summary["native_engines"] == ["pandas", "duckdb"]
        assert summary["execution_states"] == ["completed", "completed"]
        migration = ef.read_migration(next((output / "private").glob("*/migration.json")))
        assert sorted(
            ef.read_table(migration.expected).to_pylist(), key=lambda row: row["currency"]
        ) == [
            {"currency": "EUR", "total": None},
            {"currency": "USD", "total": Decimal("3.30")},
        ]
        if scenario == "different":
            assert summary["state"] == "equivalent"
            assert summary["verification"] == "divergent"
            assert summary["comparisons"]["peers"]["accepted"] is True
            assert summary["comparisons"]["pandas-expected"]["accepted"] is False
            assert summary["comparisons"]["duckdb-expected"]["accepted"] is False
    if journey == "C":
        assert summary["all_source_rows_valid"] is False
        assert summary["published"] is (scenario == "good")
        assert (output / "published" / "current.json").exists() is (scenario == "good")
        for ingestion in summary["ingestion"].values():
            assert ingestion["quarantined_records"] == 1
            assert ingestion["diagnostics"][0]["code"] == "invalid_decimal"
            assert ingestion["output_available"] is (scenario != "error")
        if scenario == "different":
            check = summary["verifications"]["csv_net"]
            assert check["technical"] == check["agreement"] == "passed"
            assert check["expected"] == ["failed", "failed"]
        if scenario == "good":
            import pyarrow.parquet as pq

            tables = [pq.read_table(path) for path in (output / "published").rglob("*.parquet")]
            assert len(tables) == 4
            totals = [table for table in tables if "total" in table.column_names]
            assert len(totals) == 2
            for table in totals:
                assert sorted(table.to_pylist(), key=lambda row: row["currency"]) == [
                    {"currency": "EUR", "total": Decimal("9.00"), "rows": 1},
                    {"currency": "USD", "total": Decimal("14.00"), "rows": 2},
                ]
    if journey == "G":
        assert summary["manifest_requests"] == summary["download_count"] == 1
        assert summary["provenance_preserved"] is True
        assert summary["output_available"] is (expected_exit != 2)
        if expected_exit == 2:
            assert summary["problem_code"] == "artifact_integrity_error"
    if journey == "H":
        assert summary["original_paths_available"] is False
        assert summary["integrity"] == ("rejected" if scenario == "error" else "passed")
        if scenario != "error":
            assert ef.inspect_bundle(output / "private" / "imported")["integrity"] == "passed"
            assert summary["independent_review"] == "not_requested"


def test_example_scripts_never_overwrite_existing_evidence(tmp_path, copied_journeys):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("retained evidence")
    response = subprocess.run(
        [sys.executable, str(copied_journeys / SCRIPTS["A"]), "--output", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert response.returncode == 2
    assert sentinel.read_text() == "retained evidence"
    assert set(output.iterdir()) == {sentinel}
    assert "Traceback" not in response.stderr


def test_pandas_recipe_can_be_a_real_pytest_assertion(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES / "journeys"))
    spec = importlib.util.spec_from_file_location("journey_a", EXAMPLES / "journeys" / SCRIPTS["A"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate, expected = module.materialize("different")
    result = ef.diff(candidate, expected, contract=module.declaration(), work_dir=tmp_path)
    with pytest.raises(ef.EquivalenceDifferentError):
        ef.assert_equivalent(result)
    # Invalid expected output is unavailable judgment, even if values agree.
    duplicated = expected.iloc[[0, 0, 1, 2]].reset_index(drop=True)
    invalid_expected = ef.diff(
        duplicated, duplicated, contract=module.declaration(), work_dir=tmp_path
    )
    with pytest.raises(ef.EquivalenceNotEvaluableError):
        ef.assert_equivalent(invalid_expected)


def test_journey_dependency_lock_reuses_the_existing_hash_pinned_route():
    assert (EXAMPLES / "journeys" / "requirements.lock").read_bytes() == (
        EXAMPLES / "first_use" / "requirements.lock"
    ).read_bytes()


def test_journey_imports_do_not_eagerly_load_optional_engines(tmp_path, copied_journeys):
    code = """
import importlib, sys
sys.path.insert(0, sys.argv[1])
for module in sys.argv[2:]:
    importlib.import_module(module)
optional = ('pandas','polars','duckdb','pyarrow','numpy','sklearn')
assert not any(name in sys.modules for name in optional)
"""
    response = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(copied_journeys),
            *[name.removesuffix(".py") for name in SCRIPTS.values()],
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert response.returncode == 0, response.stdout + response.stderr


@pytest.mark.parametrize("journey,dependency", [("A", "pandas"), ("D", "pyarrow")])
def test_missing_optional_dependency_is_explicit_setup_failure(
    tmp_path, copied_journeys, journey, dependency
):
    code = """
import builtins, importlib, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
module = importlib.import_module(sys.argv[2])
real_import = builtins.__import__
dependency = sys.argv[3]
def controlled_import(name, *args, **kwargs):
    if name == dependency:
        raise ModuleNotFoundError('private dependency path must not leak')
    return real_import(name, *args, **kwargs)
builtins.__import__ = controlled_import
sys.argv = ['journey', '--output', sys.argv[4]]
raise SystemExit(module.cli(module.run, 'synthetic dependency failure'))
"""
    output = tmp_path / "output"
    response = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(copied_journeys),
            SCRIPTS[journey].removesuffix(".py"),
            dependency,
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert response.returncode == 2
    assert "Optional dependency missing" in response.stderr
    assert "Traceback" not in response.stderr
    assert "private dependency path" not in response.stderr
    assert not (output / "summary.json").exists()
