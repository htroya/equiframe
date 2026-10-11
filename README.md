# EquiFrame

[Portal de documentación / Documentation portal](docs/README.md): rutas por
tarea, glosario, integración y controles manuales. Las guías empaquetadas y los
informes históricos tienen alcances separados.

[Documentación profesional](docs/DOCUMENTATION_RESULT_20261010.md):
**18/20 controles = 90 %** bajo DOC-PRO-20-v1, una rúbrica propia fijada antes
de los cambios. Incluye navegación manual comprobada y cuatro bloques de código
ejecutados desde el texto contra el wheel A13 identificado. Lectura por una
persona independiente y documentación pública con derechos aprobados siguen
pendientes. No equivale al 85 % histórico sin una fórmula identificada.

[Verificación documental vigente](docs/DOCUMENTATION_RECHECK_20261010.md):
mantiene el 90 % con controles actuales y evidencia de ejemplos ligada a los
mismos bytes de A13. El recibo original conserva sus resultados históricos.

[Primer uso por perfil / First use](packages/equiframe/docs/first-use.md)

[Preparación manual de PyPI](docs/PYPI_PREPARATION_RESULT_20261010.md):
**16/20 controles = 80 %** bajo PYPI-PREP-20-v1. Se auditó el par privado A13
y se probó el procedimiento local. Licencia, cuentas/roles, documentación
pública y ensayo real en TestPyPI siguen pendientes. El indicador no autoriza
publicación; la guía identifica los pasos restantes para el 90 % solicitado.

[Calidad verificable de paquete A13](docs/PACKAGE_QUALITY_RESULT_20261010.md):
**16/20 controles = 80 %**, con la rúbrica propia PACKAGE-QUALITY-RP-20-v1,
inspirada en Real Python. El artículo no define una nota oficial. Publicación,
adopción externa, comunidad y licencia permanecen pendientes. Se comprobó el
par privado en Windows y Linux ARM64; no se declara toda la matriz de OS/Python.
El informe identifica artefactos, suites completas, fallos corregidos y límites.

Trazabilidad del wheel A13, medida aparte: **4.298/8.385 = 51,26 %**,
con 3.445 casos distintos y 0 FAIL en ejecución normal y optimizada.
Los recibos A11/A12 siguientes conservan sus artefactos históricos.

[Pruebas con trazabilidad por opción del núcleo A12](docs/OPTION_TRACEABILITY_RESULT_20261010.md):
4.296/8.383 obligaciones (51,25 %), con 3.443 casos sintéticos distintos.
Este porcentaje identifica el wheel A12; no se atribuye automáticamente a A13.
El recibo distingue validación de metadatos, rechazos esperados y opciones
pendientes; no acredita por sí solo sus efectos en motores nativos.

[Usabilidad técnica evaluada](docs/USABILITY_CURRENT_RESULT_20261010.md):
11/12 criterios completos (91,67 %) para A12, con la misma rúbrica U01–U12.
La evaluación con personas reales sigue pendiente; no es un porcentaje de
satisfacción ni modifica el índice separado de Universalidad A11.
Las evaluaciones A11/A12 permanecen ligadas a sus artefactos históricos.

[Arquitecto](packages/equiframe/docs/arquitecto.md) · [Científico](packages/equiframe/docs/cientifico.md) · [Inicio en español](packages/equiframe/docs/inicio.md) · [Choose an API](packages/equiframe/docs/choosing-api.md) · [Eight journeys](packages/equiframe/docs/journeys.md)

**Semantic comparison and reviewable evidence for tabular results in Python.**

Declare what your data must preserve, compare complete captured outputs, and
locate differences in values, types, keys, multiplicity and order. Use EquiFrame
inside an existing pandas, Polars, Arrow or CI workflow, or use its separate
native execution, verification and bounded migration APIs.

**Status: private Alpha pair: core 0.12.0a13 / benchmark 0.12.0a13.** Identify artifacts by commit and
wheel/sdist SHA-256, not the version string alone. The team's package is **not
publicly released on PyPI**. License and name/ownership decisions remain pending.
Public release requires STEP10, the global review and specific owner approval.
A local install, passing test, prepared metadata or configured CI job does not
close those gates. [Release process](packages/equiframe/docs/releasing.md).

[Universalidad en cinco pasos](packages/equiframe/docs/universalidad-cinco-pasos.md)
adds interchangeable typed inputs, native windows, explicit source extensions
and a complete installed six-input/three-engine example.

[Avance técnico evaluado](docs/UNIVERSALITY_80_RESULT_20261010.md):
48/60 comprobaciones (80 %) en la misma rúbrica propia para A11; antes 41/60
(68,3 %). El informe publica
las definiciones y los pendientes; no certifica universalidad completa ni
compara directamente ese resultado con el 25 % de cierre del corte histórico A9.

[Quick start](packages/equiframe/docs/quickstart.md) ·
[Three installed recipes](packages/equiframe/docs/recipes.md) ·
[English handbook](packages/equiframe/docs/index.md) ·
[API](packages/equiframe/docs/api.md) ·
[Extension ports](packages/equiframe/docs/extending.md) ·
[Semantics and limits](packages/equiframe/docs/semantics.md)

## Install the private candidate

Use the [private wheelhouse installation guide](packages/equiframe/docs/installed-private.md) with
`equiframe[arrow]==0.12.0a13`, a fresh environment outside the checkout,
normal pip dependency resolution and the separately supplied artifact hashes.
It includes Linux and PowerShell commands and a separate hash-locked trial.
This is private installation by name, not publication in PyPI or TestPyPI.
Choose `[duckdb]` for the architect's SQL exercise, `[arrow]` for the scientist's
preparation, or `[engines]` for native migration across all three engines. Add
`ml` only when using the optional detector fitting APIs. The
[role first-use guide](packages/equiframe/docs/first-use.md) needs no ML package.
The separate benchmark is `equiframe-benchmark[engines,ml,resources]==0.12.0a13`
and requires exactly core `0.12.0a13`. The prior a6 package artifacts and
observations remain historical; current receipts identify corrected minimum-Polars
expression composition.
Python metadata targets 3.10/3.11/3.12/3.13; the maturity matrix remains open until every required cell is reviewed; only actual artifact-specific receipts establish
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
