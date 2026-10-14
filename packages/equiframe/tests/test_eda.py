"""Independent small expected values, source integrity and outcome separation."""

import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import equiframe as ef
from equiframe.eda import (
    Conversion,
    EdaConfig,
    KeyRule,
    NumericRule,
    Resources,
    Source,
    analyze,
    analyze_migration,
    read_result,
)
from equiframe.eda.cli import app


def source(tmp_path, table, suffix="parquet"):
    directory = tmp_path / "input"
    directory.mkdir(exist_ok=True)
    path = directory / ("data." + suffix)
    if suffix == "parquet":
        pq.write_table(table, path)
    else:
        with pa.ipc.new_file(path, table.schema) as writer:
            writer.write_table(table)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return Source(path=str(path), format=suffix, snapshot_id="synthetic", expected_sha256=digest)


def run(tmp_path, table, config=None, name="run", suffix="parquet", **kwargs):
    ref = source(tmp_path, table, suffix)
    result = analyze(ref, config=config, output=tmp_path / name, **kwargs)
    assert hashlib.sha256(Path(ref.path).read_bytes()).hexdigest() == ref.expected_sha256
    assert read_result(tmp_path / name) == result
    return result


def test_timezone_is_initialized_after_connect_without_extension_downloads(tmp_path, monkeypatch):
    import duckdb

    connect = duckdb.connect
    configurations = []

    def observe(*args, **kwargs):
        configurations.append(kwargs["config"])
        assert "TimeZone" not in kwargs["config"]
        assert kwargs["config"]["autoinstall_known_extensions"] is False
        return connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", observe)
    result = run(tmp_path, pa.table({"id": [1], "date": ["2025-01-01"]}))
    assert result.state == "completed"
    assert len(configurations) == 1


def test_unavailable_timezone_fails_and_closes_connection(tmp_path, monkeypatch):
    import duckdb

    class FailedConnection:
        closed = False

        def execute(self, statement):
            assert statement == "SET TimeZone='UTC'"
            raise RuntimeError("timezone initialization unavailable")

        def close(self):
            self.closed = True

    connection = FailedConnection()
    monkeypatch.setattr(duckdb, "connect", lambda *args, **kwargs: connection)
    result = run(tmp_path, pa.table({"id": [1]}))
    assert result.state == "failed"
    assert connection.closed


def test_raw_distinctions_and_identifiers(tmp_path):
    table = pa.table(
        {"id": ["", "0", None, "NaN", "001"], "n": [None, float("nan"), 0.0, float("inf"), 1.0]}
    )
    result = run(tmp_path, table, EdaConfig(identifiers=("id",)))
    assert result.state == "completed" and result.rows == 5
    text, num = result.columns
    assert (text.nulls, text.empty, text.nan, text.zero, text.valid, text.distinct_present) == (
        1,
        1,
        0,
        0,
        3,
        4,
    )
    assert (num.nulls, num.nan, num.empty, num.zero, num.nonfinite, num.valid) == (1, 1, 0, 1, 2, 2)
    assert num.nan_rate == 0.2 and text.empty_rate == 0.2
    assert "001" in [f["value"] for f in text.frequencies]
    with pytest.raises(TypeError):
        bool(result)


def test_empty_and_all_absent(tmp_path):
    empty = run(
        tmp_path,
        pa.table({"a": pa.array([], type=pa.float64())}),
        EdaConfig(numeric=(NumericRule(column="a"),)),
    )
    assert empty.rows == 0 and empty.columns[0].null_rate is None
    assert empty.numeric[0]["groups"][0]["reason"] == "no_finite_values"
    assert empty.duplicates[0].excess_rate is None
    absent = run(
        tmp_path,
        pa.table({"a": pa.array([None, None], type=pa.float64())}),
        EdaConfig(numeric=(NumericRule(column="a"),)),
        name="absent",
    )
    assert absent.columns[0].nulls == 2 and absent.columns[0].valid == 0
    assert absent.numeric[0]["groups"][0]["valid"] == 0


