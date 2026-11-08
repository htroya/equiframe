"""Four bounded real-data workflows with independent standard-library expectations.

Expected calculations never call an EquiFrame transform or a native engine.
They verify the declared arithmetic/data-preservation specification, not the
truth of the agencies' measurements or unlabeled business/scientific outcomes.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict, cast

import pyarrow as pa

import equiframe as ef

from .evidence import JsonObject, require

Columns: TypeAlias = tuple[ef.ColumnSpec, ...]
Rows: TypeAlias = Sequence[Mapping[str, object]]
PlanNode: TypeAlias = ef.Scan | ef.Project | ef.Filter | ef.Aggregate | ef.EquiJoin


class TreasuryRow(TypedDict):
    record_date: str
    security_type: str
    security: str
    rate: Decimal


class EarthquakeRow(TypedDict):
    event_id: str
    network: str
    magnitude: Decimal
    observed_at: datetime


class NetworkGroup(TypedDict):
    network: str
    events: int
    magnitude_sum: Decimal


class PopulationRow(TypedDict):
    state: str
    name: str
    region: str
    population_start: int
    population_end: int


PROGRAMS = ("reconciliation", "refactor", "migration", "preparation")
PROGRAM_INPUT_PATHS = {
    "reconciliation": "raw/treasury.json",
    "refactor": "raw/earthquakes.csv",
    "migration": "population.csv",
    "preparation": "raw/earthquakes.csv",
}
ENGINES = ("pandas", "polars", "duckdb")
VARIANTS = ("good", "defect", "not_evaluable")


def string(name: str) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )


def integer(name: str, unit: str, nullable: bool = False) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit=unit),
    )


def decimal(
    name: str, precision: int, scale: int, unit: str, nullable: bool = False
) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.DecimalType(precision=precision, scale=scale),
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit=unit),
    )


def timestamp(name: str) -> ef.ColumnSpec:
    return ef.ColumnSpec(
        name=name,
        logical_type=ef.TimestampType(unit="us", timezone="UTC"),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        temporal_policy=ef.TimestampPolicy(
            granularity="us",
            timezone="UTC",
            naive="reject",
            comparison="instant",
            ambiguous="reject",
            closed="both",
        ),
    )


def schema(columns: Columns, keys: tuple[str, ...] = ()) -> ef.TableSchema:
    return ef.TableSchema(
        columns=columns,
        keys=(
            ef.KeySpec(
                name="identity",
                columns=keys,
                unique=True,
                incomplete="reject",
                scope=ef.TableKeyScope(),
            ),
        )
        if keys
        else (),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )


def arrow_type(column: ef.ColumnSpec) -> pa.DataType:
    logical_type = column.logical_type
    kind = logical_type.kind
    if kind == "string":
        return pa.string()
    if kind == "integer":
        return pa.int64()
    if kind == "decimal":
        return pa.decimal128(
            cast(ef.DecimalType, logical_type).precision, cast(ef.DecimalType, logical_type).scale
        )
    if kind == "timestamp":
        return pa.timestamp(
            cast(ef.TimestampType, logical_type).unit,
            tz=cast(ef.TimestampType, logical_type).timezone,
        )
    raise ValueError("Unexpected consumer logical type")


def table(rows: Rows, columns: Columns) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=pa.schema([(c.name, arrow_type(c)) for c in columns]))


def project(columns: Columns) -> ef.Project:
    return ef.Project(
        node_id="transformed",
        source="scan",
        columns=tuple(
            ef.NamedExpression(name=c.name, expression=ef.Column(name=c.name)) for c in columns
        ),
    )


@dataclass(frozen=True)
class Program:
    name: str
    description: str
    source_file: Path
    ingestion: ef.IngestionSpec
    input_columns: Columns
    output_columns: Columns
    output_keys: tuple[str, ...]
    independent_input_rows: Rows
    independent_expected_rows: Rows
    nodes: tuple[PlanNode, ...]
    family: ef.Family
    defect: str

    def native_source(self, captured: pa.Table, baseline: pa.Table) -> ef.LocalDataSource:
        if self.name == "migration":
            # Two declared vintages from the SAME frozen ingestion. Only the new
            # side sees the controlled derived mutation; expected is never an input.
            return ef.LocalDataSource(
                {
                    "old": ef.ArrowInput(
                        baseline.select(["state", "name", "region", "population_start"])
                    ),
                    "new": ef.ArrowInput(captured.select(["state", "population_end"])),
                }
            )
        return ef.LocalDataSource({"records": ef.ArrowInput(captured)})

    def contract(self) -> ef.Contract:
        inputs: tuple[ef.TableSpec, ...] = (
            ef.TableSpec(name="records", schema_spec=schema(self.input_columns)),
        )
        if self.name == "migration":
            inputs = (
                ef.TableSpec(name="old", schema_spec=schema(self.input_columns[:4])),
                ef.TableSpec(
                    name="new", schema_spec=schema((self.input_columns[0], self.input_columns[4]))
                ),
            )
        return ef.Contract(
            schema_version="1.0",
            contract_id="consumer.real." + self.name,
            revision=1,
            family=self.family,
            inputs=inputs,
            output=ef.TableSpec(
                name="result", schema_spec=schema(self.output_columns, self.output_keys)
            ),
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

    def spec(self, source_engine: str, target_engine: str, variant: str) -> ef.MigrationSpec:
        return ef.MigrationSpec(
            contract=self.contract(),
            source_engine=source_engine,
            target_engine=target_engine,
            ir=ef.RelationalPlan(nodes=self.nodes, output="transformed"),
            require_rules=True,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore",
                justification=(
                    "Generated native RangeIndex has no domain identity; "
                    "explicit keys and multiplicity remain required."
                ),
            ),
            comparison_options=ef.ComparisonOptions(
                max_rows=1 if variant == "not_evaluable" else 10000,
                max_examples=5,
                timeout_seconds=30.0,
            ),
            execution_options=ef.ExecutionOptions(
                timeout_seconds=60.0,
                max_input_rows=10000,
                max_output_rows=10000,
                max_transport_bytes=16 * 1024 * 1024,
                duckdb_memory_mb=128,
                duckdb_threads=1,
                duckdb_timezone="UTC",
            ),
            options=ef.MigrationOptions(
                timeout_seconds=180.0, max_capture_rows=10000, max_capture_bytes=16 * 1024 * 1024
            ),
        )

    def mutate(self, source: pa.Table) -> tuple[pa.Table, JsonObject]:
        # The captured table was compared with the typed independent input before
        # mutation; Arrow's Python scalar boundary has no complete static stubs.
        rows: list[dict[str, object]] = source.to_pylist()
        require(len(rows) >= 2, "Controlled defect requires at least two original records")
        if self.name == "reconciliation":
            before: object = [rows[0]["rate"], rows[1]["rate"]]
            rows[0]["rate"] = cast(Decimal, rows[0]["rate"]) + Decimal("0.001")
            rows[1]["rate"] = cast(Decimal, rows[1]["rate"]) - Decimal("0.001")
            require(
                sum((cast(Decimal, r["rate"]) for r in rows), Decimal(0))
                == sum((r["rate"] for r in source.to_pylist()), Decimal(0)),
                "Compensated defect must preserve the total",
            )
            delta: JsonObject = {
                "rows": [0, 1],
                "before": before,
                "after": [rows[0]["rate"], rows[1]["rate"]],
                "sum_preserved": True,
            }
        elif self.name == "refactor":
            selected = next(
                i for i, r in enumerate(rows) if cast(Decimal, r["magnitude"]) >= Decimal("4.5")
            )
            removed = rows.pop(selected)
            delta = {"removed_id": removed["event_id"], "rows_removed": 1}
        elif self.name == "migration":
            before = rows[0]["state"]
            require("99" not in {r["state"] for r in rows}, "Controlled state ID must be new")
            rows[0]["state"] = "99"
            delta = {"old_state": before, "new_state": "99", "changed_vintage": "population_end"}
        else:
            before = rows[0]["observed_at"]
            rows[0]["observed_at"] = cast(datetime, before) + timedelta(hours=1)
            delta = {
                "event_id": rows[0]["event_id"],
                "before": before,
                "after": rows[0]["observed_at"],
                "offset_seconds": 3600,
            }
        return table(rows, self.input_columns), {
            "kind": self.defect,
            "controlled_derived_variant": True,
            **delta,
        }


def _ingestion(
    format: Literal["csv", "json", "jsonl"],
    columns: Columns,
    mapping: tuple[str, ...],
    *,
    records_path: tuple[str, ...] = (),
) -> ef.IngestionSpec:
    return ef.IngestionSpec(
        format=format,
        fields=tuple(
            ef.FieldMapping(column=c, path=(raw,)) for c, raw in zip(columns, mapping, strict=True)
        ),
        records_path=records_path,
        extra_fields="ignore",
        invalid_records="reject",
        max_records=10000,
        max_source_bytes=4 * 1024 * 1024,
    )


def load_program(name: str, data: Path) -> Program:
    scan = ef.Scan(node_id="scan", table="records")
    cols: Columns
    out: Columns
    if name == "reconciliation":
        path = data / PROGRAM_INPUT_PATHS[name]
        cols = (
            string("record_date"),
            string("security_type"),
            string("security"),
            decimal("rate", 8, 3, "percentage_points"),
        )
        treasury_rows: list[TreasuryRow] = [
            {
                "record_date": r["record_date"],
                "security_type": r["security_type_desc"],
                "security": r["security_desc"],
                "rate": Decimal(r["avg_interest_rate_amt"]),
            }
            for r in json.loads(path.read_text())["data"]
        ]
        return Program(
            name,
            "Reconcile each security's exact Treasury average rate; "
            "matching totals are insufficient.",
            path,
            _ingestion(
                "json",
                cols,
                ("record_date", "security_type_desc", "security_desc", "avg_interest_rate_amt"),
                records_path=("data", "*"),
            ),
            cols,
            cols,
            ("record_date", "security_type", "security"),
            treasury_rows,
            [dict(r) for r in treasury_rows],
            (scan, project(cols)),
            "nulls_types",
            "compensated_rate_change",
        )
    if name in ("refactor", "preparation"):
        path = data / PROGRAM_INPUT_PATHS[name]
        cols = (
            string("event_id"),
            string("network"),
            decimal("magnitude", 6, 3, "magnitude"),
            timestamp("observed_at"),
        )
        with path.open(encoding="utf-8", newline="") as stream:
            earthquake_rows: list[EarthquakeRow] = [
                {
                    "event_id": r["id"],
                    "network": r["net"],
                    "magnitude": Decimal(r["mag"]),
                    "observed_at": datetime.fromisoformat(r["time"].replace("Z", "+00:00")),
                }
                for r in csv.DictReader(stream)
            ]
        ingestion = _ingestion("csv", cols, ("id", "net", "mag", "time"))
        if name == "refactor":
            out = (
                cols[1],
                integer("events", "rows"),
                decimal("magnitude_sum", 12, 3, "magnitude", True),
            )
            groups: dict[str, NetworkGroup] = {}
            with localcontext() as ctx:
                ctx.prec = 38
                for r in earthquake_rows:
                    if r["magnitude"] < Decimal("4.5"):
                        continue
                    g = groups.setdefault(
                        r["network"],
                        {"network": r["network"], "events": 0, "magnitude_sum": Decimal("0.000")},
                    )
                    g["events"] += 1
                    g["magnitude_sum"] += r["magnitude"]
            selection = ef.Filter(
                node_id="selected",
                source="scan",
                predicate=ef.Compare(
                    operation="ge",
                    left=ef.Column(name="magnitude"),
                    right=ef.LiteralExpression(
                        logical_type=ef.DecimalType(precision=6, scale=3),
                        value=ef.DecimalValue(value=Decimal("4.500")),
                        unit="magnitude",
                    ),
                ),
            )
            node: ef.Aggregate | ef.Project = ef.Aggregate(
                node_id="transformed",
                source="selected",
                group_by=("network",),
                measures=(
                    ef.Measure(
                        name="events",
                        operation="count_rows",
                        logical_type=ef.IntegerType(bits=64, signed=True),
                        unit="rows",
                    ),
                    ef.Measure(
                        name="magnitude_sum",
                        operation="sum",
                        column="magnitude",
                        logical_type=ef.DecimalType(precision=12, scale=3),
                        unit="magnitude",
                    ),
                ),
                null_groups="retain",
                empty_sum="null",
            )
            return Program(
                name,
                "Refactor network-level aggregation without losing event multiplicity or exact "
                "decimal sums. Magnitude sum is a software-check quantity, not an energy measure.",
                path,
                ingestion,
                cols,
                out,
                ("network",),
                earthquake_rows,
                list(groups.values()),
                (scan, selection, node),
                "aggregations",
                "lost_event",
            )
        out = (cols[0], cols[3], decimal("magnitude_tenths", 8, 3, "scaled_magnitude"))
        expected = [
            {
                "event_id": r["event_id"],
                "observed_at": r["observed_at"],
                "magnitude_tenths": r["magnitude"] * Decimal("10"),
            }
            for r in earthquake_rows
        ]
        node = ef.Project(
            node_id="transformed",
            source="scan",
            columns=(
                ef.NamedExpression(name="event_id", expression=ef.Column(name="event_id")),
                ef.NamedExpression(name="observed_at", expression=ef.Column(name="observed_at")),
                ef.NamedExpression(
                    name="magnitude_tenths",
                    expression=ef.Arithmetic(
                        operation="multiply",
                        left=ef.Column(name="magnitude"),
                        right=ef.LiteralExpression(
                            logical_type=ef.DecimalType(precision=2, scale=0),
                            value=ef.DecimalValue(value=Decimal("10")),
                            unit="factor",
                        ),
                        logical_type=ef.DecimalType(precision=8, scale=3),
                        unit="scaled_magnitude",
                    ),
                ),
            ),
        )
        return Program(
            name,
            "Prepare a declared scaled magnitude feature while retaining event identity and "
            "the exact UTC instant; no anomaly labels or trained model.",
            path,
            ingestion,
            cols,
            out,
            ("event_id",),
            earthquake_rows,
            expected,
            (scan, node),
            "dates",
            "one_hour_time_shift",
        )
    if name == "migration":
        path = data / PROGRAM_INPUT_PATHS[name]
        cols = (
            string("state"),
            string("name"),
            string("region"),
            integer("population_start", "persons"),
            integer("population_end", "persons"),
        )
        with path.open(encoding="utf-8", newline="") as stream:
            population_rows: list[PopulationRow] = [
                {
                    "state": r["state"],
                    "name": r["name"],
                    "region": r["region"],
                    "population_start": int(r["population_start"]),
                    "population_end": int(r["population_end"]),
                }
                for r in csv.DictReader(stream)
            ]
        # Full outer join independently reunites two physically separated vintages.
        out = (
            *(c.model_copy(update={"nullable": True}) for c in cols[:4]),
            string("right.state").model_copy(update={"nullable": True}),
            cols[4].model_copy(update={"name": "right.population_end", "nullable": True}),
        )
        expected = [
            {
                **{c.name: cast(Mapping[str, object], r)[c.name] for c in cols[:4]},
                "right.state": r["state"],
                "right.population_end": r["population_end"],
            }
            for r in population_rows
        ]
        nodes = (
            ef.Scan(node_id="oldscan", table="old"),
            ef.Scan(node_id="newscan", table="new"),
            ef.EquiJoin(
                node_id="transformed",
                left="oldscan",
                right="newscan",
                keys=(ef.JoinKey(left="state", right="state"),),
                how="full",
                null_keys="never",
                cardinality="one_to_one",
            ),
        )
        return Program(
            name,
            "Migrate two real population vintages through a full outer one-to-one join, "
            "preserving zero-padded state IDs, counts and orphaned sides.",
            path,
            _ingestion("csv", cols, tuple(c.name for c in cols)),
            cols,
            out,
            (),
            population_rows,
            expected,
            nodes,
            "joins",
            "changed_state_id",
        )
    raise ValueError("Unknown consumer program")
