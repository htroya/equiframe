# EquiFrame: semantic comparison and dataframe migration

> Release target: **0.12.3**. Check the official index for availability and
> verify the identified artifact hashes. Publication requires the
> [release gates](https://github.com/htroya/equiframe/blob/main/docs/releasing.md).

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

EquiFrame 0.12.3 supports **Python 3.10, 3.11, 3.12 and 3.13**.

```bash
python -m pip install "equiframe[files,engines,ml]==0.12.3"
python -m pip check
```

The base installation is `python -m pip install equiframe==0.12.3`.
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
