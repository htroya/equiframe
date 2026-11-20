# Temporal replay with EquiFrame 0.15.0

The replay used the installed 0.15.0 core wheel and the same 2025 SERCOP
selection as the [0.14.5 experiment](../temporal-0145/README.md). The model
trained on January through June and calibrated on July through September.
October through December supplied 24 controlled faults and 36 correct batches.
Pandas, Polars and DuckDB agreed on the 60 held-out cases. There were 276
native executions across training, calibration and holdout.

| Check | Faults detected / 24 | Omissions / 24 | False alarms / 36 |
| --- | ---: | ---: | ---: |
| Exact comparison | 24 | 0 | 0 |
| Group check by buyer and currency | 24 | 0 | 0 |
| Isolation Forest | 9 | 15 | 3 |

The per-case decisions reproduced across the two measured wheels. These
rates describe the selected corpus, controlled faults and model seed.
The [JSON report](report.json) records the installed wheel and script hashes,
dependency versions and results by month and fault. Use the earlier
[reproduction procedure](../temporal-0145/README.md#temporal-validation-with-equiframe-0145)
with the 0.15.0 wheel and a new report path.
