"""Synthetic native conformance only; fixture reviews are never human approvals."""

import json
import platform
from collections import Counter

import equiframe as ef
import pytest
from equiframe.local import local_path
from pydantic import ValidationError
from test_freeze import native_definition

import equiframe_benchmark as eb
from equiframe_benchmark.costs import CostProtocol
from equiframe_benchmark.evaluation import FAMILIES, BootstrapPlan, EvaluationConfig
from equiframe_benchmark.fixtures import registry
from equiframe_benchmark.freeze import (
    DECISIONS,
    EnvironmentPin,
    ExperimentalDecision,
    FreezeDefinition,
    FrozenFamilyModel,
    create_freeze,
)
from equiframe_benchmark.freeze import TestCaseDefinition as FrozenCase
from equiframe_benchmark.pilot import profile_spec, write_table
from equiframe_benchmark.study import read_study, run_study


def pending_definition(make_case, tmp_path):
    """Five test families plus two disjoint placeholder groups; O has no reviews."""
    scenarios, candidates = [], {}
    for number, family in enumerate((*FAMILIES, "nulls_types", "nulls_types")):
        original, candidate, *_ = make_case(family)
        if number >= 5:
            import pyarrow as pa

            table = ef.read_table(original.inputs[0].artifact)
            table = table.set_column(
                0, "id", pa.array([f"placeholder:{number}:{row}" for row in range(table.num_rows)])
            )
            source = write_table(table, tmp_path / f"placeholder-{number}.arrow")
            expected = write_table(table, tmp_path / f"placeholder-expected-{number}.arrow")
            original = original.model_copy(
                update={
                    "inputs": (eb.InputBinding(name="items", artifact=source),),
                    "expected": expected,
                }
            )
            candidate = candidate.model_copy(update={"output": expected})
        scenario = original.model_copy(
            update={
                "scenario_id": f"pilot.{number}",
                "dependencies": (f"independent-fixture:{number}",),
            }
        )
        candidate = candidate.model_copy(
            update={
                "candidate_id": f"pilot.candidate.{number}",
                "scenario_sha256": eb.digest(scenario),
            }
        )
        scenarios.append(scenario)
        candidates[scenario.scenario_id] = candidate
    catalog = eb.Catalog(
        catalog_id="all-native-family-fixtures", synthetic=True, scenarios=tuple(scenarios)
    )
    # The first two deterministic groups get training/calibration. A large test
    # weight sends all remaining groups to test; choose a seed with placeholders first.
    for seed in range(1000):
        splits = eb.make_splits(catalog, seed=seed, weights=(1, 1, 100))
        tests = {a.scenario_id for a in splits.assignments if a.partition == "test"}
        if tests == {s.scenario_id for s in scenarios[:5]}:
            break
    else:
        raise AssertionError("deterministic software fixture split not found")
    case_defs = []
    for scenario in scenarios[:5]:
        candidate = candidates[scenario.scenario_id]
        packet = eb.review_packet(
            scenario, candidate, directory=tmp_path / ("review-" + scenario.scenario_id)
        )
        pending = eb.evaluate_oracle(scenario, candidate, packet=packet, work_dir=tmp_path)
        assert pending.status == "pending" and pending.label is None
        for engine in ("pandas", "polars", "duckdb"):
            case_defs.append(
                FrozenCase(
                    case_id=scenario.scenario_id + ":" + engine,
                    scenario_id=scenario.scenario_id,
                    candidate=candidate,
                    oracle=pending,
                    migration="synthetic:" + engine,
                    pipeline=ef.PipelineSpec(
                        execution=ef.ExecutionPlan(
                            contract=scenario.comparison.contract,
                            engine=engine,
                            transformation_id=scenario.family,
                        ),
                        profile=profile_spec(scenario.family),
                        comparison_policy=scenario.comparison.policy,
                        comparison_reference="expected",
                    ),
                )
            )
    return FreezeDefinition(
        study_id="synthetic.pending-native-study",
        revision=1,
        mode="pilot",
        catalog=catalog,
        splits=splits,
        cases=tuple(case_defs),
        models=tuple(
            FrozenFamilyModel(
                family=f, profile=profile_spec(f), reason="no reviewed scientific model"
            )
            for f in FAMILIES
        ),
        selection_evidence=(),
        files=(),
        code_revision="test-fixture",
        decisions=tuple(
            ExperimentalDecision(
                name=n, status="pending", value=None, rationale="not decided by synthetic tests"
            )
            for n in DECISIONS
        ),
        environment=(EnvironmentPin(package="python", version=platform.python_version()),),
        evaluation=EvaluationConfig(
            mode="pilot",
            freeze_sha256=None,
            bootstrap=BootstrapPlan(
                seed=7,
                repetitions=5,
                min_groups=2,
                independence_supported=False,
                rationale="software fixture",
            ),
        ),
        cost_protocol=CostProtocol(
            seed=7,
            cache_policy="warm test cache",
            threads=1,
            concurrent_loads="test runner",
            controls_rationale="test only",
        ),
    )


