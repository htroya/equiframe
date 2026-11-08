# Semantics, guarantees and limits

[Handbook](index.md) · [API](api.md) · [Security](security.md)

## What equivalence means

`ComparisonResult` evaluates the contract's **output schema** over two captured
results. `equivalent` means a complete scan found no differences or output-contract
violations under the declared policies. It does not prove arbitrary programs
equivalent, validate an entire business process, evaluate operational R rules,
establish an independent expected output, or authorize data publication.

`diff` treats the right side as `expected` by default. `compare` defaults to
`peer`; explicitly pass `reference="expected"` when the right side is your
reference. An invalid expected result yields `not_evaluable`, including when a
scan completed. Two peers can agree on the same incorrect output.

| State | Scan/diagnostic interpretation |
|---|---|
| `equivalent` | Complete evaluation; no differences or violations in scope |
| `different` | Complete evaluation; differences or violations retained |
| `not_evaluable` | Required judgment unavailable; partial findings may remain |

Inspect `state`, `complete`, diagnostics and `counts.final` separately. A complete
scan is necessary but not sufficient for equivalence. Counts from interrupted
scans are partial observations. `difference_records` counts diagnostic records,
not necessarily distinct affected rows. Missing files, failed finalization,
resource exhaustion and exceptions never imply a pass.

