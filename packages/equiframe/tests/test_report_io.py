"""Adversarial read-only report inspection and explicitly requested capture export."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pandas as pd
import pyarrow as pa
import pytest

import equiframe as ef
import equiframe._report_io as io
from equiframe.errors import ArtifactIntegrityError, ArtifactIOError, ResourceLimitError

BUDGET = 4 * 1024 * 1024


def inspect(result, root, **options):
    return io.inspect_evidence(
        result, root, **({"max_bytes": BUDGET, "max_records": 100, "max_examples": 20} | options)
    )


def export(result, root, destination, **options):
    return io.export_reproduction(
        result, root, destination, **({"max_bytes": BUDGET, "max_records": 100} | options)
    )


def path_of(ref):
    return Path(url2pathname(urlsplit(ref.uri).path))


def keyed(tmp_path, **options):
    # Two changed cells in one row, one added, one removed, one unchanged.
    left = pa.table({"id": [1, 2, 3], "x": [9, 8, 3], "y": [9, 8, 3]})
    right = pa.table({"id": [1, 2, 4], "x": [1, 8, 4], "y": [1, 8, 4]})
    return ef.diff(left, right, keys=["id"], work_dir=tmp_path, **options)


def persist(result):
    path_of(result.differences).with_name("comparison.json").write_text(result.model_dump_json())
    return result


def forged(result, differences):
    raw = b"".join(json.dumps(item).encode() + b"\n" for item in differences)
    path_of(result.differences).write_bytes(raw)
    ref = result.differences.model_copy(
        update={"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    )
    return persist(result.model_copy(update={"differences": ref, "examples": ()}))


def raw_forged(result, raw):
    path_of(result.differences).write_bytes(raw)
    ref = result.differences.model_copy(
        update={"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    )
    return persist(result.model_copy(update={"differences": ref, "examples": ()}))


def rows(result):
    return [json.loads(line) for line in path_of(result.differences).read_bytes().splitlines()]


def test_verified_keyed_counts_are_distinct_rows_and_examples_are_only_display(tmp_path):
    result = keyed(tmp_path, options=ef.ComparisonOptions(max_examples=1))
    found = inspect(result, tmp_path, max_examples=2)
    assert (found.added, found.removed, found.modified) == (1, 1, 1)
    assert (found.candidate_excess, found.reference_excess) == (1, 1)
    assert found.records == 4 and found.violations == 0
    assert found.code_counts == (("cell_value", 2), ("row_multiplicity", 2))
    assert len(found.examples) == 2
    assert inspect(result, path_of(result.differences).parent, max_examples=0).examples == ()


def test_bag_counts_keep_modified_and_named_row_counts_unknown(tmp_path):
    result = ef.diff(pa.table({"x": [1, 1, 2]}), pa.table({"x": [1, 3]}), work_dir=tmp_path)
    found = inspect(result, tmp_path)
    assert result.strategy == "multiset"
    assert found.added is found.removed is found.modified is None
    assert (found.candidate_excess, found.reference_excess) == (2, 1)
    assert found.records == 3


def test_matching_keeps_occurrence_counts_without_modified_inference(tmp_path):
    from test_comparison import column, contract, run

    policy = ef.NumericPolicy(
        comparison="approximate",
        unit="count",
        tolerance=ef.Tolerance(absolute="0.1", unit="count", justification="test"),
    )
    declaration = contract((column("x", ef.FloatType(bits=64), numeric_policy=policy),))
    result = run(tmp_path, pa.table({"x": [1.0, 2.0]}), pa.table({"x": [1.05, 3.0]}), declaration)
    found = inspect(result, tmp_path)
    assert result.strategy == "matching"
    assert found.modified is None and found.added is None and found.removed is None
    assert (found.candidate_excess, found.reference_excess) == (1, 1)


def test_sequence_counts_modified_position_once_and_unmatched_tail(tmp_path):
    from test_comparison import column, contract, run

    order = ef.SignificantOrder(
        by=(ef.SortSpec(column="id", direction="ascending", nulls="first"),), ties="preserve"
    )
    declaration = contract((column("id"), column("x"), column("y")), order=order)
    left = pa.table({"id": [1, 2], "x": [9, 3], "y": [9, 3]})
    right = pa.table({"id": [1], "x": [1], "y": [1]})
    result = run(tmp_path, left, right, declaration)
    found = inspect(result, tmp_path)
    assert result.strategy == "sequence"
    assert (found.added, found.removed, found.modified) == (1, 0, 1)


def test_equivalent_empty_evidence(tmp_path):
    result = ef.diff(pa.table({"id": [1]}), pa.table({"id": [1]}), keys=["id"], work_dir=tmp_path)
    found = inspect(result, tmp_path)
    assert found.records == 0 and found.modified == found.added == found.removed == 0


def test_pending_failure_preserves_unknown_alignment(tmp_path):
    result = keyed(tmp_path, options=ef.ComparisonOptions(max_rows=1))
    found = inspect(result, tmp_path)
    assert not result.complete and result.strategy == "pending"
    assert found.modified is found.added is found.removed is None


def test_partial_ingestion_violation_can_point_at_unfinished_row(tmp_path):
    from test_comparison import column, contract, run

    declaration = contract((column(nullable=False),))
    # Emission happens before the row increment, and its work-budget check interrupts.
    result = run(
        tmp_path,
        pa.table({"value": pa.array([None], pa.int64())}),
        pa.table({"value": [1]}),
        declaration,
        options=ef.ComparisonOptions(max_work=1),
    )
    assert not result.complete
    inspect(result, tmp_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d | {"position": 99},
        lambda d: d | {"other_position": 99},
        lambda d: d | {"column": "not-a-column"},
        lambda d: d | {"left_count": 3},
        lambda d: d | {"left": []},
        lambda d: d | {"left": d["left"] * 2},
        lambda d: d | {"key": []},
        lambda d: d | {"side": "left"},
        lambda d: d | {"category": "schema"},
        lambda d: d | {"code": "invented"},
        lambda d: d | {"left_count": True},
        lambda d: d | {"position": "0"},
        lambda d: d | {"extra": 1},
    ],
)
def test_reject_typed_or_dimension_forgery_even_with_rehashed_bytes(tmp_path, mutate):
    result = keyed(tmp_path)
    original = rows(result)
    index = next(i for i, item in enumerate(original) if item["code"] == "cell_value")
    original[index] = mutate(original[index])
    with pytest.raises(ArtifactIntegrityError):
        inspect(forged(result, original), tmp_path)


def test_duplicate_cell_and_inconsistent_alignment_are_rejected(tmp_path):
    result = keyed(tmp_path)
    original = rows(result)
    cell_indices = [i for i, item in enumerate(original) if item["code"] == "cell_value"]
    original[cell_indices[1]] = original[cell_indices[0]]
    with pytest.raises(ArtifactIntegrityError, match="duplicate aligned"):
        inspect(forged(result, original), tmp_path)
    original[cell_indices[1]] = original[cell_indices[1]] | {"column": "y", "other_position": 1}
    with pytest.raises(ArtifactIntegrityError, match="one-to-one"):
        inspect(forged(result, original), tmp_path)


def test_manifest_prefix_must_match_evidence_beyond_requested_display(tmp_path):
    result = keyed(tmp_path)
    changed = result.examples[0].model_copy(update={"message": "a forged witness"})
    result = persist(result.model_copy(update={"examples": (changed, *result.examples[1:])}))
    with pytest.raises(ArtifactIntegrityError, match="prefix"):
        inspect(result, tmp_path, max_examples=0)


def test_manifest_must_equal_supplied_result(tmp_path):
    result = keyed(tmp_path)
    persist(result.model_copy(update={"work_units": result.work_units + 1}))
    with pytest.raises(ArtifactIntegrityError, match="differs"):
        inspect(result, tmp_path)


@pytest.mark.parametrize("file", ["comparison.json", "differences.jsonl"])
def test_missing_evidence_is_not_a_success(tmp_path, file):
    result = keyed(tmp_path)
    path_of(result.differences).with_name(file).unlink()
    with pytest.raises(ArtifactIOError):
        inspect(result, tmp_path)


@pytest.mark.parametrize("file", ["comparison.json", "differences.jsonl"])
def test_duplicate_json_members_rejected(tmp_path, file):
    result = keyed(tmp_path)
    path = path_of(result.differences).with_name(file)
    raw = path.read_bytes().replace(
        b'"schema_version":', b'"schema_version":"1.0","schema_version":', 1
    )
    if file.endswith("jsonl"):
        result = raw_forged(result, raw)
    else:
        path.write_bytes(raw)
    with pytest.raises(ArtifactIntegrityError, match="duplicate"):
        inspect(result, tmp_path)


@pytest.mark.parametrize(
    "raw", [b'{"x": NaN}\n', b"{}\n", b"\xff", b"[]\n", b"\n", b"{}{}\n", b'{"x": Infinity}\n']
)
def test_nonstandard_or_invalid_json_lines_rejected(tmp_path, raw):
    result = raw_forged(keyed(tmp_path), raw)
    with pytest.raises(ArtifactIntegrityError):
        inspect(result, tmp_path)


def test_corrupt_hash_even_when_file_size_is_unchanged(tmp_path):
    result = keyed(tmp_path)
    path = path_of(result.differences)
    raw = path.read_bytes().replace(b"aligned values differ", b"changed values differ")
    assert len(raw) == result.differences.size_bytes
    path.write_bytes(raw)
    with pytest.raises(ArtifactIntegrityError):
        inspect(result, tmp_path)


def test_rehashed_record_count_and_violations_must_match_manifest(tmp_path):
    result = keyed(tmp_path)
    with pytest.raises(ArtifactIntegrityError, match="record count"):
        inspect(forged(result, rows(result)[:-1]), tmp_path)
    result = keyed(tmp_path)
    counts = result.counts.model_copy(update={"contract_violations": 1})
    with pytest.raises(ArtifactIntegrityError, match="violation count"):
        inspect(persist(result.model_copy(update={"counts": counts})), tmp_path)


@pytest.mark.parametrize("kwargs", [{"max_bytes": 1}, {"max_records": 1}])
def test_inspection_budgets_are_hard_failures(tmp_path, kwargs):
    with pytest.raises(ResourceLimitError):
        inspect(keyed(tmp_path), tmp_path, **kwargs)


@pytest.mark.parametrize("kwargs", [{"max_bytes": True}, {"max_records": 0}, {"max_examples": -1}])
def test_invalid_inspection_limits(tmp_path, kwargs):
    with pytest.raises(ValueError):
        inspect(keyed(tmp_path), tmp_path, **kwargs)


def test_one_oversized_line_and_manifest_are_independently_bounded(tmp_path, monkeypatch):
    result = keyed(tmp_path)
    monkeypatch.setattr(io, "_MAX_LINE_BYTES", 12)
    with pytest.raises(ResourceLimitError, match="line"):
        inspect(result, tmp_path)
    monkeypatch.setattr(io, "_MAX_DOCUMENT_BYTES", 12)
    with pytest.raises(ResourceLimitError, match="manifest"):
        inspect(result, tmp_path)


@pytest.mark.parametrize(
    "uri",
    [
        "file://remote/differences.jsonl",
        "https://example.com/differences.jsonl",
        "file://localhost/differences.jsonl",
        "file:///tmp/../differences.jsonl",
        "file:///tmp/%2e%2e/differences.jsonl",
        "file:relative",
        "file:////remote/differences.jsonl",
    ],
)
def test_unsafe_difference_uris_rejected_without_following_them(tmp_path, uri):
    result = keyed(tmp_path)
    result = result.model_copy(
        update={"differences": result.differences.model_copy(update={"uri": uri})}
    )
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        inspect(result, tmp_path)


def test_paths_outside_root_and_nonconventional_locations_rejected(tmp_path):
    result = keyed(tmp_path / "runs")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    with pytest.raises(ArtifactIntegrityError, match="outside"):
        inspect(result, allowed)
    wrong = result.differences.model_copy(
        update={"uri": (tmp_path / "runs" / result.comparison_id / "other.jsonl").as_uri()}
    )
    with pytest.raises(ArtifactIntegrityError, match="conventional"):
        inspect(result.model_copy(update={"differences": wrong}), tmp_path)


@pytest.mark.parametrize("location", ["root", "ancestor", "manifest", "differences"])
def test_symlinks_rejected_in_root_ancestors_and_files(tmp_path, location):
    actual = tmp_path / "actual"
    result = keyed(actual)
    root = actual
    if location in ("root", "ancestor"):
        link = tmp_path / "alias"
        try:
            link.symlink_to(actual, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks unavailable")
        root = link if location == "root" else link / result.comparison_id
    else:
        path = path_of(result.differences)
        if location == "manifest":
            path = path.with_name("comparison.json")
        target = path.with_suffix(".saved")
        path.rename(target)
        try:
            path.symlink_to(target)
        except OSError:
            pytest.skip("symlinks unavailable")
    with pytest.raises(ArtifactIntegrityError, match=r"symlink|link"):
        inspect(result, root)


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junctions only")
@pytest.mark.parametrize("location", ["root", "ancestor"])
def test_windows_junctions_are_rejected_before_evidence_reads(tmp_path, location):
    actual = tmp_path / "actual"
    result = keyed(actual)
    link = tmp_path / "junction"
    quoted_link = str(link).replace("'", "''")
    quoted_target = str(actual).replace("'", "''")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"New-Item -ItemType Junction -Path '{quoted_link}' "
            f"-Target '{quoted_target}' | Out-Null",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    assert link.lstat().st_file_attributes & 0x400
    root = link if location == "root" else link / result.comparison_id
    with pytest.raises(io.EvidencePathError, match="reparse"):
        inspect(result, root)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unavailable")
def test_special_evidence_file_rejected_before_open(tmp_path):
    result = keyed(tmp_path)
    path = path_of(result.differences)
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(ArtifactIntegrityError, match="regular"):
        inspect(result, tmp_path)


def test_inspection_opens_no_snapshots_execution_paths_or_unrelated_files(tmp_path, monkeypatch):
    result = keyed(tmp_path)
    source = result.left
    assert source is not None
    for item in (result.left, result.right):
        path_of(item.data).unlink()
    (tmp_path / "unrelated-secret").write_text("never open me")
    actual = os.open
    opened = []

    def tracking(path, flags, *args, **kwargs):
        opened.append(str(path))
        return actual(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", tracking)
    inspect(result, tmp_path)
    assert all(Path(path).name in {"comparison.json", "differences.jsonl"} for path in opened)


def test_export_has_closed_portable_inventory_and_required_context(tmp_path):
    root = tmp_path / "runs"
    result = keyed(root)
    destination = tmp_path / "reproduction"
    manifest = export(result, root, destination)
    assert manifest["complete"] and manifest["source_state"] == "different"
    files = manifest["files"]
    assert {file["path"] for file in files} | {"reproduction.json"} == {
        path.name for path in destination.iterdir()
    }
    for file in files:
        raw = (destination / file["path"]).read_bytes()
        assert len(raw) == file["size_bytes"] and hashlib.sha256(raw).hexdigest() == file["sha256"]
    context = json.loads((destination / "context.json").read_bytes())
    assert context["spec"] == result.spec.model_dump(mode="json")
    assert context["options"] == result.options.model_dump(mode="json")
    assert context["diff_declaration"]["reference"] == result.reference
    assert context["left"]["table"]["row_count"] == 3
    assert "notes" not in context["left"]["table"]
    assert str(root) not in (destination / "context.json").read_text()
    assert "uri" not in context["left"]["data"]
    if os.name == "posix":
        assert destination.stat().st_mode & 0o777 == 0o700
        assert all(path.stat().st_mode & 0o777 == 0o600 for path in destination.iterdir())
    # Independently perform the explicitly described captured-output comparison.
    rerun = ef.compare(
        destination / context["left"]["data"]["path"],
        destination / context["right"]["data"]["path"],
        contract=result.spec.contract,
        policy=result.spec.policy,
        reference=result.reference,
        options=result.options,
        work_dir=tmp_path / "rechecked",
    )
    assert rerun.state == result.state and rerun.counts == result.counts


def test_export_preserves_meaningful_captured_index(tmp_path):
    left = pd.DataFrame({"id": [1], "x": [2]}, index=pd.Index(["row-A"], name="label"))
    right = pd.DataFrame({"id": [1], "x": [3]}, index=pd.Index(["row-B"], name="label"))
    policy = ef.ComparisonPolicy(index="ignore", justification="explicit test policy")
    root = tmp_path / "runs"
    result = ef.diff(left, right, keys=["id"], policy=policy, work_dir=root)
    destination = tmp_path / "reproduction"
    export(result, root, destination)
    context = json.loads((destination / "context.json").read_bytes())
    assert context["left"]["index"]["path"] == "left-index.arrow"
    assert context["left"]["table"]["index_columns"]


def test_export_rejects_incomplete_comparison(tmp_path):
    result = keyed(tmp_path / "runs", options=ef.ComparisonOptions(max_rows=1))
    with pytest.raises(ArtifactIntegrityError, match="complete comparison"):
        export(result, tmp_path / "runs", tmp_path / "reproduction")
    assert not (tmp_path / "reproduction").exists()


def test_export_is_exclusive_and_does_not_modify_existing_directory(tmp_path):
    result = keyed(tmp_path / "runs")
    destination = tmp_path / "reproduction"
    destination.mkdir()
    marker = destination / "keep"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        export(result, tmp_path / "runs", destination)
    assert marker.read_text() == "keep"


@pytest.mark.parametrize("failure", ["hash", "missing", "external", "symlink", "budget", "write"])
def test_export_failure_never_leaves_success_manifest(tmp_path, monkeypatch, failure):
    root = tmp_path / "runs"
    result = keyed(root)
    destination = tmp_path / "reproduction"
    source = result.right
    assert source is not None
    path = path_of(source.data)
    options = {}
    if failure == "hash":
        raw = path.read_bytes()
        path.write_bytes(b"x" + raw[1:])
    elif failure == "missing":
        path.unlink()
    elif failure == "external":
        external = tmp_path / "outside.arrow"
        path.rename(external)
        result = persist(
            result.model_copy(
                update={
                    "right": source.model_copy(
                        update={"data": source.data.model_copy(update={"uri": external.as_uri()})}
                    )
                }
            )
        )
    elif failure == "symlink":
        external = tmp_path / "outside.arrow"
        path.rename(external)
        try:
            path.symlink_to(external)
        except OSError:
            pytest.skip("symlinks unavailable")
    elif failure == "budget":
        options["max_bytes"] = (
            path_of(result.differences).with_name("comparison.json").stat().st_size
            + result.differences.size_bytes
        )
    else:

        def broken(*args, **kwargs):
            raise OSError("injected write failure")

        monkeypatch.setattr(io, "_write_private", broken)
    with pytest.raises((ArtifactIntegrityError, ArtifactIOError, ResourceLimitError, OSError)):
        export(result, root, destination, **options)
    assert not destination.exists()


def test_export_refuses_forged_provenance_and_duplicate_json(tmp_path):
    root = tmp_path / "runs"
    result = keyed(root)
    receipt = path_of(result.differences).with_name("diff-contract.json")
    raw = receipt.read_bytes()
    receipt.write_bytes(raw.replace(result.comparison_id.encode(), b"wrong-comparison"))
    with pytest.raises(ArtifactIntegrityError, match="declaration"):
        export(result, root, tmp_path / "reproduction")
    receipt.write_bytes(
        raw.replace(b'"schema_version":', b'"schema_version":"1.0","schema_version":', 1)
    )
    with pytest.raises(ArtifactIntegrityError, match="duplicate"):
        export(result, root, tmp_path / "reproduction")


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "additional",
        "column_order",
        "type",
        "null",
        "nan",
        "duplicate_key",
        "incomplete_key",
        "distinct",
        "order",
        "order_tie",
    ],
)
def test_real_violation_codes_and_dimensions_are_accepted(tmp_path, case):
    from test_comparison import column, contract, key, run

    declaration = contract((column("value"),))
    left = pa.table({"value": [1, 2]})
    right = left
    if case == "missing":
        left = pa.table({"other": [1, 2]})
    elif case == "additional":
        left = pa.table({"value": [1, 2], "other": [1, 2]})
    elif case == "column_order":
        declaration = contract((column("value"), column("other")))
        left = pa.table({"other": [1, 2], "value": [1, 2]})
        right = pa.table({"value": [1, 2], "other": [1, 2]})
    elif case == "type":
        left = pa.table({"value": ["a", "b"]})
    elif case == "null":
        declaration = contract((column("value", nullable=False),))
        left = pa.table({"value": pa.array([None, 2], pa.int64())})
    elif case == "nan":
        declaration = contract(
            (column("value", ef.FloatType(bits=64), nan_policy=ef.NaNPolicy(handling="forbid")),)
        )
        left = pa.table({"value": [float("nan"), 2.0]})
        right = pa.table({"value": [1.0, 2.0]})
    elif case in ("duplicate_key", "incomplete_key"):
        declaration = contract((column("value"),), keys=(key(("value",)),))
        left = pa.table(
            {"value": pa.array([1, 1] if case == "duplicate_key" else [None, 1], pa.int64())}
        )
    elif case == "distinct":
        declaration = contract((column("value"),), multiplicity="distinct")
        left = pa.table({"value": [1, 1]})
    else:
        declaration = contract(
            (column("value"),),
            order=ef.SignificantOrder(
                by=(ef.SortSpec(column="value", direction="ascending", nulls="first"),),
                ties="reject",
            ),
        )
        left = pa.table({"value": [2, 1] if case == "order" else [1, 1]})
    result = run(tmp_path, left, right, declaration)
    assert result.counts.contract_violations > 0
    found = inspect(result, tmp_path)
    assert found.violations == result.counts.contract_violations


def test_complete_invalid_expected_is_exported_without_equivalence_claim(tmp_path):
    from test_comparison import column, contract, run

    declaration = contract((column("value", nullable=False),))
    root = tmp_path / "runs"
    result = run(
        root,
        pa.table({"value": [1]}),
        pa.table({"value": pa.array([None], pa.int64())}),
        declaration,
        reference="expected",
    )
    assert result.complete and result.state == "not_evaluable"
    manifest = export(result, root, tmp_path / "reproduction")
    assert manifest["source_state"] == "not_evaluable"
    assert manifest["source_complete"]


def test_execution_paths_are_never_opened_and_export_is_explicitly_unsupported(tmp_path):
    from test_comparison_execution import DEMO, POLICY, execute

    case = DEMO["cases"]()[0]
    execution = execute(case, "pandas", tmp_path / "executions")
    result = ef.compare(
        execution,
        ef.ArrowInput(DEMO["expected_table"](case)),
        contract=case.contract,
        policy=POLICY,
        work_dir=tmp_path / "comparisons",
    )
    assert result.complete
    for captured in (*execution.inputs, execution.output):
        path_of(captured.data).unlink(missing_ok=True)
        if captured.index is not None:
            path_of(captured.index).unlink(missing_ok=True)
    # Inspection still succeeds even though the historical execution is gone.
    inspect(result, tmp_path / "comparisons")
    with pytest.raises(ArtifactIntegrityError, match="execution-backed"):
        export(result, tmp_path / "comparisons", tmp_path / "reproduction")


def test_snapshot_outside_comparison_directory_is_not_exported_even_under_root(tmp_path):
    root = tmp_path / "runs"
    result = keyed(root)
    source = result.right
    unrelated = root / "unrelated.arrow"
    path_of(source.data).rename(unrelated)
    result = persist(
        result.model_copy(
            update={
                "right": source.model_copy(
                    update={"data": source.data.model_copy(update={"uri": unrelated.as_uri()})}
                )
            }
        )
    )
    with pytest.raises(ArtifactIntegrityError, match="outside"):
        export(result, root, tmp_path / "reproduction")
    assert unrelated.exists()
    assert not (tmp_path / "reproduction").exists()
