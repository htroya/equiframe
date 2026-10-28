"""Synthetic snapshot-client conformance; no remote service or DW is assumed."""

import hashlib
import json
import math
import time
from datetime import date, datetime
from datetime import timezone as _timezone
from decimal import Decimal

import equiframe as ef
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from equiframe.errors import (
    ArtifactIntegrityError,
    ExecutionCancelled,
    ExecutionTimeout,
    InvalidExecutionInput,
    ResourceLimitError,
)
from equiframe.execution import RunContext
from equiframe.local import LocalArtifactStore
from pydantic import ValidationError

from equiframe_benchmark.fixtures import column, contract
from equiframe_benchmark.snapshot import (
    SnapshotColumn,
    SnapshotDataSource,
    SnapshotManifest,
    SnapshotTable,
    snapshot_fingerprint,
)

UTC = _timezone.utc


class LocalClient:
    """Injected test client: copies synthetic bytes without network or credentials."""

    def __init__(self, manifest, payloads):
        self.manifest = manifest
        self.payloads = payloads
        self.snapshot_calls = []
        self.download_calls = []
        self.after_download = lambda: None

    def get_snapshot(self, snapshot_id):
        self.snapshot_calls.append(snapshot_id)
        return self.manifest

    def download_artifact(self, ref, destination):
        self.download_calls.append((ref, destination))
        with destination.open("xb") as stream:
            stream.write(self.payloads[ref.uri])
        self.after_download()


def make_snapshot(format="arrow"):
    logical = (
        ef.IntegerType(bits=64, signed=True),
        ef.StringType(),
        ef.DecimalType(precision=18, scale=2),
        ef.FloatType(bits=64),
        ef.DateType(),
        ef.TimestampType(unit="us", timezone="UTC"),
        ef.BooleanType(),
    )
    table = pa.table(
        {
            "id": [1, 1, 2, 3],
            "currency": ["USD", "USD", "EUR", None],
            "amount": pa.array(
                [Decimal("1.10"), Decimal("1.10"), None, Decimal("0.00")],
                type=pa.decimal128(18, 2),
            ),
            "measurement": pa.array([float("nan"), None, -0.0, 2.0], from_pandas=False),
            "day": pa.array([date(2026, 1, 2)] * 4, type=pa.date32()),
            "instant": pa.array(
                [datetime(2026, 1, 2, tzinfo=UTC)] * 4,
                type=pa.timestamp("us", tz="UTC"),
            ),
            "active": [True, False, None, True],
        }
    )
    dimension = pa.table({"id": [1, 2, 3]})
    tables = {"items": table, "dimension": dimension}
    descriptors = []
    payloads = {}
    for name, data in tables.items():
        sink = pa.BufferOutputStream()
        if format == "parquet":
            pq.write_table(data, sink)
        else:
            with pa.ipc.new_file(sink, data.schema) as writer:
                writer.write_table(data)
        payload = sink.getvalue().to_pybytes()
        uri = f"https://synthetic.invalid/snapshot-001/{name}.{format}"
        artifact = ef.ArtifactRef(
            schema_version="1.0",
            uri=uri,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            format=format,
            media_type="application/vnd.apache.arrow.file"
            if format == "arrow"
            else "application/vnd.apache.parquet",
        )
        payloads[uri] = payload
        kinds = logical if name == "items" else (logical[0],)
        descriptors.append(
            SnapshotTable(
                name=name,
                artifact=artifact,
                row_count=data.num_rows,
                columns=tuple(
                    SnapshotColumn(
                        name=field.name,
                        physical_type=str(field.type),
                        logical_type=kind,
                        nullable=True,
                    )
                    for field, kind in zip(data.schema, kinds, strict=True)
                ),
            )
        )
    manifest = SnapshotManifest(
        snapshot_id="snapshot-001",
        domain_schema_revision="synthetic-domain.1",
        extraction_revision="synthetic-extract.1",
        provenance=("synthetic conformance fixture; no real DW data",),
        tables=tuple(descriptors),
    )
    return manifest, payloads, tables


