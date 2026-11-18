# Paso 10: evaluación y reproducción

El paso 10 implementa el protocolo del capítulo 3 y la generación verificable de
tablas a partir de evidencia capturada. Las pruebas nativas y los corpus
sintéticos son comprobaciones de ingeniería. No constituyen revisiones humanas,
resultados sobre contratación pública ni evidencia para aceptar H1/H2/H3.

## Configuración congelada y ejecución

`FreezeDefinition` declara catálogo, particiones por componentes de dependencia,
casos de test, modelos por familia, selecciones normales separadas de entrenamiento
y calibración, decisiones experimentales, archivos con SHA-256/tamaño, revisiones,
entorno, protocolo de evaluación y protocolo de costes. `create_freeze` verifica
los archivos reales, contratos, reglas fijadas antes de variantes, perfiles,
procedencia de selecciones, calibración y soporte antes de emitir `FreezeManifest`.
No entrena un Isolation Forest ni produce revisiones. El ajuste de medianas y la
calibración pueden recalcularse para verificar las selecciones ya declaradas.

El modo `pilot` exige integridad técnica y conserva los bloqueos científicos. El
modo `final` exige que tampoco queden esos bloqueos. La configuración contiene
doce decisiones explícitas; un hash no demuestra independencia de personas,
licencia de datos, suficiencia estadística ni que un autor no haya observado test
durante su desarrollo. Estas condiciones necesitan evidencia externa.

`run_study(manifest, registry=..., rule_registry=..., work_dir=..., cancellation=...)`
consume un freeze existente. Reaudita las fuentes antes y después, ejecuta cada
caso una sola vez con las entradas Arrow del escenario y el registro confiable
explícito, y usa el bundle congelado de su familia. La ausencia de modelo produce
M/B no evaluables; no activa entrenamiento. Las excepciones y ejecuciones nativas
fallidas quedan como casos con cuatro componentes no evaluables. Si una ejecución
es válida pero una etapa posterior falla, se conserva el R realmente disponible.

Una etiqueta confirmada de EquiFrame Verify, la validación independiente de
equivalencia, se reutiliza únicamente cuando los inputs capturados tienen las
mismas identidades, la versión de implementación coincide con el candidato y la
salida fresca compara equivalente con su salida revisada. Esa comparación usa el
contrato y la política declarados. Una salida distinta, comparación no evaluable
o versión diferente deja O no evaluable y sin etiqueta. Ninguna mutación se etiqueta
por su intención. Las revisiones pendientes o en desacuerdo conservan ese estado.

Si cambia la auditoría de fuentes durante una corrida, se preserva la evidencia
fallida y su evaluación queda en modo piloto. No se emite una evaluación científica
final sobre un freeze que dejó de cumplir su verificación.

## Soportes, métricas e hipótesis

La unidad de detección es el caso con su ejecución nativa única. El soporte
principal contiene exactamente los casos con etiqueta confirmada y R, M, B y H
completos. Se usan los mismos casos para comparar métodos. H conserva la decisión
`R OR M` y solo está completo cuando ambos componentes están completos. MAD sigue
como B independiente. Las alertas parciales se registran y no entran como decisiones
completas en el soporte principal.

El soporte propio de cada método contiene sus decisiones completas con etiqueta
confirmada. Es una descripción secundaria de disponibilidad, no un reemplazo del
soporte emparejado. Se publican casos programados, confirmados, pendientes,
desacuerdos, O no evaluable, fallidos, excluidos y completos. Algunas categorías se
superponen: por ejemplo, una etapa posterior fallida puede conservar un R válido.
La cobertura principal es `N_principal / N_confirmados`; la cobertura de un método
es `N_propio / N_confirmados`. El total programado se presenta por separado.

Para cada soporte se conservan TP, FP, TN y FN y los cocientes exactos:

| Métrica | Numerador / denominador |
| --- | --- |
| Precisión | `TP / (TP + FP)` |
| Recall | `TP / (TP + FN)` |
| F1 | `2 TP / (2 TP + FP + FN)` |
| Tasa de falsos positivos | `FP / (FP + TN)` |

