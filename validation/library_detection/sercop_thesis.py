"""Freeze a SERCOP detector and require an ML outcome alongside ETL acceptance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import public_spending as study
from operational_replay import replay_case
from run import digest, metrics
from runtime_receipt import receipt
from sercop_cohorts import select

import equiframe as ef
from equiframe.evidence import publish_json

ALPHA = "0.05"
SEED = 7
SUPPORT = 48


def train(source_dir: Path, wheel: Path, output: Path) -> dict[str, Any]:
    identity = receipt(wheel)
    output.mkdir(parents=True)
    print("Reading the 2019–2026 archived SERCOP snapshots", flush=True)
    cases, selection = select(source_dir)
    publish_json(
        {
            **selection,
            "wheel_sha256": identity["wheel_sha256"],
            "alpha": ALPHA,
            "seed": SEED,
            "profile_version": "1.1",
            "trained_trees_requested": 200,
            "selection_unit": "Whole OCID assigned once using local compiled-release month.",
            "implementation_sha256": {
                name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in (
                    "sercop_thesis.py",
                    "sercop_cohorts.py",
                    "operational_replay.py",
                    "public_spending.py",
                    "run.py",
                )
            },
            "source_registry": "https://data.open-contracting.org/es/publication/110",
            "license": "https://creativecommons.org/licenses/by/3.0/ec/",
        },
        output / "protocol.json",
    )
    earlier: dict[str, list[ef.ProfileVector]] = defaultdict(list)
    holdout = []
    for case in cases:
        split = case["split"]
        if split not in ("training", "calibration"):
            holdout.append(case)
            continue
        with TemporaryDirectory(dir=output) as scratch:
            record, profiles = study.execute_case(case, "pandas", Path(scratch), True, ("1.1",))
        if record["divergent"]:
            raise ValueError("Training and calibration require independently checked normal lots")
        earlier[split].append(profiles["1.1"])
        checked = sum(map(len, earlier.values()))
        if checked % 96 == 0:
            print(f"Checked {checked} normal training/calibration lots", flush=True)

    print("Fitting and calibrating Isolation Forest on disjoint lots", flush=True)
    spec = study.specifications("1.1")[1]
    training, calibration = (
        {
            month: record["batch_sha256"]
            for month, record in selection["periods"].items()
            if record["partition"] == split
        }
        for split in ("training", "calibration")
    )
    fit = ef.fit_detectors(
        ef.NormalTrainingProfiles(
            purpose="normal_training",
            profiles=tuple(earlier["training"]),
            selection_manifest_sha256=digest(training),
        ),
        spec=spec,
        config=ef.IsolationForestConfig(random_state=SEED, n_estimators=200, max_samples=256),
        support=ef.DetectorSupport(
            min_training_rows=SUPPORT,
            min_calibration_rows=SUPPORT,
            rationale="Required normal cohort size for the thesis workflow.",
        ),
    )
    bundle = ef.calibrate_detectors(
        fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration",
            profiles=tuple(earlier["calibration"]),
            selection_manifest_sha256=digest(calibration),
        ),
        alpha=ALPHA,
    )
    if bundle.m.state != "ready":
        raise ValueError("The SERCOP Isolation Forest did not reach a calibrated state")
    model = output / "detector.json"
    model_sha256 = ef.write_detector_bundle(bundle, model)
    bundle = ef.read_detector_bundle(model, expected_sha256=model_sha256)

    print("Evaluating the frozen model on held-out 2026 lots", flush=True)
    rows = []
    profiles = []
    for case in holdout:
        native = []
        for engine in study.ENGINES:
            with TemporaryDirectory(dir=output) as scratch:
                native.append(replay_case(case, engine, Path(scratch)))
        if any(item != native[0] for item in native[1:]):
            raise ValueError("Native engines disagree on holdout checks or profiles")
        divergent, exact, group, profile = native[0]
        rows.append(
            {
                "month": case["period"],
                "divergent": divergent,
                "batch_sha256": case["source_sha256"],
                "scenario": "shifted_normal" if case["split"] == "shifted_normal" else case["kind"],
                "exact_gate": {"equivalent": "no_alert", "different": "alert"}.get(
                    exact, "not_evaluable"
                ),
                "group_rule": group,
            }
        )
        profiles.append(profile)
    detection = ef.detect_component(bundle, tuple(profiles), method="isolation_forest")
    for row, decision in zip(rows, detection.decisions, strict=True):
        row.update(
            isolation_forest=decision.result.decision,
            score=decision.score,
            reason=decision.result.reason,
        )
    methods = ("isolation_forest", "exact_gate", "group_rule")
    report = {
        "wheel_version": identity["version"],
        "wheel_sha256": identity["wheel_sha256"],
        "versions": {name: version(name) for name in (*study.ENGINES, "scikit-learn", "pyarrow")},
        "model": {
            "file": model.name,
            "sha256": model_sha256,
            "threshold": bundle.m.threshold,
            "training_batches": len(earlier["training"]),
            "calibration_batches": len(earlier["calibration"]),
            "trees": len(bundle.fit.m.trees),
        },
        "holdout_engines": study.ENGINES,
        "overall": {name: metrics(rows, name) for name in methods},
        "by_scenario": {
            scenario: {
                name: metrics([r for r in rows if r["scenario"] == scenario], name)
                for name in methods
            }
            for scenario in ("normal", "shifted_normal", *study.FAULTS)
        },
        "holdout": rows,
    }
    publish_json(report, output / "report.json")
    return report


def assess_execution(
    output: Path,
    model: Path,
    model_sha256: str,
    verification: ef.VerificationResult | None,
) -> dict[str, Any]:
    evaluation: dict[str, Any] = {
        "required": True,
        "method": "isolation_forest",
        "state": "not_evaluable",
        "complete": False,
        "threshold": None,
        "outputs": {},
    }
    if not model.is_file():
        return {**evaluation, "reason": "model_unavailable"}
    try:
        bundle = ef.read_detector_bundle(model, expected_sha256=model_sha256)
    except (OSError, ValueError, ef.EquiFrameError):
        return {**evaluation, "reason": "model_invalid_or_fingerprint_mismatch"}
    evaluation.update(model_sha256=model_sha256, threshold=bundle.m.threshold)
    if bundle.m.state != "ready":
        return {**evaluation, "reason": "model_not_calibrated"}
    if verification is None or not verification.executions:
        return {**evaluation, "reason": "execution_receipts_unavailable"}
    contract, spec = study.specifications("1.1")
    if verification.contract != contract or bundle.fit.preprocessor.spec != spec:
        return {**evaluation, "reason": "contract_or_profile_outside_sercop_model_scope"}

    scores: dict[str, dict[str, Any]] = {}
    for name, execution in verification.executions:
        try:
            measured = ef.profile_execution(execution, spec=spec, work_dir=output / "profiles")
            if not measured.complete:
                scores[name] = {
                    "state": "not_evaluable",
                    "reason": "profile_incomplete",
                    "score": None,
                }
                continue
            detected = ef.detect_component(bundle, (measured.vector,), method="isolation_forest")
            decision = detected.decisions[0]
            scores[name] = {
                "state": decision.result.decision,
                "score": decision.score,
                "reason": decision.result.reason,
                "execution_id": execution.execution_id,
            }
        except (OSError, ValueError, ef.EquiFrameError):
            scores[name] = {
                "state": "not_evaluable",
                "reason": "profile_or_detection_failed",
                "score": None,
            }
    complete = len(scores) == verification.coverage.outputs_requested and all(
        value["state"] in ("alert", "no_alert") for value in scores.values()
    )
    return {
        **evaluation,
        "outputs": scores,
        "state": (
            ("alert" if any(item["state"] == "alert" for item in scores.values()) else "no_alert")
            if complete
            else "not_evaluable"
        ),
        "complete": complete,
        "reason": None if complete else "incomplete_isolation_forest_coverage",
    }


def evaluate(request: Path, binding: Path, model: Path, model_sha256: str, output: Path) -> int:
    output.mkdir(parents=True)
    contract_root = output / "contract"
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "equiframe",
        "verify",
        "accept",
        str(request),
        "--reference-binding",
        str(binding),
        "--require-execution",
        "--output",
        str(contract_root),
    ]
    contract_exit = 3
    result = None
    try:
        proc = subprocess.run(command, capture_output=True, encoding="utf-8", timeout=300)
        contract_exit = proc.returncode
        if proc.stdout:
            summary = json.loads(proc.stdout)
            result = ef.read_verification(contract_root / summary["verification_id"])
    except (OSError, ValueError, ef.EquiFrameError, subprocess.TimeoutExpired):
        contract_exit = 3
    ml = assess_execution(output, model, model_sha256, result)
    if result is None and contract_exit == 0:
        contract_exit = 3
    exit_code = 3 if contract_exit == 0 and not ml["complete"] else contract_exit
    report = {
        "contract": {
            "exit_code": contract_exit,
            "state": result.operational_state if result is not None else "unavailable",
            "publishable": result is not None and result.publishable,
        },
        "isolation_forest": ml,
        "review_required": any(item["state"] == "alert" for item in ml["outputs"].values()),
        "exit_code": exit_code,
    }
    publish_json(report, output / "report.json")
    print(json.dumps(report, indent=2, allow_nan=False))
    return exit_code


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="mode", required=True)
    fit = commands.add_parser("train")
    fit.add_argument("--source-dir", type=Path, required=True)
    fit.add_argument("--wheel", type=Path, required=True)
    fit.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("evaluate")
    for name in ("request", "reference-binding", "model", "output"):
        check.add_argument("--" + name, type=Path, required=True)
    check.add_argument("--model-sha256", required=True)
    args = cli.parse_args()
    if args.mode == "train":
        result = train(args.source_dir.resolve(), args.wheel.resolve(), args.output.resolve())
        print(json.dumps({"model": result["model"], "overall": result["overall"]}, indent=2))
        return 0
    return evaluate(
        args.request.resolve(),
        args.reference_binding.resolve(),
        args.model.resolve(),
        args.model_sha256,
        args.output.resolve(),
    )


if __name__ == "__main__":
    sys.exit(main())
