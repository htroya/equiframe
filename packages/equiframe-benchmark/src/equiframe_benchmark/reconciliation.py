"""Read-only award reconciliation configured by the DW owner, without float money.

The independently supplied expected table is evidence, not an automatic oracle
label. No DW is opened, transformed or published by this module.
"""

from collections import Counter
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal

from equiframe._base import strict_bool_literal
from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Document, Text

if TYPE_CHECKING:
    import pyarrow as pa


class AwardReconciliationSpec(Document):
    """Names and business grain supplied explicitly by the domain owner."""

    domain_schema_revision: Text
    award_keys: tuple[Text, ...]
    amount_column: Text
    currency_column: Text
    bridge_award_keys: tuple[Text, ...] = ()
    supplier_column: Text | None = None
    max_rows: Annotated[int, Field(ge=1)] = 100_000

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if not self.award_keys or len(set(self.award_keys)) != len(self.award_keys):
            raise ValueError("a nonempty unique award grain is required")
        if len(set((*self.award_keys, self.amount_column, self.currency_column))) != (
            len(self.award_keys) + 2
        ):
            raise ValueError("award keys and monetary columns must be distinct")
        if bool(self.bridge_award_keys) != (self.supplier_column is not None):
            raise ValueError("bridge keys and supplier column must be supplied together")
        if self.bridge_award_keys and (
            len(self.bridge_award_keys) != len(self.award_keys)
            or len(set((*self.bridge_award_keys, self.supplier_column)))
            != len(self.bridge_award_keys) + 1
        ):
            raise ValueError("bridge grain must map all award keys and a distinct supplier")
        return self


class CurrencyReconciliation(Document):
    currency: Annotated[str, Field(min_length=1)]
    expected_awards: Annotated[int, Field(ge=0)]
    observed_awards: Annotated[int, Field(ge=0)]
    observed_missing_amounts: Annotated[int, Field(ge=0)]
    currency_assignment_complete: bool = True
    expected_total: Text
    observed_total: Text | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.observed_missing_amounts > self.observed_awards or (
            (self.observed_total is None)
            != (bool(self.observed_missing_amounts) or not self.currency_assignment_complete)
        ):
            raise ValueError("missing amounts require an unavailable exact total")
        return self


class ReconciliationCheck(Document):
    code: Text
    state: Literal["conformant", "divergent", "not_evaluable"]
    count: Annotated[int, Field(ge=0)]


class AwardReconciliationResult(Document):
    spec: AwardReconciliationSpec
    checks: tuple[ReconciliationCheck, ...]
    currencies: tuple[CurrencyReconciliation, ...]
    expected_rows: Annotated[int, Field(ge=0)]
    observed_rows: Annotated[int, Field(ge=0)]
    observed_missing_currencies: Annotated[int, Field(ge=0)] | None = None
    scientific_label_confirmed: Annotated[Literal[False], BeforeValidator(strict_bool_literal)] = (
        False
    )

    @property
    def complete(self) -> bool:
        return all(check.state != "not_evaluable" for check in self.checks)

    @property
    def state(self) -> str:
        if any(check.state == "divergent" for check in self.checks):
            return "divergent"
        return "conformant" if self.complete else "not_evaluable"


def _exact_sum(values: list[Decimal]) -> str:
    """Integer accumulation avoids the ambient Decimal context's rounding."""
    if not values:
        return "0"
    exponents = [value.as_tuple().exponent for value in values]
    if any(not isinstance(exponent, int) for exponent in exponents):
        raise ValueError("finite decimal amounts are required")
    scale = min(int(exponent) for exponent in exponents)
    total = 0
    for value in values:
        sign, digits, exponent = value.as_tuple()
        if not (isinstance(exponent, int)):
            raise AssertionError("Internal invariant check failed.")
        coefficient = int("".join(map(str, digits)))
        total += (-coefficient if sign else coefficient) * 10 ** (exponent - scale)
    digits = tuple(map(int, str(abs(total))))
    return format(Decimal((int(total < 0), digits, scale)), "f")