Las definiciones de precisión, recall y F1 coinciden con la
[documentación primaria de scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_fscore_support.html).

Un denominador cero produce `value=None` y un motivo explícito. Los conteos cero
son conteos reales; no se sustituyen estimaciones indefinidas por cero. Los
resultados se calculan globalmente, por familia, por migración y por su cruce,
incluidos los estratos declarados sin casos.

Para H1 se cuentan los verdaderos positivos adicionales de H respecto de R:
casos divergentes con `H=alert` y `R=no_alert`, divididos por todos los divergentes
del soporte principal. H2 cuenta análogamente los falsos positivos adicionales
sobre todos los normales del mismo soporte. Estas tasas incrementales preservan
los casos y denominadores; no afirman aceptación de las hipótesis sin evaluación.

Average precision se calcula con scores orientados hacia anomalía y todos los
empates al mismo umbral: `AP = sum((Recall_k - Recall_(k-1)) * Precision_k)`.
El cálculo usa fracciones exactas y no interpola la curva. La política requiere
ambas clases, una familia y un mismo bundle dentro del soporte; si falta alguna
condición se publica el motivo indefinido. No se mezclan rankings de modelos
heterogéneos como si compartieran una escala calibrada. M y B conservan sus AP
independientes; R/H no reciben scores artificiales.
La suma sin interpolación sigue la definición de
[average precision de scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html);
las condiciones de soporte y homogeneidad son políticas explícitas de EquiFrame.

## Bootstrap por grupos

Los intervalos remuestrean componentes completos de dependencia con reemplazo.
Cada réplica toma tantos grupos como hay en el soporte y conserva todas las
ejecuciones/variantes de cada grupo seleccionado. El estimando es la métrica
agregada de ejecuciones, no la media de métricas de grupos. El tamaño variable de
los grupos se conserva; no se impone una independencia entre variantes o motores.

`BootstrapPlan` fija semilla, número de réplicas, confianza decimal, mínimo de
grupos y justificación explícita de independencia. Sin esa justificación o con
menos grupos que el mínimo, los extremos del intervalo quedan ausentes. Para
confianza `c` y `B` réplicas, los ordinales de base 1 son
`max(1, ceil((1-c) B / 2))` y `ceil((1-(1-c)/2) B)`.
Se ordenan los estimadores y se toman esos ordinales sin interpolación. Si alguna
réplica de una métrica es indefinida, se conserva su contador y no se publica un
intervalo condicionado a haber descartado réplicas. Una estimación puntual
indefinida tampoco recibe un intervalo.

El principio de remuestreo y la distinción entre intervalos percentile y BCa se
describen en la [documentación primaria de SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).
El remuestreo de grupos, los ordinales `ceil` sin interpolación y el bloqueo ante
cualquier réplica indefinida son políticas de EquiFrame. Este módulo no llama a
`scipy.stats.bootstrap` ni afirma reproducir su implementación BCa predeterminada.

## Costes operacionales de H3

`CostSpec` fija la ejecución y referencia ya materializadas, hashes de todas sus
capturas, bundle, perfil, política/opciones de comparación y `CostProtocol`.
`measure_costs` recibe dos callbacks síncronos y confiables, `profile_m` y
`comparison`. M usa `ef.profile_execution` seguido de
`ef.detect_component(..., method="isolation_forest")`; se evita puntuar MAD en ese
lado. La comparación usa las mismas salidas capturadas y conserva la metadata de
una referencia `ExecutionResult`, incluidas sus precondiciones de inputs/parámetros.

Se realizan un par de warmup, conservado aparte, y cinco pares medidos. La semilla
fija el primer método y el orden se alterna entre pares. Se declaran política de
caché, hilos, presupuesto de memoria, cargas coexistentes y motivo de los controles.
Son declaraciones del entorno; el medidor no impone cuotas duras a código nativo.
Las doce observaciones se conservan incluso cuando un método falla o se cancela.

