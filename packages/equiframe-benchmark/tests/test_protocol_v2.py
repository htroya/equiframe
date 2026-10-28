"""Bounded engineering checks; all records and review identities are fictional."""

import csv
import hashlib
import io
import json
import platform
from fractions import Fraction

import equiframe as ef
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import equiframe_benchmark as eb
from equiframe_benchmark.cli import app
from equiframe_benchmark.costs import CostProtocol
from equiframe_benchmark.evaluation import EvaluationRecord, EvaluationReport
from equiframe_benchmark.evaluation_v2 import PRIMARY_FAMILIES, PRIMARY_MIGRATIONS
from equiframe_benchmark.fixtures import registry
from equiframe_benchmark.freeze import DECISIONS
from equiframe_benchmark.pilot import profile_spec
from equiframe_benchmark.reproduction import make_reproduction_record


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def decision(alert=False):
    return ef.ComponentDecision(decision="alert" if alert else "no_alert", complete=True)


MISSING = ef.ComponentDecision(decision="not_evaluable", complete=False, reason="fixture_missing")


def record(number, positive, *, r=False, m=False, b=False, b_missing=False, group=None):
    return EvaluationRecord(
        case_id=f"v2-case-{number}",
        scenario_id=f"v2-scenario-{number}",
        group_id=group or f"v2-group-{number}",
        family="joins",
        migration="pandas-polars",
        engine="polars",
        candidate_sha256=sha(f"candidate-{number}"),
        pipeline_sha256=sha(f"pipeline-{number}"),
        oracle_sha256=sha(f"oracle-{number}"),
        oracle_state="confirmed",
        oracle_label="divergent" if positive else "normal",
        r=decision(r),
        m=decision(m),
        b=MISSING if b_missing else decision(b),
        h=decision(r or m),
        m_score=0.8 if m else 0.2,
        b_score=None if b_missing else 0.8 if b else 0.2,
        detector_bundle_sha256=sha("bundle-joins"),
        freeze_sha256=None,
    )


def config(*, independent=False, repetitions=8, contrasts=None):
    return eb.EvaluationConfigV2(
        mode="pilot",
        freeze_sha256=None,
        contrasts=contrasts or (eb.ContrastSpecV2(left="H", right="R"),),
        bootstrap=eb.BootstrapPlan(
            seed=17,
            repetitions=repetitions,
            min_groups=2,
            independence_supported=independent,
            rationale="Synthetic engineering fixture only; no scientific independence claim.",
        ),
    )


def test_paired_principal_keeps_case_without_mad_and_preserves_signed_differences():
    records = (
        record(1, True, m=True, b_missing=True),
        record(2, True, r=True),
        record(3, False, m=True),
        record(4, False),
    )
    result = eb.evaluate_records_v2(records, config())
    paired = result.strata[0].principal[0]
    assert paired.comparison.support_case_ids == tuple(row.case_id for row in records)
    assert result.strata[0].common.case_ids == tuple(row.case_id for row in records[1:])
    assert paired.comparison.coverage_confirmed.value == 1.0
    assert (paired.comparison.left_metrics.tp, paired.comparison.left_metrics.fp) == (2, 1)
    assert (paired.comparison.right_metrics.tp, paired.comparison.right_metrics.fp) == (1, 0)
    estimates = {item.name: item.estimate for item in paired.estimates}
    assert estimates["difference.H-R.recall"].value == 0.5
    assert estimates["difference.H-R.precision"].value == float(Fraction(-1, 3))
    assert estimates["H_only_vs_R.true_positive_rate"].value == 0.5
    assert estimates["H_only_vs_R.false_positive_rate"].value == 0.5
    assert not result.scientific
    assert eb.EvaluationReportV2.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        EvaluationReport.model_validate_json(result.model_dump_json())


