# Protocolo principal pareado V2

Esta versión implementa el recorrido de ingeniería de T19: congelación,
captura de casos retenidos, evaluación principal por contraste, incertidumbre
por grupos, tablas y reproducción. No cambia los documentos, algoritmos,
lectores ni fingerprints del protocolo V1. Los reportes suplementarios
`evaluate_pairwise` de V1 conservan su significado anterior.

Es desarrollo solicitado el 26 de octubre de 2026. Su validación acotada,
autorizada posteriormente, supera 24 casos nuevos y tres regresiones V1 pequeñas.
Incluye dos recorridos de un caso nativo DuckDB ficticio retenido: uno mediante
API y otro mediante los ocho comandos V2. Comprueba lectura del estudio,
reproducción portable y salidas/errores CLI; no entrena detectores ni acredita
resultados científicos o aprobación académica. Ruff, formato y mypy estricto
se completan para los archivos de la integración. Los 13 esquemas V2 generados
coinciden con los modelos actuales. Datos y decisiones de los tests son fixtures.

## Alcance y soporte

`EvaluationConfigV2` fija las familias principales `nulls_types`, `joins` y
`aggregations`, y las parejas `pandas-polars`, `pandas-duckdb` y `polars-duckdb`.
Hay nueve estratos familia/pareja, además de los resúmenes global, por familia
y por pareja. Los estratos sin observaciones se muestran con denominadores
cero y motivos explícitos; no se descartan del informe.

Los contrastes entre R (reglas), M (Isolation Forest), B (MAD) y H (reglas OR M)
se declaran explícitamente en `contrasts`, sin repetir una pareja en sentido
inverso. Cada contraste utiliza sólo casos con O confirmado y decisiones
completas de **los dos métodos comparados**. La disponibilidad de B no elimina
un caso del contraste H–R, por ejemplo. El informe conserva exclusiones,
alertas parciales, grupos y cobertura respecto de casos confirmados y de
casos programados. Una indisponibilidad no equivale a ausencia de alerta.

La intersección completa R/M/B/H se mantiene en `stratum.common`, con el rol
explícito `additional_common_R_M_B_H`; no sustituye el soporte principal.
Las cinco familias genéricas de la biblioteca siguen disponibles mediante
las interfaces existentes, pero no se agregan al protocolo principal V2.

## API de configuración

```python
import equiframe_benchmark as eb

config = eb.EvaluationConfigV2(
    mode="pilot",
    freeze_sha256=None,
    bootstrap=bootstrap_plan,  # BootstrapPlan explícito, justificado antes de prueba.
    contrasts=(
        eb.ContrastSpecV2(left="H", right="R"),
        eb.ContrastSpecV2(left="M", right="R"),
        eb.ContrastSpecV2(left="M", right="B"),
    ),
)
protocol_sha256 = eb.evaluation_protocol_sha256_v2(config)
```

La lista mostrada ilustra la sintaxis; no es una selección científica ya
aprobada. Puede declararse cualquier subconjunto no vacío de las seis parejas
distintas de métodos. Las hipótesis, contrastes, confianza, soporte mínimo e
independencia deben revisarse y fijarse antes del estudio.

`FreezeDefinitionV2` conserva los campos de catálogo, splits, casos, modelos,
fuentes, entorno, decisiones y costos, pero requiere exactamente los tres
modelos de familia principales. Reutiliza los tipos `FrozenFamilyModel`,
`TestCaseDefinition`, `FrozenInput` y los registros de selección existentes.
La evaluación precongelación debe seguir siendo `mode="pilot"` y no llevar
un hash circular de freeze.

La nueva revisión explícita es obligatoria:

```python
review = eb.ProtocolReviewV2(
    status="pending",
    protocol_sha256=None,
    reviewer=None,
    rationale="Protocolo nuevo pendiente de revisión antes del estudio final.",
)
```

Un piloto puede conservar esa revisión pendiente. Un freeze final exige una
revisión declarada `approved` con el SHA exacto del protocolo y el revisor,
además de todas las barreras científicas originales. Declarar metadatos no
autentica a un revisor. El código no genera una aprobación ni rellena etiquetas,
cohorte, licencias, entrenamiento o decisiones pendientes.

También bloquean el freeze final los nueve estratos sin casos programados.
Esta condición no fija cuotas de potencia, grupos o perfiles: la suficiencia
científica sigue dependiendo del protocolo y de los datos reales.

## Ejecución y regeneración