El tiempo de pared abarca el callback y la validación de su resultado. Incluye las
verificaciones, releídas Arrow y publicación de evidencia internas de esas APIs.
Excluye la lectura inicial del DW, ETL, captura inicial, hashes externos antes y
después, preparación/cierre del monitor, `observation.json` y el manifiesto final
del medidor. No se resta una estimación de I/O ni se presenta como CPU pura.

Con el extra opcional `equiframe-benchmark[resources]`, psutil 7.x observa el CPU
acumulado del proceso (`user + system`) y su RSS. El CPU registrado es la diferencia
entre las muestras inicial/final; incluye actividad del hilo de muestreo y su
bracket de preparación/cierre, y excluye CPU de procesos hijos. El RSS es el máximo
absoluto de las muestras, un límite inferior al pico real. Se preservan la muestra
inicial, los timestamps, intervalo y máxima separación observada; el RSS previo
no se reporta como memoria adicional atribuible a la operación.
Las unidades y el alcance de los contadores se apoyan en la
[API primaria de psutil 7.2.2](https://psutil.readthedocs.io/stable/index.html).

Un fallo de probe o del hilo de muestreo no omite el callback. Se conserva su
resultado y tiempo de pared real con recursos parciales o ausentes. Un retraso
mayor de dos intervalos queda declarado como muestreo parcial; un contador CPU
decreciente también. No se inventan CPU/RSS/tiempos cero para operaciones no
iniciadas. Los hashes antes/después detectan capturas alteradas y evitan ejecutar
pares posteriores sobre bytes que dejaron de coincidir con la configuración.

Las cinco repeticiones evalúan coste; no aumentan la muestra de detección ni los
grupos para bootstrap. Reproducir costes significa conservar protocolo,
repeticiones, contenido y decisiones; no exigir los mismos floats de tiempos o RSS.

## Persistencia, tablas y límites

`StudyResult` vincula el freeze, sus dos auditorías, los recibos por caso, pipelines,
comparaciones de reproducción de salida, evaluación, tablas e inventario cerrado.
`study.json` se publica al final. `read_study` comprueba inventario/hashes, recibos
originales de pipelines, comparaciones locales y sus diferencias, reaudita las
fuentes del freeze y vuelve a verificar el manifiesto durante la lectura. Nunca
ejecuta transformaciones del registro ni entrena modelos; la auditoría puede
recalcular perfiles y comparaciones sobre capturas ya existentes.

`write_tables` produce seis CSV deterministas: cobertura, métricas, AP, ganancia
incremental, bootstrap y casos. `read_tables` regenera los bytes desde el
`EvaluationReport` vinculado y verifica conteos, tamaño, hash e inventario. Cambiar
un valor y recalcular su hash no basta para alterar una tabla aceptada. Estos seis
CSV son tablas de detección; los recibos de recursos/coste se conservan aparte.
`write_cost_table` exporta aparte las doce observaciones crudas con unidades,
warmup distinguido, estados, ausencias y diagnósticos; no calcula promedios ni
descarta operaciones fallidas para presentar solo las más rápidas.

`read_costs` verifica las doce observaciones, la configuración, capturas originales
e inventario de evidencia. Los resultados de cada método se guardan completos,
incluidos los no evaluables, esperados inválidos y cancelaciones. Las acciones del
medidor y el registro nativo siguen siendo código confiable que el caller declara
explícitamente; JSON no contiene instrucciones para importar o ejecutar callbacks.

El bundle genérico de reproducción conserva archivos/identidades y los contenidos
canónicos declarados de configuración, splits, etiquetas, decisiones y tablas.
Comparar contenido reproducido no autentica a revisores ni demuestra equivalencia
de todos los entornos. El cliente del DW, snapshot/DDL reales, corpus revisado,
decisiones científicas pendientes y publicación PyPI mantienen sus gates externos.
