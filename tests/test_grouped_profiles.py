"""Independent synthetic checks; no thesis labels or statistical efficacy claims."""

import random
from fractions import Fraction

import pyarrow as pa
import pytest
from pydantic import ValidationError
from test_profiles import make_run

import equiframe as ef

METRICS = (
    "prop_grupos_suma_modificada",
    "max_diferencia_relativa_grupo",
    "prop_grupos_cambio_desde_cero",
    "cobertura_grupos",
)


def feature(metric=METRICS[0], **kwargs):
    return ef.GroupedProfileFeature(
        name=metric,
        metric=metric,
        table=kwargs.pop("table", "result"),
        column="amount",
        reference_table=kwargs.pop("reference_table", "source"),
        reference_column="raw",
        by=("entity", "currency"),
        **kwargs,
    )


def table(keys, amounts, *, input=False):
    return pa.table(
        {
            "entity": pa.array(keys, pa.string()),
            "currency": ["USD"] * len(keys),
            "raw" if input else "amount": pa.array(amounts, pa.int64()),
        }
    )


def extract(
    tmp_path, output, source, *, metrics=METRICS, options=None, cancellation=None, **kwargs
):
    run = make_run(tmp_path / "run", "aggregations", output, {"source": source})
    spec = ef.ProfileSpec(
        family="aggregations",
        feature_version="1.1",
        features=tuple(feature(metric, **kwargs) for metric in metrics),
    )
    return ef.profile_execution(
        run,
        spec=spec,
        options=options,
        cancellation=cancellation,
        work_dir=tmp_path / "profiles",
    )


def test_exact_input_output_metrics_and_persistence(tmp_path):
    result = extract(
        tmp_path,
        table(["A", "A", "B", "C", "E"], [90, 60, 25, 50, 7]),
        table(["A", "A", "B", "C", "D"], [40, 60, 0, 50, 9], input=True),
    )
    assert result.complete
    assert result.metadata.implementation_version == "equiframe-profiles-1.1"
    assert [o.value for o in result.vector.observations] == [2 / 3, 1 / 2, 1, 3 / 5]
    assert [(o.numerator, o.denominator) for o in result.vector.observations] == [
        (2, 3),
        (1, 2),
        (1, 1),
        (3, 5),
    ]
    path = tmp_path / "profiles" / result.metadata.profile_id / "profile.json"
    assert ef.read_profile(path) == result
    assert (
        ef.ProfileSpec.model_validate_json(result.vector.spec.model_dump_json())
        == result.vector.spec
    )
    assert ef.ProfileVector.model_validate_json(result.vector.model_dump_json()) == result.vector


def test_explicit_opt_in_and_unchanged_old_profile_shape():
    with pytest.raises(ValidationError, match="feature_version"):
        ef.ProfileSpec(family="aggregations", features=(feature(),))
    old = ef.ProfileSpec(
        family="aggregations",
        features=(ef.ProfileFeature(name="count", metric="log_filas", table="result"),),
    )
    assert old.feature_version == "1.0"
    assert "GroupedProfileFeature" not in str(old.model_dump())
    assert ef.ProfileSpec.model_validate(old.model_dump()) == old


@pytest.mark.parametrize(
    "field,value", [("label", True), ("expected", "peer"), ("engine", "duckdb")]
)
def test_predictor_spec_rejects_foreign_metadata(field, value):
    with pytest.raises(ValidationError):
        feature(**{field: value})


@pytest.mark.parametrize("reference", ["peer_engine", "held_out_expected"])
def test_reference_must_be_a_declared_captured_input(tmp_path, reference):
    run = make_run(
        tmp_path / "run",
        "aggregations",
        table(["A"], [1]),
        {"source": table(["A"], [1], input=True)},
    )
    spec = ef.ProfileSpec(
        family="aggregations", feature_version="1.1", features=(feature(reference_table=reference),)
    )
    with pytest.raises(ValueError, match="own input"):
        ef.profile_execution(run, spec=spec, work_dir=tmp_path / "profiles")


def test_metrics_require_the_execution_output(tmp_path):
    run = make_run(
        tmp_path / "run",
        "aggregations",
        table(["A"], [1]),
        {
            "source": table(["A"], [1], input=True),
            "other": table(["A"], [1]),
        },
    )
    spec = ef.ProfileSpec(
        family="aggregations", feature_version="1.1", features=(feature(table="other"),)
    )
    with pytest.raises(ValueError, match="output"):
        ef.profile_execution(run, spec=spec, work_dir=tmp_path / "profiles")


