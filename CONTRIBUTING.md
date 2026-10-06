# Contributing to EquiFrame

EquiFrame is a private Alpha candidate. Use your own authorized repository account,
a focused branch and a reviewable change. Read `AGENTS.md` and the required
architecture/API/integration/roadmap documents before implementation.

The complete, distribution-carried [contribution guide](packages/equiframe/docs/contributing.md)
covers environment setup, final-byte checks, review, semantic boundaries and
publishing permissions. [Compatibility](packages/equiframe/docs/compatibility.md)
and [upgrading](packages/equiframe/docs/upgrading.md) describe the public contract.

## Core checks

From `packages/equiframe`, with Python 3.12 and `uv` available:

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
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

These commands are instructions, not claims of a passed candidate. Preserve the
aggregate byte-bound receipt from `tools/check_candidate.py`; repeat affected
compatibility cells after dependency changes. Do not erase skips, failed attempts
or missing platform results. Manual CI configuration is not evidence that a
remote job ran, and a push/PR does not automatically run the platform matrix.

## Review expectations

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
