"""Every author, review and corpus here is a TEST FIXTURE, never a real approval."""

import hashlib
import math
import platform
from decimal import Decimal
from pathlib import Path

import equiframe as ef
import pyarrow as pa
import pytest
from conftest import reviews
from equiframe.local import local_path
from equiframe.profile_types import profile_digest

import equiframe_benchmark as eb
import equiframe_benchmark.freeze as freeze_module
from equiframe_benchmark.costs import CostProtocol
from equiframe_benchmark.evaluation import FAMILIES, BootstrapPlan, EvaluationConfig
from equiframe_benchmark.fixtures import COMPARISON_POLICY, cases, registry
from equiframe_benchmark.freeze import (
    DECISIONS,
    EnvironmentPin,
    ExperimentalDecision,
    FreezeDefinition,
    FreezeManifest,
    FrozenFamilyModel,
    FrozenInput,
    SelectionEvidence,
    audit_freeze,
    create_freeze,
    read_freeze,
)
from equiframe_benchmark.freeze import (
    TestCaseDefinition as FrozenCase,
)
from equiframe_benchmark.pilot import profile_spec, write_table


def native_definition(directory: Path) -> FreezeDefinition:
    """Six genuinely captured, isolated groups with explicitly fictional reviews."""
    directory.mkdir()
    contract = cases()[0].contract
    spec = profile_spec("nulls_types")
    scenarios, candidates, executions, profiles, oracles = [], {}, {}, {}, {}
    for number in range(1, 7):
        root = directory / str(number)
        root.mkdir()
        table = pa.table(
            {
                "id": pa.array([f"case:{number}:{i}" for i in range(number)]),
                "amount": pa.array([Decimal("10.20")] * number, type=pa.decimal128(18, 2)),
                "measurement": pa.array([float(number)] * number),
            }
        )
        input_ref = write_table(table, root / "input.arrow")
        expected = write_table(table, root / "expected.arrow")
        scenario = eb.Scenario(
            scenario_id=f"fixture.{number}",
            family="nulls_types",
            dependencies=(f"isolated-fixture:{number}",),
            authors=("fixture-author",),
            inputs=(eb.InputBinding(name="items", artifact=input_ref),),
            transformation_revision="synthetic.v1",
            comparison=ef.ComparisonSpec(contract=contract, policy=COMPARISON_POLICY),
            rules_sha256=ef.rule_set_fingerprint(
                contract, ef.default_rule_registry(), ef.RuleOptions()
            ),
            features_sha256=ef.profile_spec_fingerprint(spec),
            expected=expected,
            expected_method="explicit synthetic test rows",
            expected_authors=("fixture-author",),
        )
        execution = ef.execute(
            ef.ExecutionPlan(contract=contract, engine="duckdb", transformation_id="nulls_types"),
            source=ef.LocalDataSource({"items": input_ref}),
            registry=registry(),
            work_dir=root,
        )
        assert execution.state == "completed" and execution.output is not None
        candidate = eb.Candidate(
            candidate_id=f"fixture.candidate.{number}",
            scenario_sha256=eb.digest(scenario),
            output=execution.output.data,
            authors=("fixture-author",),
            kind="control",
            description="synthetic control, not a real experimental case",
            implementation="synthetic.v1",
            rules_sha256_before_candidate=scenario.rules_sha256,
        )
        packet = eb.review_packet(scenario, candidate, directory=root / "review")
        assignment = eb.ReviewAssignment(
            packet_sha256=eb.digest(packet),
            reviewers=("test-reviewer-a", "test-reviewer-b"),
            arbitrator="test-arbitrator",
            assigned_at="2026-10-01T00:00:00Z",
        )
        oracle = eb.evaluate_oracle(
            scenario,
            candidate,
            packet=packet,
            assignment=assignment,
            reviews=reviews(packet),
            work_dir=root,
        )
        assert oracle.status == "confirmed" and oracle.label == "normal"
        scenarios.append(scenario)
        key = candidate.candidate_id
        candidates[key], executions[key], oracles[key] = candidate, execution, oracle
        profiles[key] = ef.profile_execution(execution, spec=spec, work_dir=root)
    catalog = eb.Catalog(
        catalog_id="freeze-test-fixtures", synthetic=True, scenarios=tuple(scenarios)
    )
    splits = eb.make_splits(catalog, seed=7, weights=(3, 1, 2))
    partitions = {a.scenario_id: a.partition for a in splits.assignments}
    by_hash = {eb.digest(s): s for s in scenarios}

    def selected(partition):
        names = [
            k
            for k, c in candidates.items()
            if partitions[by_hash[c.scenario_sha256].scenario_id] == partition
        ]
        selector = (
            eb.select_normal_training if partition == "training" else eb.select_normal_calibration
        )
        return selector(
            catalog,
            splits,
            candidates={k: candidates[k] for k in names},
            oracles={k: oracles[k] for k in names},
            profiles={k: profiles[k] for k in names},
            executions={k: executions[k] for k in names},
        )

    training, calibration = selected("training"), selected("calibration")
    support = eb.audit_detector_selections(
        training,
        calibration,
        min_training_groups=2,
        min_calibration_groups=1,
        rationale="test support only; not a scientific independence or power claim",
    )
    fit = ef.fit_detectors(
        training.training,
        spec=spec,
        config=ef.IsolationForestConfig(random_state=12, n_estimators=2, max_samples=3),
        support=ef.DetectorSupport(
            min_training_rows=2, min_calibration_rows=1, rationale="test only"
        ),
    )
    bundle = ef.calibrate_detectors(fit, calibration.calibration, alpha="0.25")
    models = (
        FrozenFamilyModel(
            family="nulls_types",
            profile=spec,
            training=training,
            calibration=calibration,
            audit=support,
            bundle=bundle,
        ),
        *(
            FrozenFamilyModel(
                family=f, profile=profile_spec(f), reason="unsupported synthetic fixture family"
            )
            for f in FAMILIES[1:]
        ),
    )
    case_defs, evidence = [], []
    for key, candidate in candidates.items():
        scenario = by_hash[candidate.scenario_sha256]
        if partitions[scenario.scenario_id] == "test":
            case_defs.append(
                FrozenCase(
                    case_id="case:" + key,
                    scenario_id=scenario.scenario_id,
                    candidate=candidate,
                    oracle=oracles[key],
                    migration="synthetic identity",
                    pipeline=ef.PipelineSpec(
                        execution=executions[key].plan,
                        profile=spec,
                        comparison_policy=scenario.comparison.policy,
                        comparison_reference="expected",
                    ),
                )
            )
        else:
            evidence.append(
                SelectionEvidence(
                    candidate=candidate,
                    oracle=oracles[key],
                    execution=executions[key],
                    profile=profiles[key],
                )
            )
    return FreezeDefinition(
        study_id="freeze-test-fixtures",
        revision=1,
        mode="pilot",
        catalog=catalog,
        splits=splits,
        cases=tuple(case_defs),
        models=models,
        selection_evidence=tuple(evidence),
        decisions=tuple(
            ExperimentalDecision(
                name=n, status="pending", value=None, rationale="unresolved synthetic test decision"
            )
            for n in DECISIONS
        ),
        files=(),
        environment=(EnvironmentPin(package="python", version=platform.python_version()),),
        code_revision="test-fixture",
        evaluation=EvaluationConfig(
            mode="pilot",
            freeze_sha256=None,
            bootstrap=BootstrapPlan(
                seed=23,
                repetitions=5,
                min_groups=2,
                independence_supported=False,
                rationale="synthetic smoke test; no inference claim",
            ),
        ),
        cost_protocol=CostProtocol(
            seed=23,
            cache_policy="warm test cache",
            threads=1,
            concurrent_loads="test process only",
            controls_rationale="test fixture controls only",
        ),
    )


