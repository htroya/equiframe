# Continuación local de universalidad A10

Base GitHub comprobada el 2026-10-09: `c9ded729835490a99d9d2110b05682c0c611e154`.
Esta continuación conserva el denominador de doce criterios y veinte celdas de
`UNIVERSALITY_PLAN.md`. A10 es un candidato privado en validación; no acredita
100 %, publicación, aceptación humana ni resultados científicos.

## Cambios en revisión

- Captura DuckDB: cerrar el writer Arrow antes de sincronizar por el descriptor
  writable original, incluyendo el footer en el presupuesto. Corrige el fallo
  de fsync al reabrir en modo lectura en Windows.
- Medición: implementación y contratos explícitos por plataforma; contadores
  ausentes siguen indisponibles. No se inventan límites duros ni SLO.
- Laboratorio: intérprete solicitado, instalación del par exacto, perfiles y
  extremos, optimización observada, aislamiento y recuperación verificables.
- Controladores Actions: candidato único y hashes, veinte celdas nativas,
  inventario completo de evidencia y agregación que rechaza celdas ausentes.
- Fixtures históricos: Git preserva bytes, sin conversiones automáticas EOL.
- Cancelación Windows: terminar el árbol del proceso propio; la ruta POSIX
  conserva su grupo privado. No se usa killpg en Windows.
- Tests del arnés: separar modos normal/optimizado y usar rutas de fixtures
  válidas en el sistema anfitrión. Los controles de Bash/AlmaLinux se ejecutan
  únicamente en POSIX; no acreditan un instalador Bash nativo de Windows.
- Kits OCI: incluir los tres manifiestos de tests y pasar el del núcleo al
  verificador A10. Los archivos se comparan con cada sdist; la revisión exige
  identidades JUnit exactas y las dos omisiones exclusivas de Windows en Linux.
- Entornos POSIX: conservar la entrada del venv aunque sea un enlace válido
  al intérprete, para no ejecutar accidentalmente el Python global.
- Revisión desde Windows: interpretar las rutas de los recibos Linux como
  POSIX y mantener separadas las rutas del inventario y del disco local.
  Se rechazan rutas de otro laboratorio y traversal; no se normalizan los
  nombres de miembros para ocultar diferencias del inventario.
- Contadores Linux: conservar la última muestra acumulada completa cuando
  `/proc/PID/io` desaparece o deniega acceso tras confirmar la terminación del
  hijo propio. Una denegación mientras vive, una muestra previa incompleta o
  contadores malformados siguen siendo fallos explícitos.

## Evidencia inicial ejecutada

Controles de estilo, formato, tipado y assets del core/benchmark pasan. El tipado
estricto revisó 92 archivos de core, 36 de benchmark y cinco controladores.
Los controladores tienen 25 tests y 46 subcasos aprobados. Las herramientas de
handoff tienen 78 tests y 30 subcasos aprobados. El foco de recursos tiene
84 tests aprobados y cinco omisiones explícitas de comportamientos POSIX/Linux
en Windows, con sus sustitutos Windows comprobados por la suite.

Tras corregir la conexión de manifiestos del kit OCI, las herramientas de handoff
tienen 86 tests y 35 subcasos aprobados en Windows. Una prueba adicional de enlaces
de intérprete requiere POSIX; su ejecución real se registra más abajo.
Los manifiestos congelados de 4506, 617 y 16 casos coinciden con todos los bytes
de las pruebas de los tres sdists entregados.

En Linux ARM64 se ejecutaron 18 controles de repositorio sin omisiones y las
87 pruebas del arnés del commit `aae584b`: 86 aprobadas y una omisión exclusiva
de APIs Win32. La regresión de enlaces POSIX pasa realmente en esa VM.
La corrección posterior de rutas del revisor tiene 66 pruebas y 29 subcasos
aprobados en Windows; una prueba de enlaces exclusiva de POSIX se omite allí.

Los inventarios de dependencias ligados a los seis artefactos locales tienen
134 consultas core y 124 benchmark completas a PyPI/OSV, cero consultas
desconocidas y cero avisos conocidos. Se verificaron offline contra artefactos,
locks y entornos registrados. Este resultado corresponde a Windows CPython
3.12 y versiones exactas; no cubre otros entornos, bibliotecas nativas incluidas
ni sustituye la decisión de licencia del propietario.

Los inventarios se regeneraron para los artefactos reconstruidos del núcleo.
Se comprobaron sin red: dependencias públicas, declaraciones, locks, entorno y
evidencia de licencias permanecen idénticos. La diferencia es documental y está
ligada a hashes nuevos de artefactos/SBOM; las respuestas de avisos y sus fechas
originales se conservan mediante una relación explícita, sin presentar un nuevo
escaneo ni ampliar su alcance a otras plataformas.

