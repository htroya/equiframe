"""Independent behavioral expectations for ingestion policy alternatives."""

import json
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from test_ingestion_batches import int_spec
from test_migration_backends import column

import equiframe as ef


@pytest.mark.parametrize("format", ["csv", "jsonl"])
@pytest.mark.parametrize("extra_fields", ["reject", "ignore"])
def test_extra_field_policy_accepts_only_explicit_ignore(tmp_path, format, extra_fields):
    path = tmp_path / "source"
    path.write_text(
        "n,extra\n1,untouched\n" if format == "csv" else '{"n":1,"extra":"untouched"}\n'
    )
    result = ef.ingest_file(
        path, spec=int_spec(format, extra_fields=extra_fields), work_dir=tmp_path
    )
    if extra_fields == "reject":
        assert result.state == "rejected"
        assert result.output is None
    else:
        assert result.state == "completed"
        assert ef.read_table(result.output).to_pylist() == [{"n": 1}]
        assert len(result.conversions) == 1
        assert "untouched" in (tmp_path / result.ingestion_id / "source.original").read_text()


@pytest.mark.parametrize("missing", ["reject", "null"])
def test_missing_field_policy_does_not_conflate_missing_and_zero(tmp_path, missing):
    path = tmp_path / "source.jsonl"
    path.write_text('{}\n{"n":0}\n')
    spec = ef.IngestionSpec(
        format="jsonl",
        invalid_records="quarantine",
        fields=(
            ef.FieldMapping(
                column=column("n", ef.IntegerType(bits=64, signed=True)),
                path=("n",),
                missing=missing,
            ),
        ),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=1)
    if missing == "null":
        assert result.state == "completed"
        assert ef.read_table(result.output)["n"].to_pylist() == [None, 0]
        assert result.conversions[0].original_kind == "missing"
        assert result.conversions[0].original_text == "<missing>"
        assert result.conversions[0].converted_text == "null"
    else:
        assert result.state == "quarantined"
        assert ef.read_table(result.output)["n"].to_pylist() == [0]
        assert result.quarantined[0].code == "missing_field"


@pytest.mark.parametrize(
    "tokens", [(), ("",), ("", "NULL")], ids=["default-empty", "empty-string", "empty-and-null"]
)
def test_null_tokens_are_authorized_per_field_and_keep_zero(tmp_path, tokens):
    path = tmp_path / "source.jsonl"
    path.write_text('{"n":""}\n{"n":"NULL"}\n{"n":"0"}\n{"n":null}\n')
    kwargs = {} if tokens == () else {"null_tokens": tokens}
    spec = ef.IngestionSpec(
        format="jsonl",
        invalid_records="quarantine",
        fields=(
            ef.FieldMapping(
                column=column("n", ef.IntegerType(bits=64, signed=True)), path=("n",), **kwargs
            ),
        ),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=1)
    expected = (
        [0, None] if tokens == () else [None, 0, None] if tokens == ("",) else [None, None, 0, None]
    )
    assert ef.read_table(result.output)["n"].to_pylist() == expected
    assert result.inspected_records == 4
    assert len(result.quarantined) == 2 - len(tokens)


@pytest.mark.parametrize(
    "decimal_separator,thousands_separator,token",
    [
        (".", None, "1234.50"),
        (".", ",", "1,234.50"),
        (".", " ", "1 234.50"),
        (",", None, "1234,50"),
        (",", ".", "1.234,50"),
        (",", " ", "1 234,50"),
    ],
    ids=["dot-none", "dot-comma", "dot-space", "comma-none", "comma-dot", "comma-space"],
)
def test_all_admitted_decimal_separator_pairs_are_exact(
    tmp_path, decimal_separator, thousands_separator, token
):
    path = tmp_path / "money.jsonl"
    path.write_text(json.dumps({"money": token}) + "\n")
    spec = ef.IngestionSpec(
        format="jsonl",
        fields=(
            ef.FieldMapping(
                column=column("money", ef.DecimalType(precision=10, scale=2), unit="USD"),
                path=("money",),
                decimal_separator=decimal_separator,
                thousands_separator=thousands_separator,
            ),
        ),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path)
    assert result.state == "completed"
    assert ef.read_table(result.output)["money"].to_pylist() == [Decimal("1234.50")]
    assert result.conversions[0].original_text == json.dumps(token)
    assert result.conversions[0].converted_text == '"1234.50"'


