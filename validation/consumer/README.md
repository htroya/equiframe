# Consumer validation application

This application now lives in the EquiFrame repository under
`validation/consumer/`. It is a development and integration test tool, separate
from the library and from the two distributions published to PyPI.

It exercises four independently specified programs:

- Financial reconciliation preserves exact decimal rates and record identities.
- Refactoring checks filtering and aggregation against standard-library calculations.
- ETL migration checks a full outer join and preserves zero-padded identifiers.
- Data preparation preserves UTC instants while calculating a declared feature.

Each program compares native Pandas, Polars and DuckDB results against separately
authored expectations. Agreement between two engines alone is insufficient.
Good, deliberately different and non-evaluable cases retain their real outcomes.
The harness defines 72 program/direction/variant cases; an actual run reports how
many executed and matched their expected outcomes.

## Installation and use

The application version is **0.1.18**, paired with **EquiFrame 0.12.2**.
Build it with the existing development toolchain:

```bash
python -m build --no-isolation validation/consumer
```

Install its wheel and the matching core with normal dependency resolution from
a reviewed local wheelhouse. Run outside the source checkout:

```bash
python -m pip install --no-index --find-links /path/to/wheelhouse equiframe-consumer-lab==0.1.18
python -m pip check
python -I -m equiframe_consumer_lab --help
python -I -m equiframe_consumer_lab run --all --data /path/to/frozen-data --output /path/to/new-run
```

Use a supported Python 3.10–3.13 environment and its compatible dependencies.
Frozen datasets remain outside Git. Their manifest must enumerate every file
actually consumed, and each digest is checked before and after execution.
An empty, incomplete, changed or linked inventory is rejected. Output directories
must be new; local reports and data never belong in a public commit.

The suite distinguishes successful acceptance, semantic differences, invalid
input and non-evaluable judgments. A suite exit of zero means its expected
outcomes matched; it does not mean that every input was accepted.
Normal and optimized Python runs are separate executions.

## Tests and scope

The tests cover independent domain calculations, the external extension,
failure receipts and frozen-inventory integrity. The new inventory tests include
omitted inputs, same-size changes, manifest replacement, duplicate paths and a
valid frozen input. Historical test counts are not acceptance of this revision.
No trained detector, business truth or independent human adoption is inferred
from these technical checks.

Original application code is covered by the repository's [MIT license](../../LICENSE)
from 2026-10-28. Third-party rights and data licenses remain separate.
The original private history is retained privately; this source application does
not publish its datasets, old reports or earlier private distribution artifacts.
