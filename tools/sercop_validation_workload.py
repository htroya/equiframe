"""Dimension and compare one frozen public SERCOP export on native engines.

This consumer workload is engineering evidence, not a domain DW, scientific O,
confirmed normality, an effective learning corpus, or an accepted thesis study.
Missing and null source fields remain distinguishable through explicit flags.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import time
import zipfile
from collections import Counter
from decimal import Decimal, localcontext
from itertools import combinations
from pathlib import Path

ARCHIVE = "9ee4e5f94f44e42c89ade804d00ed69cd24604d246ad6450a4a43b2bd42e3632"
CORE_WHEEL = "c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23"
AWARD_COLUMNS = (
    "ocid",
    "award_id",
    "currency",
    "amount",
    "value_state",
    "currency_state",
    "amount_state",
)
FAMILIES = ("nulls_types", "joins", "aggregations")
ENGINES = ("pandas", "polars", "duckdb")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
        stream.write("\n")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            value.update(block)
    return value.hexdigest()


def packages(stream, chunk_size=65536, max_item_chars=16_777_216):
    """Streaming top-level objects; both integer and fractional tokens are exact."""
    require(chunk_size > 0 and max_item_chars > 0, "Positive JSON budgets required")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Nonfinite JSON token")

    decoder = json.JSONDecoder(
        object_pairs_hook=pairs,
        parse_int=Decimal,
        parse_float=Decimal,
        parse_constant=reject,
    )
    buffer, eof = "", False

    def fill():
        nonlocal buffer, eof
        block = stream.read(chunk_size)
        eof = not block
        buffer += block

    def peek():
        nonlocal buffer
        while True:
            buffer = buffer.lstrip()
            if buffer or eof:
                return buffer[:1]
            fill()

    require(peek() == "[", "Expected a top-level array")
    buffer = buffer[1:]
    if peek() != "]":
        while True:
            while True:
                peek()
                try:
                    value, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError as error:
                    if eof or len(buffer) >= max_item_chars:
                        raise ValueError(
                            "Invalid, truncated or oversized JSON package"
                        ) from error
                    fill()
                    continue
                require(
                    end <= max_item_chars and isinstance(value, dict),
                    "Invalid package shape/size",
                )
                buffer = buffer[end:]
                yield value
                break
            separator = peek()
            if separator == "]":
                break
            require(separator == ",", "Expected a package separator")
            buffer = buffer[1:]
            require(peek() != "]", "JSON trailing comma")
    require(peek() == "]", "Missing array closing delimiter")
    buffer = buffer[1:]
    require(not peek(), "Trailing JSON data")


def presence(document, key):
    return (
        "missing"
        if key not in document
        else "null"
        if document[key] is None
        else "present"
    )


def award_value(award):
    state = presence(award, "value")
    value = award.get("value")
    if state in ("missing", "null"):
        return {
            "currency": None,
            "amount": None,
            "value_state": state,
            "currency_state": "not_applicable",
            "amount_state": "not_applicable",
        }
    require(isinstance(value, dict), "award.value must be an object, missing or null")
    currency, amount = value.get("currency"), value.get("amount")
    require(currency is None or isinstance(currency, str), "Invalid currency type")
    if amount is not None:
        require(type(amount) in (int, Decimal), "Amount must be an exact JSON number")
        amount = Decimal(amount)
        require(
            amount.is_finite() and not (amount.is_zero() and amount.is_signed()),
            "Unsupported nonfinite or negative-zero money",
        )
    return {
        "currency": currency,
        "amount": amount,
        "value_state": state,
        "currency_state": presence(value, "currency"),
        "amount_state": presence(value, "amount"),
    }


def scaled_digits(amount, scale):
    require(type(scale) is int and 0 <= scale <= 38, "Unsupported Decimal128 scale")
    require(
        amount.is_finite() and not (amount.is_zero() and amount.is_signed()),
        "Unsupported money",
    )
    parts = amount.as_tuple()
    require(parts.exponent + scale >= 0, "Scaling would discard decimal places")
    return 1 if amount.is_zero() else len(parts.digits) + parts.exponent + scale


def protocol():
    return {
        "schema": "equiframe.sercop-engineering-workload.v1",
        "candidate": "0.12.0a13",
        "source": "Frozen official SERCOP year2025 month0 methodall export; selector is not an award/release cohort",
        "archive_sha256": ARCHIVE,
        "json_member": "releases_2025.json",
        "expected_packages": 190619,
        "expected_award_occurrences": 183891,
        "sizes": [100, 1000, 10000, "full"],
        "size_definition": "Deterministic prefixes of the same observed unique award grain; shared observations, not independent cohorts/groups",
        "grain": "Exactly one release per package, unique ocid and (ocid,award.id); ambiguous or unsupported inputs fail without repair",
        "award_columns": list(AWARD_COLUMNS),
        "absence": "Explicit missing/null/present flags; malformed value objects are not converted to null",
        "money": "Exact JSON int/float tokens decoded as Decimal, including signed zero; Decimal128(38,observed scale) only if exact coefficient fits38 digits; negative zero rejected",
        "dates": "Release publication text and presence flag; no award/cohort date inferred",
        "families": list(FAMILIES),
        "engines": list(ENGINES),
        "expected": "Python raw projection, exact left join lookup and currency counts built before native execution; engine outputs never generate expected values",
        "native": "Independent pandas,Polars,DuckDB projection/left join/currency count implementations; no engine output converted to simulate another engine",
        "comparisons_each_size": "3 families x (3 independent expected comparisons +3 engine pairs) =18; source data are shared",
        "corrupt_controls_full": {
            "count": 9,
            "site": "Deliberately altered native transformation output, not corruption of the raw export",
            "nulls_types": "Add exactly1 to amount for first source award with a present amount",
            "joins": "Replace release_date for that exact award key with literal0001-01-01",
            "aggregations": "Add exactly1 to award_count for that award's currency",
            "acceptance": "different AND complete with nonzero verified differences; these are expected differences, not input rejection",
        },
        "comparison_options": {
            "max_rows": 500000,
            "max_work": 50000000,
            "max_disk_bytes": 256 * 1024**2,
            "max_evidence_bytes": 128 * 1024**2,
            "timeout_seconds": 180.0,
            "partitions": 16,
        },
        "host_budgets": {
            "one_process_at_a_time": True,
            "threads_each_engine": 1,
            "wall_seconds": 2400,
            "rss_bytes": 2 * 1024**3,
            "output_bytes": 3 * 1024**3,
            "minimum_free_ram_bytes": 3 * 1024**3,
            "minimum_free_disk_bytes": 5 * 1024**3,
            "kind": "Owned-run supervision and cooperative SDK checks; no production OS/container quota claim",
        },
        "model_fitting": False,
        "scientific_acceptance": False,
        "human_labels": 0,
        "dw_or_gateway_implemented": False,
        "word_modified": False,
    }


def extract(archive_path):
    rows, releases, ocids, awards = [], [], set(), set()
    years, methods = Counter(), Counter()
    require(digest(archive_path) == ARCHIVE, "Frozen corpus identity differs")
    with zipfile.ZipFile(archive_path) as archive:
        require(
            archive.namelist() == ["releases_2025.json"], "Unexpected archive members"
        )
        with (
            archive.open("releases_2025.json") as binary,
            io.TextIOWrapper(binary, encoding="utf-8") as stream,
        ):
            for package in packages(stream):
                items = package.get("releases")
                require(
                    isinstance(items, list) and len(items) == 1,
                    "Ambiguous release history",
                )
                release = items[0]
                require(isinstance(release, dict), "Invalid release shape")
                ocid, date = release.get("ocid"), release.get("date")
                require(
                    isinstance(ocid, str) and ocid and ocid not in ocids,
                    "Ambiguous release identity",
                )
                require(
                    date is None or isinstance(date, str), "Invalid release date type"
                )
                ocids.add(ocid)
                releases.append(
                    {
                        "ocid": ocid,
                        "release_date": date,
                        "release_date_state": presence(release, "date"),
                    }
                )
                years[date[:4] if date else "MISSING"] += 1
                tender = release.get("tender")
                require(
                    tender is None or isinstance(tender, dict), "Invalid tender shape"
                )
                method = (tender or {}).get("procurementMethodDetails")
                require(
                    method is None or isinstance(method, str), "Invalid method type"
                )
                methods[method] += 1
                released_awards = release.get("awards")
                require(
                    released_awards is None or isinstance(released_awards, list),
                    "Invalid awards shape",
                )
                for award in released_awards or []:
                    require(isinstance(award, dict), "Invalid award shape")
                    award_id = award.get("id")
                    require(
                        isinstance(award_id, str)
                        and award_id
                        and (ocid, award_id) not in awards,
                        "Ambiguous award identity",
                    )
                    awards.add((ocid, award_id))
                    rows.append(
                        {"ocid": ocid, "award_id": award_id, **award_value(award)}
                    )
    require(
        len(rows) == 183891 and len(releases) == 190619, "Frozen source counts differ"
    )
    amounts = [row["amount"] for row in rows if row["amount"] is not None]
    scale = max((max(0, -value.as_tuple().exponent) for value in amounts), default=0)
    require(
        all(scaled_digits(value, scale) <= 38 for value in amounts),
        "Money does not fit exact Decimal128",
    )
    sorted_amounts = sorted(amounts)
    currencies = Counter(row["currency"] for row in rows)
    amount_presence = Counter(row["amount_state"] for row in rows)
    value_presence = Counter(row["value_state"] for row in rows)
    stats = {
        "packages": len(releases),
        "release_rows": len(releases),
        "award_rows": len(rows),
        "json_crc_verified_by_complete_read": True,
        "release_publication_years": dict(years),
        "observed_procurement_method_categories": len(methods),
        "currency_counts": [
            {"currency": key, "rows": value} for key, value in currencies.items()
        ],
        "amount_state_counts": dict(amount_presence),
        "value_state_counts": dict(value_presence),
        "money_precision": 38,
        "money_scale": scale,
        "present_amounts": len(amounts),
        "zero_amounts": sum(value.is_zero() for value in amounts),
        "negative_amounts": sum(value < 0 for value in amounts),
        "amount_min": str(sorted_amounts[0]),
        "amount_max": str(sorted_amounts[-1]),
        "amount_p50_nearest_rank": str(
            sorted_amounts[math.ceil(0.5 * len(amounts)) - 1]
        ),
        "amount_p95_nearest_rank": str(
            sorted_amounts[math.ceil(0.95 * len(amounts)) - 1]
        ),
        "scope": "Descriptive observations of this export; no financial anomaly labels, temporal cohort or effective learning profiles inferred",
    }
    return rows, releases, scale, stats


def native_outputs(awards, releases, target, corrupt=False):
    import duckdb
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    timings = {"load_seconds": {}, "transform_seconds": {}}

    def timed(bucket, key, operation):
        begin = time.perf_counter()
        result = operation()
        bucket[key] = time.perf_counter() - begin
        return result

    panda, panda_release = timed(
        timings["load_seconds"],
        "pandas",
        lambda: (
            awards.to_pandas(types_mapper=pd.ArrowDtype),
            releases.to_pandas(types_mapper=pd.ArrowDtype),
        ),
    )
    polar, polar_release = timed(
        timings["load_seconds"],
        "polars",
        lambda: (pl.from_arrow(awards), pl.from_arrow(releases)),
    )

    def load_duckdb():
        connection = duckdb.connect(
            config={"threads": 1, "enable_external_access": False}
        )
        connection.register("awards", awards)
        connection.register("releases", releases)
        return connection

    connection = timed(timings["load_seconds"], "duckdb", load_duckdb)
    transform = timings["transform_seconds"]
    columns = ",".join(AWARD_COLUMNS)
    try:
        output = {
            "nulls_types": {
                "pandas": timed(
                    transform,
                    "nulls_types:pandas",
                    lambda: panda[list(AWARD_COLUMNS)].copy(),
                ),
                "polars": timed(
                    transform,
                    "nulls_types:polars",
                    lambda: polar.select(*AWARD_COLUMNS),
                ),
                "duckdb": timed(
                    transform,
                    "nulls_types:duckdb",
                    lambda: connection.execute(
                        "SELECT " + columns + " FROM awards"
                    ).to_arrow_table(),
                ),
            },
            "joins": {
                "pandas": timed(
                    transform,
                    "joins:pandas",
                    lambda: panda.merge(
                        panda_release, on="ocid", how="left", validate="many_to_one"
                    ),
                ),
                "polars": timed(
                    transform,
                    "joins:polars",
                    lambda: polar.join(
                        polar_release, on="ocid", how="left", validate="m:1"
                    ),
                ),
                "duckdb": timed(
                    transform,
                    "joins:duckdb",
                    lambda: connection.execute(
                        "SELECT a.*,r.release_date,r.release_date_state FROM awards a LEFT JOIN releases r ON a.ocid=r.ocid"
                    ).to_arrow_table(),
                ),
            },
            "aggregations": {
                "pandas": timed(
                    transform,
                    "aggregations:pandas",
                    lambda: (
                        panda.groupby("currency", dropna=False)
                        .size()
                        .rename("award_count")
                        .reset_index()
                        .astype({"award_count": pd.ArrowDtype(pa.int64())})
                    ),
                ),
                "polars": timed(
                    transform,
                    "aggregations:polars",
                    lambda: polar.group_by("currency").agg(
                        pl.len().cast(pl.Int64).alias("award_count")
                    ),
                ),
                "duckdb": timed(
                    transform,
                    "aggregations:duckdb",
                    lambda: connection.execute(
                        "SELECT currency,COUNT(*) AS award_count FROM awards GROUP BY currency"
                    ).to_arrow_table(),
                ),
            },
        }
        if corrupt:
            mutation_begin = time.perf_counter()
            ocid, award_id, currency = (
                target["ocid"],
                target["award_id"],
                target["currency"],
            )
            for family in FAMILIES[:2]:
                frame = output[family]["pandas"]
                mask = (frame.ocid == ocid) & (frame.award_id == award_id)
                if family == "nulls_types":
                    with localcontext() as context:
                        context.prec = 100
                        frame.loc[mask, "amount"] = target["amount"] + Decimal(1)
                else:
                    frame.loc[mask, "release_date"] = "0001-01-01"
            frame = output["aggregations"]["pandas"]
            mask = (
                frame.currency.isna()
                if currency is None
                else frame.currency == currency
            )
            frame.loc[mask, "award_count"] = frame.loc[mask, "award_count"] + 1
            match = (pl.col("ocid") == ocid) & (pl.col("award_id") == award_id)
            output["nulls_types"]["polars"] = output["nulls_types"][
                "polars"
            ].with_columns(
                pl.when(match)
                .then(pl.col("amount") + pl.lit(Decimal(1)))
                .otherwise(pl.col("amount"))
                .alias("amount")
            )
            output["joins"]["polars"] = output["joins"]["polars"].with_columns(
                pl.when(match)
                .then(pl.lit("0001-01-01"))
                .otherwise(pl.col("release_date"))
                .alias("release_date")
            )
            match_currency = (
                pl.col("currency").is_null()
                if currency is None
                else pl.col("currency") == currency
            )
            output["aggregations"]["polars"] = output["aggregations"][
                "polars"
            ].with_columns(
                pl.when(match_currency)
                .then(pl.col("award_count") + 1)
                .otherwise(pl.col("award_count"))
                .alias("award_count")
            )
            scale = awards.schema.field("amount").type.scale
            projection = (
                "ocid,award_id,currency,CASE WHEN ocid=? AND award_id=? THEN amount+CAST(1 AS DECIMAL(38,"
                + str(scale)
                + ")) ELSE amount END AS amount,value_state,currency_state,amount_state"
            )
            output["nulls_types"]["duckdb"] = connection.execute(
                "SELECT " + projection + " FROM awards", [ocid, award_id]
            ).to_arrow_table()
            output["joins"]["duckdb"] = connection.execute(
                "SELECT a.*,CASE WHEN a.ocid=? AND a.award_id=? THEN '0001-01-01' ELSE r.release_date END AS release_date,r.release_date_state FROM awards a LEFT JOIN releases r ON a.ocid=r.ocid",
                [ocid, award_id],
            ).to_arrow_table()
            output["aggregations"]["duckdb"] = connection.execute(
                "SELECT currency,COUNT(*)+CASE WHEN currency IS NOT DISTINCT FROM ? THEN 1 ELSE 0 END AS award_count FROM awards GROUP BY currency",
                [currency],
            ).to_arrow_table()
            timings["deliberate_mutations_seconds"] = (
                time.perf_counter() - mutation_begin
            )
        return output, timings
    finally:
        connection.close()


def readback(ef, directory, outcome):
    restored = ef.read_comparison(directory / outcome.comparison_id / "comparison.json")
    require(restored == outcome, "Comparison readback differs")
    difference_count = sum(1 for _ in ef.iter_differences(restored.differences))
    require(
        difference_count == outcome.counts.difference_records,
        "Persisted difference count differs",
    )
    return difference_count


def run(args, frozen):
    import importlib.util

    import equiframe as ef
    import polars as pl
    import pyarrow as pa

    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    require(pl.thread_pool_size() == 1, "Set POLARS_MAX_THREADS=1 before launch")
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "operations", root / "tools/option_operations.py"
    )
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    identity = op.identity(args.wheel, CORE_WHEEL, root)
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    rows, releases, scale, dimensions = extract(args.archive)
    extraction_seconds = time.perf_counter() - started
    dimensions_begin = time.perf_counter()
    write(args.output / "dimensions.json", dimensions)
    dimensions_persist_seconds = time.perf_counter() - dimensions_begin
    arrow_begin = time.perf_counter()
    award_schema = pa.schema(
        [
            (key, pa.decimal128(38, scale) if key == "amount" else pa.string())
            for key in AWARD_COLUMNS
        ]
    )
    release_schema = pa.schema(
        [
            ("ocid", pa.string()),
            ("release_date", pa.string()),
            ("release_date_state", pa.string()),
        ]
    )
    release_map = {row["ocid"]: row for row in releases}
    release_table = pa.Table.from_pylist(releases, schema=release_schema)
    release_arrow_seconds = time.perf_counter() - arrow_begin
    policy = ef.ComparisonPolicy(
        index="ignore",
        justification="Only generated pandas RangeIndex ignored; raw SERCOP identity, exact money, null flags and multiplicity retained.",
    )
    options = ef.ComparisonOptions(**frozen["comparison_options"])
    checks, stages = [], []
    for size in frozen["sizes"]:
        step_start = time.perf_counter()
        selected = rows if size == "full" else rows[:size]
        awards = pa.Table.from_pylist(selected, schema=award_schema)
        joined = [
            {
                **row,
                "release_date": release_map[row["ocid"]]["release_date"],
                "release_date_state": release_map[row["ocid"]]["release_date_state"],
            }
            for row in selected
        ]
        join_schema = pa.schema(
            [
                *award_schema,
                pa.field("release_date", pa.string()),
                pa.field("release_date_state", pa.string()),
            ]
        )
        counts = Counter(row["currency"] for row in selected)
        expected = {
            "nulls_types": awards,
            "joins": pa.Table.from_pylist(joined, schema=join_schema),
            "aggregations": pa.Table.from_pylist(
                [
                    {"currency": currency, "award_count": count}
                    for currency, count in counts.items()
                ],
                schema=pa.schema(
                    [("currency", pa.string()), ("award_count", pa.int64())]
                ),
            ),
        }
        target = next(row for row in selected if row["amount"] is not None)
        expected_build_seconds = time.perf_counter() - step_start
        persist_begin = time.perf_counter()
        for family, table in expected.items():
            destination = args.output / f"{size}-{family}-expected.arrow"
            with (
                pa.OSFile(str(destination), "wb") as sink,
                pa.ipc.new_file(sink, table.schema) as writer,
            ):
                writer.write_table(table)
        expected_persist_seconds = time.perf_counter() - persist_begin
        actual, native_timings = native_outputs(awards, release_table, target)

        row_count = len(selected)

        def check(family, label, left, right, state, *, size=size, row_count=row_count):
            begin = time.perf_counter()
            directory = args.output / f"{size}-{family}-{label}"
            outcome = ef.diff(
                left, right, policy=policy, options=options, work_dir=directory
            )
            compare_seconds = time.perf_counter() - begin
            read_begin = time.perf_counter()
            difference_count = readback(ef, directory, outcome)
            observed = {
                "size": size,
                "award_rows": row_count,
                "family": family,
                "check": label,
                "expected_state": state,
                "state": outcome.state,
                "complete": outcome.complete,
                "difference_records": outcome.counts.difference_records,
                "verified_difference_records": difference_count,
                "comparison_id": outcome.comparison_id,
                "comparison_seconds": compare_seconds,
                "readback_seconds": time.perf_counter() - read_begin,
                "status": "PASS"
                if outcome.state == state
                and outcome.complete
                and (state != "different" or outcome.counts.difference_records > 0)
                else "FAIL",
            }
            checks.append(observed)
            write(args.output / f"check-{len(checks):03d}.json", observed)
            print(
                json.dumps(
                    {
                        key: observed[key]
                        for key in [
                            "size",
                            "family",
                            "check",
                            "status",
                            "state",
                            "complete",
                        ]
                    }
                ),
                flush=True,
            )
            require(
                observed["status"] == "PASS",
                "Unexpected result retained; no coverage credit",
            )

        for family in FAMILIES:
            for engine in ENGINES:
                check(
                    family,
                    engine + "-literal",
                    actual[family][engine],
                    expected[family],
                    "equivalent",
                )
            for left, right in combinations(ENGINES, 2):
                check(
                    family,
                    left + "-" + right,
                    actual[family][left],
                    actual[family][right],
                    "equivalent",
                )
        corrupt_timings = None
        if size == "full":
            corrupt, corrupt_timings = native_outputs(
                awards, release_table, target, corrupt=True
            )
            for family in FAMILIES:
                for engine in ENGINES:
                    check(
                        family,
                        engine + "-deliberate-difference",
                        corrupt[family][engine],
                        expected[family],
                        "different",
                    )
        stages.append(
            {
                "size": size,
                "award_rows": len(selected),
                "expected_build_seconds": expected_build_seconds,
                "expected_persist_seconds": expected_persist_seconds,
                "native_timings": native_timings,
                "control_native_timings": corrupt_timings,
            }
        )
    require(
        len(checks) == 81 and all(row["status"] == "PASS" for row in checks),
        "Incomplete engineering workload",
    )
    result = {
        "schema": "equiframe.sercop-engineering-result.v1",
        "candidate": ef.__version__,
        "package": identity,
        "engine_thread_settings": {
            "arrow_cpu_count": pa.cpu_count(),
            "arrow_io_thread_count": pa.io_thread_count(),
            "polars_pool_size": pl.thread_pool_size(),
            "duckdb_configured_threads": 1,
        },
        "archive_sha256": ARCHIVE,
        "protocol_sha256": digest(args.protocol),
        "tool_sha256": digest(Path(__file__)),
        "dimensions_sha256": digest(args.output / "dimensions.json"),
        "extraction_seconds": extraction_seconds,
        "dimensions_persist_seconds": dimensions_persist_seconds,
        "release_arrow_and_lookup_seconds": release_arrow_seconds,
        "comparison_timing_scope": "Includes SDK capture, comparison and persistence; readback timed separately. No internal persistence-only duration inferred.",
        "stages": stages,
        "checks": checks,
        "positive_checks": 72,
        "deliberate_difference_checks": 9,
        "all_expected_results": True,
        "scientific_acceptance": False,
        "human_labels": 0,
        "effective_learning_profiles_accredited": 0,
        "word_modified": False,
        "new_option_obligations_credited": 0,
        "scope": "Overlapping prefix/full real export engineering checks; no new independent cohorts, scientific O, domain DW, fitting or original rubric closure inferred",
    }
    write(args.output / "result.json", result)
    print(
        json.dumps(
            {
                "checks_passed": len(checks),
                "award_rows": len(rows),
                "release_rows": len(releases),
                "scientific_acceptance": False,
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "plan":
        write(args.protocol, protocol())
        print(json.dumps({"protocol_sha256": digest(args.protocol), "executed": False}))
        return 0
    require(
        args.protocol_sha256 and digest(args.protocol) == args.protocol_sha256,
        "Frozen protocol differs",
    )
    frozen = json.loads(args.protocol.read_text("utf-8"))
    require(frozen == protocol(), "Protocol differs from reviewed definitions")
    require(args.archive and args.wheel and args.output, "Run inputs required")
    run(args, frozen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
