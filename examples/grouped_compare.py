"""Four synthetic grouped-sum consumers with independent expected metrics."""

from fractions import Fraction

import pyarrow as pa
import pyarrow.compute as pc

import equiframe as ef


def check_filtered_totals() -> None:
    """Require every eligible buyer/currency group and its exact total."""
    inputs = pa.table(
        {
            "buyer": ["A", "A", "B", "C"],
            "currency": ["USD", "USD", "USD", "USD"],
            "cents": [10_000, 15_000, 12_000, 9_999],
        }
    )
    eligible = inputs.filter(pc.greater_equal(inputs["cents"], 10_000))
    correct = pa.table({"buyer": ["A", "B"], "currency": ["USD", "USD"], "cents": [25_000, 12_000]})
    wrong_cent = correct.set_column(2, "cents", pa.array([24_999, 12_000]))
    for candidate, expected_changes in (
        (correct, (0, 0, 0)),
        (correct.slice(0, 1), (0, 1, 0)),
        (wrong_cent, (0, 0, 1)),
    ):
        check = ef.compare_grouped(candidate, eligible, by=("buyer", "currency"), column="cents")
        assert check.complete
        assert (check.added_groups, check.removed_groups, check.modified_groups) == expected_changes
    print("Exact totals accept the valid filtered result and detect a missing group and one cent")


def main() -> None:
    recipes = (
        (("entidad", "moneda"), "monto"),
        (("sucursal",), "ventas"),
        (("almacen", "producto"), "existencias"),
        (("departamento", "periodo"), "gasto"),
    )
    for by, measure in recipes:
        expected_data = {by[0]: ["A", "A", "B", "C", "D"], measure: [40, 60, 0, 50, 9]}
        candidate_data = {by[0]: ["A", "A", "B", "C", "E"], measure: [90, 60, 25, 50, 7]}
        if len(by) == 2:
            expected_data[by[1]] = ["USD"] * 5
            candidate_data[by[1]] = ["USD"] * 5
        result = ef.compare_grouped(
            pa.table(candidate_data),
            pa.table(expected_data),
            by=by,
            column=measure,
            options=ef.GroupedComparisonOptions(max_examples=0),
        )
        assert result.candidate_groups == result.expected_groups == 4
        assert result.common_groups == result.comparable_groups == 3
        assert result.union_groups == 5
        assert result.modified_groups == 2
        assert result.modified_group_proportion == Fraction(2, 3)
        assert result.maximum_relative_difference == Fraction(1, 2)
        assert result.zero_baseline_groups == result.changed_from_zero_groups == 1
        assert result.changed_from_zero_proportion == 1
        assert result.added_groups == result.removed_groups == 1
        assert result.unavailable_groups == 0 and result.complete is True
        assert result.group_coverage == result.comparison_coverage == Fraction(3, 5)
        assert result.reference_coverage == Fraction(3, 4)
        assert result.examples == ()
        assert ef.GroupedComparisonResult.model_validate_json(result.model_dump_json()) == result
    print("Four installed grouped consumers passed independent expected metrics")
    check_filtered_totals()


if __name__ == "__main__":
    main()
