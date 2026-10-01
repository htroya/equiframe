"""Profile one captured execution using an explicit, versioned feature specification."""

import argparse
from pathlib import Path

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path("equiframe-runs"))
    args = parser.parse_args()
    execution = ef.ExecutionResult.model_validate_json(args.run.read_bytes())
    spec = ef.ProfileSpec.model_validate_json(args.spec.read_bytes())
    result = ef.profile_execution(execution, spec=spec, work_dir=args.work_dir)
    for observation in result.vector.observations:
        print(
            observation.name,
            observation.state,
            observation.value,
            observation.numerator,
            observation.denominator,
            observation.reason,
        )
    print("Saved", args.work_dir / result.metadata.profile_id / "profile.json")
    if not result.complete:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
