"""Five small native examples: retail and sensor telemetry (not a benchmark)."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa

import equiframe as ef

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pandas as pd
    import polars as pl


def column(name: str, dtype: ef.LogicalType) -> ef.ColumnSpec:
    numeric = isinstance(dtype, (ef.IntegerType, ef.FloatType, ef.DecimalType))
    temporal = None
    if isinstance(dtype, ef.DateType):
        temporal = ef.DatePolicy(closed="both")
    elif isinstance(dtype, ef.TimestampType):
        temporal = ef.TimestampPolicy(
            granularity=dtype.unit,
            timezone=dtype.timezone,
            naive="reject" if dtype.timezone else "preserve",
            comparison="instant" if dtype.timezone else "wall_time",
            ambiguous="reject",
            closed="both",
        )
    return ef.ColumnSpec(
        name=name,
        logical_type=dtype,
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        nan_policy=ef.NaNPolicy(handling="distinct") if isinstance(dtype, ef.FloatType) else None,
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="synthetic_units")
        if numeric
        else None,
        temporal_policy=temporal,
        allowed_values=(),
    )


def schema(columns: tuple[ef.ColumnSpec, ...]) -> ef.TableSchema:
    return ef.TableSchema(
        columns=columns, keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )


def contract(
    family: ef.Family,
    inputs: dict[str, tuple[ef.ColumnSpec, ...]],
    output: tuple[ef.ColumnSpec, ...],
) -> ef.Contract:
    return ef.Contract(
        schema_version="1.0",
        contract_id="synthetic." + family,
        revision=1,
        family=family,
        inputs=tuple(ef.TableSpec(name=n, schema_spec=schema(c)) for n, c in inputs.items()),
        output=ef.TableSpec(name="result", schema_spec=schema(output)),
        preconditions=(),
        rules=(),
    )


@dataclass
class Case:
    contract: ef.Contract
    inputs: dict[str, pa.Table]
    expected: list[dict[str, object]]


def cases() -> list[Case]:
    text = ef.StringType()
    integer = ef.IntegerType(bits=64, signed=True)
    decimal = ef.DecimalType(precision=18, scale=2)
    retail = (
        column("id", text),
        column("amount", decimal),
        column("measurement", ef.FloatType(bits=64)),
    )
    sales = pa.table(
        {
            "id": pa.array(["001", "001", "002", "003"], type=pa.string()),
            "amount": pa.array(
                [Decimal("10.20"), Decimal("10.20"), None, Decimal("0.00")],
                type=pa.decimal128(18, 2),
            ),
            "measurement": pa.array(
                [None, float("nan"), 0.0, 2.5], type=pa.float64(), from_pandas=False
            ),
        }
    )
    observed = [
        {"id": "001", "amount": Decimal("10.20"), "measurement": None},
        {"id": "001", "amount": Decimal("10.20"), "measurement": float("nan")},
        {"id": "002", "amount": None, "measurement": 0.0},
        {"id": "003", "amount": Decimal("0.00"), "measurement": 2.5},
    ]
    orders = (column("id", text), column("product_id", text))
    products = (column("product_id", text), column("category", text))
    joined = (*orders, column("category", text))
    grouped = (column("warehouse", text), column("amount", decimal), column("id", text))
    totals = (
        column("warehouse", text),
        column("total", ef.DecimalType(precision=38, scale=2)),
        column("rows", integer),
    )
    stamps = (
        column("sensor_id", text),
        column("recorded_at", ef.TimestampType(unit="us", timezone="UTC")),
    )
    days = (column("sensor_id", text), column("day", ef.DateType()))
    return [
        Case(contract("nulls_types", {"items": retail}, retail), {"items": sales}, observed),
        Case(contract("duplicates_order", {"items": retail}, retail), {"items": sales}, observed),
        Case(
            contract("joins", {"orders": orders, "products": products}, joined),
            {
                "orders": pa.table({"id": ["001", "002"], "product_id": ["A", "Z"]}),
                "products": pa.table({"product_id": ["A"], "category": ["books"]}),
            },
            [
                {"id": "001", "product_id": "A", "category": "books"},
                {"id": "002", "product_id": "Z", "category": None},
            ],
        ),
        Case(
            contract("aggregations", {"items": grouped}, totals),
            {
                "items": pa.table(
                    {
                        "warehouse": ["east", "east", "east"],
                        "amount": pa.array(
                            [Decimal("10.20"), None, Decimal("0.00")], type=pa.decimal128(18, 2)
                        ),
                        "id": ["001", "002", "003"],
                    }
                )
            },
            [{"warehouse": "east", "total": Decimal("10.20"), "rows": 3}],
        ),
        Case(
            contract("dates", {"readings": stamps}, days),
            {
                "readings": pa.table(
                    {
                        "sensor_id": ["0007", "0008"],
                        "recorded_at": pa.array(
                            [
                                datetime.fromisoformat("2024-02-29T23:59:59.123456+00:00"),
                                None,
                            ],
                            type=pa.timestamp("us", tz="UTC"),
                        ),
                    }
                )
            },
            [{"sensor_id": "0007", "day": date(2024, 2, 29)}, {"sensor_id": "0008", "day": None}],
        ),
    ]


def pandas_transform(tables: Mapping[str, pd.DataFrame], ctx: ef.RunContext) -> pd.DataFrame:
    family = ctx.plan.contract.family
    if family == "joins":
        return tables["orders"].merge(tables["products"], on="product_id", how="left", sort=False)
    if family == "aggregations":
        return (
            tables["items"]
            .groupby("warehouse", dropna=False, sort=False)
            .agg(
                total=("amount", "sum"),
                rows=("id", "size"),
            )
            .reset_index()
        )
    if family == "dates":
        frame = tables["readings"]
        return frame[["sensor_id"]].assign(day=frame["recorded_at"].dt.date)
    return tables["items"].copy(deep=True)


def polars_transform(tables: Mapping[str, pl.DataFrame], ctx: ef.RunContext) -> pl.LazyFrame:
    import polars as pl

    family = ctx.plan.contract.family
    if family == "joins":
        return (
            tables["orders"]
            .lazy()
            .join(tables["products"].lazy(), on="product_id", how="left", maintain_order="left")
        )
    if family == "aggregations":
        return (
            tables["items"]
            .lazy()
            .group_by("warehouse", maintain_order=True)
            .agg(
                pl.col("amount").sum().alias("total"),
                pl.len().alias("rows"),
            )
        )
    if family == "dates":
        return (
            tables["readings"]
            .lazy()
            .select("sensor_id", pl.col("recorded_at").dt.date().alias("day"))
        )
    return tables["items"].lazy().select(pl.all())


def registry() -> ef.TransformationRegistry:
    result = ef.TransformationRegistry()
    sql = {
        "nulls_types": 'SELECT * FROM "items"',
        "duplicates_order": 'SELECT * FROM "items"',
        "joins": 'SELECT o.id, o.product_id, p.category FROM "orders" o '
        'LEFT JOIN "products" p ON o.product_id=p.product_id ORDER BY o.id',
        "aggregations": 'SELECT warehouse, sum(amount) AS total, count(*) AS rows FROM "items" '
        "GROUP BY warehouse",
        "dates": 'SELECT sensor_id, CAST(recorded_at AS DATE) AS day FROM "readings"',
    }
    for family, query in sql.items():
        result.register(ef.PandasTransformation(family, pandas_transform, "synthetic.v1"))
        result.register(ef.PolarsTransformation(family, polars_transform, "synthetic.v1"))
        result.register(ef.DuckDBTransformation(family, query, "synthetic.v1"))
    return result


def assert_expected(actual: list[dict[str, object]], expected: list[dict[str, object]]) -> None:
    assert len(actual) == len(expected), (actual, expected)
    for observed, wanted in zip(actual, expected, strict=True):
        assert observed.keys() == wanted.keys()
        for key, value in wanted.items():
            if isinstance(value, float) and math.isnan(value):
                assert isinstance(observed[key], float) and math.isnan(observed[key])
            else:
                assert observed[key] == value, (observed, wanted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("pandas", "polars", "duckdb"), action="append")
    parser.add_argument("--work-dir", type=Path, default=Path("example-runs"))
    args = parser.parse_args()
    registered = registry()
    for engine in args.engine or ("pandas", "polars", "duckdb"):
        for case in cases():
            result = ef.execute(
                ef.ExecutionPlan(
                    contract=case.contract, engine=engine, transformation_id=case.contract.family
                ),
                source=ef.LocalDataSource(
                    {name: ef.ArrowInput(table) for name, table in case.inputs.items()}
                ),
                registry=registered,
                work_dir=args.work_dir,
            )
            assert result.state == "completed", result.problem
            assert result.output is not None
            assert_expected(ef.read_table(result.output.data).to_pylist(), case.expected)
            print(engine, case.contract.family, result.state, result.output.row_count)


if __name__ == "__main__":
    main()
