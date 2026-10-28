"""DuckDB aggregates over one private fixed snapshot; identifiers are quoted."""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from equiframe._duckdb_transport import duckdb_parameters
from equiframe.errors import CapabilityError

from .models import ColumnProfile, DuplicateProfile, EdaConfig, Finding, KeyRule, NumericRule

if TYPE_CHECKING:
    import duckdb


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def value(item: Any) -> Any:
    """JSON transport never silently turns Decimal/nonfinite into JSON floats."""
    if isinstance(item, Decimal):
        return str(item)
    if isinstance(item, float) and not math.isfinite(item):
        return {"kind": "nan" if math.isnan(item) else "infinity", "sign": str(item)}
    if hasattr(item, "isoformat"):
        return item.isoformat()
    return item


class Backend:
    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        config: EdaConfig,
        checkpoint: Callable[[], None],
    ) -> None:
        self.connection, self.config, self.checkpoint = connection, config, checkpoint
        self.findings: list[Finding] = []
        self.raw_schema: dict[str, str] = {}
        self.schema: dict[str, str] = {}

    def query(self, sql: str, params: list[Any] | None = None) -> list[Any]:
        self.checkpoint()
        provided = params or []
        bound = duckdb_parameters({str(i): p for i, p in enumerate(provided)})
        rows = self.connection.execute(
            sql, [bound[str(i)] for i in range(len(provided))]
        ).fetchall()
        self.checkpoint()
        return rows

    def examples(
        self, predicate: str, columns: tuple[str, ...], params: list[Any] | None = None
    ) -> tuple[dict[str, object], ...]:
        names = ("__ef_eda_row", *columns)
        rows = self.query(
            f"SELECT {','.join(quote(c) for c in names)} FROM typed "
            f"WHERE {predicate} ORDER BY __ef_eda_row LIMIT "
            f"{self.config.resources.examples}",
            params,
        )
        return tuple({name: value(v) for name, v in zip(names, row, strict=True)} for row in rows)

    def columns(self, rows: int) -> tuple[ColumnProfile, ...]:
        self.raw_schema = {
            r[0]: r[1] for r in self.query("DESCRIBE SELECT * EXCLUDE (__ef_eda_row) FROM raw")
        }
        profiles = []
        for name, dtype in self.raw_schema.items():
            col = quote(name)
            floating = dtype in ("DOUBLE", "FLOAT")
            numeric = floating or dtype.startswith(
                (
                    "DECIMAL",
                    "INTEGER",
                    "BIGINT",
                    "SMALLINT",
                    "TINYINT",
                    "HUGEINT",
                    "UBIGINT",
                    "UINTEGER",
                    "UTINYINT",
                    "USMALLINT",
                )
            )
            text = dtype == "VARCHAR"
            nan = f"isnan({col})" if floating else "FALSE"
            nonfinite = f"NOT isfinite({col})" if floating else "FALSE"
            empty = f"{col} = ''" if text else "FALSE"
            zero = f"{col} = 0" if numeric else "FALSE"
            present = f"{col} IS NOT NULL AND NOT ({nan})"
            valid = f"{present} AND NOT ({empty}) AND NOT ({nonfinite})"
            counts = self.query(
                f"SELECT count(*) FILTER (WHERE {col} IS NULL), "
                f"count(*) FILTER (WHERE {nan}), count(*) FILTER (WHERE {empty}), "
                f"count(*) FILTER (WHERE {zero}), count(*) FILTER (WHERE {nonfinite}), "
                f"count(*) FILTER (WHERE {valid}), count(DISTINCT {col}) "
                f"FILTER (WHERE {present}) FROM raw"
            )[0]
            freq = self.query(
                f"SELECT {col}, count(*) __ef_count FROM raw GROUP BY {col} "
                f"ORDER BY __ef_count DESC, {col} ASC NULLS LAST LIMIT "
                f"{self.config.resources.top_categories}"
            )
            profiles.append(
                ColumnProfile(
                    name=name,
                    physical_type=dtype,
                    rows=rows,
                    nulls=counts[0],
                    nan=counts[1],
                    empty=counts[2],
                    zero=counts[3],
                    nonfinite=counts[4],
                    valid=counts[5],
                    distinct_present=counts[6],
                    null_rate=counts[0] / rows if rows else None,
                    empty_rate=counts[2] / rows if rows else None,
                    nan_rate=counts[1] / rows if rows else None,
                    frequencies=tuple(
                        {"value": value(v), "count": n, "denominator": rows} for v, n in freq
                    ),
                )
            )
        return tuple(profiles)

    def convert(self) -> tuple[dict[str, object], ...]:
        expressions = ["*"]
        metadata: list[dict[str, object]] = []
        for conversion in self.config.conversions:
            if (
                conversion.column not in self.raw_schema
                or conversion.target.casefold() in {n.casefold() for n in self.raw_schema}
                or conversion.target.casefold().startswith("__ef_")
            ):
                raise ValueError("conversion requires existing source and new derived name")
            if self.raw_schema[conversion.column] != "VARCHAR":
                raise ValueError("MVP explicit conversion requires a text source column")
            col = quote(conversion.column)
            base = f"nullif({col}, '')" if conversion.empty == "missing" else col
            if conversion.kind == "decimal":
                # Reject excess fractional precision instead of DuckDB's rounded cast.
                pattern = (
                    rf"[+-]?[0-9]+(\.[0-9]{{1,{conversion.scale}}})?"
                    if conversion.scale
                    else r"[+-]?[0-9]+"
                )
                expression = (
                    f"CASE WHEN regexp_full_match({base}, '{pattern}') THEN "
                    f"try_cast({base} AS DECIMAL({conversion.precision},{conversion.scale})) END"
                )
            elif conversion.kind == "integer":
                expression = (
                    f"CASE WHEN regexp_full_match({base}, '[+-]?[0-9]+') "
                    f"THEN try_cast({base} AS BIGINT) END"
                )
            elif conversion.kind == "date":
                expression = (
                    f"CASE WHEN regexp_full_match({base}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}') "
                    f"THEN try_cast({base} AS DATE) END"
                )
            else:
                # Preserve explicit instants; never guess a zone for naive timestamps.
                pattern = (
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                    r"(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})"
                )
                expression = (
                    f"CASE WHEN regexp_full_match({base}, '{pattern}') "
                    f"THEN try_cast({base} AS TIMESTAMPTZ) END"
                )
            expressions.append(expression + " AS " + quote(conversion.target))
            attempted = f"{base} IS NOT NULL"
            invalid = f"({attempted}) AND ({expression}) IS NULL"
            attempted_n, failures, missing = self.query(
                f"SELECT count(*) FILTER (WHERE {attempted}), count(*) FILTER (WHERE {invalid}), "
                f"count(*) FILTER (WHERE {base} IS NULL) FROM raw"
            )[0]
            ex = self.query(
                f"SELECT __ef_eda_row, {col} FROM raw WHERE {invalid} "
                f"ORDER BY __ef_eda_row LIMIT {self.config.resources.examples}"
            )
            metadata.append(
                {
                    "column": conversion.column,
                    "target": conversion.target,
                    "policy": conversion.model_dump(mode="json"),
                    "attempted": attempted_n,
                    "invalid": failures,
                    "missing": missing,
                    "examples": [{"row": r, "original": v} for r, v in ex],
                }
            )
            if failures:
                self.findings.append(
                    Finding(
                        code="conversion_invalid",
                        severity="rule_violation",
                        column=conversion.column,
                        count=failures,
                        denominator=attempted_n,
                        reason=(
                            "Explicit conversion failed; original values retained; "
                            "no rounding or guessed dates."
                        ),
                        examples=tuple({"row": r, "original": v} for r, v in ex),
                    )
                )
        self.query("CREATE TEMP VIEW typed AS SELECT " + ",".join(expressions) + " FROM raw")
        self.schema = {r[0]: r[1] for r in self.query("DESCRIBE typed")}
        for item, conversion in zip(metadata, self.config.conversions, strict=True):
            if conversion.kind in ("date", "timestamp"):
                col = quote(conversion.target)
                low, high = self.query(
                    f"SELECT cast(min({col}) AS VARCHAR), cast(max({col}) AS VARCHAR) FROM typed"
                )[0]
                years = self.query(
                    f"SELECT extract(year FROM {col}) __ef_year, count(*) __ef_count FROM typed "
                    f"WHERE {col} IS NOT NULL GROUP BY 1 ORDER BY 1"
                )
                item["observed_dates"] = {
                    "minimum": value(low),
                    "maximum": value(high),
                    "years": [{"year": int(y), "rows": n} for y, n in years],
                    "timezone": "UTC for explicit instants; dates unchanged",
                    "cohort_inferred": False,
                }
        return tuple(metadata)

    def duplicates(self, columns: tuple[str, ...], rule: KeyRule | None = None) -> DuplicateProfile:
        if not set(columns) <= self.raw_schema.keys():
            raise ValueError("duplicate rule references unknown source column")
        names = ",".join(quote(c) for c in columns)
        predicates = []
        for name in columns:
            col, dtype = quote(name), self.raw_schema[name]
            predicates.append(f"{col} IS NULL")
            if dtype in ("DOUBLE", "FLOAT"):
                predicates.append(f"isnan({col})")
            if rule is not None and rule.empty_is_missing and dtype == "VARCHAR":
                predicates.append(f"{col} = ''")
        missing = " OR ".join(predicates)
        incomplete = self.query(f"SELECT count(*) FROM raw WHERE {missing}")[0][0] if rule else 0
        where = f"WHERE NOT ({missing})" if rule and rule.incomplete != "include" else ""
        denominator = self.query(f"SELECT count(*) FROM raw {where}")[0][0]
        repeated = (
            f"SELECT {names}, count(*) __ef_count FROM raw {where} "
            f"GROUP BY {names} HAVING count(*) > 1"
        )
        groups, involved, excess = self.query(
            f"SELECT count(*), coalesce(sum(__ef_count),0), "
            f"coalesce(sum(__ef_count-1),0) FROM ({repeated})"
        )[0]
        examples = self.query(
            f"SELECT {names}, __ef_count FROM ({repeated}) ORDER BY __ef_count DESC, {names} "
            f"LIMIT {self.config.resources.examples}"
        )
        # Group examples include bounded row references without loading groups in Python.
        references = self.query(
            f"SELECT __ef_eda_row FROM (SELECT *, count(*) OVER "
            f"(PARTITION BY {names}) __ef_n FROM raw {where}) "
            f"WHERE __ef_n > 1 ORDER BY __ef_eda_row LIMIT {self.config.resources.examples}"
        )
        if rule is not None and incomplete and rule.incomplete == "reject":
            self.findings.append(
                Finding(
                    code="incomplete_key",
                    severity="rule_violation",
                    count=incomplete,
                    denominator=denominator + incomplete,
                    reason="Declared key policy rejects incomplete keys; source retained.",
                    examples=self.examples(missing, columns),
                )
            )
        if groups:
            self.findings.append(
                Finding(
                    code="key_duplicates" if rule else "row_duplicates",
                    severity="rule_violation" if rule and rule.require_unique else "observation",
                    count=int(excess),
                    denominator=denominator,
                    reason="Repetitions observed; may be legitimate history. No row was removed.",
                    examples=tuple({"row": r[0]} for r in references),
                )
            )
        return DuplicateProfile(
            columns=columns,
            denominator=denominator,
            incomplete_rows=incomplete,
            policy=rule.incomplete if rule else "all_rows_including_null_and_nan",
            repeated_groups=int(groups),
            involved_rows=int(involved),
            excess_rows=int(excess),
            excess_rate=float(excess / denominator) if denominator else None,
            examples=tuple(
                {
                    "values": {c: value(v) for c, v in zip(columns, row[:-1], strict=True)},
                    "rows": row[-1],
                }
                for row in examples
            ),
        )

    def numeric(self, rule: NumericRule) -> dict[str, object]:
        if rule.column not in self.schema or not set(rule.groups) <= self.schema.keys():
            raise ValueError("numeric rule references unknown column")
        dtype, col = self.schema[rule.column], quote(rule.column)
        if dtype not in (
            "DOUBLE",
            "FLOAT",
            "INTEGER",
            "BIGINT",
            "SMALLINT",
            "TINYINT",
            "HUGEINT",
            "UBIGINT",
            "UINTEGER",
            "UTINYINT",
            "USMALLINT",
        ) and not dtype.startswith("DECIMAL"):
            raise ValueError("numeric column must be numeric or explicitly converted")
        if rule.monetary and not dtype.startswith("DECIMAL"):
            raise ValueError("monetary diagnostics require exact Decimal, never float")
        if rule.monetary and (
            rule.currency_column is None or self.schema[rule.currency_column] != "VARCHAR"
        ):
            raise ValueError("currency identifiers must be explicit text, not numeric groups")
        if any(
            self.schema[g]
            not in (
                "VARCHAR",
                "BOOLEAN",
                "INTEGER",
                "BIGINT",
                "FLOAT",
                "DOUBLE",
                "UTINYINT",
                "USMALLINT",
                "SMALLINT",
                "TINYINT",
                "UINTEGER",
                "UBIGINT",
            )
            and not self.schema[g].startswith("DECIMAL")
            for g in rule.groups
        ):
            raise CapabilityError("MVP comparable groups admit text/bool/integer/Decimal/float")
        names = ",".join(quote(g) for g in rule.groups)
        group_count = (
            self.query(f"SELECT count(*) FROM (SELECT {names} FROM typed GROUP BY {names})")[0][0]
            if names
            else 1
        )
        if group_count > self.config.resources.max_groups:
            self.findings.append(
                Finding(
                    code="group_limit",
                    severity="not_evaluable",
                    column=rule.column,
                    reason=(
                        "Comparable group count exceeds configured budget; "
                        "no groups silently discarded."
                    ),
                )
            )
            return {
                "rule": rule.model_dump(mode="json"),
                "state": "not_evaluable",
                "reason": "group_limit",
                "groups_total": group_count,
            }
        groups = (
            self.query(f"SELECT {names} FROM typed GROUP BY {names} ORDER BY {names}")
            if names
            else [()]
        )
        output = []
        for group in groups:
            where = (
                " AND ".join(f"{quote(c)} IS NOT DISTINCT FROM ?" for c in rule.groups) or "TRUE"
            )
            float_type = dtype in ("DOUBLE", "FLOAT")
            finite = f"{col} IS NOT NULL" + (f" AND isfinite({col})" if float_type else "")
            valid_where = f"({where}) AND ({finite})"
            total, valid, missing, nonfinite = self.query(
                f"SELECT count(*), count(*) FILTER (WHERE {finite}), "
                f"count(*) FILTER (WHERE {col} IS NULL), "
                f"count(*) FILTER (WHERE {col} IS NOT NULL AND NOT ({finite})) "
                f"FROM typed WHERE {where}",
                list(group),
            )[0]
            record: dict[str, object] = {
                "group": {c: value(v) for c, v in zip(rule.groups, group, strict=True)},
                "total": total,
                "valid": valid,
                "missing": missing,
                "nonfinite": nonfinite,
                "state": "completed" if valid else "not_evaluable",
                "reason": None if valid else "no_finite_values",
            }
            incomparable = (
                rule.monetary and group[rule.groups.index(rule.currency_column)] in (None, "")
            ) or any(isinstance(v, float) and not math.isfinite(v) for v in group)
            if incomparable:
                record.update(
                    state="not_evaluable",
                    reason="missing_currency" if rule.monetary else "nonfinite_group",
                    outliers={
                        "method": rule.outliers,
                        "state": "not_evaluable",
                        "count": None,
                        "reason": "missing_currency" if rule.monetary else "nonfinite_group",
                    },
                )
                self.findings.append(
                    Finding(
                        code="incomparable_group",
                        severity="not_evaluable",
                        column=rule.column,
                        denominator=valid,
                        reason=(
                            "Grouping has missing currency or nonfinite values; "
                            "no pooled numeric amounts."
                        ),
                    )
                )
                output.append(record)
                continue
            if not valid:
                output.append(record)
                continue
            percentiles = sorted(set((0.25, 0.5, 0.75, *self.config.percentiles)))
            qs = ",".join(f"quantile_disc({col}, {p})" for p in percentiles)
            sums = self.query(
                f"SELECT min({col}), max({col}), sum({col}), avg({col}), "
                f"stddev_{'pop' if self.config.stddev == 'population' else 'samp'}({col}), {qs} "
                f"FROM typed WHERE {valid_where}",
                list(group),
            )[0]
            qmap = dict(zip(percentiles, sums[5:], strict=True))
            record.update(
                minimum=value(sums[0]),
                maximum=value(sums[1]),
                sum=value(sums[2]),
                mean_approximate=value(sums[3]),
                stddev_approximate=value(sums[4]),
                stddev_definition=self.config.stddev,
                quantiles={str(p): value(qmap[p]) for p in percentiles},
                median=value(qmap[0.5]),
                quantile_method=(
                    "DuckDB quantile_disc, Hyndman-Fan type 1; observed value, no interpolation"
                ),
                precision=(
                    "Exact sum/min/max/discrete quantiles for integer/Decimal; "
                    "mean/stddev float64 approximate; float aggregates approximate"
                ),
                excluded_from_statistics=(
                    "NULL and nonfinite; failed conversions remain separate in conversion receipt"
                ),
            )
            if isinstance(sums[2], (int, Decimal)):
                mean = Fraction(sums[2]) / valid
                record["mean_exact_rational"] = {
                    "numerator": str(mean.numerator),
                    "denominator": str(mean.denominator),
                }
            outlier: dict[str, object] = {
                "method": rule.outliers,
                "multiplier": rule.multiplier,
                "min_support": rule.min_support,
                "state": "not_evaluable",
                "count": None,
                "reason": "disabled" if rule.outliers == "none" else "insufficient_support",
            }
            if valid >= rule.min_support and rule.outliers != "none":
                median = qmap[0.5]
                with localcontext() as ctx:
                    ctx.prec = 80
                    if rule.outliers == "iqr":
                        dispersion = Decimal(str(qmap[0.75])) - Decimal(str(qmap[0.25]))
                        lower = (
                            Decimal(str(qmap[0.25])) - Decimal(str(rule.multiplier)) * dispersion
                        )
                        upper = (
                            Decimal(str(qmap[0.75])) + Decimal(str(rule.multiplier)) * dispersion
                        )
                    else:
                        mad = self.query(
                            f"SELECT quantile_disc(abs({col} - ?),0.5) "
                            f"FROM typed WHERE {valid_where}",
                            [median, *group],
                        )[0][0]
                        dispersion = Decimal(str(mad))
                        lower = Decimal(str(median)) - Decimal(str(rule.multiplier)) * dispersion
                        upper = Decimal(str(median)) + Decimal(str(rule.multiplier)) * dispersion
                    if dispersion == 0:
                        outlier["reason"] = "zero_dispersion"
                    else:
                        predicate = f"{valid_where} AND ({col} < ? OR {col} > ?)"
                        # Reduce only transient bounds by exact trailing-zero removal,
                        # within the high-precision local context, never original money.
                        lower = lower.normalize()
                        upper = upper.normalize()
                        if int(lower.as_tuple().exponent) > 0:
                            lower = Decimal(format(lower, "f"))
                        if int(upper.as_tuple().exponent) > 0:
                            upper = Decimal(format(upper, "f"))
                        params = [*group, lower, upper]
                        try:
                            count = self.query(
                                f"SELECT count(*) FROM typed WHERE {predicate}", params
                            )[0][0]
                            ex = self.examples(predicate, (rule.column, *rule.groups), params)
                        except CapabilityError:
                            outlier["reason"] = "unrepresentable_decimal_bounds"
                            record["outliers"] = outlier
                            self.findings.append(
                                Finding(
                                    code="outliers_unavailable",
                                    severity="not_evaluable",
                                    column=rule.column,
                                    denominator=valid,
                                    reason=(
                                        "Exact outlier bounds cannot be admitted by DuckDB; "
                                        "no float fallback."
                                    ),
                                )
                            )
                            output.append(record)
                            continue
                        outlier.update(
                            state="completed",
                            reason=None,
                            count=count,
                            lower=str(lower),
                            upper=str(upper),
                            dispersion=str(dispersion),
                            examples=list(ex),
                            denominator=valid,
                            interpretation=(
                                "Case for investigation; not confirmed error; unscaled MAD or IQR"
                            ),
                        )
                        if count:
                            self.findings.append(
                                Finding(
                                    code="outlier_candidate",
                                    severity="observation",
                                    column=rule.column,
                                    count=count,
                                    denominator=valid,
                                    reason=(
                                        "Outside configured bounds in a comparable group; "
                                        "legitimate extremes remain intact."
                                    ),
                                    examples=ex,
                                )
                            )
            record["outliers"] = outlier
            if outlier["state"] == "not_evaluable" and rule.outliers != "none":
                self.findings.append(
                    Finding(
                        code="outliers_unavailable",
                        severity="not_evaluable",
                        column=rule.column,
                        denominator=valid,
                        reason=str(outlier["reason"]),
                    )
                )
            if not incomparable:
                # Histogram is full-population; bounds/bins use declared float visualization only.
                hist = self.query(
                    f"SELECT b, count(*) FROM (SELECT CASE WHEN ? = ? THEN 0 ELSE "
                    f"least({self.config.resources.histogram_bins - 1}, greatest(0, "
                    f"floor((cast({col} AS DOUBLE)-?) / (? - ?) * "
                    f"{self.config.resources.histogram_bins}))) END b FROM typed "
                    f"WHERE {valid_where}) GROUP BY b ORDER BY b",
                    [
                        float(sums[0]),
                        float(sums[1]),
                        float(sums[0]),
                        float(sums[1]),
                        float(sums[0]),
                        *group,
                    ],
                )
                record["histogram"] = [{"bin": int(b), "count": n} for b, n in hist]
                record["histogram_bounds_approximate"] = [float(sums[0]), float(sums[1])]
                sample = self.query(
                    f"SELECT __ef_eda_row, {col} FROM typed WHERE {valid_where} "
                    f"ORDER BY __ef_eda_row LIMIT {self.config.resources.chart_rows}",
                    list(group),
                )
                record["chart_sample"] = [{"row": r, "value": value(v)} for r, v in sample]
                record["chart_scope"] = (
                    "Deterministic first finite rows in source order; visualization only, "
                    "not representative; all statistics calculated on full group"
                )
            output.append(record)
        return {
            "rule": rule.model_dump(mode="json"),
            "groups_total": group_count,
            "groups": output,
            "state": "not_evaluable"
            if any(r["state"] != "completed" for r in output)
            else "completed",
        }
