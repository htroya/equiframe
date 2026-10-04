"""Benchmark utilities for Jhair: run ETL across engines, collect profiles,
apply Isolation Forest and MAD detectors, and compute metrics vs rule-based divergence."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[3]))

import equiframe as ef
from equiframe.detectors import (
    fit_detectors,
    calibrate_detectors,
    detect,
    combine_decisions,
)
from equiframe.detector_types import IsolationForestConfig, DetectorSupport
from equiframe.profile_types import ProfileSpec, ProfileVector, ProfileFeature
from equiframe.types import DecisionState
import pandas as pd

# ---------------------------------------------------------------------------
# Helper to run a single ETL case and capture its profile vector
# ---------------------------------------------------------------------------


def _run_single(
    case: ef.Case,
    engine: str,
    registry: ef.TransformationRegistry,
    work_dir: Path,
) -> Tuple[ef.ExecutionResult, ef.ProfileVector]:
    """Execute a case, return execution result and its profile vector."""
    plan = ef.ExecutionPlan(
        contract=case.contract,
        engine=engine,
        transformation_id=case.contract.family,
    )
    source = ef.LocalDataSource(
        {name: ef.ArrowInput(table) for name, table in case.inputs.items()}
    )
    result = ef.execute(plan, source, registry, work_dir=work_dir)
    if result.state != "completed":
        raise RuntimeError(f"Execution failed: {result.problem}")
    # Build a simple profile vector: row count and null rate for first output column
    # In a real benchmark we would define a rich ProfileSpec per family.
    output_table = ef.read_table(result.output.data)
    df = output_table.to_pandas()
    n_rows = len(df)
    # null rate across all columns (simple)
    null_rate = df.isnull().mean().mean() if n_rows > 0 else 0.0
    feature_rowcount = ProfileFeature(
        name="row_count",
        metric="filas",
        table="result",
    )
    feature_nullrate = ProfileFeature(
        name="null_rate",
        metric="tasa_nulos",
        table="result",
    )
    observations = (
        ef.FeatureObservation(
            name="row_count",
            state="available",
            value=n_rows,
            numerator=n_rows,
            denominator=1,
        ),
        ef.FeatureObservation(
            name="null_rate",
            state="available",
            value=null_rate,
            numerator=df.isnull().sum().sum(),
            denominator=df.size if df.size > 0 else 1,
        ),
    )
    spec = ProfileSpec(
        family=case.contract.family,
        features=(feature_rowcount, feature_nullrate),
    )
    vector = ef.ProfileVector(
        spec=spec,
        spec_sha256=ef.profile_spec_fingerprint(spec),
        observations=observations,
    )
    return result, vector


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(
    engines: List[str],
    families: List[str],
    work_dir: Path,
) -> Dict[str, Dict[str, List[ef.ExecutionResult]]]:
    """Run ETL benchmark for given engines and families.

    Returns a nested dict results[family][engine] -> list of ExecutionResult.
    Also writes profiles to work_dir/profiles/<family>/<engine>.json.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir = work_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # Load synthetic cases from examples (nulls_types, duplicates_order, joins, aggregations, dates)
    # Import the case generator from execute_native to reuse.
    from equiframe.examples.execute_native import cases, registry as make_registry

    all_cases = cases()
    # Filter by families if needed
    case_map = {c.contract.family: c for c in all_cases}
    selected_cases = [case_map[f] for f in families if f in case_map]

    reg = make_registry()

    results: Dict[str, Dict[str, List[ef.ExecutionResult]]] = {
        f: {e: [] for e in engines} for f in families
    }

    for case in selected_cases:
        family = case.contract.family
        for engine in engines:
            exec_res, profile_vec = _run_single(case, engine, reg, work_dir)
            results[family][engine].append(exec_res)
            # Save profile vector
            engine_dir = profiles_dir / family
            engine_dir.mkdir(parents=True, exist_ok=True)
            out_file = engine_dir / f"{engine}.json"
            ef.write_profile(
                ef.Profile(vector=profile_vec, schema_version="1.0"), out_file
            )
    return results


# ---------------------------------------------------------------------------
# Profile collection
# ---------------------------------------------------------------------------


