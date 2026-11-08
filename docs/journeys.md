# Eight reproducible user journeys

[Handbook](index.md) · [Quick start](quickstart.md) · [API](api.md) ·
[Semantics](semantics.md) · [External SQLite source](sqlite-snapshots.md)

**Entrada en español:** estos ocho recorridos contienen datos pequeños totalmente
sintéticos, un esperado literal independiente y casos correcto, discrepante y
fallido/no evaluable. Los comandos y criterios de aceptación están aquí como
fuente única. Un resultado `completed`, un reporte o acuerdo entre motores no
aprueba los datos. Los casos negativos deben rechazarse; ninguna prueba sustituye
revisión científica, aceptación del DW real ni un piloto con usuarios.

Each journey is a complete script using the existing APIs. They are examples,
not a second core API, framework, connector service or anomaly benchmark.
`common.py` shares only example contract construction, reports, CLI and runtime
receipts. No callbacks, models or hidden datasets are downloaded.

## Installation outside the checkout

The commands below use an identified **0.12.4 offline wheelhouse**, with a
matching identity for the actual CPython 3.10–3.13 minor and platform. Follow
[installed-private.md](installed-private.md) for normal resolution, `pip check`,
import verification and the separate complete hash-lock trial. Use `[engines]`
for the current common journey environment; ML and benchmark are unnecessary.
Run from a fresh consumer directory outside the checkout:

```bash
python3.12 -m venv .venv
WHEELHOUSE=/absolute/path/reviewed-wheelhouse
.venv/bin/python -I -m pip install --no-index --find-links "$WHEELHOUSE" \
  'equiframe[engines]==0.12.4' --report install-report.json
.venv/bin/python -I -m pip check
.venv/bin/python -I -c 'import equiframe, sys; print(sys.executable); print(equiframe.__file__); print(equiframe.__version__)'
.venv/bin/python -I -m equiframe.examples.journeys.verify_journeys --output acceptance
```

Replace the placeholder with the reviewed wheelhouse, containing exactly the
chosen core artifact and compatible dependencies. Verify its separately supplied
hash inventory first. The import must be in this environment's site-packages.
Do not use editable installs, PYTHONPATH, `--no-deps`, or an unreviewed public
homonym. A new repetition uses a new output directory.

Historical recipe: the retained `examples/journeys/requirements.lock` is a
byte-for-byte copy of the **0.11.1 / Python 3.12** first-use kit dependency lock.
Its pins (including Typer 0.27.2 and tzdata 2026.4) and old receipts are retained
for that exact historical kit, described in [recipes.md](recipes.md). It is not
the current A7 platform lock. Current independent hash-locked installation uses
`runtime-with-candidate.lock` supplied with the selected artifact/environment,
including the candidate hash; never mix old and new wheels with one filename.

Dependencies may need to be downloaded in a separately reviewed preparation
step. The A7 private kit has a pinned public-dependency reconstruction procedure;
only after that preparation is installation completely offline. None of these
synthetic examples needs network data. The examples alone do not establish a
platform run; see [measured compatibility](compatibility.md) for executed scope.

The **candidate wheel includes these scripts** and the guide. Alternatively,
copy the entire `examples/journeys` directory from the sdist or approved handoff:
`python journeys/a_pandas_refactor.py ...` works from another directory without
checkout imports or `PYTHONPATH`. Use ordinary Python for copied direct scripts;
`-I` removes the script directory and is intended here for the installed `-m`
route. On Windows use your environment's `Scripts/python.exe`; the commands are
not a claim of a newly executed Windows matrix.

A/F use pandas+Arrow; B/C use pandas+DuckDB+Arrow; D/E use Arrow; G/H use
DuckDB+Arrow. All also need core base dependencies. The single lock deliberately
covers the entire suite and pytest. Importing a journey module does not load any
optional engine. A missing direct Python import exits 2 with an installation
hint rather than a traceback; native engine failures retain their separate
core stage diagnostics and cannot approve data. Polars, ML, benchmark, SQLite services, cloud
accounts and SERCOP are not needed for these eight journeys. The existing native
migration tests separately cover all six pandas/Polars/DuckDB directions.

Every completed script writes `environment.json` with the actual interpreter,
platform, installed dependency versions and SHA-256 of the example scripts. The
candidate's commit and wheel hash belong in the accompanying build receipt;
a version string alone is insufficient to identify code. Historical results do not prove
a new wheel passed.

## Commands and exits

All modules are under `equiframe.examples.journeys`. Replace `a_pandas_refactor`
in this command with the module below; choose a fresh output directory:

```bash
python -I -m equiframe.examples.journeys.a_pandas_refactor --case good --output evidence-a
```

