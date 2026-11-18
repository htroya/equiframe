"""Failures must not publish external exception values or break cancellation."""

import hashlib
import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from equiframe import _error_reporting
from equiframe.eda import EdaConfig, Source, analyze, read_result
from equiframe.eda.cli import app

MARKER = "SYNTHETIC_PRIVATE_MARKER_9387"


class UnsafeStringError(RuntimeError):
    def __str__(self):
        raise AssertionError("Exception values must never be formatted")


def test_debug_frames_exclude_exception_values_and_source_paths(caplog):
    caplog.set_level(logging.DEBUG, logger="equiframe.diagnostics")
    try:
        raise UnsafeStringError(MARKER)
    except UnsafeStringError as error:
        assert _error_reporting.report_failure(error, "operation_failed") == "operation_failed"
    assert "safe frames=" in caplog.text
    assert MARKER not in caplog.text
    assert str(Path(__file__)) not in caplog.text
    assert "UnsafeStringError" not in caplog.text


def test_failed_logging_handler_cannot_replace_the_operation_result(monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError(MARKER)

    monkeypatch.setattr(_error_reporting._LOG, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(_error_reporting._LOG, "debug", broken)
    assert _error_reporting.report_failure(UnsafeStringError(MARKER), "operation_failed") == (
        "operation_failed"
    )


def csv_source(tmp_path):
    directory = tmp_path / "inputs"
    directory.mkdir()
    path = directory / "source.csv"
    path.write_text("id,amount\n1,2\n", encoding="utf8")
    return Source(
        path=str(path),
        format="csv",
        snapshot_id="synthetic-errors",
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_failed_cancellation_callback_is_called_once_and_keeps_safe_evidence(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger="equiframe.diagnostics")
    source = csv_source(tmp_path)
    calls = []

    def cancellation():
        calls.append(1)
        raise UnsafeStringError(MARKER)

    result = analyze(source, output=tmp_path / "result", cancellation=cancellation)
    assert calls == [1]
    assert result.state == "not_evaluable" and result.reason == "cancellation_callback_failed"
    assert not result.snapshot_complete
    assert read_result(tmp_path / "result") == result
    assert MARKER not in result.model_dump_json()
    assert MARKER not in (tmp_path / "result/report.html").read_text("utf8")
    assert MARKER not in caplog.text
    assert hashlib.sha256(Path(source.path).read_bytes()).hexdigest() == source.expected_sha256


class UntrustedTruthValue:
    def __bool__(self):
        raise AssertionError("An invalid cancellation value must not be truth-tested")


@pytest.mark.parametrize("returned", [None, 1, "false", UntrustedTruthValue()])
def test_cancellation_requires_an_actual_boolean(tmp_path, returned):
    calls = []

    def cancellation():
        calls.append(1)
        return returned

    result = analyze(csv_source(tmp_path), output=tmp_path / "result", cancellation=cancellation)
    assert calls == [1]
    assert result.state == "not_evaluable" and result.reason == "invalid_cancellation_result"
    assert not result.snapshot_complete
    assert read_result(tmp_path / "result") == result


def test_cli_validation_does_not_echo_invalid_input_values(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger="equiframe.diagnostics")
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(tmp_path / "source.csv"),
            "--output",
            str(tmp_path / "result"),
            "--expected-sha256",
            MARKER,
        ],
    )
    assert result.exit_code == 2
    assert "Check the inputs and retry" in result.output
    assert MARKER not in result.output and MARKER not in caplog.text


def test_unexpected_chart_failure_is_stored_without_disclosing_values(
    tmp_path, monkeypatch, caplog
):
    from equiframe.eda import _report

    caplog.set_level(logging.DEBUG, logger="equiframe.diagnostics")

    def failure(*_args):
        raise UnsafeStringError(MARKER)

    monkeypatch.setattr(_report, "_charts", failure)
    result = analyze(
        csv_source(tmp_path), config=EdaConfig(charts=True), output=tmp_path / "result"
    )
    assert result.state == "not_evaluable" and result.reason == "requested_charts_unavailable"
    assert result.chart_state == "not_evaluable"
    assert read_result(tmp_path / "result") == result
    assert MARKER not in result.model_dump_json() and MARKER not in caplog.text
    assert MARKER not in (tmp_path / "result/report.html").read_text("utf8")
