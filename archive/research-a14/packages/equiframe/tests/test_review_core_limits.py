"""Real resource and numeric context regressions for reusable local ETL."""

from decimal import ROUND_FLOOR, Decimal, Inexact, InvalidOperation, Rounded, localcontext

import pyarrow as pa
import pytest
from rule_helpers import captured
from test_migration_backends import column, contract, run

from equiframe.contracts import AggregateCheck, DecimalType, RuleSpec, StringType
from equiframe.errors import ExecutionCancelled, ResourceLimitError
from equiframe.ingestion import FieldMapping, IngestionSpec, ingest_file
from equiframe.migration.types import (
    Aggregate,
    Arithmetic,
    Column,
    LiteralExpression,
    Measure,
    NamedExpression,
    Project,
    RelationalPlan,
    Scan,
)
from equiframe.rules import evaluate_rules
from equiframe.tables import read_table
from equiframe.values import DecimalValue


@pytest.mark.parametrize("invalid_records", ["reject", "quarantine"])
@pytest.mark.parametrize("max_records", [1, 2])
def test_malformed_csv_record_respects_budget_and_keeps_file_failure(
    tmp_path, invalid_records, max_records
):
    path = tmp_path / "malformed.csv"
    path.write_text('id\n1\n"unterminated\n', encoding="utf-8")
    spec = IngestionSpec(
        format="csv",
        fields=(FieldMapping(column=column("id", StringType()), path=("id",)),),
        invalid_records=invalid_records,
        max_records=max_records,
    )
    if max_records == 1:
        with pytest.raises(ResourceLimitError, match="record budget"):
            ingest_file(path, spec=spec, work_dir=tmp_path)
        return
    result = ingest_file(path, spec=spec, work_dir=tmp_path)
    assert result.state == "rejected" and result.output is None
    assert result.inspected_records == 2 and result.accepted_records == 1
    assert len(result.quarantined) == 1
    assert result.quarantined[0].code == "Error:unexpected end of data"


@pytest.mark.parametrize(
    "format,content", [("csv", b'"unterminated\n'), ("json", b""), ("csv", b"\xff")]
)
def test_file_parser_failures_cannot_exceed_zero_record_budget(tmp_path, format, content):
    path = tmp_path / ("invalid." + format)
    path.write_bytes(content)
    spec = IngestionSpec(
        format=format,
        fields=(FieldMapping(column=column("id", StringType()), path=("id",)),),
        invalid_records="quarantine",
        max_records=0,
    )
    with pytest.raises(ResourceLimitError, match="record budget"):
        ingest_file(path, spec=spec, work_dir=tmp_path)


@pytest.mark.parametrize("numeric_token", [True, False])
def test_money_ingestion_is_independent_of_the_callers_decimal_context(tmp_path, numeric_token):
    dtype = DecimalType(precision=20, scale=2)
    value = "1234567890123456.78"
    token = value if numeric_token else '"' + value + '"'
    path = tmp_path / "money.jsonl"
    path.write_text('{"money":' + token + '}\n{"money":2.001}', encoding="utf-8")
    spec = IngestionSpec(
        format="jsonl",
        fields=(FieldMapping(column=column("money", dtype, unit="USD"), path=("money",)),),
        invalid_records="quarantine",
    )
    with localcontext() as context:
        context.prec = 2
        context.Emin = -9
        context.Emax = 9
        context.rounding = ROUND_FLOOR
        context.clamp = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        original = context.copy()
        result = ingest_file(path, spec=spec, work_dir=tmp_path)
        assert read_table(result.output).to_pylist() == [{"money": Decimal(value)}]
        assert context.prec == original.prec
        assert context.flags == original.flags
        assert context.traps == original.traps
    assert result.state == "quarantined"
    assert result.inspected_records == 2
    assert result.accepted_records == 1
    assert result.quarantined[0].code == "decimal_overflow_or_precision_loss"


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
@pytest.mark.parametrize("operation", ["literal", "add", "sum"])
def test_native_decimal_etl_is_independent_of_the_callers_decimal_context(
    tmp_path, engine, operation
):
    dtype = DecimalType(precision=20, scale=2)
    wider = DecimalType(precision=21, scale=2)
    value = Decimal("1234567890123456.78")
    source = pa.table({"money": pa.array([value, value], type=pa.decimal128(20, 2))})
    schema = contract(
        {"input": [column("money", dtype, unit="USD")]},
        [column("result", wider if operation != "literal" else dtype, unit="USD")],
    )
    if operation == "sum":
        step = Aggregate(
            node_id="result",
            source="scan",
            group_by=(),
            null_groups="retain",
            empty_sum="null",
            measures=(Measure(name="result", operation="sum", column="money", logical_type=wider),),
        )
    else:
        expression = (
            LiteralExpression(value=DecimalValue(value=value), logical_type=dtype, unit="USD")
            if operation == "literal"
            else Arithmetic(
                operation="add",
                left=Column(name="money"),
                right=Column(name="money"),
                logical_type=wider,
                unit="USD",
            )
        )
        step = Project(
            node_id="result",
            source="scan",
            columns=(NamedExpression(name="result", expression=expression),),
        )
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"), step), output="result")
    expected = (
        [Decimal("2469135780246913.56")]
        if operation == "sum"
        else [value, value]
        if operation == "literal"
        else [Decimal("2469135780246913.56"), Decimal("2469135780246913.56")]
    )
    with localcontext() as context:
        context.prec = 2
        context.Emin = -9
        context.Emax = 9
        context.rounding = ROUND_FLOOR
        context.clamp = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        original = context.copy()
        result = run(plan, schema, {"input": source}, engine, tmp_path)
        assert result.state == "completed", result.problem
        assert read_table(result.output.data)["result"].to_pylist() == expected
        assert context.flags == original.flags
        assert context.traps == original.traps


