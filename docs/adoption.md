# Adoption: real projects and repeat use

[Handbook](index.md) · [Installed recipes](recipes.md) ·
[Maintenance and incidents](maintenance.md) · [Upgrading](upgrading.md)

## Current status and the acceptance boundary

As of **2026-10-06**, no independent human pilot, participant consent or retained
real-project integration is recorded. The three STEP1 pilot definitions and the
first-use kit provide a starting protocol and synthetic technical exercises.
They are not three external projects. Automated recipe execution, independent
artifact review and a repeated technical replay cannot establish human adoption
or the five-minute first-diagnosis target. Both remain **pending**.

STEP10 adoption needs **at least three independent real projects**, collectively
covering Python refactoring, SQL/DuckDB and CI regression checking. Each project
needs an independently observed initial use and retained integration through a
later real change. The consumers must be independent of the implementation they
are assessing. Review shared authorship, people, data and project ownership when
assessing independence; splitting one project into jobs or repeating one fixture
does not create independent projects. Consent, independence and outcomes require
human review, not a positive field in a JSON record.

The historical adoption requirements above remain unaccredited; a stable API or
registry publication does not count as human adoption or scientific acceptance.
The owner has separately authorized manual 0.12.2 TestPyPI/PyPI preparation and
publication subject to its technical/security/ownership gates. Project-owned
code is MIT and the maintainer role is assigned. Check [release status](releasing.md)
for completed publication facts and [security](security.md) for safe reporting.

The earlier Linux x86_64 and Python-3.12-only kit results retain their historical
scope. Current measured Windows/Linux ARM64 Python 3.10–3.13 implementation runs
are described in [compatibility](compatibility.md); interpreter-specific kits
need their own matching pins and artifact checks. Neither table establishes
human adoption, and old receipts do not validate changed wheel bytes.

## U12 acceptance for the 2026-10-07 usability plan

The three eligible first-use observations must each reach a correct first diagnosis
within **300 seconds**, without essential instructions outside the supplied guide.
This threshold is an explicit acceptance condition of that plan, not a measured
product property. At least one participant must perform data-architecture tasks
and one data-science tasks. Consent and independence require human review.

Freeze timing before observation: Python preparation and obtaining the kit are
recorded separately; start at the beginning of installation and stop only at the
first correct diagnosis. Include dependency downloads, retries, failed attempts
and help. Never move the starting clock after seeing a result. Keep an unfavorable
first-use observation; an already-practiced participant cannot produce a new
first-use observation. Revalidation needs new independent participants. Retained
integration after a later real project change is a separate necessary condition.

[Three fictional role profiles](piloto-simulado.md) may rehearse instructions.
They have no consent, human measurements, real projects or adoption credit.
The schema checker only checks record consistency; it cannot close U12.

## Before an observation

This is a protocol for an authorized pilot; it does not recruit participants,
contact consumers, grant repository access or authorize sharing their data.

1. Agree the real decision: which refactor, query or pipeline change must preserve
   which meaning, and who reviews the expected result. Select the smallest useful
   supported contract before seeing the candidate result
2. Obtain explicit consent for the observation and agreed use of its record.
   State the purpose, fields collected, permitted readers, retention/review date,
   contact for withdrawal and whether a sanitized issue may be shared. Permission
   to observe is not permission to publish data, identify a company or send a report
3. Use a random project/participant alias. Keep the consent and identity mapping
   locally, outside Git and apart from technical evidence. A hash of a consent
   reference binds bytes; it neither anonymizes a person nor proves consent
4. Obtain an identified artifact and trusted hash through the reviewed registry
   or offline channel. If a kit is provided, verify it and install outside the
   checkout as [recipes](recipes.md) describes. Verify registry ownership rather
   than installing an unrelated package solely by name
5. Agree what success and safe refusal look like, including complete differences,
   invalid expected data and incomplete evaluation. Keep raw data local. Identify
   a permitted minimal reproduction and an appropriate evidence retention location
6. Record unavailable prerequisites honestly. If consent, data rights, safe handling
   or the required capability is missing, stop that observation and leave it pending

Use the kit's separate `OBSERVATION.md` for first-use timing and interpretation.
Keep the immutable kit unchanged. Record preparing Python and obtaining the kit
separately, then time installation through the first correct diagnosis without
discarding download time, unsuccessful attempts or help. Automated command duration
must not be reported as human diagnosis time.