@pytest.mark.parametrize(
    "policy,denominator,incomplete", [("exclude", 3, 2), ("include", 5, 2), ("reject", 3, 2)]
)
def test_incomplete_keys_and_repetition_without_deletion(tmp_path, policy, denominator, incomplete):
    table = pa.table({"id": ["001", "001", None, "", "002"], "v": [1, 1, 2, 3, 4]})
    result = run(
        tmp_path,
        table,
        EdaConfig(keys=(KeyRule(columns=("id",), incomplete=policy, require_unique=True),)),
    )
    full, key = result.duplicates
    assert (full.repeated_groups, full.involved_rows, full.excess_rows) == (1, 2, 1)
    assert (
        key.denominator,
        key.incomplete_rows,
        key.repeated_groups,
        key.involved_rows,
        key.excess_rows,
    ) == (denominator, incomplete, 1, 2, 1)
    assert result.rows == 5 and any(f.code == "key_duplicates" for f in result.findings)
    assert any(f.code == "incomplete_key" for f in result.findings) == (policy == "reject")


def test_legitimate_duplicate_key_is_observation(tmp_path):
    result = run(
        tmp_path,
        pa.table({"ocid": ["x", "x"], "revision": [1, 2]}),
        EdaConfig(keys=(KeyRule(columns=("ocid",), require_unique=False),)),
    )
    assert result.duplicates[0].repeated_groups == 0
    assert result.duplicates[1].excess_rows == 1
    assert next(f for f in result.findings if f.code == "key_duplicates").severity == "observation"


def test_duplicate_examples_preserve_a_source_column_named_rows(tmp_path):
    result = run(
        tmp_path,
        pa.table({"rows": ["invoice-001", "invoice-001"], "values": [4, 4]}),
        EdaConfig(keys=(KeyRule(columns=("rows",)),)),
    )
    full, key = result.duplicates
    assert full.examples == ({"values": {"rows": "invoice-001", "values": 4}, "rows": 2},)
    assert key.examples == ({"values": {"rows": "invoice-001"}, "rows": 2},)


@pytest.mark.parametrize("suffix", ["parquet", "arrow"])
def test_raw_nanosecond_times_do_not_invent_duplicate_microsecond_values(tmp_path, suffix):
    result = run(tmp_path, pa.table({"t": pa.array([1, 2], type=pa.time64("ns"))}), suffix=suffix)
    assert result.state == "not_evaluable"
    assert result.columns == () and result.duplicates == ()


def test_observed_years_ignore_an_original_column_named_y(tmp_path):
    result = run(
        tmp_path,
        pa.table({"date": ["2025-01-01", "2026-01-01"], "y": ["a", "b"]}),
        EdaConfig(conversions=(Conversion(column="date", target="derived_date", kind="date"),)),
    )
    assert result.state == "completed"
    assert result.conversions[0]["observed_dates"]["years"] == [
        {"year": 2025, "rows": 1},
        {"year": 2026, "rows": 1},
    ]


def test_exact_decimal_currency_and_failed_conversion(tmp_path):
    table = pa.table(
        {
            "id": ["001", "002", "003", "004", "005", "006", "007"],
            "amount": ["0.10", "0.20", "0.30", "100.00", "oops", "", "0.123"],
            "currency": ["USD", "USD", "USD", "EUR", "USD", "USD", "USD"],
        }
    )
    config = EdaConfig(
        identifiers=("id",),
        conversions=(
            Conversion(column="amount", target="money", kind="decimal", scale=2, empty="missing"),
        ),
        numeric=(
            NumericRule(
                column="money",
                groups=("currency",),
                monetary=True,
                currency_column="currency",
                outliers="none",
            ),
        ),
    )
    result = run(tmp_path, table, config)
    assert result.conversions[0]["invalid"] == 2 and result.conversions[0]["missing"] == 1
    usd = next(g for g in result.numeric[0]["groups"] if g["group"]["currency"] == "USD")
    assert usd["valid"] == 3 and usd["sum"] == "0.60"
    assert usd["median"] == "0.20" and usd["mean_exact_rational"] == {
        "numerator": "1",
        "denominator": "5",
    }
    eur = next(g for g in result.numeric[0]["groups"] if g["group"]["currency"] == "EUR")
    assert eur["sum"] == "100.00" and sum(h["count"] for h in usd["histogram"]) == 3
    typed = pq.read_table(tmp_path / "run/typed.parquet")
    assert typed["amount"].to_pylist() == table["amount"].to_pylist()
    assert typed["id"].to_pylist()[0] == "001"
    assert typed["money"].to_pylist() == [
        Decimal("0.10"),
        Decimal("0.20"),
        Decimal("0.30"),
        Decimal("100.00"),
        None,
        None,
        None,
    ]


