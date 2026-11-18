# Segunda revisión del paso 2 — EquiFrame 0.2.1

Revisión de ingeniería, 2026-09-28. Base: entrega 0.2.0 `0171663`.
El usuario autorizó integrar los cambios en `main`. El informe anterior se conserva
como evidencia histórica: [entrega 0.2.0](STEP_02_REVIEW.md).

## Hallazgos reproducidos y correcciones

| Área | Problema observado | Corrección y regresión real |
|---|---|---|
| Numéricos Pandas | uint64 máximo desbordaba al inferir int64; nullable Int8/Float32 se trataban como objetos | Usar almacenamiento nativo/ExtensionArray; 48 casos de anchos/signo y seis de máscaras Float32/64 en tres motores |
| Categorías y objetos | Categorías perdían diccionario/orden; int/float object se unificaban al inferir | Rechazo previo también en índices/etiquetas; conservar el dtype explícito del consumidor |
| Decimal | Decimal256 de precisión baja provocaba pánico Polars; escala negativa no admitida en motores | Rechazo de capacidades antes de convertir; Pandas conserva tipos representables |
| Tiempo Polars | timestamp[s] extremo se convertía en ms con wraparound | Comprobar límites int64 de la unidad destino; conservar bordes válidos |
| Tiempo DuckDB | Sentinels de infinito se exportaban como épocas finitas; zoned s/ms podía exceder us | Rechazar sentinels en entradas/salidas y validar rango antes de conversión; date32 mínimo finito conservado |
| Pánico nativo | PanicException Polars deriva de BaseException y escapaba sin manifiesto | Traducir el pánico específico a NativeEngineError y estado failed; prueba con pánico FFI real |
| Índices | Fuente nativa inyectada podía compartir buffers del índice/columnas | Copiar explícitamente ambos e intentar mutación directa de buffers en la regresión |
| Captura parcial | Fallo del índice tras publicar datos dejaba bytes sin referencia en el resultado | Retener artefacto parcial y nota en estado fallido; verificar todas las referencias publicadas |
| Presupuestos/limpieza | Buffers de índice sin límite; descarga inyectada fallida dejaba temporal | Comprobar índice antes de publicar; descarga dentro del bloque de limpieza |
| Contexto y recursos | Medición interna exitosa ocultaba la etapa posterior; cancelación setup DuckDB podía dejar conexión | Restaurar etapa padre; conexión real dentro del setup y del cierre garantizado |
| Puertos/manifiestos | Nombres/retornos externos y evidencias estructuralmente falsas no se validaban | Tipos runtime; huella del contrato, entradas, salida, formatos, nombres físicos y conteos coherentes |
| Cardinalidad | Algunas conversiones de tablas sin columnas perdían filas o fallaban opacamente | Conservar donde el motor retiene cardinalidad y rechazar explícitamente lo demás |
| Dependencias/distribución | El rango DuckDB incluía versiones sin to_arrow_table; el verificador fijaba 0.2.0 en una aserción | DuckDB mínimo 1.5.6; comprobar versión declarada al instalar el wheel |

Las regresiones están en
[`test_execution_regressions.py`](../packages/equiframe/tests/test_execution_regressions.py).
Se ejecutan Pandas, Polars y DuckDB reales. La instrumentación de setup/cierre abre
conexiones reales; los fallos de almacén prueban I/O y evidencia parcial.
No se normaliza la salida al contrato ni se modifica el diseño experimental.

## Verificación local

Windows x64, CPython 3.12.4. Lock: Pandas 3.0.6, Polars/runtime-32 1.44.2,
DuckDB 1.5.6, PyArrow 25.0.1, NumPy 2.5.3 y tzdata 2026.4.
Los rangos de metadatos no certifican todas sus combinaciones.

| Control | Resultado |
|---|---|
| Suite completa | 463 passed en 49.51 s; 198 casos del paso 1, 123 de la entrega inicial del paso 2 y 142 regresiones nuevas |
| Estilo/formato | Ruff sin incidencias; 34 archivos formateados |
| Tipado | mypy strict sin incidencias en 19 archivos src/tools |
| Assets | Nueve contratos/esquemas coinciden; no se cambia el formato 1.0 |
| Build | Wheel y sdist 0.2.1 construidos con backend del lock |
| Instalación limpia | Base y cinco extras verificados fuera del checkout; mínimo del README y ejemplos nativos ejecutados |
| Sdist instalado | 463 passed en 60.72 s; nueve assets; consumidor mypy externo; wheel reconstruido idéntico byte a byte |

El verificador de distribución instala base, arrow, pandas, polars, duckdb y engines
sin editable y fuera del checkout. Comprueba import ligero, CLI/API, ejemplos externos,
el mínimo del README ejecutado literalmente, consumidor mypy estricto y la suite
completa contra el wheel reconstruido desde el sdist. Compara todos los bytes del
wheel y regenera los assets. Los comandos están en el README del paquete.

## CI e integración en Git

La matriz usa Python 3.12 con estos runners:

| Sistema | Arquitectura |
|---|---|
| Ubuntu 24.04 | x64 |
| Windows Server 2022 | x64 |
| macOS 15 Intel | x64 |
| macOS 15 Apple Silicon | ARM64 |
| Ubuntu 24.04 ARM | ARM64 |

Todos ejecutan Ruff/formato, mypy, assets, pruebas nativas, build y el verificador
completo de distribución. Push y PR admiten ramas de cualquier colaborador.
[Evidencia y resultados de cada ejecución](https://github.com/htroya/equiframe/actions/workflows/equiframe.yml),
[checks de la revisión](https://github.com/htroya/equiframe/pull/12/checks).
La configuración de matriz por sí sola no acredita un check exitoso: cada run
conserva el commit, plataforma y conclusión verificables.

El flujo integra primero #11 y después #12 para conservar la dependencia entre
fundamentos y ejecución. El usuario autorizó explícitamente subir todo a `main`.
El README raíz presenta instalación, uso, capacidades y límites del producto.
La guía personal del equipo y el texto WhatsApp quedan fuera del repositorio.
El repositorio privado conserva su visibilidad; no se cambian planes ni se publican paquetes.

## OCI y límites

El [contrato técnico OCI](OCI_INTEGRATION.md) establece que DW, DuckDB real y
programa de conexión residen en la VM. EquiFrame podrá ejecutarse allí o recibir
snapshots por un proveedor externo. Esa integración necesita el servicio de datos,
los contratos de dominio y pruebas sobre el entorno real; sigue pendiente del paso 9.

Los runners GitHub temporales no son la VM OCI ni despliegan servicios. Los checks
Linux ARM64 ayudan a detectar incompatibilidad de arquitectura, sin certificar la
imagen, red o capacidad de RAM de la VM real.

Se mantienen los límites de callbacks cooperativos, memoria propia DuckDB,
checkpoints por tabla, falta de sandbox y ausencia de comparador/reglas/detectores.
completed solo acredita ejecución. Evidencia parcial significa captura fallida,
no tabla íntegra. No hay publicación PyPI ni resultados científicos añadidos.

El DOCX conserva SHA-256
`c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d`.