@pytest.mark.parametrize("mode", ["default", "custom", "native"])
def test_boolean_token_modes_preserve_true_false_and_reject_other_values(tmp_path, mode):
    path = tmp_path / "booleans.jsonl"
    rows = (
        [{"b": "true"}, {"b": "false"}, {"b": "TRUE"}]
        if mode == "default"
        else [{"b": "sí"}, {"b": "N"}, {"b": "true"}]
        if mode == "custom"
        else [{"b": True}, {"b": False}, {"b": 1}]
    )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    tokens = {"true_tokens": ("Y", "sí"), "false_tokens": ("N",)} if mode == "custom" else {}
    spec = ef.IngestionSpec(
        format="jsonl",
        invalid_records="quarantine",
        fields=(ef.FieldMapping(column=column("b", ef.BooleanType()), path=("b",), **tokens),),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=1)
    assert ef.read_table(result.output)["b"].to_pylist() == [True, False]
    assert result.quarantined[0].code == "invalid_boolean"
    assert result.quarantined[0].record == 2


@pytest.mark.parametrize("date_format", ["default", None, "%d/%m/%Y"])
def test_date_formats_require_valid_calendar_dates(tmp_path, date_format):
    iso = date_format in ("default", None)
    path = tmp_path / "dates.jsonl"
    path.write_text(
        "".join(
            json.dumps({"d": s}) + "\n"
            for s in (["2024-02-29", "2026-02-29"] if iso else ["29/02/2024", "29/02/2026"])
        )
    )
    day = column("d", ef.StringType()).model_copy(
        update={"logical_type": ef.DateType(), "temporal_policy": ef.DatePolicy(closed="both")}
    )
    kwargs = {} if date_format == "default" else {"date_format": date_format}
    result = ef.ingest_file(
        path,
        spec=ef.IngestionSpec(
            format="jsonl",
            invalid_records="quarantine",
            fields=(ef.FieldMapping(column=day, path=("d",), **kwargs),),
        ),
        work_dir=tmp_path,
    )
    assert ef.read_table(result.output)["d"].to_pylist() == [date(2024, 2, 29)]
    assert len(result.quarantined) == 1
    assert result.quarantined[0].record == 1


@pytest.mark.parametrize("scope", ["record", "root", "ancestor"])
def test_all_scopes_use_the_declared_object_and_default_ancestor_level(tmp_path, scope):
    path = tmp_path / "nested.json"
    path.write_text('{"label":"root","items":[{"label":"parent","row":{"label":"record"}}]}')
    kwargs = {"scope": scope}
    spec = ef.IngestionSpec(
        format="json",
        records_path=("items", "*", "row"),
        fields=(
            ef.FieldMapping(column=column("label", ef.StringType()), path=("label",), **kwargs),
        ),
        extra_fields="ignore",
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path)
    assert ef.read_table(result.output)["label"].to_pylist() == [
        {"record": "record", "root": "root", "ancestor": "parent"}[scope]
    ]
    assert result.spec.fields[0].ancestor_levels == 1


@pytest.mark.parametrize("header", ["default", True, False])
def test_csv_header_default_and_both_explicit_values(tmp_path, header):
    path = tmp_path / "source.csv"
    path.write_text("1\n" if header is False else "n\n1\n")
    kwargs = {} if header == "default" else {"header": header, "fieldnames": ("n",)}
    result = ef.ingest_file(path, spec=int_spec(**kwargs), work_dir=tmp_path)
    assert result.state == "completed"
    assert ef.read_table(result.output)["n"].to_pylist() == [1]


@pytest.mark.parametrize("format", ["csv", "json", "jsonl"])
def test_zero_record_budget_accepts_only_explicit_empty_source(tmp_path, format):
    path = tmp_path / "source"
    path.write_text("n\n" if format == "csv" else "[]" if format == "json" else "")
    kwargs = {"records_path": ("*",)} if format == "json" else {}
    spec = int_spec(format, max_records=0, **kwargs)
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path)
    assert result.state == "completed"
    assert result.inspected_records == result.accepted_records == 0


@pytest.mark.parametrize("encoding", ["", "   "])
def test_empty_encoding_specification_is_rejected(encoding):
    with pytest.raises(ValidationError):
        int_spec(encoding=encoding)


