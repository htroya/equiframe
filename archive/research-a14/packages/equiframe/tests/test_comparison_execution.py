"""Compare real independent engines and independently specified expected tables."""

import runpy
from pathlib import Path

import pyarrow as pa
import pytest

import equiframe as ef

DEMO = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "execute_native.py"))
POLICY = DEMO["COMPARISON_POLICY"]


def execute(case, engine, tmp_path, inputs=None):
    return ef.execute(
        ef.ExecutionPlan(
            contract=case.contract, engine=engine, transformation_id=case.contract.family
        ),
        source=ef.LocalDataSource(
            {n: ef.ArrowInput(t) for n, t in (inputs or case.inputs).items()}
        ),
        registry=DEMO["registry"](),
        work_dir=tmp_path,
    )


@pytest.mark.parametrize("case", DEMO["cases"](), ids=lambda c: c.contract.family)
def test_three_real_engines_same_inputs_and_independent_expected(tmp_path, case):
    before = {n: t.to_pylist() for n, t in case.inputs.items()}
    expected = ef.ArrowInput(DEMO["expected_table"](case))
    runs = [execute(case, engine, tmp_path) for engine in ("pandas", "polars", "duckdb")]
    for result in runs:
        assert result.state == "completed"
        comparison = ef.compare(
            result,
            expected,
            contract=case.contract,
            policy=POLICY,
            reference="expected",
            work_dir=tmp_path,
        )
        assert comparison.state == "equivalent", comparison.diagnostics or comparison.examples
    for i, left in enumerate(runs):
        for right in runs[i + 1 :]:
            assert [(t.name, t.data.sha256) for t in left.inputs] == [
                (t.name, t.data.sha256) for t in right.inputs
            ]
            comparison = ef.compare(
                left, right, contract=case.contract, policy=POLICY, work_dir=tmp_path
            )
            assert comparison.state == "equivalent", comparison.diagnostics or comparison.examples
    for name, table in case.inputs.items():
        DEMO["assert_expected"](table.to_pylist(), before[name])


def test_execution_state_contract_evidence_and_index_are_verified(tmp_path):
    case = DEMO["cases"]()[0]
    result = execute(case, "pandas", tmp_path)
    expected = ef.ArrowInput(DEMO["expected_table"](case))

    def compare(value, **kw):
        return ef.compare(value, expected, contract=case.contract, work_dir=tmp_path, **kw)

    assert compare(result).diagnostics[0].code == "unsupported_capability"
    assert compare(result, policy=POLICY).state == "equivalent"
    failed = result.model_copy(update={"state": "failed"})
    assert compare(failed, policy=POLICY).state == "not_evaluable"
    forged = result.model_copy(update={"contract_sha256": "0" * 64})
    assert compare(forged, policy=POLICY).state == "not_evaluable"
    assert result.output is not None
    wrong = result.output.model_copy(update={"row_count": 123})
    assert (
        compare(result.model_copy(update={"output": wrong}), policy=POLICY).diagnostics[0].code
        == "invalid_artifact"
    )
    assert compare(result.output, policy=POLICY).state == "equivalent"
    # Tamper the exact captured input, not an arbitrary unrelated output.
    from equiframe.local import local_path

    input_path = local_path(result.inputs[0].data)
    input_path.write_bytes(b"altered")
    assert compare(result, policy=POLICY).diagnostics[0].code == "invalid_artifact"


def test_different_inputs_do_not_claim_comparable_execution(tmp_path):
    case = DEMO["cases"]()[0]
    left = execute(case, "polars", tmp_path)
    right = execute(case, "duckdb", tmp_path, {"items": case.inputs["items"].slice(0, 1)})
    result = ef.compare(left, right, contract=case.contract, policy=POLICY, work_dir=tmp_path)
    assert result.state == "not_evaluable" and not result.complete
    assert "execution_inputs_differ" in result.diagnostics[0].message


def test_compare_never_calls_transformation_or_full_table_reader(tmp_path, monkeypatch):
    case = DEMO["cases"]()[0]
    left = execute(case, "polars", tmp_path)
    right = execute(case, "duckdb", tmp_path)

    def prohibited(*a, **kw):
        raise AssertionError("comparison cannot rerun or materialize a whole table")

    import pyarrow.parquet as pq

    import equiframe.execution as execution
    import equiframe.tables as tables

    monkeypatch.setattr(tables, "read_table", prohibited)
    monkeypatch.setattr(pq, "read_table", prohibited)
    monkeypatch.setattr(execution, "execute", prohibited)
    assert (
        ef.compare(left, right, contract=case.contract, policy=POLICY, work_dir=tmp_path).state
        == "equivalent"
    )


def test_post_normalization_unique_wall_clock_key(tmp_path):
    stamp = ef.TimestampType(unit="s", timezone="Europe/Madrid")
    col = ef.ColumnSpec(
        name="time",
        logical_type=stamp,
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        temporal_policy=ef.TimestampPolicy(
            granularity="s",
            timezone="Europe/Madrid",
            naive="reject",
            comparison="wall_time",
            ambiguous="reject",
            closed="both",
        ),
    )
    schema = ef.TableSchema(
        columns=(col,),
        keys=(
            ef.KeySpec(
                name="time",
                columns=("time",),
                unique=True,
                incomplete="reject",
                scope=ef.GlobalKeyScope(),
            ),
        ),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="dst.key",
        revision=1,
        family="dates",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )
    # 00:30Z and 01:30Z both map to 02:30 in Madrid at the autumn transition.
    table = pa.table(
        {"time": pa.array([1729989000, 1729992600], type=pa.timestamp("s", "Europe/Madrid"))}
    )
    result = ef.compare(
        ef.ArrowInput(table), ef.ArrowInput(table), contract=contract, work_dir=tmp_path
    )
    codes = {v.code for v in ef.iter_differences(result.differences)}
    assert result.state == "different"
    assert "duplicate_normalized_key_time" in codes and "duplicate_raw_key_time" not in codes
