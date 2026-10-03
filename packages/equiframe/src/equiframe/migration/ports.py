"""Explicit compiler registry; JSON never imports or registers a plugin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from equiframe.contracts import Contract
from equiframe.errors import CapabilityError
from equiframe.registry import Transformation

from .types import CompilationCheck, CompilationDiagnostic, RelationalPlan
from .validation import ValidatedIR, validate_ir


@dataclass(frozen=True)
class CompiledPlan:
    engine: str
    transformation: Transformation
    ir_sha256: str
    contract_sha256: str
    check: CompilationCheck


class PlanCompiler(Protocol):
    @property
    def engine(self) -> str: ...

    def check(self, plan: RelationalPlan, contract: Contract) -> CompilationCheck: ...

    def compile(self, plan: RelationalPlan, contract: Contract) -> CompiledPlan: ...


class CompilerRegistry:
    def __init__(self) -> None:
        self._compilers: dict[str, PlanCompiler] = {}

    def register(self, compiler: PlanCompiler) -> None:
        if not compiler.engine or compiler.engine in self._compilers:
            raise ValueError("compiler engine must be nonempty and registered once")
        self._compilers[compiler.engine] = compiler

    def resolve(self, engine: str) -> PlanCompiler:
        if engine not in self._compilers:
            raise CapabilityError("no explicitly registered compiler for engine: " + engine)
        return self._compilers[engine]


def compiler_check(engine: str, plan: RelationalPlan, contract: Contract) -> CompilationCheck:
    try:
        validate_ir(plan, contract)
    except (ValueError, CapabilityError) as error:
        return CompilationCheck(
            engine=engine,
            supported=False,
            diagnostics=(
                CompilationDiagnostic(
                    code="unsupported_ir", message=str(error).strip() or "invalid IR"
                ),
            ),
        )
    return CompilationCheck(engine=engine, supported=True)


def require_supported(engine: str, plan: RelationalPlan, contract: Contract) -> ValidatedIR:
    check = compiler_check(engine, plan, contract)
    if not check.supported:
        raise CapabilityError(check.diagnostics[0].message)
    return validate_ir(plan, contract)


def native_compiler_registry() -> CompilerRegistry:
    from .backends.duckdb import DuckDBCompiler
    from .backends.pandas import PandasCompiler
    from .backends.polars import PolarsCompiler

    registry = CompilerRegistry()
    for compiler in (PandasCompiler(), PolarsCompiler(), DuckDBCompiler()):
        registry.register(compiler)
    return registry
