"""Arrow-only external consumer: independent expectation, full differences, no ETL."""

import argparse
from decimal import Decimal
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path("comparison-runs"))
    args = parser.parse_args()
    schema = ef.TableSchema(
        columns=(
            ef.ColumnSpec(
                name="account",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            ef.ColumnSpec(
                name="amount",
                logical_type=ef.DecimalType(precision=18, scale=2),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
            ),
        ),
        keys=(
            ef.KeySpec(
                name="account",
                columns=("account",),
                unique=True,
                incomplete="reject",
                scope=ef.TableKeyScope(),
            ),
        ),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="retail.amounts",
        revision=1,
        family="aggregations",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    expected = pa.table(
        {
            "account": ["001", "002"],
            "amount": pa.array([Decimal("100.00"), Decimal("200.00")], type=pa.decimal128(18, 2)),
        }
    )
    observed = pa.table(
        {
            "account": ["001", "002"],
            "amount": pa.array([Decimal("200.00"), Decimal("100.00")], type=pa.decimal128(18, 2)),
        }
    )
    result = ef.compare(
        ef.ArrowInput(observed),
        ef.ArrowInput(expected),
        contract=contract,
        reference="expected",
        work_dir=args.work_dir,
        options=ef.ComparisonOptions(max_examples=1),
    )
    assert result.state == "different" and result.complete
    assert result.counts.difference_records == 2 and len(result.examples) == 1
    assert len(list(ef.iter_differences(result.differences))) == 2
    # Persisted inputs can be compared again without rerunning a transformation.
    assert result.right is not None
    identical = ef.compare(
        result.right.data,
        ef.ArrowInput(expected),
        contract=contract,
        reference="expected",
        work_dir=args.work_dir,
    )
    assert identical.state == "equivalent"
    print(result.state, result.counts.difference_records, result.differences.uri)


if __name__ == "__main__":
    main()