| Journey/module | Correct | Discrepancy | Error/unavailable | Additional regression |
|---|---|---|---|---|
| A `a_pandas_refactor` | `good` → 0 | `different` → 1 | `not_evaluable` → 3 | `duplicate` → 1 |
| B `b_native_migration` | `good` → 0 | `different` → 1 | `not_evaluable` → 3 | Shared error despite peer agreement |
| C `c_retail_etl` | `good` → 0 | `different` → 1 | `error` → 2 | Both CSV and JSON exercised |
| D `d_financial_reconciliation` | `good` → 0 | `different` → 1 | `not_evaluable` → 3 | Equal totals with two wrong records |
| E `e_telemetry` | `good` → 0 | `different` → 1 | `not_evaluable` → 3 | `null_nan`, `duplicate_loss` → 1 |
| F `f_data_science_preparation` | `good` → 0 | `different` → 1 | `not_evaluable` → 3 | `dropped_row`, `changed_id` → 1 |
| G `g_external_snapshots` | `good` → 0 | `different` → 1 | `error` → 2 | `schema_error` → 2 |
| H `h_portable_ci` | `good` → 0 | `different` → 1 | `not_evaluable` → 3 | `error` → 2 |

For individual journeys, 0 means the requested acceptance checks passed; 1 is a
real discrepancy; 2 is invalid input/integrity/setup failure; 3 is unavailable
required judgment. A one-row comparison budget creates real non-evaluability in
the relevant branches; the script never fabricates a result state. Setup errors
fail closed. Existing output directories are refused, without overwriting them.

`verify_journeys` is different: it is a **test harness**, deliberately expecting
negative exits. Its 0 means all 31 named scenarios matched their specified
outcomes. `production_data_approval` is always false. Do not replace your CI
acceptance gate with a harness that expects a discrepancy.

## A. Pandas refactor regression

**User/problem:** a Python developer replaces row-wise multiplication with a
vectorized calculation and needs meaningful pytest diagnostics. Three order
lines use composite identity `(order_id, line)`, preserving leading zeroes and
repeated order IDs. Money is exact signed int64 **USD cents**, not float.

The independent expected literal is `(001,1,250)`, `(001,2,50)`, `(002,1,300)`.
The old implementation is separately checked against it; the candidate is then
compared after harmless row permutation. `different` adds one cent to the third
line. The diagnostic must identify key `("002", 1)`, column `total_cents`, 301
versus 300. `duplicate` inserts another occurrence with an already-used composite
key; it is not silently deduplicated. A budget failure remains non-evaluable.

**Acceptance:** `diff` plus `assert_equivalent`, complete/final counts and the
actual difference records. The repository pytest recipe includes a direct
`pytest.raises(EquivalenceDifferentError)` test and rejects an invalid duplicate
expected table with `EquivalenceNotEvaluableError`. In your own pytest test:

```python
from equiframe.examples.journeys.a_pandas_refactor import declaration, materialize
import equiframe as ef


def test_optimized_totals(tmp_path):
    candidate, expected = materialize("good")
    ef.assert_equivalent(ef.diff(candidate, expected, contract=declaration(), work_dir=tmp_path))
```

**Artifacts/limits:** private full captures and differences; minimized
`reports/refactor/report.html`; runtime receipt and summary. Integer cents are a
USD-specific declaration in this example; do not infer arbitrary currencies or
rounding policies. A pandas index is not automatically the business key.

## B. Native migration with an independent expected

**User/problem:** an engineer migrates a currency aggregate from pandas to
DuckDB. Both native compilers receive the same admitted IR and captured inputs;
neither engine's output feeds the other. `check_migration` runs before capture,
and the counted source resolves exactly once. Native execution identities and
identical input SHA-256 are recorded.

Four source rows contain USD 1.10 and 2.20 and two EUR NULLs. The expected is a
separate literal: USD 3.30, EUR NULL, with Decimal(20,2). `different` changes the
IR's NULL-only sum policy to zero. Both engines successfully execute and agree,
yet both fail against the unchanged literal. `not_evaluable` leaves native
execution completed but required comparisons unavailable.

**Acceptance:** preflight supported; one source capture; two distinct native
execution records; materialized expected independent of those outputs; all
three comparisons and the migration exit gate accepted. `read_migration`
checks persisted evidence after DuckDB closes. Reports cover peers and each
engine-versus-expected comparison separately.

**Limits:** bounded declarative compilation, not arbitrary code translation. The
same declarative plan is compiled independently; that does not prove independent
human design. The expected has no claim of external scientific review. This
journey demonstrates one direction; the separate matrix checks six directions.

## C. Retail CSV/JSON ETL and local Parquet

**User/problem:** an ETL engineer needs explicit input schemas, a visible
invalid-record decision, native transformations, Verify and gated local output.
CSV and nested JSON independently encode the same four synthetic sales; they
are alternate representations, **not batches to concatenate**.

