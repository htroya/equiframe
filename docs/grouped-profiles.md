# Grouped sums as execution-profile features

EquiFrame 0.14.0 adds `GroupedProfileFeature` with explicit
`ProfileSpec(feature_version="1.1")`. It uses the output and a declared captured
input of **one execution**. It accepts no peer-engine output, held-out expected
result, label or fault identifier. Existing feature-version 1.0 formulas and
serialized vectors retain their original meaning and fingerprints.

## Declare the relationship before fitting

```python
import equiframe as ef

spec = ef.ProfileSpec(
    family="aggregations",
    feature_version="1.1",
    features=tuple(
        ef.GroupedProfileFeature(
            name=metric,
            metric=metric,
            table="result",
            column="total",
            reference_table="source",
            reference_column="amount",
            by=("department", "currency"),
        )
        for metric in (
            "prop_grupos_suma_modificada",
            "max_diferencia_relativa_grupo",
            "prop_grupos_cambio_desde_cero",
            "cobertura_grupos",
        )
    ),
)
```

Pass the completed `ExecutionResult` to `profile_execution(execution, spec=spec)`.
Both tables and the grouping columns must occur in the execution contract. The
measured table must be its captured output; `reference_table` must be one of its
captured inputs. Numeric column names may differ. Grouping names must be shared
by both tables, and currency should be included whenever amounts use different
currencies. Table content and physical metadata are checked against the captured
artifacts before measurement. Declared numeric units must match for the measures
and numeric grouping keys; the profiler does not convert units or currencies.

These features describe an input/output relationship. Filters, discounts, joins
and other valid transformations can legitimately change group sums. Select and
justify the relationship for the transformation being studied, then fit and
calibrate on independently selected normal profiles of that same relationship.
A changed sum is not itself an error label or an independent expected result.

## Formulas and unavailable values

For each key, `S_out` and `S_in` are exact numeric sums. A common valid group is
modified when `abs(S_out-S_in) > max(absolute_tolerance,
relative_tolerance*abs(S_in))`. Both tolerances default to zero and must be
finite, nonnegative, bounded Decimals. Their admission and NULL-key policy match
the [grouped comparison contract](grouped-comparison.md).

| Metric | Definition |
| --- | --- |
| `prop_grupos_suma_modificada` | Modified common valid groups / common valid groups |
| `max_diferencia_relativa_grupo` | Maximum `abs(S_out-S_in)/abs(S_in)` over common valid groups with nonzero input sum |
| `prop_grupos_cambio_desde_cero` | Modified common valid groups with zero input sum / common valid groups with zero input sum |
| `cobertura_grupos` | Common groups / union of input and output groups |

Added and removed groups are represented by coverage; they are not silently
assigned a zero amount. An empty denominator produces `undefined`, not zero.
NULL, NaN or infinity in a common group's measure makes the grouped measurement
`not_evaluable`. NULL keys require `null_keys="group"`; otherwise measurement is
unavailable. Unsupported types and incomplete resource-limited evaluation never
produce successful partial feature values. A profile containing a failed
measurement is rejected by preprocessing rather than imputed.

Summation and maximum relative differences use exact rational arithmetic. For
the maximum, the observation's numerator and denominator are the reduced exact
ratio, not group counts. For the other metrics they retain the displayed counts.
Conversion to a finite Python float occurs only at the feature-observation/model
boundary. Values outside that representation are unavailable. The relative
maximum may exceed one; the three proportions cannot.

## Fit, calibrate and infer

The returned `ProfileVector` can be passed to the existing
`NormalTrainingProfiles`, `fit_preprocessor` and `fit_detectors` interfaces.
Keep normal training and calibration selections separate with their external
selection-manifest identities; use `NormalCalibrationProfiles` and
`calibrate_detectors` before inference. These types do not authenticate review
or prove normality. Metadata such as run IDs, engines, entity labels and expected
outputs never becomes a numeric matrix column. Feature order, definitions and
version are fingerprinted, and incompatible vectors are rejected.

`equiframe-profiles-1.1` identifies extraction for feature-version 1.1. Readers
retain 1.0 support. Older EquiFrame releases reject the new feature specification;
do not relabel a 1.1 vector or model as 1.0. This addition does not change the IF,
MAD or hybrid algorithms, comparison acceptance, independent R review or the
scientific meaning of an anomaly score.

## Resource scope

Extraction shares `ProfileOptions` and cancellation with the existing profiler.
One conservative work bound is charged before each distinct grouped aggregation;
the grouped kernel also checks that bound, its remaining timeout and group/row/
byte limits. Identical grouping declarations across metrics reuse a result only
within that profile execution. Changing tolerances or NULL policy requires a new
aggregation. Cached results are not reused between executions or training sets.
These checks are cooperative and do not impose a process RSS quota or guarantee
streaming. No group examples or raw entity labels are embedded in the vector.

The source and installed-package tests use synthetic independent expectations,
error and leakage-boundary cases, historical readers and the existing model
pipeline. They establish software behavior, not empirical detection accuracy.

From a repository checkout or source distribution, the self-contained example
`python examples/grouped_profiles.py --engine pandas --rows 30000` executes a
native transformation, extracts all four features and checks independent literal
expectations. Select `polars` or `duckdb` to run their native implementations.
The example uses temporary synthetic data and removes its files when finished.
