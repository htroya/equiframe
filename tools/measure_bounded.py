"""Run a small engineering cost suite using the existing benchmark supervisor.

This is a developer tool, not a new core API or scientific experiment. Synthetic
fixtures, complete comparisons and retained evidence use bounded ordinary loads.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import statistics
import sys
import time
from collections.abc import Callable
from datetime import datetime
from datetime import timezone as _timezone
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, TypeVar

import equiframe as ef

UTC = _timezone.utc
_T = TypeVar("_T")

MIB = 1024**2
CASES = ("late-difference", "many-differences", "duplicates", "wide-strings", "disk-evidence")


def scale_specs(rows: int, repetitions: int) -> tuple[Any, ...]:
    """Reuse the published exact integer/text/NULL scale protocol without extending it."""
    eb = importlib.import_module("equiframe_benchmark")
    shapes: tuple[dict[str, Any], ...] = (
        dict(rows=rows, width=4, alignment="keyed", difference_last=True),
        dict(rows=rows, width=4, alignment="keyed", difference_every=1),
        dict(rows=rows, width=4, distinct_rows=8, difference_last=True),
        dict(rows=rows, width=8, text_max_length=1024, cardinality=rows, difference_last=True),
        dict(
            rows=rows * 2,
            width=8,
            text_max_length=512,
            cardinality=rows * 2,
            alignment="keyed",
            difference_every=1,
        ),
    )
    return tuple(
        eb.ScaleSpec(
            case_id=name,
            **shape,
            repetitions=repetitions,
            batch_rows=128,
            timeout_seconds=120.0,
            rss_budget_bytes=512 * MIB,
            disk_budget_bytes=64 * MIB,
            run_baselines=False,
            comparison_options=ef.ComparisonOptions(
                batch_rows=128,
                max_disk_bytes=32 * MIB,
                max_evidence_bytes=8 * MIB,
                timeout_seconds=30.0,
            ),
            concurrent_loads="Shared host; workload/caches uncontrolled; record concurrent work",
        )
        for name, shape in zip(CASES, shapes, strict=True)
    )


def fingerprint(directory: Path) -> str:
    hashed = hashlib.sha256()
    for path in sorted(directory.rglob("*.py")):
        hashed.update(path.relative_to(directory).as_posix().encode() + b"\0" + path.read_bytes())
    return hashed.hexdigest()


def runtime_identity() -> dict[str, Any]:
    eb = importlib.import_module("equiframe_benchmark")
    versions = {}
    for name in ("equiframe", "equiframe-benchmark", "pyarrow", "pandas", "psutil"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "not_installed"
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "versions": versions,
        "core_python_sources_sha256": fingerprint(Path(ef.__file__ or "").parent),
        "benchmark_python_sources_sha256": fingerprint(Path(eb.__file__ or "").parent),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def decimal_tables(rows: int) -> tuple[Any, Any]:
    """Expected USD cents are defined directly; change only the final record by one cent."""
    pa = importlib.import_module("pyarrow")
    values = [Decimal(index).scaleb(-2) for index in range(rows)]
    changed = [*values[:-1], values[-1] + Decimal("0.01")]
    tables = tuple(
        pa.table(
            {
                "id": pa.array(range(rows), type=pa.int64()),
                "currency": pa.array(["USD"] * rows, type=pa.string()),
                "amount": pa.array(amounts, type=pa.decimal128(18, 2)),
            }
        )
        for amounts in (changed, values)
    )
    return tables[0], tables[1]


def publish_bytes(path: Path, payload: bytes) -> None:
    """An additional timed durable write, not a breakdown of comparison internals."""
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def decimal_trial(directory: Path, rows: int, repetition: int) -> dict[str, Any]:
    pa = importlib.import_module("pyarrow")
    pd = importlib.import_module("pandas")
    directory.mkdir()
    stages: list[dict[str, Any]] = []
    started = time.perf_counter()

    def measured(name: str, scope: str, action: Callable[[], _T]) -> _T:
        began = time.perf_counter()
        value = action()
        stages.append({"name": name, "wall_seconds": time.perf_counter() - began, "scope": scope})
        return value

    tables = measured(
        "generate", "Synthetic exact Decimal/Arrow input construction", lambda: decimal_tables(rows)
    )
    frames = measured(
        "convert",
        "Additional Arrow-to-pandas ArrowDtype conversion; diff includes its own capture again",
        lambda: tuple(table.to_pandas(types_mapper=pd.ArrowDtype) for table in tables),
    )
    paths = (directory / "candidate.arrow", directory / "expected.arrow")

    def capture() -> None:
        for table, path in zip(tables, paths, strict=True):
            with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
                writer.write_table(table, max_chunksize=128)

    measured("capture", "Additional complete batched Arrow IPC writes of both inputs", capture)

    def input_hashes() -> dict[str, str]:
        hashes = {}
        for path in paths:
            with path.open("rb") as source:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(chunk)
                hashes[path.name] = hasher.hexdigest()
        return hashes

    hashes = measured(
        "hash",
        "Complete SHA-256 reread of both captured IPC files",
        input_hashes,
    )
    result = measured(
        "compare",
        "Public diff: full pandas capture, inference, exact comparison and evidence publication",
        lambda: ef.diff(
            *frames,
            keys=["id"],
            work_dir=directory / "comparison",
            options=ef.ComparisonOptions(
                batch_rows=128,
                max_disk_bytes=32 * MIB,
                max_evidence_bytes=8 * MIB,
                timeout_seconds=30.0,
            ),
        ),
    )
    payload = measured(
        "serialize",
        "Additional standalone comparison JSON serialization",
        lambda: result.model_dump_json().encode(),
    )
    serialized = directory / "serialized-comparison.json"
    measured(
        "persist",
        "Additional standalone exclusive fsync write",
        lambda: publish_bytes(serialized, payload),
    )
    measured(
        "report",
        "Redacted report construction and JSON/text/HTML publication",
        lambda: ef.write_comparison_report(result, directory / "report"),
    )

    def verify() -> int:
        if ef.read_comparison(serialized) != result:
            raise ValueError("comparison roundtrip changed")
        return sum(1 for _ in ef.iter_differences(result.differences))

    count = measured("verify", "Comparison reader and every difference record", verify)
    elapsed = time.perf_counter() - started
    complete = (
        result.complete
        and result.state == "different"
        and result.counts.left_rows == result.counts.right_rows == rows
        and count == result.counts.difference_records == 1
    )
    return {
        "repetition": repetition,
        "cache_state": "fresh_worker_os_cache_uncontrolled"
        if repetition == 0
        else "warm_worker_os_cache_uncontrolled",
        "expected_state": "different",
        "expected_difference_records": 1,
        "complete": complete,
        "state": result.state,
        "difference_records": count,
        "rows_per_side": rows,
        "stages": stages,
        "end_to_end_seconds": elapsed,
        "capture_sha256": hashes,
        "retained_apparent_bytes": sum(
            path.stat().st_size for path in directory.rglob("*") if path.is_file()
        ),
        "comparison": result.model_dump(mode="json"),
    }


def decimal_worker(output: Path, rows: int, repetitions: int) -> int:
    trials = []
    for repetition in range(repetitions):
        trial = decimal_trial(output / f"trial-{repetition:03d}", rows, repetition)
        publish_bytes(output / f"trial-{repetition:03d}.json", json.dumps(trial, indent=2).encode())
        trials.append(trial)
    complete = all(trial["complete"] for trial in trials)
    publish_bytes(
        output / "completed.json",
        json.dumps(
            {"identity": runtime_identity(), "complete": complete, "trials": trials}, indent=2
        ).encode(),
    )
    return 0 if complete else 3


def measure_suite(output: Path, rows: int, repetitions: int) -> dict[str, Any]:
    if not 8 <= rows <= 2048 or not 2 <= repetitions <= 5:
        raise ValueError("bounded suite requires 8..2048 rows and 2..5 repetitions")
    output.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(output).free < 384 * MIB:
        raise ValueError("bounded suite requires at least 384 MiB free before starting")
    eb = importlib.import_module("equiframe_benchmark")
    process = importlib.import_module("equiframe_benchmark.scale_process")
    identity = runtime_identity()
    cases = []
    for spec in scale_specs(rows, repetitions):
        run = eb.measure_scale(spec, work_dir=output / spec.case_id)
        verified = eb.read_scale(output / spec.case_id / run.run_id)
        cases.append(
            {"case_id": spec.case_id, "run_id": run.run_id, "summary": eb.summarize_scale(verified)}
        )
        print(spec.case_id + ": complete=" + str(verified.complete), flush=True)
    decimal_directory = output / "decimal"
    observed = process.supervise(
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--decimal-worker",
            "--output",
            str(decimal_directory),
            "--rows",
            str(rows),
            "--repetitions",
            str(repetitions),
        ],
        directory=decimal_directory,
        timeout_seconds=120.0,
        rss_budget_bytes=512 * MIB,
        disk_budget_bytes=64 * MIB,
    )
    completion_path = decimal_directory / "completed.json"
    completion = json.loads(completion_path.read_text()) if completion_path.is_file() else None
    decimal_complete = (
        observed.exit_code == 0
        and observed.termination_reason == "exited"
        and completion is not None
        and completion["identity"] == identity
        and completion["complete"] is True
        and len(completion["trials"]) == repetitions
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "identity": identity,
        "scope": "Bounded synthetic engineering observations; no scientific inference",
        "rows": rows,
        "repetitions": repetitions,
        "cases": cases,
        "decimal": {
            "complete": decimal_complete,
            "resource_measurement_complete": (
                not observed.monitoring_errors
                and all(
                    getattr(observed, field) is not None
                    for field in (
                        "sampled_rss_peak_bytes",
                        "cpu_user_seconds",
                        "cpu_system_seconds",
                        "io_read_bytes",
                        "io_write_bytes",
                        "io_read_chars",
                        "io_write_chars",
                        "disk_apparent_peak_bytes",
                        "disk_allocated_peak_bytes",
                    )
                )
            ),
            "process": observed.model_dump(mode="json"),
            "completion": completion,
        },
        "complete": all(case["summary"]["complete"] for case in cases) and decimal_complete,
        "limitations": [
            "Shared host and OS caches uncontrolled; no paired before/after speed claim",
            "Sampled RSS/disk peaks are lower bounds; thresholds are reactive, not hard quotas",
            "CPU/I/O are last available observations; missing counters are not zeros",
            "Additional conversion/capture/serialization/persistence do not isolate diff internals",
            "No network, service, saturation, larger-than-RAM or engine allocator measurement",
            "Decimal supplement has a separate explicit format; historical ScaleSpec is unchanged",
        ],
    }
    if completion is not None:
        result["decimal"]["median_end_to_end_seconds"] = statistics.median(
            trial["end_to_end_seconds"] for trial in completion["trials"]
        )
    result["runtime_unchanged"] = runtime_identity() == identity
    result["complete"] = result["complete"] and result["runtime_unchanged"]
    publish_bytes(output / "suite.json", json.dumps(result, indent=2).encode())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new private output directory")
    parser.add_argument("--rows", type=int, default=512)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--decimal-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 8 <= args.rows <= 2048 or not 2 <= args.repetitions <= 5:
        parser.error("use 8..2048 rows and 2..5 repetitions")
    output = args.output.resolve()
    if args.decimal_worker:
        raise SystemExit(decimal_worker(output, args.rows, args.repetitions))
    result = measure_suite(output, args.rows, args.repetitions)
    print("Retained cost observations: " + str(output / "suite.json"))
    raise SystemExit(0 if result["complete"] else 3)


if __name__ == "__main__":
    main()
