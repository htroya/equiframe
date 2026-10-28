"""A bounded installed consumer; larger scales require an explicit argument."""

import argparse
import json
from pathlib import Path

import equiframe as ef

import equiframe_benchmark as eb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, choices=(1000, 100_000, 1_000_000), default=1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = eb.ScaleSpec(
        case_id=f"multiset-{args.rows}",
        rows=args.rows,
        width=2,
        difference_last=True,
        repetitions=3,
        timeout_seconds=1800.0 if args.rows == 1_000_000 else 300.0,
        comparison_options=ef.ComparisonOptions(
            max_work=1_000_000_000,
            max_disk_bytes=2 * 1024**3,
            timeout_seconds=540.0,
        ),
        concurrent_loads="Consumer must record other jobs; host and OS cache uncontrolled",
    )
    result = eb.measure_scale(spec, work_dir=args.output)
    restored = eb.read_scale(args.output / result.run_id)
    print(json.dumps(eb.summarize_scale(restored), sort_keys=True, indent=2))
    raise SystemExit(0 if result.complete else 3)


if __name__ == "__main__":
    main()