@pytest.fixture(scope="module")
def supported_manifest(tmp_path_factory):
    definition = native_definition(tmp_path_factory.mktemp("study-support") / "data")
    return create_freeze(definition)


def test_all_three_engines_five_families_one_native_execution_each_pending_o(
    make_case,
    tmp_path,
    monkeypatch,
):
    import equiframe.pipeline as pipeline_module

    definition = pending_definition(make_case, tmp_path)
    manifest = create_freeze(definition)
    calls = Counter()
    execute = pipeline_module.execute

    def counted(plan, **kwargs):
        calls[plan.engine] += 1
        return execute(plan, **kwargs)

    monkeypatch.setattr(pipeline_module, "execute", counted)
    monkeypatch.setattr(ef, "fit_detectors", lambda *_a, **_k: pytest.fail("study fitted a forest"))
    result = run_study(manifest, registry=registry(), work_dir=tmp_path)
    assert result.complete and not result.scientific and not result.evaluation.scientific
    assert calls == {"pandas": 5, "polars": 5, "duckdb": 5}
    assert len(result.cases) == len(result.evaluation.records) == 15
    assert result.audit_before == result.audit_after == manifest.audit
    assert result.audit_before.blockers and result.audit_before.technical_ready
    assert all(
        c.record.oracle_state == "pending" and c.record.oracle_label is None for c in result.cases
    )
    assert all(c.record.m.decision == c.record.b.decision == "not_evaluable" for c in result.cases)
    assert len(result.tables.tables) == 6
    global_scope = result.evaluation.strata[0]
    assert global_scope.coverage.total_cases == 15
    assert global_scope.coverage.oracle_pending == 15
    assert global_scope.coverage.principal_case_ids == ()
    assert all(m.principal.f1.value is None for m in global_scope.methods)
    monkeypatch.setattr(pipeline_module, "execute", lambda *_a, **_k: pytest.fail("reader ran ETL"))
    assert read_study(tmp_path / result.study_id) == result


