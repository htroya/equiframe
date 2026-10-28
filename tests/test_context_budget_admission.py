"""Truthy strings and numeric false values cannot select or disable row budgets."""

import pyarrow as pa
import pytest
from pydantic import ValidationError

import equiframe as ef


def context(root):
    column = ef.ColumnSpec(
        name="id",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    contract = ef.bag_contract((column,)).spec.contract
    plan = ef.ExecutionPlan(
        contract=contract,
        engine="pandas",
        transformation_id="identity",
        options=ef.ExecutionOptions(max_input_rows=1, max_output_rows=4),
    )
    return ef.RunContext(
        "run-owned",
        "execution-owned",
        plan,
        root,
        ef.LocalArtifactStore(root),
        ef.CancellationToken(),
        None,
    )


@pytest.mark.parametrize("name", ["output", "enforce_rows"])
@pytest.mark.parametrize("value", [0, 1, None, "false", "true", []])
def test_non_boolean_budget_flags_reject_before_any_capture(tmp_path, name, value):
    run = context(tmp_path)
    args = {"output": False, "enforce_rows": True, name: value}
    with pytest.raises(ef.InvalidExecutionInput, match="explicit booleans"):
        run.check_table(pa.table({"id": [1, 1, 2]}), **args)
    assert not run.captured_inputs and run.captured_output is None


def test_explicit_flags_keep_separate_input_output_and_transport_controls(tmp_path):
    run = context(tmp_path)
    table = pa.table({"id": [1, 1, 2]})
    with pytest.raises(ef.ResourceLimitError):
        run.check_table(table, output=False)
    run.check_table(table, output=True)
    run.check_table(table, output=False, enforce_rows=False)
    limited = run.plan.model_copy(update={"options": ef.ExecutionOptions(max_transport_bytes=1)})
    run.plan = ef.ExecutionPlan.model_validate(limited)
    with pytest.raises(ef.ResourceLimitError):
        run.check_table(table, output=False, enforce_rows=False)


@pytest.mark.parametrize("stage", [0, None, "", " padded "])
def test_invalid_measure_stage_never_enters_operation_or_changes_context(tmp_path, stage):
    run = context(tmp_path)
    calls = []
    with pytest.raises(ValidationError), run.measure(stage):
        calls.append("operation")
    assert not calls and not run.timings and run.stage == "preflight"


def test_valid_measure_restores_stage_and_records_real_timing(tmp_path):
    run = context(tmp_path)
    with run.measure("owned stage"):
        assert run.stage == "owned stage"
    assert run.stage == "preflight"
    assert run.timings[0].stage == "owned stage" and run.timings[0].seconds >= 0