def test_dates_are_observed_not_assumed_cohort(tmp_path):
    table = pa.table(
        {
            "date": [
                "2025-02-03T10:00:00Z",
                "2026-01-01T01:00:00+01:00",
                "",
                "2025-99-99",
                "2025-01-01T00:00:00",
            ]
        }
    )
    result = run(
        tmp_path,
        table,
        EdaConfig(
            conversions=(
                Conversion(column="date", target="instant", kind="timestamp", empty="missing"),
            )
        ),
    )
    dates = result.conversions[0]
    assert dates["invalid"] == 2 and dates["missing"] == 1
    assert dates["observed_dates"]["years"] == [
        {"year": 2025, "rows": 1},
        {"year": 2026, "rows": 1},
    ]
    assert dates["observed_dates"]["cohort_inferred"] is False


@pytest.mark.parametrize("method", ["iqr", "mad"])
def test_outliers_are_candidates_not_errors(tmp_path, method):
    config = EdaConfig(numeric=(NumericRule(column="n", outliers=method, multiplier=1.5),))
    result = run(tmp_path, pa.table({"n": [1, 2, 3, 4, 5, 6, 7, 100]}), config)
    group = result.numeric[0]["groups"][0]
    assert group["quantiles"] == {"0.25": 2, "0.5": 4, "0.75": 6}
    assert group["outliers"]["count"] == 1
    assert group["outliers"]["examples"] == [{"__ef_eda_row": 7, "n": 100}]
    assert (
        next(f for f in result.findings if f.code == "outlier_candidate").severity == "observation"
    )
    assert result.rows == 8


@pytest.mark.parametrize(
    "values,reason", [([1, 2], "insufficient_support"), ([7] * 8, "zero_dispersion")]
)
@pytest.mark.parametrize("method", ["iqr", "mad"])
def test_unevaluable_dispersion_is_not_zero_alerts(tmp_path, values, reason, method):
    result = run(
        tmp_path,
        pa.table({"n": values}),
        EdaConfig(numeric=(NumericRule(column="n", outliers=method),)),
    )
    outlier = result.numeric[0]["groups"][0]["outliers"]
    assert (
        outlier["state"] == "not_evaluable"
        and outlier["reason"] == reason
        and outlier["count"] is None
    )


