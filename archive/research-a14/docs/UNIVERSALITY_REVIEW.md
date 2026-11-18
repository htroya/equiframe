# Universalidad R2 — corte técnico intermedio A9

Fecha: 2026-10-09 UTC. **No es cierre al 100 % ni integración final en main.**
El universo y las veinte celdas se fijaron antes de ampliar pruebas en
[UNIVERSALITY_PLAN](UNIVERSALITY_PLAN.md). Madurez, usabilidad y ciencia mantienen
sus puertas independientes.

## Identidad y mejoras implementadas

- Base remota observada: `479838316111cc47287153ca315d3f69b5c00d7f`, árbol
  `06654c9e90f34f257b3ed2a8844b6c8b64a18d2a`; A8 ya estaba integrado
- Fuente congelada de A9: `95d74a0e304790b347750451de75e9101b1f1b33`, árbol
  `e8d1222659bef1d9cf1fe6cfdbd2a3fe9c83b1b5`. Los cambios posteriores de guía
  no modifican los artefactos o scripts de ese candidato
- Núcleo/benchmark `0.12.0a9`; consumidor separado `0.1.11`, fuente
  `86b76301d0f9a298c8f3a4c1add6a8c7f1a25e33`, fuera de este repositorio
- Typing-extensions directo en benchmark y lock regenerado **offline** tras
  resolución de requisitos públicos mínimos. Ninguna versión pública del lock
  propio de cada paquete cambió respecto de su base A8
- Runner/revisor existente ampliado a cuatro Python, esquema 2; esquema 1 conserva
  exactamente su alcance histórico de dos versiones. Se añaden identidad de
  tooling/controlador/datos y comprobación final de integridad
- Transporte opcional parametrizado, ZIP cerrado, rutas con espacios, host fijado,
  recogida tras error/timeout y rechazo de éxito sin evidencia. El recorrido
  solicitado actualmente es **directo en Linux ARM64 de OCI con Codex en VS Code**;
  no requiere ejecutar Windows ni fabricar un recibo de transporte inexistente
- Capacidad IR documentada según implementación existente, sin atribuir right/full,
  cardinalidad, selección determinista o timestamps a este cambio
- Preparación offline de consultas, allowlist exacta, cuerpo/URL/cabeceras mínimas,
  rechazo de redirects y de procedencia ambigua. Un registro público por sí solo
  no autoriza enviar un nombre interno
- El arnés ahora reinstala también la raíz: se reprodujo y corrigió la reutilización
  de un wheel local de igual versión que conservaba un registro anterior

## Resultados observados al corte

| Recorrido | Resultado | Alcance y límite |
|---|---|---|
| Herramientas del puente | 53 unitarias, PASS en 3.10/3.11/3.12/3.13 x64 | Transporte simulado; no ARM64 funcional |
| Privacidad/inventario | 62 pruebas PASS | Incluye transporte HTTP simulado, no cobertura de avisos |
| Registro/arnés de candidato | 106 pruebas focalizadas PASS | Conserva selección de intérprete y refresh de raíz |
| Núcleo CPython 3.10.22 x64 | 4.499 tests PASS | Wheel congelado, corpus de tests extraído del sdist |
| Núcleo CPython 3.11.17 x64 | 4.499 tests PASS | Suite de fuente; payload instalado cotejado con wheel |
| Núcleo CPython 3.12.14 x64 | 4.499 tests PASS | Suite de fuente; payload instalado cotejado con wheel |
| Núcleo CPython 3.13.5 x64 | 4.499 tests PASS | Suite de fuente; payload instalado cotejado con wheel |
| Benchmark 3.12 x64 | Nueve controles PASS; 596 fuente e instalados | Identidad de sus propios artefactos; no otras celdas |
| Benchmark 3.10/3.11/3.13 x64 | 596 tests instalados PASS en cada Python, sin bajar guardias | Cierre de pruebas común del núcleo + psutil; no cierre de su lock de desarrollo propio |
| Consumidor, cuatro Python x64 | 14 pruebas + 6 subcasos PASS en cada versión; recuperación -O PASS | Implementación externa real de puertos/Polars y productor SQLite existente; sintético técnico |
| Corpus público congelado, cuatro Python x64 | Por versión: 72 casos PASS, 24 aceptados, 48 rechazos esperados, 144 ejecuciones nativas | Los mismos 219 registros y 72 casos; seis direcciones; esperado independiente |
| Tipos físicos inválidos adicionales | 12 casos por Python, 48 PASS bajo -I -O | Finanzas/telemetría × seis direcciones; entrada string en campo Decimal/Timestamp; no se inicia ejecución nativa |
| Tipado estricto 3.10 | 92 archivos core y 36 benchmark, PASS | Control real, no simple aceptación de sintaxis |
| Rebuild adicional 3.10 | Wheel/sdist del núcleo idénticos a los congelados | Backend exacto ya instalado; este ensayo no aislado no reemplaza instalación aislada de sdist |
| Medición A9 3.12 x64 | 100/1000 filas ×3 correctas; límite pequeño devuelve not_evaluable | Estado parcial, exit 3: io_counters_unavailable:AccessDenied; overlay observado, sin SLO/cuota RSS dura |

