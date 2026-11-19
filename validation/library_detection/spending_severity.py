"""Prespecified severity extension and actual tree-path evidence.

Sixty-four unused source chunks each receive five paired variants. They are
64 independent source groups, not 320 independent input samples. No raw data
or fitted model is published. The exact grouped rule is a stronger comparator
than a global-total check for this completely specified transformation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import struct
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import public_spending as primary
import pyarrow as pa
import pyarrow.compute as pc
from run import canonical, digest, metrics

import equiframe as ef

LEVELS = ("correct", "one_cent", "one_percent", "ten_percent", "fifty_percent")


def extra_sources(
    procedures: dict[str, list[dict[str, Any]]], main: list[dict[str, Any]], count: int
) -> list[list[dict[str, Any]]]:
    used = {row["ocid"] for case in main for row in case["source"]}
    remaining = sorted(
        (ocid for ocid in procedures if primary.partition(ocid) == "test" and ocid not in used),
        key=lambda ocid: digest(["severity-order-20261119", ocid]),
    )
    result = []
    cursor = 0
    for _ in range(count):
        while True:
            rows: list[dict[str, Any]] = []
            while len(rows) < 32:
                if cursor >= len(remaining):
                    raise ValueError("Insufficient untouched source procedures")
                rows.extend(procedures[remaining[cursor]])
                cursor += 1
            gold = primary.expected(rows)
            if len(gold) >= 2 and len({row["currency"] for row in gold}) == 1:
                break
        result.append(rows)
    return result


def amount_to_move(source: list[dict[str, Any]], level: str) -> int:
    gold = primary.expected(source)
    smaller = min(gold[0]["total"], gold[1]["total"])
    return (
        0
        if level == "correct"
        else 1
        if level == "one_cent"
        else max(1, smaller // {"one_percent": 100, "ten_percent": 10, "fifty_percent": 2}[level])
    )


def transformation(source: list[dict[str, Any]], delta: int, engine: str) -> Any:
    normal = primary.registration(source, "normal", engine)
    keys = [(row["buyer"], row["currency"]) for row in primary.expected(source)]
    first, second = keys[:2]
    if engine == "pandas":

        def pandas_transform(tables: Any, context: Any) -> Any:
            out = normal.callback(tables, context)
            a = (out.buyer == first[0]) & (out.currency == first[1])
            b = (out.buyer == second[0]) & (out.currency == second[1])
            out.loc[a, "total"] += delta
            out.loc[b, "total"] -= delta
            return out

        return ef.PandasTransformation("severity", pandas_transform, "severity.1")
    if engine == "polars":
        import polars as pl

        def polars_transform(tables: Any, context: Any) -> Any:
            out = normal.callback(tables, context)
            a = (pl.col("buyer") == first[0]) & (pl.col("currency") == first[1])
            b = (pl.col("buyer") == second[0]) & (pl.col("currency") == second[1])
            return out.with_columns(
                (pl.col("total") + a.cast(pl.Int64) * delta - b.cast(pl.Int64) * delta).alias(
                    "total"
                )
            )

        return ef.PolarsTransformation("severity", polars_transform, "severity.1")

    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    a = f"buyer={literal(first[0])} AND currency={literal(first[1])}"
    b = f"buyer={literal(second[0])} AND currency={literal(second[1])}"
    return ef.DuckDBTransformation(
        "severity",
        f"WITH normal AS ({normal.sql}) SELECT buyer,currency,CAST(total + "
        f"CASE WHEN {a} THEN {delta} WHEN {b} THEN -{delta} ELSE 0 END "
        "AS BIGINT) AS total FROM normal",
        "severity.1",
    )


def source_table(source: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(
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


def one_variant(
    source: list[dict[str, Any]], group: int, level: str, engine: str, folder: Path
) -> tuple[dict[str, Any], dict[str, ef.ProfileVector]]:
    delta = amount_to_move(source, level)
    registry = ef.TransformationRegistry()
    registry.register(transformation(source, delta, engine))
    arrow = source_table(source)
    contract = primary.specifications("1.1")[0]
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract, engine=engine, transformation_id="severity"),
        source=ef.LocalDataSource({"source": ef.ArrowInput(arrow)}),
        registry=registry,
        work_dir=folder / "execution",
    )
    if execution.state != "completed" or execution.output is None:
        raise RuntimeError("Native severity execution did not complete")
    actual_table = ef.read_table(execution.output.data)
    actual, gold = actual_table.to_pylist(), primary.expected(source)
    divergent = canonical(actual) != canonical(gold)
    if divergent != (level != "correct"):
        raise RuntimeError("Controlled defect did not change the actual result")
    # This independent Arrow filter implements the declared selection. The rule
    # compares grouped input/output sums; it does not read a label or model score.
    filtered = (
        arrow.filter(pc.greater_equal(arrow["amount"], primary.LIMIT_CENTS))
        .select(["buyer", "currency", "amount"])
        .rename_columns(["buyer", "currency", "total"])
    )
    start = time.perf_counter()
    grouped = ef.compare_grouped(actual_table, filtered, by=("buyer", "currency"), column="total")
    grouped_seconds = time.perf_counter() - start
    r_group = (
        "not_evaluable"
        if not grouped.complete
        else "alert"
        if grouped.modified_groups + grouped.added_groups + grouped.removed_groups
        else "no_alert"
    )
    r_global = (
        "alert"
        if sum(row["total"] for row in actual)
        != sum(row["amount"] for row in source if row["amount"] >= primary.LIMIT_CENTS)
        else "no_alert"
    )
    vectors: dict[str, ef.ProfileVector] = {}
    row = {
        "group": group,
        "level": level,
        "engine": engine,
        "source_sha256": digest(source),
        "actual_sha256": digest(canonical(actual)),
        "expected_sha256": digest(canonical(gold)),
        "divergent": divergent,
        "r_global": r_global,
        "r_group": r_group,
        "grouped_rule_seconds": grouped_seconds,
        "moved_cents": delta,
        "source_rows": len(source),
        "_actual_rows": canonical(actual),
    }
    for version in primary.VERSIONS:
        measured = ef.profile_execution(
            execution,
            spec=primary.specifications(version)[1],
            work_dir=folder / ("profile-" + version),
        )
        if not measured.complete:
            raise RuntimeError("Incomplete severity profile")
        vectors[version] = measured.vector
        row["profile_sha256_" + version] = digest(measured.vector.model_dump(mode="json"))
    return row, vectors


def reconstruct_models(
    main: list[dict[str, Any]], selection: dict[str, Any], output: Path
) -> dict[str, ef.DetectorBundle]:
    vectors: dict[str, dict[str, list[ef.ProfileVector]]] = {
        version: defaultdict(list) for version in primary.VERSIONS
    }
    count = 0
    for case in main:
        if case["split"] not in ("training", "calibration"):
            continue
        with tempfile.TemporaryDirectory(prefix="equiframe-severity-fit-") as scratch:
            _, measured = primary.execute_case(case, "pandas", Path(scratch), True)
        for version in primary.VERSIONS:
            vectors[version][case["split"]].append(measured[version])
        count += 1
        if count % 64 == 0:
            print(json.dumps({"reconstructed_training_calibration_cases": count}), flush=True)
    models: dict[str, ef.DetectorBundle] = {}
    for version in primary.VERSIONS:
        fit = ef.fit_detectors(
            ef.NormalTrainingProfiles(
                purpose="normal_training",
                selection_manifest_sha256=digest([selection["training"], version]),
                profiles=tuple(vectors[version]["training"]),
            ),
            spec=primary.specifications(version)[1],
            config=ef.IsolationForestConfig(n_estimators=200, max_samples=256, random_state=7),
            support=ef.DetectorSupport(
                min_training_rows=256,
                min_calibration_rows=256,
                rationale=(
                    "Prespecified technical support for a controlled proof of con"
                    "cept; no population power claim"
                ),
            ),
        )
        models[version] = ef.calibrate_detectors(
            fit,
            ef.NormalCalibrationProfiles(
                purpose="normal_calibration",
                selection_manifest_sha256=digest([selection["calibration"], version]),
                profiles=tuple(vectors[version]["calibration"]),
            ),
            alpha="0.05",
        )
        # Own declarative JSON retained locally for the isolated timing pass.
        # These private task artifacts are never added to the public repository.
        ef.write_detector_bundle(models[version], output / ("private-model-" + version + ".json"))
    return models


def average_path(samples: int) -> float:
    return (
        0.0
        if samples <= 1
        else 1.0
        if samples == 2
        else 2 * (math.log(samples - 1) + 0.5772156649015329) - 2 * (samples - 1) / samples
    )


def actual_trace(bundle: ef.DetectorBundle, vector: ef.ProfileVector, score: Any) -> dict[str, Any]:
    matrix = ef.transform_profiles(bundle.fit.preprocessor, (vector,))
    values = tuple(struct.unpack("f", struct.pack("f", value))[0] for value in matrix.values[0])
    lengths = []
    examples = []
    for tree_index, tree in enumerate(bundle.fit.m.trees):
        index = depth = 0
        path = []
        node = tree.nodes[index]
        while node.left is not None:
            assert (
                node.feature is not None and node.threshold is not None and node.right is not None
            )
            left = values[node.feature] <= node.threshold
            path.append(
                {
                    "node": index,
                    "feature": matrix.columns[node.feature],
                    "value_float32": values[node.feature],
                    "threshold": node.threshold,
                    "branch": "left" if left else "right",
                }
            )
            index = node.left if left else node.right
            depth += 1
            node = tree.nodes[index]
        lengths.append(depth + average_path(node.samples))
        if tree_index < 3:
            examples.append(
                {
                    "tree": tree_index,
                    "path": path,
                    "leaf_node": index,
                    "leaf_training_samples": node.samples,
                    "adjusted_length": lengths[-1],
                }
            )
    assert bundle.fit.m.effective_samples is not None and lengths
    reconstructed = 2 ** (
        -(sum(lengths) / len(lengths)) / average_path(bundle.fit.m.effective_samples)
    )
    if not isinstance(score, float) or not math.isclose(reconstructed, score, rel_tol=1e-14):
        raise RuntimeError("Actual forest path calculation disagrees with detector score")
    return {
        "trees_used": len(lengths),
        "effective_samples": bundle.fit.m.effective_samples,
        "mean_adjusted_path_length": sum(lengths) / len(lengths),
        "score_from_paths": reconstructed,
        "score_from_api": score,
        "threshold": bundle.m.threshold,
        "tree_examples": examples,
        "meaning": (
            "Traversal evidence, not a causal explanation or a probability of semantic error."
        ),
    }


def clustered_difference(
    rows: list[dict[str, Any]], left: str, right: str, divergent: bool
) -> dict[str, Any]:
    groups: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        if (
            row["divergent"] == divergent
            and row[left] in ("alert", "no_alert")
            and row[right] in ("alert", "no_alert")
        ):
            groups[row["group"]].append(int(row[left] == "alert") - int(row[right] == "alert"))
    grouped = list(groups.values())
    if not grouped:
        return {"source_groups": 0, "delta": None, "cluster_bootstrap95": None}
    rng = random.Random(20261119)
    estimates = []
    for _ in range(2000):
        sample = rng.choices(grouped, k=len(grouped))
        estimates.append(sum(map(sum, sample)) / sum(map(len, sample)))
    estimates.sort()
    return {
        "source_groups": len(grouped),
        "delta": sum(map(sum, grouped)) / sum(map(len, grouped)),
        "cluster_bootstrap95": [estimates[49], estimates[1949]],
        "scope": (
            "Whole source chunk and all paired severity variants; conditi"
            "onal on this fitted model and snapshot."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    protocol = json.loads((args.primary / "protocol.json").read_bytes())
    if protocol["script_sha256"] != hashlib.sha256(Path(primary.__file__).read_bytes()).hexdigest():
        raise ValueError("Primary benchmark source changed")
    (args.output / "protocol.json").write_text(
        json.dumps(
            {
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "primary_protocol_sha256": hashlib.sha256(
                    (args.primary / "protocol.json").read_bytes()
                ).hexdigest(),
                "preregistration_sha256": hashlib.sha256(
                    args.preregistration.read_bytes()
                ).hexdigest(),
                "preregistration": json.loads(args.preregistration.read_bytes()),
                "models": (
                    "Exact reconstruction of seed-7 primary bundles, fingerprint "
                    "checked before scoring"
                ),
                "published_model": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    procedures, _ = primary.cohort(args.csv_dir)
    cases, selection = primary.select_cases(procedures, protocol["counts"])
    sources = extra_sources(procedures, cases, 64)
    models = reconstruct_models(cases, selection, args.output)
    main_report = json.loads((args.primary / "report.json").read_bytes())
    for version, model in models.items():
        reference = next(
            row
            for row in main_report["summaries"]
            if row["version"] == version and row["seed"] == 7
        )
        if ef.detector_fingerprint(model) != reference["bundle_sha256"]:
            raise RuntimeError("Reconstructed model differs; no new test scoring allowed")
    records = []
    native = []
    vectors: dict[str, list[ef.ProfileVector]] = {version: [] for version in primary.VERSIONS}
    for group, source in enumerate(sources):
        for level in LEVELS:
            reference_row = None
            reference_vectors = None
            for engine in primary.ENGINES:
                with tempfile.TemporaryDirectory(prefix="equiframe-severity-test-") as scratch:
                    row, measured = one_variant(source, group, level, engine, Path(scratch))
                actual_rows = row.pop("_actual_rows")
                native.append(row)
                if reference_row is None:
                    reference_row, reference_vectors = row, measured
                    reference_actual = actual_rows
                else:
                    if actual_rows != reference_actual or measured != reference_vectors:
                        raise RuntimeError("Exact native values or profile objects disagree")
                    for key in (
                        "actual_sha256",
                        "r_global",
                        "r_group",
                        "profile_sha256_1.1",
                        "profile_sha256_1.2",
                    ):
                        if row[key] != reference_row[key]:
                            raise RuntimeError("Native severity output/profile disagreement")
            assert reference_row is not None and reference_vectors is not None
            records.append(reference_row)
            for version in primary.VERSIONS:
                vectors[version].append(reference_vectors[version])
        if group % 8 == 0:
            print(
                json.dumps(
                    {
                        "severity_source_groups_completed": group + 1,
                        "native_test_executions": len(native),
                    }
                ),
                flush=True,
            )
    summaries = []
    scored = []
    traces = []
    for version, model in models.items():
        detection = ef.detect(model, tuple(vectors[version]))
        rows = [row.copy() for row in records]
        for index, (row, m, b) in enumerate(zip(rows, detection.m, detection.b, strict=True)):
            row.update(
                version=version,
                m=m.result.decision,
                b=b.result.decision,
                m_score=m.score,
                m_threshold=m.threshold,
                b_score=b.score,
                b_threshold=b.threshold,
            )
            row["h_global"] = (
                "alert"
                if "alert" in (row["r_global"], row["m"])
                else "no_alert"
                if row["m"] == "no_alert"
                else "not_evaluable"
            )
            if row["group"] == 0:
                traces.append(
                    {
                        "version": version,
                        "level": row["level"],
                        "group": 0,
                        "source_sha256": row["source_sha256"],
                        **actual_trace(model, vectors[version][index], m.score),
                    }
                )
        methods = ("r_global", "r_group", "m", "b", "h_global")
        summaries.append(
            {
                "version": version,
                "bundle_sha256": ef.detector_fingerprint(model),
                "all": {method: metrics(rows, method) for method in methods},
                "per_level": {
                    level: {
                        method: metrics([row for row in rows if row["level"] == level], method)
                        for method in methods
                    }
                    for level in LEVELS
                },
                "hybrid_minus_global_recall": clustered_difference(
                    rows, "h_global", "r_global", True
                ),
                "hybrid_minus_global_fpr": clustered_difference(
                    rows, "h_global", "r_global", False
                ),
                "hybrid_minus_group_rule_recall": clustered_difference(
                    rows, "h_global", "r_group", True
                ),
            }
        )
        scored.extend(rows)
    report = {
        "protocol_sha256": hashlib.sha256((args.output / "protocol.json").read_bytes()).hexdigest(),
        "independent_source_groups": 64,
        "paired_variants_per_group": 5,
        "test_cases": len(records),
        "native_test_executions": len(native),
        "reconstructed_training_calibration_executions": 512,
        "model_identity_matches_primary": True,
        "native_parity": True,
        "summaries": summaries,
        "interpretation": (
            "Actual public input, controlled defects; exact grouped rules"
            " use the declared filter and must remain visible as a strong"
            "er baseline. Severity variants share source groups."
        ),
    }
    for filename, value in (
        ("report.json", report),
        ("records.json", scored),
        ("native-records.json", native),
        ("tree-traces.json", traces),
    ):
        (args.output / filename).write_text(
            json.dumps(value, indent=2, allow_nan=False), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "finished": True,
                "independent_source_groups": 64,
                "test_cases": len(records),
                "native_test_executions": len(native),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
