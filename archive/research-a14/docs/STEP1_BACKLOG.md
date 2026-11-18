# STEP1: backlog de aceptación del candidato

Fecha: 2026-10-04. Prioridades operativas para este candidato, con responsables
**por rol todavía por asignar**. Un defecto confirmado, un rechazo intencional
y una mejora de experiencia no tienen el mismo estado. Los resultados de
ejecución pertenecen a la [ficha y sus recibos](STEP1_CANDIDATE.md).

## P0: saneamiento y vínculo de evidencia

| ID / clase | Trabajo y disposición | Reproductor / prueba de aceptación | Rol | Estado de esta intervención |
|---|---|---|---|---|
| G01 — trazabilidad | Identificar fuente, commit y cuatro artefactos de los dos paquetes; repetir nueve controles por paquete | [check_candidate](../packages/equiframe/tools/check_candidate.py) y [release_manifest](../packages/equiframe/tools/release_manifest.py); incluir pruebas de fuente cambiada/recibo antiguo en [test_release_manifest](../packages/equiframe/tests/test_release_manifest.py) | Releases / QA | 9/9 etapas por paquete, fuente y cuatro artefactos identificados en ficha; SHA final en manifiesto externo tras commit |
| G02 — defecto CLI | Salida 0 solo con `equivalent` completo; `invalid_expected` completo sale 3 | [test_cli_complete_decision_table](../packages/equiframe/tests/test_comparison_decisions.py): ocho casos reales, incluyendo esperado NULL inválido y ambos lados inválidos; [test_cli_missing_capture_never_passes](../packages/equiframe/tests/test_comparison_decisions.py) | CLI / QA | Corregido; regresiones aprobadas en fuente y suite instalada del candidato |
| G03 — superficie no validada | Poner fuera de uso el auxiliar `equiframe.benchmark`, que no es el paquete científico `equiframe-benchmark`; ningún cálculo ni métrica ficticia | [auxiliar](../packages/equiframe/src/equiframe/benchmark.py), [entrada de ejemplo](../packages/equiframe/examples/benchmark_local.py) y [test_benchmark_quarantine](../packages/equiframe/tests/test_benchmark_quarantine.py): siete helpers fallan explícitamente, CLI sale 2 y no crea resultados; ayuda sale 0 | Núcleo / benchmark | Cuarentena y regresiones aprobadas en fuente e instalación; no habilita capacidad experimental |
| S01 — preservación de contrato | Mantener `different` solo con recorrido completo y los hechos parciales de `not_evaluable` | [test_partial_differences_do_not_become_complete_difference](../packages/equiframe/tests/test_comparison_decisions.py), [test_cancel_after_observed_difference_and_spill_cleanup](../packages/equiframe/tests/test_comparison.py) | Núcleo / QA | Aprobado en suites fuente/instalada; alcance y entorno en ficha |
| S02 — composición segura | No extrapolar equivalencia de fragmentos ni imponer diferencia global desde un fragmento terminado | [test_equivalent_partitions_do_not_prove_global_key_contract](../packages/equiframe/tests/test_comparison_decisions.py), [test_known_partition_difference_does_not_override_unfinished_scope](../packages/equiframe/tests/test_comparison_decisions.py) | Arquitectura / QA | Regresiones aprobadas sobre API existente; no se añade combinador |
| D01 — alcance inicial | Revisar [matriz](STEP1_CAPABILITIES.md), [RFC](STEP1_SEMANTIC_RFC.md) y [pilotos](STEP1_PILOTS.md), con tipos y exclusiones explícitos | Cada afirmación tiene fuente o pendiente; cada piloto tiene esperado enumerado, casos negativos, artefacto y criterio humano | Arquitectura / documentación | Definiciones listas para revisión; no aceptación humana inventada |

### Comandos de reproducción dirigida

Desde `packages/equiframe`, después de preparar el entorno bloqueado según
[RELEASE_CANDIDATE.md](RELEASE_CANDIDATE.md):

```bash
uv run --locked --all-extras pytest -q tests/test_comparison_decisions.py tests/test_pipeline.py::test_cli_compare_outcomes
uv run --locked --all-extras pytest -q tests/test_benchmark_quarantine.py
uv run --locked --all-extras pytest -q tests/test_comparison.py::test_partial_differences_retained_on_resource_limit tests/test_comparison.py::test_cancel_after_observed_difference_and_spill_cleanup
uv run --locked --all-extras pytest -q tests/test_comparison.py::test_maximum_matching_is_not_greedy_or_transitive tests/test_comparison.py::test_matching_against_independent_exhaustive_permutations
uv run --locked --all-extras pytest -q tests/test_release_manifest.py
```

Son comandos para reproducir propiedades, no recibos de que hayan pasado.
En G02 el esperado independiente es la tabla de códigos de la RFC, no el
resultado de la condición antigua de la CLI. En S02 dos particiones iguales con
`id=1` producen claves duplicadas al recombinar: el contrato global debe fallar
como `different` en peer o `not_evaluable / invalid_expected` en expected, ambos
con recorrido completo.
Estos filtros no sustituyen `pytest -q` de la suite completa ni instalación
externa, build o matriz remota.