Las ejecuciones del mismo corpus no son muestras científicas independientes.
Se mantienen intentos anteriores fallidos: hashes de esquemas inicialmente
atrasados, wheel de raíz cacheado y una expectativa de posición de argumento
que se actualizó conservando la comprobación del Python solicitado. No se
cambiaron esperados semánticos ni guardias para obtener los pases.

El control de distribución íntegro del núcleo sigue parcial: el recorrido de
primera instalación encuentra metadatos públicos ausentes en caché en modo
sin red. El build aislado 3.10 encuentra la misma limitación con tomli. Se
reutilizaron bytes ya descargados donde existían, sin reconstruir metadatos,
sustituir el control aislado por otro sin aislamiento, activar red alternativa
o atribuir éxito a una etapa omitida.

Se materializó y verificó el kit original A7: sus seis hashes coinciden con su
manifiesto. Su core tiene identidad distinta del A7 de usabilidad requerido por
el replay existente; no se intercambian wheels homónimos. El A7 de usabilidad
está identificado y disponible como antecedente privado. La limitación actual
del replay offline A7→A9→A7 es el wheelhouse público original ausente, no la
disponibilidad del archivo A7. Hay entradas de caché uv ya extraídas, pero no se
reempacan como wheels originales ni se inventa su procedencia. Los 42 comandos
históricos A7→A8 no se atribuyen a A9. El preflight conserva el inventario de
archivos públicos requerido y no modifica el hash esperado del arnés.

## Avisos de dependencias: cobertura desconocida

El inventario 3.12 produjo 70 pares públicos y 140 consultas mínimas a PyPI/OSV;
ningún nombre privado, path, código, dato o cabecera de proyecto salió en ellas.
Hubo 19 respuestas completas (9 PyPI, 10 OSV), 118 errores de túnel HTTP 403,
dos respuestas JSON truncadas y una HTTP 502. No se probaron otras rutas tras
el bloqueo. Se conservan fecha, request/response y errores: **121 consultas
permanecen desconocidas**. La ausencia de avisos en esas 19 respuestas no
acredita ausencia de vulnerabilidades, cobertura íntegra ni auditoría exhaustiva.

El inventario se regeneró y verificó offline contra el wheel/sdist finalmente
entregados. Inputs, componentes, perfiles y entorno son idénticos al inventario
consultado; cambiaron solamente la identidad del sdist y sus SBOM. El mapeo
conserva las respuestas originales, fechas y límites, sin reescribirlas como una
consulta nueva. Otros entornos, componentes del benchmark y binarios vendorizados
no heredan cobertura por este cotejo.

## Puente y condiciones de cierre