def collect_profile_vectors(
    work_dir: Path, families: List[str], engines: List[str]
) -> List[Tuple[str, str, ef.ProfileVector]]:
    """Read all saved profile vectors and return list of (family, engine, vector)."""
    profiles_dir = work_dir / "profiles"
    vectors: List[Tuple[str, str, ef.ProfileVector]] = []
    for family in families:
        family_dir = profiles_dir / family
        if not family_dir.exists():
            continue
        for engine in engines:
            file_path = family_dir / f"{engine}.json"
            if not file_path.exists():
                continue
                # If missing, skip
            prof = ef.read_profile(file_path)
            vectors.append((family, engine, prof.vector))
    return vectors


# ---------------------------------------------------------------------------
# Detector fitting and calibration (Isolation Forest + MAD)
# ---------------------------------------------------------------------------


def fit_isolation_forest_mad(
    training_vectors: List[ef.ProfileVector],
    config: IsolationForestConfig | None = None,
    support: DetectorSupport | None = None,
) -> ef.DetectorBundle:
    """Fit Isolation Forest (M) and compute MAD (B) on training profile vectors.

    Returns a DetectorBundle ready for calibration/detection.
    """
    if config is None:
        config = IsolationForestConfig(random_state=42)
    if support is None:
        support = DetectorSupport(
            min_training_rows=2, min_calibration_rows=1, rationale="Benchmark support"
        )
    # Use the spec of the first vector as the detector spec
    spec = training_vectors[0].spec
    # Fit
    fit = ef.fit_detectors(
        ef.NormalTrainingProfiles(
            purpose="normal_training",
            selection_manifest_sha256="a" * 64,  # placeholder
            profiles=tuple(training_vectors),
        ),
        spec=spec,
        config=config,
        support=support,
    )
    # Calibrate with a simple hold-out: we reuse same data for demo; in practice split.
    calibration = ef.calibrate_detectors(
        fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration",
            selection_manifest_sha256="b" * 64,
            profiles=tuple(training_vectors),
        ),
        alpha="0.10",
    )
    return calibration


def detect_anomalies(
    bundle: ef.DetectorBundle, vectors: List[ef.ProfileVector]
) -> Tuple[List[DecisionState], List[DecisionState]]:
    """Run detection on vectors; return M (Isolation Forest) and B (MAD) decisions."""
    scores = ef.detect(bundle, tuple(vectors))
    m_decisions = [d.result.decision for d in scores.m]
    b_decisions = [d.result.decision for d in scores.b]
    return m_decisions, b_decisions


# ---------------------------------------------------------------------------
# Rule-based divergence detection (R)
# ---------------------------------------------------------------------------


def rule_divergence(results: Dict[str, Dict[str, List[ef.ExecutionResult]]]) -> Dict[
    str, List[bool]
]:
    """For each family-engine pair, determine if output diverges from others.

    Returns dict family -> list of booleans per engine (in same order as engines list)
    where True indicates divergence (i.e., at least one other engine gave different result).
    """
    divergence: Dict[str, List[bool]] = {}
    for family, engine_map in results.items():
        engines = list(engine_map.keys())
        # We'll compare pairwise; for simplicity consider divergence if any engine differs
        # from the first engine's result.
        baseline_results = engine_map[engines[0]]
        divergence_list = []
        for idx, eng in enumerate(engines):
            current = engine_map[eng]
            diverged = False
            # Compare each corresponding case (same order)
            for base_res, cur_res in zip(baseline_results, current):
                if base_res.output is None or cur_res.output is None:
                    diverged = True
                    break
                # Compare row counts and schema as simple proxy
                base_tbl = ef.read_table(base_res.output.data)
                cur_tbl = ef.read_table(cur_res.output.data)
                if base_tbl.row_count != cur_tbl.row_count:
                    diverged = True
                    break
                # Optional: compare a few values; we skip for brevity
            divergence_list.append(diverged)
        divergence[family] = divergence_list
    return divergence


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def compute_metrics(
    rule_diverge: Dict[str, List[bool]],
    model_decisions: List[DecisionState],
    engines: List[str],
) -> Dict[str, float]:
    """Compute precision, recall, f1 for model alerts vs rule divergence.

    model_decisions: list of decisions (alert/no_alert) per engine, in same order as engines list.
    We'll aggregate across families.
    """
    y_true = []  # rule divergence True -> divergence present (we treat as positive class)
    y_pred = []  # model alert == "alert"
    for family, diverge_list in rule_diverge.items():
        for idx, is_div in enumerate(diverge_list):
            y_true.append(is_div)
            # model decisions per family? We'll need to pass per-family model decisions.
            # For simplicity we assume model_decisions correspond to same ordering across families.
            # We'll adjust later.
    # Placeholder; implement properly when integrating.
    return {"precision": 0.0, "recall": 0.0, "f1": 0.0}


