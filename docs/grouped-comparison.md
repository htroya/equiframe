# Compare numeric amounts by arbitrary groups

[Handbook](index.md) · [API](api.md) · [Semantics](semantics.md)

Available in **EquiFrame 0.13.4**. Install `equiframe[arrow]==0.13.4`, or the
selected `pandas`, `polars` or `duckdb` extra. Optional engines stay lazy.

`compare_grouped` sums one numeric column within each declared key and compares
candidate totals with the right-hand reference. Choose any nonempty set of
grouping columns and any integer, Decimal or finite-float measure. There is no
dependency on SERCOP, procurement data or a particular field name.

```python
from fractions import Fraction
import pyarrow as pa
import equiframe as ef

expected = pa.table(
    {
        "entidad": ["A", "A", "B", "C", "D"],
        "moneda": ["USD"] * 5,
        "monto": [40, 60, 0, 50, 9],
    }
)
candidate = pa.table(
    {
        "entidad": ["A", "A", "B", "C", "E"],
        "moneda": ["USD"] * 5,
        "monto": [90, 60, 25, 50, 7],
    }
)
result = ef.compare_grouped(
    candidate,
    expected,
    by=("entidad", "moneda"),
    column="monto",
)
assert result.modified_group_proportion == Fraction(2, 3)
assert result.maximum_relative_difference == Fraction(1, 2)
assert result.changed_from_zero_groups == 1
assert result.group_coverage == Fraction(3, 5)
assert result.reference_coverage == Fraction(3, 4)
print(result.model_dump_json(indent=2))
```

The same call supports sales with `by=("branch",), column="sales"`, inventory
with `by=("warehouse", "product"), column="stock"`, or expenses with
`by=("department",), column="expense"`. Currency conversion and units are the
caller's responsibility; include currency in the key to keep currencies apart.

## Definitions and denominators

Let **E** be observed reference groups, **C** observed candidate groups, **U**
their union, **I** their intersection, and **V** the common groups with valid
numeric values on both sides. Every row contributes once, including duplicates.

| Field | Definition |
| --- | --- |
| `modified_groups` | Groups in V whose absolute sum difference exceeds the declared tolerance |
| `modified_group_proportion` | modified groups / V |
| `maximum_relative_difference` | maximum `abs(candidate_sum - expected_sum) / abs(expected_sum)` over V with nonzero reference sum, even for differences inside tolerance |
| `zero_baseline_groups` | Groups in V whose reference sum is zero, including sums that cancel to zero |
| `changed_from_zero_groups` | Modified groups among zero-baseline groups |
| `changed_from_zero_proportion` | changed-from-zero groups / zero-baseline groups |
| `added_groups`, `removed_groups` | C minus E, and E minus C; absence is never an assumed zero |
| `group_coverage` | I / U, presence on both sides |
| `comparison_coverage` | V / U, valid numeric comparison support |
| `reference_coverage` | I / E, reference groups represented in the candidate |
| `unavailable_groups` | Common groups with at least one invalid measure |

An empty denominator produces **`None`**, including empty or disjoint inputs.
Zero-to-nonzero changes have no finite reference-relative difference; their
separate count and proportion retain the information. A negative reference uses
its absolute magnitude in the denominator. Reversing inputs can change relative
differences. Missing groups reduce coverage even when all comparable sums agree.

`complete` means all common groups have evaluable sums; it does not require full
group coverage and does not imply acceptance. Inspect coverage, added/removed
groups and availability explicitly. Results reject `bool(result)`.

## Exact arithmetic and tolerances

All sums, differences and ratios use `fractions.Fraction`, including finite IEEE
values exactly as stored. There is no intermediate float, Decimal-context rounding
or fixed-width integer overflow in aggregation. The default comparison is exact.
For example, IEEE `0.1 + 0.2` and `0.3` have distinct exact totals. A descriptive
sum is order-independent and can exceed the input dtype's representable range;
it is not the output of a native engine's SUM operation.

```python
options = ef.GroupedComparisonOptions(
    absolute_tolerance="0.01",
    relative_tolerance="0.001",
    max_examples=10,
)
result = ef.compare_grouped(
    candidate,
    expected,
    by=("entidad", "moneda"),
    column="monto",
    options=options,
)
```

A group is modified when:

```text
abs(candidate_sum - expected_sum)
    > max(absolute_tolerance, relative_tolerance * abs(expected_sum))
```

The boundary is inclusive for agreement; zero-reference changes use the absolute
tolerance. Tolerances must be nonnegative Decimal objects or exact decimal text,
never inferred from the data. They do not affect grouping or raw maximum relative
difference. Tolerances are limited to 1000 integer digits and 1000 decimal places,
checked before rational conversion; larger compact exponents are rejected.
JSON encodes Fractions as strings such as `"2/3"`; restore with
`GroupedComparisonResult.model_validate_json(text)`. Convert ratios with
`float(value)` only when an approximate display is appropriate.
Serialized group numbers admit bounded integer or `numerator/denominator` text,
not scientific-exponent strings. Each text is limited to 4096 characters and
numerators/denominators to 6000 bits, comfortably covering the admitted Arrow
numeric types and their grouped sums/ratios.
The reader accepts reducible fraction text (`"2/4"`) and signed zero (`"-0"`),
then emits reduced canonical text (`"1/2"` and `"0"`). JSON numbers, booleans,
decimal-point text, whitespace and exponent notation are rejected. Python model
construction accepts Fraction objects or the same bounded fraction text.

