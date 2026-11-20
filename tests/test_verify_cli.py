"""CLI distinguishes semantic outcomes from intact evidence and portable inspection."""

import hashlib
import json
from decimal import Decimal

import pyarrow as pa
import pytest
from test_migration import contract, run, table
from test_verify import artifact
from typer.testing import CliRunner

import equiframe as ef
from equiframe.cli import app
from equiframe.evidence import canonical_bytes, publish_json
from equiframe.local import local_path
from equiframe.pipeline_types import PipelineInput
from equiframe.serialization import contract_fingerprint
from equiframe.verification_request import ReferenceBinding, VerificationRequest


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
    "change",
    [
        None,
        "expected",
        "contract",
        "plan",
        "snapshot",
        "missing",
        "bytes",
        "partial",
        "policy",
        "unbound_policy",
    ],
)
def test_cli_reference_binding_requires_matching_reference_and_batch(tmp_path, change):
    expected = artifact(tmp_path, "expected", table())
    output = artifact(tmp_path, "output", table())
    source = artifact(tmp_path, "source", table())
    plan_sha256 = "1" * 64
    request_path = tmp_path / "request.json"
    binding_path = tmp_path / "binding.json"
    declared = contract()
    if change == "partial":
        lookup = declared.inputs[0].model_copy(update={"name": "lookup"})
        declared = declared.model_copy(update={"inputs": (*declared.inputs, lookup)})
    binding = ReferenceBinding(
        expected_sha256="0" * 64 if change == "expected" else expected.sha256,
        contract_sha256="0" * 64 if change == "contract" else contract_fingerprint(declared),
        comparison_spec_sha256=None
        if change == "unbound_policy"
        else ef.comparison_fingerprint(ef.ComparisonSpec(contract=declared)),
        plan_sha256="0" * 64 if change == "plan" else plan_sha256,
        snapshots=(("other" if change == "snapshot" else "input", source.sha256),),
        outputs=(),
    )
    publish_json(binding, binding_path)
    publish_json(
        VerificationRequest(
            contract=declared,
            outputs=(PipelineInput(name="candidate", artifact=output),),
            expected=None if change == "missing" else expected,
            snapshots=(PipelineInput(name="input", artifact=source),),
            plan_sha256=plan_sha256,
            policy=ef.ComparisonPolicy(column_order="ignored", justification="Audit policy")
            if change == "policy"
            else ef.ComparisonPolicy(),
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
    ("total", "has_input", "exit_code"), [(6, True, 0), (7, True, 1), (6, False, 3)]
)
def test_cli_strict_acceptance_checks_required_rule_even_when_reference_matches(
    tmp_path, total, has_input, exit_code
):
    base = contract()
    aggregation = ef.RuleSpec(
        rule_id="balance",
        revision=1,
        required=True,
        severity="error",
        specification=ef.AggregateCheck(
            table="input",
            group_by=(),
            measure="id",
            function="sum",
            output_table="result",
            output_column="id",
        ),
    )
    result_table = pa.table({"id": [total], "value": pa.array([None], type=pa.string())})
    path = tmp_path / "request.json"
    publish_json(
        VerificationRequest(
            contract=base.model_copy(update={"rules": (aggregation,)}),
            outputs=(
                PipelineInput(
                    name="candidate", artifact=artifact(tmp_path, "output", result_table)
                ),
            ),
            expected=artifact(tmp_path, "expected", result_table),
            snapshots=(PipelineInput(name="input", artifact=artifact(tmp_path, "input", table())),)
            if has_input
            else (),
        ),
        path,
    )
    runner = CliRunner()
    directory = tmp_path / "runs"
    result = runner.invoke(
        app, ["verify", "run", str(path), "--require-expected", "--output", str(directory)]
    )
    assert result.exit_code == exit_code, result.output
    summary = json.loads(result.stdout)
    assert summary["expected"][0]["state"] == "passed"
    assert summary["rules"][0]["state"] == {0: "passed", 1: "failed", 3: "not_evaluable"}[exit_code]
    assert summary["rule_evaluations"][0]["execution_state"] == "captured_artifacts"
    assert summary["coverage"]["input_execution_evidence_available"] is False
    evidence = directory / summary["verification_id"]
    assert runner.invoke(app, ["verify", "inspect", str(evidence)]).exit_code == 0
    portable = tmp_path / "portable"
    assert runner.invoke(app, ["bundle", "export", str(evidence), str(portable)]).exit_code == 0
    assert runner.invoke(app, ["bundle", "verify", str(portable)]).exit_code == 0


def test_cli_captured_execution_must_prove_requested_plan_and_output(tmp_path):
    migration = run(tmp_path / "migration")
    execution = migration.source.execution
    assert execution is not None and execution.output is not None
    digest = hashlib.sha256(canonical_bytes(execution.plan.model_dump(mode="json"))).hexdigest()
    request = VerificationRequest(
        contract=execution.plan.contract,
        outputs=(PipelineInput(name="candidate", artifact=execution.output.data),),
        expected=artifact(tmp_path, "expected", table()),
        policy=ef.ComparisonPolicy(
            index="ignore", justification="The index has no business identity."
        ),
        executions=(("candidate", execution),),
        plan_sha256=digest,
        require_expected=True,
    )
    runner = CliRunner()
    path = tmp_path / "request.json"
    args = ["verify", "run", str(path), "--output", str(tmp_path / "runs")]
    publish_json(request, path)
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["coverage"]["input_execution_evidence_available"] is True
    path.unlink()
    publish_json(request.model_copy(update={"plan_sha256": "0" * 64}), path)
    mismatch = runner.invoke(app, args)
    assert mismatch.exit_code == 3
    assert "execution_binding_mismatch" in mismatch.stderr


@pytest.mark.parametrize(
    ("case", "exit_code"),
    [
        ("match", 0),
        ("different", 1),
        ("no_binding", 2),
        ("relaxed", 2),
        ("approximate", 2),
        ("no_execution", 3),
        ("corrupt", 1),
    ],
)
def test_acceptance_refuses_incomplete_or_nonexact_scope(tmp_path, case, exit_code):
    declared = contract()
    if case == "approximate":
        schema = declared.output.schema_spec
        approximate = schema.columns[0].model_copy(
            update={
                "numeric_policy": ef.NumericPolicy(
                    comparison="approximate",
                    unit="identifier",
                    tolerance=ef.Tolerance(
                        absolute="1", unit="identifier", justification="Audit threshold"
                    ),
                )
            }
        )
        revised = schema.model_copy(update={"columns": (approximate, *schema.columns[1:])})
        declared = declared.model_copy(
            update={"output": declared.output.model_copy(update={"schema_spec": revised})}
        )
    policy = (
        ef.ComparisonPolicy(physical_types="lossless", justification="Audit type policy")
        if (case == "relaxed")
        else ef.ComparisonPolicy()
    )
    expected = artifact(tmp_path, "expected", table())
    source = artifact(tmp_path, "input", table())
    candidate = (
        pa.table({"id": [4, 5, 6], "value": ["a", None, "c"]}) if (case == "different") else table()
    )
    path = tmp_path / "request.json"
    binding_path = tmp_path / "binding.json"
    binding = ReferenceBinding(
        contract_sha256=contract_fingerprint(declared),
        expected_sha256=expected.sha256,
        plan_sha256="1" * 64,
        comparison_spec_sha256=ef.comparison_fingerprint(
            ef.ComparisonSpec(contract=declared, policy=policy)
        ),
        snapshots=(("input", source.sha256),),
        outputs=(),
    )
    publish_json(binding, binding_path)
    publish_json(
        VerificationRequest(
            contract=declared,
            policy=policy,
            expected=expected,
            plan_sha256=binding.plan_sha256,
            snapshots=(PipelineInput(name="input", artifact=source),),
            outputs=(
                PipelineInput(
                    name="candidate", artifact=artifact(tmp_path, "candidate", candidate)
                ),
            ),
        ),
        path,
    )
    if case == "corrupt":
        local_path(expected).write_bytes(b"replaced")
    runner = CliRunner()
    runs = tmp_path / "runs"
    args = ["verify", "accept", str(path), "--output", str(runs)]
    if case != "no_binding":
        args += ["--reference-binding", str(binding_path)]
    if case == "no_execution":
        args += ["--require-execution"]
    result = runner.invoke(app, args)
    assert result.exit_code == exit_code, result.output
    if exit_code != 2:
        summary = json.loads(result.stdout)
        assert summary["publishable"] is (case == "match")
        assert summary["acceptance"]["reference"] == binding.model_dump(mode="json")
        assert summary["acceptance"]["require_execution"] is (case == "no_execution")
        directory = runs / summary["verification_id"]
        assert runner.invoke(app, ["verify", "inspect", str(directory)]).exit_code == 0
        if case == "match":
            portable = tmp_path / "portable"
            assert (
                runner.invoke(app, ["bundle", "export", str(directory), str(portable)]).exit_code
                == 0
            )
            assert runner.invoke(app, ["bundle", "verify", str(portable)]).exit_code == 0


def test_acceptance_can_require_completed_execution(tmp_path):
    migration = run(tmp_path / "migration")
    execution = migration.target.execution
    assert execution is not None and execution.output is not None
    declared = execution.plan.contract
    digest = hashlib.sha256(canonical_bytes(execution.plan.model_dump(mode="json"))).hexdigest()
    expected = artifact(tmp_path, "reference", table())
    binding = ReferenceBinding(
        contract_sha256=execution.contract_sha256,
        plan_sha256=digest,
        comparison_spec_sha256=ef.comparison_fingerprint(ef.ComparisonSpec(contract=declared)),
        snapshots=tuple((table.name, table.data.sha256) for table in execution.inputs),
        expected_sha256=expected.sha256,
        outputs=(),
    )
    request = VerificationRequest(
        contract=declared,
        plan_sha256=digest,
        expected=expected,
        snapshots=tuple(
            PipelineInput(name=table.name, artifact=table.data) for table in execution.inputs
        ),
        outputs=(PipelineInput(name="candidate", artifact=execution.output.data),),
        executions=(("candidate", execution),),
    )
    request_path = tmp_path / "request.json"
    binding_path = tmp_path / "binding.json"
    publish_json(request, request_path)
    publish_json(binding, binding_path)
    out = CliRunner().invoke(
        app,
        [
            "verify",
            "accept",
            str(request_path),
            "--reference-binding",
            str(binding_path),
            "--require-execution",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert out.exit_code == 0, out.output
    report = json.loads(out.stdout)
    assert report["coverage"]["input_execution_evidence_available"] is True
    assert report["acceptance"]["require_execution"] is True


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
