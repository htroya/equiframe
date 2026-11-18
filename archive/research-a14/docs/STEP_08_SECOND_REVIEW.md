# Segunda revisión del paso 8 — candidata 0.8.1

Revisión de ingeniería y alineación con la tesis, 2026-10-02. La candidata
corresponde al núcleo y al benchmark 0.8.1; conserva el alcance del paso 8 de la
[hoja de ruta de veinte pasos](HERNAN_ROADMAP.md). La [entrega 0.8.0](STEP_08_REVIEW.md)
se mantiene como evidencia histórica: sus resultados no se trasladan a esta
corrección sin ejecutar las comprobaciones de la revisión actual.

## Fuente y criterio de conformidad

Se contrastó directamente `TFM_EquiFrame_ACTUAL.docx`, ubicado en la carpeta
padre del repositorio, especialmente §1.3, §1.4, §3.3, §3.4, §3.6–3.9. El
documento conserva el SHA-256 registrado en la [trazabilidad](THESIS_TRACEABILITY.md):

```text
c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d
```

No se modifica el DOCX. La revisión distingue requisitos del borrador,
decisiones de ingeniería y cierre experimental pendiente. No encuentra un
desvío central del paso 8 respecto de los objetivos y del método propuesto.

| Referencia del TFM | Evidencia concreta y límite |
|---|---|
| OE3 de §1.3: biblioteca con reglas, perfiles, Isolation Forest, MAD, reportes y estados no decidibles | `run_pipeline` integra componentes existentes sobre una captura nativa única. Mantiene configuración, decisiones y disponibilidad; no ajusta modelos durante inferencia |
| §3.4: módulos sustituibles y CLI con configuración versionada | Fuente, transformación, adaptador, registro R y bundle se reciben explícitamente. La CLI operacional y los comandos del benchmark tienen entradas estrictas; no importan código indicado por JSON |
| §3.4.1 y §3.6: R y M sobre una sola ejecución; comparación separada | R y perfil reutilizan la captura. M/B reciben el mismo preprocesamiento del bundle. La comparación opcional no alimenta las features ni las alertas; O permanece en el benchmark |
| §3.4.2: evidencia, reducción con precondiciones y presupuesto | Manifiestos, journal, resultados y referencias preservan la procedencia. El reductor elimina filas conservando esquema, orden relativo y multiplicidad, y exige la firma del fallo y las precondiciones declaradas |
| §3.4.3: H = R OR M y disponibilidad explícita | H conserva alertas parciales. La ausencia de alerta exige R y M evaluables; B conserva su decisión independiente |
| OE4 y quinto objetivo específico de §1.3 | La evidencia prepara comparación y reproducción. Una prueba automática con paquetes instalados no constituye la evaluación científica ni la reproducción realizada por otro integrante |

Las decisiones A72–A78 de [DECISIONS.md](DECISIONS.md) documentan la entrega
original. La corrección conserva las fórmulas, R, alpha, la independencia
R/M/B/H/O y los criterios de revisión; refuerza la verificación de los
artefactos persistidos. Los formatos 1.0 permanecen separados de la versión
de producto. Admitir la versión emisora 0.8.1 no reinterpreta bundles explícitos
0.7.0/0.8.0 ni cambia el algoritmo declarativo IF/MAD 1.0.

## Defectos de evidencia y correcciones candidatas

| Área | Defecto identificado | Corrección y regresión prevista |
|---|---|---|
| Inventario de pipeline | El lector verificaba únicamente los archivos enumerados. Omitir una captura del inventario y borrarla podía dejar una corrida completa aceptada | Exigir correspondencia entre archivos de la corrida e inventario final; vincular referencias propias de ejecución, reglas, perfil y comparación a rutas contenidas y archivos inventariados con el mismo SHA-256 y tamaño |
| Snapshots y procedencia de comparación | La verificación no vinculaba suficientemente las referencias de captura al inventario | Verificar los snapshots capturados de la comparación. Mantener la referencia original externa como procedencia, sin exigir que esa fuente siga disponible para verificar la captura local |
| CLI de evidencia y reportes | JSON o manifiestos persistidos corruptos podían clasificarse como petición inválida con código 2 | `evidence verify` y `report` deben devolver 3 ante evidencia corrupta; la configuración o petición inválida conserva 2. Se añaden casos de JSON truncado y esquema inválido |
| Tablas reducidas | Hashes de archivos y recuentos de eventos no demostraban que el resultado reducido correspondiera a las posiciones originales declaradas | Verificar referencias originales/reducidas, configuración guardada, número de filas y contenido Arrow reconstruido desde `retained_positions`, sin reescribir valores |
| Observaciones y minimalidad de reducción | La coherencia superficial del journal no bastaba para justificar baseline, aceptaciones, confirmaciones ni una afirmación `one_minimal` | Vincular selecciones y observaciones de cada intento con las transiciones del journal, firma objetivo, precondiciones y confirmaciones; comprobar la relación entre candidatos aceptados y resultado final, y la evidencia de supresiones individuales cuando se afirma minimalidad |

