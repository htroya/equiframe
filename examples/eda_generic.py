"""Reproducible synthetic EDA; standalone, no migration or detector training."""

import argparse
import csv
import hashlib
from pathlib import Path

from equiframe.eda import Conversion, EdaConfig, NumericRule, Source, analyze, read_result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=False)
    inputs = args.work_dir / "input"
    inputs.mkdir()
    path = inputs / "sales.csv"
    with path.open("x", encoding="utf8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "amount", "currency"])
        writer.writerows(
            (f"{i:03}", f"{v}.00", "USD") for i, v in enumerate([1, 2, 3, 4, 5, 6, 7, 100], 1)
        )
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    result = analyze(
        Source(
            path=str(path),
            format="csv",
            snapshot_id="synthetic-sales-v1",
            expected_sha256=fingerprint,
        ),
        config=EdaConfig(
            charts=True,
            identifiers=("id",),
            conversions=(Conversion(column="amount", target="money", kind="decimal", scale=2),),
            numeric=(
                NumericRule(
                    column="money", groups=("currency",), monetary=True, currency_column="currency"
                ),
            ),
        ),
        output=args.work_dir / "eda",
    )
    if (
        result.state != "completed"
        or result.rows != 8
        or read_result(args.work_dir / "eda") != result
    ):
        raise RuntimeError("synthetic EDA incomplete or inconsistent")
    if result.numeric[0]["groups"][0]["outliers"]["count"] != 1:
        raise RuntimeError("independent expected outlier count differs")
    if hashlib.sha256(path.read_bytes()).hexdigest() != fingerprint:
        raise RuntimeError("input changed")
    print("PASS: eight synthetic rows, exact Decimal, one investigation candidate; input unchanged")
    print(args.work_dir / "eda/report.html")


if __name__ == "__main__":
    main()
