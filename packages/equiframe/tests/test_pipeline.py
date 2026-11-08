"""End-to-end orchestration with native engines and independently expected decisions."""

import json
from concurrent.futures import ThreadPoolExecutor

import pyarrow as pa
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import equiframe as ef
from equiframe.cli import app
from equiframe.evidence import EventJournal, publish_json
from equiframe.pipeline_types import EvidenceFile


def contract():
    schema = ef.TableSchema(
        columns=(
            ef.ColumnSpec(
                name="id",
                logical_type=ef.IntegerType(bits=64, signed=True),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="identifier"),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            ef.ColumnSpec(
                name="value",
                logical_type=ef.StringType(),
                nullable=True,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
        ),
        keys=(),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="pipeline.synthetic",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="input", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="rows",
                revision=1,
                severity="error",
                required=True,
                specification=ef.CardinalityCheck(table="result", minimum=2),
            ),
        ),
    )


def profile_spec():
    return ef.ProfileSpec(
        family="nulls_types",
        features=(
            ef.ProfileFeature(
                name="missing", metric="tasa_nulos", table="result", columns=("value",)
            ),
        ),
    )


def registered(sql='SELECT * FROM "input"'):
    registry = ef.TransformationRegistry()
    registry.register(
        ef.DuckDBTransformation(
            transformation_id="identity", revision=1, code_version="synthetic.1", sql=sql
        )
    )
    registry.register(
        ef.PandasTransformation(
            transformation_id="identity",
            revision=1,
            code_version="synthetic.1",
            callback=lambda tables, context: tables["input"].copy(),
        )
    )
    registry.register(
        ef.PolarsTransformation(
            transformation_id="identity",
            revision=1,
            code_version="synthetic.1",
            callback=lambda tables, context: tables["input"].lazy().select("id", "value"),
        )
    )
    return registry


def table():
    return pa.table({"id": [1, 2, 3], "value": ["a", None, "c"]})


def run(tmp_path, **kwargs):
    spec = kwargs.pop(
        "spec",
        ef.PipelineSpec(
            execution=ef.ExecutionPlan(
                contract=contract(), engine="duckdb", transformation_id="identity"
            ),
            profile=profile_spec(),
        ),
    )
    registry = kwargs.pop("registry", registered())
    return ef.run_pipeline(
        spec,
        source=ef.LocalDataSource({"input": ef.ArrowInput(table())}),
        registry=registry,
        work_dir=tmp_path,
        **kwargs,
    )


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
def test_native_pipeline_evidence_and_no_duplicate_execution(tmp_path, engine):
    spec = ef.PipelineSpec(
        execution=ef.ExecutionPlan(
            contract=contract(), engine=engine, transformation_id="identity"
        ),
        profile=profile_spec(),
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            physical_types="lossless",
            justification="Synthetic RangeIndex is not a data column; string widths are lossless",
        ),
    )
    result = run(tmp_path, spec=spec, comparison=ef.ArrowInput(table()))
    assert result.complete and result.exit_code == 0
    assert result.rules.decision == "no_alert" and result.comparison.state == "equivalent"
    assert result.hybrid.result.decision == "not_evaluable"  # detector not requested
    assert result.profile.vector.observations[0].value == 1 / 3
    directory = tmp_path / result.pipeline_id
    assert ef.read_pipeline(directory) == result
    assert len(list(directory.rglob("run.json"))) == 1
    assert ef.inspect_evidence(directory)["finalized"]
    assert ef.PipelineResult.model_validate_json(result.model_dump_json()) == result


def test_alerts_and_comparison_remain_independent(tmp_path):
    result = run(
        tmp_path,
        registry=registered('SELECT * FROM "input" LIMIT 1'),
        comparison=ef.ArrowInput(table()),
    )
    assert result.complete and result.exit_code == 1
    assert result.rules.decision == result.hybrid.result.decision == "alert"
    assert not result.hybrid.result.complete
    assert result.comparison.state == "different"
    assert ef.read_pipeline(tmp_path / result.pipeline_id) == result


