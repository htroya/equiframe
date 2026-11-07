#!/usr/bin/env python3
"""Independent expected outcomes for paired optional benchmark profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("base", "engines", "ml", "resources", "all"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import equiframe as ef
    import equiframe_benchmark as eb
    import pyarrow as pa

    checks = []
    expected = pa.table({"id": [1, 2], "amount": [10, 20]})
    for name, table, max_rows in [
        ("equivalent", expected, 100),
        ("different", pa.table({"id": [1, 2], "amount": [10, 21]}), 100),
        ("not_evaluable", expected, 1),
    ]:
        result = ef.diff(
            table,
            expected,
            keys=["id"],
            options=ef.ComparisonOptions(max_rows=max_rows),
            work_dir=args.output.parent / ("boundary-" + name),
        )
        if result.state != name:
            raise ValueError("independent Arrow expected outcome failed: " + name)
        checks.append(name)
    if not callable(eb.evaluate_records) or not callable(eb.oracle_verification_bridge):
        raise ValueError("paired benchmark public API is unavailable")
    checks.append("public_benchmark_API")
    if args.profile in ("ml", "all"):
        spec = ef.ProfileSpec(
            family="nulls_types",
            features=(
                ef.ProfileFeature(
                    name="null_rate",
                    metric="tasa_nulos",
                    table="result",
                    columns=("x",),
                ),
            ),
        )

        def profile(count):
            return ef.ProfileVector(
                spec=spec,
                spec_sha256=ef.profile_spec_fingerprint(spec),
                observations=(
                    ef.FeatureObservation(
                        name="null_rate",
                        state="available",
                        value=count / 100,
                        numerator=count,
                        denominator=100,
                    ),
                ),
            )

        fit = ef.fit_detectors(
            ef.NormalTrainingProfiles(
                purpose="normal_training",
                selection_manifest_sha256="a" * 64,
                profiles=tuple(profile(i) for i in range(20)),
            ),
            spec=spec,
            config=ef.IsolationForestConfig(random_state=7),
            support=ef.DetectorSupport(
                min_training_rows=10,
                min_calibration_rows=5,
                rationale="Synthetic compatibility fixture, not scientific calibration",
            ),
        )
        bundle = ef.calibrate_detectors(
            fit,
            ef.NormalCalibrationProfiles(
                purpose="normal_calibration",
                selection_manifest_sha256="b" * 64,
                profiles=tuple(profile(i) for i in range(2, 18, 2)),
            ),
            alpha="0.10",
        )
        result = ef.detect(bundle, (profile(10), profile(95)))
        if result.b[0].result.decision != "no_alert" or result.b[1].result.decision != "alert":
            raise ValueError("independent MAD fixture outcomes differ")
        if not all(item.result.complete for item in result.m):
            raise ValueError("ML profile unavailable despite selected dependency")
        checks.append("native_IsolationForest_and_independent_MAD")
    if args.profile in ("resources", "all"):
        import psutil

        if psutil.Process().memory_info().rss <= 0:
            raise ValueError("native resource measurement unavailable")
        checks.append("native_resource_probe")
    args.output.write_text(
        json.dumps(
            {
                "status": "passed",
                "profile": args.profile,
                "checks": checks,
                "synthetic": True,
                "scientific_acceptance": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