def test_nonfinite_numeric_excluded_and_missing_currency_unavailable(tmp_path):
    result = run(
        tmp_path,
        pa.table({"n": [float("nan"), float("inf"), None, 2.0, 3.0]}),
        EdaConfig(numeric=(NumericRule(column="n"),)),
    )
    group = result.numeric[0]["groups"][0]
    assert (group["total"], group["valid"], group["missing"], group["nonfinite"]) == (5, 2, 1, 2)
    missing = run(
        tmp_path,
        pa.table({"n": pa.array([Decimal("1.00"), Decimal("2.00")]), "currency": ["", ""]}),
        EdaConfig(
            numeric=(
                NumericRule(
                    column="n", groups=("currency",), monetary=True, currency_column="currency"
                ),
            )
        ),
        name="missing_currency",
    )
    group = missing.numeric[0]["groups"][0]
    assert (
        group["state"] == "not_evaluable"
        and group["reason"] == "missing_currency"
        and "sum" not in group
    )


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"max_rows": 0}, "row_budget_exhausted"),
        ({"max_input_bytes": 1}, "input_bytes_budget_exhausted"),
        ({"timeout_seconds": 0.000001}, "timeout_budget_exhausted"),
        ({"max_columns": 1}, "column_budget_exhausted"),
    ],
)
def test_exhausted_budgets_are_explicit(tmp_path, changes, reason):
    result = run(
        tmp_path,
        pa.table({"n": [1, 2], "k": ["a", "b"]}),
        EdaConfig(resources=Resources(**changes)),
    )
    assert result.state == "not_evaluable" and result.reason == reason
    assert result.rows is None or result.rows == 2


def test_group_budget_does_not_silently_drop_groups(tmp_path):
    result = run(
        tmp_path,
        pa.table({"n": [1, 2], "g": ["a", "b"]}),
        EdaConfig(
            resources=Resources(max_groups=1), numeric=(NumericRule(column="n", groups=("g",)),)
        ),
    )
    assert result.numeric[0]["state"] == "not_evaluable" and result.numeric[0]["groups_total"] == 2


def test_cancelled_and_failed_remain_distinct(tmp_path):
    cancelled = run(tmp_path, pa.table({"n": [1]}), cancellation=lambda: True)
    assert cancelled.state == "cancelled" and cancelled.rows is None
    failed = run(
        tmp_path,
        pa.table({"n": [1]}),
        EdaConfig(numeric=(NumericRule(column="unknown"),)),
        name="failed",
    )
    assert failed.state == "failed" and failed.reason == "analysis_failed"


@pytest.mark.parametrize("suffix", ["parquet", "arrow"])
def test_api_cli_and_portable_report_agree(tmp_path, suffix):
    table = pa.table({"id": ["001", "002"], "n": [1, 3]})
    ref = source(tmp_path, table, suffix)
    config = EdaConfig(charts=True, numeric=(NumericRule(column="n", outliers="none"),))
    cfg = tmp_path / "config.json"
    cfg.write_text(config.model_dump_json(), encoding="utf8")
    direct = analyze(ref, config=config, output=tmp_path / "api")
    cli = CliRunner().invoke(
        app,
        [
            "run",
            ref.path,
            "--output",
            str(tmp_path / "cli"),
            "--format",
            suffix,
            "--snapshot-id",
            ref.snapshot_id,
            "--expected-sha256",
            ref.expected_sha256,
            "--config",
            str(cfg),
        ],
    )
    assert cli.exit_code == 0, cli.output
    other = read_result(tmp_path / "cli")
    for field in (
        "rows",
        "columns",
        "duplicates",
        "numeric",
        "findings",
        "state",
        "config_sha256",
        "source_sha256",
    ):
        assert getattr(direct, field) == getattr(other, field)
    report = (tmp_path / "api/report.html").read_text(encoding="utf8")
    assert '<script src="https://' not in report and "eda-chart-0" in report
    assert "not population quartiles" in report
    assert CliRunner().invoke(app, ["inspect", str(tmp_path / "cli")]).exit_code == 0


def test_csv_empty_and_nan_text_are_not_null(tmp_path):
    directory = tmp_path / "input"
    directory.mkdir()
    path = directory / "data.csv"
    path.write_text("id,n\n001,\n002,NaN\n003,0\n", encoding="utf8")
    result = analyze(
        Source(path=str(path), format="csv", snapshot_id="synthetic"), output=tmp_path / "csv"
    )
    assert result.state == "completed"
    assert (
        result.columns[1].empty == 1 and result.columns[1].nulls == 0 and result.columns[1].nan == 0
    )
    assert result.columns[1].zero == 0
    assert read_result(tmp_path / "csv") == result


