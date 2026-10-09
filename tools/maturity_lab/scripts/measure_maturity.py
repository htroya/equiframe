#!/usr/bin/env python3
"""Bounded deterministic resource observations, with no accepted SLO or scientific claim."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--storage", required=True, choices=("disk", "tmpfs"))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new measurement directory")
    args.output.mkdir(parents=True)
    import equiframe as ef
    import equiframe_benchmark as eb

    protocol = {
        "rows": [100, 1000],
        "width": 2,
        "repetitions": 3,
        "rss_budget_bytes": 512 * 1024**2,
        "disk_budget_bytes": 64 * 1024**2,
        "timeout_seconds": 120,
        "threads_per_engine": 1,
        "expected_state": "different",
        "storage": args.storage,
        "concurrent_known_loads": "No other task-controlled suite; shared host not controlled",
        "os_cache": "uncontrolled",
        "slo_accepted": False,
        "scope": "local synthetic capture/compare/evidence; no network transport or VM claim",
        "python": platform.python_version(),
        "machine": platform.machine(),
        "executable": sys.executable,
    }
    (args.output / "protocol.json").write_text(
        json.dumps(protocol, indent=2) + "\n", encoding="utf-8"
    )
    results = []
    for rows in protocol["rows"]:
        spec = eb.ScaleSpec(
            case_id=f"maturity-{rows}",
            rows=rows,
            width=2,
            difference_last=True,
            repetitions=3,
            timeout_seconds=120,
            rss_budget_bytes=protocol["rss_budget_bytes"],
            disk_budget_bytes=protocol["disk_budget_bytes"],
            comparison_options=ef.ComparisonOptions(
                max_rows=2000, max_disk_bytes=32 * 1024**2, timeout_seconds=60
            ),
            concurrent_loads=protocol["concurrent_known_loads"],
        )
        result = eb.measure_scale(spec, work_dir=args.output / f"rows-{rows}")
        restored = eb.read_scale(args.output / f"rows-{rows}" / result.run_id)
        if restored != result:
            raise ValueError("measured evidence readback differs")
        summary = eb.summarize_scale(result)
        results.append(summary)
        (args.output / "summary.json").write_text(
            json.dumps({"protocol": protocol, "results": results}, indent=2) + "\n",
            encoding="utf-8",
        )
        if not result.complete or not result.resource_measurement_complete:
            raise RuntimeError("measurement incomplete; retain the actual partial result")
    # A separate tiny case exercises cooperative admission, never an OOM or shared-host disruption.
    import pyarrow as pa

    table = pa.table({"id": [1, 2], "value": [10, 20]})
    limited = ef.diff(
        table,
        table,
        options=ef.ComparisonOptions(max_rows=1),
        work_dir=args.output / "bounded-limit",
    )
    if limited.state != "not_evaluable" or limited.complete:
        raise ValueError("resource limit was incorrectly converted into equivalence")
    (args.output / "bounded-limit.json").write_text(
        limited.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "sizes": protocol["rows"],
                "repetitions_each": 3,
                "storage": args.storage,
                "slo_accepted": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
