"""Transitive dependency components precede deterministic whole-group assignment."""

import hashlib
import json
from collections import Counter
from fractions import Fraction

from equiframe_benchmark.models import Assignment, Catalog, Partition, SplitManifest, digest


def dependency_groups(catalog: Catalog) -> tuple[tuple[str, ...], ...]:
    catalog = Catalog.model_validate(catalog)
    # Exact shared input/expected bytes group cases even if a caller omitted a token.
    # Template, transformation, fragment and OCID relations still require declarations.
    remaining = {
        s.scenario_id: set(s.dependencies)
        | {"artifact:" + ref.sha256 for ref in (s.expected, *(i.artifact for i in s.inputs))}
        for s in catalog.scenarios
    }
    groups: list[tuple[str, ...]] = []
    while remaining:
        first = min(remaining)
        members = {first}
        dependencies = remaining.pop(first)
        changed = True
        while changed:
            changed = False
            for key in sorted(remaining):
                if dependencies & remaining[key]:
                    dependencies.update(remaining.pop(key))
                    members.add(key)
                    changed = True
        groups.append(tuple(sorted(members)))
    return tuple(sorted(groups))


def _group_id(group: tuple[str, ...]) -> str:
    return hashlib.sha256(json.dumps(group, separators=(",", ":")).encode()).hexdigest()


def make_splits(catalog: Catalog, *, seed: int, weights: tuple[int, int, int]) -> SplitManifest:
    # Validate configuration even when there are too few groups for all partitions.
    if type(seed) is not int or seed < 0 or len(weights) != 3:
        raise ValueError("nonnegative seed and three positive integer weights required")
    if any(type(w) is not int or w <= 0 for w in weights):
        raise ValueError("positive integer weights required")
    groups = sorted(
        dependency_groups(catalog),
        key=lambda g: hashlib.sha256(f"{seed}:{_group_id(g)}".encode()).digest(),
    )
    names: tuple[Partition, ...] = ("training", "calibration", "test")
    counts = [0, 0, 0]
    assignments: list[Assignment] = []
    for group in groups:
        index = min(range(3), key=lambda i: (Fraction(counts[i], weights[i]), i))
        counts[index] += len(group)
        assignments.extend(
            Assignment(scenario_id=s, group_id=_group_id(group), partition=names[index])
            for s in group
        )
    return SplitManifest(
        catalog_sha256=digest(catalog),
        seed=seed,
        weights=weights,
        assignments=tuple(sorted(assignments, key=lambda a: a.scenario_id)),
    )


def validate_splits(catalog: Catalog, manifest: SplitManifest) -> None:
    catalog = Catalog.model_validate(catalog)
    manifest = SplitManifest.model_validate(manifest)
    if manifest.catalog_sha256 != digest(catalog):
        raise ValueError("split catalog fingerprint mismatch")
    assignments = {a.scenario_id: a for a in manifest.assignments}
    if set(assignments) != {s.scenario_id for s in catalog.scenarios}:
        raise ValueError("split must cover exactly the catalog")
    for group in dependency_groups(catalog):
        if {assignments[s].group_id for s in group} != {_group_id(group)}:
            raise ValueError("incorrect dependency component")
        if len({assignments[s].partition for s in group}) != 1:
            raise ValueError("dependency leakage across partitions")
    if manifest != make_splits(catalog, seed=manifest.seed, weights=manifest.weights):
        raise ValueError("assignments differ from declared deterministic algorithm")


def split_counts(catalog: Catalog, manifest: SplitManifest) -> dict[str, dict[str, int]]:
    validate_splits(catalog, manifest)
    families = {s.scenario_id: s.family for s in catalog.scenarios}
    return {
        p: dict(Counter(families[a.scenario_id] for a in manifest.assignments if a.partition == p))
        for p in ("training", "calibration", "test")
    }
