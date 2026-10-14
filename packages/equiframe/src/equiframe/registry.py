"""Explicit instance-owned registry of trusted native implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import ConfigDict, TypeAdapter

from equiframe._base import Identifier, PositiveInt, Text
from equiframe.errors import InvalidExecutionInput
from equiframe.execution_types import ExecutionPlan

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

    from equiframe.execution import RunContext


class Transformation(Protocol):
    @property
    def engine(self) -> str: ...

    @property
    def transformation_id(self) -> str: ...

    @property
    def revision(self) -> int: ...

    @property
    def code_version(self) -> str: ...


def _native_identity(
    engine: str, expected: str, transformation_id: str, revision: int, code_version: str
) -> None:
    """Validate built-in metadata without importing or invoking native runtimes."""
    safe_errors = ConfigDict(hide_input_in_errors=True)
    TypeAdapter(Identifier, config=safe_errors).validate_python(transformation_id, strict=True)
    TypeAdapter(PositiveInt, config=safe_errors).validate_python(revision, strict=True)
    TypeAdapter(Text, config=safe_errors).validate_python(code_version, strict=True)
    if type(engine) is not str or engine != expected:
        raise InvalidExecutionInput("native transformation engine differs from its class")


@dataclass(frozen=True)
class PandasTransformation:
    transformation_id: str
    callback: Callable[[Mapping[str, pd.DataFrame], RunContext], pd.DataFrame]
    code_version: str
    revision: int = 1
    engine: Literal["pandas"] = "pandas"

    def __post_init__(self) -> None:
        _native_identity(
            self.engine, "pandas", self.transformation_id, self.revision, self.code_version
        )
        if not callable(self.callback):
            raise InvalidExecutionInput("native transformation requires a trusted callable")


@dataclass(frozen=True)
class PolarsTransformation:
    transformation_id: str
    callback: Callable[[Mapping[str, pl.DataFrame], RunContext], pl.DataFrame | pl.LazyFrame]
    code_version: str
    revision: int = 1
    engine: Literal["polars"] = "polars"

    def __post_init__(self) -> None:
        _native_identity(
            self.engine, "polars", self.transformation_id, self.revision, self.code_version
        )
        if not callable(self.callback):
            raise InvalidExecutionInput("native transformation requires a trusted callable")


@dataclass(frozen=True)
class DuckDBTransformation:
    transformation_id: str
    sql: str
    code_version: str
    revision: int = 1
    engine: Literal["duckdb"] = "duckdb"

    def __post_init__(self) -> None:
        _native_identity(
            self.engine, "duckdb", self.transformation_id, self.revision, self.code_version
        )
        if not isinstance(self.sql, str) or not self.sql.strip() or "\x00" in self.sql:
            raise InvalidExecutionInput("native transformation requires nonempty trusted SQL text")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in self.sql):
            raise InvalidExecutionInput("native SQL requires valid Unicode scalar values")


class TransformationRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, int], Transformation] = {}

    def register(self, transformation: Transformation) -> None:
        from pydantic import TypeAdapter

        TypeAdapter(Identifier).validate_python(transformation.engine, strict=True)
        TypeAdapter(Identifier).validate_python(transformation.transformation_id, strict=True)
        TypeAdapter(PositiveInt).validate_python(transformation.revision, strict=True)
        TypeAdapter(Text).validate_python(transformation.code_version, strict=True)
        key = (transformation.engine, transformation.transformation_id, transformation.revision)
        if key in self._items:
            raise InvalidExecutionInput("transformation already registered")
        self._items[key] = transformation

    def resolve(self, plan: ExecutionPlan) -> Transformation:
        key = (plan.engine, plan.transformation_id, plan.transformation_revision)
        try:
            return self._items[key]
        except KeyError:
            raise InvalidExecutionInput(
                "transformation is not registered for this engine/revision"
            ) from None
