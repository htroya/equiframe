"""Read temporary orders, convert native frames and verify a one-row regression."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import equiframe as ef


def positive_rows(value: str) -> int:
    """Reject invalid sizes through argparse's normal stderr/exit-2 path."""
    try:
        rows = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("rows must be a positive integer") from error
    if rows < 1:
        raise argparse.ArgumentTypeError("rows must be a positive integer")
    return rows


def check_orders(rows: int) -> None:
    """Use installed EquiFrame APIs; remove all synthetic files when finished."""
    orders = [{"id": f"{index:06d}", "amount": index * 3} for index in range(rows)]
    with tempfile.TemporaryDirectory(prefix="equiframe-orders-") as temporary:
        directory = Path(temporary)
        source = directory / "orders.json"
        source.write_text(json.dumps(orders), encoding="utf-8")

        with ef.load_dataset(source) as loaded:
            assert len(loaded.pandas) == rows
            for engine in ("polars", "duckdb"):
                with ef.convert_dataset(loaded, target=engine) as converted:
                    result = ef.diff(
                        loaded.pandas,
                        converted.frame,
                        keys=["id"],
                        work_dir=directory / f"compare-{engine}",
                    )
                    ef.assert_equivalent(result)
                    print(f"Pandas -> {engine}: {rows} rows, {result.state}")

            with ef.convert_dataset(loaded, target="polars") as converted:
                import polars as pl

                changed = converted.frame.with_columns(
                    pl.when(pl.col("id") == orders[-1]["id"])
                    .then(pl.col("amount") + 1)
                    .otherwise(pl.col("amount"))
                    .alias("amount")
                )
                result = ef.diff(
                    loaded.pandas,
                    changed,
                    keys=["id"],
                    work_dir=directory / "changed-order",
                )
                assert result.complete and result.state == "different"
                changes = tuple(ef.iter_differences(result.differences))
                assert len(changes) == 1 and changes[0].column == "amount"
                try:
                    ef.assert_equivalent(result)
                except ef.EquivalenceAssertionError as error:
                    assert error.code == "different"
                    print("One changed amount detected; acceptance correctly rejected")
                else:
                    raise AssertionError("The changed order was accepted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=positive_rows, default=30000)
    arguments = parser.parse_args()
    try:
        check_orders(arguments.rows)
    except ef.EquiFrameError as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")
    except OSError as error:
        parser.exit(1, f"temporary_file_error: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
