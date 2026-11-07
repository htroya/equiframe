"""Trusted isolated synthetic cost worker. No source/service/network access."""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypeVar

import equiframe as ef
from equiframe.evidence import describe_file, inventory, load_json, publish_json, verify_files

from equiframe_benchmark.costs import _Monitor, _PsutilProbe
from equiframe_benchmark.models import digest
from equiframe_benchmark.scale_io import save_scale_document
from equiframe_benchmark.scale_types import (
    SCALE_SAMPLE_INTERVAL_SECONDS,
    BaselineCost,
    ScaleSpec,
    ScaleTrial,
    ScaleWorkerCompletion,
    StageCost,
)

_T = TypeVar("_T")


def make_contract(spec: ScaleSpec) -> ef.Contract:
    columns = tuple(
        ef.ColumnSpec(
            name="id" if i == 0 else f"value_{i}",
            logical_type=ef.StringType()
            if i > 1 and i % 2 == 0
            else ef.IntegerType(bits=64, signed=True),
            nullable=i > 0 and spec.null_every is not None,
            numeric_policy=None
            if i > 1 and i % 2 == 0
            else ef.NumericPolicy(comparison="exact", unit="count"),
            null_policy=ef.NullPolicy(representations=("null",)),
        )
        for i in range(spec.width)
    )
    keys = (
        (
            ef.KeySpec(
                name="id",
                columns=("id",),
                unique=True,
                incomplete="reject",
                scope=ef.TableKeyScope(),
            ),
        )
        if spec.alignment == "keyed"
        else ()
    )
    schema = ef.TableSchema(
        columns=columns, keys=keys, multiplicity="preserve", order=ef.IgnoredOrder()
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="engineering.scale",
        revision=1,
        family="duplicates_order",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )


def _schema(spec: ScaleSpec) -> Any:
    pa = importlib.import_module("pyarrow")
    return pa.schema(
        [
            pa.field(
                "id" if i == 0 else f"value_{i}",
                pa.string() if i > 1 and i % 2 == 0 else pa.int64(),
                nullable=i > 0 and spec.null_every is not None,
            )
            for i in range(spec.width)
        ]
    )


def _value(spec: ScaleSpec, row: int, column: int, *, changed: bool) -> int | str | None:
    identity = row % (spec.distinct_rows or spec.rows)
    if column == 0:
        return identity
    # Alter the first payload column after NULL generation, so even NULL is a real change.
    if changed and column == 1:
        return -(identity + 1)
    if spec.null_every is not None and identity % spec.null_every == 0:
        return None
    number = 0 if identity % 100 < spec.skew_percent else identity % spec.cardinality
    if column > 1 and column % 2 == 0:
        return ("x" * (1 + number % spec.text_max_length)) + str(number)
    return number


def capture(spec: ScaleSpec, directory: Path) -> tuple[Path, Path]:
    """Generate both complete sides in bounded batches directly into Arrow IPC files."""
    pa = importlib.import_module("pyarrow")
    schema = _schema(spec)
    paths = directory / "candidate.arrow", directory / "expected.arrow"
    for side, path in enumerate(paths):
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, schema) as writer:
            for start in range(0, spec.rows, spec.batch_rows):
                rows = range(start, min(start + spec.batch_rows, spec.rows))
                arrays = [
                    pa.array(
                        [
                            _value(
                                spec,
                                row,
                                column,
                                changed=side == 0
                                and (
                                    (spec.difference_last and row == spec.rows - 1)
                                    or (
                                        spec.difference_every is not None
                                        and row % spec.difference_every == 0
                                    )
                                ),
                            )
                            for row in rows
                        ],
                        type=schema.field(column).type,
                    )
                    for column in range(spec.width)
                ]
                writer.write_batch(pa.RecordBatch.from_arrays(arrays, schema=schema))
    return paths


def _snapshot(paths: tuple[Path, Path], directory: Path) -> None:
    pa = importlib.import_module("pyarrow")
    records = []
    for path in paths:
        with pa.memory_map(str(path), "r") as source:
            reader = pa.ipc.open_file(source)
            rows = sum(reader.get_batch(i).num_rows for i in range(reader.num_record_batches))
            records.append(
                {"artifact": describe_file(path, directory).model_dump(mode="json"), "rows": rows}
            )
    publish_json({"inputs": records}, directory / "snapshot.json")


def _baseline(spec: ScaleSpec, paths: tuple[Path, Path], method: str) -> BaselineCost:
    name: Any = method
    if method == "datacompy":
        return BaselineCost(
            method=name,
            state="not_available",
            wall_seconds=None,
            reason=(
                "DataComPy is not a pinned dependency of this candidate; "
                "no untested semantic or version claims"
            ),
        )
    if method == "pandas_assert" and spec.alignment != "keyed":
        return BaselineCost(
            method=name,
            state="not_applicable",
            wall_seconds=None,
            reason=(
                "Native assertion baseline is restricted to declared unique keys; "
                "no silent row sorting or multiset policy substitution"
            ),
        )
    start = time.perf_counter()
    state: Literal["equivalent", "different"]
    try:
        pa = importlib.import_module("pyarrow")
        engine = importlib.import_module("pandas" if method == "pandas_assert" else "duckdb")
        tables = []
        for path in paths:
            with pa.memory_map(str(path), "r") as source:
                tables.append(pa.ipc.open_file(source).read_all())
        if not tables[0].schema.equals(tables[1].schema, check_metadata=True):
            state = "different"
        elif method == "pandas_assert":
            frames = [
                table.to_pandas(types_mapper=engine.ArrowDtype)
                .sort_values("id")
                .reset_index(drop=True)
                for table in tables
            ]
            try:
                engine.testing.assert_frame_equal(
                    frames[0], frames[1], check_exact=True, check_dtype=True, check_names=True
                )
                state = "equivalent"
            except AssertionError:
                state = "different"
        else:
            with engine.connect(config={"threads": "1", "memory_limit": "256MB"}) as connection:
                connection.register("lhs", tables[0])
                connection.register("rhs", tables[1])
                delta = connection.execute(
                    "SELECT EXISTS(SELECT * FROM (SELECT * FROM lhs EXCEPT ALL SELECT * FROM rhs) "
                    "UNION ALL SELECT * FROM (SELECT * FROM rhs EXCEPT ALL SELECT * FROM lhs))"
                ).fetchone()
                state = "different" if delta[0] else "equivalent"
        return BaselineCost(
            method=name,
            state=state,
            wall_seconds=time.perf_counter() - start,
            reason=(
                "Exact integers/text/NULL and equal Arrow schemas; includes native loading/"
                "conversion/query; excludes full differences, durable snapshots, reporting "
                "and integrity verification"
            ),
        )
    except ImportError:
        return BaselineCost(
            method=name,
            state="not_available",
            wall_seconds=None,
            reason="Optional native engine is not installed",
        )
    except Exception as error:
        return BaselineCost(
            method=name,
            state="failed",
            wall_seconds=time.perf_counter() - start,
            reason=type(error).__name__,
        )


