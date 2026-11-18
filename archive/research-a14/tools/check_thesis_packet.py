"""Verify a proposed SERCOP packet; scientific acceptance remains a separate gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SOURCE_SHA256 = "80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3"
FAMILIES = ("nulls_types", "joins", "aggregations")


def packet_io():
    path = Path(__file__).with_name("thesis_packet_io.py")
    specification = importlib.util.spec_from_file_location("thesis_packet_io", path)
    if specification is None or specification.loader is None:
        raise ValueError("packet_reader_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def model_from_json(model, value):
    # Preserve strict JSON validation: Python-mode strict tuples reject JSON arrays.
    return model.model_validate_json(
        json.dumps(value, ensure_ascii=True, allow_nan=False)
    )


def check_semantics(checks):
    values = []
    for check_result in checks:
        value = check_result.model_dump(mode="json")
        if value["findings"] is not None:
            # Each replay gets a fresh directory; content hash/size/format must match.
            value["findings"].pop("uri")
        values.append(value)
    return values


def check(root, output):
    import equiframe as ef
    import equiframe_benchmark as eb
    from equiframe_benchmark.oracle import validate_packet

    files = packet_io()
    require = files.require
    root = files.root_path(root)
    require(
        not output.exists() and not output.resolve().is_relative_to(root),
        "new_external_output_required",
    )
    verified_inventory = files.verify_inventory(root)
    manifest_bytes = files.read_bytes(root, "preparation-manifest.json", files.MAX_JSON)
    manifest = files.read_json(root, "preparation-manifest.json")
    require(
        manifest.get("schema") == "equiframe.sercop-experiment-preparation.v1"
        and manifest.get("source_sha256") == SOURCE_SHA256,
        "packet_source_identity_mismatch",
    )
    require(
        manifest.get("candidate") == ef.__version__ == eb.__version__ == "0.12.0a14",
        "candidate_identity_mismatch",
    )
    require(
        manifest.get("scientific_ready") is False
        and manifest.get("human_review_complete") is False
        and type(manifest.get("confirmed_normal_profiles")) is int
        and manifest["confirmed_normal_profiles"] == 0,
        "unconfirmed_scientific_claim",
    )
    require(
        manifest.get("n_fit_accredited_per_family")
        == {family: 0 for family in FAMILIES}
        and all(
            type(value) is int
            for value in manifest["n_fit_accredited_per_family"].values()
        ),
        "unconfirmed_training_claim",
    )
    catalog = model_from_json(eb.Catalog, files.read_json(root, "catalog.json"))
    splits = model_from_json(eb.SplitManifest, files.read_json(root, "splits.json"))
    require(
        catalog.synthetic is False
        and eb.digest(catalog) == manifest["catalog_sha256"]
        and eb.digest(splits) == manifest["splits_sha256"],
        "catalog_identity_mismatch",
    )
    eb.validate_splits(catalog, splits)
    require(
        len(eb.dependency_groups(catalog)) == manifest["dependency_groups"]
        and eb.split_counts(catalog, splits) == manifest["split_counts"],
        "partition_receipt_mismatch",
    )
    proposal = files.read_json(root, "protocol-proposal.json")
    require(
        proposal.get("status") == "PROPOSED"
        and proposal.get("normality_confirmed") is False
        and proposal.get("human_decisions") is None
        and proposal.get("scientific_results") is None,
        "proposal_misrepresented_as_accepted",
    )
    require(
        proposal["catalog_sha256"] == eb.digest(catalog)
        and proposal["splits_sha256"] == eb.digest(splits)
        and proposal["source_sha256"] == SOURCE_SHA256,
        "proposal_binding_mismatch",
    )
    declared = manifest["records"]
    require(
        isinstance(declared, list)
        and 0 < len(declared) <= 4608
        and len(declared)
        == manifest["native_executions"]
        == manifest["pending_human_packets"],
        "invalid_record_inventory",
    )
    scenarios = {scenario.scenario_id: scenario for scenario in catalog.scenarios}
    require(
        {scenario.family for scenario in catalog.scenarios} == set(FAMILIES),
        "family_scope_mismatch",
    )
    verified_refs = {}

    def references(value):
        if isinstance(value, dict):
            if {"uri", "format", "sha256", "size_bytes"} <= set(value):
                reference = model_from_json(ef.ArtifactRef, value)
                identity = (reference.sha256, reference.size_bytes)
                if reference.uri not in verified_refs:
                    files.verify_reference(root, reference)
                    verified_refs[reference.uri] = identity
                require(
                    verified_refs[reference.uri] == identity,
                    "conflicting_artifact_identity",
                )
            for child in value.values():
                references(child)
        elif isinstance(value, list):
            for child in value:
                references(child)

    references(catalog.model_dump(mode="json"))
    prepared = []
    tokens, paths, executions, candidates = set(), set(), set(), set()
    cells = Counter()
    for entry in declared:
        require(
            isinstance(entry, dict)
            and set(entry) == {"file", "sha256", "case_token"}
            and isinstance(entry["case_token"], str)
            and re.fullmatch(r"[0-9a-f]{32}", entry["case_token"]) is not None,
            "invalid_case_entry",
        )
        require(
            entry["file"].startswith("coordinator/")
            and entry["file"].endswith("/preparation.json")
            and entry["file"] not in paths
            and entry["case_token"] not in tokens,
            "duplicate_or_misplaced_record",
        )
        paths.add(entry["file"])
        tokens.add(entry["case_token"])
        require(
            files.file_entry(root, entry["file"])["sha256"] == entry["sha256"],
            "case_hash_mismatch",
        )
        record = files.read_json(root, entry["file"])
        references(record)
        scenario = scenarios[record["scenario"]]
        pipeline = model_from_json(ef.PipelineResult, record["pipeline"])
        candidate = model_from_json(eb.Candidate, record["candidate"])
        oracle = model_from_json(eb.OracleResult, record["oracle"])
        require(
            pipeline.execution is not None
            and pipeline.execution.state == "completed"
            and pipeline.execution.output is not None
            and pipeline.profile is not None
            and pipeline.profile.complete
            and pipeline.rules is not None,
            "execution_or_components_unavailable",
        )
        execution, profile = pipeline.execution, pipeline.profile
        require(
            execution.model_dump(mode="json") == record["execution"]
            and profile.model_dump(mode="json") == record["profile"]
            and pipeline.rules.model_dump(mode="json") == record["rules"]
            and pipeline.comparison is not None
            and pipeline.comparison.model_dump(mode="json") == record["comparison"],
            "duplicated_receipts_disagree",
        )
        require(
            execution.plan.contract == scenario.comparison.contract
            and profile.vector.spec_sha256 == scenario.features_sha256
            and pipeline.rules.rule_set_sha256 == scenario.rules_sha256
            and candidate.output == execution.output.data,
            "native_lineage_mismatch",
        )
        require(
            candidate.candidate_id not in candidates
            and execution.execution_id not in executions,
            "reused_native_execution",
        )
        candidates.add(candidate.candidate_id)
        executions.add(execution.execution_id)
        validate_packet(scenario, candidate, oracle.packet)
        require(
            oracle.packet.case_token == entry["case_token"]
            and oracle.scenario_sha256 == eb.digest(scenario)
            and oracle.candidate_sha256 == eb.digest(candidate)
            and oracle.packet_sha256 == eb.digest(oracle.packet)
            and oracle.status == "pending"
            and oracle.label is None
            and oracle.assignment is None
            and not oracle.reviews
            and oracle.resolution is None,
            "pending_review_evidence_mismatch",
        )
        saved_packet = model_from_json(
            eb.ReviewPacket,
            files.read_json(root, "reviewers/" + entry["case_token"] + "/packet.json"),
        )
        require(
            saved_packet == oracle.packet
            and set(saved_packet.model_dump())
            == {
                "schema_version",
                "case_token",
                "scenario_sha256",
                "comparison",
                "inputs",
                "expected",
                "candidate",
            },
            "blind_packet_mismatch",
        )
        state = "equivalent" if candidate.kind == "control" else "different"
        require(
            pipeline.comparison.state == state
            and oracle.comparison.state == state
            and pipeline.comparison.reference
            == oracle.comparison.reference
            == "expected"
            and pipeline.comparison.spec == scenario.comparison,
            "expected_comparison_mismatch",
        )
        cell = (scenario.scenario_id, candidate.kind, execution.plan.engine)
        cells[cell] += 1
        prepared.append((scenario, candidate, oracle, pipeline))
    expected_cells = {
        (scenario.scenario_id, variant, engine)
        for scenario in catalog.scenarios
        for variant in ("control", "mutation")
        for engine in ("pandas", "polars", "duckdb")
    }
    require(
        set(cells) == expected_cells and all(count == 1 for count in cells.values()),
        "native_matrix_incomplete",
    )
    for reviewer in ("A", "B"):
        rows = list(
            csv.DictReader(
                io.StringIO(
                    files.read_bytes(
                        root, f"reviewer-{reviewer}.csv", files.MAX_JSON
                    ).decode("utf-8")
                )
            )
        )
        require(
            len(rows) == len(tokens) and {row["case_token"] for row in rows} == tokens,
            "review_worksheet_incomplete",
        )
        packet_hashes = {
            oracle.packet.case_token: eb.digest(oracle.packet)
            for _, _, oracle, _ in prepared
        }
        require(
            all(
                row["packet_sha256"] == packet_hashes[row["case_token"]]
                and all(
                    row[field] == ""
                    for field in (
                        "reviewer",
                        "assigned_at",
                        "label",
                        "reason",
                        "recorded_at",
                    )
                )
                for row in rows
            ),
            "review_worksheet_contains_unconfirmed_decisions",
        )
    output.mkdir(parents=True)
    outcomes = Counter()
    for index, (scenario, candidate, oracle, pipeline) in enumerate(prepared):
        execution, profile = pipeline.execution, pipeline.profile
        recalculated = ef.profile_execution(
            execution,
            spec=profile.vector.spec,
            options=profile.options,
            conversions=profile.metadata.conversion_receipts,
            work_dir=output / str(index) / "profile",
        )
        require(
            recalculated.complete
            and recalculated.vector == profile.vector
            and recalculated.metadata.execution_sha256
            == profile.metadata.execution_sha256,
            "profile_recalculation_mismatch",
        )
        rules = ef.evaluate_rules(
            execution,
            options=pipeline.rules.options,
            work_dir=output / str(index) / "rules",
        )
        require(
            rules.rule_set_sha256 == scenario.rules_sha256
            and rules.decision == pipeline.rules.decision
            and rules.coverage == pipeline.rules.coverage
            and check_semantics(rules.rules) == check_semantics(pipeline.rules.rules)
            and check_semantics(rules.preconditions)
            == check_semantics(pipeline.rules.preconditions),
            "rule_recalculation_mismatch",
        )
        comparison = ef.compare(
            candidate.output,
            scenario.expected,
            contract=scenario.comparison.contract,
            policy=scenario.comparison.policy,
            reference="expected",
            work_dir=output / str(index) / "comparison",
        )
        require(
            comparison.state == oracle.comparison.state
            and comparison.complete
            and comparison.counts == oracle.comparison.counts,
            "full_recomparison_mismatch",
        )
        outcomes[comparison.state] += 1
    require(
        files.verify_inventory(root) == verified_inventory,
        "packet_changed_during_verification",
    )
    result = {
        "schema": "equiframe.thesis-packet-verification.v1",
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "candidate": ef.__version__,
        "preparation_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "integrity_manifest_sha256": hashlib.sha256(
            files.read_bytes(root, "integrity-manifest.json", files.MAX_JSON)
        ).hexdigest(),
        "technical_preparation": "PASS",
        "source_reparsed_by_this_verifier": False,
        "native_transformations_rerun_by_this_verifier": False,
        "file_count": len(verified_inventory["files"]),
        "catalog_scenarios": len(catalog.scenarios),
        "native_executions": len(prepared),
        "profiles_rules_and_comparisons_recalculated": len(prepared),
        "comparison_counts": dict(outcomes),
        "pending_review_packets": len(tokens),
        "dependency_groups": len(eb.dependency_groups(catalog)),
        "split_counts": eb.split_counts(catalog, splits),
        "n_fit_accredited_per_family": {family: 0 for family in FAMILIES},
        "scientific_ready": False,
        "scientific_blockers": [
            "Protocol/cohort/normality not approved",
            "Two independent blind reviews and conflict resolution pending",
            "Calibration and test partition support must be resolved without breaking dependency groups",
            "Confirmed training support and final models/evaluation absent",
        ],
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with (output / "verification.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.packet, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, "Packet verification failed: " + type(error).__name__ + "\n")
    print(
        json.dumps(
            {
                "technical_preparation": result["technical_preparation"],
                "native_executions": result["native_executions"],
                "scientific_ready": False,
                "receipt": str(args.output / "verification.json"),
            }
        )
    )
    parser.exit(3, "Technical preparation verified; scientific acceptance pending.\n")


if __name__ == "__main__":
    main()