def reconcile_awards(
    expected: "pa.Table",
    observed: "pa.Table",
    *,
    spec: AwardReconciliationSpec,
    bridge: "pa.Table | None" = None,
) -> AwardReconciliationResult:
    """Check grain, exact per-award money, currency totals and optional bridge.

    Monetary columns must be Arrow decimal, never floating point. Missing/null
    values remain visible. The row budget is cooperative; this verifier reads
    already materialized tables and does not enforce a hard memory quota.
    """
    import pyarrow as pa

    spec = AwardReconciliationSpec.model_validate(spec)
    if not isinstance(expected, pa.Table) or not isinstance(observed, pa.Table):
        raise TypeError("expected and observed must be Arrow tables")
    if bridge is not None and not isinstance(bridge, pa.Table):
        raise TypeError("bridge must be an Arrow table")
    checks: list[ReconciliationCheck] = []
    missing_currencies: int | None = None

    def record(code: str, count: int, *, unavailable: bool = False) -> None:
        checks.append(
            ReconciliationCheck(
                code=code,
                count=count,
                state="not_evaluable" if unavailable else "divergent" if count else "conformant",
            )
        )

    def result(currencies: tuple[CurrencyReconciliation, ...] = ()) -> AwardReconciliationResult:
        return AwardReconciliationResult(
            spec=spec,
            checks=tuple(checks),
            currencies=currencies,
            expected_rows=expected.num_rows,
            observed_rows=observed.num_rows,
            observed_missing_currencies=missing_currencies,
        )

    tables = (expected, observed, *((bridge,) if bridge is not None else ()))
    if sum(table.num_rows for table in tables) > spec.max_rows:
        record("row_budget", 1, unavailable=True)
        return result()
    fields = (*spec.award_keys, spec.currency_column, spec.amount_column)
    for table in (expected, observed):
        table.validate(full=True)
        if len(set(table.column_names)) != table.num_columns or not set(fields) <= set(
            table.column_names
        ):
            record("required_columns", 1, unavailable=True)
            return result()
        if not pa.types.is_decimal(table.schema.field(spec.amount_column).type):
            record("exact_decimal_required", 1, unavailable=True)
            return result()
        if not all(
            pa.types.is_string(table.schema.field(name).type)
            or pa.types.is_large_string(table.schema.field(name).type)
            for name in (*spec.award_keys, spec.currency_column)
        ):
            record("text_identifiers_currency_required", 1, unavailable=True)
            return result()
    if any(expected.schema.field(name).type != observed.schema.field(name).type for name in fields):
        record("physical_types_mismatch", 1, unavailable=True)
        return result()
    rows = (expected.select(fields).to_pylist(), observed.select(fields).to_pylist())
    keys = [[tuple(row[name] for name in spec.award_keys) for row in side] for side in rows]
    expected_invalid = sum(
        any(row[name] is None or row[name] == "" for name in fields) for row in rows[0]
    )
    if expected_invalid or len(set(keys[0])) != len(keys[0]):
        record(
            "invalid_independent_reference",
            expected_invalid + len(keys[0]) - len(set(keys[0])),
            unavailable=True,
        )
        return result()
    record(
        "missing_award_keys", sum(any(key is None or key == "" for key in item) for item in keys[1])
    )
    record("duplicate_award_grain", len(keys[1]) - len(set(keys[1])))
    missing_currencies = sum(row[spec.currency_column] in (None, "") for row in rows[1])
    record("missing_currencies", missing_currencies)
    record(
        "missing_monetary_values",
        sum(
            row[spec.amount_column] is None or row[spec.currency_column] in (None, "")
            for row in rows[1]
        ),
    )
    expected_records = Counter(tuple(row[name] for name in fields) for row in rows[0])
    observed_records = Counter(tuple(row[name] for name in fields) for row in rows[1])
    record(
        "per_award_values",
        sum((expected_records - observed_records).values())
        + sum((observed_records - expected_records).values()),
    )
    totals: list[dict[str, list[Decimal]]] = [{}, {}]
    counts = [
        Counter(
            row[spec.currency_column]
            for row in side
            if isinstance(row[spec.currency_column], str) and row[spec.currency_column]
        )
        for side in rows
    ]
    for side, side_rows in zip(totals, rows, strict=True):
        for row in side_rows:
            currency, amount = row[spec.currency_column], row[spec.amount_column]
            if isinstance(currency, str) and currency and isinstance(amount, Decimal):
                side.setdefault(currency, []).append(amount)
    currencies = tuple(
        CurrencyReconciliation(
            currency=currency,
            expected_awards=counts[0][currency],
            observed_awards=counts[1][currency],
            observed_missing_amounts=counts[1][currency] - len(totals[1].get(currency, [])),
            currency_assignment_complete=not missing_currencies,
            expected_total=_exact_sum(totals[0].get(currency, [])),
            observed_total=_exact_sum(totals[1].get(currency, []))
            if not missing_currencies and counts[1][currency] == len(totals[1].get(currency, []))
            else None,
        )
        for currency in sorted(set(counts[0]) | set(counts[1]))
    )
    record(
        "currency_totals",
        sum(
            Decimal(item.expected_total) != Decimal(item.observed_total)
            for item in currencies
            if item.observed_total is not None
        ),
    )
    missing_totals = sum(item.observed_total is None for item in currencies)
    if missing_totals or missing_currencies:
        record("currency_totals_unavailable", max(missing_totals, 1), unavailable=True)
    if spec.bridge_award_keys:
        if bridge is None:
            record("bridge_unavailable", 1, unavailable=True)
        else:
            bridge_fields = (*spec.bridge_award_keys, spec.supplier_column)
            if (
                not set(bridge_fields) <= set(bridge.column_names)
                or len(set(bridge.column_names)) != bridge.num_columns
            ):
                record("bridge_required_columns", 1, unavailable=True)
            elif not all(
                pa.types.is_string(bridge.schema.field(name).type)
                or pa.types.is_large_string(bridge.schema.field(name).type)
                for name in bridge_fields
                if name is not None
            ):
                record("bridge_identifier_types", 1, unavailable=True)
            else:
                bridge.validate(full=True)
                bridge_rows = bridge.select(
                    [name for name in bridge_fields if name is not None]
                ).to_pylist()
                links = [tuple(row[name] for name in bridge_fields) for row in bridge_rows]
                record("bridge_duplicate_links", len(links) - len(set(links)))
                record(
                    "bridge_missing_identifiers",
                    sum(any(value in (None, "") for value in link) for link in links),
                )
                observed_keys = set(keys[1])
                record(
                    "bridge_unmatched_awards",
                    sum(
                        tuple(row[name] for name in spec.bridge_award_keys) not in observed_keys
                        for row in bridge_rows
                    ),
                )
                record("bridge_contains_amount", int(spec.amount_column in bridge.column_names))
    elif bridge is not None:
        raise ValueError("bridge data requires an explicit bridge mapping")
    return result(currencies)