El kit original tiene manifest
`8d9dee522703875fd0c7bea35110152a7be32e10b544c4764ed88f101a2a696e`.
La edición DOC2 corrige solo la guía y tiene manifest
`1017a0147d66d49ffeb4369104712a33496a16fddefa9318e096df0846706f4b`.
Los seis artefactos y scripts son idénticos entre ambas. Cada recibo se revisa
contra su propio kit original; no se exige repetir un laboratorio iniciado por
un cambio exclusivamente documental. Los ZIP y datos/evidencias permanecen
fuera de Git.

Pendientes: recibos ARM64 de las cuatro versiones, celdas nativas Windows/macOS,
los extremos/perfiles no completados, cobertura de avisos y controles de
instalación pendientes. No se ha habilitado o disparado Actions, publicado en
PyPI/TestPyPI, desplegado servicios, cambiado el DW ni integrado la ampliación
como completa en main. La revisión final actualizará UV01–UV12 con sus
subobligaciones completas; una fila parcial no suma al índice.

## Correspondencia de fuente, rama y artefactos

La rama `universalidad/r2-main-20261009` se publicó inicialmente como
`ef22886b388dbae44ccffa24d5452f65d1c34a75`, hija de main `4798383`, con árbol
`e954446ddce3615fd374b78ef7bab98f42412995`: idéntico al checkout local
`79afaaa2513fb02689a718d49009b8046c76af8d`. Sus 59 cambios y 727 archivos se
cotejaron; no incluye consumidor separado, artefactos o expediente privado.
Las actualizaciones posteriores de este corte afectan solamente estos dos
documentos raíz; no cambian distribuciones, scripts ni los kits ya entregados.
El recibo de publicación conserva el SHA remoto exacto y la comprobación de main.

| Artefacto congelado | SHA-256 |
|---|---|
| core wheel | `7ea6841cd6d8c6685466921ac8ca2bdfa16b0ee6e7483b9a2c01e1b0f6a3206b` |
| core sdist | `d0521134bc2224e32b65515936f3853828e7f3affaf7e56962b3273b1f68e342` |
| benchmark wheel | `66e282e4040e8dc028b42010e1811e05006c3cc2e5d8c8930f0ca26d6e58ae18` |
| benchmark sdist | `59a064fd91f4a2f2869111260525f34f4c9f9875dee26793773ec201bb7c7c0a` |
| consumidor wheel | `bd38930d22443e7ed5cb658e0055d46064bca877f34ad58fd7d42ddd24ef17df` |
| consumidor sdist | `7cb42b4b4d1240b49ad3466884662b2f0fda53cb5d3fbbd80b8dee5a8398db7f` |

La [matriz actualizada](UNIVERSALITY_MATRIX.md) acredita **3/12 criterios (25 %)**:
UV01, UV07 y UV08. Hay ejecución funcional en cuatro de veinte celdas, ninguna
íntegra todavía. No se reduce el denominador por runners ausentes.

## Próximos controles y dependencias

1. Revisar los recibos OCI cuando lleguen, contra el manifest exacto utilizado,
   las cuatro versiones, negativos, logs e inventario. El recorrido directo con
   Codex en VS Code registra operador/contexto real; no exige transport.json de
   un launcher Windows que no se utilizó
2. Completar instalaciones aisladas, perfiles/extremos y replay cuando se disponga
   de los artefactos/metadatos públicos genuinos faltantes. No repetir suites ya
   ligadas a los mismos bytes por rutina ni reabrir las rutas de red bloqueadas
3. Ejecutar los runners nativos Windows/macOS pendientes; el YAML preparado no
   los ejecuta. Revisar límites semánticos con cada combinación comprometida;
   una capacidad faltante necesaria exige implementación nativa y regresión,
   no un cambio del esperado o de la etiqueta de cobertura
4. Completar cobertura pública autorizada y revisar errores/hallazgos. La medición
   íntegra necesita acceso efectivo a los contadores; el parcial actual no se
   transforma en éxito por omitir el instrumento
5. Solo tras esas puertas: reconciliar main real, integrar sin fuerza y reconstruir
   el candidato integrado. Una publicación de rama no cumple UV12