The schema preserves text SKU zeroes and exact Decimal money. Each source has
three valid rows and one invalid decimal. `good` deliberately quarantines the
known fourth record and writes a precise disposition: only record 3 with
`invalid_decimal` is excluded. It does not declare the entire input valid or
authorize similar exclusions on real data. `error` uses reject-whole-input and
never hands partial data to a workflow.

Native pandas/DuckDB checkpoints compute net then totals, once per source
format. Independent expected net literals are SKU 0007 USD 12.00, 0008 USD 2.00,
0009 EUR 9.00. Totals are USD 14.00/2 rows and EUR 9.00/1 row. NULL discount is
explicitly zero in the transformation, not silently repaired by comparison.
The one-cent CSV discrepancy fails its net checkpoint and skips its dependent
totals; unrelated JSON checkpoints still run. Nothing is published after any
required checkpoint fails.

**Acceptance:** explicit subset disposition, all four checkpoints, required
expected/rule checks, Verify coverage and current-publication readback. Four
Parquet tables are written only for `good`; automated checks inspect their
literal values. `raw/quarantine-disposition.json` explains exclusions;
`raw/` includes sources, ingestion receipts, original invalid rows, workflows
and verification evidence. `public_reports/` contains minimized comparison
reports. `published/current.json` points to the verified local Parquet version.

**Limits/privacy:** raw files, receipt and publication metadata may disclose
values and local paths. Publish only the explicitly reviewed report view to
other people. Local Parquet publication is file creation; it does not publish
the Python package, deploy infrastructure, write a production DW, implement a
remote transaction, or accept Jhair's domain policy.

## D. Exact financial reconciliation

**User/problem:** a financial-data engineer must find compensating errors that
an aggregate reconciliation misses. Identity is `(account, currency)` and money
is Decimal(20,2). USD and EUR remain separate; there is no inferred FX conversion.

The literal ledger is A/USD 1000000000000000.01, B/USD 0.09 and A/EUR 12.50.
`different` moves one cent from B/USD to A/USD. Both **per-currency totals stay
identical**, yet two keyed amount differences must remain. No intermediate
float, tolerance, quantization or deduplication hides them.

**Acceptance/artifacts:** complete exact keyed `diff`, assertion and two
per-record differences for the deliberate fault; minimized `reports/ledger/`,
private captures and the explicit `per_currency_totals_match` field. The error
branch uses a real comparison budget. This is a precision example, not accounting
advice, balancing rules or support for all financial instrument semantics.

## E. Telemetry, zones, missingness, duplicates and order

**User/problem:** an engineer must distinguish transport changes from changed
measurements. Four records include a repeated observation, a separate NaN, a
NULL measurement and a NULL timestamp. The two non-NULL instants have literal
integer nanoseconds ending in 1 and 2; those sub-microsecond digits are retained.
Expected timestamps use UTC; the candidate uses America/Guayaquil at the same
instants. An explicitly lossless/instant policy admits that zone difference.

The expected sequence retains both repeated observations. `different` reorders
it; `duplicate_loss` removes one occurrence; `null_nan` swaps distinct missing
representations. All must fail. `good` preserves order and multiplicity.

**Acceptance:** Arrow `diff` with significant order, NULL last, ties preserved,
NaN distinct, exact readings and a declared instant policy. The script also
runs real `check_migration` calls: this Scan-only plan is refused because its
significant-order contract has no matching final Sort. This is not evidence that
all timestamp IR is unsupported. A successful direct comparison never implies
admission of a particular migration plan.

**API limits:** direct eager capture/comparison can retain nanoseconds. This
migration IR admits a bounded timestamp subset, documented in
[migration-ir.md](migration-ir.md). Native DuckDB zoned transport has its
separate microsecond limit; no silent conversion to it is demonstrated here.
NaN distinctions already collapsed by NumPy cannot be recovered. Original
per-row timestamp text/offset is not retained by Arrow; store it separately if
required. Timezone-provider versions may differ across engines. Artifacts are
private captures and minimized `reports/telemetry/`.

## F. Data-science preparation without anomaly claims

**User/problem:** a data scientist optimizes feature preparation and must preserve
sample identity, row coverage, feature values and ordering of feature columns.
Four synthetic samples have zero-prefixed IDs. A predetermined milliseconds-to-
seconds conversion has independent literal seconds `[1.0, 2.5, 0.0, 1000.0]` and
event counts `[2, 3, 0, 99]`. No labels, training output or other engine determine
the expected table or scale.

`different` clips the large fourth feature to 100.0, `dropped_row` removes that
record, and `changed_id` erases identifier zeroes. Each fails exact keyed
comparison. The large value must survive `good`, whatever a future model might
think of it. A budget interruption is unavailable judgment.

