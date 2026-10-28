"""Audit receipts must fail closed and prove precisely their linked option."""

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

PATH = Path(__file__).parents[1] / "tools" / "option_trace.py"
SPEC = importlib.util.spec_from_file_location("option_trace", PATH)
assert SPEC is not None and SPEC.loader is not None
trace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trace)


class Fixture(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    enabled: bool = False
    count: int
    mode: Literal["small", "large"] = "small"


MODULE = ModuleType("equiframe")
MODULE.__all__ = ["Fixture"]
MODULE.Fixture = Fixture
SEEDS = {"Fixture": {"input": {"enabled": True, "count": 2, "mode": "small"}}}


def case(operation="field_value", field="enabled", expected=True, **extra):
    return {
        "id": "synthetic",
        "model": "Fixture",
        "operation": operation,
        "field": field,
        "expected": expected,
        "basis": "Independent literal synthetic test contract",
        "obligations": ["field:equiframe.Fixture:enabled:value:true"],
        **extra,
    }


@pytest.mark.parametrize(
    "test_case,status",
    [
        (case(), "PASS"),
        (case(expected=False), "FAIL"),
        (case(expected=1), "FAIL"),
        (case("default", expected=False), "PASS"),
        (case("required_omission", "count", {"error_codes": ["missing"]}), "EXPECTED_REJECTION"),
        (case("required_omission", "count", {"error_codes": ["int_type"]}), "FAIL"),
        (
            case("invalid", expected={"error_codes": ["bool_type"]}, value="false"),
            "EXPECTED_REJECTION",
        ),
        (case("invalid", expected={"error_codes": ["bool_type"]}, value=False), "FAIL"),
        (case("field_value", "count", None, value=None), "FAIL"),
    ],
)
def test_receipts_match_literals_and_exact_rejection_location(test_case, status):
    seed = copy.deepcopy(SEEDS)
    receipt = trace.execute_case(test_case, seed, MODULE)
    assert receipt["status"] == status
    assert receipt["independent_expected"] == test_case["expected"]
    assert len(receipt["input_sha256"]) == 64
    assert seed == SEEDS


def test_unexpected_programming_error_is_never_an_expected_rejection(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("synthetic programmer fault")

    monkeypatch.setattr(Fixture, "model_validate_json", broken)
    receipt = trace.execute_case(
        case("invalid", expected={"error_codes": ["bool_type"]}), SEEDS, MODULE
    )
    assert receipt["status"] == "FAIL"
    assert receipt["observed"] == {"unexpected_exception": "RuntimeError"}


def rows():
    return [
        {"id": "field:equiframe.Fixture:enabled:value:true", "option_value_or_class": True},
        {"id": "field:equiframe.Fixture:enabled:value:false", "option_value_or_class": False},
        {
            "id": "field:equiframe.Fixture:count:required_omission",
            "option_value_or_class": "missing",
        },
    ]


def catalog():
    return {
        "schema_version": "equiframe.option-cases/1.0",
        "seeds": SEEDS,
        "obligation_ids_sha256": trace.digest(sorted(r["id"] for r in rows())),
        "cases": [case()],
    }


@pytest.mark.parametrize(
    "attack", ["duplicate", "unknown", "unrelated", "wrong_boolean", "denominator", "no_basis"]
)
def test_catalog_cannot_claim_other_options_or_shrink_the_denominator(attack):
    data = catalog()
    if attack == "duplicate":
        data["cases"].append(copy.deepcopy(data["cases"][0]))
    elif attack == "unknown":
        data["cases"][0]["obligations"] = ["missing-row"]
    elif attack == "unrelated":
        data["cases"][0]["obligations"] = [rows()[2]["id"]]
    elif attack == "wrong_boolean":
        data["cases"][0]["expected"] = 1
    elif attack == "denominator":
        data["obligation_ids_sha256"] = trace.digest([rows()[0]["id"]])
    else:
        del data["cases"][0]["basis"]
    with pytest.raises(ValueError):
        trace.validate_catalog(data, rows())


def test_failure_overrides_passing_repeat_and_unlinked_rows_remain_unrun():
    receipts = [
        {"case_id": "positive", "status": "PASS", "obligations": [rows()[0]["id"]]},
        {"case_id": "negative", "status": "FAIL", "obligations": [rows()[0]["id"]]},
        {"case_id": "omission", "status": "EXPECTED_REJECTION", "obligations": [rows()[2]["id"]]},
    ]
    result = trace.aggregate(rows(), receipts)
    assert result["counts"] == {"FAIL": 1, "NOT_RUN": 1, "EXPECTED_REJECTION": 1}
    assert result["verified"] == 1 and result["total"] == 3
    assert result["unique_cases"] == 3
    assert result["percent"] == pytest.approx(100 / 3)
    with pytest.raises(ValueError, match="Duplicate execution"):
        trace.aggregate(rows(), [*receipts, receipts[0]])


@pytest.mark.parametrize("document", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_ambiguous_json_is_rejected(tmp_path, document):
    path = tmp_path / "catalog.json"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(ValueError):
        trace.read_json(path)


def test_valid_json_and_boolean_identity_are_preserved(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"flag": False, "count": 0}), encoding="utf-8")
    assert trace.read_json(path) == {"flag": False, "count": 0}
    assert not trace.same(False, 0)
    trace.validate_catalog(catalog(), rows())