@pytest.fixture(scope="module")
def frozen_definition(tmp_path_factory):
    return native_definition(tmp_path_factory.mktemp("freeze-fixtures") / "data")


def replace_model(definition, model):
    return definition.model_copy(update={"models": (model, *definition.models[1:])})


def assert_blocked(definition, tmp_path, component):
    result = audit_freeze(definition, work_dir=tmp_path)
    assert not result.ready and not result.technical_ready
    assert any(component in b for b in result.integrity_blockers), result.integrity_blockers


@pytest.fixture(scope="module")
def sealed_manifest(frozen_definition, tmp_path_factory):
    return create_freeze(frozen_definition, work_dir=tmp_path_factory.mktemp("sealed-fixture"))


def test_pilot_seals_integrity_preserves_scientific_blockers(
    frozen_definition, tmp_path, monkeypatch
):
    # Freeze must only use already fitted forests; this guard would reject any retraining.
    monkeypatch.setattr(ef, "fit_detectors", lambda *_a, **_k: pytest.fail("freeze trained ML"))
    frozen = create_freeze(frozen_definition, work_dir=tmp_path)
    assert frozen.audit.ready and frozen.audit.technical_ready
    assert not frozen.audit.scientific_ready
    assert "scientific:synthetic_catalog" in frozen.audit.blockers
    assert len(frozen.audit.counts) == 15
    counts = {(c.family, c.partition): c for c in frozen.audit.counts}
    assert counts[("nulls_types", "training")].scenarios == 3
    assert counts[("nulls_types", "calibration")].scenarios == 1
    assert counts[("nulls_types", "test")].confirmed == 2
    model = frozen_definition.models[0]
    assert frozen.model_bindings[0].bundle_sha256 == ef.detector_fingerprint(model.bundle)
    path = tmp_path / "freeze.json"
    eb.save_document(frozen, path)
    assert (
        read_freeze(
            path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), work_dir=tmp_path
        )
        == frozen
    )
    assert not any(p.name.startswith("equiframe-freeze-") for p in tmp_path.iterdir())