def test_three_by_three_strata_and_empty_denominators_are_explicit():
    report = eb.evaluate_records_v2((), config())
    cells = [row for row in report.strata if row.kind == "family_migration"]
    assert {(row.family, row.migration) for row in cells} == {
        (family, migration) for family in PRIMARY_FAMILIES for migration in PRIMARY_MIGRATIONS
    }
    assert len(report.strata) == 16
    for cell in cells:
        pair = cell.principal[0].comparison
        assert pair.coverage_scheduled.denominator == 0
        assert pair.coverage_scheduled.value is None
        assert pair.coverage_scheduled.reason == "no_scheduled_cases"
    with pytest.raises(ValidationError):
        eb.EvaluationConfigV2.model_validate(
            config().model_copy(update={"expected_families": ("joins",)})
        )
    with pytest.raises(ValidationError):
        config(
            contrasts=(
                eb.ContrastSpecV2(left="H", right="R"),
                eb.ContrastSpecV2(left="R", right="H"),
            )
        )


def test_paired_bootstrap_same_group_draw_preserves_zero_difference():
    records = (
        record(1, True, r=True, group="positive"),
        record(2, True, r=True, group="positive"),
        record(3, False, group="normal"),
        record(4, False, group="normal"),
    )
    report = eb.evaluate_records_v2(records, config(independent=True))
    result = report.strata[0].principal[0].bootstrap
    assert result.attempted_replicates == 8
    assert result.group_ids == ("normal", "positive")
    f1 = next(item for item in result.intervals if item.metric == "difference.H-R.f1")
    # All groups in a replicate are sampled together for both equal decisions.
    assert f1.lower == f1.upper == 0.0 or f1.reason == "undefined_bootstrap_replicates"
    assert f1.defined_replicates + f1.undefined_replicates == 8
    again = eb.evaluate_records_v2(tuple(reversed(records)), config(independent=True))
    assert again == report


def test_all_undefined_replicates_and_unsupported_independence_are_reported():
    records = (record(1, False, group="a"), record(2, False, group="b"))
    result = eb.evaluate_records_v2(records, config(independent=True)).strata[0].principal[0]
    recall = next(item for item in result.bootstrap.intervals if item.metric == "H.recall")
    assert recall.lower is recall.upper is None
    assert recall.undefined_replicates == 8 and recall.defined_replicates == 0
    disabled = eb.evaluate_records_v2(records, config()).strata[0].principal[0].bootstrap
    assert disabled.attempted_replicates == 0
    assert {item.reason for item in disabled.intervals} == {"independence_not_supported"}


def test_whole_balanced_groups_keep_both_class_denominators_in_every_replicate():
    records = (
        record(1, True, m=True, group="a"),
        record(2, False, m=True, group="a"),
        record(3, True, m=True, group="b"),
        record(4, False, m=True, group="b"),
    )
    result = eb.evaluate_records_v2(records, config(independent=True)).strata[0].principal[0]
    for metric in ("difference.H-R.recall", "difference.H-R.false_positive_rate"):
        interval = next(item for item in result.bootstrap.intervals if item.metric == metric)
        assert interval.lower == interval.upper == 1.0
        assert interval.defined_replicates == 8 and interval.undefined_replicates == 0


@pytest.fixture
def definition(make_case):
    data = tuple(make_case(family) for family in PRIMARY_FAMILIES)
    catalog = eb.Catalog(
        catalog_id="v2-fictional", synthetic=True, scenarios=tuple(row[0] for row in data)
    )
    splits = eb.make_splits(catalog, seed=9, weights=(1, 1, 1))
    held = {item.scenario_id for item in splits.assignments if item.partition == "test"}
    cases = tuple(
        eb.TestCaseDefinition(
            case_id="held:" + scenario.scenario_id,
            scenario_id=scenario.scenario_id,
            candidate=candidate,
            oracle=None,
            migration="pandas-duckdb",
            pipeline=ef.PipelineSpec(
                execution=ef.ExecutionPlan(
                    contract=scenario.comparison.contract,
                    engine="duckdb",
                    transformation_id=scenario.family,
                ),
                profile=profile_spec(scenario.family),
                comparison_policy=scenario.comparison.policy,
                comparison_reference="expected",
            ),
        )
        for scenario, candidate, *_ in data
        if scenario.scenario_id in held
    )
    return eb.FreezeDefinitionV2(
        protocol_review=eb.ProtocolReviewV2(
            status="pending",
            protocol_sha256=None,
            reviewer=None,
            rationale="Fictional fixture; not a human approval.",
        ),
        study_id="v2-fictional",
        revision=1,
        mode="pilot",
        catalog=catalog,
        splits=splits,
        cases=cases,
        models=tuple(
            eb.FrozenFamilyModel(
                family=family,
                profile=profile_spec(family),
                reason="No fitted model in this bounded fixture.",
            )
            for family in PRIMARY_FAMILIES
        ),
        selection_evidence=(),
        decisions=tuple(
            eb.ExperimentalDecision(
                name=name,
                status="pending",
                value=None,
                rationale="Fictional fixture decision remains pending.",
            )
            for name in DECISIONS
        ),
        files=(),
        environment=(eb.EnvironmentPin(package="python", version=platform.python_version()),),
        code_revision="fixture",
        evaluation=config(),
        cost_protocol=CostProtocol(
            seed=1,
            cache_policy="fixture",
            threads=1,
            concurrent_loads="fixture",
            controls_rationale="fixture",
        ),
    )


