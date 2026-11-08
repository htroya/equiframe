"""Native ICU localization with explicit fold/gap policy and exact tick arithmetic."""

from collections.abc import Sequence

from equiframe._timezones import native_timezone_key
from equiframe.errors import CapabilityError


def localize(
    argument: str,
    *,
    unit: str,
    timezone: str,
    ambiguous: str,
    columns: Sequence[str],
) -> str:
    """Enumerate integer-second UTC offsets, validating every native round trip.

    IANA offsets use integral seconds. The IR admits displacement of at most one
    day. Searching that complete interval finds gaps, ordinary instants and all
    valid fold candidates, including historical second offsets and date-line
    changes. No default native ambiguity policy or Python row callback chooses
    the result. A scalar correlated query preserves multiplicity in the caller.
    """
    if unit not in ("s", "ms", "us", "ns") or ambiguous not in ("reject", "earlier", "later"):
        raise CapabilityError("unsupported timestamp localization unit or ambiguity policy")
    prefix = "_equiframe_timestamp_localization_"
    while any(name.casefold().startswith(prefix) for name in columns):
        prefix += "_"

    def name(short: str) -> str:
        return '"' + prefix + short + '"'

    raw, wall, candidates, matches, totals, selected = map(
        name, ("raw", "wall", "candidates", "matches", "totals", "selected")
    )
    tick, microseconds, fraction, offset, instant, count, chosen, result = map(
        name, ("tick", "microseconds", "fraction", "offset", "instant", "count", "chosen", "result")
    )
    factor = {"s": 1_000_000, "ms": 1000, "us": 1, "ns": 1}[unit]
    if unit == "ns":
        # Native // truncates towards zero. Use floor so the residual is 0..999,
        # including negative ticks preceding the Unix epoch.
        micros = f"({tick}//1000-CASE WHEN {tick}<0 AND {tick}%1000<>0 THEN 1 ELSE 0 END)"
        residual = f"({tick}-({micros})*1000)"
    else:
        micros, residual = f"({tick}*{factor})", "0::HUGEINT"
    # Keep both candidate construction and native round trips away from DuckDB's
    # reserved finite/infinite boundaries. Out-of-range localization fails before
    # timezone evaluation; raw timestamp transport does not need this restriction.
    margin = 2 * 86400 * 1_000_000
    lower, upper = -(2**63) + margin, 2**63 - 1 - margin
    zone = "'" + native_timezone_key(timezone).replace("'", "''") + "'"
    chooser = "max" if ambiguous == "later" else "min"
    reject_fold = (
        f"WHEN {count}>1 THEN error('Timestamp localization: ambiguous wall time') "
        if ambiguous == "reject"
        else ""
    )
    encoded = f"({chosen}*1000+{fraction})" if unit == "ns" else f"({chosen}//{factor})"
    return f"""(WITH {raw} AS MATERIALIZED (
      SELECT CAST({argument} AS HUGEINT) AS {tick}
    ), {wall} AS MATERIALIZED (
      SELECT {tick},CASE WHEN {tick} IS NULL THEN NULL
        WHEN {micros} BETWEEN {lower}::HUGEINT AND {upper}::HUGEINT
        THEN CAST({micros} AS BIGINT)
        ELSE error('Timestamp localization: native microsecond range exceeded')
        END AS {microseconds},
        {residual} AS {fraction} FROM {raw}
    ), {candidates} AS MATERIALIZED (
      SELECT make_timestamptz(CAST(CAST({microseconds} AS HUGEINT)-{offset}*1000000 AS BIGINT))
        AS {instant} FROM {wall}
      CROSS JOIN range(-86400,86401) AS {name("offsets")}({offset})
      WHERE {tick} IS NOT NULL
    ), {matches} AS (
      SELECT {instant} FROM {candidates} CROSS JOIN {wall}
      WHERE timezone({zone},{instant})=make_timestamp({microseconds})
    ), {totals} AS (
      SELECT count(*) AS {count},{chooser}(CAST(epoch_us({instant}) AS HUGEINT)) AS {chosen}
      FROM {matches}
    ), {selected} AS (
      SELECT {tick},{count},{encoded} AS {result} FROM {totals} CROSS JOIN {wall}
    ) SELECT CASE WHEN {tick} IS NULL THEN NULL
      WHEN {count}=0 THEN error('Timestamp localization: nonexistent wall time')
      {reject_fold}WHEN {result} BETWEEN {-(2**63)}::HUGEINT AND {2**63 - 1}::HUGEINT
      THEN CAST({result} AS BIGINT)
      ELSE error('Timestamp localization: output tick range exceeded') END FROM {selected})"""
