"""Experimental boundary: no detector imports or labels in the EquiFrame core."""

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
from equiframe_benchmark.selection import select_normal_training
from equiframe_benchmark.splits import dependency_groups, make_splits, split_counts, validate_splits
from equiframe_benchmark.training_types import TrainingManifest, TrainingRecord, TrainingSelection

__version__ = "0.6.0"
__all__ = [
    "Assignment",
    "Candidate",
    "Catalog",
    "InputBinding",
    "OracleResult",
    "Review",
    "ReviewAssignment",
    "ReviewPacket",
    "Scenario",
    "SplitManifest",
    "TrainingManifest",
    "TrainingRecord",
    "TrainingSelection",
    "dependency_groups",
    "digest",
    "evaluate_oracle",
    "load_document",
    "make_splits",
    "review_packet",
    "save_document",
    "select_normal_training",
    "split_counts",
    "validate_splits",
]
