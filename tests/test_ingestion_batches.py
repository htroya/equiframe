"""Bounded value batches preserve complete independent expectations and receipts."""

import hashlib
import json
import time
from pathlib import Path

import pyarrow as pa
import pytest
from conftest import document
from test_ingestion import fields
from test_migration_backends import column

import equiframe as ef
from equiframe.ingestion import FileInput, IngestionResult


def context(tmp_path, **options):
    return ef.RunContext(
        run_id="ingestion.run",
        execution_id="ingestion.execution",
        plan=ef.ExecutionPlan(
            contract=ef.validate_contract(document()),
            engine="duckdb",
            transformation_id="identity",
            options=ef.ExecutionOptions(**options),
        ),
        directory=tmp_path,
        store=ef.LocalArtifactStore(tmp_path / "artifacts"),
        cancellation=ef.CancellationToken(),
        deadline=None,
    )


def int_spec(format="csv", **kwargs):
    return ef.IngestionSpec(
        format=format,
        fields=(
            ef.FieldMapping(column=column("n", ef.IntegerType(bits=64, signed=True)), path=("n",)),
        ),
        **kwargs,
    )


def assert_no_published_table(root):
    assert not list(root.rglob("accepted.arrow"))
    assert not list(root.rglob("*.part"))
    assert not list(root.rglob("artifacts/*.arrow"))


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_default_path_does_not_read_entire_decoded_file_and_batches_values(
    tmp_path, monkeypatch, format
):
    path = tmp_path / ("source." + format)
    content = "n\n" + "7\n" * 5000 if format == "csv" else '{"n":7}\n' * 5000
    path.write_text(content, encoding="utf-8")
    original_read_text = Path.read_text
    original_open = Path.open
    original_array = pa.array
    sizes = []

    class BoundedReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __iter__(self):
            return iter(self.stream)

        def seek(self, *args):
            return self.stream.seek(*args)

        def read(self, size=-1):
            assert 0 < size <= 64 * 1024
            return self.stream.read(size)

    def bounded_open(self, mode="r", *args, **kwargs):
        stream = original_open(self, mode, *args, **kwargs)
        if self.name == "source.original" and mode == "r":
            return BoundedReader(stream)
        return stream

    def no_whole_read(self, *args, **kwargs):
        if self.name == "source.original":
            raise AssertionError("ingestion decoded the complete source")
        return original_read_text(self, *args, **kwargs)

    def bounded_array(values, *args, **kwargs):
        sizes.append(len(values))
        assert len(values) <= 4096
        return original_array(values, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", no_whole_read)
    monkeypatch.setattr(Path, "open", bounded_open)
    monkeypatch.setattr(pa, "array", bounded_array)
    result = ef.ingest_file(path, spec=int_spec(format), work_dir=tmp_path)
    assert result.state == "completed"
    assert result.accepted_records == 5000
    assert sizes == [4096, 904]
    assert ef.read_table(result.output)["n"].to_pylist() == [7] * 5000


@pytest.mark.parametrize("format", ["csv", "jsonl"])
@pytest.mark.parametrize("batch_rows", [1, 2, 3, 4096])
def test_variable_batches_keep_duplicates_null_unicode_and_receipt_positions(
    tmp_path, format, batch_rows
):
    from decimal import Decimal

    content = (
        "id,money\n001,1.10\n001,1.10\nCafé,NULL\n,0.00\nbad,0.001\nlast,-0.01\n"
        if format == "csv"
        else '{"id":"001","money":1.10}\n{"id":"001","money":1.10}\n'
        '{"id":"Café","money":null}\n{"id":"","money":0}\n'
        '{"id":"bad","money":0.001}\n{"id":"last","money":-0.01}\n'
    )
    raw = content.encode("utf-8")
    path = tmp_path / ("con espacios á." + format)
    path.write_bytes(raw)
    result = ef.ingest_file(
        path,
        spec=ef.IngestionSpec(format=format, fields=fields(), invalid_records="quarantine"),
        work_dir=tmp_path,
        batch_rows=batch_rows,
    )
    assert result.state == "quarantined"
    assert result.inspected_records == 6
    assert result.accepted_records == 5
    assert ef.read_table(result.output).to_pylist() == [
        {"id": "001", "money": Decimal("1.10")},
        {"id": "001", "money": Decimal("1.10")},
        {"id": "Café", "money": None},
        {"id": "", "money": Decimal("0.00")},
        {"id": "last", "money": Decimal("-0.01")},
    ]
    assert [r.record for r in result.conversions] == [0, 0, 1, 1, 2, 2, 3, 3, 5, 5]
    assert result.quarantined[0].record == 4
    assert result.quarantined[0].path == ("$[4]" if format == "csv" else "line:5$")
    assert result.conversions[-1].path == ("$[5]" if format == "csv" else "line:6$")
    directory = tmp_path / result.ingestion_id
    assert (directory / "source.original").read_bytes() == raw
    assert result.source.sha256 == hashlib.sha256(raw).hexdigest()
    assert result.source.size_bytes == len(raw)
    stored = IngestionResult.model_validate_json((directory / "ingestion.json").read_bytes())
    assert stored == result
    assert result.spec.schema_version == result.schema_version == "1.0"
    assert not list(directory.glob("*.part"))


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "cp1252"])
@pytest.mark.parametrize("delimiter", [";", "\t", "|"])
def test_csv_incremental_encoding_separator_and_quoted_newline(tmp_path, encoding, delimiter):
    path = tmp_path / "source.csv"
    path.write_bytes(f'id{delimiter}money\r\n"Café\r\n001"{delimiter}1.10\r\n'.encode(encoding))
    result = ef.ingest_file(
        path,
        spec=ef.IngestionSpec(
            format="csv", fields=fields(), delimiter=delimiter, encoding=encoding
        ),
        work_dir=tmp_path,
        batch_rows=1,
    )
    assert result.state == "completed"
    # Historical read_text universal-newline behavior is retained even in quoted cells.
    assert ef.read_table(result.output)["id"].to_pylist() == ["Café\n001"]
    assert result.conversions[0].path == "$[0]"
    assert (tmp_path / result.ingestion_id / "source.original").read_bytes() == path.read_bytes()


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_late_invalid_encoding_preserves_bytes_and_rejects_before_acceptance(tmp_path, format):
    path = tmp_path / ("source." + format)
    prefix = b"n\n" + b"7\n" * 40000 if format == "csv" else b'{"n":7}\n' * 10000
    path.write_bytes(prefix + b"\xff")
    result = ef.ingest_file(path, spec=int_spec(format), work_dir=tmp_path, batch_rows=1)
    assert result.state == "rejected"
    assert result.output is None
    assert result.accepted_records == 0
    assert result.inspected_records == 1
    assert result.quarantined[0].code.startswith("UnicodeDecodeError:")
    assert (tmp_path / result.ingestion_id / "source.original").read_bytes() == prefix + b"\xff"
    assert_no_published_table(tmp_path)


