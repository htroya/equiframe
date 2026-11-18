# STEP10 adoption and maintenance candidate

This stage implements technical support for genuine adoption and sustainable
maintenance. It does not establish adoption: **zero real pilot projects**,
participant consent, independent human first use, later real-project retention
and consumer-confirmed fixes have been observed. The human five-minute target
remains pending. Nominal maintainers/backups and response commitments have not
been assigned. Public release remains closed and main integration is held for
the separately requested global review.

## Delivered technical scope

- A developer-only, bounded local JSON record checker with a deliberately empty
  real registry. It separates synthetic replays from human attestations, preserves
  failed attempts and unknown effort, records supplied artifact/lock/contract
  identities, and checks outcome/retention consistency without reading those
  referenced bytes
- One chronological history per project/context prevents an older success from
  hiding a later failure. Retention starts from a useful completed comparison,
  so preserving failed installation attempts does not penalize later valid use
- Critical issue history blocks retained-use counts until the affected consumer's
  confirmation is explicitly recorded. Omitting an issue or downgrading its
  priority cannot clear the record. Valid data still does not authenticate
  consent, people, independence, semantic truth or the referenced evidence
- A standalone synthetic replay covers Python refactor, SQL/DuckDB and local
  CI-style assertions over initial and changed inputs. All three keep the exact
  contract and independently literal expected outputs. Equivalent, different,
  invalid expected and budget-limited cases produce 24 checked observations
- Two English handbook chapters and minimal issue templates define consent,
  permitted reproduction, six friction categories, proposed support priorities,
  critical false-equivalence containment/correction/notification/reconfirmation,
  and admission conditions for new engines
- The wheel carries 14 handbook chapters. The sdist additionally carries the
  checker, empty registry, replay and tests. The first-use v1 kit's closed
  inventory is unchanged; no parallel telemetry or new runtime command is added

Current usage: [adoption](../packages/equiframe/docs/adoption.md) and
[maintenance](../packages/equiframe/docs/maintenance.md).

## Verification

All **18 final byte-bound gates passed**, nine per package. Core source and
installed suites each passed **2,745** tests; benchmark source and installed
suites each passed **524**. Wheel and sdist rebuilt byte-identically for both
packages. The clean independent installed consumer passed **286** checks and
**472** additional new/historical tests, including all 24 replay observations.

The fresh matrix passed **12/12 cells** on Linux x86_64, CPython 3.12.14 and
3.13.5: Arrow/all profiles at minimum/recent-permitted endpoints plus four exact
core-bound benchmark consumers. It executed 13,076 suite cases and checked 296
commands, with zero failures, errors, skips or xfails. Every corresponding STEP9
case ID remains covered; 12 cells and 16 runtime/test locks have identical exact
dependency version maps to STEP9. Repeated test executions are not independent
scientific samples, human adoption or support for unexecuted platforms. No remote
CI run is claimed. All checks bind the final frozen source and artifact bytes.

| Artifact | SHA-256 |
|---|---|
| Core wheel | `d0fed9d1d5a0fefbe62dd067a3ea3908196271783b8b1ad6570d4c6cca9c30f8` |
| Core sdist | `d6fc8659981aba03f6dc5fd36b8a3544978240beb9648de9b4fe25744abb1995` |
| Benchmark wheel | `24c5203c6a47ed7e0856e5c9283ad67004f8310c09fad593716b83a2a60cd8ec` |
| Benchmark sdist | `b698de3d941cec3280a6e7002a5dae66e2fb3efc1f080d7c0eb33f11db7bb047` |

The final delivery carries complete hashes, receipts, logs, locked inventories,
ordinary independent review and known limits. Hashes establish consistency, not
human identity, consent, source-security completeness or universal correctness.

The new focused corpus has 70 record-consistency tests and 16 replay
tests. Four draft record-workflow findings were corrected before the freeze;
they concern adoption bookkeeping, not discovered false equivalence in the
comparison engine. Failed development attempts remain in the delivered evidence.

## Boundaries preserved

No core/benchmark runtime API, semantic comparison algorithm, scientific protocol,
versioned schema, dependency range/lock, infrastructure or DW component changes.
The protected thesis traceability, historical fixtures and existing stability
contracts remain unchanged. The version string remains private 0.11.1; hashes
and commit identify this candidate, not that string alone.

Exact-byte SBOM/inventory generation is offline. External locked components
remain unchanged from STEP9; this is not a fresh advisory or source-security
assessment. Source-security assessment remains incomplete and was not resumed
or bypassed. The retained minimum-profile Arrow match CVE-2026-25087 and
upstream's explicit Python-binding exclusion remain visible; release triage is
pending, without an exploitable-path or clean-scan claim.

## Outstanding adoption and production decisions

The proposed real-adoption gate needs at least three independent consented real
projects spanning refactor Python, SQL/DuckDB and CI, completed useful cases,
a later real change with retained integration, and demonstrated reporting and
upgrade knowledge. Correct abstention is useful safe behavior but cannot alone
establish a completed integration. Downloads, stars, fixtures and automated
repetitions do not satisfy this gate.

The owner must approve and staff core, adapter, documentation, release and
security responsibilities with backups, verified channels, priorities, capacity
and response goals before production commitments. New engines require repeated
real demand, a willing owner, independent corpus, maintenance budget and support
decision. No recruitment, external contact, real-data upload, nominal assignment
or SLA was performed by this step.

Public distribution additionally retains license, channel, name/ownership,
publisher and exact-release approval decisions, incomplete security/advisory
triage, and the requested global review. A private installable candidate is not a
publicly published package. The reinforced roadmap remains outside Git.
