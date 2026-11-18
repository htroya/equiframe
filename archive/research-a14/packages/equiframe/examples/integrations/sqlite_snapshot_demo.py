"""Run a synthetic SQLite -> pinned snapshot -> native DuckDB -> comparison gate."""

from __future__ import annotations

import argparse
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pyarrow as pa
from sqlite_snapshot import SQLiteQuery, SQLiteSnapshotClient, capture_sqlite_snapshot

import equiframe as ef


def declarations() -> tuple[SQLiteQuery, ...]:
    return (
        SQLiteQuery(
            "accounts",
            "SELECT account_id, label FROM accounts ORDER BY account_id",
            pa.schema(
                [pa.field("account_id", pa.int64(), nullable=False), pa.field("label", pa.string())]
            ),
        ),
        SQLiteQuery(
            "entries",
            "SELECT id, account_id, amount, currency FROM entries WHERE cohort = ? ORDER BY id",
            pa.schema(
                [
                    pa.field("id", pa.string(), nullable=False),
                    pa.field("account_id", pa.int64(), nullable=False),
                    pa.field("amount", pa.decimal128(10, 2)),
                    pa.field("currency", pa.string(), nullable=False),
                ]
            ),
            parameters=("synthetic",),
        ),
    )


def create_synthetic_database(database: Path, *, discrepant: bool) -> None:
    """Write only this demo's new synthetic database; never reuse an existing one."""
    with database.open("xb"):
        pass
    connection = sqlite3.connect(database)
    try:
        with connection:
            connection.execute("CREATE TABLE accounts (account_id INTEGER, label TEXT)")
            # TEXT affinity is intentional: SQLite REAL would lose decimal meaning.
            connection.execute(
                "CREATE TABLE entries "
                "(id TEXT, account_id INTEGER, amount TEXT, currency TEXT, cohort TEXT)"
            )
            connection.executemany("INSERT INTO accounts VALUES (?, ?)", [(1, "Café"), (2, None)])
            connection.executemany(
                "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
                [
                    ("A", 1, "1.11" if discrepant else "1.10", "USD", "synthetic"),
                    ("B", 1, None, "USD", "synthetic"),
                    ("C", 2, "-0.01", "EUR", "synthetic"),
                    ("excluded", 2, "99.99", "EUR", "other"),
                ],
            )
    finally:
        connection.close()


def expected_output() -> pa.Table:
    """Literal expectation authored separately; no query/source output is its oracle."""
    return pa.table(
        {
            "id": pa.array(["A", "B", "C"], pa.string()),
            "label": pa.array(["Café", "Café", None], pa.string()),
            "amount": pa.array([Decimal("1.10"), None, Decimal("-0.01")], pa.decimal128(10, 2)),
            "currency": pa.array(["USD", "USD", "EUR"], pa.string()),
        }
    )


def contract_for(manifest: ef.SnapshotManifest) -> ef.Contract:
    def schema(columns: tuple[ef.SnapshotColumn, ...]) -> ef.TableSchema:
        declarations = tuple(
            ef.ColumnSpec(
                name=column.name,
                logical_type=column.logical_type,
                nullable=column.nullable,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=(
                    ef.NumericPolicy(
                        comparison="exact",
                        unit=(
                            "currency_units"
                            if isinstance(column.logical_type, ef.DecimalType)
                            else "identifier"
                        ),
                    )
                    if isinstance(column.logical_type, (ef.DecimalType, ef.IntegerType))
                    else None
                ),
            )
            for column in columns
        )
        return ef.bag_contract(declarations).spec.contract.output.schema_spec

    output_columns = (
        manifest.tables[1].columns[0],
        manifest.tables[0].columns[1],
        *manifest.tables[1].columns[2:],
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="sqlite.synthetic.join",
        revision=1,
        family="joins",
        inputs=tuple(
            ef.TableSpec(name=table.name, schema_spec=schema(table.columns))
            for table in manifest.tables
        ),
        output=ef.TableSpec(name="result", schema_spec=schema(output_columns)),
        preconditions=(),
        rules=(),
    )


class CorruptingTransport:
    """Synthetic functional failure: change one byte without changing its manifest."""

    def __init__(self, client: SQLiteSnapshotClient) -> None:
        self.client = client

    def get_snapshot(self, snapshot_id: str) -> ef.SnapshotManifest:
        return self.client.get_snapshot(snapshot_id)

    def download_artifact(self, ref: ef.ArtifactRef, destination: Path) -> None:
        self.client.download_artifact(ref, destination)
        with destination.open("r+b") as stream:
            first = stream.read(1)
            stream.seek(0)
            stream.write(bytes([first[0] ^ 1]))


def run_demo(output: Path, case: Literal["good", "different", "corrupt"]) -> int:
    """Exit 0 only for an equivalent capture; 1 difference, 3 failed/incomplete."""
    if case not in ("good", "different", "corrupt"):
        raise ValueError("unknown demonstration case")
    output.mkdir(parents=True, exist_ok=False)
    database = output / "synthetic.sqlite"
    create_synthetic_database(database, discrepant=case == "different")
    client = capture_sqlite_snapshot(
        database,
        snapshot_id="synthetic.sqlite.001",
        queries=declarations(),
        domain_schema_revision="synthetic.accounts.1",
        extraction_revision="sqlite.exact-text-decimal.1",
        provenance=(
            "Synthetic accounts and entries; no real service or DW acceptance",
            f"SQLite {sqlite3.sqlite_version}; one owned native read transaction",
        ),
    )
    source = ef.SnapshotDataSource(
        client.manifest.snapshot_id,
        client=CorruptingTransport(client) if case == "corrupt" else client,
        expected_domain_schema_revision="synthetic.accounts.1",
    )
    registry = ef.TransformationRegistry()
    registry.register(
        ef.DuckDBTransformation(
            "join",
            "SELECT e.id, a.label, e.amount, e.currency "
            "FROM entries e LEFT JOIN accounts a USING (account_id)",
            "sqlite-demo.join.1",
        )
    )
    contract = contract_for(source.manifest)
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract, engine="duckdb", transformation_id="join"),
        source=source,
        registry=registry,
        work_dir=output / "execution",
    )
    receipt = {
        "case": case,
        "snapshot_id": source.snapshot_id,
        "snapshot_manifest_sha256": ef.snapshot_fingerprint(source.manifest),
        "execution_state": execution.state,
        "comparison_state": "not_evaluable",
    }
    code = 3
    if execution.state == "completed":
        comparison = ef.compare(
            execution,
            ef.ArrowInput(expected_output()),
            contract=contract,
            reference="expected",
            work_dir=output / "comparison",
        )
        # Persist a redacted report BEFORE enforcing the gate.
        ef.write_comparison_report(comparison, output / "report")
        receipt["comparison_state"] = comparison.state
        try:
            ef.assert_equivalent(comparison)
        except ef.EquivalenceDifferentError:
            code = 1
        except ef.EquivalenceNotEvaluableError:
            code = 3
        else:
            code = 0
    with (output / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump({**receipt, "exit_code": code}, stream, indent=2)
        stream.write("\n")
    print(f"execution={execution.state}; comparison={receipt['comparison_state']}; exit={code}")
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=("good", "different", "corrupt"), default="good")
    args = parser.parse_args()
    raise SystemExit(run_demo(args.output, args.case))


if __name__ == "__main__":
    main()
