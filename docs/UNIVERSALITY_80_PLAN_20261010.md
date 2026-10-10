# Plan de avance técnico: 41/60 a 48/60 — 2026-10-10

Plan solicitado por el propietario. Se conserva la rúbrica
`UV-TECH-A11-60-v1`, sus sesenta definiciones y sus pesos. El punto de partida
es el [corte 41/60](UNIVERSALITY_TECHNICAL_PROGRESS_20261010.md), sobre los
artefactos A11 identificados allí. El objetivo es **48/60 = 80 % de avance
técnico en esa misma escala**, sujeto a resultados reales; no universalidad
absoluta, aceptación científica ni aprobación de licencia.

## Cinco pasos y siete comprobaciones pendientes

| Paso | Trabajo y aceptación previa a asignar puntos | Puntos objetivo |
|---|---|---|
| 1. Versiones Python | Instalar los mismos wheels A11 fuera del checkout en CPython 3.10, 3.11 y 3.13; comprobar metadatos, bytes instalados, dependencias, casos nativos y negativos. Registrar cada intérprete/plataforma y sus resultados propios. | 02.1, 02.2, 02.4: +3 |
| 2. Perfiles | Ejecutar base, arrow, pandas, polars, duckdb, engines, ml y all del núcleo; base, engines, ml, resources y all del benchmark. Cada perfil usa instalación aislada y con resolución normal, conducta positiva/negativa apropiada e inventario efectivo. Probar Windows x64 y Linux ARM64 disponibles, sin atribuir las veinte celdas a esos recibos. | 04.4: +1 |
| 3. Consumidor externo | Actualizar la aplicación del repositorio independiente al par A11, construir e instalar sus artefactos fuera de los checkouts y ejecutar el corpus congelado de 72 casos y las extensiones externas; comprobar hashes de las entradas antes/después y resultados esperados independientes. No atribuir independencia humana al uso de otro repo. | 07.5: +1 |
| 4. Tres dominios | Añadir al consumidor una matriz sintética de finanzas, comercio y telemetría con contratos y esperados propios, casos equivalentes, discrepantes y realmente inválidos. El rechazo debe deberse a datos/tipos inválidos y no solo a presupuesto agotado; los negativos no publican. | 08.4: +1 |
| 5. Avisos de dependencias | Congelar la unión de todas las dependencias/versiones efectivamente instaladas en los entornos A11 del alcance; consultar avisos públicos oficiales con paginación completa, fecha y recibos. Un error/consulta pendiente conserva cero; los avisos encontrados se informan y no se describen como un dictamen limpio. | 11.2: +1 |

La lista de perfiles se refiere a comprobar cada perfil definido; no cierra
04.5 (todos los mínimos/recientes y las celdas comprometidas) ni 10.5/12.5
(matriz nativa completa/aceptación independiente). Python no hereda pruebas
de otro intérprete, ni A11 las de A9/A10. El corpus y la nueva matriz sintética
conservan identidades diferentes.

## Ejecución y límites

- Se reutilizan Windows y la VM ARM64 existente. No se ejecuta GitHub Actions,
  publica en PyPI ni crea infraestructura o recursos de pago.
- Se mantienen los bytes del núcleo/benchmark A11; se amplía su evidencia.
  Los cambios funcionales previstos pertenecen a la aplicación consumidora.
- La ejecución se limita a procesos secuenciales por entorno, hilos acotados,
  límites cooperativos y guardias de disco. Los entornos y recibos quedan en
  un laboratorio privado fuera de Git; temporales de pytest en carpetas
  excluidas por el editor para evitar reintroducir los 412 cambios.
- Los recibos identifican artefactos, intérpretes, dependencias, comandos y
  estados observados. La documentación pública contiene resultados agregados,
  definiciones y hashes, sin corpus, bases, secretos ni recibos privados.
- Solo tras comprobar los resultados se publica un nuevo corte y se compara
  41/60 contra su numerador efectivo. El plan por sí mismo no suma puntos.

macOS, la matriz íntegra, operaciones/semántica aún incompletas, rollback en
todos los entornos, adopción humana y licencia/condiciones conservan sus
pendientes. No se reemplaza el criterio original de cierre UV01–UV12.

## Resultado comprobado

Plan ejecutado: **48/60 = 80 %**, con los siete puntos previstos demostrados
mediante recibos A11 propios. Los trece perfiles aprobaron en cada plataforma,
el consumidor ejecutó 72 casos del corpus congelado y 54 casos sintéticos en
cada una, y se completaron 258 consultas de avisos sin desconocidos.
El [informe final](UNIVERSALITY_80_RESULT_20261010.md) conserva resultados,
identidades, fallos previos y doce comprobaciones pendientes. El corte 41/60
permanece histórico y comparable; no se cambian los pesos para llegar a 80.