Native [windows](migration-ir.md#deterministic-windows) preserve every input row.
Lag/lead retain Decimal precision/scale and units, integer width, timestamp
unit/zone, and the separate NULL/NaN meaning of the input. They introduce NULL
only at partition boundaries; input NULL values also remain NULL. Row-number
output is signed64 and nonnullable. Partition/order ties fail rather than select
an arbitrary original position. Explicit final sorting remains necessary for a
sequence contract. The compiler rejects incompatible declared types/units and
unsupported native plans before execution; comparison does not repair them.

Use `assert_equivalent`, which requires complete/final `observed_contract`
equivalence and any additional policy/evidence requirements. `ComparisonResult`
and `EquivalenceDecision` reject truth testing; use the assertion or the explicit
`.accepted` field. Presentation reports cannot be passed to this gate.

## Explicit contract, conservative inference

The observed physical schema is captured separately from the expected logical
schema. EquiFrame does not silently cast to the expected schema, fill NULL, trim
text, normalize Unicode, deduplicate, reorder or round values to remove a
mismatch. Any allowed equivalence must be declared, justified where required,
and visible in the recorded policy.

Typed contract models are strict and frozen, reject unknown fields and use
explicit tagged scalars. Contract validation checks metadata and cross-field
relationships; it does not evaluate actual tables or execute declared rules.
A valid JSON Schema document alone is not proof of all cross-field constraints.
Use the public validator and the appropriate data/evidence API.

Without an explicit contract, `diff` infers only from the right-hand Arrow
schema after faithful capture. It records provenance, defaults to nullable,
retains NULL separately from NaN and uses exact numbers with unit `unspecified`.
It does not learn tolerance, business keys, money units, non-nullability or
business meaning from samples. `ColumnSpec` overrides are the route to explicit
domain requirements.

## Schema, types and metadata

Default `ComparisonPolicy` is `column_order="significant"`,
`physical_types="exact"`, `index="reject"`. Nonconservative permissions require a
justification. Column names, authorized order, nullability, allowed values,
ranges and granularities are evaluated, even if both inputs violate them in the
same way. Empty tables retain and validate their schema.

"Exact physical types" uses the comparator's documented logical signature:
booleans; integer width/sign; float width; decimal precision/scale; strings;
dates; timestamp unit/timezone. Arrow string, large_string and string_view
represent the same string family; decimal128/256 of identical precision/scale
represent the same decimal; date32/date64 represent days, with whole-day checks.
This is not native dtype identity or arbitrary metadata equality.

`physical_types="lossless"` permits checked representable variations **within**
a family: integer width/sign, exactly representable float narrowing and exact
Decimal rescaling/range. It does not equate integer, float, Decimal and string.
An Arrow null-typed column needs explicit lossless permission and a nullable
contract to specialize. The expected domain is not invented.

Direct `diff` capture rejects uninterpreted Arrow field/schema metadata,
meaningful unsupported pandas metadata, categories, heterogeneous object cells,
unsupported subclasses and undeclared dtype metadata. Rejection is preferable
to asserting an equality that erased a distinction. Existing artifact routes
retain their own documented admission; wrapping an input does not expand it.

## NULL, NaN, zero and text

NULL, NaN, empty text and numeric zero remain distinct unless `NullPolicy` or
`NaNPolicy` explicitly authorizes an equivalence. Such permissions do not add
missing-value distinctions absent from the original representation.

- NaN `forbid` is a violation; `distinct` is a category distinct from NULL and
  numbers; `as_null` needs the declared nullable/equivalence policy
- NaN payload/signaling distinctions are not compared
- Positive and negative float zero have equal numeric value; evidence retains
  the observed sign. This is not bitwise floating-point identity
- Text remains exact: no trimming, case folding, Unicode normalization,
  accent/collation inference or removal of leading identifier zeroes
- A NumPy float column cannot recover None versus NaN already collapsed before
  EquiFrame sees it. Separate Arrow masks or suitable admitted representations
  can preserve distinctions that still exist

## Decimal, units and approximation

Decimal comparison uses exact rational arithmetic, never an intermediate float
or the consumer's mutable Decimal context. Declared precision/scale, units and
engine capabilities matter. A rounding policy describes the intended
transformation; it does not authorize repairing a result during comparison.
Currency conversion is not inferred. A declared unit absent from the actual
data cannot be empirically recovered from a number alone.

For integer/float measures with an explicitly fixed tolerance:

```text
abs(a - b) <= max(absolute or 0, (relative or 0) * max(abs(a), abs(b)))
```

The formula is symmetric and inclusive. Finite IEEE values and decimal-textual
tolerances are evaluated exactly as rationals. Infinities match only the same
sign, and NaN follows its separate policy. Decimal remains exact. Tolerances are
not estimated from the pair and do not define keys, uniqueness or ordering.
Approximate equality is not transitive.

Exact multisets count complete canonical values. Approximate multiset matching
uses bounded maximum matching to preserve occurrences; it is not a greedy
nearest-row heuristic. Work, candidate-pair and matching-memory limits can make
a case `not_evaluable`. Hashes partition work or verify bytes; hash equality
alone never substitutes for exact value comparison.

## Keys, duplicates and order

All declared keys are checked before and after authorized normalization. A
columns-scoped key includes its scope columns; table/global key scope covers the
compared output, not all external tables or future snapshots.

When row order is ignored, the first declared unique key is eligible for
alignment only after uniqueness and completeness are verified on both sides.
Otherwise the complete multiset is compared and key violations remain visible.
There are no approximate keys. `incomplete="allow"` retains incomplete rows and
excludes them from uniqueness checking; it does not fabricate identity or drop
those rows. Duplicate keys cannot be "fixed" by selecting the first occurrence.

`multiplicity="preserve"` counts every occurrence. `"distinct"` is a requirement
that normalized rows do not repeat, not permission to deduplicate. Without
verified identity, a report describes excess occurrences instead of inventing
modified business rows.

`SignificantOrder` compares sequence and validates the declared sort columns,
direction, NULL placement and ties. `ties="preserve"` retains observed relative
order; `ties="reject"` disallows ties. No sort repairs an output during comparison.
A pandas index is not automatically a key. A trivial unnamed
`RangeIndex(0, n, 1)` is not business identity; meaningful indices need promotion
to explicit columns or an explicit justified exclusion policy.

## Time and capture fidelity

Dates are whole days. Timestamps retain integer epochs and physical precision,
including nanoseconds, without a float or Python datetime rounding step.
`instant` and `wall_time` are separate policies. Changing timezone requires the
appropriate lossless/instant policy; local time requires the declared zone.
Naive timestamps can be preserved, rejected or interpreted using the declared
zone and DST policy. Nonexistent local DST times are violations; calendar/zone
operations outside the supported year range are not evaluated.

Contract timezone logic uses Python `tzdata`. General native transformations
use the provider available to their engine: pandas' input provider, Polars'
compiled provider, or DuckDB's ICU. Compiler-generated IR `LocalizeTimestamp`
in Polars instead reads the installed TZif metadata and evaluates its transition
rules with native Polars expressions. Resource hashes participate in the
compilation identity, and a resource changed before execution is rejected.
EquiFrame does not assume all providers share an IANA version. Engine, runtime,
resource and configuration facts remain explicit; tested agreement has a finite
scope and does not establish identical timezone databases.

Arrow does not retain each row's original ISO text/offset, negative Decimal zero
or distinct Decimal exponents within a fixed-scale column. Store those required
facts as explicit columns **before** they are lost. EquiFrame does not reconstruct
them after conversion.

## Capture, execution and migration are different capabilities

| Route | Admitted scope and important rejection |
|---|---|
| Direct `diff` | Eager pandas/Polars DataFrames, Arrow tables and explicitly supplied DuckDBPyRelation objects; relation submission authorizes bounded materialization; no inferred SQL strings, connections, Polars lazy plans or consumable readers |
| `compare` | `ArrowInput`, local `ArtifactRef`, local Arrow IPC file/Parquet `Path`, `TableArtifact`, completed `ExecutionResult` |
| Native pandas | Admitted scalar bool, integers, text, floats, decimals and temporal types; unsupported metadata/object/category cases rejected |
| Native Polars | Decimal precision at most 38 and nonnegative scale; date32; seconds promoted to milliseconds only when representable |
| Native DuckDB | Faithful admitted native types; decimals at most precision/scale 38; zoned timestamps limited to representable microseconds |
| Declarative migration | Bounded typed relational IR over each engine's genuine native implementation |

Native transport excludes dictionaries/categories, nested tabular values, binary,
arbitrary objects and Arrow streams. Capture support does not imply that every
native transformation supports every admitted type. Consult
`get_adapter_capabilities()` for stage-specific conditions and known losses.

DuckDB HUGEINT/UHUGEINT, UUID/ENUM and other types without declared faithful
mapping are rejected before Arrow conversion; temporal infinities and zoned
nanosecond timestamps are also rejected. Decimal SQL parameters are bound with
exact checked precision/scale. Nonfinite Decimal, negative zero, positive
exponent, excessive precision/scale and integers outside signed/unsigned 64-bit
range are rejected. A consumer-chosen explicit cast requires a justified
representable domain; EquiFrame never inserts it to make results match.

The migration IR includes Scan, Project, Filter, exact Cast, EquiJoin,
Aggregate, Sort, Concatenate and Deduplicate, with closed typed expressions
including Arithmetic, Coalesce and Conditional. It has explicit NULL-join,
NULL-group, empty-sum, tie and multiplicity policies. It does not translate
arbitrary Python/SQL. Its common decimal precision is at most 38. Right/full joins, matchable-key
cardinality, deterministic key deduplication, exact Decimal multiplication,
declared rounding/division and timestamp transport/localization have the
[per-engine contracts and bounds](migration-ir.md). Float join/group/order
keys and float SUM/min/max remain outside this IR.
`count_valid` can admit float. Native admission can reject a mathematically safe
case conservatively, for example a Polars sum with cancelling large terms.

Arithmetic `overflow="reject"` applies to every intermediate expression, even
when a later expression would cancel its value or produce a boolean or NULL.
Pandas and Polars evaluate those checks eagerly. DuckDB compiler v8 and its
native adapter consume each fallible expression and relational node at an
in-memory native checkpoint before a containing predicate or later operation
can prune it. The [checkpoint contract](migration-ir.md#eager-failures-and-historical-evidence)
defines adapter admission, resource checks and the remaining common IR limits.
No fallback or lossy cast supplies an answer.

`check_migration` checks both compilers without reading inputs or loading engines.
`migrate` captures the same inputs once and executes two native pipelines. The
optional expected output is separate and never feeds the transformations,
profiles or detectors. `require_rules=False` is an explicit change of requested
scope, not proof that R passed; child pipeline states and partial alerts remain.

## Evidence, privacy and execution limits

- Capture and comparison retain snapshots and full differences subject to budgets.
  A report example limit does not reduce evaluation coverage
- Default comparison reports hide values, names and paths. Optional disclosure
  must be deliberate. Redacting a view does not erase the raw evidence directory
- `read_comparison` validates the manifest; `iter_differences` verifies the
  difference file's size/hash while reading it. Other readers have their own
  closed-inventory and semantic checks; they are not interchangeable
- Report `diagnostic`, `detail` and `reproduction` modes offer different evidence.
  Reproduction exports supported materialized inputs, not original transformations
  or external services. `require_exhaustive` is independent of shown example count
- Hashes identify bytes relative to a trusted reference. They do not authenticate
  authors/reviewers, prove expected-output correctness or certify a dependency safe
- Local files require a suitable filesystem, including exclusive atomic hard-link
  publication where used. Publication failures can raise and leave partial files
- No API guarantees a report after process kill, disk failure or host OOM. CI must
  fail closed on missing finalization or abnormal termination
- Core time, memory, row, disk and work checks are cooperative. Native allocations
  may precede checkpoints. DuckDB engine limits are not total-process RSS quotas
- Callbacks, registered plugins, SQL and model-related integrations must be trusted.
  EquiFrame is not a sandbox or a service concurrency/security controller

See [performance](performance.md), [security](security.md) and
[upgrading](upgrading.md) for operating and recovery procedures.

## Rules and anomaly signals are not equivalence

R evaluates declared rules over one execution; M is Isolation Forest; B is MAD;
H is R OR M; O is independent expected-output/review evidence. They remain
separate. Profiles and detectors do not receive labels, mutations or another
engine's output. Fitting, calibration and inference are distinct operations.

An unavailable component is `not_evaluable`, never `no_alert`. H retains an alert
from either R or M even if the other component is unavailable, while marking
coverage incomplete. With no alert and an unavailable component, H is not
evaluable. B does not participate in H. Empty rules do not establish R coverage.
A low anomaly score or `no_alert` is not an equivalence gate or load authorization.
