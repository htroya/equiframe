# Endurecimiento adicional de rutas EDA durante el cierre A14

El objetivo continúa siendo acreditar el 90 % técnico de los siete rubros,
con diez puntos manuales reservados. Este cambio corrige un problema observado;
no declara completado el objetivo ni sustituye los recibos anteriores.

Una reproducción privada con el wheel A14 del código `37e0ea7` mostró que
`analyze()` aceptaba un directorio junction de Windows en la ruta de entrada:
leyó las dos filas sintéticas y terminó con `state=completed`. Resolver la
ruta antes de inspeccionar los directorios borraba la identificación del enlace.
El original queda en `a14_review_fixes_20261013/eda-junction-before-v1/reproduction.json`.

La implementación actual inspecciona archivos y directorios antes de resolverlos.
Se rechazan symlinks y reparse points en entrada, salida, manifiestos, resultados
y migraciones. Los miembros de un manifiesto permanecen dentro de su entrega;
el manifiesto admite como máximo 16 MiB y 2.000 entradas, debe ser un objeto y
su SHA-256 se contrasta con los bytes efectivamente leídos. Hash y captura de
archivos utilizan las lecturas protegidas del núcleo. No cambia el formato EDA
1.0 ni los campos y firmas públicos.

Se observaron **63 pruebas EDA distintas aprobadas** en la fuente actual:
52 existentes y 11 nuevas. Los XML `eda-source-path-safety-v2.xml` y
`eda-source-path-safety-v3.xml` conservan el detalle; las nueve pruebas repetidas
no se suman. El arnés registró la importación deliberada de la fuente actual,
separada de la instalación del wheel anterior. Mypy pasó con 107 archivos;
Ruff y formato pasaron, los 71 activos generados coincidieron y la revisión
arquitectónica registró 87 módulos, 575 imports y cero violaciones/ciclos eager.

Bandit conservó dos avisos B608 por SQL construido dinámicamente: los nombres
del CSV y los destinos se escapan como literales antes de usar SQL. Las nuevas
pruebas con una columna que contiene `DROP TABLE` y `<script>` preservaron el
nombre y las filas, y comprobaron HTML codificado. Otro caso produjo y volvió
a leer el Parquet en un directorio con apóstrofo. Se documentan estos avisos
revisados; no se presenta el escáner como libre de avisos ni como certificación.

También se corrigió el orden de los encabezados A14/A13 del changelog, sin
reescribir resultados históricos. La guía EDA distribuida explica los límites
de rutas y manifiestos. Los nuevos bytes del paquete **requieren reconstrucción
y validación privada propia**, todavía en curso: los porcentajes y hashes del
[corte anterior](A14_ROOT_CONTEXT_REVALIDATION_20261013.md) conservan su candidato.

La reconstrucción desde los tres sdists anteriores dio wheels idénticos a sus
originales; ocho ejemplos documentales actuales pasaron normal/`-O`. Estas
evidencias se conservan para sus bytes A14 originales, sin trasladarlas al
candidato nuevo. Las consultas públicas fechadas de los dos nombres en PyPI
y TestPyPI devolvieron cuatro 404: no demuestran reserva ni propiedad.

Los servicios y datos de la tutora no forman parte de estos ensayos privados.
No se utilizó Codex Security, no se abrieron agentes y TestPyPI sigue limitado
a configuración. No hay publicación, cierre de Alpha, cambio a Beta ni
solicitud nueva a Robot antes de cumplir la condición del propietario.
