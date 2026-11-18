"""Synthetic comparison report; --render-only needs no Arrow/notebook dependency."""

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("report-example"))
    parser.add_argument("--render-only", type=Path)
    args = parser.parse_args()
    if args.render_only is not None:
        report = ef.read_comparison_report(args.render_only)
        assert report.state == "different" and report.complete
        assert "different" in report.to_text()
        assert "<html" in report.to_html()
        assert "<script" not in report._repr_html_()
        print("Detached JSON/text/HTML/notebook views agree without optional dependencies")
        return

    import pyarrow as pa

    expected = pa.table(
        {
            "id": [1, 2, 3],
            "amount": pa.array(
                [Decimal("10.00"), Decimal("20.00"), Decimal("30.00")], type=pa.decimal128(12, 2)
            ),
            "day": [date(2026, 1, 1)] * 3,
            "measure": pa.array([None, float("nan"), 3.0], type=pa.float64()),
        }
    )
    candidate = expected.set_column(
        1,
        "amount",
        pa.array([Decimal("11.00"), Decimal("20.00"), Decimal("31.00")], type=pa.decimal128(12, 2)),
    )
    result = ef.diff(
        candidate,
        expected,
        keys=["id"],
        work_dir=args.output / "original",
        options=ef.ComparisonOptions(max_examples=1),
    )
    root = args.output / "original" / result.comparison_id
    private = ef.write_comparison_report(result, args.output / "diagnostic")
    assert private.state == "different" and private.evidence.values_withheld
    report = ef.write_comparison_report(
        result,
        args.output / "detail",
        evidence_root=root,
        options=ef.ReportOptions(
            mode="detail",
            include_values=True,
            include_metadata=True,
            max_examples=1,
            require_exhaustive=True,
        ),
        declaration=ef.read_diff_contract(result),
    )
    assert report.state == "different" and report.complete
    assert report.evidence.acceptance == "satisfied" and not report.evidence.display_complete
    counts = {item.name: item for item in report.counts}
    assert counts["modified_rows"].value == 2 and counts["modified_rows"].precision == "exact"
    assert ef.read_comparison_report(args.output / "detail" / "report.json") == report
    print(report.to_text())
    print("Synthetic reports:", args.output / "detail" / "report.html")


if __name__ == "__main__":
    main()
