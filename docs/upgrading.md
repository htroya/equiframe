# Upgrading, recovery and support

[Handbook](index.md) · [Compatibility](compatibility.md) · [Security](security.md) ·
[Release/rollback](releasing.md)

## 0.12.2 compatible patch

This patch retains the reviewed 0.12.0 public API and file-format contracts. Its
package description is in English; repository READMEs present English before
Spanish. A runnable file/conversion/comparison example is included with both
source and wheel distributions.

Release versions now come from the reviewed Git tag through Hatch. Installed
`__version__` values read distribution metadata. Build from an identified source
archive or a correctly tagged Git checkout; do not inject an SCM override to
manufacture a release version. The exact paired benchmark remains Beta.

Existing evidence keeps its original producer. The new producer is admitted
explicitly without relabeling previous detector fits or historical fixtures.
Source changes and rebuilt distributions need their own final checks and hashes.

## 0.12.0 public contract

The 0.12.0 stabilization protects the explicitly reviewed file-reading/conversion,
DuckDB capture, closed IR/native migration, profile/IF/MAD/H and language-R
interfaces. See the per-name `get_stability_register()` and
[compatibility boundaries](compatibility.md). This is not a blanket promotion of
every export: EDA, reduction, providers, ingestion/workflows and standalone
pipeline orchestration remain experimental. Shared pipeline models embedded in
stable migration evidence retain their format and reader commitments.

Existing valid calls, typed outcomes, exact values, historical format semantics
and fail-closed rejections remain the contract. No caller needs to replace `1.0`
format markers with the package version. Do not relabel old compiler identities,
producer versions, detector evidence or successful/failed historical runs as
0.12.0. A new package identity requires its own final artifact checks; the A14
implementation matrix is separately identified in compatibility documentation.

Stability does not promise that a trained forest survives arbitrary changes to
scikit-learn, NumPy, preprocessing features or training/calibration selection.
Keep the original environment and bundle for retained inference; after a
dependency change, check version admission, reproduce representative scores and
retrain/recalibrate deliberately where required. No inference path may refit a
model or turn unavailable support into `no_alert`.

## Before changing a dependency or candidate

The 26 October 2026 source development introduced
[file loading/conversion](lectura-conversion.md) and [language-R review](r_review.md)
APIs, now included in the reviewed 0.12.0 public contract. Existing contract,
comparison, migration and detector semantics remain separate. Initial file
loading constructs Pandas before its selected native target; later conversion
consumes the currently selected Pandas, Polars or DuckDB frame, verifies its
captured identity and records the new provenance. Conversion is not a replacement
for executing independent transformations. R review
requires an explicit contract and preserves existing alerts/unavailable states.
Select the `files` extra for Excel/XML readers and the corresponding engine extra
for conversion; install Rscript separately only when using the optional R API.
Validation results for these source additions are reported separately and do not
inherit results from older candidate artifacts.

A14 introduced construction-time rejection of invalid built-in transformation
metadata; 0.12.0 retains it. `PandasTransformation` and `PolarsTransformation` require an
explicit callable; `DuckDBTransformation` requires nonempty trusted Unicode SQL
without NUL. No constructor runs that code or imports a native engine. Valid SQL
is preserved verbatim, including surrounding whitespace. Revision/identity/version
errors retain `ValidationError`; engine/callback/SQL admission errors use
`InvalidExecutionInput`. Custom registered implementations remain explicit.

`RunContext.check_table` requires actual boolean `output` and `enforce_rows`
values. Pass `False` deliberately to skip its row checkpoint; this does not
disable its Arrow buffer budget. `measure` rejects invalid stage text before
entering the operation. Constructor validation and budget guards do not sandbox
trusted callbacks or provide hard process-memory/preemption guarantees.

Historical A11 added source inputs and deterministic windows; see the
[five-step guide](universalidad-cinco-pasos.md). Existing plans keep their node
defaults. That candidate's consumers needed its regenerated IR/migration/workflow
schemas and a fresh compilation/validation; older
readers do not understand a new `window` kind. A11 introduced its detector
producer identity; historical producer records remain readable. No historical expected
output or receipt is rewritten. Core/benchmark versions are paired exactly.

1. Keep the current wheel/sdist, trusted receipt, dependency pins/hashes and
   environment details. `0.11.1` alone cannot identify private candidate bytes
