# Optional standalone dataset EDA

[Handbook](index.md) · [Outcome gates](outcome-gates.md) · [Compatibility](compatibility.md)

Private Alpha **0.12.0a14** introduced `equiframe.eda`; that subpackage remains
experimental in 0.12.4, separately from the stable comparison/migration interfaces.
It diagnoses one fixed dataset independently of ETL or a migration. It never
changes a plan, tolerance, expected output, detector bundle or publication gate.
Install the identified wheel and its `eda` extra (DuckDB and Arrow),
or `eda-charts` for portable Plotly HTML. No public PyPI release is implied.
Imports remain lazy: importing EquiFrame, EDA contracts or CLI does not import
DuckDB, Arrow, Plotly or the ML engines.

## Python API

```python
from pathlib import Path
from equiframe.eda import EdaConfig, NumericRule, Source, analyze, read_result

result = analyze(
    Source(path="/absolute/input/numbers.parquet", snapshot_id="numbers-v1"),
    config=EdaConfig(numeric=(NumericRule(column="value", outliers="iqr"),)),
    output=Path("/absolute/private-runs/numbers-run-001"),
)
print(result.state, result.reason)  # Inspect each metric's availability as well.
checked = read_result(Path("/absolute/private-runs/numbers-run-001"))
```

Paths above are placeholders, not proof of execution. The supplied synthetic
example uses real generated CSV, independent expected counts and exact money:

```bash
python examples/eda_generic.py --work-dir /absolute/new-private-example
```

The wheel includes `equiframe/examples/integrations/eda_generic.py`; extract
that resource into a fresh project to run it outside the checkout. Files and
reports remain private. Use a new work directory every time.

`analyze_artifact(TableArtifact, config=..., output=...)` reuses a captured
table's SHA/size without making an execution. `analyze_migration(path,
side="source"|"target", config=..., output=...)` first calls the existing verified
migration/bundle reader. It resolves only an inventoried captured output and
records its original evidence identity/state separately. Revalidation precedes
the EDA commit marker. A changed evidence document makes EDA fail; it does not
rewrite the original. Existing index artifacts are not profiled; the link says so.
Standalone ETL input/output files can be diagnosed in separate runs with the
same explicit config. Their profiles are diagnostics, not a second verifier.

## CLI

The same implementation is exposed as `equiframe eda` and `equiframe-eda`:

```bash
equiframe eda run input.parquet --output /private/runs/new-run \
  --snapshot-id snapshot-v1 --expected-sha256 ACTUAL_TRUSTED_SHA \
  --config eda-config.json
equiframe eda inspect /private/runs/new-run
equiframe eda migration /private/migration --side target \
  --output /private/runs/new-migration-eda --config eda-config.json
