# Revisión independiente con el lenguaje R

EquiFrame ofrece `review_with_r`, `finalize_with_r` y
`finalize_execution_with_r` como una etapa opcional.
El revisor ejecuta una segunda comparación determinista sobre las dos tablas
observadas completas y el contrato declarado. Su implementación usa base R;
no recibe el veredicto del comparador Python ni los scores de los detectores
como respuesta esperada.

Esta independencia de implementación ayuda a encontrar discrepancias entre
comparadores. No demuestra por sí sola que la migración sea correcta para
cualquier entrada. Una alerta de Isolation Forest sigue siendo una anomalía,
no una prueba de diferencia semántica. Replicar el mismo Isolation Forest en
R no aportaría esa garantía y no forma parte de esta etapa.

La letra `r` de `HybridDecision.r` sigue significando **reglas**. El lenguaje R
no reemplaza reglas, M (Isolation Forest), B (MAD), H (reglas OR M) ni O
(oráculo científico). El revisor tampoco modifica perfiles, entrenamiento,
calibración o inferencia de los detectores.

## Uso después de reglas e Isolation Forest

R debe estar instalado por el usuario y `Rscript` debe estar en `PATH`, o se
debe indicar su ejecutable. EquiFrame no instala R ni paquetes R. Sólo necesita
base R. Los ejemplos siguientes describen llamadas de uso; no son ejecuciones
ni resultados de validación.

```python
import equiframe as ef

# Valores obtenidos previamente de las API reales:
# execution: ExecutionResult con la salida capturada que se está analizando.
# rules_result: RuleEvaluation para la ejecución que se está analizando.
# profile: ProfileResult producido para esa ejecución.
# detector_bundle: bundle Isolation Forest previamente ajustado y calibrado.
# python_comparison: ComparisonResult que conserva esa ejecución en uno de sus lados.
detection = ef.detect_component(detector_bundle, (profile.vector,), method="isolation_forest")

final = ef.finalize_execution_with_r(
    execution,
    rules_result,
    profile,
    detection,
    comparison=python_comparison,
    options=ef.RReviewOptions(rscript="Rscript", timeout_seconds=30.0),
)

# Consultar los componentes y su disponibilidad de forma explícita.
hybrid_decision = final.hybrid.result
independent_comparison = final.r_review
previous_comparison = final.comparison
comparators_disagree = final.comparison_disagreement
final_decision = final.result
may_continue = final.accepted
execution_binding = final.execution_binding
```

Ésta es la ruta vinculada: comprueba IDs, huellas de ejecución, contrato,
artefactos del perfil y el resultado IF de exactamente un vector. Exige que
la comparación conserve esa ejecución y su salida en uno de sus lados; lee
directamente los artefactos comprobados de ambos lados. Una asociación inválida
se rechaza antes de iniciar R, mediante un error de validación. La vinculación
no autentica al autor humano ni convierte una etiqueta declarada en verdad.

`final.execution_binding` es un `RExecutionBinding` con `execution_id`,
`execution_sha256`, `profile_id`, `profile_sha256`, `detection_sha256` y
`output_sha256`. Identifica los documentos y la salida realmente asociados por
el finalizador. El ejemplo no entrena un modelo ni proporciona un bundle ficticio.

`finalize_with_r` permanece como API de bajo nivel para quien ya tiene decisiones
operacionales y observaciones eager. Recibe `rules`, una `ComponentDecision` de
Isolation Forest, `left`, `right`, `contract` y `comparison` opcional. En esa ruta
el llamante debe asegurar la asociación de las decisiones; una decisión aislada
no contiene toda la procedencia de su ejecución. No se declara
`execution_binding` por deducirla del nombre de una variable.

Para solicitar exclusivamente la segunda comparación:

```python
from equiframe.r_review import review_with_r

review = review_with_r(
    pandas_output,
    polars_output,
    contract=diff_contract,
    comparison=python_comparison,
)
```

`review_with_r` admite salidas eager de Pandas, Polars, Arrow, `ArrowInput`,
artefactos locales `ArtifactRef` y `TableArtifact`, y objetos reales
`DuckDBPyRelation`. Pasar una relación DuckDB autoriza consumir su plan nativo
una vez por entrada suministrada, con comprobación de tipos y límites de filas
y bytes. La captura rechaza el exceso de filas, sin truncarlo para aceptar la
comparación, y conserva una observación separada de la relación. El llamante
mantiene la propiedad de su conexión, configuración y plan nativo.
No se infieren cadenas SQL, conexiones, callbacks, lectores consumibles ni
`LazyFrame` de Polars como entradas tabulares. También puede capturarse DuckDB
previamente como Arrow/artefacto para revisar una observación ya materializada.
`comparison` es opcional para la revisión aislada. Cuando se aporta,
comprueba los SHA-256 de sus artefactos y que todo el transporte observado de
`left` y `right` corresponda a esos mismos datos antes de enviarlos a R.
Una especificación distinta bloquea la finalización; el veredicto Python no se
envía como respuesta esperada.

Una revisión vinculada conserva `review.binding`, un `RReviewBinding` con
`comparison_id`, `left_artifact_sha256` y `right_artifact_sha256`. Una revisión
aislada sin `comparison` conserva su dictamen, sin inventar ese vínculo.

Los modelos de opciones, vínculos y resultados tienen esquemas versionados estables
`1.0` incluidos en el sdist y como recursos `equiframe/schemas` del wheel:
`r-review-options`, `r-review-binding`,
`r-execution-binding`, `r-review-result` y `reviewed-decision`. Su registro
explícito de compatibilidad conserva la huella del productor actual; no cambia
los esquemas o recibos anteriores de comparación, reglas y detectores.
La estabilidad protege la interfaz y los estados de error dentro del subconjunto
admitido; no acredita precisión científica, todos los contratos posibles ni
cualquier versión externa de R. Véanse los límites de [compatibilidad](compatibility.md).