```python
manifest = eb.create_freeze_v2(definition, rule_registry=rules)
study = eb.run_study_v2(manifest, registry=transformations, rule_registry=rules)
report = eb.evaluate_records_v2(study.evaluation.records, study.evaluation.config)
tables = eb.write_tables_v2(report, output_directory)
```

`run_study_v2` consume transformaciones registradas explícitamente y ejecuta
cada caso nativo retenido una vez. No ajusta ni selecciona parámetros. Conserva
fallos y cancelaciones, reaudita fuentes antes/después y sólo reutiliza una
etiqueta cuando la salida nativa vuelve a coincidir con el candidato revisado.
Un cambio de fuentes impide mantener un reporte final y conserva la captura
como piloto. Los splits usan los mismos componentes transitivos y no permiten
separar dependencias entre entrenamiento, calibración y prueba.

`read_freeze_v2`, `read_study_v2` y `read_tables_v2` verifican documentos e
integridad de las fuentes capturadas. Su recorrido y el rechazo de alteraciones
de tablas se incluyen en los controles acotados de ingeniería citados arriba.

Comandos equivalentes, separados de V1:

```text
equiframe-benchmark freeze-v2 definition-v2.json --output freeze-v2.json
equiframe-benchmark verify-freeze-v2 freeze-v2.json
equiframe-benchmark run-study-v2 freeze-v2.json --registry proyecto:registry --output studies
equiframe-benchmark verify-study-v2 studies/study_v2_ID
equiframe-benchmark evaluate-v2 studies/study_v2_ID --output evaluation-v2.json
equiframe-benchmark tables-v2 studies/study_v2_ID --output tables-v2
equiframe-benchmark bundle-study-v2 studies/study_v2_ID --output portable-v2
equiframe-benchmark reproduce-study-v2 portable-v2
```

Estas instrucciones no relanzan campañas automáticamente. Los comandos de
ejecución sólo actúan cuando el usuario los invoca.

## Métricas e incertidumbre

Cada contraste incluye precisión, recall, F1 y tasa de falsos positivos para
ambos métodos en el mismo soporte. Registra sus diferencias con signo
izquierda menos derecha, y detecciones adicionales verdaderas/falsas en ambos
sentidos. AP se calcula para M/B sólo con scores comparables del mismo modelo
y familia y con ambas clases; de otro modo queda indefinida con su motivo.

El bootstrap remuestrea **grupos completos** con reemplazo, usando la misma
selección de grupos para ambos métodos en cada réplica. Recalcula las métricas
y las diferencias a partir de esas mismas observaciones, preservando el
emparejamiento. Semilla, repeticiones, confianza, soporte e independencia son
parte de la configuración fijada. No se eliminan réplicas indefinidas para
producir un intervalo artificial: el resultado conserva sus conteos y motivo.
Sin independencia justificada o grupos suficientes no se calcula un intervalo.

Los intervalos son de agregados de ejecuciones; no convierten repeticiones o
reutilizaciones entre parejas en nuevas unidades independientes. No se añaden
tests de hipótesis, correcciones por multiplicidad ni garantías de potencia
sin una decisión metodológica posterior.

## Tablas y reproducción

V2 produce siete tablas, todas ligadas al documento de evaluación:

| Archivo | Contenido |
|---|---|
| `coverage.csv` | Denominadores, grupos, clases, exclusiones y alertas parciales por contraste. |
| `metrics.csv` | Métricas de ambos métodos, diferencias y tasas incrementales. |
| `bootstrap.csv` | Intervalos pareados, rangos y réplicas definidas/indefinidas. |
| `exclusions.csv` | Caso, estado O y todos los motivos de exclusión aplicables. |
| `common_metrics.csv` | Intersección R/M/B/H adicional con rol explícito. |
| `common_bootstrap.csv` | Incertidumbre de esa intersección adicional. |
| `cases.csv` | Todos los casos, disponibilidad de componentes y procedencia. |

`bundle_study_v2` conserva los bytes originales y los insumos fijados.
`regenerate_study_record_v2` y `reproduce_study_bundle_v2` regeneran las
métricas e intervalos y cada CSV desde las decisiones capturadas, sin repetir
ETL ni reescribir hashes de procedencia. La reproducción técnica no afirma
que otra persona haya repetido independientemente el experimento.

Los modelos V2 son documentos estrictos con `schema_version="2.0"`. Se pueden
exportar sus esquemas mediante `model_json_schema()` o la herramienta
`tools/generate_assets_v2.py --output NUEVA_CARPETA`; los 13 esquemas generados
se conservan en `schemas/protocol-v2`. La herramienta exige un destino nuevo.
Los esquemas, reportes y tablas V1 permanecen separados.
