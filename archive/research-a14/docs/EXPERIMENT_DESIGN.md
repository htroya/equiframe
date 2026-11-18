# Diseño experimental implementable

Requisitos derivados de las secciones 3.1, 3.3, 3.6, 3.7, 3.8 y 3.9 del borrador. Las cantidades y parámetros propuestos se distinguen de decisiones congeladas. No hay resultados todavía.

## 1. Comparaciones y unidades

Migraciones principales: Pandas a Polars y Pandas a DuckDB. Polars a DuckDB se reporta aparte. Pandas es referencia de desarrollo; no determina corrección.

- Escenario base: transformación, contrato y mecanismo de variación de entrada.
- Ejecución: escenario, variante, motor y entrada concretos.
- Grupo de procedencia: componente conexo de casos que comparten plantilla, transformación, caso base, fragmento o OCID, incluso mediante vínculos transitivos.
- Snapshot: corpus identificado por manifiesto inmutable. Filas, semillas, repeticiones y variantes no se convierten artificialmente en observaciones independientes.

Las cinco familias son `nulls_types`, `joins`, `duplicates_order`, `aggregations` y `dates`. Se conserva un catálogo versionado con entrada, resultado esperado, contrato, transformación, revisión, regla R y procedencia por escenario.

## 2. Separación R, M, B, H y O

| Componente | Evidencia permitida | Función |
|---|---|---|
| R | Contrato + entrada/salida de una ejecución | Comprobaciones deterministas limitadas y fijadas previamente |
| M | Perfil de esa ejecución y bundle entrenado | Puntuación Isolation Forest y umbral |
| B | Mismas features/preprocesamiento y su bundle | Referencia basada en mediana/MAD |
| H | Decisiones/disponibilidad de R y M | OR con estado no evaluable |
| O | Resultado esperado revisado + comparación completa + controles del dominio | Etiqueta independiente |

Ninguna etiqueta se deriva de una alerta. Ninguna mutación se considera divergente sin efecto observado. Una salida puede conservar totales y aun intercambiar montos entre entidades; esos casos deben estar en el catálogo. También hay controles correctos difíciles con orden/representación/tamaño legítimamente distintos.

Dos revisores evalúan cada caso sin consultar alertas, clase de mutación, etiqueta propuesta ni decisión del otro. El autor de una variante no es revisor independiente de ella. Registrar decisiones A/B, razones, fechas, versiones, desacuerdo, resolución y etiqueta final. Pendientes no entran a ajuste/calibración/métricas de exactitud. El conflicto de autoría en arbitraje con tres integrantes se resuelve antes de declarar ese procedimiento cerrado.

## 3. Comparador y referencia esperada

O compara `N(salida_candidata)` con `N(salida_esperada)`; N es la normalización permitida por el contrato. Los esperados pequeños se calculan manualmente o mediante una implementación independiente revisada. Una comparación entre dos motores sirve para localizar discrepancias, no demuestra que alguno sea correcto ni que ambos no compartan el mismo error.

R se fija antes de generar variantes de prueba. La lógica del comparador, los esperados y R se prueban por separado para evitar errores compartidos. O no se evalúa contra sus propias etiquetas como si fuera otro detector de exactitud; se mide su costo y sus limitaciones.

## 4. Perfiles y preprocesamiento

Cada perfil usa únicamente entrada, salida y métricas de una implementación. Se registran fórmulas, columnas, etapas y denominadores. Propuestas del borrador:

| Feature | Cálculo / comportamiento |
|---|---|
| `log_filas` | `ln(1 + n_salida)`; salida vacía da 0 |
| `razon_salida_entrada` | `n_salida / n_entrada`; sin denominador, indefinida |
| `tasa_nulos` | Ausencia lógica por columna / filas de salida; no incluye NaN, vacío o cero |
| `tasa_nan` | NaN por columna numérica / filas de salida |
| `prop_duplicados` | `(n_clave_completa - claves_distintas_completas) / n_clave_completa` |
| `cardinalidad_rel` | Valores distintos informados / valores informados; excluye ausentes/NaN |
| `expansion_union` | Filas tras unión / filas izquierdas; no duplicar una feature idéntica |
| `claves_sin_pareja` | Filas izquierdas sin correspondencia / filas izquierdas, con semántica de claves nulas del contrato |
| `conversiones_fallidas` | Conversiones fallidas de valores presentes / intentos; vacío cuenta presente |
| `fechas_invalidas` | Fechas presentes inválidas / presentes examinadas; fuera de cohorte no implica inválida |

Aplicabilidad por familia según tabla 13; no mezclar denominadores de columnas. Ausencia de medida y cero válido son diferentes. Se conserva motivo e indicador. M y B usan exactamente las mismas columnas, orden, indicadores e imputación.

Imputación: mediana calculada únicamente sobre ajuste normal de la familia. Si una feature no tiene valores válidos, se retira de ambos con evidencia o se declara el componente no estimable. Si no hay soporte o variación suficiente, no se inventan perfiles para entrenar. IDs, etiquetas, mutación, partición, motor y variables que revelen artificialmente la clasificación no forman parte del vector. Metadatos necesarios se mantienen fuera de la matriz.

## 5. Ajuste, calibración y decisión

