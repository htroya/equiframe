"""Synthetic retail ETL consumer; runs from an installed package without this checkout."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from equiframe.comparison_types import ComparisonPolicy
from equiframe.contracts import (
    ColumnSpec,
    Contract,
    DecimalType,
    IgnoredOrder,
    NullPolicy,
    NumericPolicy,
    StringType,
    TableSchema,
    TableSpec,
)
from equiframe.destinations import ParquetDestination
from equiframe.ingestion import FieldMapping, FileInput, IngestionSpec
from equiframe.local import LocalArtifactStore
from equiframe.migration.runner_types import MigrationSpec
from equiframe.migration.types import (
    Aggregate,
    Column,
    Measure,
    NamedExpression,
    Project,
    RelationalPlan,
    Scan,
)
from equiframe.tables import LocalDataSource, read_table
from equiframe.verify import verify
from equiframe.workflow import (
    InputBinding,
    WorkflowSpec,
    WorkflowStage,
    read_workflow,
    run_workflow,
)


def field(name, dtype, *, nullable=False, unit=None):
    return ColumnSpec(
        name=name,
        logical_type=dtype,
        nullable=nullable,
        null_policy=NullPolicy(representations=("null",)),
        numeric_policy=NumericPolicy(comparison="exact", unit=unit) if unit else None,
    )


def table(name, columns):
    return TableSpec(
        name=name,
        schema_spec=TableSchema(
            columns=tuple(columns), keys=(), multiplicity="preserve", order=IgnoredOrder()
        ),
    )


def main() -> None:
    import pyarrow as pa

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("retail-etl"))
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "orders.csv"
    if not source.exists():
        source.write_text(
            "id,currency,amount\n001,USD,10.10\n002,USD,0.20\n003,EUR,8.00\n", encoding="utf-8"
        )
    inputs = (
        field("id", StringType()),
        field("currency", StringType()),
        field("amount", DecimalType(precision=10, scale=2), unit="money"),
    )
    totals = (
        field("currency", StringType()),
        field("total", DecimalType(precision=12, scale=2), nullable=True, unit="money"),
    )
    final = (
        totals[0],
        field("revenue", DecimalType(precision=12, scale=2), nullable=True, unit="money"),
    )
    first = Contract(
        schema_version="1.0",
        contract_id="retail.totals",
        revision=1,
        family="aggregations",
        inputs=(table("orders", inputs),),
        output=table("totals", totals),
        preconditions=(),
        rules=(),
    )
    second = Contract(
        schema_version="1.0",
        contract_id="retail.publish",
        revision=1,
        family="aggregations",
        inputs=(table("totals", totals),),
        output=table("revenue", final),
        preconditions=(),
        rules=(),
    )
    aggregate = RelationalPlan(
        nodes=(
            Scan(node_id="orders", table="orders"),
            Aggregate(
                node_id="totals",
                source="orders",
                group_by=("currency",),
                measures=(
                    Measure(
                        name="total",
                        operation="sum",
                        column="amount",
                        logical_type=DecimalType(precision=12, scale=2),
                        unit="money",
                    ),
                ),
                null_groups="retain",
                empty_sum="null",
            ),
        ),
        output="totals",
    )
    rename = RelationalPlan(
        nodes=(
            Scan(node_id="totals", table="totals"),
            Project(
                node_id="publish",
                source="totals",
                columns=(
                    NamedExpression(name="currency", expression=Column(name="currency")),
                    NamedExpression(name="revenue", expression=Column(name="total")),
                ),
            ),
        ),
        output="publish",
    )
    policy = ComparisonPolicy(
        index="ignore", justification="Generated row indices are not retail keys"
    )
    spec = WorkflowSpec(
        workflow_id="retail",
        stages=(
            WorkflowStage(
                stage_id="totals",
                migration=MigrationSpec(
                    ir=aggregate,
                    contract=first,
                    source_engine="pandas",
                    target_engine="polars",
                    require_rules=False,
                    comparison_policy=policy,
                ),
                inputs=(InputBinding(name="orders", source="orders"),),
            ),
            WorkflowStage(
                stage_id="publish",
                migration=MigrationSpec(
                    ir=rename,
                    contract=second,
                    source_engine="duckdb",
                    target_engine="pandas",
                    require_rules=False,
                    comparison_policy=policy,
                ),
                inputs=(InputBinding(name="totals", source="totals", stage="totals"),),
            ),
        ),
    )
    expected = {}
    for name, amount_name in (("totals", "total"), ("publish", "revenue")):
        ledger = pa.table(
            {
                "currency": ["USD", "EUR"],
                amount_name: pa.array(
                    [Decimal("10.30"), Decimal("8.00")], type=pa.decimal128(12, 2)
                ),
            }
        )
        path = directory / ("expected-" + name + ".arrow")
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, ledger.schema) as writer:
            writer.write_table(ledger)
        expected[name] = LocalArtifactStore(directory / "expected").put(
            path, media_type="application/vnd.apache.arrow.file"
        )
    ingestion = IngestionSpec(
        format="csv", fields=tuple(FieldMapping(column=c, path=(c.name,)) for c in inputs)
    )
    result = run_workflow(
        spec,
        source=LocalDataSource({"orders": FileInput(source, ingestion)}),
        work_dir=directory,
        expected=expected,
    )
    if not result.complete:
        raise RuntimeError(
            "ETL checkpoint failed: "
            + str([(c.stage_id, c.state, c.code) for c in result.checkpoints])
        )
    checkpoint = result.checkpoints[-1].migration
    report = verify(
        {"source": checkpoint.source, "target": checkpoint.target},
        contract=second,
        expected=expected["publish"],
        policy=policy,
        work_dir=directory,
    )
    receipt = ParquetDestination(directory / "published").publish(
        {"revenue": result.outputs["publish"]},
        run_id=result.run_id,
        verifications={"revenue": report},
        policy="replace",
    )
    assert read_workflow(directory / result.run_id) == result
    print(
        json.dumps(
            {
                "workflow": result.run_id,
                "complete": result.complete,
                "verification": report.operational_state,
                "load": receipt.run_id,
                "revenue": str(read_table(result.outputs["publish"]).to_pylist()),
                "scientific_O": report.independent_review.state,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
