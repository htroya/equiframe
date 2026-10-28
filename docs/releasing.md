# Candidate, release, withdrawal and rollback

## Current state

The release target is `equiframe 0.12.2` with the exactly paired
`equiframe-benchmark 0.12.2`, identified by commit and artifact SHA-256.
On 2026-10-27 the owner authorized manual publication to TestPyPI followed by
PyPI after the release checks pass. Publication is established by the observed
index inventories and clean downloaded consumers, not by this guide or a build.

Hernán Troya (`htroya`) accepted maintenance, release and security responsibility.
No response-time SLA or staffed on-call coverage is promised. Accounts, 2FA,
name control, public documentation and private security intake must be verified
for the selected target. A name lookup does not reserve a package name.

Original project code and accompanying materials use MIT. Each distribution
carries LICENSE and THIRD_PARTY_NOTICES.md. Vendored CycloneDX schemas retain
Apache-2.0; the core artifact metadata records the combined licensing terms.
See [license scope](licensing.md) and [offline wheel installation](installed-private.md).

The version-2 release policy separates the nine technical checks from factual
publication gates: security/dependency review, rights, public documentation,
account protection, independent artifact review and the owner's current task.
UNKNOWN, missing or failed gates block publication. A temporary packet binds
observations to the exact commit, four artifacts, destination and date; it does
not authenticate a human or grant permission by itself. The inspector never
uploads files or handles credentials. Publication remains a separate manual act.

TestPyPI is a public index with separate accounts. Upload only the four approved
files, download them again, verify every SHA-256 and exercise a clean consumer.
Promote those same four bytes to PyPI only after this succeeds. Rebuilding or
changing a file requires new checks. TestPyPI can use an ephemeral local API token
supplied through a hidden terminal prompt and revoked after upload. Never store
that token in a repository, a report or GitHub secrets.

On 2026-10-28 the owner explicitly selected local manual publication and
instructed this release not to use GitHub Actions. A newly prepared OIDC
workflow was withdrawn before use. GitHub jobs are not a prerequisite for this
manual release route; no environment or publisher configuration is implied.

For each index, use its official endpoint and a uniquely named temporary token
created under the authenticated maintainer account. Pass it through a native
hidden terminal prompt, upload only the four identified files, then revoke it.
Keep the exact artifact hashes, account protection and downloaded-consumer
checks; changing the authentication route does not waive them. Neither account
passwords nor API tokens belong in source, reports, GitHub secrets or shell
history.

## Tagged versions

Hatch and `hatch-vcs` derive both distributions from the same reviewed Git tag
`vMAJOR.MINOR.PATCH`. Runtime versions come from installed distribution metadata.
There is no second manually maintained runtime version and no silent fallback
release number. A source archive retains its package metadata so rebuilding the
sdist does not require Git history. Release checks reject an absent/mismatched
tag, dirty or noncanonical source, and SCM version overrides.

Create the tag only after the complete source revision is reviewed and committed.
Use a new patch version for documentation or compatible fixes; use a minor
version for compatible new functionality and explicitly document breaking
changes. During the `0.x` series, read the compatibility and upgrade guides.
Never move an existing release tag or replace published TestPyPI/PyPI files.

Historical Alpha candidates keep their original results and closed version-1
policy. STEP10's real-data evaluation, external scientific acceptance and DW
integration remain separate research/integration deliverables; they are not
claimed complete by a library release.

## Repeatable candidate checks

From the repository root, select the supported Python interpreter for the chosen
profile. The driver uses each package's exact `uv.lock` and supports the benchmark
with `--package`:

```sh
python tools/check_candidate.py \
  --package . --output /absolute/evidence/core-checks.json
python tools/check_candidate.py \
  --package packages/equiframe-benchmark --output /absolute/evidence/benchmark-checks.json
```

Each driver checks locked sync, Ruff check/format, mypy, generated assets, the
full pytest suite, build, strict Twine validation and installed distribution
consumption. The final distribution stage uses clean environments outside the
checkout, exercises optional profiles/recipes, runs shipped tests against
site-packages and compares both rebuilt wheel and sdist bytes. A passing wheel
rebuild alone is not a claim about every compiler, platform or dependency build.
Source snapshots, exact artifact hashes and loaded local dependency bytes bind
the receipts; they do not authenticate the executor. Keep receipts outside the
source tree so writing them does not change the source being checked.

