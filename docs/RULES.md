# Reglas operativas R — EquiFrame 0.4.0

**R nombra el componente de reglas de EquiFrame, implementado en Python; no
se refiere al lenguaje de programación R.**

R evalúa **una ejecución capturada**: `ExecutionResult` con contrato 1.0,
configuración fijada, entradas y salida Arrow/Parquet. No reejecuta la
transformación, no llama a `compare` y no recibe otras salidas, resultados
esperados, etiquetas, mutaciones, particiones ni decisiones M/B/H. El
`RuleContext` entregado a implementaciones registradas contiene únicamente el
contrato y las tablas capturadas y verificadas. Se reutilizan conversiones
escalares del módulo `normalization`; R tiene evaluadores y pruebas propios.

```python
import equiframe as ef

result = ef.evaluate_rules(execution, work_dir=work_dir)
print(result.decision, result.complete, result.coverage)
for check in result.rules:
    if check.findings is not None:
        for finding in ef.iter_rule_findings(check.findings):
            print(finding.check_id, finding.code, finding.table, finding.position)
```

`execution` debe proceder de una captura con su `plan.contract` y referencias
locales accesibles. Se verifica estado `completed`, huella del contrato, conjunto
de entradas, nombre de salida, SHA-256/tamaño de cada archivo, conteos de filas,
columnas/tipos físicos, NULL/NaN e índice capturado. Cualquier fallo deja
`not_evaluable` con motivo. No se atribuye éxito a una ejecución fallida o una
captura parcial. El extra `arrow` basta para evaluar una captura ya existente;
Pandas, Polars y DuckDB no son dependencias de R. La importación base sigue ligera.

## Semántica cerrada de contrato 1.0

| Forma | Observación y condición |
|---|---|
| `SchemaCheck` | Orden/nombres y compatibilidad del tipo Arrow con el tipo lógico declarado; sobre valores tipados comprueba nulabilidad, NaN, rango, precisión, conjunto permitido y límites temporales. La política de ausencias declarada se aplica antes de evaluar los valores. No fuerza conversiones. Un tipo Arrow transportable pero no interpretable para el contrato es incumplimiento de esquema. |
| `KeyCheck` | Columnas normalizadas y ámbito declarado. Una clave incompleta contiene alguna ausencia lógica, incluido NaN solo si `as_null`; `reject` alerta y `allow` omite esa fila **solo del control de unicidad**. `unique=false` comprueba únicamente incompletitud. `global` y `table` cubren todas las filas de esta tabla; `columns` particiona el ámbito por esos valores. |
| `CardinalityCheck` | Número total de filas, no número de valores presentes ni distintos. Mínimo y máximo inclusivos. |
| `JoinCheck` | En las dos entradas capturadas, `one_to_one` exige unicidad de ambos lados; `one_to_many` de la izquierda; `many_to_one` de la derecha; `many_to_many` no exige unicidad. Claves con ausencia lógica nunca emparejan. `unmatched=reject` revisa **ambas direcciones**, incluido NULL; `allow` admite faltas de pareja. Esta regla no afirma que la proyección de salida sea un join correcto. |
| `OrderCheck` | Recorre la secuencia física de salida según `SignificantOrder.by`, direcciones, posición de NULL y política de empates. `ties=reject` alerta por claves de orden iguales; `preserve` admite el empate sin comprobar la estabilidad respecto de otra tabla. |
| `AggregateCheck` | Recalcula **solo** `function/group_by/measure/output_column` declarados desde la entrada y contrasta grupos de salida, ausentes, extras y duplicados. `count` sin `measure` cuenta filas; con `measure` cuenta valores presentes tras la política de ausencia, incluido NaN `distinct`. Grupos vacíos: con `group_by` no hay filas; sin `group_by`, `count=0` y `sum/min/max=NULL`. Enteros y decimales se suman exactamente; para `sum` float se exige tolerancia declarada y se contrasta contra suma racional exacta. No redondea dinero ni mezcla unidades/monedas: el contrato exige tipos/unidades compatibles y la agrupación seleccionada conserva las claves como moneda. |

Cada regla que lee valores exige tipos físicos compatibles para sus columnas;
un tipo incompatible queda `not_evaluable` salvo `SchemaCheck`, que lo registra
como incumplimiento observado.

Las precondiciones usan las mismas seis formas. Una precondición satisfecha habilita
las reglas que la citan; una incumplida permite declarar esas reglas
`not_applicable` con ID comprobable; si falta evidencia/implementación o se agota
un límite, la aplicabilidad queda `not_evaluable`. Una regla sin referencias se
evalúa igualmente. No se ejecutan expresiones arbitrarias de JSON.
Si una regla cita varias precondiciones y alguna es verificablemente falsa,
esa falsedad basta para omitirla; el motivo identifica la precondición falsa
aunque otra no haya podido evaluarse.

