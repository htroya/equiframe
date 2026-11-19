"""Exact independent moments, opt-in, unavailable support and limits."""

from fractions import Fraction

import pytest
from pydantic import ValidationError
from test_grouped_profiles import feature, table
from test_profiles import make_run

import equiframe as ef

METRICS = ("media_diferencia_relativa_grupo", "varianza_diferencia_relativa_grupo")


def extract(tmp_path, source, output, **kwargs):
    run = make_run(tmp_path / "run", "aggregations", output, {"source": source})
    spec = ef.ProfileSpec(
        family="aggregations",
        feature_version="1.2",
        features=tuple(feature(metric) for metric in METRICS),
    )
    return ef.profile_execution(run, spec=spec, work_dir=tmp_path / "profiles", **kwargs)


def test_exact_population_moments_and_restoration(tmp_path):
    # Relative absolute changes: 0, 1/2, 1. Mean 1/2; population variance 1/6.
    result = extract(
        tmp_path,
        table(["A", "B", "C"], [100, 200, 50], input=True),
        table(["A", "B", "C"], [100, 300, 0]),
    )
    assert result.complete
    assert result.metadata.implementation_version == "equiframe-profiles-1.2"
    assert [Fraction(o.numerator, o.denominator) for o in result.vector.observations] == [
        Fraction(1, 2),
        Fraction(1, 6),
    ]
    path = tmp_path / "profiles" / result.metadata.profile_id / "profile.json"
    assert ef.read_profile(path) == result


def test_mean_and_variance_can_exceed_one(tmp_path):
    result = extract(tmp_path, table(["A", "B"], [1, 1], input=True), table(["A", "B"], [1, 11]))
    assert [o.value for o in result.vector.observations] == [5.0, 25.0]


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_distribution_formulas_require_version_12(version):
    with pytest.raises(ValidationError, match="feature_version"):
        ef.ProfileSpec(
            family="aggregations", feature_version=version, features=(feature(METRICS[0]),)
        )


def test_zero_reference_and_absent_groups_do_not_become_zero_ratios(tmp_path):
    result = extract(
        tmp_path, table(["zero", "gone"], [0, 2], input=True), table(["zero", "added"], [5, 8])
    )
    assert result.complete
    assert all(o.state == "undefined" and o.denominator == 0 for o in result.vector.observations)


def test_negative_reference_uses_absolute_denominator(tmp_path):
    result = extract(tmp_path, table(["A", "B"], [-10, 10], input=True), table(["A", "B"], [-5, 5]))
    assert [o.value for o in result.vector.observations] == [0.5, 0.0]


def test_invalid_measures_are_not_imputed(tmp_path):
    result = extract(tmp_path, table(["A"], [1], input=True), table(["A"], [None]))
    assert not result.complete
    assert all(o.state == "not_evaluable" for o in result.vector.observations)


def test_limits_prevent_partial_distribution(tmp_path):
    result = extract(
        tmp_path,
        table(["A", "B"], [1, 2], input=True),
        table(["A", "B"], [2, 3]),
        options=ef.ProfileOptions(max_distinct=1),
    )
    assert not result.complete
    assert all(o.value is None for o in result.vector.observations)


def test_population_moments_share_one_bounded_aggregation(tmp_path, monkeypatch):
    import equiframe._grouped_profiles as implementation

    original = implementation.compare_grouped
    calls = []

    def observed(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(implementation, "compare_grouped", observed)
    result = extract(tmp_path, table(["A"], [1], input=True), table(["A"], [2]))
    assert result.complete and len(calls) == 1
