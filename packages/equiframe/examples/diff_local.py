"""Installed-wheel consumer of direct inputs and inspectable contract provenance."""

import argparse
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("arrow", "pandas", "polars"), default="arrow")
    parser.add_argument("--work-dir", type=Path, default=Path("diff-evidence"))
    args = parser.parse_args()
    expected = pa.table({"id": ["001", "002"], "quantity": [10, 20]})
    candidate = pa.table({"id": ["002", "001"], "quantity": [21, 10]})

    def native(table: pa.Table) -> ef.DiffInput:
        if args.engine == "pandas":
            return table.to_pandas()
        if args.engine == "polars":
            import polars as pl

            return pl.from_arrow(table)
        return table

    result = ef.diff(
        native(candidate),
        native(expected),
        keys=["id"],
        work_dir=args.work_dir,
        options=ef.ComparisonOptions(batch_rows=1),
    )
    assert result.state == "different" and result.complete and result.strategy == "key"
    changes = tuple(ef.iter_differences(result.differences))
    assert len(changes) == 1 and changes[0].column == "quantity"
    assert changes[0].key[0].value == "002"
    declaration = ef.read_diff_contract(result)
    assert declaration.spec == result.spec and declaration.reference == "expected"
    assert ef.DiffContract.model_validate_json(declaration.model_dump_json()) == declaration
    same = ef.diff(native(expected), native(expected), contract=declaration, work_dir=args.work_dir)
    assert same.state == "equivalent" and same.complete
    print(args.engine, result.state, len(changes), same.state, "provenance verified")


if __name__ == "__main__":
    main()