def test_final_rejects_pilot_claims_without_converting_pending(frozen_definition, tmp_path):
    definition = frozen_definition.model_copy(update={"mode": "final"})
    result = audit_freeze(definition, work_dir=tmp_path)
    assert result.technical_ready and not result.ready
    assert "scientific:pending_decision:source_license" in result.blockers
    with pytest.raises(ValueError, match="freeze is blocked"):
        create_freeze(definition, work_dir=tmp_path)
    assert all(d.status == "pending" and d.value is None for d in frozen_definition.decisions)


def test_pending_cases_remain_counted_and_cannot_train(frozen_definition, tmp_path):
    pending = tuple(c.model_copy(update={"oracle": None}) for c in frozen_definition.cases)
    definition = frozen_definition.model_copy(update={"cases": pending})
    result = audit_freeze(definition, work_dir=tmp_path)
    assert result.ready
    assert sum(c.pending for c in result.counts) == 2
    assert sum(c.confirmed for c in result.counts) == 0
    assert "scientific:no_confirmed_test_case" in result.blockers


@pytest.mark.parametrize(
    "fault", ("definition", "catalog", "splits", "protocol", "bindings", "counts", "blockers")
)
def test_manifest_cannot_accept_rebound_hashes_or_dropped_blockers(sealed_manifest, fault):
    frozen = sealed_manifest
    update = {}
    if fault in ("definition", "catalog", "splits"):
        update[fault + "_sha256"] = "f" * 64
    elif fault == "protocol":
        update["evaluation_protocol_sha256"] = "f" * 64
    elif fault == "bindings":
        update["model_bindings"] = (
            frozen.model_bindings[0].model_copy(update={"bundle_sha256": "f" * 64}),
            *frozen.model_bindings[1:],
        )
    else:
        audit = frozen.audit
        if fault == "counts":
            counts = (audit.counts[0].model_copy(update={"scenarios": 99}), *audit.counts[1:])
            audit = audit.model_copy(update={"counts": counts})
        else:
            audit = audit.model_copy(update={"blockers": ()})
        update["audit"] = audit
    with pytest.raises(ValueError):
        FreezeManifest.model_validate(frozen.model_copy(update=update))


