"""Warm public detector API costs on generated vectors; no accuracy claim."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import equiframe as ef


def vectors(dimensions: int, count: int, seed: int) -> tuple[ef.ProfileVector, ...]:
    spec = ef.ProfileSpec(
        family="nulls_types",
        features=tuple(
            ef.ProfileFeature(
                name=f"rate_{i}", metric="tasa_nulos", table="result", columns=(f"x_{i}",)
            )
            for i in range(dimensions)
        ),
    )
    rng = random.Random(seed)
    fingerprint = ef.profile_spec_fingerprint(spec)
    profiles = []
    for _ in range(count):
        numerators = [rng.randint(0, 1000) for _ in range(dimensions)]
        profiles.append(
            ef.ProfileVector(
                spec=spec,
                spec_sha256=fingerprint,
                observations=tuple(
                    ef.FeatureObservation(
                        name=f"rate_{i}",
                        state="available",
                        numerator=n,
                        denominator=1000,
                        value=n / 1000,
                    )
                    for i, n in enumerate(numerators)
                ),
            )
        )
    return tuple(profiles)


def run(output: Path) -> dict[str, Any]:
    if ef.__version__ != "0.14.0" or "site-packages" not in ef.__file__:
        raise RuntimeError("Use installed EquiFrame 0.14.0")
    if output.exists() or output.with_suffix(".protocol.json").exists():
        raise FileExistsError(output)
    plan: dict[str, Any] = {
        "protocol": "equiframe-component-api-cost-1",
        "dimensions": [4, 6],
        "training": 256,
        "calibration": 256,
        "batch_sizes": [1, 32, 512],
        "repetitions": 5,
        "forest_seed": 7,
        "n_estimators": 200,
        "max_samples": 256,
        "input": "Generated rate vectors, not native execution profiles; no efficacy labels",
        "scope": "Warm API wall clock including validation, preprocessing and provenance hashing",
        "exclusions": "Generation, execution, profiling, cold import, I/O and peak memory",
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output.with_suffix(".protocol.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )
    # Import/fit warm-up is outside the reported clocks. Both dimensions use
    # the same number of repetitions; all observations are retained.
    warm = vectors(4, 32, 1)
    ef.fit_detectors(
        ef.NormalTrainingProfiles(
            purpose="normal_training", selection_manifest_sha256="1" * 64, profiles=warm
        ),
        spec=warm[0].spec,
        config=ef.IsolationForestConfig(random_state=0, n_estimators=2, max_samples=32),
        support=ef.DetectorSupport(
            min_training_rows=32, min_calibration_rows=32, rationale="Import warm-up only"
        ),
    )
    experiments = []
    for dimensions in plan["dimensions"]:
        training = vectors(dimensions, 256, 101)
        calibration = vectors(dimensions, 256, 202)
        probes = vectors(dimensions, 512, 303)
        start = time.perf_counter()
        cpu_start = time.process_time()
        fit = ef.fit_detectors(
            ef.NormalTrainingProfiles(
                purpose="normal_training",
                selection_manifest_sha256="a" * 64,
                profiles=training,
            ),
            spec=training[0].spec,
            config=ef.IsolationForestConfig(random_state=7, n_estimators=200, max_samples=256),
            support=ef.DetectorSupport(
                min_training_rows=256,
                min_calibration_rows=256,
                rationale="Fixed generated-vector cost experiment",
            ),
        )
        fit_seconds = time.perf_counter() - start
        fit_cpu_seconds = time.process_time() - cpu_start
        start = time.perf_counter()
        cpu_start = time.process_time()
        bundle = ef.calibrate_detectors(
            fit,
            ef.NormalCalibrationProfiles(
                purpose="normal_calibration",
                selection_manifest_sha256="b" * 64,
                profiles=calibration,
            ),
            alpha="0.05",
        )
        calibration_seconds = time.perf_counter() - start
        calibration_cpu_seconds = time.process_time() - cpu_start
        frozen = ef.detector_fingerprint(bundle)
        batches = []
        for batch_size in plan["batch_sizes"]:
            batch = probes[:batch_size]
            calls: dict[str, Callable[[], Any]] = {
                "isolation_forest_only": partial(
                    ef.detect_component, bundle, batch, method="isolation_forest"
                ),
                "mad_only": partial(ef.detect_component, bundle, batch, method="mad"),
                "joint_m_b": partial(ef.detect, bundle, batch),
            }
            observations: dict[str, list[float]] = {name: [] for name in calls}
            cpu_observations: dict[str, list[float]] = {name: [] for name in calls}
            # Warm each public entry point on this batch before measurement.
            results = {name: call() for name, call in calls.items()}
            for _ in range(plan["repetitions"]):
                for name, call in calls.items():
                    start = time.perf_counter()
                    cpu_start = time.process_time()
                    result = call()
                    observations[name].append(time.perf_counter() - start)
                    cpu_observations[name].append(time.process_time() - cpu_start)
                    results[name] = result
            assert tuple(results["isolation_forest_only"].decisions) == results["joint_m_b"].m
            assert tuple(results["mad_only"].decisions) == results["joint_m_b"].b
            batches.append(
                {
                    "batch_size": batch_size,
                    "methods": {
                        name: {
                            "seconds": values,
                            "process_cpu_seconds": cpu_observations[name],
                            "median_process_cpu_seconds": statistics.median(cpu_observations[name]),
                            "median_batch_seconds": statistics.median(values),
                            "median_amortized_seconds_per_profile": statistics.median(values)
                            / batch_size,
                        }
                        for name, values in observations.items()
                    },
                }
            )
            print(f"cost dimensions{dimensions}, batch{batch_size}: completed", flush=True)
        if frozen != ef.detector_fingerprint(bundle):
            raise RuntimeError("Model changed during measurement")
        experiments.append(
            {
                "raw_features": dimensions,
                "matrix_columns": len(fit.preprocessor.columns),
                "joint_fit_seconds": fit_seconds,
                "joint_fit_cpu_seconds": fit_cpu_seconds,
                "joint_calibration_seconds": calibration_seconds,
                "joint_calibration_cpu_seconds": calibration_cpu_seconds,
                "model_sha256": frozen,
                "batches": batches,
            }
        )
    report = {
        "protocol": plan,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_processors": os.cpu_count(),
        "python": sys.version,
        "equiframe": ef.__version__,
        "dependencies": {
            name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn")
        },
        "experiments": experiments,
        "limitations": [
            "Generated-vector compute benchmark only; no end-to-end execution accuracy claim",
            "fit_detectors and calibrate_detectors measure M+B jointly; no M-only fit claim",
            "Component APIs include provenance work and differ from bare sklearn score_samples",
            "One host, one fitted model per dimension; five timing repetitions are not five models",
        ],
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