M: Isolation Forest por familia con soporte suficiente. Propuesta inicial revisable: 200 árboles y submuestras de hasta 256 perfiles. Semilla y versiones registradas. Score `s(x) = -score_samples(x)`; mayor significa más anómalo. `contamination` no sustituye la calibración externa. Ver [API oficial de IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).

Calibración normal independiente: ordenar n scores, usar posición `ceil((1-alpha)*n)` contando desde 1, sin interpolación. Alertar si `score > threshold`, no con igualdad. Alpha debe estar en `(0,1)` y tener justificación antes de congelar. El 5% de la tesis es propuesta, no garantía ni default silencioso para evaluación final. Registrar tamaño de calibración, número de grupos y precisión justificable. No combinar scores de modelos por familia en un umbral global.

B: mediana y MAD sin factor de escala calculados en ajuste. Por variable, `abs(x - mediana) / MAD`; score máximo de contribuciones aplicables. Si MAD=0, contribución 0 al coincidir con mediana e infinito en otro caso. Umbral por mismo cuantil/inequidad estricta. Umbral infinito o ausencia de variables utilizables implica `not_estimable`. No devolver un detector que nunca alerta como si fuera válido.

H: la tabla completa de [estados](API_CONTRACTS.md) es normativa. Una alerta de R o M se conserva aunque el otro no pueda decidir; ausencia de alerta exige ambos evaluables. B se reporta separado, no se añade a H.

Persistir modelos con metadatos de compatibilidad, hashes, variables, preprocesamiento y referencias de entrenamiento/calibración. No cargar pickle/joblib no confiables. Elegir formato soportado con verificación de tipos y carga explícita; probar predicciones idénticas tras guardar/restaurar en la versión bloqueada. Un hash comprueba integridad, no confianza en el autor.

## 6. Grupos, particiones y congelación

La meta del borrador es 60 escenarios (12 por familia) y al menos 300 perfiles; propuesta 30/10/20 de ajuste/calibración/prueba. Son metas, no hechos ni cálculo de potencia. Primero construir componentes conexos de procedencia, después particionar grupos completos con semilla. Verificar intersecciones vacías de toda dependencia declarada, no solo IDs de escenario. No romper un grupo para cumplir cantidades.

El piloto puede ampliar casos independientes, variar features y revisar parámetros. Registrar cada cambio. Las repeticiones o semillas adicionales no aumentan los grupos. Si las cantidades o soporte no alcanzan, reportar evaluación exploratoria y componentes no estimables.

El cierre de evaluación exige `FreezeManifest` con:

- Corpus/cohorte y hashes, políticas temporales/decimales y tratamiento de incompletas resueltos.
- Contratos, R y features versionados; registro de cambios anterior a las variantes finales.
- Catálogo, esperados, revisiones y etiquetas confirmadas o pendientes explícitas.
- Grupos y splits comprobados; prueba no usada para seleccionar reglas, modelo o umbral.
- Bundles, alpha justificado, parámetros, semillas y procedimiento de métricas/costos.
- Entorno, dependencias exactas y recursos medibles.

La CLI debe bloquear evaluación final si falta un requisito obligatorio. Puede ejecutar piloto con estado explícito. Cambios después de abrir prueba generan nueva versión y se reportan como análisis adicional.

## 7. Métricas y cobertura

Conjunto principal: intersección de casos etiquetados y evaluables por R/M/B/H. Mostrar además soporte propio por método, sin comparar denominadores distintos como si fueran iguales. Registrar todos los casos programados, pendientes y no evaluables.

TP/FP/TN/FN, precisión, sensibilidad, F1 y tasa de falsas alarmas; denominador cero da valor no definido con motivo. Average precision para scores M/B solo con soporte de clases adecuado; R/H son puntos de operación. Desagregar familia y migración, conservando grupos.

H1: TP adicionales de H respecto de R; H2: FP adicionales y tasa total de H respecto a tolerancia fijada. La tesis propone intervalos del 95% mediante 2.000 remuestras de grupos completos y cuantiles por rango sin interpolación. Guardar semilla, número de remuestras válidas/indefinidas, estimando por ejecución y tamaño de grupos. No reemplazar métricas indefinidas por cero ni ignorar su frecuencia. Pocos grupos o ausencia de eventos no justifican garantías poblacionales; si no hay soporte, resultados descriptivos.

H3: comparar perfilado + inferencia de M frente a comparación completa sobre las mismas salidas materializadas. Registrar aparte lectura, transformación, materialización, reglas, inferencia, comparación y reducción. Un calentamiento y cinco repeticiones alternadas por carga según la propuesta; repeticiones miden variación temporal, no aumentan muestra de detección.

Memoria: mismo alcance de proceso, distinguir RSS de pico e incremento; registrar frecuencia de muestreo o herramienta nativa y sus límites. No atribuir a un componente la memoria de otros procesos. H3 no implica automáticamente que todo H sea más rápido.

## 8. Evidencia final

Catálogo, datasheet del snapshot/benchmark, manifests, contratos, versiones, splits, revisiones, modelos, reportes y scripts regeneradores de tablas del capítulo 4. Un integrante distinto reproduce un subconjunto en entorno limpio y documenta incidencias. Coincidencia de conteos no basta: también contenido lógico, montos por moneda, configuración y decisiones.
