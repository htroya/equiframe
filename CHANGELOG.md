## 0.12.2 — English distribution and release hardening

- Standard repository layout with core source, documentation, tests and metadata
  at the root; the consumer validation application is consolidated separately.
- Current guides and version checks follow the configured dynamic metadata.

- Publish an English package README and an English-first bilingual repository
  README, with direct installation/CLI commands and explicit compatibility scope.
- Include a self-contained typed example that reads temporary synthetic orders,
  converts Pandas to Polars/DuckDB and detects a deliberate one-row regression.
- Derive paired package versions from reviewed Git release tags. Preserve
  historical producer identities and admit the new detector producer explicitly.
- Add reproducible security-audit input handling and stricter secret-file ignores.
- Keep publication manual with a local ephemeral API token, exact reviewed
  TestPyPI bytes and no GitHub Actions execution or stored publishing secrets.
- Retain the 0.12.0 API contracts; this patch does not establish scientific
  acceptance, reviewed real-data labels or external service/warehouse delivery.

## 0.12.0 — defined compatibility and manual public distribution

- Define stable contracts for local file loading/conversion, native DuckDB
  capture, supported relational migration, profiles, IF/MAD/H and optional
  independent language-R review. Advanced orchestration, EDA and reduction
  retain their explicitly experimental status.
- Preserve historical formats and fixtures. New detector fits identify
  `0.12.0`; readers continue to admit the previously supported producer versions.
- Carry MIT licensing for original code and preserve vendored Apache-2.0
  schemas, provenance and redistribution notices.
- Add factual manual release checks for TestPyPI and PyPI, binding the reviewed
  source, four artifact hashes and downloaded consumers without an upload bypass.
- Assign maintenance, release and security responsibility to Hernán Troya
  (`htroya`), without a response-time SLA, and provide a public documentation
  repository with private vulnerability reporting.
- Update release-tool dependency locks for the certifi CA advisory; historical
  test results and scientific acceptance remain separately scoped.
- Collect legacy `LICENCE` notices and declared `License-File` members without
  guessing SPDX expressions; retain the optional xlrd acknowledgement.

## 0.12.0a14 — private Alpha, optional standalone EDA

### Source corrections of 27 October 2026

- Consume the selected native frame for all six dataset conversion directions.
  Check captured Polars/DuckDB schemas before Arrow export and reject stale
  source identities, including lossy native integer transport.
- Accept explicitly supplied DuckDB relations in `diff`, with bounded batch
  capture, native type validation, detached snapshots and cancellation checks.
- Avoid repeated disk scans during immutable reads and in-memory comparison;
  preserve work/time/cancellation checks and disk checks at write checkpoints.
- Reuse exact integer bounds and Decimal representations in the independent R
  reviewer. Give its child process a deterministic locale without changing the
  caller's environment or reducing precision or the rows reviewed.
- Report a missing Windows architecture variable when it prevents Polars from
  initializing, while retaining nonzero CLI exits and errors on stderr.
- Fail promptly on denied Parquet output creation instead of retrying Windows
  permission errors as temporary-name collisions; retain exclusive publication
  and removal of unfinished temporary files.

### Source development of 26 October 2026

- Add experimental local dataset discovery/loading for JSON/JSONL, Excel, TXT,
  XML, CSV, Parquet and GeoJSON. `load_dataset` creates Pandas and optionally
  converts that same frame to Polars or an owned in-memory DuckDB relation.
  Add `inspect_dataset`, `convert_dataset`, typed reading choices and
  `equiframe dataset load`/`dataset inspect` with optional interactive decisions.
- Read observed Excel rows/cells independently of underspecified worksheet
  dimensions. Publish Parquet exports through a synced sibling temporary and an
  exclusive hard link, and keep dataset CLI diagnostics behind the stable
  first-line code and fixed hint.
- Preserve exact Decimal input, identifiers, nested values and null/NaN
  distinctions, with explicit representation errors instead of silent fallback.
  Add the optional `files` extra with deferred Excel/XML reader imports.
- Add `DatasetSource` and `DatasetProvenance` for the exact consumed byte
  snapshot, effective read options and original/destination frame identities.
  Reject mutation of the captured Pandas input before conversion/export and
  omit private source provenance from ordinary structure summaries by default.
- Add independent exact comparison in base R through `review_with_r` and
  `finalize_with_r`. Preserve rules/Isolation Forest alerts, optional Python
  comparison, comparator disagreement and unavailable components. Keep the R
  language separate from operational rules R and scientific oracle O.
- Bind an optional Python comparison to the exact observed artifact transports
  via `RReviewBinding`. Add `finalize_execution_with_r` and `RExecutionBinding`
  to check actual execution/rules/profile/single-profile IF associations before
  reviewing verified output artifacts, while retaining the explicit low-level API.
- Classify the added APIs/CLI as experimental and document their data/resource
  ownership, admitted policies, dependencies and failure states in the installed
  handbook. This entry records implementation; validation results are reported
  separately for the identified sources/artifacts and do not inherit past runs.

### Private SDK11 candidate: checked Polars DecimalRound

- Prepare DecimalRound with checked native coefficient arithmetic before its destination cast.
- Preserve valid carries into wider Decimal destinations, signed values, NULLs and multiplicity.
- Reject declared precision overflow explicitly before a native Decimal intermediate can panic.
- Version all Polars compiled identities as product-semantics-v14; retain the public IR format.
- Keep prior SDK10 native failures and artefact-specific evidence under their original identities.
- Require fresh validation and reviewed artefacts for the corrected candidate.

- Bound DuckDB Arrow export record batches to 2,048 rows at both eager IR
  checkpoints and final materialization, avoiding large speculative buffers for
  wide Decimal tables. Results remain complete materialized tables with their
  original schema, values, multiplicity, order and resource checks. Native
  regression and the controlled Windows replay are required for candidate acceptance.

- Exclude Pandas 3.0.3–3.0.6 from both native-engine extras: their upstream
  `ZoneInfo.from_file` regression can silently replace the authoritative TZif
  rules. Keep the Pandas 2.2 minimum and update both lockfiles to select a
  compatible release. Runtime SDK bytes remain unchanged; new artifact and
  changed-environment evidence are required.

- Align the handbook's Arrow minimum and optional EDA profiles with the package
  metadata, and distinguish current A14 producer/pairing guidance from the
  historical A13 correction. Revised manual bytes require newly identified
  private wheel/sdist artifacts; earlier receipts keep their own digests.

- Bind the declared EDA example relocation when building a first-use kit. Keep
  exact source/wheel byte checks and reject missing, altered, cached or otherwise
  remapped payloads. Runtime package bytes and installation requirements are unchanged.

