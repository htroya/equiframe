"""D: exact Decimal reconciliation catches offsetting per-record money errors."""

from __future__ import annotations

from decimal import Decimal, localcontext
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, column, comparison_record, new_output, write_summary
else:
    from common import cli, column, comparison_record, new_output, write_summary


def fixture(scenario: str) -> tuple[pa.Table, pa.Table]:
    import pyarrow as pa

    schema = pa.schema(
        [("account", pa.string()), ("currency", pa.string()), ("amount", pa.decimal128(20, 2))]
    )
    # Authored from the tiny synthetic ledger specification, not from totals.
    expected = pa.Table.from_pylist(
        [
            {"account": "A", "currency": "USD", "amount": Decimal("1000000000000000.01")},
            {"account": "B", "currency": "USD", "amount": Decimal("0.09")},
            {"account": "A", "currency": "EUR", "amount": Decimal("12.50")},
        ],
        schema=schema,
    )
    candidate = pa.Table.from_pylist(
        [
            {
                "account": "A",
                "currency": "USD",
                "amount": Decimal(
                    "1000000000000000.02" if scenario == "different" else "1000000000000000.01"
                ),
            },
            {
                "account": "B",
                "currency": "USD",
                "amount": Decimal("0.08" if scenario == "different" else "0.09"),
            },
            {"account": "A", "currency": "EUR", "amount": Decimal("12.50")},
        ],
        schema=schema,
    )
    return candidate, expected


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    private = new_output(output, scenario)
    candidate, expected = fixture(scenario)
    with localcontext() as context:
        context.prec = 40  # Enough for exact sums of this explicitly bounded fixture.
        totals_match = all(
            sum(row["amount"] for row in candidate.to_pylist() if row["currency"] == currency)
            == sum(row["amount"] for row in expected.to_pylist() if row["currency"] == currency)
            for currency in ("USD", "EUR")
        )
    declaration = ef.keyed_contract(
        (
            column("account", ef.StringType()),
            column("currency", ef.StringType()),
            column("amount", ef.DecimalType(precision=20, scale=2), unit="currency_amount"),
        ),
        keys=["account", "currency"],
        contract_id="journey.D.exact-ledger",
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
            "journey": "D",
            "synthetic": True,
            "scenario": scenario,
            "per_currency_totals_match": totals_match,
            "currency_conversion": "not_requested",
            **comparison_record(result, output, "ledger"),
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "D"))
