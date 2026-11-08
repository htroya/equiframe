# Native relational contracts

[API](api.md) · [Semantics](semantics.md) · [Compatibility](compatibility.md)

These additions were introduced experimentally in 0.12.0a1 and retained in
0.12.0a14. Their admitted public semantics join the stable 0.12.0
`RelationalPlan` and `migrate` contracts. They do not infer business rules, change comparison policy,
translate arbitrary code, or calculate one output for conversion into other
engines. Every supported compiler executes its own native transformation.
The tests use independently specified literal expectations; dated receipts
preserve failed attempts and separately establish installed-artifact
validation. See the existing `get_adapter_capabilities()` and
`get_stability_register()` records, not a second capability catalogue.

## Literal column names

Column references and output names are exact, case-sensitive strings. A name
such as `*`, `^a$`, a dotted name, or a name containing quotes is a literal
column name, never a wildcard, regular expression, or SQL expression. Input
names, projected aliases, group keys, join keys, sort keys, and deduplication
keys obey the same rule. Names and column order are preserved; a missing name
is rejected by IR validation rather than expanded into matching columns.
Backends may use temporary internal names to execute a native operation, but
these do not appear in captured output. Existing `Text` validation, name
uniqueness and engine-specific identifier limits still apply: for example,
DuckDB rejects NUL names and case-insensitively colliding names. This contract
does not relax those boundaries or the separate table-identifier restrictions.

## Deterministic windows

The admitted `Window` node appends `WindowMeasure` outputs to every input
row. `row_number` starts at 1 in each partition, or in the entire input when
`partition_by=()`. `lag` and `lead` select the preceding/following row at a
positive `offset` (default 1), retaining its exact logical type and unit.
They return NULL outside the partition and preserve NULL values inside it.
No arithmetic, rounding, default fill or NULL skipping occurs.

```python
window = ef.Window(
    node_id="history",
    source="events",
    partition_by=("account",),
    by=(ef.SortKey(column="sequence", direction="ascending", nulls="last"),),
    measures=(
        ef.WindowMeasure(
            name="position",
            operation="row_number",
            logical_type=ef.IntegerType(bits=64, signed=True),
            unit="rows",
        ),
        ef.WindowMeasure(
            name="previous_amount",
            operation="lag",
            column="amount",
            logical_type=ef.DecimalType(precision=12, scale=2),
        ),
    ),
)
```

NULL partition components group together. Every ordering term declares its
direction and NULL position; partition-plus-order tuples must be unique.
`ties="reject"` rejects even identical tied rows, so input order cannot choose
an arbitrary predecessor. Float partition/order keys remain unsupported.
`row_number` requires signed64, nonnullable output; lag/lead output is nullable
even for a nonnullable input. Row multiplicity remains unchanged. Output bag
order is unspecified until a final `Sort` requests it.

Each compiler uses its own native operations. DuckDB materializes the checked
window before executing later filters/projections, so they cannot prune its
error guard. See the eager checkpoint contract below.
Arbitrary frames, rank/dense_rank and window aggregates remain unsupported.
The additions extended the IR and nested migration/workflow schemas; historical
node defaults remain unchanged. IR/migration contracts are stable in 0.12.0;
standalone workflow orchestration retains its separate experimental status.

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

## Exact integer operations

Integer `add`, `subtract` and `multiply` accept signed and unsigned 8/16/32/64-bit
operands of identical type with matching explicit units. The declared integer
output must contain the actual result; overflow and unsigned underflow fail.
NULL operands propagate. Integer division remains unsupported.

Pandas operates on native object-backed integer Series, DuckDB widens operands
to native HUGEINT and checks its final cast, and Polars uses exact native
Decimal(38,0) coefficients. Polars proves a bound before multiplying because
UInt64 squared can exceed both signed Int128 and Decimal128. Every integer
result is checked against its exact destination bounds before the native cast.
No floating intermediate or cross-engine result fallback is used. DuckDB checks
each nested arithmetic expression before a containing predicate or later node.

