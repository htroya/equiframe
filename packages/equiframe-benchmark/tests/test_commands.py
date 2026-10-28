"""Synthetic command checks; no publication or independent human reproduction."""

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
import typer
from test_distribution import source
from typer.testing import CliRunner

from equiframe_benchmark.commands import register
from equiframe_benchmark.io import save_document
from equiframe_benchmark.reproduction import create_bundle, make_reproduction_record

runner = CliRunner()


def app() -> typer.Typer:
    instance = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
    register(instance)
    return instance


def bundle(tmp_path: Path) -> Path:
    record = make_reproduction_record(
        configuration={"code": "untrusted_json:must_not_import"},
        splits=[],
        labels=[],
        decisions=[],
        tables={"rows": [["USD", {"decimal": "1.00"}]]},
    )
    source = tmp_path / "record.json"
    save_document(record, source)
    directory = tmp_path / "bundle"
    create_bundle(
        {"record.json": source},
        directory=directory,
        bundle_id="unit-commands",
        record_path="record.json",
    )
    return directory


def module_fixture(monkeypatch, callback):
    fixture = ModuleType("unit_command_factory")
    called = []

    def factory():
        called.append("factory")
        return callback

    fixture.factory = factory
    monkeypatch.setitem(sys.modules, "unit_command_factory", fixture)
    return called


def test_distribution_command_prints_pending_inventory_and_writes_exclusive_receipt(tmp_path):
    package = source(tmp_path)
    output = tmp_path / "readiness.json"
    result = runner.invoke(app(), ["distribution-readiness", str(package), "--output", str(output)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["publication_ready"] is False
    assert "pending_license" in payload["pending_conditions"]
    assert output.exists()
    repeated = runner.invoke(
        app(), ["distribution-readiness", str(package), "--output", str(output)]
    )
    assert repeated.exit_code == 3 and "operation_failed" in repeated.output


def test_readiness_invalid_path_is_input_error_and_not_publication_success(tmp_path):
    result = runner.invoke(app(), ["distribution-readiness", str(tmp_path / "missing")])
    assert result.exit_code == 2 and "invalid_input" in result.output


def test_verify_bundle_checks_digest_and_does_not_import_json_code(tmp_path):
    directory = bundle(tmp_path)
    result = runner.invoke(app(), ["verify-bundle", str(directory)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["evidence_verified"] is True
    assert payload["independent_person_reproduced"] is False
    invalid = runner.invoke(app(), ["verify-bundle", str(directory), "--expected-sha256", "0" * 64])
    assert invalid.exit_code == 3
    assert "operation_failed" in invalid.output
    assert "untrusted_json" not in sys.modules


def test_reproduce_requires_explicit_regenerator_and_factory_returns_callable(
    tmp_path, monkeypatch
):
    directory = bundle(tmp_path)
    missing = runner.invoke(app(), ["reproduce-bundle", str(directory)])
    assert missing.exit_code == 2
    calls = module_fixture(monkeypatch, 42)
    invalid = runner.invoke(
        app(), ["reproduce-bundle", str(directory), "--regenerator", "unit_command_factory:factory"]
    )
    assert invalid.exit_code == 2 and calls == ["factory"]


def test_reproduce_full_logical_content_and_save_receipt(tmp_path, monkeypatch):
    directory = bundle(tmp_path)
    calls = module_fixture(monkeypatch, lambda record: record)
    output = tmp_path / "receipt.json"
    result = runner.invoke(
        app(),
        [
            "reproduce-bundle",
            str(directory),
            "--regenerator",
            "unit_command_factory:factory",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "reproduced"
    assert calls == ["factory"]
    assert len(payload["components"]) == 5 and output.exists()
    assert "untrusted_json" not in sys.modules


def test_different_reproduction_is_preserved_and_returns_one(tmp_path, monkeypatch):
    directory = bundle(tmp_path)
    module_fixture(monkeypatch, lambda record: record.model_copy(update={"tables": '{"rows":[]}'}))
    result = runner.invoke(
        app(), ["reproduce-bundle", str(directory), "--regenerator", "unit_command_factory:factory"]
    )
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["status"] == "different"


@pytest.mark.parametrize("invalid", ["not-a-reference", "unit_command_factory:factory()"])
def test_invalid_factory_reference_does_not_execute_any_callback(tmp_path, monkeypatch, invalid):
    calls = module_fixture(monkeypatch, lambda record: record)
    result = runner.invoke(
        app(), ["reproduce-bundle", str(bundle(tmp_path)), "--regenerator", invalid]
    )
    assert result.exit_code == 2 and calls == []


def test_corrupted_bundle_is_operation_error_before_explicit_factory_runs(tmp_path, monkeypatch):
    directory = bundle(tmp_path)
    (directory / "record.json").write_bytes(b"corrupted")
    calls = module_fixture(monkeypatch, lambda record: record)
    result = runner.invoke(
        app(), ["reproduce-bundle", str(directory), "--regenerator", "unit_command_factory:factory"]
    )
    assert result.exit_code == 3 and calls == []
