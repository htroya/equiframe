# A14: recuperación de informes y supervisor Windows

El intento de validación del corte `1ce7c58` se conserva como **fallido**.
No se acredita el 90 % ni se trasladan sus pases a un candidato posterior.
Se corrigen los problemas detectados antes de repetir la validación privada.

## Resultados que motivaron la corrección

En Linux ARM64, el núcleo registró 8.159 aprobadas, 11 fallidas y siete omitidas;
el benchmark, 621 aprobadas, cuatro fallidas y dos omitidas. Las 175 pruebas
del cliente/DW y verificadores pasaron. EDA conservó sus 704 casos normal y
`-O`, pero los ejemplos documentales no pasaron completos.

En Windows, el benchmark registró 597 aprobadas, 16 fallidas, siete errores y
siete omisiones. Se detuvo únicamente el trabajo de pruebas de ese candidato
ya fallido antes de consumir otra suite completa; sus logs/XML permanecen.
Los servicios de la tutora y los datos originales no se interrumpieron.

Una regresión del inventario protegido convirtió las rutas en absolutas sin
ajustar el cálculo de nombres relativos. Se corrige calculando ambos desde
la misma raíz validada. Los informes vuelven a conservar sus nombres relativos,
hashes y tamaños sin retirar las protecciones de archivos especiales.

Los lectores genéricos conservaron errores de tipo propio donde consumidores
esperaban errores del sistema operativo. Se mantiene el tipo/errno de esos
errores, con texto fijo y sin nombres de archivos. La CLI identifica la clase
inmediata de la causa para dar instrucciones fijas; no muestra valores ni rutas.
Claves JSON duplicadas y CSV truncados conservan códigos reconocibles fijos.

El supervisor Windows además rechazaba una creación estándar de venv desde
otro venv: `pyvenv.cfg` registra al creador, que puede ser otro launcher y no
el intérprete base. Ahora comprueba hasta 16 configuraciones de creadores,
con un máximo de 64 KiB cada una, claves únicas y un mismo intérprete base.
Rechaza ciclos, rutas relativas, homes diferentes, enlaces y configuraciones
excesivas. Sigue lanzando solamente el intérprete base identificado del proceso
actual; nunca ejecuta el creador indicado por un archivo ni cambia comandos ajenos.

## Comprobaciones de la fuente corregida

`recovery-relative-source-v2` conserva **166 aprobadas y 20 omitidas** del
núcleo y **76 aprobadas y cinco omitidas** del supervisor en Windows, sin
fallos. Sus pruebas de procesos incluyen launchers reales y ausencia de
descendientes falsos. Las nueve pruebas nuevas de configuración emplean
identidades sintéticas que nunca se ejecutan. No se suman repeticiones.

Después se comprobó el contrato de errores genéricos y los límites de lectura:
`recovery-final-reader-source-v1` registra **19 aprobadas, 14 omitidas y cero
fallidas**. Incluye conservación exacta de bytes con rutas relativas, rechazo
de documentos mayores a 64 MiB y error de archivo ausente sin divulgar la ruta.

Mypy pasó con 109 archivos del núcleo y 37 del benchmark usando caches privados.
Los intentos anteriores con cache predeterminado fallaron, se conservan y no se cuentan
como pases. Ruff/formato pasaron. Los 71 activos actuales coinciden; el análisis
arquitectónico registró 89 módulos, 590 imports, cero ciclos eager e infracciones.
Estas verificaciones de fuente **requieren reconstruir y validar nuevos artefactos**.

## Trabajo de trazabilidad preparado

Se fijaron 25 contextos adicionales para resultados de comparación, vistas de
informes, especificaciones de ingestión y evaluación de reglas. Sumados a los
282 anteriores, el plan tiene 307 casos con JSON esperado completo, antes de
su ejecución. Catálogo privado `root-plan-security-extension-v1/catalog.json`,
SHA-256 `c91f943424c8c874a1579be3aeae3679a664b5889f4f2706b351dc669a2c7162`.

No se acreditan esos 25 hasta ejecutarlos normal/`-O` sobre los nuevos bytes y
contrastar IDs y observados. Tampoco acreditan entrenamiento, normalidad,
etiquetas humanas ni resultados científicos. El último saldo completo de
trazabilidad conserva su candidato: [7.187/9.142 y 1.955 pendientes](A14_SAFE_ERRORS_EVIDENCE_20261013.md).

Continúa Alpha privada A14. TestPyPI sigue solo en configuración; no se usó
Codex Security ni se crearon agentes. Las intervenciones manuales pesan
conjuntamente diez puntos por rubro. Las evidencias técnicas pendientes no se
convierten en aprobaciones ni se trasladan automáticamente a ese bloque manual.
