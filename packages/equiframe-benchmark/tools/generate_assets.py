"""Generate the benchmark's strict versioned JSON schemas."""

import argparse
import json
from pathlib import Path

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
    Scenario,
    SnapshotManifest,
    SplitManifest,
    StudyResult,
    TableExport,
    TrainingManifest,
    TrainingSelection,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
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
    Scenario,
    SplitManifest,
    TrainingManifest,
    TrainingSelection,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "schemas"
    directory.mkdir(exist_ok=True)
    for model in MODELS:
        path = directory / (model.__name__ + "-1.0.schema.json")
        payload = (
            json.dumps(model.model_json_schema(), ensure_ascii=True, sort_keys=True, indent=2)
            + "\n"
        )
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != payload:
                raise SystemExit("outdated schema: " + path.name)
        else:
            path.write_text(payload, encoding="utf-8")
    print(f"{len(MODELS)} benchmark schemas verified" if args.check else "schemas generated")


if __name__ == "__main__":
    main()