def test_unknown_codec_never_publishes_success(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("n\n1\n")
    with pytest.raises(LookupError):
        ef.ingest_file(path, spec=int_spec(encoding="not-an-installed-codec"), work_dir=tmp_path)
    assert not list(tmp_path.rglob("ingestion.json"))
    assert not list(tmp_path.rglob("accepted.arrow"))


@pytest.mark.parametrize(
    "changes",
    [
        {"format": "xlsx"},
        {"format": None},
        {"delimiter": ""},
        {"delimiter": "||"},
        {"delimiter": False},
        {"header": False},
        {"header": "false"},
        {"max_records": -1},
        {"max_records": True},
        {"max_source_bytes": 0},
        {"max_source_bytes": -1},
        {"max_source_bytes": True},
        {"extra_fields": "coerce"},
        {"invalid_records": "repair"},
        {"records_path": ("*",)},
        {"fields": ()},
    ],
    ids=[
        "format-unknown",
        "format-none",
        "delimiter-empty",
        "delimiter-multiple",
        "delimiter-bool",
        "headerless-without-fieldnames",
        "header-string",
        "records-negative",
        "records-bool",
        "bytes-zero",
        "bytes-negative",
        "bytes-bool",
        "extras-unknown",
        "invalid-policy-unknown",
        "csv-records-path",
        "fields-empty",
    ],
)
def test_invalid_ingestion_spec_options_fail_closed(changes):
    base = {"format": "csv", "fields": int_spec().fields}
    with pytest.raises(ValidationError):
        ef.IngestionSpec(**(base | changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"path": ()},
        {"path": ("*",)},
        {"path": ("",)},
        {"scope": "arbitrary"},
        {"ancestor_levels": 0},
        {"ancestor_levels": -1},
        {"ancestor_levels": True},
        {"decimal_separator": ";"},
        {"decimal_separator": ".", "thousands_separator": "."},
        {"decimal_separator": ",", "thousands_separator": ","},
        {"thousands_separator": "_"},
        {"true_tokens": ("yes",), "false_tokens": ("yes",)},
        {"missing": "invent"},
        {"date_format": False},
    ],
    ids=[
        "path-empty",
        "path-wildcard",
        "path-empty-component",
        "scope-unknown",
        "ancestor-zero",
        "ancestor-negative",
        "ancestor-bool",
        "decimal-separator-unknown",
        "decimal-dot-collision",
        "decimal-comma-collision",
        "thousands-unknown",
        "boolean-overlap",
        "missing-unknown",
        "date-format-bool",
    ],
)
def test_invalid_field_mapping_options_fail_closed(changes):
    base = {"column": column("n", ef.IntegerType(bits=64, signed=True)), "path": ("n",)}
    with pytest.raises(ValidationError):
        ef.FieldMapping(**(base | changes))


@pytest.mark.parametrize(
    "changes", [{"null_tokens": ("",)}, {"missing": "null"}], ids=["null-tokens", "missing-null"]
)
def test_absence_conversion_requires_nullable_column(changes):
    with pytest.raises(ValidationError, match="nullable"):
        ef.FieldMapping(
            column=column("n", ef.IntegerType(bits=64, signed=True), nullable=False),
            path=("n",),
            **changes,
        )


def test_duplicate_output_names_and_csv_nonrecord_scopes_are_rejected():
    mapping = int_spec().fields[0]
    with pytest.raises(ValidationError, match="unique"):
        ef.IngestionSpec(format="jsonl", fields=(mapping, mapping))
    with pytest.raises(ValidationError, match="direct record fields"):
        ef.IngestionSpec(format="csv", fields=(mapping.model_copy(update={"scope": "root"}),))


@pytest.mark.parametrize("bits", [32, 64])
def test_float_parsing_admission_has_independent_precision_expectation(tmp_path, bits):
    path = tmp_path / "float.jsonl"
    path.write_text('{"x":"1.5"}\n{"x":"0.1"}\n{"x":"inf"}\n')
    spec = ef.IngestionSpec(
        format="jsonl",
        invalid_records="quarantine",
        fields=(ef.FieldMapping(column=column("x", ef.FloatType(bits=bits)), path=("x",)),),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path)
    assert ef.read_table(result.output)["x"].to_pylist() == ([1.5] if bits == 32 else [1.5, 0.1])
    assert result.quarantined[-1].code == "nonfinite_float_requires_explicit_external_input"
    if bits == 32:
        assert result.quarantined[0].code == "float32_precision_loss"


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_file_input_does_not_accept_quarantined_partial_data(tmp_path, format):
    from test_ingestion_batches import context

    path = tmp_path / "source"
    path.write_text("n\n1\nbad\n" if format == "csv" else '{"n":1}\n{"n":"bad"}\n')
    source = ef.FileInput(path, int_spec(format, invalid_records="quarantine"))
    assert source.batch_rows == 4096
    with pytest.raises(ef.InvalidExecutionInput, match="rejected/quarantined"):
        source.load(context(tmp_path))
    manifest = next(tmp_path.rglob("ingestion.json"))
    result = ef.IngestionResult.model_validate_json(manifest.read_bytes())
    assert result.state == "quarantined"
    assert result.accepted_records == 1
    assert result.output is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "2.0"},
        {"extractor_version": "invented"},
        {"state": "success"},
        {"accepted_records": -1},
        {"inspected_records": 2},
        {"output": None},
        {"state": "rejected"},
    ],
    ids=[
        "schema-version",
        "extractor-version",
        "unknown-state",
        "negative-count",
        "coverage-count",
        "completed-without-output",
        "rejected-with-output",
    ],
)
def test_result_cannot_relabel_invalid_or_partial_evidence_as_success(tmp_path, changes):
    path = tmp_path / "source.csv"
    path.write_text("n\n1\n")
    result = ef.ingest_file(path, spec=int_spec(), work_dir=tmp_path, context=None)
    payload = result.model_dump(mode="json") | changes
    with pytest.raises(ValidationError):
        ef.IngestionResult.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("missing", ["format", "fields"])
