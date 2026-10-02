"""Experimental boundary: no detector imports or labels in the EquiFrame core."""

from equiframe_benchmark.calibration_types import (
    CalibrationManifest,
    CalibrationSelection,
    DetectorSelectionAudit,
    audit_detector_selections,
)
from equiframe_benchmark.integration import (
    IntegrationComparison,
    IntegrationResult,
    IntegrationRun,
    IntegrationSpec,
    read_integration,
    run_integration,
)
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import (
    Assignment,
    Candidate,
    Catalog,
    InputBinding,
    OracleResult,
    Review,
    ReviewAssignment,
    ReviewPacket,
    Scenario,
    SplitManifest,
    digest,
)
from equiframe_benchmark.oracle import evaluate_oracle, review_packet
from equiframe_benchmark.reconciliation import (
    AwardReconciliationResult,
    AwardReconciliationSpec,
    CurrencyReconciliation,
    ReconciliationCheck,
    reconcile_awards,
)
from equiframe_benchmark.selection import select_normal_calibration, select_normal_training
from equiframe_benchmark.snapshot import (
    SnapshotClient,
    SnapshotColumn,
    SnapshotDataSource,
    SnapshotManifest,
    SnapshotTable,
    snapshot_fingerprint,
)
from equiframe_benchmark.splits import dependency_groups, make_splits, split_counts, validate_splits
from equiframe_benchmark.training_types import TrainingManifest, TrainingRecord, TrainingSelection

__version__ = "0.9.0"
__all__ = [
    "Assignment",
    "AwardReconciliationResult",
    "AwardReconciliationSpec",
    "CalibrationManifest",
    "CalibrationSelection",
    "Candidate",
    "Catalog",
    "CurrencyReconciliation",
    "DetectorSelectionAudit",
    "InputBinding",
    "IntegrationComparison",
    "IntegrationResult",
    "IntegrationRun",
    "IntegrationSpec",
    "OracleResult",
    "ReconciliationCheck",
    "Review",
    "ReviewAssignment",
    "ReviewPacket",
    "Scenario",
    "SnapshotClient",
    "SnapshotColumn",
    "SnapshotDataSource",
    "SnapshotManifest",
    "SnapshotTable",
    "SplitManifest",
    "TrainingManifest",
    "TrainingRecord",
    "TrainingSelection",
    "audit_detector_selections",
    "dependency_groups",
    "digest",
    "evaluate_oracle",
    "load_document",
    "make_splits",
    "read_integration",
    "reconcile_awards",
    "review_packet",
    "run_integration",
    "save_document",
    "select_normal_calibration",
    "select_normal_training",
    "snapshot_fingerprint",
    "split_counts",
    "validate_splits",
]
