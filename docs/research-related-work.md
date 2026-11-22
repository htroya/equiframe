# Research context and the scope of EquiFrame's contribution

EquiFrame provides a reusable instrument for checking whether specific tabular
transformations preserve a declared contract. Its research question concerns
the information represented in execution profiles and the measured benefit,
false alarms and cost of adding Isolation Forest to explicit checks.

Isolation Forest is an existing algorithm. Combining constraints, data profiles
and anomaly detection also has substantial prior work. An implementation or a
new application domain does not by itself establish an original algorithm or
general empirical superiority.

## Directed review on 19 November 2026

The review used directed web searches for combinations of `semantic conformance`,
`dataframe comparison`, `ETL`, `data quality`, `execution profiles`, `Isolation
Forest`, `hybrid` and `entity-aware`. Primary papers and official tool
documentation were selected for their relationship to the problem. Crossref
and DataCite metadata were used to check bibliographic identity. This is a
documented narrative review, not an exhaustive systematic search or a proof
that no comparable system exists.

| Antecedent | Established scope | Implication for EquiFrame |
| --- | --- | --- |
| [DataComPy](https://github.com/capitalone/datacompy) | Compares supported DataFrames/tables, including keyed differences and tolerances. | Tabular comparison is prior functionality. Compare policies and supported inputs explicitly; do not infer a performance advantage from documentation. |
| [Schelter et al. (2018), Deequ](https://www.vldb.org/pvldb/vol11/p1781-schelter.pdf) | Declarative quality constraints, efficient metric computation and anomaly detection over historical quality metrics. | Rules plus learning and metric histories are established ideas. |
| [Breck et al. (2019)](https://proceedings.mlsys.org/paper_files/paper/2019/file/928f1160e52192e3e0017fb63ab65391-Paper.pdf) | Validates data used in machine-learning pipelines, including schema and distribution issues. | Data validation and distribution monitoring do not originate in this project. |
| [S. Liu et al. (2024), SemConT](https://www.vldb.org/pvldb/vol18/p850-liu.pdf) | Tests relational systems against executable SQL semantics. | Independent reference semantics are an important antecedent; testing captured outputs does not prove arbitrary programs equivalent. |
| [Soomro et al. (2026), H-StreamQ](https://doi.org/10.3390/info17080786) | A proof of concept combines entity/context information, rules, Isolation Forest and drift monitoring for electronic health records. Its reported context conditioning did not improve aggregate forest performance. | Context-aware hybrid quality assessment is prior work, and additional features require evidence rather than an assumed benefit. Its healthcare results do not estimate EquiFrame's effectiveness. |
| [Bouman et al. (2024)](https://jmlr.org/papers/v25/23-0570.html) | Compares unsupervised anomaly detectors on multiple tabular datasets. | Detector choice depends on the observed anomaly structure; results for Extended Isolation Forest must not be attributed to ordinary Isolation Forest. |

## Contribution to evaluate

The concrete artifact combines declared contracts, native Pandas/Polars/DuckDB
executions, input/output profiles tied to a single captured execution, independent
expected-output evidence, separate R/M/B/H outcomes and reproducible manifests.
The public-spending proof of concept evaluates this design on an identified
public input snapshot. These are contributions of the implemented instrument
and its evaluation; they are not claims of being the first hybrid detector.

Feature representation 1.2 adds the population mean and variance of absolute
relative grouped changes. For a group present on both sides with a valid
nonzero input total, let `d_g = abs(output_sum - input_sum) / abs(input_sum)`.
The features are `mean(d_g)` and `mean((d_g - mean(d_g))**2)`, with equal weight
per eligible group. They exclude zero-reference and unpaired groups from these
two denominators; the other grouped features continue to expose those cases.
No eligible group produces an explicit undefined measurement. Invalid common
measures produce a not-evaluable measurement. The statistics use exact rational
arithmetic until the finite numeric boundary of the model.

A legitimate filter can change these quantities. They therefore describe
behavior; they are not independent labels of semantic correctness. A profile
can still hide changes within one group or compensating changes that preserve
its statistics. Known invariants belong in explicit checks. A full expected
output remains the stronger source of correctness evidence when available.

## Evidence required for an effectiveness claim

Compare rules, Isolation Forest, MAD and the hybrid on the same held-out cases.
Separate model training, threshold calibration and final testing. Keep the
independent expected output, fault identity, other engine outputs and partition
metadata out of model features. Report TP/FP/TN/FN, coverage, per-fault results,
legitimate workload changes, paired uncertainty and complete operation costs.
Engine or seed repetitions of one input are not new independent observations.

The hypotheses retained from the study are an incremental hybrid sensitivity of
at least five percentage points, at most two percentage points of additional
false alarms and a profile/inference cost below full comparison for the same
materialized outputs. A controlled proof of concept addresses only its specified
workload and sampling process. Neither a publication on PyPI nor successful
software tests confirms these hypotheses.

The [0.14.0 controlled baseline](detection-benchmark.md) remains unchanged,
including its low forest recall, missed faults and legitimate-shift false alarms.
Subsequent experiments must preserve unfavorable results and their original
versions. Preventing controlled distortions illustrates possible benefits to
public reporting. Saved review time and societal impact require separate
measurement.
