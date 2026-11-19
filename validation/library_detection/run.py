"""Standalone generated-data benchmark of the installed EquiFrame 0.14.0 library.

No thesis corpus, human labels, network, service, DW or saved executable model.
Labels come from a separate exact Python oracle applied to materialized output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import random
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa

import equiframe as ef

WORKLOADS = ("identity", "discount_aggregation")
GroupedMetric = Literal[
    "prop_grupos_suma_modificada",
    "max_diferencia_relativa_grupo",
    "prop_grupos_cambio_desde_cero",
    "cobertura_grupos",
]
GROUPED_METRICS: tuple[GroupedMetric, ...] = (
    "prop_grupos_suma_modificada",
    "max_diferencia_relativa_grupo",
    "prop_grupos_cambio_desde_cero",
    "cobertura_grupos",
)
FAULTS = {
    "identity": ("fill_null", "drop_rows", "duplicate_rows", "permute_values"),
    "discount_aggregation": ("drop_group", "scale_amount", "redistribute", "one_cent"),
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def seed_for(workload: str, split: str, index: int) -> int:
    return int(digest([20261119, workload, split, index])[:16], 16)


def generated(workload: str, split: str, index: int) -> list[dict[str, Any]]:
    rng = random.Random(seed_for(workload, split, index))
    shifted = split == "shifted_normal"
    size = rng.randint(4096, 8192) if shifted else rng.randint(256, 1024)
    groups = rng.randint(40, 64) if shifted else rng.randint(8, 24)
    null_rate = rng.uniform(0.35, 0.45) if shifted else rng.uniform(0.05, 0.2)
    rates = [rng.randint(500, 1500) for _ in range(groups)]
    # Every group is present. IDs are data keys, never profile predictors.
    return [
        {
            "id": i,
            "department": f"g{i % groups}",
            "amount": (
                None
                if workload == "identity" and rng.random() < null_rate
                else rng.randint(100, 100000)
            ),
            "discount_bp": rates[i % groups],
        }
        for i in range(size)
    ]


def expected_rows(workload: str, source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Deliberately separate from the native Pandas groupby/transform code.
    if workload == "identity":
        return [{"id": r["id"], "amount": r["amount"]} for r in source]
    totals: dict[str, int] = defaultdict(int)
    for row in source:
        totals[row["department"]] += row["amount"] * (10000 - row["discount_bp"]) // 10000
    return [{"department": key, "total": totals[key]} for key in sorted(totals)]


def canonical(rows: list[dict[str, Any]]) -> list[str]:
    # Sorted JSON rows preserve multiplicity and NULL separately from zero.
    return sorted(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows)


def oracle(workload: str, source: list[dict[str, Any]], actual: list[dict[str, Any]]) -> bool:
    return canonical(actual) != canonical(expected_rows(workload, source))


def mutate(frame: Any, workload: str, kind: str, rng: random.Random) -> Any:
    if kind == "normal":
        return frame
    frame = frame.copy()
    if workload == "identity":
        if kind == "fill_null":
            frame["amount"] = frame["amount"].fillna(0)
        elif kind == "drop_rows":
            frame = frame.iloc[: -max(1, int(len(frame) * rng.uniform(0.02, 0.3)))]
        elif kind == "duplicate_rows":
            import pandas as pd

            frame = pd.concat([frame, frame.iloc[: rng.randint(1, max(2, len(frame) // 4))]])
        elif kind == "permute_values":
            positions = [
                i for i, v in enumerate(frame["amount"]) if v is not None and str(v) != "<NA>"
            ]
            a = positions[0]
            b = next(i for i in positions[1:] if frame.iloc[i, 1] != frame.iloc[a, 1])
            frame.iloc[a, 1], frame.iloc[b, 1] = frame.iloc[b, 1], frame.iloc[a, 1]
        else:
            raise ValueError(kind)
    elif kind == "drop_group":
        frame = frame.iloc[1:]
    elif kind == "scale_amount":
        frame["total"] = frame["total"] * rng.randint(2, 5)
    elif kind == "redistribute":
        delta = max(1, int(frame.iloc[0]["total"] * rng.uniform(0.02, 0.5)))
        frame.iloc[0, 1] += delta
        frame.iloc[1, 1] -= delta
    elif kind == "one_cent":
        frame.iloc[-1, 1] += 1
    else:
        raise ValueError(kind)
    return frame


def table_spec(name: str, columns: tuple[tuple[str, str, bool], ...]) -> ef.TableSpec:
    return ef.TableSpec(
        name=name,
        schema_spec=ef.TableSchema(
            columns=tuple(
                ef.ColumnSpec(
                    name=col,
                    logical_type=ef.StringType()
                    if typ == "str"
                    else ef.IntegerType(bits=64, signed=True),
                    nullable=nullable,
                    null_policy=ef.NullPolicy(representations=("null",)),
                    numeric_policy=None
                    if typ == "str"
                    else ef.NumericPolicy(comparison="exact", unit="unspecified"),
                )
                for col, typ, nullable in columns
            ),
            keys=(),
            multiplicity="preserve",
            order=ef.IgnoredOrder(),
        ),
    )


def specifications(workload: str) -> tuple[ef.Contract, ef.ProfileSpec]:
    source_columns = (
        ("id", "int", False),
        ("department", "str", False),
        ("amount", "int", workload == "identity"),
        ("discount_bp", "int", False),
    )
    output_columns = (
        (("id", "int", False), ("amount", "int", True))
        if workload == "identity"
        else (("department", "str", False), ("total", "int", False))
    )
    # Aggregations admits row ratios, cardinality and nullable rates. The first
    # workload is an identity transform evaluated under this declared family.
    contract = ef.Contract(
        schema_version="1.0",
        contract_id=f"library_benchmark.{workload}",
        revision=1,
        family="aggregations",
        inputs=(table_spec("source", source_columns),),
        output=table_spec("result", output_columns),
        rules=(),
        preconditions=(),
    )
    features: list[Any] = [
        ef.ProfileFeature(name="log_rows", metric="log_filas", table="result"),
        ef.ProfileFeature(
            name="row_ratio",
            metric="razon_salida_entrada",
            table="result",
            denominator_table="source",
        ),
    ]
    if workload == "identity":
        features.extend(
            (
                ef.ProfileFeature(
                    name="null_rate", metric="tasa_nulos", table="result", columns=("amount",)
                ),
                ef.ProfileFeature(
                    name="key_cardinality",
                    metric="cardinalidad_rel",
                    table="result",
                    columns=("id",),
                ),
            )
        )
    else:
        features.extend(
            ef.GroupedProfileFeature(
                name=metric,
                metric=metric,
                table="result",
                column="total",
                reference_table="source",
                reference_column="amount",
                by=("department",),
            )
            for metric in GROUPED_METRICS
        )
    return contract, ef.ProfileSpec(
        family="aggregations",
        feature_version="1.0" if workload == "identity" else "1.1",
        features=tuple(features),
    )


def arrow_source(rows: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(
        rows,
        schema=pa.schema(
            [
                ("id", pa.int64()),
                ("department", pa.string()),
                ("amount", pa.int64()),
                ("discount_bp", pa.int64()),
            ]
        ),
    )


def native_callback(workload: str, kind: str, seed: int) -> Callable[..., Any]:
    def transform(tables: Any, context: Any) -> Any:
        source = tables["source"]
        if workload == "identity":
            output = source[["id", "amount"]].copy()
        else:
            output = (
                source.assign(total=source["amount"] * (10000 - source["discount_bp"]) // 10000)
                .groupby("department", as_index=False)["total"]
                .sum()
            )
        return mutate(output, workload, kind, random.Random(seed))

    return transform


def one_case(
    workload: str, split: str, index: int, kind: str, directory: Path
) -> tuple[ef.ProfileVector, dict[str, Any]]:
    source = generated(workload, split, index)
    contract, spec = specifications(workload)
    registry = ef.TransformationRegistry()
    registry.register(
        ef.PandasTransformation(
            "generated_transform",
            native_callback(workload, kind, seed_for(workload, split, index)),
            "1",
        )
    )
    started = time.perf_counter()
    execution = ef.execute(
        ef.ExecutionPlan(
            contract=contract, engine="pandas", transformation_id="generated_transform"
        ),
        source=ef.LocalDataSource({"source": ef.ArrowInput(arrow_source(source))}),
        registry=registry,
        work_dir=directory / "execution",
    )
    execution_seconds = time.perf_counter() - started
    if execution.state != "completed":
        raise RuntimeError(f"{workload}/{split}/{index}: {execution.state}")
    # Use the actual captured result, never the injected-fault name, as truth.
    if execution.output is None:
        raise RuntimeError("Completed execution has no captured output")
    actual = ef.read_table(execution.output.data).to_pylist()
    started = time.perf_counter()
    divergent = oracle(workload, source, actual)
    oracle_seconds = time.perf_counter() - started
    if divergent != (kind != "normal"):
        raise RuntimeError("Generator produced a mislabeled/no-op mutation; evaluation stopped")
    started = time.perf_counter()
    profile = ef.profile_execution(execution, spec=spec, work_dir=directory / "profile")
    profile_seconds = time.perf_counter() - started
    if not profile.complete:
        raise RuntimeError("Incomplete generated-case profile; evaluation stopped")
    record = {
        "workload": workload,
        "split": split,
        "index": index,
        "fault": kind,
        "source_sha256": digest(source),
        "actual_sha256": digest(canonical(actual)),
        "expected_sha256": digest(canonical(expected_rows(workload, source))),
        "profile_sha256": digest(profile.vector.model_dump(mode="json")),
        "divergent": divergent,
        "source_rows": len(source),
        "output_rows": len(actual),
        "execution_seconds": execution_seconds,
        "profile_seconds": profile_seconds,
        "oracle_seconds": oracle_seconds,
    }
    return profile.vector, record


def wilson(successes: int, trials: int) -> list[float] | None:
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    divisor = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / divisor
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / divisor
    return [max(0.0, centre - radius), min(1.0, centre + radius)]


def metrics(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    tp = fp = tn = fn = unavailable = 0
    for record in records:
        state = record[field]
        if state not in ("alert", "no_alert"):
            unavailable += 1
        elif record["divergent"]:
            tp += state == "alert"
            fn += state == "no_alert"
        else:
            fp += state == "alert"
            tn += state == "no_alert"

    def rate(a: int, b: int) -> float | None:
        return a / b if b else None

    return {
        "cases": len(records),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "unavailable": unavailable,
        "coverage": rate(len(records) - unavailable, len(records)),
        "recall": rate(tp, tp + fn),
        "precision": rate(tp, tp + fp),
        "f1": rate(2 * tp, 2 * tp + fp + fn),
        "false_positive_rate": rate(fp, fp + tn),
        "recall_wilson95": wilson(tp, tp + fn),
        "fpr_wilson95": wilson(fp, fp + tn),
    }


def distribution(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "n": len(values),
        "median_seconds": statistics.median(values),
        "p95_seconds": ordered[math.ceil(0.95 * len(values)) - 1],
        "total_seconds": sum(values),
    }


def protocol(smoke: bool) -> dict[str, Any]:
    return {
        "protocol": "equiframe-library-detection-1",
        "scope": "Generated-data library evaluation; not real-world efficacy or thesis acceptance",
        "purpose": "smoke" if smoke else "evaluation",
        "generator_seed": 20261119,
        "training": 8 if smoke else 256,
        "calibration": 8 if smoke else 256,
        "test_normal": 4 if smoke else 256,
        "test_per_fault": 2 if smoke else 64,
        "shifted_normal": 2 if smoke else 128,
        "workloads": list(WORKLOADS),
        "faults": FAULTS,
        "primary_forest_seed": 7,
        "sensitivity_forest_seeds": [] if smoke else [23, 71],
        "n_estimators": 200,
        "max_samples": 256,
        "alpha": "0.05",
        "threshold_rule": "strict score > empirical calibration quantile ceil((1-alpha)*n)",
        "selection": (
            "Training and calibration contain only exact-oracle-confirmed correct executions; "
            "no labels/fault IDs/expected or peer outputs in profile"
        ),
        "partitions": (
            "Independent deterministic seeds per workload/split/index; "
            "unique source hashes checked; test never used to tune features/thresholds/models"
        ),
        "normal_distributions": (
            "256..1024 rows; identity null probability U(.05,.20); 8..24 groups; "
            "per-group discount 500..1500bp; integer cents"
        ),
        "shifted_normal_distribution": (
            "4096..8192 rows; identity null probability U(.35,.45); 40..64 groups; "
            "same correct transformation"
        ),
        "claims": (
            "Per-workload/fault recall, FPR and unavailable coverage; Wilson95 intervals "
            "conditional on this generator and fixed model. Shifted correct cases reported "
            "separately. No acceptance score threshold or best-seed selection."
        ),
        "cost_scope": (
            "Wall clock per native execution/materialization, profile extraction and Python "
            "exact labeling; fit/calibration/batch inference separately; generation/import/file "
            "cleanup excluded. Not an end-to-end production latency guarantee."
        ),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "equiframe_required": "0.14.0",
    }


def run(output: Path, *, smoke: bool = False) -> dict[str, Any]:
    if ef.__version__ != "0.14.0" or "site-packages" not in ef.__file__:
        raise RuntimeError(
            "Run against the installed public 0.14.0 library, outside its source tree"
        )
    output.mkdir(parents=True, exist_ok=False)
    plan = protocol(smoke)
    plan_hash = digest(plan)
    (output / "protocol.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "equiframe": ef.__version__,
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scikit-learn", "pandas", "pyarrow")
        },
        "native_engine": "pandas",
        "forest_jobs": 1,
    }
    records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for workload in WORKLOADS:
        vectors: dict[str, list[ef.ProfileVector]] = defaultdict(list)
        rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        splits = [
            ("training", plan["training"], "normal"),
            ("calibration", plan["calibration"], "normal"),
            ("test_normal", plan["test_normal"], "normal"),
            ("shifted_normal", plan["shifted_normal"], "normal"),
        ]
        splits.extend((kind, plan["test_per_fault"], kind) for kind in FAULTS[workload])
        for split, count, kind in splits:
            for index in range(count):
                # All scratch paths belong to this run and are removed before
                # the next case. No growing database or real input is touched.
                with tempfile.TemporaryDirectory(prefix="case-", dir=output) as temporary:
                    vector, record = one_case(workload, split, index, kind, Path(temporary))
                if record["source_sha256"] in hashes:
                    raise RuntimeError("Source data crossed split/case boundary")
                hashes.add(record["source_sha256"])
                vectors[split].append(vector)
                rows[split].append(record)
            print(f"{workload}: {split} {count} completed", flush=True)
        _, spec = specifications(workload)
        training = ef.NormalTrainingProfiles(
            purpose="normal_training",
            selection_manifest_sha256=digest(rows["training"]),
            profiles=tuple(vectors["training"]),
        )
        calibration = ef.NormalCalibrationProfiles(
            purpose="normal_calibration",
            selection_manifest_sha256=digest(rows["calibration"]),
            profiles=tuple(vectors["calibration"]),
        )
        test_splits = ["test_normal", "shifted_normal", *FAULTS[workload]]
        test_vectors = tuple(v for split in test_splits for v in vectors[split])
        test_records = [r for split in test_splits for r in rows[split]]
        workload_models = []
        for seed in [plan["primary_forest_seed"], *plan["sensitivity_forest_seeds"]]:
            started = time.perf_counter()
            fit = ef.fit_detectors(
                training,
                spec=spec,
                config=ef.IsolationForestConfig(
                    random_state=seed,
                    n_estimators=plan["n_estimators"],
                    max_samples=plan["max_samples"],
                ),
                support=ef.DetectorSupport(
                    min_training_rows=plan["training"],
                    min_calibration_rows=plan["calibration"],
                    rationale=(
                        "Prespecified generated-data benchmark support; not a statistical guarantee"
                    ),
                ),
            )
            fit_seconds = time.perf_counter() - started
            started = time.perf_counter()
            bundle = ef.calibrate_detectors(fit, calibration, alpha=plan["alpha"])
            calibration_seconds = time.perf_counter() - started
            before = ef.detector_fingerprint(bundle)
            started = time.perf_counter()
            detected = ef.detect(bundle, test_vectors)
            infer_seconds = time.perf_counter() - started
            if ef.detector_fingerprint(bundle) != before:
                raise RuntimeError("Model changed during test inference")
            scored = []
            for record, m, b in zip(test_records, detected.m, detected.b, strict=True):
                scored.append(
                    {
                        **record,
                        "forest_seed": seed,
                        "m": m.result.decision,
                        "m_score": m.score,
                        "b": b.result.decision,
                        "b_score": b.score,
                    }
                )
            records.extend(scored)
            partitions = {
                "in_distribution": [r for r in scored if r["split"] != "shifted_normal"],
                "shifted_correct": [r for r in scored if r["split"] == "shifted_normal"],
            }
            partitions.update(
                {kind: [r for r in scored if r["fault"] == kind] for kind in FAULTS[workload]}
            )
            model = {
                "seed": seed,
                "fit_seconds": fit_seconds,
                "calibration_seconds": calibration_seconds,
                "batch_inference_seconds": infer_seconds,
                "batch_inference_cases": len(test_vectors),
                "batch_mean_inference_seconds": infer_seconds / len(test_vectors),
                "training_unique_vectors": len(
                    {digest(v.model_dump(mode="json")) for v in vectors["training"]}
                ),
                "fit_state": {"m": fit.m.state, "b": fit.b.state},
                "calibration_state": {"m": bundle.m.state, "b": bundle.b.state},
                "threshold": {"m": bundle.m.threshold, "b": bundle.b.threshold},
                "bundle_sha256": before,
                "results": {
                    key: {method: metrics(selected, method) for method in ("m", "b")}
                    for key, selected in partitions.items()
                },
            }
            workload_models.append(model)
            print(
                f"{workload}: model seed{seed} evaluated; fit {fit.m.state}/{fit.b.state}",
                flush=True,
            )
        all_generated = [r for split_rows in rows.values() for r in split_rows]
        summaries.append(
            {
                "workload": workload,
                "generated_executions": len(all_generated),
                "profile_spec": spec.model_dump(mode="json"),
                "models": workload_models,
                "costs": {
                    stage: distribution([r[stage] for r in all_generated])
                    for stage in ("execution_seconds", "profile_seconds", "oracle_seconds")
                },
            }
        )
    fields = list(records[0])
    with (output / "cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    report = {
        "protocol_sha256": plan_hash,
        "environment": environment,
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": plan["purpose"],
        "unique_source_cases": len(hashes),
        "workloads": summaries,
        "case_records_sha256": hashlib.sha256((output / "cases.csv").read_bytes()).hexdigest(),
        "limitations": [
            "Generated cases only; no external project effectiveness claim",
            "Distribution and fault prevalence are designed, not representative market prevalence",
            "Wilson intervals describe generator trials conditional on a fixed fitted model",
            "Sensitivity seeds share the same test cases and do not increase sample size",
            "Correct shifted workloads may trigger novelty alerts",
            "Global statistics can hide exact keyed/value errors",
            "Only Pandas native execution is measured in this benchmark",
            "Timing observations depend on this host, cache and concurrent load; "
            "no peak memory or production latency claim",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--smoke", action="store_true", help="Engineering smoke only; never scientific evidence"
    )
    args = parser.parse_args()
    report = run(args.output, smoke=args.smoke)
    print(
        json.dumps(
            {
                "purpose": report["purpose"],
                "unique_source_cases": report["unique_source_cases"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
