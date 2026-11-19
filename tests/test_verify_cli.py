"""CLI distinguishes semantic outcomes from intact evidence and portable inspection."""

import json
from decimal import Decimal

import pyarrow as pa
import pytest
from test_migration import contract, run, table
from test_verify import artifact
from typer.testing import CliRunner

import equiframe as ef
from equiframe.cli import app
from equiframe.evidence import publish_json
from equiframe.pipeline_types import PipelineInput
from equiframe.verification_request import VerificationRequest


def request(tmp_path, *, wrong=False, require_expected=False):
    expected = artifact(tmp_path, "expected", table())
    output = artifact(
        tmp_path,
        "output",
        pa.table({"id": [99, 99, 99], "value": ["a", None, "c"]}) if wrong else table(),
    )
    path = tmp_path / "request.json"
    publish_json(
        VerificationRequest(
            contract=contract(),
            outputs=(PipelineInput(name="external", artifact=output),),
            expected=expected if wrong else None,
            require_expected=require_expected,
        ),
        path,
    )
    return path


def test_cli_metadata_validation_and_semantic_run_inspection(tmp_path):
    path = request(tmp_path, wrong=True)
    runner = CliRunner()
    validated = runner.invoke(app, ["verify", "validate", str(path)])
    assert validated.exit_code == 0 and json.loads(validated.stdout)["metadata_valid"]
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(tmp_path / "runs")])
    assert result.exit_code == 1
    summary = json.loads(result.stdout)
    assert summary["operational_state"] == "failed"
    directory = tmp_path / "runs" / summary["verification_id"]
    inspected = runner.invoke(app, ["verify", "inspect", str(directory)])
    assert inspected.exit_code == 0
    assert json.loads(inspected.stdout)["publishable"] is False
    (directory / "report.json").write_text("{}", encoding="utf-8")
    assert runner.invoke(app, ["verify", "inspect", str(directory)]).exit_code == 3


def test_cli_required_expected_absent_and_invalid_request(tmp_path):
    path = request(tmp_path, require_expected=True)
    runner = CliRunner()
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(tmp_path / "runs")])
    assert result.exit_code == 3
    data = json.loads(path.read_bytes())
    data["outputs"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    assert runner.invoke(app, ["verify", "validate", str(path)]).exit_code == 2


def test_cli_can_require_expected_even_if_request_omits_it(tmp_path):
    path = request(tmp_path)
    runner = CliRunner()
    command = ["verify", "run", str(path), "--output", str(tmp_path / "runs")]
    assert runner.invoke(app, command).exit_code == 0
    required = runner.invoke(app, [*command, "--require-expected"])
    assert required.exit_code == 3
    summary = json.loads(required.stdout)
    assert summary["operational_state"] == "not_evaluable"
    assert summary["publishable"] is False


@pytest.mark.parametrize(
    ("amounts", "buyers", "exit_code"),
    [
        (("30.00", "20.00"), ("B", "A"), 0),
        (("20.01", "29.99"), ("A", "B"), 1),
        (("20.00",), ("A",), 1),
        (("20.00", "30.00", "20.00"), ("A", "B", "A"), 1),
        (("20.00", "30.00"), ("X", "B"), 1),
    ],
    ids=["equal-reordered", "same-total-redistribution", "missing", "duplicate", "unexpected"],
)
def test_cli_expected_gate_checks_money_by_buyer_and_currency(tmp_path, amounts, buyers, exit_code):
    money = pa.decimal128(12, 2)
    columns = (
        ef.ColumnSpec(
            name="buyer",
            logical_type=ef.StringType(),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
        ),
        ef.ColumnSpec(
            name="currency",
            logical_type=ef.StringType(),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
        ),
        ef.ColumnSpec(
            name="amount",
            logical_type=ef.DecimalType(precision=12, scale=2),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
        ),
    )
    declaration = ef.keyed_contract(columns, keys=("buyer", "currency"))
    expected = pa.table(
        {
            "buyer": ["A", "B"],
            "currency": ["USD", "USD"],
            "amount": pa.array([Decimal("20.00"), Decimal("30.00")], type=money),
        }
    )
    candidate = pa.table(
        {
            "buyer": list(buyers),
            "currency": ["USD"] * len(buyers),
            "amount": pa.array([Decimal(amount) for amount in amounts], type=money),
        }
    )
    path = tmp_path / "request.json"
    publish_json(
        VerificationRequest(
            contract=declaration.spec.contract,
            outputs=(
                PipelineInput(name="candidate", artifact=artifact(tmp_path, "actual", candidate)),
            ),
            expected=artifact(tmp_path, "expected", expected),
        ),
        path,
    )
    result = CliRunner().invoke(
        app, ["verify", "run", str(path), "--require-expected", "--output", str(tmp_path / "runs")]
    )
    assert result.exit_code == exit_code, result.stdout
    assert json.loads(result.stdout)["publishable"] is (exit_code == 0)


def test_cli_bundle_export_import_verify_preserve_semantic_failure(tmp_path):
    runner = CliRunner()
    path = request(tmp_path, wrong=True)
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(tmp_path / "runs")])
    directory = tmp_path / "runs" / json.loads(result.stdout)["verification_id"]
    portable = tmp_path / "portable"
    relocated = tmp_path / "relocated"
    assert runner.invoke(app, ["bundle", "export", str(directory), str(portable)]).exit_code == 0
    directory.rename(tmp_path / "hidden_original")
    assert runner.invoke(app, ["bundle", "import", str(portable), str(relocated)]).exit_code == 0
    verified = runner.invoke(app, ["bundle", "verify", str(relocated)])
    assert verified.exit_code == 0
    assert json.loads(verified.stdout)["outcome"]["operational_state"] == "failed"
    assert (
        runner.invoke(app, ["bundle", "verify", str(relocated), "--sha256", "0" * 64]).exit_code
        == 3
    )


def test_cli_existing_migration_is_verified_without_native_callbacks(tmp_path, monkeypatch):
    migration = run(tmp_path / "migration_runs")

    def prohibited(*args, **kwargs):
        raise AssertionError("native ETL must not rerun during Verify")

    monkeypatch.setattr("equiframe.migration.runner.migrate", prohibited)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "verify",
            "migration",
            str(tmp_path / "migration_runs" / migration.migration_id),
            "--output",
            str(tmp_path / "verify_runs"),
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["dimensions"]["technical"]["state"] == "passed"
