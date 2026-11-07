"""Generic snapshot consumption without the experimental benchmark package."""

import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe._documents import digest, save_document


def snapshot(tmp_path):
    table = pa.table(
        {
            "id": [1, 1, 2],
            "amount": pa.array([Decimal("1.10"), None, Decimal("-0.01")], pa.decimal128(8, 2)),
        }
    )
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
    payload = sink.getvalue().to_pybytes()
    artifact = ef.ArtifactRef(
        schema_version="1.0",
        uri=(tmp_path / "immutable.arrow").as_uri(),
        sha256=hashlib.sha256(payload).hexdigest(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        size_bytes=len(payload),
    )
    manifest = ef.SnapshotManifest(
        snapshot_id="synthetic.001",
        domain_schema_revision="domain.1",
        extraction_revision="extract.1",
        provenance=("Synthetic exact snapshot: café, no external service",),
        tables=(
            ef.SnapshotTable(
                name="items",
                artifact=artifact,
                row_count=3,
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
    return manifest, payload, table


class Client:
    def __init__(self, manifest, payload):
        self.manifest = manifest
        self.payload = payload
        self.calls = []

    def get_snapshot(self, snapshot_id):
        self.calls.append(snapshot_id)
        return self.manifest

    def download_artifact(self, ref, destination):
        with destination.open("xb") as stream:
            stream.write(self.payload)


def context(tmp_path, manifest):
    columns = tuple(
        ef.ColumnSpec(
            name=column.name,
            logical_type=column.logical_type,
            nullable=column.nullable,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="synthetic"),
        )
        for column in manifest.tables[0].columns
    )
    schema = ef.bag_contract(columns).spec.contract.output.schema_spec
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="snapshot.consumer",
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
        run_id="synthetic.run",
        execution_id="synthetic.execution",
        plan=ef.ExecutionPlan(contract=contract, engine="duckdb", transformation_id="identity"),
        directory=directory,
        store=ef.LocalArtifactStore(directory / "artifacts"),
        cancellation=ef.CancellationToken(),
        deadline=None,
    )


def test_core_snapshot_pins_identity_and_preserves_exact_content(tmp_path):
    manifest, payload, expected = snapshot(tmp_path)
    client = Client(manifest, payload)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=client)
    run = context(tmp_path, manifest)
    loaded = source.resolve("items", context=run)
    assert client.calls == [manifest.snapshot_id]
    assert loaded.origin == manifest.tables[0].artifact
    assert loaded.table.equals(expected)
    assert loaded.table.to_pylist() == [
        {"id": 1, "amount": Decimal("1.10")},
        {"id": 1, "amount": None},
        {"id": 2, "amount": Decimal("-0.01")},
    ]
    assert source.manifest == manifest and source.table_names == ("items",)
    recorded = (run.directory / "snapshot-manifest.json").read_bytes()
    assert hashlib.sha256(recorded[:-1]).hexdigest() == ef.snapshot_fingerprint(manifest)
    assert b"caf\\u00e9" in recorded
    assert recorded.endswith(b"\n")


def test_historical_schema_and_ascii_fingerprint_are_unchanged(tmp_path):
    manifest, _, _ = snapshot(tmp_path)
    payload = json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    assert (
        ef.snapshot_fingerprint(manifest) == digest(manifest) == hashlib.sha256(payload).hexdigest()
    )
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "schemas/snapshot-manifest-1.0.schema.json"
        ).read_text()
    )
    assert manifest.model_json_schema() == schema
    assert (
        hashlib.sha256(
            (json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        ).hexdigest()
        == "213bd042e61f312908d8800bddb508c7aace554088c7d4875cfef6015099595f"
    )
    target = tmp_path / "published.json"
    save_document(manifest, target)
    assert target.read_bytes() == payload + b"\n"
    with pytest.raises(FileExistsError):
        save_document(manifest, target)
    assert target.read_bytes() == payload + b"\n"


@pytest.mark.parametrize("change", ["snapshot", "schema", "bytes", "content"])
def test_core_source_rejects_mismatched_manifest_or_artifact(tmp_path, change):
    manifest, payload, _ = snapshot(tmp_path)
    client = Client(manifest, payload)
    if change == "snapshot":
        with pytest.raises(ef.ArtifactIntegrityError):
            ef.SnapshotDataSource("other.snapshot", client=client)
    elif change == "schema":
        with pytest.raises(ef.InvalidExecutionInput):
            ef.SnapshotDataSource(
                manifest.snapshot_id, client=client, expected_domain_schema_revision="other"
            )
    else:
        client.payload = (
            payload + b"x" if change == "bytes" else bytes([payload[0] ^ 1]) + payload[1:]
        )
        source = ef.SnapshotDataSource(manifest.snapshot_id, client=client)
        with pytest.raises(ef.ArtifactIntegrityError):
            source.resolve("items", context=context(tmp_path, manifest))


@pytest.mark.parametrize("selection", [(), ("missing",), ("items", "items")])
def test_table_selection_stays_explicit(tmp_path, selection):
    manifest, payload, _ = snapshot(tmp_path)
    with pytest.raises(ValueError):
        ef.SnapshotDataSource(
            manifest.snapshot_id, client=Client(manifest, payload), table_names=selection
        )


def test_metadata_remains_strict_and_versioned(tmp_path):
    manifest, _, _ = snapshot(tmp_path)
    for update in ({"snapshot_id": "latest"}, {"schema_version": "2.0"}, {"immutable": False}):
        with pytest.raises(ValidationError):
            ef.SnapshotManifest.model_validate({**manifest.model_dump(), **update})


def test_core_import_and_manifest_use_do_not_load_benchmark_or_optional_engines():
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import equiframe as ef; "
            "assert ef.SnapshotManifest.model_json_schema(); "
            "blocked = {'equiframe_benchmark', 'pyarrow', 'pandas', 'polars', "
            "'duckdb', 'numpy', 'sklearn'}; "
            "assert not any(n.split('.')[0] in blocked for n in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_long_lived_source_does_not_retain_finished_run_identities(tmp_path):
    manifest, payload, _ = snapshot(tmp_path)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=Client(manifest, payload))
    run = context(tmp_path, manifest)
    source.resolve("items", context=run)
    source.resolve("items", context=run)
    assert len(run.effective_configuration) == 4
    assert not hasattr(source, "_recorded_runs")


