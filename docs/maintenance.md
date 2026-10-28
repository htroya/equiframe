# Maintenance, support and trust incidents

[Handbook](index.md) · [Adoption](adoption.md) · [Compatibility](compatibility.md) ·
[Upgrading](upgrading.md) · [Security](security.md) · [Release/rollback](releasing.md)

## Maintainer and best-effort support

For the 0.12.2 release, the project owner has assigned **Hernán Troya (`htroya`)**
responsibility for maintenance, releases and security coordination. This is
best-effort maintenance by one owner, not a staffed service or support contract.
No backup, on-call coverage, numeric response deadline or SLA is promised.

| Role | Scope | Named owner | Backup |
|---|---|---|---|
| Core | Comparison/contracts, typed states, assertions, evidence integrity and historical readers | Hernán Troya (`htroya`) | Not designated |
| Adapters | Native capture/execution, capabilities, dependencies and measured matrix cells | Hernán Troya (`htroya`) | Not designated |
| Documentation | Installation, diagnosis, migration guidance and reproducible examples | Hernán Troya (`htroya`) | Not designated |
| Releases | Exact-byte checks, manual publication/withdrawal and recovery | Hernán Troya (`htroya`) | Not designated |
| Security | Private intake, exposure review and vulnerability coordination | Hernán Troya (`htroya`) | Not designated |

The core remains independent of a service, domain schema and infrastructure.
Service/DW ownership, concurrency, authorization and aggregate quotas stay with
those components' owners; an adapter issue does not authorize redesigning them.
Keep experimental benchmark/scientific acceptance distinct from operational
comparison maintenance.

## Report a problem

