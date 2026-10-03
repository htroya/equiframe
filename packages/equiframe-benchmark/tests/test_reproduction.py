"""Technical reproduction fixtures; no person or scientific approval is asserted."""

import hashlib
import json
import shutil
from decimal import Decimal

import equiframe as ef
import pytest
from equiframe.errors import ArtifactIntegrityError, ResourceLimitError
from equiframe.evidence import canonical_bytes
from equiframe.local import local_path
from pydantic import ValidationError

from equiframe_benchmark import reproduction
from equiframe_benchmark.pilot import write_table
from equiframe_benchmark.reproduction import (
    BundleFile,
    BundleLimits,
    ComparisonReceipt,
    ReproductionBundle,
    ReproductionRecord,
    bundle_artifact,
    compare_reproductions,
    create_bundle,
    make_reproduction_record,
    read_bundle,
    reproduce_bundle,
)


def record(*, rows=None, **changes):
    values = {
        "configuration": {"alpha": {"decimal": "0.05"}, "seed": 10},
        "splits": [{"scenario": "synthetic-a", "group": "g1", "partition": "test"}],
        "labels": [{"scenario": "synthetic-a", "status": "pending", "label": None}],
        "decisions": [
            {"scenario": "synthetic-a", "R": "alert", "M": "not_evaluable", "H": "alert"}
        ],
        "tables": {
            "logical_columns": ["entity", "currency", "amount"],
            "logical_rows": rows
            or [
                ["a", "USD", {"decimal": "100.00"}],
                ["b", "USD", {"decimal": "200.00"}],
            ],
            "currency_totals": {"USD": {"decimal": "300.00"}},
        },
    }
    values.update(changes)
    return make_reproduction_record(**values)


def source_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    config = source / "record.json"
    config.write_bytes(canonical_bytes(record().model_dump(mode="json")))
    payload = source / "table.arrow"
    payload.write_bytes(b"synthetic opaque artifact, not an Arrow-table validity claim")
    ref = ef.ArtifactRef(
        schema_version="1.0",
        uri=payload.as_uri(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
        size_bytes=payload.stat().st_size,
    )
    return {"records/record.json": config, "data/table.arrow": payload}, ref


def packaged(tmp_path):
    files, ref = source_files(tmp_path)
    destination = tmp_path / "bundle"
    bundle = create_bundle(
        files,
        directory=destination,
        bundle_id="explicit-synthetic-reproduction",
        record_path="records/record.json",
        artifacts={"data/table.arrow": ref},
    )
    return destination, bundle, ref


def test_streaming_portable_bundle_preserves_original_documents(tmp_path, monkeypatch):
    files, ref = source_files(tmp_path)
    files["data/table.arrow"].write_bytes(b"x" * (3 * 1024 * 1024 + 23))
    content_hash = hashlib.sha256(files["data/table.arrow"].read_bytes()).hexdigest()
    original_record = files["records/record.json"].read_bytes()

    def no_whole_file_reads(self):
        raise AssertionError("bundle copies must stream rather than read_bytes")

    monkeypatch.setattr(type(tmp_path), "read_bytes", no_whole_file_reads)
    original_ref = ef.ArtifactRef.model_validate(
        {
            **ref.model_dump(mode="python"),
            "sha256": content_hash,
            "size_bytes": files["data/table.arrow"].stat().st_size,
        }
    )
    root = tmp_path / "bundle"
    bundle = create_bundle(
        files,
        directory=root,
        bundle_id="synthetic-large",
        record_path="records/record.json",
        artifacts={"data/table.arrow": original_ref},
    )
    moved = tmp_path / "independent-directory"
    root.rename(moved)
    shutil.rmtree(tmp_path / "source")
    assert read_bundle(moved) == bundle
    rebound = bundle_artifact(bundle, moved, original_ref)
    assert rebound.sha256 == content_hash
    assert rebound.format == original_ref.format
    assert rebound.uri != original_ref.uri
    with (moved / "records/record.json").open("rb") as data:
        assert data.read() == original_record
    assert local_path(rebound) == moved / "data/table.arrow"


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/absolute",
        "a/../outside",
        "a//b",
        "a\\b",
        "C:/outside",
        "a/./b",
        "a/b.",
        "a/b ",
        "a/CON.txt",
        "aux",
        "a:b",
        "a\x00b",
        "a?b",
        "COM¹.txt",
    ],
)
def test_rejects_unsafe_portable_names(path):
    with pytest.raises(ValidationError):
        BundleFile(path=path, sha256="0" * 64, size_bytes=0)


