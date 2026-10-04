# EquiFrame

**Comparación semántica y evidencia verificable para resultados tabulares en Python.**

EquiFrame permite declarar qué deben conservar tus datos, comparar resultados bajo ese contrato y localizar diferencias de valores, tipos, claves, multiplicidad y orden. También ejecuta transformaciones nativas con **pandas, Polars y DuckDB**, verifica resultados contra un esperado y conserva evidencia para revisar una migración o una regresión.

La comparación funciona sobre resultados ya materializados: puedes incorporarla a un proceso existente sin usar el runner de EquiFrame. La equivalencia siempre corresponde a las capturas y políticas evaluadas; dos motores pueden coincidir en un resultado incorrecto.

**Estado actual:** candidato **0.11.1**, clasificado como **Alpha**, para **Python 3.12** (`>=3.12,<3.13`). El repositorio es privado, la licencia de distribución está pendiente y el paquete del equipo **todavía no está publicado en PyPI**. Consulta el [estado del candidato](docs/RELEASE_CANDIDATE.md) antes de distribuir o adoptar un artefacto.

[Inicio rápido](#inicio-rápido) · [Capacidades](#capacidades-disponibles) · [Semántica y límites](#semántica-y-límites) · [Documentación](#documentación)

## Para qué sirve

- **Detectar regresiones:** comparar una salida nueva con una referencia bajo políticas explícitas, conservando las diferencias completas y sus diagnósticos
- **Revisar cambios entre motores:** ejecutar implementaciones nativas o aportar sus resultados, y comprobar el alcance que deben preservar
- **Validar una migración:** contrastar origen y destino, añadir un esperado independiente y revisar las condiciones de aceptación antes de publicar una salida
- **Conservar evidencia:** registrar contratos, versiones, capturas, estados y artefactos que permitan inspeccionar el resultado sin volver a ejecutar la transformación

Su enfoque combina contratos tipados, captura de las distinciones admitidas y comparación detallada. Una validación de esquema responde si un dataset cumple restricciones; una comparación responde si dos resultados satisfacen la relación declarada. La ejecución en varios motores y las señales de anomalía son capacidades separadas, con sus propios límites.

## Inicio rápido

### Instalar desde el repositorio

Necesitas acceso al repositorio y un entorno con Python 3.12. Para comparar datos locales basta el extra `arrow`; no hace falta instalar los tres motores.

```bash
git clone https://github.com/htroya/equiframe.git
cd equiframe/packages/equiframe
python -m pip install ".[arrow]"
python examples/compare_local.py --work-dir comparison-runs
```

El [ejemplo autocontenido](packages/equiframe/examples/compare_local.py) crea dos tablas Arrow con cuentas e importes `Decimal`, declara una clave única y compara valores exactos. Intercambia los importes de dos cuentas: el total coincide, pero los registros difieren. Comprueba dos diferencias persistidas aunque el resumen se limite a un ejemplo, y después compara una captura idéntica.

La última línea tiene la forma `different 2 <URI del archivo de diferencias>`. Los datos del ejemplo son sintéticos; no requiere archivos previos, credenciales ni conexión a un DW.

No uses `pip install equiframe` para obtener este candidato: el nombre podría resolver un paquete ajeno. Para reproducir el entorno de desarrollo utiliza `uv.lock` y la [instalación reproducible](packages/equiframe/README.md#instalación-reproducible). También pueden usarse los wheels identificados del equipo según la [guía de distribución](docs/RELEASE_CANDIDATE.md).

### Comparar archivos de tu proyecto

Con un contrato y dos archivos Parquet propios, la API disponible es `ef.compare`:

```python
from pathlib import Path

import equiframe as ef

contract = ef.read_contract("my-contract.json")
result = ef.compare(
    Path("candidate.parquet"),
    Path("independent-expected.parquet"),
    contract=contract,
    reference="expected",
    work_dir=Path("comparison-evidence"),
    options=ef.ComparisonOptions(batch_rows=4096, max_examples=20),
)

print(result.state, result.complete, result.counts)
for difference in ef.iter_differences(result.differences):
    print(difference.code, difference.key, difference.column)
```

`my-contract.json` define el esquema de salida y sus políticas; los archivos del ejemplo anterior pertenecen al consumidor. Para ver cómo construir un contrato completo, consulta [el ejemplo Arrow](packages/equiframe/examples/compare_local.py) o la [referencia de contratos](docs/API_CONTRACTS.md).

Cada lado admite `ArrowInput`, `ArtifactRef` local, `Path` a Arrow IPC **file** o Parquet, `TableArtifact` y `ExecutionResult` con estado `completed`. Los DataFrames no se aceptan directamente en `compare`: deben capturarse mediante ejecución o convertirse explícitamente a un transporte que preserve las distinciones necesarias. La comparación no vuelve a ejecutar los motores.

### Interpretar el resultado

| Estado de comparación | Significado |
|---|---|
| `equivalent` | Recorrido completo, sin diferencias ni incumplimientos dentro del alcance declarado |
| `different` | Recorrido completo con diferencias o incumplimientos y evidencia persistida |
| `not_evaluable` | No puede emitirse el juicio requerido: referencia esperada inválida, capacidad insuficiente, fallo, cancelación o presupuesto agotado |

Consulta siempre `state`, `complete`, los diagnósticos y `counts.final`. Una referencia esperada inválida puede producir `not_evaluable` aun con `complete=True`. Una evaluación interrumpida conserva las diferencias observadas, pero no las presenta como totales definitivos. `difference_records` cuenta registros de diagnóstico, no necesariamente filas distintas.

Para exigir equivalencia en una prueba o en CI, comprueba ambos campos después de guardar o consultar el diagnóstico:

```python
if result.state != "equivalent" or not result.complete:
    raise AssertionError(f"Comparación no aceptada: {result.state}, complete={result.complete}")
```

**Limitación actual de la CLI:** `equiframe compare` puede devolver código 0 cuando la referencia esperada es inválida y el resultado es `not_evaluable` con `complete=True`. No bases una aceptación automática solo en ese código; comprueba `state == "equivalent"` y `complete` mediante la API o el resultado JSON.

El estado de ejecución `completed` solo indica que la transformación terminó y su salida se materializó; no acredita equivalencia, corrección ni ausencia de anomalías. [Estados y evidencia de comparación](docs/COMPARISON.md#estados-y-evidencia).

## Capacidades disponibles

| Necesidad | API o componente | Alcance |
|---|---|---|
| Contratos tipados | `Contract`, `validate_contract`, CLI de contratos | Esquema, claves, unidades, ausencias, orden y políticas explícitas; validar metadatos no evalúa los datos |
| Comparación de resultados | `compare`, `read_comparison`, `iter_differences` | Clave verificada, multiconjunto o secuencia; normalizaciones autorizadas, tolerancias y evidencia completa |
| Ejecución nativa | `execute`, `TransformationRegistry` | Callbacks pandas, DataFrame/LazyFrame Polars y consultas DuckDB parametrizadas |
| Migración declarativa | `check_migration`, `migrate`, `read_migration` | Plan relacional cerrado, implementaciones nativas y seis direcciones entre los tres motores, dentro de las capacidades admitidas |
| Verificación | `verify`, `verify_migration` | Separa acuerdo entre salidas, comparación contra esperado, integridad, reglas, cobertura y revisión independiente |
| Ingestión y workflows | `ingest_file`, `run_workflow`, `ParquetDestination` | CSV/JSON/JSONL con esquema explícito, etapas verificadas y publicación Parquet local |
| Reglas y operación | `evaluate_rules`, `run_pipeline` | Reglas seleccionadas, precondiciones, eventos, reportes JSON/HTML y composición de componentes |
| Evidencia portátil | `export_bundle`, `import_bundle`, `read_bundle` | Expedientes finalizados de migración, Verify y workflow con inventario cerrado y verificación de integridad |
| Perfiles y anomalías | Perfiles, preprocesamiento, Isolation Forest y MAD | Componentes separados del juicio de equivalencia; ajuste, calibración e inferencia diferenciados |

Las APIs no tienen todas las mismas entradas, estados o dependencias. La [referencia pública](docs/API_CONTRACTS.md), el [README del paquete](packages/equiframe/README.md) y la [matriz semántica](docs/SEMANTIC_SUPPORT.md) detallan sus condiciones. No existe traducción de programas Python o SQL arbitrarios.

### Extras

| Extra | Uso |
|---|---|
| `arrow` | Comparación, verificación y trabajo tabular con Arrow |
| `pandas`, `polars`, `duckdb` | Motor correspondiente y PyArrow |
| `engines` | Los tres motores y PyArrow |
| `ml` | Entrenamiento de Isolation Forest con scikit-learn y NumPy |

La instalación base contiene contratos, CLI, modelos y almacenamiento local de artefactos. `import equiframe as ef` no carga motores, Arrow, NumPy ni ML. Instala los extras que requiera tu recorrido; por ejemplo, `python -m pip install ".[engines]"` desde `packages/equiframe`.

### Recorridos ejecutables

Desde `packages/equiframe`, con los extras indicados:

| Recorrido | Comando | Extra |
|---|---|---|
| Comparar importes con contrato explícito | `python examples/compare_local.py --work-dir comparison-runs` | `arrow` |
| Detectar un error compartido frente a un esperado | `python examples/verify_generic.py --output verify-example` | `arrow` |
| Ejecutar ejemplos nativos en tres motores | `python examples/execute_native.py --work-dir native-runs` | `engines` |
| Comprobar las seis direcciones de migración | `python examples/migrate_native.py --output migration-runs` | `engines` |
| Ingerir, verificar y publicar Parquet local | `python examples/retail_etl.py --output retail-example` | `engines` |

Usa una carpeta de destino nueva cuando el ejemplo la exija. Son ejemplos sintéticos de comportamiento técnico. No acreditan por sí solos evaluación científica, aceptación externa o integración con infraestructura real.

## Semántica y límites

**El contrato determina qué se compara.** La captura conserva la salida observada separada del esquema esperado. No hace casts, rellena ausencias, deduplica, ordena o redondea para acomodar una discrepancia. Las equivalencias o normalizaciones permitidas deben estar declaradas y justificadas.

- **Claves, duplicados y orden.** Las claves se usan para alinear solo tras comprobar unicidad y completitud en ambos lados. En los demás casos se aplican las políticas de multiconjunto o secuencia. Preservar multiplicidad cuenta cada ocurrencia; exigir valores distintos no autoriza deduplicar
- **NULL, NaN, vacío y cero.** Son distinciones independientes salvo autorización explícita. El transporte no puede reconstruir información que ya se perdió antes de recibir los datos
- **Dinero y precisión.** Decimal se compara de forma exacta, sin conversión intermedia a float. Precisión, escala, unidades y límites de cada motor siguen siendo parte del contrato y sus capacidades
- **Tolerancias.** Se fijan antes de comparar; no se estiman para hacer coincidir resultados. La comparación aproximada no es transitiva. El matching de multiconjuntos conserva ocurrencias y tiene presupuestos explícitos
- **Fechas e índices.** Se distinguen días, instantes, unidades y zonas. Los índices pandas necesitan una política explícita; no se convierten automáticamente en claves
- **Recursos.** El comparador usa lotes e índices SQLite privados en disco. Tiempo, trabajo, filas y evidencia tienen presupuestos cooperativos; no son cuotas duras de RSS ni una garantía de tamaño máximo o latencia

El resumen limita ejemplos; el recorrido y `differences.jsonl` conservan su alcance declarado. Los fallos controlados y presupuestos agotados producen `not_evaluable`. Una configuración inválida o la imposibilidad de crear o publicar evidencia pueden lanzar una excepción al llamante; la ausencia de finalización nunca debe interpretarse como éxito.

### Soporte por etapa

Capturar un tipo, compararlo y ejecutarlo dentro de una transformación son capacidades distintas. La [matriz de soporte](docs/SEMANTIC_SUPPORT.md) identifica operaciones, tipos, motores, políticas, rechazos y pruebas concretas; no certifica todos sus cruces posibles.

Entre los límites actuales: categorías/diccionarios, tipos tabulares anidados, binarios, objetos arbitrarios y Arrow streams no forman parte del transporte nativo admitido. El migrador tiene un IR acotado; timestamps y ciertas operaciones numéricas o joins quedan fuera de ese subconjunto aunque existan capacidades de ingestión o comparación relacionadas. Consulta [transporte fiel](packages/equiframe/README.md#transporte-fiel-y-capacidades-comprobadas) y [migración](docs/MIGRATION.md) antes de elegir una ruta.

## Evidencia y uso seguro

Las corridas conservan contratos, opciones, versiones, capturas, diagnósticos y artefactos con tamaño y SHA-256. El alcance de lectura y verificación depende de cada API: `read_comparison` valida el manifiesto; `iter_differences` comprueba tamaño y hash del archivo de diferencias; los verificadores de bundles y migraciones inspeccionan sus inventarios. Los bundles permiten trasladar expedientes admitidos sin reescribir sus bytes históricos. Un hash identifica contenido frente a una referencia: no autentica personas, no certifica la independencia de un esperado y no convierte un resultado incorrecto en correcto.

Los contratos, parámetros, capturas y diferencias pueden contener datos del consumidor. Elige almacenamiento y permisos adecuados antes de compartir un expediente; mantén credenciales, bases reales y resultados privados fuera de Git. La biblioteca ejecuta callbacks, SQL y extensiones confiables del usuario: **no es un sandbox**. Los controles cooperativos tampoco sustituyen los límites de un servicio.

[Verify y evidencia portátil](docs/VERIFY.md) · [Arquitectura](docs/ARCHITECTURE.md) · [Contratos de integración](docs/TEAM_INTEGRATION.md)

## Compatibilidad y madurez

- Python admitido por metadatos: **3.12**. Las versiones resueltas están fijadas en `uv.lock`; el lock no demuestra que se hayan probado. Cada validación corresponde al candidato y entorno identificados en su evidencia
- La [revisión integral](docs/COMPREHENSIVE_REVIEW_20261003.md) documenta controles de una revisión anterior en **Windows x64 / Python 3.12.4**. Los cambios posteriores requieren revalidación; esos resultados no se atribuyen automáticamente al HEAD actual
- La CI es manual (`workflow_dispatch`) y exige activar la matriz de Windows x64, Linux x64/ARM64 y macOS Intel/Apple Silicon. No se encontraron ejecuciones de GitHub Actions para el candidato revisado `635e35b`; su configuración no acredita compatibilidad ejecutada. Consulta los resultados del commit correspondiente antes de anunciar una plataforma como probada
- El núcleo puede trabajar con datos locales, sin OCI, SERCOP ni DW. `DataSource` permite proveedores externos explícitos; el servicio y la aceptación del DW real conservan entregas independientes
- Licencia, acceso público, publicación y aceptación externa siguen pendientes. La evidencia técnica y los ejemplos sintéticos no cierran la evaluación científica

Durante la serie 0.x, los cambios incompatibles requieren changelog y migración explícita. Consulta los [cambios por versión](packages/equiframe/CHANGELOG.md) y el [candidato de release](docs/RELEASE_CANDIDATE.md).

### Evaluación experimental

La evaluación se documenta en la distribución separada [equiframe-benchmark](packages/equiframe-benchmark/README.md), con escenarios, particiones, revisión y reproducción. Sus controles técnicos no reemplazan la evidencia empírica ni la revisión independiente pendientes.

El auxiliar reciente [`equiframe.benchmark`](packages/equiframe/src/equiframe/benchmark.py) y su [ejemplo local](packages/equiframe/examples/benchmark_local.py) del paquete núcleo están incompletos: incluyen métricas de relleno, una comparación limitada a conteos y reutilización de datos de ajuste para calibración. No deben usarse para reportar precisión, recall, F1 o conclusiones de equivalencia. Su revisión y validación siguen pendientes; no son el recorrido de comparación mostrado arriba.

## Desarrollo y contribución

Las instrucciones completas de entorno, ramas y revisión están en [CONTRIBUTING.md](CONTRIBUTING.md). Desde `packages/equiframe`, con Python 3.12 y `uv` disponible:

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --all-extras python tools/verify_distribution.py
```

Estos son comandos para ejecutar, no una declaración de que una revisión concreta los haya superado. El [proceso de candidato](docs/RELEASE_CANDIDATE.md) vincula controles y artefactos con sus bytes; una prueba dirigida o un recibo histórico no sustituye la validación del candidato actual.

## Documentación

| Guía | Contenido |
|---|---|
| [API y ejemplos](packages/equiframe/README.md) | Instalación, contratos, ejecución, CLI y límites |
| [Referencia de formatos](docs/API_CONTRACTS.md) | Tipos públicos, estados y serialización |
| [Comparación](docs/COMPARISON.md) | Políticas, alineación, tolerancias, presupuestos y evidencia |
| [Verify](docs/VERIFY.md) | Acuerdo, esperados, reglas, cobertura y bundles portátiles |
| [Migración nativa](docs/MIGRATION.md) | IR, capacidades, API/CLI y límites por motor |
| [Ingestión y ETL](docs/ETL.md) | CSV/JSON/JSONL, workflows y publicación Parquet local |
| [Matriz semántica](docs/SEMANTIC_SUPPORT.md) | Soporte y rechazos por operación, tipo, motor y política |
| [Reglas](docs/RULES.md) | Precondiciones, cobertura, catálogo y estados |
| [Perfiles](docs/PROFILES.md) y [detectores](docs/DETECTORS.md) | Fórmulas, preprocesamiento, calibración y limitaciones |
| [Arquitectura](docs/ARCHITECTURE.md) | Componentes, interfaces y dependencias |
| [Benchmark](packages/equiframe-benchmark/README.md) | Escenarios, revisión, particiones, evaluación y reproducción |
| [Integración OCI](docs/OCI_INTEGRATION.md) | Proveedores, snapshots y responsabilidades del servicio/DW |
| [Calidad](docs/QUALITY.md) y [release](docs/RELEASE_CANDIDATE.md) | Pruebas, artefactos, evidencia y decisiones pendientes |

Las revisiones históricas y la planificación del proyecto permanecen en `docs/`. Documentan decisiones y pendientes; no sustituyen el alcance actual de la API ni resultados de ejecución del candidato.

## Organización del repositorio

```text
packages/equiframe/            biblioteca Python, ejemplos y pruebas
packages/equiframe-benchmark/  evaluación, reproducción y pruebas del benchmark
packages/equiframe-data/       especificación del acceso a datos
packages/equiframe-sercop/     integración y scripts del dominio SERCOP
services/data-gateway/         especificación del servicio de datos
infra/                        especificación de infraestructura
docs/                         documentación técnica
.github/                      CI y plantillas de colaboración
```

`equiframe` y `equiframe-benchmark` son distribuciones Python separadas. Los componentes de datos, dominio e infraestructura mantienen sus propias responsabilidades y contratos de integración; la presencia de scripts no acredita aceptación del servicio o DW real. El núcleo no depende del paquete de benchmark ni de una infraestructura concreta.

**Licencia:** la licencia de distribución está pendiente de decisión de los autores. El acceso al repositorio no implica autorización de redistribución.
