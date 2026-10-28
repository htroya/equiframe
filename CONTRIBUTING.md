# Contributing to EquiFrame

Use a focused branch and a small, reviewable change. Read the [API reference](docs/api.md),
[compatibility register](docs/compatibility.md) and [semantic contract](docs/semantics.md)
before changing public behavior. Report ordinary bugs in the
[issue tracker](https://github.com/htroya/equiframe/issues); sensitive reports belong
in the [private security channel](https://github.com/htroya/equiframe/security/advisories/new).

## Development

The library uses the standard source layout: source in `src/`, guides in `docs/`,
tests in `tests/` and package metadata in `pyproject.toml`. The benchmark is a separate
package under `packages/equiframe-benchmark/`. The application under
`validation/consumer/` checks independent expected outputs and is excluded from
both published distributions.

With an existing supported Python and `uv`, run from the repository root:

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy --python-version 3.12
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
```

Use the interpreter and dependency resolution appropriate to Python 3.10, 3.11,
3.12 or 3.13. A passing run on one interpreter does not certify every dependency
combination. Development environments may use source installs; release validation
must also consume installed wheels and sdists outside the checkout.

## Review and releases

Preserve exact decimals, keys, missing values, multiplicity, order and dates under
the declared contract. Keep rules, Isolation Forest, MAD and independently authored
expectations separate. Every engine executes its own native implementation. Add
positive, different, invalid and incomplete cases with independent expectations.

Public functions need type annotations and actionable exceptions. CLI changes
must cover exit codes, stdout/stderr, interactive input and relevant environment
or permission failures. Never publish credentials, private datasets, models or
execution results. Existing synthetic compatibility fixtures keep their exact bytes.

Versions derive from reviewed Git tags. Update the changelog and upgrade notes
when behavior changes. Release checks require canonical raw Git bytes, a clean
tagged commit and source plus installed-distribution validation; see the
[release guide](docs/releasing.md) for the manual commands and acceptance checks.
No GitHub Actions job is used for this release.

Hernán Troya (`htroya`) maintains releases and security coordination without a
fixed response-time SLA. Original project code is MIT; third-party components
retain their licenses and notices. Research conclusions and external adoption
have their own acceptance criteria.
