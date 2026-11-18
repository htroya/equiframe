"""E: timezone-aware nanoseconds, NULL/NaN, duplicates and sequence semantics."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, column, comparison_record, new_output, write_summary
else:
    from common import cli, column, comparison_record, new_output, write_summary

SCENARIOS = ("good", "different", "not_evaluable", "null_nan", "duplicate_loss")


def declaration() -> ef.DiffContract:
    return ef.sequence_contract(
        (
            column("sensor", ef.StringType()),
            column("at", ef.TimestampType(unit="ns", timezone="UTC"), nullable=True),
            column("reading", ef.FloatType(bits=64), nullable=True, unit="degrees_C"),
        ),
        by=(ef.SortSpec(column="at", direction="ascending", nulls="last"),),
        ties="preserve",
        contract_id="journey.E.telemetry",
        policy=ef.ComparisonPolicy(
            physical_types="lossless",
            justification="Zones may encode the same instant; retain nanoseconds exactly.",
        ),
    )


def fixture(scenario: str) -> tuple[pa.Table, pa.Table]:
    import pyarrow as pa

    expected = pa.table(
        {
            "sensor": ["s1", "s1", "s1", "s2"],
            "at": pa.array(
                [1704067200000000001, 1704067200000000001, 1704067201000000002, None],
                type=pa.timestamp("ns", tz="UTC"),
            ),
            "reading": pa.array(
                [1.5, 1.5, float("nan"), None], type=pa.float64(), from_pandas=False
            ),
        }
    )
    candidate = pa.table(
        {
            "sensor": ["s1", "s1", "s1", "s2"],
            "at": pa.array(
                [1704067200000000001, 1704067200000000001, 1704067201000000002, None],
                type=pa.timestamp("ns", tz="America/Guayaquil"),
            ),
            "reading": pa.array(
                [
                    1.5,
                    1.5,
                    None if scenario == "null_nan" else float("nan"),
                    float("nan") if scenario == "null_nan" else None,
                ],
                type=pa.float64(),
                from_pandas=False,
            ),
        }
    )
    if scenario == "different":
        candidate = candidate.take([2, 0, 1, 3])
    elif scenario == "duplicate_loss":
        candidate = candidate.take([0, 2, 3])
    return candidate, expected


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    private = new_output(output, scenario, SCENARIOS)
    candidate, expected = fixture(scenario)
    declared = declaration()
    result = ef.diff(
        candidate,
        expected,
        contract=declared,
        options=ef.ComparisonOptions(max_rows=1 if scenario == "not_evaluable" else 100),
        work_dir=private,
    )
    # This Scan has no final Sort matching the significant-order contract.
    schema = declared.spec.contract.output.schema_spec
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="journey.E.migration-limit",
        revision=1,
        family="dates",
        inputs=(ef.TableSpec(name="telemetry", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    checks = ef.check_migration(
        ef.MigrationSpec(
            contract=contract,
            source_engine="pandas",
            target_engine="duckdb",
            ir=ef.RelationalPlan(
                nodes=(ef.Scan(node_id="scan", table="telemetry"),), output="scan"
            ),
            require_rules=False,
        )
    )
    if any(check.supported for check in checks):
        raise RuntimeError(
            "Review the matching-final-Sort preflight contract before changing this example"
        )
    return write_summary(
        output,
        {
            "journey": "E",
            "synthetic": True,
            "scenario": scenario,
            "timezone_policy": "instant; UTC and America/Guayaquil",
            "timestamp_unit": "ns",
            "duplicate_policy": "preserve",
            "null_nan_policy": "distinct",
            "order_policy": "significant",
            "migration_preflight": [check.model_dump(mode="json") for check in checks],
            **comparison_record(result, output, "telemetry"),
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "E", SCENARIOS))