- DuckDB compiler v8 executes native eager checkpoints for every relational node
  and nested fallible expression. Later pruning cannot conceal overflow,
  localization, cardinality or tie errors. Its private IR program requires the
  native adapter; standalone SQL replay fails explicitly. Intermediate Arrow
  byte budgets and cancellation/time checks apply before further execution.
  Serialized IR/result formats and ordinary trusted DuckDB SQL remain unchanged.
  The capability register describes this program interface and the common IR
  restrictions on fallible short-circuit expressions and integer division.

- Use native Pandas UTC datetimes in the five-family date example, preserving
  microseconds and NULLs without requiring Arrow 23's separate C++ timezone
  database on Windows. The example's declared UTC date semantics are unchanged.

- Admit signed and unsigned integer add/subtract/multiply through 64 bits with
  exact destination bounds. Polars proves coefficient bounds before UInt64
  products and checks the integer range before casting; no wrapped or floating
  result is accepted. Compiler identities advance to Pandas v4, Polars v11 and
  DuckDB v7. Integer division and DuckDB placement restrictions remain explicit.

- Admit Decimal multiplication with each operand through precision 38 when the
  actual product fits the declared output and summed scale. Polars v10 checks
  native coefficient bounds before multiplication, preserving fractional digits,
  NULLs and eager overflow failures without floats or Python row callbacks.

- Preserve IR timestamp ticks in seconds, milliseconds, microseconds and
  nanoseconds, with declared zones, using lossless explicit native tick transport
  in Polars and DuckDB. Add native DuckDB localization with reject/earlier/later
  folds and gap rejection; preserve submicrosecond residuals without floating
  arithmetic or Python row UDFs. Compiler identities advance to Polars v9 and
  DuckDB v6. General trusted transformations retain their existing native limits.

- Add independent native Decimal division for Polars and DuckDB through precision
  38, using bounded integer quotient/remainder steps with explicit exact,
  half-even and half-away-from-zero semantics. Preserve NULLs and reject zero,
  inexact scale and overflow without floating intermediates or Python row UDFs.
  Polars/DuckDB compiler identities advance to v8/v5; historical identities stay
  unchanged. DuckDB retains its direct-projection/eager-error restrictions.
- Add exact native half-even DecimalRound in DuckDB through precision 38, using
  integer coefficients rather than its DOUBLE-returning round_even function.
- Preserve `resource_exhausted` for SQLite disk-budget exhaustion on CPython
  3.10, which lacks SQLite result-code attributes. The compatibility fallback
  recognizes only the exact canonical FULL diagnostic when no code is present;
  other SQLite failures keep their original failure category.
- Validate built-in native transformation metadata and callback/SQL types at
  construction, without invoking code or importing engines. Fixed native
  engines must match their class; SQL whitespace and text remain unchanged.
  Metadata rejection retains Pydantic ValidationError with input values hidden.
- Require explicit boolean output/row-enforcement flags in RunContext checks;
  numeric and string truthiness cannot select or disable row budgets. Validate
  measurement stages before entering a callback or changing timing state.

- Add optional `equiframe.eda` and `equiframe eda`/`equiframe-eda`: fixed local
  snapshots, raw quality/repetitions, explicit text conversions, grouped exact
  Decimal/discrete quantiles, IQR/unscaled MAD and separate JSON/portable HTML.
- New experimental version 1.0 EDA contracts; no existing migration/Verify
  signatures, defaults, comparisons, outcomes or R/M/B/H/O algorithms change.
- DuckDB/Plotly stay optional and lazy. Historical fixtures and original A13
  distributions remain immutable. A13 measurements are not automatically A14.
- New detector metadata defaults to actual A14 producer, with older producers
  retained as admitted history. This changes the experimental producer schema,
  not trained features or algorithms. No Beta or public distribution claim.
- Initialize DuckDB UTC after opening its connection without automatic extension
  downloads, preserving Linux and Windows execution.
- Inspect EDA paths before resolving them: reject source, output, manifest and
  evidence symlinks/Windows junctions; confine manifest members to their delivery.
  Read source manifests with a 16 MiB/2,000-member budget and verify the exact
  bytes consumed. Protected file reads preserve the existing diagnostic formats.
- Reject Windows reparse points in comparison-evidence directories and ancestors.
- Use fixed operational error messages and bounded, value-free DEBUG frames;
  do not publish external exception values in EDA, execution, rules, ingestion,
  comparison or verification results. Preserve closed recovery codes and states.
- Validate EDA cancellation callbacks and their boolean results, avoid invoking
  failed callbacks again, and retain incomplete evidence after chart failures.
- Reject pipes, links, reparse points and special members in generic evidence
  readers and portable bundles; pin POSIX directories before reading and compare
  manifest hashes against the same bounded bytes parsed. Historical data stays unchanged.
- Preserve relative report paths and safe recovery categories with the protected
  readers. Contract/profile/preprocessor document reads reject special files and use
  a 64 MiB budget; generic document OS errors retain their type/errno without paths.
- Extend protected reads to detector bundles and detached comparison reports,
  retaining duplicate/nonfinite rejection, document budgets and generic OS errors.
  Protect report publication against Windows junction ancestors and preserve
  caller-selected ordinary parent navigation. No executable model input is added.
- Protect local artifact copies against special files and linked directories;
  bound verified copies by the declared byte size before publication, reject
  wrong path types explicitly, and preserve exclusive publication and source bytes.
- Apply protected regular-file reads and a 64 MiB budget to comparison, rule
  evaluation and supplementary diff manifests; preserve strict JSON validation.
- Check operation work directories before normalization across native APIs;
  reject linked roots and wrong path types instead of activating falsey defaults.
  Guard publication subdirectories and document parents; reject special ingestion
  sources before creating output and bound reads to the remaining source budget.

## 0.12.0a13 — package quality and producer identity (2026-10-10)

- Align the current experimental detector-schema inventory with the reviewed
  A13 producer identity. Asset preflight now rejects stale inventory hashes
  without rewriting them; add a corruption regression before full test runs.

- Correct detector producer identity: new evidence identifies A13 instead of
  retaining A11 when executed from A12. Preserve explicit historical producer
  records and admit A12/A13 without changing `equiframe-if-mad-1.0`, R/M/B/H/O,
  model parameters, training support or expected outputs.
- Regenerate current producer-containing schemas and their asset hashes;
  preserve all historical fixture and receipt bytes. Keep the exact paired
  core dependency and align current installation guides.