def test_freeze_binds_exact_review_without_manufacturing_approval(definition, tmp_path):
    audit = eb.audit_freeze_v2(definition)
    assert audit.technical_ready and audit.ready
    assert "scientific:pending_paired_protocol_review_v2" in audit.blockers
    assert any(item.startswith("scientific:empty_primary_stratum:") for item in audit.blockers)
    manifest = eb.create_freeze_v2(definition)
    path = tmp_path / "freeze-v2.json"
    eb.save_document(manifest, path)
    assert eb.read_freeze_v2(path) == manifest
    with pytest.raises(ValidationError, match="exact V2 protocol"):
        eb.FreezeDefinitionV2.model_validate(
            definition.model_copy(
                update={
                    "protocol_review": eb.ProtocolReviewV2(
                        status="approved",
                        protocol_sha256="0" * 64,
                        reviewer="fictional reviewer",
                        rationale="Negative binding fixture.",
                    ),
                }
            )
        )
    final = eb.FreezeDefinitionV2.model_validate(definition.model_copy(update={"mode": "final"}))
    with pytest.raises(ValueError, match="pending_paired_protocol_review_v2"):
        eb.create_freeze_v2(final)


def test_environment_pin_is_checked_as_integrity_not_scientific_approval(definition):
    wrong = eb.FreezeDefinitionV2.model_validate(
        definition.model_copy(
            update={
                "environment": (eb.EnvironmentPin(package="python", version="0.0.0"),),
            }
        )
    )
    audit = eb.audit_freeze_v2(wrong)
    assert not audit.ready and not audit.technical_ready
    assert any("environment:python" in item for item in audit.integrity_blockers)


def test_seven_tables_reproduce_and_reject_byte_tampering(tmp_path):
    report = eb.evaluate_records_v2((record(1, True, m=True), record(2, False)), config())
    directory = tmp_path / "tables"
    receipt = eb.write_tables_v2(report, directory)
    assert len(receipt.tables) == 7
    assert eb.read_tables_v2(directory, report=report) == receipt
    content = dict(eb.table_payloads_v2(report))["metrics.csv"][0].decode()
    parsed = list(csv.DictReader(io.StringIO(content)))
    assert any(row["metric"] == "difference.H-R.recall" for row in parsed)
    with (directory / "metrics.csv").open("ab") as stream:
        stream.write(b"tampered\n")
    with pytest.raises(ValueError, match="size"):
        eb.read_tables_v2(directory, report=report)


def test_captured_record_regeneration_binds_v2_and_splits(definition):
    report = eb.evaluate_records_v2((record(1, True, m=True),), config())
    captured = make_reproduction_record(
        configuration={
            "protocol_version": "2.0",
            "evaluation": config().model_dump(mode="json"),
            "splits_sha256": eb.digest(definition.splits),
        },
        splits=definition.splits.model_dump(mode="json"),
        labels=[
            {
                "case_id": row.case_id,
                "oracle_sha256": row.oracle_sha256,
                "state": row.oracle_state,
                "label": row.oracle_label,
            }
            for row in report.records
        ],
        decisions=[row.model_dump(mode="json") for row in report.records],
        tables={
            "evaluation_sha256": eb.digest(report),
            "csv": {
                name: payload.decode()
                for name, (payload, _) in eb.table_payloads_v2(report).items()
            },
        },
    )
    assert eb.regenerate_study_record_v2(captured) == captured