@pytest.mark.parametrize(
    "format,content", [("csv", 'n\n1\n"unterminated'), ("jsonl", '{"n":1}\n{bad}')]
)
def test_parse_error_after_flushed_batch_cannot_publish_partial(tmp_path, format, content):
    path = tmp_path / "source"
    path.write_text(content, encoding="utf-8")
    result = ef.ingest_file(path, spec=int_spec(format), work_dir=tmp_path, batch_rows=1)
    assert result.state == "rejected"
    assert result.accepted_records == 1
    assert result.inspected_records == 2
    assert result.output is None
    assert_no_published_table(tmp_path)


@pytest.mark.parametrize("batch_rows", [1, 2, 99])
def test_nested_jsonl_preserves_root_ancestor_and_atomic_document_expansion(tmp_path, batch_rows):
    path = tmp_path / "source.jsonl"
    path.write_text(
        '{"parent":"P","items":[{"n":2},{"n":3}]}\n{"parent":"Q","items":[{"n":4},{"n":5}]}\n',
        encoding="utf-8",
    )
    spec = ef.IngestionSpec(
        format="jsonl",
        records_path=("items", "*"),
        fields=(
            ef.FieldMapping(column=column("p", ef.StringType()), path=("parent",), scope="root"),
            ef.FieldMapping(
                column=column("a", ef.StringType()),
                path=("parent",),
                scope="ancestor",
                ancestor_levels=2,
            ),
            *int_spec().fields,
        ),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=batch_rows)
    assert ef.read_table(result.output).to_pylist() == [
        {"p": "P", "a": "P", "n": 2},
        {"p": "P", "a": "P", "n": 3},
        {"p": "Q", "a": "Q", "n": 4},
        {"p": "Q", "a": "Q", "n": 5},
    ]
    assert result.conversions[-1].path == "line:2$.items[1]"
    path.write_text('{"items":[{"v":{"n":1}},{"missing":true}]}\n', encoding="utf-8")
    result = ef.ingest_file(
        path,
        spec=int_spec("jsonl", records_path=("items", "*", "v"), invalid_records="quarantine"),
        work_dir=tmp_path,
        batch_rows=batch_rows,
    )
    assert result.state == "quarantined"
    assert result.accepted_records == 0
    assert result.inspected_records == 1
    assert result.quarantined[0].code == "records_path field is absent"


