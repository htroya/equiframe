# EquiFrame

[Inicio en español](packages/equiframe/docs/inicio.md) · [Choose an API](packages/equiframe/docs/choosing-api.md) · [Eight journeys](packages/equiframe/docs/journeys.md)

**Semantic comparison and reviewable evidence for tabular results in Python.**

Declare what your data must preserve, compare complete captured outputs, and
locate differences in values, types, keys, multiplicity and order. Use EquiFrame
inside an existing pandas, Polars, Arrow or CI workflow, or use its separate
native execution, verification and bounded migration APIs.

**Status: private Alpha candidate 0.12.0a3.** Identify artifacts by commit and
wheel/sdist SHA-256, not the version string alone. The team's package is **not
publicly released on PyPI**. License and name/ownership decisions remain pending.
Public release requires STEP10, the global review and specific owner approval.
A local install, passing test, prepared metadata or configured CI job does not
close those gates. [Release process](packages/equiframe/docs/releasing.md).

[Quick start](packages/equiframe/docs/quickstart.md) ·
[Three installed recipes](packages/equiframe/docs/recipes.md) ·
[English handbook](packages/equiframe/docs/index.md) ·
[API](packages/equiframe/docs/api.md) ·
[Extension ports](packages/equiframe/docs/extending.md) ·
[Semantics and limits](packages/equiframe/docs/semantics.md)

## Install the private candidate

Use the [private wheelhouse installation guide](packages/equiframe/docs/installed-private.md) with
`equiframe[engines,ml]==0.12.0a3`, a fresh environment outside the checkout,
normal pip dependency resolution and the separately supplied artifact hashes.
It includes Linux and PowerShell commands and a separate hash-locked trial.
This is private installation by name, not publication in PyPI or TestPyPI.
Python metadata admits 3.12/3.13; only actual artifact-specific receipts establish
platform results. The earlier 0.11.1 first-use kit remains historical.

## A small comparison

After installing the identified wheel with its `arrow` extra and reviewed
dependencies:

```python
from pathlib import Path
import equiframe as ef
import pyarrow as pa

expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
candidate = pa.table({"id": ["B", "A"], "quantity": [21, 10]})
result = ef.diff(candidate, expected, keys=["id"], work_dir=Path("private-evidence"))
print(result.state, result.complete)  # different True
report = ef.write_comparison_report(result, Path("comparison-report"))
print(report.to_text())  # Values, names and paths are hidden by default
try:
    ef.assert_equivalent(result)
except ef.EquivalenceDifferentError:
    print("Expected regression: equivalence rejected")
else:
    raise RuntimeError("The regression was incorrectly accepted")
```

The right-hand side is the expected output by default. `B` has quantity 21
instead of 20; row reordering is allowed by this declaration. Use a fresh report
directory each time. Raw snapshots/differences stay in the private evidence
directory; a redacted report does not delete them.

`equivalent` means the captured data satisfies the evaluated contract, including
explicitly authorized policies. It does not establish business correctness or
universal program equivalence. Two engines can agree on the same bug.
`different` and `not_evaluable` both fail the gate. `complete=True` alone is not
acceptance, and `assert result` / `if result` raise `TypeError` in every state.

## Choose the service you need

| Need | API | Boundary |
|---|---|---|
| Compare eager DataFrames/Arrow | `diff` | Conservative inspectable contract; no implicit lazy/SQL execution |
| Compare captured results/files | `compare` | Explicit contract; complete values and multiplicity |
| Enforce equivalence in tests | `assert_equivalent` | Explicit guarantee and optional persisted-evidence requirements |
| Explain a result | `comparison_report` | Common redacted JSON/text/HTML/notebook view |
| Capture trusted DuckDB SQL | `capture_duckdb` | Explicit one-query execution and detached snapshot |
| Consume a pinned external snapshot | `SnapshotDataSource` | Injected client; no benchmark dependency or implicit transport |
| Execute native transformations | `execute` | pandas/Polars callbacks or registered DuckDB SQL; completion is not correctness |
| Migrate a bounded relational plan | `migrate` | Genuine native implementations; no arbitrary Python/SQL translation |
| Verify existing outputs | `verify` | Agreement, expected output, rules, coverage and review are separate |
| Ingest/workflow/local publication | `ingest_file`, `run_workflow`, `ParquetDestination` | Explicit schemas/checkpoints; no production gateway claim |
| Preserve portable evidence | `export_bundle`, `import_bundle` | Supported finalized closed inventories; hashes are not signatures |
| Study anomalies and costs | Separate `equiframe-benchmark` | Experimental; technical synthetic checks are not scientific results |

The core does not require OCI, SERCOP, a data warehouse or the benchmark package.
Optional extras are `arrow`, `pandas`, `polars`, `duckdb`, `engines` and `ml`.
Importing `equiframe` does not load those optional runtimes.

## Guarantees and operating limits

- Preserve Decimal, NULL/NaN, keys, duplicates, order and time under explicit
  contracts; do not cast, deduplicate, round or relax tolerance to conceal differences
- Capture, comparison, native execution and migration have distinct supported
  subsets. Unsupported metadata/types fail explicitly
- Core budgets are cooperative, not hard process memory/time limits. Missing
  finalization, publication failure and process kill never imply equivalence
- Default local operation is not a sandbox or a verified no-egress guarantee.
  Trusted callbacks, SQL, injected clients/plugins and dependencies can have
  network or other external effects. See [security](packages/equiframe/docs/security.md)
- An integrity hash does not authenticate an author, prove independent review or
  establish expected-output correctness

Read [semantics](packages/equiframe/docs/semantics.md),
[compatibility](packages/equiframe/docs/compatibility.md),
[performance](packages/equiframe/docs/performance.md) and
[upgrading/support](packages/equiframe/docs/upgrading.md) before adoption.
Historical Linux matrix receipts apply to identified wheels; no unexecuted
Windows/macOS/ARM64 job is presented as current support.

## Documentation and development

The [English handbook](packages/equiframe/docs/index.md) is self-contained and
carried in wheel and sdist. Installed copies are readable at
`importlib.resources.files("equiframe").joinpath("docs/index.md")`.
[CONTRIBUTING.md](CONTRIBUTING.md) contains development commands and review rules.
The [post-roadmap review](docs/GLOBAL_REVIEW_REFACTOR_20261006.md) records concrete
correctness/refactoring changes and their remaining release boundaries.
[Benchmark README](packages/equiframe-benchmark/README.md) explains its separate
experimental package and installation.

Historical design, thesis, integration and candidate records remain under
[`docs/`](docs/), primarily in Spanish. They retain dated context and pending
external criteria; they do not override current English API guidance or prove a
new candidate passed old checks. [Architecture](docs/ARCHITECTURE.md) and
[team ownership](docs/TEAM_INTEGRATION.md) preserve the integration boundaries.

```text
packages/equiframe/            core library, packaged handbook, examples and tests
packages/equiframe-benchmark/  experimental evaluation and engineering costs
packages/equiframe-data/       data-access integration component
packages/equiframe-sercop/     domain integration component
services/data-gateway/         data-service specification
infra/                        infrastructure specification
docs/                         historical design, review and candidate records
```

**License:** pending owner decision. Private access does not authorize
redistribution. Public release, external adoption, real service/DW acceptance and
scientific conclusions retain their separate unresolved gates.
