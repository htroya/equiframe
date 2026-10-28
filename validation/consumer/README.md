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
The optional reviewed [offline corpus](../corpus/README.md) is included under
`validation/corpus/`, with 219 effective public-source records and its own
attribution, conditions and active manifest. From the repository root, pass
`--data validation/corpus` to the commands above. Larger and private datasets
remain outside Git. Each input manifest must enumerate every file actually
consumed, and each digest is checked before and after execution.
An empty, incomplete, changed or linked inventory is rejected. Output directories
must be new; local reports and data never belong in a public commit.

The suite distinguishes successful acceptance, semantic differences, invalid
input and non-evaluable judgments. A suite exit of zero means its expected
outcomes matched; it does not mean that every input was accepted.
Normal and optimized Python runs are separate executions.

## Operational checks

Use a fresh output directory for each command. Select a single program and
deliberate defect without replacing the independently calculated expectation:

```bash
python -I -m equiframe_consumer_lab run --program reconciliation --variant defect --source pandas --target duckdb --data /path/to/frozen-data --output /path/to/new-defect-run
```

Programs are `reconciliation`, `refactor`, `migration` and `preparation`;
variants are `good`, `defect` and `not_evaluable`. Source and target must be
different members of `pandas`, `polars` and `duckdb`. A single case returns
0 for acceptance, 1 for a semantic difference, 2 for invalid input or an
execution/evidence failure, and 3 for a non-evaluable judgment.

Run the complete matrix under an actual optimized interpreter, or exercise the
separate synthetic domain and local Parquet publication controls:

```bash
python -I -O -m equiframe_consumer_lab run --all --require-optimized --data /path/to/frozen-data --output /path/to/new-optimized-run
python -I -m equiframe_consumer_lab domain-checks --output /path/to/new-domain-run
python -I -O -m equiframe_consumer_lab fault-checks --output /path/to/new-fault-run
```

`--require-optimized` is valid only with `run --all`; the runner checks the
interpreter's optimization flag and passes `-O` to its children. Domain checks
exercise finance, retail and telemetry acceptance, changed values and invalid
physical inputs. Fault checks cover acceptance, rejected input, controlled
precommit failure, prior-publication preservation and report corruption. Their
successful suite exits mean the expected outcomes matched. Run receipts record
which checks actually executed.

Local publication uses a staged version and an atomic visibility pointer on a
single-writer filesystem. A terminal receipt can fail after that pointer changes;
a nonzero exit then requires inspecting the publication and available receipts.
This procedure provides no distributed-transaction or power-loss guarantee.

The four program workflows limit input/output to 10,000 rows and capture or
transport to 16 MiB. Comparison, native execution and migration use cooperative
30-, 60- and 180-second budgets respectively. DuckDB uses one thread and a
128 MB native memory setting. The matrix launches one child at a time with a
300-second process timeout. Program and domain suites stop new work below
4 GiB of free filesystem space. These settings do not impose a process-RSS cap
or a total output-directory quota. Private inputs, reports and local publication
outputs must remain outside public commits. The reviewed public-source corpus
is an explicit exception for input data; it is excluded from PyPI distributions.

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
not publish private datasets, old reports or earlier private distribution artifacts.
