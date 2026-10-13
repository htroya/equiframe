# EquiFrame

**Código actual: pareja 0.12.0a14, Alpha privada.** La extensión opcional
[EDA](packages/equiframe/docs/eda.md) usa salidas privadas separadas. Los
porcentajes enlazados abajo conservan sus candidatos evaluados (A13/A11);
no se transfieren automáticamente al nuevo candidato ni activan Beta.


[Portal de documentación / Documentation portal](docs/README.md): rutas por
tarea, glosario, integración y controles manuales. Las guías empaquetadas y los
informes históricos tienen alcances separados.

[Matriz de estado y porcentajes](docs/PROJECT_STATUS_MATRIX_20261011_EIGHT.md):
ocho áreas vigentes y **75,82 % de promedio** con fracciones originales.
Usabilidad se reevaluó sobre A13; Universalidad conserva su medición A11.
La meta vigente es acreditar **90 % en cada una de las siete áreas solicitadas**
con A14, reservando un 10 % por área a tareas humanas según
[el método actualizado](docs/A14_TECHNICAL_90_METHOD_20261013.md).
La [brecha calculada](docs/A14_PROGRESS_GAP_20261013.md) distingue este objetivo
del promedio histórico y de los requisitos todavía pendientes.
El [plan Alpha](docs/ALPHA_MAXIMIZATION_PLAN_20261012.md) distingue trabajo
técnico y [entregas humanas/PyPI](docs/HUMAN_REQUIREMENTS_20261012.md).
Beta sigue aplazada: alcanzar el promedio no cierra cada área.

El [desarrollo seguro A14](docs/A14_SECURE_DEVELOPMENT_20261013.md) incluye
correcciones del cliente/gateway, coordinación y recuperación, invariantes con
`-O`, pruebas, SAST/SCA y sus límites; no acredita una matriz completa al 90 %.

La [identidad de TestPyPI](docs/TESTPYPI_PUBLISHER_PREPARATION_20261013.md)
está preparada con `publish-testpypi.yml` y entorno `testpypi`; su workflow
comprueba únicamente la configuración. No se ha ejecutado ni publica paquetes.

[Trazabilidad revalidada A14, 13/10/2026](docs/A14_REVALIDATION_CHECKPOINT_20261013.md):
**6.201/8.438 obligaciones**, con **2.237 pendientes** en el inventario indicado.
La revisión independiente del corte `44aa0bd` reprodujo esos conteos. Este
inventario se amplió explícitamente con EDA en la
[revalidación de artefactos corregidos](docs/A14_REVIEW_ARTIFACT_VALIDATION_20261013.md):
**6.905/9.142**, con las mismas **2.237 obligaciones raíz pendientes**. El
inventario ampliado incluye el namespace EDA declarado; otros componentes del
monorepo conservan sus pruebas e inventarios propios. Las repeticiones
y plataformas no crean nuevos IDs. El
[corte histórico A13](docs/OPTION_EXCEPTIONS_RESULT_20261012.md) conserva
**6.309/8.385 = 75,24 %**; su cifra no se transfiere a A14.

[Madurez reevaluada A13](docs/MATURITY_SCOPE_REASSESSMENT_20261012.md):
**11/16 = 68,75 %** con las definiciones originales y recibos actuales.
[M13 ARM64](docs/M13_VM_COMPLETED_20261012.md) concluyó 115 comandos y 52
perfiles; su expediente completo fue devuelto y verificado. Los intentos
anteriores y sus fallos permanecen separados. Las [sdists y suites adicionales](docs/ALPHA_SDIST_AND_SUITES_20261012.md)
complementan la evidencia sin atribuir aceptación humana ni todos los sistemas.

[Dataset entregado a la tutora](docs/SERCOP_PUBLIC_DELIVERY_20261012.md):
captura SERCOP organizada, hashes verificados, carpeta VM de lectura y HTTPS
temporal. [Copia local](docs/SERCOP_LOCAL_REPOSITORY_20261012.md) fuera de Git.
La [ruta compartida vigente](docs/SERCOP_SHARED_ACCESS_20261013.md) está en
`/var/tmp/equiframe-public-sercop-2025/entrega-20261012-v1`, accesible para
`jair` y `ubuntu` mediante el grupo de lectura, conservando el enlace de la
tutora. La entrega antigua del home se eliminó tras verificar la copia.
La entrega pública contiene datos y procedencia, sin EDA ni reflexión.
El [diagnóstico DW](docs/JHAIR_DW_DIAGNOSTIC_20261012.md) delimita el prototipo,
sus fallos reproducidos y los pendientes de Jhair/José.

El [encargo EDA posterior](docs/EDA_NEXT_TASK_20261012.md) se ejecutó después
de esa entrega. Su [implementación A14 y pruebas Windows/ARM64](docs/EDA_IMPLEMENTATION_20261012.md)
conservan salidas privadas, candidatos históricos y la entrega de la tutora.