def test_one_aggregation_serves_all_four_metrics(tmp_path, monkeypatch):
    import equiframe._grouped_profiles as kernel

    original = kernel.compare_grouped
    calls = []

    def checked(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(kernel, "compare_grouped", checked)
    result = extract(tmp_path, table(["A", "B"], [3, 1]), table(["A", "B"], [1, 0], input=True))
    assert result.complete and len(calls) == 1
    assert result.vector.observations[1].value == 2  # relative changes may exceed one
    assert calls[0]["options"].max_examples == 0


def test_null_measures_are_unavailable_and_never_imputed(tmp_path):
    result = extract(tmp_path, table(["A", "B"], [None, 3]), table(["A", "B"], [0, 3], input=True))
    assert not result.complete
    assert all(o.state == "not_evaluable" and o.value is None for o in result.vector.observations)
    training = ef.NormalTrainingProfiles(
        purpose="normal_training", profiles=(result.vector,), selection_manifest_sha256="a" * 64
    )
    with pytest.raises(ValueError, match="failed measurements"):
        ef.fit_preprocessor(training, spec=result.vector.spec)


def test_zero_baselines_and_empty_denominators(tmp_path):
    result = extract(tmp_path, table(["A", "B"], [5, 0]), table(["A", "B"], [0, 0], input=True))
    modified, relative, zero, coverage = result.vector.observations
    assert result.complete
    assert modified.value == zero.value == 0.5 and coverage.value == 1
    assert relative.state == "undefined" and relative.denominator == 0
    assert relative.value is None


def test_disjoint_groups_retain_zero_coverage(tmp_path):
    result = extract(tmp_path, table(["B"], [1]), table(["A"], [1], input=True))
    assert result.complete
    assert all(o.state == "undefined" for o in result.vector.observations[:3])
    assert result.vector.observations[3].value == 0


@pytest.mark.parametrize(
    "options", [ef.ProfileOptions(max_work=1), ef.ProfileOptions(max_distinct=1)]
)
def test_exhausted_budgets_do_not_return_partial_values(tmp_path, options):
    result = extract(
        tmp_path, table(["A", "B"], [1, 2]), table(["A", "B"], [1, 2], input=True), options=options
    )
    assert not result.complete
    assert all(o.state == "not_evaluable" and o.value is None for o in result.vector.observations)


def test_cancelled_extraction_has_no_model_values(tmp_path):
    token = ef.CancellationToken()
    token.cancel()
    result = extract(tmp_path, table(["A"], [1]), table(["A"], [1], input=True), cancellation=token)
    assert not result.complete and all(o.value is None for o in result.vector.observations)


def test_null_keys_require_explicit_admission(tmp_path):
    a, b = table([None, "B"], [2, 3]), table([None, "B"], [1, 3], input=True)
    rejected = extract(tmp_path / "reject", a, b)
    accepted = extract(tmp_path / "group", a, b, null_keys="group")
    assert not rejected.complete
    assert accepted.complete and accepted.vector.observations[0].value == 0.5


@pytest.mark.parametrize("seed", range(12))
def test_independent_exact_reference_for_random_group_totals(tmp_path, seed):
    rng = random.Random(seed)
    a = [(rng.randrange(6), rng.randrange(-1000, 1000)) for _ in range(30)]
    b = [(rng.randrange(6), rng.randrange(-1000, 1000)) for _ in range(30)]

    def totals(rows):
        result = {}
        for key, value in rows:
            result[key] = result.get(key, 0) + value
        return result

    left, right = totals(a), totals(b)
    common = left.keys() & right.keys()
    union = left.keys() | right.keys()
    modified = sum(left[k] != right[k] for k in common)
    rel = [Fraction(abs(left[k] - right[k]), abs(right[k])) for k in common if right[k]]
    result = extract(
        tmp_path,
        table([str(k) for k, _ in a], [v for _, v in a]),
        table([str(k) for k, _ in b], [v for _, v in b], input=True),
    )
    assert result.complete
    observed = result.vector.observations
    assert observed[0].value == modified / len(common)
    if rel:
        assert Fraction(observed[1].numerator, observed[1].denominator) == max(rel)
    assert observed[3].value == len(common) / len(union)


def test_existing_preprocessor_and_detector_pipeline_accept_version_11(tmp_path):
    def vector(i):
        return extract(
            tmp_path / str(i),
            table(["A", "B"], [100 + i, 50]),
            table(["A", "B"], [100, 50], input=True),
            metrics=(METRICS[0], METRICS[1], METRICS[3]),
        ).vector

    vectors = {i: vector(i) for i in (0, 1, 2, 3, 4, 5, 8)}
    training = ef.NormalTrainingProfiles(
        purpose="normal_training",
        profiles=tuple(vectors[i] for i in (0, 1, 2, 3)),
        selection_manifest_sha256="a" * 64,
    )
    calibration = ef.NormalCalibrationProfiles(
        purpose="normal_calibration",
        profiles=(vectors[4], vectors[5]),
        selection_manifest_sha256="b" * 64,
    )
    fitted = ef.fit_detectors(
        training,
        spec=vectors[0].spec,
        config=ef.IsolationForestConfig(n_estimators=7, max_samples=4, random_state=7),
        support=ef.DetectorSupport(
            min_training_rows=3,
            min_calibration_rows=2,
            rationale="Synthetic software integration check",
        ),
    )
    assert fitted.m.state == "fitted"
    bundle = ef.calibrate_detectors(fitted, calibration, alpha="0.5")
    detected = ef.detect(bundle, (vectors[8],))
    assert len(detected.m) == 1
    matrix = ef.transform_profiles(fitted.preprocessor, (vectors[8],))
    assert len(matrix.values) == 1 and all(isinstance(x, float) for x in matrix.values[0])
    assert not any("entity" in name or "engine" in name for name in matrix.columns)
    path = tmp_path / "bundle.json"
    ef.write_detector_bundle(bundle, path)
    assert ef.read_detector_bundle(path) == bundle


def test_decimal_sums_ignore_ambient_decimal_precision(tmp_path):
    from decimal import Decimal, localcontext

    def exact(column, values):
        return pa.table(
            {
                "entity": ["A", "A"],
                "currency": ["USD", "USD"],
                column: pa.array([Decimal(v) for v in values], pa.decimal128(30, 8)),
            }
        )

    output = exact("amount", ["9007199254740993.00000002", "0.00000001"])
    source = exact("raw", ["9007199254740993.00000001", "0.00000001"])
    with localcontext() as context:
        context.prec = 2
        result = extract(tmp_path, output, source)
    assert result.complete
    relative = result.vector.observations[1]
    assert Fraction(relative.numerator, relative.denominator) == Fraction(
        1, 900719925474099300000002
    )


def test_profile_implementation_marker_cannot_mislabel_new_features(tmp_path):
    result = extract(tmp_path, table(["A"], [2]), table(["A"], [1], input=True))
    forged = result.model_copy(
        update={
            "metadata": result.metadata.model_copy(
                update={"implementation_version": "equiframe-profiles-1.0"}
            )
        }
    )
    with pytest.raises(ValidationError, match="implementation"):
        ef.ProfileResult.model_validate(forged)


def test_declared_numeric_units_cannot_be_silently_mixed(tmp_path):
    from rule_helpers import captured

    source, output = table(["A"], [1], input=True), table(["A"], [1])
    run = make_run(tmp_path / "original", "aggregations", output, {"source": source})
    document = run.plan.contract.model_dump()
    document["output"]["schema_spec"]["columns"][2]["numeric_policy"]["unit"] = "other_unit"
    contract = ef.Contract.model_validate(document)
    execution = captured(contract, {"source": source}, output, tmp_path / "other_unit")
    spec = ef.ProfileSpec(family="aggregations", feature_version="1.1", features=(feature(),))
    with pytest.raises(ValueError, match="numeric units"):
        ef.profile_execution(execution, spec=spec, work_dir=tmp_path / "profiles")


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
def test_actual_native_30000_row_execution_profiles(engine, tmp_path):
    # Independent literal: 15,000 input units per group; the A output adds one.
    source = table(["A"] * 15000 + ["B"] * 15000, [1] * 30000, input=True)
    expected = table(["A", "B"], [15001, 15000])
    declaration = make_run(tmp_path / "declaration", "aggregations", expected, {"source": source})
    registry = ef.TransformationRegistry()
    if engine == "pandas":

        def pandas_transform(tables, context):
            result = tables["source"].groupby(["entity", "currency"], as_index=False)["raw"].sum()
            result = result.rename(columns={"raw": "amount"})
            result.loc[result["entity"] == "A", "amount"] += 1
            return result

        registry.register(
            ef.PandasTransformation("grouped_profile", pandas_transform, "synthetic.1")
        )
    elif engine == "polars":
        import polars as pl

        def polars_transform(tables, context):
            return (
                tables["source"]
                .group_by("entity", "currency")
                .agg(pl.col("raw").sum().alias("amount"))
                .with_columns(
                    (pl.col("amount") + (pl.col("entity") == "A").cast(pl.Int64)).alias("amount")
                )
            )

        registry.register(
            ef.PolarsTransformation("grouped_profile", polars_transform, "synthetic.1")
        )
    else:
        registry.register(
            ef.DuckDBTransformation(
                "grouped_profile",
                "SELECT entity,currency,CAST(SUM(raw) AS BIGINT) + "
                "CASE WHEN entity='A' THEN 1 ELSE 0 END AS amount "
                "FROM source GROUP BY entity,currency",
                "synthetic.1",
            )
        )
    executed = ef.execute(
        ef.ExecutionPlan(
            contract=declaration.plan.contract, engine=engine, transformation_id="grouped_profile"
        ),
        source=ef.LocalDataSource({"source": ef.ArrowInput(source)}),
        registry=registry,
        work_dir=tmp_path / "native",
    )
    assert executed.state == "completed", executed.problem
    spec = ef.ProfileSpec(
        family="aggregations",
        feature_version="1.1",
        features=tuple(feature(metric) for metric in METRICS),
    )
    result = ef.profile_execution(executed, spec=spec, work_dir=tmp_path / "profiles")
    assert result.complete
    observed = result.vector.observations
    assert observed[0].value == 0.5 and observed[3].value == 1
    assert Fraction(observed[1].numerator, observed[1].denominator) == Fraction(1, 15000)
    assert observed[2].state == "undefined"