def context(tmp_path, manifest, *, options=None, cancellation=None, deadline=None, name="run"):
    specifications = {
        table.name: tuple(column(item.name, item.logical_type) for item in table.columns)
        for table in manifest.tables
    }
    plan = ef.ExecutionPlan(
        contract=contract("nulls_types", specifications, specifications["items"]),
        engine="duckdb",
        transformation_id="synthetic.identity",
        options=options or ef.ExecutionOptions(),
    )
    directory = tmp_path / name
    directory.mkdir()
    return RunContext(
        run_id=name,
        execution_id="execution." + name,
        plan=plan,
        directory=directory,
        store=LocalArtifactStore(directory / "artifacts"),
        cancellation=cancellation or ef.CancellationToken(),
        deadline=deadline,
    )


@pytest.mark.parametrize("format", ["arrow", "parquet"])
def test_pins_manifest_once_and_preserves_data_types_and_original_reference(tmp_path, format):
    manifest, payloads, tables = make_snapshot(format)
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource(
        "snapshot-001", client=client, expected_domain_schema_revision="synthetic-domain.1"
    )
    client.manifest = SnapshotManifest.model_validate_json(
        manifest.model_dump_json().replace("snapshot-001", "snapshot-002")
    )
    run = context(tmp_path, manifest)
    items = source.resolve("items", context=run)
    dimension = source.resolve("dimension", context=run)
    again = source.resolve("items", context=run)
    assert source.snapshot_id == manifest.snapshot_id and source.manifest == manifest
    assert source.table_names == ("items", "dimension")
    assert client.snapshot_calls == ["snapshot-001"]
    assert items.origin == manifest.tables[0].artifact
    assert items.table.schema == tables["items"].schema
    assert dimension.table.equals(tables["dimension"])
    rows = items.table.to_pylist()
    assert rows[0]["amount"] == rows[1]["amount"] == Decimal("1.10")
    assert rows[2]["amount"] is None and rows[3]["amount"] == Decimal("0.00")
    assert math.isnan(rows[0]["measurement"]) and rows[1]["measurement"] is None
    assert math.copysign(1.0, rows[2]["measurement"]) == -1.0
    assert rows[0]["instant"] == datetime(2026, 1, 2, tzinfo=UTC)
    assert again.origin == items.origin
    assert len({destination.parent for _, destination in client.download_calls}) == 3
    recorded = {item.name: item.value.value for item in run.effective_configuration}
    assert recorded["snapshot_id"] == "snapshot-001"
    assert recorded["snapshot_manifest_sha256"] == snapshot_fingerprint(manifest)
    assert len(run.effective_configuration) == 4
    assert json.loads(
        (run.directory / "snapshot-manifest.json").read_text("utf8")
    ) == manifest.model_dump(mode="json")
    assert not list(run.directory.rglob("download.part.*"))


def test_repeated_run_records_same_snapshot_identity_in_each_execution(tmp_path):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource("snapshot-001", client=client)
    first = context(tmp_path, manifest, name="first")
    second = context(tmp_path, manifest, name="second")
    source.resolve("items", context=first)
    source.resolve("items", context=second)
    assert (first.directory / "snapshot-manifest.json").read_bytes() == (
        second.directory / "snapshot-manifest.json"
    ).read_bytes()
    assert client.snapshot_calls == ["snapshot-001"]


@pytest.mark.parametrize("identifier", ["latest", "LATEST", "Latest"])
def test_rejects_latest_before_calling_client(identifier):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    with pytest.raises(ValueError, match="explicit"):
        SnapshotDataSource(identifier, client=client)
    assert not client.snapshot_calls
    value = manifest.model_dump(mode="json")
    value["snapshot_id"] = identifier
    with pytest.raises(ValidationError, match="explicit"):
        SnapshotManifest.model_validate_json(json.dumps(value))


def test_rejects_identity_and_domain_revision_mismatch():
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    with pytest.raises(ArtifactIntegrityError, match="different snapshot"):
        SnapshotDataSource("snapshot-other", client=client)
    with pytest.raises(InvalidExecutionInput, match="schema revision"):
        SnapshotDataSource(
            "snapshot-001", client=client, expected_domain_schema_revision="domain.other"
        )


