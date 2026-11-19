# Temporal validation with EquiFrame 0.14.5

We assigned whole SERCOP procedures to the month of release in Guayaquil.
The model used 48 correct batches from January through June 2025 for training,
48 from July through September for calibration, and 60 from October through
December for testing. The October–December cases were held out of model
selection, fitting and threshold calculation. The same monthly quotas supplied
8 regular matches, 4 larger correct batches, and 2 cases of each of four
controlled faults. The exact oracle calculated reference totals in integer
cents from public awards. Pandas, Polars and DuckDB agreed on the 60 holdout
cases, giving 180 holdout and 276 total native executions.

The model uses profile 1.1, 200 trees, seed 7, and calibration alpha 0.05.

| Check | Faults detected / 24 | Omissions / 24 | False alarms / 36 |
| --- | ---: | ---: | ---: |
| Exact comparison | 24 | 0 | 0 |
| Rule comparing groups by buyer and currency | 24 | 0 | 0 |
| Isolation Forest | 9 | 15 | 3 |

| Isolation Forest | October | November | December | Total |
| --- | ---: | ---: | ---: | ---: |
| Dropped groups detected | 0 / 2 | 0 / 2 | 0 / 2 | 0 / 6 |
| Scaled groups detected | 2 / 2 | 2 / 2 | 2 / 2 | 6 / 6 |
| Redistributions detected | 0 / 2 | 1 / 2 | 1 / 2 | 2 / 6 |
| One-cent deviations detected | 1 / 2 | 0 / 2 | 0 / 2 | 1 / 6 |
| False alarms on regular matches | 0 / 8 | 0 / 8 | 1 / 8 | 1 / 24 |
| False alarms on larger correct batches | 1 / 4 | 0 / 4 | 1 / 4 | 2 / 12 |

The exact and grouped checks agree here because the declared output is
already aggregated by buyer and currency. When acceptance requires line
items, the [ETL acceptance guide](../../../../docs/outcome-gates.md) explains
how to enforce full keys, multiplicity and values. These observations cover
the selected 2025 batches and injected faults. The holdout comes from one
public corpus with a single model seed, so the rates describe this workload.

The [machine-readable report](report.json) records month and fault metrics,
the installed wheel hash, dependency versions, source file hashes, selection
identities and script hashes. The [artifact SHA-256 list](SHA256SUMS.txt)
identifies both distributions. The script checked the installed core package
files against the wheel before running.

Reproduce from the source tree using the exact wheel in a clean environment
with the report's dependency versions and the original identified CSV files.

```sh
python -m pip install "./equiframe-0.14.5-py3-none-any.whl[engines,ml]"
python validation/library_detection/temporal_spending.py \
  --csv-dir /path/to/2025/csv \
  --wheel ./equiframe-0.14.5-py3-none-any.whl \
  --output /path/to/new-report.json
```