def test_one_native_heldout_study_roundtrip_without_training(definition, tmp_path):
    manifest = eb.create_freeze_v2(definition)
    study = eb.run_study_v2(manifest, registry=registry(), work_dir=tmp_path / "studies")
    assert len(study.cases) == 1
    assert study.cases[0].pipeline.execution.state == "completed"
    assert study.cases[0].record.oracle_state == "pending"
    assert study.cases[0].record.m.complete is False
    assert not study.scientific
    assert eb.read_study_v2(tmp_path / "studies" / study.study_id) == study
    bundle_path = tmp_path / "portable"
    eb.bundle_study_v2(tmp_path / "studies" / study.study_id, output=bundle_path)
    assert eb.reproduce_study_bundle_v2(bundle_path).status == "reproduced"


def test_cli_parser_missing_file_stderr_and_no_interactive_prompt(tmp_path):
    runner = CliRunner()
    missing = runner.invoke(app, ["freeze-v2"])
    assert missing.exit_code == 2 and missing.stdout == ""
    assert "Missing argument" in missing.stderr and "?" not in missing.stdout
    absent = runner.invoke(app, ["verify-freeze-v2", str(tmp_path / "secret-token.json")])
    assert absent.exit_code == 3 and absent.stdout == ""
    assert "secret-token" not in absent.stderr and "missing_path" in absent.stderr


def test_cli_freeze_pending_output_and_permission_failure(definition, tmp_path, monkeypatch):
    source = tmp_path / "definition.json"
    output = tmp_path / "freeze.json"
    eb.save_document(definition, source)
    runner = CliRunner()
    response = runner.invoke(app, ["freeze-v2", str(source), "--output", str(output)])
    assert response.exit_code == 0 and response.stderr == "", response.output
    assert json.loads(response.stdout)["scientific_ready"] is False
    import equiframe_benchmark.freeze_v2 as module

    def denied(*args, **kwargs):
        raise PermissionError("secret-permission-path")

    monkeypatch.setattr(module, "read_freeze_v2", denied)
    failed = runner.invoke(app, ["verify-freeze-v2", str(output)])
    assert failed.exit_code == 3 and failed.stdout == ""
    assert "permission_denied" in failed.stderr and "secret-permission-path" not in failed.stderr


