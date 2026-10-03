# Refuerzo de informes y aceptación semántica de migración

Fecha: 3 de octubre de 2026, America/Guayaquil. Base inspeccionada:
`5b3ea35ac042384bbedbb8d501fb797f5a95ea1d`, núcleo 0.10.0,
benchmark 0.10.1. Nueva autorización del autor para mejoras y subida a Git,
en paralelo con la reorientación documental. Cambios registrados en A108–A110.
No se modifica el cambio ajeno de `docs/HERNAN_ROADMAP.md`.

## Problema y comportamiento resultante

El HTML y la ayuda CLI denominaban «Independent verification» a la comparación
automática con un esperado aportado. El runner no recoge autoría independiente
ni revisión humana; esa denominación podía confundirse con EquiFrame Verify (O).
El informe ahora dice comparación con esperado aportado y deja explícito
`equiframe_verify.status="not_established"`. Esto no crea una etiqueta negativa:
solo indica que el runner no acredita el procedimiento completo.

`migration_summary` conserva `independent_verification` por compatibilidad,
añade `expected_output_comparison` y conserva estado/completitud/ID/conteo de
las tres comparaciones: origen–destino y cada motor contra el esperado.
El lector sigue aceptando reportes históricos completos o ampliados completos
y mantiene todas las comprobaciones de archivos, inventarios, eventos y tablas.
No acepta una mezcla arbitraria de campos antiguos y nuevos como formato válido.

Las nuevas pruebas integradas cubren las tres familias en cada dirección
Pandas→Polars, Polars→Pandas, Pandas→DuckDB, DuckDB→Pandas, Polars→DuckDB y
DuckDB→Polars. Invocan una vez ambos adaptadores reales con esperado literal,
NULL/NaN distintos, claves/cardinalidad, relación many-to-many conservada,
NULL sin pareja y Decimal exacto por moneda. Direcciones técnicas verificadas
no son resultados científicos ni prueban generalización bidireccional sobre SERCOP.

## Comprobaciones efectivamente ejecutadas

Se reutilizaron entornos locales existentes, Python 3.12.4/Windows x64, con src
explícito en PYTHONPATH. No se instaló ni publicó un paquete. Dependencias del
entorno núcleo: Pandas 3.0.6, Polars 1.44.2, DuckDB 1.5.6, PyArrow 25.0.1,
NumPy 2.5.3, Pydantic 2.13.5, Typer 0.27.2 y Pytest 9.1.1.

| Control | Resultado real |
|---|---|
| Contratos/comparación/R/perfiles/preprocesamiento/inferencia declarativa/backends nativos | 240 aprobadas; 101,60 s |
| Benchmark: EquiFrame Verify, particiones, selecciones/calibración, métricas y costos | 150 aprobadas, 1 omitida por enlaces simbólicos Windows; 103,13 s |
| Runner/evidencia de migración y nueva suite semántica | 82 aprobadas, 1 excluida explícitamente; 218,22 s |
| CLI e integridad + lectura de informe histórico tras última edición textual | 2 aprobadas; 13,39 s |
| Ruff check sobre 4 archivos Python afectados | Sin errores |
| Ruff format --check sobre esos 4 archivos | 4 archivos ya formateados |
| Mypy sobre io.py y cli.py | Sin errores en 2 archivos |
| git diff --check | Sin errores |
| Ayudas de migración y benchmark | Comandos disponibles contrastados |

Las 20 pruebas nuevas son 18 combinaciones familia/dirección, un caso sin
esperado y un expediente legado. Se ejecutaron 36 pipelines nativos en las
18 combinaciones. El total de invocaciones aprobadas incluye dos repeticiones
dirigidas: no se presenta como número de casos científicos únicos.

El entorno venv no contiene sklearn. La prueba existente
`test_profile_and_detector_do_not_receive_expected_results` se excluyó
explícitamente porque ajusta un bosque sintético; la inferencia declarativa
sí se comprobó en suites focalizadas. El sklearn 1.4.2 del entorno global es
ajeno al rango declarado >=1.7,<1.10 y no se utilizó para atribuir ajuste válido.
No se afirma suite completa, consumo desde wheel nuevo, CI de otras plataformas
ni entrenamiento empírico real. El cambio no altera algoritmos ni esquemas
tipados, y permanece en `Unreleased`.

## Comandos ejecutados

Desde raíz de repo o paquete según ruta, con destinos temporales nuevos fuera
del repo y `PYTHONDONTWRITEBYTECODE=1`:

```powershell
# Fuente de ambos paquetes declarada explícitamente para estas pruebas.
$env:PYTHONPATH = '<workspace>\equiframe\packages\equiframe\src;<workspace>\equiframe\packages\equiframe-benchmark\src'
python -B -m pytest tests/test_contracts.py tests/test_comparison.py tests/test_rules.py tests/test_profiles.py tests/test_preprocessing.py tests/test_detector_component.py tests/test_migration_backends.py -q -p no:cacheprovider -o addopts='' --basetemp='<output>\pytest_core'
python -B -m pytest tests/test_oracle.py tests/test_splits.py tests/test_selection.py tests/test_calibration.py tests/test_evaluation.py tests/test_costs.py -q -p no:cacheprovider -o addopts='' --basetemp='<output>\pytest_benchmark'
python -B -m pytest tests/test_migration_semantic_directions.py tests/test_migration.py tests/test_migration_evidence.py -q -p no:cacheprovider -o addopts='' -k 'not profile_and_detector_do_not_receive_expected_results' --basetemp='<output>\pytest_migration'
python -B -m ruff check --no-cache src/equiframe/migration/io.py src/equiframe/cli.py tests/test_migration_semantic_directions.py examples/migrate_native.py
python -B -m ruff format --no-cache --check src/equiframe/migration/io.py src/equiframe/cli.py tests/test_migration_semantic_directions.py examples/migrate_native.py
python -B -m mypy --cache-dir='<output>\mypy_cache' src/equiframe/migration/io.py src/equiframe/cli.py
git diff --check
```

`python` representa el ejecutable existente de cada paquete indicado arriba;
los marcadores se sustituyeron por rutas absolutas del workspace/salida. Ruff
necesitó permiso del entorno para escribir formato; el control final usa
`--no-cache`. No hubo cambio de dependencias o instalación persistente.

## Pendientes científicos y de alcance

Corpus real, más de 10.000 perfiles efectivos con interpretación por modelo,
grupos y particiones suficientes, revisión humana elegible antes de aprender,
calibración/freeze, evaluación y reproducción real siguen pendientes.
El benchmark actual calcula contraste incremental sobre intersección R/M/B/H;
el protocolo debe añadir S_HR para H–R sin condicionarlo a B y reportar también
S_MB e intersección común S_all. H2 limita el incremento ΔFPR_add sobre R mediante
δ_add; calibración normal S_cal_HR debe seleccionar un umbral finito admisible.
Se informa también FPR total de H: alpha de M no garantiza su control. Esas ampliaciones permanecen
propuestas, sin resultados fabricados ni cambios experimentales encubiertos.
