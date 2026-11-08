"""Independent expectations for the six declared operational rule forms."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
from pydantic import ValidationError
from rule_helpers import captured

import equiframe as ef

EXAMPLES = Path(__file__).parents[1] / "examples"


def example(name: str) -> ef.Contract:
    document = json.loads((EXAMPLES / (name + ".json")).read_text(encoding="utf8"))
    for table in (*document["inputs"], document["output"]):
        for column in table["schema_spec"]["columns"]:
            column["allowed_values"] = []
    return ef.validate_contract(json.dumps(document))


def rule(
    name: str,
    specification: ef.RuleDefinition,
    *,
    applicability=(),
    required=True,
    severity="error",
) -> ef.RuleSpec:
    return ef.RuleSpec(
        rule_id=name,
        revision=1,
        specification=specification,
        severity=severity,
        required=required,
        applicability=applicability,
    )


def evaluate(contract, inputs, output, tmp_path, **kwargs):
    execution = captured(contract, inputs, output, tmp_path / "capture")
    return ef.evaluate_rules(execution, work_dir=tmp_path / "rules", **kwargs)


def codes(check):
    assert check.findings is not None
    return [item.code for item in ef.iter_rule_findings(check.findings)]


def test_aggregate_schema_key_and_cardinality_success_and_failure(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "rules": (
                rule("schema", ef.SchemaCheck(table="result")),
                rule("key", ef.KeyCheck(table="result", key="primary")),
                rule("count", ef.CardinalityCheck(table="result", minimum=1, maximum=2)),
                rule(
                    "sum",
                    ef.AggregateCheck(
                        table="source",
                        group_by=("currency",),
                        measure="amount",
                        function="sum",
                        output_table="result",
                        output_column="total",
                    ),
                ),
            )
        }
    )
    amount = pa.decimal128(38, 18)
    source = pa.table(
        {
            "currency": ["USD", "USD", "EUR"],
            "amount": pa.array(
                [
                    Decimal("1.000000000000000001"),
                    Decimal("2.000000000000000002"),
                    Decimal("4.000000000000000000"),
                ],
                type=amount,
            ),
        }
    )
    good = pa.table(
        {
            "currency": ["USD", "EUR"],
            "total": pa.array(
                [Decimal("3.000000000000000003"), Decimal("4.000000000000000000")], type=amount
            ),
        }
    )
    result = evaluate(contract, {"source": source}, good, tmp_path / "good")
    assert result.decision == "no_alert" and result.complete
    assert all(item.state == "satisfied" for item in result.rules)
    assert (
        ef.read_rule_evaluation(tmp_path / "good" / "rules" / result.evaluation_id / "rules.json")
        == result
    )
    bad = pa.table(
        {
            "currency": ["USD", "USD"],
            "total": pa.array(
                [Decimal("3.000000000000000004"), Decimal("4.000000000000000000")], type=amount
            ),
        }
    )
    result = evaluate(
        contract, {"source": source}, bad, tmp_path / "bad", options=ef.RuleOptions(max_examples=1)
    )
    assert result.decision == "alert" and result.complete
    assert "duplicate_key" in codes(result.rules[1])
    assert "aggregate_value" in codes(result.rules[3])
    assert "missing_group" in codes(result.rules[3])
    assert len(result.rules[3].examples) == 1
    assert len(codes(result.rules[3])) > len(result.rules[3].examples)


def test_join_relationship_and_both_unmatched_directions(tmp_path):
    base = example("joins")
    join = ef.JoinCheck(
        left_table="orders",
        right_table="suppliers",
        left_columns=("supplier_id",),
        right_columns=("supplier_id",),
        relationship="many_to_one",
        unmatched="reject",
    )
    contract = base.model_copy(update={"preconditions": (), "rules": (rule("join", join),)})
    orders = pa.table({"id": ["1", "2"], "supplier_id": ["A", "A"]})
    suppliers = pa.table({"supplier_id": ["A"], "name": ["Name"]})
    output = pa.table({"id": ["1", "2"], "supplier_id": ["A", "A"], "name": ["Name", "Name"]})
    assert (
        evaluate(
            contract, {"orders": orders, "suppliers": suppliers}, output, tmp_path / "good"
        ).decision
        == "no_alert"
    )
    suppliers_bad = pa.table({"supplier_id": ["A", "A", "B"], "name": ["N1", "N2", "N3"]})
    result = evaluate(
        contract, {"orders": orders, "suppliers": suppliers_bad}, output, tmp_path / "bad"
    )
    assert result.decision == "alert"
    assert set(codes(result.rules[0])) == {"join_cardinality", "unmatched_key"}
    orders_bad = pa.table({"id": ["1", "2"], "supplier_id": ["A", "Z"]})
    result = evaluate(
        contract,
        {"orders": orders_bad, "suppliers": suppliers},
        output,
        tmp_path / "left-unmatched",
    )
    assert result.decision == "alert" and "unmatched_key" in codes(result.rules[0])


def test_preconditions_missing_implementation_and_empty_set(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "preconditions": (
                ef.PreconditionSpec(
                    precondition_id="enough",
                    requirement=ef.CardinalityCheck(table="source", minimum=2),
                ),
            ),
            "rules": (
                rule(
                    "sum",
                    ef.AggregateCheck(
                        table="source",
                        group_by=("currency",),
                        measure="amount",
                        function="sum",
                        output_table="result",
                        output_column="total",
                    ),
                    applicability=("enough",),
                ),
            ),
        }
    )
    amount = pa.decimal128(38, 18)
    source = pa.table({"currency": ["USD"], "amount": pa.array([Decimal("1")], type=amount)})
    output = pa.table({"currency": ["USD"], "total": pa.array([Decimal("1")], type=amount)})
    result = evaluate(contract, {"source": source}, output, tmp_path / "skip")
    assert result.preconditions[0].state == "violated"
    assert result.rules[0].state == "not_applicable"
    assert result.decision == "not_evaluable"  # no active rule
    empty = base.model_copy(update={"rules": (), "preconditions": ()})
    assert (
        evaluate(empty, {"source": source}, output, tmp_path / "empty").decision == "not_evaluable"
    )
    registry = ef.RuleRegistry()
    result = evaluate(contract, {"source": source}, output, tmp_path / "missing", registry=registry)
    assert result.decision == "not_evaluable"
    assert "missing implementation" in result.preconditions[0].reason
    assert "unverified applicability" in result.rules[0].reason


def test_verified_false_precondition_is_decisive_even_when_another_is_unknown(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "preconditions": (
                ef.PreconditionSpec(
                    precondition_id="too_few",
                    requirement=ef.CardinalityCheck(table="source", minimum=2),
                ),
                ef.PreconditionSpec(
                    precondition_id="unknown_key",
                    requirement=ef.KeyCheck(table="result", key="primary"),
                ),
            ),
            "rules": (
                rule(
                    "output_present",
                    ef.CardinalityCheck(table="result", minimum=1),
                    applicability=("too_few", "unknown_key"),
                ),
            ),
        }
    )
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    registry = ef.RuleRegistry()
    cardinality = ef.default_rule_registry().resolve("cardinality")
    assert cardinality is not None
    registry.register("cardinality", cardinality.revision, cardinality.evaluate)
    result = evaluate(contract, {"source": source}, output, tmp_path, registry=registry)
    assert result.preconditions[0].state == "violated"
    assert result.preconditions[1].state == "not_evaluable"
    assert result.rules[0].state == "not_applicable"
    assert result.rules[0].reason == "verified false precondition: too_few"


def test_limits_cancellation_failure_and_tampering(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={"preconditions": (), "rules": (rule("source", ef.SchemaCheck(table="source")),)}
    )
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    execution = captured(contract, {"source": source}, output, tmp_path / "capture")
    limited = ef.evaluate_rules(
        execution, options=ef.RuleOptions(max_work=1), work_dir=tmp_path / "limited"
    )
    assert limited.decision == "not_evaluable" and not limited.complete
    bytes_limited = ef.evaluate_rules(
        execution, options=ef.RuleOptions(max_artifact_bytes=1), work_dir=tmp_path / "bytes-limited"
    )
    assert (
        bytes_limited.decision == "not_evaluable"
        and bytes_limited.diagnostic == "rule_inputs_unavailable"
    )
    token = ef.CancellationToken()
    token.cancel()
    cancelled = ef.evaluate_rules(execution, cancellation=token, work_dir=tmp_path / "cancelled")
    assert cancelled.decision == "not_evaluable" and cancelled.diagnostic
    tampered = execution.inputs[0].data
    from equiframe.local import local_path

    local_path(tampered).write_bytes(b"tampered")
    invalid = ef.evaluate_rules(execution, work_dir=tmp_path / "invalid")
    assert invalid.decision == "not_evaluable" and invalid.diagnostic == "rule_inputs_unavailable"
    failed = execution.model_copy(
        update={
            "state": "failed",
            "problem": ef.ExecutionProblem(
                code="failed", stage="test", exception_type="RuntimeError", message="failed"
            ),
        }
    )
    assert ef.evaluate_rules(failed, work_dir=tmp_path / "failed").decision == "not_evaluable"


def test_fingerprint_tracks_contract_code_and_configuration():
    contract = example("aggregations")
    registry = ef.default_rule_registry()
    original = ef.rule_set_fingerprint(contract, registry, ef.RuleOptions())
    assert original != ef.rule_set_fingerprint(contract, registry, ef.RuleOptions(max_examples=1))
    changed = contract.model_copy(update={"revision": 2})
    assert original != ef.rule_set_fingerprint(changed, registry, ef.RuleOptions())
    alternative = ef.RuleRegistry()

    def replacement(definition, context):
        context.checkpoint()

    alternative.register("schema", 2, replacement)
    assert original != ef.rule_set_fingerprint(contract, alternative, ef.RuleOptions())


def test_comparison_equivalent_manifest_rejects_contradictory_counts(tmp_path):
    base = example("aggregations")
    table = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    comparison = ef.compare(
        ef.ArrowInput(table), ef.ArrowInput(table), contract=base, work_dir=tmp_path
    )
    assert comparison.state == "equivalent"
    manifest = tmp_path / comparison.comparison_id / "comparison.json"
    document = json.loads(manifest.read_text(encoding="utf8"))
    document["counts"]["right_rows"] = 2
    manifest.write_text(json.dumps(document), encoding="utf8")
    with pytest.raises(ValidationError):
        ef.read_comparison(manifest)


def test_rule_manifest_structure_and_artifact_verification_are_distinct(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "preconditions": (),
            "rules": (rule("count", ef.CardinalityCheck(table="result", minimum=2)),),
        }
    )
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    result = evaluate(contract, {"source": source}, output, tmp_path)
    manifest = tmp_path / "rules" / result.evaluation_id / "rules.json"
    assert ef.read_rule_evaluation(manifest) == result
    assert result.rules[0].findings is not None
    from equiframe.local import local_path

    local_path(result.rules[0].findings).write_bytes(b"changed")
    assert ef.read_rule_evaluation(manifest) == result
    with pytest.raises(ef.ArtifactIntegrityError):
        list(ef.iter_rule_findings(result.rules[0].findings))


def test_rule_manifest_rejects_contradictory_decision_and_completeness(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "preconditions": (),
            "rules": (rule("count", ef.CardinalityCheck(table="result", minimum=2)),),
        }
    )
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    result = evaluate(contract, {"source": source}, output, tmp_path)
    assert result.decision == "alert" and result.complete
    manifest = tmp_path / "rules" / result.evaluation_id / "rules.json"
    original = json.loads(manifest.read_text(encoding="utf8"))
    for changes in (
        {"decision": "not_evaluable"},
        {"complete": False},
        {"decision": "no_alert"},
    ):
        manifest.write_text(json.dumps(original | changes), encoding="utf8")
        with pytest.raises(ValidationError):
            ef.read_rule_evaluation(manifest)


def test_schema_rule_reports_unsupported_captured_type_as_violation(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={"preconditions": (), "rules": (rule("schema", ef.SchemaCheck(table="result")),)}
    )
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {
            "currency": pa.array([0], type=pa.timestamp("s", tz="Mars/Phobos")),
            "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18)),
        }
    )
    result = evaluate(contract, {"source": source}, output, tmp_path)
    assert result.decision == "alert" and result.complete
    assert "schema_type" in codes(result.rules[0])


def test_schema_absence_nan_and_date_interval(tmp_path):
    base = example("nulls_types")
    columns = list(base.output.schema_spec.columns)
    columns[2] = columns[2].model_copy(
        update={"nullable": False, "nan_policy": ef.NaNPolicy(handling="forbid")}
    )
    output_spec = base.output.model_copy(
        update={
            "schema_spec": base.output.schema_spec.model_copy(update={"columns": tuple(columns)})
        }
    )
    base = base.model_copy(update={"output": output_spec})
    contract = base.model_copy(
        update={"preconditions": (), "rules": (rule("schema", ef.SchemaCheck(table="result")),)}
    )
    decimal = pa.decimal128(38, 18)

    def table(signals):
        return pa.table(
            {
                "id": ["0007", "x"],
                "text": ["", None],
                "signal": pa.array(signals, type=pa.float64(), from_pandas=False),
                "active": [True, False],
                "count": pa.array([0, 1], type=pa.int64()),
                "amount": pa.array([Decimal("1"), Decimal("2")], type=decimal),
            }
        )

    result = evaluate(
        contract, {"source": table([1.0, 2.0])}, table([float("nan"), None]), tmp_path / "null"
    )
    assert result.decision == "alert"
    assert {"nan_forbidden", "null_forbidden"} <= set(codes(result.rules[0]))

    dates = example("dates")
    dates = dates.model_copy(
        update={"preconditions": (), "rules": (rule("schema", ef.SchemaCheck(table="result")),)}
    )
    epoch = date(1970, 1, 1).toordinal() * 86400 * 10**9
    timestamp = ef.TimestampValue(
        value="2000-02-29T12:00:00.123456789-05:00", zone="America/Guayaquil"
    )
    ns = timestamp.nanoseconds(instant=True) - epoch

    def dated(day):
        return pa.table(
            {
                "id": ["0007"],
                "day": pa.array([day], type=pa.date32()),
                "instant": pa.array([ns], type=pa.timestamp("ns", "America/Guayaquil")),
            }
        )

    assert (
        evaluate(
            dates,
            {"source": dated(date(2000, 2, 29))},
            dated(date(2000, 2, 29)),
            tmp_path / "date-good",
        ).decision
        == "no_alert"
    )
    outside = evaluate(
        dates, {"source": dated(date(2000, 2, 29))}, dated(date(2000, 3, 1)), tmp_path / "date-bad"
    )
    assert outside.decision == "alert" and "temporal_interval" in codes(outside.rules[0])


def test_count_rows_vs_present_values_and_empty_groups(tmp_path):
    text = ef.ColumnSpec(
        name="g",
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )
    number = ef.ColumnSpec(
        name="v",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    total = ef.ColumnSpec(
        name="n",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    input_schema = ef.TableSchema(
        columns=(text, number), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    output_schema = ef.TableSchema(
        columns=(text, total), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.count",
        revision=1,
        family="aggregations",
        inputs=(ef.TableSpec(name="source", schema_spec=input_schema),),
        output=ef.TableSpec(name="result", schema_spec=output_schema),
        preconditions=(),
        rules=(
            rule(
                "present",
                ef.AggregateCheck(
                    table="source",
                    group_by=("g",),
                    measure="v",
                    function="count",
                    output_table="result",
                    output_column="n",
                ),
            ),
        ),
    )
    source = pa.table({"g": ["A", "A", "B"], "v": pa.array([None, 0, None], type=pa.int64())})
    output = pa.table({"g": ["A", "B"], "n": pa.array([1, 0], type=pa.int64())})
    assert (
        evaluate(contract, {"source": source}, output, tmp_path / "present").decision == "no_alert"
    )
    wrong = pa.table({"g": ["A", "B"], "n": pa.array([2, 1], type=pa.int64())})
    assert evaluate(contract, {"source": source}, wrong, tmp_path / "rows").decision == "alert"
    empty_source = source.slice(0, 0)
    empty_output = output.slice(0, 0)
    assert (
        evaluate(contract, {"source": empty_source}, empty_output, tmp_path / "empty").decision
        == "no_alert"
    )


def test_order_and_incomplete_key_policy(tmp_path):
    base = example("duplicates_order")
    contract = base.model_copy(
        update={
            "preconditions": (),
            "rules": (rule("order", ef.OrderCheck(table="result", columns=("position",))),),
        }
    )
    good = pa.table({"id": ["0007", "0007"], "position": pa.array([0, 1], type=pa.int64())})
    bad = pa.table({"id": ["0007", "0007"], "position": pa.array([1, 0], type=pa.int64())})
    assert evaluate(contract, {"source": good}, good, tmp_path / "good").decision == "no_alert"
    result = evaluate(contract, {"source": good}, bad, tmp_path / "bad")
    assert result.decision == "alert" and "out_of_order" in codes(result.rules[0])


def test_alert_survives_an_unavailable_rule(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "preconditions": (),
            "rules": (
                rule(
                    "count",
                    ef.CardinalityCheck(table="result", minimum=2),
                    required=False,
                    severity="info",
                ),
                rule("schema", ef.SchemaCheck(table="result")),
            ),
        }
    )
    registry = ef.RuleRegistry()
    registry.register("cardinality", 1, ef.default_rule_registry().resolve("cardinality").evaluate)
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    result = evaluate(contract, {"source": source}, output, tmp_path, registry=registry)
    assert result.decision == "alert" and not result.complete
    assert result.rules[0].state == "violated" and result.rules[0].severity == "info"
    assert result.rules[1].state == "not_evaluable"


def test_key_check_requires_compatible_captured_column_type(tmp_path):
    column = ef.ColumnSpec(
        name="id",
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )
    schema = ef.TableSchema(
        columns=(column,),
        keys=(
            ef.KeySpec(
                name="primary",
                columns=("id",),
                unique=True,
                incomplete="reject",
                scope=ef.TableKeyScope(),
            ),
        ),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.key_type",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(rule("key", ef.KeyCheck(table="result", key="primary")),),
    )
    result = evaluate(
        contract,
        {"source": pa.table({"id": ["a"]})},
        pa.table({"id": pa.array([1], type=pa.int64())}),
        tmp_path,
    )
    assert result.decision == "not_evaluable" and not result.complete
    assert result.rules[0].reason == "rule_evaluation_failed"


def test_key_scope_and_incomplete_policy(tmp_path):
    tenant = ef.ColumnSpec(
        name="tenant",
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )
    identifier = tenant.model_copy(update={"name": "id", "nullable": True})
    key = ef.KeySpec(
        name="primary",
        columns=("id",),
        unique=True,
        incomplete="allow",
        scope=ef.ColumnKeyScope(columns=("tenant",)),
    )
    schema = ef.TableSchema(
        columns=(tenant, identifier), keys=(key,), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.scoped_key",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(rule("key", ef.KeyCheck(table="result", key="primary")),),
    )
    good = pa.table({"tenant": ["A", "A", "A", "B"], "id": [None, None, "x", "x"]})
    assert evaluate(contract, {"source": good}, good, tmp_path / "good").decision == "no_alert"
    bad = pa.table({"tenant": ["A", "A", "A", "A"], "id": [None, None, "x", "x"]})
    result = evaluate(contract, {"source": good}, bad, tmp_path / "duplicate")
    assert result.decision == "alert" and codes(result.rules[0]) == ["duplicate_key"]
    reject = key.model_copy(update={"incomplete": "reject"})
    strict_schema = schema.model_copy(update={"keys": (reject,)})
    strict = contract.model_copy(
        update={
            "inputs": (contract.inputs[0].model_copy(update={"schema_spec": strict_schema}),),
            "output": contract.output.model_copy(update={"schema_spec": strict_schema}),
        }
    )
    result = evaluate(strict, {"source": good}, good, tmp_path / "incomplete")
    assert result.decision == "alert" and codes(result.rules[0]) == [
        "incomplete_key",
        "incomplete_key",
    ]


def test_order_null_position_and_ties(tmp_path):
    position = ef.ColumnSpec(
        name="position",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="ordinal"),
    )
    schema = ef.TableSchema(
        columns=(position,),
        keys=(),
        multiplicity="preserve",
        order=ef.SignificantOrder(
            by=(ef.SortSpec(column="position", direction="ascending", nulls="last"),), ties="reject"
        ),
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.order",
        revision=1,
        family="duplicates_order",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(rule("order", ef.OrderCheck(table="result", columns=("position",))),),
    )
    source = pa.table({"position": pa.array([0, 1, None], type=pa.int64())})
    assert evaluate(contract, {"source": source}, source, tmp_path / "good").decision == "no_alert"
    tied = pa.table({"position": pa.array([0, 0, None], type=pa.int64())})
    assert "order_tie" in codes(
        evaluate(contract, {"source": source}, tied, tmp_path / "tie").rules[0]
    )
    misplaced = pa.table({"position": pa.array([None, 0], type=pa.int64())})
    assert "out_of_order" in codes(
        evaluate(contract, {"source": source}, misplaced, tmp_path / "null").rules[0]
    )


def test_global_empty_count_and_float_sum_tolerance(tmp_path):
    value = ef.ColumnSpec(
        name="value",
        logical_type=ef.FloatType(bits=64),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        nan_policy=ef.NaNPolicy(handling="distinct"),
        numeric_policy=ef.NumericPolicy(
            comparison="approximate",
            unit="unit",
            tolerance=ef.Tolerance(
                absolute="0.000001", unit="unit", justification="synthetic test"
            ),
        ),
    )
    output = value.model_copy(update={"name": "total"})
    source_schema = ef.TableSchema(
        columns=(value,), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    result_schema = ef.TableSchema(
        columns=(output,), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.float_sum",
        revision=1,
        family="aggregations",
        inputs=(ef.TableSpec(name="source", schema_spec=source_schema),),
        output=ef.TableSpec(name="result", schema_spec=result_schema),
        preconditions=(),
        rules=(
            rule(
                "sum",
                ef.AggregateCheck(
                    table="source",
                    group_by=(),
                    measure="value",
                    function="sum",
                    output_table="result",
                    output_column="total",
                ),
            ),
        ),
    )
    data = pa.table({"value": pa.array([0.1, 0.2], type=pa.float64())})
    good = pa.table({"total": pa.array([0.3], type=pa.float64())})
    assert (
        evaluate(contract, {"source": data}, good, tmp_path / "float-good").decision == "no_alert"
    )
    bad = pa.table({"total": pa.array([0.4], type=pa.float64())})
    assert evaluate(contract, {"source": data}, bad, tmp_path / "float-bad").decision == "alert"
    count_col = ef.ColumnSpec(
        name="n",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="rows"),
    )
    count_schema = ef.TableSchema(
        columns=(count_col,), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    count_contract = contract.model_copy(
        update={
            "output": ef.TableSpec(name="result", schema_spec=count_schema),
            "rules": (
                rule(
                    "count",
                    ef.AggregateCheck(
                        table="source",
                        group_by=(),
                        measure=None,
                        function="count",
                        output_table="result",
                        output_column="n",
                    ),
                ),
            ),
        }
    )
    empty = data.slice(0, 0)
    zero = pa.table({"n": pa.array([0], type=pa.int64())})
    assert (
        evaluate(count_contract, {"source": empty}, zero, tmp_path / "empty-good").decision
        == "no_alert"
    )
    missing = zero.slice(0, 0)
    assert "missing_group" in codes(
        evaluate(count_contract, {"source": empty}, missing, tmp_path / "empty-missing").rules[0]
    )


@pytest.mark.parametrize("function,expected", [("min", 1), ("max", 3)])
def test_min_max_and_all_missing_group(tmp_path, function, expected):
    group = ef.ColumnSpec(
        name="group",
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )
    measure = ef.ColumnSpec(
        name="amount",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=True,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="units"),
    )
    extreme = measure.model_copy(update={"name": "extreme"})
    source_schema = ef.TableSchema(
        columns=(group, measure), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    output_schema = ef.TableSchema(
        columns=(group, extreme), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.extreme",
        revision=1,
        family="aggregations",
        inputs=(ef.TableSpec(name="source", schema_spec=source_schema),),
        output=ef.TableSpec(name="result", schema_spec=output_schema),
        preconditions=(),
        rules=(
            rule(
                "extreme",
                ef.AggregateCheck(
                    table="source",
                    group_by=("group",),
                    measure="amount",
                    function=function,
                    output_table="result",
                    output_column="extreme",
                ),
            ),
        ),
    )
    source = pa.table(
        {"group": ["A", "A", "A", "B"], "amount": pa.array([3, None, 1, None], type=pa.int64())}
    )
    good = pa.table({"group": ["A", "B"], "extreme": pa.array([expected, None], type=pa.int64())})
    assert evaluate(contract, {"source": source}, good, tmp_path / "good").decision == "no_alert"
    bad = pa.table({"group": ["A", "B"], "extreme": pa.array([2, None], type=pa.int64())})
    assert evaluate(contract, {"source": source}, bad, tmp_path / "bad").decision == "alert"


def test_schema_and_total_can_miss_entity_amount_swap(tmp_path):
    text = ef.ColumnSpec(
        name="entity",
        logical_type=ef.StringType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
    )

    def money(name):
        return ef.ColumnSpec(
            name=name,
            logical_type=ef.DecimalType(precision=12, scale=2),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
        )

    source_schema = ef.TableSchema(
        columns=(text, money("amount")), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    output_schema = ef.TableSchema(
        columns=(money("entity_a"), money("entity_b"), money("total")),
        keys=(),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="test.limited_rules",
        revision=1,
        family="aggregations",
        inputs=(ef.TableSpec(name="source", schema_spec=source_schema),),
        output=ef.TableSpec(name="result", schema_spec=output_schema),
        preconditions=(),
        rules=(
            rule("schema", ef.SchemaCheck(table="result")),
            rule(
                "total",
                ef.AggregateCheck(
                    table="source",
                    group_by=(),
                    measure="amount",
                    function="sum",
                    output_table="result",
                    output_column="total",
                ),
            ),
        ),
    )
    amount = pa.decimal128(12, 2)
    source = pa.table(
        {
            "entity": ["A", "B"],
            "amount": pa.array([Decimal("10.00"), Decimal("20.00")], type=amount),
        }
    )

    def output(a, b):
        return pa.table(
            {
                "entity_a": pa.array([Decimal(a)], type=amount),
                "entity_b": pa.array([Decimal(b)], type=amount),
                "total": pa.array([Decimal("30.00")], type=amount),
            }
        )

    good, swapped = output("10.00", "20.00"), output("20.00", "10.00")
    assert (
        evaluate(contract, {"source": source}, swapped, tmp_path / "rules").decision == "no_alert"
    )
    comparison = ef.compare(
        ef.ArrowInput(good),
        ef.ArrowInput(swapped),
        contract=contract,
        work_dir=tmp_path / "comparison",
    )
    assert comparison.state == "different"


def test_catalog_fixes_five_rule_sets_and_code_configuration():
    catalog = json.loads((EXAMPLES / "rules" / "catalog-1.0.json").read_text(encoding="utf8"))
    assert {entry["family"] for entry in catalog["entries"]} == {
        "nulls_types",
        "joins",
        "duplicates_order",
        "aggregations",
        "dates",
    }
    options = ef.RuleOptions.model_validate(catalog["options"])
    registry = ef.default_rule_registry()
    for entry in catalog["entries"]:
        contract = ef.read_contract(EXAMPLES / "rules" / entry["contract_file"])
        assert contract.contract_id == entry["contract_id"]
        assert ef.contract_fingerprint(contract) == entry["contract_sha256"]
        assert ef.rule_set_fingerprint(contract, registry, options) == entry["rule_set_sha256"]
        assert entry["rules"] and entry["preconditions"] and entry["limitations"]


def test_finding_budget_marks_incomplete(tmp_path):
    base = example("aggregations")
    contract = base.model_copy(
        update={
            "preconditions": (),
            "rules": (
                rule("count", ef.CardinalityCheck(table="result", minimum=2)),
                rule("schema", ef.SchemaCheck(table="result")),
            ),
        }
    )
    source = pa.table(
        {"currency": ["USD"], "amount": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    output = pa.table(
        {"currency": ["USD"], "total": pa.array([Decimal("1")], type=pa.decimal128(38, 18))}
    )
    result = evaluate(
        contract, {"source": source}, output, tmp_path, options=ef.RuleOptions(max_evidence_bytes=1)
    )
    assert result.decision == "not_evaluable" and not result.complete
    assert result.rules[0].state == "not_evaluable"
