"""Synthetic inventory outputs: equal totals and shared error do not establish correctness."""

import argparse
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    schema = ef.TableSchema(
        columns=(
            ef.ColumnSpec(
                name="sku",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            ef.ColumnSpec(
                name="quantity",
                logical_type=ef.IntegerType(bits=64, signed=True),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="units"),
            ),
        ),
        keys=(
            ef.KeySpec(
                name="sku_key",
                columns=("sku",),
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
        contract_id="inventory.verify",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="inventory", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    store = ef.LocalArtifactStore(root / "artifacts")

    def capture(name: str, quantities: list[int]) -> ef.ArtifactRef:
        data = pa.table({"sku": ["001", "002"], "quantity": quantities})
        path = root / (name + ".arrow")
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, data.schema) as writer:
            writer.write_table(data)
        return store.put(path, media_type="application/vnd.apache.arrow.file")

    expected = capture("independent_literal", [2, 8])
    wrong = capture("shared_wrong", [8, 2])
    report = ef.verify(
        {"external_a": wrong, "external_b": wrong},
        contract=contract,
        expected=expected,
        require_expected=True,
        work_dir=root,
    )
    assert report.agreement.state == "passed"
    assert all(c.state == "failed" for c in report.expected)
    assert not report.publishable and report.exit_code == 1
    operation = root / report.verification_id
    assert ef.read_verification(operation) == report
    ef.export_bundle(operation, root / "portable")
    ef.import_bundle(root / "portable", root / "relocated")
    print("Agreement passed; both expected comparisons failed; publication blocked.")
    print(operation)


if __name__ == "__main__":
    main()
