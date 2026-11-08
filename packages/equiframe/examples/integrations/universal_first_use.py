"""One exact contract, six input variants and three independent native engines.

All data and the injected API response are synthetic. No remote service, paid
resource, credentials, benchmark or GitHub Actions are required.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import equiframe as ef

INT = ef.IntegerType(bits=64, signed=True)
MONEY = ef.DecimalType(precision=12, scale=2)


def column(
    name: str, dtype: ef.LogicalType, *, nullable: bool = True, unit: str | None = None
) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=dtype,
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit=unit)
        if unit is not None
        else None,
    )


def declarations() -> tuple[ef.Contract, ef.RelationalPlan, ef.IngestionSpec]:
    columns = (
        column("id", ef.StringType(), nullable=False),
        column("sequence", INT, nullable=False, unit="sequence"),
        column("amount", MONEY, unit="USD"),
    )
    outputs = (
        *columns,
        column("position", INT, nullable=False, unit="rows"),
        column("previous_amount", MONEY, unit="USD"),
    )

    def table(name: str, fields: tuple[ef.ColumnSpec, ...]) -> ef.TableSpec:
        return ef.TableSpec(
            name=name,
            schema_spec=ef.TableSchema(
                columns=fields, keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
            ),
        )

    contract = ef.Contract(
        schema_version="1.0",
        contract_id="universal.synthetic",
        revision=1,
        family="nulls_types",
        inputs=(table("input", columns),),
        output=table("output", outputs),
        preconditions=(),
        rules=(),
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="s", table="input"),
            ef.Window(
                node_id="w",
                source="s",
                partition_by=("id",),
                by=(ef.SortKey(column="sequence", direction="ascending", nulls="last"),),
                measures=(
                    ef.WindowMeasure(
                        name="position", operation="row_number", logical_type=INT, unit="rows"
                    ),
                    ef.WindowMeasure(
                        name="previous_amount", operation="lag", column="amount", logical_type=MONEY
                    ),
                ),
            ),
        ),
        output="w",
    )
    spec = ef.IngestionSpec(
        format="jsonl",
        fields=tuple(ef.FieldMapping(column=field, path=(field.name,)) for field in columns),
    )
    return contract, plan, spec


def source_table() -> pa.Table:
    return pa.table(
        {
            "id": ["001", "001", "002", "001"],
            "sequence": [2, 1, 1, 3],
            "amount": pa.array(
                [None, Decimal("12.30"), Decimal("-0.01"), Decimal("2.00")],
                type=pa.decimal128(12, 2),
            ),
        }
    )


def expected_output() -> pa.Table:
    """Literal expected authored independently of source loading/native execution."""
    return pa.table(
        {
            "id": ["001", "001", "001", "002"],
            "sequence": [1, 2, 3, 1],
            "amount": pa.array(
                [Decimal("12.30"), None, Decimal("2.00"), Decimal("-0.01")],
                type=pa.decimal128(12, 2),
            ),
            "position": [1, 2, 3, 1],
            "previous_amount": pa.array(
                [None, Decimal("12.30"), None, None], type=pa.decimal128(12, 2)
            ),
        }
    )


def inputs(root: Path, spec: ef.IngestionSpec, case: str) -> dict[str, ef.DataSource]:
    root.mkdir(exist_ok=False)
    csv = root / "input.csv"
    csv.write_text(
        "id,sequence,amount\n001,2,NULL\n001,1,12.30\n002,1,-0.01\n001,3,2.00\n", encoding="utf-8"
    )
    csv_spec = ef.IngestionSpec(
        format="csv",
        fields=tuple(
            mapping.model_copy(update={"null_tokens": ("NULL",)})
            if mapping.column.nullable
            else mapping
            for mapping in spec.fields
        ),
    )
    database = root / "input.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE entries (id TEXT, sequence INTEGER, amount TEXT, cohort TEXT)")
        db.executemany(
            "INSERT INTO entries VALUES (?, ?, ?, ?)",
            [
                ("001", 2, None, "demo"),
                ("001", 1, "12.31" if case == "different" else "12.30", "demo"),
                ("002", 1, "-0.01", "demo"),
                ("001", 3, "2.00", "demo"),
                ("excluded", 1, "99.99", "other"),
            ],
        )
    records = [
        {"id": "001", "sequence": 2, "amount": None},
        {"id": "001", "sequence": 1, "amount": "12.30"},
        {"id": "002", "sequence": 1, "amount": "-0.01"},
        {"id": "001", "sequence": 3, "amount": "2.00"},
    ]
    json_path = root / "input.json"
    json_path.write_text(json.dumps({"records": records}), encoding="utf-8")
    json_spec = ef.IngestionSpec(format="json", records_path=("records", "*"), fields=spec.fields)
    response = ("\n".join(json.dumps(row) for row in records) + "\n").encode()
    response_sha = "0" * 64 if case == "corrupt" else hashlib.sha256(response).hexdigest()
    raw = source_table()
    parquet = root / "input.parquet"
    pq.write_table(raw, parquet)
    ref = ef.LocalArtifactStore(root / "artifacts").put(
        parquet, media_type="application/vnd.apache.parquet"
    )
    batch_input = ef.RecordBatchInput(
        lambda: closing(
            pa.RecordBatchReader.from_batches(raw.schema, raw.to_batches(max_chunksize=2))
        ),
        raw.schema,
    )
    items = {
        "csv": ef.FileInput(csv, csv_spec, batch_rows=2),
        "sqlite": ef.SQLiteInput(
            database,
            "SELECT id, sequence, amount FROM entries WHERE cohort = ?",
            spec,
            ("demo",),
            batch_rows=2,
        ),
        "json": ef.FileInput(json_path, json_spec),
        "api_response": ef.StreamInput(lambda: closing(io.BytesIO(response)), spec, response_sha),
        "parquet": ef.ArtifactInput(ref),
        "arrow_batches": batch_input,
    }
    return {
        name: ef.CompositeDataSource(
            {"input": (ef.LocalDataSource({"provider_table": item}), "provider_table")}
        )
        for name, item in items.items()
    }


def run_demo(output: Path, case: str = "good") -> int:
    if case not in ("good", "different", "corrupt"):
        raise ValueError("unknown synthetic case")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    contract, plan, spec = declarations()
    sources = inputs(output / "inputs", spec, case)
    receipts: list[dict[str, object]] = []
    exit_code = 0
    for engine in ("pandas", "polars", "duckdb"):
        compiled = ef.native_compiler_registry().resolve(engine).compile(plan, contract)
        registry = ef.TransformationRegistry()
        registry.register(compiled.transformation)
        for name, source in sources.items():
            directory = output / engine / name
            execution = ef.execute(
                ef.ExecutionPlan(
                    contract=contract,
                    engine=engine,
                    transformation_id=compiled.transformation.transformation_id,
                    options=ef.ExecutionOptions(
                        max_input_rows=100,
                        max_output_rows=100,
                        max_transport_bytes=1_000_000,
                        timeout_seconds=30,
                    ),
                ),
                source=source,
                registry=registry,
                work_dir=directory / "execution",
            )
            receipt: dict[str, object] = {
                "engine": engine,
                "source": name,
                "execution_state": execution.state,
                "comparison_state": None,
                "problem": execution.problem.model_dump(mode="json") if execution.problem else None,
            }
            if execution.state != "completed":
                exit_code = 3
            else:
                comparison = ef.compare(
                    execution,
                    ef.ArrowInput(expected_output()),
                    contract=contract,
                    reference="expected",
                    work_dir=directory / "comparison",
                    policy=ef.ComparisonPolicy(
                        index="ignore",
                        justification=(
                            "This declared relational bag has no native index identity."
                        ),
                    ),
                )
                ef.write_comparison_report(comparison, directory / "report")
                receipt["comparison_state"] = comparison.state
                receipt["comparison_complete"] = comparison.complete
                try:
                    ef.assert_equivalent(comparison)
                except ef.EquivalenceDifferentError:
                    exit_code = max(exit_code, 1)
                except ef.EquivalenceNotEvaluableError:
                    exit_code = 3
            receipts.append(receipt)
            print(
                f"{engine}/{name}: execution={execution.state}; "
                f"comparison={receipt['comparison_state']}"
            )
    (output / "receipt.json").write_text(
        json.dumps(
            {
                "equiframe": ef.__version__,
                "synthetic": True,
                "case": case,
                "exit_code": exit_code,
                "runs": receipts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=("good", "different", "corrupt"), default="good")
    args = parser.parse_args()
    raise SystemExit(run_demo(args.output, args.case))


if __name__ == "__main__":
    main()
