"""Hostile SQL names remain identifiers and hostile HTML remains text."""

import hashlib
import html
import importlib.util
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from equiframe.eda import EdaConfig, NumericRule, Source, analyze


@pytest.mark.parametrize("format", ["csv", "parquet"])
def test_eda_does_not_execute_sql_or_html_from_source(tmp_path, format):
    name = 'amount"; DROP TABLE raw; --'
    text = '<img src=x onerror="window.__equiframeProbe=1">'
    inputs = tmp_path / "input"
    inputs.mkdir()
    path = inputs / ("data'with_quote." + format)
    if format == "parquet":
        pq.write_table(pa.table({name: [10, 20], text: [text, "ok"]}), path)
    else:
        import csv

        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow([name, text])
            writer.writerow([10, text])
            writer.writerow([20, "ok"])
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    config = (
        EdaConfig(numeric=(NumericRule(column=name, outliers="none"),))
        if format == "parquet"
        else EdaConfig()
    )
    result = analyze(
        Source(path=str(path), format=format, snapshot_id="synthetic", expected_sha256=before),
        config=config,
        output=tmp_path / "report",
    )
    assert result.state == "completed"
    assert result.rows == 2
    assert result.columns[0].name == name
    report = (tmp_path / "report/report.html").read_text("utf-8")
    assert text not in report
    assert html.escape(text) in report
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.skipif(
    importlib.util.find_spec("plotly") is None, reason="Requires the eda-charts profile"
)
def test_plotly_labels_are_encoded(tmp_path):
    text = "<script>window.__equiframeProbe=1</script>"
    inputs = tmp_path / "input"
    inputs.mkdir()
    path = inputs / "table.parquet"
    pq.write_table(pa.table({"category": [text, "safe"]}), path)
    result = analyze(
        Source(path=str(path), format="parquet", snapshot_id="synthetic"),
        config=EdaConfig(charts=True),
        output=tmp_path / "report",
    )
    assert result.chart_state == "completed"
    report = (tmp_path / "report/report.html").read_text("utf-8")
    assert text not in report


def test_fixture_validation_survives_python_optimization():
    program = """
from equiframe_benchmark.fixtures import assert_expected
try:
    assert_expected([{"value":1}], [{"value":2}])
except AssertionError:
    print("EXPECTED_REJECTION")
else:
    raise RuntimeError("Incorrect fixture was accepted under optimization")
"""
    if importlib.util.find_spec("equiframe_benchmark") is None:
        pytest.skip("Requires the companion benchmark")
    result = subprocess.run(
        [sys.executable, "-I", "-O", "-c", program], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "EXPECTED_REJECTION"
