"""A: pandas refactor, exact money, composite keys and visible duplicate failures."""

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

SCENARIOS = ("good", "different", "not_evaluable", "duplicate")


def materialize(scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import pandas as pd

    source = pd.DataFrame(
        {
            "order_id": pd.Series(["001", "001", "002"], dtype="string[pyarrow]"),
            "line": [1, 2, 1],
            "quantity": [2, 1, 3],
            "unit_cents": [125, 50, 100],
        }
    )
    # Independent literal, not computed using old or optimized transformation.
    expected = pd.DataFrame(
        {
            "order_id": pd.Series(["001", "001", "002"], dtype="string[pyarrow]"),
            "line": [1, 2, 1],
            "total_cents": [250, 50, 300],
        }
    )
    old = source[["order_id", "line"]].copy()
    old["total_cents"] = [
        int(quantity) * int(price)
        for quantity, price in zip(source["quantity"], source["unit_cents"], strict=True)
    ]
    pd.testing.assert_frame_equal(old, expected)
    candidate = source[["order_id", "line"]].assign(
        total_cents=source["quantity"] * source["unit_cents"]
    )
    if scenario == "different":
        candidate["total_cents"] += candidate["order_id"].eq("002").astype("int64")
    if scenario == "duplicate":
        candidate = pd.concat([candidate, candidate.iloc[[0]]], ignore_index=True)
    else:
        candidate = candidate.iloc[[2, 0, 1]].reset_index(drop=True)
    return candidate, expected


def declaration() -> ef.DiffContract:
    return ef.keyed_contract(
        (
            column("order_id", ef.StringType()),
            column("line", ef.IntegerType(bits=64, signed=True), unit="line_identifier"),
            column("total_cents", ef.IntegerType(bits=64, signed=True), unit="USD_cent"),
        ),
        keys=["order_id", "line"],
        contract_id="journey.A.refactor",
    )


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    private = new_output(output, scenario, SCENARIOS)
    candidate, expected = materialize(scenario)
    result = ef.diff(
        candidate,
        expected,
        contract=declaration(),
        options=ef.ComparisonOptions(max_rows=1 if scenario == "not_evaluable" else 100),
        work_dir=private,
    )
    record = comparison_record(result, output, "refactor")
    return write_summary(
        output,
        {"journey": "A", "synthetic": True, "scenario": scenario, **record},
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "A", SCENARIOS))
