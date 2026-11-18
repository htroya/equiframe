"""Fit from explicitly selected normal training profiles and transform with frozen medians.

The caller owns the reviewed selection manifest. Synthetic demo selections are not
scientific evidence. Neither this script nor the core infer normality from R/M/O.
"""

import argparse
import hashlib
from pathlib import Path

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, nargs="+", required=True)
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--score", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profiles = tuple(ef.read_profile(p).vector for p in args.training)
    selection = ef.NormalTrainingProfiles(
        purpose="normal_training",
        selection_manifest_sha256=hashlib.sha256(args.selection_manifest.read_bytes()).hexdigest(),
        profiles=profiles,
    )
    bundle = ef.fit_preprocessor(selection, spec=profiles[0].spec)
    ef.write_preprocessor(bundle, args.output)
    if bundle.state != "ready":
        print("Preprocessor not estimable:", bundle.features)
        raise SystemExit(3)
    restored = ef.read_preprocessor(args.output)
    matrix = ef.transform_profiles(restored, tuple(ef.read_profile(p).vector for p in args.score))
    print(matrix.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
