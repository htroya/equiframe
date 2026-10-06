# Native relational contracts

[API](api.md) · [Semantics](semantics.md) · [Compatibility](compatibility.md)

These experimental additions in 0.12.0a1 extend the existing `RelationalPlan`
and `migrate` APIs. They do not infer business rules, change comparison policy,
translate arbitrary code, or calculate one output for conversion into other
engines. Every supported compiler executes its own native transformation.
The executable literal expectations were written and run failing before the
implementation; installed-artifact receipts separately establish distribution
validation. See the existing `get_adapter_capabilities()` and
`get_stability_register()` records, not a second capability catalogue.

## Outer joins and cardinality

```python
join = ef.EquiJoin(
    node_id="joined",
    left="old",
    right="new",
    keys=(ef.JoinKey(left="id", right="id"),),
    how="full",
    null_keys="never",
    cardinality="one_to_one",
)
```

`how` admits `inner`, `left`, `right`, `full`, `semi` and `anti`. Joins preserve
all matching occurrences. Outer joins preserve unmatched occurrences on their
respective sides; the absent side has NULL in **every** column. Both original
key columns remain, with `right_prefix="right."` on the right. There is no
implicit coalescing. The output contract must include both sides except for
semi/anti joins, which retain only left columns and left multiplicity.
Unmatched sides must be nullable in the output contract.

`cardinality` describes uniqueness of the **input matchable key tuples**:

- `one_to_one`: both sides unique
- `one_to_many`: left unique
- `many_to_one`: right unique
- `many_to_many` (historical default): neither side required unique

With `null_keys="equal"`, NULL components compare as equal and participate in
uniqueness. With `"never"`, a tuple with any NULL component cannot match and is
excluded from cardinality uniqueness checks; it is still retained where outer
join semantics require it. A duplicate matchable key violates the declaration
even if the other input is empty or contains no matching key. Violations fail
execution, rather than producing a successful empty result. This declaration
is technical input cardinality, not an inferred business relationship.

## Deterministic selection by key

```python
selection = ef.Deduplicate(
    node_id="latest",
    source="events",
    keys=("event_id",),
    keep="first",
    by=(ef.SortKey(column="revision", direction="descending", nulls="last"),),
)
```

The existing `keep="identical"` still requires every column in `keys` and
forbids `by`. The new `keep="first"` requires a nonempty `by` tuple. Sort
semantics are applied within each key group, then exactly one row is selected.
NULL keys group together (`nulls="equal"`); each sort term explicitly declares
direction and NULL placement. The key-plus-sort tuple must be unique:
`ties="reject"` rejects all remaining ties, including identical tied rows.
No original input order or engine-dependent arbitrary first row resolves ties.
Input permutation therefore preserves the selected bag. Output sequence is
unspecified unless a final `Sort` establishes the order required by the contract.
Float key/tiebreak columns remain unsupported.

## Exact Decimal operations

`Arithmetic(operation="multiply", left=..., right=..., logical_type=..., unit=...)`
admits Decimal operands with potentially different declared precision/scale.
The result scale must equal the sum of operand scales; the sum of operand
precisions must be at most 38. Each intermediate result must fit its declared
precision. There is no implicit rounding. The explicit result `unit` declares
the intended product unit; the compiler does not infer dimensional algebra.
Existing add/subtract retain identical types/units, scale and a guard digit.

Polars additionally requires the sum of both operand precisions **and scales**
to be at most 38. Its native multiplication uses the largest input scale;
EquiFrame promotes scale before multiplication and proves a conservative
coefficient bound so fractional digits are not silently truncated. A safe
calculation outside that bound remains explicitly rejected.

```python
rounded = ef.DecimalRound(
    argument=ef.Column(name="amount"),
    logical_type=ef.DecimalType(precision=12, scale=2),
    rounding="half_away_from_zero",
)
```

`DecimalRound` requires a Decimal argument and an output scale no greater than
its input scale. It preserves the argument's unit and NULL values. Overflow
rejects. `half_away_from_zero` is supported by all three compilers; `half_even`
is supported by pandas and Polars and explicitly rejected by DuckDB's exact
Decimal path. Rounding is a requested transformation, never a comparison repair.
Fixed-scale Arrow output does not preserve a signed zero representation.