## The three real-project paths

| Context | Initial real use | Later change required for repeat-use evidence |
|---|---|---|
| Python refactor | Compare the project's original and revised captured outputs under a reviewed contract; validate expected behavior independently | A subsequent real code or data revision still uses the integration and preserves the required gate and evidence |
| SQL/DuckDB | Use trusted explicit capture or supported native migration; preserve Decimal, NULL, keys, duplicates and the expected-output distinction | A later real query, plan or input revision is checked without silently broadening the supported subset or weakening its contract |
| CI regression | Integrate the explicit assertion into the project's real test workflow, retain a minimized verified report before failure and keep nonzero status | A later real change still runs the check; the consumer can locate evidence, explain the decision and update safely |

The installed recipes teach these paths with synthetic data. Replace their
fixture selectors with the real project's authorized candidate/reference pair;
do not present the tutorial's deliberate regression as a discovered production
defect. Local CI-style execution is not proof that a remote CI job ran. Keep the
exact authorized run reference if a real CI run is part of the observation.

For every path, ask the consumer to explain:

- Why `equivalent` is limited to captured data and the evaluated contract
- Why two native engines can share a bug, and where the independent expectation
  came from; pandas is not an oracle
- Why `different` fails the gate, and why `not_evaluable` is a safe abstention
  rather than success, even when `complete=True`
- Where keys/positions, types, policies and retained evidence explain the result
- How to report a problem and test an [upgrade or safe rollback](upgrading.md)

Preserve answers and assistance as observations, including misunderstandings.
Do not supply an answer and record it as an unaided explanation. A correct safe
refusal can be a useful pilot outcome; it is not accepted equivalence and cannot
by itself demonstrate a completed integration.

## Minimal local observation record

Collect only information needed to reproduce or interpret the observation:

- Pseudonymous project ID, context, participant role and independence explanation
- Consent status and a local reference to the separately retained permission;
  record withdrawal and exclude withdrawn observations from adoption claims
- Date/time with timezone, exact commit and wheel/kit/dependency-lock hashes,
  Python/OS/architecture, installed engine versions and selected extras
- The project's real revision/change, contract revision/hash, expected-output
  provenance and any separately reviewed requirement change
- Installation, integration and diagnosis effort; actual help, failed attempts,
  commands and sanitized errors. Unknown measurements remain unknown, not zero
- Expected versus observed state, completeness and gate decision; evidence hash,
  missing evidence and what the consumer found useful or could not interpret
- A later observation's changed project revision, retained integration, outcome,
  report/update knowledge, unresolved issues and consumer reconfirmation
- Maintainer effort for triage, reproduction, correction, documentation and
  consumer follow-through, with the relevant issue/correction reference

The structured local record supplements the human observation; it is not a
telemetry service, a public API, a signed attestation or a scientific dataset.
Keep free text short and sanitized. Never collect credentials, environment dumps,
full SQL containing secrets, real rows, raw evidence paths, personal identifiers
or contact details simply because they might help later. Keep any indispensable
private reproduction under separately approved access rather than in this record.
Use opaque local references instead of private URLs with embedded tokens.

Before sharing, review metadata as well as values. Redacted reports do not remove
the original snapshots, spill files, exception causes or private evidence.
Hashing low-entropy values is not anonymization. Agree retention for the local
record, identity mapping and raw evidence separately; do not promise secure erasure.
Withdrawal stops further use outside the remaining permission and requires review
of retained/shared copies, not silent deletion of the historical outcome.

## Check the structured record locally

The verified source distribution carries the developer-only
`tools/check_adoption.py` and the intentionally empty
`examples/adoption/empty-registry.json`. The wheel carries this handbook, not a
new `equiframe` adoption command or runtime API. The existing first-use kit keeps
its closed inventory unchanged. To use the checker without a checkout, obtain the
matching verified sdist through the authorized channel and copy the checker to
a separate working directory if needed. Use an environment with the candidate's
reviewed Pydantic dependency; the checker does not install anything.

From the unpacked sdist's package directory:

```bash
python tools/check_adoption.py --schema
python tools/check_adoption.py examples/adoption/empty-registry.json
python tools/check_adoption.py /absolute/path/private-pilot-records.json
```

