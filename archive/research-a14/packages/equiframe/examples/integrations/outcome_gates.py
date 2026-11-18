"""Synthetic installed-package smoke: reports and empty outputs never grant approval.

Requires the identified private wheel with the arrow extra. Run this copied file
outside the repository. Every case uses a new child directory; no prior evidence
is overwritten. Exit zero means the expected gate behavior was observed.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def reject_truth_value(value: object) -> None:
    """Treat failure to reject implicit approval as a broken example, even with -O."""
    try:
        bool(value)
    except TypeError as error:
        if "has no truth value" not in str(error):
            raise
    else:
        raise RuntimeError(f"{type(value).__name__} incorrectly accepted a truth test")


def run(work_dir: Path) -> list[dict[str, str | bool | int]]:
    work_dir.mkdir(parents=True, exist_ok=True)
    expected = pa.table({"id": ["one", "two"], "quantity": [10, 20]})
    observations: list[dict[str, str | bool | int]] = []
    for case in ("equivalent", "different", "not_evaluable", "empty"):
        reference = expected.slice(0, 0) if case == "empty" else expected
        candidate = (
            pa.table({"id": ["one", "two"], "quantity": [10, 21]})
            if case == "different"
            else reference
        )
        directory = Path(tempfile.mkdtemp(prefix=case + "-", dir=work_dir))
        result = ef.diff(
            candidate,
            reference,
            keys=["id"],
            options=ef.ComparisonOptions(max_work=1) if case == "not_evaluable" else None,
            work_dir=directory / "comparison",
        )
        report = ef.write_comparison_report(result, directory / "report")
        reject_truth_value(result)
        reject_truth_value(report)
        wanted_state = "equivalent" if case == "empty" else case
        if result.state != wanted_state or report.state != result.state:
            raise RuntimeError("comparison/report state differs from the synthetic expectation")
        try:
            ef.assert_equivalent(result)
        except ef.EquivalenceDifferentError:
            gate = "different"
        except ef.EquivalenceNotEvaluableError:
            gate = "not_evaluable"
        else:
            gate = "equivalent"
        if gate != wanted_state:
            raise RuntimeError("the explicit assertion did not preserve the comparison verdict")
        # Emptiness is legitimate only for this captured-output contract. It does
        # not establish a business requirement that any records must exist.
        observations.append(
            {
                "case": case,
                "state": result.state,
                "complete": result.complete,
                "candidate_rows": candidate.num_rows,
                "explicit_gate": gate,
                "report_generated": True,
                "implicit_approval_rejected": True,
            }
        )
    for state in ("passed", "failed", "not_evaluable", "not_requested", "pending_review"):
        reject_truth_value(ef.VerificationCheck(state=state, reason="Synthetic gate example"))
    reject_truth_value(ef.CompilationCheck(engine="synthetic", supported=True))
    reject_truth_value(ef.DetectorScores(state="not_estimable", reason="No input support"))
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.work_dir), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