2. Preserve contracts, their revisions, reviewed expected outputs and finalized
   evidence. Do not overwrite old runs or automatically approve new baselines
3. Read the artifact's changelog, per-name stability register, compatibility
   policy, dependency inventory and affected security/release notes
4. Create a new isolated environment. Install the new identified artifact and
   reviewed dependencies outside the checkout; check imports and `pip check`
5. Run your representative positive, different, invalid-expected, incomplete and
   resource-limit cases, plus the appropriate installed recipe and regression suite
6. Compare semantics, diagnostics, artifact readability and performance budgets.
   A successful import is not enough; historical artifact readers must still
   satisfy their integrity and supported-format checks
7. Move the application only after those checks pass. Retain the previous safe
   environment and evidence for rollback, without reinstating a known unsafe version

Dependency upgrades can change native transport, timezones and fitted ML
behavior. Use the same exact identified wheel for every claimed matrix cell.
Do not edit lock hashes, reference outputs or capability fingerprints to silence
a failure. Escalate the smallest reproducible semantic difference instead.

## Retained behavior and historical candidate corrections

### Historical A13/A14 producer identities

A12 incorrectly inherited the A11 default when fitting a new detector. The
historical A13 correction addressed that default for its own candidate. The
then-current A14 candidate recorded `0.12.0a14` for newly fitted detector evidence;
supported older records retain their recorded producer. This concerns provenance
metadata, not fitting,
thresholds, labels or the `equiframe-if-mad-1.0` algorithm identity. Existing
bundles retain their recorded producer; readers never relabel old evidence.
Recreate affected A12 fits when accurate producer provenance is required.
The frozen A12 option catalog remains bound to its original artifact and does
not establish a current release's coverage percentage. New 0.12.0 producers
record their own package identity; supported historical records keep theirs.

### Truth testing is intentionally rejected

Replace:

```python
# Unsafe historical pattern; now raises TypeError
assert result
```

With:

```python
ef.assert_equivalent(result)
```

For absence checks use `result is not None`, and for a decision use
`decision.accepted`. Do not use `result or fallback`, `any([result])`, or
`if decision`. All three comparison states reject truth testing.

### Operational outcomes also reject truth testing

The [explicit outcome inventory](outcome-gates.md) extends this rule to operational
results, checks, decisions and comparison reports. Replace optional-presence
checks with `value is not None`; replace acceptance checks with the documented
state/completeness/decision gate. Do not mechanically replace `if result` with
`if result is not None` when the original intent was approval. Configuration,
input data and bundle containers are not globally converted to boolean guards.
Persisted fields, formats, readers and fingerprints remain unchanged.

### Complete does not mean accepted

An invalid right-hand expected result may be `not_evaluable` with `complete=True`.
Use the explicit assertion and do not replace it with a check of only
`result.complete` or an empty example list. `equiframe compare` uses 0 only for
accepted complete equivalence; 1 is a complete difference; 3 is unavailable
judgment/failure; invalid input/configuration may use 2.

### Existing evidence keeps its meaning

Readers reject unknown versions, inconsistent counts, corrupted inventory and
unsafe references even if an earlier candidate accepted them or hashes were
recomputed. That is a fail-closed correctness restriction, not permission to
reinterpret an old schema. Core format `1.0`, contract revision and package
version are independent. Save a new artifact when an explicit supported
migration exists; no universal automatic converter is promised.

### Native capture can reject previously lossy cases

Unsupported metadata, Decimal/time representations, DuckDB HUGEINT/UHUGEINT and
other unfaithful native transports are rejected instead of coerced. Do not
work around a rejection by turning precise numbers into floats or discarding
metadata. A deliberate consumer-side conversion needs its own reviewed domain
and range proof. Preserve the original data and conversion provenance.

### Migration arithmetic rejects concealed intermediate overflow

Each arithmetic expression's declared range is enforced before its value is
consumed. DuckDB compiler v8 replaces its earlier placement rejections with
native eager checkpoints, allowing nested arithmetic, arithmetic predicates
and later relational operations without concealing errors. Compiled IR programs
require the native checkpoint-aware adapter; executing their `.sql` alone fails
explicitly. Ordinary registered trusted DuckDB SQL keeps its interface.

