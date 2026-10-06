# Candidate, release, withdrawal and rollback

## Current state

`equiframe` and `equiframe-benchmark` are private Alpha candidates, currently
numbered `0.12.0a3` and distinguished by commit plus SHA-256. They are **not** a
public PyPI release. No project distribution license has been selected or
authorized. Technical installation tests do not grant redistribution permission.
Do not run an unqualified `pip install equiframe` to obtain this candidate: a
public name can resolve unrelated bytes. Use the identified wheel supplied
through the authorized private channel and verify its hash.

Public distribution requires the owner to decide the channel and licensing,
assign release and vulnerability-response responsibility, complete STEP10 and
the requested global review, resolve the security review, and expressly approve
the exact release. Names/account ownership, documentation access, publisher
configuration and protections must be checked then. No availability lookup
reserves a package name. No owner has committed to a response SLA.

The 0.12.0a3 task explicitly authorizes isolated installation and the private
wheelhouse channel. Missing license/account decisions block external publication,
not these local checks. [Private install commands](installed-private.md).

## Repeatable candidate checks

From each package, use the exact `uv.lock` and Python interpreter for the chosen
profile. The core driver supports the benchmark with `--package`:

```sh
python packages/equiframe/tools/check_candidate.py \
  --package packages/equiframe --output /absolute/evidence/core-checks.json
python packages/equiframe/tools/check_candidate.py \
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

After freezing a clean commit, run `tools/release_manifest.py` with the exact
receipts for both packages. Inspect the independent compatibility matrix, the
installed consumer report, dependency inventory, licenses and dated advisories,
source review coverage and all unresolved decisions. Build tools and versions
must be identical for a byte-for-byte reproduction claim.

A candidate directory containing both manifests and their adjacent wheel/sdist
files can be checked with:

```sh
python packages/equiframe/tools/verify_publication.py \
  --candidate-root /absolute/candidate --commit EXACT_40_CHARACTER_SHA \
  --output /absolute/evidence/publication-readiness.json
```

Malformed, stale, incomplete, linked or substituted artifacts are rejected.
Valid candidate bytes produce a decision packet and exit **3**, because this
STEP9 policy remains closed. There is no `--force`, token or approval switch.
The packet is not proof of human approval and cannot enable a release.

## CI permissions and provenance

The checked-in workflows are manual and disabled by their default inputs.
A push or PR does not itself run the matrix. Candidate building has `contents:
read`, pinned official actions, no persisted checkout credentials and no upload
credential or OIDC permission. Workflow files are a recipe; only a recorded run
on the exact commit is remote-CI evidence. Dependency advisories are separate
networked checks and must preserve unknown/unavailable results.

The publication example is outside `.github/workflows`, performs only readiness
inspection, and has no publishing action or `id-token: write`. Before a future
release, review a separate protected workflow that verifies the build run's
repository, workflow path, event, successful conclusion and exact head SHA,
uses only already-verified bytes, and obtains the minimum required permissions
only in the publishing job. Do not create publisher access in this candidate.
A future PyPI attestation may bind an artifact to its publishing workflow; it
cannot certify semantic correctness, dataset truth or the adequacy of testing.

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