def test_unsafe_creation_cannot_escape_or_publish(tmp_path):
    source = tmp_path / "source"
    source.write_text("original")
    with pytest.raises(ValueError):
        create_bundle({"../escape": source}, directory=tmp_path / "bundle", bundle_id="bad")
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "bundle").exists()
    assert not list(tmp_path.glob(".bundle-*"))


@pytest.mark.parametrize("fault", ("hash", "size"))
def test_raw_expected_file_pin_rejects_before_publication(tmp_path, fault):
    source = tmp_path / "source.bin"
    source.write_bytes(b"raw frozen content, no format conversion")
    checksum, size = hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size
    expected = ("0" * 64, size) if fault == "hash" else (checksum, size + 1)
    output = tmp_path / "bundle"
    with pytest.raises(ArtifactIntegrityError, match="expected file pin"):
        create_bundle(
            {"raw/source.bin": source},
            directory=output,
            bundle_id="raw-pin-test",
            expected_files={"raw/source.bin": expected},
        )
    assert not output.exists() and not list(tmp_path.glob(".bundle-*"))


def test_raw_source_changed_after_pin_is_not_published(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"before")
    expected = (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size)
    source.write_bytes(b"after!")
    output = tmp_path / "bundle"
    with pytest.raises(ArtifactIntegrityError, match="expected file pin"):
        create_bundle(
            {"source.bin": source},
            directory=output,
            bundle_id="changed-raw-test",
            expected_files={"source.bin": expected},
        )
    assert not output.exists() and not list(tmp_path.glob(".bundle-*"))


@pytest.mark.parametrize(
    "expected", (("bad-hash", 1), ("0" * 64, -1), ("0" * 64, True), ["0" * 64, 1])
)
def test_raw_pins_validate_types_and_ranges_before_copy(tmp_path, expected):
    source = tmp_path / "source.bin"
    source.write_bytes(b"raw")
    with pytest.raises(ValueError):
        create_bundle(
            {"source.bin": source},
            directory=tmp_path / "bundle",
            bundle_id="invalid-pin",
            expected_files={"source.bin": expected},
        )
    assert not (tmp_path / "bundle").exists() and not list(tmp_path.glob(".bundle-*"))


def test_raw_pin_has_no_implicit_format_and_requires_an_inventoried_key(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"raw")
    expected = (hashlib.sha256(source.read_bytes()).hexdigest(), 3)
    with pytest.raises(ValueError, match="belong"):
        create_bundle(
            {"source.bin": source},
            directory=tmp_path / "invalid",
            bundle_id="invalid-key",
            expected_files={"absent.bin": expected},
        )
    output = tmp_path / "bundle"
    bundle = create_bundle(
        {"source.bin": source},
        directory=output,
        bundle_id="raw-pin",
        expected_files={"source.bin": expected},
    )
    assert bundle.files[0].artifact_format is None
    assert read_bundle(output) == bundle


def test_rejects_reserved_manifest_case_collisions_and_file_prefixes():
    def item(path, uri=None):
        return BundleFile(path=path, sha256="0" * 64, size_bytes=0, source_uri=uri)

    with pytest.raises(ValidationError):
        item("BUNDLE.JSON")
    with pytest.raises(ValidationError):
        item("bundle.json/nested")
    for files in (
        (item("A"), item("a")),
        (item("a"), item("a/b")),
        (item("a", "file:///same"), item("b", "file:///same")),
        (item("A/file1"), item("a/file2")),
    ):
        with pytest.raises(ValidationError):
            ReproductionBundle(bundle_id="bad", files=files)


