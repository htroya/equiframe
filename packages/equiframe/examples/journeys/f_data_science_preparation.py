"""F: prove feature preparation preserves records; do not infer anomaly quality."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, column, comparison_record, new_output, write_summary
else:
    from common import cli, column, comparison_record, new_output, write_summary

SCENARIOS = ("good", "different", "not_evaluable", "dropped_row", "changed_id")


def materialize(scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import pandas as pd

    source = pd.DataFrame(
        {
            "sample_id": pd.Series(["0001", "0002", "0003", "0004"], dtype="string[pyarrow]"),
            "duration_ms": [1000, 2500, 0, 1000000],
            "events": [2, 3, 0, 99],
        }
    )
    # Explicit predetermined scale; it is not fitted using labels or test outputs.
    candidate = source[["sample_id", "events"]].assign(duration_s=source["duration_ms"] / 1000.0)
    candidate = candidate[["sample_id", "duration_s", "events"]]
    # The large fourth value is intentionally conserved, not called an anomaly.
    expected = pd.DataFrame(
        {
            "sample_id": pd.Series(["0001", "0002", "0003", "0004"], dtype="string[pyarrow]"),
            "duration_s": [1.0, 2.5, 0.0, 1000.0],
            "events": [2, 3, 0, 99],
        }
    )
    if scenario == "different":
        candidate["duration_s"] = candidate["duration_s"].clip(upper=100.0)
    elif scenario == "dropped_row":
        candidate = candidate.iloc[:3].reset_index(drop=True)
    elif scenario == "changed_id":
        candidate.loc[0, "sample_id"] = "1"
    return candidate, expected


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    private = new_output(output, scenario, SCENARIOS)
    candidate, expected = materialize(scenario)
    declaration = ef.keyed_contract(
        (
            column("sample_id", ef.StringType()),
            column("duration_s", ef.FloatType(bits=64), unit="seconds"),
            column("events", ef.IntegerType(bits=64, signed=True), unit="events"),
        ),
        keys=["sample_id"],
        contract_id="journey.F.features",
    )
    result = ef.diff(
        candidate,
        expected,
        contract=declaration,
        options=ef.ComparisonOptions(max_rows=1 if scenario == "not_evaluable" else 100),
        work_dir=private,
    )
    return write_summary(
        output,
        {
            "journey": "F",
            "synthetic": True,
            "scenario": scenario,
            "anomaly_detection": "not_requested",
            "model_training": "not_requested",
            **comparison_record(result, output, "features"),
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "F", SCENARIOS))