**Conversiones:** la captura final permite detectar tipos o valores inválidos y
las reconciliaciones declaradas. No permite contar intentos de conversión fallidos
ni reconstruir valores descartados antes de capturar la salida. El campo previsto
`conversiones_fallidas` de perfiles sigue pendiente. Una regla que necesite esa
estadística requiere evidencia adicional versionada de la transformación;
actualmente debe reportarse no evaluable, no inferirse de NULL/NaN final. El
catálogo 1.0 no declara tal regla.

## Estados, cobertura y prioridad

| Hallazgo / disponibilidad | Estado de regla | Decisión R |
|---|---|---|
| Al menos una regla violada; las demás evaluables | `violated` y otras | `alert`, completa |
| Al menos una regla violada; otra sin evaluar | `violated` y `not_evaluable` | `alert`, incompleta |
| Ninguna violada; todas evaluadas o justificadamente no aplicables; al menos una evaluada | `satisfied` / `not_applicable` | `no_alert`, completa |
| Ninguna violada; alguna sin evaluar | `not_evaluable` | `not_evaluable`, incompleta |
| Conjunto vacío o todas no aplicables | ninguna evaluada | `not_evaluable` |

`required` cuenta en `coverage.required_declared/required_checked`; cualquier
regla no evaluable, obligatoria u opcional, impide una afirmación completa de
`no_alert`. Una regla obligatoria verificablemente no aplicable se registra como
omitida y solo permite `no_alert` si hay otra regla efectivamente evaluada.
`severity` no silencia un incumplimiento: `info`, `warning` y `error` alertan.
`coverage.highest_alert_severity` indica la mayor prioridad observada. La
cobertura registra declaradas, ejecutadas, omitidas, no disponibles, alertas,
hallazgos y verificación de precondiciones. La decisión nunca oculta esos conteos.

Cada evaluación crea directorio propio, `rules.json` y JSONL completo por chequeo.
`max_examples` limita el resumen, no el análisis. `max_rows` limita filas
examinadas acumuladas, `max_artifact_bytes` limita bytes capturados/decodificados,
`max_work`, `max_evidence_bytes` y `timeout_seconds` limitan trabajo/evidencia/tiempo.
La cancelación es cooperativa. Al agotarse un límite, el chequeo queda incompleto;
una alerta ya comprobada se conserva. No hay cuota RSS ni interrupción dura de una
lectura Arrow indivisible. `read_rule_evaluation` comprueba la estructura y
coherencia del manifiesto; `iter_rule_findings` verifica SHA-256 y tamaño de **todo**
el JSONL antes de exponer registros. La lectura estructural no acredita por sí sola
los bytes de los artefactos referenciados. Lo mismo rige para `read_comparison` e
`iter_differences`.
La validación estructural rechaza también decisiones o marcas de completitud
contradictorias con los estados de los chequeos; la comprobación de contenido
de cada JSONL sigue siendo una operación separada.

## Catálogo y congelación técnica

[`catalog-1.0.json`](../packages/equiframe/examples/rules/catalog-1.0.json)
fija contrato/revisión/huella, reglas y revisiones, precondiciones,
implementaciones, opciones, cobertura declarada y limitaciones para las cinco
familias. `rule_set_fingerprint` incorpora el contrato completo, la configuración
y el código fuente de cada implementación registrada; los evaluadores integrados
incluyen `normalization.py` en esa identidad. Un consumidor puede verificar la
huella antes de evaluar. El catálogo se genera con `tools/generate_assets.py` y
`--check` detecta cambios sin actualizar el manifiesto.

[`rules_catalog.py`](../packages/equiframe/examples/rules_catalog.py) construye
capturas **sintéticas** de una fila y prueba las cinco entradas con el extra Arrow.
Estas entradas técnicas no son el benchmark revisado, la congelación experimental
final, el oráculo O ni la validación del DW. Las reglas se fijan antes de variantes
finales de prueba; no se seleccionan mediante etiquetas o resultados de prueba.
Un ejemplo de límite legítimo está en `test_schema_and_total_can_miss_entity_amount_swap`:
si el contrato controla solo esquema y suma global, intercambiar los dos montos
entre entidades mantiene esos controles mientras `compare` encuentra diferencias.
Un contrato con reconciliación por entidad sí podría detectarlas.
