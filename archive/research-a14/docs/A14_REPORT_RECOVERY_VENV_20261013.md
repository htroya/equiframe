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

## Seguimiento del 14 de octubre

El corte `062429b85dd0d73def2f85fb1e4ba72893e1bb93` acreditó los 307 contextos
normal/`-O`: 284 admitidos y 23 rechazos esperados, con observados e IDs idénticos.
El baseline volvió a ejecutar sus 5.230 casos y conservó 6.201 obligaciones;
EDA volvió a comprobar sus 704. El consolidado ligado al wheel del núcleo
`d575586402459c1e05c32b4fdc1e4215ea677c3ccd8eab0239049dbdbca9c700`
registra **7.212/9.142 y 1.930 pendientes**: 25 nuevas respecto del saldo previo.
La contribución técnica, con diez puntos manuales pendientes, es
**70,9998/90 puntos**; no es el promedio de los siete rubros.

Sus 15 perfiles también pasaron comprobaciones específicas del SDK mediante
actualización de copias privadas, con resolución normal de dependencias, pip
26.2.1 y verificación del contenido instalado completo. Los originales no se
modificaron. Un primer intento del arnés exigía el perfil completo al comprobar
perfiles mínimos; se conservó como fallido y se corrigió la comprobación de
identidad sin retirar los controles de disponibilidad específicos de cada perfil.

Las pruebas completas siguen siendo necesarias: Linux registró 8.178 aprobadas,
dos fallidas y nueve omitidas del núcleo. La comprobación de catálogo de reglas
detectó que el lector protegido rechazaba sus rutas relativas con `..`; la otra
falla esperaba la categoría genérica de I/O donde ahora se ofrece `missing_path`.
El benchmark registró dos fallos por el tipo de error al faltar su recibo final,
tanto en Linux como en Windows. Los intentos fallidos conservan sus XML y logs.

La corrección permite navegación local explícita de contratos después de
inspeccionar los directorios atravesados, sin resolver enlaces antes de comprobarlos.
Los lectores de evidencia conservan la prohibición de navegar a padres. El lector
de escala mantiene clases/errno del sistema con mensajes fijos y sin filenames;
rechaza raíces enlazadas y miembros especiales en su inventario. No se cambia
la negativa a aceptar operaciones sin finalización.

Las pruebas focalizadas de estas correcciones registran **33 aprobadas y 15
omisiones** del núcleo, y **11 aprobadas sin omisiones** del lector de escala/CLI
en Windows. Incluyen navegación legítima, junctions que intentan ocultarse con
`..` y conservación de la política estricta de evidencias. Estos nuevos cambios
requieren otro candidato privado y comprobaciones propias; el saldo anterior
permanece asociado a sus bytes. Mypy pasó con 109 archivos del núcleo y 37 del benchmark.

Los controles de publicador/documentación/DW/cliente/verificadores del candidato
`062429b` registraron 209 aprobadas, cinco omitidas y 39 subpruebas aprobadas.
Su wheel del núcleo reconstruido desde el sdist fue idéntico. La preparación
de publicación mantuvo el código de salida tres por puertas públicas pendientes;
Twine sólo comprobó los archivos. No se subió ningún paquete.

El enlace de la tutora respondió HTTP 200 el `2026-10-14T05:27:36Z`, con el
mismo SHA-256 de su índice. La comprobación fue de lectura y no modificó servicios.
