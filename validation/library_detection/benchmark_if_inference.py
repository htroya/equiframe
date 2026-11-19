"""Measure the same 200-tree synthetic detector on identified installed wheels."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import platform
import statistics
import time
from importlib.metadata import version
from pathlib import Path

from runtime_receipt import receipt

import equiframe as ef
from equiframe.detector_types import IsolationNode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--create-bundle", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity = receipt(args.wheel)
    spec = ef.ProfileSpec(
        family="nulls_types",
        features=(
            ef.ProfileFeature(
                name="null_rate", metric="tasa_nulos", table="result", columns=("x",)
            ),
        ),
    )
    spec_hash = ef.profile_spec_fingerprint(spec)

    def profile(count: int) -> ef.ProfileVector:
        return ef.ProfileVector(
            spec=spec,
            spec_sha256=spec_hash,
            observations=(
                ef.FeatureObservation(
                    name="null_rate",
                    numerator=count,
                    denominator=512,
                    state="available",
                    value=count / 512,
                ),
            ),
        )

    if args.create_bundle:
        fit = ef.fit_detectors(
            ef.NormalTrainingProfiles(
                purpose="normal_training",
                selection_manifest_sha256="a" * 64,
                profiles=tuple(profile(n) for n in range(1, 257)),
            ),
            spec=spec,
            config=ef.IsolationForestConfig(random_state=7, n_estimators=200, max_samples=256),
            support=ef.DetectorSupport(
                min_training_rows=2,
                min_calibration_rows=2,
                rationale="Synthetic review probe for the API wall-clock cost",
            ),
        )
        bundle = ef.calibrate_detectors(
            fit,
            ef.NormalCalibrationProfiles(
                purpose="normal_calibration",
                selection_manifest_sha256="b" * 64,
                profiles=tuple(profile(n) for n in range(2, 258, 4)),
            ),
            alpha="0.05",
        )
        ef.write_detector_bundle(bundle, args.bundle)
    bundle = ef.read_detector_bundle(args.bundle)
    probes = tuple(profile(n) for n in range(20, 36))
    measurements = {}
    for size in (1, 16):
        sample = probes[:size]
        reference = ef.detect_component(bundle, sample, method="isolation_forest")
        assert reference.complete and reference.rows == size
        timings = []
        for _ in range(7):
            start = time.perf_counter_ns()
            result = ef.detect_component(bundle, sample, method="isolation_forest")
            timings.append((time.perf_counter_ns() - start) / 1_000_000)
            assert result == reference
        measurements[size] = {
            "median_ms": statistics.median(timings),
            "raw_ms": timings,
            "result_sha256": hashlib.sha256(reference.model_dump_json().encode()).hexdigest(),
        }
    profiler = cProfile.Profile()
    with profiler:
        ef.detect_component(bundle, probes[:1], method="isolation_forest")
    validator = IsolationNode.consistent.__code__
    node_validations = next(
        entry.callcount for entry in profiler.getstats() if entry.code == validator
    )
    node_count = sum(len(tree.nodes) for tree in bundle.fit.m.trees)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "version": identity["version"],
                "wheel_sha256": identity["wheel_sha256"],
                "package_files_checked": identity["files_checked"],
                "host": platform.platform(),
                "python": platform.python_version(),
                "dependencies": {
                    name: version(name) for name in ("pydantic", "numpy", "scikit-learn")
                },
                "producer": bundle.fit.versions.equiframe,
                "bundle_sha256": ef.detector_fingerprint(bundle),
                "trees": len(bundle.fit.m.trees),
                "nodes": node_count,
                "node_validations_per_single_call": node_validations,
                "measurements": measurements,
            },
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