## Exact Decimal operations

`Arithmetic(operation="multiply", left=..., right=..., logical_type=..., unit=...)`
admits Decimal operands with potentially different declared precision/scale.
The result scale must equal the sum of operand scales, at most 38; each operand
precision must be at most 38. Each actual intermediate result must fit its declared
precision. There is no implicit rounding. The explicit result `unit` declares
the intended product unit; the compiler does not infer dimensional algebra.
Existing add/subtract retain identical types/units, scale and a guard digit.

Polars multiplies native Decimal(38,0) coefficients and reconstructs the declared
summed scale with native string kernels. Before multiplying it checks each
non-NULL coefficient pair against `floor((10**precision - 1) / abs(right))`.
Zero and NULL operands are handled explicitly. The proof precedes native
multiplication, so valid large products are admitted without overflowing a
scaled intermediate. No float intermediate or Python row callback is used.

```python
rounded = ef.DecimalRound(
    argument=ef.Column(name="amount"),
    logical_type=ef.DecimalType(precision=12, scale=2),
    rounding="half_away_from_zero",
)
```

`DecimalRound` requires a Decimal argument and an output scale no greater than
its input scale. It preserves the argument's unit and NULL values. Overflow
rejects. `half_away_from_zero` and `half_even` are supported by all three
compilers. DuckDB uses exact HUGEINT coefficient division for half-even rather
than its floating `round_even` function. Rounding is a requested transformation,
never a comparison repair.
Fixed-scale Arrow output does not preserve a signed zero representation.

`Arithmetic(operation="divide", ..., logical_type=DecimalType(...), unit=...,
rounding="exact" | "half_even" | "half_away_from_zero")` uses independent
native implementations in all three engines. Pandas uses isolated Decimal
arithmetic; Polars uses native Decimal(38,0) coefficient arithmetic with Int128
quotient/remainder kernels, and DuckDB uses native HUGEINT
SQL quotient/remainder steps. `exact` is the default and rejects any
nonrepresentable quotient at the declared scale, including recurring fractions.
The explicit rounding modes quantize to the declared scale. A non-NULL
zero denominator fails; NULL operands propagate without evaluating a division
by zero. Integer division is unsupported. Polars and DuckDB support Decimal
coefficients through precision 38. Modular doubling keeps each remainder below
its denominator without an overflowing multiplication by ten; scale adjustment
takes at most 76 native digit steps. No FLOAT/DOUBLE intermediate, Python row UDF
or common-result fallback is used. DuckDB materializes each fallible expression
before a containing expression or later relational node can discard it.
Large inputs and scales can require
substantial working memory/time; cooperative budgets are not hard RSS quotas.

## Timestamp transport and DST localization

`TimestampType(unit=..., timezone=...)` is admitted in IR columns with the
existing matching `TimestampPolicy` on their input/output contracts. Units are
physical `s`, `ms`, `us` and `ns`. Transport does not silently change unit/zone:

All three compilers transport all four units with naive or named-zone timestamps.
Polars and DuckDB IR transformations explicitly encode timestamps as unchanged
signed int64 ticks before native execution and restore their unit/zone metadata
through Arrow buffer views. A decoder requires actual int64 output; it never
casts floats or incorrectly typed output to fit a contract. Each engine still
executes its own operations. The codec is not a common ETL result or an implicit
comparison repair. Native input/output types and the encoding are recorded.

This encoding belongs to compiler-generated IR transformations. General trusted
callbacks/SQL keep their existing native unit, zone, range and infinity-sentinel
restrictions. Non-NULL timestamp literals, calendar arithmetic and implicit
zone/unit conversion have not been added.

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

The implementations remain independent: pandas uses its native datetime route,
Polars computes UTC candidates with native expressions from the installed
`tzdata` TZif metadata, and DuckDB uses native ICU round trips. The Polars
compiler records the exact resource hashes in its compilation identity and
rejects a resource changed before execution. Explicit transition intervals and
POSIX continuation rules retain historical second offsets, negative daylight
adjustments and fractional-hour zones. Only timezone metadata is read in Python;
table rows, candidate counts and fold selection stay in Polars. Gaps, rejected
folds and output overflow remain errors, including inside a branch or filter.

