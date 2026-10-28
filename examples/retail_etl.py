"""Synthetic retail CSV to two native ETL checkpoints, Verify and local Parquet."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def text(name: str) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )


def money(name: str, precision: int, *, nullable: bool = False) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.DecimalType(precision=precision, scale=2),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_amount"),
    )


def table(name: str, columns: tuple[ef.ColumnSpec, ...]) -> ef.TableSpec:
    return ef.TableSpec(
        name=name,
        schema_spec=ef.TableSchema(
            columns=columns, keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
        ),
    )


def contract(
    identifier: str, inputs: tuple[ef.TableSpec, ...], output: ef.TableSpec
) -> ef.Contract:
    return ef.Contract(
        schema_version="1.0",
        contract_id=identifier,
        revision=1,
        family="aggregations",
        inputs=inputs,
        output=output,
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                severity="error",
                required=True,
                specification=ef.SchemaCheck(table=output.name),
            ),
        ),
    )


def artifact(value: pa.Table, path: Path) -> ef.ArtifactRef:
    with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, value.schema) as writer:
        writer.write_table(value)
    return ef.LocalArtifactStore(path.parent / "expected-artifacts").put(
        path, media_type="application/vnd.apache.arrow.file"
    )


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    source = output / "retail.csv"
    source.write_text(
        "sku,currency,gross,discount\n0007,USD,12.50,0.50\n0008,USD,2.00,NULL\n0009,EUR,10.00,1.00\n",
        encoding="utf-8",
    )
    sku, currency = text("sku"), text("currency")
    gross, discount, net, total = (
        money("gross", 18),
        money("discount", 18, nullable=True),
        money("net", 19),
        money("total", 20, nullable=True),
    )
    ingestion = ef.ingest_file(
        source,
        spec=ef.IngestionSpec(
            format="csv",
            fields=(
                ef.FieldMapping(column=sku, path=("sku",)),
                ef.FieldMapping(column=currency, path=("currency",)),
                ef.FieldMapping(column=gross, path=("gross",)),
                ef.FieldMapping(column=discount, path=("discount",), null_tokens=("NULL",)),
            ),
        ),
        work_dir=output / "ingestion",
    )
    assert ingestion.state == "completed" and ingestion.output is not None
    normalize = contract(
        "retail.net",
        (table("sales", (sku, currency, gross, discount)),),
        table("result", (sku, currency, net)),
    )
    rows = ef.ColumnSpec(
        name="rows",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="rows"),
    )
    aggregate = contract(
        "retail.totals",
        (table("sales", (sku, currency, net)),),
        table("result", (currency, total, rows)),
    )
    policy = ef.ComparisonPolicy(
        index="ignore", justification="Generated RangeIndex has no business identity"
    )
    net_ir = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="sales"),
            ef.Project(
                node_id="net",
                source="scan",
                columns=(
                    ef.NamedExpression(name="sku", expression=ef.Column(name="sku")),
                    ef.NamedExpression(name="currency", expression=ef.Column(name="currency")),
                    ef.NamedExpression(
                        name="net",
                        expression=ef.Arithmetic(
                            operation="subtract",
                            left=ef.Column(name="gross"),
                            right=ef.Coalesce(
                                arguments=(
                                    ef.Column(name="discount"),
                                    ef.LiteralExpression(
                                        logical_type=ef.DecimalType(precision=18, scale=2),
                                        value=ef.DecimalValue(value=Decimal("0.00")),
                                        unit="currency_amount",
                                    ),
                                )
                            ),
                            logical_type=ef.DecimalType(precision=19, scale=2),
                            unit="currency_amount",
                        ),
                    ),
                ),
            ),
        ),
        output="net",
    )
    totals_ir = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="sales"),
            ef.Aggregate(
                node_id="totals",
                source="scan",
                group_by=("currency",),
                measures=(
                    ef.Measure(
                        name="total",
                        operation="sum",
                        column="net",
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
    spec = ef.WorkflowSpec(
        workflow_id="retail.example",
        stages=(
            ef.WorkflowStage(
                stage_id="net",
                migration=ef.MigrationSpec(
                    contract=normalize,
                    ir=net_ir,
                    source_engine="pandas",
                    target_engine="duckdb",
                    comparison_policy=policy,
                ),
                inputs=(ef.WorkflowInputBinding(name="sales", source="sales"),),
            ),
            ef.WorkflowStage(
                stage_id="totals",
                migration=ef.MigrationSpec(
                    contract=aggregate,
                    ir=totals_ir,
                    source_engine="pandas",
                    target_engine="duckdb",
                    comparison_policy=policy,
                ),
                inputs=(ef.WorkflowInputBinding(name="sales", source="result", stage="net"),),
            ),
        ),
    )
    # Enumerated separately from the IR and from every engine; no human O is claimed.
    expected_net = artifact(
        pa.table(
            {
                "sku": ["0007", "0008", "0009"],
                "currency": ["USD", "USD", "EUR"],
                "net": pa.array(
                    [Decimal("12.00"), Decimal("2.00"), Decimal("9.00")], type=pa.decimal128(19, 2)
                ),
            }
        ),
        output / "expected-net.arrow",
    )
    expected_totals = artifact(
        pa.table(
            {
                "currency": ["USD", "EUR"],
                "total": pa.array([Decimal("14.00"), Decimal("9.00")], type=pa.decimal128(20, 2)),
                "rows": pa.array([2, 1], type=pa.int64()),
            }
        ),
        output / "expected-totals.arrow",
    )
    workflow = ef.run_workflow(
        spec,
        source=ef.LocalDataSource({"sales": ingestion.output}),
        expected={"net": expected_net, "totals": expected_totals},
        work_dir=output / "workflows",
    )
    if not workflow.complete:
        raise RuntimeError(workflow.model_dump_json())
    assert ef.read_workflow(output / "workflows" / workflow.run_id) == workflow
    reports = {
        checkpoint.stage_id: ef.verify_migration(
            output
            / "workflows"
            / workflow.run_id
            / checkpoint.stage_id
            / checkpoint.migration.migration_id,
            work_dir=output / "verify",
        )
        for checkpoint in workflow.checkpoints
        if checkpoint.migration is not None
    }
    destination = ef.ParquetDestination(output / "published")
    receipt = destination.publish(
        workflow.outputs, run_id="retail-example-v1", verifications=reports
    )
    repeated = destination.publish(
        workflow.outputs, run_id="retail-example-v1", verifications=reports
    )
    assert receipt == repeated == destination.current()
    bundle = output / (workflow.run_id + "-bundle")
    ef.export_bundle(output / "workflows" / workflow.run_id, bundle)
    ef.import_bundle(bundle, output / (workflow.run_id + "-copied"))
    summary = {
        "synthetic": True,
        "workflow_id": workflow.run_id,
        "complete": workflow.complete,
        "ingested_rows": ingestion.accepted_records,
        "checkpoints": [c.state for c in workflow.checkpoints],
        "verifications": {
            name: ef.verification_summary(report) for name, report in reports.items()
        },
        "load": receipt.model_dump(mode="json"),
        "idempotent": True,
        "portable_bundle_verified": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("retail-etl"))
    args = parser.parse_args()
    summary = run(args.output)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "synthetic",
                    "workflow_id",
                    "complete",
                    "ingested_rows",
                    "idempotent",
                    "portable_bundle_verified",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