```

`run`/`migration`: 0 completed diagnostics, 2 invalid configuration/preflight,
3 persisted unavailable/failed/cancelled diagnostics. `inspect`: 0 intact
closed evidence, including stored unavailable results; 3 integrity/read failure.
None of these codes authorizes a DW or establishes equivalence/correctness.
API results reject boolean evaluation. Compare full content through the existing
`diff`/`compare`/Verify APIs and use their explicit assertions/outcomes.

## Original representation and conversion

Parquet and Arrow IPC file snapshots admit scalar representations the initial
backend can preserve; CSV is explicit UTF-8/header/delimiter text, including
empty fields and textual `NaN`. Original names are checked before DuckDB can
deduplicate them. Case-insensitive/reserved-name collisions are rejected.
The MVP admits raw null, boolean, integer, float32/64, string/large string,
date32, naive second/millisecond/microsecond timestamps and decimals with
precision at most 38 and nonnegative scale within precision. Other raw types
(including time, duration, nested/binary/dictionary types, date64, float16,
nanosecond/zoned timestamps and wider decimals) remain explicitly unavailable
because the report/transport cannot preserve those types faithfully.
Timestamp strings remain strings in the raw profile.

`Conversion` creates a new column with original text retained. Decimal requires
plain decimal text within configured precision/scale; excess fraction digits,
overflow and invalid lexemes are counted, never rounded. Integer requires
integral text; date requires ISO date; timestamp requires a valid explicit
offset/Z and at most six fraction digits. Original offsets/text remain intact,
with derived instants in UTC. Blank is invalid unless `empty="missing"` is
declared. No identifiers are converted. Unknown NULL distinctions lost by an
export cannot be reconstructed. `typed.parquet` is a separate derived artifact.

## Meaning of results

Raw profiles distinguish NULL, numeric NaN, empty text, numeric zero and
nonfinite values. Valid excludes NULL/NaN/empty/nonfinite; distinct present
excludes NULL/NaN and retains empty text. Each count/rate records its row
denominator; an empty denominator has no rate. Nonfinite includes NaN, so
these two categories overlap and must not be summed as disjoint populations.
Frequencies are bounded top categories with complete counts, not sampled counts.

Full-row repetitions and declared keys report repeated groups, involved rows,
excess rows and denominator. Key policy includes/excludes/rejects incomplete
NULL/NaN and optionally empty text keys. `require_unique=False` records an
observation: repeated OCID/history is not automatically an error. Nothing is
removed. Examples and zero-based row references are bounded and tied to the
snapshot hash; counts scan the complete table.

`NumericRule` selects a native numeric or explicitly converted column and
comparable groups. Money requires Decimal and text currency grouping; missing
currency groups report unavailable counts without pooling amounts. Group types
are text/bool/64-bit integer/Decimal/finite float; other types are explicit
capability limitations. Groups above `max_groups` are not silently dropped.

Integer/Decimal sum, min/max and **discrete quantiles** are exact. Quantiles use
DuckDB `quantile_disc`, Hyndman–Fan type 1, including the discrete median. Mean
also records the exact sum/count rational for integer/Decimal. Float64 mean,
stddev and visualization/histogram binning are labeled approximate. Population
or sample stddev is explicit. NULL/nonfinite are excluded with counts; failed
conversions are recorded separately. Approximate display never changes money.

IQR uses `[Q1 − multiplier×IQR, Q3 + multiplier×IQR]`; unscaled MAD uses median
± multiplier×median absolute deviation. Bounds are strict: equality is not an
outlier. Support minimum, method and multiplier are recorded. Insufficient
support, zero dispersion, missing comparable group or unrepresentable exact
bound leaves a reason and **count=null**, never zero alerts. Decimal bindings
use the existing typed transport guard; no float fallback for exact money.
Only transient bounds may remove exact trailing zeros to fit native precision.
An outlier remains a case to investigate, including legitimate extremes.

Unavailable requested metrics give run state `not_evaluable` while preserving
calculated quality and available statistics. Failure, cancellation and source
changes remain distinct. A completed run without findings does not prove a
transformation correct. Two different tables can have identical statistics;
two engines can agree on the same error. R/M/B/H/O and model fitting are unchanged.

## Resources and evidence

Source, output, manifest and evidence paths reject symlinks and Windows reparse
points, including directory ancestors, before resolving the path. Source-delivery
members must be normalized relative paths inside that delivery. The delivery
manifest is limited to 16 MiB and 2,000 entries; its trusted SHA-256 identifies
the exact bytes read. These checks do not grant operating-system access or make
this library a sandbox for untrusted callbacks.

`Resources` records memory, threads, timeout, temp spill, input bytes/rows,
columns/groups, top categories, examples, histogram bins and chart rows/bytes.
DuckDB memory controls its buffer manager, not process RSS. Temporary-disk cap
covers DuckDB spill; fixed snapshots, typed files and reports use extra disk.
Byte/row/group caps and callback cancellation are cooperative. A timer
interrupts DuckDB queries; callbacks are checked before/after operations and
chart exports, without promising immediate preemption or hard RSS quotas.

Every exclusive run writes config/source, fixed snapshot, optional typed
Parquet, findings/summary JSON, HTML and a closed hashed manifest. A partial
snapshot is labeled `snapshot_complete=False`. The final manifest is the
commit marker: no readable completed run without it. Publication I/O failure
can leave an interrupted directory that the reader rejects; do not reuse it.
`calculation_elapsed_seconds` and elapsed time through report preparation are
separate; filesystem commit overhead is not a performance guarantee. Report
budgets can produce an unavailable HTML stub with full JSON diagnostics.

HTML embeds Plotly JavaScript locally. Full histograms and quality counts are
distinct from the declared first-finite-row sample used for box/scatter display;
that sample is not representative and its box quartiles are not population
quantiles. Plotly is never required by migration, comparison or Verify.
