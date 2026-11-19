# Measured anomaly detection in EquiFrame 0.14.0

This standalone library experiment was completed on 19 November 2026 against
the public installed **0.14.0 Beta**. It measures generated tabular transformations
with exact expected results; it is independent of any domain-specific application
or deployed service. It is a controlled benchmark, not a production accuracy claim.

## Reproduce and inspect

- [Runnable protocol and interpretation](../validation/library_detection/README.md).
- [Frozen protocol](../validation/library_detection/results/v1/protocol.json).
- [Complete report, all three model seeds and confidence intervals](../validation/library_detection/results/v1/report.json).
- [All 3,840 scored records, gzip CSV](../validation/library_detection/results/v1/cases.csv.gz).
- [Separate component API costs](../validation/library_detection/results/v1/component-costs.json).
- [Installed files matched the original release wheel](../validation/library_detection/results/v1/runtime-identity.json).

Install `equiframe[pandas,ml]==0.14.0` in a clean environment, then run:

```sh
python -I validation/library_detection/run.py --output /absolute/new/evidence
python -I validation/library_detection/verify_results.py /absolute/new/evidence --source validation/library_detection/run.py
python -I validation/library_detection/component_costs.py --output /absolute/new/component-costs.json
```

The verifier also reads the compressed published records directly:

```sh
python -I validation/library_detection/verify_results.py validation/library_detection/results/v1 --source validation/library_detection/run.py
```

## Design and denominators

**2,304 native Pandas executions** cover identity preservation and integer-cent
discount aggregation. Each workload has 256 correct training executions, 256
separate correct calibration executions, 256 correct in-distribution test cases,
256 divergent test cases (64 in each of four fault classes), and 128 additional
correct test cases under a prespecified change of workload distribution.

A separate Python dictionary/integer oracle checks actual captured outputs.
Correct training/calibration selections are confirmed by that oracle. Labels,
fault names, expected outputs and peer-engine outputs never enter model features.
Source hashes are unique across cases and partitions. Preprocessing, 200-tree
forests, calibration alpha 0.05 and all feature definitions were fixed before
the reported test inference. Seed 7 is primary; 23 and 71 are prespecified
sensitivity models on the same cases, not additional independent observations.

## Primary in-distribution results

M is Isolation Forest; B is the separate MAD baseline. Each row has 256
oracle-confirmed divergent and 256 correct test cases. Unavailable outcomes
are reported separately and are never counted as no-alert decisions.

| Workload | Method | TP / FN | FP / TN | Recall (Wilson 95%) | False alarms (Wilson 95%) | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| identity | M | 88 / 168 | 28 / 228 | 34.38% (28.83–40.39%) | 10.94% (7.68–15.35%) | 100.00% |
| identity | B | 196 / 60 | 16 / 240 | 76.56% (71.00–81.34%) | 6.25% (3.88–9.91%) | 100.00% |
| discount_aggregation | M | 14 / 242 | 18 / 238 | 5.47% (3.29–8.97%) | 7.03% (4.49–10.84%) | 100.00% |
| discount_aggregation | B | 195 / 61 | 16 / 240 | 76.17% (70.59–80.98%) | 6.25% (3.88–9.91%) | 100.00% |

Precision and F1, which depend on the designed test prevalence, are retained
in the complete JSON. These intervals describe generator draws conditional
on one fitted model; they do not estimate deployment-population uncertainty.

### Detection by fault class

| Workload | Fault | M detected / 64 | B detected / 64 |
| --- | --- | --- | --- |
| identity | fill_null | 64 | 64 |
| identity | drop_rows | 7 | 64 |
| identity | duplicate_rows | 10 | 64 |
| identity | permute_values | 7 | 4 |
| discount_aggregation | drop_group | 2 | 64 |
| discount_aggregation | scale_amount | 5 | 64 |
| discount_aggregation | redistribute | 1 | 61 |
| discount_aggregation | one_cent | 6 | 6 |

### Correct cases under workload shift

These 128 correct cases per workload have larger row/group counts and,
for identity, a higher legitimate NULL rate. They are excluded from the
in-distribution false-alarm denominator above.

| Workload | M false alerts / 128 | B false alerts / 128 |
| --- | --- | --- |
| identity | 128 | 128 |
| discount_aggregation | 37 | 3 |

### Sensitivity to forest seed

| Workload | Forest seed | M recall | M false-alarm rate |
| --- | --- | --- | --- |
| identity | 7 | 34.38% | 10.94% |
| identity | 23 | 32.03% | 9.38% |
| identity | 71 | 31.64% | 8.59% |
| discount_aggregation | 7 | 5.47% | 7.03% |
| discount_aggregation | 23 | 4.69% | 6.64% |
| discount_aggregation | 71 | 3.12% | 6.64% |

## Measured costs

The execution experiment separates the `execute` API (including capture
and materialization) from profile extraction. Medians below use all 1,152
generated executions per workload, including the shifted correct cases.

| Workload | Execute median / p95, ms | Profile median / p95, ms |
| --- | --- | --- |
| identity | 128.151 / 193.743 | 188.194 / 806.279 |
| discount_aggregation | 121.461 / 176.375 | 156.862 / 627.060 |

A separate warm experiment measures public M-only, B-only and joint APIs on
generated feature vectors. It excludes execution, profiling and cold imports
and includes each API’s validation, preprocessing and provenance hashing.
Numbers are median wall time over five repetitions of the same frozen model.

| Raw features | Batch | M-only batch, ms | M amortized per profile, ms | B-only batch, ms | Joint batch, ms |
| --- | --- | --- | --- | --- | --- |
| 4 | 1 | 1636.314 | 1636.314 | 1738.732 | 2034.132 |
| 4 | 32 | 1644.232 | 51.382 | 1614.663 | 2001.860 |
| 4 | 512 | 3021.245 | 5.901 | 2832.401 | 3269.935 |
| 6 | 1 | 2155.870 | 2155.870 | 1778.292 | 2397.610 |
| 6 | 32 | 2358.039 | 73.689 | 2175.874 | 3246.061 |
| 6 | 512 | 4530.146 | 8.848 | 4064.892 | 5406.505 |

Full JSON also retains process CPU times and joint fit/calibration times.
The fit/calibration APIs produce both M and B, so their timings are explicitly
joint. Amortized batch cost is not single-request latency. One Windows x86_64
host, Python 3.13.18, Pandas 3.1.0, PyArrow 25.0.1, NumPy 2.5.3 and
scikit-learn 1.9.1 were measured. Concurrent host load, caches and dependency
versions can change costs. No peak-memory or cross-platform cost claim is made.

## Interpretation and maturity

Isolation Forest reports unusual profiles rather than exact business errors.
Value permutations can retain all chosen identity features; one-cent changes
can retain the grouped maximum. Forests also cannot split features that were
constant throughout training. A correct workload shift can trigger novelty
alerts. The recorded false negatives and false positives remain part of the
result; they were not removed or used to tune a replacement model.

Use semantic comparison and justified deterministic rules for acceptance.
Use anomaly scores as an additional signal under a justified normal-training
and calibration distribution. A lack of alert does not certify equivalence.
The observed cases support a bounded public Beta experiment; they do not
establish universal detection power or a Production/Stable promotion.

This evaluation is complete for its frozen generated-data scope. External
datasets, other transformations and later dependency/platform combinations
need their own prospective evaluation. These are library evidence questions
and require no particular application deployment.

See [feature semantics](grouped-profiles.md), [compatibility](compatibility.md)
and the [scikit-learn novelty-detection documentation](https://scikit-learn.org/stable/modules/outlier_detection.html).