Pandas v4 and Polars v11 retain their own native paths. DuckDB's new version is
`product-semantics-v8`; old identities and historical formats remain unchanged.
Read the [checkpoint and budget contract](migration-ir.md#eager-failures-and-historical-evidence)
and rerun affected plans against the identified artifact. Source-only tests and
earlier artifacts do not establish validation of a new installed wheel.

## Optional configuration and pinned snapshots

Optional `options`/`policy` arguments now use defaults only for `None`. Invalid
falsey values such as `False`, `0` or `[]` raise validation errors before work
begins. Existing option models and valid strict mappings, including an empty
all-default mapping, retain their behavior. Use an explicit empty mapping only
where a mapping is the documented input, not as a substitute for another type.

The generic snapshot API is now available from `equiframe` and
`equiframe.snapshot`. Existing `equiframe_benchmark` imports are supported aliases,
so there is no forced import migration or manifest rewrite. New integrations can
avoid installing the benchmark; see [extension ports](extending.md).

## Failure diagnosis

| Symptom | Safe next step |
|---|---|
| `missing_optional_dependency` | Install the required extra from reviewed artifacts; retain its pinned dependency identity |
| Import resolves inside checkout | Recreate a clean environment outside the source tree; remove editable/PYTHONPATH influence |
| Missing compatible dependency wheel | Record Python/OS/architecture and exact pins; request a reviewed supported set instead of dropping hashes |
| `CapabilityError` / unsupported representation | Inspect adapter stage/type policy; do not silently cast, deduplicate or drop metadata |
| `different` | Inspect key/position, both values/types, policy and actual contract violation; fix the candidate or review a genuine requirement change |
| `not_evaluable` | Inspect diagnostics and completeness; repair invalid reference/input or deliberately revise sufficient resource budgets |
| Evidence missing/corrupt/outside root | Preserve the failed directory; verify source/receipt and configured authorized root; do not rehash corruption into validity |
| Destination already exists | Use a new output directory rather than overwriting earlier evidence |
| Timeout, cancellation or process kill | Retain partial evidence and nonzero status; require valid finalization on a new run |
| HTML looks valid but integrity check fails | Treat publication as failed; a rendered view is not verified acceptance |
| ML bundle incompatible/not estimable | Preserve the reason; validate features, versions and disjoint normal training/calibration support; do not convert to `no_alert` |

Exception messages are concise but arbitrary caller/dependency tracebacks,
Pydantic `.errors()`, pytest `--showlocals`, plugins and environment dumps can
still reveal data. Share a minimized synthetic reproduction, not raw private
captures or credentials.

## Reporting a problem

Use the repository issue channel linked in the README for nonsensitive bugs and
minimal synthetic reproductions. Follow [security](security.md) for sensitive
reports. This handbook does not establish a guaranteed response time, staffed
security duty roster or SLA. Package stability protects the published technical
contract; it is not a support-service promise.

Include only what is needed:

- Exact wheel/sdist hashes, package and dependency versions, Python/OS/architecture
- Minimal synthetic inputs, reviewed contract/policy and expected versus observed
  state/completeness/exit code
- Reproduction command, budget settings and whether failure is repeatable
- Redacted validated report where sufficient; record missing evidence honestly
- Whether a prior **identified artifact** behaved differently

A possible false `equivalent` deserves urgent owner review because it can
undermine downstream trust. Stop using that result for acceptance, preserve
private evidence, bound affected versions/data and avoid publishing sensitive
examples while the issue is assessed. This is an incident-handling expectation,
not a claim that a staffed response service already exists.

## Rollback and withdrawal

Rollback means selecting an earlier **known-safe identified artifact and matching
dependency environment**, then revalidating your representative workload. Do not
alter historical reports or downgrade format markers to make them readable.
An old version known to admit false equivalence is not a safe fallback. If no
safe reader/environment is available, retain the evidence and suspend acceptance.
Only the owner can authorize public release/withdrawal decisions; see
[release procedure](releasing.md). Authorization to prepare a stable release is
not evidence that registry publication, clean installation or the other release
gates have finished; use the status of the identified final artifact.

## Retained use and incident follow-through

Use the [adoption protocol](adoption.md) to record whether an integration survives
a later real change, including failures and assistance. Technical replays are
not human acceptance. [Maintenance](maintenance.md) documents proposed priorities,
minimal permitted reproductions, pending owners and critical false-equivalence
containment, correction, safe recovery and consumer reconfirmation.

## Shared primitives and installed learning routes

The consolidation retains all current public names and their imports. Generic
byte publication no longer depends on profile computation; physical captured-table
validation no longer belongs to migration. Old private aliases remain identical.
No serializer, schema version, newline or fingerprint was unified by this move.
Existing historical fixtures remain immutable regression inputs.

Start from [the Spanish introduction](inicio.md) or [API choice](choosing-api.md).
The wheel now carries [A–H runnable journeys](journeys.md) and the complete
[SQLite snapshot integration](sqlite-snapshots.md) as package resources, so their
use need not depend on a checkout. These are synthetic engineering examples;
they do not establish independent human adoption, domain/DW acceptance or a
completed security assessment.


## 0.12.0a1 native relational additions

The [IR extension reference](migration-ir.md) specifies the new outer joins,
cardinality, deterministic deduplication, Decimal operations and timestamp/DST
contracts. Existing `EquiJoin` defaults remain many-to-many; existing identical
dedup and arithmetic behavior remain unchanged. New default fields are omitted
from old-shaped serialization to preserve historical IR/spec fingerprints.
Historical evidence is read without rewriting bytes, schemas or old compiler
identities. New compilers carry `product-semantics-v2` identities. Previously
blanket-rejected operations now have explicit per-engine admitted subsets.

Decimal division now has independent exact native routes in all three engines;
Polars/DuckDB use bounded integer quotient/remainder steps through precision 38.
DuckDB also supports explicit half-even DecimalRound through the exact integer
coefficient path; its compiler identity advances to product-semantics-v5.
Rerun affected rounding plans with the new wheel and independent expected values;
older rejected half-even plans do not become historical successful executions.

The subsequent IR timestamp implementation uses Polars product-semantics-v9 and
DuckDB product-semantics-v6. Exact int64 tick codecs preserve all four units and
declared zones. DuckDB localization now enforces explicit fold/gap policies in
native ICU SQL; Polars seconds localization uses a checked native millisecond
view. General transformations keep their original native transport restrictions.
Rerun affected time plans against the new wheel and literal expected instants;
the source-only foundation checks and previous artifacts retain their identities.
The earlier foundation used Polars v6 and DuckDB v4. Those compiler identities
and their evidence remain unchanged: that revision rejected DuckDB explicit DST
localization and Polars timestamp seconds, and restricted DuckDB arithmetic
placement. Current transport, localization and checkpoint behavior is specified
in [the IR manual](migration-ir.md); capture support alone never establishes
localization support.
Check both compilers before migrating; a source test is not installed-wheel
validation. These additions do not alter thesis families, partitions or R/M/B/H/O.

Polars `product-semantics-v13` subsequently replaces bundled-provider IR
localization with native transition lookup and POSIX-rule evaluation from the
installed `tzdata` resources. This addresses timezone history revisions such as
the Colombian May 1992 transition without changing input ticks or expected
instants. Compilation identities include resource hashes; changing a resource
before execution rejects the run. Rerun affected plans against the identified
wheel. Earlier Factory, numeric and timezone receipts retain their original
artifact identities and do not establish acceptance of the new implementation.


## 0.12.0a2 strict numeric and boolean metadata literals

Numeric/boolean `Literal` fields now require the exact declared Python value type.
For example, `64.0` is rejected for an integer bit-width literal and `1` is rejected
for a `Literal[True]` confirmation. This closes a reproduced coercion in both core
and benchmark metadata, rather than changing valid value encodings or the
scientific method. String-only literals retain their existing behavior.

Candidate 0.12.0a2 introduced these guards. Its producer register retained
0.12.0a1 and older admitted identities for valid historical evidence; retaining
an identity does not certify the correctness of every earlier input. Preserve
a1 receipts separately and rerun affected cases against the new wheel. Its matching
benchmark required exactly `equiframe[arrow]==0.12.0a2`.


## 0.12.0a3 verification reader consistency

Use 0.12.0a3 for new validation, with the benchmark pinned to the same core
candidate. A verification must request at least one output. A failed capture
may still have one requested output and zero inspected outputs; that remains
non-publishable and incomplete rather than becoming a publishable empty result.

Retained execution/snapshot mismatches must remain failed and incomplete. Readers
reject expected pass/fail claims without a bound comparison and invalid integrity
states.
Complete verification requires passed integrity; requested comparison counts and
coverage completeness must agree with the retained dimensions. These checks strengthen
the existing acceptance boundary without changing scientific protocols or admitting
partial, missing or contradictory evidence as success. They check consistency,
not producer authentication.

Valid historical producer identities, including 0.12.0a1 and 0.12.0a2, remain
admitted. Admission is not a certification of malformed earlier documents.
Preserve the original evidence and failed probes; do not rewrite old results or
infer acceptance from old passing totals. Revalidate affected cases against the
identified 0.12.0a3 wheel and preserve the new artifact-specific receipts.


## 0.12.0a4 explicit integrity-reader controls

`read_pipeline`, `read_migration`, `read_workflow`, and the benchmark's
`read_integration` require an actual Python `bool` for `verify`. The default and
explicit `True` verify retained evidence. Explicit `False` is a deliberate
metadata-only read: returned producer decisions such as `complete` or `exit_code`
are not proof that retained bytes are intact.

Other values, including `0`, `1`, `None`, strings and empty collections, raise
`TypeError` before evidence I/O. Convert external configuration to a validated
boolean explicitly; do not use truthiness to interpret text such as `"false"`.
This closes reproduced cases where invalid falsey values silently skipped
corrupted-evidence checks. Valid boolean behavior and evidence formats are
unchanged. Preserve earlier artifacts and failed probes, and rerun acceptance
against the identified 0.12.0a4 package pair.

For portable bundles, only `expected_sha256=None` omits the optional trusted
manifest pin. Empty strings or other falsey supplied values no longer disable
pin checking; they fail the exact SHA-256 comparison. This also applies to
`inspect_bundle` and `import_bundle`; a rejected import does not create its
destination. Bundle member checks remain mandatory even when the pin is omitted.


## 0.12.0a5 literal native column names

IR column strings denote exact names, including `*`, regex-shaped names and
projected aliases. Earlier Polars compilers could expand such names, fail
planning or return unintended extra columns. The comparison/expected gates
remain necessary; successful native execution alone never proves correctness.

The corrected Polars compiler uses literal selectors and temporary native-local
join identifiers, restoring exact public names and order. It carries
`product-semantics-v3`; Pandas/DuckDB compiler identities are unchanged. No IR
format, comparison policy or scientific method changes. Existing name validation
and engine-specific identifier limitations remain in force. See
[migration contracts](migration-ir.md#literal-column-names).

Preserve old artifacts and receipts. Recompile/rerun affected plans with the
identified A5 wheel and retain new evidence; do not reinterpret A4 results as A5.


## 0.12.0a6 optimization-independent input rejection

The shared snapshot boundary now rejects unsupported input objects with an
explicit `TypeError` rather than a Python assertion. This avoids diagnostic
behavior changing when assertions are disabled with `python -O`. In `verify`,
an unsupported expected object follows the existing failed-capture path and
cannot make a result publishable. It does not become a supported expected type;
use the documented `ArtifactRef`, `ExecutionResult`, or `None` inputs.

Supported snapshot inputs and recorded valid evidence are unchanged. Preserve
A5 artifacts and receipts, and use the exact A6 package hashes for new validation.
No output-model contract or scientific methodology changed.


## 0.12.0a14 first use and environment diagnosis

Two new experimental commands use existing public comparison/report APIs:
`python -I -m equiframe doctor --extra arrow` checks local metadata;
`python -I -m equiframe demo --role scientist --output NEW_DIRECTORY` runs a
small synthetic preparation and saves reports before the gate. See
[first use](first-use.md) for both roles and all three states. Dependency ranges,
existing API signatures and persisted format versions are unchanged.

Core and benchmark must both be A14. External consumers with an exact older
core pin continue to require their identified older artifact; do not bypass
dependency checks to force an upgrade. Reinstall the correct artifact in the
selected interpreter if doctor reports code/metadata identity disagreement.

## 0.12.0a7 minimum-Polars expression composition

The A5/A6 literal-name selector compiles to escaped regex expressions on admitted
Polars 1.30. Combining different columns can fail with `ComputeError: an expression
is not allowed to have different regexes`, including ordinary two-column Boolean
filters. Affected migrations remain incomplete/non-evaluable; that is a defect for
valid admitted plans, not acceptance of their data. Historical A5/A6 passes on a
newer Polars do not establish minimum-version support for those combinations.

The Polars compiler now evaluates expressions in a collision-free native-local
column namespace, mapped from the actual input frame's literal names and order.
Even `nth(index)` can expand its resolved name in Polars 1.30, so positional
selection alone is insufficient. Logical names are restored after evaluation;
every stored node is normalized to validated schema order. Projections compute
all expressions from one renamed source using distinct temporary output aliases.
New aliases, replacements and literal `*`/regex-shaped names stay literal.
Aggregation, deduplication, sorting and join-key checks use the same safe naming
boundary; existing collision-free join renaming is retained. There is no fallback
to another engine and no raised Polars minimum.

Reinstall the exact A7 wheel and rerun affected Polars plans against their
independent expected output at both dependency endpoints. The compiler identity
is `migration-native-ir1.0/polars/product-semantics-v4`; Pandas and DuckDB retain
v2. The public IR, contract and evidence formats remain 1.0. Preserve old artifacts
and receipts; do not relabel previous failures or passes as results for A7.

## Private a8 compatibility candidate

Install a8 into a new environment; its runtime bytes and package identity differ
from a7. The benchmark requires exactly a8 and the independent consumer is
0.1.10. Named aliases retain their names and underlying alternatives; no public
signature, default, acceptance state or format is intentionally withdrawn.
The detector producer version admits a8 and retains every previously accepted
producer version. Its new default identifies a8; prior saved artifacts are not
rewritten. Two producer-version schemas consequently extend their known-version
enumeration; this does not change the detector algorithm or scientific protocol.

Use the chosen interpreter explicitly. Never force requires-python, ignore
dependencies or reuse a 3.12 binary wheelhouse on ARM64/3.10. Restore the retained
a7 environment only on its supported Python (3.12/3.13), using original hashes;
an attempted a7 rollback on 3.10/3.11 must fail normal metadata admission.

The Windows offline lifecycle check uses the reviewed executable A7 core wheel
`5d435e75a79754ab45c8a27f7d30ff513c006034bdddbff170ec9506816b9ff0`.
The distinct A7 documentary-delivery wheel
`abab950c4bdbaf38056f493ca4efc97148b0d85d8d34322d2725437c9f2b42c9`
is retained as document history, not substituted as the runtime baseline. The
upgrade receipt records both identities and rejects any baseline whose outer
wheel hash differs from the reviewed executable artifact.

## Private SDK11 checked Polars DecimalRound candidate

The SDK10 diagnostic matrix observed four Polars native panics for the frozen
DecimalRound case `G06.value.guard.620d9009465585d69de18975`, across ARM310/312
and normal/optimized modes. Those observations remain failures of SDK10. A panic
wrapped as NativeEngineError is not an accepted semantic range rejection.

The corrected candidate prepares DecimalRound through exact native coefficient
arithmetic before the final Decimal cast. It retains the declared half_even and
half_away_from_zero policies, signed values, NULLs, duplicates and physical scale.
A valid carry from Decimal(38,18) to Decimal(38,1) is preserved; an incompatible
Decimal(1,1) destination produces an explicit range rejection. Arithmetic division
keeps its separate exact mode. No DecimalRound exact mode or implicit float path
is added, and Pandas/DuckDB continue executing their own native implementations.

Polars compiler identities advance from product-semantics-v13 to v14, including
plans without DecimalRound. Recompile plans with the selected candidate and
register their actual new transformation IDs. Preserve saved compiled identities,
runtime source maps and historical receipts; never rewrite them to v14 or relabel
an SDK10 observation as a new candidate execution. Public IR/contract/evidence
formats remain unchanged. Verify and the separation of rules, profiles and
Isolation Forest remain unchanged; legacy R denotes rules, not language R.

Use the actual reviewed wheel/sdist and fresh source/bytecode/compiler maps for
the selected environment. Validation must cover normal and optimized modes,
direct filter predicates, nested projections, overflow, the valid wider neighbor,
temporary-style logical names, empty inputs and all-NULL inputs. Candidate source
or proposed tests alone do not establish a completed regression or publication.