- Add the source-carried standard-library offline wheel integrity audit and
  tests for corruption, unsafe paths, Unicode metadata and occupied receipts.
  Fix strict typing of heterogeneous observations in the option-trace tool.
- Public distribution, license approval, ecosystem adoption and full platform
  acceptance remain independent pending gates; no Actions or paid resources.

## 0.12.0a12 — installed role onboarding (2026-10-10)

- Add experimental `equiframe doctor --extra ... [--json]`: local Python,
  code/metadata identity and dependency availability with actionable recovery.
  It imports no optional engines, installs nothing and makes no network request;
  metadata availability does not establish version-range or binary compatibility.
- Add experimental `equiframe demo --role architect|scientist --case
  good|different|not-evaluable --output NEW_DIRECTORY`. Synthetic SQL or
  Decimal/UTC/NULL/ID preparation uses the existing comparator and independent
  expected literals. Persist redacted and synthetic-detail reports before the
  gate; reject differences, unavailable evaluation and occupied destinations,
  also with Python `-O`. Existing API signatures and persisted formats remain.
- Align current installation/handbook candidate references and add short
  Spanish/English first use. Keep dated receipts and human adoption pending.
- Present reasons, next action, counts and witnesses before technical policies
  in text, HTML and notebooks. Give two-column HTML tables predictable label
  width so long policy JSON cannot compress labels into individual characters.
  Preserve every disclosed fact, redaction setting and evidence limit.
- Advance the exact core/benchmark pair to A12 without changing dependency
  ranges, engine implementations or the scientific R/M/B/H/O protocol. Previous
  consumer pins and A11 universality receipts remain bound to their own bytes.

## 0.12.0a11 — universalidad del producto en cinco pasos (2026-10-09)

- Add experimental read-only parameterized SQLite and caller-owned API/stream
  inputs reusing explicit typed ingestion and its retained original/conversion receipts.
- Add native deterministic `Window` with row_number/lag/lead, partitions, declared
  ordering and offsets in pandas, Polars and DuckDB; reject remaining ties and
  incompatible types/units instead of silently selecting or casting.
- Add explicit external-source composition, exact-schema Arrow record batches,
  cumulative budgets, cleanup and cooperative SQLite progress interruption.
- Ship a complete installed six-source/three-engine example with independent
  literal expectations, discrepancies, integrity failures and explanatory reports.
- Canonicalize only wheel ZIP creator metadata using a shipped build hook;
  preserve payload/RECORD bytes and normalized modes for cross-host reconstruction.
- Regenerate experimental IR-containing and detector-producer schemas and their
  canonical registry hashes. Retain historical defaults, receipts and readers;
  identify new detector evidence as A11 without changing scientific algorithms.
- Keep new APIs experimental and distinguish cooperative final materialization
  from hard memory limits. No Actions, paid resources or public publication.

## 0.12.0a10 — remediación del laboratorio de universalidad (2026-10-09)

- Execute and close separate exact 72-case consumer matrices under normal Python
  and the native interpreter's real `-O` mode in every universality cell.
- Reuse the hash-locked dependency environment when reinstalling the exact core wheel;
  the second phase uses `--no-deps --reinstall`, followed by `pip check`, installed
  payload comparison and runtime binding checks.
- Preserve all A9 runtime semantics and formats. The new identity is required because
  the compatibility verifier is distributed in the sdist and its bytes changed.
- Keep A9 receipts historical; they do not establish A10 support.

## 0.12.0a9 — candidato de universalidad (sin publicación pública)

Nueva identidad distribuida para herramientas/guías revisadas y dependencia directa de typing-extensions en benchmark. A8 permanece histórico. La matriz de veinte celdas requiere recibos nativos; preparación no equivale a soporte observado.

- Target CPython 3.10-3.13 without discarding existing native extras or semantic gates
- Replace post-3.10 syntax/std-library requirements with typed equivalents; preserve named aliases, historical formats and nanosecond/Decimal semantics
- Resolve dependency branches by interpreter and propagate the chosen Python through validation tools
- Produce Python-specific first-use closures; retain failed attempts and exact-byte distribution evidence
- Keep the candidate private Alpha. VM/platform receipts, rights, governance, security coverage and actual independent acceptance remain explicit gates

- Match quick and installed-consumer strict type checks to the actual Python; preserve complete type-check scope
- Extend the historical installer to the declared minors and keep all GitHub workflows manual and unexecuted

## 0.12.0a8 - Python compatibility maturity candidate (2026-10-08)

# Private A7 usability documentation revision — 2026-10-07

- Add executable Spanish data-architect and data-scientist paths with explicit
  expected results, reports before assertion and optimization-independent gates
- Separate the current normal-resolver A7 journey recipe from the retained 0.11.1
  kit; correct the Scan/significant-order preflight explanation in journey E
- Freeze U01–U12 scope and evidence accounting; extend the real-human protocol
  with predeclared timing/roles and clearly fictional rehearsal profiles

Runtime modules, dependency metadata, formats, algorithms and consumer 0.1.9 pin
are unchanged. This private documentation build keeps 0.12.0a7 but has distinct
wheel/sdist hashes and source commit; never mix it with the earlier same-name
artifact in one wheelhouse. Prior receipts retain their original identity.
No security, scientific, human-adoption or public-release gate is closed by this.

# Private installed-product alpha 0.12.0a7 — 2026-10-07

- Evaluate Polars expressions in a collision-free native-local column namespace;
  escaped-name selectors in admitted Polars 1.30 cannot compose different columns
  and positional selectors still expand wildcard/regex-shaped resolved names
- Preserve ordinary and wildcard/regex-shaped names through Boolean, comparison,
  arithmetic, coalesce and conditional expressions without raising the minimum
- Map logical names from actual frame order before native evaluation and restore
  them afterward; retain simultaneous aliases, reordered columns, NULLs, empty
  schemas and native joins/aggregates/deduplication/sorts
- Identify the corrected Polars compiler as product-semantics-v4; retain the
  independently executed Pandas and DuckDB compiler identities unchanged
- Retain A6 artifacts and failed minimum-consumer observations as historical;
  exact new artifacts require their own source and installed validation receipts

No public IR/format, dependency range, scientific method or detector independence
changes. See `docs/upgrading.md` for affected reruns and historical evidence.

# Private installed-product alpha 0.12.0a6 — 2026-10-07

- Replace the snapshot input type assertion with an explicit TypeError, so
  unsupported input objects take the same rejection path under normal Python
  and `python -O`; supported ArrowInput/ArtifactRef/Path behavior is unchanged
- Preserve failed expected captures as non-publishable in the verification path;
  no output-model validators, scientific methods or evidence formats changed