@pytest.mark.parametrize(
    "format,content,kwargs,rows",
    [
        ("csv", "n\n", {}, []),
        ("csv", "", {"header": False, "fieldnames": ("n",)}, []),
        ("csv", "1\n2\n", {"header": False, "fieldnames": ("n",)}, [1, 2]),
        ("jsonl", "", {}, []),
        ("json", "[]", {"records_path": ("*",)}, []),
    ],
)
def test_empty_sources_and_header_false(tmp_path, format, content, kwargs, rows):
    path = tmp_path / "source"
    path.write_text(content, encoding="utf-8")
    result = ef.ingest_file(path, spec=int_spec(format, **kwargs), work_dir=tmp_path, batch_rows=1)
    assert result.state == "completed"
    assert ef.read_table(result.output)["n"].to_pylist() == rows


@pytest.mark.parametrize("batch_rows", [1, 2, 4096])
@pytest.mark.parametrize("option,value", [("max_input_rows", 4), ("max_transport_bytes", 39)])
def test_context_budgets_are_cumulative_across_batches(tmp_path, batch_rows, option, value):
    path = tmp_path / "source.csv"
    path.write_text("n\n1\n2\n3\n4\n5\n", encoding="utf-8")
    with pytest.raises(ef.ResourceLimitError):
        ef.ingest_file(
            path,
            spec=int_spec(),
            work_dir=tmp_path,
            context=context(tmp_path, **{option: value}),
            batch_rows=batch_rows,
        )
    assert_no_published_table(tmp_path)
    assert not list(tmp_path.rglob("ingestion.json"))
    result = ef.ingest_file(
        path,
        spec=int_spec(),
        work_dir=tmp_path,
        context=context(tmp_path, max_input_rows=5, max_transport_bytes=40),
        batch_rows=batch_rows,
    )
    assert result.state == "completed"
    assert result.accepted_records == 5


@pytest.mark.parametrize(
    "format,content", [("csv", "n\n1\n2\n3\n"), ("jsonl", '{"n":1}\n{"n":2}\n{"n":3}\n')]
)
@pytest.mark.parametrize("limit", ["max_records", "max_source_bytes"])
def test_ingestion_source_and_record_budgets_boundary(tmp_path, format, content, limit):
    path = tmp_path / "source"
    source_bytes = content.encode("utf-8")
    path.write_bytes(source_bytes)
    allowed = 3 if limit == "max_records" else len(source_bytes)
    with pytest.raises(ef.ResourceLimitError):
        ef.ingest_file(
            path, spec=int_spec(format, **{limit: allowed - 1}), work_dir=tmp_path, batch_rows=1
        )
    assert_no_published_table(tmp_path)
    result = ef.ingest_file(
        path, spec=int_spec(format, **{limit: allowed}), work_dir=tmp_path, batch_rows=1
    )
    assert result.accepted_records == 3


