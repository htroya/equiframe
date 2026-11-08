"""Executable acceptance decisions, including invalid expectations and partial facts."""

import json
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

import equiframe as ef
from equiframe.cli import app


def decision_contract(*, unique: bool = False) -> ef.Contract:
    schema = ef.TableSchema(
        columns=(
            ef.ColumnSpec(
                name="id",
                logical_type=ef.IntegerType(bits=64, signed=True),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="identifier"),
            ),
        ),
        keys=(
            ef.KeySpec(
                name="primary",
                columns=("id",),
                unique=True,
                incomplete="reject",
                scope=ef.TableKeyScope(),
            ),
        )
        if unique
        else (),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="candidate.decision",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="source", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(),
    )


def table(values: list[int | None]) -> pa.Table:
    return pa.table({"id": pa.array(values, type=pa.int64())})


@pytest.mark.parametrize(
    ("left", "right", "expected", "state", "exit_code"),
    [
        ([1, 2], [2, 1], False, "equivalent", 0),
        ([1, 2], [1, 3], False, "different", 1),
        ([1, 2], [2, 1], True, "equivalent", 0),
        ([1, 2], [1, 3], True, "different", 1),
        ([None], [1], True, "different", 1),
        ([1], [None], False, "different", 1),
        ([1], [None], True, "not_evaluable", 3),
        ([None], [None], True, "not_evaluable", 3),
    ],
)
def test_cli_complete_decision_table(
    tmp_path: Path,
    left: list[int | None],
    right: list[int | None],
    expected: bool,
    state: str,
    exit_code: int,
) -> None:
    """Only complete equivalence may return success, even when both inputs are invalid."""
    spec = tmp_path / "spec.json"
    spec.write_text(ef.ComparisonSpec(contract=decision_contract()).model_dump_json())
    lhs, rhs = tmp_path / "left.parquet", tmp_path / "right.parquet"
    pq.write_table(table(left), lhs)
    pq.write_table(table(right), rhs)
    output = tmp_path / "evidence"
    args = ["compare", str(spec), str(lhs), str(rhs), "--output", str(output)]
    if expected:
        args.append("--expected")
    response = CliRunner().invoke(app, args)
    summary = json.loads(response.stdout)
    result = ef.read_comparison(output / summary["comparison_id"] / "comparison.json")
    assert result.state == state
    assert result.complete and result.counts.final
    assert summary["state"] == state and summary["complete"] is True
    if state == "not_evaluable":
        assert any(d.code == "invalid_expected" for d in result.diagnostics)
        assert result.counts.contract_violations > 0
        assert tuple(ef.iter_differences(result.differences))
    assert response.exit_code == exit_code, response.output


def test_cli_missing_capture_never_passes(tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(ef.ComparisonSpec(contract=decision_contract()).model_dump_json())
    lhs = tmp_path / "left.parquet"
    pq.write_table(table([1]), lhs)
    response = CliRunner().invoke(
        app,
        [
            "compare",
            str(spec),
            str(lhs),
            str(tmp_path / "missing.parquet"),
            "--output",
            str(tmp_path / "evidence"),
        ],
    )
    assert response.exit_code == 3
    assert json.loads(response.stdout)["state"] == "not_evaluable"
    assert json.loads(response.stdout)["complete"] is False


def test_partial_differences_do_not_become_complete_difference(tmp_path: Path) -> None:
    result = ef.compare(
        ef.ArrowInput(table([None, None, None])),
        ef.ArrowInput(table([1, 2, 3])),
        contract=decision_contract(),
        options=ef.ComparisonOptions(max_rows=2),
        work_dir=tmp_path,
    )
    assert result.state == "not_evaluable"
    assert not result.complete and not result.counts.final
    assert result.counts.difference_records == 2
    assert len(tuple(ef.iter_differences(result.differences))) == 2
    assert result.diagnostics[0].code == "resource_exhausted"


@pytest.mark.parametrize("reference", ["peer", "expected"])
def test_equivalent_partitions_do_not_prove_global_key_contract(
    tmp_path: Path, reference: Literal["peer", "expected"]
) -> None:
    """Partition verdicts cannot replace a global uniqueness/completeness check."""
    contract = decision_contract(unique=True)
    for number in range(2):
        part = ef.compare(
            ef.ArrowInput(table([1])),
            ef.ArrowInput(table([1])),
            contract=contract,
            reference=reference,
            work_dir=tmp_path / f"part-{number}",
        )
        assert part.state == "equivalent" and part.complete
    whole = ef.compare(
        ef.ArrowInput(table([1, 1])),
        ef.ArrowInput(table([1, 1])),
        contract=contract,
        reference=reference,
        work_dir=tmp_path / "whole",
    )
    assert whole.state == ("not_evaluable" if reference == "expected" else "different")
    assert whole.complete and whole.counts.final
    assert whole.counts.contract_violations > 0
    if reference == "expected":
        assert any(d.code == "invalid_expected" for d in whole.diagnostics)


def test_known_partition_difference_does_not_override_unfinished_scope(tmp_path: Path) -> None:
    contract = decision_contract()
    observed = ef.compare(
        ef.ArrowInput(table([1])),
        ef.ArrowInput(table([2])),
        contract=contract,
        work_dir=tmp_path / "observed",
    )
    assert observed.state == "different" and observed.complete
    whole = ef.compare(
        ef.ArrowInput(table([1, 3])),
        ef.ArrowInput(table([2, 3])),
        contract=contract,
        options=ef.ComparisonOptions(max_rows=1),
        work_dir=tmp_path / "unfinished",
    )
    assert whole.state == "not_evaluable"
    assert not whole.complete and not whole.counts.final


@pytest.mark.parametrize("payload", ["{", '{"unexpected":true}'])
def test_cli_invalid_spec_exits_2_without_success_json(tmp_path: Path, payload: str) -> None:
    spec = tmp_path / "invalid.json"
    spec.write_text(payload)
    response = CliRunner().invoke(
        app,
        [
            "compare",
            str(spec),
            str(tmp_path / "left"),
            str(tmp_path / "right"),
            "--output",
            str(tmp_path / "evidence"),
        ],
    )
    assert response.exit_code == 2
    assert response.stdout == ""
    assert response.stderr.splitlines()[0] == "invalid_input"
    assert not (tmp_path / "evidence").exists()


def test_cli_unwritable_evidence_exits_3_without_success_json(tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(ef.ComparisonSpec(contract=decision_contract()).model_dump_json())
    source = tmp_path / "input.parquet"
    pq.write_table(table([1]), source)
    output = tmp_path / "occupied"
    output.write_bytes(b"existing file must be preserved")
    response = CliRunner().invoke(
        app,
        ["compare", str(spec), str(source), str(source), "--output", str(output)],
    )
    assert response.exit_code == 3
    assert response.stdout == ""
    assert response.stderr.splitlines()[0] == "operation_failed"
    assert output.read_bytes() == b"existing file must be preserved"