- Retain A5's native literal-column correction and its installed regression
  receipts; rebuild and validate this separately identified package pair

The invalid object cases are caller misuse, not a newly supported input format.
See `docs/upgrading.md` for the optimization-independent input boundary.

# Private installed-product alpha 0.12.0a5 — 2026-10-06

- Resolve IR column names literally in every native Polars selector context,
  including wildcard/regex-shaped inputs and generated aliases
- Use native-local collision-free join identifiers and restore exact original
  names; preserve key multiplicity, NULL policy, column order and empty schemas
- Retain the declared Polars 1.30 minimum through its escaped-name selector
  path; keep exact name admission and missing-column checks
- Version the corrected Polars compiler identity as product-semantics-v3;
  Pandas and DuckDB implementations retain their independently executed code
- Preserve all A4 artifacts and passing suites as historical evidence, alongside
  the subsequently reproduced literal-name failures; revalidate new A5 bytes

No scientific method, detector independence or evidence format changes.
See `docs/upgrading.md` for the native-name correction and rerun guidance.

# Private installed-product alpha 0.12.0a4 — 2026-10-06

- Require actual boolean controls in pipeline, migration and workflow readers;
  reject wrong-type values before evidence I/O instead of silently treating
  falsey values as an intentional integrity-verification opt-out
- Preserve default/explicit True verification and explicit False metadata-only
  reads; producer decisions returned without verification do not prove byte integrity
- Treat only None as an omitted portable-bundle manifest pin; supplied falsey
  pins fail exact digest comparison in read, inspect and import operations
- Retain valid historical producer identities and preserve A3 artifacts and
  failed probes; rebuild and revalidate the corrected package pair as A4

No scientific method, detector independence or evidence format changes.
See `docs/upgrading.md` for caller migration and explicit metadata-only semantics.

# Private installed-product alpha 0.12.0a3 — 2026-10-06

- Reject zero-requested-output verification evidence at public model/read boundaries
- Preserve failed captures with requested outputs but no inspected output as
  non-publishable and incomplete; reject contradictory execution/snapshot, expected-output
  and integrity claims instead of computing publication eligibility from them
- Require passed integrity for complete verification and bound comparisons for
  expected pass/fail decisions; reconstruct requested comparison counts and
  coverage completeness from the retained result dimensions
- Preserve original CSV values when diagnostic field names collide with input
  headers; use a separate diagnostic wrapper only for colliding overflow records
- Make public-option signature and CLI type displays reproducible across
  processes by excluding process-local object addresses from audit descriptions
- Keep a1/a2 artifacts and receipts historical; use a distinct candidate identity
  and retain valid older producer identities without certifying malformed evidence

No thesis method, detector independence or scientific protocol changes.
See `docs/upgrading.md` for the stricter reader boundary and revalidation guidance.

# Private installed-product alpha 0.12.0a2 — 2026-10-06

- Reject numerically equal values of the wrong type in integer and boolean
  `Literal` metadata, including Python/JSON input and revalidated copied or
  constructed models. Field-local guards preserve valid JSON tuple decoding
- Keep valid historical encodings and admitted producer identities, while using
  a distinct candidate for corrected artifacts and installed validation
- Preserve a1 receipts, including the independent probes that exposed the
  coercion; passing older suites did not cover these wrong-type boundaries

No scientific method, detector independence, data format or valid value changes.
See `docs/upgrading.md` for the stricter rejection boundary.

# Private installed-product alpha 0.12.0a1 — 2026-10-06

- Give the new candidate a distinct version; retain exact prior 0.11.1 artifacts
  and historical reader compatibility. Benchmark pins the matching core version
- Add genuine native right/full joins with explicit matchable-key cardinality,
  deterministic key-based deduplication and rejection of unresolved ties
- Add exact Decimal multiplication, explicit Decimal rounding and bounded pandas
  Decimal division. Per-engine unsupported precision/rounding/division paths
  reject rather than convert a shared output or relabel floating results
- Admit timestamp IR unit/zone transport and native pandas/Polars DST localization
  under explicit fold/gap policies. Reject unrepresentable NaT ticks and native
  int64 localization wrap; equal incorrect native outputs must not be accepted
- Preserve typed both-empty outer joins and widen DuckDB multiplication operands
  before its intermediate calculation. Add independent literal regressions
- Add optional `batch_rows=4096` to `ingest_file` and `FileInput`. Stream CSV/JSONL
  converted batches and canonical receipt JSON while preserving raw source bytes,
  positions, quarantine, exact values and old-format JSON bytes. Complete receipt
  objects, full JSON documents and eager source resolution remain memory bounds
- Document normal pip resolution through a private wheelhouse, base/extra and
  historical lifecycle checks. No public upload or new license is implied
- Add installed public-option inventory, explicit audit obligations and machine
  case receipts; discovery and line coverage are not behavioral completeness
- Exercise finite comparison/report/acceptance matrices and independent real-data
  consumer programs separately from the historical synthetic A–H journeys

New IR defaults serialize in the historical shape to preserve old fingerprints;
new options have explicit serialization and compiler identities. Public imports,
existing formats, R/M/B/H/O independence and scientific protocols remain intact.
Unsupported platforms, unbound option interactions and the broader security
assessment remain explicit; no 100% behavior, universal platform or security claim.

# Post-roadmap review: correctness and reusable Python integrations

## Private consolidation — 2026-10-06 (candidate still identified by commit/hash)

- Reject implicit truth testing of operational outcomes/decisions/reports as
  specified in `docs/outcome-gates.md`; replace optional-presence checks with
  explicit `is not None` while preserving serialized fields and verdict rules
- Move generic document byte I/O and captured physical metadata out of specialized
  profile/migration modules, retaining identity aliases and historical encodings
- Add a checked static dependency graph including relative imports and explicit
  architectural ownership boundaries; retain documented lazy/type cycles
- Add a progressive Spanish entry, small existing-API route and eight synthetic
  installable journeys covering refactors, native migration, local ETL, finance,
  telemetry, data science preparation, snapshots and portable review
- Demonstrate a complete external SQLite producer through existing snapshot ports,
  with one consistent owned read transaction and exact declared Arrow schemas
- Add reusable local quick checks with fixed-action, read-only GitHub tooling;
  the owner subsequently requested manual-only GitHub execution to avoid Actions
  minutes. Quick, platform and candidate workflows require explicit dispatch
- Add bounded engineering measurement tools; unchanged guarantees, no claimed
  speedup, and missing resource observations remain visible

No public publication, service deployment, license/visibility change, completed
source-security assessment, human pilot or real service/DW acceptance is implied.
Serialized formats, scientific methodology and private Alpha version remain intact.


