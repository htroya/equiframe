"""Shared strict configuration and validation helpers (not public API)."""

from typing import Annotated, ClassVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
)
from pydantic_core import PydanticCustomError
from typing_extensions import Never


class _ExplicitOutcome:
    """Field-free guard for the explicitly selected operational outcome models.

    Object presence, technical completion and an approval decision are separate.
    This mixin intentionally does not apply to every frozen model.
    """

    __slots__ = ()
    _truth_value_guidance: ClassVar[str]

    def __bool__(self) -> Never:
        raise TypeError(f"{type(self).__name__} has no truth value; {self._truth_value_guidance}")


class FrozenModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        validate_default=True,
        revalidate_instances="always",
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )


def _text(value: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError("text must be nonempty and have no surrounding whitespace")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("text must contain valid Unicode scalar values")
    return value


Text = Annotated[str, StringConstraints(min_length=1), AfterValidator(_text)]
Identifier = Annotated[Text, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


def fail(code: str, message: str, *location: str | int) -> Never:
    """Attach a cross-field failure to its actual field, including nested paths."""
    raise ValidationError.from_exception_data(
        "EquiFrame",
        [{"type": PydanticCustomError(code, message), "loc": location, "input": None}],
    )


def unique(values: tuple[str, ...], field: str) -> None:
    seen: set[str] = set()
    for index, value in enumerate(values):
        if value in seen:
            fail("duplicate_reference", "repeated reference: " + value, field, index)
        seen.add(value)


def strict_int_literal(value: object) -> int:
    """Preserve strict integer metadata before Literal's numeric equality lookup."""
    if type(value) is not int:
        raise PydanticCustomError("literal_type", "integer literals require an exact integer type")
    return value


def strict_bool_literal(value: object) -> bool:
    """Do not normalize numeric 0/1 to a declared boolean literal."""
    if type(value) is not bool:
        raise PydanticCustomError("literal_type", "boolean literals require an exact boolean type")
    return value
