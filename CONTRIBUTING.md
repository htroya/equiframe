# Contributing to EquiFrame

EquiFrame is a private Alpha candidate. Use your own authorized repository account,
a focused branch and a reviewable change. Read `AGENTS.md` and the required
architecture/API/integration/roadmap documents before implementation.

The complete, distribution-carried [contribution guide](packages/equiframe/docs/contributing.md)
covers environment setup, final-byte checks, review, semantic boundaries and
publishing permissions. [Compatibility](packages/equiframe/docs/compatibility.md)
and [upgrading](packages/equiframe/docs/upgrading.md) describe the public contract.

## Source-development setup helper

The historical `install_deps_alma9.sh` entry point now uses the actual core package
and committed lock. It requires an existing supported Python and `uv`, performs
no OS updates, and does not install the benchmark or DW components:

```bash
bash install_deps_alma9.sh --python python3.12 --dry-run
bash install_deps_alma9.sh --python python3.12
```

It can run from any working directory and targets only
`packages/equiframe/.venv`, ignoring an unrelated `UV_PROJECT_ENVIRONMENT`.
Use `--python python3.13` for an already-installed 3.13 interpreter. The filename
is historical: neither these command-contract tests nor the Linux cloud gates
qualify AlmaLinux. On Windows, use the direct `uv` commands below.
Run the root helper tests without installing packages with
`python -m unittest discover -s tests -v` (Bash required).

## Core checks

Before installing a privately supplied candidate, use the standard-library
[offline wheel audit](docs/OFFLINE_WHEEL_AUDIT.md) with its separately supplied
trusted SHA-256. This verifies artifact integrity and local Markdown destinations;
it does not authenticate a self-supplied hash or approve public distribution.

From `packages/equiframe`, with a selected supported Python and `uv` available:

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

For the benchmark, first build the matching core wheel, then use its package
directory and `uv sync --locked --all-extras --reinstall-package equiframe` before
the same check sequence. Installed tests run outside the checkout; a successful
source test or editable import does not establish distribution correctness.

The aggregate `check_candidate.py` driver accepts `--python` (default: the driver executable),
propagates it to sync/run, and records the observed target interpreter separately.
For example: `python3.10 tools/check_candidate.py --python python3.10 --output /absolute/new/checks.json`.
Every attempt needs a new receipt path.

The aggregate `check_candidate.py` driver and `release_manifest.py` require the
Git checkout; isolated sdists can run package checks but cannot establish that
Git-bound source receipt. Benchmark distribution verification also requires the
adjacent matching core source directory and built wheel. See the packaged
contribution guide for the distinction between these verification inputs.

These commands are instructions, not claims of a passed candidate. Preserve the
aggregate byte-bound receipt from `tools/check_candidate.py`; repeat affected
compatibility cells after dependency changes. Do not erase skips, failed attempts
or missing platform results. Manual CI configuration is not evidence that a
remote job ran, and a push/PR does not automatically run the platform matrix.

## Review expectations

For documentation changes, follow the [documentation maintenance policy](docs/DOCUMENTATION_MAINTENANCE.md)
and run its manual navigation/example checks. The repository portal is distinct
from the handbook carried by an already-built wheel; changing root guides does
not change or revalidate those historical artifact bytes.

- Preserve contract semantics, typed states, safe failure and historical evidence
- Keep R/M/B/H/O independent; execute each engine natively
- Add independently expected positive, different, invalid and incomplete fixtures
- Keep current public documentation in English and runnable from exact artifacts
- Review lock, schema, stability, changelog and migration effects explicitly
- Honor [component ownership](docs/TEAM_INTEGRATION.md); no infrastructure or DW
  redesign inside a core-only change
- Exclude credentials, real datasets, databases, binary models and private outputs
- Request review; do not assert unverified branch-protection or approval status

License, name/ownership, security/release responsibilities and public distribution
remain owner decisions. No PyPI publication before STEP10, global review and
specific owner approval. See [security](packages/equiframe/docs/security.md),
[dependency evidence](packages/equiframe/docs/dependencies.md) and
[release/rollback](packages/equiframe/docs/releasing.md).

Type-check each selected Python with its own resolved dependency/stub set and
matching `mypy --python-version X.Y`. The aggregate driver observes that version
after sync and supplies it automatically. The checked-in minimum target remains
3.10 and strict mode remains enabled; no error codes or imports are suppressed.
A 3.11+ stub package requiring newer typing syntax is not evidence about the
3.10 dependency branch. Each branch must pass under its actual interpreter.
