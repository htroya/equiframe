"""Native pilot seal, study, six CSV and portable regeneration; no scientific labels."""

import argparse
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import equiframe as ef

import equiframe_benchmark as eb
from equiframe_benchmark.evaluation import FAMILIES
from equiframe_benchmark.fixtures import registry
from equiframe_benchmark.freeze import DECISIONS
from equiframe_benchmark.pilot import profile_spec, run_pilot
from equiframe_benchmark.study import read_study, run_study
from equiframe_benchmark.study_bundle import bundle_study, reproduce_study_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    root = parser.parse_args().output.absolute()
    root.mkdir(parents=True, exist_ok=False)
    pilot = root / "pilot"
    summary = run_pilot(pilot)
    assert summary["confirmed"] == 0 and summary["pending"] == 35
    catalog = eb.load_document(eb.Catalog, pilot / "catalog.json")
    splits = eb.load_document(eb.SplitManifest, pilot / "splits.json")
    test_ids = {a.scenario_id for a in splits.assignments if a.partition == "test"}
    cases = []
    for scenario in catalog.scenarios:
        if scenario.scenario_id not in test_ids:
            continue
        for engine in ("pandas", "polars", "duckdb"):
            family = scenario.family
            candidate = eb.load_document(
                eb.Candidate, pilot / family / (engine + "-candidate.json")
            )
            oracle = eb.load_document(eb.OracleResult, pilot / family / (engine + "-oracle.json"))
            cases.append(
                eb.TestCaseDefinition(
                    case_id=family + "." + engine,
                    scenario_id=scenario.scenario_id,
                    candidate=candidate,
                    oracle=oracle,
                    pipeline=ef.PipelineSpec(
                        execution=ef.ExecutionPlan(
                            contract=scenario.comparison.contract,
                            engine=engine,
                            transformation_id=family,
                        ),
                        profile=profile_spec(family),
                        comparison_policy=scenario.comparison.policy,
                        comparison_reference="expected",
                    ),
                    migration="native-independent:" + engine,
                )
            )
    definition = eb.FreezeDefinition(
        study_id="technical-step10",
        revision=1,
        mode="pilot",
        catalog=catalog,
        splits=splits,
        cases=tuple(cases),
        models=tuple(
            eb.FrozenFamilyModel(
                family=family,
                profile=profile_spec(family),
                reason="No independent normal labels; no scientific detector trained",
            )
            for family in FAMILIES
        ),
        selection_evidence=(),
        decisions=tuple(
            eb.ExperimentalDecision(
                name=name,
                status="pending",
                value=None,
                rationale="Technical conformance only; scientific protocol remains unresolved",
            )
            for name in DECISIONS
        ),
        files=(),
        environment=(
            eb.EnvironmentPin(package="python", version=platform.python_version()),
            eb.EnvironmentPin(package="equiframe", version=version("equiframe")),
        ),
        code_revision="synthetic.v1",
        evaluation=eb.EvaluationConfig(
            mode="pilot",
            freeze_sha256=None,
            bootstrap=eb.BootstrapPlan(
                seed=41,
                repetitions=20,
                min_groups=3,
                independence_supported=False,
                rationale="Synthetic template groups, no inferential independence claim",
            ),
            expected_migrations=tuple(
                "native-independent:" + e for e in ("pandas", "polars", "duckdb")
            ),
        ),
        cost_protocol=eb.CostProtocol(
            seed=41,
            cache_policy="warm cache; no flush",
            threads=1,
            concurrent_loads="local technical runner",
            controls_rationale="Declared engineering protocol; no H3 scientific conclusion",
        ),
    )
    freeze = eb.create_freeze(definition)
    assert freeze.audit.technical_ready and not freeze.audit.scientific_ready
    eb.save_document(freeze, root / "freeze.json")
    result = run_study(freeze, registry=registry(), work_dir=root)
    study = root / result.study_id
    assert read_study(study) == result
    assert not result.evaluation.scientific
    assert len(result.evaluation.records) == len(cases) > 0
    assert all(
        r.oracle_state == "pending" and r.oracle_label is None for r in result.evaluation.records
    )
    portable = root / "portable"
    bundle_study(study, output=portable)
    manifest_sha256 = hashlib.sha256((portable / "bundle.json").read_bytes()).hexdigest()
    receipt = reproduce_study_bundle(portable, expected_sha256=manifest_sha256)
    assert receipt.status == "reproduced" and all(c.identical for c in receipt.components)
    print(
        json.dumps(
            {
                "study_id": result.study_id,
                "native_test_cases": len(cases),
                "scientific": False,
                "confirmed": 0,
                "tables": len(result.tables.tables),
                "bundle_sha256": manifest_sha256,
                "table_regeneration": receipt.status,
                "external_repetition_pending": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
