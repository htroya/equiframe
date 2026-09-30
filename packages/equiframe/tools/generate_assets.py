"""Generate versioned schemas and synthetic contract fixtures; --check never writes."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from equiframe import (
    AggregateCheck,
    ArtifactRef,
    BooleanType,
    BooleanValue,
    CardinalityCheck,
    ColumnSpec,
    ComparisonDifference,
    ComparisonOptions,
    ComparisonResult,
    ComparisonSpec,
    Contract,
    DatePolicy,
    DateType,
    DateValue,
    DecimalType,
    DecimalValue,
    ExecutionPlan,
    ExecutionResult,
    Family,
    FloatType,
    FloatValue,
    IgnoredOrder,
    IntegerType,
    IntegerValue,
    JoinCheck,
    KeyCheck,
    KeySpec,
    NaNPolicy,
    NaNValue,
    NullPolicy,
    NullValue,
    NumericPolicy,
    OrderCheck,
    OrderPolicy,
    PreconditionSpec,
    RuleDefinition,
    RuleSpec,
    SchemaCheck,
    SignificantOrder,
    SortSpec,
    StringType,
    StringValue,
    TableKeyScope,
    TableSchema,
    TableSpec,
    TimestampPolicy,
    TimestampType,
    TimestampValue,
    Tolerance,
    canonical_contract_bytes,
    contract_json_schema,
)

ROOT = Path(__file__).resolve().parents[1]
NULLS = NullPolicy(representations=("null",))


def string(name: str, *, samples: tuple[StringValue, ...] = ()) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        logical_type=StringType(),
        nullable=False,
        null_policy=NULLS,
        allowed_values=samples,
    )


def integer(name: str) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        logical_type=IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=NULLS,
        numeric_policy=NumericPolicy(comparison="exact", unit="rows"),
        allowed_values=(IntegerValue(value=0),),
    )


def money(name: str) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        logical_type=DecimalType(precision=38, scale=18),
        nullable=False,
        null_policy=NULLS,
        numeric_policy=NumericPolicy(comparison="exact", unit="synthetic_currency"),
        allowed_values=(
            DecimalValue(value=Decimal("12345678901234567890.123456789012345678")),
            DecimalValue(value=Decimal("-0.000000000000000000")),
        ),
    )


def table(
    name: str,
    columns: tuple[ColumnSpec, ...],
    *,
    keys: tuple[KeySpec, ...] = (),
    order: OrderPolicy | None = None,
) -> TableSpec:
    return TableSpec(
        name=name,
        schema_spec=TableSchema(
            columns=columns,
            keys=keys,
            multiplicity="preserve",
            order=order if order is not None else IgnoredOrder(),
        ),
    )


def key(column: str) -> KeySpec:
    return KeySpec(
        name="primary", columns=(column,), unique=True, incomplete="reject", scope=TableKeyScope()
    )


def contract(
    family: Family, inputs: tuple[TableSpec, ...], output: TableSpec, definition: RuleDefinition
) -> Contract:
    return Contract(
        schema_version="1.0",
        contract_id="synthetic." + family,
        revision=1,
        family=family,
        inputs=inputs,
        output=output,
        preconditions=(
            PreconditionSpec(
                precondition_id="input_schema", requirement=SchemaCheck(table=inputs[0].name)
            ),
        ),
        rules=(
            RuleSpec(
                rule_id="output_schema",
                revision=1,
                specification=SchemaCheck(table=output.name),
                severity="error",
                required=True,
            ),
            RuleSpec(
                rule_id="family_declaration",
                revision=1,
                specification=definition,
                severity="warning",
                required=True,
                applicability=("input_schema",),
            ),
        ),
    )


def examples() -> dict[str, Contract]:
    identifiers = string("id", samples=(StringValue(value="0007"),))
    null_columns = (
        identifiers,
        ColumnSpec(
            name="text",
            logical_type=StringType(),
            nullable=True,
            null_policy=NULLS,
            allowed_values=(StringValue(value=""), StringValue(value="0"), NullValue()),
        ),
        ColumnSpec(
            name="signal",
            logical_type=FloatType(bits=64),
            nullable=True,
            null_policy=NULLS,
            nan_policy=NaNPolicy(handling="distinct"),
            numeric_policy=NumericPolicy(
                comparison="approximate",
                unit="synthetic_sensor",
                tolerance=Tolerance(
                    absolute=Decimal("0.0001"),
                    relative=Decimal("0.001"),
                    unit="synthetic_sensor",
                    justification="Synthetic sensor example, not benchmark policy",
                ),
            ),
            allowed_values=(FloatValue(value=0.0), NaNValue(), NullValue()),
        ),
        ColumnSpec(
            name="active",
            logical_type=BooleanType(),
            nullable=False,
            null_policy=NULLS,
            allowed_values=(BooleanValue(value=False), BooleanValue(value=True)),
        ),
        integer("count"),
        money("amount"),
    )
    supplier = string("supplier_id")
    date_column = ColumnSpec(
        name="day",
        logical_type=DateType(),
        nullable=False,
        null_policy=NULLS,
        temporal_policy=DatePolicy(
            lower=DateValue(value="2000-02-01"), upper=DateValue(value="2000-03-01"), closed="left"
        ),
        allowed_values=(DateValue(value="2000-02-29"),),
    )
    time_column = ColumnSpec(
        name="instant",
        logical_type=TimestampType(unit="ns", timezone="America/Guayaquil"),
        nullable=False,
        null_policy=NULLS,
        temporal_policy=TimestampPolicy(
            granularity="ns",
            timezone="America/Guayaquil",
            naive="reject",
            comparison="instant",
            ambiguous="reject",
            closed="both",
            lower=TimestampValue(
                value="2000-02-29T00:00:00.000000001-05:00", zone="America/Guayaquil"
            ),
            upper=TimestampValue(
                value="2000-02-29T23:59:59.999999999-05:00", zone="America/Guayaquil"
            ),
        ),
        allowed_values=(
            TimestampValue(value="2000-02-29T12:00:00.123456789-05:00", zone="America/Guayaquil"),
        ),
    )
    return {
        "nulls_types": contract(
            "nulls_types",
            (table("source", null_columns, keys=(key("id"),)),),
            table("result", null_columns, keys=(key("id"),)),
            KeyCheck(table="result", key="primary"),
        ),
        "joins": contract(
            "joins",
            (
                table("orders", (identifiers, supplier), keys=(key("id"),)),
                table("suppliers", (supplier, string("name")), keys=(key("supplier_id"),)),
            ),
            table("result", (identifiers, supplier, string("name"))),
            JoinCheck(
                left_table="orders",
                right_table="suppliers",
                left_columns=("supplier_id",),
                right_columns=("supplier_id",),
                relationship="many_to_one",
                unmatched="reject",
            ),
        ),
        "duplicates_order": contract(
            "duplicates_order",
            (table("source", (identifiers, integer("position"))),),
            table(
                "result",
                (identifiers, integer("position")),
                order=SignificantOrder(
                    by=(SortSpec(column="position", direction="ascending", nulls="last"),),
                    ties="preserve",
                ),
            ),
            OrderCheck(table="result", columns=("position",)),
        ),
        "aggregations": contract(
            "aggregations",
            (table("source", (string("currency"), money("amount"))),),
            table("result", (string("currency"), money("total")), keys=(key("currency"),)),
            AggregateCheck(
                table="source",
                group_by=("currency",),
                measure="amount",
                function="sum",
                output_table="result",
                output_column="total",
            ),
        ),
        "dates": contract(
            "dates",
            (table("source", (identifiers, date_column, time_column)),),
            table("result", (identifiers, date_column, time_column)),
            CardinalityCheck(table="result", minimum=0),
        ),
    }


def render_schema(schema: dict[str, object]) -> bytes:
    return (json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assets = {
        ROOT / "examples" / (name + ".json"): canonical_contract_bytes(value)
        for name, value in examples().items()
    }
    assets[ROOT / "schemas" / "contract-1.0.schema.json"] = render_schema(contract_json_schema())
    assets[ROOT / "schemas" / "artifact-ref-1.0.schema.json"] = render_schema(
        ArtifactRef.model_json_schema()
    )
    assets[ROOT / "schemas" / "execution-plan-1.0.schema.json"] = render_schema(
        ExecutionPlan.model_json_schema()
    )
    assets[ROOT / "schemas" / "execution-result-1.0.schema.json"] = render_schema(
        ExecutionResult.model_json_schema()
    )
    for name, model in (
        ("comparison-spec", ComparisonSpec),
        ("comparison-options", ComparisonOptions),
        ("comparison-result", ComparisonResult),
        ("comparison-difference", ComparisonDifference),
    ):
        assets[ROOT / "schemas" / (name + "-1.0.schema.json")] = render_schema(
            model.model_json_schema()
        )
    failures = []
    for path, data in assets.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                failures.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if failures:
        parser.exit(1, "Assets differ: " + ", ".join(failures) + "\n")
    print("Checked" if args.check else "Generated", len(assets), "synthetic fixtures/schemas")


if __name__ == "__main__":
    main()