`contract` acepta `Contract`, `DiffContract` o `ComparisonSpec`; no se inventa
un esquema o una tolerancia a partir del veredicto anterior. Si se necesita
inferir un contrato de metadatos, se puede construir antes mediante la API
existente `infer_diff_contract` y revisar sus políticas.

## Resultado final

| Condición | Resultado final |
|---|---|
| Alguna regla o M alerta | Se conserva `alert`, aunque R encuentre equivalencia. |
| El comparador Python previo encuentra diferencias | Se conserva `alert`, aunque R encuentre equivalencia. |
| R encuentra diferencias o violaciones del contrato | `alert`. |
| H está completo sin alertas, R termina equivalente y la comparación Python aportada también es completa/equivalente con la misma especificación y artefactos vinculados | `no_alert`, `accepted=True`. |
| Falta R, hay timeout/cancelación/fallo o una política no está admitida | `accepted=False`; se conserva cualquier alerta y se indica evaluación incompleta. |
| El comparador Python aportado está incompleto o no es evaluable | `accepted=False`; se conserva cualquier alerta y se indica evaluación incompleta. |

El campo `final.r_review.state` mantiene por separado `equivalent`,
`different` o `not_evaluable`. Una comparación equivalente en R y una alerta
de M no se cancelan: son observaciones distintas. `final.result.complete`
requiere disponibilidad de todos los componentes solicitados. `no_alert`
no se convierte en una etiqueta científica de corrección.

`comparison` es opcional. Si se aporta, EquiFrame conserva el documento Python
completo, comprueba las observaciones y lo combina después de ejecutar R, sin
usar su veredicto como esperado para R.
`comparison_disagreement=True` indica que ambos comparadores terminaron con
dictámenes distintos; no decide cuál tiene razón ni borra diferencias.
Una especificación diferente también se conserva y bloquea la aceptación.
Si se omite `comparison`, la finalización mantiene su comportamiento H más R;
no presupone que antes se ejecutó el comparador Python.
Esta opción corresponde a `finalize_with_r`; la ruta
`finalize_execution_with_r` exige una comparación vinculada.

## Alcance exacto del revisor 1.0

Se compara contenido completo, sin muestreo y sin decidir igualdad mediante
hashes. Se mantienen multiplicidad y claves; puede compararse como multiconjunto
o como secuencia, comprobando las columnas de orden y sus empates. El orden
de columnas puede ignorarse sólo cuando el contrato lo autoriza. Un índice
significativo de Pandas exige la autorización explícita existente para ignorarlo
o su promoción previa a columnas del contrato.

Tipos admitidos: booleanos, cadenas UTF-8, enteros de 8–64 bits con signo o
sin signo, decimales de precisión física admitida por Arrow, flotantes de
32/64 bits, fechas `date32` y timestamps. Los enteros y decimales no se
convierten a `double` en R. Se distingue NULL de NaN; NaN puede ser distinto
o estar prohibido. Se preservan signos de infinito; cero positivo y negativo
se comparan según la igualdad numérica exacta existente.

Los timestamps zonificados sólo se admiten para comparación de instantes con
`naive="reject"`; las observaciones ya contienen ticks y zona. Los timestamps
sin zona se admiten con `naive="preserve"`, sin interpretación local.
El revisor no resuelve DST ni convierte cadenas de fecha en instantes.

Las siguientes configuraciones devuelven `not_evaluable` en esta versión:

- Tipos físicos relajados mediante `physical_types="lossless"`.
- Tolerancias numéricas, redondeo, alias de NULL o NaN convertido a NULL.
- Restricciones `allowed_values` e intervalos temporales con límites.
- Resolución de hora local (`assume_zone`), comparación zonificada por hora
  de pared y tipos `date64`.
- Tipos tabulares anidados o metadatos que la captura fiel actual no admite.

Estas limitaciones afectan únicamente a la revisión opcional en R. No
redefinen ni reducen las capacidades del comparador Python. Una política
no admitida no se sustituye por otra para obtener una aprobación.

## Recursos, privacidad y procedencia

Los límites predeterminados son 100.000 filas por entrada, 256 columnas,
64 MiB de captura por entrada y 64 MiB de transporte acumulado, con 30
segundos cooperativos para la operación y un proceso R terminable. No son
cuotas duras de memoria RSS: las copias y los objetos de R tienen sobrecoste.
La captura de un plan nativo DuckDB precede al proceso R y puede bloquear
dentro del motor; el tiempo cooperativo no constituye una interrupción dura
de esa captura.

El proceso usa `Rscript --vanilla --default-packages=NULL`, una carpeta
temporal privada por operación y argumentos estructurados sin shell. Los
archivos temporales se retiran al terminar, incluso ante fallo o cancelación.
El resultado devuelve versión de R, estado, conteos y SHA-256 del código,
especificación y transportes observados. Los hashes sirven para identificar
entradas; R decide con filas completas. No se incluyen valores de las filas
en los canales de diagnóstico ni se guarda un modelo adicional.

La captura Arrow es un límite compartido con el resto del producto: R vuelve
a implementar comparación y validaciones admitidas, pero no reinterpreta los
archivos fuente sin pasar por esa captura. Esta independencia es técnica,
no una revisión humana ni un oráculo de negocio independiente.

Referencias del lanzador y transporte: [Rscript](https://www.stat.ethz.ch/R-manual/R-devel/library/utils/html/Rscript.html),
[readLines](https://www.stat.math.ethz.ch/R-manual/R-devel/library/base/html/readLines.html)
y [writeLines](https://www.stat.math.ethz.ch/R-manual/R-devel/library/base/html/writeLines.html).