`--schema` prints the complete tool-only schema; use it for exact required fields
and limits. The empty registry contains only `schema="equiframe-adoption-1"`
and `pilots=[]`. It intentionally reports zero human observations and unknown
aggregate effort (`null`). Create completed records outside the kit, sdist and
Git; do not replace the empty example with invented people or results.

The principal field groups are:

| Group | Supplied observations |
|---|---|
| Pilot | `id`, pseudonymous `project_id`, `context` (`refactor_python`, `sql_duckdb`, `ci_regression`), `kind` (`human_pilot`, `synthetic_replay`), `independent`, `consent`, `consent_sha256`, `attempts` |
| Attempt identity | `id`, `phase`, timezone-aware `occurred_at`, real revision/change identity `change_sha256`, `package_version`, `wheel_sha256`, `dependency_lock_sha256`, `contract_sha256`, `contract_review_sha256` |
| Environment and effort | `python`, `os`, `architecture`, `engines`, `installation_seconds`, `integration_seconds`, `diagnosis_seconds`, `help_received` |
| Outcome and retained use | `expected` and `observed`, each with `state`, `complete`, `accepted`; `usefulness`, `integration_retained`, `knows_reporting`, `knows_upgrading`, `evidence_sha256`, `issues` |
| Issue observation | `id`, `category`, proposed `priority`, `false_equivalent`, reproduction/expected/observed hashes, `data_permission`, `status`, separate regression/consumer-confirmation hashes, `support_seconds` |

Use `null` where an optional observation is unknown. For an installation attempt
that reached no comparison, both `expected` and `observed` are `null`; do not
invent a semantic result. `accepted=True` requires complete equivalence, but a
complete equivalent result may still fail additional evidence requirements.
The actual assertion/report remains the source for those observations.

Human attempts require recorded consent with a separately retained receipt hash.
Synthetic records must use `synthetic_replay`, `independent=False` and
`consent="synthetic_only"`, without a human consent hash or consumer-confirmed
fix. They never enter the human counters. The schema has no withdrawal state:
record withdrawals in the separate permission ledger and exclude withdrawn
observations from active summaries under the agreed retention terms. Do not
rename a withdrawn human attempt synthetic or silently claim renewed consent.

Keep one chronological pilot history per project/context; append attempts rather
than creating another pilot ID that could hide an earlier failure.
The first attempt is `initial`; later attempts are `follow_up` in strictly
increasing time order. Changed established contracts require a distinct
`contract_review_sha256`. Retained-use counters inspect the **latest** follow-up,
require a changed `change_sha256` relative to the earliest useful completed
integration observation and check
the supplied usefulness, retained-integration and reporting/upgrading answers.
That integration baseline must contain a useful completed equivalent or different
comparison matching the independent expectation; preceding installation failures
stay in the history and effort counters. First successful installation/integration
is not itself retained use: a later changed observation is required. Safe
abstention alone cannot establish a completed integration. A
later useful safe abstention can show that an already established check remains
in use. Any P0/false-equivalence issue reported anywhere in the history blocks
the retained-use count until a later observation explicitly records that same
issue as consumer-confirmed. Omitting an issue or downgrading its priority does
not clear it.
They compare expected with observed fields instead of treating every recorded
outcome as success. The hashes do not establish that a real project changed or
that review occurred; retain the permitted supporting evidence separately.

Exit **0** means record consistency passed, including an honest empty registry;
exit **2** means invalid/unreadable input or invalid command use. Neither is a
human adoption decision. The tool reads one bounded regular JSON record, does
not follow the evidence references, execute a reproducer, contact anyone or
upload observations. It cannot authenticate consent, identity, independence,
semantic truth or the referenced bytes. Summary counters are **attestations**;
`human_adoption_verified` always remains `false`, and independent manual review
stays pending even if the proposed diversity target is recorded. No supplied
record can open the public release gate or establish a five-minute human claim.

## Synthetic repeat-use rehearsal

The sdist's `examples/adoption_replay.py` is a standalone technical check of the
three consumer contexts. Copy it outside the checkout and run with the exact
installed wheel and reviewed pandas, DuckDB and Arrow dependencies:

```bash
python -I adoption_replay.py --output /absolute/path/new-replay --wheel-sha256 VERIFIED_WHEEL_SHA256
```