def run_trial(spec: ScaleSpec, directory: Path, repetition: int) -> ScaleTrial:
    directory.mkdir()
    stages: list[StageCost] = []
    monitor = _Monitor(_PsutilProbe, SCALE_SAMPLE_INTERVAL_SECONDS)
    monitor.start()
    start = time.perf_counter()

    def measured(name: str, scope: str, action: Callable[[], _T]) -> _T:
        began = time.perf_counter()
        value = action()
        stages.append(StageCost(name=name, wall_seconds=time.perf_counter() - began, scope=scope))
        return value

    try:
        paths = measured(
            "capture",
            "Synthetic generation and batch Arrow IPC writing; no external database",
            lambda: capture(spec, directory),
        )
        measured(
            "snapshot",
            "Complete input hashing and batch row counting",
            lambda: _snapshot(paths, directory),
        )
        transferred = directory / "left.arrow", directory / "right.arrow"
        measured(
            "transfer",
            "Local file copies only, no network transfer",
            lambda: tuple(shutil.copyfile(a, b) for a, b in zip(paths, transferred, strict=True)),
        )
        contract = measured(
            "plan",
            "Declare and validate the exact contract; "
            "comparator internal planning remains in compare",
            lambda: make_contract(spec),
        )
        result = measured(
            "compare",
            "Public compare end-to-end including its input snapshots, planning, "
            "exact SQLite work, serialization and persistence",
            lambda: ef.compare(
                *transferred,
                contract=contract,
                reference="expected",
                work_dir=directory / "comparison",
                options=spec.comparison_options,
            ),
        )
        serialized = measured(
            "serialize",
            "Additional standalone serialization of the returned comparison document",
            lambda: result.model_dump_json().encode("utf-8"),
        )

        def persist() -> None:
            target = directory / "serialized-comparison.json"
            partial = directory / "serialized-comparison.json.part"
            with partial.open("xb") as output:
                output.write(serialized)
                output.flush()
                os.fsync(output.fileno())
            os.link(partial, target)
            partial.unlink()

        measured(
            "persist",
            "Additional standalone fsync plus exclusive atomic manifest publication",
            persist,
        )
        measured(
            "render",
            "Privacy-filtered report construction and HTML/text/JSON publication "
            "without reexecuting inputs",
            lambda: ef.write_comparison_report(result, directory / "report"),
        )

        def verify() -> int:
            restored = ef.read_comparison(directory / "serialized-comparison.json")
            if restored != result:
                raise ValueError("comparison roundtrip changed")
            count = sum(1 for _ in ef.iter_differences(result.differences))
            verify_files(directory, inventory(directory))
            return count

        count = measured(
            "verify",
            "Comparison reader, all difference records, and complete evidence SHA-256 reread",
            verify,
        )
        elapsed = time.perf_counter() - start
    finally:
        resources = monitor.finish(time.perf_counter() - start)
    # Baselines are separate services and outside EquiFrame pipeline duration/RSS samples.
    baselines = (
        tuple(
            _baseline(spec, transferred, name)
            for name in ("pandas_assert", "duckdb_sql", "datacompy")
        )
        if spec.run_baselines
        else ()
    )
    evidence = inventory(directory)
    return ScaleTrial(
        case_sha256=digest(spec),
        repetition=repetition,
        cache_state="fresh_process_os_cache_uncontrolled"
        if repetition == 0
        else "warm_process_os_cache_uncontrolled",
        stages=tuple(stages),
        end_to_end_seconds=elapsed,
        resources=resources,
        comparison=result,
        verified_difference_records=count,
        evidence_bytes=sum(item.size_bytes for item in evidence),
        evidence=evidence,
        baselines=baselines,
    )


def main() -> None:
    from equiframe_benchmark.scaling import _environment

    spec = load_json(ScaleSpec, Path(sys.argv[1]))
    directory = Path(sys.argv[2])
    for repetition in range(spec.repetitions):
        trial = run_trial(spec, directory / f"trial-{repetition:03d}", repetition)
        save_scale_document(trial, directory / f"trial-{repetition:03d}.json")
    files = tuple(
        item
        for item in inventory(directory)
        if item.path in {f"trial-{i:03d}.json" for i in range(spec.repetitions)}
    )
    save_scale_document(
        ScaleWorkerCompletion(
            environment=_environment(), case_sha256=digest(spec), trial_files=files
        ),
        directory / "worker-completed.json",
    )


if __name__ == "__main__":
    main()
