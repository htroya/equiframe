"""Ingestion distinguishes absence, exact money, identifiers and temporal units."""

import hashlib
from datetime import date
from decimal import Decimal

import pytest
from test_migration_backends import column

from equiframe.contracts import (
    DatePolicy,
    DateType,
    DecimalType,
    IntegerType,
    StringType,
    TimestampPolicy,
    TimestampType,
)
from equiframe.ingestion import FieldMapping, IngestionSpec, ingest_file
from equiframe.tables import read_table


def fields():
    return (
        FieldMapping(column=column("id", StringType(), nullable=False), path=("id",)),
        FieldMapping(
            column=column("money", DecimalType(precision=10, scale=2), unit="USD"),
            path=("money",),
            null_tokens=("NULL",),
        ),
    )


@pytest.mark.parametrize(
    "format,content,records_path",
    [
        ("csv", 'id,money\n001,"1,234.50"\n002,NULL\n003,0.00\n', ()),
        (
            "json",
            '[{"id":"001","money":"1,234.50"},{"id":"002","money":null},{"id":"003","money":"0.00"}]',
            ("*",),
        ),
        (
            "jsonl",
            '{"id":"001","money":"1,234.50"}\n{"id":"002","money":null}\n{"id":"003","money":"0.00"}\n',
            (),
        ),
    ],
    ids=("csv", "json", "jsonl"),
)
def test_exact_money_ids_sources_and_receipts(tmp_path, format, content, records_path):
    path = tmp_path / ("source." + format)
    path.write_text(content, encoding="utf-8")
    mapping = fields()
    mapping = (mapping[0], mapping[1].model_copy(update={"thousands_separator": ","}))
    result = ingest_file(
        path,
        spec=IngestionSpec(format=format, fields=mapping, records_path=records_path),
        work_dir=tmp_path,
    )
    assert result.state == "completed"
    assert result.source.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert read_table(result.output).to_pylist() == [
        {"id": "001", "money": Decimal("1234.50")},
        {"id": "002", "money": None},
        {"id": "003", "money": Decimal("0.00")},
    ]
    assert len(result.conversions) == 6
    assert result.conversions[0].original_text == '"001"'


@pytest.mark.parametrize("value", ['""', "1.001", "999999999.00", "true", '"-0.00"'])
def test_invalid_money_is_quarantined_without_repair(tmp_path, value):
    path = tmp_path / "source.jsonl"
    path.write_text(
        '{"id":"001","money":' + value + '}\n{"id":"002","money":2.00}', encoding="utf-8"
    )
    result = ingest_file(
        path,
        spec=IngestionSpec(format="jsonl", fields=fields(), invalid_records="quarantine"),
        work_dir=tmp_path,
    )
    assert result.state == "quarantined"
    assert result.inspected_records == 2
    assert result.accepted_records == 1
    assert len(result.quarantined) == 1
    assert read_table(result.output).to_pylist() == [{"id": "002", "money": Decimal("2.00")}]


@pytest.mark.parametrize(
    "content",
    [
        '{"id":1,"money":0}',
        '{"id":"001"}',
        '{"id":"001","money":0,"new":1}',
        '{"id":"001","id":"002","money":0}',
        '{"id":"001","money":NaN}',
        "{broken}",
    ],
    ids=("numeric_id", "missing", "extra", "duplicate", "nan", "malformed"),
)
def test_rejected_schema_bad_json_and_numeric_id_do_not_publish(tmp_path, content):
    path = tmp_path / "source.json"
    path.write_text(content, encoding="utf-8")
    result = ingest_file(
        path, spec=IngestionSpec(format="json", fields=fields()), work_dir=tmp_path
    )
    assert result.state == "rejected"
    assert result.output is None
    assert result.quarantined


def test_nested_grain_and_parent_relation_are_explicit(tmp_path):
    path = tmp_path / "source.json"
    path.write_text(
        '{"records":[{"ocid":"0007","awards":[{"id":"a","money":2.00},{"id":"b","money":3.00}]}]}',
        encoding="utf-8",
    )
    mappings = (
        FieldMapping(
            column=column("ocid", StringType(), nullable=False),
            path=("ocid",),
            scope="ancestor",
            ancestor_levels=2,
        ),
        *fields(),
    )
    result = ingest_file(
        path,
        spec=IngestionSpec(
            format="json", fields=mappings, records_path=("records", "*", "awards", "*")
        ),
        work_dir=tmp_path,
    )
    assert result.state == "completed"
    assert read_table(result.output).to_pylist() == [
        {"ocid": "0007", "id": "a", "money": Decimal("2.00")},
        {"ocid": "0007", "id": "b", "money": Decimal("3.00")},
    ]
    assert "[1]" in result.conversions[-1].path
    missing_expansion = ingest_file(
        path,
        spec=IngestionSpec(format="json", fields=fields(), records_path=("records",)),
        work_dir=tmp_path,
    )
    assert missing_expansion.state == "rejected"


