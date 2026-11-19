"""Frozen public-data proof of concept; labels are exact output checks, not fault names.

Read an immutable local SERCOP CSV delivery. Do not upload source rows or models.
Actual awards are used; deliberately altered ETL implementations are experimental.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import random
import statistics
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pyarrow as pa
from run import canonical, digest, distribution, metrics, table_spec
from runtime_receipt import receipt

import equiframe as ef

FILES = {
    "releases_2025.csv": "ac2befc303dbbe1aaeeecc8739f657878e05cb06a8cf12d6560356a30bc81d24",
    "awards_2025.csv": "63cdb63bc413c419a3bf33cce3d6755e5566440e959c56ec77f18d43c3d6e91d",
}
LIMIT_CENTS = 10_000
Version = Literal["1.1", "1.2"]
GroupMetric = Literal[
    "prop_grupos_suma_modificada",
    "max_diferencia_relativa_grupo",
    "prop_grupos_cambio_desde_cero",
    "cobertura_grupos",
    "media_diferencia_relativa_grupo",
    "varianza_diferencia_relativa_grupo",
]
VERSIONS: tuple[Version, ...] = ("1.1", "1.2")
BASE_METRICS: tuple[GroupMetric, ...] = (
    "prop_grupos_suma_modificada",
    "max_diferencia_relativa_grupo",
    "prop_grupos_cambio_desde_cero",
    "cobertura_grupos",
)
NEW_METRICS: tuple[GroupMetric, ...] = (
    "media_diferencia_relativa_grupo",
    "varianza_diferencia_relativa_grupo",
)
FAULTS = ("drop_group", "scale_group", "redistribute", "one_cent")
ENGINES = ("pandas", "polars", "duckdb")


def cohort(csv_dir: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    for filename, expected in FILES.items():
        if hashlib.sha256((csv_dir / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("Source differs from the identified public snapshot: " + filename)
    publications = {}
    with (csv_dir / "releases_2025.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["ocid"] in publications:
                raise ValueError("Duplicate procedure; no last-row selection is permitted")
            local_date = (
                datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
                .astimezone(ZoneInfo("America/Guayaquil"))
                .date()
            )
            publications[row["ocid"]] = (row["buyer_id"], local_date.year == 2025)
    procedures: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded: Counter[str] = Counter()
    seen = set()
    with (csv_dir / "awards_2025.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            identity = row["ocid"], row["id"]
            if identity in seen:
                raise ValueError("Duplicate award identity")
            seen.add(identity)
            buyer, included = publications[row["ocid"]]
            if not included:
                excluded["release_date_outside_2025"] += 1
                continue
            if not buyer or not row["currency"]:
                excluded["missing_buyer_or_currency"] += 1
                continue
            if not row["amount"]:
                excluded["missing_amount_for_numeric_group_study"] += 1
                continue
            decimal = Decimal(row["amount"]) * 100 if row["amount"] else None
            if decimal is not None and (not decimal.is_finite() or decimal != int(decimal)):
                raise ValueError("Amount cannot be represented in exact cents")
            procedures[row["ocid"]].append(
                {
                    "ocid": row["ocid"],
                    "award": row["id"],
                    "buyer": buyer,
                    "currency": row["currency"],
                    "amount": int(decimal) if decimal is not None else None,
                }
            )
    return dict(procedures), {
        "awards_read": len(seen),
        "procedures_included": len(procedures),
        "awards_included": sum(map(len, procedures.values())),
        "excluded": dict(excluded),
    }


def partition(ocid: str) -> str:
    bucket = int(digest(["equiframe-spending-20261119", ocid])[:16], 16) % 100
    return (
        "training"
        if bucket < 40
        else "development"
        if bucket < 50
        else "calibration"
        if bucket < 70
        else "test"
    )


def expected(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for row in source:
        amount = row["amount"]
        if amount is not None and amount >= LIMIT_CENTS:
            totals[row["buyer"], row["currency"]] += amount
    return [
        {"buyer": buyer, "currency": currency, "total": total}
        for (buyer, currency), total in sorted(totals.items())
    ]


def select_cases(
    procedures: dict[str, list[dict[str, Any]]], counts: dict[str, int]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pools: dict[str, list[str]] = defaultdict(list)
    for ocid in procedures:
        pools[partition(ocid)].append(ocid)
    cases = []
    selections = {}
    for split in ("training", "development", "calibration", "test"):
        pool = sorted(pools[split], key=lambda ocid: digest(["order", ocid]))
        cursor = 0
        skipped = 0
        used = []
        for index in range(counts[split]):
            shifted = split == "test" and index >= counts["test"] - counts["shift"]
            target = 64 if shifted else 32
            while True:
                source: list[dict[str, Any]] = []
                ids = []
                while len(source) < target:
                    if cursor >= len(pool):
                        raise ValueError(
                            "Insufficient disjoint source support for the frozen study"
                        )
                    ocid = pool[cursor]
                    cursor += 1
                    ids.append(ocid)
                    source.extend(procedures[ocid])
                # A predeclared applicability condition; never inspect detector decisions.
                gold = expected(source)
                if len(gold) >= 2 and len({row["currency"] for row in gold}) == 1:
                    break
                skipped += 1
            used.extend(ids)
            if split != "test" or shifted or index < counts["normal"]:
                kind = "normal"
            else:
                kind = FAULTS[(index - counts["normal"]) % len(FAULTS)]
            cases.append(
                {
                    "split": "shifted_normal" if shifted else split,
                    "index": index,
                    "kind": kind,
                    "source": source,
                    "source_sha256": digest(source),
                    "procedures_sha256": digest(sorted(ids)),
                    "procedure_count": len(ids),
                }
            )
        selections[split] = {
            "source_procedures": len(used),
            "used_ids_sha256": digest(sorted(used)),
            "available_procedures": len(pool),
            "skipped_nonapplicable_chunks": skipped,
        }
    hashes = [case["source_sha256"] for case in cases]
    if len(set(hashes)) != len(hashes):
        raise ValueError("Source duplication across cases")
    return cases, selections


def specifications(version: Version) -> tuple[ef.Contract, ef.ProfileSpec]:
    source = table_spec(
        "source",
        (
            ("ocid", "str", False),
            ("award", "str", False),
            ("buyer", "str", False),
            ("currency", "str", False),
            ("amount", "int", True),
        ),
    )
    result = table_spec(
        "result", (("buyer", "str", False), ("currency", "str", False), ("total", "int", False))
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="spending.threshold_aggregation",
        revision=1,
        family="aggregations",
        inputs=(source,),
        output=result,
        preconditions=(),
        rules=(),
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
    for metric in BASE_METRICS + (NEW_METRICS if version == "1.2" else ()):
        features.append(
            ef.GroupedProfileFeature(
                name=metric,
                metric=metric,
                table="result",
                column="total",
                reference_table="source",
                reference_column="amount",
                by=("buyer", "currency"),
            )
        )
    return contract, ef.ProfileSpec(
        family="aggregations", feature_version=version, features=tuple(features)
    )


def registration(source: list[dict[str, Any]], kind: str, engine: str) -> Any:
    selected = sorted(
        {
            (r["buyer"], r["currency"])
            for r in source
            if r["amount"] is not None and r["amount"] >= LIMIT_CENTS
        }
    )
    first, second = selected[:2]
    if engine == "pandas":

        def transform(tables: Any, context: Any) -> Any:
            frame = tables["source"]
            out = (
                frame.loc[frame.amount >= LIMIT_CENTS]
                .groupby(["buyer", "currency"], as_index=False)["amount"]
                .sum()
                .rename(columns={"amount": "total"})
            )
            a = (out.buyer == first[0]) & (out.currency == first[1])
            b = (out.buyer == second[0]) & (out.currency == second[1])
            if kind == "drop_group":
                out = out.loc[~a]
            elif kind == "scale_group":
                out.loc[a, "total"] *= 2
            elif kind == "redistribute":
                out.loc[a, "total"] += 100
                out.loc[b, "total"] -= 100
            elif kind == "one_cent":
                out.loc[a, "total"] += 1
            return out

        return ef.PandasTransformation("spending", transform, "proof.1")
    if engine == "polars":
        import polars as pl

        def transform(tables: Any, context: Any) -> Any:
            out = (
                tables["source"]
                .filter(pl.col("amount") >= LIMIT_CENTS)
                .group_by("buyer", "currency")
                .agg(pl.col("amount").sum().alias("total"))
            )
            a = (pl.col("buyer") == first[0]) & (pl.col("currency") == first[1])
            b = (pl.col("buyer") == second[0]) & (pl.col("currency") == second[1])
            if kind == "drop_group":
                return out.filter(~a)
            delta = a.cast(pl.Int64) * (
                100 if kind == "redistribute" else 1 if kind == "one_cent" else 0
            )
            if kind == "redistribute":
                delta = delta - b.cast(pl.Int64) * 100
            if kind == "scale_group":
                return out.with_columns(
                    pl.when(a).then(pl.col("total") * 2).otherwise(pl.col("total")).alias("total")
                )
            return out.with_columns((pl.col("total") + delta).alias("total"))

        return ef.PolarsTransformation("spending", transform, "proof.1")

    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    a = f"buyer={literal(first[0])} AND currency={literal(first[1])}"
    b = f"buyer={literal(second[0])} AND currency={literal(second[1])}"
    expression = "total"
    if kind == "scale_group":
        expression = f"CASE WHEN {a} THEN total*2 ELSE total END"
    elif kind == "redistribute":
        expression = f"total + CASE WHEN {a} THEN 100 WHEN {b} THEN -100 ELSE 0 END"
    elif kind == "one_cent":
        expression = f"total + CASE WHEN {a} THEN 1 ELSE 0 END"
    query = (
        "WITH grouped AS (SELECT buyer,currency,SUM(amount) AS total FROM source "
        f"WHERE amount>={LIMIT_CENTS} GROUP BY buyer,currency) SELECT buyer,currency,"
        f"CAST({expression} AS BIGINT) AS total FROM grouped"
        + (f" WHERE NOT ({a})" if kind == "drop_group" else "")
    )
    return ef.DuckDBTransformation("spending", query, "proof.1")


def execute_case(
    case: dict[str, Any],
    engine: str,
    folder: Path,
    profile: bool,
    versions: tuple[Version, ...] = VERSIONS,
) -> tuple[dict[str, Any], dict[str, ef.ProfileVector]]:
    source = case["source"]
    contract, _ = specifications("1.1")
    registry = ef.TransformationRegistry()
    registry.register(registration(source, case["kind"], engine))
    arrow = pa.Table.from_pylist(
        source,
        schema=pa.schema(
            [
                ("ocid", pa.string()),
                ("award", pa.string()),
                ("buyer", pa.string()),
                ("currency", pa.string()),
                ("amount", pa.int64()),
            ]
        ),
    )
    start = time.perf_counter()
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract, engine=engine, transformation_id="spending"),
        source=ef.LocalDataSource({"source": ef.ArrowInput(arrow)}),
        registry=registry,
        work_dir=folder / "execution",
    )
    execution_seconds = time.perf_counter() - start
    if execution.state != "completed" or execution.output is None:
        raise RuntimeError(f"{engine}: native execution failed: {execution.problem}")
    actual = ef.read_table(execution.output.data).to_pylist()
    start = time.perf_counter()
    gold = expected(source)
    divergent = canonical(actual) != canonical(gold)
    oracle_seconds = time.perf_counter() - start
    if divergent != (case["kind"] != "normal"):
        raise RuntimeError("No-op or mislabeled fault; do not report detection metrics")
    gold_table = pa.Table.from_pylist(
        gold,
        schema=pa.schema(
            [("buyer", pa.string()), ("currency", pa.string()), ("total", pa.int64())]
        ),
    )
    start = time.perf_counter()
    comparison = ef.compare(
        execution.output,
        ef.ArrowInput(gold_table),
        contract=contract,
        reference="expected",
        policy=ef.ComparisonPolicy(
            index="ignore",
            justification=(
                "The declared business identity is buyer/currency columns; na"
                "tive row indices have no domain meaning."
            ),
        ),
        work_dir=folder / "comparison",
    )
    comparison_seconds = time.perf_counter() - start
    if not comparison.complete or (comparison.state == "different") != divergent:
        raise RuntimeError(
            "Full comparison disagrees with independent exact output check: "
            + json.dumps(
                {
                    "state": comparison.state,
                    "complete": comparison.complete,
                    "diagnostics": [
                        item.model_dump(mode="json") for item in comparison.diagnostics
                    ],
                    "counts": comparison.counts.model_dump(mode="json"),
                }
            )
        )
    # R is a deliberately specified inexpensive contract subset, not the full oracle.
    start = time.perf_counter()
    required_total = sum(
        row["amount"]
        for row in source
        if row["amount"] is not None and row["amount"] >= LIMIT_CENTS
    )
    keys = [(row["buyer"], row["currency"]) for row in actual]
    r_alert = sum(row["total"] for row in actual) != required_total or len(keys) != len(set(keys))
    rule_seconds = time.perf_counter() - start
    record = {
        k: case[k]
        for k in ("split", "index", "kind", "source_sha256", "procedures_sha256", "procedure_count")
    }
    record.update(
        engine=engine,
        divergent=divergent,
        r="alert" if r_alert else "no_alert",
        source_rows=len(source),
        output_rows=len(actual),
        actual_sha256=digest(canonical(actual)),
        expected_sha256=digest(canonical(gold)),
        execution_seconds=execution_seconds,
        oracle_seconds=oracle_seconds,
        comparison_seconds=comparison_seconds,
        rule_seconds=rule_seconds,
    )
    vectors: dict[str, ef.ProfileVector] = {}
    if profile:
        for version in versions:
            _, spec = specifications(version)
            start = time.perf_counter()
            measured = ef.profile_execution(
                execution, spec=spec, work_dir=folder / ("profile-" + version)
            )
            record["profile_seconds_" + version] = time.perf_counter() - start
            if not measured.complete:
                raise RuntimeError("Incomplete profile; no imputed technical failures")
            vectors[version] = measured.vector
            record["profile_sha256_" + version] = digest(measured.vector.model_dump(mode="json"))
    return record, vectors


def bootstrap_delta(
    records: list[dict[str, Any]], left: str, right: str, divergent: bool
) -> dict[str, Any]:
    values = [
        int(r[left] == "alert") - int(r[right] == "alert")
        for r in records
        if r["divergent"] == divergent
    ]
    if not values:
        return {"n": 0, "delta": None, "paired_case_bootstrap95": None}
    rng = random.Random(20261119)
    estimates = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(2000))
    return {
        "n": len(values),
        "delta": statistics.mean(values),
        "paired_case_bootstrap95": [estimates[49], estimates[1949]],
        "scope": (
            "Conditional on frozen source selection and fitted model; eng"
            "ines and seeds are not resampling units."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-receipt", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, help="Reverify the receipt against installed bytes")
    parser.add_argument("--baseline-only", action="store_true", help="Measure only profile 1.1")
    parser.add_argument(
        "--cost-model-dir", type=Path, help="Private output for the frozen seed-7 bundles"
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    versions = VERSIONS[:1] if args.baseline_only else VERSIONS
    identity = json.loads(args.runtime_receipt.read_bytes())
    if identity["version"] != ef.__version__:
        raise ValueError("Receipt version does not match the installed distribution")
    if args.wheel is not None and receipt(args.wheel) != identity:
        raise ValueError("Receipt does not match the installed wheel bytes")
    if args.cost_model_dir is not None:
        args.cost_model_dir.mkdir(exist_ok=False)
    args.output.mkdir(exist_ok=False)
    counts = (
        {"training": 8, "development": 4, "calibration": 8, "normal": 8, "fault": 8, "shift": 4}
        if args.smoke
        else {
            "training": 256,
            "development": 64,
            "calibration": 256,
            "normal": 512,
            "fault": 512,
            "shift": 128,
        }
    )
    counts["test"] = counts["normal"] + counts["fault"] + counts["shift"]
    procedures, inventory = cohort(args.csv_dir)
    cases, selection = select_cases(procedures, counts)
    source_root = Path(ef.__file__).resolve().parent
    protocol = {
        "created_at": datetime.now().astimezone().isoformat(),
        "engineering_smoke": args.smoke,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime_source_root": "installed equiframe package; exact modules listed below",
        "runtime_identity": identity,
        "wheel_reverified_at_execution": args.wheel is not None,
        "runtime_distribution_metadata_version": ef.__version__,
        "source_files": FILES,
        "inventory": inventory,
        "selection": selection,
        "counts": counts,
        "source_modules": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_root.glob("*.py")
        },
        "normal_query": (
            "amount >= 100 original monetary units; sum by buyer and curr"
            "ency. No currency conversion."
        ),
        "helper_sha256": hashlib.sha256(
            Path(__file__).with_name("run.py").read_bytes()
        ).hexdigest(),
        "actual_limit_cents": LIMIT_CENTS,
        "partition_unit": "whole OCID; deterministic hash buckets 40/10/20/30",
        "profile_versions": versions,
        "alpha": "0.05",
        "trees": 200,
        "max_samples": 256,
        "seeds": [7, 23, 71],
        "primary_seed": 7,
        "hypotheses": {
            "H1": "hybrid sensitivity - R >= 0.05",
            "H2": "hybrid FPR - R <= 0.02",
            "H3": (
                "profile plus inference faster than a complete comparison of "
                "the same materialized outputs"
            ),
        },
        "new_feature_contrast": None
        if args.baseline_only
        else (
            "same cases and information in baseline; add only group-relat"
            "ive-change population mean and variance"
        ),
        "rules": (
            "exact selected input total conservation and output composite"
            "-key uniqueness; intentionally incomplete contract subset"
        ),
        "truth": (
            "separate Python integer/dictionary oracle on actual captured"
            " output; no manual labels or detector-derived labels"
        ),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("pandas", "polars", "duckdb", "pyarrow", "scikit-learn", "numpy")
        },
    }
    (args.output / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    vectors: dict[str, dict[str, list[ef.ProfileVector]]] = {
        version: defaultdict(list) for version in versions
    }
    records = []
    native = []
    for index, case in enumerate(cases):
        split = case["split"]
        is_testing = split in ("test", "shifted_normal")
        primary = None
        primary_vectors = None
        for engine in ENGINES if is_testing else ("pandas",):
            with tempfile.TemporaryDirectory(prefix="equiframe-spending-") as scratch:
                row, measured = execute_case(
                    case, engine, Path(scratch), profile=True, versions=versions
                )
            native.append(row)
            if primary is None:
                primary, primary_vectors = row, measured
            else:
                for key in (
                    "divergent",
                    "r",
                    "actual_sha256",
                    *("profile_sha256_" + version for version in versions),
                ):
                    if row[key] != primary[key]:
                        raise RuntimeError(
                            "Engine disagreement must be investigated before pooling: " + key
                        )
        assert primary is not None and primary_vectors is not None
        records.append(primary)
        for version in vectors:
            vectors[version][split].append(primary_vectors[version])
        if index % 32 == 0:
            print(
                json.dumps(
                    {
                        "completed_cases": index + 1,
                        "native_executions": len(native),
                        "total_cases": len(cases),
                    }
                ),
                flush=True,
            )
    summaries = []
    scored: list[dict[str, Any]] = []
    for version in versions:
        for seed in (7, 23, 71):
            fit = ef.fit_detectors(
                ef.NormalTrainingProfiles(
                    purpose="normal_training",
                    selection_manifest_sha256=digest([selection["training"], version]),
                    profiles=tuple(vectors[version]["training"]),
                ),
                spec=specifications(version)[1],
                config=ef.IsolationForestConfig(
                    n_estimators=200, max_samples=256, random_state=seed
                ),
                support=ef.DetectorSupport(
                    min_training_rows=8 if args.smoke else 256,
                    min_calibration_rows=8 if args.smoke else 256,
                    rationale=(
                        "Prespecified technical support for a controlled proof of con"
                        "cept; no population power claim"
                    ),
                ),
            )
            bundle = ef.calibrate_detectors(
                fit,
                ef.NormalCalibrationProfiles(
                    purpose="normal_calibration",
                    selection_manifest_sha256=digest([selection["calibration"], version]),
                    profiles=tuple(vectors[version]["calibration"]),
                ),
                alpha="0.05",
            )
            if seed == 7 and args.cost_model_dir is not None:
                ef.write_detector_bundle(
                    bundle, args.cost_model_dir / f"private-model-{version}.json"
                )
            testing = [r.copy() for r in records if r["split"] in ("test", "shifted_normal")]
            probes = tuple(vectors[version]["test"] + vectors[version]["shifted_normal"])
            start = time.perf_counter()
            detection = ef.detect(bundle, probes)
            inference_seconds = time.perf_counter() - start
            for row, m, b in zip(testing, detection.m, detection.b, strict=True):
                row.update(
                    version=version,
                    seed=seed,
                    m=m.result.decision,
                    b=b.result.decision,
                    m_score=m.score,
                    m_threshold=m.threshold,
                    b_score=b.score,
                    b_threshold=b.threshold,
                )
                row["h"] = (
                    "alert"
                    if "alert" in (row["r"], row["m"])
                    else "no_alert"
                    if row["m"] == "no_alert"
                    else "not_evaluable"
                )
            main_rows = [r for r in testing if r["split"] == "test"]
            shifted = [r for r in testing if r["split"] == "shifted_normal"]
            summaries.append(
                {
                    "version": version,
                    "seed": seed,
                    "main": {method: metrics(main_rows, method) for method in ("r", "m", "b", "h")},
                    "shifted_normal": {
                        method: metrics(shifted, method) for method in ("r", "m", "b", "h")
                    },
                    "per_fault": {
                        kind: {
                            method: metrics([r for r in main_rows if r["kind"] == kind], method)
                            for method in ("r", "m", "b", "h")
                        }
                        for kind in FAULTS
                    },
                    "hybrid_minus_rules_recall": bootstrap_delta(main_rows, "h", "r", True),
                    "hybrid_minus_rules_fpr": bootstrap_delta(main_rows, "h", "r", False),
                    "inference_batch_seconds": inference_seconds,
                    "bundle_sha256": ef.detector_fingerprint(bundle),
                    "m_state": fit.m.state,
                    "m_tree_count": len(fit.m.trees),
                    "m_split_nodes": sum(
                        node.left is not None for tree in fit.m.trees for node in tree.nodes
                    ),
                    "calibration_state": bundle.m.state,
                    "threshold": bundle.m.threshold,
                    "ablation": (
                        "R omits M; H differs only by OR with the recorded actual M decisions"
                    ),
                }
            )
            scored.extend(testing)
    report = {
        "protocol_sha256": hashlib.sha256((args.output / "protocol.json").read_bytes()).hexdigest(),
        "cases": len(cases),
        "unique_test_cases": counts["test"],
        "native_executions": len(native),
        "engine_output_and_profile_parity": True,
        "source_selection": selection,
        "summaries": summaries,
        "timings": {
            engine: {
                key: distribution([r[key] for r in native if r["engine"] == engine])
                for key in (
                    "execution_seconds",
                    *("profile_seconds_" + version for version in versions),
                    "oracle_seconds",
                    "comparison_seconds",
                    "rule_seconds",
                )
            }
            for engine in ENGINES
        },
        "H3_scope": (
            "Profile and full-comparison stages exclude native execution."
            " The same captured output and already materialized independe"
            "nt expected table are used; costs include each API's reads a"
            "nd validation. Inference is a shared frozen-model batch, not"
            " isolated single-case latency."
        ),
        "interpretation": (
            "Real public inputs with controlled ETL defects; no fraud lab"
            "els, field deployment or human review. Conditional uncertain"
            "ty, single snapshot and host. Test entities may recur across"
            " procedure-disjoint partitions."
        ),
    }
    for filename, data in (
        ("report.json", report),
        ("native-records.json", native),
        ("scored-records.json", scored),
    ):
        (args.output / filename).write_text(
            json.dumps(data, indent=2, allow_nan=False), encoding="utf-8"
        )
    print(
        json.dumps({"finished": True, "cases": len(cases), "native_executions": len(native)}),
        flush=True,
    )


if __name__ == "__main__":
    main()
