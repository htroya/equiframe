# Post roadmap functional review and refactoring

Date: 2026-10-06 UTC. Base candidate: `d97aa9db0d1b07a81f1c69f05b736923b46ad9de`.
This private 0.11.1 revision follows the ten technical product steps. It reviews
ordinary functionality, architecture, typing, extension boundaries, maintainability,
installation and developer journeys across the repository. It is not a completed
source-security assessment, a scientific result or a public-release authorization.
Identify the revision by its commit and exact wheel/sdist hashes.

## Correctness before cosmetic changes

| Finding | Resolution |
|---|---|
| Workflow dropped a captured pandas index and could pass where direct migration refused | Preserve the complete capture and runtime index significance through the workflow source boundary |
| One failed source or expected artifact skipped independent stages | Record failures per source/expected stage; retain valid captures and skip only dependents |
| First-stage capture limits constrained unrelated stages | Derive per-source consumer envelopes, followed by each stage's unchanged limits |
| Intermediate arithmetic overflow could disappear into a predicate, zero or NULL | Check every pandas arithmetic result; refuse unsupported eager DuckDB shapes in preflight |
| Migration detachment lost native dtype/notes provenance | Carry native observations and provider notes through root and child captures |
| Falsey invalid options or expected mappings silently selected defaults | Defaults apply only to None; malformed values fail before work |
| Generic snapshot consumer required the experimental package | Move implementation to core with exact benchmark aliases and no new base dependency |
| Snapshot source retained completed-run identities | Remove the run cache; verify/reuse exact manifest bytes and configuration per run |
| CLI errors lacked useful next steps | Share fixed-text recovery hints while preserving first-line codes and exit meanings |
| Table/pairwise handling repeated deterministic bootstrap validation | Validate once per public boundary and format already-validated data privately |
| Candidate reruns could overwrite receipt/log/temp evidence | Refuse reused output sets and reserve new receipt/logs exclusively |
| Root setup script targeted a nonexistent parent project | Use the actual core package and locked local environment; no OS updates |
| SERCOP prototype SQL had mechanical column-list/placeholder errors and returned 0 after partial failures | Correct those mechanics and report failure; defer domain policies to the owner |
| Lower-level compiler input preconditions were implicit | Document them and test that migrate enforces admission while execute alone establishes no equivalence |
| Sdist contributor instructions implied Git-bound checks were standalone | Distinguish source checks, Git-bound candidate checks and adjacent-core benchmark checks |

The initial context-lifetime cache correction exposed a two-table workflow
interaction during independent review. Final code has no source-owned cache and
passes the full snapshot/workflow interaction. The final benchmark distribution
verifier also stages the sdist's schema directory beside installed tests; the
failed earlier attempt is retained in the evidence package.

## Useful architectural changes

The six new core exports are `SnapshotClient`, `SnapshotColumn`, `SnapshotTable`,
`SnapshotManifest`, `SnapshotDataSource` and `snapshot_fingerprint`. Their core
classification is experimental. Historical benchmark imports alias the same
objects, and manifest format 1.0 retains its exact schema, strictness and
ASCII-escaped canonical JSON/fingerprint. Base users can work with metadata
without Arrow or benchmark; resolution still requires Arrow. Transport,
authentication, timeouts and service coordination remain responsibilities of an
explicitly injected client.

The [packaged extension guide](../packages/equiframe/docs/extending.md) and
`examples/snapshot_source.py` provide a core-only synthetic snapshot-to-DuckDB
comparison journey. Existing structural ports and instance-owned registries
remain the extension mechanism. There is no implicit plugin discovery or new
framework. Native pandas, Polars and DuckDB implementations remain independent.

Large schema/algorithm modules were not split merely to reduce line count, and
345 existing public names were not renamed or removed. Six core snapshot exports
are additive. Shared private document and CLI helpers remove concrete coupling;
serialization algorithms with different historical contracts are not conflated.