Private 0.11.1 candidate; identify this revision by commit and exact artifact
hashes. Public release, licensing, platform qualification and adoption remain
separate unresolved gates.

- Preserve workflow indexes and native provenance across captured inputs; isolate
  unrelated source failures and consumer-specific resource budgets
- Reject every out-of-range pandas arithmetic intermediate. DuckDB refuses
  nested arithmetic/predicates whose eager errors SQL optimization can omit;
  corrected compiler identities include `/arithmetic-checks-v1`
- Retain native dtype observations and provider notes through migration detachment
  and child captures. Document direct compiler/execute input preconditions
- Expose generic pinned snapshots from core, with exact historical benchmark
  aliases, manifest format/fingerprint preservation and no new base dependency
- Remove source-owned completed-run bookkeeping; verify per-run manifest reuse
  across contexts with different budgets. Add a core-only installed
  snapshot example and an extension guide for source, adapter and compiler ports
- Use defaults only for `None` configuration arguments; reject invalid falsey
  values before work while retaining valid strict mappings and model instances
- Preserve operational CLI exit statuses and first-line codes; add shared
  fixed-text recovery hints without rendering raw exception payloads
- Regenerate only the current synthetic rule catalog because its fingerprint
  binds the edited rules.py implementation bytes; rule formulas and all historical
  fixtures remain unchanged
- Preserve candidate-check receipts/logs against accidental reuse of an output
  destination; earlier failed attempts remain reviewable

Historical JSON formats, comparison truth-testing rejection, exact value
semantics and independent R/M/B/H/O boundaries remain intact. The workflow and
arithmetic corrections can reject previously accepted defective cases; preserve
old evidence and rerun affected plans before using them for acceptance. This is
ordinary functional/architectural review, not a completed security assessment.

# STEP10 candidate: adoption records and sustainable maintenance

Private 0.11.1 candidate, identified by exact commit and artifact hashes.

- Add a strict local developer-only pilot-record checker and honest empty
  registry. Distinguish synthetic replays, consented human attestations,
  later-change retention, unknown effort and critical incident evidence
- Add a standalone synthetic repeat-use replay for Python refactor,
  SQL/DuckDB and CI-style assertions, with exact contracts and independent
  literal expectations. Technical repetition does not establish human adoption
- Package adoption and maintenance guidance; provide minimal issue templates,
  pending owner/backup roles, proposed priorities and false-equivalence response
- Keep runtime APIs, comparison semantics, historical schemas and dependency
  ranges unchanged. First-use kit v1 retains its closed inventory

No real pilots, human five-minute result, nominal maintenance assignment, SLA,
new engine, completed security assessment or public publication is claimed.
The source-security assessment and retained advisory triage remain unresolved;
public release stays closed pending owner decisions and the global review.

# STEP9 candidate: distribution, English handbook and release controls

Private 0.11.1 candidate, identified by source commit and artifact hashes.

- Package the standalone English handbook in wheel and sdist; translate the
  first-use kit documentation without changing recipe behavior
- Verify byte-identical wheel and sdist rebuilds, outside-checkout consumption,
  separate optional profiles and historical reader tests
- Add artifact-bound CycloneDX dependency inventories, license observations and
  explicit dated vulnerability-query evidence with unavailable states preserved
- Add a tested fail-closed publication-readiness gate; the dormant workflow
  contains no upload step, credential or OIDC permission
- Document threat boundaries, incomplete security assessment, incident response,
  immutable releases, withdrawal and isolated rollback

No project license, public publication, new maintainer/SLA or completed source
security scan is claimed. Existing runtime APIs and protected historic formats
are unchanged by this engineering stage. See `docs/index.md`.

# Changelog

- Preserve the declared Polars 1.30 minimum: use exact native Decimal coefficients
  for addition/subtraction and Int128 quotient/remainder kernels. Native Int128
  column arithmetic in that release can panic. Keep boolean coefficient casts
  explicit, and accommodate the supported pandas 2.2 typing stubs.

## Candidato STEP8 (2026-10-06)

- Reduce llamadas redundantes al sistema de archivos en cada control de disco
  del comparador mediante scandir. Conserva frecuencia, errores, cancelación,
  trabajo, tiempos y umbrales; no cambia normalización, alineamiento, contenido
  exacto ni evidencia. Casos medidos y límites en docs/SCALING.md.
- Añade regresiones de contabilidad, enlaces, cierres y fallos de recursos.
  No cambia API pública, formatos históricos ni límites declarados por defecto.

## Candidato STEP7 (2026-10-06)

- Nueva captura explícita `capture_duckdb` y `DuckDBCaptureOptions`: consulta
  confiable, consumo único por lotes, snapshot Arrow desacoplado, presupuestos
  cooperativos y propiedad/conservación de sesión documentadas
- Rechazo fail-closed antes de Arrow de HUGEINT/UHUGEINT, UUID y tipos nativos
  sin transporte fiel declarado, también en `DuckDBAdapter`. Antes podía
  ocultarse una pérdida (UHUGEINT máximo pasa a -1 en DuckDB 1.5.6).
  Use un cast SQL explícito solo si el rango y la semántica del caso lo permiten
- Los parámetros Decimal se enlazan con tipo nativo y texto exacto en ambas
  rutas: la inferencia DuckDB de `Decimal("1E-38")` podía degradar a DOUBLE.
  Parámetros Decimal no representables o enteros fuera de 64 bits se rechazan;
  para una conversión deliberada, pase texto y un cast SQL explícito
- La nueva API es experimental. Formatos anteriores, comparación, política de
  esquema, IR de migración y lectores históricos conservan sus contratos
- Fallos nativos tardíos envueltos por Arrow como `OSError` conservan cancelación
  o timeout, omiten SQL/valores del diagnóstico público y limpian staging.
  Los errores de escritura/fsync siguen identificándose como I/O


## Sin publicar — revisión del candidato 0.11.1

- STEP6: clasificación pública de estabilidad, política de deprecación y registro
  de capacidades por etapa. Lectura de fixtures históricas inmutables; rechaza
  versiones futuras en los expedientes, incluido environment.json rehasheado.
  Nuevas guardas Polars rechazan pérdida de dimensiones en captura/conversión.
- Metadatos Python ampliados a 3.12/3.13 tras evaluación, con locks revisados y
  matriz ejecutable de extras/dependencias mínimas directas y recientes permitidas.
  Cada resultado identifica el mismo wheel y su entorno; no acredita SO/arquitecturas
  no ejecutados, compatibilidad de todo el rango, ni CI remota. Ver STEP6_CANDIDATE.
