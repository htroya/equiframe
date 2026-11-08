"""Exact native Decimal coefficient arithmetic with explicit overflow checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from equiframe.errors import CapabilityError

if TYPE_CHECKING:
    import polars as pl

    from equiframe.execution import RunContext


def divide(
    frame: pl.DataFrame,
    left: pl.Expr,
    right: pl.Expr,
    *,
    left_scale: int,
    right_scale: int,
    precision: int,
    scale: int,
    rounding: str,
    prefix: str,
    context: RunContext,
) -> tuple[pl.DataFrame, pl.Expr]:
    """Materialize native quotient/remainder steps; never use floats or row callbacks.

    Each operand coefficient fits 38 decimal digits. Modular doubling computes
    the next digit without multiplying a potentially 38-digit remainder by ten.
    Decimal(38,0) carries exact coefficient arithmetic: Polars 1.30 panics on
    Int128 column/column addition and subtraction. Integer floor/modulo remain
    native Int128 operations; every resulting coefficient still fits 38 digits.
    Only finite native boolean reductions cross back to the coordinator to reject
    invalid arithmetic; neither operands nor answers are computed in Python.
    """
    import polars as pl

    def col(name: str) -> pl.Expr:
        return pl.col(prefix + name)

    def named(value: pl.Expr, name: str) -> pl.Expr:
        return value.alias(prefix + name)

    wide = pl.Decimal(38, 0)
    zero = pl.lit(0, dtype=wide)

    def constant(value: int) -> pl.Expr:
        return pl.lit(str(value)).cast(wide)

    def floor(left: pl.Expr, right: pl.Expr) -> pl.Expr:
        # The native direct Int128 -> Decimal cast rejects valid large values
        # in Polars 1.30. Its native integer text and Decimal parsers are exact.
        return (left.cast(pl.Int128) // right.cast(pl.Int128)).cast(pl.String).cast(wide)

    def modulo(left: pl.Expr, right: pl.Expr) -> pl.Expr:
        return (left.cast(pl.Int128) % right.cast(pl.Int128)).cast(pl.String).cast(wide)

    frame = frame.with_columns(
        named(left.is_not_null() & right.is_not_null(), "active"),
        named(left.cast(pl.String).str.replace_all(r"\.", "").cast(wide), "a"),
        named(right.cast(pl.String).str.replace_all(r"\.", "").cast(wide), "b"),
    )

    def reject(condition: pl.Expr, reason: str) -> None:
        context.check()
        if frame.select((col("active") & condition).any()).item():
            raise CapabilityError("Polars Decimal division: " + reason)

    reject(col("b") == 0, "zero denominator")
    frame = frame.with_columns(
        named((col("a") < 0).xor(col("b") < 0), "negative"),
        named(pl.when(col("active")).then(col("a").abs()).otherwise(zero), "a"),
        named(
            pl.when(col("active")).then(col("b").abs()).otherwise(constant(1)),
            "b",
        ),
    )
    frame = frame.with_columns(
        named(floor(col("a"), col("b")), "q"), named(modulo(col("a"), col("b")), "r")
    )
    exponent = scale + right_scale - left_scale
    limit = 10**precision - 1
    if exponent >= 0:
        reject(col("q") > constant(limit), "output precision exceeded")
        for _ in range(exponent):
            reject(col("q") > constant(limit // 10), "output precision exceeded")
            remainder, denominator = col("r"), col("b")
            carry = remainder >= denominator - remainder
            frame = frame.with_columns(
                named(carry.cast(pl.Int64).cast(wide), "c2"),
                named(
                    remainder
                    - pl.when(carry).then(denominator - remainder).otherwise(zero - remainder),
                    "r2",
                ),
            )
            for first, second in ((2, 4), (4, 8)):
                remainder = col("r" + str(first))
                carry = remainder >= denominator - remainder
                frame = frame.with_columns(
                    named(
                        col("c" + str(first)) * constant(2) + carry.cast(pl.Int64).cast(wide),
                        "c" + str(second),
                    ),
                    named(
                        remainder
                        - pl.when(carry).then(denominator - remainder).otherwise(zero - remainder),
                        "r" + str(second),
                    ),
                )
            r8, r2 = col("r8"), col("r2")
            carry = r8 >= denominator - r2
            frame = frame.with_columns(
                named(
                    col("q") * constant(10)
                    + col("c8")
                    + col("c2")
                    + carry.cast(pl.Int64).cast(wide),
                    "q",
                ),
                named(r8 - pl.when(carry).then(denominator - r2).otherwise(zero - r2), "r"),
            )
        remainder = col("r")
        exact = remainder == 0
        above = remainder > col("b") - remainder
        tie = remainder == col("b") - remainder
    else:
        factor = pl.lit(10 ** (-exponent), dtype=pl.Int128)
        frame = frame.with_columns(
            named(modulo(col("q"), factor), "dropped"), named(floor(col("q"), factor), "q")
        )
        dropped, remainder = col("dropped"), col("r")
        half = constant(5 * 10 ** (-exponent - 1))
        exact = (dropped == 0) & (remainder == 0)
        above = (dropped > half) | ((dropped == half) & (remainder > 0))
        tie = (dropped == half) & (remainder == 0)
    if rounding == "exact":
        reject(~exact, "declared exact scale is insufficient")
        increment = pl.lit(False)
    elif rounding == "half_even":
        increment = above | (tie & (modulo(col("q"), constant(2)) == 1))
    elif rounding == "half_away_from_zero":
        increment = above | tie
    else:
        raise CapabilityError("unsupported Decimal division rounding")
    reject(
        (col("q") > constant(limit)) | ((col("q") == constant(limit)) & increment),
        "output precision exceeded",
    )
    frame = frame.with_columns(named(col("q") + increment.cast(pl.Int64).cast(wide), "q"))
    text = col("q").cast(pl.String)
    if scale:
        text = text.str.pad_start(scale + 1, "0")
        text = pl.concat_str(
            text.str.slice(0, text.str.len_chars() - scale), pl.lit("."), text.str.slice(-scale)
        )
    text = pl.concat_str(
        pl.when(col("negative") & (col("q") != 0)).then(pl.lit("-")).otherwise(pl.lit("")),
        text,
    )
    output = prefix + "result"
    frame = frame.with_columns(
        pl.when(col("active"))
        .then(text.cast(pl.Decimal(precision, scale), strict=True))
        .otherwise(None)
        .alias(output)
    )
    return frame, pl.col(output)


def multiply(
    frame: pl.DataFrame,
    left: pl.Expr,
    right: pl.Expr,
    *,
    precision: int,
    scale: int,
    prefix: str,
    context: RunContext,
) -> tuple[pl.DataFrame, pl.Expr]:
    """Bound native coefficient multiplication before the product can overflow."""
    import polars as pl

    def col(name: str) -> pl.Expr:
        return pl.col(prefix + name)

    def named(value: pl.Expr, name: str) -> pl.Expr:
        return value.alias(prefix + name)

    wide = pl.Decimal(38, 0)
    zero, one = pl.lit(0, dtype=wide), pl.lit(1, dtype=wide)
    limit = pl.lit(str(10**precision - 1)).cast(wide)
    context.check()
    frame = frame.with_columns(
        named(left.is_not_null() & right.is_not_null(), "active"),
        named(left.cast(pl.String).str.replace_all(r"\.", "").cast(wide), "a"),
        named(right.cast(pl.String).str.replace_all(r"\.", "").cast(wide), "b"),
    ).with_columns(
        named((col("a") < 0).xor(col("b") < 0), "negative"),
        named(pl.when(col("active")).then(col("a").abs()).otherwise(zero), "a"),
        named(pl.when(col("active")).then(col("b").abs()).otherwise(zero), "b"),
    )
    denominator = pl.when(col("b") != 0).then(col("b")).otherwise(one)
    bound = (limit.cast(pl.Int128) // denominator.cast(pl.Int128)).cast(pl.String).cast(wide)
    too_large = col("active") & (col("b") != 0) & (col("a") > bound)
    if frame.select(too_large.any()).item():
        raise CapabilityError("Polars Decimal multiply: output precision exceeded")
    context.check()
    # Both magnitudes fit the declared coefficient bound before this product.
    # No intermediate is scaled up to the final scale or widened through float.
    frame = frame.with_columns(named(col("a") * col("b"), "value"))
    text = col("value").cast(pl.String)
    if scale:
        text = text.str.pad_start(scale + 1, "0")
        text = pl.concat_str(
            text.str.slice(0, text.str.len_chars() - scale), pl.lit("."), text.str.slice(-scale)
        )
    text = pl.concat_str(
        pl.when(col("negative") & (col("value") != 0)).then(pl.lit("-")).otherwise(pl.lit("")),
        text,
    )
    output = prefix + "result"
    frame = frame.with_columns(
        pl.when(col("active"))
        .then(text.cast(pl.Decimal(precision, scale), strict=True))
        .otherwise(None)
        .alias(output)
    )
    return frame, pl.col(output)