def test_manifest_pin_and_corrupt_artifacts_rejected(tmp_path):
    root, bundle, _ = packaged(tmp_path)
    with pytest.raises(ArtifactIntegrityError, match="manifest"):
        read_bundle(root, expected_sha256="0" * 64)
    file = root / bundle.files[0].path
    data = bytearray(file.read_bytes())
    data[-1] ^= 1
    file.write_bytes(data)
    with pytest.raises(ArtifactIntegrityError, match="SHA-256"):
        read_bundle(root)


@pytest.mark.parametrize("kind", ["file", "empty_directory", "nested_directory", "missing"])
def test_closed_inventory_rejects_extras_and_missing(tmp_path, kind):
    root, _, _ = packaged(tmp_path)
    if kind == "file":
        (root / "extra").write_text("not registered")
    elif kind == "empty_directory":
        (root / "extra").mkdir()
    elif kind == "nested_directory":
        (root / "extra/more").mkdir(parents=True)
    else:
        (root / "data/table.arrow").unlink()
    with pytest.raises((ArtifactIntegrityError, ResourceLimitError)):
        read_bundle(root)


def test_manifest_cannot_claim_traversal(tmp_path):
    root, _, _ = packaged(tmp_path)
    document = json.loads((root / "bundle.json").read_text())
    document["files"][0]["path"] = "../source/table.arrow"
    (root / "bundle.json").write_bytes(canonical_bytes(document))
    with pytest.raises(ValidationError):
        read_bundle(root)


def test_duplicate_json_members_and_nan_are_rejected(tmp_path):
    root, _, _ = packaged(tmp_path)
    for contents in (b'{"bundle_id":"a","bundle_id":"b"}', b'{"value":NaN}'):
        (root / "bundle.json").write_bytes(contents)
        with pytest.raises(ValueError):
            read_bundle(root)


def test_publication_never_replaces_even_empty_existing_directory(tmp_path):
    files, _ = source_files(tmp_path)
    destination = tmp_path / "bundle"
    destination.mkdir()
    before = destination.stat()
    with pytest.raises(FileExistsError):
        create_bundle(files, directory=destination, bundle_id="existing")
    assert destination.stat().st_ino == before.st_ino
    assert not list(destination.iterdir())


def test_source_artifact_identity_and_format_must_be_registered(tmp_path):
    files, ref = source_files(tmp_path)
    bad = ef.ArtifactRef.model_validate({**ref.model_dump(mode="python"), "sha256": "0" * 64})
    with pytest.raises(ArtifactIntegrityError):
        create_bundle(
            files, directory=tmp_path / "bad", bundle_id="bad", artifacts={"data/table.arrow": bad}
        )
    assert not (tmp_path / "bad").exists()
    root = tmp_path / "unregistered"
    bundle = create_bundle(files, directory=root, bundle_id="unregistered")
    with pytest.raises(ArtifactIntegrityError, match="format"):
        bundle_artifact(bundle, root, ref)


def test_rebasing_checks_all_four_identity_fields(tmp_path):
    root, bundle, ref = packaged(tmp_path)
    for change in (
        {"uri": "file:///other"},
        {"sha256": "0" * 64},
        {"size_bytes": ref.size_bytes + 1},
        {"format": "parquet"},
    ):
        altered = ef.ArtifactRef.model_validate({**ref.model_dump(mode="python"), **change})
        with pytest.raises(ArtifactIntegrityError):
            bundle_artifact(bundle, root, altered)


@pytest.mark.parametrize(
    "limit",
    [
        {"max_files": 1},
        {"max_file_bytes": 10},
        {"max_total_bytes": 10},
        {"max_manifest_bytes": 10},
    ],
)
def test_creation_and_reader_enforce_accounting_budgets(tmp_path, limit):
    root, _, _ = packaged(tmp_path)
    limits = BundleLimits(**limit)
    with pytest.raises(ResourceLimitError):
        read_bundle(root, limits=limits)
    files = {"a": tmp_path / "source/record.json", "b": tmp_path / "source/table.arrow"}
    with pytest.raises(ResourceLimitError):
        create_bundle(files, directory=tmp_path / "small", bundle_id="small", limits=limits)
    assert not (tmp_path / "small").exists()


