"""Four synthetic grouped-sum consumers with independent expected metrics."""

from fractions import Fraction

import pyarrow as pa

import equiframe as ef


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


if __name__ == "__main__":
    main()