def trained_bundle():
    spec = profile_spec()

    def vector(n):
        return ef.ProfileVector(
            spec=spec,
            spec_sha256=ef.profile_spec_fingerprint(spec),
            observations=(
                ef.FeatureObservation(
                    name="missing", state="available", value=n / 10, numerator=n, denominator=10
                ),
            ),
        )

    fit = ef.fit_detectors(
        ef.NormalTrainingProfiles(
            purpose="normal_training",
            selection_manifest_sha256="a" * 64,
            profiles=tuple(vector(n) for n in range(10)),
        ),
        spec=spec,
        config=ef.IsolationForestConfig(random_state=8, n_estimators=9, max_samples=10),
        support=ef.DetectorSupport(
            min_training_rows=3, min_calibration_rows=2, rationale="synthetic engineering test"
        ),
    )
    return ef.calibrate_detectors(
        fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration",
            selection_manifest_sha256="b" * 64,
            profiles=tuple(vector(n) for n in range(10)),
        ),
        alpha="0.1",
    )


def test_full_pipeline_uses_frozen_detectors(tmp_path, monkeypatch):
    bundle = trained_bundle()
    before = bundle.model_dump_json()
    monkeypatch.setattr("equiframe.detectors.fit_detectors", lambda *a, **k: pytest.fail("refit"))
    result = run(tmp_path, detector_bundle=bundle, comparison=ef.ArrowInput(table()))
    assert result.complete and result.hybrid.result.complete
    assert result.detection == ef.detect(bundle, (result.profile.vector,))
    assert bundle.model_dump_json() == before
    assert ef.read_pipeline(tmp_path / result.pipeline_id) == result


def test_incompatible_bundle_retains_rules_and_comparison(tmp_path):
    from test_detectors import bundle

    result = run(tmp_path, detector_bundle=bundle(), comparison=ef.ArrowInput(table()))
    assert not result.complete and result.exit_code == 3
    assert result.stages[3].state == "failed"
    assert result.rules.decision == "no_alert" and result.comparison.state == "equivalent"
    assert result.hybrid.result.decision == "not_evaluable"


def test_failed_execution_and_pre_cancelled_never_succeed(tmp_path):
    result = run(tmp_path, registry=registered('SELECT missing FROM "input"'))
    assert result.execution.state != "completed" and result.exit_code == 3
    assert result.hybrid.result.decision == "not_evaluable"
    assert ef.read_pipeline(tmp_path / result.pipeline_id) == result
    token = ef.CancellationToken()
    token.cancel()
    cancelled = run(tmp_path, cancellation=token)
    assert cancelled.cancelled and cancelled.exit_code == 3 and cancelled.execution is None
    assert all(s.code == "cancelled" for s in cancelled.stages[:-1])
    assert ef.read_pipeline(tmp_path / cancelled.pipeline_id) == cancelled


def test_component_error_no_secrets_and_independent_comparison(tmp_path, monkeypatch):
    secret = "password-test-canary-7812"

    def fail(*args, **kwargs):
        raise ValueError(secret)

    monkeypatch.setattr("equiframe.pipeline.profile_execution", fail)
    monkeypatch.setenv("API_TOKEN", secret)
    result = run(tmp_path, comparison=ef.ArrowInput(table()))
    assert not result.complete and result.comparison.state == "equivalent"
    assert result.stages[2].state == "failed"
    directory = tmp_path / result.pipeline_id
    for path in directory.rglob("*.json*"):
        assert secret not in path.read_text("utf-8")
    assert secret not in (directory / "report.html").read_text("utf-8")


def test_reruns_and_parallel_runs_do_not_overwrite(tmp_path):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(tmp_path), range(2)))
    assert len({r.pipeline_id for r in results}) == 2
    assert all(ef.read_pipeline(tmp_path / r.pipeline_id) == r for r in results)


@pytest.mark.parametrize("relative", ["report.html", "events.jsonl", "pipeline.json"])
def test_tamper_detected_before_report_generation(tmp_path, relative):
    result = run(tmp_path)
    directory = tmp_path / result.pipeline_id
    with (directory / relative).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_pipeline(directory)
    response = CliRunner().invoke(
        app, ["report", str(directory), "--output", str(tmp_path / "html")]
    )
    assert response.exit_code == 3 and not (tmp_path / "html").exists()


