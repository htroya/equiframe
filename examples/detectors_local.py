"""Synthetic API demonstration. These profiles are not reviewed thesis observations."""

import argparse
from pathlib import Path

import equiframe as ef


def profile(count: int) -> ef.ProfileVector:
    spec = ef.ProfileSpec(
        family="nulls_types",
        features=(
            ef.ProfileFeature(
                name="null_rate", metric="tasa_nulos", table="result", columns=("x",)
            ),
        ),
    )
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--restore-only", action="store_true")
    args = parser.parse_args()
    if args.restore_only:
        bundle = ef.read_detector_bundle(args.bundle)
    else:
        fit = ef.fit_detectors(
            ef.NormalTrainingProfiles(
                purpose="normal_training",
                selection_manifest_sha256="a" * 64,
                profiles=tuple(profile(i) for i in range(20)),
            ),
            spec=profile(0).spec,
            config=ef.IsolationForestConfig(random_state=7),
            support=ef.DetectorSupport(
                min_training_rows=10,
                min_calibration_rows=5,
                rationale="Synthetic demonstration only; not statistical guarantees",
            ),
        )
        bundle = ef.calibrate_detectors(
            fit,
            ef.NormalCalibrationProfiles(
                purpose="normal_calibration",
                selection_manifest_sha256="b" * 64,
                profiles=tuple(profile(i) for i in range(2, 18, 2)),
            ),
            alpha="0.10",  # Demonstration choice, not the thesis's final alpha.
        )
        fingerprint = ef.write_detector_bundle(bundle, args.bundle)
        assert ef.read_detector_bundle(args.bundle, expected_sha256=fingerprint) == bundle
    result = ef.detect(bundle, (profile(10), profile(95)))
    assert result.b[0].result.decision == "no_alert"
    assert result.b[1].result.decision == "alert"
    hybrid = ef.combine_decisions(
        ef.ComponentDecision(decision="not_evaluable", complete=False, reason="R not supplied"),
        result.m[1].result,
    )
    print("Synthetic demonstration; no scientific false-alarm claim")
    print(result.model_dump_json(indent=2))
    print(hybrid.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