`Arithmetic(operation="divide", ..., logical_type=DecimalType(...), unit=...,
rounding="exact" | "half_even" | "half_away_from_zero")` is implemented by
pandas with isolated Decimal arithmetic. `exact` is the default and rejects any
nonrepresentable quotient at the declared scale, including recurring fractions.
The explicit rounding modes quantize to the declared scale. A non-NULL
zero denominator fails; NULL operands propagate without evaluating a division
by zero. Integer division is unsupported. Polars and DuckDB reject Decimal
division at compilation: their current native routes cannot honor this contract
(the DuckDB operation produces DOUBLE). No Python UDF or common-result fallback
is substituted for those native operations.

## Timestamp transport and DST localization

`TimestampType(unit=..., timezone=...)` is admitted in IR columns with the
existing matching `TimestampPolicy` on their input/output contracts. Units are
physical `s`, `ms`, `us` and `ns`. Transport does not silently change unit/zone:

- pandas: all four units, naive or named-zone timestamps
- Polars: `ms`, `us`, `ns`; seconds rejected rather than silently promoted
- DuckDB: naive timestamps in all four units, or zoned `UTC` microseconds only

Other DuckDB session zones, zoned units and native infinity sentinels retain
explicit rejection. These are migration limits; general capture/execute may
have different capabilities. Non-NULL timestamp literals, calendar arithmetic and
implicit zone/unit conversion have not been added.

```python
localized = ef.LocalizeTimestamp(
    argument=ef.Column(name="local_time"),
    timezone="America/New_York",
    ambiguous="earlier",
    nonexistent="reject",
)
```

`LocalizeTimestamp` interprets a **naive** timestamp as local wall time in the
named IANA zone, preserving its physical unit and NULLs. The output contract
must declare that zone and the same unit. `ambiguous="reject"` rejects a fold;
`"earlier"` and `"later"` choose the earlier/later UTC instant, independent of
whether a provider labels an offset as daylight time. Gaps always reject;
`nonexistent="reject"` is the only admitted value. Already-zoned input is
rejected: conversion between zones is a different operation.

pandas and Polars implement localization independently. DuckDB rejects it at
compilation because its native localization does not enforce the requested fold
and gap policy. pandas additionally rejects an int64-min input to localization because its
native datetime representation reserves that tick for NaT. Both implementations
check every localization's input/output NULL mask and tick displacement in an
overflow-safe numeric domain. Any displacement larger than the maximum one-day
timezone offset is rejected, so a wrapped native timestamp cannot become a
successful date centuries away. This guard also applies before a containing
predicate could hide the bad value. Native exceptions at other range limits
remain failures. Provider/version differences remain recorded limits; agreement
on tested dates is not proof that all providers have identical IANA databases.

## Eager failures and historical evidence

DuckDB's optimizer can prune a failing intermediate computation. Therefore
checked cardinality joins and `keep="first"` deduplication, like checked
arithmetic/aggregates/sorts, can only be final or followed by `Sort` nodes.
The SQL has a separate error-producing guard branch so even empty join results
cannot hide violations. Pandas both-empty full joins preserve an explicit typed
empty frame rather than passing zero-chunk Arrow columns to native factorization.
DuckDB Decimal multiplication promotes each operand to precision 38 at its own
scale before multiplying; an outer result cast alone would overflow an inferred
DECIMAL(18) intermediate for valid large inputs. Unsupported placements fail compilation. pandas and
Polars perform their own checks during native execution.

Format 1.0 readers remain compatible. Newly added historical defaults
(`many_to_many`, `rounding="exact"`, empty dedup `by` and its fixed tie policy)
are omitted from serialized old-shaped nodes, preserving existing IR and full
specification fingerprints. Nondefault new options and new expression kinds
are serialized and fingerprinted. New compiler implementations use new code
identities; old stored identities are not recomputed or rewritten.

The finite new technical matrix explicitly covers the 144 combinations of six
join kinds, four cardinalities, two NULL policies and three engines on one
composite-key fixture, plus 24 engine/unit/zone timestamp transport cells and
separate literal/migration/overflow/DST/permutation cases. It is not exhaustive
over all types, timezones, numeric values, plans, directions or interactions.
The semantic matrix records source execution separately from final installed
artifact results; neither establishes thesis outcomes or business truth.
