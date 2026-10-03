"""Publication failure preserves the previous version and never duplicates retry data."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_migration_backends import column, contract
from test_workflow import reference

from equiframe.contracts import IntegerType
from equiframe.destinations import LoadReceipt, ParquetDestination
from equiframe.errors import ArtifactIntegrityError
from equiframe.local import local_path
from equiframe.verify import verify


def approved(tmp_path, values=(1, 2)):
    ref = reference(pa.table({"n": list(values)}), tmp_path / "candidate.arrow")
    schema = contract(
        {"input": [column("n", IntegerType(bits=64, signed=True))]},
        [column("n", IntegerType(bits=64, signed=True))],
    )
    report = verify({"candidate": ref}, contract=schema, expected=ref, work_dir=tmp_path)
    assert report.publishable
    return ref, report


def test_idempotent_load_versions_create_replace_and_row_counts(tmp_path):
    ref, report = approved(tmp_path)
    destination = ParquetDestination(tmp_path / "published")
    receipt = destination.publish({"table": ref}, run_id="one", verifications={"table": report})
    repeated = destination.publish({"table": ref}, run_id="one", verifications={"table": report})
    assert repeated == receipt == destination.current()
    assert len(list((destination.root / "versions").iterdir())) == 1
    assert pq.read_table(destination.root / "versions" / "one" / "table.parquet").num_rows == 2
    with pytest.raises(FileExistsError):
        destination.publish({"table": ref}, run_id="two", verifications={"table": report})
    replaced = destination.publish(
        {"table": ref}, run_id="two", policy="replace", verifications={"table": report}
    )
    assert replaced.previous_run == "one"
    assert (destination.root / "versions" / "one" / "load.json").exists()
    with pytest.raises(ValueError, match="newer"):
        destination.publish({"table": ref}, run_id="one", verifications={"table": report})


def test_failure_halfway_loading_multiple_tables_keeps_previous(tmp_path, monkeypatch):
    ref, report = approved(tmp_path)
    destination = ParquetDestination(tmp_path / "published")
    previous = destination.publish({"a": ref}, run_id="old", verifications={"a": report})
    actual = pq.write_table
    writes = 0

    def fail_second(table, where, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("injected full disk")
        actual(table, where, **kwargs)

    monkeypatch.setattr(pq, "write_table", fail_second)
    with pytest.raises(OSError, match="full disk"):
        destination.publish(
            {"a": ref, "b": ref},
            run_id="new",
            policy="replace",
            verifications={"a": report, "b": report},
        )
    assert destination.current() == previous
    assert not (destination.root / "versions" / "new").exists()
    assert not list((destination.root / ".staging").iterdir())
    assert not (destination.root / ".publication.lock").exists()


def test_gate_must_bind_same_output_and_closed_evidence(tmp_path):
    ref, report = approved(tmp_path)
    other = reference(pa.table({"n": [2, 1]}), tmp_path / "other.arrow")
    destination = ParquetDestination(tmp_path / "published")
    with pytest.raises(ValueError, match="bind"):
        destination.publish({"table": other}, run_id="one", verifications={"table": report})
    captured = local_path(report.outputs[0][1])
    captured.write_bytes(b"corrupted")
    with pytest.raises(ArtifactIntegrityError):
        destination.publish({"table": ref}, run_id="one", verifications={"table": report})
    assert destination.current() is None


def test_failed_expected_gate_blocks_publication(tmp_path):
    ref, report = approved(tmp_path)
    expected = reference(pa.table({"n": [9, 2]}), tmp_path / "expected.arrow")
    failed = verify(
        {"candidate": ref}, contract=report.contract, expected=expected, work_dir=tmp_path
    )
    destination = ParquetDestination(tmp_path / "published")
    with pytest.raises(ValueError, match="not approved"):
        destination.publish({"table": ref}, run_id="one", verifications={"table": failed})
    assert not destination.root.exists()


def test_pointer_write_failure_is_recoverable_without_losing_prior(tmp_path, monkeypatch):
    ref, report = approved(tmp_path)
    destination = ParquetDestination(tmp_path / "published")
    previous = destination.publish({"table": ref}, run_id="old", verifications={"table": report})
    switch = destination._switch

    def fail_pointer(directory, receipt):
        raise OSError("injected pointer failure")

    monkeypatch.setattr(destination, "_switch", fail_pointer)
    with pytest.raises(OSError, match="pointer failure"):
        destination.publish(
            {"table": ref}, run_id="new", policy="replace", verifications={"table": report}
        )
    assert destination.current() == previous
    assert (destination.root / "versions" / "new").exists()
    monkeypatch.setattr(destination, "_switch", switch)
    recovered = destination.publish(
        {"table": ref}, run_id="new", policy="replace", verifications={"table": report}
    )
    assert destination.current() == recovered
    assert len(list((destination.root / "versions").iterdir())) == 2


def test_case_colliding_table_names_are_rejected_before_destination_creation(tmp_path):
    ref, report = approved(tmp_path)
    destination = ParquetDestination(tmp_path / "published")
    with pytest.raises(ValueError, match="case-insensitive"):
        destination.publish(
            {"Table": ref, "table": ref},
            run_id="collision",
            verifications={"Table": report, "table": report},
        )
    assert not destination.root.exists()


def test_case_colliding_replace_preserves_prior_bytes_without_staging(tmp_path, monkeypatch):
    ref, report = approved(tmp_path)
    other = reference(pa.table({"n": [9, 2]}), tmp_path / "other.arrow")
    other_report = verify(
        {"candidate": other}, contract=report.contract, expected=other, work_dir=tmp_path
    )
    destination = ParquetDestination(tmp_path / "published")
    previous = destination.publish({"old": ref}, run_id="old", verifications={"old": report})
    pointer_bytes = (destination.root / "current.json").read_bytes()

    def unexpected_write(*args, **kwargs):
        pytest.fail("case collision must be rejected before any Parquet write")

    monkeypatch.setattr(pq, "write_table", unexpected_write)
    with pytest.raises(ValueError, match="case-insensitive"):
        destination.publish(
            {"Table": ref, "table": other},
            run_id="new",
            policy="replace",
            verifications={"Table": report, "table": other_report},
        )
    assert (destination.root / "current.json").read_bytes() == pointer_bytes
    assert destination.current() == previous
    assert not (destination.root / "versions" / "new").exists()
    assert not (destination.root / ".publication.lock").exists()
    assert not list((destination.root / ".staging").iterdir())


def test_receipt_rejects_case_colliding_physical_table_paths(tmp_path):
    ref, report = approved(tmp_path)
    receipt = ParquetDestination(tmp_path / "published").publish(
        {"table": ref}, run_id="one", verifications={"table": report}
    )
    original = receipt.tables[0]
    aliased = original.model_copy(
        update={
            "name": "TABLE",
            "parquet": original.parquet.model_copy(update={"path": "TABLE.parquet"}),
        }
    )
    with pytest.raises(ValueError, match="case-insensitive"):
        LoadReceipt.model_validate(receipt.model_copy(update={"tables": (original, aliased)}))
