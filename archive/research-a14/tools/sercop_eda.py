"""Private annual SERCOP diagnostics over the exact already delivered snapshot.

No EDA/reflection is written to the teacher directory or published by HTTP.
Domain observations remain exploratory; Jhair approves grain/cohort/semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from equiframe.eda import EdaConfig, Source, analyze, read_result

EXPECTED_MANIFEST = "712022f8470428f25fa12b307e301ad6ef6fb0f9c59634ab8b90569380ac279c"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(root: Path) -> dict[str, object]:
    if sha(root / "manifest.json") != EXPECTED_MANIFEST:
        raise ValueError("teacher delivery manifest identity mismatch")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf8"))
    for member in manifest["files"]:
        path = root / member["file"]
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
            or path.stat().st_size != member["bytes"]
            or sha(path) != member["sha256"]
        ):
            raise ValueError(
                "teacher delivery member identity mismatch: " + member["file"]
            )
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != {m["file"] for m in manifest["files"]} | {"manifest.json"}:
        raise ValueError("teacher delivery is not closed")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--configs",
        type=Path,
        default=Path(__file__).parent / "eda-sercop-configs.json",
    )
    args = parser.parse_args()
    root, output = args.delivery.resolve(), args.output.resolve()
    if output.is_relative_to(root):
        raise ValueError("output must be outside teacher delivery")
    configs = json.loads(args.configs.read_text(encoding="utf8"))
    manifest = verify(root)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    dictionary = json.loads(
        (root / "metadata/tablas-y-diccionario.json").read_text(encoding="utf8")
    )
    summaries = []
    for table in (t for t in dictionary if t["period"] == "anual"):
        name = Path(table["parquet"]).stem
        config = EdaConfig.model_validate_json(
            json.dumps(configs.get(name, configs["default"]))
        )
        destination = output / name
        result = analyze(
            Source(
                path=str(root / table["parquet"]),
                snapshot_id="sercop-2025-method-all-captured-20261012",
                expected_sha256=table["parquet_sha256"],
                expected_bytes=(root / table["parquet"]).stat().st_size,
                manifest_path=str(root / "manifest.json"),
                manifest_sha256=EXPECTED_MANIFEST,
            ),
            config=config,
            output=destination,
        )
        if (
            read_result(destination) != result
            or result.rows != table["rows"]
            or result.source_unchanged is not True
        ):
            raise ValueError("annual diagnostic readback/count/source mismatch")
        if result.state in ("failed", "cancelled"):
            raise ValueError("annual diagnostic failed: " + str(result.reason))
        summaries.append(
            {
                "table": name,
                "rows": result.rows,
                "state": result.state,
                "reason": result.reason,
                "raw_columns": len(result.columns),
                "conversion_counts": [
                    {
                        k: c[k]
                        for k in ("column", "target", "attempted", "invalid", "missing")
                    }
                    for c in result.conversions
                ],
                "observed_dates": [
                    c["observed_dates"]
                    for c in result.conversions
                    if "observed_dates" in c
                ],
                "numeric_states": [n["state"] for n in result.numeric],
                "manifest_sha256": sha(destination / "manifest.json"),
                "summary_sha256": sha(destination / "summary.json"),
                "report_sha256": sha(destination / "report.html"),
                "run_id": result.run_id,
            }
        )
        print(
            json.dumps({"table": name, "rows": result.rows, "state": result.state}),
            flush=True,
        )
    verify(root)
    receipt = {
        "schema": "equiframe.sercop-eda-example.v1",
        "manifest_sha256": EXPECTED_MANIFEST,
        "source_full_hash_readback_before_after": True,
        "source_files": len(manifest["files"]) + 1,
        "annual_only_no_month_overlap": True,
        "annual_rows_across_distinct_business_and_metadata_tables": sum(
            s["rows"] for s in summaries
        ),
        "tables": summaries,
        "configs_sha256": sha(args.configs),
        "interpretation": "Generic full-table diagnostics, retrospective capture; no unique process count, official irregularity, confirmed error, accepted DW or thesis oracle inferred.",
        "domain_pending": [
            "Jhair: grain, release history, business uniqueness and cohort approval",
            "Jhair: approve decimal scale/date semantics and real currency/status rules",
            "Jose: immutable providers and controlled service resources",
        ],
        "publication": "Private output, no public report/EDA/reflection or service changes",
    }
    with (output / "example-receipt.json").open(
        "x", encoding="utf8", newline="\n"
    ) as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