def test_expanded_record_budget_rejects_before_scalar_conversions(tmp_path, monkeypatch):
    import equiframe.ingestion as ingestion

    path = tmp_path / "nested.json"
    path.write_text('[{"money":1},{"money":2}]', encoding="utf-8")
    spec = IngestionSpec(
        format="json",
        fields=(
            FieldMapping(
                column=column("money", DecimalType(precision=10, scale=2)), path=("money",)
            ),
        ),
        records_path=("*",),
        max_records=1,
    )

    def unexpected_conversion(*args):
        pytest.fail("expanded input must respect its budget before scalar conversion")

    monkeypatch.setattr(ingestion, "_convert", unexpected_conversion)
    with pytest.raises(ResourceLimitError, match="record budget"):
        ingest_file(path, spec=spec, work_dir=tmp_path)
    assert not list(tmp_path.rglob("accepted.arrow"))
    assert not list(tmp_path.rglob("ingestion.json"))


def test_record_tree_expansion_observes_cancellation():
    from equiframe.ingestion import _records

    checks = 0

    def cancelled():
        nonlocal checks
        checks += 1
        if checks == 4:
            raise ExecutionCancelled("cancelled during nested record expansion")

    with pytest.raises(ExecutionCancelled, match="nested record expansion"):
        _records([{"money": n} for n in range(20)], ("*",), check=cancelled)
    assert checks == 4


@pytest.mark.parametrize("exponent", ["999999999999999999999999", "-999999999999999999999999"])
@pytest.mark.parametrize("invalid_records", ["reject", "quarantine"])
def test_json_unrepresentable_decimal_exponent_obeys_record_policy(
    tmp_path, exponent, invalid_records
):
    path = tmp_path / "exponents.jsonl"
    path.write_text('{"money":1e' + exponent + '}\n{"money":2.00}', encoding="utf-8")
    spec = IngestionSpec(
        format="jsonl",
        fields=(
            FieldMapping(
                column=column("money", DecimalType(precision=10, scale=2)), path=("money",)
            ),
        ),
        invalid_records=invalid_records,
    )
    with localcontext() as context:
        context.traps[InvalidOperation] = True
        original = context.copy()
        result = ingest_file(path, spec=spec, work_dir=tmp_path)
        assert context.flags == original.flags
    assert result.quarantined[0].code == "json_decimal_outside_supported_range"
    if invalid_records == "reject":
        assert result.state == "rejected"
        assert result.output is None
        assert result.inspected_records == 1
    else:
        assert result.state == "quarantined"
        assert result.inspected_records == 2
        assert read_table(result.output).to_pylist() == [{"money": Decimal("2.00")}]


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
def test_empty_native_sum_preserves_scaled_zero_and_consumer_context(tmp_path, engine):
    dtype = DecimalType(precision=20, scale=20)
    source = pa.table({"money": pa.array([], type=pa.decimal128(20, 20))})
    schema = contract({"input": [column("money", dtype)]}, [column("result", dtype)])
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Aggregate(
                node_id="sum",
                source="scan",
                group_by=(),
                null_groups="retain",
                empty_sum="zero",
                measures=(
                    Measure(name="result", operation="sum", column="money", logical_type=dtype),
                ),
            ),
        ),
        output="sum",
    )
    with localcontext() as context:
        context.prec = 2
        context.Emin = -9
        context.Emax = 9
        context.rounding = ROUND_FLOOR
        context.clamp = 1
        original = context.copy()
        result = run(plan, schema, {"input": source}, engine, tmp_path)
        assert result.state == "completed", result.problem
        assert read_table(result.output.data)["result"].to_pylist() == [Decimal("0E-20")]
        assert context.flags == original.flags


@pytest.mark.parametrize("correct", [True, False])
def test_decimal_sum_rule_keeps_its_decision_under_the_callers_decimal_context(tmp_path, correct):
    dtype = DecimalType(precision=20, scale=2)
    schema = contract(
        {"input": [column("money", dtype, unit="USD")]},
        [column("result", DecimalType(precision=21, scale=2), unit="USD")],
        family="aggregations",
    )
    schema = schema.model_copy(
        update={
            "rules": (
                RuleSpec(
                    rule_id="sum",
                    revision=1,
                    specification=AggregateCheck(
                        table="input",
                        group_by=(),
                        measure="money",
                        function="sum",
                        output_table="output",
                        output_column="result",
                    ),
                    severity="error",
                    required=True,
                ),
            ),
        }
    )
    value = Decimal("1234567890123456.78")
    source = pa.table({"money": pa.array([value, value], type=pa.decimal128(20, 2))})
    output = pa.table(
        {
            "result": pa.array(
                [Decimal("2469135780246913.56" if correct else "2469135780246913.57")],
                type=pa.decimal128(21, 2),
            ),
        }
    )
    execution = captured(schema, {"input": source}, output, tmp_path / "capture")
    with localcontext() as context:
        context.prec = 2
        context.Emin = -9
        context.Emax = 9
        context.rounding = ROUND_FLOOR
        context.clamp = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        original = context.copy()
        result = evaluate_rules(execution, work_dir=tmp_path / "rules")
        assert result.complete
        assert result.decision == ("no_alert" if correct else "alert")
        assert context.flags == original.flags
        assert context.traps == original.traps