- Regresiones de transporte comprueban float16 con un escalar representable en
  Arrow20, sin admitir ese tipo. El test ML compara los splits con sklearn nativo
  y mantiene una prueba determinista de rechazo de bosque sin splits; no fija
  umbrales que difieren entre versiones nativas ni cambia el método del detector.

- STEP5: kit de primer uso con tres recetas autocontenidas, wheel identificado,
  dependencias bloqueadas con hashes, guía de interpretación y formulario de
  observación humana sin completar. Refactor pandas con clave/bolsa, migración
  nativa acotada pandas → DuckDB y receta pytest/CI existente con evidencia
  previa al fallo. El verificador instala el kit fuera del checkout y comprueba
  códigos, reportes y políticas; no se anuncia una prueba humana de cinco minutos,
  nueva compatibilidad, nueva semántica, CI remota ni publicación.

- El verificador del candidato actualiza dependencias locales `path` y vincula
  sus bytes runtime importados al cierre de fuente, para impedir que una copia
  antigua del mismo candidato valide accidentalmente el benchmark nuevo.
- STEP4: `assert_equivalent`, `equivalence_decision`, `EquivalencePolicy` y
  `EquivalenceDecision` exigen equivalencia completa bajo contrato, con hashes
  y referencia fijables y evidencia persistida verificable de forma opcional.
  Errores tipados distinguen diferencia, no evaluabilidad, garantía, evidencia
  y configuración; diagnóstico seguro y esquema de aceptación propio 1.0.
- Cambio de compatibilidad deliberado: truth testing de `ComparisonResult` y
  `EquivalenceDecision` lanza `TypeError`; use la aserción o campos explícitos.
  No cambia el formato serializado previo. No se convierte `not_evaluable` en
  `False`, diferencia ni éxito.
- CLI compare conserva códigos 0/1/2/3 y JSON stdout, añade diagnósticos seguros
  stderr y valida el resultado antes de emitir éxito. Recetas pytest/CI guardan
  una vista redactada antes del fallo, con cuatro archivos permitidos. Pruebas
  instaladas comprueban éxito/fallo y privacidad; no se añade plugin, dependencia,
  workflow remoto ni publicación.

- STEP3: `comparison_report` produce un `ComparisonReport` 1.0 común para JSON,
  consola, HTML y notebooks; redacción conservadora por defecto, tipos escalares
  fieles, posiciones por lado y recuentos exactos/cotas/desconocidos. No vuelve
  a ejecutar fuentes ni cambia `ComparisonResult` o el comparador.
- `write_comparison_report` y `read_comparison_report` publican/leen vistas
  independientes. Inspección de evidencia con raíz autorizada, límites, hashes
  y defensas frente a archivos corruptos/rutas/symlinks. Reproducción opcional
  de capturas materializadas con contexto y manifiesto; ejecución original,
  cifrado, borrado de originales y assertion helpers quedan fuera del alcance.
- HTML escapado sin scripts/recursos remotos y CSP; texto con controles visibles;
  pruebas de redacción, claves con ámbito, límites y fallos de publicación. El
  ejemplo de reporte corre también desde wheel, y la lectura/render usa la base
  instalada sin dependencias tabulares ni notebook.

- STEP2: `diff` acepta tablas eager pandas/Polars/Arrow, construye contratos a
  partir del esquema derecho y delega al mismo núcleo de comparación.
  `DiffContract`, constructores de clave/bolsa/secuencia y `read_diff_contract`
  hacen visibles todas las políticas y su procedencia sin cambiar los formatos
  anteriores. Claves explícitas, valores estrictos y fallback existente.
- Captura nativa con límites de filas/bytes, snapshots aislados, conservación de
  índices significativos y rechazos explícitos para categorías, metadatos sin
  política, tipos no fieles, planes lazy y relaciones DuckDB. No ejecuta SQL.
  Las opciones de comparación, diagnósticos y estados conservan su significado.
- Pruebas de paridad pública, captura, procedencia y claves globales; ejemplo
  directo ejecutado por el verificador del wheel fuera del checkout. No añade
  HTML/aserciones en STEP2, amplía versiones/plataformas ni publica paquetes.
- Cuarentena explícita del auxiliar incompleto `equiframe.benchmark`: sus siete
  funciones conservan los argumentos anteriores pero lanzan
  `UnsupportedBenchmarkError` antes de leer entradas, entrenar o escribir.
  Se retiran las métricas ficticias, la calibración con datos de entrenamiento
  y el proxy de conteo presentado como R; no hay resultados sustitutos.
- El módulo y `examples/benchmark_local.py` terminan con código 2 y una guía al
  paquete separado `equiframe_benchmark`; `--help` sigue disponible. Ese paquete
  no es un reemplazo directo: conserva sus requisitos de revisión y protocolo.
  Las API soportadas del núcleo, sus formatos y el import ligero no cambian.
- `equiframe compare` devuelve 0 solo para una comparación completa y
  `equivalent`, 1 para una completa y `different`, y 3 para todo `not_evaluable`,
  incluida una referencia esperada inválida con `complete=True`.

## 0.11.1 — 2026-10-03

- Decimales exactos de ingestión, IR, ejecución nativa y sumas R aislados del
  contexto decimal del consumidor, conservando sus flags y sin autorizar redondeo.
- Exponentes JSON fuera de rango siguen rechazo/cuarentena; expansión de registros
  comprueba presupuesto y cancelación antes de materializar la colección completa.
- Recibos de calidad vinculados a bytes de fuente, dependencias locales y
  wheel/sdist; evidencia histórica legible pero insuficiente para un candidato nuevo.
- Productores 0.11.1 añadidos a DetectorVersions conservando los anteriores y
  esquemas 1.0. Python 3.12, motores y dependencias bloqueadas sin ampliar soporte.

## 0.11.0 — 2026-10-03

- Verify reutilizable para artefactos, ejecuciones y migraciones; dimensiones
  separadas y puente opcional de O, sin cambiar los algoritmos R/M/B/H.
- CSV/JSON/JSONL con esquema explícito, copias originales, conversiones exactas,
  rutas/grano y cuarentena; workflow de checkpoints y destino Parquet con staging,
  gate de Verify, versiones, visibilidad local atómica e idempotencia.
- JSON vacío rechazado sin salida; desbordamiento timestamp rechazado o puesto
  en cuarentena antes de materializar Arrow, conservando límites int64 exactos.
- Carga Parquet rechaza colisiones de nombres sin distinguir mayúsculas antes
  de escribir; recibos y versiones conservan una identidad física inequívoca.
