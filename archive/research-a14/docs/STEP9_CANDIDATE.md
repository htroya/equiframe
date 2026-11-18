# STEP9 distribution and release readiness

This engineering stage prepares an identified private Alpha candidate. Public
release remains blocked: the owner has not approved a distribution license or
channel, the source-security assessment is incomplete, and STEP10 plus the
requested global review and exact release approval remain outstanding. Building
and installing a wheel is not the roadmap's published-artifact acceptance gate.

## What changed

- English root/package entrypoints and a standalone 12-chapter handbook covering
  quick start, three installed recipes, API, semantics, guarantees, limits,
  compatibility, performance, upgrades, contribution, dependency evidence,
  security and release/rollback. The wheel carries the handbook as package
  resources; the sdist and first-use kit include the relevant English guides
- Exact source-to-wheel/sdist handbook binding in both kit and compatibility
  verifiers. Changed, missing and extra documentation bytes fail those checks
- Both distributions rebuild the wheel **and** sdist and require byte equality
  in their outside-checkout distribution gate. Separate extras stay separate;
  neither project has gained a runtime dependency for SBOM/advisory work
- A developer-only offline inventory tool binds CycloneDX 1.6 SBOMs to each exact
  artifact, records lock/environment/profile membership and license observations,
  and validates against pinned official schemas. The schemas' upstream license
  is preserved and does not assign a license to EquiFrame
- A separate explicitly networked PyPI/OSV snapshot captures exact provider
  responses and failures; a verifier checks bindings, completeness and freshness
- A tested publication readiness tool checks two manifests, four artifacts and
  the benchmark's exact core-wheel dependency, then returns exit 3 under the
  deliberately closed release policy. It has no override/upload switch
- Candidate CI remains manual, read-only and disabled by default; optional
  advisory queries are explicit. The dormant publication example has no upload
  action, stored publishing credential or OIDC permission

No runtime comparison algorithm, public API signature, versioned schema or
scientific protocol was changed. The quarantined historical benchmark helper
remains unsupported. Protected thesis traceability and existing reader fixtures
remain unchanged. Historical source receipts stay historical.

## Frozen artifact identity

The private version string remains 0.11.1; commit plus hashes identify this
candidate. These exact bytes were frozen for STEP9 verification:

| Artifact | Size bytes | SHA-256 |
|---|---:|---|
| `equiframe-0.11.1-py3-none-any.whl` | 296239 | `3f6531a73c7fdfad515952d269664ab575a981c33c0e684293a97246ef328273` |
| `equiframe-0.11.1.tar.gz` | 852235 | `6a9e295e0f28345aa4805ce5bb74af181c2f071e7ee04967b8e2f0abfd566677` |
| `equiframe_benchmark-0.11.1-py3-none-any.whl` | 124319 | `24c5203c6a47ed7e0856e5c9283ad67004f8310c09fad593716b83a2a60cd8ec` |
| `equiframe_benchmark-0.11.1.tar.gz` | 366989 | `b698de3d941cec3280a6e7002a5dae66e2fb3efc1f080d7c0eb33f11db7bb047` |

Source snapshots cover 377 core files and 492 files in the benchmark's local
source closure. The artifact-source check also binds Hatch's inherited root
`.gitignore`; generated PKG-INFO is separately checked as metadata. These are
unsigned consistency records, not producer authentication or signatures.

## Verification status

All **18 final v2 release gates passed**, nine per package, with source and
artifact binding. Core source and installed suites each passed **2,659** tests;
benchmark source and installed suites each passed **524**. Both reconstructed
wheel/sdist pairs were byte-identical.

The independent fresh installed consumer passed 113 checks and 25 commands,
plus 124 result-state/witness/count/inventory checks. It checked every installed
package byte, all 12 handbook files, README/handbook snippets and recipe exit
matrices. Independent SBOM review passed 70 checks. A separate base-only rollback
consumer passed 32 checks using the exact STEP8 wheel and 13 pins from its own
lock, reading STEP9 different/complete and not_evaluable/partial report views
without changing their bytes or meaning. These are technical checks, not human
first-use observation, adoption or security completion.

