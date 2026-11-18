"""Audit real prepared profiles and exercise rejection of unreviewed selection.

This verifies technical gates. It never assigns labels, approves normality or
counts raw awards, repeated engine runs or distinct vectors as accredited N_fit.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import equiframe as ef
import equiframe_benchmark as eb

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ("nulls_types", "joins", "aggregations")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "owned_helper_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model(kind, value):
    return kind.model_validate_json(
        json.dumps(value, ensure_ascii=True, allow_nan=False)
    )


def audit(packet, verification, verification_sha256, binding_path, output):
    require(sys.flags.isolated, "isolated_installed_interpreter_required")
    require(ef.__version__ == eb.__version__ == "0.12.0a14", "a14_required")
    files = helper("owned_thesis_files", ROOT / "tools/thesis_packet_io.py")
    protected = helper(
        "owned_thesis_inputs", ROOT / "tools/revalidate_root_contexts.py"
    )
    protected.require_ordinary_parents(packet.absolute())
    packet = files.root_path(packet)
    inventory_before = files.verify_inventory(packet)
    protected.require_ordinary_parents(output.absolute().parent)
    require(
        not output.exists() and not output.absolute().is_relative_to(packet),
        "new_external_output_required",
    )
    raw, checked = protected.bounded_json(verification)
    require(
        hashlib.sha256(raw).hexdigest() == verification_sha256,
        "verification_identity_mismatch",
    )
    manifest_raw = files.read_bytes(packet, "preparation-manifest.json", files.MAX_JSON)
    manifest = files.read_json(packet, "preparation-manifest.json")
    require(
        checked.get("schema") == "equiframe.thesis-packet-verification.v1"
        and checked.get("technical_preparation") == "PASS"
        and checked.get("preparation_manifest_sha256")
        == hashlib.sha256(manifest_raw).hexdigest()
        and checked.get("scientific_ready") is False,
        "verified_pending_packet_required",
    )
    require(
        manifest.get("scientific_ready") is False
        and manifest.get("confirmed_normal_profiles") == 0
        and manifest.get("candidate") == "0.12.0a14",
        "pending_preparation_required",
    )
    _, binding = protected.bounded_json(binding_path)
    binder = helper(
        "owned_thesis_binding", ROOT / "packages/equiframe/tools/compatibility_probe.py"
    )
    runtime = binder.runtime_binding(binding)
    catalog = model(eb.Catalog, files.read_json(packet, "catalog.json"))
    splits = model(eb.SplitManifest, files.read_json(packet, "splits.json"))
    eb.validate_splits(catalog, splits)
    require(
        eb.digest(catalog) == manifest["catalog_sha256"]
        and eb.digest(splits) == manifest["splits_sha256"],
        "catalog_binding_mismatch",
    )
    scenarios = {s.scenario_id: s for s in catalog.scenarios}
    assignments = {a.scenario_id: a for a in splits.assignments}
    records = manifest.get("records")
    require(
        isinstance(records, list)
        and 0 < len(records) <= 4608
        and len(records) == checked["native_executions"],
        "invalid_record_inventory",
    )
    prepared = []
    candidate_ids = set()
    for entry in records:
        data = files.read_json(packet, entry["file"])
        candidate = model(eb.Candidate, data["candidate"])
        oracle = model(eb.OracleResult, data["oracle"])
        profile = model(ef.ProfileResult, data["profile"])
        execution = model(ef.ExecutionResult, data["execution"])
        scenario = scenarios[data["scenario"]]
        require(candidate.candidate_id not in candidate_ids, "reused_candidate_id")
        candidate_ids.add(candidate.candidate_id)
        require(
            candidate.scenario_sha256 == eb.digest(scenario)
            and profile.complete
            and execution.state == "completed"
            and execution.output is not None
            and candidate.output == execution.output.data
            and profile.metadata.execution_sha256 == eb.digest(execution)
            and profile.vector.spec.family == scenario.family,
            "selection_lineage_mismatch",
        )
        require(
            oracle.status == "pending" and oracle.label is None and not oracle.reviews,
            "unreviewed_packet_required",
        )
        prepared.append((scenario, candidate, oracle, profile, execution))
    scope = []
    gate_checks = []
    for family in FAMILIES:
        selected = [
            row
            for row in prepared
            if row[0].family == family and row[1].kind == "control"
        ]
        require(bool(selected), "family_controls_missing")
        maps = {
            "candidates": {c.candidate_id: c for _, c, _, _, _ in selected},
            "oracles": {c.candidate_id: o for _, c, o, _, _ in selected},
            "profiles": {c.candidate_id: p for _, c, _, p, _ in selected},
            "executions": {c.candidate_id: e for _, c, _, _, e in selected},
        }
        for partition, select in (
            ("training", eb.select_normal_training),
            ("calibration", eb.select_normal_calibration),
        ):
            first_scenario = min(selected, key=lambda row: row[1].candidate_id)[0]
            expected = (
                "confirmed normal oracle required"
                if assignments[first_scenario.scenario_id].partition == partition
                else "only " + partition + " scenarios may enter this normal selection"
            )
            try:
                select(catalog, splits, **maps)
            except ValueError as failure:
                require(str(failure) == expected, "unexpected_selection_rejection")
                gate_checks.append(
                    {
                        "family": family,
                        "partition": partition,
                        "status": "EXPECTED_REJECTION",
                        "reason": expected,
                    }
                )
            else:
                raise ValueError("unreviewed_selection_was_admitted")
        scope.append(
            {
                "family": family,
                "native_control_executions": len(selected),
                "controls_by_engine": dict(
                    Counter(e.plan.engine for _, _, _, _, e in selected)
                ),
                "scenario_counts_by_partition": dict(
                    Counter(
                        assignments[s.scenario_id].partition
                        for s in catalog.scenarios
                        if s.family == family
                    )
                ),
                "distinct_execution_documents": len(
                    {eb.digest(e) for _, _, _, _, e in selected}
                ),
                "distinct_numeric_vectors": len(
                    {eb.digest(p.vector) for _, _, _, p, _ in selected}
                ),
                "confirmed_normal_profiles": 0,
                "n_fit_accredited": 0,
                "minimum_accredited_training_required": 10001,
            }
        )
    require(
        files.verify_inventory(packet) == inventory_before,
        "packet_changed_during_audit",
    )
    result = {
        "schema": "equiframe.thesis-selection-audit.v1",
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "candidate": ef.__version__,
        "core_wheel_sha256": binding["wheel_sha256"],
        "runtime_origin": runtime["origin"],
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "preparation_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "verification_sha256": verification_sha256,
        "catalog_sha256": eb.digest(catalog),
        "splits_sha256": eb.digest(splits),
        "transitive_dependency_groups": len(eb.dependency_groups(catalog)),
        "family_support": scope,
        "gate_checks": gate_checks,
        "technical_selection_gates": "PASS",
        "labels_assigned": 0,
        "models_fitted": 0,
        "scientific_ready": False,
        "packet_unchanged": True,
        "pending": [
            "Approved protocol/cohort and two blind reviews with conflict resolution",
            "Enough dependency components for calibration and held-out test",
            "More than 10000 confirmed effective normal training profiles per model/family",
            "Actual fit, external calibration and paired final evaluation",
        ],
    }
    output.mkdir()
    with (output / "selection-audit.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--verification-sha256", required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(
            args.packet,
            args.verification,
            args.verification_sha256,
            args.binding,
            args.output,
        )
    except (ValueError, OSError, KeyError, TypeError) as failure:
        parser.exit(2, "Selection audit failed: " + type(failure).__name__ + "\n")
    print(
        json.dumps(
            {
                "technical_selection_gates": result["technical_selection_gates"],
                "gate_checks": len(result["gate_checks"]),
                "scientific_ready": False,
            }
        )
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
