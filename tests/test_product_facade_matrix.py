"""Finite high-risk facade matrix with independent literals, not a universal claim.

Universe: 3 admitted eager inputs x 3 alignments x 2 batch sizes x 2 evidence
requirements x 3 expected verdicts. Every one of the 108 combinations runs.
No truth oracle is derived from another engine or from the comparator.
"""

from decimal import Decimal

import pandas as pd
import polars as pl
import pyarrow as pa
import pytest

import equiframe as ef


def declaration(alignment):
    columns = (
        ef.ColumnSpec(
            name="id",
            logical_type=ef.StringType(),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
        ),
        ef.ColumnSpec(
            name="amount",
            logical_type=ef.DecimalType(precision=8, scale=2),
            nullable=True,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
        ),
    )
    if alignment == "key":
        return ef.keyed_contract(columns, keys=["id"])
    if alignment == "sequence":
        return ef.sequence_contract(
            columns, by=[ef.SortSpec(column="id", direction="ascending", nulls="last")]
        )
    return ef.bag_contract(columns)


def native(rows, kind):
    table = pa.table(
        {
            "id": pa.array([row[0] for row in rows], pa.string()),
            "amount": pa.array([row[1] for row in rows], pa.decimal128(8, 2)),
        }
    )
    if kind == "pandas":
        return table.to_pandas(types_mapper=pd.ArrowDtype)
    if kind == "polars":
        return pl.from_arrow(table)
    return table


@pytest.mark.parametrize("kind", ["arrow", "pandas", "polars"])
@pytest.mark.parametrize("alignment", ["bag", "key", "sequence"])
@pytest.mark.parametrize("batch_rows", [1, 4])
@pytest.mark.parametrize("persisted", [False, True])
@pytest.mark.parametrize("verdict", ["equal", "compensated_cents", "null_to_zero"])
def test_finite_facade_risk_matrix(tmp_path, kind, alignment, batch_rows, persisted, verdict):
    expected_rows = [("001", Decimal("10.01")), ("002", Decimal("20.02")), ("é", None)]
    candidate_rows = list(expected_rows)
    if verdict == "compensated_cents":
        candidate_rows[:2] = [("001", Decimal("10.02")), ("002", Decimal("20.01"))]
        assert sum(row[1] for row in candidate_rows[:2]) == Decimal("30.03")
    elif verdict == "null_to_zero":
        candidate_rows[2] = ("é", Decimal("0.00"))
    work = tmp_path / "evidencia con acentos á"
    result = ef.diff(
        native(candidate_rows, kind),
        native(expected_rows, kind),
        contract=declaration(alignment),
        options=ef.ComparisonOptions(batch_rows=batch_rows),
        work_dir=work,
    )
    assert result.state == ("equivalent" if verdict == "equal" else "different")
    assert result.complete is True
    options = ef.ReportOptions(include_values=True, include_metadata=True)
    report_dir = tmp_path / "diagnóstico"
    report = ef.write_comparison_report(result, report_dir, options=options)
    assert ef.read_comparison_report(report_dir / "report.json") == report
    policy = ef.EquivalencePolicy(require_persisted_evidence=persisted)
    root = work / result.comparison_id if persisted else None
    decision = ef.equivalence_decision(result, policy=policy, evidence_root=root)
    assert decision.accepted is (verdict == "equal")
    if verdict == "equal":
        ef.assert_equivalent(result, policy=policy, evidence_root=root)
    else:
        with pytest.raises(ef.EquivalenceDifferentError):
            ef.assert_equivalent(result, policy=policy, evidence_root=root, report_path=report_dir)
    with pytest.raises(TypeError):
        bool(result)


@pytest.mark.parametrize("kind", ["arrow", "pandas", "polars"])
@pytest.mark.parametrize("alignment", ["bag", "key"])
@pytest.mark.parametrize("batch_rows", [1, 2, 5])
def test_permutation_and_batch_size_metamorphism(tmp_path, kind, alignment, batch_rows):
    rows = [("000", Decimal("0.00")), ("é", None), ("漢字", Decimal("-0.01"))]
    result = ef.diff(
        native(list(reversed(rows)), kind),
        native(rows, kind),
        contract=declaration(alignment),
        options=ef.ComparisonOptions(batch_rows=batch_rows),
        work_dir=tmp_path,
    )
    ef.assert_equivalent(result)


@pytest.mark.parametrize("kind", ["arrow", "pandas", "polars"])
def test_bag_duplicate_loss_cannot_hide_behind_equal_distinct_values(tmp_path, kind):
    expected = [("001", Decimal("1.00")), ("001", Decimal("1.00"))]
    result = ef.diff(
        native(expected[:1], kind),
        native(expected, kind),
        contract=declaration("bag"),
        work_dir=tmp_path,
    )
    assert result.complete and result.state == "different"
    with pytest.raises(ef.EquivalenceDifferentError):
        ef.assert_equivalent(result)


@pytest.mark.parametrize("mode", ["diagnostic", "detail", "reproduction"])
@pytest.mark.parametrize("include_values", [False, True])
@pytest.mark.parametrize("include_metadata", [False, True])
@pytest.mark.parametrize("require_exhaustive", [False, True])
def test_report_disclosure_finite_matrix(
    tmp_path, mode, include_values, include_metadata, require_exhaustive
):
    """All24 mode/disclosure/exhaustiveness cells, including invalid combinations."""
    from pydantic import ValidationError

    if mode == "reproduction" and not (include_values and include_metadata):
        with pytest.raises(ValidationError, match="reproduction requires"):
            ef.ReportOptions(
                mode=mode,
                include_values=include_values,
                include_metadata=include_metadata,
                require_exhaustive=require_exhaustive,
            )
        return
    result = ef.diff(
        pa.table({"id": ["SECRET_KEY"], "secret_amount": [11]}),
        pa.table({"id": ["SECRET_KEY"], "secret_amount": [10]}),
        keys=["id"],
        work_dir=tmp_path / "comparison",
    )
    options = ef.ReportOptions(
        mode=mode,
        include_values=include_values,
        include_metadata=include_metadata,
        require_exhaustive=require_exhaustive,
    )
    report = ef.write_comparison_report(
        result,
        tmp_path / "report",
        options=options,
        evidence_root=tmp_path / "comparison" / result.comparison_id,
    )
    rendered = report.to_text()
    assert report.options.include_values is include_values
    assert report.options.include_metadata is include_metadata
    if not include_values:
        assert "SECRET_KEY" not in rendered
    if not include_metadata:
        assert "secret_amount" not in rendered
    assert result.state == "different"
    with pytest.raises(ef.EquivalenceDifferentError):
        ef.assert_equivalent(result)


def test_facade_defaults_are_safe_without_explicit_boolean_overrides(tmp_path):
    result = ef.diff(
        pa.table({"id": ["PRIVATE"], "value": [2]}),
        pa.table({"id": ["PRIVATE"], "value": [1]}),
        keys=["id"],
        work_dir=tmp_path / "comparison",
    )
    report = ef.write_comparison_report(result, tmp_path / "report")
    assert report.options.include_values is False
    assert report.options.include_metadata is False
    assert report.options.require_exhaustive is False
    assert "PRIVATE" not in report.to_text()
    assert ef.EquivalencePolicy().require_persisted_evidence is False
    with pytest.raises(ef.EquivalenceDifferentError):
        ef.assert_equivalent(result)