Use [the public issue channel](https://github.com/htroya/equiframe/issues)
for nonsensitive bugs and minimal synthetic reproductions. Use
[private vulnerability reporting](https://github.com/htroya/equiframe/security/advisories/new)
for sensitive security reports. The public repository, issue intake and private
vulnerability reporting were enabled and verified on 27 October 2026. If a route
becomes unavailable, contact the owner through the established private project
channel to arrange safe intake; do not move sensitive details to a public issue.

Do not put credentials, real data, personal information or sensitive exploit
details in a public issue, an ordinary issue with a broader audience, or a
guessed email address. A repository issue is not automatically a private
security channel. If a safe route cannot be verified, retain sensitive details
locally and stop using the affected acceptance path.

Provide only the minimal permitted reproduction:

1. Classify installation, comprehension, semantics, integration, performance
   and/or evidence; state impact and whether false `equivalent` is suspected
2. Identify exact package/commit, wheel/sdist and dependency-lock hashes, Python,
   OS/architecture, engine versions and selected extras. Redact account/path data
3. Give a small synthetic fixture and trusted code/SQL that someone can inspect
   before executing. Include the contract, relevant policy, budgets and explicit
   reproduction commands; do not upload a complete private run or environment
4. State independently expected versus observed state, completeness, acceptance
   and exit code. Explain the expected-output provenance. Separate engine
   agreement from correctness and report integrity from semantic acceptance
5. Attach only a reviewed minimized report when permitted, with its inventory
   verification outcome and hash. Mark missing/partial evidence explicitly
6. Identify the last known-good **artifact**, if known, repeatability and any safe
   workaround. Preserve earlier failures; do not silently replace the baseline

The [adoption guide](adoption.md) describes consent and minimal observation.
Permission to participate does not authorize sharing the person's data or posting
to an issue. Do not request additional private data until its necessity, recipient
and handling have been agreed. Raw exception causes can reveal more than the
ordinary report; inspect diagnostics before sending them.

## Triage priorities without response deadlines

The maintainer uses the following best-effort triage order. It does not establish
staffed coverage, response deadlines or a service guarantee.

| Priority | Examples | Triage goal |
|---|---|---|
| P0: critical trust incident | Suspected false `equivalent`, acceptance of incomplete/invalid evidence, or material disclosure/integrity risk | Stop relying on the affected claim, preserve evidence and seek owner-led containment/escalation before restoring acceptance |
| P1: blocking defect | Reproducible installation/integration failure, documented supported case incorrectly rejected, or an unusable evidence reader | Establish scope and a safe workaround, then reproduce and verify a focused correction |
| P2: nonblocking friction | Comprehension gaps, minor diagnosis problems, performance outside an unpromised target | Preserve observations, assess impact and prioritize repeated real pain without weakening semantics |
| P3: capability proposal | New engine, integration or unsupported representation | Require repeated real need, ownership, corpus, budget and an explicit support decision before implementation commitment |

Category and severity are separate. A semantics report is not automatically a
confirmed defect; an evidence issue may be critical. Safe `not_evaluable` is
not false equivalence. If the owner is unavailable, leave the issue pending;
there is no designated backup or automatic escalation promise. Do not promise a
reply or reopen a potentially unsafe path merely because time has passed.

## Reproduce, correct and reconfirm

Use a local incident/issue record with source evidence, scope, category, proposed
priority, triage decision, assigned owner when accepted, correction and validation
references. Keep review, release approval and consumer confirmation separately
pending. A suggested workflow is: reported, scoped, reproduced or needs evidence,
correction under review, technically verified, awaiting consumer reconfirmation,
then resolved. Unsupported, duplicate or withdrawn reports need an explicit
rationale; do not erase the original observation.

For a reproducible defect:

1. Preserve the failing artifact, permitted evidence and independent expectation.
   Reduce a copy to a minimal synthetic case while retaining the same failure
2. Add a regression that fails against the affected version for the stated reason.
   Include relevant equivalent, different, invalid and incomplete cases; tests
   derived only from the implementation can confirm the same error
3. Make a narrow correction with review of API/format/adapter/contract impacts.
   Do not rename a stable surface experimental to evade compatibility duties
4. Run affected semantic and historical-reader tests, full candidate checks,
   outside-checkout installed recipes and affected compatibility matrix cells
   against new immutable bytes. Record failed, blocked and unexecuted checks
5. Document scope, behavior changes, migration, exact hashes and residual limits.
   Follow [release approval](releasing.md); technical verification does not
   authorize distribution, a public issue, dependency access or a remote CI run
6. Through the authorized channel, ask the affected consumer to test the original
   use case and the relevant later real change with the identified correction.
   Record whether the integration is retained and reporting/updating is understood
7. Mark consumer reconfirmation only after their actual response and evidence.
   If they cannot repeat it, keep that gap open rather than treating internal tests
   as their approval. Reopen the issue if their case still fails

Track actual triage/reproduction/review/documentation effort and unresolved work.
Sustainable support needs observed capacity and accepted owners, not estimates
presented as delivered service.

## False `equivalent`: critical trust incident procedure

A plausible false-equivalence report triggers precautionary containment while
validation proceeds. This means the evaluated contract admitted a difference or
invalid/incomplete evaluation as acceptance; a deliberate permissive contract or
two engines sharing the same bug needs separate diagnosis. Do not dismiss the
report merely because existing tests pass or a manifest has valid hashes.

1. **Contain.** Stop using the suspect result/path as an acceptance gate. Preserve
   original artifacts and private evidence; suspend distribution/recommendation
   of affected candidate hashes within the authorized scope. Do not silently
   weaken a contract, remove the check or convert `not_evaluable` to success
2. **Escalate safely.** Seek an accepted incident owner and relevant core/adapter,
   release and security reviewers through verified routes. Keep sensitive details
   restricted. No staffed response or automatic external notification is implied
3. **Bound impact.** Identify affected package commits and wheel hashes, exact
   dependency versions, APIs, adapter stages, data types, contract revisions and
   policies, output/evidence formats and environments. Distinguish confirmed,
   possibly affected and untested scopes; inventory downstream decisions that
   relied on the suspect result without uploading their raw data
4. **Reproduce independently.** Build the smallest permitted case with an expected
   result reviewed independently of the failing path. Compare the identified
   previous and current artifacts; keep counterexamples and original decisions
5. **Correct and verify.** Add the failing regression, repair the narrow cause and
   exercise adjacent policies, all affected native adapters, interruption/limits,
   invalid expected inputs and persisted readers. Re-run full affected source,
   distribution and compatibility gates. A fail-closed fix may reject formerly
   accepted input immediately; explain that boundary explicitly
6. **Prepare safe recovery.** Supply a new approved artifact with exact pins,
   change notes and validation evidence. Test upgrade in an isolated environment
   and re-evaluate affected consumer cases. Roll back only to a demonstrated
   known-safe artifact/environment; if none exists, suspend acceptance. Never
   rewrite historic evidence or downgrade format markers to force readability
7. **Notify with approval.** The owner approves the recipient scope, channel and
   consequential content before an affected-user notice is sent. Explain affected
   and uncertain versions/contracts/adapters, impact, containment, safe upgrade
   or rollback and cases requiring re-evaluation. Reach only authorized recipients
   through verified channels and share no other consumer's private data. Record
   actual dispatch/acknowledgment separately from a prepared draft
8. **Reconfirm and close.** Obtain affected-consumer confirmation on their original
   and later-change cases, record any downstream corrective decision, and document
   residual exposure. Keep unreached consumers and unverified environments open.
   Owner review closes containment only with evidence; a green internal suite
   alone does not close the trust incident

For a future public release, advisory and index actions require the owner's
separate approval. A yank does not remove installed or exactly pinned copies.
Published artifacts must not be overwritten. Before a first registry publication
there is no public release to withdraw; afterwards use the same identified-byte
withdrawal/recovery process in [releasing](releasing.md).

## Upgrade, dependency and support decisions

Preserve package version, contract revision and evidence format as separate
identities. Follow the [compatibility policy](compatibility.md), including its
deprecation window and fail-closed exception, and [upgrade checks](upgrading.md).
New evidence must not change the meaning of historical records. Unknown formats
remain rejected; migration needs explicit review and new traceable artifacts.

Support claims must cite exact measured cells. The current maturity plan requires
Python 3.10/3.11/3.12/3.13 with per-interpreter first-use closures and explicit
platform receipts. Do not expand support from metadata, configured but unexecuted CI, or past results
for different candidate hashes. Dependency changes require fresh affected-cell
validation and updated artifact-bound inventories; timestamps and old advisory
receipts cannot certify changed dependencies.

The retained STEP9 minimum-profile advisory match for **CVE-2026-25087** remains
visible. The recorded advisory states the affected Arrow C++ functionality is
not exposed through Python bindings, which are excluded from vulnerability;
this does not turn the retained package-version match into a clean scan, prove
all native dependencies safe or complete the source-security assessment.
That historical result does not substitute for triage of the dependencies in a
new release. See [dependency evidence](dependencies.md) and current release gates.

The earlier stopped source-security assessment remains historical and is not
relabeled as a pass. The owner has now authorized stable-release preparation and
manual TestPyPI/PyPI publication subject to current security and release gates.
MIT licensing, the maintainer role and reporting-channel activation are decided
and verified. Registry ownership, final artifact checks and publication remain
separate observable steps. Do not claim that authorization fixes a vulnerability or completes
a security assessment. Scientific acceptance and human adoption are independent
of interface stability and registry publication.

## Admitting a new engine or integration

Do not expand the adapter catalog because a feature is popular or a synthetic
demo passed. Before accepting an implementation commitment, require:

- Repeated, documented blockers in independent real uses and why existing
  supported routes cannot meet the need without semantic loss
- A named willing maintainer with boundaries agreed by component owners; any
  backup or staffed coverage must be explicit rather than assumed
- A permitted representative corpus with independent expectations, positive,
  negative, unsupported, invalid and incomplete cases, including key/multiplicity,
  NULL/NaN, Decimal and time boundaries relevant to the integration
- An explicit resource and maintenance budget covering native dependencies,
  CI/platform cells, performance, evidence readers, security and upgrade costs
- An owner-approved support decision: supported subset, version/platform matrix,
  stability, failure/abstention rules, migration/deprecation and exit criteria

Record the decision and its evidence before adding an engine. Preserve genuine
native execution and explicit registration; do not simulate a new engine by
converting another engine's already-computed output. Missing demand, ownership,
corpus, budget or support approval leaves the proposal pending.

## Python 3.10 runtime policy

The supported compatibility range includes Python 3.10 through 3.13, with the
measured scope in [compatibility](compatibility.md). Application deployment
owners remain responsible for the interpreter's lifecycle, dependency risks and
their upgrade path. Passing package tests does not provide upstream/vendor
security maintenance, a backup maintainer or a response deadline.
