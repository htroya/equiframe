# Verificación del paso 8

Fecha: 2026-10-01. Núcleo y benchmark 0.8.0. Base `main`/`origin/main`
`cd5fc83`; rama de entrega `feat/step-8-orchestration`.

## Alcance implementado

Orquestación sobre una única captura nativa: ejecución, R, perfil, M/B con bundle
congelado, H y comparación opcional. Publicación exclusiva, journal encadenado,
inventario verificable, reportes JSON/HTML y códigos CLI. Reducción por filas entre
tablas con precondiciones/firma explícitas, confirmaciones, presupuestos y
minimalidad local. CLI separada del benchmark y piloto integrado con el runner.

[Diseño](STEP_08_DESIGN.md), [uso](ORCHESTRATION.md), decisiones A72–A78 y
[trazabilidad](THESIS_TRACEABILITY.md). Siete esquemas nuevos 1.0; formatos
de ejecución/contrato/reglas/perfil previos conservados. La versión emisora del
detector acepta 0.7.0 y 0.8.0 sin cambiar el algoritmo declarativo 1.0.

## Entorno y controles

Windows x64, Python 3.12.4, uv 0.11.6. Locks conservados salvo las versiones
de las distribuciones del proyecto. Núcleo: Pydantic 2.13.5, PyArrow 25.0.1,
Pandas 3.0.6, Polars 1.44.2, DuckDB 1.5.6, scikit-learn 1.9.1, NumPy 2.5.3;
pytest 9.1.1, Ruff 0.16.9 y mypy 1.20.2. El benchmark mantiene su propio lock.

| Control ejecutado | Resultado |
|---|---|
| Ruff y formato, ambos paquetes | Aprobados |
| mypy estricto | Núcleo: 36 archivos; benchmark: 15 archivos |
| Assets núcleo | 41 fixtures/esquemas comprobados |
| Assets benchmark | 13 esquemas comprobados |
| Pruebas nuevas núcleo | 43 aprobadas, 45,05 s |
| Suite núcleo instalada desde wheel/sdist | **692 aprobadas**, 161,70 s |
| Benchmark instalado fuera del checkout | 88 aprobadas, 64,36 s |
| Piloto instalado | 5 escenarios, 35 candidatos, 15 perfiles, 4 grupos |
| Distribución benchmark | Instalación pip de ambos 0.8.0, import ligero y wheel reconstruido idéntico |
| Distribución núcleo | Base, arrow, pandas, polars, duckdb, engines y ml; API/CLI y ejemplos externos aprobados |
| Reproducción núcleo | Wheel reconstruido idéntico en bytes y consumidor mypy externo aprobado |

Ambos verificadores finalizaron con código 0. No se atribuyen a esta máquina
resultados Linux/macOS. La CI remota se consulta sobre la revisión publicada;
su configuración por sí sola no acredita haber pasado.

El entorno de desarrollo temporal se creó con `uv sync --locked --all-extras
--no-install-project`, reutilizando la caché. Las pruebas focalizadas usan un
PYTHONPATH temporal; las verificaciones de distribución eliminan PYTHONPATH,
instalan wheels en directorios temporales externos y comprueban la ruta efectiva
del import. Los verificadores eliminan sus entornos al terminar. No hay instalación
persistente de EquiFrame ni publicación TestPyPI/PyPI.

Comandos de comprobación, ejecutados con el Python del entorno temporal:

```text
python -m ruff check . --no-cache
python -m ruff format . --no-cache
python -m mypy --cache-dir .cache/step8-mypy
python tools/generate_assets.py --check
python -m pytest -q tests/test_pipeline.py tests/test_reduction.py
python -m build --no-isolation
python tools/verify_distribution.py --uv <ruta-al-uv-del-equipo>  # núcleo
python tools/verify_distribution.py                            # benchmark
```

