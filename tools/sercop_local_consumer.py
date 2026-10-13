"""Read every CSV-derived Parquet in three native engines, then compare receipts.

Full rows are verified independently against hashes made from source CSV before
writing Parquet. SDK comparisons cover the complete 104-row receipt summaries;
they are not advertised as SDK comparisons of all raw contracting records.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "local_exports", Path(__file__).with_name("sercop_local_exports.py")
)
exports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exports)
require, digest, write = exports.require, exports.digest, exports.write


def verify_rows(iterator, columns, expected):
    observed = hashlib.sha256()
    count = 0
    for row in iterator:
        require(
            list(row) == columns and all(type(value) is str for value in row.values()),
            "Native columns or text types differ",
        )
        observed.update((exports.sources.exact_json(row) + "\n").encode("utf-8"))
        count += 1
    require(
        count == expected["rows"]
        and observed.hexdigest() == expected["source_row_sha256"],
        "Complete native source-row readback differs",
    )
    return count, observed.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=exports.sources.ROOT)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
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
    expected_wheel = "c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23"
    identity = op.identity(wheel, expected_wheel, Path(__file__).parents[1])
    catalog_path = args.root / "03_metadatos/organized-exports.json"
    catalog_sha = digest(catalog_path)
    records = json.loads(catalog_path.read_text("utf-8"))["files"]
    tables = sorted(
        (record for record in records if "projection" in record),
        key=lambda record: record["projection"]["file"],
    )
    require(
        len(tables) == 104
        and all(r["projection"]["full_readback_verified"] for r in tables),
        "Expected full source-CSV projections",
    )
    args.output.mkdir(parents=True, exist_ok=False)
    tool_sha = digest(Path(__file__))
    expected = [
        {
            "file": r["projection"]["file"],
            "rows": r["projection"]["rows"],
            "source_rows_sha256": r["projection"]["source_row_sha256"],
        }
        for r in tables
    ]
    write(
        args.output / "frozen-expected.json",
        {"catalog_sha256": catalog_sha, "rows": expected},
    )
    outputs, full_readbacks = {}, []
    connection = duckdb.connect(":memory:")
    connection.execute("SET threads=1")
    connection.execute("SET memory_limit='512MB'")
    try:
        for engine in ("pandas", "polars", "duckdb"):
            summaries = []
            for record in tables:
                p = record["projection"]
                path = (args.root / p["file"]).resolve()
                require(
                    path.is_relative_to(args.root.resolve())
                    and digest(path) == p["parquet_sha256"],
                    "Projection identity differs",
                )
                if engine == "pandas":
                    frame = pd.read_parquet(path)
                    require(
                        list(frame.columns) == p["columns"], "Pandas columns differ"
                    )
                    iterator = (
                        dict(zip(p["columns"], row, strict=True))
                        for row in frame.itertuples(index=False, name=None)
                    )
                elif engine == "polars":
                    frame = pl.read_parquet(path)
                    require(frame.columns == p["columns"], "Polars columns differ")
                    iterator = frame.iter_rows(named=True)
                else:
                    batches = connection.read_parquet(str(path)).fetch_record_batch(
                        4096
                    )
                    require(
                        batches.schema.names == p["columns"], "DuckDB columns differ"
                    )
                    iterator = (row for batch in batches for row in batch.to_pylist())
                count, row_sha = verify_rows(iterator, p["columns"], p)
                require(
                    digest(path) == p["parquet_sha256"],
                    "Projection changed during read",
                )
                summaries.append(
                    {"file": p["file"], "rows": count, "source_rows_sha256": row_sha}
                )
                full_readbacks.append(
                    {
                        "engine": engine,
                        "file": p["file"],
                        "rows": count,
                        "source_rows_sha256": row_sha,
                        "status": "PASS",
                    }
                )
            outputs[engine] = (
                pd.DataFrame(summaries)
                if engine == "pandas"
                else pl.DataFrame(summaries)
                if engine == "polars"
                else pa.Table.from_pylist(summaries)
            )
            print(
                json.dumps(
                    {
                        "engine": engine,
                        "complete_tables": len(summaries),
                        "complete_rows": sum(row["rows"] for row in summaries),
                    }
                ),
                flush=True,
            )
    finally:
        connection.close()
    expected_table = pa.Table.from_pylist(
        expected,
        schema=pa.schema(
            [
                ("file", pa.string()),
                ("rows", pa.int64()),
                ("source_rows_sha256", pa.string()),
            ]
        ),
    )
    policy = ef.ComparisonPolicy(
        index="ignore",
        justification="Receipt summaries have only a generated pandas RangeIndex; source cell hashes, rows and identities remain explicit.",
    )
    checks = []

    def check(label, left, right, state):
        directory = args.output / label
        result = ef.diff(left, right, keys=["file"], policy=policy, work_dir=directory)
        require(
            result.complete and result.counts.final and result.state == state,
            "SDK receipt comparison differs",
        )
        restored = ef.read_comparison(
            directory / result.comparison_id / "comparison.json"
        )
        require(restored == result, "SDK persisted receipt readback differs")
        differences = sum(1 for _ in ef.iter_differences(restored.differences))
        require(
            differences == result.counts.difference_records
            and (differences == 0) is (state == "equivalent"),
            "SDK difference inventory differs",
        )
        checks.append(
            {
                "label": label,
                "state": state,
                "complete": True,
                "summary_rows": 104,
                "difference_records": differences,
                "comparison_id": result.comparison_id,
                "status": "PASS",
            }
        )

    for engine, value in outputs.items():
        check(engine + "-expected", value, expected_table, "equivalent")
        changed = [
            {**row, "rows": row["rows"] + 1} if index == 0 else row
            for index, row in enumerate(expected)
        ]
        check(
            engine + "-deliberate-count-change",
            value,
            pa.Table.from_pylist(changed, schema=expected_table.schema),
            "different",
        )
    engines = list(outputs)
    for index, left in enumerate(engines):
        for right in engines[index + 1 :]:
            check(left + "-" + right, outputs[left], outputs[right], "equivalent")
    require(
        digest(catalog_path) == catalog_sha and digest(Path(__file__)) == tool_sha,
        "Catalog/tool changed during run",
    )
    op.identity(wheel, expected_wheel, Path(__file__).parents[1])
    write(
        args.output / "result.json",
        {
            "schema": "equiframe.sercop-local-native-consumer.v1",
            "candidate": "0.12.0a13",
            "package": identity,
            "python": sys.version,
            "catalog_sha256": catalog_sha,
            "tool_sha256": tool_sha,
            "tables": 104,
            "source_rows": sum(row["rows"] for row in expected),
            "native_full_readbacks": full_readbacks,
            "sdk_summary_comparisons": checks,
            "all_expected": True,
            "automatic_rubric_points": 0,
            "scientific_cohort_approved": False,
            "scope": "312 complete native table readbacks against source-constructed CSV hashes;9 SDK comparisons of104-row receipt summaries only;not SDK comparisons of all raw rows or scientific evaluation",
        },
    )
    print(
        json.dumps(
            {
                "native_full_readbacks": len(full_readbacks),
                "sdk_summary_comparisons": len(checks),
                "all_expected": True,
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
