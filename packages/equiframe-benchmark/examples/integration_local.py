"""Synthetic consumer example; no real service, DW, oracle review or ML training.

Run from an installed distribution with the ``engines`` extra. Each native
implementation aggregates three awards independently, preserving exact amounts
and currencies. Expected USD 30.75 / EUR 7.00 totals are manually specified.
All three implementations explicitly produce the strict decimal(38,2) output
contract. Pandas declares the wider output dtype instead of relying on a
version-dependent groupby result dtype.
"""

import argparse
import hashlib
import json
import tempfile
from decimal import Decimal
from pathlib import Path

import equiframe as ef
import pyarrow as pa

import equiframe_benchmark as eb


def column(name, logical_type):
    return ef.ColumnSpec(
        name=name,
        logical_type=logical_type,
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_units")
        if isinstance(logical_type, ef.DecimalType)
        else None,
    )


def contract():
    source_columns = (
        column("snapshot_id", ef.StringType()),
        column("ocid", ef.StringType()),
        column("award_id", ef.StringType()),
        column("currency", ef.StringType()),
        column("amount", ef.DecimalType(precision=18, scale=2)),
    )
    output_columns = (
        column("currency", ef.StringType()),
        column("total", ef.DecimalType(precision=38, scale=2)),
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="synthetic.awards_by_currency",
        revision=1,
        family="aggregations",
        inputs=(
            ef.TableSpec(
                name="awards",
                schema_spec=ef.TableSchema(
                    columns=source_columns,
                    keys=(
                        ef.KeySpec(
                            name="award_grain",
                            columns=("snapshot_id", "ocid", "award_id"),
                            unique=True,
                            incomplete="reject",
                            scope=ef.TableKeyScope(),
                        ),
                    ),
                    multiplicity="preserve",
                    order=ef.IgnoredOrder(),
                ),
            ),
        ),
        output=ef.TableSpec(
            name="totals",
            schema_spec=ef.TableSchema(
                columns=output_columns,
                keys=(
                    ef.KeySpec(
                        name="currency",
                        columns=("currency",),
                        unique=True,
                        incomplete="reject",
                        scope=ef.TableKeyScope(),
                    ),
                ),
                multiplicity="preserve",
                order=ef.IgnoredOrder(),
            ),
        ),
        preconditions=(
            ef.PreconditionSpec(
                precondition_id="award_grain",
                requirement=ef.KeyCheck(table="awards", key="award_grain"),
            ),
        ),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                severity="error",
                required=True,
                specification=ef.SchemaCheck(table="totals"),
            ),
            ef.RuleSpec(
                rule_id="currency_key",
                revision=1,
                severity="error",
                required=True,
                specification=ef.KeyCheck(table="totals", key="currency"),
            ),
            ef.RuleSpec(
                rule_id="sum_by_currency",
                revision=1,
                severity="error",
                required=True,
                applicability=("award_grain",),
                specification=ef.AggregateCheck(
                    table="awards",
                    group_by=("currency",),
                    measure="amount",
                    function="sum",
                    output_table="totals",
                    output_column="total",
                ),
            ),
        ),
    )


def pandas_totals(tables, context):
    import pandas as pd

    result = (
        tables["awards"]
        .groupby("currency", sort=False, dropna=False)
        .agg(total=("amount", "sum"))
        .reset_index()
    )
    result["total"] = result["total"].astype(pd.ArrowDtype(pa.decimal128(38, 2)))
    return result


def polars_totals(tables, context):
    import polars as pl

    return tables["awards"].lazy().group_by("currency").agg(pl.col("amount").sum().alias("total"))


def registry_factory():
    registry = ef.TransformationRegistry()
    registry.register(
        ef.PandasTransformation("currency_totals", pandas_totals, "synthetic-pandas.2")
    )
    registry.register(
        ef.PolarsTransformation("currency_totals", polars_totals, "synthetic-polars.1")
    )
    registry.register(
        ef.DuckDBTransformation(
            "currency_totals",
            'SELECT currency, sum(amount) AS total FROM "awards" GROUP BY currency',
            "synthetic-duckdb.1",
        )
    )
    return registry


class LocalExampleClient:
    """A local fixture transport, unrelated to the future shared service."""

    def __init__(self, manifest):
        self.manifest = manifest

    def get_snapshot(self, snapshot_id):
        if snapshot_id != self.manifest.snapshot_id:
            raise ValueError("unknown synthetic snapshot")
        return self.manifest

    def download_artifact(self, ref, destination):
        ef.LocalArtifactStore(destination.parent).get(ref, destination)


