# Contributing to EquiFrame

[Handbook](index.md) · [Compatibility](compatibility.md) · [Release process](releasing.md)

The 0.12.2 release contract uses MIT for project-owned code; third-party materials
retain their notices and licenses. Redistribution rights follow those licenses.
Hernán Troya (`htroya`) maintains the project and owns releases/security
coordination on a best-effort basis without a promised backup or response-time SLA.

The public repository contains the library source, user documentation and tests.
Open a nonsensitive issue or contribute a focused patch using your own account.
Never include credentials, private datasets, models or execution results.
The benchmark remains a separate package in this repository.

The owner has authorized manual TestPyPI/PyPI preparation and publication subject
to the [release gates](releasing.md). This is not permission for a contributor or
an ordinary CI run to publish. Historical private candidate notes retain their
original versions and outcomes.

## Boundaries to preserve

- Read the API, compatibility and semantic-contract guides before a change
- Preserve Decimal, currency, keys, multiplicity, NULL/NaN and temporal distinctions
  according to contract; never normalize differences just to pass a test
- Keep R, M, B, H and O independent. Detectors/profiles must not receive labels,
  mutation definitions or another engine's output. pandas is not an oracle
- Never map failure, invalid input, missing support or not-estimable output to
  success or no alert. Test fail-closed behavior, not just the happy path
- Native engines execute their own implementations; do not compute once and
  convert the result to simulate independent implementations
- Core code must not depend on OCI, SERCOP, the experimental package or a specific
  external service. Use explicit typed ports and trusted registrations
- Honor component ownership: core/benchmark work does not authorize infrastructure,
  data-gateway or domain-warehouse redesign
- Do not execute untrusted callbacks, SQL, plugins or models. The library is not a
  sandbox. Do not introduce shared DuckDB files with independent process writers
- Keep credentials, real datasets, private reports, databases, model binaries and
  environments out of Git. Small identified synthetic fixtures are appropriate

## Reproducible local checks

The commands below describe checks to run; they do not assert this artifact has
already passed them. Use an authorized source checkout or the identified sdist,
Python 3.12 and a suitable `uv` installation. Dependency installation may access
your configured package index unless a reviewed offline cache is supplied.
From the core package directory:

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy --python-version 3.12
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --all-extras python tools/verify_distribution.py
```

The distribution verifier uses isolated installed consumers outside the checkout,
checks runtime bytes, exercises examples and compares the rebuilt wheel from
sdist. It is distinct from source tests and from a remote CI job. The first-use
kit verifier preserves deliberate negative recipe exits; do not turn them into
unconditional success.

The candidate driver provides a byte-bound aggregate receipt:

```bash
python tools/check_candidate.py --package . --output /absolute/path/new-checks.json
```

Every invocation needs a fresh receipt name and matching log/pytest paths. The
driver refuses existing output evidence before starting checks and reserves its
receipt exclusively. After a failed or interrupted attempt, keep that output
and choose another `--output` name for the retry.

The aggregate candidate driver and `release_manifest.py` require a Git checkout
to bind the complete source tree to a commit. An extracted sdist can run the
package's lint, types, assets, tests and build checks, but it cannot create that
Git-bound release receipt by itself. Keep the original source revision and
artifact receipt from the provider. The benchmark distribution verifier also
expects the monorepo layout, including the adjacent matching core source and
built wheel; an isolated benchmark sdist does not supply those inputs.

For the benchmark, work from `packages/equiframe-benchmark`, build the matching
core wheel first, and run the same lint/type/assets/test/build/Twine/distribution
sequence after:

```bash
uv sync --locked --all-extras --reinstall-package equiframe
```

Reinstallation matters when editing a local unreleased candidate with the same
version string: dependency caches
can otherwise retain an old local core. The candidate driver checks runtime
source hashes and reinstalls local dependencies; installed artifact verification
still consumes the exact wheels, not an editable checkout.
Published distribution files remain immutable; a local development reinstall
does not authorize replacing them.

Changing dependencies requires reviewed lock changes and the relevant
`tools/verify_compatibility.py` cells. Minimum/recent direct resolutions, platforms,
extras, corpus, hashes, failures and skips must be recorded accurately. A narrower
focused test does not replace all affected checks. Never update a compatibility
fingerprint automatically just to silence a regression.

## Reviewable change procedure

1. Describe the problem, affected contract/capability and evidence of failure
2. Work on a branch based on the agreed candidate/base; identify dependencies
   on unmerged changes. Do not assume the candidate is already on main
3. Implement real behavior with minimal synthetic regression fixtures, including
   positive, negative, invalid and not-evaluable cases
4. Update public English usage, reference/limits, schemas and compatibility
   classification when affected. Record observable changes and migration guidance
5. Preserve historical fixture bytes and unknown-version rejection. New incompatible
   writes need a new format, not retrospective reinterpretation
6. Run affected source and installed-artifact checks against final bytes and retain
   receipts. Distinguish passed, failed, blocked and unexecuted checks
7. Request review with scope, rationale, artifacts, test outcomes and known limits.
   A PR convention is not proof of enforced branch protection or independent approval

Methodological changes require explicit rationale, version and consequences in
the repository's decision/traceability documents. Do not describe synthetic
fixtures, untrained models, planned APIs, pending pilots or unexecuted tests as
scientific evidence or external acceptance.

Public-facing current documentation is English. Historical design and the
reinforced roadmap can remain Spanish with their original context. Keep the
installed handbook self-contained; essential instructions must not depend on
private monorepo links. Run examples against the exact distribution, and label
signature sketches or consumer-specific request templates as such.

## CI and publishing permissions

The project's existing CI is manually dispatched; platform jobs require explicit
selection/authorization. Pushing a branch or creating a PR does not prove the
matrix ran. Verify the exact workflow run, commit, environment and artifact before
claiming remote results. CI should use least privilege, and publication remains
a separate protected owner decision.

Building locally, checking Twine metadata, producing an SBOM or installing by
local wheel does not publish, reserve a project name or approve licensing.
Do not upload to PyPI, deploy a service, grant sharing access or activate a remote
release flow without the specific authorization and completed gates in
[releasing.md](releasing.md).

## Adoption and maintenance evidence

The [adoption record checker](adoption.md#check-the-structured-record-locally)
is a developer-only sdist tool. Its exit 0 establishes input consistency, never
consent, human independence or adoption. Keep the example registry empty and
real observations outside Git. The [maintenance process](maintenance.md) requires
minimal permitted reproductions and separate technical/consumer confirmation;
Hernán Troya (`htroya`) is the confirmed owner; no backup, response deadline or
SLA is promised.

## Fast source feedback

Use the [quick CI layer](fast-ci.md) for bounded PR/change feedback and the
`tools/check_architecture.py --check` from the source distribution.
Its smoke receipt is separate from the full candidate/distribution/matrix checks.
The installed [product journeys](journeys.md) make positive, different and
unavailable outcomes reproducible without a source checkout.

Type-check each selected Python with its own resolved dependency/stub set and
matching `mypy --python-version X.Y`. The aggregate driver observes that version
after sync and supplies it automatically. The checked-in minimum target remains
3.10 and strict mode remains enabled; no error codes or imports are suppressed.
A 3.11+ stub package requiring newer typing syntax is not evidence about the
3.10 dependency branch. Each branch must pass under its actual interpreter.