def test_runs_are_exclusive_and_inventory_is_closed(tmp_path):
    ref = source(tmp_path, pa.table({"n": [1]}))
    result = analyze(ref, output=tmp_path / "result")
    with pytest.raises(FileExistsError):
        analyze(ref, output=tmp_path / "result")
    (tmp_path / "result/extra.txt").write_text("extra")
    with pytest.raises(ValueError, match="not closed"):
        read_result(tmp_path / "result")
    assert result.state == "completed"


def test_corrupted_report_and_snapshot_rejected(tmp_path):
    run(tmp_path, pa.table({"n": [1]}))
    with (tmp_path / "run/report.html").open("a") as stream:
        stream.write("modified")
    with pytest.raises(ValueError, match="integrity"):
        read_result(tmp_path / "run")


def test_identifiers_and_money_require_explicit_semantics():
    with pytest.raises(ValidationError):
        EdaConfig(
            identifiers=("id",), conversions=(Conversion(column="id", target="x", kind="integer"),)
        )
    with pytest.raises(ValidationError):
        NumericRule(column="n", monetary=True)
    with pytest.raises(ValidationError):
        Source(path="data.parquet", snapshot_id="x", manifest_path="manifest.json")
    with pytest.raises(ValidationError):
        EdaConfig(schema_version="2.0")


def test_delivery_root_and_wrong_identity_are_protected(tmp_path):
    ref = source(tmp_path, pa.table({"n": [1]}))
    root = Path(ref.path).parent
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "equiframe.sercop-public-dataset-delivery.v1",
                "files": [
                    {
                        "file": "data.parquet",
                        "bytes": Path(ref.path).stat().st_size,
                        "sha256": ref.expected_sha256,
                    }
                ],
            }
        )
    )
    trusted = ref.model_copy(
        update={
            "manifest_path": str(manifest),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
    )
    with pytest.raises(ValueError):
        analyze(trusted, output=root / "forbidden")
    result = analyze(
        trusted.model_copy(update={"expected_sha256": "0" * 64}), output=tmp_path / "invalid"
    )
    assert result.state == "failed" and result.rows is None


def test_equal_statistics_do_not_replace_complete_comparison(tmp_path):
    left = pa.table({"id": ["a", "b"], "n": [1, 3]})
    right = pa.table({"id": ["a", "b"], "n": [3, 1]})
    config = EdaConfig(numeric=(NumericRule(column="n", outliers="none"),))
    a = run(tmp_path, left, config, name="a")
    b = run(tmp_path, right, config, name="b")
    x, y = a.numeric[0]["groups"][0], b.numeric[0]["groups"][0]
    assert x["sum"] == y["sum"] == 4 and x["quantiles"] == y["quantiles"]
    comparison = ef.diff(left, right, keys=["id"], work_dir=tmp_path / "comparison")
    assert comparison.state == "different"
    with pytest.raises(ef.EquivalenceAssertionError):
        ef.assert_equivalent(comparison)


def test_two_motors_same_error_do_not_gain_correctness(tmp_path):
    wrong = pa.table({"id": ["a", "b"], "n": [0, 0]})
    expected = pa.table({"id": ["a", "b"], "n": [1, 3]})
    eda = run(tmp_path, wrong)
    assert eda.state == "completed" and not eda.findings
    peer = ef.diff(wrong, wrong, keys=["id"], reference="peer", work_dir=tmp_path / "peer")
    actual = ef.diff(wrong, expected, keys=["id"], work_dir=tmp_path / "expected")
    assert peer.state == "equivalent" and actual.state == "different"


def test_optional_imports_and_existing_migration_without_eda(tmp_path):
    program = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'duckdb', 'plotly'}:
            raise ImportError('EDA dependencies deliberately unavailable')
