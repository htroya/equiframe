# Fast source checks and explicit release checks

[Handbook](index.md) · [Contributing](contributing.md) · [Performance](performance.md)

The quick selection runs locally without consuming GitHub Actions minutes.
At the owner's request, its GitHub workflow now has only `workflow_dispatch`:
pushes and pull requests do not start it. Explicitly dispatching it in GitHub
still consumes Actions minutes and runs one Linux x86_64/Python 3.12 job.
The existing platform matrix and release-candidate workflows remain manual.
A workflow file is configuration, not evidence that a GitHub job has run. A quick
pass does not establish full-suite, wheel/sdist, platform or release readiness.

## Run exactly the quick selection locally

From the repository root, with the existing supported interpreter and `uv`.
These commands explicitly select 3.12 for development; choose 3.10, 3.11 or 3.13
for another cell. The driver uses its actual interpreter for strict typing:

```bash
cd /path/to/equiframe
uv sync --locked --all-extras --no-editable --python 3.12
uv run --locked --all-extras python tools/quick_check.py --package core
cd ../equiframe-benchmark
uv sync --locked --all-extras --no-editable --reinstall-package equiframe --python 3.12
uv run --locked --all-extras python ../equiframe/tools/quick_check.py --package benchmark
```

Use `--list` to inspect commands without executing them. `--output /new/private/path`
retains the receipt, individual logs and pytest files in that new directory.
Omitting it creates a fresh repository `.cache/quick-<id>` directory. Reusing an
output directory is rejected before commands run. A failed command stops the
selection, retains its real exit code, and leaves `complete=false`. An interruption
or missing final receipt is not a pass. Review logs locally; they can include
ordinary diagnostic paths and fixture values and are not automatically uploaded.

The runner deliberately uses the current core and benchmark source directories
for imports. Receipts record the commit, worktree status, package lock digest,
interpreter, platform, selected commands, exits and elapsed seconds. This is
source-development evidence, not the final-byte artifact receipt produced by
`check_candidate.py`. It requires the Git checkout and is not an installed-wheel
consumer test. Dependency installation time is outside runner timings.

## What runs

- Root command and workflow contract tests
- Core AST architecture boundary check
- Whole-package Ruff lint, formatting, strict mypy and generated-asset drift checks
- A fixed, reviewable core semantic selection covering contracts, explicit result
  truthiness, optional configuration, assertions, diff declarations, public
  compatibility/stability, pinned snapshots, historical readers, six native
  migration directions, CLI diagnostics, progressive documentation, SQLite
  snapshots, eight product journeys and the new developer tools
- A fixed benchmark selection covering core aliases, grouped splits, training
  selection, evaluation boundaries, the Verify bridge and CLI diagnostics

The test file lists live only in `tools/quick_check.py`; CI invokes that runner.
The selection is intentionally small and cannot replace all comparison, engine,
workflow, ingestion, evidence, ML or experimental evaluation tests. Extend it when
a cheap regression guards a high-impact invariant, rather than duplicating tests
or silently dropping failures. There is no claimed fixed wall-time guarantee.

## Manual workflow boundaries

`equiframe-quick.yml` has only an explicit `workflow_dispatch` event. There are no
push, pull-request, scheduled or chained-workflow triggers. It has only
`contents: read`, disables persisted checkout credentials, reuses the full commit
pins already used by the manual workflows, and installs the locked environments.
It does not reference secrets,
accept command inputs, upload private artifacts, build releases, deploy or publish.
Concurrent runs for the same workflow/ref are cancelled in favor of the newer run;
a cancelled run is not a successful check.

The `.yml` file uses JSON syntax, which is valid YAML, so stdlib tests can parse
its event/permission/step structure without adding a runtime or development YAML
dependency. The root workflow contract tests guard the manual-only quick and expensive
workflows, and verify that both packages' selected source tests exist. GitHub branch-protection settings are external and are not configured
or claimed by this change.

An earlier automatic run failed before any step executed; its failure remains
visible and its startup cause is unverified. The manual-only policy does not
turn that failure into a pass, disable tests or alter account/billing settings.
No rerun or manual dispatch is implied by this guide. Local receipts identify
what actually ran separately from the failed remote attempt.

Before approving an identified candidate, run the complete checks in
[Contributing](contributing.md): full tests, build, strict Twine, clean wheel/sdist
consumers, exact artifact receipts and affected dependency/platform cells. Those
explicit gates retain their own evidence and pending release-owner decisions.
