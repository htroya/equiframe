"""Migrate one declared ETL over all six native directions; synthetic inputs only."""

import argparse
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def configuration(source: str, target: str) -> ef.MigrationSpec:
    nulls = ef.NullPolicy(representations=("null",))
    currency = ef.ColumnSpec(
        name="currency",
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=nulls,
    )
    amount = ef.ColumnSpec(
        name="amount",
        logical_type=ef.DecimalType(precision=18, scale=2),
        nullable=True,
        null_policy=nulls,
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="currency_amount"),
    )
    total = amount.model_copy(
        update={
            "name": "total",
            "logical_type": ef.DecimalType(precision=20, scale=2),
        }
    )
    count = ef.ColumnSpec(
        name="rows",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=nulls,
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="rows"),
    )

    def schema(columns: tuple[ef.ColumnSpec, ...]) -> ef.TableSchema:
        return ef.TableSchema(
            columns=columns,
            keys=(),
            multiplicity="preserve",
            order=ef.IgnoredOrder(),
        )

    contract = ef.Contract(
        schema_version="1.0",
        contract_id="migration.synthetic.money",
        revision=1,
        family="aggregations",
        inputs=(
            ef.TableSpec(
                name="orders",
                schema_spec=schema((currency, amount)),
            ),
        ),
        output=ef.TableSpec(name="result", schema_spec=schema((currency, total, count))),
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
        source_engine=source,
        target_engine=target,
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
                    empty_sum="null",
                ),
            ),
            output="totals",
        ),
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            justification="Generated RangeIndex has no business identity.",
        ),
        options=ef.MigrationOptions(timeout_seconds=120.0, max_capture_rows=100),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("migration-runs"))
    args = parser.parse_args()
    inputs = pa.table(
        {
            "currency": ["USD", "USD", "EUR", "EUR"],
            "amount": pa.array(
                [Decimal("1.20"), Decimal("2.30"), None, None], type=pa.decimal128(18, 2)
            ),
        }
    )
    # This literal expected is independent of every compiler and native execution.
    expected = pa.table(
        {
            "currency": ["USD", "EUR"],
            "total": pa.array([Decimal("3.50"), None], type=pa.decimal128(20, 2)),
            "rows": pa.array([2, 2], type=pa.int64()),
        }
    )
    for source, target in permutations(("pandas", "polars", "duckdb"), 2):
        result = ef.migrate(
            configuration(source, target),
            source=ef.LocalDataSource({"orders": ef.ArrowInput(inputs)}),
            expected=ef.ArrowInput(expected),
            work_dir=args.output,
        )
        assert result.complete and result.exit_code == 0, ef.migration_summary(result)
        assert result.state == "equivalent" and result.verification == "correct"
        assert ef.read_migration(args.output / result.migration_id) == result
        print(source, "to", target, result.state, "supplied expected:", result.verification)
    print("Six actual native migrations verified; synthetic data are not thesis results.")


if __name__ == "__main__":
    main()
