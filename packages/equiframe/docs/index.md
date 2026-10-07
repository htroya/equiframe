# EquiFrame user handbook

[Inicio en español](inicio.md) · [Choose an API](choosing-api.md) · [Eight journeys](journeys.md)

**Semantic comparison and reviewable evidence for tabular results in Python.**

EquiFrame lets you declare what a result must preserve, compare materialized
outputs, and locate differences in values, types, keys, multiplicity and order.
You can use it inside an existing pandas, Polars, Arrow or CI workflow without
adopting its execution runner. Native execution, bounded declarative migration,
operational verification and experimental anomaly detection are separate services.

## Release status

This handbook describes the **private Alpha candidate 0.12.0a7**. The version string
alone does not identify its bytes: use the commit, wheel/sdist SHA-256 and build
receipt supplied with your artifact. The team's package is **not publicly
released on PyPI**. Do not install a project by the same name from an arbitrary
index to obtain this candidate.

Public distribution remains blocked on the owner's license and name/ownership
decisions, STEP10, the global review and specific owner approval. Technical
installation tests do not authorize publication. There is no claimed production
certification, independent human adoption, security-response SLA or accepted
real data-warehouse integration. Access to a private artifact does not grant
redistribution rights. See [release and rollback](releasing.md) and
[security](security.md).

## Start here

1. [Quick start](quickstart.md): verified private artifacts, a clean environment,
   a complete small comparison and a fail-closed assertion
2. [Three installed recipes](recipes.md): diagnose a pandas refactor, validate a
   pandas → DuckDB migration and retain evidence before a pytest/CI failure
3. [Public API reference](api.md): entry points, models, CLI and safe result states
4. [Semantics, guarantees and limits](semantics.md): what equality means, what is
   preserved, what is rejected and what evidence proves
5. [Compatibility](compatibility.md): stability, dependency extras, measured
   platforms and the distinction between declared and demonstrated support
6. [Performance and resource budgets](performance.md): cost boundaries, bounded
   measurement, missing finalization and practical budget choices
7. [Upgrading and troubleshooting](upgrading.md): safe acceptance, historical
   evidence, deprecations and actionable failure diagnosis
8. [Extension ports and pinned snapshots](extending.md): reuse your own data client
   without the benchmark, preserve metadata and understand resource ownership
9. [Contributing](contributing.md): reproducible checks, review and ownership
10. [Dependency inventory](dependencies.md), [security](security.md) and
   [release process](releasing.md): artifact identity, supply-chain evidence,
   disclosure and unresolved owner decisions
11. [Adoption](adoption.md) and [maintenance](maintenance.md): consented real-project
    observations, later-change retention, useful issue reports and critical trust incidents

## New candidate guides

- [Normal pip installation through the private channel](installed-private.md)
- [Native relational extensions and per-engine limits](migration-ir.md)
- [CSV/JSONL batches and exact ingestion receipts](ingestion.md)
- [Installed option inventory and honest coverage denominators](option-audit.md)

## Reading this handbook without the repository

The source distribution contains `README.md`, this `docs/` directory, examples,
tests, tools and JSON schemas. The wheel carries the same handbook as package
resources under `equiframe/docs/`; it does not require access to the private
repository. After installing the identified wheel, locate it with:

```python
from importlib.resources import files

handbook = files("equiframe").joinpath("docs")
print(handbook.joinpath("index.md").read_text(encoding="utf-8"))
```

The first-use kit additionally contains the exact wheel, dependency pins and
hashes, four recipe/test scripts, an integrity verifier and English guides.
[Recipes](recipes.md) explains its layout. The package's README is also part of
its distribution metadata. Relative links within this handbook stay within the
handbook; no private-repository document is required to follow the core guide.

## Choosing the right service

| Need | Entry point | Important boundary |
|---|---|---|
| Compare eager DataFrames or Arrow tables | `diff` | Right-hand reference by default; no implicit SQL/lazy execution |
| Compare existing captured outputs or local files | `compare` | Explicit contract; peer comparison by default |
| Fail a test on anything short of accepted equivalence | `assert_equivalent` | Never use truth testing of the result |
| Explain a comparison safely | `comparison_report` | Redacted by default; a view is not the acceptance gate |
| Capture one trusted DuckDB query | `capture_duckdb` | Explicit execution and ownership; detached snapshot |
| Execute a registered native transformation | `execute` | `completed` means execution, not semantic correctness |
| Compile and compare a bounded relational plan | `migrate` | Native implementations; not arbitrary program translation |
| Verify existing outputs against a reviewed reference | `verify` | Agreement, expected-output checks and review remain distinct |
| Retain transportable finalized evidence | `export_bundle` | Only the supported closed inventories; hashes are not signatures |
| Study anomalies or engineering costs | Separate `equiframe_benchmark` | Experimental protocol; synthetic checks are not scientific results |

The [outcome-gate guide](outcome-gates.md) lists the result/decision models that
reject implicit truth testing and the explicit field appropriate to each.

## The minimum safe interpretation

An `equivalent` result means the **captured outputs satisfy the evaluated
contract**, including any explicitly authorized tolerance or normalization. It
does not establish universal program equivalence or business correctness. Two
engines can share a bug, and a declared expected result can be wrong.

`different` and `not_evaluable` both fail an equivalence gate. A complete scan
with an invalid expected result is still `not_evaluable`. Missing finalization,
failed publication, resource exhaustion and an unhandled exception are never a
pass. See [semantics](semantics.md) before using a result to approve a deployment
or data publication.
