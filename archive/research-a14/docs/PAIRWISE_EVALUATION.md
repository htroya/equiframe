# Evaluación descriptiva sobre soportes pareados

`equiframe_benchmark.pairwise.evaluate_pairwise` añade una inspección explícita
de los soportes de cada contraste. Recibe un `EvaluationReport` existente,
valida sus registros y resultados derivados y devuelve un `PairwiseReport`
tipado. No ejecuta ETL, entrena, calibra ni puntúa detectores.

```python
from equiframe_benchmark.pairwise import evaluate_pairwise

paired = evaluate_pairwise(evaluation)
global_result = paired.strata[0]
rh = next(p for p in global_result.pairs if (p.left_method, p.right_method) == ("R", "H"))
print(rh.support_case_ids, rh.left_metrics, rh.right_metrics)
print(rh.right_only.additional_true_positive_rate)
print(rh.right_only.additional_false_positive_rate)
```

`evaluation` es un informe previamente obtenido mediante `evaluate_records` o
leído desde JSON con `load_document(EvaluationReport, ...)`.

## Soportes y denominadores

Cada estrato global, familia, migración y familia–migración contiene las seis
parejas R–M, R–B, R–H, M–B, M–H y B–H. Se preservan también los estratos
declarados sin casos. Cada pareja usa **los mismos casos** para ambos métodos:
O confirmado y decisiones completas de los dos. No exige que un tercer método
esté disponible. La intersección histórica R/M/B/H figura como `common_case_ids`.

| Campo | Significado |
|---|---|
| `support_case_ids`, `group_ids` | Ejecuciones elegibles únicas y sus grupos de procedencia |
| `divergent_cases`, `normal_cases` | Denominadores de clase dentro del soporte de esa pareja |
| `coverage_confirmed` | Casos pareados / O confirmados del estrato |
| `coverage_scheduled` | Casos pareados / total programado del estrato |
| `left_metrics`, `right_metrics` | TP/FP/FN/TN, precisión, sensibilidad, F1 y tasa de falsos positivos sobre el mismo soporte |
| `left_only`, `right_only` | Alertas de un método cuando el otro tiene `no_alert`, separadas por clase |
| `exclusions` | Todos los motivos aplicables por caso: O no confirmado, izquierda incompleta y derecha incompleta |
| `left_partial_alert_case_ids`, `right_partial_alert_case_ids` | Alertas conservadas que no acreditan una decisión completa |

Para una dirección, la tasa adicional verdadera divide sus alertas exclusivas
divergentes por todos los divergentes pareados; la falsa divide sus alertas
exclusivas normales por todos los normales pareados. En R–H, `right_only` es
H respecto de R. Las dos direcciones se informan también para las otras parejas;
no se interpreta una diferencia como superioridad o significancia estadística.

Un denominador cero mantiene `value=None` y un motivo explícito. O pendiente,
en desacuerdo o no evaluable nunca se convierte en un caso normal. H parcial
con alerta conserva la alerta en el inventario y queda fuera de cualquier
soporte que requiera H completo. Un fallo posterior puede conservar R disponible;
se usa la disponibilidad declarada y validada de cada componente, sin descartar
o aprobar automáticamente toda la ejecución.

## Vinculación y compatibilidad científica

El reporte contiene el `EvaluationReport` original completo, su digest, su
`protocol_sha256` y un `analysis_policy_sha256` separado para esta derivación.
La lectura reconstruye los resultados y rechaza conteos, casos, protocolos,
políticas o métricas que no concuerden, aun con hashes de archivo recalculados.
Los hashes no autentican revisores ni prueban independencia científica.

Esta extensión tiene `analysis_role="supplementary_descriptive"` y
`scientific=False`, incluso si el informe de origen era final. **No modifica**
el protocolo congelado, sus seis CSV históricos, AP, bootstrap, métodos ni
decisiones de detección. No produce intervalos nuevos o pruebas de hipótesis.

La tesis vigente propone soportes por contraste y una intersección común
adicional. Estos diagnósticos permiten inspeccionar esa distinción sin
reinterpretar estudios ya congelados. Usarlos como análisis científico principal
requiere revisar y congelar previamente un nuevo protocolo, sus estimandos,
incertidumbre, decisiones y criterios de aceptación. No basta con añadir este
JSON después de observar los resultados de prueba.

## Exportación explícita y ejemplo ejecutable

La API no escribe archivos. El consumidor puede guardar JSON de forma explícita
con los validadores y publicación exclusiva existentes:

```python
from pathlib import Path
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.pairwise import PairwiseReport

save_document(paired, Path("paired.json"))
checked = load_document(PairwiseReport, Path("paired.json"))
```

La carpeta destino debe existir y el archivo debe ser nuevo; no se sobrescriben
evidencias anteriores. Desde un entorno con `equiframe-benchmark` instalado,
el ejemplo de este repositorio lee un `evaluation.json` existente:

```powershell
& $py -I ./packages/equiframe-benchmark/examples/pairwise_evaluation.py --evaluation ../resultados/evaluation.json --output ../resultados/paired.json
```

Los datos y resultados privados permanecen fuera de Git. Este JSON suplementario
no se incorpora automáticamente al inventario de un estudio/bundle existente;
se conserva aparte con su vinculación explícita. La API no crea un séptimo CSV
ni cambia los lectores de tablas anteriores.