Las pruebas locales emplean también rutas propias para `--basetemp` y caché de
pytest. El verificador del núcleo ejecuta todos los tests contenidos en el sdist
contra el wheel instalado, y el benchmark ejecuta su suite instalada completa.
La caché no contenía inicialmente `librt 0.16.0`, ya fijado en el lock del
benchmark: el primer intento offline falló antes de los tests y se repitió con
descarga de esa dependencia. No se alteraron versiones para eludir el fallo.

## Casos de aceptación

- Tres motores con implementación propia y una captura por corrida; perfiles y
  comparación reutilizan esa captura. Inferencia no reajusta modelos.
- R alerta y comparación diferente conservadas; fallos de perfil/bundle no
  impiden evaluar componentes independientes. Cancelación y límites producen 3.
- Índice Pandas separado rechazado por defecto; las pruebas que lo ignoran lo
  declaran expresamente con justificación. No se cambia el contrato para igualar
  salidas. La política de tipos lossless también se declara explícitamente.
- Dos corridas concurrentes conservan carpetas distintas. Fallo al publicar el
  manifiesto deja evidencia inspeccionable sin declaración de finalización.
- SHA-256/tamaños, cadena, etapas, procedencia, bundle/matriz/perfil y reportes
  vinculados. Modificar bytes o un resumen que contradice el resultado se rechaza.
- JSON duplicado, rutas con escape del directorio y registros de código inválidos
  rechazados. HTML escapa texto; reportes/eventos omiten secretos del entorno y
  mensajes de excepciones. Artefactos completos siguen siendo privados.
- El reductor conserva duplicados, decimales y precondiciones referenciales entre
  tablas; distingue fallo incorrecto, baseline inválido y predicado fallido.
  Confirma repeticiones, rechaza callbacks tardíos y registra presupuestos exactos.
- La solución reducida de prueba es comprobada mediante todas las supresiones
  individuales restantes. Se declara `one_minimal`, nunca mínimo global.
- CLI run/compare/report/evidence/reduce y benchmark validate/split ejercitados
  con resultados esperados, errores y no sobrescritura.

## Artefactos locales

Construidos en `dist/`, excluidos de Git. Hashes de bytes, no de equivalencia:

| Archivo | SHA-256 |
|---|---|
| `equiframe-0.8.0-py3-none-any.whl` | `2bf57743f99a35bf0d79632df042a27d3f46e203e977fb9f394680a644b4b45b` |
| `equiframe-0.8.0.tar.gz` | `20ee22f41868f048a9de82a1fd077efd4a0fe32175566562ea1896e5e38fc863` |
| `equiframe_benchmark-0.8.0-py3-none-any.whl` | `fee845e0bd4bf884ca8e5e24c17a399b4ac66da06196c8e93bf456c3dcc4a6a2` |
| `equiframe_benchmark-0.8.0.tar.gz` | `d8ab06fd3701f6018abe367daf67f1793858b28085eaad335f7756c9bce9cbcf` |

Registros locales ignorados por Git: `packages/equiframe/.cache/step8-distribution.log`
y `packages/equiframe-benchmark/.cache/step8-distribution.log`.

## Límites y pendientes

Integridad local no equivale a firma digital ni WORM. Presupuestos de callbacks
son cooperativos; el reductor no preempta código bloqueante ni certifica un
predicado proporcionado por el consumidor. No hay sandbox, reanudación automática,
cuota dura de RSS/disco ni relocalización automática de URI.

El piloto conserva 35 revisiones pendientes y cero etiquetas confirmadas:
25 comparaciones equivalentes y 10 diferentes son evidencia técnica, no acuerdos
humanos ni evaluación final. Los modelos de tests son sintéticos. OCI/DW real,
congelación y métricas científicas pertenecen a los pasos siguientes. Continúa
vigente el calendario de publicación pública indicado por Hernán.

El cambio previo de `docs/HERNAN_ROADMAP.md`, presente al empezar, se conserva en
el árbol de trabajo y no se incluye en este commit. Este informe identifica el
estado técnico del paso 8 sin incorporar trabajo previo ajeno al cambio.
