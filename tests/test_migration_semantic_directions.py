"""Synthetic, independently enumerated semantics in every directed engine pair."""

from decimal import Decimal
from itertools import permutations

import pyarrow as pa
import pytest
from test_migration import run, spy_adapter, table
from test_migration_backends import INT, column, contract

import equiframe as ef
from equiframe.evidence import describe_file

DIRECTIONS = tuple(permutations(("pandas", "polars", "duckdb"), 2))


def semantic_case(family):
    if family == "nulls_types":
        columns = [column("id", INT, nullable=False), column("v", ef.FloatType(bits=64))]
        inputs = {
            "input": pa.table(
                {
                    "id": [1, 2, 3, 4],
                    "v": pa.array([None, float("nan"), 0.0, 1.5], from_pandas=False),
                }
            )
        }
        schema = contract({"input": columns}, columns)
        plan = ef.RelationalPlan(nodes=(ef.Scan(node_id="scan", table="input"),), output="scan")
        expected = inputs["input"]
        keys = ("id",)
    elif family == "joins":
        left_columns = [column("id", INT), column("row", ef.StringType(), nullable=False)]
        right_columns = [column("id", INT), column("row", ef.StringType(), nullable=False)]
        outputs = [
            *left_columns,
            column("right.id", INT),
            column("right.row", ef.StringType()),
        ]
        schema = contract({"left": left_columns, "right": right_columns}, outputs, family=family)
        inputs = {
            "left": pa.table({"id": [1, 1, None, 2], "row": ["a", "b", "n", "z"]}),
            "right": pa.table({"id": [1, 1, None], "row": ["r1", "r2", "rn"]}),
        }
        plan = ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="left", table="left"),
                ef.Scan(node_id="right", table="right"),
                ef.EquiJoin(
                    node_id="joined",
                    left="left",
                    right="right",
                    keys=(ef.JoinKey(left="id", right="id"),),
                    how="left",
                    null_keys="never",
                ),
            ),
            output="joined",
        )
        # Enumerated occurrences preserve the many-to-many Cartesian matches;
        # NULL never matches NULL, and unmatched left rows remain exactly once.
        expected = pa.table(
            {
                "id": [1, 1, 1, 1, None, 2],
                "row": ["a", "a", "b", "b", "n", "z"],
                "right.id": pa.array([1, 1, 1, 1, None, None], type=pa.int64()),
                "right.row": ["r1", "r2", "r1", "r2", None, None],
            }
        )
        keys = ("row", "right.row")
    else:
        money = ef.DecimalType(precision=10, scale=2)
        total = ef.DecimalType(precision=12, scale=2)
        schema = contract(
            {
                "input": [
                    column("currency", ef.StringType(), nullable=False),
                    column("amount", money, unit="currency_amount"),
                ]
            },
            [
                column("currency", ef.StringType(), nullable=False),
                column("total", total, unit="currency_amount"),
                column("rows", INT, nullable=False, unit="rows"),
            ],
            family=family,
        )
        inputs = {
            "input": pa.table(
                {
                    "currency": ["USD", "USD", "EUR", "EUR", "JPY"],
                    "amount": pa.array(
                        [Decimal("1.50"), Decimal("2.25"), None, None, Decimal("900.00")],
                        type=pa.decimal128(10, 2),
                    ),
                }
            )
        }
        plan = ef.RelationalPlan(
            nodes=(
                ef.Scan(node_id="scan", table="input"),
                ef.Aggregate(
                    node_id="totals",
                    source="scan",
                    group_by=("currency",),
                    measures=(
                        ef.Measure(
                            name="total",
                            operation="sum",
                            column="amount",
                            logical_type=total,
                            unit="currency_amount",
                        ),
                        ef.Measure(
                            name="rows", operation="count_rows", logical_type=INT, unit="rows"
                        ),
                    ),
                    null_groups="retain",
                    empty_sum="null",
                ),
            ),
            output="totals",
        )
        expected = pa.table(
            {
                "currency": ["USD", "EUR", "JPY"],
                "total": pa.array(
                    [Decimal("3.75"), None, Decimal("900.00")], type=pa.decimal128(12, 2)
                ),
                "rows": pa.array([2, 2, 1], type=pa.int64()),
            }
        )
        keys = ("currency",)
    output = schema.output.model_copy(
        update={
            "schema_spec": schema.output.schema_spec.model_copy(
                update={
                    "keys": (
                        ef.KeySpec(
                            name="output_key",
                            columns=keys,
                            unique=True,
                            incomplete="allow" if family == "joins" else "reject",
                            scope=ef.TableKeyScope(),
                        ),
                    )
                }
            )
        }
    )
    schema = ef.Contract.model_validate(
        {
            **schema.model_dump(),
            "output": output,
            "rules": (
                ef.RuleSpec(
                    rule_id="output_schema",
                    revision=1,
                    required=True,
                    severity="error",
                    specification=ef.SchemaCheck(table="output"),
                ),
                ef.RuleSpec(
                    rule_id="output_key",
                    revision=1,
                    required=True,
                    severity="error",
                    specification=ef.KeyCheck(table="output", key="output_key"),
                ),
                ef.RuleSpec(
                    rule_id="output_cardinality",
                    revision=1,
                    required=True,
                    severity="error",
                    specification=ef.CardinalityCheck(
                        table="output", minimum=expected.num_rows, maximum=expected.num_rows
                    ),
                ),
            ),
        }
    )
    return schema, plan, inputs, expected