sys.meta_path.insert(0, Block())
import equiframe as ef
from equiframe.eda import EdaConfig
import runpy
assert not {'duckdb','plotly','sklearn','numpy','polars','pandas','pyarrow'} & set(sys.modules)
example = sys.argv[2]
sys.argv=['outcome_gates.py','--work-dir',sys.argv[1]]
runpy.run_path(example, run_name='__main__')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-O",
            "-c",
            program,
            str(tmp_path / "gates"),
            str(Path(__file__).parents[1] / "examples/integrations/outcome_gates.py"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_verified_historical_migration_unchanged_after_eda(tmp_path):
    # A public verified import relocalizes frozen original bytes to this private test copy.
    fixture = Path(__file__).parent / "fixtures/versioned/baseline/migration-bundle/bundle.json"
    ef.import_bundle(fixture.parent, tmp_path / "original")
    root = tmp_path / "original"
    before = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }
    original = ef.inspect_bundle(root)
    result = analyze_migration(root, output=tmp_path / "eda")
    assert result.state == "completed"
    assert result.evidence_links[0]["state"] == original["outcome"]["state"]
    assert ef.inspect_bundle(root) == original
    assert before == {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }
    assert read_result(tmp_path / "eda") == result


@pytest.mark.parametrize("dtype", [pa.uint8(), pa.uint16()])
def test_unsigned_small_numbers_are_numeric(tmp_path, dtype):
    result = run(
        tmp_path,
        pa.table({"n": pa.array([0, 1], type=dtype)}),
        EdaConfig(numeric=(NumericRule(column="n", outliers="none"),)),
    )
    assert result.state == "completed" and result.columns[0].zero == 1
    assert result.numeric[0]["groups"][0]["sum"] == 1


@pytest.mark.parametrize("suffix", ["parquet", "arrow"])
def test_nonfaithful_raw_temporal_transport_is_explicit(tmp_path, suffix):
    table = pa.table({"instant": pa.array([0, 1, 1000], type=pa.timestamp("ns"))})
    result = run(tmp_path, table, suffix=suffix)
    assert result.state == "not_evaluable" and result.rows is None
    assert result.reason == "analysis_unavailable"


@pytest.mark.parametrize("suffix", ["parquet", "arrow"])
def test_original_name_collisions_rejected_before_duckdb_rewrite(tmp_path, suffix):
    result = run(tmp_path, pa.table({"Amount": ["1"], "amount": ["2"]}), suffix=suffix)
    assert result.state == "failed" and result.reason == "analysis_failed"


def test_derived_name_and_identifier_case_collisions_rejected(tmp_path):
    result = run(
        tmp_path,
        pa.table({"Amount": ["1.00"]}),
        EdaConfig(conversions=(Conversion(column="Amount", target="amount", kind="decimal"),)),
    )
    assert result.state == "failed" and result.reason == "analysis_failed"
    with pytest.raises(ValidationError):
        EdaConfig(
            identifiers=("ID",), conversions=(Conversion(column="id", target="n", kind="integer"),)
        )


def test_exact_subnormal_decimal_bounds_never_use_float(tmp_path):
    table = pa.table(
        {
            "money": pa.array(
                [Decimal(f"{i}E-38") for i in [1, 2, 3, 4, 5, 6, 7, 100]],
                type=pa.decimal128(38, 38),
            ),
            "currency": ["USD"] * 8,
        }
    )
    result = run(
        tmp_path,
        table,
        EdaConfig(
            numeric=(
                NumericRule(
                    column="money", monetary=True, groups=("currency",), currency_column="currency"
                ),
            )
        ),
    )
    group = result.numeric[0]["groups"][0]
    assert result.state == "completed" and group["outliers"]["count"] == 1
    assert Decimal(group["sum"]) == Decimal("128E-38")
    assert Decimal(group["median"]) == Decimal("4E-38")


def test_nonrepresentable_threshold_is_unavailable(tmp_path):
    values = [1, 1, 2, 2, 2, 2, 2, 3]
    table = pa.table(
        {"n": pa.array([Decimal(f"{i}E-38") for i in values], type=pa.decimal128(38, 38))}
    )
    result = run(tmp_path, table, EdaConfig(numeric=(NumericRule(column="n", multiplier=0.5),)))
    outlier = result.numeric[0]["groups"][0]["outliers"]
    assert result.state == "not_evaluable" and outlier["reason"] == "unrepresentable_decimal_bounds"
    assert outlier["count"] is None


