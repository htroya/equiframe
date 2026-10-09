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
| Benchmark 3.10 x64 | 596 tests instalados PASS, sin bajar guardias | Cierre de pruebas común del núcleo + psutil; no cierre del lock de desarrollo propio del benchmark |
| Consumidor 3.12 x64 | 14 pruebas + 6 subcasos PASS | Implementación externa real de puertos/Polars y productor SQLite existente; sintético técnico |
| Corpus público congelado, consumidor 3.12 | 72 casos PASS: 24 aceptados, 48 rechazos esperados, 144 ejecuciones nativas | 219 registros; seis direcciones; esperado independiente; sin adopción humana/ciencia |

Las ejecuciones del mismo corpus no son muestras científicas independientes.
Se mantienen intentos anteriores fallidos: hashes de esquemas inicialmente
atrasados, wheel de raíz cacheado y una expectativa de posición de argumento
que se actualizó conservando la comprobación del Python solicitado. No se
cambiaron esperados semánticos ni guardias para obtener los pases.

El control de distribución íntegro del núcleo sigue parcial: el recorrido de
primera instalación encuentra metadatos públicos ausentes en caché en modo
sin red. El build aislado 3.10 encuentra la misma limitación con tomli. Se
reutilizaron bytes ya descargados donde existían, sin reconstruir metadatos,
retirar aislamiento, activar red alternativa o atribuir éxito a una etapa omitida.

## Avisos de dependencias: cobertura desconocida

El inventario 3.12 produjo 70 pares públicos y 140 consultas mínimas a PyPI/OSV;
ningún nombre privado, path, código, dato o cabecera de proyecto salió en ellas.
Hubo 19 respuestas completas (9 PyPI, 10 OSV), 118 errores de túnel HTTP 403,
dos respuestas JSON truncadas y una HTTP 502. No se probaron otras rutas tras
el bloqueo. Se conservan fecha, request/response y errores: **121 consultas
permanecen desconocidas**. La ausencia de avisos en esas 19 respuestas no
acredita ausencia de vulnerabilidades, cobertura íntegra ni auditoría exhaustiva.

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