Replace the hash placeholder with the separately verified lowercase SHA-256.
The script records that supplied hash but does not authenticate it or establish
which wheel was installed; independently check installed payload bytes and
import origins. The 24 observations are three contexts, two genuinely changed
synthetic input fixtures and four cases: equivalent, different, invalid expected
and resource-limited. Exact contracts remain unchanged, expectations are literal
fixtures, and failed assertions are preserved. SQL capture is compared after its
in-memory source has changed and the connection is closed.

Exit 0 means the expected technical outcomes were observed, including rejection
of deliberately wrong or unavailable comparisons; it does not accept those
outputs as equivalent. Exit 2 means setup, receipt or replay checks failed.
Keep the receipt and reviewed redacted report directories. Temporary raw
captures are removed; report integrity is not full raw-data reproduction.
Provenance includes local import paths, so review it before sharing. The replay
never fills a human registry, measures human effort, verifies reporting/upgrading
knowledge or claims a production CI job. It cannot close genuine repeat-use
acceptance or the five-minute first-use criterion.

## Classify friction without hiding safe outcomes

| Category | Useful minimal observation |
|---|---|
| Installation | Exact artifact/pins, interpreter/platform, import location and sanitized failing command |
| Comprehension | Task attempted, guide/version, the consumer's interpretation and assistance needed |
| Semantics | Small typed fixture, contract/policy, independent expected versus observed state/completeness and gate |
| Integration | Call site or CI step, selected API/adapter, environment boundary, evidence-before-failure and actual exit |
| Performance | Workload shape, exact environment/configuration, measured elapsed/resource scope, budget and final/partial status |
| Evidence | Missing or unreadable artifact, expected inventory/format, hashes, reader and observed verification outcome |

A problem can involve more than one category; select one primary category for
each structured issue observation and keep secondary context in its separate
triage evidence. Do not duplicate one observation to inflate category totals.
Separate a documented unsupported capability, a correct abstention and a defect.
Do not cast, round, deduplicate,
drop metadata, accept partial counts or relax tolerance to improve a success rate.
Installation failure is not a semantic pass. Zero displayed differences or a
successful integrity check is not an equivalence decision.

Convert a reproducible problem into an authorized, sanitized issue using the
[maintenance procedure](maintenance.md#report-a-problem). Preserve the original
attempt and connect the correction to a new exact artifact. Maintainer tests
are technical verification; only the affected consumer can reconfirm their own
integration. Keep that confirmation pending until it actually happens.

## Repeat use and useful indicators

A later timestamp alone is insufficient. Observe a subsequent real project
revision or workload change after initial integration, and establish that the
consumer retained the check and its evidence. Replaying the same fixture, a
second installation or a changed run ID is only technical repeatability.

If a genuine requirement changed, retain the old contract, failed result and
reference. Record the rationale and responsible review; create a new contract
revision and independently reviewed expected output. Keep that event distinct
from unchanged-contract regression checking. A copied candidate baseline or
silent policy relaxation invalidates an adoption success claim.

Report small-sample observations directly, with denominators and exclusions:

- Consented, independently reviewed real projects started and completed by context
- Projects observed after a later real change, and those retaining a working
  integration; show projects awaiting follow-through or withdrawing separately
- Consumer-confirmed useful differences, with the decision they helped make;
  tutorial mutations and merely emitted diagnostics are not confirmed benefits
- Safe abstentions, failed/abandoned attempts and unresolved blockers by category
- Observed installation/integration/diagnosis effort and help; show the individual
  observations rather than a universal five-minute claim
- Reproductions, verified corrections, consumer-reconfirmed fixes and unresolved
  incidents; a maintainer-only fix is not a consumer-confirmed resolution
- Actual maintenance effort and recurring burdens, with unknown effort explicit

At present the real-project count is **0** and the required minimum remains
**3**; repeat-use and consumer-confirmed-correction evidence are absent.
Rates with no eligible observations are **not available**, not 0% success or
failure. Downloads, stars, synthetic fixtures and repeated automated test runs
may describe activity but do not prove professional adoption.

## Review before declaring adoption

A responsible human reviews consent scope, project independence, original
evidence, interpretation, the real later change, retained integration, reporting
and upgrade knowledge, unresolved risks and sustainable maintenance ownership.
All three contexts need independent real projects. False-equivalence incidents
need the containment and correction process in [maintenance](maintenance.md),
not an optimistic aggregate metric. Technical validation never signs off these
human facts or opens the [public release gate](releasing.md).
