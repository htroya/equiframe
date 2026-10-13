"""Real optional integration: verified Parquet, exact Decimal and core schema checks."""

import sys
from decimal import Decimal
from pathlib import Path

import equiframe as ef
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core_adapter import CoreSnapshotClient
from job_manager import JobManager
from snapshot_client import SnapshotClient


def fixture(tmp_path):
    table = pa.table(
        {"id": [1, 2], "amount": pa.array([Decimal("10.20"), None], pa.decimal128(8, 2))}
    )
    path = tmp_path / "table.parquet"
    pq.write_table(table, path)
    manager = JobManager(tmp_path / "state")
    job = manager.submit_job("load", "v1", "key")
    manager.run_job(job.job_id, {"items": path})
    local = SnapshotClient(manager.snaps_dir)
    ref = local.get_snapshot("v1").artifacts[0]
    artifact = ef.ArtifactRef(
        schema_version="1.0",
        uri=path.as_uri(),
        sha256=ref.sha256,
        format="parquet",
        media_type="application/vnd.apache.parquet",
        size_bytes=ref.size_bytes,
    )
    manifest = ef.SnapshotManifest(
        snapshot_id="v1",
        domain_schema_revision="domain.1",
        extraction_revision="extract.1",
        provenance=("Synthetic independent expectations",),
        tables=(
            ef.SnapshotTable(
                name="items",
                artifact=artifact,
                row_count=2,
                columns=(
                    ef.SnapshotColumn(
                        name="id",
                        physical_type="int64",
                        logical_type=ef.IntegerType(bits=64, signed=True),
                        nullable=False,
                    ),
                    ef.SnapshotColumn(
                        name="amount",
                        physical_type="decimal128(8, 2)",
                        logical_type=ef.DecimalType(precision=8, scale=2),
                        nullable=True,
                    ),
                ),
            ),
        ),
    )
    return manager, local, manifest, table


def context(tmp_path, manifest):
    columns = tuple(
        ef.ColumnSpec(
            name=c.name,
            logical_type=c.logical_type,
            nullable=c.nullable,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="synthetic"),
        )
        for c in manifest.tables[0].columns
    )
    schema = ef.bag_contract(columns).spec.contract.output.schema_spec
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="consumer",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="items", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    directory = tmp_path / "execution"
    directory.mkdir()
    return ef.RunContext(
        run_id="r",
        execution_id="e",
        plan=ef.ExecutionPlan(contract=contract, engine="duckdb", transformation_id="identity"),
        directory=directory,
        store=ef.LocalArtifactStore(directory / "artifacts"),
        cancellation=ef.CancellationToken(),
        deadline=None,
    )


def test_real_core_consumer_preserves_decimal_and_missing_values(tmp_path):
    manager, client, manifest, expected = fixture(tmp_path)
    bridge = CoreSnapshotClient(client, manifest)
    source = ef.SnapshotDataSource("v1", client=bridge)
    loaded = source.resolve("items", context=context(tmp_path, manifest))
    assert loaded.table.to_pylist() == [
        {"id": 1, "amount": Decimal("10.20")},
        {"id": 2, "amount": None},
    ]
    assert loaded.table.schema == expected.schema
    assert source.manifest is not None


def test_bridge_rejects_wrong_hash(tmp_path):
    _, client, manifest, _ = fixture(tmp_path)
    wrong = manifest.model_copy(
        update={
            "tables": (
                manifest.tables[0].model_copy(
                    update={
                        "artifact": manifest.tables[0].artifact.model_copy(
                            update={"sha256": "0" * 64}
                        )
                    }
                ),
            )
        }
    )
    with pytest.raises(ef.ArtifactIntegrityError):
        CoreSnapshotClient(client, wrong)


def test_bridge_rejects_foreign_snapshot(tmp_path):
    _, client, manifest, _ = fixture(tmp_path)
    bridge = CoreSnapshotClient(client, manifest)
    with pytest.raises(ValueError):
        bridge.get_snapshot("v2")


def test_core_detects_independent_row_count_disagreement(tmp_path):
    _, client, manifest, _ = fixture(tmp_path)
    wrong = manifest.model_copy(
        update={"tables": (manifest.tables[0].model_copy(update={"row_count": 3}),)}
    )
    source = ef.SnapshotDataSource("v1", client=CoreSnapshotClient(client, wrong))
    with pytest.raises(ef.ArtifactIntegrityError):
        source.resolve("items", context=context(tmp_path, wrong))