def test_same_context_ids_do_not_skip_manifest_in_an_independent_context(tmp_path):
    manifest, payload, _ = snapshot(tmp_path)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=Client(manifest, payload))
    first = context(tmp_path, manifest)
    other = tmp_path / "other"
    other.mkdir()
    second = context(other, manifest)
    assert (first.run_id, first.execution_id) == (second.run_id, second.execution_id)
    source.resolve("items", context=first)
    source.resolve("items", context=second)
    source.resolve("items", context=first)
    source.resolve("items", context=second)
    assert (first.directory / "snapshot-manifest.json").read_bytes() == (
        second.directory / "snapshot-manifest.json"
    ).read_bytes()
    assert len(first.effective_configuration) == len(second.effective_configuration) == 4


def test_replaced_contexts_share_verified_snapshot_publication(tmp_path):
    from dataclasses import replace

    manifest, payload, _ = snapshot(tmp_path)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=Client(manifest, payload))
    run = context(tmp_path, manifest)
    first = replace(
        run, plan=run.plan.model_copy(update={"options": ef.ExecutionOptions(max_input_rows=10)})
    )
    second = replace(
        run, plan=run.plan.model_copy(update={"options": ef.ExecutionOptions(max_input_rows=20)})
    )
    source.resolve("items", context=first)
    source.resolve("items", context=second)
    assert len(run.effective_configuration) == 4
    assert first.effective_configuration is second.effective_configuration


@pytest.mark.parametrize("change", ["missing", "bytes", "configuration"])
def test_repeated_resolve_rejects_inconsistent_manifest_state(tmp_path, change):
    manifest, payload, _ = snapshot(tmp_path)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=Client(manifest, payload))
    run = context(tmp_path, manifest)
    source.resolve("items", context=run)
    path = run.directory / "snapshot-manifest.json"
    if change == "missing":
        path.unlink()
    elif change == "bytes":
        path.write_bytes(b"wrong")
    else:
        run.effective_configuration[0] = ef.Parameter(
            name="snapshot_id", value=ef.StringValue(value="other.snapshot")
        )
    with pytest.raises(ef.ArtifactIntegrityError):
        source.resolve("items", context=run)


def test_two_table_snapshot_workflow_reuses_manifest_across_consumer_contexts(tmp_path):
    manifest, payload, _ = snapshot(tmp_path)
    manifest = manifest.model_copy(
        update={
            "tables": tuple(
                manifest.tables[0].model_copy(update={"name": name}) for name in ("left", "right")
            )
        }
    )
    contract = context(tmp_path, manifest).plan.contract
    client = Client(manifest, payload)
    source = ef.SnapshotDataSource(manifest.snapshot_id, client=client)
    stages = tuple(
        ef.WorkflowStage(
            stage_id=name,
            migration=ef.MigrationSpec(
                ir=ef.RelationalPlan(
                    nodes=(ef.Scan(node_id="scan", table="items"),), output="scan"
                ),
                contract=contract,
                source_engine="pandas",
                target_engine="polars",
                require_rules=False,
                execution_options=ef.ExecutionOptions(max_input_rows=budget),
                comparison_policy=ef.ComparisonPolicy(
                    index="ignore", justification="Generated native indexes have no ETL meaning"
                ),
            ),
            inputs=(ef.WorkflowInputBinding(name="items", source=name),),
        )
        for name, budget in (("left", 3), ("right", 6))
    )
    result = ef.run_workflow(
        ef.WorkflowSpec(workflow_id="snapshot.two-tables", stages=stages),
        source=source,
        work_dir=tmp_path / "workflow",
    )
    assert result.complete and result.exit_code == 0
    assert [checkpoint.state for checkpoint in result.checkpoints] == ["passed", "passed"]
    assert {item.name for item in result.inputs} == {"left", "right"}
    assert client.calls == [manifest.snapshot_id]
    assert ef.read_workflow(tmp_path / "workflow" / result.run_id) == result