@pytest.mark.parametrize(
    "fault",
    (
        "matrix",
        "alpha",
        "calibration",
        "groups",
        "wrong_selection_group",
        "test_leakage",
        "profile",
        "mad",
    ),
)
def test_model_integrity_recomputed_from_selection_evidence(frozen_definition, tmp_path, fault):
    definition, model = frozen_definition, frozen_definition.models[0]
    bundle = model.bundle
    if fault == "matrix":
        model = model.model_copy(
            update={
                "bundle": bundle.model_copy(
                    update={
                        "fit": bundle.fit.model_copy(update={"training_matrix_sha256": "f" * 64})
                    }
                )
            }
        )
    elif fault == "mad":
        changed = bundle.fit.b.model_copy(
            update={"medians": tuple(v + 1 for v in bundle.fit.b.medians)}
        )
        fit = bundle.fit.model_copy(update={"b": changed})
        # Even a recalibrated forged baseline must not bypass the training matrix.
        altered = ef.calibrate_detectors(fit, model.calibration.calibration, alpha="0.25")
        model = model.model_copy(update={"bundle": altered})
    elif fault == "alpha":
        decisions = tuple(
            d.model_copy(update={"status": "resolved", "value": "0.20"}) if d.name == "alpha" else d
            for d in definition.decisions
        )
        definition = definition.model_copy(update={"decisions": decisions})
    elif fault == "calibration":
        model = model.model_copy(
            update={"bundle": bundle.model_copy(update={"calibration_matrix_sha256": "f" * 64})}
        )
    elif fault == "groups":
        model = model.model_copy(
            update={"audit": model.audit.model_copy(update={"training_groups": 99})}
        )
    elif fault in ("wrong_selection_group", "test_leakage"):
        selection = model.training
        record = selection.manifest.records[0]
        if fault == "wrong_selection_group":
            changed = record.model_copy(update={"group_id": "f" * 64})
        else:
            changed = record.model_copy(
                update={"candidate_id": definition.cases[0].candidate.candidate_id}
            )
        manifest = selection.manifest.model_copy(
            update={"records": (changed, *selection.manifest.records[1:])}
        )
        selection = selection.model_copy(
            update={
                "manifest": manifest,
                "training": selection.training.model_copy(
                    update={"selection_manifest_sha256": eb.digest(manifest)}
                ),
            }
        )
        model = model.model_copy(update={"training": selection})
    elif fault == "profile":
        # A valid but false log-row count, with every declared fingerprint updated.
        item = definition.selection_evidence[0]
        vector = item.profile.vector
        row = vector.observations[0].model_copy(update={"numerator": 123, "value": math.log1p(123)})
        profile = item.profile.model_copy(
            update={
                "vector": vector.model_copy(
                    update={"observations": (row, *vector.observations[1:])}
                )
            }
        )
        item = item.model_copy(update={"profile": profile})
        definition = definition.model_copy(
            update={"selection_evidence": (item, *definition.selection_evidence[1:])}
        )
    assert_blocked(
        replace_model(definition, model), tmp_path, "model:" if fault != "profile" else "selection:"
    )


@pytest.mark.parametrize("fault", ("partition", "rules", "policy", "reference", "metadata"))
def test_cases_reject_wrong_partition_configuration_and_capture_metadata(
    frozen_definition, tmp_path, fault
):
    definition = frozen_definition
    case = definition.cases[0]
    if fault == "partition":
        scenario_hash = definition.selection_evidence[0].candidate.scenario_sha256
        scenario_id = next(
            s.scenario_id for s in definition.catalog.scenarios if eb.digest(s) == scenario_hash
        )
        case = case.model_copy(update={"scenario_id": scenario_id})
    elif fault == "rules":
        case = case.model_copy(
            update={
                "pipeline": case.pipeline.model_copy(
                    update={"rule_options": ef.RuleOptions(max_rows=1)}
                )
            }
        )
    elif fault == "policy":
        policy = case.pipeline.comparison_policy.model_copy(update={"physical_types": "exact"})
        case = case.model_copy(
            update={"pipeline": case.pipeline.model_copy(update={"comparison_policy": policy})}
        )
    elif fault == "reference":
        case = case.model_copy(
            update={"pipeline": case.pipeline.model_copy(update={"comparison_reference": "peer"})}
        )
    else:
        item = definition.selection_evidence[0]
        first = item.execution.inputs[0]
        execution = item.execution.model_copy(
            update={"inputs": (first.model_copy(update={"row_count": 100}),)}
        )
        item = item.model_copy(update={"execution": execution})
        definition = definition.model_copy(
            update={"selection_evidence": (item, *definition.selection_evidence[1:])}
        )
    definition = definition.model_copy(update={"cases": (case, *definition.cases[1:])})
    assert_blocked(definition, tmp_path, "selection:" if fault == "metadata" else "case:")