- IR nativo ampliado con aritmética acotada, coalesce, condiciones, concatenación,
  deduplicación explícita y semi/anti join. Capacidades/rechazos trazables por prueba.
- Bundles cerrados para Verify/migración/workflow, lectura relocalizada sin ETL,
  protección de rutas y comprobación de decisiones/refencias a evidencia.
- API/CLI, once esquemas nuevos, productores previos de detectores preservados,
  ejemplos genéricos y OCDS sintético/consumidor real sin descarga implícita.
- Twine reproducible, verificadores de wheel/sdist ampliados, manifiesto de
  candidato y automatización separada de publicación. Python 3.12 sin ampliar
  plataformas; licencia, publicación e integración DW/OCI pendientes.


- Informes de migración distinguen la comparación con el esperado aportado de
  EquiFrame Verify (O), cuya independencia/revisión humana no establece el runner.
  Resúmenes conservan estados y evidencia de las tres comparaciones por separado,
  mantienen la clave histórica y permiten leer reportes previos completos.
- Pruebas integradas de las seis direcciones para NULL/NaN, uniones many-to-many
  sin coincidencia NULL, claves/multiplicidad y sumas Decimal por moneda con
  esperados literales. Son verificaciones sintéticas de software.

## 0.10.0 — 2026-10-03

- EquiFrame Migrate: IR relacional estricto, compiladores nativos Pandas/Polars/
  DuckDB y registro explícito extensible; seis direcciones entre los tres motores.
- `migrate`, `check_migration`, `read_migration` y `migration_summary`; captura
  única aislada, comprobación de ambos motores antes de ETL, esperado separado,
  perfiles/detectores congelados y presupuestos cooperativos de extremo a extremo.
- Diferencias observadas y comprobación contra esperado se conservan separadas.
  R es requerida por defecto; `require_rules=False` permite exigir solo los
  componentes declarados sin convertir estados ausentes de R/H en «sin alerta».
- CLI migration validate/run/verify, reportes, journal e inventario cerrado;
  lectura verifica archivos, referencias y metadatos físicos sin ejecutar ETL.
  Manifiesto publicado al final; operaciones interrumpidas permanecen visibles.
- Cinco JSON Schema nuevos 1.0. `DetectorVersions` añade el emisor 0.10.0 y
  conserva productores anteriores; sus esquemas reciben la ampliación compatible
  de enum/default. No cambia el algoritmo de inferencia ni entrena durante migración.
- Ejemplo con Decimal, monedas, grupos nulos y esperado literal independiente.
  Timestamps/operaciones float declaradas fuera del IR inicial; plugins confiables,
  límites de buffers tras materialización y evidencia local sin portabilidad automática.

## 0.9.0 — 2026-10-03

- API aditiva `detect_component` y resultado `ComponentDetectionResult` para
  inferir M o MAD con el preprocesador y la calibración congelados, sin puntuar
  el otro detector. Conserva los scores, umbrales y decisiones de `detect`.
- Huellas del bundle, ajuste, perfiles y matriz enlazan el resultado aislado a
  sus entradas. Los modelos/calibraciones no estimables conservan sus motivos
  y scores ausentes; las mediciones fallidas o incompatibles se rechazan.
- Paridad de inferencia, restauración declarativa y regresiones de independencia;
  formatos anteriores y algoritmo conjunto conservados. El benchmark separado
  incorpora evaluación y costes operacionales del paso 10.
- `DetectorVersions` admite el emisor 0.9.0 y conserva productores explícitos
  0.7.0/0.8.0/0.8.1. Sin ajuste implícito, nuevas etiquetas ni publicación PyPI.

## 0.8.1 — 2026-10-02

- Revisión del paso 8 frente al TFM: conserva objetivos, fórmulas, separación de
  detectores/oráculo y pendientes científicos; corrige referencias de estado.
- Verificación de evidencia vinculada a las capturas y referencias inventariadas;
  rechaza artefactos omitidos y reducciones inconsistentes con sus observaciones
  y posiciones originales.
- CLI de evidencia/reportes distingue corrupción de una petición inválida.
- Formatos 1.0 y bundles explícitos 0.7.0/0.8.0 conservados; la versión emisora
  admite 0.8.1. Distribución privada; publicación pública sigue en el paso 19.

## 0.8.0 — 2026-10-01

- Paso 8: API `run_pipeline`, configuración/resultados estrictos, R/perfil/M/B/H
  y comparación opcional sobre una captura nativa; sin entrenamiento implícito.
- Eventos encadenados SHA-256, manifiestos exclusivos, inspección de interrupciones
  y verificación de archivos, procedencia y consistencia de reportes JSON/HTML.
- CLI run/compare/report/evidence/reduce y CLI separada del benchmark; códigos
  0/1/2/3 que conservan la prioridad de fallos y componentes no evaluables.
- Reducción determinista por filas entre tablas, firma de fallo y precondiciones
  verificadas por predicado confiable, presupuestos y confirmaciones explícitos.
  Minimalidad local únicamente; nunca se afirma mínimo global.
- Siete esquemas nuevos 1.0. DetectorVersions acepta también 0.8.0 y conserva
  bundles 0.7.0 explícitos sin cambiar el algoritmo declarativo.
- Ejemplo instalado, pruebas nativas y distribución reproducible; PyPI, integración
  OCI/DW y cierre científico permanecen pendientes según el plan vigente.

## 0.7.0 — 2026-10-01

- Paso 7: Isolation Forest y MAD por familia sobre el mismo preprocesamiento,
  soporte explícito, calibración normal independiente y alpha decimal obligatorio.
- Cuantil empírico exacto sin interpolación, desigualdad estricta, MAD cero e
  infinito y estados no estimables; ninguna excepción se convierte en no alerta.
- H = R OR M con tres estados y conservación de alertas parciales.
- Árboles declarativos y bundles JSON verificables, sin cargar pickle/joblib;
  inferencia base sin ML y ajuste opcional mediante `equiframe[ml]`.
- Benchmark 0.7.0 incorpora selección normal de calibración y auditoría de grupos.
  Conserva contratos, perfiles y reglas 1.0. La API añade formatos independientes.
- Wheel/sdist, consumidor externo, tipado y pruebas. No publica en PyPI ni
  entrena modelos científicos con el piloto pendiente de revisión humana.

## 0.5.0 — 2026-10-01

- Perfiles de una captura para las cinco familias y diez métricas de la Tabla 13.
- Conteos y denominadores explícitos; NULL/NaN/vacío/cero, no aplicabilidad y
  fallos técnicos separados. Recibos para conversiones instrumentadas.
