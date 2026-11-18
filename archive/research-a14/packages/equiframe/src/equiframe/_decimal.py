"""Isolated arithmetic for bounded exact decimals, independent of consumer state."""

from decimal import ROUND_HALF_EVEN, Context, DivisionByZero, InvalidOperation, Overflow


def exact_decimal_context() -> Context:
    """Create fresh settings and flags; callers retain their own context unchanged.

    One hundred digits exceed the 76-digit Arrow decimal contract and the common
    38-digit native IR. Rounding is never permission to lose precision: ingestion
    and IR validation compare quantized values with their exact source values.
    """
    return Context(
        prec=100,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
