"""CLI exercises explicitly supplied trusted code and real synthetic native runs."""

import json
import sys
from types import ModuleType

import pytest
from test_integration import environment
from typer.testing import CliRunner

from equiframe_benchmark.cli import app
from equiframe_benchmark.integration import read_integration
from equiframe_benchmark.io import save_document


def request(tmp_path, monkeypatch, *, corrupt_download=None):
    spec, source, registry, client, counters, _ = environment(
        tmp_path, corrupt_download=corrupt_download
    )
    module = ModuleType("trusted_integration_test")
    module.client_factory = lambda: client
    module.registry_factory = lambda: registry
    monkeypatch.setitem(sys.modules, module.__name__, module)
    path = tmp_path / "integration-spec.json"
    save_document(spec, path)
    output = tmp_path / "cli-output"
    arguments = [
        "integrate",
        str(path),
        "--snapshot-id",
        source.snapshot_id,
        "--client",
        module.__name__ + ":client_factory",
        "--registry",
        module.__name__ + ":registry_factory",
        "--output",
        str(output),
    ]
    return arguments, output, path, module, client, counters


def test_cli_integrates_three_native_engines_and_verifies_receipt(tmp_path, monkeypatch):
    arguments, output, _, _, client, counters = request(tmp_path, monkeypatch)
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 0, response.output
    summary = json.loads(response.stdout)
    assert summary["complete"] and summary["inputs_verified"]
    assert not summary["scientific_equivalence_confirmed"]
    result = read_integration(output / summary["integration_id"])
    assert len(result.runs) == 3 and len(result.comparisons) == 3
    assert counters == {"pandas": 1, "polars": 1} and client.downloads == 3
    verified = CliRunner().invoke(app, ["verify-integration", str(output / result.integration_id)])
    assert verified.exit_code == 0
    assert json.loads(verified.stdout)["evidence_verified"]


def test_cli_invalid_configuration_is_two_without_loading_factories(tmp_path, monkeypatch):
    arguments, output, path, _, client, counters = request(tmp_path, monkeypatch)
    path.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf8")
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 2 and response.output.splitlines()[0] == "invalid_input"
    assert client.downloads == 0 and not counters and not output.exists()


def test_cli_corrupt_receipt_is_three(tmp_path, monkeypatch):
    arguments, output, *_ = request(tmp_path, monkeypatch)
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 0
    directory = output / json.loads(response.stdout)["integration_id"]
    (directory / "integration.json").write_text('{"truncated":', encoding="utf8")
    verified = CliRunner().invoke(app, ["verify-integration", str(directory)])
    assert verified.exit_code == 3 and verified.output.splitlines()[0] == "operation_failed"


def test_cli_client_hash_failure_is_three_with_verified_failure_evidence(tmp_path, monkeypatch):
    arguments, output, *_ = request(tmp_path, monkeypatch, corrupt_download=1)
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 3, response.output
    summary = json.loads(response.stdout)
    assert not summary["complete"] and not summary["inputs_verified"]
    directory = output / summary["integration_id"]
    result = read_integration(directory)
    assert result.runs[0].result.execution.problem.code == "artifact_integrity_error"
    assert CliRunner().invoke(app, ["verify-integration", str(directory)]).exit_code == 0


def test_cli_latest_is_two_without_contacting_client(tmp_path, monkeypatch):
    arguments, output, _, _, client, counters = request(tmp_path, monkeypatch)
    arguments[arguments.index("--snapshot-id") + 1] = "latest"
    requests_before = len(client.requests)
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 2
    assert len(client.requests) == requests_before
    assert client.downloads == 0 and not counters and not output.exists()


@pytest.mark.parametrize("factory", ["client_factory", "registry_factory"])
def test_cli_invalid_factory_result_is_two(tmp_path, monkeypatch, factory):
    arguments, output, _, module, client, counters = request(tmp_path, monkeypatch)
    setattr(module, factory, lambda: object())
    response = CliRunner().invoke(app, arguments)
    assert response.exit_code == 2 and response.output.splitlines()[0] == "invalid_input"
    assert client.downloads == 0 and not counters and not output.exists()
