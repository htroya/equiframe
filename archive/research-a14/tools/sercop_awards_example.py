"""Compare complete public award counts by currency using three native engines.

The independent expected counts come from every original annual CSV record,
before native grouping. Currency text and the empty string stay unchanged.
This counts offered CSV records; it does not approve a cohort or sum money.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "exports", Path(__file__).with_name("sercop_local_exports.py")
)
exports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=exports.sources.ROOT)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.setdefault("POLARS_MAX_THREADS", "1")
    import duckdb
    import equiframe as ef
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    spec = importlib.util.spec_from_file_location(
        "identity", Path(__file__).with_name("option_operations.py")
    )
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    wheel = (
        args.workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl"
    )
    wheel_sha = "c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23"
    identity = op.identity(wheel, wheel_sha, Path(__file__).parents[1])
    catalog_path = args.root / "03_metadatos/organized-exports.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))
    record = next(
        row
        for row in catalog["files"]
        if row["kind"] == "csv"
        and row["month"] == 0
        and row["member"] == "awards_2025.csv"
    )
    source = args.root / record["file"]
    parquet = args.root / record["projection"]["file"]
    exports.require(
        exports.digest(source) == record["sha256"]
        and exports.digest(parquet) == record["projection"]["parquet_sha256"],
        "Award source identity differs",
    )
    # Frozen source expectation precedes every native implementation.
    expected_counts = Counter(row["currency"] for row in exports.csv_rows(source))
    exports.require(
        sum(expected_counts.values()) == 183891, "Complete annual award support differs"
    )
    expected_rows = [
        {"currency": currency, "award_count": count}
        for currency, count in sorted(expected_counts.items())
    ]
    expected = pa.Table.from_pylist(
        expected_rows,
        schema=pa.schema([("currency", pa.string()), ("award_count", pa.int64())]),
    )
    args.output.mkdir(parents=True, exist_ok=False)
    exports.write(
        args.output / "frozen-expected.json",
        {
            "source_csv_sha256": exports.digest(source),
            "records": 183891,
            "rows": expected_rows,
        },
    )
    pandas = (
        pd.read_parquet(parquet, columns=["currency"])
        .groupby("currency", dropna=False)
        .size()
        .reset_index(name="award_count")
    )
    polars = (
        pl.read_parquet(parquet, columns=["currency"])
        .group_by("currency")
        .agg(pl.len().cast(pl.Int64).alias("award_count"))
    )
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("SET threads=1")
        duck = connection.execute(
            "SELECT currency, COUNT(*) AS award_count FROM read_parquet(?) GROUP BY currency",
            [str(parquet)],
        ).fetch_arrow_table()
    finally:
        connection.close()
    native = {"pandas": pandas, "polars": polars, "duckdb": duck}
    policy = ef.ComparisonPolicy(
        index="ignore",
        justification="Only generated pandas group result RangeIndex is ignored; exact source currency text and integral counts remain columns.",
    )
    checks = []

    def compare(label, left, right, state):
        directory = args.output / label
        result = ef.diff(
            left, right, keys=["currency"], policy=policy, work_dir=directory
        )
        exports.require(
            result.complete and result.counts.final and result.state == state,
            "Unexpected complete aggregate comparison",
        )
        restored = ef.read_comparison(
            directory / result.comparison_id / "comparison.json"
        )
        exports.require(restored == result, "Persisted comparison differs")
        observed = sum(1 for _ in ef.iter_differences(restored.differences))
        exports.require(
            observed == result.counts.difference_records
            and (observed == 0) is (state == "equivalent"),
            "Difference readback differs",
        )
        checks.append(
            {
                "label": label,
                "expected_state": state,
                "state": result.state,
                "complete": True,
                "difference_records": observed,
                "comparison_id": result.comparison_id,
                "status": "PASS",
            }
        )

    for engine, table in native.items():
        compare(engine + "-source-expected", table, expected, "equivalent")
    names = list(native)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            compare(left + "-" + right, native[left], native[right], "equivalent")
    altered = [
        {**row, "award_count": row["award_count"] + 1} if index == 0 else row
        for index, row in enumerate(expected_rows)
    ]
    compare(
        "deliberate-one-count-change",
        pandas,
        pa.Table.from_pylist(altered, schema=expected.schema),
        "different",
    )
    exports.require(
        exports.digest(source) == record["sha256"]
        and exports.digest(parquet) == record["projection"]["parquet_sha256"],
        "Source changed during example",
    )
    op.identity(wheel, wheel_sha, Path(__file__).parents[1])
    exports.write(
        args.output / "result.json",
        {
            "schema": "equiframe.sercop-complete-award-example.v1",
            "candidate": "0.12.0a13",
            "package": identity,
            "source_csv_sha256": exports.digest(source),
            "source_parquet_sha256": exports.digest(parquet),
            "tool_sha256": exports.digest(Path(__file__)),
            "annual_award_records": 183891,
            "currency_groups": len(expected_rows),
            "native_implementations": list(native),
            "sdk_comparisons": checks,
            "all_expected": True,
            "automatic_rubric_points": 0,
            "scientific_approval": False,
            "scope": "Complete annual CSV award-count grouping;three native implementations;source Python CSV count oracle;6 equivalent comparisons and1 complete deliberate difference;not raw full-row SDK comparison or model training",
        },
    )
    print(
        json.dumps(
            {
                "annual_award_records": 183891,
                "currency_groups": len(expected_rows),
                "sdk_comparisons": len(checks),
                "all_expected": True,
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