def test_supported_frozen_fixture_reuses_confirmed_labels_without_fitting(
    supported_manifest,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(ef, "fit_detectors", lambda *_a, **_k: pytest.fail("study fitted a forest"))
    result = run_study(supported_manifest, registry=registry(), work_dir=tmp_path)
    assert result.complete and not result.scientific
    assert all(
        c.record.oracle_state == "confirmed" and c.record.oracle_label == "normal"
        for c in result.cases
    )
    assert all(
        c.pipeline.detection.bundle_sha256 == c.record.detector_bundle_sha256 for c in result.cases
    )
    assert read_study(tmp_path / result.study_id) == result


@pytest.mark.parametrize("change", ["output", "implementation"])
def test_changed_replay_or_implementation_cannot_reuse_reviewed_label(
    supported_manifest,
    tmp_path,
    change,
):
    registered = ef.TransformationRegistry()
    registered.register(
        ef.DuckDBTransformation(
            "nulls_types",
            'SELECT * FROM "items" LIMIT 0' if change == "output" else 'SELECT * FROM "items"',
            "synthetic.v1" if change == "output" else "changed.implementation",
        )
    )
    result = run_study(supported_manifest, registry=registered, work_dir=tmp_path)
    assert not result.complete and result.exit_code == 3
    assert all(
        c.record.oracle_state == "not_evaluable" and c.record.oracle_label is None
        for c in result.cases
    )
    assert all(
        c.pipeline.execution.state == "completed" and c.record.r.complete for c in result.cases
    )
    assert read_study(tmp_path / result.study_id) == result


def test_reader_rejects_coherently_forged_equivalent_replay_for_different_output(
    supported_manifest,
    tmp_path,
    monkeypatch,
):
    import hashlib

    from equiframe.evidence import inventory

    from equiframe_benchmark.evaluation import evaluate_records
    from equiframe_benchmark.study import StudyCaseResult, StudyResult, _record
    from equiframe_benchmark.tables import EvaluationTable, TableExport, table_payloads

    registered = ef.TransformationRegistry()
    registered.register(
        ef.DuckDBTransformation(
            "nulls_types",
            "SELECT id || ':changed' AS id, amount, measurement FROM \"items\"",
            "synthetic.v1",
        )
    )
    result = run_study(supported_manifest, registry=registered, work_dir=tmp_path)
    directory = tmp_path / result.study_id
    original = result.cases[0]
    assert original.record.oracle_state == "not_evaluable"
    replay = original.output_replay
    assert replay is not None and replay.complete and replay.state == "different"
    assert replay.counts.left_rows == replay.counts.right_rows

    # Rewrite the full metadata chain without changing either captured table.
    # This passes all manifest/model/hash bindings but cannot change their rows.
    difference_path = local_path(replay.differences)
    difference_path.write_bytes(b"")
    forged_replay_data = replay.model_dump()
    forged_replay_data.update(
        state="equivalent",
        diagnostics=(),
        examples=(),
        counts={
            "left_rows": replay.counts.left_rows,
            "right_rows": replay.counts.right_rows,
            "matched_rows": replay.counts.left_rows,
            "difference_records": 0,
            "contract_violations": 0,
            "final": True,
        },
    )
    forged_replay_data["differences"].update(sha256=hashlib.sha256(b"").hexdigest(), size_bytes=0)
    forged_replay = ef.ComparisonResult.model_validate(forged_replay_data)
    (difference_path.parent / "comparison.json").write_text(
        forged_replay.model_dump_json(), encoding="utf-8"
    )
    definition = supported_manifest.definition.cases[0]
    scenario = next(
        s
        for s in supported_manifest.definition.catalog.scenarios
        if s.scenario_id == definition.scenario_id
    )
    model = next(m for m in supported_manifest.definition.models if m.family == scenario.family)
    record = _record(
        definition,
        scenario,
        original.record.group_id,
        model,
        original.pipeline,
        forged_replay,
        original.error,
        result.evaluation.config,
    )
    assert record.oracle_state == "confirmed" and record.oracle_label == "normal"
    forged_case = StudyCaseResult.model_validate(
        original.model_dump() | {"output_replay": forged_replay, "record": record}
    )
    (directory / "case-0/case.json").write_text(forged_case.model_dump_json(), encoding="utf-8")
    cases = (forged_case, *result.cases[1:])
    evaluation = evaluate_records(tuple(c.record for c in cases), result.evaluation.config)
    (directory / "evaluation.json").write_text(evaluation.model_dump_json(), encoding="utf-8")
    tables = []
    for filename, (payload, rows) in table_payloads(evaluation).items():
        (directory / "tables" / filename).write_bytes(payload)
        tables.append(
            EvaluationTable(
                filename=filename,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                rows=rows,
            )
        )
    exported = TableExport(
        evaluation_sha256=eb.digest(evaluation),
        scientific=evaluation.scientific,
        tables=tuple(tables),
    )
    (directory / "tables/tables.json").write_text(exported.model_dump_json(), encoding="utf-8")
    forged = StudyResult.model_validate(
        result.model_dump()
        | {
            "cases": cases,
            "evaluation": evaluation,
            "tables": exported,
            "evidence": tuple(item for item in inventory(directory) if item.path != "study.json"),
        }
    )
    (directory / "study.json").write_text(forged.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(ef, "execute", lambda *_a, **_k: pytest.fail("reader ran ETL"))
    with pytest.raises(ef.ArtifactIntegrityError, match="physically reproduced reviewed output"):
        read_study(directory)


def test_failed_native_cases_retained_all_components_unavailable(supported_manifest, tmp_path):
    registered = ef.TransformationRegistry()
    registered.register(
        ef.DuckDBTransformation("nulls_types", 'SELECT missing FROM "items"', "synthetic.v1")
    )
    result = run_study(supported_manifest, registry=registered, work_dir=tmp_path)
    assert not result.complete and len(result.cases) == len(supported_manifest.definition.cases)
    assert result.evaluation.strata[0].coverage.failed_case_ids
    for case in result.cases:
        assert case.record.failure_reason == "native_execution_unavailable"
        assert all(
            not d.complete and d.decision == "not_evaluable"
            for d in (case.record.r, case.record.m, case.record.b, case.record.h)
        )
        assert case.record.m_score is None and case.record.b_score is None
        assert case.record.oracle_label is None
    assert read_study(tmp_path / result.study_id) == result


def test_pre_cancelled_study_retains_scheduled_cases(supported_manifest, tmp_path):
    token = ef.CancellationToken()
    token.cancel()
    result = run_study(
        supported_manifest, registry=registry(), work_dir=tmp_path, cancellation=token
    )
    assert not result.complete and result.exit_code == 3
    assert len(result.cases) == len(supported_manifest.definition.cases)
    assert all(
        c.pipeline.cancelled and c.record.oracle_state == "not_evaluable" for c in result.cases
    )
    assert read_study(tmp_path / result.study_id) == result


def test_raised_pipeline_operation_keeps_failed_case_and_other_case(
    supported_manifest,
    tmp_path,
    monkeypatch,
):
    original = ef.run_pipeline
    calls = 0

    def interrupted(spec, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("synthetic pipeline publication failure")
        return original(spec, **kwargs)

    monkeypatch.setattr(ef, "run_pipeline", interrupted)
    result = run_study(supported_manifest, registry=registry(), work_dir=tmp_path)
    assert calls == len(supported_manifest.definition.cases) and not result.complete
    failed = result.cases[0]
    assert failed.pipeline is None and failed.record.pipeline_sha256 is None
    assert failed.error == failed.record.failure_reason == "pipeline_operation_failed:OSError"
    assert all(
        not decision.complete
        for decision in (failed.record.r, failed.record.m, failed.record.b, failed.record.h)
    )
    assert result.cases[1].pipeline.execution.state == "completed"
    assert read_study(tmp_path / result.study_id) == result


def test_after_audit_preserves_changed_source_as_failed_evidence(
    supported_manifest,
    tmp_path,
    monkeypatch,
):
    import hashlib

    from equiframe_benchmark.freeze import FrozenInput

    code = tmp_path / "declared-code.txt"
    code.write_bytes(b"original fixed source")
    frozen_input = FrozenInput(
        name="source",
        role="code",
        path=str(code.resolve()),
        sha256=hashlib.sha256(code.read_bytes()).hexdigest(),
        size_bytes=code.stat().st_size,
    )
    definition = supported_manifest.definition.model_copy(update={"files": (frozen_input,)})
    manifest = create_freeze(definition)
    original = ef.run_pipeline

    def change_after_pipeline(spec, **kwargs):
        returned = original(spec, **kwargs)
        code.write_bytes(b"changed after native callback")
        return returned

    monkeypatch.setattr(ef, "run_pipeline", change_after_pipeline)
    result = run_study(manifest, registry=registry(), work_dir=tmp_path)
    assert not result.complete and not result.scientific and result.exit_code == 3
    assert result.audit_before.technical_ready and not result.audit_after.technical_ready
    assert any("input:source" in blocker for blocker in result.audit_after.integrity_blockers)
    assert all(case.pipeline.execution.state == "completed" for case in result.cases)
    assert read_study(tmp_path / result.study_id) == result


def test_changed_before_freeze_rejected_without_launch(supported_manifest, tmp_path):
    definition = supported_manifest.definition
    pin = definition.environment[0].model_copy(update={"version": "wrong-version"})
    altered = definition.model_copy(update={"environment": (pin,)})
    # Existing manifest cannot silently be rewritten to match this changed definition.
    with pytest.raises(ValidationError, match="fingerprints"):
        run_study(
            supported_manifest.model_copy(update={"definition": altered}),
            registry=registry(),
            work_dir=tmp_path,
        )
    assert not list(tmp_path.glob("study_*"))


@pytest.mark.parametrize("change", ["table", "pipeline", "extra", "record"])
def test_deep_reader_rejects_corruption_extra_evidence_and_changed_records(
    supported_manifest,
    tmp_path,
    change,
):
    result = run_study(supported_manifest, registry=registry(), work_dir=tmp_path)
    directory = tmp_path / result.study_id
    if change == "table":
        (directory / "tables" / "metrics.csv").write_bytes(b"invented metric\n")
    elif change == "pipeline":
        local_path(result.cases[0].pipeline.execution.output.data).write_bytes(b"corrupt capture")
    elif change == "extra":
        (directory / "extra.json").write_bytes(b"{}")
    else:
        raw = json.loads((directory / "study.json").read_text(encoding="utf-8"))
        raw["cases"][0]["record"]["oracle_state"] = "pending"
        raw["cases"][0]["record"]["oracle_label"] = None
        (directory / "study.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises((ef.ArtifactIntegrityError, ValidationError)):
        read_study(directory)


def test_final_mode_cannot_bypass_pilot_scientific_blockers(supported_manifest, tmp_path):
    from equiframe_benchmark.freeze import audit_freeze

    final_definition = supported_manifest.definition.model_copy(update={"mode": "final"})
    audit = audit_freeze(final_definition)
    assert not audit.ready and audit.technical_ready and audit.blockers
    with pytest.raises(ValueError, match="blocked"):
        create_freeze(final_definition)
    assert not list(tmp_path.glob("study_*"))


def test_final_publication_failure_preserves_partial_evidence(
    supported_manifest,
    tmp_path,
    monkeypatch,
):
    import equiframe_benchmark.study as study

    publish = study.save_document

    def interrupted(document, path):
        if path.name == "study.json":
            raise OSError("synthetic publication failure")
        return publish(document, path)

    monkeypatch.setattr(study, "save_document", interrupted)
    with pytest.raises(OSError):
        run_study(supported_manifest, registry=registry(), work_dir=tmp_path)
    directory = next(tmp_path.glob("study_*"))
    assert not (directory / "study.json").exists()
    assert (directory / "evaluation.json").exists() and (directory / "tables/tables.json").exists()
