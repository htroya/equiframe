"""C: synthetic CSV/JSON retail ETL, explicit quarantine and gated local Parquet.

Requires the installed EquiFrame wheel with pandas, DuckDB and Arrow extras.
Run with a NEW directory: python c_retail_etl.py --output ./retail-good --case good
The two source formats represent the same sales, not two batches to concatenate.
Exit 0 accepts the explicitly selected valid subset; 1 rejects a discrepancy;
2 rejects invalid input. Raw evidence contains original values and local paths.
Only public_reports/ contains the default data-minimized comparison reports.
This example does not publish a package, deploy a service or claim scientific O.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, write_summary
else:
    from common import cli, write_summary


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def _text(name: str) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )


def _money(name: str, precision: int, *, nullable: bool = False) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.DecimalType(precision=precision, scale=2),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_amount"),
    )


def _table(name: str, columns: tuple[ef.ColumnSpec, ...]) -> ef.TableSpec:
    return ef.TableSpec(
        name=name,
        schema_spec=ef.TableSchema(
            columns=columns, keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
        ),
    )


def _contract(
    identifier: str, inputs: tuple[ef.ColumnSpec, ...], output: tuple[ef.ColumnSpec, ...]
) -> ef.Contract:
    return ef.Contract(
        schema_version="1.0",
        contract_id=identifier,
        revision=1,
        family="aggregations",
        inputs=(_table("sales", inputs),),
        output=_table("result", output),
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                severity="error",
                required=True,
                specification=ef.SchemaCheck(table="result"),
            ),
        ),
    )


def _artifact(value: pa.Table, path: Path) -> ef.ArtifactRef:
    import pyarrow as pa

    with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, value.schema) as writer:
        writer.write_table(value)
    return ef.LocalArtifactStore(path.parent / "expected-artifacts").put(
        path, media_type="application/vnd.apache.arrow.file"
    )


def _plans() -> tuple[ef.RelationalPlan, ef.RelationalPlan]:
    net = ef.RelationalPlan(
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
    totals = ef.RelationalPlan(
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
    return net, totals


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    """Run a complete example; existing output directories are never reused."""
    import pyarrow as pa

    if scenario not in ("good", "different", "error"):
        raise ValueError("scenario must be good, different or error")
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    raw = output / "raw"
    raw.mkdir()
    sku, currency = _text("sku"), _text("currency")
    gross, discount = _money("gross", 18), _money("discount", 18, nullable=True)
    net, total = _money("net", 19), _money("total", 20, nullable=True)
    rows = ef.ColumnSpec(
        name="rows",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="rows"),
    )
    fields = tuple(
        ef.FieldMapping(
            column=column,
            path=(column.name,),
            null_tokens=("NULL",) if column.name == "discount" else (),
        )
        for column in (sku, currency, gross, discount)
    )
    # A one-cent upstream CSV regression changes both native engines' answer.
    # JSON remains correct, demonstrating that an independent chain can finish.
    first_gross = "12.51" if scenario == "different" else "12.50"
    (raw / "sales.csv").write_text(
        "sku,currency,gross,discount\n"
        f"0007,USD,{first_gross},0.50\n"
        "0008,USD,2.00,NULL\n0009,EUR,10.00,1.00\n"
        "0010,USD,not-money,0.00\n",
        encoding="utf-8",
    )
    _write_json(
        raw / "sales.json",
        {
            "sales": [
                {"sku": "0007", "currency": "USD", "gross": "12.50", "discount": "0.50"},
                {"sku": "0008", "currency": "USD", "gross": "2.00", "discount": None},
                {"sku": "0009", "currency": "EUR", "gross": "10.00", "discount": "1.00"},
                {"sku": "0010", "currency": "USD", "gross": "not-money", "discount": "0.00"},
            ]
        },
    )
    ingestions = {}
    for source_format in ("csv", "json"):
        spec = ef.IngestionSpec(
            format=source_format,
            fields=fields,
            records_path=("sales", "*") if source_format == "json" else (),
            invalid_records="reject" if scenario == "error" else "quarantine",
            max_source_bytes=16_384,
            max_records=10,
        )
        ingestions[source_format] = ef.ingest_file(
            raw / ("sales." + source_format), spec=spec, work_dir=raw / "ingestion"
        )

    # This is an explicit example-level disposition, not automatic approval of
    # any quarantined dataset. FileInput deliberately refuses quarantine.
    # Exactly the known fourth synthetic record may be excluded in this demo.
    adopt_subset = scenario != "error" and all(
        result.state == "quarantined"
        and result.inspected_records == 4
        and result.accepted_records == 3
        and len(result.quarantined) == 1
        and result.quarantined[0].record == 3
        and result.quarantined[0].code == "invalid_decimal"
        and result.output is not None
        for result in ingestions.values()
    )
    disposition = {
        "synthetic": True,
        "choice": "adopt_explicit_valid_subset" if adopt_subset else "reject_entire_input",
        "all_source_rows_valid": False,
        "accepted_subset_adopted": adopt_subset,
        "allowed_exclusion": "Only zero-based record 3 with invalid_decimal in each source",
        "reason": (
            "The example explicitly selects three valid records per format and retains the "
            "invalid originals. Real input requires its owner's separate disposition."
            if adopt_subset
            else "Invalid records reject each complete input; no partial table is used."
        ),
        "sources": {
            name: {
                "state": result.state,
                "inspected_records": result.inspected_records,
                "parsed_records": result.accepted_records,
                "quarantined_records": len(result.quarantined),
                "output_available": result.output is not None,
                "diagnostics": [
                    {"record": item.record, "path": item.path, "code": item.code}
                    for item in result.quarantined
                ],
                "raw_receipt": f"raw/ingestion/{result.ingestion_id}/ingestion.json",
            }
            for name, result in ingestions.items()
        },
    }
    _write_json(raw / "quarantine-disposition.json", disposition)
    summary: dict[str, object] = {
        "synthetic": True,
        "journey": "C",
        "scenario": scenario,
        "exit_code": 2,
        "accepted": False,
        "state": "invalid_input",
        "workflow_complete": False,
        "workflow_exit_code": None,
        "first_divergent_stage": None,
        "checkpoints": {},
        "verifications": {},
        "published": False,
        "publication": None,
        "all_source_rows_valid": False,
        "accepted_subset_adopted": adopt_subset,
        "ingestion": disposition["sources"],
        "expected_method": "Literal Decimal rows enumerated separately from the IR and engines",
        "acceptance": {
            "requires": "Explicit subset disposition, all checkpoints, Verify and local readback",
            "expected_required": True,
            "rules_required": True,
            "scientific_review": "not_requested",
        },
        "artifacts": {
            "environment": "environment.json",
            "raw_evidence": "raw/",
            "quarantine_disposition": "raw/quarantine-disposition.json",
            "data_minimized_reports": [],
            "publication": None,
        },
        "privacy": (
            "raw/ includes source values, quarantine originals and local paths; "
            "public_reports/ contains only default redacted comparison views"
        ),
        "limits": (
            "Synthetic local files; pandas and DuckDB execute separately. No real DW, "
            "business approval, scientific O, distributed transaction or hard resource quota."
        ),
    }
    if not adopt_subset:
        return write_summary(output, summary)

    normalize = _contract(
        "retail.journey.net", (sku, currency, gross, discount), (sku, currency, net)
    )
    aggregate = _contract("retail.journey.totals", (sku, currency, net), (currency, total, rows))
    net_ir, totals_ir = _plans()
    policy = ef.ComparisonPolicy(
        index="ignore", justification="Generated RangeIndex has no business identity"
    )
    stages = []
    for name in ingestions:
        for suffix, contract, plan in (
            ("net", normalize, net_ir),
            ("totals", aggregate, totals_ir),
        ):
            stages.append(
                ef.WorkflowStage(
                    stage_id=f"{name}_{suffix}",
                    migration=ef.MigrationSpec(
                        contract=contract,
                        ir=plan,
                        source_engine="pandas",
                        target_engine="duckdb",
                        comparison_policy=policy,
                    ),
                    inputs=(
                        ef.WorkflowInputBinding(name="sales", source=name)
                        if suffix == "net"
                        else ef.WorkflowInputBinding(
                            name="sales", source="result", stage=f"{name}_net"
                        ),
                    ),
                )
            )
    expected_net = _artifact(
        pa.table(
            {
                "sku": ["0007", "0008", "0009"],
                "currency": ["USD", "USD", "EUR"],
                "net": pa.array(
                    [Decimal("12.00"), Decimal("2.00"), Decimal("9.00")],
                    type=pa.decimal128(19, 2),
                ),
            }
        ),
        raw / "expected-net.arrow",
    )
    expected_totals = _artifact(
        pa.table(
            {
                "currency": ["USD", "EUR"],
                "total": pa.array([Decimal("14.00"), Decimal("9.00")], type=pa.decimal128(20, 2)),
                "rows": pa.array([2, 1], type=pa.int64()),
            }
        ),
        raw / "expected-totals.arrow",
    )
    workflow = ef.run_workflow(
        ef.WorkflowSpec(workflow_id="retail.journey.C", stages=tuple(stages)),
        source=ef.LocalDataSource(
            {
                name: result.output
                for name, result in ingestions.items()
                if result.output is not None
            }
        ),
        expected={
            stage.stage_id: expected_net if stage.stage_id.endswith("net") else expected_totals
            for stage in stages
        },
        work_dir=raw / "workflows",
    )
    workflow_path = raw / "workflows" / workflow.run_id
    if ef.read_workflow(workflow_path) != workflow:
        raise RuntimeError("Persisted workflow differs from its returned result")
    reports = {}
    public_reports = []
    for checkpoint in workflow.checkpoints:
        migration = checkpoint.migration
        if migration is None or migration.source is None or migration.target is None:
            continue
        report = ef.verify(
            {"source": migration.source, "target": migration.target},
            contract=migration.spec.contract,
            expected=migration.expected,
            require_expected=True,
            require_rules=True,
            snapshots={table.name: table.data for table in migration.inputs},
            plan_sha256=ef.ir_fingerprint(migration.spec.ir),
            policy=policy,
            work_dir=raw / "verify",
        )
        if ef.read_verification(raw / "verify" / report.verification_id) != report:
            raise RuntimeError("Persisted verification differs from its returned result")
        reports[checkpoint.stage_id] = report
        for number, comparison in enumerate(report.comparisons):
            directory = output / "public_reports" / checkpoint.stage_id / str(number)
            ef.write_comparison_report(comparison, directory)
            public_reports.append(str((directory / "report.html").relative_to(output)))

    gate = (
        workflow.complete
        and len(reports) == len(stages)
        and all(report.publishable and report.coverage.complete for report in reports.values())
    )
    publication = None
    if gate:
        destination = ef.ParquetDestination(output / "published")
        receipt = destination.publish(
            workflow.outputs, run_id="retail-journey-C", verifications=reports
        )
        if destination.current() != receipt:
            raise RuntimeError("Local Parquet publication failed verified readback")
        publication = receipt.model_dump(mode="json")
    summary.update(
        exit_code=0 if gate else 1 if workflow.exit_code == 1 else 3,
        accepted=gate,
        state="accepted" if gate else "different" if workflow.exit_code == 1 else "not_evaluable",
        workflow_complete=workflow.complete,
        workflow_exit_code=workflow.exit_code,
        published=publication is not None,
        first_divergent_stage=workflow.first_divergent_stage,
        checkpoints={item.stage_id: item.state for item in workflow.checkpoints},
        verifications={
            name: {
                "operational_state": report.operational_state,
                "publishable": report.publishable,
                "technical": report.technical.state,
                "agreement": report.agreement.state,
                "expected": [check.state for check in report.expected],
                "rules": [check.state for check in report.rules],
                "coverage_complete": report.coverage.complete,
                "independent_review": report.independent_review.state,
                "raw_manifest": f"raw/verify/{report.verification_id}/verification.json",
            }
            for name, report in reports.items()
        },
        publication=publication,
        artifacts={
            "environment": "environment.json",
            "raw_evidence": "raw/",
            "quarantine_disposition": "raw/quarantine-disposition.json",
            "workflow": str((workflow_path / "workflow.json").relative_to(output)),
            "data_minimized_reports": public_reports,
            "publication": "published/current.json" if gate else None,
        },
    )
    return write_summary(output, summary)


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "C", ("good", "different", "error")))