def test_partial_evidence_inspection(tmp_path):
    directory = tmp_path / "pipeline_interrupted"
    directory.mkdir()
    journal = EventJournal(directory, directory.name)
    journal.emit("pipeline", "started", "pipeline_started")
    journal.emit("execution", "started", "stage_started")
    result = ef.inspect_evidence(directory)
    assert not result["complete"] and not result["finalized"] and result["exit_code"] == 3
    with (directory / "events.jsonl").open("ab") as stream:
        stream.write(b'{"truncated":')
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.inspect_evidence(directory)


def test_report_escape_and_exclusive_publication(tmp_path):
    malicious = '</pre><script>alert("x")</script><img src=x onerror=alert(1)>'
    rendered = ef.render_report({"input": malicious})
    assert "<script>" not in rendered and "<img" not in rendered
    assert "&lt;/pre&gt;&lt;script&gt;" in rendered and "Content-Security-Policy" in rendered
    result = run(tmp_path)
    ef.write_report(result, tmp_path / "report")
    with pytest.raises(FileExistsError):
        ef.write_report(result, tmp_path / "report")


@pytest.mark.parametrize("path", ["../x", "/x", "C:/x", "a/../b", "a\\b", "a//b", "."])
def test_evidence_path_traversal_rejected(path):
    with pytest.raises(ValidationError):
        EvidenceFile(path=path, sha256="a" * 64, size_bytes=1)


def test_credentials_rejected_and_corrupt_lineage_rejected(tmp_path):
    execution = ef.ExecutionPlan(
        contract=contract(),
        engine="duckdb",
        transformation_id="identity",
        parameters=(ef.Parameter(name="api_token", value=ef.StringValue(value="secret")),),
    )
    with pytest.raises(ValidationError, match="credential"):
        ef.PipelineSpec(execution=execution)
    result = run(tmp_path)
    with pytest.raises(ValidationError):
        ef.PipelineResult.model_validate(result.model_copy(update={"spec_sha256": "b" * 64}))
    other = run(tmp_path)
    with pytest.raises(ValidationError):
        ef.PipelineResult.model_validate(result.model_copy(update={"rules": other.rules}))


def test_cli_run_report_verify_invalid_input(tmp_path, monkeypatch):
    import equiframe.cli as cli

    runner = CliRunner()
    result = run(tmp_path)
    request = ef.PipelineRequest(
        spec=result.spec,
        inputs=(ef.PipelineInput(name="input", artifact=result.execution.inputs[0].data),),
    )
    path = tmp_path / "request.json"
    publish_json(request, path)
    monkeypatch.setattr(cli, "_trusted_callable", lambda reference: registered)
    response = runner.invoke(
        app, ["run", str(path), "--registry", "trusted:factory", "--output", str(tmp_path / "cli")]
    )
    assert response.exit_code == 0, response.output
    summary = json.loads(response.stdout)
    directory = tmp_path / "cli" / summary["pipeline_id"]
    assert runner.invoke(app, ["evidence", "verify", str(directory)]).exit_code == 0
    assert (
        runner.invoke(
            app, ["report", str(directory), "--output", str(tmp_path / "share")]
        ).exit_code
        == 0
    )
    path.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf8")
    response = runner.invoke(app, ["run", str(path), "--registry", "untrusted:factory"])
    assert response.exit_code == 2 and "Traceback" not in response.output


def test_comparison_unavailable_and_native_budget_take_priority_over_alert(tmp_path):
    spec = ef.PipelineSpec(
        execution=ef.ExecutionPlan(
            contract=contract(), engine="duckdb", transformation_id="identity"
        ),
        comparison_options=ef.ComparisonOptions(max_rows=1),
    )
    result = run(
        tmp_path,
        spec=spec,
        registry=registered('SELECT * FROM "input" LIMIT 1'),
        comparison=ef.ArrowInput(table()),
    )
    assert result.rules.decision == "alert" and result.exit_code == 3
    assert result.comparison.state == "not_evaluable" and not result.complete
    limited = ef.PipelineSpec(
        execution=spec.execution.model_copy(
            update={"options": ef.ExecutionOptions(max_input_rows=1)}
        )
    )
    result = run(tmp_path, spec=limited)
    assert result.execution.state == "resource_exhausted" and result.exit_code == 3