def test_symlink_source_and_inventory_are_rejected(tmp_path):
    root, _, _ = packaged(tmp_path)
    source = tmp_path / "source/record.json"
    link = tmp_path / "source-link"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("this Windows account lacks symlink creation privileges")
    with pytest.raises(ArtifactIntegrityError, match="links"):
        create_bundle({"record": link}, directory=tmp_path / "linked", bundle_id="linked")
    (root / "data/table.arrow").unlink()
    (root / "data/table.arrow").symlink_to(source)
    with pytest.raises(ArtifactIntegrityError, match="link"):
        read_bundle(root)


def test_comparison_compares_complete_values_not_sizes_or_totals():
    original = record()
    exchanged = record(
        rows=[
            ["a", "USD", {"decimal": "200.00"}],
            ["b", "USD", {"decimal": "100.00"}],
        ]
    )
    receipt = compare_reproductions(original, exchanged)
    assert receipt.status == "different"
    assert [c.component for c in receipt.components if not c.identical] == ["tables"]
    repeated = ReproductionRecord.model_validate_json(original.model_dump_json())
    assert compare_reproductions(original, repeated).status == "reproduced"
    assert "reviewer" not in receipt.model_dump()


@pytest.mark.parametrize("component", ["configuration", "splits", "labels", "decisions", "tables"])
def test_each_logical_component_is_compared(component):
    altered = record(**{component: {"changed": True}})
    receipt = compare_reproductions(record(), altered)
    assert receipt.status == "different"
    assert [c.component for c in receipt.components if not c.identical] == [component]
    raw = receipt.model_dump(mode="json")
    raw["status"] = "reproduced"
    with pytest.raises(ValidationError):
        ComparisonReceipt.model_validate_json(json.dumps(raw))


def test_exact_quantities_undefined_values_multiplicity_and_order_are_preserved():
    left = record(rows=[["a", "USD", {"decimal": "1.00"}], ["a", "USD", None]])
    for rows in (
        [["a", "USD", {"decimal": "1.0"}], ["a", "USD", None]],
        [["a", "EUR", {"decimal": "1.00"}], ["a", "USD", None]],
        [["a", "USD", {"decimal": "1.00"}], ["a", "USD", 0]],
        [["a", "USD", None], ["a", "USD", {"decimal": "1.00"}]],
        [["a", "USD", {"decimal": "1.00"}]],
    ):
        assert compare_reproductions(left, record(rows=rows)).status == "different"
    assert left.decisions.find("not_evaluable") >= 0
    with pytest.raises(TypeError):
        record(tables={"amount": Decimal("1.00")})
    with pytest.raises(TypeError):
        record(configuration={1: "untyped JSON key"})
    with pytest.raises(ValueError):
        record(tables={"amount": float("nan")})


def test_json_object_order_is_canonical_but_duplicate_members_rejected():
    assert record(configuration={"a": 1, "b": 2}) == record(configuration={"b": 2, "a": 1})
    raw = record().model_dump(mode="python")
    raw["configuration"] = '{"a":1,"a":1}'
    with pytest.raises(ValidationError):
        ReproductionRecord.model_validate(raw)


def test_regenerator_is_explicit_trusted_and_preserves_pending_labels(tmp_path):
    root, _, _ = packaged(tmp_path)
    calls = []

    def regenerate(captured):
        calls.append(captured)
        return record()

    assert read_bundle(root).record_path == "records/record.json"
    assert not calls
    receipt = reproduce_bundle(root, regenerator=regenerate)
    assert len(calls) == 1
    assert receipt.status == "reproduced"
    assert receipt.repeated.labels == record().labels
    assert json.loads(receipt.repeated.labels)[0]["status"] == "pending"


def test_regenerator_mutation_of_bundle_is_rejected(tmp_path):
    root, _, _ = packaged(tmp_path)

    def modify(captured):
        (root / "data/table.arrow").write_text("corrupted by explicit callback")
        return captured

    with pytest.raises(ArtifactIntegrityError):
        reproduce_bundle(root, regenerator=modify)


