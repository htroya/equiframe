"""A pinned synthetic data client consumed by core alone; no real service or DW."""

from __future__ import annotations

import argparse
import hashlib
from decimal import Decimal
from pathlib import Path

import pyarrow as pa

import equiframe as ef


class LocalClient:
    """Replace this trusted local transport with your separately managed client."""

    def __init__(self, manifest: ef.SnapshotManifest, payload: bytes) -> None:
        self.manifest = manifest
        self.payload = payload
        self.manifest_calls = 0

    def get_snapshot(self, snapshot_id: str) -> ef.SnapshotManifest:
        if snapshot_id != self.manifest.snapshot_id:
            raise LookupError("unknown snapshot")
        self.manifest_calls += 1
        return self.manifest

    def download_artifact(self, ref: ef.ArtifactRef, destination: Path) -> None:
        if ref != self.manifest.tables[0].artifact:
            raise LookupError("unknown snapshot artifact")
        with destination.open("xb") as stream:
            stream.write(self.payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = pa.table(
        {
            "id": pa.array([1, 1, 2], type=pa.int64()),
            "amount": pa.array([Decimal("1.10"), None, Decimal("-0.01")], pa.decimal128(8, 2)),
        }
    )
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, expected.schema) as writer:
        writer.write_table(expected)
    payload = sink.getvalue().to_pybytes()
    logical_types = (ef.IntegerType(bits=64, signed=True), ef.DecimalType(precision=8, scale=2))
    manifest = ef.SnapshotManifest(
        snapshot_id="synthetic.001",
        domain_schema_revision="synthetic-domain.1",
        extraction_revision="synthetic-extract.1",
        provenance=("Synthetic local integration example; no real client or DW acceptance",),
        tables=(
            ef.SnapshotTable(
                name="items",
                artifact=ef.ArtifactRef(
                    schema_version="1.0",
                    uri="https://example.invalid/synthetic.arrow",
                    sha256=hashlib.sha256(payload).hexdigest(),
                    format="arrow",
                    media_type="application/vnd.apache.arrow.file",
                    size_bytes=len(payload),
                ),
                row_count=expected.num_rows,
                columns=tuple(
                    ef.SnapshotColumn(
                        name=field.name,
                        physical_type=str(field.type),
                        logical_type=kind,
                        nullable=True,
                    )
                    for field, kind in zip(expected.schema, logical_types, strict=True)
                ),
            ),
        ),
    )
    # The URI identifies bytes. This injected client does not visit it or use credentials.
    client = LocalClient(manifest, payload)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=client)
    columns = tuple(
        ef.ColumnSpec(
            name=field.name,
            logical_type=kind,
            nullable=True,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="synthetic_units"),
        )
        for field, kind in zip(expected.schema, logical_types, strict=True)
    )
    schema = ef.bag_contract(columns).spec.contract.output.schema_spec
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="synthetic.snapshot",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="items", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    registry = ef.TransformationRegistry()
    registry.register(ef.DuckDBTransformation("identity", 'SELECT * FROM "items"', "example.v1"))
    result = ef.execute(
        ef.ExecutionPlan(contract=contract, engine="duckdb", transformation_id="identity"),
        source=source,
        registry=registry,
        work_dir=args.output / "execution",
    )
    if result.state != "completed":
        raise RuntimeError("snapshot execution did not complete: " + result.state)
    comparison = ef.compare(
        result,
        ef.ArrowInput(expected),
        contract=contract,
        reference="expected",
        work_dir=args.output / "comparison",
    )
    ef.assert_equivalent(comparison)
    if client.manifest_calls != 1:
        raise RuntimeError("the snapshot was not pinned exactly once")
    print("Pinned core-only snapshot: 3 rows, exact Decimal/NULL/multiplicity, equivalent")
    print("Synthetic behavior check; no remote service or independent human acceptance")


if __name__ == "__main__":
    main()