def test_pandas_index_requires_explicit_policy(tmp_path):
    spec = ef.PipelineSpec(
        execution=ef.ExecutionPlan(
            contract=contract(), engine="pandas", transformation_id="identity"
        )
    )
    result = run(tmp_path, spec=spec, comparison=ef.ArrowInput(table()))
    assert result.exit_code == 3 and result.comparison.state == "not_evaluable"
    assert any(d.code == "unsupported_capability" for d in result.comparison.diagnostics)


def test_manifest_publication_failure_remains_incomplete(tmp_path, monkeypatch):
    import equiframe.pipeline as pipeline

    original = pipeline.publish_json

    def fail_manifest(value, path):
        if path.name == "manifest.json":
            raise OSError("simulated write failure")
        return original(value, path)

    monkeypatch.setattr(pipeline, "publish_json", fail_manifest)
    with pytest.raises(OSError):
        run(tmp_path)
    directory = next(tmp_path.glob("pipeline_*"))
    assert not ef.inspect_evidence(directory)["finalized"]
    assert (directory / "report.html").exists()


def test_reader_rejects_manifest_and_component_disagreement(tmp_path):
    result = run(tmp_path)
    directory = tmp_path / result.pipeline_id
    raw = json.loads((directory / "manifest.json").read_bytes())
    raw["elapsed_seconds"] += 1  # valid typed field, inconsistent with the saved report
    (directory / "manifest.json").write_text(json.dumps(raw), encoding="utf8")
    with pytest.raises(ef.ArtifactIntegrityError, match="report contradicts"):
        ef.read_pipeline(directory)


def test_reader_rejects_forged_comparison_lineage(tmp_path):
    first = run(tmp_path, comparison=ef.ArrowInput(table()))
    second = run(tmp_path, comparison=ef.ArrowInput(table()))
    with pytest.raises(ValidationError, match="comparison does not belong"):
        ef.PipelineResult.model_validate(first.model_copy(update={"comparison": second.comparison}))


def test_cli_compare_outcomes(tmp_path):
    source = tmp_path / "input.arrow"
    different = tmp_path / "different.arrow"
    for path, data in ((source, table()), (different, table().slice(1))):
        with path.open("xb") as output, pa.ipc.new_file(output, data.schema) as writer:
            writer.write_table(data)
    spec = tmp_path / "comparison-spec.json"
    publish_json(ef.ComparisonSpec(contract=contract()), spec)
    runner = CliRunner()
    for right, code in ((source, 0), (different, 1), (tmp_path / "missing.arrow", 3)):
        response = runner.invoke(
            app, ["compare", str(spec), str(source), str(right), "--output", str(tmp_path / "runs")]
        )
        assert response.exit_code == code, response.output


def test_cli_reduction_and_safe_predicate_loading(tmp_path, monkeypatch):
    import equiframe.cli as cli

    result = run(tmp_path)
    request = ef.PipelineRequest(
        spec=result.spec,
        inputs=(ef.PipelineInput(name="input", artifact=result.execution.inputs[0].data),),
    )
    path = tmp_path / "request.json"
    publish_json(request, path)

    def predicate(tables):
        return ef.ReductionObservation(preconditions="satisfied", failure_signature="synthetic")

    monkeypatch.setattr(cli, "_trusted_callable", lambda reference: predicate)
    response = CliRunner().invoke(
        app,
        [
            "reduce",
            str(path),
            "--predicate",
            "my_etl:predicate",
            "--predicate-version",
            "v1",
            "--failure-signature",
            "synthetic",
            "--output",
            str(tmp_path / "reduced"),
        ],
    )
    assert response.exit_code == 0, response.output
    document = json.loads(response.stdout)
    assert not document["global_minimum_claimed"]
    directory = tmp_path / "reduced" / document["reduction_id"]
    assert ef.inspect_evidence(directory)["finalized"]


@pytest.mark.parametrize("reference", ["file.py", "os:system('x')", "../plugin:factory"])
def test_registration_syntax_cannot_execute_json_code(reference):
    from equiframe.cli import _trusted_callable

    with pytest.raises(ValueError):
        _trusted_callable(reference)
