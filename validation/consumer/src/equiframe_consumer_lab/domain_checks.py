"""Finite synthetic domain conformance; independent literals and invalid types."""

from __future__ import annotations

import itertools
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa

import equiframe as ef

from .evidence import ConsumerError, environment, publish, require, write_json
from .programs import ENGINES, decimal, integer, project, schema, string, table, timestamp

DOMAINS = ("finance", "retail", "telemetry")
VARIANTS = ("good", "different", "invalid")


def declarations(domain: str, variant: str):
    """Expected rows are authored literals, never engine-produced outputs."""
    if variant not in VARIANTS:
        raise ValueError("Unknown domain variant")
    if domain == "finance":
        columns = (string("id"), string("currency"), decimal("amount", 20, 2, "currency_amount"))
        expected_rows = [
            {"id": "001", "currency": "USD", "amount": Decimal("1000000000000000.01")},
            {"id": "002", "currency": "EUR", "amount": Decimal("12.50")},
        ]
        rows = [
            {
                "id": "001",
                "currency": "USD",
                "amount": Decimal(
                    "1000000000000000.02" if variant == "different" else "1000000000000000.01"
                ),
            },
            {"id": "002", "currency": "EUR", "amount": Decimal("12.50")},
        ]
        invalid_column, invalid_array = "amount", pa.array([1.0, 12.5], type=pa.float64())
    elif domain == "retail":
        columns = (
            string("id"),
            integer("quantity", "item", nullable=True),
            decimal("price", 12, 2, "USD"),
        )
        expected_rows = [
            {"id": "001", "quantity": 4, "price": Decimal("12.50")},
            {"id": "002", "quantity": None, "price": Decimal("0.99")},
        ]
        rows = [
            {
                "id": "001",
                "quantity": 5 if variant == "different" else 4,
                "price": Decimal("12.50"),
            },
            {"id": "002", "quantity": None, "price": Decimal("0.99")},
        ]
        invalid_column, invalid_array = "id", pa.array([1, 2], type=pa.int64())
    elif domain == "telemetry":
        columns = (string("id"), timestamp("observed_at"), decimal("reading", 8, 2, "degree_C"))
        first, second = (
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        expected_rows = [
            {"id": "001", "observed_at": first, "reading": Decimal("23.50")},
            {"id": "002", "observed_at": second, "reading": Decimal("24.00")},
        ]
        rows = [
            {
                "id": "001",
                "observed_at": first,
                "reading": Decimal("23.60" if variant == "different" else "23.50"),
            },
            {"id": "002", "observed_at": second, "reading": Decimal("24.00")},
        ]
        invalid_column, invalid_array = (
            "observed_at",
            pa.array(["bad-time", "also-bad"], type=pa.string()),
        )
    else:
        raise ValueError("Unknown domain")
    expected, actual = table(expected_rows, columns), table(rows, columns)
    declared_type = str(actual.schema.field(invalid_column).type)
    if variant == "invalid":
        index = actual.schema.get_field_index(invalid_column)
        actual = actual.set_column(index, invalid_column, invalid_array)
        require(
            str(actual.schema.field(invalid_column).type) != declared_type,
            "Invalid fixture retained the declared type",
        )
    declaration = ef.Contract(
        schema_version="1.0",
        contract_id="consumer.synthetic." + domain,
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="records", schema_spec=schema(columns, ("id",))),),
        output=ef.TableSpec(name="result", schema_spec=schema(columns, ("id",))),
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
    plan = ef.RelationalPlan(
        nodes=(ef.Scan(node_id="scan", table="records"), project(columns)), output="transformed"
    )
    mutation = (
        {
            "column": invalid_column,
            "declared_type": declared_type,
            "actual_type": str(actual.schema.field(invalid_column).type),
        }
        if variant == "invalid"
        else None
    )
    return declaration, plan, actual, expected, mutation


