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
from equiframe.local import local_path
from equiframe.pipeline_types import PipelineInput
from equiframe.serialization import contract_fingerprint
from equiframe.verification_request import VerificationRequest
from equiframe.verify_types import VerificationBinding


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


@pytest.mark.parametrize("relationship", ["same_path", "hardlink", "separate"])
def test_required_expected_uses_distinct_source_file(tmp_path, relationship):
    expected = artifact(tmp_path, "expected", table())
    candidate = expected
    if relationship == "hardlink":
        alias = tmp_path / "hardlink.arrow"
        alias.hardlink_to(local_path(expected))
        candidate = expected.model_copy(update={"uri": alias.as_uri()})
    elif relationship == "separate":
        candidate = artifact(tmp_path, "candidate", table())
    assert candidate.sha256 == expected.sha256
    path = tmp_path / "request.json"
    publish_json(
        VerificationRequest(
            contract=contract(),
            outputs=(PipelineInput(name="candidate", artifact=candidate),),
            expected=expected,
            require_expected=True,
        ),
        path,
    )
    runner = CliRunner()
    runs = tmp_path / "runs"
    result = runner.invoke(app, ["verify", "run", str(path), "--output", str(runs)])
    assert result.exit_code == (0 if relationship == "separate" else 3), result.output
    summary = json.loads(result.stdout)
    assert summary["publishable"] is (relationship == "separate")
    if relationship != "separate":
        assert summary["expected"][0]["reason"] == "Expected and candidate refer to the same file"
    directory = runs / summary["verification_id"]
    assert runner.invoke(app, ["verify", "inspect", str(directory)]).exit_code == 0


@pytest.mark.parametrize(
    "change", [None, "expected", "contract", "plan", "snapshot", "missing", "bytes"]
)
def test_cli_reference_binding_requires_matching_reference_and_batch(tmp_path, change):
    expected = artifact(tmp_path, "expected", table())
    output = artifact(tmp_path, "output", table())
    source = artifact(tmp_path, "source", table())
    plan_sha256 = "1" * 64
    request_path = tmp_path / "request.json"
    binding_path = tmp_path / "binding.json"
    binding = VerificationBinding(
        expected_sha256="0" * 64 if change == "expected" else expected.sha256,
        contract_sha256="0" * 64 if change == "contract" else contract_fingerprint(contract()),
        plan_sha256="0" * 64 if change == "plan" else plan_sha256,
        snapshots=(("other" if change == "snapshot" else "input", source.sha256),),
        outputs=(),
    )
    publish_json(binding, binding_path)
    publish_json(
        VerificationRequest(
            contract=contract(),
            outputs=(PipelineInput(name="candidate", artifact=output),),
            expected=None if change == "missing" else expected,
            snapshots=(PipelineInput(name="input", artifact=source),),
            plan_sha256=plan_sha256,
        ),
        request_path,
    )
    if change == "bytes":
        local_path(expected).write_bytes(b"replaced")
    result = CliRunner().invoke(
        app,
        [
            "verify",
            "run",
            str(request_path),
            "--reference-binding",
            str(binding_path),
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == {None: 0, "bytes": 1}.get(change, 3), result.output
    if change not in (None, "bytes"):
        assert "reference_binding_mismatch" in result.stderr
    else:
        summary = json.loads(result.stdout)
        assert summary["publishable"] is (change is None)
        if change == "bytes":
            assert summary["dimensions"]["integrity"]["state"] == "failed"
            assert summary["expected"][0]["state"] == "not_evaluable"


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


@pytest.mark.parametrize("mutation", ["redistribution", "duplicate", "missing_zero", "null"])
def test_required_expected_checks_lines_even_when_group_sums_match(tmp_path, mutation):
    contract = ef.keyed_contract(
        (
            *(
                ef.ColumnSpec(
                    name=name,
                    logical_type=ef.StringType(),
                    nullable=False,
                    null_policy=ef.NullPolicy(representations=("null",)),
                )
                for name in ("buyer", "currency", "line")
            ),
            ef.ColumnSpec(
                name="amount",
                logical_type=ef.DecimalType(precision=12, scale=2),
                nullable=True,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
            ),
        ),
        keys=("buyer", "currency", "line"),
    ).spec.contract
    rows = [("A", "L1", "10.00"), ("A", "L2", "20.00"), ("B", "L3", "30.00"), ("B", "L4", "0.00")]
    altered = rows.copy()
    if mutation == "redistribution":
        altered[:2] = [("A", "L1", "10.01"), ("A", "L2", "19.99")]
    elif mutation == "duplicate":
        altered[:1] = [("A", "L1", "5.00"), ("A", "L1", "5.00")]
    elif mutation == "missing_zero":
        altered.pop()
    else:
        altered[-1] = ("B", "L4", None)

    def write(name, values):
        return artifact(
            tmp_path,
            name,
            pa.table(
                {
                    "buyer": [buyer for buyer, _, _ in values],
                    "currency": ["USD"] * len(values),
                    "line": [line for _, line, _ in values],
                    "amount": pa.array(
                        [
                            Decimal(amount) if amount is not None else None
                            for _, _, amount in values
                        ],
                        type=pa.decimal128(12, 2),
                    ),
                }
            ),
        )

    path = tmp_path / "request.json"
    publish_json(
        VerificationRequest(
            contract=contract,
            outputs=(PipelineInput(name="candidate", artifact=write("candidate", altered)),),
            expected=write("expected", rows),
        ),
        path,
    )
    result = CliRunner().invoke(
        app, ["verify", "run", str(path), "--require-expected", "--output", str(tmp_path / "runs")]
    )
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["publishable"] is False


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
