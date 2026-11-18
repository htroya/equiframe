"""Prevent dropping weak areas, moving denominators or rounding before averaging."""

import copy
import importlib.util
from fractions import Fraction
from pathlib import Path

import pytest

PATH = Path(__file__).parents[1] / "tools" / "measure_global_progress.py"
SPEC = importlib.util.spec_from_file_location("global_progress", PATH)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def metrics():
    numerators = {
        "usability": 11,
        "universality": 48,
        "pypi_preparation": 16,
        "documentation": 18,
        "option_traceability": 5786,
        "package_quality": 16,
        "maturity": 4,
        "thesis": 9,
        "security": 7,
    }
    return [
        {
            "key": key,
            "numerator": numerators[key],
            "denominator": binding[2],
            "record_targets_current_a13": key not in ("usability", "universality"),
            "assessed_candidate": "historical"
            if key in ("usability", "universality")
            else "0.12.0a13",
            "source": "fixture.json",
            "source_sha256": "fixture",
        }
        for key, binding in tool.BINDINGS.items()
    ]


def test_exact_unrounded_nine_area_average_and_historical_scopes():
    result = tool.calculate(metrics())
    expected = (
        sum(Fraction(100 * row["numerator"], row["denominator"]) for row in metrics())
        / 9
    )
    assert result["exact_fraction"] == {
        "numerator": expected.numerator,
        "denominator": expected.denominator,
    }
    assert result["rounded_percent"] == 65.73
    assert result["target_met"] is False
    assert result["all_area_measurements_are_current_a13"] is False
    assert result["historical_candidate_areas"] == ["usability", "universality"]


def test_explicit_eight_area_scope_preserves_exact_original_area_fractions():
    rows = [row for row in metrics() if row["key"] != "security"]
    result = tool.calculate(rows, exclude_security=True)
    expected = (
        sum(Fraction(100 * row["numerator"], row["denominator"]) for row in rows) / 8
    )
    assert result["exact_fraction"] == {
        "numerator": expected.numerator,
        "denominator": expected.denominator,
    }
    assert result["area_count"] == 8
    assert result["excluded_areas"] == ["security"]
    assert result["scope_change_is_technical_progress"] is False
    assert all(
        row["weight"] == {"numerator": 1, "denominator": 8} for row in result["areas"]
    )
    assert result["historical_candidate_areas"] == ["usability", "universality"]
    with pytest.raises(ValueError):
        tool.calculate(rows)


@pytest.mark.parametrize(
    "mutation", ["nine_areas", "drop_thesis", "replace_maturity", "denominator"]
)
def test_new_scope_cannot_silently_omit_other_weak_areas_or_change_denominators(
    mutation,
):
    rows = [row for row in metrics() if row["key"] != "security"]
    if mutation == "nine_areas":
        rows = metrics()
    elif mutation == "drop_thesis":
        rows = [row for row in rows if row["key"] != "thesis"]
    elif mutation == "replace_maturity":
        rows = [row if row["key"] != "maturity" else metrics()[-1] for row in rows]
    else:
        rows[0]["denominator"] = 11
    with pytest.raises(ValueError):
        tool.calculate(rows, exclude_security=True)


@pytest.mark.parametrize(
    "mutation", ["drop", "duplicate", "denominator", "boolean", "negative", "excess"]
)
def test_omitted_reweighted_or_forged_areas_cannot_raise_average(mutation):
    rows = copy.deepcopy(metrics())
    if mutation == "drop":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif mutation == "denominator":
        rows[-1]["denominator"] = 7
    elif mutation == "boolean":
        rows[-1]["numerator"] = True
    elif mutation == "negative":
        rows[-1]["numerator"] = -1
    else:
        rows[-1]["numerator"] = 21
    with pytest.raises(ValueError):
        tool.calculate(rows)


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "hash",
        "candidate",
        "historical_scope",
        "source_boolean",
        "missing_candidate",
    ],
)
def test_measurement_checks_real_source_bytes_candidate_and_integer_counts(
    tmp_path, mutation
):
    import hashlib
    import json

    rows = metrics()
    for row in rows:
        row["assessed_candidate"] = (
            "0.12.0a12"
            if row["key"] == "usability"
            else "0.12.0a11"
            if row["key"] == "universality"
            else "0.12.0a13"
        )
        row["source"] = row["key"] + ".json"
        n_key, d_key, _ = tool.BINDINGS[row["key"]]
        candidate = row["assessed_candidate"]
        if row["key"] == "documentation":
            candidate = {"equiframe": candidate, "equiframe-benchmark": candidate}
        source = {
            n_key: row["numerator"],
            d_key: row["denominator"],
            "candidate": candidate,
        }
        if mutation == "missing_candidate" and row["key"] == "usability":
            source.pop("candidate")
        if mutation == "source_boolean" and row["key"] == "maturity":
            row["numerator"] = 1
            source[n_key] = True
        path = tmp_path / row["source"]
        path.write_text(json.dumps(source), encoding="utf-8")
        row["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if mutation == "hash":
        (tmp_path / rows[0]["source"]).write_text("{}", encoding="utf-8")
    elif mutation == "candidate":
        rows[0]["assessed_candidate"] = "0.12.0a13"
        rows[0]["record_targets_current_a13"] = True
    elif mutation == "historical_scope":
        rows[0]["record_targets_current_a13"] = True
    matrix = tmp_path / "matrix.json"
    matrix.write_text(json.dumps({"metrics": rows}), encoding="utf-8")
    if mutation == "none":
        assert tool.measure(matrix, tmp_path)["rounded_percent"] == 65.73
    else:
        with pytest.raises(ValueError):
            tool.measure(matrix, tmp_path)
