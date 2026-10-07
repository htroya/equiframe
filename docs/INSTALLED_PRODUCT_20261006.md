# Installed general-purpose product candidate

## Identity and scope

This work starts from the freshly verified main commit
`f288cc353e36c33c89c04e6dd132eb1d200510b4`, tree
`7982eecdc6a3ab92436d3ed812c191a3429d878b`. The isolated work branch is
`product/installed-consumer-20261006`. The current private alpha pair is core `0.12.0a5` and benchmark `0.12.0a5`;
the benchmark retains an exact dependency on that core. Both distributions
identify the core correction for literal native Polars column names and retain
the previously corrected integrity-reader control boundaries. Earlier artifacts,
consumer runs and source/installed suites are retained as historical evidence;
current receipts identify the new source and artifact bytes independently.
The former 3,083 core / 561 benchmark / 16 root tests and twelve Linux cells are
historical evidence, not results for this candidate.

The consumer-lab is a separate packaged application, not an EquiFrame module or
another orchestration platform. Its frozen public datasets and execution evidence
stay outside this Git repository. No production or TestPyPI publication, main
merge, deployment, workflow dispatch, license choice or scientific acceptance is
implied. Existing GitHub workflows remain manual.

## Product objectives, separate from thesis methodology

General product objective: provide a reusable Python library that verifies,
reconciles and explains complete tabular outputs under explicit contracts for
values, types, keys, multiplicity, order and time, with reproducible installation
and independently checkable evidence.

Measurable engineering objectives:

1. Install the exact candidate with ordinary pip dependency resolution from a
   private wheelhouse into fresh external environments, covering base and each
   declared extra, and prove the imported files match the wheel
2. Execute independent consumer programs for reconciliation, refactoring,
   migration/ETL and preparation over at least three permitted real datasets from
   different domains, preserving provenance and distinguishing controlled defects
3. Add contract-first native relational capabilities, test independent expected
   results and all six engine directions where admitted, and reject unsupported
   precision or temporal behavior explicitly
4. Reduce redundant CSV/JSONL materialization while preserving original source
   bytes, positions, exact conversion/quarantine receipts and atomic publication
5. Inventory every declared public surface and discrete option, and expose the
   executed, rejected, blocked and untested obligations with explicit denominators
6. Keep complete evaluation, equivalence, expected-output correctness, component
   evaluability and evidence integrity separate in reports and acceptance gates

These are product objectives. They do not change the thesis families, nine
principal strata, partitions, statistical protocols, R/M/B/H/O independence or
requirements for real reviewers. No methodological change is necessary merely
to add a library feature; historical scientific records remain unchanged.

## Code-grounded diagnosis and ordered work

| Capacity | Existing evidence | Limit/classification | User impact | Priority | Change | Acceptance |
|---|---|---|---|---|---|---|
| Packaging and extras | Prior wheel/sdist verifiers, external recipes, exact dependency locks | New artifact not identified by old version/tests; release ownership and license unresolved | A source pass can conceal a broken installation | A | Distinct alpha version, normal-resolver private wheelhouse, independent builds and installed proof | Exact wheel/sdist, pip check/report, site-packages byte identity and clean consumer |
| Public discovery | Existing stability/capability registers and 351 core exports in base | Per-field/default/option behavior not exhaustively mapped | Undefined coverage denominator | A | Derive auditable installed option inventory and missing obligations from those registers | Every item classified; never label introspection as a behavior pass |
| Ordinary comparison | diff, common reports and explicit assertions already implemented | Advanced options need clear progression; completeness is not acceptance | Misinterpreting an error or caught rejection | B | Small executable route and finite risk matrix with literal expected values | Differences persist before gate rejects; optimized Python cannot bypass gate |
| Joins | Native inner/left/semi/anti with NULL and multiplicity contracts | right/full and enforced cardinality absent by design | Reconciliation can need unmatched rows from either side | C | Native right/full and explicit matchable-key cardinality | Independent orphan/duplicate/composite/NULL expectations and six directions |
| Deduplication | Explicit identical-all-column dedup | Key selection with deterministic tie-breaking absent by design | Latest-record preparation cannot be expressed faithfully | C | Declared key and sort-based first selection; unresolved ties rejected | Reordering inputs cannot change the chosen semantic row |
| Decimal operations | Exact add/subtract, bounded native sums; integer multiplication | Decimal multiply/divide/round absent from IR | Money/rate ETL needs explicit precision and scale | C | Exact typed operations and declared rounding; narrow backend admission | Literal Decimal expected results, overflow/division-by-zero and unsupported paths |
| Timestamp IR | Transport/comparison and strict timestamp policies exist | IR timestamps absent, transport alone is not IR support | Time-preserving migration and local-time preparation | C | Unit/zone-preserving IR subset and explicit DST localization policies | Unit ticks, gap/fold, out-of-range and engine-specific rejection |
| CSV/JSONL ingestion | Exact original source and per-value receipts | Full decoded input and converted columns materialized | Unnecessary memory copies with long inputs | D | Bounded parser/Arrow batches and unchanged exact receipts | Batch metamorphisms, late invalid encoding, budget/cancel/write failures |
| External sources | DataSource/SnapshotClient/SQLite snapshot producer | No universal streaming, PostgreSQL, Excel or object-store connector | Conflating a port with an implemented service | E | Reuse and exercise existing SQLite reference, document boundaries | Detached consistent snapshot and honest connector/partition limitations |

Designed rejections are not defects. Each reproduced defect has its own initial
command, expected/observed behavior, regression and installed retest. Test-harness
mistakes remain separate from product defects.

## Audit and completion rule

`tools/option_inventory.py` reads the installed candidate, its existing registers,
actual signatures/model fields/CLI and distribution metadata. It verifies payload
bytes against the selected wheel. Aliases are recorded without inflating unique
capabilities. Discovery creates `NOT_RUN` obligations; it does not fabricate
independent expected values or infer semantic coverage from a name occurring in
a passing test.

The finite facade risk universe is 3 admitted eager input kinds × 3 alignment
contracts × 2 batch sizes × 2 persisted-evidence requirements × 3 verdict classes,
108 cases, with independent exact Decimal/NULL values. Separate permutation,
batch-size and duplicate-loss metamorphisms supplement it. That is exhaustive
only within this declared finite universe. It is not exhaustive across every
field, backend, optional dependency or interaction in the installed inventory.

Final evidence must preserve distinct cases versus repeated executions and
application acceptance versus a harness successfully observing a rejection.
Windows/macOS/ARM64 cells without a real executor remain BLOCKED/NOT_RUN.
Neither configuring commands nor passing Linux tests validates another platform.
The broad security assessment and static-alert validation remain incomplete.