def test_record_budget_and_missing_record_prevent_regeneration(tmp_path):
    root, _, _ = packaged(tmp_path)
    with pytest.raises(ResourceLimitError):
        reproduce_bundle(root, regenerator=lambda x: x, limits=BundleLimits(max_record_bytes=10))
    files = {"artifact": tmp_path / "source/table.arrow"}
    opaque = tmp_path / "opaque"
    create_bundle(files, directory=opaque, bundle_id="opaque")
    with pytest.raises(ValueError, match="no declared"):
        reproduce_bundle(opaque, regenerator=lambda x: x)


def test_code_like_imported_json_is_never_executed(tmp_path):
    source = tmp_path / "untrusted.json"
    source.write_text('{"factory":"os.system","sql":"DROP TABLE x","python":"raise"}')
    root = tmp_path / "opaque"
    create_bundle({"code-like.json": source}, directory=root, bundle_id="opaque")
    assert read_bundle(root).files[0].path == "code-like.json"


def test_real_arrow_is_portable_with_exact_decimal_currency_nulls_and_duplicate_rows(tmp_path):
    import pyarrow as pa

    original = pa.table(
        {
            "entity": ["a", "a", "b", "c"],
            "currency": ["USD", "USD", "EUR", "EUR"],
            "amount": pa.array(
                [Decimal("100.00"), Decimal("100.00"), None, Decimal("200.00")],
                type=pa.decimal128(16, 2),
            ),
        }
    )
    path = tmp_path / "source.arrow"
    ref = write_table(original, path)
    root = tmp_path / "bundle"
    bundle = create_bundle(
        {"tables/output.arrow": path},
        directory=root,
        bundle_id="real-arrow",
        artifacts={"tables/output.arrow": ref},
    )
    moved = tmp_path / "relocated"
    root.rename(moved)
    path.unlink()
    rebound = bundle_artifact(bundle, moved, ref)
    observed = ef.read_table(rebound)
    assert observed.equals(original)
    assert observed.num_rows == 4
    assert observed.column("amount").to_pylist() == [
        Decimal("100.00"),
        Decimal("100.00"),
        None,
        Decimal("200.00"),
    ]


def test_manifest_swap_after_parsing_is_detected(tmp_path, monkeypatch):
    root, _, _ = packaged(tmp_path)
    reader = reproduction._bounded_json

    def swap(model, path, maximum):
        result = reader(model, path, maximum)
        if path == root / "bundle.json":
            raw = json.loads(path.read_text())
            raw["bundle_id"] = "another-synthetic-id"
            path.write_bytes(canonical_bytes(raw))
        return result

    monkeypatch.setattr(reproduction, "_bounded_json", swap)
    with pytest.raises(ArtifactIntegrityError, match="manifest changed"):
        read_bundle(root)


def test_competing_directory_reservation_is_preserved(tmp_path, monkeypatch):
    files, _ = source_files(tmp_path)
    target = tmp_path / "bundle"
    mkdir = type(tmp_path).mkdir

    def competitor(self, *args, **kwargs):
        if self == target:
            mkdir(self)
            (target / "owner.txt").write_text("other owner's evidence")
            raise FileExistsError(self)
        return mkdir(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "mkdir", competitor)
    with pytest.raises(FileExistsError):
        create_bundle(files, directory=target, bundle_id="racing-publication")
    assert (target / "owner.txt").read_text() == "other owner's evidence"
    assert not (target / "bundle.json").exists()


def test_failed_atomic_manifest_commit_leaves_no_readable_bundle(tmp_path, monkeypatch):
    files, _ = source_files(tmp_path)
    target = tmp_path / "bundle"

    def reject_commit(source, destination):
        assert target.is_dir()
        assert not (target / "bundle.json").exists()
        raise OSError("synthetic interrupted manifest publication")

    monkeypatch.setattr(reproduction.os, "link", reject_commit)
    with pytest.raises(OSError, match="interrupted"):
        create_bundle(files, directory=target, bundle_id="interrupted")
    assert not target.exists()
    assert not list(tmp_path.glob(".bundle-*"))
