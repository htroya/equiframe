"""Reject misattributed validation failures; these fixtures do not score SDK coverage."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from pydantic import ConfigDict, create_model

SPEC = importlib.util.spec_from_file_location(
    "configuration",
    Path(__file__).resolve().parents[1] / "tools/option_configuration_followup.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def case():
    return {
        "api": "compare",
        "parameter": "options",
        "model": "ComparisonOptions",
        "kind": "invalid_bool",
        "expected_error_codes": ["model_type"],
        "expected_options": {},
        "expected_returned_options": {},
        "returned_options_kind": "normalized_configuration",
        "expected_error_title": "ComparisonOptions",
        "expected_error_prefix": [],
        "obligations": ["pending"],
    }


def configured_api(compare, infer=None):
    contract = SimpleNamespace(family="nulls_types")
    return SimpleNamespace(
        compare=compare,
        infer_diff_contract=infer
        or (lambda schema: SimpleNamespace(spec=SimpleNamespace(contract=contract))),
        diff=lambda *args, **kwargs: object(),
        ArrowInput=lambda table: table,
        ProfileSpec=lambda **kwargs: object(),
        ProfileFeature=lambda **kwargs: object(),
    )


def capture(*args):
    return SimpleNamespace(output=SimpleNamespace(data=None))


def test_preparation_validation_error_cannot_credit_configuration_rejection(tmp_path):
    model = create_model("ComparisonOptions", __config__=ConfigDict(extra="forbid"))

    def bad_preparation(schema):
        return model.model_validate(False)

    def uncalled(left, right, *, options, **kwargs):
        raise AssertionError("Target must not be called")

    result = module.execute(
        case(), tmp_path, configured_api(uncalled, bad_preparation), capture
    )
    assert result["status"] == "FAIL"
    assert result["observed"]["unexpected_exception"] == "ValidationError"
    assert sys.getprofile() is None


def test_direct_matching_rejection_records_entry_and_restores_profiler(tmp_path):
    model = create_model("ComparisonOptions", __config__=ConfigDict(extra="forbid"))

    def compare(left, right, *, options, **kwargs):
        return model.model_validate(options)

    result = module.execute(case(), tmp_path, configured_api(compare), capture)
    assert result["status"] == "EXPECTED_REJECTION"
    assert result["observed"]["public_api_entry"]["count"] == 1
    assert result["observed"]["public_api_entry"]["explicit_argument_identity_matches"]
    assert result["observed"]["errors"][0]["input"] is False
    assert sys.getprofile() is None


def test_error_about_different_model_cannot_credit_selected_model(tmp_path):
    wrong = create_model("OtherOptions")

    def compare(left, right, *, options, **kwargs):
        return wrong.model_validate(options)

    assert (
        module.execute(case(), tmp_path, configured_api(compare), capture)["status"]
        == "FAIL"
    )
    assert sys.getprofile() is None


def test_integer_zero_error_cannot_credit_boolean_false_argument(tmp_path):
    model = create_model("ComparisonOptions")

    def compare(left, right, *, options, **kwargs):
        return model.model_validate(0)

    assert (
        module.execute(case(), tmp_path, configured_api(compare), capture)["status"]
        == "FAIL"
    )
    assert sys.getprofile() is None


def test_admitted_invalid_argument_cannot_be_reported_as_rejection(tmp_path):
    def compare(left, right, *, options, **kwargs):
        return object()

    assert (
        module.execute(case(), tmp_path, configured_api(compare), capture)["status"]
        == "FAIL"
    )
    assert sys.getprofile() is None


def test_compare_policy_error_must_match_exact_reviewed_wrapper_path(tmp_path):
    policy_model = create_model("ComparisonPolicy")
    spec_model = create_model("ComparisonSpec", policy=(policy_model, ...))

    def compare(left, right, *, policy, **kwargs):
        return spec_model.model_validate({"policy": policy})

    selected_case = {
        **case(),
        "parameter": "policy",
        "model": "ComparisonPolicy",
        "expected_error_title": "ComparisonSpec",
        "expected_error_prefix": ["policy"],
    }
    result = module.execute(selected_case, tmp_path, configured_api(compare), capture)
    assert result["status"] == "EXPECTED_REJECTION"
    assert result["observed"]["errors"][0]["loc"] == ("policy",)
    wrong_path = {**selected_case, "expected_error_prefix": []}
    assert (
        module.execute(wrong_path, tmp_path, configured_api(compare), capture)["status"]
        == "FAIL"
    )
    assert sys.getprofile() is None
