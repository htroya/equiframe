"""Frozen training medians, numeric-only matrices, compatibility and persistence."""

import json

import pytest
from pydantic import ValidationError

import equiframe as ef


def spec():
    return ef.ProfileSpec(
        family="nulls_types",
        features=(
            ef.ProfileFeature(
                name="null_rate", metric="tasa_nulos", table="result", columns=("x",)
            ),
        ),
    )


def vector(numerator, denominator, schema=None):
    schema = schema or spec()
    observation = ef.FeatureObservation(
        name="null_rate",
        numerator=numerator,
        denominator=denominator,
        state="available" if denominator else "undefined",
        value=numerator / denominator if denominator else None,
        reason=None if denominator else "empty_denominator",
    )
    return ef.ProfileVector(
        spec=schema, spec_sha256=ef.profile_spec_fingerprint(schema), observations=(observation,)
    )


def training(*profiles):
    return ef.NormalTrainingProfiles(
        purpose="normal_training", selection_manifest_sha256="a" * 64, profiles=profiles
    )


def test_frozen_training_medians_are_shared_and_restorable(tmp_path):
    bundle = ef.fit_preprocessor(training(vector(1, 4), vector(3, 4), vector(0, 0)), spec=spec())
    assert bundle.features[0].median == 0.5 and bundle.features[0].valid_count == 2
    before = bundle.model_dump_json()
    inference = (vector(0, 0), vector(1, 1), vector(0, 1))
    matrix = ef.transform_profiles(bundle, inference)
    assert matrix.values == ((0.5, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    assert matrix.columns == ("null_rate", "null_rate.undefined", "null_rate.not_applicable")
    assert before == bundle.model_dump_json()
    path = tmp_path / "preprocessor.json"
    ef.write_preprocessor(bundle, path)
    restored = ef.read_preprocessor(path)
    # Both future detectors consume this SAME matrix; no separate fitting path.
    assert ef.transform_profiles(restored, inference) == matrix
    with pytest.raises(FileExistsError):
        ef.write_preprocessor(bundle, path)


@pytest.mark.parametrize("purpose", ["calibration", "test", "mixed", "normal_calibration"])
def test_fit_boundary_rejects_other_selection_purposes(purpose):
    with pytest.raises(ValidationError):
        ef.NormalTrainingProfiles(purpose=purpose, selection_manifest_sha256="a" * 64, profiles=())


@pytest.mark.parametrize("policy", ["drop", "not_estimable"])
def test_no_training_support_is_not_estimable(policy):
    for rows in (training(), training(vector(0, 0))):
        bundle = ef.fit_preprocessor(rows, spec=spec(), empty_policy=policy)
        assert bundle.state == "not_estimable"
        assert bundle.features[0].reason == "no_valid_training_values"
        with pytest.raises(ValueError, match="not estimable"):
            ef.transform_profiles(bundle, (vector(1, 2),))


def test_partial_unsupported_features_removed_from_both_detectors():
    base = spec().features[0]
    schema = ef.ProfileSpec(
        family="nulls_types",
        features=(base, base.model_copy(update={"name": "other", "columns": ("y",)})),
    )
    supported = vector(1, 4).observations[0]
    missing = vector(0, 0).observations[0].model_copy(update={"name": "other"})
    profile = ef.ProfileVector(
        spec=schema,
        spec_sha256=ef.profile_spec_fingerprint(schema),
        observations=(supported, missing),
    )
    bundle = ef.fit_preprocessor(training(profile), spec=schema)
    assert bundle.state == "ready" and len(bundle.columns) == 3
    assert bundle.features[1].reason == "no_valid_training_values"
    strict = ef.fit_preprocessor(training(profile), spec=schema, empty_policy="not_estimable")
    assert strict.state == "not_estimable"


def test_technical_failure_is_never_imputed():
    profile = vector(0, 0)
    failed = profile.model_copy(
        update={
            "observations": (
                ef.FeatureObservation(
                    name="null_rate", state="not_evaluable", reason="resource_exhausted"
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="failed measurements"):
        ef.fit_preprocessor(training(failed), spec=spec())
    bundle = ef.fit_preprocessor(training(vector(1, 2)), spec=spec())
    with pytest.raises(ValueError, match="failed measurements"):
        ef.transform_profiles(bundle, (failed,))


def test_feature_versions_order_and_definitions_rejected():
    bundle = ef.fit_preprocessor(training(vector(1, 2)), spec=spec())
    changed = spec().model_copy(
        update={"features": (spec().features[0].model_copy(update={"columns": ("y",)}),)}
    )
    with pytest.raises(ValueError, match="incompatible"):
        ef.transform_profiles(bundle, (vector(1, 2, changed),))
    data = spec().model_dump(mode="json") | {"feature_version": "2.0"}
    with pytest.raises(ValidationError):
        ef.ProfileSpec.model_validate_json(json.dumps(data))
    forged = bundle.model_copy(update={"spec_sha256": "0" * 64})
    with pytest.raises(ValidationError):
        ef.transform_profiles(forged, (vector(1, 2),))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "0.5"])
def test_matrix_is_finite_numeric_not_labels(bad):
    with pytest.raises(ValidationError):
        ef.FeatureMatrix(preprocessor_sha256="a" * 64, columns=("rate",), values=((bad,),))


def test_duplicate_json_members_and_inconsistent_bundles_rejected(tmp_path):
    bundle = ef.fit_preprocessor(training(vector(1, 2)), spec=spec())
    path = tmp_path / "bundle.json"
    path.write_text(bundle.model_dump_json()[:-1] + ',"state":"ready"}', encoding="utf-8")
    with pytest.raises(ef.ContractParseError):
        ef.read_preprocessor(path)
    with pytest.raises(ValidationError):
        ef.PreprocessorBundle.model_validate(bundle.model_copy(update={"state": "not_estimable"}))


def test_measurement_ratio_cannot_be_silently_rewritten():
    with pytest.raises(ValidationError):
        ef.FeatureObservation(name="x", state="available", value=0.5, numerator=0, denominator=3)