@pytest.mark.parametrize(
    "changed", ["hash", "size", "row_count", "physical", "logical", "names", "nullable"]
)
def test_verifies_bytes_rows_and_declared_schema_before_exposing_data(tmp_path, changed):
    manifest, payloads, _ = make_snapshot()
    value = manifest.model_dump(mode="json")
    expected = value["tables"][0]
    if changed == "hash":
        original = payloads[expected["artifact"]["uri"]]
        payloads[expected["artifact"]["uri"]] = original[:-1] + bytes([original[-1] ^ 1])
    elif changed == "size":
        payloads[expected["artifact"]["uri"]] += b"unexpected bytes"
    elif changed == "row_count":
        expected["row_count"] -= 1
    elif changed == "physical":
        expected["columns"][0]["physical_type"] = "int32"
    elif changed == "logical":
        expected["columns"][0]["logical_type"] = {"kind": "integer", "bits": 32, "signed": True}
    elif changed == "names":
        expected["columns"][0]["name"] = "other"
    else:
        expected["columns"][1]["nullable"] = False
    manifest = SnapshotManifest.model_validate_json(json.dumps(value))
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource("snapshot-001", client=client)
    run = context(tmp_path, manifest)
    with pytest.raises(ArtifactIntegrityError):
        source.resolve("items", context=run)
    assert not list(run.directory.rglob("download.part.*"))


def test_missing_table_and_predeclared_resource_limits_do_not_download(tmp_path):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource("snapshot-001", client=client)
    normal = context(tmp_path, manifest, name="normal")
    with pytest.raises(InvalidExecutionInput, match="absent"):
        source.resolve("missing", context=normal)
    for index, options in enumerate(
        (ef.ExecutionOptions(max_input_rows=1), ef.ExecutionOptions(max_transport_bytes=1))
    ):
        run = context(tmp_path, manifest, options=options, name="limit" + str(index))
        with pytest.raises(ResourceLimitError):
            source.resolve("items", context=run)
    assert not client.download_calls


def test_materialized_arrow_buffer_limit_is_checked_for_compressed_input(tmp_path):
    manifest, payloads, _ = make_snapshot("parquet")
    # A highly compressible column can fit the transport budget while decoded
    # Arrow buffers exceed it. Both sizes must be checked independently.
    data = pa.table({"id": [1] * 10_000})
    sink = pa.BufferOutputStream()
    pq.write_table(data, sink, compression="zstd")
    payload = sink.getvalue().to_pybytes()
    value = manifest.model_dump(mode="json")
    expected = value["tables"][1]
    expected["row_count"] = data.num_rows
    expected["artifact"]["size_bytes"] = len(payload)
    expected["artifact"]["sha256"] = hashlib.sha256(payload).hexdigest()
    payloads[expected["artifact"]["uri"]] = payload
    manifest = SnapshotManifest.model_validate_json(json.dumps(value))
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource("snapshot-001", client=client)
    assert len(payload) < data.nbytes
    run = context(tmp_path, manifest, options=ef.ExecutionOptions(max_transport_bytes=len(payload)))
    with pytest.raises(ResourceLimitError, match="Arrow buffer"):
        source.resolve("dimension", context=run)


def test_checks_cancellation_and_deadline_before_and_after_client_calls(tmp_path):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    token = ef.CancellationToken()
    token.cancel()
    with pytest.raises(ExecutionCancelled):
        SnapshotDataSource("snapshot-001", client=client, cancellation=token)
    assert not client.snapshot_calls
    source = SnapshotDataSource("snapshot-001", client=client)
    cancelled = context(tmp_path, manifest, cancellation=token, name="cancelled")
    with pytest.raises(ExecutionCancelled):
        source.resolve("items", context=cancelled)
    expired = context(tmp_path, manifest, deadline=time.perf_counter() - 1, name="expired")
    with pytest.raises(ExecutionTimeout):
        source.resolve("items", context=expired)
    assert not client.download_calls
    active = context(tmp_path, manifest, name="during")
    client.after_download = active.cancellation.cancel
    with pytest.raises(ExecutionCancelled):
        source.resolve("items", context=active)
    assert not list(active.directory.rglob("download.part.*"))
    late = context(tmp_path, manifest, name="late")
    client.after_download = lambda: setattr(late, "deadline", time.perf_counter() - 1)
    with pytest.raises(ExecutionTimeout):
        source.resolve("items", context=late)