Se reprodujo el defecto de reducción alterando solo `reduction.json`: el lector
aceptaba una firma de fallo nunca observada y una selección de una fila mientras
la referencia reducida apuntaba a las tres filas originales, junto con la
afirmación `one_minimal`. El manifiesto final no puede inventariar su propio
contenido; por ello la verificación debe contrastar sus declaraciones con las
capturas, observaciones y transiciones independientes que sí están inventariadas.

Las regresiones de pipeline se incorporan en
[`test_pipeline_evidence.py`](../packages/equiframe/tests/test_pipeline_evidence.py)
y las de reducción en
[`test_reduction.py`](../packages/equiframe/tests/test_reduction.py).
Cubren firmas, opciones, posiciones, referencias, conteos y estados alterados,
incluidas observaciones y selecciones cuyo hash se recalcula, así como evidencia
legítima de NaN, datos anidados, baseline inválido, cancelación, presupuesto y
fallo del predicado. Los resultados ejecutados se registran en la sección de
verificaciones; esta descripción no acredita por sí sola que hayan pasado.

El lector comprueba la coherencia de la evidencia registrada sin ejecutar de
nuevo el ETL ni el predicado de reducción. La veracidad del predicado confiable
y la suficiencia de sus precondiciones siguen siendo responsabilidad de su
autor. Hashes y enlaces detectan corrupción respecto del manifiesto recibido;
no aportan firma digital, almacenamiento WORM ni protección frente a un actor
que pueda reemplazar toda la evidencia y recalcularla.

## Límites científicos y dependencias reales

El piloto conserva cinco escenarios, cuatro grupos de procedencia, quince
perfiles y 35 revisiones pendientes, con cero etiquetas científicas confirmadas.
Sus mutaciones de artefactos y modelos temporales de tests verifican ingeniería;
no son implementaciones ETL mutadas revisadas, resultados SERCOP ni evidencia
de mejora del híbrido. La meta de 60 escenarios y al menos 300 perfiles de
§3.7 sigue siendo una meta; no se fragmentan grupos ni se cuentan semillas o
repeticiones como observaciones independientes para alcanzarla.

Persisten los requisitos de §3.2/§3.5 sobre corpus SERCOP real, cohorte temporal,
compilación OCDS, grano del DW y reconciliación por moneda/estado. La VM y el
cliente corresponden a José; el modelo y las cargas del DW a Jhair. El núcleo
genérico y su DuckDB local no acreditan una conexión real al DW compartido.
La integración y las dos validaciones reales conservan sus pasos y condiciones
de entrada en la hoja de ruta.

Antes de la evaluación final siguen pendientes la revisión humana de §3.3.4,
soporte normal y variación por familia, justificación de alpha, grupos disjuntos
y `FreezeManifest` experimental. Las métricas de §3.8 deben usar la intersección
evaluable con etiquetas confirmadas, conservar denominadores y separar costos.
La reproducción de §3.9 requiere la ejecución y el registro de otro integrante.
Esta corrección no confirma H1–H3 ni aporta falsas alarmas poblacionales.

A58 añade independencia respecto de autores del escenario y del resultado
esperado, también para el árbitro. Es una condición adicional documentada y
conservadora frente al procedimiento de tres integrantes descrito en el TFM;
puede requerir otro revisor. No constituye un desvío central, pero el equipo
debe resolver su viabilidad antes de confirmar etiquetas. No se simulan
aprobaciones para cerrar ese requisito.

