"""Generate and check the benchmark's strict V1 and V2 JSON schemas."""

import argparse
import json
import runpy
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from equiframe_benchmark import (
    AwardReconciliationResult,
    AwardReconciliationSpec,
    BootstrapPlan,
    BundleLimits,
    CalibrationManifest,
    CalibrationSelection,
    Candidate,
    Catalog,
    ComparisonReceipt,
    CostComparisonResult,
    CostProtocol,
    CostSpec,
    DetectorSelectionAudit,
    DistributionReadiness,
    EvaluationConfig,
    EvaluationRecord,
    EvaluationReport,
    FreezeAudit,
    FreezeDefinition,
    FreezeManifest,
    FrozenFamilyModel,
    IntegrationResult,
    IntegrationSpec,
    NameCheck,
    OracleResult,
    OracleVerificationBridge,
    PairwiseReport,
    ReproductionBundle,
    ReproductionRecord,
    Review,
    ReviewAssignment,
    ReviewPacket,
    ScaleRun,
    ScaleSpec,
    ScaleTrial,
    Scenario,
    SnapshotManifest,
    SplitManifest,
    StudyResult,
    TableExport,
    TrainingManifest,
    TrainingSelection,
)
from equiframe_benchmark.scale_process import ProcessObservation
from equiframe_benchmark.scale_types import ScaleWorkerCompletion
from equiframe_benchmark.scaling import ScaleFinalization

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    ProcessObservation,
    ScaleWorkerCompletion,
    ScaleFinalization,
    StudyResult,
    BootstrapPlan,
    BundleLimits,
    ComparisonReceipt,
    CostComparisonResult,
    CostProtocol,
    CostSpec,
    DistributionReadiness,
    EvaluationConfig,
    EvaluationRecord,
    EvaluationReport,
    FreezeAudit,
    PairwiseReport,
    FreezeDefinition,
    FreezeManifest,
    FrozenFamilyModel,
    NameCheck,
    ReproductionBundle,
    ReproductionRecord,
    TableExport,
    AwardReconciliationResult,
    AwardReconciliationSpec,
    IntegrationResult,
    IntegrationSpec,
    SnapshotManifest,
    CalibrationManifest,
    CalibrationSelection,
    DetectorSelectionAudit,
    Candidate,
    Catalog,
    OracleResult,
    OracleVerificationBridge,
    Review,
    ReviewAssignment,
    ReviewPacket,
    ScaleRun,
    ScaleSpec,
    ScaleTrial,
    Scenario,
    SplitManifest,
    TrainingManifest,
    TrainingSelection,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    models_v2 = cast(
        tuple[type[BaseModel], ...],
        runpy.run_path(str(ROOT / "tools/generate_assets_v2.py"))["MODELS_V2"],
    )
    groups = (
        (ROOT / "schemas", "1.0", MODELS),
        (ROOT / "schemas/protocol-v2", "2.0", models_v2),
    )
    count = 0
    for directory, schema_version, models in groups:
        for model in models:
            count += 1
            path = directory / (model.__name__ + "-" + schema_version + ".schema.json")
            payload = (
                json.dumps(model.model_json_schema(), ensure_ascii=True, sort_keys=True, indent=2)
                + "\n"
            )
            if path.exists() and path.read_text(encoding="utf-8") == payload:
                # Keep matching historical bytes, including their original line endings.
                continue
            if args.check:
                raise SystemExit(
                    "outdated schema: " + path.relative_to(ROOT / "schemas").as_posix()
                )
            directory.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
    print(f"{count} benchmark schemas verified" if args.check else "schemas generated")


if __name__ == "__main__":
    main()