def test_manifest_rejects_mutability_unpublished_and_duplicate_tables():
    manifest, _, _ = make_snapshot()
    for changed, replacement in (("immutable", False), ("state", "building")):
        value = manifest.model_dump(mode="json")
        value[changed] = replacement
        with pytest.raises(ValidationError):
            SnapshotManifest.model_validate_json(json.dumps(value))
    value = manifest.model_dump(mode="json")
    value["tables"].append(value["tables"][0])
    with pytest.raises(ValidationError, match="unique"):
        SnapshotManifest.model_validate_json(json.dumps(value))
    with pytest.raises(ValidationError):
        manifest.snapshot_id = "changed"


def test_changed_artifact_after_first_resolve_is_rejected_without_refetching_manifest(tmp_path):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource("snapshot-001", client=client)
    run = context(tmp_path, manifest)
    source.resolve("items", context=run)
    uri = manifest.tables[0].artifact.uri
    original = payloads[uri]
    payloads[uri] = original[:-1] + bytes([original[-1] ^ 1])
    with pytest.raises(ArtifactIntegrityError, match="SHA-256"):
        source.resolve("items", context=run)
    assert client.snapshot_calls == ["snapshot-001"]


def test_transport_failure_is_propagated_without_retry_or_partial_artifact(tmp_path):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    calls = []

    def fail(ref, destination):
        calls.append(ref)
        destination.write_bytes(b"partial download")
        raise ConnectionError("synthetic transport failure")

    client.download_artifact = fail
    source = SnapshotDataSource("snapshot-001", client=client)
    run = context(tmp_path, manifest)
    with pytest.raises(ConnectionError, match="synthetic transport"):
        source.resolve("items", context=run)
    assert len(calls) == 1
    assert not list(run.directory.rglob("download.part.*"))


def test_constructor_rejects_a_manifest_returned_after_cancellation():
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    token = ef.CancellationToken()

    def fetch(snapshot_id):
        token.cancel()
        return manifest

    client.get_snapshot = fetch
    with pytest.raises(ExecutionCancelled, match="after cancellation"):
        SnapshotDataSource("snapshot-001", client=client, cancellation=token)


def test_table_selection_keeps_full_pinned_manifest_and_only_resolves_selected_inputs(tmp_path):
    manifest, payloads, tables = make_snapshot()
    client = LocalClient(manifest, payloads)
    source = SnapshotDataSource("snapshot-001", client=client, table_names=("items",))
    assert source.table_names == ("items",)
    assert source.manifest == manifest
    assert len(source.manifest.tables) == 2
    assert snapshot_fingerprint(source.manifest) == snapshot_fingerprint(manifest)
    run = context(tmp_path, manifest)
    loaded = source.resolve("items", context=run)
    assert loaded.table.num_rows == tables["items"].num_rows
    with pytest.raises(InvalidExecutionInput, match="absent"):
        source.resolve("dimension", context=run)
    assert client.snapshot_calls == ["snapshot-001"]
    assert len(client.download_calls) == 1


@pytest.mark.parametrize("selection", [(), ("items", "items"), ("missing",)])
def test_invalid_table_selection_is_rejected_before_download(selection):
    manifest, payloads, _ = make_snapshot()
    client = LocalClient(manifest, payloads)
    with pytest.raises(ValueError, match="nonempty, unique and available"):
        SnapshotDataSource("snapshot-001", client=client, table_names=selection)
    assert client.snapshot_calls == ["snapshot-001"]
    assert not client.download_calls
