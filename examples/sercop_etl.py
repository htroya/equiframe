"""Offline consumer of pinned official OCDS packages; never downloads implicitly."""

import argparse
import hashlib
import json
from decimal import Decimal
from itertools import permutations
from pathlib import Path
from time import perf_counter

import pyarrow as pa

import equiframe as ef


def column(name: str, *, money: bool = False, nullable: bool = False) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.DecimalType(precision=18, scale=2) if money else ef.StringType(),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_amount")
        if money
        else None,
    )


def spec(name: str, columns: tuple[ef.ColumnSpec, ...], keys: tuple[str, ...] = ()) -> ef.TableSpec:
    return ef.TableSpec(
        name=name,
        schema_spec=ef.TableSchema(
            columns=columns,
            keys=(
                ef.KeySpec(
                    name="grain",
                    columns=keys,
                    unique=True,
                    incomplete="reject",
                    scope=ef.TableKeyScope(),
                ),
            )
            if keys
            else (),
            multiplicity="preserve",
            order=ef.IgnoredOrder(),
        ),
    )


def contract(identifier: str, input_spec: ef.TableSpec, output_spec: ef.TableSpec) -> ef.Contract:
    return ef.Contract(
        schema_version="1.0",
        contract_id=identifier,
        revision=1,
        family="aggregations",
        inputs=(input_spec,),
        output=output_spec,
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                severity="error",
                required=True,
                specification=ef.SchemaCheck(table=output_spec.name),
            ),
        ),
    )


def artifact(value: pa.Table, path: Path) -> ef.ArtifactRef:
    with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, value.schema) as writer:
        writer.write_table(value)
    return ef.LocalArtifactStore(path.parent / "artifacts").put(
        path, media_type="application/vnd.apache.arrow.file"
    )