# ---------------------------------------------------------------------------
# Table output
# ---------------------------------------------------------------------------


def write_summary_tables(
    work_dir: Path,
    results: Dict[str, Dict[str, List[ef.ExecutionResult]]],
    profile_vectors: List[Tuple[str, str, ef.ProfileVector]],
    m_decisions: List[DecisionState],
    b_decisions: List[DecisionState],
    rule_diverge: Dict[str, List[bool]],
    engines: List[str],
) -> None:
    """Write CSV summaries for inspection."""
    summary_dir = work_dir / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    # Table 1: Profile vectors per family-engine
    rows = []
    for family, engine, vec in profile_vectors:
        for obs in vec.observations:
            rows.append(
                {
                    "family": family,
                    "engine": engine,
                    "feature": obs.name,
                    "value": obs.value,
                    "state": obs.state,
                }
            )
    if rows:
        pd.DataFrame(rows).to_csv(summary_dir / "profile_vectors.csv", index=False)

    # Table 2: Decisions
    dec_rows = []
    # We need to align decisions; for simplicity we'll assume ordering matches profile_vectors
    for (family, engine, _), m_dec, b_dec in zip(profile_vectors, m_decisions, b_decisions):
        dec_rows.append(
            {
                "family": family,
                "engine": engine,
                "isolation_forest": m_dec,
                "mad": b_dec,
                "rule_divergence": rule_diverge.get(family, [False])[engines.index(engine)]
                if family in rule_diverge
                else False,
            }
        )
    if dec_rows:
        pd.DataFrame(dec_rows).to_csv(summary_dir / "decisions.csv", index=False)

    # Table 3: Execution metrics (row counts, status)
    exec_rows = []
    for family, engine_map in results.items():
        for engine, exec_list in engine_map.items():
            for idx, exec_res in enumerate(exec_list):
                exec_rows.append(
                    {
                        "family": family,
                        "engine": engine,
                        "case_idx": idx,
                        "state": exec_res.state,
                        "row_count": exec_res.output.row_count if exec_res.output else 0,
                        "problem": exec_res.problem or "",
                    }
                )
    if exec_rows:
        pd.DataFrame(exec_rows).to_csv(summary_dir / "executions.csv", index=False)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Jhair benchmark for EquiFrame")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["pandas", "polars", "duckdb"],
        help="Engines to run",
    )
    parser.add_argument(
        "--families",
        nargs="+",
        default=["nulls_types", "duplicates_order", "joins", "aggregations", "dates"],
        help="ETL families to benchmark",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("benchmark_runs"),
        help="Directory to store outputs",
    )
    parser.add_argument(
        "--fit-only",
        action="store_true",
        help="Only fit detector, do not detect",
    )
    args = parser.parse_args()

    work_dir = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running benchmark with engines={args.engines}, families={args.families}")
    results = run_benchmark(args.engines, args.families, work_dir)

    vectors = collect_profile_vectors(work_dir, args.families, args.engines)
    print(f"Collected {len(vectors)} profile vectors")

    # Fit detector on all vectors (in practice split normal/anomaly)
    bundle = fit_isolation_forest_mad([v for _, _, v in vectors])
    print("Detector fitted and calibrated")

    if not args.fit_only:
        m_decisions, b_decisions = detect_anomalies(bundle, [v for _, _, v in vectors])
        print(f"Isolation Forest decisions: {m_decisions}")
        print(f"MAD decisions: {b_decisions}")

        # Rule-based divergence
        rule_diverge = rule_divergence(results)
        print(f"Rule divergence: {rule_diverge}")

        # Write summary tables
        write_summary_tables(
            work_dir,
            results,
            vectors,
            m_decisions,
            b_decisions,
            rule_diverge,
            args.engines,
        )
        print(f"Summary written to {work_dir / 'summary'}")
    else:
        # Still write basic tables
        write_summary_tables(
            work_dir,
            results,
            vectors,
            [],
            [],
            {},
            args.engines,
        )


if __name__ == "__main__":
    main()
