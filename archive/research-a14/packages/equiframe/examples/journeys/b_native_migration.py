"""B: real pandas and DuckDB compilation, one input capture, independent expected."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, column, comparison_record, new_output, write_summary
else:
    from common import cli, column, comparison_record, new_output, write_summary


class CountedSource:
    """Observe actual source resolution without changing the production source port."""

    def __init__(self, source: ef.LocalDataSource) -> None:
        self.source = source
        self.calls = 0

    @property
    def table_names(self) -> tuple[str, ...]:
        return self.source.table_names

    def resolve(self, name: str, *, context: ef.RunContext) -> ef.LoadedTable:
        self.calls += 1
        return self.source.resolve(name, context=context)


def configuration(scenario: str) -> ef.MigrationSpec:
    currency = column("currency", ef.StringType())
    amount = column(
        "amount", ef.DecimalType(precision=18, scale=2), nullable=True, unit="currency_amount"
    )
    total = column(
        "total", ef.DecimalType(precision=20, scale=2), nullable=True, unit="currency_amount"
    )
    output_schema = ef.keyed_contract(
        (currency, total), keys=["currency"]
    ).spec.contract.output.schema_spec
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="journey.B.native-totals",
        revision=1,
        family="aggregations",
        inputs=(
            ef.TableSpec(
                name="sales",
                schema_spec=ef.bag_contract((currency, amount)).spec.contract.output.schema_spec,
            ),
        ),
        output=ef.TableSpec(name="result", schema_spec=output_schema),
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
    return ef.MigrationSpec(
        contract=contract,
        source_engine="pandas",
        target_engine="duckdb",
        ir=ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="source", table="sales"),
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
                    ),
                    null_groups="retain",
                    empty_sum="zero" if scenario == "different" else "null",
                ),
            ),
            output="totals",
        ),
        comparison_policy=ef.ComparisonPolicy(
            index="ignore", justification="Native generated RangeIndex is not row identity."
        ),
        comparison_options=ef.ComparisonOptions(max_rows=1 if scenario == "not_evaluable" else 100),
        execution_options=ef.ExecutionOptions(
            duckdb_threads=1, duckdb_timezone="UTC", max_input_rows=100, max_output_rows=100
        ),
    )


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    import pyarrow as pa

    private = new_output(output, scenario)
    source = CountedSource(
        ef.LocalDataSource(
            {
                "sales": ef.ArrowInput(
                    pa.table(
                        {
                            "currency": ["USD", "USD", "EUR", "EUR"],
                            "amount": pa.array(
                                [Decimal("1.10"), Decimal("2.20"), None, None],
                                type=pa.decimal128(18, 2),
                            ),
                        }
                    )
                )
            }
        )
    )
    # This literal is independent of both native implementations and their IR.
    expected = pa.table(
        {
            "currency": ["USD", "EUR"],
            "total": pa.array([Decimal("3.30"), None], type=pa.decimal128(20, 2)),
        }
    )
    spec = configuration(scenario)
    checks = ef.check_migration(spec)
    if source.calls != 0 or not all(check.supported for check in checks):
        raise RuntimeError("Preflight unexpectedly read input or refused the documented plan")
    result = ef.migrate(spec, source=source, expected=ef.ArrowInput(expected), work_dir=private)
    if ef.read_migration(private / result.migration_id) != result:
        raise RuntimeError("Migration readback failed")
    comparisons = {}
    for label, comparison in (
        ("peers", result.comparison),
        ("pandas-expected", result.verification_source),
        ("duckdb-expected", result.verification_target),
    ):
        if comparison is not None:
            comparisons[label] = comparison_record(comparison, output, label)
    executions = [
        pipeline.execution
        for pipeline in (result.source, result.target)
        if pipeline is not None and pipeline.execution is not None
    ]
    same_input = (
        len(executions) == 2
        and executions[0].inputs[0].data.sha256 == executions[1].inputs[0].data.sha256
    )
    accepted = result.exit_code == 0 and source.calls == 1 and same_input
    return write_summary(
        output,
        {
            "journey": "B",
            "synthetic": True,
            "scenario": scenario,
            "preflight": [check.model_dump(mode="json") for check in checks],
            "source_resolutions": source.calls,
            "same_input_sha256": same_input,
            "native_engines": [execution.plan.engine for execution in executions],
            "execution_states": [execution.state for execution in executions],
            "state": result.state,
            "verification": result.verification,
            "complete": result.complete,
            "accepted": accepted,
            "exit_code": result.exit_code if not (result.exit_code == 0 and not accepted) else 3,
            "comparisons": comparisons,
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "B"))