def run_example(directory):
    directory.mkdir(parents=True, exist_ok=False)
    data = pa.table(
        {
            "snapshot_id": ["synthetic-snapshot-1"] * 3,
            "ocid": ["synthetic-001", "synthetic-002", "synthetic-003"],
            "award_id": ["award-1"] * 3,
            "currency": ["USD", "USD", "EUR"],
            "amount": pa.array(
                [Decimal("10.25"), Decimal("20.50"), Decimal("7.00")], type=pa.decimal128(18, 2)
            ),
        }
    )
    input_path = directory / "awards.arrow"
    with input_path.open("xb") as stream, pa.ipc.new_file(stream, data.schema) as writer:
        writer.write_table(data)
    raw = input_path.read_bytes()
    reference = ef.ArtifactRef(
        schema_version="1.0",
        uri=input_path.resolve().as_uri(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    domain = contract()
    manifest = eb.SnapshotManifest(
        snapshot_id="synthetic-snapshot-1",
        domain_schema_revision="synthetic-awards.1",
        extraction_revision="synthetic-fixture.1",
        provenance=("synthetic manual fixture",),
        tables=(
            eb.SnapshotTable(
                name="awards",
                artifact=reference,
                row_count=3,
                columns=tuple(
                    eb.SnapshotColumn(
                        name=spec.name,
                        physical_type=str(data.schema.field(spec.name).type),
                        logical_type=spec.logical_type,
                        nullable=spec.nullable,
                    )
                    for spec in domain.inputs[0].schema_spec.columns
                ),
            ),
        ),
    )
    profile = ef.ProfileSpec(
        family="aggregations",
        features=(
            ef.ProfileFeature(name="rows", metric="log_filas", table="totals"),
            ef.ProfileFeature(
                name="output_input",
                metric="razon_salida_entrada",
                table="totals",
                denominator_table="awards",
            ),
        ),
    )
    spec = eb.IntegrationSpec(
        pipelines=tuple(
            ef.PipelineSpec(
                execution=ef.ExecutionPlan(
                    contract=domain,
                    engine=engine,
                    transformation_id="currency_totals",
                ),
                profile=profile,
            )
            for engine in ("pandas", "polars", "duckdb")
        ),
        domain_schema_revision=manifest.domain_schema_revision,
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            physical_types="lossless",
            justification="RangeIndex carries no award data; decimals and scale remain exact.",
        ),
    )
    # These literal totals are independent of the three native computations.
    expected = pa.table(
        {
            "currency": ["EUR", "USD"],
            "total": pa.array([Decimal("7.00"), Decimal("30.75")], type=pa.decimal128(38, 2)),
        }
    )
    source = eb.SnapshotDataSource(manifest.snapshot_id, client=LocalExampleClient(manifest))
    result = eb.run_integration(
        spec,
        source=source,
        registry=registry_factory(),
        expected=ef.ArrowInput(expected),
        work_dir=directory,
    )
    assert result.inputs_verified and result.complete and result.exit_code == 0
    assert len(result.comparisons) == 6
    assert all(
        item.result.complete and item.result.state == "equivalent" for item in result.comparisons
    )
    for run in result.runs:
        output = ef.read_table(run.result.execution.output.data)
        assert output.schema.field("total").type == pa.decimal128(38, 2)
        assert sorted((row["currency"], row["total"]) for row in output.to_pylist()) == [
            ("EUR", Decimal("7.00")),
            ("USD", Decimal("30.75")),
        ]
        assert run.result.rules.decision == "no_alert" and run.result.rules.complete
        assert len(run.result.rules.rules) == 3
        assert all(check.state == "satisfied" for check in run.result.rules.rules)
    assert eb.read_integration(directory / result.integration_id) == result
    return {
        "synthetic": True,
        "real_dw_acceptance": False,
        "inputs_verified": result.inputs_verified,
        "complete": result.complete,
        "integration_id": result.integration_id,
        "exit_code": result.exit_code,
        "expected_totals": {"USD": "30.75", "EUR": "7.00"},
        "R": {
            run.engine: {
                "decision": run.result.rules.decision,
                "complete": run.result.rules.complete,
            }
            for run in result.runs
        },
        "comparisons": len(result.comparisons),
        "evidence_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.output is not None:
        summary = run_example(arguments.output)
    else:
        with tempfile.TemporaryDirectory(prefix="equiframe-integration-example-") as temporary:
            summary = run_example(Path(temporary) / "evidence")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