def run_domain_case(output: Path, domain: str, variant: str, source: str, target: str) -> dict:
    require(
        source in ENGINES and target in ENGINES and source != target, "Invalid engine direction"
    )
    require(not output.exists(), "Use a new domain evidence directory")
    declaration, plan, actual, expected, mutation = declarations(domain, variant)
    spec = ef.MigrationSpec(
        contract=declaration,
        ir=plan,
        source_engine=source,
        target_engine=target,
        require_rules=True,
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            justification="Explicit synthetic ID; generated index has no domain identity",
        ),
        comparison_options=ef.ComparisonOptions(max_rows=100, timeout_seconds=30.0),
        execution_options=ef.ExecutionOptions(
            timeout_seconds=60.0,
            max_input_rows=100,
            max_output_rows=100,
            max_transport_bytes=1024 * 1024,
            duckdb_memory_mb=128,
            duckdb_threads=1,
        ),
    )
    native = ef.migrate(
        spec,
        source=ef.LocalDataSource({"records": ef.ArrowInput(actual)}),
        expected=ef.ArrowInput(expected),
        work_dir=output / "native",
    )
    require(
        ef.read_migration(output / "native" / native.migration_id) == native,
        "Domain evidence readback differs",
    )
    executions = [
        child.execution
        for child in (native.source, native.target)
        if child is not None and child.execution is not None
    ]
    accepted = False
    if variant == "invalid":
        require(
            native.exit_code == 2 and not native.complete,
            "Invalid physical input did not fail admission",
        )
        require(
            native.source is None and native.target is None and not executions,
            "Invalid physical input reached native execution",
        )
        require(mutation is not None, "Invalid case lacks a type mutation")
    else:
        require(
            len(executions) == 2 and all(e.state == "completed" for e in executions),
            "Valid native engines did not complete",
        )
        require(
            native.complete and native.state == "equivalent",
            "Identity projection differs between native engines",
        )
        if variant == "good":
            require(
                native.exit_code == 0 and native.verification == "correct",
                "Expected literal was not accepted",
            )
            for result in (
                native.comparison,
                native.verification_source,
                native.verification_target,
            ):
                require(result is not None, "Required comparison missing")
                ef.assert_equivalent(result)
            accepted = True
            require(
                native.target is not None
                and native.target.execution is not None
                and native.target.execution.output is not None,
                "Accepted native target is unavailable",
            )
            publish(
                ef.read_table(native.target.execution.output.data),
                output / "publication",
                accepted=True,
            )
        else:
            require(
                native.exit_code == 1 and native.verification == "divergent",
                "Changed input was not rejected against the literal expected",
            )
    if not accepted:
        require(not (output / "publication").exists(), "Rejected domain input was published")
    record = {
        "domain": domain,
        "variant": variant,
        "synthetic": True,
        "direction": source + "->" + target,
        "observed_exit_code": native.exit_code,
        "verification": native.verification,
        "accepted": accepted,
        "published": accepted,
        "native_execution_count": len(executions),
        "invalid_type_mutation": mutation,
        "stages": [s.model_dump(mode="json") for s in native.stages],
        "comparison_max_rows": 100,
        "fixture_rows": 2,
        "expected_method": "authored literals; identity projection",
        "human_adoption": "not_claimed",
        "status": "PASS",
    }
    write_json(output / "case.json", record)
    return record


def run_domains(output: Path) -> int:
    require(not output.exists(), "Use a new domain-suite directory")
    output.mkdir(parents=True)
    records = []
    try:
        env = environment()
        for domain, variant, source, target in itertools.product(
            DOMAINS, VARIANTS, ENGINES, ENGINES
        ):
            if source == target:
                continue
            require(shutil.disk_usage(output).free >= 4 * 1024**3, "Domain-suite disk guard")
            folder = output / f"{domain}-{variant}-{source}-{target}"
            records.append(run_domain_case(folder, domain, variant, source, target))
        require(len(records) == 54, "Domain suite has missing cases")
        require(
            sum(r["native_execution_count"] for r in records) == 72,
            "Domain native execution count differs",
        )
        require(sum(r["accepted"] for r in records) == 18, "Domain acceptance count differs")
    except Exception as error:
        write_json(
            output / "summary.json",
            {
                "status": "FAIL",
                "consumer_version": "0.1.19",
                "candidate": "0.12.3",
                "synthetic": True,
                "completed_cases": len(records),
                "records": records,
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise ConsumerError("Domain suite incomplete; see retained failure summary") from error
    write_json(
        output / "summary.json",
        {
            "status": "PASS",
            "consumer_version": "0.1.19",
            "candidate": "0.12.3",
            "synthetic": True,
            "environment": env,
            "distinct_cases": len(records),
            "native_executions": sum(r["native_execution_count"] for r in records),
            "accepted_cases": sum(r["accepted"] for r in records),
            "records": records,
        },
    )
    return 0