def test_exact_nanosecond_timestamp_offset_and_calendar(tmp_path):
    stamp = column("t", StringType()).model_copy(
        update={
            "logical_type": TimestampType(unit="ns", timezone="UTC"),
            "temporal_policy": TimestampPolicy(
                granularity="ns",
                timezone="UTC",
                naive="reject",
                comparison="instant",
                ambiguous="reject",
                closed="both",
            ),
        }
    )
    spec = IngestionSpec(
        format="jsonl",
        fields=(FieldMapping(column=stamp, path=("t",)),),
        invalid_records="quarantine",
    )
    path = tmp_path / "dates.jsonl"
    path.write_text(
        '{"t":"2026-10-03T00:00:00.000000123Z"}\n{"t":"2026-10-03T00:00:00"}\n{"t":"2026-02-30T00:00:00Z"}\n{"t":"2026-10-03T00:00:00+01:00"}',
        encoding="utf-8",
    )
    result = ingest_file(path, spec=spec, work_dir=tmp_path)
    assert result.accepted_records == 1
    assert len(result.quarantined) == 3
    assert read_table(result.output)["t"].cast("int64").to_pylist() == [1790985600000000123]


def test_dates_are_days_and_integer_overflow_rejects(tmp_path):
    day = column("d", StringType()).model_copy(
        update={"logical_type": DateType(), "temporal_policy": DatePolicy(closed="both")}
    )
    path = tmp_path / "dates.csv"
    path.write_text("d,n\n2026-10-03,127\n2026-02-30,1\n2026-10-03,128\n", encoding="utf-8")
    spec = IngestionSpec(
        format="csv",
        invalid_records="quarantine",
        fields=(
            FieldMapping(column=day, path=("d",)),
            FieldMapping(column=column("n", IntegerType(bits=8, signed=True)), path=("n",)),
        ),
    )
    result = ingest_file(path, spec=spec, work_dir=tmp_path)
    assert read_table(result.output).to_pylist() == [{"d": date(2026, 10, 3), "n": 127}]
    assert len(result.quarantined) == 2


def test_json_numeric_exponents_are_bounded_before_plain_string_expansion(tmp_path):
    path = tmp_path / "exponents.jsonl"
    path.write_text(
        '{"id":"tiny","money":1e-999999999}\n'
        '{"id":"huge","money":1e999999999}\n'
        '{"id":"exact","money":2e3}',
        encoding="utf-8",
    )
    result = ingest_file(
        path,
        spec=IngestionSpec(
            format="jsonl", fields=fields(), invalid_records="quarantine", max_source_bytes=200
        ),
        work_dir=tmp_path,
    )
    assert len(result.quarantined) == 2
    assert read_table(result.output).to_pylist() == [{"id": "exact", "money": Decimal("2000.00")}]


@pytest.mark.parametrize("content", ["", " \n\t"])
def test_empty_json_document_is_rejected_without_publishing_a_table(tmp_path, content):
    path = tmp_path / "empty.json"
    path.write_text(content, encoding="utf-8")
    result = ingest_file(
        path, spec=IngestionSpec(format="json", fields=fields()), work_dir=tmp_path
    )
    assert result.state == "rejected"
    assert result.output is None
    assert result.accepted_records == 0
    assert result.inspected_records == 1
    assert result.quarantined[0].code == "ValueError:empty_json_document"


@pytest.mark.parametrize("format,content,records_path", [("json", "[]", ("*",)), ("jsonl", "", ())])
def test_explicit_empty_collection_and_empty_jsonl_stream_remain_valid(
    tmp_path, format, content, records_path
):
    path = tmp_path / ("empty." + format)
    path.write_text(content, encoding="utf-8")
    result = ingest_file(
        path,
        spec=IngestionSpec(format=format, fields=fields(), records_path=records_path),
        work_dir=tmp_path,
    )
    assert result.state == "completed"
    assert result.inspected_records == 0
    assert read_table(result.output).num_rows == 0


@pytest.mark.parametrize("invalid_records", ["reject", "quarantine"])
def test_timestamp_overflow_respects_record_policy_and_preserves_int64_boundaries(
    tmp_path, invalid_records
):
    stamp = column("t", StringType(), nullable=False).model_copy(
        update={
            "logical_type": TimestampType(unit="ns", timezone="UTC"),
            "temporal_policy": TimestampPolicy(
                granularity="ns",
                timezone="UTC",
                naive="reject",
                comparison="instant",
                ambiguous="reject",
                closed="both",
            ),
        }
    )
    path = tmp_path / "overflow.jsonl"
    path.write_text(
        '{"t":"9999-12-31T00:00:00Z"}\n'
        '{"t":"0001-01-01T00:00:00Z"}\n'
        '{"t":"1677-09-21T00:12:43.145224192Z"}\n'
        '{"t":"2262-04-11T23:47:16.854775807Z"}',
        encoding="utf-8",
    )
    result = ingest_file(
        path,
        spec=IngestionSpec(
            format="jsonl",
            fields=(FieldMapping(column=stamp, path=("t",)),),
            invalid_records=invalid_records,
        ),
        work_dir=tmp_path,
    )
    if invalid_records == "reject":
        assert result.state == "rejected"
        assert result.output is None
        assert result.inspected_records == 1
        assert result.accepted_records == 0
    else:
        assert result.state == "quarantined"
        assert result.inspected_records == 4
        assert result.accepted_records == 2
        assert read_table(result.output)["t"].cast("int64").to_pylist() == [-(2**63), 2**63 - 1]
    assert all(item.code == "timestamp_overflow" for item in result.quarantined)