@pytest.mark.parametrize("source,target", DIRECTIONS)
@pytest.mark.parametrize("family", ("nulls_types", "joins", "aggregations"))
def test_semantic_native_directions_and_independent_validation_scope(
    tmp_path, source, target, family
):
    schema, plan, inputs, expected = semantic_case(family)
    adapters = {engine: spy_adapter(engine) for engine in (source, target)}
    result = ef.migrate(
        ef.MigrationSpec(
            contract=schema,
            ir=plan,
            source_engine=source,
            target_engine=target,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated index is not a logical key."
            ),
        ),
        source=ef.LocalDataSource({name: ef.ArrowInput(data) for name, data in inputs.items()}),
        expected=ef.ArrowInput(expected),
        adapters=adapters,
        work_dir=tmp_path,
    )
    assert result.complete and result.exit_code == 0, ef.migration_summary(result)
    assert [adapter.calls for adapter in adapters.values()] == [1, 1]
    assert result.source.execution.plan.engine == source
    assert result.target.execution.plan.engine == target
    assert all(child.rules.decision == "no_alert" for child in (result.source, result.target))
    summary = ef.migration_summary(result)
    assert (summary["source_engine"], summary["target_engine"]) == (source, target)
    assert summary["expected_output_comparison"] == "correct"
    assert summary["independent_verification"] == "correct"  # Historical key retained.
    assert summary["equiframe_verify"]["status"] == "not_established"
    assert summary["equiframe_verify"]["procedure"] == "EquiFrame Verify"
    assert all(
        c["state"] == "equivalent" and c["complete"] for c in summary["comparisons"].values()
    )
    html = ef.render_migration_report(result)
    assert "Supplied expected comparison: correct" in html
    assert "EquiFrame Verify (O): not established" in html
    assert "Independent verification: correct" not in html
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_reports_separate_no_expected_from_unestablished_equiframe_verify(tmp_path):
    result = run(tmp_path)
    summary = ef.migration_summary(result)
    assert summary["expected_output_comparison"] == "not_requested"
    assert summary["comparisons"]["source_expected"]["state"] == "not_requested"
    assert summary["comparisons"]["target_expected"]["state"] == "not_requested"
    assert summary["equiframe_verify"]["status"] == "not_established"


def test_reader_preserves_legacy_complete_reports_without_claiming_review(tmp_path):
    import json

    result = run(tmp_path, expected=ef.ArrowInput(table()))
    directory = tmp_path / result.migration_id
    summary = ef.migration_summary(result)
    for name in ("expected_output_comparison", "comparisons", "equiframe_verify"):
        del summary[name]
    (directory / "report.json").write_text(json.dumps(summary), encoding="utf-8")
    html = (
        ef.render_migration_report(result)
        .replace(". Supplied expected comparison: ", ". Independent verification: ")
        .replace(
            "<p>EquiFrame Verify (O): not established. Comparing supplied expected content "
            "does not establish independent expected authorship or collect two independent "
            "human reviews.</p>",
            "",
        )
    )
    (directory / "report.html").write_text(html, encoding="utf-8")
    updated = ef.MigrationResult.model_validate(
        {
            **result.model_dump(),
            "evidence": tuple(
                describe_file(path, directory)
                for path in sorted(directory.rglob("*"))
                if path.is_file() and path.name != "migration.json"
            ),
        }
    )
    (directory / "migration.json").write_text(updated.model_dump_json(), encoding="utf-8")
    assert ef.read_migration(directory) == updated
    assert ef.migration_summary(updated)["equiframe_verify"]["status"] == "not_established"
