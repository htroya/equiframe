"""Prepare a private real-data pilot and blind review files; labels stay pending.

Input is the exact annual JSON export delivered to the tutor. Proposed scenarios
and R/features are frozen before generating native controls or mutations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import shutil
import zipfile
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

SOURCE_SHA256 = "80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3"
FAMILIES = ("nulls_types", "joins", "aggregations")
ENGINES = ("pandas", "polars", "duckdb")
PAIRS = (("pandas", "polars"), ("pandas", "duckdb"), ("polars", "duckdb"))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_helper(filename):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    require(spec is not None and spec.loader is not None, "Reader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helper():
    return load_helper("sercop_validation_workload.py")


def selected_units(archive_path, count):
    """Parse full raw input, preserve presence and take predeclared bounded units."""
    reader = helper()
    require(sha(archive_path) == SOURCE_SHA256, "Source export identity differs")
    units, ocids, years = [], set(), Counter()
    award_count, excluded = 0, Counter()
    with zipfile.ZipFile(archive_path) as archive:
        require(
            archive.namelist() == ["releases_2025.json"], "Unexpected export members"
        )
        require(
            archive.getinfo("releases_2025.json").file_size <= 4 * 1024**3,
            "Source byte budget exceeded",
        )
        with (
            archive.open("releases_2025.json") as binary,
            io.TextIOWrapper(binary, encoding="utf-8") as stream,
        ):
            for package in reader.packages(stream):
                items = package.get("releases")
                require(
                    isinstance(items, list) and len(items) == 1,
                    "Ambiguous release history",
                )
                release = items[0]
                require(isinstance(release, dict), "Invalid release structure")
                ocid, date = release.get("ocid"), release.get("date")
                require(
                    isinstance(ocid, str) and ocid and ocid not in ocids,
                    "Ambiguous release identity",
                )
                require(date is None or isinstance(date, str), "Invalid date structure")
                ocids.add(ocid)
                years[date[:4] if date else "MISSING"] += 1
                awards = release.get("awards")
                require(
                    awards is None or isinstance(awards, list),
                    "Invalid award collection",
                )
                rows, ids = [], set()
                for award in awards or ():
                    require(isinstance(award, dict), "Invalid award structure")
                    identity = award.get("id")
                    require(
                        isinstance(identity, str) and identity and identity not in ids,
                        "Ambiguous award identity",
                    )
                    ids.add(identity)
                    rows.append(
                        {
                            "ocid": ocid,
                            "award_id": identity,
                            **reader.award_value(award),
                        }
                    )
                award_count += len(rows)
                if not rows:
                    excluded["no_awards"] += 1
                elif not any(r["amount"] is not None for r in rows):
                    excluded["no_amount_for_declared_mutation"] += 1
                elif len(rows) > 256:
                    excluded["unit_row_budget"] += 1
                elif len(units) < count:
                    units.append(
                        (
                            rows,
                            {
                                "ocid": ocid,
                                "release_date": date,
                                "release_date_state": reader.presence(release, "date"),
                            },
                        )
                    )
    require(len(units) == count, "Insufficient eligible source units")
    require(sha(archive_path) == SOURCE_SHA256, "Source changed during extraction")
    return units, {
        "release_records_observed": len(ocids),
        "award_records_observed": award_count,
        "publication_year_counts": dict(years),
        "selected_ocid_units": len(units),
        "excluded_unit_counts": dict(excluded),
        "selection": "First eligible units in pinned source order; fixed before outcomes",
        "cohort_approved": False,
        "normality_confirmed": False,
    }


def registry(family, variant, target, scale):
    import equiframe as ef
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    mutate = variant == "mutation"
    name = "sercop." + family + "." + variant
    columns = helper().AWARD_COLUMNS
    sql_projection = ",".join(columns)
    base_sql = {
        "nulls_types": "SELECT " + sql_projection + " FROM awards",
        "joins": "SELECT a.*,r.release_date,r.release_date_state FROM awards a LEFT JOIN releases r ON a.ocid=r.ocid",
        "aggregations": "SELECT currency,COUNT(*) AS award_count FROM awards GROUP BY currency",
    }[family]
    if mutate:
        if family == "nulls_types":
            base_sql = (
                "SELECT ocid,award_id,currency,CASE WHEN award_id=$target THEN amount+CAST(1 AS DECIMAL(38,"
                + str(scale)
                + ")) ELSE amount END AS amount,value_state,currency_state,amount_state FROM awards"
            )
        elif family == "joins":
            base_sql = "SELECT a.*,CASE WHEN a.award_id=$target THEN '0001-01-01' ELSE r.release_date END AS release_date,r.release_date_state FROM awards a LEFT JOIN releases r ON a.ocid=r.ocid"
        else:
            base_sql = "SELECT currency,COUNT(*)+1 AS award_count FROM awards GROUP BY currency"

    def pandas(inputs, context):
        left = inputs["awards"]
        if family == "nulls_types":
            output = left[list(columns)].copy()
        elif family == "joins":
            output = left.merge(
                inputs["releases"], on="ocid", how="left", validate="many_to_one"
            )
        else:
            output = (
                left.groupby("currency", dropna=False)
                .size()
                .rename("award_count")
                .reset_index()
                .astype({"award_count": pd.ArrowDtype(pa.int64())})
            )
        if mutate:
            if family == "nulls_types":
                mask = output.award_id == target
                with localcontext() as ctx:
                    ctx.prec = 100
                    changed = output.loc[mask, "amount"].map(
                        lambda value: value + Decimal(1)
                    )
                    output.loc[mask, "amount"] = changed.astype(
                        pd.ArrowDtype(pa.decimal128(38, scale))
                    )
            elif family == "joins":
                output.loc[output.award_id == target, "release_date"] = "0001-01-01"
            else:
                output["award_count"] = output["award_count"] + 1
        return output

    def polars(inputs, context):
        left = inputs["awards"]
        if family == "nulls_types":
            output = left.select(*columns)
        elif family == "joins":
            output = left.join(
                inputs["releases"], on="ocid", how="left", validate="m:1"
            )
        else:
            output = left.group_by("currency").agg(
                pl.len().cast(pl.Int64).alias("award_count")
            )
        if mutate:
            if family == "nulls_types":
                output = output.with_columns(
                    pl.when(pl.col("award_id") == target)
                    .then(pl.col("amount") + pl.lit(Decimal(1)))
                    .otherwise(pl.col("amount"))
                    .cast(pl.Decimal(38, scale), strict=True)
                    .alias("amount")
                )
            elif family == "joins":
                output = output.with_columns(
                    pl.when(pl.col("award_id") == target)
                    .then(pl.lit("0001-01-01"))
                    .otherwise(pl.col("release_date"))
                    .alias("release_date")
                )
            else:
                output = output.with_columns(
                    (pl.col("award_count") + 1).alias("award_count")
                )
        return output

    result = ef.TransformationRegistry()
    for transformation in (
        ef.PandasTransformation(name, pandas, "sercop-proposed-v1"),
        ef.PolarsTransformation(name, polars, "sercop-proposed-v1"),
        ef.DuckDBTransformation(name, base_sql, "sercop-proposed-v1"),
    ):
        result.register(transformation)
    return result, name


def prepare(archive_path, directory, units_count):
    import equiframe as ef
    import equiframe_benchmark as eb
    import pyarrow as pa
    from equiframe_benchmark.models import digest
    from equiframe_benchmark.pilot import write_table

    packet_io = load_helper("thesis_packet_io.py")
    source_files = (
        Path(__file__),
        Path(__file__).with_name("sercop_validation_workload.py"),
        Path(__file__).with_name("thesis_packet_io.py"),
    )
    tool_identity = {p.name: sha(p) for p in source_files}
    require(not directory.exists(), "Preserve previous preparation")
    # Each unit produces hundreds of files; remain below the closed inventory
    # budget. A larger corpus needs an explicitly designed sharded packet.
    require(
        type(units_count) is int and 1 <= units_count <= 32,
        "Pilot supports 1..32 integer units per packet",
    )
    require(
        shutil.disk_usage(directory.parent).free >= 2 * 1024**3,
        "Insufficient private workspace reserve",
    )
    units, dimensions = selected_units(archive_path, units_count)
    directory.mkdir(parents=True)
    save(directory / "source-dimensions.json", dimensions)
    scenarios, planned, records = [], [], []
    for number, (rows, release) in enumerate(units):
        root = directory / "coordinator" / f"unit-{number:05d}"
        root.mkdir(parents=True)
        scale = max(
            max(0, -r["amount"].as_tuple().exponent)
            for r in rows
            if r["amount"] is not None
        )
        require(scale <= 38, "Source money exceeds decimal scale")
        schema = pa.schema(
            [
                ("ocid", pa.string()),
                ("award_id", pa.string()),
                ("currency", pa.string()),
                ("amount", pa.decimal128(38, scale)),
                ("value_state", pa.string()),
                ("currency_state", pa.string()),
                ("amount_state", pa.string()),
            ]
        )
        awards = pa.Table.from_pylist(rows, schema=schema)
        releases = pa.Table.from_pylist(
            [release],
            schema=pa.schema(
                [
                    ("ocid", pa.string()),
                    ("release_date", pa.string()),
                    ("release_date_state", pa.string()),
                ]
            ),
        )
        award_ref = write_table(awards, root / "awards.arrow")
        release_ref = write_table(releases, root / "releases.arrow")
        for family in FAMILIES:
            target = next(r["award_id"] for r in rows if r["amount"] is not None)
            # Expected rows come from stdlib/source objects, before native execution.
            expected_rows = (
                rows
                if family == "nulls_types"
                else [
                    dict(
                        r,
                        release_date=release["release_date"],
                        release_date_state=release["release_date_state"],
                    )
                    for r in rows
                ]
                if family == "joins"
                else [
                    {"currency": key, "award_count": count}
                    for key, count in Counter(r["currency"] for r in rows).items()
                ]
            )
            expected_schema = (
                schema
                if family == "nulls_types"
                else pa.schema(
                    [
                        *schema,
                        ("release_date", pa.string()),
                        ("release_date_state", pa.string()),
                    ]
                )
                if family == "joins"
                else pa.schema([("currency", pa.string()), ("award_count", pa.int64())])
            )
            expected = write_table(
                pa.Table.from_pylist(expected_rows, schema=expected_schema),
                root / (family + "-expected.arrow"),
            )
            output_schema = ef.infer_diff_contract(expected_schema).spec.contract.output
            award_schema = ef.infer_diff_contract(
                schema
            ).spec.contract.output.model_copy(update={"name": "awards"})
            release_schema = ef.infer_diff_contract(
                releases.schema
            ).spec.contract.output.model_copy(update={"name": "releases"})
            input_schemas = (
                (award_schema, release_schema) if family == "joins" else (award_schema,)
            )
            policy = ef.ComparisonPolicy(
                physical_types="lossless",
                index="ignore",
                justification="Proposed table comparison: OCID/award_id are explicit columns; native pandas index is transport metadata. Compatible Arrow string widths/decimal precision may differ losslessly; values, scale, presence flags and multiplicity stay under the contract.",
            )
            contract = ef.Contract(
                schema_version="1.0",
                contract_id=f"sercop.proposed.{number}.{family}",
                revision=1,
                family=family,
                inputs=input_schemas,
                output=output_schema,
                preconditions=(),
                rules=(
                    ef.RuleSpec(
                        rule_id="schema",
                        revision=1,
                        specification=ef.SchemaCheck(table=output_schema.name),
                        severity="error",
                        required=True,
                    ),
                ),
            )
            features = [
                ef.ProfileFeature(
                    name="rows", metric="log_filas", table=output_schema.name
                )
            ]
            if family != "aggregations":
                features.append(
                    ef.ProfileFeature(
                        name="missing_amount",
                        metric="tasa_nulos",
                        table=output_schema.name,
                        columns=("amount",),
                    )
                )
            else:
                features.append(
                    ef.ProfileFeature(
                        name="output_input",
                        metric="razon_salida_entrada",
                        table=output_schema.name,
                        denominator_table="awards",
                    )
                )
            profile = ef.ProfileSpec(family=family, features=tuple(features))
            bindings = (eb.InputBinding(name="awards", artifact=award_ref),) + (
                (eb.InputBinding(name="releases", artifact=release_ref),)
                if family == "joins"
                else ()
            )
            scenario = eb.Scenario(
                scenario_id=f"sercop.{number}.{family}",
                family=family,
                dependencies=(
                    "ocid:" + release["ocid"],
                    "template:sercop-proposed-" + family,
                ),
                authors=("automated-preparation",),
                inputs=bindings,
                transformation_revision="sercop-proposed-v1",
                comparison=ef.ComparisonSpec(contract=contract, policy=policy),
                rules_sha256=ef.rule_set_fingerprint(
                    contract, ef.default_rule_registry(), ef.RuleOptions()
                ),
                features_sha256=ef.profile_spec_fingerprint(profile),
                expected=expected,
                expected_method="Source preservation, stdlib mapping/Counter; no engine-derived reference",
                expected_authors=("automated-preparation",),
            )
            scenarios.append(scenario)
            planned.append(
                (
                    root,
                    scenario,
                    profile,
                    awards,
                    releases,
                    target,
                    scale,
                    expected_rows,
                )
            )
    catalog = eb.Catalog(
        catalog_id="sercop-2025-proposed-a14-v1",
        synthetic=False,
        scenarios=tuple(scenarios),
    )
    save(directory / "catalog.json", catalog.model_dump(mode="json"))
    splits = eb.make_splits(catalog, seed=20261013, weights=(3, 1, 1))
    eb.validate_splits(catalog, splits)
    save(directory / "splits.json", splits.model_dump(mode="json"))
    save(
        directory / "protocol-proposal.json",
        {
            "status": "PROPOSED",
            "source_sha256": SOURCE_SHA256,
            "catalog_sha256": digest(catalog),
            "splits_sha256": digest(splits),
            "families": list(FAMILIES),
            "engine_pairs": [list(p) for p in PAIRS],
            "source_selector_is_not_approved_cohort": True,
            "normality_confirmed": False,
            "human_decisions": None,
            "scientific_results": None,
        },
    )
    worksheets = []
    for (
        root,
        scenario,
        profile,
        awards,
        releases,
        target,
        scale,
        expected_rows,
    ) in planned:
        outputs = {}
        for variant in ("control", "mutation"):
            transforms, transformation_id = registry(
                scenario.family, variant, target, scale
            )
            for engine in ENGINES:
                work = root / (scenario.family + "-" + variant + "-" + engine)
                parameters = (
                    (ef.Parameter(name="target", value=ef.StringValue(value=target)),)
                    if engine == "duckdb"
                    and variant == "mutation"
                    and scenario.family != "aggregations"
                    else ()
                )
                plan = ef.ExecutionPlan(
                    contract=scenario.comparison.contract,
                    engine=engine,
                    transformation_id=transformation_id,
                    parameters=parameters,
                    options=ef.ExecutionOptions(
                        timeout_seconds=120.0,
                        max_input_rows=512,
                        max_output_rows=512,
                        max_transport_bytes=16 * 1024**2,
                        duckdb_threads=1,
                    ),
                )
                source = ef.LocalDataSource(
                    {
                        "awards": ef.ArrowInput(awards),
                        **(
                            {"releases": ef.ArrowInput(releases)}
                            if scenario.family == "joins"
                            else {}
                        ),
                    }
                )
                result = ef.run_pipeline(
                    ef.PipelineSpec(
                        execution=plan,
                        profile=profile,
                        comparison_reference="expected",
                        comparison_policy=scenario.comparison.policy,
                    ),
                    source=source,
                    registry=transforms,
                    comparison=scenario.expected,
                    work_dir=work,
                )
                require(
                    result.execution is not None
                    and result.execution.state == "completed"
                    and result.execution.output is not None,
                    "Native execution did not complete",
                )
                expected_state = "equivalent" if variant == "control" else "different"
                require(
                    result.comparison is not None
                    and result.comparison.state == expected_state,
                    "Full expected comparison disagrees with proposed control",
                )
                require(
                    result.profile is not None and result.profile.complete,
                    "Profile incomplete",
                )
                if variant == "control":
                    vector = result.profile.vector.observations
                    require(
                        math.isclose(
                            vector[0].value,
                            math.log1p(len(expected_rows)),
                            rel_tol=1e-12,
                        ),
                        "Independent row feature differs",
                    )
                candidate = eb.Candidate(
                    candidate_id=f"{scenario.scenario_id}.{variant}.{engine}",
                    scenario_sha256=digest(scenario),
                    output=result.execution.output.data,
                    authors=("automated-preparation",),
                    kind=variant,
                    description="Proposed baseline or controlled output alteration",
                    implementation=result.execution.implementation_version,
                    rules_sha256_before_candidate=scenario.rules_sha256,
                )
                packet = eb.review_packet(
                    scenario, candidate, directory=directory / "reviewers"
                )
                oracle = eb.evaluate_oracle(
                    scenario, candidate, packet=packet, work_dir=work / "oracle"
                )
                require(
                    oracle.status == "pending" and oracle.label is None,
                    "Preparation must retain human review pending",
                )
                record = {
                    "pipeline": result.model_dump(mode="json"),
                    "scenario": scenario.scenario_id,
                    "candidate": candidate.model_dump(mode="json"),
                    "execution": result.execution.model_dump(mode="json"),
                    "profile": result.profile.model_dump(mode="json"),
                    "rules": result.rules.model_dump(mode="json")
                    if result.rules is not None
                    else None,
                    "comparison": result.comparison.model_dump(mode="json"),
                    "oracle": oracle.model_dump(mode="json"),
                }
                save(work / "preparation.json", record)
                records.append(
                    {
                        "file": (work / "preparation.json")
                        .relative_to(directory)
                        .as_posix(),
                        "sha256": sha(work / "preparation.json"),
                        "case_token": packet.case_token,
                    }
                )
                worksheets.append(
                    {
                        "case_token": packet.case_token,
                        "packet_sha256": digest(packet),
                        "reviewer": "",
                        "assigned_at": "",
                        "label": "",
                        "reason": "",
                        "recorded_at": "",
                    }
                )
                outputs[(variant, engine)] = result.execution.output.data
        for variant in ("control", "mutation"):
            for left, right in PAIRS:
                compared = ef.compare(
                    outputs[(variant, left)],
                    outputs[(variant, right)],
                    contract=scenario.comparison.contract,
                    policy=scenario.comparison.policy,
                    reference="peer",
                    work_dir=root
                    / (scenario.family + "-peer-" + variant + "-" + left + "-" + right),
                )
                require(compared.state == "equivalent", "Peer engines disagree")
        print(
            scenario.scenario_id
            + ": native controls/mutations and pending review packets prepared",
            flush=True,
        )
    for reviewer in ("A", "B"):
        with (directory / f"reviewer-{reviewer}.csv").open(
            "x", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(worksheets[0]))
            writer.writeheader()
            writer.writerows(worksheets)
    summary = {
        "schema": "equiframe.sercop-experiment-preparation.v1",
        "candidate": ef.__version__,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": SOURCE_SHA256,
        "catalog_sha256": digest(catalog),
        "splits_sha256": digest(splits),
        "source_dimensions": dimensions,
        "native_executions": len(records),
        "pending_human_packets": len(worksheets),
        "dependency_groups": len(eb.dependency_groups(catalog)),
        "split_counts": eb.split_counts(catalog, splits),
        "confirmed_normal_profiles": 0,
        "n_fit_accredited_per_family": {f: 0 for f in FAMILIES},
        "scientific_ready": False,
        "human_review_complete": False,
        "records": records,
        "remaining": [
            "Approve cohort/domain/protocol and resolve conservative template grouping",
            "Assign two independent reviewers/arbitrator and collect blind decisions",
            "Supply >10000 confirmed normal fit profiles per model/family, calibration and held-out test",
            "Freeze/fitting/paired metrics require those actual inputs",
        ],
        "tool_sha256": tool_identity[Path(__file__).name],
        "tool_source_sha256": tool_identity,
    }
    save(directory / "preparation-manifest.json", summary)
    (directory / "LEEME.txt").write_text(
        "Expediente SERCOP propuesto para Alpha A14.\n"
        "Entregar a cada revisor solamente reviewers/ y su CSV A o B.\n"
        "coordinator/ y preparation-manifest.json contienen variantes/decisiones técnicas: conservar privados del coordinador.\n"
        "Registrar asignación, identidad, fechas, decisión y razón. El árbitro resuelve desacuerdos después de ambas revisiones.\n"
        "Las etiquetas están vacías. Este piloto no acredita normalidad, N_fit ni resultados científicos.\n",
        encoding="utf-8",
    )
    require(
        {p.name: sha(p) for p in source_files} == tool_identity,
        "Preparation tools changed during execution",
    )
    save(
        directory / "integrity-manifest.json",
        {
            "schema": "equiframe.private-packet-integrity.v1",
            "files": packet_io.inventory(packet_io.root_path(directory)),
        },
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--units", type=int, default=12)
    args = parser.parse_args()
    try:
        result = prepare(args.archive.resolve(), args.output.resolve(), args.units)
    except (ValueError, OSError) as error:
        parser.exit(2, "Preparation failed: " + type(error).__name__ + "\n")
    print(
        json.dumps(
            {
                "technical_preparation": "PASS",
                "native_executions": result["native_executions"],
                "scientific_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
