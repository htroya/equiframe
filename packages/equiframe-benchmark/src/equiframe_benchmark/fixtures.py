"""Five manually specified synthetic fixtures; adapted from the step 2 native examples."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import equiframe as ef
import pyarrow as pa

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pandas as pd
    import polars as pl


def column(name: str, dtype: ef.LogicalType) -> ef.ColumnSpec:
    numeric = isinstance(dtype, (ef.IntegerType, ef.FloatType, ef.DecimalType))
    temporal: ef.DatePolicy | ef.TimestampPolicy | None = None
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
        rules=(
            ef.RuleSpec(
                rule_id="output_schema",
                revision=1,
                required=True,
                severity="error",
                applicability=(),
                specification=ef.SchemaCheck(table="result"),
            ),
        ),
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
    observed: list[dict[str, object]] = [
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
                        "warehouse": ["east", "east", "east", "west"],
                        "amount": pa.array(
                            [Decimal("10.20"), None, Decimal("0.00"), Decimal("20.40")],
                            type=pa.decimal128(18, 2),
                        ),
                        "id": ["001", "002", "003", "004"],
                    }
                )
            },
            [
                {"warehouse": "east", "total": Decimal("10.20"), "rows": 3},
                {"warehouse": "west", "total": Decimal("20.40"), "rows": 1},
            ],
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
        import pandas as pd

        frame = tables["readings"]
        # This fixture declares UTC microseconds. Use Pandas' own temporal
        # implementation: Arrow-backed .dt.date needs an additional C++ IANA
        # database on some Windows wheels, independently of Python tzdata.
        recorded_at: pd.Series[pd.Timestamp] = pd.Series(
            frame["recorded_at"].tolist(), dtype="datetime64[us, UTC]", index=frame.index
        )
        day: pd.Series[date] = recorded_at.dt.date.astype(pd.ArrowDtype(pa.date32()))
        return frame[["sensor_id"]].assign(day=day)
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
    if not (len(actual) == len(expected)):
        raise AssertionError("Internal invariant check failed.")
    for observed, wanted in zip(actual, expected, strict=True):
        if not (observed.keys() == wanted.keys()):
            raise AssertionError("Internal invariant check failed.")
        for key, value in wanted.items():
            if isinstance(value, float) and math.isnan(value):
                actual_value = observed[key]
                if not (isinstance(actual_value, float) and math.isnan(actual_value)):
                    raise AssertionError("Internal invariant check failed.")
            else:
                if not (observed[key] == value):
                    raise AssertionError("Internal invariant check failed.")


def expected_table(case: Case) -> pa.Table:
    """Manually specified expected physical schemas, independent of normalization."""
    schemas = {
        "nulls_types": pa.schema(
            [("id", pa.string()), ("amount", pa.decimal128(18, 2)), ("measurement", pa.float64())]
        ),
        "duplicates_order": pa.schema(
            [("id", pa.string()), ("amount", pa.decimal128(18, 2)), ("measurement", pa.float64())]
        ),
        "joins": pa.schema(
            [("id", pa.string()), ("product_id", pa.string()), ("category", pa.string())]
        ),
        "aggregations": pa.schema(
            [("warehouse", pa.string()), ("total", pa.decimal128(38, 2)), ("rows", pa.int64())]
        ),
        "dates": pa.schema([("sensor_id", pa.string()), ("day", pa.date32())]),
    }
    return pa.Table.from_pylist(case.expected, schema=schemas[case.contract.family])


COMPARISON_POLICY = ef.ComparisonPolicy(
    physical_types="lossless",
    index="ignore",
    justification="Only declared columns carry meaning; lossless native widths allowed.",
)