def test_verified_originals_and_corrupt_frozen_source_are_rechecked(frozen_definition, tmp_path):
    source = tmp_path / "corpus.csv"
    source.write_bytes(b"declared fixture corpus\n")
    frozen_input = FrozenInput(
        name="fixture-corpus",
        role="corpus",
        path=str(source.absolute()),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        size_bytes=source.stat().st_size,
    )
    definition = frozen_definition.model_copy(update={"files": (frozen_input,)})
    frozen = create_freeze(definition, work_dir=tmp_path)
    path = tmp_path / "freeze.json"
    eb.save_document(frozen, path)
    source.write_bytes(b"altered fixture corpus\n")
    with pytest.raises(ValueError, match="no longer matches"):
        read_freeze(path, work_dir=tmp_path)
    assert_blocked(definition, tmp_path, "input:fixture-corpus")


def test_corrupt_arrow_rejects_metadata_only_seal(frozen_definition, tmp_path):
    ref = frozen_definition.cases[0].candidate.output
    source = local_path(ref)
    original = source.read_bytes()
    try:
        source.write_bytes(b"corrupt")
        assert_blocked(frozen_definition, tmp_path, "case:")
    finally:
        source.write_bytes(original)


def test_corrupt_original_oracle_capture_is_rejected(frozen_definition, tmp_path):
    source = local_path(frozen_definition.cases[0].oracle.comparison.left.data)
    original = source.read_bytes()
    try:
        source.write_bytes(b"corrupted original oracle capture")
        assert_blocked(frozen_definition, tmp_path, "case:")
    finally:
        source.write_bytes(original)


def test_confirmed_oracle_is_rechecked_against_logical_contents(frozen_definition, tmp_path):
    case = frozen_definition.cases[0]
    table = ef.read_table(case.candidate.output)
    amounts = pa.array([Decimal("999.99")] * table.num_rows, type=pa.decimal128(18, 2))
    ref = write_table(table.set_column(1, "amount", amounts), tmp_path / "altered.arrow")
    candidate = case.candidate.model_copy(update={"output": ref})
    old = case.oracle
    packet = old.packet.model_copy(update={"candidate": ref})
    fingerprint = eb.digest(packet)
    comparison = old.comparison.model_copy(
        update={"left": old.comparison.left.model_copy(update={"data": ref})}
    )
    claimed = old.model_copy(
        update={
            "candidate_sha256": eb.digest(candidate),
            "packet": packet,
            "packet_sha256": fingerprint,
            "assignment": old.assignment.model_copy(update={"packet_sha256": fingerprint}),
            "reviews": tuple(
                r.model_copy(update={"packet_sha256": fingerprint}) for r in old.reviews
            ),
            "comparison": comparison,
        }
    )
    # All declared hashes, counts and agreement are internally consistent; bytes differ.
    claimed = eb.OracleResult.model_validate(claimed)
    assert claimed.status == "confirmed" and claimed.comparison.state == "equivalent"
    changed = case.model_copy(update={"candidate": candidate, "oracle": claimed})
    assert_blocked(
        frozen_definition.model_copy(update={"cases": (changed, *frozen_definition.cases[1:])}),
        tmp_path,
        "case:",
    )


def test_source_mutation_during_verification_is_not_sealed(
    frozen_definition, tmp_path, monkeypatch
):
    source = tmp_path / "metadata.txt"
    source.write_bytes(b"before verification")
    item = FrozenInput(
        name="source",
        role="code",
        path=str(source.absolute()),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        size_bytes=source.stat().st_size,
    )
    definition = frozen_definition.model_copy(update={"files": (item,)})
    original = ef.profile_execution

    def mutate(*args, **kwargs):
        observed = original(*args, **kwargs)
        source.write_bytes(b"changed during verification")
        return observed

    monkeypatch.setattr(ef, "profile_execution", mutate)
    assert_blocked(definition, tmp_path, "sources_unchanged")