@pytest.mark.parametrize("fault", ["cancel", "timeout", "write"])
def test_interruptions_after_flush_remove_staging_and_keep_previous_result(
    tmp_path, monkeypatch, fault
):
    path = tmp_path / "source.csv"
    path.write_text("n\n1\n2\n3\n", encoding="utf-8")
    previous = ef.ingest_file(path, spec=int_spec(), work_dir=tmp_path / "prior", batch_rows=1)
    prior_bytes = (tmp_path / "prior" / previous.ingestion_id / "ingestion.json").read_bytes()
    run = context(tmp_path)
    original_new_file = pa.ipc.new_file

    class InterruptedWriter:
        def __init__(self, *args, **kwargs):
            self.writer = original_new_file(*args, **kwargs)

        def __enter__(self):
            self.writer.__enter__()
            return self

        def __exit__(self, *args):
            return self.writer.__exit__(*args)

        def write_table(self, table):
            self.writer.write_table(table)
            if fault == "cancel":
                run.cancellation.cancel()
            elif fault == "timeout":
                run.deadline = time.perf_counter() - 1
            else:
                raise OSError("bounded simulated disk write failure")

    monkeypatch.setattr(pa.ipc, "new_file", InterruptedWriter)
    expected = {"cancel": ef.ExecutionCancelled, "timeout": ef.ExecutionTimeout, "write": OSError}[
        fault
    ]
    with pytest.raises(expected):
        ef.ingest_file(
            path, spec=int_spec(), work_dir=tmp_path / "failed", context=run, batch_rows=1
        )
    assert_no_published_table(tmp_path / "failed")
    assert not list((tmp_path / "failed").rglob("ingestion.json"))
    assert (
        tmp_path / "prior" / previous.ingestion_id / "ingestion.json"
    ).read_bytes() == prior_bytes


@pytest.mark.parametrize("invalid", [0, -1, True, False, 1.5, "2", None])
def test_invalid_batch_size_is_rejected_before_files_are_created(tmp_path, invalid):
    with pytest.raises(ValueError, match="positive integer"):
        ef.ingest_file(tmp_path / "absent", spec=int_spec(), work_dir=tmp_path, batch_rows=invalid)
    assert not list(tmp_path.iterdir())


def test_file_input_uses_requested_batch_size(tmp_path, monkeypatch):
    path = tmp_path / "source.csv"
    path.write_text("n\n1\n2\n3\n", encoding="utf-8")
    original_array = pa.array
    sizes = []

    def array(values, *args, **kwargs):
        sizes.append(len(values))
        return original_array(values, *args, **kwargs)

    monkeypatch.setattr(pa, "array", array)
    loaded = FileInput(path, int_spec(), batch_rows=2).load(context(tmp_path))
    assert loaded.table["n"].to_pylist() == [1, 2, 3]
    assert sizes == [2, 1]


def test_jsonl_unusual_splitlines_boundaries_keep_historical_positions(tmp_path):
    path = tmp_path / "source.jsonl"
    path.write_bytes('{"n":1}\u0085{"n":2}\r\n\n{"n":3}'.encode())
    result = ef.ingest_file(
        path, spec=int_spec("jsonl", invalid_records="quarantine"), work_dir=tmp_path, batch_rows=1
    )
    assert ef.read_table(result.output)["n"].to_pylist() == [1, 2, 3]
    assert [r.path for r in result.conversions] == ["line:1$", "line:2$", "line:4$"]
    assert result.quarantined[0].path == "line:3"
    payload = json.loads((tmp_path / result.ingestion_id / "ingestion.json").read_text())
    assert "batch_rows" not in payload["spec"]


def test_streamed_result_bytes_match_historical_canonical_json(tmp_path):
    from equiframe.evidence import canonical_bytes

    key = 'ñ"name'
    path = tmp_path / "source.jsonl"
    path.write_text(
        json.dumps({key: "Café\n界", "money": "1.10"}, ensure_ascii=False) + '\n{"broken": true}\n',
        encoding="utf-8",
    )
    spec = ef.IngestionSpec(
        format="jsonl",
        fields=(ef.FieldMapping(column=column(key, ef.StringType()), path=(key,)), fields()[1]),
        invalid_records="quarantine",
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=1)
    actual = (tmp_path / result.ingestion_id / "ingestion.json").read_bytes()
    expected = canonical_bytes(result.model_dump(mode="json")) + b"\n"
    assert actual == expected
    assert b"\\u00e9" in actual
    assert b"\\u754c" in actual
    assert b'\\"name' in actual
    assert actual.endswith(b"}\n") and not actual.endswith(b"}\n\n")


