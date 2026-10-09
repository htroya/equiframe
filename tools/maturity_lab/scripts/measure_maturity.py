#!/usr/bin/env python3
"""Bounded deterministic resource observations, with no accepted SLO or scientific claim."""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
from pathlib import Path


def observed_filesystem(directory: Path) -> str:
    """Record Linux mount type; never silently call a RAM-backed path disk."""
    selected = None
    try:
        rows = Path("/proc/self/mountinfo").read_text("utf-8").splitlines()
    except OSError as error:
        raise RuntimeError("Cannot observe filesystem type for the measurement") from error
    for row in rows:
        before, separator, after = row.partition(" - ")
        if not separator:
            continue
        fields = before.split()
        if len(fields) < 5 or not after.split():
            continue
        decoded = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), fields[4])
        mount = Path(decoded)
        if directory.resolve().is_relative_to(mount) and (
            selected is None or len(mount.parts) > selected[0]
        ):
            selected = (len(mount.parts), after.split()[0])
    if selected is None:
        raise RuntimeError("Measurement filesystem was not found in this mount namespace")
    return selected[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--storage", required=True, choices=("disk", "tmpfs"))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new measurement directory")
    args.output.mkdir(parents=True)
    filesystem = observed_filesystem(args.output)
    observed_storage = "tmpfs" if filesystem in {"tmpfs", "ramfs"} else "disk"
    if observed_storage != args.storage:
        raise ValueError("requested storage label differs from observed filesystem")
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
        "storage": observed_storage,
        "filesystem_observed": filesystem,
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
        # Independent sizes continue even when one instrument is incomplete.
        # The final return code remains nonzero; no partial measurement becomes a pass.
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
    complete = all(item["complete"] and item["resource_measurement_complete"] for item in results)
    status = "passed" if complete else "partial"
    print(
        json.dumps(
            {
                "status": status,
                "sizes": protocol["rows"],
                "repetitions_each": 3,
                "storage": observed_storage,
                "filesystem_observed": filesystem,
                "slo_accepted": False,
            }
        )
    )
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
