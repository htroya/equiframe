"""Independent monetary examples; no data or schema from the actual DW."""

from decimal import Decimal, localcontext

import pyarrow as pa
import pytest

from equiframe_benchmark.reconciliation import AwardReconciliationSpec, reconcile_awards


def spec(**kwargs):
    return AwardReconciliationSpec(
        domain_schema_revision="synthetic-owner.1",
        award_keys=("snapshot", "ocid", "award"),
        amount_column="amount",
        currency_column="currency",
        **kwargs,
    )


def facts(amounts=("10.50", "20.25", "7.00"), currencies=("USD", "USD", "EUR")):
    return pa.table(
        {
            "snapshot": ["s1"] * len(amounts),
            "ocid": ["p1"] * len(amounts),
            "award": [str(i) for i in range(len(amounts))],
            "currency": currencies,
            "amount": pa.array(
                [Decimal(value) if value is not None else None for value in amounts],
                type=pa.decimal128(38, 2),
            ),
        }
    )


def check(result, code):
    return next(item for item in result.checks if item.code == code)


def test_exact_currency_totals_and_permutation():
    source = facts()
    result = reconcile_awards(source, source.take([2, 0, 1]), spec=spec())
    assert result.complete and result.state == "conformant"
    assert [(item.currency, item.expected_total) for item in result.currencies] == [
        ("EUR", "7.00"),
        ("USD", "30.75"),
    ]
    assert not result.scientific_label_confirmed


def test_swapped_money_detected_even_when_totals_agree():
    result = reconcile_awards(facts(), facts(("20.25", "10.50", "7.00")), spec=spec())
    assert check(result, "currency_totals").state == "conformant"
    assert check(result, "per_award_values").state == "divergent"
    assert result.state == "divergent"


def test_duplicate_award_never_deduplicated():
    source = facts()
    result = reconcile_awards(source, pa.concat_tables([source, source.slice(0, 1)]), spec=spec())
    assert check(result, "duplicate_award_grain").count == 1
    assert (
        next(item for item in result.currencies if item.currency == "USD").observed_total == "41.25"
    )


def test_decimal_context_does_not_round_high_precision_money():
    source = facts(("999999999999999999999999999999.99", "0.01"), ("USD", "USD"))
    with localcontext() as context:
        context.prec = 3
        result = reconcile_awards(source, source, spec=spec())
    assert result.currencies[0].observed_total == "1000000000000000000000000000000.00"


def test_float_money_and_bad_reference_are_not_evaluable():
    source = facts()
    floating = source.set_column(4, "amount", pa.array([10.5, 20.25, 7.0]))
    result = reconcile_awards(source, floating, spec=spec())
    assert not result.complete and result.state == "not_evaluable"
    duplicate_reference = pa.concat_tables([source, source.slice(0, 1)])
    result = reconcile_awards(duplicate_reference, source, spec=spec())
    assert check(result, "invalid_independent_reference").state == "not_evaluable"


def test_missing_money_does_not_become_zero():
    result = reconcile_awards(facts(), facts((None, "20.25", "7.00")), spec=spec())
    assert check(result, "missing_monetary_values").count == 1
    assert result.state == "divergent"
    usd = next(item for item in result.currencies if item.currency == "USD")
    assert usd.observed_awards == 2 and usd.observed_missing_amounts == 1
    assert usd.observed_total is None
    assert not result.complete
    assert check(result, "currency_totals_unavailable").state == "not_evaluable"
    all_missing = reconcile_awards(facts(), facts((None, None, None)), spec=spec())
    assert {item.currency for item in all_missing.currencies} == {"USD", "EUR"}
    assert all(
        item.observed_total is None and item.observed_awards > 0 for item in all_missing.currencies
    )


def test_bridge_multiple_suppliers_does_not_multiply_money():
    source = facts()
    bridge = pa.table(
        {
            "snapshot": ["s1", "s1"],
            "ocid": ["p1", "p1"],
            "award": ["0", "0"],
            "supplier": ["a", "b"],
        }
    )
    mapping = spec(bridge_award_keys=("snapshot", "ocid", "award"), supplier_column="supplier")
    result = reconcile_awards(source, source, spec=mapping, bridge=bridge)
    assert result.state == "conformant"
    polluted = bridge.append_column(
        "amount", pa.array([Decimal("10.50")] * 2, type=pa.decimal128(38, 2))
    )
    result = reconcile_awards(source, source, spec=mapping, bridge=polluted)
    assert check(result, "bridge_contains_amount").state == "divergent"
    orphan = bridge.set_column(2, "award", pa.array(["unknown", "0"]))
    result = reconcile_awards(source, source, spec=mapping, bridge=orphan)
    assert check(result, "bridge_unmatched_awards").count == 1


def test_requested_bridge_absent_and_budget_are_explicit():
    source = facts()
    result = reconcile_awards(
        source,
        source,
        spec=spec(bridge_award_keys=("snapshot", "ocid", "award"), supplier_column="supplier"),
    )
    assert not result.complete and check(result, "bridge_unavailable").state == "not_evaluable"
    result = reconcile_awards(source, source, spec=spec(max_rows=1))
    assert result.state == "not_evaluable" and check(result, "row_budget").count == 1


def test_currency_changes_and_raw_text_preserved():
    source = facts()
    result = reconcile_awards(source, facts(currencies=(" USD", "USD", "EUR")), spec=spec())
    assert result.state == "divergent"
    assert {item.currency for item in result.currencies} == {" USD", "USD", "EUR"}


@pytest.mark.parametrize("currencies", [(None, "", None), (None, "USD", "EUR")])
def test_missing_currency_prevents_inference_of_complete_totals(currencies):
    result = reconcile_awards(facts(), facts(currencies=currencies), spec=spec())
    assert not result.complete and result.state == "divergent"
    assert result.observed_missing_currencies == sum(value in (None, "") for value in currencies)
    assert check(result, "currency_totals").count == 0
    assert check(result, "currency_totals_unavailable").state == "not_evaluable"
    assert all(item.observed_total is None for item in result.currencies)
    assert all(not item.currency_assignment_complete for item in result.currencies)
    assert sum(item.observed_awards for item in result.currencies) == sum(
        value not in (None, "") for value in currencies
    )


def test_schema_scale_and_mapping_errors_are_visible():
    source = facts()
    altered = source.set_column(
        4,
        "amount",
        pa.array(
            [Decimal("10.500"), Decimal("20.250"), Decimal("7.000")], type=pa.decimal128(38, 3)
        ),
    )
    result = reconcile_awards(source, altered, spec=spec())
    assert result.state == "not_evaluable"
    with pytest.raises(ValueError):
        AwardReconciliationSpec(
            domain_schema_revision="synthetic.1",
            award_keys=(),
            amount_column="amount",
            currency_column="currency",
        )
