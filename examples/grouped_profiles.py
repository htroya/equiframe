"""Native input/output grouped profiles from synthetic rows; no expected-output input."""

from __future__ import annotations

import argparse
import tempfile
from fractions import Fraction
from pathlib import Path

import equiframe as ef


def run(engine: str, rows: int, output: Path) -> ef.ProfileResult:
    import pyarrow as pa

    half = rows // 2
    source = pa.table(
        {
            "department": ["A"] * half + ["B"] * (rows - half),
            "currency": ["USD"] * rows,
            "amount": [1] * rows,
        }
    )

    def columns(amount: str) -> tuple[ef.ColumnSpec, ...]:
        return (
            ef.ColumnSpec(
                name="department",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            ef.ColumnSpec(
                name="currency",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            ef.ColumnSpec(
                name=amount,
                logical_type=ef.IntegerType(bits=64, signed=True),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD_cent"),
            ),
        )

    def table(name: str, amount: str) -> ef.TableSpec:
        return ef.TableSpec(
            name=name,
            schema_spec=ef.TableSchema(
                columns=columns(amount), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
            ),
        )

    contract = ef.Contract(
        schema_version="1.0",
        contract_id="example.grouped_profile",
        revision=1,
        family="aggregations",
        inputs=(table("source", "amount"),),
        output=table("result", "total"),
        rules=(),
        preconditions=(),
    )
    registry = ef.TransformationRegistry()
    if engine == "pandas":

        def pandas_sum(tables, context):
            frame = (
                tables["source"].groupby(["department", "currency"], as_index=False)["amount"].sum()
            )
            frame = frame.rename(columns={"amount": "total"})
            frame.loc[frame["department"] == "A", "total"] += 1
            return frame

        registry.register(ef.PandasTransformation("group_sum", pandas_sum, "synthetic.1"))
    elif engine == "polars":
        import polars as pl

        def polars_sum(tables, context):
            return (
                tables["source"]
                .group_by("department", "currency")
                .agg(pl.col("amount").sum().alias("total"))
                .with_columns(
                    (pl.col("total") + (pl.col("department") == "A").cast(pl.Int64)).alias("total")
                )
            )

        registry.register(ef.PolarsTransformation("group_sum", polars_sum, "synthetic.1"))
    else:
        registry.register(
            ef.DuckDBTransformation(
                "group_sum",
                "SELECT department,currency,CAST(SUM(amount) AS BIGINT) + "
                "CASE WHEN department='A' THEN 1 ELSE 0 END AS total "
                "FROM source GROUP BY department,currency",
                "synthetic.1",
            )
        )
    execution = ef.execute(
        ef.ExecutionPlan(contract=contract, engine=engine, transformation_id="group_sum"),
        source=ef.LocalDataSource({"source": ef.ArrowInput(source)}),
        registry=registry,
        work_dir=output / "execution",
    )
    if execution.state != "completed":
        raise RuntimeError("Synthetic native execution did not complete")
    spec = ef.ProfileSpec(
        family="aggregations",
        feature_version="1.1",
        features=tuple(
            ef.GroupedProfileFeature(
                name=metric,
                metric=metric,
                table="result",
                column="total",
                reference_table="source",
                reference_column="amount",
                by=("department", "currency"),
            )
            for metric in (
                "prop_grupos_suma_modificada",
                "max_diferencia_relativa_grupo",
                "prop_grupos_cambio_desde_cero",
                "cobertura_grupos",
            )
        ),
    )
    result = ef.profile_execution(execution, spec=spec, work_dir=output / "profiles")
    if not result.complete:
        raise RuntimeError("Synthetic grouped profile did not complete")
    modified, relative, zero, coverage = result.vector.observations
    if not (
        modified.value == 0.5
        and coverage.value == 1
        and zero.state == "undefined"
        and Fraction(relative.numerator, relative.denominator) == Fraction(1, half)
    ):
        raise RuntimeError("Synthetic profile differs from independent literal expectations")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("pandas", "polars", "duckdb"), default="pandas")
    parser.add_argument("--rows", type=int, default=30000)
    args = parser.parse_args()
    if args.rows < 2:
        parser.error("--rows must be at least two")
    with tempfile.TemporaryDirectory(prefix="equiframe-grouped-profile-") as temporary:
        result = run(args.engine, args.rows, Path(temporary))
        print(result.vector.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
