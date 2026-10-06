"""CSV overflow diagnostics cannot overwrite a legitimate source header."""

import hashlib
import json

import pytest
from test_migration_backends import column

import equiframe as ef


@pytest.mark.parametrize("header", ["source", "<surplus_fields>", "<surplus_fields>#", "null"])
@pytest.mark.parametrize("overflow", [False, True])
@pytest.mark.parametrize("extra_fields", ["ignore", "reject"])
@pytest.mark.parametrize("invalid_records", ["reject", "quarantine"])
def test_arbitrary_header_surplus_contract(
    tmp_path, header, overflow, extra_fields, invalid_records
):
    raw = (header + "\n001" + (",extra" if overflow else "") + "\n002\n").encode()
    source = tmp_path / "source.csv"
    source.write_bytes(raw)
    spec = ef.IngestionSpec(
        format="csv",
        fields=(ef.FieldMapping(column=column("id", ef.StringType()), path=(header,)),),
        extra_fields=extra_fields,
        invalid_records=invalid_records,
    )
    result = ef.ingest_file(source, spec=spec, work_dir=tmp_path, batch_rows=1)
    rejected_row = overflow and extra_fields == "reject"
    if not rejected_row:
        assert result.state == "completed"
        assert result.inspected_records == result.accepted_records == 2
        assert ef.read_table(result.output).to_pylist() == [{"id": "001"}, {"id": "002"}]
        assert [item.original_text for item in result.conversions] == ['"001"', '"002"']
        assert [item.path for item in result.conversions] == ["$[0]", "$[1]"]
    else:
        assert result.quarantined[0].record == 0
        assert result.quarantined[0].path == "$[0]"
        assert result.quarantined[0].code == "new_or_extra_field"
        diagnostic = json.loads(result.quarantined[0].original_text)
        if header in {"<surplus_fields>", "null"}:
            assert diagnostic == {"fields": {header: "001"}, "surplus_fields": ["extra"]}
        else:
            assert diagnostic == {header: "001", "null": ["extra"], "<surplus_fields>": ["extra"]}
        if invalid_records == "reject":
            assert result.state == "rejected"
            assert result.output is None
            assert result.accepted_records == 0
            assert result.inspected_records == 1
        else:
            assert result.state == "quarantined"
            assert result.inspected_records == 2
            assert result.accepted_records == 1
            assert ef.read_table(result.output).to_pylist() == [{"id": "002"}]
            assert result.conversions[0].record == 1
            assert result.conversions[0].path == "$[1]"
    assert result.source.sha256 == hashlib.sha256(raw).hexdigest()
    assert result.source.size_bytes == len(raw)
    assert (tmp_path / result.ingestion_id / "source.original").read_bytes() == raw


@pytest.mark.parametrize("extra_fields", ["ignore", "reject"])
def test_overflow_never_becomes_a_declared_missing_field(tmp_path, extra_fields):
    source = tmp_path / "source.csv"
    source.write_text("source\n001,extra\n")
    spec = ef.IngestionSpec(
        format="csv",
        fields=(
            ef.FieldMapping(column=column("id", ef.StringType()), path=("source",)),
            ef.FieldMapping(
                column=column("optional", ef.StringType()),
                path=("<surplus_fields>",),
                missing="null",
            ),
        ),
        extra_fields=extra_fields,
    )
    result = ef.ingest_file(source, spec=spec, work_dir=tmp_path)
    if extra_fields == "ignore":
        assert result.state == "completed"
        assert ef.read_table(result.output).to_pylist() == [{"id": "001", "optional": None}]
        assert result.conversions[1].original_kind == "missing"
        assert result.conversions[1].original_text == "<missing>"
    else:
        assert result.state == "rejected"
        assert result.quarantined[0].code == "new_or_extra_field"
        diagnostic = json.loads(result.quarantined[0].original_text)
        assert diagnostic == {"fields": {"source": "001"}, "surplus_fields": ["extra"]}