La ejecución histórica A9 de OCI terminó con código 1. Sus recibos se conservan.
Los intentos locales previos de A10 tampoco se relabelan como éxitos: quedaron
detenidos por inventario de tests desactualizado y diferencias del contrato
entre el colector y el controlador local. Los intentos corregidos usan salidas
nuevas y los mismos hashes de distribuciones, sin cambiar expectativas de datos.

## Corrección comprobada en la VM

El laboratorio A10 con 617 casos benchmark conserva el fallo observado en
CPython 3.10: 614 aprobados, dos omisiones exclusivas de Windows y un fallo al
leer `/proc/PID/io` del hijo terminado. Una observación separada confirmó el
estado zombie y la terminación del hijo propio mediante `waitid(WNOWAIT)`;
existían cuatro contadores acumulados válidos medidos mientras vivía.

La corrección añade diez regresiones que distinguen esa carrera de una
denegación real o datos inválidos. El módulo completo tiene 59 pruebas aprobadas
y cinco omisiones POSIX/Linux en Windows; en un entorno nuevo de la VM ARM64,
con el wheel corregido instalado, pasa 62 pruebas y las dos omisiones exclusivas
de Windows. Se verificaron los bytes instalados de 120 archivos core y 35
benchmark contra ambos wheels, y el archivo de tests contra el manifiesto.
No se cambió el candidato de la ejecución histórica en curso.

El benchmark corregido congela 627 casos; sus artefactos tienen hashes nuevos.
La suite completa se ejecutó en un entorno nuevo Linux ARM64 CPython 3.10:
625 aprobadas, dos omisiones exclusivas de Windows, cero fallos y cero errores.
Las 627 identidades JUnit se compararon exactamente con el manifiesto; todos
los archivos devueltos se verificaron por tamaño y SHA256. El siguiente kit
incluirá ese manifiesto. Los 617 casos y 40 perfiles históricos no se atribuyen al wheel
corregido. El inventario nuevo conserva las mismas dependencias públicas,
declaraciones, locks y metadatos del entorno registrado; la relación con las
respuestas originales mantiene sus fechas. Esto no es una auditoría del código
modificado ni una nueva consulta de vulnerabilidades.

## Diagnóstico de la ejecución manual Windows

Los intentos completos CPython 3.10 y 3.11 registraron, cada uno, 4449 pruebas
aprobadas, 32 fallos y 25 omisiones, sobre 4506 casos. El controlador privado
omitía herramientas de desarrollo declaradas por el sdist. Tras instalarlas en
esos entornos ya inactivos, el módulo completo de manifest de release pasó sus
75 pruebas en cada intérprete. Esa verificación focal no convierte las suites
anteriores en éxitos completos.

La máquina Windows no permite crear enlaces simbólicos: 24 omisiones no están
admitidas por el contrato de la celda; la otra requiere FIFO POSIX. El nuevo
controlador comprueba esa capacidad antes de invertir tiempo en una suite
completa. No se cambió la configuración global ni se amplió la lista de skips.
Los intentos incompletos de 3.12 y 3.13 se interrumpieron conservando sus recibos.

## Continuación manual sin costos adicionales contratados

El usuario indicó ejecutar todo manualmente y evitar acciones que originen
gastos. No se disparó Actions, no se creó un token y el workflow de matriz volvió
a su estado `disabled_manually`. Las tres variables añadidas para Actions se
retiraron. La validación continúa mediante SSH en la VM existente y comandos
locales; no se contrataron runners, máquinas ni servicios nuevos.

Los dos repositorios independientes autorizados se crearon privados y contienen
los commits exactos ya comprobados:

| Repositorio | Commit publicado en `main` |
|---|---|
| [htroya/equiframe-consumer-validation](https://github.com/htroya/equiframe-consumer-validation) | `5ac90c9fa2f196a11c178376653056d561e88699` |
| [htroya/equiframe-universality-data](https://github.com/htroya/equiframe-universality-data) | `e8e17976dfa2c36a5cbcf4c2ec183469a73adbc7` |

El corpus conserva su manifest, procedencia y condiciones, incluida la limitación
de Treasury; su publicación privada no resuelve esa limitación. No se transfieren
llaves, credenciales, entornos ni recibos privados al repositorio principal.

Los recursos disponibles acreditan pruebas nativas en Linux ARM64 y pruebas
parciales en Windows x64. No se encontró un motor Linux x64 utilizable: la única
distribución WSL registrada es `docker-desktop`, detenida y sin el CLI de Docker.
No hay acceso disponible a macOS Intel o Apple Silicon. Esas celdas quedan
pendientes y no se reemplazan por emulación ni se retiran del denominador.

El usuario confirmó que todavía no existe una licencia aprobada. UV11 conserva
ese bloqueo; no se elige una licencia ni se atribuye una aprobación a titulares
no identificados. Se continuará con el trabajo técnico disponible sin nuevas
preguntas. El cierre final deberá registrar evidencia efectiva de UV01–UV12;
esta continuación no acredita universalidad al 100 %.
