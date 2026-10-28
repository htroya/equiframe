"""Disk accounting keeps every checkpoint and full-comparison guarantee."""

import errno
import importlib
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.errors import ExecutionCancelled, ExecutionTimeout, ResourceLimitError

comparison = importlib.import_module("equiframe.comparison")


def work_for(directory, **options):
    work = object.__new__(comparison._Work)
    work.work = work.peak_disk = 0
    work.directory = directory
    work.options = ef.ComparisonOptions(**options)
    work.cancellation = ef.CancellationToken()
    work.start = time.perf_counter()
    work.sql_error = None
    return work


def test_disk_scan_observes_every_checkpoint_and_file_growth(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.write_bytes(b"x" * 17)
    (tmp_path / "empty").touch()
    (tmp_path / "directory").mkdir()
    original = os.scandir
    calls = []

    def tracked(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(comparison.os, "scandir", tracked)
    work = work_for(tmp_path, max_disk_bytes=25)
    work.check(3)
    assert (work.work, work.peak_disk) == (3, 17)
    data.write_bytes(b"x" * 25)
    work.check(5)
    assert (work.work, work.peak_disk) == (8, 25)
    data.write_bytes(b"x" * 26)
    with pytest.raises(ResourceLimitError, match="max_disk_bytes"):
        work.check(7)
    assert (work.work, work.peak_disk) == (15, 26)
    data.write_bytes(b"x")
    work.check()
    assert work.peak_disk == 26
    assert calls == [tmp_path] * 4


def test_disk_scan_matches_path_regular_symlink_and_broken_behavior(tmp_path):
    (tmp_path / "data").write_bytes(b"x" * 37)
    (tmp_path / "directory").mkdir()
    for name, target in (
        ("file-link", "data"),
        ("directory-link", "directory"),
        ("broken-link", "absent"),
        ("loop-link", "loop-link"),
    ):
        try:
            (tmp_path / name).symlink_to(
                tmp_path / target, target_is_directory=target == "directory"
            )
        except (OSError, NotImplementedError) as error:
            pytest.skip(f"symlink creation unavailable: {error}")
    expected = sum(p.stat().st_size for p in tmp_path.iterdir() if p.is_file())
    work = work_for(tmp_path)
    work.check()
    assert expected == work.peak_disk == 74


@pytest.mark.parametrize("condition", ["cancelled", "timeout", "work"])
def test_non_disk_guards_run_before_scanning(tmp_path, monkeypatch, condition):
    work = work_for(tmp_path, timeout_seconds=1, max_work=5)
    if condition == "cancelled":
        work.cancellation.cancel()
        expected = ExecutionCancelled
    elif condition == "timeout":
        work.start -= 2
        expected = ExecutionTimeout
    else:
        expected = ResourceLimitError

    def forbidden_scan(path):
        pytest.fail("must not scan after an earlier checkpoint guard fails")

    monkeypatch.setattr(comparison.os, "scandir", forbidden_scan)
    with pytest.raises(expected):
        work.check(6)
    assert work.work == 6


def test_progress_handler_preserves_cost_and_resource_failure(tmp_path):
    (tmp_path / "data").write_bytes(b"xx")
    work = work_for(tmp_path, max_disk_bytes=1)
    assert work._progress() == 1
    assert work.work == 1000
    assert isinstance(work.sql_error, ResourceLimitError)
    assert str(work.sql_error) == "max_disk_bytes"


@pytest.mark.parametrize("stage", ["open", "type", "size"])
def test_scan_failure_is_not_silently_ignored_and_iterator_closes(tmp_path, monkeypatch, stage):
    failure = PermissionError(errno.EACCES, "denied")
    closed = []

    def denied():
        raise failure

    class Entries:
        def __enter__(self):
            if stage == "open":
                raise failure
            return iter(
                [
                    SimpleNamespace(
                        path=str(tmp_path / "data"),
                        is_file=denied if stage == "type" else lambda: True,
                        stat=denied,
                    )
                ]
            )

        def __exit__(self, *exc):
            closed.append(True)

    monkeypatch.setattr(comparison.os, "scandir", lambda path: Entries())
    if stage == "type":
        monkeypatch.setattr(Path, "is_file", lambda path: denied())
    work = work_for(tmp_path)
    with pytest.raises(PermissionError) as caught:
        work.check()
    assert caught.value is failure
    assert work.work == 1 and work.peak_disk == 0
    assert closed == ([] if stage == "open" else [True])


def comparison_contract(*, keyed=False):
    schema = ef.TableSchema(
        columns=(
            ef.ColumnSpec(
                name="id",
                logical_type=ef.IntegerType(bits=64, signed=True),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
            ),
            ef.ColumnSpec(
                name="label",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
        ),
        keys=(
            ef.KeySpec(
                name="primary",
                columns=("id",),
                unique=True,
                incomplete="reject",
                scope=ef.TableKeyScope(),
            ),
        )
        if keyed
        else (),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="resource.scan",
        revision=1,
        family="duplicates_order",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )


@pytest.mark.parametrize("keyed", [False, True])
@pytest.mark.parametrize("different", [False, True])
def test_keyed_and_multiset_last_batch_complete(tmp_path, keyed, different):
    ids = list(range(13))
    labels = [f"item-{i}" for i in ids]
    left = pa.table({"id": ids, "label": labels})
    right_labels = labels[:]
    if different:
        right_labels[-1] = "changed-at-last-row"
    right = pa.table({"id": ids, "label": right_labels})
    result = ef.compare(
        ef.ArrowInput(left),
        ef.ArrowInput(right),
        contract=comparison_contract(keyed=keyed),
        work_dir=tmp_path,
        options=ef.ComparisonOptions(batch_rows=4, partitions=1, max_examples=1),
    )
    assert result.state == ("different" if different else "equivalent")
    assert result.complete and result.counts.final
    assert result.strategy == ("key" if keyed else "multiset")
    assert result.counts.left_rows == result.counts.right_rows == 13
    assert result.counts.matched_rows == (12 if different else 13)
    assert result.counts.contract_violations == 0
    differences = list(ef.iter_differences(result.differences))
    assert len(differences) == ((1 if keyed else 2) if different else 0)
    if different:
        assert {d.code for d in differences} == ({"cell_value"} if keyed else {"row_multiplicity"})
        assert any(d.position == 12 or d.other_position == 12 for d in differences)
    directory = tmp_path / result.comparison_id
    assert ef.read_comparison(directory / "comparison.json") == result
    assert not list(directory.glob("work.sqlite*"))


@pytest.mark.parametrize("different", [False, True])
def test_skewed_multiplicity_survives_one_partition(tmp_path, different):
    left = pa.table({"id": [1] * 24 + [2], "label": ["repeated"] * 24 + ["tail"]})
    right = pa.table(
        {
            "id": [1] * (23 if different else 24) + [2],
            "label": ["repeated"] * (23 if different else 24) + ["tail"],
        }
    )
    result = ef.compare(
        ef.ArrowInput(left),
        ef.ArrowInput(right),
        contract=comparison_contract(),
        work_dir=tmp_path,
        options=ef.ComparisonOptions(batch_rows=4, partitions=1),
    )
    assert result.state == ("different" if different else "equivalent")
    assert result.complete and result.counts.final
    assert result.counts.matched_rows == (24 if different else 25)
    differences = list(ef.iter_differences(result.differences))
    if different:
        assert len(differences) == 1
        assert differences[0].code == "row_multiplicity"
        assert (differences[0].left_count, differences[0].right_count) == (24, 23)
    else:
        assert not differences