The fresh matrix passed **12/12 cells** on Linux x86_64, CPython 3.12.14 and
3.13.5: Arrow/all core profiles at minimum-direct/latest-permitted endpoints,
plus four exact-core-bound benchmark consumers. Its full suites executed
12,732 pytest cases across repeated environments, with zero failures, errors,
skips or xfails. All STEP8 testcase IDs remain in each corresponding full
suite. These repeated executions are not independent scientific samples or
additional platform coverage. Receipt/log/lock, tool, source and artifact hashes
were checked after completion. No Windows/macOS/ARM64 claim is added.

## Dependency and licensing scope

The final local Linux/Python 3.12 inventories contain 71 core and 67 benchmark
Python distributions across separately identified base/extras/all/dev/build
profiles. They are not claims that a base installation needs all those packages.
All inventoried metadata was available. Declared SPDX expressions are parseable
for 54 core and 49 benchmark components; 17 and 18 observations respectively
remain for manual license review, including the unlicensed local projects.
A missing/ambiguous expression does not by itself establish an absent license;
license files, classifiers and free-form fields remain visible.

Fresh locked-environment advisory queries completed at 07:40 UTC on 2026-10-06:
140 core and 130 benchmark PyPI/OSV queries, no unknown responses and no listed
advisories for those exact versions. Both full artifact/inventory/BOM/advisory
verifications passed with a 24-hour freshness requirement. Exact UTF-8 response
bytes, hashes, requests and timestamps are retained. GHSA content is supplied
through PyPI/OSV; no separate direct GHSA query is claimed. The compatibility
resolution endpoints have their own dependency coverage, recorded separately.

The Python inventory does not enumerate every bundled native library, operating
system package or build-service component. Lock hashes identify resolver inputs,
not the origin of an already installed file. Current advisory responses cannot
prove absence of unknown vulnerabilities or complete the source-security review.

## Minimum-profile advisory match and applicability

The separate final-matrix scan covered **85 exact name/version pairs** with
**170/170 complete PyPI/OSV queries** and no unknown responses. It returned a
package-version match for `pyarrow==20.0.0` in six minimum cells. Scan/required-clean
exit **2** is retained; this result is not labeled clean or suppressed.

The two identifiers GHSA-rgxp-2hwp-jwgg and PYSEC-2026-113 refer to one issue,
**CVE-2026-25087**, High/CVSS 7.0. The advisory affects Arrow C++ versions
`>=15.0.0,<23.0.1`, fixed in `23.0.1`, and explicitly states that the triggering
functionality is not exposed through Python bindings, which are not vulnerable.
This metadata match therefore does not establish an exploitable EquiFrame path.
The tested dependency floor remains unchanged; no untested new minimum is claimed.
Release triage remains pending, and the public gate stays closed. This is an
upstream applicability statement, not a completed source-security review.
[Reviewed advisory](https://github.com/advisories/GHSA-rgxp-2hwp-jwgg) ·
[OSV record and aliases](https://osv.dev/vulnerability/PYSEC-2026-113).

## Security and remaining release decisions

The source assessment was not completed and was not retried through another
route. No official finished scan, final finding disposition or verified source
hardening is claimed. Already observed special-file availability behavior is
retained as a caution; a capture-budget observation still needs contract triage.
Use immutable regular inputs in controlled directories and isolate untrusted
workloads. The [working threat model](../packages/equiframe/docs/security.md)
separates filesystem, report, SQL/callback/plugin, resource and disclosure risks;
owner review is pending. Local-default configuration is not network isolation.

The owner must approve the license and distribution channel, assign release and
vulnerability-response responsibility and a verified reporting channel, and
complete the outstanding reviews before approving public release. No maintainer,
SLA, legal clearance, public package ownership or credential has been invented.
Official PyPI project JSON lookups returned HTTP 404 for both candidate names
at 08:05 UTC on 2026-10-06. This observation neither reserves a name nor proves
ownership or approval. No PyPI/TestPyPI upload, public visibility change, PR or main merge is part of
this STEP9 candidate. Remote workflows are not represented as executed unless a
run exists for the exact commit.

See the [English handbook](../packages/equiframe/docs/index.md),
[release controls](../packages/equiframe/docs/releasing.md),
[dependency commands](../packages/equiframe/docs/dependencies.md) and
[private reporting status](../SECURITY.md).