## P1: decisiones o mejoras posteriores, sin implementarlas aquí

| ID / clase | Brecha acotada / aceptación necesaria | Reproductor actual o prueba nueva requerida | Rol / dependencia |
|---|---|---|---|
| G04 — experiencia | Entrada directa pandas/Polars mediante fachada delgada sobre captura y `compare`; contrato visible | Firma [ComparisonInput](../packages/equiframe/src/equiframe/comparison.py) no admite DataFrames. Prueba nueva de paridad fachada/núcleo para estados, políticas, índice y pérdida de captura; **pendiente**, sin API prometida | Experiencia / captura; depende de S01 y piloto P1 |
| G05 — experiencia | Resumen/aserción/reporte de comparación sin duplicar modelo; solo equivalencia completa aprueba | [ComparisonResult](../packages/equiframe/src/equiframe/comparison_types.py) no tiene esos métodos. Pruebas nuevas: misma decisión en todas las vistas, conteo desconocido distinto de cero, última fila discrepante, evidencia antes de aserción; **pendientes** | Experiencia / QA; reutilizar [reporting](../packages/equiframe/src/equiframe/reporting.py) |
| G06 — límite semántico | Ampliar solo el operador/tipo bloqueante de un piloto; no convertir rechazos deliberados en defectos | [SEMANTIC_SUPPORT.json](SEMANTIC_SUPPORT.json); ejecutar caso parametrizado, expected independiente y rechazo negativo por etapa/dirección. Timestamp IR, Decimal divide/multiply/round y dedup first/last no se anuncian | Migración / adaptador responsable; demanda de piloto |
| G07 — compatibilidad | Ejecutar el mismo candidato en la matriz comprometida; distinguir rango admitido de versión probada | [workflow manual](../.github/workflows/equiframe.yml) y [verificador de distribución](../packages/equiframe/tools/verify_distribution.py); registrar cada SO/arquitectura/Python/extras/versión, skip/xfail y hash de wheel | Releases / QA; autorización/entornos CI y G01 |
| G08 — privacidad de nuevos reportes | Diseñar redacción/retención y límites de divulgación antes de reporte por celdas | Existente [test_report_escape_and_exclusive_publication](../packages/equiframe/tests/test_pipeline.py); nuevas pruebas de redacción, rutas, secretos, tamaño y reproducción reducida **pendientes**. No atribuir al renderer actual una fuga no demostrada | Seguridad / experiencia; G05 |
| G09 — límites operacionales | Medir captura, comparación, persistencia y ejecución por separado, con cargas declaradas | [test_budget_exhaustion_never_equivalent](../packages/equiframe/tests/test_comparison.py), [test_materialized_resource_limits](../packages/equiframe/tests/test_execution.py). Nuevos benchmarks de skew/ancho/densidad de diferencias y RSS/I/O/disco **pendientes**, sin cifras de escala | Rendimiento / núcleo; candidato correcto |
| G10 — distribución/editorial | Corregir afirmaciones desfasadas; autores deciden licencia/nombre/acceso antes de publicar | [RELEASE_CANDIDATE](RELEASE_CANDIDATE.md#decisiones-externas-pendientes); revisar README/metadata contra APIs y recibos. No cambiar licencia o reservar nombre por inferencia | Documentación / releases / titulares |

## Pruebas de frontera que deben conservarse

1. Clave normalizada que colisiona, clave incompleta, `distinct` incumplido:
   [test_comparison.py](../packages/equiframe/tests/test_comparison.py)
2. Maximum matching frente a permutaciones exhaustivas y colisiones de hash:
   mismo archivo; no sustituir por greedy ni hashes como prueba de valores
3. Seis direcciones nativas sobre NULL/NaN, left join N:M y Decimal por moneda:
   [test_migration_semantic_directions.py](../packages/equiframe/tests/test_migration_semantic_directions.py)
4. Salidas iguales pero incorrectas respecto a esperado independiente:
   [test_equal_wrong_outputs_remain_agreed_but_failed_expected](../packages/equiframe/tests/test_verify.py)
5. Evidencia corrupta, fallo de publicación, cancelación y ausencia de salida:
   [test_pipeline.py](../packages/equiframe/tests/test_pipeline.py),
   [test_verify.py](../packages/equiframe/tests/test_verify.py)

Una prueba específica de **duplicado de clave que llega en el último lote** y
otra de **pareja aproximada tardía entre lotes** deben identificarse o añadirse
antes de anunciar esa cobertura puntual. Las pruebas generales de lotes y
matching no se renombran retrospectivamente como si aislaran esos casos.

## Registro mínimo de cierre de cada hallazgo

Conservar ID, clase, prioridad, contrato/input sintético, esperado independiente,
observado antes/después, fuente y artefacto exactos, comando/entorno, resultado,
límites restantes, rol responsable y revisión. Un item se cierra por evidencia
o por una disposición segura explícita; no por escribir «resuelto» ni por una
suite de otra revisión. Publicación, revisión humana y aceptación del DW/servicio
permanecen fuera del alcance de este saneamiento.
