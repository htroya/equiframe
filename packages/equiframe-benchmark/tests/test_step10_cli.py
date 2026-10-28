"""Native CLI conformance; every review and scientific decision here is fictitious."""

import json

import equiframe as ef
import pytest
from test_costs import environment, frozen_bundle
from test_freeze import native_definition
from typer.testing import CliRunner

from equiframe_benchmark.cli import app
from equiframe_benchmark.costs import read_costs
from equiframe_benchmark.evaluation import EvaluationReport
from equiframe_benchmark.fixtures import registry
from equiframe_benchmark.freeze import read_freeze
from equiframe_benchmark.io import save_document
from equiframe_benchmark.study import read_study
from equiframe_benchmark.tables import read_tables


@pytest.mark.parametrize("command", ["verify-freeze", "verify-study", "verify-costs"])
def test_verifiers_never_echo_private_corrupt_content(tmp_path, command):
    path = tmp_path / "bad.json"
    path.write_text('{"token":"private-marker", "token":"duplicate"}', encoding="utf8")
    response = CliRunner().invoke(app, [command, str(path)])
    assert response.exit_code == 3
    assert "operation_failed" in response.output
    assert "private-marker" not in response.output and "Traceback" not in response.output


def test_cost_cli_uses_isolated_m_and_real_captured_outputs(tmp_path):
    pytest.importorskip("psutil")
    spec, _, _, _ = environment(tmp_path)
    spec_path, bundle_path = tmp_path / "spec.json", tmp_path / "detector.json"
    save_document(spec, spec_path)
    ef.write_detector_bundle(frozen_bundle(spec.profile), bundle_path)
    output = tmp_path / "costs"
    response = CliRunner().invoke(
        app,
        [
            "costs",
            str(spec_path),
            "--bundle",
            str(bundle_path),
            "--output",
            str(output),
        ],
    )
    assert response.exit_code == 0, response.output
    summary = json.loads(response.stdout)
    assert summary["scientific_h3_confirmed"] is False
    result = read_costs(output / summary["cost_id"])
    assert result.complete and len(result.observations) == 10
    assert all(
        o.profile_m.detection.method == "isolation_forest"
        for o in result.observations
        if o.profile_m
    )
    response = CliRunner().invoke(app, ["verify-costs", str(output / result.cost_id)])
    assert response.exit_code == 0 and json.loads(response.stdout)["evidence_verified"]
    import csv

    csv_path = tmp_path / "costs.csv"
    response = CliRunner().invoke(
        app,
        [
            "cost-table",
            str(output / result.cost_id),
            "--output",
            str(csv_path),
        ],
    )
    assert response.exit_code == 0
    with csv_path.open(encoding="utf8", newline="") as stream:
        rows = tuple(csv.DictReader(stream))
    assert len(rows) == 12
    assert sum(row["phase"] == "warmup" for row in rows) == 2
    assert all(row["rss_method"] == "sampled_absolute_lower_bound" for row in rows)
    assert {row["method"] for row in rows} == {"profile_m", "comparison"}
    before = csv_path.read_bytes()
    assert (
        CliRunner()
        .invoke(
            app,
            [
                "cost-table",
                str(output / result.cost_id),
                "--output",
                str(csv_path),
            ],
        )
        .exit_code
        == 3
    )
    assert csv_path.read_bytes() == before


def test_wrong_cost_bundle_is_rejected_before_measurement(tmp_path):
    spec, _, _, _ = environment(tmp_path)
    spec = type(spec).model_validate(
        {
            **spec.model_dump(mode="python"),
            "detector_bundle_sha256": "f" * 64,
        }
    )
    spec_path, bundle_path = tmp_path / "spec.json", tmp_path / "detector.json"
    save_document(spec, spec_path)
    ef.write_detector_bundle(frozen_bundle(spec.profile), bundle_path)
    output = tmp_path / "must-not-start"
    response = CliRunner().invoke(
        app,
        [
            "costs",
            str(spec_path),
            "--bundle",
            str(bundle_path),
            "--output",
            str(output),
        ],
    )
    assert response.exit_code == 2 and not output.exists()