Candidate checks and manifest generation also require every package and local
dependency file to match its raw Git HEAD blob. A clean `git status` is not
enough: automatic line-ending or other Git filter conversions can change the
bytes that a build packages. On Windows, use a fresh checkout with both
`core.autocrlf=false` and `core.eol=lf`, for example:

```text
git clone --config core.autocrlf=false --config core.eol=lf <repository> <fresh-directory>
```

Changing these settings in an existing checkout does not rewrite already converted
files. Rebuild from the canonical checkout; do not normalize an artifact to make
the verification pass.

After freezing a clean commit, run `tools/release_manifest.py` with the exact
receipts for both packages. Inspect the independent compatibility matrix, the
installed consumer report, dependency inventory, licenses and dated advisories,
source review coverage and all unresolved decisions. Build tools and versions
must be identical for a byte-for-byte reproduction claim.

A candidate directory containing both manifests and their adjacent wheel/sdist
files can be checked with:

```sh
python tools/verify_publication.py \
  --candidate-root /absolute/candidate --commit EXACT_40_CHARACTER_SHA \
  --target testpypi --gate-packet /absolute/temporary/testpypi-gates.json \
  --output /absolute/evidence/publication-readiness.json
```

Malformed, stale, incomplete, linked or substituted artifacts are rejected.
For the current version-2 policy, exit **0** means that the technical receipts
and all factual gates for the selected index passed; missing, UNKNOWN or failed
gates block readiness with a nonzero exit. Use `--target pypi` and a separate
packet after verifying the TestPyPI downloads and consumer installation.
Historical version-1 candidates retain their closed policy and exit **3**.
There is no `--force` or credential switch. The packet does not authenticate
human approval, and this command never uploads or grants account access.

## Local checks and provenance

The public repository ships no GitHub Actions workflows. Run the local candidate
commands above and retain their exact source identities, environment details,
exit codes and artifact hashes. A local receipt establishes only the work it
records; it does not establish that a remote CI job ran. Dependency advisories
are separate networked checks and retain unknown or unavailable outcomes.

Publication is manual with a local ephemeral credential. A future adoption of
Trusted Publishing requires a separately reviewed protected workflow and real
publisher configuration; OIDC is not configured or used for this release.

## Correcting a defect

1. Record exact affected commits, wheel hashes, APIs/adapters, policies and
   environments. Preserve a sanitized reproducer and independent expected result
2. Assess exposure and whether the claim of equivalence, privacy or evidence
   integrity is affected. Stop recommending the affected route if the judgment
   can be wrong; fail closed rather than silently weakening the contract
3. Assign an owner before promising a date. Implement a regression test and
   narrow correction. Re-run the relevant historic corpus, full gates, installed
   recipes and affected compatibility cells on new immutable artifacts
4. Refresh SBOM/advisory/license evidence and publish release notes describing
   behavior changes, affected versions, migration and remaining limitations
5. Obtain the required release approval and distribute a new version. Public
   artifacts are immutable: do not overwrite a released version with new bytes

## Withdrawal and rollback

For a private candidate, stop distributing the affected hash and notify only
its authorized recipients through verified channels. Keep the incident record
and superseded evidence so results can be traced. For a future public release,
the assigned owner must approve the appropriate advisory and index action;
yanking is a selection signal, not deletion of all installed copies or pinned
references. Deletion is a separate, potentially irreversible action.

Test rollback in a **new environment** using the previous known-good exact
artifacts and their matching pinned dependencies. Verify hashes, imports,
`pip check`, recipes and historic evidence readers before replacing a consumer
service. Rollback must not rewrite user evidence or downgrade a versioned file
format silently. If a new format is unreadable by the old version, retain the
new reader in an isolated environment or use an explicitly reviewed migration.
Never infer compatibility from equal version numbers on private candidates.
Re-running old tests with a new hash is a new receipt, not a historic result.

Official background: [Python packaging](https://packaging.python.org/en/latest/tutorials/packaging-projects/),
[PyPI attestations](https://docs.pypi.org/attestations/),
[PyPI yanking](https://docs.pypi.org/project-management/yanking/)
