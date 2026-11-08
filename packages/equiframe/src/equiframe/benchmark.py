"""Quarantine for the removed, unsupported auxiliary benchmark draft.

The former implementation supplied placeholder metrics, reused training profiles
for calibration, and mislabeled row-count comparisons as R. It is not scientific
evidence. The old function names remain only to give callers an actionable error;
none executes, reads inputs, fits a detector, computes metrics, or writes files.
The independent ``equiframe_benchmark`` distribution is not a drop-in replacement.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from equiframe import (
        DecisionState,
        DetectorBundle,
        DetectorSupport,
        ExecutionResult,
        IsolationForestConfig,
        ProfileVector,
    )

_UNSUPPORTED_MESSAGE = (
    "equiframe.benchmark is quarantined: the unsupported auxiliary draft has been "
    "removed and cannot produce benchmark results or evidence. Use the separate "
    "equiframe_benchmark package following packages/equiframe-benchmark/README.md "
    "(Instalar y ejecutar), then run 'equiframe-benchmark --help'. This is not a "
    "drop-in replacement; independent review and experimental protocol requirements "
    "still apply."
)


class UnsupportedBenchmarkError(RuntimeError):
    """An attempt to use the quarantined auxiliary benchmark draft."""


def run_benchmark(engines: list[str], families: list[str], work_dir: Path) -> NoReturn:
    """Reject the unsupported draft without running ETL or creating artifacts."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def collect_profile_vectors(work_dir: Path, families: list[str], engines: list[str]) -> NoReturn:
    """Reject the unsupported draft without reading any profiles."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def fit_isolation_forest_mad(
    training_vectors: list[ProfileVector],
    config: IsolationForestConfig | None = None,
    support: DetectorSupport | None = None,
) -> NoReturn:
    """Reject the unsupported draft without fitting or calibrating detectors."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def detect_anomalies(bundle: DetectorBundle, vectors: list[ProfileVector]) -> NoReturn:
    """Reject the unsupported draft without issuing detector decisions."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def rule_divergence(results: dict[str, dict[str, list[ExecutionResult]]]) -> NoReturn:
    """Reject the removed row-count proxy; it did not implement rules R."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def compute_metrics(
    rule_diverge: dict[str, list[bool]],
    model_decisions: list[DecisionState],
    engines: list[str],
) -> NoReturn:
    """Reject the removed placeholder metrics; no metric values are returned."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def write_summary_tables(
    work_dir: Path,
    results: dict[str, dict[str, list[ExecutionResult]]],
    profile_vectors: list[tuple[str, str, ProfileVector]],
    m_decisions: list[DecisionState],
    b_decisions: list[DecisionState],
    rule_diverge: dict[str, list[bool]],
    engines: list[str],
) -> NoReturn:
    """Reject the unsupported draft without creating or modifying any files."""
    raise UnsupportedBenchmarkError(_UNSUPPORTED_MESSAGE)


def main() -> NoReturn:
    """Explain quarantine and exit 2; only --help exits successfully."""
    parser = argparse.ArgumentParser(description=_UNSUPPORTED_MESSAGE)
    # Accept old options only far enough to provide the quarantine diagnostic.
    # They never select inputs, create a destination, or execute the old workflow.
    parser.parse_known_args()
    parser.error(_UNSUPPORTED_MESSAGE)


if __name__ == "__main__":
    main()
