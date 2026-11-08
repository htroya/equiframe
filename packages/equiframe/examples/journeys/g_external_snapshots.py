"""G: fixed-identity injected client, provenance and byte/schema integrity errors."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, column, comparison_record, new_output, write_summary
else:
    from common import cli, column, comparison_record, new_output, write_summary

SCENARIOS = ("good", "different", "error", "schema_error")
SNAPSHOT_ID = "synthetic.snapshot.20261006.v1"


class MemoryClient:
    """A trusted transport fixture. No HTTP request, credentials or hidden dataset."""

    def __init__(self, manifest: ef.SnapshotManifest, payload: bytes) -> None:
        self.manifest = manifest
        self.payload = payload
        self.requests: list[str] = []
        self.downloads = 0

    def get_snapshot(self, snapshot_id: str) -> ef.SnapshotManifest:
        if snapshot_id != SNAPSHOT_ID:
            raise LookupError("Unknown fixed snapshot identity")
        self.requests.append(snapshot_id)
        return self.manifest

    def download_artifact(self, ref: ef.ArtifactRef, destination: Path) -> None:
        if ref != self.manifest.tables[0].artifact:
            raise LookupError("Unknown artifact")
        self.downloads += 1
        with destination.open("xb") as stream:
            stream.write(self.payload)


def fixture(scenario: str) -> tuple[MemoryClient, pa.Table, ef.Contract]:
    import pyarrow as pa

    schema = pa.schema([("id", pa.int64()), ("amount", pa.decimal128(8, 2))])
    expected = pa.Table.from_pylist(
        [{"id": 1, "amount": Decimal("1.10")}, {"id": 2, "amount": None}], schema=schema
    )
    actual = pa.Table.from_pylist(
        [
            {"id": 1, "amount": Decimal("1.11" if scenario == "different" else "1.10")},
            {"id": 2, "amount": None},
        ],
        schema=schema,
    )
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, actual.schema) as writer:
        writer.write_table(actual)
    payload = sink.getvalue().to_pybytes()
    kinds: tuple[ef.LogicalType, ...] = (
        ef.IntegerType(bits=64, signed=True),
        ef.DecimalType(precision=8, scale=2),
    )
    manifest = ef.SnapshotManifest(
        snapshot_id=SNAPSHOT_ID,
        domain_schema_revision="synthetic-ledger.1",
        extraction_revision="synthetic-generator.1",
        provenance=("Inline synthetic fixture authored for journey G; no live warehouse",),
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
                row_count=2,
                columns=tuple(
                    ef.SnapshotColumn(
                        name=field.name,
                        physical_type="int32"
                        if scenario == "schema_error" and field.name == "id"
                        else str(field.type),
                        logical_type=kind,
                        nullable=field.name == "amount",
                    )
                    for field, kind in zip(schema, kinds, strict=True)
                ),
            ),
        ),
    )
    # Alter one known synthetic byte after recording the manifest; preserve size.
    if scenario == "error":
        payload = bytes([payload[0] ^ 1]) + payload[1:]
    client = MemoryClient(manifest, payload)
    declaration = ef.keyed_contract(
        (
            column("id", kinds[0], unit="identifier"),
            column("amount", kinds[1], nullable=True, unit="USD"),
        ),
        keys=["id"],
    )
    output_schema = declaration.spec.contract.output.schema_spec
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="journey.G.snapshot",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="items", schema_spec=output_schema),),
        output=ef.TableSpec(name="result", schema_spec=output_schema),
        preconditions=(),
        rules=(),
    )
    return client, expected, contract


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    private = new_output(output, scenario, SCENARIOS)
    client, expected, contract = fixture(scenario)
    source = ef.SnapshotDataSource(
        SNAPSHOT_ID, client=client, expected_domain_schema_revision="synthetic-ledger.1"
    )
    registry = ef.TransformationRegistry()
    registry.register(ef.DuckDBTransformation("identity", 'SELECT * FROM "items"', "journey.G.v1"))
    execution = ef.execute(
        ef.ExecutionPlan(
            contract=contract,
            engine="duckdb",
            transformation_id="identity",
            options=ef.ExecutionOptions(duckdb_threads=1),
        ),
        source=source,
        registry=registry,
        work_dir=private,
    )
    configuration = {
        parameter.name: parameter.value.value
        for parameter in execution.effective_configuration
        if isinstance(parameter.value, ef.StringValue)
    }
    provenance_preserved = configuration.get("snapshot_id") == SNAPSHOT_ID and configuration.get(
        "snapshot_manifest_sha256"
    ) == ef.snapshot_fingerprint(client.manifest)
    record: dict[str, object]
    if execution.state == "completed":
        comparison = ef.compare(
            execution,
            ef.ArrowInput(expected),
            contract=contract,
            reference="expected",
            work_dir=private,
        )
        record = comparison_record(comparison, output, "snapshot")
    else:
        record = {
            "accepted": False,
            "exit_code": 2,
            "state": "error",
            "problem_code": execution.problem.code if execution.problem is not None else None,
        }
    if client.requests != [SNAPSHOT_ID] or client.downloads != 1 or not provenance_preserved:
        raise RuntimeError("Snapshot identity/provenance was not retained")
    return write_summary(
        output,
        {
            "journey": "G",
            "synthetic": True,
            "scenario": scenario,
            "snapshot_id": SNAPSHOT_ID,
            "manifest_requests": len(client.requests),
            "download_count": client.downloads,
            "provenance_preserved": provenance_preserved,
            "execution_state": execution.state,
            "output_available": execution.output is not None,
            "integrity": (
                "passed"
                if execution.state == "completed"
                else "rejected"
                if execution.problem is not None
                and execution.problem.code == "artifact_integrity_error"
                else "not_evaluable"
            ),
            **record,
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "G", SCENARIOS))