Los reportes distinguen alertas, diferencias, completitud y confirmación
científica. Código 0 indica que las evaluaciones operacionales solicitadas
terminaron sin alertas o diferencias observadas; no acredita corrección
científica. Los artefactos completos pueden contener datos y parámetros ETL:
continúan siendo privados. Los reportes seleccionan campos y escapan HTML;
no se promete detectar secretos arbitrarios introducidos en datos o código.

## Horizonte de publicación pública

La distribución pública por `pip install equiframe` es el requisito adicional
de producto P06 y la aclaración A71; no se atribuye al texto del TFM. La hoja
de ruta ampliada exige revisión y validaciones reales en 11–15, licencia/nombre
y distribución en 16–17, ensayo en TestPyPI en 18, publicación pública en 19
y aceptación externa/mantenimiento en 20.

La candidata 0.8.1 prepara código y artefactos revisables. Construir o probar
wheel/sdist, subir código a GitHub o instalar temporalmente por nombre desde
wheels locales no satisface la disponibilidad pública en PyPI. Esta revisión
no ejecuta una publicación en TestPyPI/PyPI ni despliega los servicios del
equipo. El paso 19 requiere su tarea explícita, licencia, cuenta/nombre y
artefactos finales comprobados.

## Verificaciones de esta revisión

Controles ejecutados localmente sobre la corrección 0.8.1. El benchmark se
verificó desde una copia del índice preparado, sin incluir los archivos nuevos
del paso 9 ni el cambio previo de la hoja de ruta.

| Control | Resultado actual |
|---|---|
| Ruff y formato de ambos paquetes | Aprobados; se corrigió el formato del verificador del benchmark |
| mypy y comprobación de assets/esquemas | Núcleo: 36 archivos/41 assets; benchmark: 15 archivos/13 esquemas |
| Regresiones de pipeline, CLI y reducción | 14 pruebas nuevas de evidencia y 21 de reducción aprobadas |
| Suite completa del núcleo y benchmark | Núcleo instalado: 717 aprobadas en 252,67 s; benchmark instalado: 88 en 76,59 s |
| Build de wheel/sdist e inventario/hashes | Ambas distribuciones 0.8.1 construidas; wheels reconstruidos idénticos desde sdist |
| Distribución instalada fuera del checkout y ejemplos externos | Base/extras/API/CLI/ejemplos y consumidor mypy núcleo aprobados; piloto benchmark: 5 escenarios/35 candidatos/15 perfiles/4 grupos, cero confirmados |
| CI remota vinculada al commit publicado | Commit `6231ef8`: diez jobs aprobados en push/PR, Windows x64, Linux x64/ARM64 y macOS Intel/Apple Silicon; PR #18 integrado |

El entorno local de referencia es Windows x64 con Python 3.12. Deben registrarse
la versión concreta de Python, dependencias bloqueadas, comandos y tiempos
realmente usados para esta revisión. Un resultado local no acredita Linux,
macOS, ARM64 ni la VM OCI. La matriz CI configurada no es un resultado: cada
conclusión remota debe vincularse al commit, runner y ejecución comprobados.
No se reutilizan las cifras de la entrega 0.8.0 como aprobación de 0.8.1.

Python 3.12.4 en Windows x64; dependencias y hashes se conservaron en los locks.
Los registros completos están en las rutas locales ignoradas
`packages/equiframe/.cache/step8-second-distribution.log` y
`packages/equiframe-benchmark/.cache/step8-second-distribution.log`.
Los verificadores terminaron todos sus controles y registraron su mensaje final
de verificación. La redirección de stderr nativo en PowerShell devolvió estado 1
en el envoltorio, aunque no hubo traceback ni fallo de un subprocess comprobado;
ese estado del envoltorio no se presenta como código 0 del proceso.

CI contrastada: [push](https://github.com/htroya/equiframe/actions/runs/37035598082)
y [PR](https://github.com/htroya/equiframe/actions/runs/37035605371), sobre
`6231ef8`. El [PR #18](https://github.com/htroya/equiframe/pull/18) entrega la
corrección integrada. Estas pruebas siguen sin acreditar OCI/DW ni publicación PyPI.