def test_cli_invalid_document_uses_code_two_without_echoing_values(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"private-token":"do-not-echo",', encoding="utf-8")
    response = CliRunner().invoke(
        app, ["freeze-v2", str(path), "--output", str(tmp_path / "result.json")]
    )
    assert response.exit_code == 2 and response.stdout == ""
    assert "do-not-echo" not in response.stderr and "Traceback" not in response.stderr


def test_cli_reproduction_difference_has_code_one(monkeypatch, tmp_path):
    import equiframe_benchmark.study_bundle_v2 as module

    original = make_reproduction_record(
        configuration={},
        splits={},
        labels=[],
        decisions=[],
        tables={"metric": 1},
    )
    changed = make_reproduction_record(
        configuration={},
        splits={},
        labels=[],
        decisions=[],
        tables={"metric": 2},
    )
    observed = eb.compare_reproductions(original, changed)
    monkeypatch.setattr(module, "reproduce_study_bundle_v2", lambda path: observed)
    result = CliRunner().invoke(app, ["reproduce-study-v2", str(tmp_path)])
    assert result.exit_code == 1 and result.stderr == ""
    assert json.loads(result.stdout) == {"protocol_version": "2.0", "status": "different"}


CLI_COMMANDS_V2 = (
    "freeze-v2",
    "verify-freeze-v2",
    "run-study-v2",
    "verify-study-v2",
    "evaluate-v2",
    "tables-v2",
    "bundle-study-v2",
    "reproduce-study-v2",
)


def _cli_arguments(command, source, output):
    arguments = [command, str(source)]
    if command in ("freeze-v2", "evaluate-v2", "tables-v2", "bundle-study-v2"):
        arguments.extend(("--output", str(output)))
    if command == "run-study-v2":
        arguments.extend(("--registry", "equiframe_benchmark.fixtures:registry"))
        arguments.extend(("--output", str(output)))
    return arguments


@pytest.mark.parametrize("command", CLI_COMMANDS_V2)
def test_every_v2_command_missing_input_is_noninteractive_redacted_stderr(command, tmp_path):
    result = CliRunner().invoke(
        app,
        _cli_arguments(command, tmp_path / "private-missing-input", tmp_path / "output"),
        input="",
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    assert result.exit_code >= 1 and result.stdout == ""
    assert result.stderr and "private-missing-input" not in result.stderr
    assert "Traceback" not in result.stderr and "Password:" not in result.stderr


def test_eight_v2_commands_real_native_roundtrip(definition, tmp_path, monkeypatch):
    definition_path = tmp_path / "definition-v2.json"
    freeze_path = tmp_path / "freeze-v2.json"
    studies = tmp_path / "studies"
    portable = tmp_path / "portable"
    eb.save_document(definition, definition_path)
    runner = CliRunner()

    def invoke(command, source, output):
        result = runner.invoke(
            app,
            _cli_arguments(command, source, output),
            input="",
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )
        assert result.exit_code == 0, (command, result.stdout, result.stderr, result.exception)
        assert result.stderr == "" and result.stdout
        return json.loads(result.stdout)

    assert invoke("freeze-v2", definition_path, freeze_path)["sealed"] is True
    assert invoke("verify-freeze-v2", freeze_path, None)["evidence_verified"] is True
    executed = invoke("run-study-v2", freeze_path, studies)
    assert executed["complete"] is True and executed["cases"] == 1
    study = studies / executed["study_id"]
    assert invoke("verify-study-v2", study, None)["evidence_verified"] is True
    assert invoke("evaluate-v2", study, tmp_path / "evaluation.json")["regenerated"] is True
    assert invoke("tables-v2", study, tmp_path / "tables")["tables"] == 7
    assert invoke("bundle-study-v2", study, portable)["protocol_version"] == "2.0"
    assert invoke("reproduce-study-v2", portable, None)["status"] == "reproduced"
    import equiframe_benchmark.io as documents
    import equiframe_benchmark.tables_v2 as tables

    def denied(*args, **kwargs):
        raise PermissionError("private-write-path")

    for command, module, attribute in (
        ("evaluate-v2", documents, "save_document"),
        ("tables-v2", tables, "write_tables_v2"),
    ):
        with monkeypatch.context() as scoped:
            scoped.setattr(module, attribute, denied)
            result = runner.invoke(
                app,
                _cli_arguments(command, study, tmp_path / (command + "-denied")),
                input="",
            )
        assert result.exit_code == 3 and result.stdout == ""
        assert "permission_denied" in result.stderr and "private-write-path" not in result.stderr


def test_v2_command_write_and_read_permissions_preserve_stderr_contract(
    definition,
    tmp_path,
    monkeypatch,
):
    import equiframe_benchmark.freeze_v2 as freezes
    import equiframe_benchmark.io as documents
    import equiframe_benchmark.study_bundle_v2 as bundles
    import equiframe_benchmark.study_v2 as studies

    source = tmp_path / "definition.json"
    frozen = tmp_path / "freeze.json"
    eb.save_document(definition, source)
    eb.save_document(eb.create_freeze_v2(definition), frozen)
    runner = CliRunner()

    def denied(*args, **kwargs):
        raise PermissionError("private-denied-path")

    # Commands that write are stopped at their writer; read-only commands fail
    # at their reader. This checks CLI permission policy without changing ACLs.
    boundaries = (
        ("freeze-v2", source, documents, "save_document"),
        ("verify-freeze-v2", frozen, freezes, "read_freeze_v2"),
        ("run-study-v2", frozen, studies, "run_study_v2"),
        ("verify-study-v2", tmp_path, studies, "read_study_v2"),
        ("evaluate-v2", tmp_path, studies, "read_study_v2"),
        ("tables-v2", tmp_path, studies, "read_study_v2"),
        ("bundle-study-v2", tmp_path, bundles, "bundle_study_v2"),
        ("reproduce-study-v2", tmp_path, bundles, "reproduce_study_bundle_v2"),
    )
    for command, input_path, module, attribute in boundaries:
        with monkeypatch.context() as scoped:
            scoped.setattr(module, attribute, denied)
            response = runner.invoke(
                app,
                _cli_arguments(command, input_path, tmp_path / (command + "-out")),
                input="",
            )
        assert response.exit_code == 3 and response.stdout == "", (command, response.output)
        assert "permission_denied" in response.stderr
        assert "private-denied-path" not in response.stderr