def test_nested_manifest_cannot_escape_inventory_check(tmp_path):
    run(tmp_path, pa.table({"n": [1]}))
    (tmp_path / "run/extra").mkdir()
    (tmp_path / "run/extra/manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="not closed"):
        read_result(tmp_path / "run")


def test_report_budget_is_explicit_with_preserved_statistics(tmp_path):
    result = run(
        tmp_path,
        pa.table({"n": [1, 2]}),
        EdaConfig(charts=True, resources=Resources(max_report_bytes=100)),
    )
    assert result.state == "not_evaluable" and result.reason == "report_bytes_budget_exhausted"
    assert result.rows == 2 and result.chart_state == "not_evaluable"


def test_eda_namespace_inventory_is_explicit():
    import inspect

    from pydantic import BaseModel

    import equiframe.eda as eda
    from equiframe.eda import _inventory

    inv = _inventory.INVENTORY
    assert tuple(eda.__all__) == inv["public_names"]
    assert {
        n: str(inspect.signature(getattr(eda, n)))
        for n in eda.__all__
        if inspect.isfunction(getattr(eda, n))
    } == inv["signatures"]
    for name, expected in inv["model_shapes"].items():
        cls = getattr(eda, name)
        assert issubclass(cls, BaseModel)
        actual = hashlib.sha256(
            json.dumps(
                cls.model_json_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        assert actual == expected


def test_linked_migration_byte_change_never_leaves_completed_eda(tmp_path, monkeypatch):
    from test_migration import run as migrate_synthetic

    from equiframe.eda._backend import Backend

    migrate_synthetic(tmp_path / "native")
    root = tmp_path / "native"
    document = next(root.rglob("migration.json"))
    initial = document.read_bytes()
    original_convert = Backend.convert

    def concurrent_edit(self):
        document.write_bytes(initial + b"\n")  # Separate actor, semantically equal JSON.
        return original_convert(self)

    monkeypatch.setattr(Backend, "convert", concurrent_edit)
    result = analyze_migration(document.parent, output=tmp_path / "eda")
    assert result.state == "failed" and result.reason == "analysis_failed"
    assert document.read_bytes() == initial + b"\n"  # EDA did not rewrite other actor's edit.
    assert read_result(tmp_path / "eda") == result


def test_real_native_engines_same_error_still_fail_independent_expected(tmp_path):
    from test_migration import run as native_migrate
    from test_migration import spec as native_spec
    from test_migration import table as native_input

    from equiframe.eda import analyze_artifact

    original = native_spec(source="pandas", target="polars")
    wrong = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="project",
                source="scan",
                columns=(
                    ef.NamedExpression(
                        name="id",
                        expression=ef.LiteralExpression(
                            logical_type=ef.IntegerType(bits=64, signed=True),
                            value=ef.IntegerValue(value=99),
                            unit="identifier",
                        ),
                    ),
                    ef.NamedExpression(name="value", expression=ef.Column(name="value")),
                ),
            ),
        ),
        output="project",
    )
    migration = native_migrate(
        tmp_path / "migration",
        document=original.model_copy(update={"ir": wrong}),
        expected=ef.ArrowInput(native_input()),
    )
    assert migration.source.execution.plan.engine == "pandas"
    assert migration.target.execution.plan.engine == "polars"
    assert migration.state == "equivalent" and migration.verification == "divergent"
    for side in ("source", "target"):
        execution = getattr(migration, side).execution
        diagnostic = analyze_artifact(execution.output, output=tmp_path / ("eda-" + side))
        assert diagnostic.state == "completed" and not diagnostic.findings
    with pytest.raises(ef.EquivalenceAssertionError):
        ef.assert_equivalent(migration.verification_source)
