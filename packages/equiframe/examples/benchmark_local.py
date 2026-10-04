"""Run Jhair's benchmark locally and print summary."""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "equiframe" / "src"))

import equiframe as ef
from equiframe.benchmark import (
    run_benchmark,
    collect_profile_vectors,
    fit_isolation_forest_mad,
    detect_anomalies,
    rule_divergence,
    write_summary_tables,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
    args = parser.parse_args()

    # Run benchmark
    results = run_benchmark(args.engines, args.families, args.work_dir)

    # Collect profile vectors
    vectors = collect_profile_vectors(args.work_dir, args.families, args.engines)
    print(f"Collected {len(vectors)} profile vectors")

    # Fit detector (using all vectors as normal training for demo)
    bundle = fit_isolation_forest_mad([v for _, _, v in vectors])
    print("Detector fitted and calibrated")

    # Detect anomalies
    m_decisions, b_decisions = detect_anomalies(bundle, [v for _, _, v in vectors])
    print(f"Isolation Forest decisions: {m_decisions}")
    print(f"MAD decisions: {b_decisions}")

    # Rule-based divergence
    rule_diverge = rule_divergence(results)
    print(f"Rule divergence: {rule_diverge}")

    # Write summary tables
    write_summary_tables(
        args.work_dir,
        results,
        vectors,
        m_decisions,
        b_decisions,
        rule_diverge,
        args.engines,
    )
    print(f"Summary written to {args.work_dir / 'summary'}")

    # Optionally print a small table
    try:
        import pandas as pd

        df = pd.read_csv(args.work_dir / "summary" / "decisions.csv")
        print("\nDecisions preview:")
        print(df.head(10))
    except Exception:
        pass


if __name__ == "__main__":
    main()
