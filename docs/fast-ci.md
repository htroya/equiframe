# Quick local source checks

[Handbook](index.md) · [Contributing](contributing.md) · [Performance](performance.md)

The quick selection runs locally. Publication is manual; this public repository
does not configure a GitHub Actions workflow. A quick pass covers the selected
source checks and does not establish full-suite, installed-package, platform or
release readiness.

## Run the selection

Start at the repository root with a supported interpreter and `uv`. These
commands select Python 3.12; choose 3.10, 3.11 or 3.13 for another interpreter.
The runner uses its actual interpreter for strict typing.

```bash
cd /path/to/equiframe
uv sync --locked --all-extras --no-editable --python 3.12
uv run --locked --all-extras python tools/quick_check.py --package core
cd packages/equiframe-benchmark
uv sync --locked --all-extras --no-editable --reinstall-package equiframe --python 3.12
uv run --locked --all-extras python ../../tools/quick_check.py --package benchmark
cd ../..
```

Use `--list` to inspect commands without executing them. `--output /new/local/path`
retains the receipt, logs and pytest files in that new directory. Without it,
the runner uses a fresh repository `.cache/quick-<id>` directory. Existing output
directories are rejected. A failed command stops the selection and retains its
actual exit code; an interrupted or incomplete run is not a pass. Logs stay local
and may include ordinary diagnostic paths and synthetic fixture values.

## What is checked

- Whole-package Ruff lint, formatting, strict mypy and generated-asset drift.
- The core architecture boundary and an explicit selection of contract, semantic,
  migration, snapshot, compatibility, CLI and product-journey tests.
- An explicit benchmark selection covering core aliases, grouped splits, training
  selection, evaluation boundaries, the Verify bridge and CLI diagnostics.

The exact test lists live in `tools/quick_check.py`. The runner deliberately
imports the current source directories of the core and benchmark. Its receipt
records the commit, worktree status, lock digest, interpreter, platform, commands,
exit codes and elapsed time. Dependency installation is outside those timings.

## Before a release

Run the complete checks in [Releasing](releasing.md): full tests, builds, strict
Twine validation, clean wheel/sdist consumers, exact artifact receipts and the
affected dependency and platform combinations. Those checks run separately from
this source-development selection. Local command output does not establish that
a remote job ran or that a package was published.