**Acceptance/artifacts:** IDs, all rows and all features pass the declared
contract and assertion. `reports/features/` is minimized; raw captures remain
private. `anomaly_detection` and `model_training` are explicitly
`not_requested`. Equivalence does not imply healthy data, anomaly detection,
model quality, absence of leakage or scientific validity. R/M/B/H/O are not
redefined or coupled by this preparation check.

## G. External snapshot integration

**User/problem:** an architect adapts an independently managed source through
`SnapshotClient` and `SnapshotDataSource`, without adding a mandatory transport
or benchmark dependency. `MemoryClient` contains explicitly authored synthetic
Arrow IPC bytes; its `example.invalid` URI is an identifier and is never fetched.
It accepts only fixed identity `synthetic.snapshot.20261006.v1`.

A manifest declares domain/extraction revisions, provenance, byte size/hash,
row count and schema. The source fetches the manifest once and downloads once;
the native DuckDB identity execution records the pinned snapshot and manifest
fingerprint. Expected rows are authored separately: `(1, Decimal("1.10"))` and
`(2, NULL)`.

`different` has intact bytes but value 1.11, so integrity passes and semantics
fail. `error` changes one known payload byte **after** manifest creation;
`schema_error` declares the wrong physical schema while keeping byte integrity.
Both produce `artifact_integrity_error`, invalid input and no output artifact.
These are ordinary functional integrity regressions, not a resumed security audit.

**Acceptance/artifacts:** one fixed-ID request, pinned provenance, faithful
execution, independent expected assertion, private snapshot evidence and a
minimized `reports/snapshot/` only when comparison exists. The complete
[SQLite integration](sqlite-snapshots.md) adds a real DB-API transactional producer
through the same ports, outside core.

**Limits:** hashes detect changed bytes but do not authenticate a producer.
Provider immutability, authorization, transport timeout, coordination and storage
retention remain external. Manifest fetching precedes run budgets; a cooperative
checkpoint cannot preempt blocked client code. No real service/DW acceptance is
claimed by either synthetic integration.

## H. Portable review and CI

**User/problem:** a reviewer needs to move complete evidence without depending on
the original machine, keep a small report and reject unavailable or differing
results in CI. `capture_duckdb` executes a trusted bound synthetic query and
closes its owned connection. The expected is a separate Arrow literal with two
IDs and counts 10/20; `different` produces 10/21.

`verify` requires that expected. The finalized verification is exported, its
manifest hash pinned from this trusted local export, and the original evidence
directory renamed so its old artifact paths no longer exist. `import_bundle`
and `inspect_bundle` then verify closed inventory/integrity using captured
members, without rerunning SQL. The imported typed comparisons generate default
minimized reports before their explicit assertion gate. `different` has valid
integrity but failed semantics. `not_evaluable` retains a real budget failure.
`error` corrupts the imported root document and must refuse it without making a
report or accepting data.

**Acceptance:** intact imported inventory, requested Verify checks publishable,
at least one comparison, all comparison assertion gates accepted. Required
non-evaluability exits 3. `bool(result)`, a successful export/import and report
creation are never acceptance shortcuts. No independent review is requested or
invented. A received bundle needs a trusted out-of-band expected digest if its
identity must be pinned; the hash itself remains unsigned.

**Artifacts/privacy:** `private/portable`, `private/imported` and
`private/retired-original` contain complete raw evidence. Only `reports/` is
minimized. Tests verify report inventory hashes and absence of synthetic secret
IDs, local paths and file URIs. Minimization does not erase the raw bundle or
certify that any adapted real dataset is safe to share.

## Automated checks and interpretation

The sdist's `tests/test_product_journeys.py` copies the directory outside its
source location, runs all scenario CLIs, verifies actual return codes and
independent values, reads raw comparisons/migrations, checks Parquet totals,
asserts typed failures, verifies report inventories/redaction, and checks that
an existing output cannot be overwritten. Separate checks verify import-light
modules and explicit missing-dependency failures. It also demonstrates the direct
pytest assertion and checks the dependency lock remains the existing pinned
route. Run with the package's locked developer environment:

```bash
python -m pytest tests/test_product_journeys.py -q
```

The outside-checkout harness can be run from a notebook with subprocess or each
module's `run(Path("fresh"), "good")`. Inspect `accepted` and `exit_code`; never
use the truth value of an EquiFrame result. In an orchestrator, invoke the same
Python function or module command as a normal task, keep raw artifacts in a
private run directory, and let nonzero exits fail the task. No new orchestration
framework or service is required. Retries require a new output directory and
must account for any effects added by your own callbacks.

No five-minute human diagnosis, user pilot, performance speedup, general volume
capacity, universal platform support, producer authenticity, production service
acceptance or scientific conclusion is established by these small tests.
Resource controls are cooperative; use process/OS isolation for hard limits.