DuckDB
enumerates every integral-second UTC offset within the IR's maximum one-day
displacement, counts matching instants and applies the requested policy. Integer
quotient/remainder preserves nanosecond residuals, including negative ticks.
The search includes half-hour folds, historical second offsets and skipped days;
it does not accept ICU's default fold/gap choice without checking it.

pandas rejects an int64-min localization input because its datetime route
reserves that tick for NaT. Polars seconds localization uses a checked native
millisecond view and rejects if it cannot preserve the value exactly. Polars and
pandas check NULL masks and tick displacement in an overflow-safe numeric domain
before a containing predicate can prune a bad value. DuckDB guards its native
microsecond calendar range with a two-day margin and checks final int64 ticks;
its search itself bounds displacement to one day. These localization limits do
not narrow raw IR tick transport. Native range exceptions remain failures.

DuckDB materializes the localized ticks before a containing predicate or later
relational operation. Searching 172,801 offsets per correlated scalar evaluation can
be expensive for many distinct wall times; the query uses the configured memory,
threads and cooperative interruption limits. Those limits are not a hard total
RSS quota. Provider/version differences remain recorded: agreement on tested
dates does not prove identical IANA databases in all engines.

Polars compiler `product-semantics-v13` adds this TZif route after a revised
Colombian transition in `tzdata` differed from the bundled Polars timezone
provider. General Polars callbacks still use their own provider. Updating
`tzdata` requires revalidation of affected plans; previous wheel results and
finite campaign coverage do not transfer automatically to a new artifact.

## Eager failures and historical evidence

DuckDB compiler v8 produces a private program of native SELECT checkpoints.
The native adapter consumes each node's entire declared output into Arrow
before registering it for subsequent nodes. It also evaluates nested arithmetic,
rounding and localization from the innermost expression outward, before a
containing predicate can simplify them. Later filters, projections, joins and
aggregations therefore cannot hide overflow, forbidden ties or cardinality
errors. Joins and deterministic deduplication retain a separate error-producing
guard branch, including when the native result is empty.

These Arrow tables are in-memory transport from DuckDB back into the same
private DuckDB connection. No result comes from another engine, Python row UDF
or a shared database. A native ordinal preserves observed row order across
scalar expression kernels; join/group/window order remains unspecified until
`Sort`. Relations are released after their last consumer, including shared
branches. The connection closes on success, failure, cancellation or timeout.

Each materialized intermediate observes the cooperative Arrow byte budget and
checks cancellation/time; final row limits apply to the final output. Helper
columns can increase working memory and native checkpoint calls add overhead.
These checks are not a total process RSS cap or a hard deadline. DuckDB's
[order-preservation rules](https://duckdb.org/docs/current/sql/dialect/order_preservation)
explain why expression checkpoints explicitly restore their native ordinal.

Compiler-generated programs require `DuckDBAdapter` or an implementation that
retains that native adapter's program execution. An unrelated adapter is
rejected before resolving a provider. Replaying only the program's `.sql`
fails explicitly; it cannot bypass the checkpoints. Ordinary registered trusted
`DuckDBTransformation` SQL keeps its single SELECT/WITH interface. This changes
the private compiled IR implementation, not serialized IR/result formats or the
stable admitted semantic contract.

Fallible expressions inside `Coalesce`, `Conditional` or boolean short-circuit
forms still require preceding projected checkpoints in the common IR validator.
Integer division, conservative numeric bounds and the type/zone limits above
remain explicit. Pandas and Polars perform their own native checks. Pandas
both-empty full joins preserve an explicit typed empty frame. DuckDB Decimal
multiplication promotes each operand to precision 38 at its own scale before
multiplying; an outer result cast alone would overflow a DECIMAL(18)
intermediate for valid large inputs.

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
