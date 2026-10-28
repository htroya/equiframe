# EquiFrame

[English](#english) | [Español](#espanol)

<a id="english"></a>

> Release status: **0.12.2 is being prepared for review.** TestPyPI currently
> contains [0.12.0](https://test.pypi.org/project/equiframe/0.12.0/).
> Production PyPI publication is pending.

# EquiFrame: semantic comparison and dataframe migration

[Documentation](https://github.com/htroya/equiframe/blob/main/docs/index.md) |
[API](https://github.com/htroya/equiframe/blob/main/docs/api.md) |
[Examples](https://github.com/htroya/equiframe/blob/main/docs/journeys.md) |
[Issues](https://github.com/htroya/equiframe/issues)

**EquiFrame** checks whether tabular data and supported transformations preserve
their meaning when moving between **Pandas, Polars and DuckDB**. It reads files,
creates native dataframe objects, converts between engines and reports semantic
differences under explicit comparison policies.

Use it to check a dataframe refactor, validate an ETL result or add migration
checks to an existing application. Contracts describe keys, types, numeric
precision, missing values, duplicates, order and dates. The library works with
your own data, independently of procurement schemas, warehouses and cloud services.

## Install

EquiFrame 0.12.2 supports **Python 3.10, 3.11, 3.12 and 3.13**.

```bash
python -m pip install "equiframe[files,engines,ml]==0.12.2"
python -m pip check
```

The base installation is `python -m pip install equiframe==0.12.2`.
Optional engines and machine-learning libraries are loaded when requested.

| Extra | Purpose |
| --- | --- |
| `files` | JSON, JSONL, CSV, delimited TXT, XML, Excel, Parquet and GeoJSON readers |
| `pandas`, `polars`, `duckdb` | The selected engine and Arrow transport |
| `engines` | Pandas, Polars, DuckDB and Arrow |
| `ml` | Isolation Forest with scikit-learn and NumPy |
| `eda`, `eda-charts` | Experimental exploratory analysis and optional charts |

The independent R reviewer requires an external `Rscript` installation.
See [dependencies](https://github.com/htroya/equiframe/blob/main/docs/dependencies.md)
and [supported ranges](https://github.com/htroya/equiframe/blob/main/pyproject.toml).

## Quick start

Local file reading and comparison need no EquiFrame account or API key.
Install the optional engine extras above; install R separately only for R review.

### Read a file and choose its destination

With the `files` and `engines` extras installed, provide an existing file:

```python
import equiframe as ef

with ef.load_dataset("orders.json") as loaded:
    print(loaded.info.to_dict())
    pandas_df = loaded.pandas

    with ef.convert_dataset(loaded, target="polars") as converted:
        polars_df = converted.frame

    with ef.convert_dataset(loaded, target="duckdb") as converted:
        relation = converted.frame
        print(relation.limit(5).df())
```

EquiFrame reports columns, detected types and row count. The initial load
constructs Pandas; `target` selects the native object exposed as `loaded.frame`.
Later conversions consume the selected native frame and record its provenance.
Keep the context open while using an owned DuckDB relation.

Select a destination directly:

```python
import equiframe as ef

with ef.load_dataset("orders.parquet", target="polars") as loaded:
    polars_df = loaded.frame
```

Pass `DatasetReadOptions` for multiple Excel sheets, nested JSON/XML, ambiguous
delimiters or exact column representations. The
[file-reading guide](https://github.com/htroya/equiframe/blob/main/docs/lectura-conversion.md)
describes supported forms, preserved representations and resource limits.

```bash
equiframe dataset load orders.json
equiframe dataset load orders.json --target polars
equiframe dataset inspect orders.parquet
```

The first command asks for a destination in an interactive terminal. Supply
`--target` in automated jobs. Invalid inputs return a nonzero exit and an error
on `stderr`.

## Compare independently produced results

This example deliberately changes one amount:

```python
from pathlib import Path

import pandas as pd
import polars as pl

import equiframe as ef

original = pd.DataFrame({"id": [1, 2], "amount": [100, 200]})
migrated = pl.DataFrame({"id": [1, 2], "amount": [100, 201]})

result = ef.diff(original, migrated, keys=["id"], work_dir=Path("equiframe-runs"))
print(result.state)  # different
print(result.complete)
```

Inspect differences with `ef.iter_differences(result.differences)`. Enforce
acceptance with `ef.assert_equivalent(result)`; divergent or incomplete results
raise `ef.EquivalenceAssertionError`. Operational failures use the
`ef.EquiFrameError` hierarchy, including `DatasetReadError`,
`MissingDependencyError` and `InvalidExecutionInput`. See the
[API reference](https://github.com/htroya/equiframe/blob/main/docs/api.md)
for argument-validation exceptions and command-specific exits.

All six directed combinations of Pandas, Polars and DuckDB are supported.
A verdict concerns the supplied inputs and contract. Preserve `complete` and
unavailable-component states when deciding whether to accept a migration.

## ETL, rules, anomalies and R review

- **Data conversion:** `load_dataset` and `convert_dataset` move loaded data
  between native objects.
- **Transformation migration:** `check_migration` and `migrate` validate and run
  supported declarative plans: projections, filters, joins, aggregations, windows
  and ordering. Each engine executes its own native plan.
- **Semantic checks:** policies cover values, types, decimals, missing values,
  keys, multiplicity, order and time semantics.
- **Anomaly detection:** rules, Isolation Forest and MAD keep separate results.
  Fitting, calibration and inference are explicit operations.
- **Independent R review:** `review_with_r`, `finalize_with_r` and
  `finalize_execution_with_r` use a real R process and an explicit contract,
  preserving earlier alerts, disagreements and unavailable components.

See [entry points](https://github.com/htroya/equiframe/blob/main/docs/choosing-api.md),
[semantics](https://github.com/htroya/equiframe/blob/main/docs/semantics.md),
[migration](https://github.com/htroya/equiframe/blob/main/docs/migration-ir.md)
and [R review](https://github.com/htroya/equiframe/blob/main/docs/r_review.md).
Registered callbacks and SQL are trusted application code; EquiFrame does not
sandbox untrusted programs.

## Run a complete example

The source distribution includes `examples/load_convert_compare.py`. It creates
temporary synthetic orders, loads Pandas, converts to Polars and DuckDB, checks
equivalence and verifies a deliberate one-row regression. Its files are removed
when finished:

```bash
python examples/load_convert_compare.py --rows 30000
```

Installed wheels provide the same example as
`python -m equiframe.examples.load_convert_compare --rows 30000`. Further
[examples](https://github.com/htroya/equiframe/blob/main/docs/journeys.md)
and [recipes](https://github.com/htroya/equiframe/blob/main/docs/recipes.md)
cover ETL, reconciliation and terminal usage.

## Compatibility and development

The [compatibility register](https://github.com/htroya/equiframe/blob/main/docs/compatibility.md)
distinguishes stable interfaces and experimental capabilities. Advanced
orchestration, standalone pipelines, EDA and reduction remain experimental.
The separate `equiframe-benchmark` distribution remains Beta.

Releases use `MAJOR.MINOR.PATCH`: patches preserve documented contracts, minor
releases add compatible functionality, and breaking changes require migration
notes. During `0.x`, consult the
[upgrade guide](https://github.com/htroya/equiframe/blob/main/docs/upgrading.md)
and [changelog](https://github.com/htroya/equiframe/blob/main/CHANGELOG.md).
Release versions derive from reviewed Git tags.

The source distribution includes `src/`, `py.typed`, examples, tests, schemas and
release tools. Development uses **Ruff** for linting and formatting, **mypy** in
strict mode, and source and installed-distribution tests. The
[contribution guide](https://github.com/htroya/equiframe/blob/main/CONTRIBUTING.md)
provides commands and dependency locks.

## Support and license

Use the [issue tracker](https://github.com/htroya/equiframe/issues) for
reproducible bugs. Include package, Python and engine versions, operating system,
expected results and a shareable example. Sensitive reports belong in the
[private security channel](https://github.com/htroya/equiframe/security/advisories/new).

Hernán Troya (`htroya`) maintains releases and security handling without a fixed
response-time SLA. The reusable library and its scientific benchmark have
separate acceptance criteria.

Original code is licensed under
[MIT](https://github.com/htroya/equiframe/blob/main/LICENSE).
Bundled CycloneDX schemas retain Apache-2.0. See
[third-party notices](https://github.com/htroya/equiframe/blob/main/THIRD_PARTY_NOTICES.md)
and [license scope](https://github.com/htroya/equiframe/blob/main/NOTICE.md).

---

<a id="espanol"></a>

> Estado: **0.12.2 está en preparación y revisión.** La publicación en PyPI sigue pendiente.

# EquiFrame: comparación semántica y migración de datos en Python

[Documentación](https://github.com/htroya/equiframe/blob/main/docs/index.md) · [API](https://github.com/htroya/equiframe/blob/main/docs/api.md) · [Ejemplos](https://github.com/htroya/equiframe/blob/main/docs/journeys.md) · [Contribuir](https://github.com/htroya/equiframe/blob/main/CONTRIBUTING.md) · [Licencia MIT](https://github.com/htroya/equiframe/blob/main/LICENSE)

## ¿Qué es EquiFrame?

**EquiFrame** es una biblioteca Python para leer datos tabulares, trabajar con
Pandas, Polars y DuckDB y determinar qué cambia al migrar datos o transformaciones
entre esos motores. Compara valores y su significado bajo criterios explícitos:
tipos, precisión numérica, ausencias, claves, duplicados, orden y fechas.

Se integra en scripts, notebooks y procesos ETL. Ofrece una API Python y una CLI
para cargar archivos, convertir objetos nativos, comparar resultados y obtener
informes de las diferencias encontradas.

La versión **0.12.2** requiere **Python 3.10–3.13**.
Las interfaces con compromiso de estabilidad y las capacidades experimentales
se distinguen en la guía de compatibilidad.

## Contenido

- [Funciones principales](#funciones-principales)
- [Instalación](#instalación)
- [Dependencias](#dependencias)
- [Primeros pasos](#primeros-pasos)
- [ETL y detección de diferencias](#etl-y-detección-de-diferencias)
- [Documentación](#documentación)
- [Origen del proyecto](#origen-del-proyecto)
- [Ayuda y desarrollo](#ayuda-y-desarrollo)
- [Contribuciones](#contribuciones)
- [Licencia](#licencia)

## Funciones principales

- **Lectura multiformato:** CSV, TXT delimitado, JSON, JSONL, XML, Excel, Parquet
  y GeoJSON. Detecta estructura, columnas y tipos; permite precisar opciones
  cuando existen varias hojas, registros anidados o delimitadores ambiguos.
- **Objetos nativos:** carga los datos en Pandas y entrega un DataFrame de Pandas,
  un DataFrame de Polars o una relación DuckDB según el destino elegido.
- **Conversión entre motores:** admite las seis direcciones entre Pandas, Polars
  y DuckDB, con identidad de origen y controles de preservación de datos.
- **Comparación semántica:** identifica diferencias en valores, tipos, decimales,
  nulos/NaN, claves, multiplicidad, orden y fechas según el contrato seleccionado.
- **ETL y migración:** ejecuta planes declarativos con filtros, proyecciones,
  joins, agregaciones, ventanas y ordenación mediante compiladores nativos;
  compara los resultados entre motores.
- **Reglas y detección de anomalías:** combina reglas operativas con Isolation
  Forest y MAD, con entrenamiento, calibración e inferencia separados.
- **Revisión independiente con R:** añade una comprobación opcional de los
  resultados con un proceso R real y conserva las alertas de los otros componentes.
- **Resultados inspeccionables:** produce diferencias, informes y estados que
  distinguen equivalencia, divergencia y evaluación incompleta.
- **Benchmark separado:** `equiframe-benchmark` ofrece escenarios, evaluación
  pareada y reproducción de estudios sin añadir esa dependencia al núcleo.

## Instalación

Instala los extras necesarios para tu trabajo:

```bash
python -m pip install "equiframe[files,engines,ml]==0.12.2"
python -m pip check
```

La instalación base puede hacerse con `python -m pip install equiframe==0.12.2`.
Selecciona los extras necesarios para tu trabajo; el núcleo no importa los
motores opcionales al ejecutar `import equiframe`.

Para instalar un wheel local:

```bash
python -m pip install "./equiframe-0.12.2-py3-none-any.whl[files,engines,ml]"
```

El benchmark se instala por separado, después del núcleo:

```bash
python -m pip install equiframe-benchmark==0.12.2
```

Consulta la [guía de instalación](https://github.com/htroya/equiframe/blob/main/docs/installed-private.md) para entornos aislados,
dependencias y comprobación de los artefactos recibidos.

## Dependencias

La base utiliza Pydantic, Typer, typing-extensions y tzdata.
Las dependencias de ejecución se seleccionan por capacidad:

| Extra | Para qué se utiliza |
|---|---|
| `files` | Lectura multiformato: Pandas, Arrow, openpyxl, xlrd y defusedxml. |
| `pandas`, `polars`, `duckdb` | Uso del motor correspondiente. |
| `engines` | Pandas, Polars, DuckDB y Arrow. |
| `ml` | Isolation Forest y cálculo numérico con scikit-learn y NumPy. |
| `eda`, `eda-charts` | Análisis exploratorio y gráficos opcionales. |

La revisión con R requiere una instalación externa de R y acceso a `Rscript`.
Las [versiones admitidas](https://github.com/htroya/equiframe/blob/main/pyproject.toml) y los
[detalles de compatibilidad](https://github.com/htroya/equiframe/blob/main/docs/compatibility.md) describen el soporte declarado.

## Primeros pasos

### Leer un archivo y elegir el motor

```python
import equiframe as ef

with ef.load_dataset("ventas.json") as datos:
    print(datos.info.to_dict())
    pandas_df = datos.pandas

    with ef.convert_dataset(datos, target="polars") as convertido:
        polars_df = convertido.frame

    with ef.convert_dataset(datos, target="duckdb") as convertido:
        relacion = convertido.frame
        print(relacion.limit(5).df())
```

También puedes elegir el destino directamente:

```python
with ef.load_dataset("ventas.parquet", target="polars") as datos:
    polars_df = datos.frame
```

En la terminal, el comando sin destino pregunta qué motor deseas utilizar:

```bash
python -m equiframe dataset load ventas.json
python -m equiframe dataset load ventas.json --target polars
python -m equiframe dataset inspect ventas.parquet
```

La [guía de lectura y conversión](https://github.com/htroya/equiframe/blob/main/docs/lectura-conversion.md) explica las opciones
para Excel, XML, JSON anidado, texto y GeoJSON, junto con los tipos conservados.

### Comparar resultados de dos motores

```python
from pathlib import Path

import pandas as pd
import polars as pl
import equiframe as ef

origen = pd.DataFrame({"id": [1, 2], "importe": [100, 200]})
migrado = pl.DataFrame({"id": [1, 2], "importe": [100, 201]})

resultado = ef.diff(origen, migrado, keys=["id"], work_dir=Path("equiframe-runs"))
print(resultado.state)  # different
print(resultado.complete)
```

Para aplicar una aceptación en un proceso automatizado, utiliza
`ef.assert_equivalent(resultado)`: una diferencia provoca una excepción.
Consulta [qué API elegir](https://github.com/htroya/equiframe/blob/main/docs/choosing-api.md) para comparar objetos nativos,
capturas de archivos o resultados de una ejecución.

## ETL y detección de diferencias

Usa `convert_dataset` para convertir datos ya cargados. Para trasladar un plan
de transformación declarativo, usa `check_migration` y `migrate`; para coordinar
varias etapas, utiliza `run_workflow`. Cada motor ejecuta su propia implementación
nativa del plan admitido.

Las reglas y los detectores de anomalías tienen resultados separados.
Isolation Forest requiere ajuste y calibración adecuados a los datos.
La [revisión con R](https://github.com/htroya/equiframe/blob/main/docs/r_review.md) puede completar la decisión mediante
`finalize_with_r` o `finalize_execution_with_r`, manteniendo visibles las alertas
y los componentes que no pudieron evaluarse.

Los planes admitidos, políticas y límites se describen en
[semántica](https://github.com/htroya/equiframe/blob/main/docs/semantics.md), [API](https://github.com/htroya/equiframe/blob/main/docs/api.md) y [recetas](https://github.com/htroya/equiframe/blob/main/docs/recipes.md).

## Documentación

- [Manual de la biblioteca](https://github.com/htroya/equiframe/blob/main/docs/index.md) e [inicio en español](https://github.com/htroya/equiframe/blob/main/docs/inicio.md).
- [Referencia de la API y CLI](https://github.com/htroya/equiframe/blob/main/docs/api.md).
- [Ejemplos de uso completos](https://github.com/htroya/equiframe/blob/main/docs/journeys.md).
- [Compatibilidad](https://github.com/htroya/equiframe/blob/main/docs/compatibility.md) y [cambios entre versiones](https://github.com/htroya/equiframe/blob/main/CHANGELOG.md).
- [Seguridad](https://github.com/htroya/equiframe/blob/main/SECURITY.md) y [licencias de terceros](https://github.com/htroya/equiframe/blob/main/THIRD_PARTY_NOTICES.md).
- [Portal del proyecto y seguimiento técnico](https://github.com/htroya/equiframe/blob/main/docs/index.md).

## Origen del proyecto

EquiFrame surge de un proyecto de investigación de Hernán Troya sobre
diferencias semánticas entre motores de procesamiento tabular. La biblioteca
puede usarse con datos propios y conserva el benchmark experimental como
distribución separada.

## Ayuda y desarrollo

Utiliza el [seguimiento de incidencias](https://github.com/htroya/equiframe/issues)
para consultas técnicas, errores reproducibles y propuestas. Indica la versión
de EquiFrame, Python, sistema operativo, motores y el resultado esperado.
Los casos mínimos compartidos deben usar datos que puedas publicar.

Para problemas sensibles, sigue la [política de seguridad](https://github.com/htroya/equiframe/blob/main/SECURITY.md).

## Contribuciones

Son bienvenidas las correcciones, mejoras de documentación y propuestas.
La [guía de contribución](https://github.com/htroya/equiframe/blob/main/CONTRIBUTING.md) describe cómo preparar el entorno,
ejecutar las comprobaciones y proponer cambios. Las instrucciones de desarrollo
y revisión se mantienen en el repositorio.

## Licencia

El código propio de EquiFrame y EquiFrame Benchmark se distribuye bajo
[MIT](https://github.com/htroya/equiframe/blob/main/LICENSE). Los componentes de terceros conservan sus licencias:
los esquemas CycloneDX incluidos mantienen Apache-2.0.
Consulta los [avisos de terceros](https://github.com/htroya/equiframe/blob/main/THIRD_PARTY_NOTICES.md) y el [alcance de la licencia](https://github.com/htroya/equiframe/blob/main/docs/licensing.md).
