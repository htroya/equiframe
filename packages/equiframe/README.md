# EquiFrame 0.12.0a2

[Inicio en español](docs/inicio.md) · [Choose an API](docs/choosing-api.md) · [Eight journeys](docs/journeys.md)

**Semantic comparison and reviewable evidence for tabular results in Python.**

EquiFrame compares captured outputs under explicit contracts for values, types,
keys, multiplicity, order, missing data and time. It integrates with eager pandas,
Polars and Arrow inputs, existing files and CI. Native execution, bounded
migration, operational Verify and experimental anomaly detection are separate
APIs with explicit capabilities and failure states.

## Private Alpha status

This is the **private Alpha candidate 0.12.0a2**, identified by its commit and
artifact hashes. The team's package is **not publicly released on PyPI**.
Do not install an unrelated package with this name from an arbitrary index.
License and name/ownership remain owner decisions; access is not permission to
redistribute. Public release requires STEP10, the global review and specific
owner approval. No public security/support SLA, independent human adoption,
production certification or accepted real-DW integration is claimed.

See [release/rollback](docs/releasing.md), [security](docs/security.md) and
[dependency inventory](docs/dependencies.md). Those gates are separate from
successful build/install checks.
[Adoption](docs/adoption.md) and [maintenance](docs/maintenance.md) explain
consented real-project observations, repeat use, minimal incident reports and
pending ownership decisions.

## Install the private candidate

Use the [private wheelhouse installation guide](docs/installed-private.md) with
`equiframe[engines,ml]==0.12.0a2`, a fresh environment outside the checkout,
normal pip dependency resolution and the separately supplied artifact hashes.
It includes Linux and PowerShell commands and a separate hash-locked trial.
This is private installation by name, not publication in PyPI or TestPyPI.
Python metadata admits 3.12/3.13; only actual artifact-specific receipts establish
platform results. The earlier 0.11.1 first-use kit remains historical.

## Compare and enforce explicitly

```python
from pathlib import Path
import equiframe as ef
import pyarrow as pa

expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
candidate = pa.table({"id": ["B", "A"], "quantity": [21, 10]})
result = ef.diff(candidate, expected, keys=["id"], work_dir=Path("private-evidence"))
print(result.state, result.complete)  # different True
report = ef.write_comparison_report(result, Path("comparison-report"))
print(report.to_text())
try:
    ef.assert_equivalent(result)
except ef.EquivalenceDifferentError:
    print("Expected regression: equivalence rejected")
else:
    raise RuntimeError("The regression was incorrectly accepted")
```

Use a new report directory. Default reports hide values, names and paths; the
raw evidence directory may contain all supplied data. `diff` defaults to a
right-hand expected reference; `compare` takes an explicit contract and defaults
to peer comparison. Neither silently executes lazy frames or DuckDB relations.

`equivalent` applies to captured outputs under the evaluated contract, not all
future inputs or business correctness. Two implementations can share an error.
Both `different` and `not_evaluable` fail acceptance, including a complete scan
with an invalid expected output. Use `assert_equivalent` or explicit
`equivalence_decision(...).accepted`; truth testing a result raises `TypeError`.

## Self-contained English handbook

- [Index and service selection](docs/index.md)
- [Quick start](docs/quickstart.md) and [three installed recipes](docs/recipes.md)
- [Public API and CLI reference](docs/api.md)
- [Semantics, guarantees and limits](docs/semantics.md)
- [Compatibility and deprecations](docs/compatibility.md)
- [Performance and resource budgets](docs/performance.md)
- [Upgrade, recovery and support](docs/upgrading.md)
- [Contribution guide](docs/contributing.md)
- [Security](docs/security.md), [dependencies/SBOM](docs/dependencies.md),
  [release/rollback](docs/releasing.md)

The **wheel** carries the handbook under `equiframe/docs/`:

```python
from importlib.resources import files

print(files("equiframe").joinpath("docs/index.md").read_text(encoding="utf-8"))
```

The **sdist** also carries `docs/`, examples, tests, tools and JSON schemas.
This README is distribution metadata. Historical Spanish monorepo documents
provide additional design history, but are not needed to follow the handbook.
Default local operation is not a sandbox or a verified no-network claim: supplied
callbacks, SQL, clients/plugins and dependencies retain their own effects.