## Observable compatibility corrections

Corrected pandas and DuckDB compiler versions end in `/arithmetic-checks-v1`;
the revision participates in newly generated transformation identity. DuckDB now
refuses nested arithmetic and arithmetic predicates because native optimization
can omit their required intermediate overflow errors. One direct arithmetic
projection, with the documented optional final Sort suffix, remains supported.
Polars implementation identity is unchanged.

The lower-level `compile(...).transformation` assumes actual inputs conform to
the validated IR. Use `migrate` for enforced physical/value admission. Generic
`execute` faithfully captures native execution; a completed result alone does
not establish semantic equivalence or input conformance.

Configuration defaults still work for None and valid strict mappings/models.
Invalid False, 0 or sequence values are no longer accepted as omitted settings.
CLI stdout decisions and historical first-line failure codes/exits remain;
error stderr adds one bounded recovery hint. The standalone benchmark pilot
retains failure exit 1.

All 219 previously tracked schemas, versioned fixtures, package locks and the
protected thesis-traceability file remain byte-identical. Only the current
synthetic rule catalog is regenerated because its implementation fingerprint
binds the edited rules.py bytes. Rule formulas and historical evidence are not
rewritten. Preserve affected old workflow/arithmetic observations and rerun with
the corrected implementation before using them for acceptance.

## Verification and measured benefit

- Core: 2,949 distinct tests passed from source and again from installed artifacts
- Benchmark: 561 distinct tests passed from source and again from installed artifacts
- Root helpers: 12 synthetic command/SQL-shape tests, plus Bash syntax and style checks
- Total distinct source cases: 3,522; repeats are execution evidence, not additional tests
- All 18 package gates pass: locked sync, Ruff, formatting, mypy, generated assets,
  complete source tests, build, strict Twine and installed-distribution verification
- Both wheel/sdist pairs rebuild byte-identically. Clean base/extras, installed
  handbook/recipes and the new core-only snapshot journey are exercised
- An independent clean installed consumer verified unchanged aliases, exact
  Unicode snapshot bytes, the corrected workflow/arithmetic/configuration cases,
  the two-table snapshot integration and expected negative recipe exits
- Table read/write reduces full evaluation validation calls from 2 to 1; pairwise
  construction from 3 to 2. Historical report, pairwise and six CSV bytes remain
  identical. This is a computation-count reduction, not a timing SLA

The fresh 12-cell Linux x86_64 Python 3.12/3.13 minimum/recent dependency matrix
is recorded separately against the final artifacts. Its final receipt, exact
artifact SHA-256 inventory and all retained attempts accompany the candidate.
Only cells actually completed establish compatibility; configured remote jobs
and historical platform results are not reinterpreted as new executions.

## Boundaries that remain open

The source-security assessment remains incomplete. This phase did not retry it
or perform a new advisory query. Offline final-artifact inventories preserve 71
core and 67 benchmark components; external dependency metadata is unchanged from
STEP10. Historical PyArrow 20 advisory CVE-2026-25087 triage retains the upstream
Python-binding exclusion; it is not a blanket clearance of the package.

Public distribution is still blocked on owner licensing, name/channel/publisher,
responsibility and exact release approval. There are zero established real human
pilots; the five-minute human criterion, independent retained adoption and
response commitments remain pending. No new Windows, macOS, ARM64, AlmaLinux,
production service or real DW qualification is claimed. Cooperative budgets
remain different from hard process quotas.

The SERCOP/DW prototypes are excluded from the two distributable packages. Their
composite identity, exact monetary parsing/reconciliation, multiple suppliers or
items, missing-value/date policy, transactions/publication/concurrency and path
handling require owner review. Narrow mechanical fixes do not qualify those
workflows for production; see their [scope notice](../packages/equiframe-sercop/README.md).
The private core improvements do not replace those responsibilities or establish
universal Python/data-type compatibility.