def synthetic_cli_registry():
    """Explicitly selected fixture factory, never loaded from persisted JSON."""
    return registry()


def synthetic_changed_registry():
    """A native fixture implementation that cannot replay the reviewed candidate."""
    registered = ef.TransformationRegistry()
    registered.register(
        ef.DuckDBTransformation("nulls_types", 'SELECT * FROM "items" LIMIT 0', "synthetic.v1")
    )
    return registered


@pytest.fixture(scope="module")
def cli_native_definition(tmp_path_factory):
    # Fit the six isolated synthetic groups once for all freeze/study CLI regressions.
    return native_definition(tmp_path_factory.mktemp("step10-cli-native") / "data")


@pytest.fixture(scope="module")
def cli_pilot_freeze(cli_native_definition, tmp_path_factory):
    root = tmp_path_factory.mktemp("step10-cli-freeze")
    definition_path, manifest_path = root / "definition.json", root / "freeze.json"
    save_document(cli_native_definition, definition_path)
    response = CliRunner().invoke(
        app, ["freeze", str(definition_path), "--output", str(manifest_path)]
    )
    assert response.exit_code == 0, response.output
    summary = json.loads(response.stdout)
    assert summary["sealed"] and summary["technical_ready"]
    assert summary["mode"] == "pilot" and not summary["scientific_ready"]
    return manifest_path, summary


@pytest.fixture(scope="module")
def cli_captured_study(cli_pilot_freeze, tmp_path_factory):
    import equiframe_benchmark.study as study_module

    manifest_path, _ = cli_pilot_freeze
    output = tmp_path_factory.mktemp("step10-cli-studies")
    verified = []
    original_reader = study_module.read_study

    def tracked_reader(directory):
        verified.append(directory)
        return original_reader(directory)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ef, "fit_detectors", lambda *_a, **_k: pytest.fail("CLI study trained ML"))
        patch.setattr(study_module, "read_study", tracked_reader)
        response = CliRunner().invoke(
            app,
            [
                "run-study",
                str(manifest_path),
                "--registry",
                "test_step10_cli:synthetic_cli_registry",
                "--output",
                str(output),
            ],
        )
    # This completed fixture has statistical alerts; the recorded result controls
    # the final exit code rather than completeness alone.
    assert response.exit_code == 1, response.output
    summary = json.loads(response.stdout)
    directory = output / summary["study_id"]
    assert verified == [directory.resolve()]
    result = read_study(directory)
    assert response.exit_code == result.exit_code
    assert summary == {
        "study_id": result.study_id,
        "scientific": result.scientific,
        "complete": result.complete,
        "cases": len(result.evaluation.records),
        "evidence_verified": True,
    }
    assert result.complete and not result.scientific and len(result.cases) == 2
    return directory, result


def test_final_freeze_reports_blockers_before_sealing(cli_native_definition, tmp_path):
    definition = cli_native_definition.model_copy(update={"mode": "final"})
    definition_path, output = tmp_path / "definition.json", tmp_path / "must-not-exist.json"
    save_document(definition, definition_path)
    response = CliRunner().invoke(app, ["freeze", str(definition_path), "--output", str(output)])
    assert response.exit_code == 2, response.output
    summary = json.loads(response.stdout)
    assert summary["mode"] == "final" and not summary["sealed"]
    assert summary["technical_ready"] and not summary["scientific_ready"]
    assert "scientific:synthetic_catalog" in summary["blockers"]
    assert "scientific:pending_decision:source_license" in summary["blockers"]
    assert not output.exists() and not list(tmp_path.glob("must-not-exist.json.*"))


