"""Check reviewed normal training, complete execution lineage and group membership."""

from collections.abc import Mapping
from typing import Literal

import equiframe as ef

from equiframe_benchmark.calibration_types import CalibrationManifest, CalibrationSelection
from equiframe_benchmark.models import (
    Candidate,
    Catalog,
    OracleResult,
    SplitManifest,
    digest,
    same_content,
)
from equiframe_benchmark.oracle import validate_assignment, validate_packet
from equiframe_benchmark.splits import validate_splits
from equiframe_benchmark.training_types import TrainingManifest, TrainingRecord, TrainingSelection


def _select_normal(
    catalog: Catalog,
    splits: SplitManifest,
    *,
    candidates: Mapping[str, Candidate],
    oracles: Mapping[str, OracleResult],
    profiles: Mapping[str, ef.ProfileResult],
    executions: Mapping[str, ef.ExecutionResult],
    partition: Literal["training", "calibration"],
) -> tuple[tuple[TrainingRecord, ...], tuple[ef.ProfileVector, ...]]:
    """Mappings use candidate IDs, allowing multiple native runs per scenario.

    Records must come from trusted producers; hashes do not authenticate people.
    Pending, divergent, other partitions, unrelated or duplicated evidence is rejected.
    """
    validate_splits(catalog, splits)
    if not profiles or not (set(profiles) == set(candidates) == set(oracles) == set(executions)):
        raise ValueError("nonempty matching candidate, oracle, execution and profile sets required")
    scenarios = {digest(s): s for s in catalog.scenarios}
    assignments = {a.scenario_id: a for a in splits.assignments}
    vectors = []
    records = []
    for key in sorted(profiles):
        candidate = Candidate.model_validate(candidates[key])
        oracle = OracleResult.model_validate(oracles[key])
        profile = ef.ProfileResult.model_validate(profiles[key])
        execution = ef.ExecutionResult.model_validate(executions[key])
        scenario = scenarios.get(candidate.scenario_sha256)
        if scenario is None or assignments[scenario.scenario_id].partition != partition:
            raise ValueError("only " + partition + " scenarios may enter this normal selection")
        if key != candidate.candidate_id:
            raise ValueError("selection keys must be candidate IDs")
        if oracle.status != "confirmed" or oracle.label != "normal" or oracle.assignment is None:
            raise ValueError("confirmed normal oracle required")
        if oracle.candidate_kind != candidate.kind:
            raise ValueError("candidate kind mismatch")
        validate_packet(scenario, candidate, oracle.packet)
        validate_assignment(scenario, candidate, oracle.packet, oracle.assignment)
        if oracle.scenario_sha256 != digest(scenario) or oracle.candidate_sha256 != digest(
            candidate
        ):
            raise ValueError("oracle provenance mismatch")
        if execution.state != "completed" or execution.output is None:
            raise ValueError("completed native execution required")
        if execution.output.data != candidate.output:
            raise ValueError("candidate must be the exact execution output")
        if execution.implementation_version != candidate.implementation:
            raise ValueError("implementation revision mismatch")
        if execution.plan.contract != scenario.comparison.contract:
            raise ValueError("execution contract mismatch")
        sources = {item.name: item.data for item in execution.inputs}
        if set(sources) != {item.name for item in scenario.inputs} or any(
            not same_content(item.artifact, sources[item.name]) for item in scenario.inputs
        ):
            raise ValueError("execution input provenance mismatch")
        metadata = profile.metadata
        if (
            metadata.execution_sha256 != digest(execution)
            or metadata.run_id != execution.run_id
            or metadata.execution_id != execution.execution_id
            or metadata.contract_sha256 != execution.contract_sha256
        ):
            raise ValueError("profile execution provenance mismatch")
        artifacts = tuple(
            ref
            for table in (*execution.inputs, execution.output)
            for ref in (table.data, *((table.index,) if table.index else ()))
        )
        if metadata.artifacts != artifacts or not profile.complete:
            raise ValueError("profile must capture the exact reviewed execution completely")
        if (
            profile.vector.spec_sha256 != scenario.features_sha256
            or profile.vector.spec.family != scenario.family
        ):
            raise ValueError("feature revision mismatch")
        for ref in artifacts:
            ef.read_table(ref)
        ef.read_table(oracle.packet.expected)
        ef.read_table(oracle.packet.candidate)
        # Verify the comparison evidence file too, not just metadata fingerprints.
        difference_count = sum(1 for _ in ef.iter_differences(oracle.comparison.differences))
        if difference_count != oracle.comparison.counts.difference_records:
            raise ValueError("oracle difference inventory disagrees with recorded counts")
        vectors.append(profile.vector)
        records.append(
            TrainingRecord(
                scenario_id=scenario.scenario_id,
                candidate_id=key,
                group_id=assignments[scenario.scenario_id].group_id,
                candidate_sha256=digest(candidate),
                oracle_sha256=digest(oracle),
                profile_sha256=digest(profile),
                vector_sha256=digest(profile.vector),
                execution_sha256=digest(execution),
            )
        )
    if len({v.spec_sha256 for v in vectors}) != 1:
        raise ValueError("normal selection requires a single family and feature definition")
    return tuple(records), tuple(vectors)


def select_normal_training(
    catalog: Catalog,
    splits: SplitManifest,
    *,
    candidates: Mapping[str, Candidate],
    oracles: Mapping[str, OracleResult],
    profiles: Mapping[str, ef.ProfileResult],
    executions: Mapping[str, ef.ExecutionResult],
) -> TrainingSelection:
    """Select reviewed normal training only; all maps use the same candidate IDs."""
    records, vectors = _select_normal(
        catalog,
        splits,
        candidates=candidates,
        oracles=oracles,
        profiles=profiles,
        executions=executions,
        partition="training",
    )
    manifest = TrainingManifest(
        catalog_sha256=digest(catalog), splits_sha256=digest(splits), records=records
    )
    training = ef.NormalTrainingProfiles(
        purpose="normal_training",
        selection_manifest_sha256=digest(manifest),
        profiles=tuple(vectors),
    )
    return TrainingSelection(manifest=manifest, training=training)


def select_normal_calibration(
    catalog: Catalog,
    splits: SplitManifest,
    *,
    candidates: Mapping[str, Candidate],
    oracles: Mapping[str, OracleResult],
    profiles: Mapping[str, ef.ProfileResult],
    executions: Mapping[str, ef.ExecutionResult],
) -> CalibrationSelection:
    """Verify reviewed normal calibration with the same lineage checks as training."""
    records, vectors = _select_normal(
        catalog,
        splits,
        candidates=candidates,
        oracles=oracles,
        profiles=profiles,
        executions=executions,
        partition="calibration",
    )
    manifest = CalibrationManifest(
        catalog_sha256=digest(catalog), splits_sha256=digest(splits), records=records
    )
    calibration = ef.NormalCalibrationProfiles(
        purpose="normal_calibration", selection_manifest_sha256=digest(manifest), profiles=vectors
    )
    return CalibrationSelection(manifest=manifest, calibration=calibration)