- Preprocesamiento normal de entrenamiento: medianas congeladas, indicadores,
  retiro documentado, incompatibilidades de versión/orden y matriz común M/B.
- Persistencia JSON sin sobrescritura; esquemas, cinco ejemplos y verificación
  del wheel fuera del checkout. M/B/H y el benchmark siguen pendientes.

## 0.4.0 — 2026-09-30

- Paso 4: `ef.evaluate_rules` verifica entradas y salida capturadas de una sola
  ejecución, con registro explícito de las seis formas de regla y precondiciones.
- Hallazgos JSONL completos, resumen acotado, cobertura, presupuesto y cancelación
  cooperativa; alerta observada conserva su estado ante evaluación incompleta.
- Catálogo técnico versionado para cinco familias y huella de contrato, código de
  reglas y configuración; consumidor Arrow sin tres motores.
- `ComparisonResult` rechaza manifiestos `equivalent` con conteos contradictorios
  y valida la coherencia de la estrategia/clave seleccionada.
- Nuevos documentos/esquemas de R 1.0, contratos/ejecuciones 1.0 conservados.
- Segunda revisión: la relectura de R rechaza decisión/completitud contradictorias,
  la aplicabilidad prioriza una precondición verificablemente falsa y `SchemaCheck`
  localiza tipos Arrow transportables incompatibles con el contrato.

No incorpora perfiles, M/B/H, oráculo, benchmark final, DW ni publicación PyPI.
Las estadísticas de conversiones anteriores a la captura requieren evidencia
adicional; no se reconstruyen de una salida final.

## 0.3.0 — 2026-09-30

- Paso 3: `ef.compare`, modelos completos, lectura de manifiestos y diferencias verificables.
- Esquema observado separado; validación de valores, claves/ámbitos, multiplicidad y orden.
- Normalización autorizada de ausencias, NaN y tiempo; decimales/enteros/ns sin pérdida.
- Alineación exacta por clave comprobada, secuencias, multiconjuntos y matching máximo aproximado.
- Lotes y SQLite privado con spill; presupuestos, cancelación y completitud explícita.
- Evidencia JSONL completa, ejemplos acotados, snapshots y corridas exclusivas.
- `ComparisonSpec` y documentos propios 1.0; contratos/artefactos/ejecuciones 1.0 intactos.
- Timeout de callback determinista mediante reloj controlado; caso previo al callback separado.
- Esperados independientes, propiedades, tres motores y consumidores instalados base/extras.

Instalar el nuevo wheel; ningún contrato antiguo se migra automáticamente. Los
permisos adicionales se expresan mediante `ComparisonPolicy` con justificación.
Soporte Python 3.12; sin publicación PyPI, despliegue OCI, R/ML/DW ni resultados
científicos añadidos. El comparador evalúa `output_schema`, no certifica el oráculo.

## 0.2.1 — 2026-09-28

- Conservación de anchos/signo NumPy y nullable Pandas, UInt64 extremo y máscaras Float32/64.
- Rechazo previo de categorías e inferencia ambigua de objetos numéricos heterogéneos.
- Límites explícitos de decimal256/escala negativa, segundos Polars y microsegundos zoned DuckDB.
- Rechazo de infinito/sentinels temporales DuckDB en entradas y salidas, sin ocultarlos como fechas finitas.
- Captura parcial referenciada si falla el índice; presupuesto de buffers del índice y limpieza de descargas.
- Copia aislada de índices/columnas en fuentes inyectadas y cierre DuckDB durante setup cancelado.
- Diagnóstico de pánicos nativos Polars; etapas anidadas y puertos runtime validados.
- Coherencia estructural de manifiestos: huella, entradas, salida, formatos y conteos de ausencias.
- DuckDB mínimo 1.5.6, versión comprobada con la API usada; formato JSON 1.0 conservado.
- 142 regresiones adicionales de motores reales; documentación de producto e integración OCI.
- CI extendida a macOS Intel/Apple Silicon y Ubuntu ARM64, con triggers para ramas de cualquier colaborador.

La captura fiel puede rechazar entradas antes aceptadas mediante conversiones que
perdían información. No incorpora comparador ni conexión remota al DW.

## 0.2.0 — 2026-09-28

- Paso 2: `ef.execute`, planes/resultados estrictos, contexto, capacidades y registro por instancia.
- Adaptadores nativos Pandas, Polars lazy materializado y SQL DuckDB local parametrizado.
- Fuentes Arrow/Pandas/Polars/locales y almacén con integridad y publicación exclusiva.
- Evidencia separada del esquema esperado, índices Pandas y diferencias conservadas.
- Cancelación/timeout cooperativos, interrupción DuckDB y presupuestos documentados.
- Extras arrow/pandas/polars/duckdb/engines; importación base ligera y versión/lock actualizados.
- Ejemplos de comercio/telemetría, cinco familias, integración real y distribución fuera del checkout.
- CI Windows/Ubuntu para ramas de pasos y PR dependientes, base y cada extra instalado.

Contratos y ArtifactRef siguen en formato 1.0; el nuevo manifiesto de ejecución usa
su propio formato 1.0. Actualizar desde 0.1 requiere instalar extras para procesar
tablas; la API declarativa se conserva. Sin comparación general, R, ML o benchmark;
sin publicación PyPI ni cambios de tesis/DW/servicio remoto.

## 0.1.0 — 2026-09-28

- Primera API pública del paso 1: contratos semánticos estrictos, inmutables y versionados.
- Validación cruzada de esquemas, claves, tipos, políticas, intervalos y reglas declarativas.
- JSON canónico, SHA-256 de metadatos y esquemas JSON generados.
- CLI `equiframe contract validate`, con errores localizables y salidas documentadas.
- Fixtures sintéticos para cinco familias, pruebas por propiedades y distribución tipada.
- Bloqueo reproducible de desarrollo/ejecución y controles Windows/Ubuntu, Python 3.12 x64.
- Segunda revisión: hash independiente del contexto decimal, base IANA bloqueada,
  unidades/tipos coherentes en reglas y literales float32 exactos sin pérdida.
- Diagnósticos temporales y JSON duplicado específicos/localizables/imprimibles;
  errores de rutas inválidas y validación estricta de sintaxis de URI.
- Verificación ampliada de distribución: API/errores CLI instalada, consumidor
  mypy y batería completa contra wheel reconstruido desde sdist.

No incluye ejecución de reglas, adaptadores, comparador, modelos ni benchmark.
Los formatos del paso 1 usan `schema_version="1.0"`; cambios incompatibles requieren
nueva versión de esquema y migración expresa. No se hace migración automática.
