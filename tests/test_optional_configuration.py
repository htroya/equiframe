"""Optional configuration uses None defaults, never falsey invalid caller values."""

import duckdb
import pyarrow as pa
import pytest
from pydantic import ValidationError
from rule_helpers import captured

import equiframe as ef

CASES = (
    ("compare", "options", ef.ComparisonOptions),
    ("compare", "policy", ef.ComparisonPolicy),
    ("capture_duckdb", "options", ef.DuckDBCaptureOptions),
    ("evaluate_rules", "options", ef.RuleOptions),
    ("profile_execution", "options", ef.ProfileOptions),
    ("reduce_case", "options", ef.ReductionOptions),
    ("comparison_report", "options", ef.ReportOptions),
    ("write_comparison_report", "options", ef.ReportOptions),
    ("verify", "options", ef.ComparisonOptions),
    ("verify", "policy", ef.ComparisonPolicy),
)


@pytest.fixture
def invocation(tmp_path):
    table = pa.table({"n": [1]})
    declaration = ef.infer_diff_contract(table.schema)
    contract = declaration.spec.contract
    execution = captured(contract, {"source": table}, table, tmp_path / "fixture")
    compared = ef.diff(table, table, work_dir=tmp_path / "comparison_fixture")
    output = tmp_path / "requested_output"
    callbacks = []

    def predicate(_):
        callbacks.append("predicate")
        return ef.ReductionObservation(preconditions="satisfied", failure_signature="synthetic")

    def invoke(name, argument, selected):
        kwargs = {argument: selected}
        if name == "compare":
            return ef.compare(
                ef.ArrowInput(table),
                ef.ArrowInput(table),
                contract=contract,
                work_dir=output,
                **kwargs,
            )
        if name == "capture_duckdb":
            return ef.capture_duckdb("SELECT 1::BIGINT AS n", work_dir=output, **kwargs)
        if name == "evaluate_rules":
            return ef.evaluate_rules(execution, work_dir=output, **kwargs)
        if name == "profile_execution":
            spec = ef.ProfileSpec(
                family=contract.family,
                features=(ef.ProfileFeature(name="rows", metric="log_filas", table="result"),),
            )
            return ef.profile_execution(execution, spec=spec, work_dir=output, **kwargs)
        if name == "reduce_case":
            return ef.reduce_case(
                {"source": ef.ArrowInput(table)},
                predicate=predicate,
                predicate_version="synthetic.1",
                failure_signature="synthetic",
                work_dir=output,
                **kwargs,
            )
        if name == "comparison_report":
            return ef.comparison_report(compared, **kwargs)
        if name == "write_comparison_report":
            return ef.write_comparison_report(compared, output, **kwargs)
        assert name == "verify"
        return ef.verify(
            {"observed": execution.output.data}, contract=contract, work_dir=output, **kwargs
        )

    return invoke, output, callbacks


@pytest.mark.parametrize("name,argument,model", CASES)
@pytest.mark.parametrize("invalid", [False, 0, [], (), {"unknown_option": 1}])
def test_invalid_configuration_fails_before_work(
    invocation, monkeypatch, name, argument, model, invalid
):
    invoke, output, callbacks = invocation

    def unexpected_connection(*args, **kwargs):
        pytest.fail("invalid options must be rejected before opening a SQL connection")

    monkeypatch.setattr(duckdb, "connect", unexpected_connection)
    with pytest.raises(ValidationError):
        invoke(name, argument, invalid)
    assert not output.exists()
    assert not callbacks


@pytest.mark.parametrize("name,argument,model", CASES)
@pytest.mark.parametrize("kind", ["none", "mapping", "model"])
def test_valid_default_configuration_is_unchanged(invocation, name, argument, model, kind):
    invoke, output, _ = invocation
    selected = None if kind == "none" else {} if kind == "mapping" else model()
    result = invoke(name, argument, selected)
    if name == "compare":
        assert result.state == "equivalent"
        assert (result.options if argument == "options" else result.spec.policy) == model()
    elif name == "capture_duckdb":
        assert ef.read_table(result.data).to_pylist() == [{"n": 1}]
    elif name == "evaluate_rules":
        assert result.options == model()
        assert result.decision == "not_evaluable"  # The fixture has no operational rules.
    elif name == "profile_execution":
        assert result.options == model() and result.complete
    elif name == "reduce_case":
        assert result.options == model() and result.baseline_verified
    elif name in ("comparison_report", "write_comparison_report"):
        assert result.state == "equivalent"
        assert result.options.max_examples == model().max_examples
    else:
        assert result.publishable
        assert (
            result.comparison_options if argument == "options" else result.comparison_policy
        ) == model()
    if name != "comparison_report":
        assert output.is_dir()
