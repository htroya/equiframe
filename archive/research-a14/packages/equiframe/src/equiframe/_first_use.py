"""Small synthetic role exercises using the existing public comparison APIs."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


class Role(str, Enum):
    architect = "architect"
    scientist = "scientist"


class Case(str, Enum):
    good = "good"
    different = "different"
    not_evaluable = "not-evaluable"


def run_demo(role: Role, case: Case, output: Path) -> dict[str, Any]:
    """Save both report views before deciding; never replace existing evidence."""
    import equiframe as ef
    from equiframe.tables import require_dependency

    require_dependency("pyarrow", "arrow")
    import pyarrow as pa

    # Reserve the caller's new destination before performing any native work.
    output.mkdir(parents=True, exist_ok=False)
    if role == Role.architect:
        expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
        candidate = ef.capture_duckdb(
            "SELECT 'A' AS id, 10::BIGINT AS quantity UNION ALL SELECT 'B', $quantity::BIGINT",
            parameters={"quantity": 21 if case == Case.different else 20},
            work_dir=output / "capture",
        )
        declaration = ef.infer_diff_contract(expected.schema, keys=["id"])
    else:
        expected = pa.table(
            {
                "sample_id": ["0001", "0002", "0003"],
                "duration_s": pa.array(
                    [Decimal("1.250"), None, Decimal("1000000.001")], type=pa.decimal128(16, 3)
                ),
                "observed_at": pa.array([0, 1000000, None], type=pa.timestamp("us", tz="UTC")),
            }
        )
        # Candidate calculation is separate from the literal expected durations.
        durations = [Decimal("1250") / Decimal("1000"), None, Decimal("1000000001") / 1000]
        if case == Case.different:
            durations[0] = Decimal("1.251")
        candidate = pa.table(
            {
                "sample_id": ["0001", "0002", "0003"],
                "duration_s": pa.array(durations, type=pa.decimal128(16, 3)),
                "observed_at": pa.array([0, 1000000, None], type=pa.timestamp("us", tz="UTC")),
            }
        )
        duration = ef.ColumnSpec(
            name="duration_s",
            logical_type=ef.DecimalType(precision=16, scale=3),
            nullable=True,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="seconds"),
        )
        declaration = ef.infer_diff_contract(
            expected.schema, keys=["sample_id"], column_overrides=(duration,)
        )
    result = ef.diff(
        candidate,
        ef.ArrowInput(expected),
        contract=declaration,
        work_dir=output / "private",
        options=ef.ComparisonOptions(max_rows=1 if case == Case.not_evaluable else 100),
    )
    report = ef.write_comparison_report(result, output / "report")
    detail = ef.write_comparison_report(
        result,
        output / "synthetic-detail",
        options=ef.ReportOptions(include_values=True, include_metadata=True),
    )
    decision = ef.equivalence_decision(
        result,
        policy=ef.EquivalencePolicy(require_persisted_evidence=True),
        evidence_root=output / "private",
    )
    return {
        "role": role.value,
        "case": case.value,
        "synthetic": True,
        "state": decision.state,
        "complete": decision.complete,
        "accepted": decision.accepted,
        "code": decision.code,
        "next_action": report.next_action,
        "report": report.to_text(),
        "synthetic_detail": detail.to_text(),
        "report_html": str(output / "report" / "report.html"),
        "synthetic_detail_html": str(output / "synthetic-detail" / "report.html"),
    }
