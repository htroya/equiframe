"""Independent software checks for the supplementary native experiment."""

import pytest
from spending_severity import actual_trace, amount_to_move, one_variant
from test_detector_component import frozen_bundle
from test_preprocessing import vector

import equiframe as ef


def source():
    return [
        {"ocid": "one", "award": "1", "buyer": "A", "currency": "USD", "amount": 10000},
        {"ocid": "two", "award": "2", "buyer": "B", "currency": "USD", "amount": 10000},
        {"ocid": "three", "award": "3", "buyer": "C", "currency": "USD", "amount": 50},
    ]


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
@pytest.mark.parametrize("level", ["correct", "fifty_percent"])
def test_native_redistribution_conserves_global_total_and_breaks_group_rule(
    tmp_path, engine, level
):
    row, profiles = one_variant(source(), 0, level, engine, tmp_path)
    assert row["divergent"] == (level != "correct")
    assert row["r_global"] == "no_alert"
    assert row["r_group"] == ("no_alert" if level == "correct" else "alert")
    values = [observation.value for observation in profiles["1.2"].observations[-2:]]
    assert values == ([0.0, 0.0] if level == "correct" else [0.5, 0.0])


def test_prespecified_severity_uses_exact_integer_cents():
    assert [
        amount_to_move(source(), level)
        for level in ("correct", "one_cent", "one_percent", "ten_percent", "fifty_percent")
    ] == [0, 1, 100, 1000, 5000]


def test_actual_path_reconstruction_rejects_a_fabricated_score():
    bundle = frozen_bundle()
    probe = vector(0, 4)
    actual = ef.detect_component(bundle, (probe,), method="isolation_forest")
    score = actual.scores.values[0]
    trace = actual_trace(bundle, probe, score)
    assert trace["trees_used"] == 1
    assert trace["score_from_paths"] == trace["score_from_api"]
    assert trace["tree_examples"][0]["path"][0]["branch"] == "left"
    with pytest.raises(RuntimeError, match="disagrees"):
        actual_trace(bundle, probe, score + 0.01)
