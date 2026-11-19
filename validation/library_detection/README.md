# Standalone library detection benchmark

This benchmark measures the **installed public EquiFrame 0.14.0** implementation
on generated tabular transformations. It requires no research corpus, human
review, DW, portal, API key or service. Its scope is a controlled library
experiment; the results do not establish accuracy on an arbitrary user's data.

The [measured v1 report](../../docs/detection-benchmark.md) links the frozen
protocol, complete JSON, compressed per-case decision records and component costs.

## Reproduce

Use a fresh Python 3.10–3.13 environment outside the EquiFrame source tree:

```sh
python -m pip install "equiframe[pandas,ml]==0.14.0"
python -m pip check
python -I validation/library_detection/run.py --output /absolute/new/evidence
```

The output directory must not already exist. The script writes `protocol.json`
**before generating cases**, then `cases.csv` and `report.json` on completion.
The script SHA-256, dependencies, Python version, platform, source/expected/actual
hashes, split identities, model fingerprints, decisions and costs are recorded.
No source rows or saved models are published. Scratch captures are removed after
each case. Keep the command output when diagnosing an incomplete run.

To reconcile the published records without re-executing the experiment:

```sh
python -I validation/library_detection/verify_results.py validation/library_detection/results/v1 --source validation/library_detection/run.py
```

The verifier reads either `cases.csv` or its lossless `cases.csv.gz` publication,
checks hashes and recomputes counts, unavailable coverage and rate denominators.

For a short engineering check, use `--smoke` with another new output directory.
Smoke results are explicitly marked and are not the reported evaluation.

The checked execution uses Python 3.13.18, EquiFrame 0.14.0, NumPy 2.5.3,
scikit-learn 1.9.1, Pandas 3.1.0 and PyArrow 25.0.1 on Windows x86_64.
Use the versions recorded in a report when comparing model fingerprints.
The supported dependency ranges do not promise identical forests across versions.

Execution and model fingerprints bind a particular observed run. Selection
manifests include measured timings, so repeating a run creates new manifest and
bundle fingerprints even when its numeric profiles and decisions reproduce.
Compare the seed-specific decisions and denominators under the recorded versions;
wall-clock observations are not expected to reproduce byte for byte.

## Fixed experiment

Each of two workloads has 256 correct training executions, 256 separate correct
calibration executions, 256 correct test executions, four fault classes with
64 executions each, and 128 additional correct executions under distribution
shift: **1,152 executions per workload, 2,304 total**.

- **Identity:** preserve integer IDs, nullable integer amounts and multiplicity.
  Faults fill NULL with zero, remove rows, duplicate rows or exchange values
  between two IDs while retaining the univariate statistics.
- **Discount aggregation:** apply each row's basis-point discount with integer
  division, then sum integer cents by department. Faults drop a group, multiply
  totals, redistribute amounts while retaining the global total, or change one
  group by one cent.

Independent deterministic seeds define each workload/split/case. Source hashes
must be unique across all cases. Correct training/calibration selections are
confirmed by a separate Python oracle, which uses row dictionaries and integer
arithmetic rather than the native Pandas transformation. Actual captured outputs
are checked: an attempted fault that changes nothing stops the run instead of
receiving an invented positive label. Row order is ignored; keys, multiplicity,
integer values and NULL/zero distinctions are retained.

## Detector inputs and evaluation

Only the execution's own captured inputs and output enter its profile. No fault
name, label, independent expected result, test statistic or peer output is a
predictor. Identity uses feature-version 1.0 (row count, output/input ratio,
NULL rate and key cardinality). Discount aggregation uses feature-version 1.1,
with grouped input/output sums as documented in
[grouped profiles](../../docs/grouped-profiles.md).

Isolation Forest uses 200 trees, maximum 256 training samples per tree, primary
seed 7 and fixed sensitivity seeds 23 and 71. MAD is a separate baseline.
Preprocessing is fitted only on training profiles. The frozen calibration
threshold uses alpha 0.05 and the existing strict `score > threshold` rule.
Test cases never select features, seeds, thresholds or a preferred result.
Sensitivity seeds reuse the same cases and do not multiply the sample size.

Report TP, FP, TN, FN, recall, precision, F1, false-positive rate and unavailable
coverage per workload and fault. Wilson 95% intervals describe independent
generator draws conditional on a fitted model. They are not uncertainty estimates
for external populations. Correct shifted cases have a separate false-alarm
denominator and are excluded from the primary in-distribution rates.

## Cost interpretation

`component_costs.py --output /absolute/new/component-costs.json` runs a separate
warm API experiment on generated vectors with four or six raw features and
batches of 1, 32 and 512 profiles. Five repetitions record wall time and process
CPU time for M-only, B-only and joint detection. These vector timings carry no
accuracy claim. The model fit/calibration APIs return M+B jointly and their
times remain explicitly labeled as joint.

Wall-clock costs separate native execution/materialization, profile extraction,
Python oracle labeling, model fitting, calibration and batch inference. The mean
batch inference cost is not a single-request latency measurement. Generation,
imports and scratch cleanup are outside the per-execution/profile clocks; model
calls may include first-use imports. Measurements are observations on one host
under its actual concurrent load. There is no production latency, peak-memory
or cross-platform cost guarantee.

The exact oracle is used to label this experiment; it is not a new library
feature or a universal business-correctness oracle. An anomaly alert describes
unusual features. A lack of alert cannot replace semantic comparison, and a
correct change of workload can legitimately look unusual.

## Validate the evaluator

With pytest available:

```sh
python -m pytest -q validation/library_detection
```

The checks cover exact labels, multiplicity, NULL/zero, value permutations,
per-row rounding, disjoint partitions, unavailable outcomes and denominators.
Result checks also reject an improved-looking detection count and changed
experiment source when they disagree with the retained measurement records.