def test_diagnostic_namespace_preserves_all_actual_and_declared_names(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("<surplus_fields>,<surplus_fields>#\n001,named,extra\n")
    spec = ef.IngestionSpec(
        format="csv",
        fields=(
            ef.FieldMapping(column=column("id", ef.StringType()), path=("<surplus_fields>",)),
            ef.FieldMapping(column=column("label", ef.StringType()), path=("<surplus_fields>#",)),
            ef.FieldMapping(
                column=column("optional", ef.StringType()),
                path=("<surplus_fields>##",),
                missing="null",
            ),
        ),
    )
    result = ef.ingest_file(source, spec=spec, work_dir=tmp_path)
    assert result.state == "rejected"
    assert result.quarantined[0].code == "new_or_extra_field"
    assert json.loads(result.quarantined[0].original_text) == {
        "fields": {"<surplus_fields>": "001", "<surplus_fields>#": "named"},
        "surplus_fields": ["extra"],
    }


@pytest.mark.parametrize(
    "extra_fields,expected_code", [("reject", "new_or_extra_field"), ("ignore", "invalid_integer")]
)
def test_noncolliding_overflow_diagnostic_retains_historical_bytes(
    tmp_path, extra_fields, expected_code
):
    source = tmp_path / "source.csv"
    source.write_bytes(b"n\nbad,extra\n")
    spec = ef.IngestionSpec(
        format="csv",
        fields=(
            ef.FieldMapping(column=column("n", ef.IntegerType(bits=64, signed=True)), path=("n",)),
        ),
        extra_fields=extra_fields,
        invalid_records="quarantine",
    )
    result = ef.ingest_file(source, spec=spec, work_dir=tmp_path)
    assert result.state == "quarantined"
    assert result.quarantined[0].code == expected_code
    assert result.quarantined[0].original_text.encode("utf-8") == (
        b'{"n":"bad","null":["extra"],"<surplus_fields>":["extra"]}'
    )
    assert result.quarantined[0].path == "$[0]"
    assert result.source.sha256 == hashlib.sha256(b"n\nbad,extra\n").hexdigest()


@pytest.mark.parametrize("header", ["<surplus_fields>", "null"])
def test_colliding_header_conversion_failure_keeps_named_values_and_overflow(tmp_path, header):
    source = tmp_path / "source.csv"
    source.write_text(header + "\nbad,extra\n")
    spec = ef.IngestionSpec(
        format="csv",
        fields=(
            ef.FieldMapping(
                column=column("n", ef.IntegerType(bits=64, signed=True)), path=(header,)
            ),
        ),
        extra_fields="ignore",
        invalid_records="quarantine",
    )
    result = ef.ingest_file(source, spec=spec, work_dir=tmp_path)
    assert result.quarantined[0].code == "invalid_integer"
    assert json.loads(result.quarantined[0].original_text) == {
        "fields": {header: "bad"},
        "surplus_fields": ["extra"],
    }


@pytest.mark.parametrize("extra_fields", ["ignore", "reject"])
def test_wrapper_words_are_also_legitimate_source_headers(tmp_path, extra_fields):
    source = tmp_path / "source.csv"
    source.write_text(
        "<surplus_fields>,fields,surplus_fields,null\n"
        "001,named-fields,named-surplus,named-null,extra\n"
    )
    names = ("<surplus_fields>", "fields", "surplus_fields", "null")
    spec = ef.IngestionSpec(
        format="csv",
        fields=tuple(
            ef.FieldMapping(column=column(name, ef.StringType()), path=(name,)) for name in names
        ),
        extra_fields=extra_fields,
    )
    result = ef.ingest_file(source, spec=spec, work_dir=tmp_path)
    expected = {
        "<surplus_fields>": "001",
        "fields": "named-fields",
        "surplus_fields": "named-surplus",
        "null": "named-null",
    }
    if extra_fields == "ignore":
        assert result.state == "completed"
        assert ef.read_table(result.output).to_pylist() == [expected]
    else:
        assert result.state == "rejected"
        assert result.quarantined[0].code == "new_or_extra_field"
        assert json.loads(result.quarantined[0].original_text) == {
            "fields": expected,
            "surplus_fields": ["extra"],
        }
