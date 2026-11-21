"""Use the frozen SERCOP detector with verified captures and base R."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Literal

from equiframe._base import FrozenModel, NonNegativeInt, Text
from equiframe._bundled_r import bundled_r
from equiframe.comparison_types import ComparisonResult
from equiframe.contracts import Contract
from equiframe.detector_types import DetectorBundle
from equiframe.detectors import detect_component, read_detector_bundle
from equiframe.errors import CapabilityError, EquiFrameError
from equiframe.evidence import publish_json
from equiframe.profile_types import ProfileVector
from equiframe.profiles import _profile_execution
from equiframe.r_review import RReviewOptions, _review_with_r
from equiframe.serialization import contract_fingerprint
from equiframe.types import Sha256
from equiframe.verify import verification_summary
from equiframe.verify_types import VerificationResult


class SercopModelInfo(FrozenModel):
    schema_version: Literal["1.0"]
    model_id: Text
    model_sha256: Sha256
    contract: Contract
    contract_sha256: Sha256
    training_wheel_sha256: Sha256
    source: Text
    license: Text
    source_years: tuple[int, ...]
    training_lots: NonNegativeInt
    calibration_lots: NonNegativeInt
    evaluation_lots: NonNegativeInt


def bundled_model() -> tuple[SercopModelInfo, DetectorBundle]:
    scope = files("equiframe").joinpath("_sercop_assets")
    info = SercopModelInfo.model_validate_json(scope.joinpath("manifest.json").read_bytes())
    if contract_fingerprint(info.contract) != info.contract_sha256:
        raise ValueError("bundled SERCOP contract fingerprint mismatch")
    with as_file(scope.joinpath("detector.json")) as local:
        bundle = read_detector_bundle(local, expected_sha256=info.model_sha256)
    if bundle.m.state != "ready":
        raise ValueError("bundled SERCOP Isolation Forest is not calibrated")
    return info, bundle


def score_profile(bundle: DetectorBundle, profile: ProfileVector) -> dict[str, object]:
    detection = detect_component(bundle, (profile,), method="isolation_forest")
    item = detection.decisions[0]
    return {
        "state": item.result.decision,
        "score": item.score,
        "threshold": bundle.m.threshold,
        "model_sha256": detection.bundle_sha256,
        "reason": item.result.reason,
    }


def unavailable(reason: str) -> dict[str, object]:
    return {"state": "not_evaluable", "reason": reason}


def _case(exact_state: str, forest_state: object, r_state: object) -> tuple[str, bool]:
    """Name the evidence for the ETL decision and whether it needs review."""
    if exact_state not in {"equivalent", "different"}:
        return "exact_comparison_unavailable", True
    if r_state in ("equivalent", "different") and r_state != exact_state:
        return "comparators_disagree", True
    if forest_state not in ("alert", "no_alert"):
        return "isolation_forest_unavailable", True
    if exact_state == "equivalent" and forest_state == "no_alert":
        return "equivalent", False
    if exact_state == "different" and forest_state == "alert":
        return "difference_detected", False
    if r_state != exact_state:
        return "r_confirmation_unavailable", True
    if exact_state == "equivalent":
        return "false_alarm_confirmed", False
    return "miss_confirmed", False


def _review_capture_with_r(comparison: ComparisonResult, rscript: str) -> dict[str, object]:
    assert comparison.left is not None and comparison.right is not None
    runtime = None
    origin = "explicit"
    if rscript == "auto":
        runtime = bundled_r()
        rscript = str(runtime.executable)
        origin = "bundled"
    review = _review_with_r(
        comparison.left.data,
        comparison.right.data,
        contract=comparison.spec,
        comparison=comparison,
        options=RReviewOptions(rscript=rscript),
        runtime=runtime,
    )
    report = {**review.model_dump(mode="json"), "python_state": comparison.state, "runtime": origin}
    if runtime is not None:
        report["runtime_manifest_sha256"] = runtime.manifest_sha256
    return report


def assess_capture(
    result: VerificationResult, output: Path, rscript: str
) -> tuple[int, dict[str, object]]:
    """Report the unchanged contract verdict and independently observed IF/R results."""
    report: dict[str, object] = {"contract": verification_summary(result)}
    scope = output / (result.verification_id + "-sercop")
    scope.mkdir(exist_ok=False)
    names = tuple(item.output for item in result.expected if item.output is not None)
    scored: dict[str, dict[str, object]] = {}
    reviewed: dict[str, dict[str, object]] = {}
    cases: dict[str, dict[str, object]] = {}
    model: SercopModelInfo | None
    bundle: DetectorBundle | None
    try:
        model, bundle = bundled_model()
    except (OSError, ValueError, EquiFrameError):
        model = bundle = None
    if model is not None:
        report["model"] = model.model_dump(mode="json")

    if result.integrity.state != "passed":
        reason = "capture_integrity_unavailable"
    elif model is not None and contract_fingerprint(result.contract) != model.contract_sha256:
        reason = "contract_outside_sercop_scope"
    else:
        reason = None

    comparisons = {item.comparison_id: item for item in result.comparisons}
    expected_checks = {item.output: item for item in result.expected}
    captures = dict(result.executions)
    for name in names:
        execution = captures.get(name)
        if reason is not None or execution is None or execution.output is None:
            problem = reason or "execution_receipt_unavailable"
            scored[name] = unavailable(problem)
            reviewed[name] = unavailable(problem)
            cases[name] = {"state": problem, "review_required": True}
            continue
        if bundle is None:
            scored[name] = unavailable("bundled_model_unavailable")
        else:
            try:
                profile = _profile_execution(
                    execution,
                    spec=bundle.fit.preprocessor.spec,
                    work_dir=scope,
                    grouped_nullable_reference=("source", "amount"),
                )
                scored[name] = (
                    score_profile(bundle, profile.vector)
                    if profile.complete
                    else unavailable("profile_incomplete")
                )
                scored[name]["profile_policy"] = "sercop-grouped-reference-present-amounts-1"
                if not profile.complete:
                    scored[name]["unavailable_features"] = [
                        {"name": observation.name, "reason": observation.reason}
                        for observation in profile.vector.observations
                        if observation.state == "not_evaluable"
                    ]
            except (OSError, ValueError, EquiFrameError):
                scored[name] = unavailable("profile_or_detection_failed")

        check = expected_checks[name]
        comparison = comparisons.get(check.comparison_id or "")
        if (
            comparison is None
            or comparison.left is None
            or comparison.right is None
            or comparison.left.data.sha256 != execution.output.data.sha256
            or comparison.right.data.sha256 != result.binding.expected_sha256
        ):
            reviewed[name] = unavailable("bound_expected_comparison_unavailable")
            cases[name] = {
                "state": "bound_expected_comparison_unavailable",
                "review_required": True,
            }
            continue
        exact_state = comparison.state if comparison.complete else "not_evaluable"
        forest_state = scored[name]["state"]
        agreement = (exact_state, forest_state) in (
            ("equivalent", "no_alert"),
            ("different", "alert"),
        )
        if agreement and rscript == "auto":
            reviewed[name] = {"state": "not_requested", "reason": "contract_and_model_agree"}
        else:
            try:
                reviewed[name] = _review_capture_with_r(comparison, rscript)
            except CapabilityError as error:
                reviewed[name] = unavailable(str(error))
            except (OSError, ValueError, EquiFrameError):
                reviewed[name] = unavailable("r_review_failed")
        case, needs_review = _case(exact_state, forest_state, reviewed[name]["state"])
        if rscript != "auto" and reviewed[name]["state"] not in ("equivalent", "different"):
            case, needs_review = "r_confirmation_unavailable", True
        cases[name] = {"state": case, "review_required": needs_review}

    # Verification orders input and output self-comparisons by their captured artifacts.
    input_failures = {
        name: item
        for (name, _), item in zip(result.input_artifacts, result.input_comparisons, strict=True)
        if item.state == "different"
    }
    output_failures = {
        name: item
        for (name, _), item in zip(
            result.outputs, result.comparisons[: len(result.outputs)], strict=True
        )
        if item.state == "different"
    }
    for name, case_report in cases.items():
        if input_failures or name in output_failures:
            case_report["comparison_case"] = case_report["state"]
            case_report["state"] = "contract_constraints_failed"

    review_required = len(cases) != result.coverage.outputs_requested or any(
        case["review_required"] is True for case in cases.values()
    )
    ready = bool(names) and not review_required
    code = result.exit_code or (0 if ready else 3)
    report.update(
        isolation_forest=scored,
        r_review=reviewed,
        cases=cases,
        constraint_failures=[
            {
                "scope": scope_name,
                "name": name,
                "comparison_id": item.comparison_id,
                "contract_violations": item.counts.contract_violations,
            }
            for scope_name, failures in (("input", input_failures), ("output", output_failures))
            for name, item in failures.items()
        ],
        review_required=review_required or code == 3,
        coverage_reason=reason,
        publishable=code == 0,
        exit_code=code,
    )
    publish_json(report, scope / "report.json")
    return code, report