@pytest.mark.parametrize("exists", [False, True])
def test_chunk_writer_iterator_error_preserves_previous_and_cleans_partial(tmp_path, exists):
    from equiframe._document_io import write_document_chunks

    path = tmp_path / "result.json"
    if exists:
        path.write_bytes(b"previous\n")

    def interrupted():
        yield b'{"partial":'
        raise ef.ExecutionCancelled("bounded test interruption")

    with pytest.raises(ef.ExecutionCancelled):
        write_document_chunks(path, interrupted())
    assert list(tmp_path.glob("*.part")) == []
    if exists:
        assert path.read_bytes() == b"previous\n"
    else:
        assert not path.exists()


def test_chunk_writer_success_is_exclusive_and_preserves_arbitrary_bytes(tmp_path):
    from equiframe._document_io import write_document_chunks

    path = tmp_path / "result.json"
    write_document_chunks(path, (b"{", b'"a":"caf', b'\\u00e9"}', b"\n"))
    assert path.read_bytes() == b'{"a":"caf\\u00e9"}\n'
    with pytest.raises(FileExistsError):
        write_document_chunks(path, (b"new", b" value"))
    assert path.read_bytes() == b'{"a":"caf\\u00e9"}\n'
    assert list(tmp_path.iterdir()) == [path]


def test_cancellation_during_receipt_serialization_has_no_final_manifest(tmp_path, monkeypatch):
    import equiframe.ingestion as ingestion
    from equiframe._document_io import write_document_chunks

    path = tmp_path / "source.csv"
    path.write_text("n\n1\n2\n", encoding="utf-8")
    run = context(tmp_path)

    def cancel_receipt(target, chunks):
        def cancelled_chunks():
            yield next(chunks)
            run.cancellation.cancel()
            yield from chunks

        write_document_chunks(target, cancelled_chunks())

    monkeypatch.setattr(ingestion, "write_document_chunks", cancel_receipt)
    with pytest.raises(ef.ExecutionCancelled):
        ef.ingest_file(path, spec=int_spec(), work_dir=tmp_path, context=run, batch_rows=1)
    assert not list(tmp_path.rglob("ingestion.json"))
    assert not list(tmp_path.rglob("*.part"))
    # Completed byte artifacts may remain in the unique failed operation folder;
    # their existence is not a completed ingestion result or an acceptance gate.
    assert len(list(tmp_path.rglob("source.original"))) == 1


def test_chunk_writer_publish_failure_removes_partial(tmp_path, monkeypatch):
    from equiframe import _document_io

    path = tmp_path / "result.json"

    def denied(*args):
        raise PermissionError("bounded simulated publication denial")

    monkeypatch.setattr(_document_io.os, "link", denied)
    with pytest.raises(PermissionError):
        _document_io.write_document_chunks(path, (b"{}", b"\n"))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("batch_rows", [1, 2, 1000000000])
def test_jsonl_missing_empty_and_nonfinite_records_have_explicit_coverage(tmp_path, batch_rows):
    path = tmp_path / "source.jsonl"
    path.write_text('{"n":1}\n\n{}\n{"n":NaN}\n{"n":2}\n', encoding="utf-8")
    result = ef.ingest_file(
        path,
        spec=int_spec("jsonl", invalid_records="quarantine"),
        work_dir=tmp_path,
        batch_rows=batch_rows,
    )
    assert result.state == "quarantined"
    assert ef.read_table(result.output)["n"].to_pylist() == [1, 2]
    assert result.inspected_records == 5
    assert result.accepted_records == 2
    assert [r.record for r in result.quarantined] == [1, 2, 3]
    assert [r.code for r in result.quarantined] == [
        "record_object_required",
        "missing_field",
        "nonfinite_json_number",
    ]
    assert [r.path for r in result.conversions] == ["line:1$", "line:5$"]