def test_pilot_freeze_keeps_scientific_diagnostics_and_verifies(cli_pilot_freeze):
    manifest_path, summary = cli_pilot_freeze
    assert "scientific:synthetic_catalog" in summary["blockers"]
    assert "scientific:pending_decision:source_license" in summary["blockers"]
    manifest = read_freeze(manifest_path)
    assert manifest.audit.ready and not manifest.audit.scientific_ready
    response = CliRunner().invoke(app, ["verify-freeze", str(manifest_path)])
    assert response.exit_code == 0, response.output
    assert json.loads(response.stdout) == {
        "evidence_verified": True,
        "mode": "pilot",
        "technical_ready": True,
        "scientific_ready": False,
        "blockers": summary["blockers"],
    }


def test_native_study_cli_reproduces_evaluation_and_tables(cli_captured_study, tmp_path):
    directory, result = cli_captured_study
    evaluated = tmp_path / "evaluation.json"
    response = CliRunner().invoke(app, ["evaluate", str(directory), "--output", str(evaluated)])
    assert response.exit_code == 0, response.output
    assert json.loads(response.stdout) == {"scientific": False, "regenerated": True}
    assert EvaluationReport.model_validate_json(evaluated.read_bytes()) == result.evaluation
    tables = tmp_path / "tables"
    response = CliRunner().invoke(app, ["tables", str(directory), "--output", str(tables)])
    assert response.exit_code == 0, response.output
    assert json.loads(response.stdout) == {"tables": 6, "scientific": False}
    assert read_tables(tables, report=result.evaluation) == result.tables
    response = CliRunner().invoke(app, ["verify-study", str(directory)])
    assert response.exit_code == 0, response.output
    summary = json.loads(response.stdout)
    assert summary["complete"] and summary["evidence_verified"] and not summary["scientific"]


def test_incomplete_native_replay_returns_evidence_failure_not_success(cli_pilot_freeze, tmp_path):
    manifest_path, _ = cli_pilot_freeze
    response = CliRunner().invoke(
        app,
        [
            "run-study",
            str(manifest_path),
            "--registry",
            "test_step10_cli:synthetic_changed_registry",
            "--output",
            str(tmp_path),
        ],
    )
    assert response.exit_code == 3, response.output
    summary = json.loads(response.stdout)
    assert not summary["complete"] and not summary["scientific"]
    assert summary["evidence_verified"] and summary["cases"] == 2
    result = read_study(tmp_path / summary["study_id"])
    assert not result.complete and result.exit_code == 3
    assert all(record.oracle_state == "not_evaluable" for record in result.evaluation.records)


@pytest.mark.parametrize("content", ['{"schema_version":', '{"schema_version":"invalid"}'])
def test_run_study_rejects_corrupt_freeze_before_loading_registry(tmp_path, content):
    freeze = tmp_path / "freeze.json"
    freeze.write_text(content, encoding="utf8")
    output = tmp_path / "must-not-run"
    response = CliRunner().invoke(
        app,
        [
            "run-study",
            str(freeze),
            "--registry",
            "nonexistent_fixture_module:must_not_import",
            "--output",
            str(output),
        ],
    )
    assert response.exit_code == 3 and "operation_failed" in response.output
    assert not output.exists() and "evidence_verified" not in response.output


@pytest.mark.parametrize("command", ["evaluate", "tables"])
@pytest.mark.parametrize("content", ['{"schema_version":', '{"schema_version":"invalid"}'])
def test_corrupt_captured_study_is_evidence_failure_without_output(
    cli_captured_study, tmp_path, command, content
):
    directory, _ = cli_captured_study
    manifest = directory / "study.json"
    original = manifest.read_bytes()
    output = tmp_path / "must-not-create"
    try:
        manifest.write_text(content, encoding="utf8")
        response = CliRunner().invoke(app, [command, str(directory), "--output", str(output)])
        assert response.exit_code == 3 and "operation_failed" in response.output
        assert not output.exists() and "regenerated" not in response.output
    finally:
        manifest.write_bytes(original)