## Missing values, keys and admission

NULL, NaN and infinite numeric values invalidate the entire group on that side.
They are never skipped, filled with zero or treated as unchanged. Bounded
`examples` preserve distinct issue codes such as `candidate_null`, `expected_nan`
and `candidate_infinity`; an invalid total is `None`. Added/removed examples can
also carry such issues. The numeric column must have a declared numeric dtype,
including in empty and all-NULL tables; booleans and numeric-looking strings are
not measures. Numeric families may differ across sides: their observed values
are compared exactly as numbers, without changing either source dtype.
Decimal columns and keys admit precision up to 76 and scale between zero and
precision, matching the core logical Decimal contract; other scales fail with
`CapabilityError` before scalar conversion.

Grouping keys preserve typed scalar identities and require matching type
signatures on both sides. Arrow string buffer layouts share the string family;
date32/date64 key units must match. NULL keys fail by default; explicitly choose
`GroupedComparisonOptions(null_keys="group")` to group NULL with NULL. NaN and
infinite keys remain rejected. Text, numeric, boolean, date and timestamp keys
retain the admitted capture distinctions; there is no case folding, approximate
key matching or implicit timezone/unit normalization.

Inputs are eager Pandas/Polars DataFrames, Arrow tables, `ArrowInput`, or actual
DuckDB relations. Passing a relation authorizes bounded consumption of that plan;
the caller retains connection ownership. SQL strings, connections, lazy frames,
paths and execution-result objects are not inferred as tables. Reuse `read_table`
and `ArrowInput` explicitly for materialized artifacts. Meaningful Pandas indices
must be promoted to columns. Native metadata, duplicate labels and unsupported
types follow faithful `diff` capture admission.

## Limits and relationship to existing capabilities

`DiffCaptureOptions` limits rows and Arrow bytes per input. Grouped options bound
the group union (default 100,000), retained examples (20), work (10,000,000) and
optional elapsed time. `cancellation` accepts `CancellationToken`. Limits are
cooperative, including native first-fetch/allocations. Resource exhaustion,
cancellation, timeout and unsupported input raise the existing typed errors;
no partial summary is returned as a completed evaluation.

Examples use reference first-observed order, followed by candidate-only groups.
`max_examples=0` hides values without reducing evaluation; `examples_complete`
states whether every union group is present. Examples can disclose keys and
totals: select an appropriate limit before sharing the result.
For shared summaries, explicitly set `GroupedComparisonOptions(max_examples=0)`.
This removes example keys and totals; aggregate counts and metrics still disclose
information. It does not anonymize a dataset or decide whether sharing is safe.

Run the installed `equiframe/examples/grouped_compare.py` resource for four
synthetic recipes (entity/currency, sales, inventory and expenses), each checked
against independent expected values.

This capability is additive. `diff`, `compare`, `assert_equivalent`, existing
contracts, profiles and fitted models retain their meaning. Two tables can have
equal group totals and different rows. Use the existing semantic comparator for
row equivalence. Grouped metrics do not feed rules, Isolation Forest, MAD or the
independent R reviewer automatically, and do not supply an acceptance decision.

## Development resource measurements (2026-10-30)

The development comparison used Windows x86_64 (build 26200), CPython 3.12.4,
Intel64 Family 6 Model 142, Arrow 25.0.1 and Pydantic 2.13.5. Each of 36 cells
compared the preserved initial implementation and the revised readers in three
fresh processes per implementation: 1,000/10,000/100,000 rows per side, 100 or
one group per row, one/three keys, and integer/Decimal/finite-float measures.
Inputs on both sides were equal and `max_examples=0`. Table construction was
outside the timed comparison; process peak RSS includes imports and captures.
The table gives the range of current cell medians across the six key/type
combinations, and their largest observed process RSS, not a guaranteed budget.

| Rows per side | Groups per side | Median seconds, min–max across cells | Largest process peak RSS (MiB) |
|---|---|---|---|
| 1,000 | 100 | 0.203–0.546 | 114.6 |
| 1,000 | 1,000 | 0.266–0.711 | 118.2 |
| 10,000 | 100 | 1.778–4.223 | 118.0 |
| 10,000 | 10,000 | 2.714–5.944 | 159.2 |
| 100,000 | 100 | 25.173–44.839 | 143.4 |
| 100,000 | 100,000 | 30.160–50.348 | 575.7 |

Other QA workloads ran on the host, so timing dispersion matters. Two small
cells initially exceeded a 20% median increase; five alternating repetitions
gave ratios 1.018 and 1.092, with ranges 0.380 and 0.156 seconds for the revised
implementation. This did not reproduce a stable regression above 20%; it does
not establish a universal performance equivalence.

Five repetitions with 1,000 distinct keys containing a 1,024-character suffix
had a 0.291-second median and 124.8 MiB maximum RSS. Five repetitions with 10,000
disjoint groups per side and `max_groups=10_000` all raised `ResourceLimitError`
for the 20,000-group union, with a 2.751-second median and 138.0 MiB maximum RSS.
The union-limit rejection returns no partial successful summary. These synthetic source
measurements do not replace final installed-package checks or imply streaming,
a hard RSS bound, other-platform performance or scientific acceptance.
