# Revisión del paso 10

Fecha de implementación: 2026-10-03 UTC (2026-10-02 en Guayaquil).
Versiones: núcleo `0.9.0`, benchmark `0.10.0`. Base: merge del paso 9
`1fbcc7e16c7cc858eb86be1ba0acef85f4763b41`.

El Word ampliado se guardó y verificó antes de empezar el paso 10. Su SHA-256
es `45aaccd3d66da222389b1d153dca5fa23e5eef9cd0ec75c15c3d797ab955cbe1`;
125 páginas, 15 figuras, 17 tablas y 61 referencias. La revisión institucional
posterior pedida por Hernán es una entrega distinta: `tesis_final.docx`.

## Entrega técnica

- Sello técnico/científico con auditoría física, procedencia de selecciones,
  preprocesamiento/MAD/calibración, alcance y doce decisiones explícitas.
- Ejecución nativa de casos de test sin ajuste, conservación de fallos y
  reutilización de O únicamente tras reproducir el candidato revisado.
- Intersección evaluable común R/M/B/H, soporte propio, cobertura, estados
  pendientes y alertas parciales; precisión, recall, F1 y FPR con denominadores.
- AP con empates y familia/bundle homogéneos; bootstrap de grupos completos,
  justificación previa y réplicas indefinidas conservadas.
- Inferencia aislada de M, costes pareados sobre capturas, CPU/RSS observados,
  un warmup y cinco repeticiones; doce filas de coste sin agregación engañosa.
- Seis CSV regenerables, lectores que rechazan modificaciones rehashadas,
  bundle portable de fuentes/capturas y comparación de cinco contenidos lógicos.
- Inventario de distribución, CLI, esquemas, documentación y dependencias fijadas.

## Verificación local

Núcleo instalado fuera del checkout: **726 pruebas aprobadas** en 250,10 s.
El consumidor verificó base, Arrow, Pandas, Polars, DuckDB, los tres motores
juntos y ML; imports ligeros, API/CLI, consumidor tipado y reconstrucción de
wheel desde sdist byte por byte. 42 fixtures/esquemas verificados. Ruff y mypy
aprobaron; no se instaló EquiFrame permanentemente.

Benchmark instalado fuera del checkout: **437 pruebas aprobadas y 2 omitidas**
en 591,47 s. Las omisiones corresponden a enlaces simbólicos no disponibles
en este Windows. Ruff y formato de 54 archivos aprobados, mypy de 29 módulos
aprobado, 37 esquemas verificados. Imports ligeros, `pip check`, instalación
por nombre sin índice y reconstrucción idéntica del wheel desde sdist aprobados.
Las revisiones focalizadas ya comprobaron las tres implementaciones en cinco
familias, bloqueos finales, métricas conocidas, corrupción, cancelación,
recursos reales y reproducción sin fuentes originales disponibles.

La primera ejecución instalada detectó una prueba dependiente de las carpetas
del checkout. Se corrigió: el comando usa una fuente local explícita y el
consumidor copia las fuentes declaradas aparte de los módulos instalados.
Las 71 pruebas de distribución/comandos pasaron después. No fue un fallo de
publicación ni una excusa para omitir esas pruebas.

El ejemplo piloto produjo cinco escenarios, 35 candidatos pendientes, 15 perfiles
y cuatro grupos. El ejemplo de integración verificó sus seis comparaciones y
las sumas USD 30,75/EUR 7,00; conservó la alerta parcial de precisión de Pandas
y su salida 3, sin declarar aceptación del DW real. El nuevo ejemplo de evaluación
ejecutó seis casos de prueba nativos, exportó seis CSV y regeneró sus contenidos
desde el bundle con fuentes originales fuera de alcance. Su resultado fue
`table_regeneration=reproduced`, `confirmed=0`, `scientific=false` y repetición
externa pendiente. Es una comprobación técnica sintética.

El inventario de ambos wheels coincidió con los metadatos y las dependencias
de sus fuentes. El lector deja `publication_ready=false` y el nombre PyPI en
estado desconocido; su alcance no incluye incorporar la evidencia externa de
build/instalación que se describe arriba.

| Artefacto | SHA-256 |
| --- | --- |
| `equiframe-0.9.0-py3-none-any.whl` | `f08b0f543f97792551f3a4e6dc78aa0bd15d8b31c27352864153dcc98094d2bc` |
| `equiframe-0.9.0.tar.gz` | `bf01cab20811b95707856e519d2b220cac78b406a0ea7302ebf68464a46dc44a` |
| `equiframe_benchmark-0.10.0-py3-none-any.whl` | `898be894486d7e85bc06620d5dc4be52979ff5da1e5368566a528f88488247d0` |
| `equiframe_benchmark-0.10.0.tar.gz` | `611d59890f69d5824e847c96c650bbd3c3779723f5c74892088211b055a1ba7b` |

## Correcciones de revisión

Las revisiones independientes detectaron y corrigieron alcance de evaluación
incompatible antes de ejecutar, diagnóstico de sellos bloqueados, diferenciación
de evidencia corrupta frente a configuración inválida, confirmación de completitud
en CLI, presupuesto JSON antes de cargar el registro, pins de bytes antes de
publicar, conservación de sintaxis absoluta Windows/POSIX y contradicciones entre
recibos embebidos y originales. Los replays que autorizan una etiqueta confirmada
se comprueban contra las filas capturadas, además de sus hashes/manifiestos.
Esto verifica consistencia; no convierte hashes en autenticación de personas.

## Límites de aceptación

La ingeniería ejecutable se entrega con sus comprobaciones. La aceptación
científica del paso permanece abierta: cliente/snapshot SERCOP/DDL no disponibles,
cohorte y decisiones sin resolver, revisiones humanas, soporte normal por grupos,
experimento H1–H3 y repetición auténtica por otro integrante pendientes. No se
autogeneran esas evidencias. Las revisiones ficticias de tests no cuentan como O
del corpus y el ejemplo entregable conserva cero confirmaciones científicas.

Actions sigue `disabled_manually`; YAML solo permite despacho manual optativo.
**No hubo runs remotos de esta versión.** Los éxitos de pasos 8/9 son históricos.
No se certifican nuevos ARM64/macOS/Linux por estos controles Windows/Python 3.12.
Licencia y control del nombre se registran como pendientes; no se reservó ni
publicó en PyPI. La publicación sigue prevista para el paso 19.

[Diseño](STEP_10_DESIGN.md), [métodos y fuentes](STEP_10_EVALUATION.md),
[distribución](STEP_10_DISTRIBUTION.md) y [decisiones A89–A95](DECISIONS.md).
