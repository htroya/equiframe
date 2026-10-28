"""Run a synthetic technical pilot; every scientific review remains pending."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

import equiframe as ef
import pyarrow as pa
from equiframe._cli_support import write_failure

from equiframe_benchmark.fixtures import COMPARISON_POLICY, cases, expected_table, registry
from equiframe_benchmark.io import save_document
from equiframe_benchmark.models import Candidate, Catalog, InputBinding, Scenario, digest
from equiframe_benchmark.mutations import semantic_fault
from equiframe_benchmark.oracle import evaluate_oracle, review_packet
from equiframe_benchmark.splits import dependency_groups, make_splits, split_counts


def write_table(table: pa.Table, path: Path) -> ef.ArtifactRef:
    with path.open("xb") as stream, pa.ipc.new_file(stream, table.schema) as writer:
        writer.write_table(table)
    data = path.read_bytes()
    return ef.ArtifactRef(
        schema_version="1.0",
        uri=path.resolve().as_uri(),
        sha256=hashlib.sha256(data).hexdigest(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        size_bytes=len(data),
    )


def profile_spec(family: ef.Family) -> ef.ProfileSpec:
    extras: dict[ef.Family, tuple[ef.ProfileFeature, ...]] = {
        "nulls_types": (
            ef.ProfileFeature(
                name="missing_amount", metric="tasa_nulos", table="result", columns=("amount",)
            ),
            ef.ProfileFeature(
                name="nan_measurement", metric="tasa_nan", table="result", columns=("measurement",)
            ),
        ),
        "joins": (
            ef.ProfileFeature(
                name="expansion",
                metric="expansion_union",
                table="result",
                denominator_table="orders",
            ),
            ef.ProfileFeature(
                name="unmatched",
                metric="claves_sin_pareja",
                table="orders",
                columns=("product_id",),
                right_table="products",
                right_columns=("product_id",),
                null_matches="never",
            ),
        ),
        "duplicates_order": (
            ef.ProfileFeature(
                name="duplicates", metric="prop_duplicados", table="result", columns=("id",)
            ),
        ),
        "aggregations": (
            ef.ProfileFeature(
                name="output_input",
                metric="razon_salida_entrada",
                table="result",
                denominator_table="items",
            ),
        ),
        "dates": (
            ef.ProfileFeature(
                name="missing_day", metric="tasa_nulos", table="result", columns=("day",)
            ),
        ),
    }
    return ef.ProfileSpec(
        family=family,
        features=(
            ef.ProfileFeature(name="rows", metric="log_filas", table="result"),
            *extras[family],
        ),
    )


def run_pilot(directory: Path) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=False)
    scenarios = []
    fixtures = cases()
    registered = registry()
    rule_registry, rule_options = ef.default_rule_registry(), ef.RuleOptions()
    # Publish the complete technical catalog and R/spec hashes BEFORE candidates.
    for case in fixtures:
        family = case.contract.family
        root = directory / family
        root.mkdir()
        expected_ref = write_table(expected_table(case), root / "expected.arrow")
        inputs = tuple(
            InputBinding(name=name, artifact=write_table(t, root / (name + ".arrow")))
            for name, t in case.inputs.items()
        )
        template = "identity" if family in ("nulls_types", "duplicates_order") else family
        scenario = Scenario(
            scenario_id="synthetic." + family,
            family=family,
            dependencies=("template:" + template,),
            authors=("fixture-author",),
            inputs=inputs,
            transformation_revision="synthetic.v1",
            comparison=ef.ComparisonSpec(contract=case.contract, policy=COMPARISON_POLICY),
            rules_sha256=ef.rule_set_fingerprint(case.contract, rule_registry, rule_options),
            features_sha256=ef.profile_spec_fingerprint(profile_spec(family)),
            expected=expected_ref,
            expected_method="manually enumerated rows and physical schema",
            expected_authors=("fixture-author",),
        )
        scenarios.append(scenario)
        save_document(scenario, root / "scenario.json")
        (root / "profile-spec.json").write_text(
            profile_spec(family).model_dump_json(), encoding="utf-8"
        )
    catalog = Catalog(catalog_id="technical-pilot-1", synthetic=True, scenarios=tuple(scenarios))
    splits = make_splits(catalog, seed=6, weights=(3, 1, 2))
    save_document(catalog, directory / "catalog.json")
    save_document(splits, directory / "splits.json")
    candidate_count = profile_count = 0
    effects: dict[str, int] = {"changed": 0, "no_effect": 0}
    comparisons: dict[str, int] = {"equivalent": 0, "different": 0}
    for case, scenario in zip(fixtures, scenarios, strict=True):
        family = case.contract.family
        root = directory / family
        expected = expected_table(case)
        outputs: list[tuple[str, ef.ArtifactRef, Literal["control", "mutation"], str]] = []
        for engine in ("pandas", "polars", "duckdb"):
            pipeline = ef.run_pipeline(
                ef.PipelineSpec(
                    execution=ef.ExecutionPlan(
                        contract=case.contract, engine=engine, transformation_id=family
                    ),
                    profile=profile_spec(family),
                    rule_options=rule_options,
                ),
                source=ef.LocalDataSource({item.name: item.artifact for item in scenario.inputs}),
                registry=registered,
                rule_registry=rule_registry,
                work_dir=root,
            )
            run = pipeline.execution
            if run is None:
                raise RuntimeError("native pilot execution unavailable; inspect pipeline evidence")
            if run.state != "completed" or run.output is None:
                raise RuntimeError(f"native pilot failed: {family}/{engine}: {run.problem}")
            rules = pipeline.rules
            if rules is None:
                raise RuntimeError("pilot rules unavailable")
            if rules.rule_set_sha256 != scenario.rules_sha256:
                raise RuntimeError("rule revision changed after catalog publication")
            profile = pipeline.profile
            if profile is None or not profile.complete:
                raise RuntimeError("pilot profile incomplete")
            profile_count += 1
            outputs.append((engine, run.output.data, "control", "synthetic.v1"))
        outputs.extend(
            [
                (
                    "permuted",
                    write_table(
                        expected.take(list(reversed(range(expected.num_rows)))),
                        root / "permuted.arrow",
                    ),
                    "control",
                    "artifact.v1",
                ),
                (
                    "drop-row",
                    write_table(expected.slice(1), root / "drop-row.arrow"),
                    "mutation",
                    "artifact.v1",
                ),
                (
                    "no-effect",
                    write_table(expected, root / "no-effect.arrow"),
                    "mutation",
                    "artifact.v1",
                ),
                (
                    "semantic-fault",
                    write_table(semantic_fault(family, expected), root / "semantic-fault.arrow"),
                    "mutation",
                    "artifact.v1",
                ),
            ]
        )
        for name, output, kind, implementation in outputs:
            candidate = Candidate(
                candidate_id=family + "." + name,
                scenario_sha256=digest(scenario),
                output=output,
                authors=("fixture-author",),
                kind=kind,
                description=name,
                implementation=implementation,
                rules_sha256_before_candidate=scenario.rules_sha256,
            )
            # One neutral root for all families, with no candidate/engine names in paths.
            packet = review_packet(scenario, candidate, directory=directory / "review")
            result = evaluate_oracle(scenario, candidate, packet=packet, work_dir=root)
            if result.status != "pending":
                raise RuntimeError("pilot comparison failed; complete pilot cannot be published")
            if result.mutation_effect in effects:
                effects[result.mutation_effect] += 1
            comparisons[result.comparison.state] += 1
            save_document(candidate, root / (name + "-candidate.json"))
            save_document(result, root / (name + "-oracle.json"))
            candidate_count += 1
    summary: dict[str, object] = {
        "synthetic": True,
        "scenarios": len(scenarios),
        "groups": len(dependency_groups(catalog)),
        "candidates": candidate_count,
        "profiles": profile_count,
        "confirmed": 0,
        "pending": candidate_count,
        "effects": effects,
        "comparisons": comparisons,
        "partitions": split_counts(catalog, splits),
        "review_agreement": None,
        "review_agreement_denominator": 0,
        "scientific_freeze_ready": False,
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_pilot(args.output)
    except Exception as error:
        write_failure(error, code="pilot_operation_failed")
        raise SystemExit(1) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
