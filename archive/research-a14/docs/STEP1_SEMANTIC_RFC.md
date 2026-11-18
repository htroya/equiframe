# STEP1: contrato de decisión semántica

RFC operativa 1, 2026-10-04. **Preserva el comportamiento del comparador 0.11.1**;
no introduce campos, APIs ni nuevas garantías de ejecución. La regla de
composición de particiones es una obligación de diseño y prueba para futuros
consumidores, no un combinador público implementado.

Fuentes normativas actuales: [COMPARISON.md](COMPARISON.md),
[compare](../packages/equiframe/src/equiframe/comparison.py),
[ComparisonResult y validadores](../packages/equiframe/src/equiframe/comparison_types.py).
Los resultados de pruebas del candidato se registran en la
[ficha](STEP1_CANDIDATE.md); aquí se especifican decisiones y oráculos.

## 1. Qué afirma el resultado

El juicio pertenece a dos capturas, un contrato y un alcance identificados.
No acredita equivalencia universal entre programas ni corrección de negocio
del esperado. `reference="expected"` coloca el esperado a la **derecha**.
`ExecutionResult.state="completed"` no es un veredicto de comparación.

Mantener separados:

- Fidelidad de captura y distinciones no recuperables del origen
- Relación exacta o tolerante declarada, sin ajustes a posteriori
- Alcance completo o muestra expresamente acotada; una muestra no certifica la población
- Terminación de la evaluación (`complete`, `counts.final`)
- Persistencia e integridad de los artefactos y datos que el consumidor divulga

No se añaden ejes nuevos al formato 1.0 por documentarlos. Una política futura de
redacción/minimización necesita diseño y pruebas propios; el almacenamiento
actual conserva snapshots y diferencias dentro de sus presupuestos.

## 2. Tabla de decisión del resultado individual

| Precondiciones y resultado observado | `state` | `complete` / `counts.final` | Gate estricto |
|---|---|---|---|
| Recorrido total, ambas capturas evaluables, restricciones satisfechas, ninguna diferencia | `equivalent` | `True` / `True` | Aceptar |
| Recorrido total y diferencias de valores, esquema o restricciones; esperado válido si se pidió | `different` | `True` / `True` | Rechazar por diferencia |
| Recorrido total; referencia derecha viola contrato en `expected` | `not_evaluable`, diagnóstico `invalid_expected` | `True` / `True` | Rechazar: falta un esperado válido |
| Candidato izquierdo viola contrato, esperado derecho válido, recorrido total | `different` | `True` / `True` | Rechazar por incumplimiento |
| En `peer`, uno o ambos lados violan contrato y termina el recorrido | `different` | `True` / `True` | Rechazar por incumplimiento |
| Cancelación, timeout, presupuesto, capacidad, dependencia o fallo durante evaluación, con o sin diferencias previas | `not_evaluable`, causa específica | `False` / `False` | Rechazar; conservar hechos observados |
| Configuración inválida o fallo al crear/publicar evidencia que impide devolver resultado | Excepción, sin resultado final garantizado | No atribuir valores ficticios | Rechazar; conservar error del proceso |

`different` exige recorrido completo. Un contraejemplo observado antes de una
interrupción no cambia el estado global a `different`: permanece visible en
diagnósticos/diferencias del `not_evaluable`. Un fallo de adaptador, por sí solo,
no prueba diferencia entre datos.

