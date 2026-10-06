# Upgrading, recovery and support

[Handbook](index.md) · [Compatibility](compatibility.md) · [Security](security.md) ·
[Release/rollback](releasing.md)

## Before changing a dependency or candidate

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

## Observable changes in this private candidate

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

Pandas now enforces each arithmetic expression's declared range before its value
is used by another expression. DuckDB rejects nested arithmetic and arithmetic
predicates in preflight because SQL optimization can omit their intermediate
overflow checks. A single direct arithmetic projection retains native support;
its only supported suffix is Sort. Existing admitted source data is never cast
lossily to avoid a rejection.

The corrected pandas and DuckDB compiler implementation versions end in
`/arithmetic-checks-v1`, and new transformation identities incorporate that
revision. Polars identities and all historical formats/readers stay unchanged.
Retain old evidence as historical observations; rerun affected plans with the
corrected compiler before using their results for acceptance.

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

For ordinary private-candidate feedback, contact the artifact provider or owner
through the existing authorized project channel. If you have repository access,
a reviewable issue/PR can carry nonsensitive technical details. No public support
portal, dedicated security mailbox, named security duty roster, guaranteed
response time or SLA is established by this handbook. See [security](security.md)
for unresolved contact and incident gates before broad distribution.

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
[release procedure](releasing.md). Public release remains pending STEP10, global
review, license/name decisions and explicit approval.

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
