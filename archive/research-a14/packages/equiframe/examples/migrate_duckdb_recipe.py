"""Offline, synthetic pandas -> DuckDB migration over a bounded declared IR.

Requires Python 3.12 and an identified EquiFrame wheel with pandas and duckdb
extras (both include Arrow). Copy this script anywhere; it uses only public API.
No external data, downloads, credentials, shared database or Polars are needed.

Run: python migrate_duckdb_recipe.py --output migration-report
Cases: equivalent exits 0; different exits 1; not_evaluable exits 3. Setup,
invalid input, integrity or publication errors exit 2 and never imply success.
The deliberate different case changes the IR's NULL-only sum to zero: both
engines agree, but both differ from the unchanged literal expected. The
not_evaluable case imposes a one-row comparison budget, not a simulated result.

--output must be new and holds only redacted comparison reports. Raw captures,
both native outputs and the expected are kept in a private temporary directory
until verification/reporting finishes, then deleted. --work-dir deliberately
retains that evidence separately; never upload it as a redacted report. Each
DuckDB execution owns an in-memory session, configured below, materializes its
output and closes the connection before returning. No live relation escapes.
--show-synthetic-values opts into printing this fixture's expected and outputs;
do not keep that option when adapting this recipe to private data.

This demonstrates automatic comparison only, not human acceptance, independent
review, scientific evidence, arbitrary Python translation or general SQL support.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from typing import Literal

import equiframe as ef

Scenario = Literal["equivalent", "different", "not_evaluable"]
REPORT_FILES = frozenset({"report.json", "report.html", "report.txt", "evidence-manifest.json"})
COMPARISONS = ("source-target", "source-expected", "target-expected")


class RecipeError(RuntimeError):
    """A safe failure message without raw data, paths or exception details."""


def configuration(scenario: Scenario = "equivalent") -> ef.MigrationSpec:
    """Declare exact money, group identity, NULL semantics and bounded resources."""
    if scenario not in ("equivalent", "different", "not_evaluable"):
        raise RecipeError("Unsupported synthetic case")
    nulls = ef.NullPolicy(representations=("null",))
    currency = ef.ColumnSpec(
        name="currency", logical_type=ef.StringType(), nullable=False, null_policy=nulls
    )
    amount = ef.ColumnSpec(
        name="amount",
        logical_type=ef.DecimalType(precision=18, scale=2),
        nullable=True,
        null_policy=nulls,
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_amount"),
    )
    total = amount.model_copy(
        update={"name": "total", "logical_type": ef.DecimalType(precision=20, scale=2)}
    )
    rows = ef.ColumnSpec(
        name="rows",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=nulls,
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="rows"),
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="recipe.synthetic.money",
        revision=1,
        family="aggregations",
        inputs=(
            ef.TableSpec(
                name="orders",
                schema_spec=ef.TableSchema(
                    columns=(currency, amount),
                    keys=(),
                    multiplicity="preserve",
                    order=ef.IgnoredOrder(),
                ),
            ),
        ),
        output=ef.TableSpec(
            name="result",
            schema_spec=ef.TableSchema(
                columns=(currency, total, rows),
                keys=(
                    ef.KeySpec(
                        name="currency_key",
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
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="output_schema",
                revision=1,
                severity="error",
                required=True,
                specification=ef.SchemaCheck(table="result"),
            ),
        ),
    )
    return ef.MigrationSpec(
        contract=contract,
        source_engine="pandas",
        target_engine="duckdb",
        ir=ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="source", table="orders"),
                ef.Aggregate(
                    node_id="totals",
                    source="source",
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
                    empty_sum="zero" if scenario == "different" else "null",
                ),
            ),
            output="totals",
        ),
        require_rules=True,
        comparison_policy=ef.ComparisonPolicy(
            index="ignore", justification="Generated RangeIndex has no business identity."
        ),
        execution_options=ef.ExecutionOptions(
            timeout_seconds=30.0,
            max_input_rows=100,
            max_output_rows=100,
            max_transport_bytes=1024 * 1024,
            duckdb_memory_mb=128,
            duckdb_threads=1,
            duckdb_timezone="UTC",
        ),
        comparison_options=ef.ComparisonOptions(
            max_rows=1 if scenario == "not_evaluable" else 100,
            max_examples=2,
            timeout_seconds=30.0,
        ),
        options=ef.MigrationOptions(
            timeout_seconds=120.0, max_capture_rows=100, max_capture_bytes=1024 * 1024
        ),
    )


def fixture() -> tuple[object, object]:
    """Literal expected authored separately, never computed from an engine output."""
    import pyarrow as pa

    # A large exact cent amount, repeated rows, missing amounts, and genuine zero.
    source = pa.table(
        {
            "currency": ["USD", "USD", "USD", "EUR", "EUR", "JPY"],
            "amount": pa.array(
                [
                    Decimal("1000000000000000.01"),
                    Decimal("0.02"),
                    None,
                    None,
                    None,
                    Decimal("0.00"),
                ],
                type=pa.decimal128(18, 2),
            ),
        }
    )
    expected = pa.table(
        {
            "currency": ["EUR", "JPY", "USD"],
            "total": pa.array(
                [None, Decimal("0.00"), Decimal("1000000000000000.03")],
                type=pa.decimal128(20, 2),
            ),
            "rows": pa.array([2, 1, 3], type=pa.int64()),
        }
    )
    return source, expected


def execute_migration(work_dir: Path, scenario: Scenario) -> ef.MigrationResult:
    """Materialize both native results against one fixed input and one expected."""
    source, expected = fixture()
    return ef.migrate(
        configuration(scenario),
        source=ef.LocalDataSource({"orders": ef.ArrowInput(source)}),
        expected=ef.ArrowInput(expected),
        work_dir=work_dir,
    )


def verify_report(directory: Path) -> None:
    """Check the allowlisted redacted publication without opening raw evidence."""
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != REPORT_FILES:
        raise RecipeError("Report inventory is not the expected closed set")
    for name in REPORT_FILES:
        if (directory / name).is_symlink() or not (directory / name).is_file():
            raise RecipeError("Report inventory contains a non-file")
    manifest = ef.ReportPublicationManifest.model_validate_json(
        (directory / "evidence-manifest.json").read_bytes()
    )
    if {item.path for item in manifest.files} != REPORT_FILES - {"evidence-manifest.json"}:
        raise RecipeError("Report manifest does not match the expected inventory")
    for item in manifest.files:
        raw = (directory / item.path).read_bytes()
        if len(raw) != item.size_bytes or hashlib.sha256(raw).hexdigest() != item.sha256:
            raise RecipeError("Report integrity check failed")
    report = ef.read_comparison_report(directory / "report.json")
    if (
        report.options.mode != "diagnostic"
        or report.options.include_values
        or report.options.include_metadata
        or not report.evidence.values_withheld
        or not report.evidence.metadata_withheld
        or report.evidence.reproduction != "not_requested"
        or manifest.report_evidence != report.evidence
    ):
        raise RecipeError("Report is not a redacted publication")


def show_synthetic_outputs(result: ef.MigrationResult) -> None:
    """Opt-in disclosure, while the captured expected and both outputs still exist."""
    print("Synthetic fixture values explicitly requested; no human acceptance is claimed.")
    references = [("literal expected", result.expected)]
    for label, pipeline in (
        ("pandas reference", result.source),
        ("DuckDB candidate", result.target),
    ):
        output = (
            pipeline.execution.output
            if pipeline is not None and pipeline.execution is not None
            else None
        )
        references.append((label, output.data if output else None))
    for label, reference in references:
        if reference is None:
            print(label + ": unavailable")
            continue
        # These are persisted materialized captures, never a query on a closed session.
        rows = sorted(ef.read_table(reference).to_pylist(), key=lambda row: row["currency"])
        print(label + ": " + repr(rows))


def run_recipe(
    report_dir: Path,
    *,
    scenario: Scenario = "equivalent",
    work_dir: Path | None = None,
    show_values: bool = False,
) -> int:
    """Keep raw artifacts alive through integrity checking and report publication."""
    result = None
    try:
        # A fresh output prevents mixing redacted reports with existing private files.
        for ancestor in (report_dir, *report_dir.parents):
            if ancestor.is_symlink():
                raise RecipeError("Report destination must not contain symlinks")
        if report_dir.exists():
            raise RecipeError("Select a new report directory; existing output is never overwritten")
        private_context = (
            tempfile.TemporaryDirectory(prefix="equiframe-migration-private-")
            if work_dir is None
            else nullcontext(str(work_dir))
        )
        with private_context as private:
            private_root = Path(private)
            upload, raw = report_dir.resolve(), private_root.resolve()
            if upload == raw or upload in raw.parents or raw in upload.parents:
                raise RecipeError("Report and private evidence directories must be separate")
            result = execute_migration(private_root, scenario)
            # Reopens and verifies inventories, inputs and both outputs after the
            # adapter's DuckDB session has closed. This does not reexecute the IR.
            if ef.read_migration(private_root / result.migration_id) != result:
                raise RecipeError("Migration readback does not match its result")
            print("Synthetic pandas -> DuckDB; exact Decimal, NULLs and multiplicity declared.")
            print(
                f"Between engines: {result.state}; "
                f"against literal expected: {result.verification}; "
                f"complete={result.complete}; gate={result.exit_code}"
            )
            comparisons = (
                result.comparison,
                result.verification_source,
                result.verification_target,
            )
            if any(comparison is None for comparison in comparisons):
                # Invalid/missing dependencies can end before comparisons exist.
                print("No complete report set: migration stopped before all comparisons existed.")
                for stage in result.stages:
                    if stage.state != "completed":
                        print(f"  {stage.stage}: {stage.state} ({stage.code})")
                if any(stage.code == "missing_dependency" for stage in result.stages):
                    print("Check the installed wheel's pandas and duckdb extras.")
                return result.exit_code
            report_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            for label, comparison in zip(COMPARISONS, comparisons, strict=True):
                report = ef.write_comparison_report(
                    comparison,
                    report_dir / label,
                    evidence_root=private_root / result.migration_id,
                    options=ef.ReportOptions(include_values=False, include_metadata=False),
                )
                verify_report(report_dir / label)
                counts = {count.name: count for count in report.counts}
                differences = counts["difference_records"]
                print(
                    f"{label}: {report.state}; complete={report.complete}; "
                    f"difference records={differences.value} ({differences.precision})"
                )
                for reason in report.reasons:
                    print("  " + reason)
            if {path.name for path in report_dir.iterdir()} != set(COMPARISONS):
                raise RecipeError("Report bundle contains unexpected files")
            if show_values:
                show_synthetic_outputs(result)
            if result.verification == "divergent" and result.state == "equivalent":
                print("Both engines share the declared empty-sum error: NULL became zero.")
            if result.exit_code == 3:
                print("Not evaluable is a failing gate; observed agreement is not acceptance.")
            print(
                "Redacted reports verified; no independent review or human acceptance established."
            )
            print("Report directory: " + json.dumps(str(report_dir)[:512], ensure_ascii=True))
        # Only claim deletion after the context has closed successfully.
        print(
            "Raw evidence was temporary and has been removed."
            if work_dir is None
            else "Raw evidence retained separately by --work-dir; do not upload it."
        )
        return result.exit_code
    except RecipeError:
        raise
    except Exception:
        state = result.state if result is not None else "unavailable"
        raise RecipeError(
            "Recipe setup, execution, integrity, publication or cleanup failed; "
            f"comparison state={state}. No successful recipe gate; do not upload partial output"
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        dest="scenario",
        choices=("equivalent", "different", "not_evaluable"),
        default="equivalent",
    )
    parser.add_argument("--output", type=Path, default=Path("migration-report"))
    parser.add_argument(
        "--work-dir", type=Path, help="Retain private migration evidence separately"
    )
    parser.add_argument("--show-synthetic-values", action="store_true")
    args = parser.parse_args()
    try:
        return run_recipe(
            args.output,
            scenario=args.scenario,
            work_dir=args.work_dir,
            show_values=args.show_synthetic_values,
        )
    except RecipeError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