`difference_records` cuenta registros de diagnóstico, no filas distintas. En una
ejecución parcial los contadores son observados y no finales: no reportarlos como
totales ni sumar celdas y violaciones para inventar filas modificadas. Un límite
de ejemplos solo limita la vista. [Semántica de conteos](COMPARISON.md#estados-y-evidencia).

### Contrato del gate CLI

La condición de aceptación es `state == "equivalent" and complete`.
El saneamiento de STEP1 exige la siguiente traducción y sus pruebas:

| Resultado de `compare` | Salida requerida |
|---|---:|
| `equivalent`, completo | 0 |
| `different`, completo | 1 |
| Cualquier `not_evaluable`, incluido `invalid_expected` completo | 3 |
| Argumento/documento inválido o excepción operacional | No cero; conservar la clasificación 2/3 vigente |

Ver [CLI](../packages/equiframe/src/equiframe/cli.py),
[tabla ejecutable de decisiones](../packages/equiframe/tests/test_comparison_decisions.py)
y [regresiones de pipeline/CLI](../packages/equiframe/tests/test_pipeline.py).
El recibo del candidato confirma cuándo esta condición ha sido ejecutada.
El lector de evidencia y el comando de verificación de integridad tienen otra
finalidad: su éxito no aprueba el resultado tabular contenido.

## 3. Combinación conservadora de alcances parciales

**No combinar únicamente estados o contar votos.** Antes de reducir resultados:

1. Fijar el universo solicitado y demostrar particiones disjuntas, exhaustivas,
   sin omisiones/repeticiones, con contrato, políticas, referencia y snapshots compatibles
2. Cerrar obligaciones globales: unicidad de claves crudas/normalizadas,
   multiplicidad, orden entre fronteras y emparejamientos que atraviesen lotes
3. Conservar la procedencia de cada observación, sin duplicar evidencia ni
   reutilizaciones como si fueran muestras independientes
4. Comprobar la validez global del esperado en modo `expected`; dos fragmentos
   válidos por separado pueden formar un esperado inválido por clave duplicada

Si esas condiciones no están demostradas, solo pueden comunicarse los
resultados locales. Un juicio del universo mayor es `not_evaluable` con alcance
no cerrado; no se fabrican campos de un `ComparisonResult` que la API no produjo.
La vía actual para comparar el conjunto sigue siendo una sola llamada a
`compare` con todas las capturas requeridas.

Una vez satisfechas las precondiciones, esta tabla es la regla de decisión
esperada para **dos subalcances completos**; se extiende inductivamente:

| Izquierda / derecha | `equivalent` | `different` | `not_evaluable` |
|---|---|---|---|
| `equivalent` | `equivalent` | `different` | `not_evaluable` |
| `different` | `different` | `different` | `not_evaluable` |
| `not_evaluable` | `not_evaluable` | `not_evaluable` | `not_evaluable` |

Reglas adicionales obligatorias:

- Cualquier fragmento requerido incompleto, ausente o fallido implica evaluación
  global incompleta y `not_evaluable`, aunque otro tenga diferencias completas
- Con todos los recorridos completos, `invalid_expected` impide el juicio global;
  `complete=True` describe recorrido, no validez del esperado
- Un incumplimiento global descubierto al cerrar fronteras se trata según la
  tabla individual: `invalid_expected` en la derecha esperada; `different` en
  candidato/peer únicamente después del recorrido completo
- No emparejar bolsa aproximada por lote de forma irreversible. Una pareja puede
  llegar en el último lote; una clave duplicada tardía invalida alineación provisional
- Una evidencia truncada o corrupta no autoriza éxito de un consumidor que exige
  evidencia íntegra, aunque el resultado declarado diga `equivalent`

La composición anterior es distinta de `combine_decisions` de R OR M: ese
operador conserva una alerta parcial y tiene un contrato de disponibilidad
diferente. [Estados públicos](API_CONTRACTS.md#4-estados-públicos-separados).

## 4. Decisiones que no deben relajarse

| Área | Decisión preservada | Fuente / prueba de referencia |
|---|---|---|
| Casts y esquema | Tipo lógico exacto por defecto; `lossless` explícito, sin cruces arbitrarios de familias ni pérdida | [Políticas](COMPARISON.md#esquema-y-normalización), `test_physical_mapping_is_lossless_and_explicit` |
| Clave | Alineación solo tras unicidad/completitud comprobadas en ambos lados; fallback autorizado a bolsa si no sirve | [Claves](COMPARISON.md#claves-multiplicidad-y-orden), `test_compound_scoped_and_incomplete_keys` |
| Secuencia | Orden observado significativo; no ordenar para reparar una diferencia | Mismo documento, `test_sequence_ties_and_invalid_shared_order` |
| Bolsa | Preservar ocurrencias; `distinct` exige no duplicados, no deduplica | Mismo documento, `test_normalization_cannot_hide_key_collision_or_distinct_violation` |
| Tolerancia | Fórmula simétrica inclusiva `abs(a-b) <= max(abs_tol, rel_tol*max(abs(a),abs(b)))`; no transitiva ni clave aproximada | [Tiempo/aproximaciones](COMPARISON.md#tiempo-y-aproximaciones), `test_tolerance_boundary_zero_infinity_nan` |
| Matching | Máximo bipartito ya implementado, sin greedy ni equivalencia transitiva | [Comparador](../packages/equiframe/src/equiframe/comparison.py), `test_maximum_matching_is_not_greedy_or_transitive` |
| Evidencia | Resumen no recorta evaluación; conservar hechos previos al fallo; hash no autentica al productor | [Evidencia](COMPARISON.md#estados-y-evidencia), `test_partial_differences_retained_on_resource_limit` |
| Recursos | Presupuestos cooperativos; no degradar a muestra/hash para terminar ni prometer RSS duro | [Límites](COMPARISON.md#lotes-disco-y-límites), `test_budget_exhaustion_never_equivalent` |
| API y ciclo de vida | Comparar capturas no reejecuta SQL/callbacks; no DataFrames directos ni ejecución al renderizar | [API](API_CONTRACTS.md#9-comparación-disponible-en-030), [adaptadores](../packages/equiframe/src/equiframe/adapters.py) |

Los nodos abreviados de esta tabla pertenecen a
[test_comparison.py](../packages/equiframe/tests/test_comparison.py).
Se conserva Verify y la migración nativa existente con sus seis direcciones;
acuerdo entre motores, esperado e independencia humana siguen separados.

## 5. Casos mínimos que deben cerrar la decisión

- Igualdad completa, diferencia completa, candidato inválido y esperado inválido completo
- Diferencia observada seguida de cancelación o presupuesto agotado
- Ninguna diferencia observada seguida de interrupción: tampoco aprueba
- Bolsa aproximada `A=[0,1]`, `B=[0.5,-0.5]`, tolerancia absoluta 0.5: matching
  máximo completo debe aprobar; el emparejamiento voraz puede fallar
- Duplicado de clave en último lote, pareja de bolsa tardía y permutación de lotes:
  cerrar restricciones globales antes de decidir
- Recibo/manifiesto corrupto o ausente: consumidor estricto falla

La [tabla ejecutable](../packages/equiframe/tests/test_comparison_decisions.py)
añade `test_cli_complete_decision_table`, captura ausente, configuración inválida,
fallo de publicación y presupuesto con diferencias observadas. También contiene
`test_equivalent_partitions_do_not_prove_global_key_contract` (peer y expected)
y `test_known_partition_difference_does_not_override_unfinished_scope`.
Prueban la decisión con `compare` existente; no implementan un combinador.

El [backlog](STEP1_BACKLOG.md) separa estos casos de las pruebas específicas aún
por identificar/añadir de duplicado en último lote y pareja aproximada tardía.
La ejecución se atribuye únicamente al recibo del candidato correspondiente.