def test_freeze_file_is_rechecked_after_physical_audit(sealed_manifest, tmp_path, monkeypatch):
    path = tmp_path / "freeze.json"
    eb.save_document(sealed_manifest, path)
    original = freeze_module.audit_freeze

    def mutate(*args, **kwargs):
        observed = original(*args, **kwargs)
        path.write_bytes(b"null")
        return observed

    monkeypatch.setattr(freeze_module, "audit_freeze", mutate)
    with pytest.raises(ValueError, match="document changed"):
        read_freeze(path, work_dir=tmp_path)


@pytest.mark.parametrize(
    "path", ("C:/data/frozen.arrow", "C:\\data\\frozen.arrow", "/var/data/frozen.arrow")
)
def test_absolute_path_metadata_is_portable_without_resolving_sources(path):
    item = FrozenInput(
        name="foreign-source", role="corpus", path=path, sha256="f" * 64, size_bytes=0
    )
    assert FrozenInput.model_validate_json(item.model_dump_json()) == item


def test_environment_pin_is_checked_against_actual_runtime(frozen_definition, tmp_path):
    pin = EnvironmentPin(package="pyarrow", version="0.0.0")
    definition = frozen_definition.model_copy(update={"environment": (pin,)})
    assert_blocked(definition, tmp_path, "environment:pyarrow")


@pytest.mark.parametrize("scope", ("family", "migration", "final_all_families"))
def test_evaluation_scope_cannot_omit_scheduled_cases(frozen_definition, tmp_path, scope):
    definition = frozen_definition
    if scope == "family":
        config = definition.evaluation.model_copy(update={"expected_families": ("dates",)})
    elif scope == "migration":
        config = definition.evaluation.model_copy(
            update={"expected_migrations": ("foreign migration",)}
        )
    else:
        config = definition.evaluation.model_copy(update={"expected_families": ("nulls_types",)})
        definition = definition.model_copy(update={"mode": "final"})
    definition = definition.model_copy(update={"evaluation": config})
    assert_blocked(definition, tmp_path, "evaluation_scope")


def test_declarative_metadata_has_no_io_and_rejects_missing_decisions(
    frozen_definition, monkeypatch
):
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("model opened a file"))
    assert FreezeDefinition.model_validate(frozen_definition) == frozen_definition
    with pytest.raises(ValueError, match="twelve"):
        FreezeDefinition.model_validate(frozen_definition.model_copy(update={"decisions": ()}))
    with pytest.raises(ValueError, match="absolute"):
        FrozenInput(name="relative", role="code", path="code.py", sha256="f" * 64, size_bytes=0)
    with pytest.raises(ValueError, match="unsupported"):
        FrozenFamilyModel(family="dates", profile=profile_spec("dates"))


def test_reader_rejects_duplicate_json_and_external_hash_mismatch(frozen_definition, tmp_path):
    frozen = create_freeze(frozen_definition, work_dir=tmp_path)
    path = tmp_path / "freeze.json"
    eb.save_document(frozen, path)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        read_freeze(path, expected_sha256="f" * 64, work_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    path.write_text(
        '{"schema_version":"1.0",' + text[1:],
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        read_freeze(path, work_dir=tmp_path)


def test_preprocessor_fingerprint_is_native_not_metadata_digest(frozen_definition):
    fit = frozen_definition.models[0].bundle.fit
    matrix = ef.transform_profiles(
        fit.preprocessor, frozen_definition.models[0].training.training.profiles
    )
    assert fit.training_matrix_sha256 == profile_digest(matrix.model_dump(mode="json"))


def test_local_symlink_input_is_rejected(frozen_definition, tmp_path):
    source, link = tmp_path / "source.txt", tmp_path / "link.txt"
    source.write_bytes(b"fixture only")
    try:
        link.symlink_to(source)
    except OSError as exc:
        pytest.skip(f"host cannot create symlinks: {exc}")
    item = FrozenInput(
        name="link",
        role="code",
        path=str(link.absolute()),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        size_bytes=source.stat().st_size,
    )
    assert_blocked(frozen_definition.model_copy(update={"files": (item,)}), tmp_path, "input:link")
