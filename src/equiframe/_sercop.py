"""Use the frozen SERCOP detector with verified captures and base R."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Literal

from equiframe._base import FrozenModel, NonNegativeInt, Text
from equiframe.contracts import Contract
from equiframe.detector_types import DetectorBundle
from equiframe.detectors import detect_component, read_detector_bundle
from equiframe.errors import EquiFrameError
from equiframe.evidence import publish_json
from equiframe.profile_types import ProfileVector
from equiframe.profiles import profile_execution
from equiframe.r_review import RReviewOptions, review_with_r
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
            continue
        if bundle is None:
            scored[name] = unavailable("bundled_model_unavailable")
        else:
            try:
                profile = profile_execution(
                    execution, spec=bundle.fit.preprocessor.spec, work_dir=scope
                )
                scored[name] = (
                    score_profile(bundle, profile.vector)
                    if profile.complete
                    else unavailable("profile_incomplete")
                )
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
            continue
        try:
            review = review_with_r(
                comparison.left.data,
                comparison.right.data,
                contract=comparison.spec,
                comparison=comparison,
                options=RReviewOptions(rscript=rscript),
            )
            reviewed[name] = {**review.model_dump(mode="json"), "python_state": comparison.state}
        except (OSError, ValueError, EquiFrameError):
            reviewed[name] = unavailable("r_review_failed")

    alerts = any(item["state"] == "alert" for item in scored.values())
    r_agrees = all(item["state"] == item.get("python_state") for item in reviewed.values())
    ready = (
        len(names) == result.coverage.outputs_requested
        and all(item["state"] == "no_alert" for item in scored.values())
        and all(item["state"] == "equivalent" for item in reviewed.values())
        and r_agrees
    )
    code = result.exit_code or (0 if ready else 3)
    report.update(
        isolation_forest=scored,
        r_review=reviewed,
        review_required=alerts or not r_agrees or code == 3,
        coverage_reason=reason,
        publishable=code == 0,
        exit_code=code,
    )
    publish_json(report, scope / "report.json")
    return code, report