def test_required_ingestion_configuration_cannot_be_omitted(missing):
    spec = {"format": "csv", "fields": int_spec().fields}
    spec.pop(missing)
    with pytest.raises(ValidationError):
        ef.IngestionSpec(**spec)


@pytest.mark.parametrize(
    "bits,signed,tokens,expected",
    [
        (8, True, ["-128", "127", "-129", "128"], [-128, 127]),
        (
            64,
            False,
            ["0", "18446744073709551615", "-1", "18446744073709551616"],
            [0, 18446744073709551615],
        ),
    ],
    ids=["signed-int8", "unsigned-int64"],
)
def test_integer_ingestion_limits_preserve_exact_boundaries(
    tmp_path, bits, signed, tokens, expected
):
    path = tmp_path / "integers.jsonl"
    path.write_text("".join(json.dumps({"n": token}) + "\n" for token in tokens))
    spec = ef.IngestionSpec(
        format="jsonl",
        invalid_records="quarantine",
        fields=(
            ef.FieldMapping(
                column=column("n", ef.IntegerType(bits=bits, signed=signed)), path=("n",)
            ),
        ),
    )
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=1)
    assert ef.read_table(result.output)["n"].to_pylist() == expected
    assert [r.code for r in result.quarantined] == ["integer_overflow", "integer_overflow"]


@pytest.mark.parametrize("invalid", [0, -1, True, False, 1.5, "2", None])
def test_file_input_rejects_invalid_batch_before_source_io(tmp_path, invalid):
    from test_ingestion_batches import context

    source = ef.FileInput(tmp_path / "absent", int_spec(), batch_rows=invalid)
    with pytest.raises(ValueError, match="positive integer"):
        source.load(context(tmp_path))
    assert not list(tmp_path.rglob("source.original"))


def test_one_byte_source_budget_accepts_exact_minimum(tmp_path):
    path = tmp_path / "one.csv"
    path.write_bytes(b"1")
    spec = int_spec(header=False, fieldnames=("n",), max_source_bytes=1, max_records=1)
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path)
    assert result.state == "completed"
    assert result.source.size_bytes == 1
    assert ef.read_table(result.output)["n"].to_pylist() == [1]


def test_receipt_fields_match_independent_literal_provenance(tmp_path):
    import hashlib
    import re

    raw = b'{"n":"001"}\n{"n":"bad"}\n'
    path = tmp_path / "input con acento á.jsonl"
    path.write_bytes(raw)
    spec = int_spec("jsonl", invalid_records="quarantine")
    result = ef.ingest_file(path, spec=spec, work_dir=tmp_path, batch_rows=1)
    assert re.fullmatch(r"ingestion_[0-9a-f]{32}", result.ingestion_id)
    assert result.spec == spec
    assert result.schema_version == "1.0"
    assert result.extractor_version == "equiframe-ingestion-1.0"
    assert result.source.model_dump() == {
        "uri": path.resolve().as_uri(),
        "preserved_uri": (tmp_path / result.ingestion_id / "source.original").resolve().as_uri(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    assert [r.model_dump() for r in result.conversions] == [
        {
            "record": 0,
            "path": "line:1$",
            "column": "n",
            "original_kind": "str",
            "original_text": '"001"',
            "converted_text": "1",
            "operation": "declared_scalar_parse",
        }
    ]
    assert [r.model_dump() for r in result.quarantined] == [
        {
            "record": 1,
            "path": "line:2$",
            "original_text": '{"n":"bad"}',
            "code": "invalid_integer",
        }
    ]
    assert result.inspected_records == 2
    assert result.accepted_records == 1
    assert ef.read_table(result.output).to_pylist() == [{"n": 1}]


def test_elapsed_seconds_records_observed_interval(tmp_path, monkeypatch):
    import equiframe.ingestion as ingestion

    path = tmp_path / "source.csv"
    path.write_text("n\n1\n")
    times = iter((10.0, 12.5))
    monkeypatch.setattr(ingestion.time, "perf_counter", lambda: next(times))
    result = ef.ingest_file(path, spec=int_spec(), work_dir=tmp_path)
    assert result.elapsed_seconds == 2.5