def extract(path: Path, output: Path) -> tuple[dict[str, ef.ArtifactRef], dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    if "records" in raw:
        raise ValueError("records packages require a separate explicit selection contract")
    # This consumer supports an explicitly selected single release per package.
    # Other package/version selection rules require a separate, reviewed extractor.
    releases = raw.get("releases")
    if not isinstance(releases, list) or len(releases) != 1:
        raise ValueError("this example requires exactly one explicitly selected root release")
    release = releases[0]
    fields = (
        ef.FieldMapping(column=column("ocid"), path=("ocid",), scope="ancestor", ancestor_levels=2),
        ef.FieldMapping(column=column("award_id"), path=("id",)),
        ef.FieldMapping(column=column("currency"), path=("value", "currency")),
        ef.FieldMapping(column=column("amount", money=True), path=("value", "amount")),
    )
    tables = {}
    awards = release.get("awards", [])
    if awards:
        result = ef.ingest_file(
            path,
            spec=ef.IngestionSpec(
                format="json",
                records_path=("releases", "*", "awards", "*"),
                fields=fields,
                extra_fields="ignore",
            ),
            work_dir=output / "ingestion",
        )
        if result.state != "completed" or result.output is None:
            raise ValueError("award ingestion is incomplete: " + result.model_dump_json())
        tables["awards"] = result.output
        for relation, identity in (("suppliers", "supplier_id"), ("items", "item_id")):
            # A missing array is unknown coverage, never permission to drop valid peers.
            present = [relation in award for award in awards]
            if any(present) and not all(present):
                raise ValueError(
                    "partially absent relation arrays require an explicit extraction policy: "
                    + relation
                )
            if all(relation in award for award in awards):
                relation_fields = (
                    ef.FieldMapping(
                        column=column("ocid"), path=("ocid",), scope="ancestor", ancestor_levels=4
                    ),
                    ef.FieldMapping(
                        column=column("award_id"), path=("id",), scope="ancestor", ancestor_levels=2
                    ),
                    ef.FieldMapping(column=column(identity), path=("id",)),
                )
                result = ef.ingest_file(
                    path,
                    spec=ef.IngestionSpec(
                        format="json",
                        records_path=("releases", "*", "awards", "*", relation, "*"),
                        fields=relation_fields,
                        extra_fields="ignore",
                    ),
                    work_dir=output / "ingestion",
                )
                if result.state != "completed" or result.output is None:
                    raise ValueError(
                        "relation ingestion is incomplete: " + result.model_dump_json()
                    )
                tables[relation] = result.output
    procedure = pa.table(
        {
            "ocid": [release["ocid"]],
            "release_id": [release["id"]],
            "release_date": [release["date"]],
            "package_published_date": [raw.get("publishedDate")],
            "award_dates": [json.dumps([award.get("date") for award in awards])],
        }
    )
    tables["procedures"] = artifact(procedure, output / (path.stem + "-procedures.arrow"))
    return tables, {
        "file": path.name,
        "ocid": release["ocid"],
        "release_id": release["id"],
        "package_version": raw.get("version"),
        "selection": (
            "one explicit root release; compiled suffix retained without inferring history"
        ),
        "source_awards": len(awards),
        "license": raw.get("license"),
        "record_package": "records" in raw,
        "release_date": release.get("date"),
        "package_published_date": raw.get("publishedDate"),
        "award_dates": [award.get("date") for award in awards],
        "missing_relation_arrays": {
            name: sum(name not in a for a in awards) for name in ("suppliers", "items")
        },
    }


def run(snapshot: Path, expected_path: Path, output: Path) -> dict[str, object]:
    started = perf_counter()
    phase_seconds = {}
    output.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (snapshot / "snapshot.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    capture = output / "snapshot-capture"
    capture.mkdir(exist_ok=True)
    (capture / "snapshot.json").write_bytes(manifest_bytes)
    filenames = [receipt["file"] for receipt in manifest["receipts"]]
    if len(filenames) != len(set(filenames)):
        raise ValueError("snapshot filenames must be unique")
    collection: dict[str, list[pa.Table]] = {}
    inspection = []
    for receipt in manifest["receipts"]:
        filename = receipt["file"]
        if Path(filename).name != filename:
            raise ValueError("snapshot references must be simple local filenames")
        path = snapshot / filename
        payload = path.read_bytes()
        if (
            len(payload) != receipt["bytes"]
            or hashlib.sha256(payload).hexdigest() != receipt["sha256"]
        ):
            raise ValueError("source snapshot size/hash mismatch")
        captured = capture / filename
        captured.write_bytes(payload)
        if not filename.startswith("record-"):
            continue
        extracted, info = extract(captured, output)
        inspection.append(info)
        for name, reference in extracted.items():
            collection.setdefault(name, []).append(ef.read_table(reference))
    tables = {name: pa.concat_tables(parts) for name, parts in collection.items()}
    if "awards" not in tables:
        raise ValueError("snapshot has no awards in the explicitly supported grain")
    phase_seconds["ingestion_extraction"] = perf_counter() - started
    tick = perf_counter()
    expected_bytes = expected_path.read_bytes()
    (output / "expected-source.json").write_bytes(expected_bytes)
    expected_document = json.loads(expected_bytes)
    if expected_document["snapshot_id"] != manifest["snapshot_id"]:
        raise ValueError("manual expected subset belongs to another snapshot")
    expected_awards = pa.table(
        {
            "ocid": [r["ocid"] for r in expected_document["awards"]],
            "award_id": [r["award_id"] for r in expected_document["awards"]],
            "currency": [r["currency"] for r in expected_document["awards"]],
            "amount": pa.array(
                [Decimal(r["amount"]) for r in expected_document["awards"]],
                type=pa.decimal128(18, 2),
            ),
        }
    )
    award_columns = (
        column("ocid"),
        column("award_id"),
        column("currency"),
        column("amount", money=True),
    )
    award_spec = spec("awards", award_columns, ("ocid", "award_id"))
    identity_contract = contract(
        "sercop.example.awards", award_spec, spec("result", award_columns, ("ocid", "award_id"))
    )
    award_ref = artifact(tables["awards"], output / "awards.arrow")
    manual_ref = artifact(expected_awards, output / "manual-awards.arrow")
    expected_method = expected_document.get(
        "method", "Fixed literal fixture supplied by the consumer; no human O reviews"
    )
    expected_authors = tuple(expected_document.get("authors", ()))
    reconciliation = ef.compare(
        award_ref,
        manual_ref,
        contract=identity_contract,
        reference="expected",
        work_dir=output / "reconciliation",
    )
    if reconciliation.state != "equivalent" or not reconciliation.complete:
        raise ValueError("independent subset reconciliation failed")
    phase_seconds["expected_preparation_and_subset_comparison"] = perf_counter() - tick
    tick = perf_counter()
    # Relation tables contain no amount. Membership is checked separately before publication.
    award_keys = {(r["ocid"], r["award_id"]) for r in tables["awards"].to_pylist()}
    if len(award_keys) != tables["awards"].num_rows:
        raise ValueError(
            "multiple versions/duplicate award grain require an explicit selection contract"
        )
    for name in ("suppliers", "items"):
        if name in tables and any(
            (r["ocid"], r["award_id"]) not in award_keys for r in tables[name].to_pylist()
        ):
            raise ValueError("orphan award relation: " + name)
    total = ef.ColumnSpec(
        name="total",
        logical_type=ef.DecimalType(precision=20, scale=2),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_amount"),
    )
    rows = ef.ColumnSpec(
        name="rows",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="rows"),
    )
    totals_contract = contract(
        "sercop.example.currency", award_spec, spec("result", (column("currency"), total, rows))
    )
    totals_plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="awards"),
            ef.Aggregate(
                node_id="totals",
                source="scan",
                group_by=("currency",),
                measures=(
                    ef.Measure(
                        name="total",
                        operation="sum",
                        column="amount",
                        logical_type=ef.DecimalType(precision=20, scale=2),
                        unit="currency_amount",
                    ),
                    ef.Measure(
                        name="rows",
                        operation="count_rows",
                        logical_type=ef.IntegerType(bits=64, signed=True),
                        unit="rows",
                    ),
                ),
                null_groups="retain",
                empty_sum="null",
            ),
        ),
        output="totals",
    )
    manual_totals = expected_document["totals"]
    totals_ref = artifact(
        pa.table(
            {
                "currency": [r["currency"] for r in manual_totals],
                "total": pa.array(
                    [Decimal(r["total"]) for r in manual_totals], type=pa.decimal128(20, 2)
                ),
                "rows": pa.array([r["rows"] for r in manual_totals], type=pa.int64()),
            }
        ),
        output / "manual-totals.arrow",
    )
    migrations = []
    phase_seconds["relations_and_plan_preparation"] = perf_counter() - tick
    tick = perf_counter()
    for source, target in permutations(("pandas", "polars", "duckdb"), 2):
        migration = ef.migrate(
            ef.MigrationSpec(
                contract=totals_contract,
                ir=totals_plan,
                source_engine=source,
                target_engine=target,
                comparison_policy=ef.ComparisonPolicy(
                    index="ignore", justification="Generated index is not part of the OCDS grain"
                ),
            ),
            source=ef.LocalDataSource({"awards": award_ref}),
            expected=totals_ref,
            work_dir=output / "migrations",
        )
        if migration.exit_code:
            raise ValueError(json.dumps(ef.migration_summary(migration)))
        migrations.append(migration)
    phase_seconds["native_migrations_including_comparisons_and_evidence"] = perf_counter() - tick
    tick = perf_counter()
    gates = {
        "awards": ef.verify(
            {"observed": award_ref},
            contract=identity_contract,
            expected=manual_ref,
            provenance=(
                ef.ExpectedProvenance(
                    expected_sha256=manual_ref.sha256,
                    method=expected_method,
                    authors=expected_authors,
                    independence_declared=False,
                )
                if expected_authors
                else None
            ),
            require_expected=True,
            work_dir=output / "verify",
        )
    }
    publish = {"awards": award_ref}
    latest = migrations[-1]
    assert (
        latest.target is not None
        and latest.target.execution is not None
        and latest.target.execution.output is not None
    )
    publish["totals"] = latest.target.execution.output.data
    gates["totals"] = ef.verify_migration(
        output / "migrations" / latest.migration_id,
        work_dir=output / "verify",
        provenance=(
            ef.ExpectedProvenance(
                expected_sha256=totals_ref.sha256,
                method=expected_method,
                authors=expected_authors,
                independence_declared=False,
            )
            if expected_authors
            else None
        ),
    )
    for name in ("suppliers", "items", "procedures"):
        if name not in tables:
            continue
        current = tables[name]
        columns = tuple(
            column(field.name, nullable=current[field.name].null_count > 0)
            for field in current.schema
        )
        relation_contract = contract(
            "sercop.example." + name, spec(name, columns), spec("result", columns)
        )
        publish[name] = artifact(current, output / (name + ".arrow"))
        gates[name] = ef.verify(
            {"observed": publish[name]}, contract=relation_contract, work_dir=output / "verify"
        )
    phase_seconds["verification_and_evidence_readback"] = perf_counter() - tick
    tick = perf_counter()
    destination = ef.ParquetDestination(output / "published")
    receipt = destination.publish(publish, run_id=manifest["snapshot_id"], verifications=gates)
    assert (
        receipt
        == destination.publish(publish, run_id=manifest["snapshot_id"], verifications=gates)
        == destination.current()
    )
    phase_seconds["load_staging_readback_publication_and_idempotent_retry"] = perf_counter() - tick
    tick = perf_counter()
    bundle = output / (latest.migration_id + "-bundle")
    ef.export_bundle(output / "migrations" / latest.migration_id, bundle)
    ef.import_bundle(bundle, output / (latest.migration_id + "-copied"))
    phase_seconds["portable_evidence_export_import_readback"] = perf_counter() - tick
    tick = perf_counter()
    optional_reconciliation = None
    try:
        from equiframe_benchmark import AwardReconciliationSpec, reconcile_awards
    except ImportError:
        pass
    else:
        optional_reconciliation = reconcile_awards(
            expected_awards,
            tables["awards"],
            spec=AwardReconciliationSpec(
                domain_schema_revision="example-not-DW-v1",
                award_keys=("ocid", "award_id"),
                amount_column="amount",
                currency_column="currency",
                bridge_award_keys=("ocid", "award_id"),
                supplier_column="supplier_id",
            ),
            bridge=tables.get("suppliers"),
        ).model_dump(mode="json")
    phase_seconds["optional_benchmark_reconciliation"] = perf_counter() - tick
    summary = {
        "snapshot_id": manifest["snapshot_id"],
        "synthetic": bool(manifest.get("synthetic", False)),
        "sources": manifest,
        "expected_source": {
            "file": expected_path.name,
            "preserved_file": "expected-source.json",
            "sha256": hashlib.sha256(expected_bytes).hexdigest(),
            "size_bytes": len(expected_bytes),
            "method": expected_method,
            "authors_declared": expected_authors,
            "independence_declared": False,
        },
        "inspection": inspection,
        "rows": {name: value.num_rows for name, value in tables.items()},
        "grain": {
            "awards": ["ocid", "award_id"],
            "suppliers": ["ocid", "award_id", "supplier_id"],
            "items": ["ocid", "award_id", "item_id"],
        },
        "subset_reconciliation": {
            "complete": reconciliation.complete,
            "state": reconciliation.state,
            "expected_sha256": manual_ref.sha256,
            "scope": (
                "exactly the selected award rows; relation tables have schema and orphan checks; "
                "independent human expected review is absent"
            ),
        },
        "migrations": [ef.migration_summary(m) for m in migrations],
        "load": receipt.model_dump(mode="json"),
        "benchmark_reconciliation": optional_reconciliation,
        "idempotent": True,
        "portable_bundle_verified": True,
        "scientific_O": "not_established",
        "DW_OCI_integration": "not_requested",
        "resources": {
            "phase_wall_seconds": phase_seconds,
            "measured_until_summary_seconds": perf_counter() - started,
            "scope": (
                "sequential consumer phases; migration timing includes execution, comparison "
                "and evidence, which are not isolated costs; excludes network capture"
            ),
        },
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("sercop-etl"))
    args = parser.parse_args()
    summary = run(args.snapshot, args.expected, args.output)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "snapshot_id",
                    "synthetic",
                    "rows",
                    "idempotent",
                    "portable_bundle_verified",
                    "scientific_O",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
