# Paso 3 — normalización autorizada y comparación completa

Entrega de ingeniería 0.3.0, 2026-09-30, issue #3. Base verificada y actualizada:
`751063580fda5c072e693f0c51e4c80bb677ee96`, rama
`hernan/step-03-comparison`. Cuenta GitHub `htroya`, remoto
`https://github.com/htroya/equiframe.git`, árbol inicial limpio. No se alteró
trabajo ajeno, el DOCX ni componentes de José/Jhair.

## Funcionalidad entregada

API pública `ef.compare` y modelos completos, comparación sin volver a ejecutar
ETL, fuentes locales Arrow/Parquet y evidencia de ejecuciones verificada. Detecta
valores asociados a entidades equivocadas aunque conserven totales, cambios de
esquema, multiplicidades, ausencias, claves, orden y precisión. Aplica únicamente
políticas autorizadas; conserva observación y esperado por separado.

Secuencias, claves comprobadas, multiconjuntos exactos y matching máximo para
tolerancias. Lectura por lotes, índices SQLite privados en disco, presupuestos y
cancelación cooperativa. Diferencias completas tipadas, snapshots y manifiestos
aislados, con resumen limitado sin truncar el análisis.

Uso y decisiones precisas: [Comparación](COMPARISON.md),
[API](API_CONTRACTS.md#9-comparación-disponible-en-030),
[consumidor Arrow](../packages/equiframe/examples/compare_local.py),
[motores y esperados independientes](../packages/equiframe/examples/execute_native.py).
`ef.compare(candidate, expected, contract=contract, reference="expected")`
acepta `ArrowInput`, referencias/archivos locales y resultados ya capturados.

## Evidencia anterior y timeout

La revisión local comunicada por el usuario obtuvo **462 passed y un fallo** en
`test_callback_timeout_is_cooperative_and_returns_after_callback`; su repetición
aislada pasó. Esa observación no se sustituye por el resultado histórico distinto
del informe 0.2.1. La CI del commit base se volvió a consultar: los cinco jobs
finalizaron con éxito en la
[ejecución 36497266012](https://github.com/htroya/equiframe/actions/runs/36497266012).

El presupuesto global de 50 ms podía vencer antes de iniciar el callback.
La prueba ahora controla el reloj: el callback empieza antes del vencimiento,
avanza el reloj más allá del deadline, termina y solo después vuelve execute con
timeout. Una prueba separada vence el presupuesto antes del callback e impide
que empiece. No se desactiva timeout ni se aumentan sleeps.

## Verificación local de la entrega

Windows x64, CPython 3.12.4, dependencias del lock: Pandas 3.0.6, Polars 1.44.2,
DuckDB 1.5.6, PyArrow 25.0.1, NumPy 2.5.3 y tzdata 2026.4. El lock solo cambia
la versión propia 0.2.1→0.3.0; no se actualizan dependencias para hacer pasar casos.

| Control | Resultado observado |
|---|---|
| Ruff | Sin incidencias |
| Formato | 41 archivos comprobados |
| mypy strict | Sin incidencias en 23 archivos src/tools |
| Assets | 13 fixtures/esquemas; los nueve anteriores conservan sus bytes |
| Comparación | 74 casos dentro de la suite final, con propiedades y motores reales |
| Suite completa final | 538 passed en 74.77 s |
| Build | Wheel y sdist 0.3.0 construidos con backend del lock |
| Distribución instalada | Base y cinco extras verificados fuera del checkout; ejemplos y API/CLI correctos |
| Sdist / wheel reconstruido | 538 passed en 81.25 s; wheel idéntico byte a byte; 13 assets y consumidor mypy correcto |

La suite incorpora 74 casos de comparación más la nueva distinción de timeout,
sobre los 463 casos anteriores. Las propiedades generan casos adicionales dentro
de esos tests; no se contabilizan como escenarios científicos. Matching se compara
con un control exhaustivo independiente de permutaciones pequeñas, sin atribuir
transitividad a la tolerancia.

La revisión final incorporó regresiones para claves repetidas que son ausencia
autorizada (vacío, cero y NaN). Con `incomplete=allow` permanecen en el multiconjunto
y no producen un falso incumplimiento de unicidad previa a la normalización.

`tools/verify_distribution.py` comprueba base y los extras arrow, pandas, polars,
duckdb y engines desde entornos runtime-only fuera del checkout: import ligero,
API/CLI, ejemplos de comparación sin otros motores, ejemplos nativos con esperados,
15 comparaciones entre parejas en las cinco familias, mínimo literal del README,
reconstrucción del wheel desde sdist idéntica byte a byte, suite contra site-packages,
assets y consumidor mypy. El control completo terminó correctamente.

## Formatos, ciencia y límites

Paquete **0.3.0**; contratos/artefactos/ejecuciones **1.0** intactos; revisión de
contrato independiente. Nuevos documentos de comparación **1.0**, con autorización
suplementaria y huella propia. No se interpreta el formato anterior como permiso
para ignorar columnas, índices o tipos. Decisiones A33–A40 y especificación normativa
en [Comparación](COMPARISON.md).

Alcance `output_schema`: no ejecuta R/precondiciones operativas ni perfiles/M/B/H.
Un esperado inválido se distingue de divergencia y fallo técnico. Coincidencia
entre motores no acredita verdad ni revisión O. OE1/OE3 y fundamentos de OE4;
T05/T08 y partes de T09/T11. DW, benchmark, revisión humana, integración real y
evaluación experimental siguen pendientes en los diez pasos originales.

Límites reales: tipos escalares y archivos locales; índices separados necesitan
decisión expresa; transformaciones de zona/DST tienen capacidad de calendario
documentada; el transporte no recupera offset textual, payload NaN ni información
perdida antes de la captura. Grupos aproximados tienen límites de filas, aristas y
representaciones. IPC puede asignar su lote almacenado antes del checkpoint.
No hay cuota RSS, timeout duro, sandbox ni promesa de escala medida.

Python sigue limitado a `>=3.12,<3.13`. La matriz CI conserva Windows x64,
Ubuntu x64/ARM64 y macOS Intel/Apple Silicon. Los resultados de esta entrega se
identifican por SHA en el PR y sus checks; la configuración no acredita su éxito.
No se fusiona automáticamente. Licencia, control del nombre, metadatos públicos,
ampliación de Python con CI y publicación PyPI quedan para el paso 10. La aceptación
final exige `pip install equiframe` desde PyPI e `import equiframe as ef` fuera del
repositorio privado. Este paso no publica ni despliega OCI.

El DOCX conserva SHA-256
`c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d`.
