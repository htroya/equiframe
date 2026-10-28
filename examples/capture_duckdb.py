"""Capture once, change the source, then compare and report without DuckDB replay.

Synthetic, offline fixture: exact Decimal money, NULL, Unicode, an empty string
and duplicate rows. Requires the installed EquiFrame candidate with its duckdb
extra. Copy this file anywhere; no checkout paths or external data are needed.
Raw captures are temporary and deleted at exit. Optional --output retains only
a redacted report in a new directory, never the captured data or SQL.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import equiframe as ef

if TYPE_CHECKING:
    import pyarrow as pa


def declaration() -> ef.DiffContract:
    """Declare exact USD amounts and preserve duplicates; row order is irrelevant."""
    return ef.bag_contract(
        (
            ef.ColumnSpec(
                name="label",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            ef.ColumnSpec(
                name="amount",
                logical_type=ef.DecimalType(precision=12, scale=2),
                nullable=True,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
            ),
        ),
        multiplicity="preserve",
        reference="expected",
        contract_id="recipe.duckdb_capture.bag",
        revision=1,
    )


def independent_expected() -> pa.Table:
    """Literal expected values, not a conversion or rerun of DuckDB's output."""
    import pyarrow as pa

    # A different order also checks the declared bag semantics. Both identical
    # cafe rows are required: deduplicating either side must not pass this case.
    return pa.table(
        {
            "label": pa.array(["niño", "café", "空", "", "café"], type=pa.string()),
            "amount": pa.array(
                [Decimal("3.15"), Decimal("20.20"), None, Decimal("0.00"), Decimal("20.20")],
                type=pa.decimal128(12, 2),
            ),
        }
    )


def run_example(output: Path | None = None) -> ef.ComparisonReport:
    """Return a detached report; only --output retains the redacted publication."""
    import duckdb

    if output is not None and output.exists():
        raise ValueError("Choose a new report directory; existing evidence is not overwritten")
    contract = declaration()
    expected = independent_expected()
    with tempfile.TemporaryDirectory(prefix="equiframe-duckdb-private-") as temporary:
        private = Path(temporary)
        # The caller owns this connection and its settings. Capture borrows it
        # exclusively, with no outstanding reader or concurrent source changes.
        with duckdb.connect(
            ":memory:",
            config={
                "autoinstall_known_extensions": False,
                "autoload_known_extensions": False,
                "enable_external_access": False,
                "python_enable_replacements": False,
            },
        ) as connection:
            connection.execute(
                "CREATE TABLE sales (label VARCHAR, unit_price DECIMAL(12, 2), quantity INTEGER)"
            ).fetchall()
            connection.execute(
                "INSERT INTO sales VALUES ('café', 10.10, 2), ('空', NULL, 1), "
                "('café', 10.10, 2), ('', 0.00, 3), ('niño', 1.05, 3)"
            ).fetchall()
            captured = ef.capture_duckdb(
                "SELECT label, CAST(unit_price * quantity AS DECIMAL(12, 2)) AS amount "
                "FROM sales WHERE quantity >= $minimum",
                connection=connection,
                exclusive_connection=True,
                parameters={"minimum": 1},
                work_dir=private / "captures",
                options=ef.DuckDBCaptureOptions(
                    batch_rows=2,
                    max_rows=5,
                    max_batch_bytes=4096,
                    max_bytes=64 * 1024,
                    timeout_seconds=30.0,
                ),
            )
            assert captured.row_count == 5
            # This is caller SQL AFTER capture has fully finished. A replay of
            # the original query would now produce different amounts.
            connection.execute("UPDATE sales SET unit_price = 999.99").fetchall()
            connection.execute("DROP TABLE sales").fetchall()
        # The in-memory source no longer exists and the connection is closed.
        # Every operation below accepts captured evidence, not SQL/a relation.
        result = ef.diff(captured, expected, contract=contract, work_dir=private / "comparisons")
        report_directory = output if output is not None else private / "report"
        report = ef.write_comparison_report(
            result,
            report_directory,
            evidence_root=private,
            declaration=ef.read_diff_contract(result),
            options=ef.ReportOptions(
                mode="detail",
                include_values=False,
                include_metadata=False,
                require_exhaustive=True,
            ),
        )
        ef.assert_equivalent(
            result,
            policy=ef.EquivalencePolicy(require_persisted_evidence=True),
            evidence_root=private,
        )
        assert result.state == "equivalent" and result.complete
        assert report.evidence.values_withheld and report.evidence.metadata_withheld
        assert ef.read_comparison_report(report_directory / "report.json") == report
    # All raw evidence has now been deleted. Rendering this report remains safe
    # and requires neither a source connection nor the temporary snapshot files.
    assert "equivalent" in report.to_text()
    assert "<html" in report.to_html()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Retain a redacted report in a NEW directory")
    args = parser.parse_args()
    try:
        report = run_example(args.output)
    except ef.EquivalenceAssertionError as error:
        print(str(error), file=sys.stderr)
        return 3
    except Exception:
        print(
            "Capture example failed; no equivalence was established. Check the installed "
            "duckdb extra and choose a new, writable report directory.",
            file=sys.stderr,
        )
        return 2
    print(report.to_text())
    print("5 rows verified after source mutation and connection close; no SQL replay.")
    print("Raw snapshots deleted; report values and metadata withheld.")
    if args.output is not None:
        print("Redacted report:", args.output / "report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
