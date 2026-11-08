"""Exact Decimal division compiled to native HUGEINT SQL, never DOUBLE."""

from collections.abc import Sequence

from equiframe.errors import CapabilityError


def divide(
    left: str,
    right: str,
    *,
    left_scale: int,
    right_scale: int,
    precision: int,
    scale: int,
    rounding: str,
    columns: Sequence[str],
) -> str:
    """Bound each remainder below the denominator using modular doubling.

    A correlated recursive CTE materializes at most 76 decimal-digit steps.
    Internal names cannot shadow any outer input name, including quoted hostile
    names. Every numerical computation remains a native SQL integer operation.
    """
    prefix = "_equiframe_decimal_division_"
    while any(name.casefold().startswith(prefix) for name in columns):
        prefix += "_"

    def name(short: str) -> str:
        return '"' + prefix + short + '"'

    a0, b0, active, negative = map(name, ("a0", "b0", "active", "negative"))
    a, b, q, r, i, value, dropped = map(name, ("a", "b", "q", "r", "i", "value", "dropped"))
    raw, operands, division, final, rounded = map(
        name, ("raw", "operands", "division", "final", "rounded")
    )
    c2, c4, c8, r2, r4, r8 = map(name, ("c2", "c4", "c8", "r2", "r4", "r8"))
    zero = "0::HUGEINT"

    def doubled(remainder: str) -> tuple[str, str]:
        carry = f"({remainder} >= {b}-({remainder}))"
        result = (
            f"({remainder} - CASE WHEN {carry} THEN {b}-({remainder}) "
            f"ELSE {zero}-({remainder}) END)"
        )
        return carry, result

    k2, rem2 = doubled(r)
    k4, rem4 = doubled(r2)
    k8, rem8 = doubled(r4)
    exponent = scale + right_scale - left_scale
    limit = 10**precision - 1
    initial = f"""{raw} AS MATERIALIZED (
      SELECT CAST(REPLACE(CAST({left} AS VARCHAR),'.','') AS HUGEINT) AS {a0},
             CAST(REPLACE(CAST({right} AS VARCHAR),'.','') AS HUGEINT) AS {b0},
             ({left} IS NOT NULL AND {right} IS NOT NULL) AS {active}
    ), {operands} AS MATERIALIZED (
      SELECT CASE WHEN {active} THEN abs({a0}) ELSE {zero} END AS {a},
             CASE WHEN {active} AND {b0}=0 THEN error('Decimal division: zero denominator')
                  WHEN {active} THEN abs({b0}) ELSE 1::HUGEINT END AS {b},
             {active}, (({a0}<0) <> ({b0}<0)) AS {negative} FROM {raw}
    )"""
    if exponent >= 0:
        body = f""", {division}({i},{q},{r}) AS (
          SELECT 0,CASE WHEN {a}//{b}>{limit}::HUGEINT
            THEN error('Decimal division: output precision exceeded') ELSE {a}//{b} END,
            {a}%{b} FROM {operands}
          UNION ALL
          SELECT {i}+1,
            CASE WHEN {q}>{limit // 10}::HUGEINT
              THEN error('Decimal division: output precision exceeded')
              ELSE {q}*10+{c8}+{c2}+CAST(({r8}>={b}-{r2}) AS HUGEINT) END,
            {r8}-CASE WHEN {r8}>={b}-{r2} THEN {b}-{r2} ELSE {zero}-{r2} END
          FROM {division} CROSS JOIN {operands}
          CROSS JOIN LATERAL (SELECT CAST({k2} AS HUGEINT) AS {c2},{rem2} AS {r2}) {name("t2")}
          CROSS JOIN LATERAL (
            SELECT 2*{c2}+CAST({k4} AS HUGEINT) AS {c4},{rem4} AS {r4}) {name("t4")}
          CROSS JOIN LATERAL (
            SELECT 2*{c4}+CAST({k8} AS HUGEINT) AS {c8},{rem8} AS {r8}) {name("t8")}
          WHERE {i}<{exponent}
        ), {final} AS (
          SELECT {q},{r},{b},{active},{negative} FROM {division}
          CROSS JOIN {operands} WHERE {i}={exponent}
        )"""
        exact = f"{r}=0"
        above = f"{r}>{b}-{r}"
        tie = f"{r}={b}-{r}"
    else:
        factor = 10 ** (-exponent)
        half = factor // 2
        body = f""", {final} AS (
          SELECT ({a}//{b})//{factor}::HUGEINT AS {q},
            ({a}//{b})%{factor}::HUGEINT AS {dropped},{a}%{b} AS {r},
            {b},{active},{negative} FROM {operands}
        )"""
        exact = f"{dropped}=0 AND {r}=0"
        above = f"({dropped}>{half}::HUGEINT OR ({dropped}={half}::HUGEINT AND {r}>0))"
        tie = f"({dropped}={half}::HUGEINT AND {r}=0)"
    if rounding == "exact":
        result = (
            f"CASE WHEN {q}>{limit}::HUGEINT "
            "THEN error('Decimal division: output precision exceeded') "
            f"WHEN {exact} THEN {q} "
            "ELSE error('Decimal division: declared exact scale is insufficient') END"
        )
    elif rounding in ("half_even", "half_away_from_zero"):
        increment = f"({above}) OR (({tie})" + (
            f" AND {q}%2=1)" if rounding == "half_even" else ")"
        )
        result = (
            f"CASE WHEN {q}>{limit}::HUGEINT OR ({q}={limit}::HUGEINT AND ({increment})) "
            "THEN error('Decimal division: output precision exceeded') "
            f"ELSE {q}+CAST(({increment}) AS HUGEINT) END"
        )
    else:
        raise CapabilityError("unsupported Decimal division rounding")
    text = f"CAST({value} AS VARCHAR)"
    if scale:
        text = f"lpad({text},CAST(greatest(length({text}),{scale + 1}) AS INTEGER),'0')"
        text = f"substring({text},1,length({text})-{scale}) || '.' || right({text},{scale})"
    return f"""(WITH RECURSIVE {initial}{body},
      {rounded} AS (SELECT {result} AS {value},{active},{negative} FROM {final})
      SELECT CASE WHEN NOT {active} THEN NULL ELSE CAST(
        CASE WHEN {negative} AND {value}<>0 THEN '-' ELSE '' END || ({text})
        AS DECIMAL({precision},{scale})) END FROM {rounded})"""
