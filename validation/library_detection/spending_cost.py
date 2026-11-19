"""Repeated API cost measurements on fixed captured public-spending outputs.

Run after other experiment/test jobs finish. Does not refit or retune a model.
Native execution, expected-table generation, and imports are excluded from the
paired profile/inference/comparison costs and recorded as separate operations.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

import public_spending as primary
import pyarrow as pa
from spending_severity import source_table

import equiframe as ef


def run(csv_dir: Path, primary_dir: Path, model_dir: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("Use a fresh output folder")
    protocol = json.loads((primary_dir / "protocol.json").read_bytes())
    report = json.loads((primary_dir / "report.json").read_bytes())
    procedures, _ = primary.cohort(csv_dir)
    cases, _ = primary.select_cases(procedures, protocol["counts"])
    probes = [c for c in cases if c["split"] == "test" and c["kind"] == "normal"][:16]
    models = {
        v: ef.read_detector_bundle(model_dir / ("private-model-" + v + ".json"))
        for v in primary.VERSIONS
    }
    for v, model in models.items():
        expected_id = next(
            s["bundle_sha256"] for s in report["summaries"] if s["version"] == v and s["seed"] == 7
        )
        if ef.detector_fingerprint(model) != expected_id:
            raise RuntimeError("Cost pass must reuse the frozen primary model")
    rows = []
    vectors: dict[str, list[ef.ProfileVector]] = {v: [] for v in primary.VERSIONS}
    for i, case in enumerate(probes):
        registry = ef.TransformationRegistry()
        registry.register(primary.registration(case["source"], "normal", "pandas"))
        contract = primary.specifications("1.1")[0]
        with tempfile.TemporaryDirectory(prefix="equiframe-cost-") as scratch:
            folder = Path(scratch)
            execution = ef.execute(
                ef.ExecutionPlan(contract=contract, engine="pandas", transformation_id="spending"),
                source=ef.LocalDataSource({"source": ef.ArrowInput(source_table(case["source"]))}),
                registry=registry,
                work_dir=folder / "execution",
            )
            if execution.output is None:
                raise RuntimeError("Cost execution failed")
            gold = pa.Table.from_pylist(
                primary.expected(case["source"]),
                schema=pa.schema(
                    [("buyer", pa.string()), ("currency", pa.string()), ("total", pa.int64())]
                ),
            )
            for repeat in range(3):
                row: dict[str, Any] = {
                    "case": i,
                    "repeat": repeat,
                    "source_sha256": case["source_sha256"],
                }
                # Alternate operation order to limit a systematic order effect.
                operations: list[Literal["compare", "1.1", "1.2"]] = ["compare", "1.1", "1.2"]
                operations = operations[repeat:] + operations[:repeat]
                for operation in operations:
                    start = time.perf_counter()
                    if operation == "compare":
                        comparison = ef.compare(
                            execution.output,
                            ef.ArrowInput(gold),
                            contract=contract,
                            reference="expected",
                            policy=ef.ComparisonPolicy(
                                index="ignore", justification="Business identity is buyer/currency."
                            ),
                            work_dir=folder / ("compare-" + str(repeat)),
                        )
                        row["comparison_seconds"] = time.perf_counter() - start
                        if not comparison.complete or comparison.state != "equivalent":
                            raise RuntimeError("Cost probe differs from the independent expected")
                    else:
                        measured = ef.profile_execution(
                            execution,
                            spec=primary.specifications(operation)[1],
                            work_dir=folder / ("profile-" + operation + "-" + str(repeat)),
                        )
                        row["profile_seconds_" + operation] = time.perf_counter() - start
                        if not measured.complete:
                            raise RuntimeError("Incomplete cost profile")
                        if repeat == 0:
                            vectors[operation].append(measured.vector)
                        start = time.perf_counter()
                        result = ef.detect_component(
                            models[operation], (measured.vector,), method="isolation_forest"
                        )
                        row["m_single_seconds_" + operation] = time.perf_counter() - start
                        if result.scores.state != "scored":
                            raise RuntimeError("M-only cost probe unavailable")
                rows.append(row)
    batches = {}
    for v, model in models.items():
        elapsed = []
        for _ in range(3):
            start = time.perf_counter()
            ef.detect_component(model, tuple(vectors[v]), method="isolation_forest")
            elapsed.append(time.perf_counter() - start)
        batches[v] = {
            "cases": 16,
            "repetitions": elapsed,
            "median_seconds_per_case": statistics.median(elapsed) / 16,
        }
    summary = {}
    for v in primary.VERSIONS:
        combined = [r["profile_seconds_" + v] + r["m_single_seconds_" + v] for r in rows]
        summary[v] = {
            "profile_median_seconds": statistics.median(r["profile_seconds_" + v] for r in rows),
            "m_single_median_seconds": statistics.median(r["m_single_seconds_" + v] for r in rows),
            "paired_combined_median_seconds": statistics.median(combined),
            "full_comparison_median_seconds": statistics.median(
                r["comparison_seconds"] for r in rows
            ),
            "combined_faster_pairs": sum(
                c < r["comparison_seconds"] for c, r in zip(combined, rows, strict=True)
            ),
            "paired_observations": len(rows),
        }
    output.mkdir(parents=True)
    (output / "report.json").write_text(
        json.dumps(
            {
                "unique_inputs": 16,
                "repeats_per_input": 3,
                "engine": "pandas",
                "platform": platform.platform(),
                "python": platform.python_version(),
                "library": ef.__version__,
                "models_refitted": False,
                "scope": (
                    "Repeated local API wall-clock costs; 48 pairs are 16 inputs with three "
                    "repeats, not 48 independent inputs. No population latency guarantee. "
                    "Expected-table generation and native execution excluded equally. "
                    "No whole-process native memory claim."
                ),
                "summary": summary,
                "m_only_batches": batches,
                "records": rows,
            },
            indent=2,
            allow_nan=False,
        ),
        encoding="utf8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("csv-dir", "primary", "models", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.csv_dir, args.primary, args.models, args.output)


if __name__ == "__main__":
    main()