[SERCOP anual completo en la VM](docs/SERCOP_ANNUAL_VM_20261011.md):
81 comprobaciones SDK completas aprobadas, incluidas 27 sobre las 183.891
adjudicaciones. Se conservaron las capturas, ambos intentos ARM64 y el
[límite anterior de Windows](docs/SERCOP_ANNUAL_ENGINEERING_20261011.md).

Los siguientes seguimientos conservan sus cortes históricos:

[Ampliación declarativa comprobada](docs/OPTION_DECLARATIVE_FOLLOWUP_20261011.md):
270 obligaciones adicionales; trazabilidad **5.786/8.385 = 69,00 %**,
con 922 pendientes para el 80 %. Las otras ocho cifras conservan sus mediciones.

[Plan de las metas revisadas](docs/IMPLEMENTATION_PLAN_TARGETS_20261011.md):
umbrales de las rúbricas originales, validación y dependencias externas.
[Seguimiento de las metas revisadas](docs/TARGET_FOLLOWUP_RESULT_20261011.md):
1.072 obligaciones nuevas y las mediciones de ese corte,
con metas pendientes. El [plan inicial del 95 %](docs/IMPLEMENTATION_95_PLAN_20261011.md)
se conserva como histórico.
[Validación VM autorizada](docs/VM_TARGET_FOLLOWUP_20261011.md): 32 pruebas POSIX
y catálogo ARM64 3.10/3.12 normal/optimizado aprobados; madurez estricta 4/16 = 25 %.
La ampliación Linux pasa las 8.077 pruebas del núcleo y las 625 aplicables del
benchmark, con los dos casos de Windows separados.
[Revisión de aportes de tesis](docs/THESIS_CONTRIBUTIONS_REVIEW_20261011.md)
y [seguimiento de seguridad](docs/SECURITY_FOLLOWUP_20261011.md).
La meta permanece pendiente de evidencia; no sustituye las mediciones anteriores.
[Resultado de esta entrega](docs/IMPLEMENTATION_95_RESULT_20261011.md):
pruebas nuevas, identidad de los paquetes y pendientes que impiden acreditar la meta.
[Seguimiento técnico posterior](docs/FOLLOWUP_95_RESULT_20261011.md): corpus y
piloto público SERCOP, segunda revisión IA, obligaciones adicionales y validación
ARM64 3.10/3.12, conservando el Word.

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

[Trazabilidad incremental del wheel A13](docs/OPTION_TRACE_INCREMENTAL_20261011.json):
**4.444/8.385 = 53,00 %**, con 3.584 casos distintos entre el catálogo anterior
y los casos nuevos. Las regresiones y repeticiones no añaden cobertura.
Los recibos A11/A12 siguientes conservan sus artefactos históricos.

[Pruebas con trazabilidad por opción del núcleo A12](docs/OPTION_TRACEABILITY_RESULT_20261010.md):
4.296/8.383 obligaciones (51,25 %), con 3.443 casos sintéticos distintos.
Este porcentaje identifica el wheel A12; no se atribuye automáticamente a A13.
El recibo distingue validación de metadatos, rechazos esperados y opciones
pendientes; no acredita por sí solo sus efectos en motores nativos.

[Usabilidad técnica actual](docs/USABILITY_A13_REASSESSMENT_20261012.md):
11/12 criterios completos (91,67 %) reevaluados para A13 con la misma rúbrica U01–U12.
La evaluación con personas reales sigue pendiente; no es un porcentaje de
satisfacción ni modifica el índice separado de Universalidad A11.
Las evaluaciones A11/A12 permanecen ligadas a sus artefactos históricos.

[Arquitecto](packages/equiframe/docs/arquitecto.md) · [Científico](packages/equiframe/docs/cientifico.md) · [Inicio en español](packages/equiframe/docs/inicio.md) · [Choose an API](packages/equiframe/docs/choosing-api.md) · [Eight journeys](packages/equiframe/docs/journeys.md)

**Semantic comparison and reviewable evidence for tabular results in Python.**

Declare what your data must preserve, compare complete captured outputs, and
locate differences in values, types, keys, multiplicity and order. Use EquiFrame
inside an existing pandas, Polars, Arrow or CI workflow, or use its separate
native execution, verification and bounded migration APIs.

**Status: private Alpha pair: core 0.12.0a14 / benchmark 0.12.0a14.** Identify artifacts by commit and
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
`equiframe[arrow]==0.12.0a14`, a fresh environment outside the checkout,
normal pip dependency resolution and the separately supplied artifact hashes.
It includes Linux and PowerShell commands and a separate hash-locked trial.
This is private installation by name, not publication in PyPI or TestPyPI.
Choose `[duckdb]` for the architect's SQL exercise, `[arrow]` for the scientist's
preparation, or `[engines]` for native migration across all three engines. Add
`ml` only when using the optional detector fitting APIs. The
[role first-use guide](packages/equiframe/docs/first-use.md) needs no ML package.
The separate benchmark is `equiframe-benchmark[engines,ml,resources]==0.12.0a14`
and requires exactly core `0.12.0a14`. Add `[eda]` or `[eda-charts]` for the
[optional diagnostics](packages/equiframe/docs/eda.md). The prior a6 package artifacts and
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
