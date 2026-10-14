# Operaciones protegidas y corpus anual propuesto

Se continúa el objetivo de [90 puntos técnicos y diez manuales](A14_TECHNICAL_90_METHOD_20261013.md).
Los resultados de este corte no acreditan todavía el cierre de los siete rubros.

## Protección de entradas y salidas

La inspección encontró operaciones que aplicaban `resolve()` antes de comprobar
los ancestros de `work_dir`. Eso borraba de la ruta la evidencia de symlinks o
junctions. `_regular_io.local_output_directory` comprueba la ruta elegida antes
de normalizarla. Se usa en ejecución, pipeline, comparación/diff, migración,
Verify, reglas, perfiles, reducción, workflow, ingestión, captura DuckDB y el
destino Parquet. Sólo `None` activa los defaults documentados; cero, `False` y
objetos de tipo incorrecto ya no pueden activar una carpeta por defecto.

El destino también inspecciona `versions`, `.staging` y `.validation` antes de
adquirir su lock o escribir. Los documentos compartidos comprueban sus ancestros
antes de publicar, conservando la publicación exclusiva y los errores OS sin
valores externos. Ingestión abre un archivo regular antes de crear su operación,
rechaza FIFO/enlaces y lee como máximo el presupuesto restante más un byte.
No se alteran esquemas, formatos, algoritmos ni políticas de comparación. Estas
comprobaciones no son una sandbox frente a un propietario hostil del filesystem.

La batería focalizada de fuente `operation-roots-tests-v4` pasó **153 pruebas**,
con **23 omisiones de plataforma y cero fallos**. Incluye trece APIs, junctions
reales, rechazo de tipos incorrectos sin crear salidas, navegación local ordinaria,
límites de lectura y conservación del destino. Tipado, arquitectura y 71 activos
pasaron en la comprobación de fuente. Se conservan los intentos previos: una
fixture usó un nombre de API incorrecto y el caso Verify necesitaba snapshots
vinculados y autorización explícita para su RangeIndex de transporte. Las
expectativas de éxito se conservaron al completar esas precondiciones.

`tools/revalidate_native_operations.py` declara tres filas sintéticas, incluyendo
una repetición, y sus resultados esperados antes de ejecutar operaciones nativas.
Su catálogo `native-operations-plan-v1/catalog.json` fija **69 casos y 177 IDs
nuevos**, SHA-256
`640706833899087f942c2f1ffa95abd58d1332157d410e9f299cb72a242c6592`.
Exige wheel/baseline concordantes y separa los IDs anteriores sólo para delimitar
trabajo nuevo. No importa sus conteos. La ejecución instalada normal/optimizada
y la suma de esos IDs siguen pendientes del nuevo artefacto.

El wheel anterior del corte `8f8138c` terminó su suite propia Windows con **8.170
aprobadas, 51 omitidas y cero fallos**. Esos recibos mantienen su identidad y no
se trasladan a la modificación de directorios. La trazabilidad anterior continúa
en **7.334 / 9.142, con 1.808 pendientes**, hasta comprobar el candidato nuevo.

## Preparación del corpus más allá del piloto

`tools/prepare_sercop_cohort.py` leyó íntegramente el snapshot público original,
SHA-256 `80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3`.
La fuente se comprobó antes, después y por su ruta al finalizar. Se conservan
los atributos OCDS no proyectados en ese original; los fragmentos nuevos no
sustituyen una compilación completa OCDS ni el DW de dominio.

En Linux ARM64 se prepararon **182.277 unidades OCID propuestas**, con **183.891
adjudicaciones**, en **19 fragmentos y 89.272.752 bytes**. Los **8.342 registros
sin adjudicaciones** tienen exclusión explícita. Se contabilizaron las 190.619
releases originales: 176.665 publicadas en 2025 y 13.954 en 2026. La ejecución
no aplicó un filtro de año oculto; un filtro explícito por `release.date` sería
sólo una propuesta de cohorte, que requiere aprobación de dominio.

Los montos permanecen como texto decimal exacto, incluyendo escala y flags
missing/null/present. Cuatro adjudicaciones mantienen ausencia del valor; no se
convierten a cero. Cada fragmento tiene límite de 16 MiB y 10.000 unidades; cada
unidad, 256 KiB y 256 adjudicaciones. El mayor grano observado contiene 233
adjudicaciones. El manifiesto `sercop-annual-candidates-v1/cohort-proposal.json`
tiene SHA-256
`7e76a4233e26aaf08b84835fe9c582b7a9464d6ca03f76ae542a78a36c75825b`.
Las ocho pruebas de contabilidad, exactitud, duplicación y presupuestos pasaron.

**Estas unidades todavía no son ejecuciones normales ni perfiles de aprendizaje.**
El manifiesto conserva `native_executions=0`, etiquetas sin asignar, particiones
finales pendientes y `N_fit` acreditado cero por familia. Falta ejecutar y
perfilar las unidades propuestas, declarar dependencias de plantillas/fragmentos,
resolver particiones completas y obtener las revisiones necesarias para ajustar,
calibrar y evaluar. Los conteos de adjudicaciones o motores no reemplazan ese
soporte efectivo.

No se modificó el Word, la entrega pública ni el servicio de la tutora. No se
usaron Codex Security ni agentes, y no se publicó en PyPI/TestPyPI ni se ejecutaron
Actions. La solicitud posterior a Robot mantiene la condición de siete rubros
acreditados al 90 % y el corte correspondiente subido.
