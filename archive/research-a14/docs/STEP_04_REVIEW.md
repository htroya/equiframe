# Paso 4 — reglas R y catálogo técnico

Entrega local 0.4.0, 2026-09-30, rama `hernan/step-04-rules`, basada en
`4643e5e` (`hernan/step-03-comparison`), por lo que incluye el paso 3 aún no
integrado en `main` al iniciar este trabajo. El árbol inicial estaba limpio.
No se modificó el DOCX ni las carpetas de José/Jhair.

## Funcionalidad y corrección heredada

`ef.evaluate_rules` usa contrato, opciones fijas y los artefactos de una sola
ejecución capturada. Verifica identidad/integridad y evalúa las seis formas de
regla y precondiciones con registro explícito. Registra estados por chequeo,
hallazgos JSONL completos, resumen acotado, cobertura, prioridad, límites y
cancelación cooperativa. Una alerta observada permanece aunque la evaluación
sea incompleta. [Semántica y uso](RULES.md),
[API](API_CONTRACTS.md#10-reglas-r-disponibles-en-040) y
[ejemplos](../packages/equiframe/examples/README.md#reglas-r-del-paso-4).

La regresión del paso 3 altera `counts.right_rows` de 1 a 2 conservando
`matched_rows=1` y `state="equivalent"`; `read_comparison` ahora rechaza el
manifiesto. También exige coherencia de `strategy/selected_key`. La lectura del
manifiesto es validación estructural; `iter_differences` y
`iter_rule_findings` verifican los bytes SHA-256/tamaño de sus JSONL.

El catálogo suplementario 1.0 conserva los cinco contratos anteriores sin
cambiar sus bytes. Fija ID/revisión/huella, reglas, implementación, opciones,
cobertura declarada y limitaciones. El ejemplo del intercambio de montos
demuestra un límite de reglas que controlan solo esquema y suma global;
`compare` detecta el intercambio. No se atribuye el resultado a todos los
contratos. La estadística de conversiones fallidas antes de la captura exige
evidencia adicional: no se infiere de la salida.

## Verificación observada

Windows x64, Python 3.12.4. Los comandos siguientes usaron
`packages/equiframe/.venv` preexistente con dependencias del lock; `uv` no está
instalado en el entorno de esta sesión.

| Control | Resultado observado |
|---|---|
| `.venv/Scripts/ruff check --no-cache .` | Sin incidencias |
| `.venv/Scripts/ruff format --check --no-cache .` | 47 archivos formateados |
| `.venv/Scripts/mypy --cache-dir rule-mypy-cache src tools` | Sin incidencias en 25 archivos de fuente/herramientas |
| `.venv/Scripts/python tools/generate_assets.py --check` | 18 assets correctos; 13 anteriores sin modificación |
| `.venv/Scripts/pytest -q` | **558 passed en 94,29 s** |
| `.venv/Scripts/python -m build --no-isolation` | Wheel y sdist 0.4.0 construidos |
| Inspección tar/zip | 70 entradas en sdist, 28 en wheel; código R, catálogo, esquemas y `py.typed` presentes |
| Wheel instalado fuera del checkout | `import equiframe as ef` desde site-packages y `pip check` correctos; importación base sin motores/Arrow/NumPy cargados |
| Cinco capturas sintéticas desde wheel | `no_alert` en `nulls_types`, `joins`, `duplicates_order`, `aggregations`, `dates` con PyArrow 25.0.1 del entorno bloqueado |
| Relectura de `run.json` desde wheel | `no_alert`, cobertura completa, ningún módulo Pandas/Polars/DuckDB cargado |

El consumidor externo fue una venv nueva sin paquetes del sistema, con wheel
0.4.0 instalado sin editable; para usar las versiones exactas bloqueadas se
añadió temporalmente la ruta de site-packages de `.venv` como dependencias de
solo lectura. No se instalaron los tres motores en esa venv. Esta prueba no
equivale al verificador runtime-only que crea `uv`.

`tools/verify_distribution.py` se intentó ejecutar y terminó antes de iniciar
sus perfiles: `uv executable not found`. Por ello sus pasos de reconstrucción
idéntica desde sdist, instalación runtime-only de cada extra y suite desde
site-packages quedan pendientes; no se presentan como controles pasados. El
lock solo cambia la versión propia 0.3.0→0.4.0, sin modificar dependencias.

## Segunda revisión del paso 4

Se revisaron de nuevo las rutas de evaluación y relectura del manifiesto. Se
encontraron y corrigieron tres casos, cada uno con una prueba de regresión:

- La relectura aceptaba una decisión o una marca de completitud contradictoria
  con los chequeos. Ahora valida ambos valores derivados.
- Una precondición verificablemente falsa quedaba eclipsada por otra no
  evaluable. La regla dependiente queda `not_applicable` con el motivo falso.
- Un tipo Arrow transportable cuya zona horaria no puede interpretarse para el
  contrato hacía `not_evaluable` el chequeo de esquema. Ahora produce el
  hallazgo `schema_type`.

La nueva ejecución observada en Windows x64 con Python 3.12.4 pasó **561
pruebas** en 99,02 s; Ruff, formato de 47 archivos, mypy en 25 archivos,
los 18 assets generados y `python -m build --no-isolation` también pasaron.
Se reinstaló el wheel 0.4.0 en el consumidor externo sin editable y las cinco
familias sintéticas del catálogo dieron `no_alert`; `pip check` pasó. Ese
consumidor aún toma las dependencias bloqueadas de la `.venv` del proyecto;
no sustituye la verificación runtime-only pendiente por falta de `uv`.
La huella de implementación del catálogo se regeneró tras corregir `rules.py`.

## Alcance y entrega remota

Contratos, artefactos y ejecuciones 1.0 siguen intactos; los documentos de R
usan formato suplementario 1.0. El catálogo es técnico/sintético, no benchmark
revisado, oráculo, congelación experimental final ni validación del DW. R no
reconstruye el ETL completo, no prueba la corrección de un join proyectado por
la salida si el contrato solo declara relaciones de entrada, y no calcula
conversiones fallidas que la captura no registra. Los límites son cooperativos;
no hay cuota RSS ni timeout duro de lectura Arrow.

El intento de `git push -u origin hernan/step-04-rules` devolvió
`remote: Repository not found` para `https://github.com/htroya/equiframe.git`.
`gh auth status` informó tokens inválidos para `labinv` y `htroya`; con este
acceso no se puede distinguir entre un repositorio no disponible y un rechazo
por autenticación. La rama/PR y los checks del SHA remoto quedan pendientes.
Ningún PR se fusiona.
Los pasos 5–10, la publicación PyPI y la integración OCI conservan sus etapas.
