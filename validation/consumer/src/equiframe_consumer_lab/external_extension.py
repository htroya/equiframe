"""A bounded real external compiler/adapter, using native Polars and existing ports.

This synthetic retail projection is deliberately not a fourth engine or generic
plugin framework. Only Scan + literal Column Project over text/int64 is claimed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import polars as pl
import pyarrow as pa

import equiframe as ef

from .programs import integer, string
from .programs import schema as declared_schema

ENGINE = "consumer_polars"


@dataclass(frozen=True)
class Projection:
    transformation_id: str
    table: str
    columns: tuple[tuple[str, str], ...]
    code_version: str = "external-consumer/literal-projection-v1"
    revision: int = 1
    engine: str = ENGINE


class ProjectionCompiler:
    engine = ENGINE

    def check(self, plan, contract):
        try:
            ef.validate_ir(plan, contract)
            if (
                len(plan.nodes) != 2
                or not isinstance(plan.nodes[0], ef.Scan)
                or not isinstance(plan.nodes[1], ef.Project)
            ):
                raise ValueError("external compiler supports only Scan then Project")
            scan, project = plan.nodes
            if (
                project.source != scan.node_id
                or plan.output != project.node_id
                or any(not isinstance(c.expression, ef.Column) for c in project.columns)
            ):
                raise ValueError("external projection requires literal column expressions")
            for table in (*contract.inputs, contract.output):
                for column in table.schema_spec.columns:
                    kind = column.logical_type
                    if not (
                        isinstance(kind, ef.StringType)
                        or (isinstance(kind, ef.IntegerType) and kind.bits == 64 and kind.signed)
                    ):
                        raise ValueError("external projection admits only text and signed int64")
        except (ValueError, ef.CapabilityError) as error:
            return ef.CompilationCheck(
                engine=self.engine,
                supported=False,
                diagnostics=(ef.CompilationDiagnostic(code="external_subset", message=str(error)),),
            )
        return ef.CompilationCheck(engine=self.engine, supported=True)

    def compile(self, plan, contract):
        check = self.check(plan, contract)
        if not check.supported:
            raise ef.CapabilityError(check.diagnostics[0].message)
        ir_hash, contract_hash = ef.ir_fingerprint(plan), ef.contract_fingerprint(contract)
        identifier = "external_" + hashlib.sha256((ir_hash + contract_hash).encode()).hexdigest()
        scan, project = plan.nodes
        transformation = Projection(
            identifier, scan.table, tuple((c.expression.name, c.name) for c in project.columns)
        )
        return ef.CompiledPlan(
            engine=self.engine,
            transformation=transformation,
            ir_sha256=ir_hash,
            contract_sha256=contract_hash,
            check=check,
        )


class ProjectionAdapter:
    engine = ENGINE

    def __init__(self):
        self.native_executions = 0

    def capabilities(self):
        return ef.EngineCapabilities(
            engine=self.engine,
            decimal_precision=1,
            timestamp_units=(),
            zoned_timestamp_units=(),
            lazy=False,
            cancellation="cooperative",
            resource_controls=("cooperative materialized-table checkpoints",),
            required_packages=("polars", "pyarrow"),
        )

    def execute(self, transformation, inputs, context):
        if not isinstance(transformation, Projection):
            raise ef.CapabilityError("wrong external transformation type")
        context.check()
        loaded = inputs[transformation.table]
        if loaded.meaningful_index or loaded.index is not None:
            raise ef.CapabilityError("external projection refuses an index")
        if any(
            not (
                pa.types.is_string(f.type)
                or pa.types.is_large_string(f.type)
                or f.type == pa.int64()
            )
            for f in loaded.table.schema
        ):
            raise ef.CapabilityError("external projection refuses unsupported physical input")
        frame = pl.from_arrow(loaded.table)
        # get_column resolves a literal name; no wildcard/regex selector is evaluated.
        output = frame.select(
            [frame.get_column(source).alias(target) for source, target in transformation.columns]
        )
        self.native_executions += 1
        context.check()
        table = output.to_arrow()
        context.check_table(table, output=True)
        return ef.LoadedTable(
            table,
            native_types=tuple((n, str(t)) for n, t in output.schema.items()),
            notes=("External application-owned native Polars projection",),
        )


class CapturedSource:
    """External DataSource keeps the entire LoadedTable, not only its Arrow buffer."""

    table_names = ("sales",)

    def __init__(self, loaded):
        self.loaded = loaded
        self.resolutions = 0

    def resolve(self, name, *, context):
        if name != "sales":
            raise KeyError(name)
        context.check()
        self.resolutions += 1
        return self.loaded


def declarations():
    columns = (string("sku"), integer("quantity", "item", nullable=True))
    schema = declared_schema(columns, ("sku",))
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="external.retail.projection",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="sales", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                severity="error",
                required=True,
                specification=ef.SchemaCheck(table="result"),
            ),
        ),
    )
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="source", table="sales"),
            ef.Project(
                node_id="result",
                source="source",
                columns=tuple(
                    ef.NamedExpression(name=name, expression=ef.Column(name=name))
                    for name in ("sku", "quantity")
                ),
            ),
        ),
        output="result",
    )
    return contract, plan


def run(output, variant):
    if variant not in ("good", "different", "invalid"):
        raise ValueError("unknown external fixture variant")
    contract, plan = declarations()
    # Independent literals, never computed by either engine.
    expected = pa.table(
        {
            "sku": pa.array(["001", "002"], type=pa.string()),
            "quantity": pa.array([4, None], type=pa.int64()),
        }
    )
    actual = (
        expected
        if variant == "good"
        else pa.table(
            {
                "sku": pa.array(["001", "002"], type=pa.string()),
                "quantity": pa.array([5, None], type=pa.int64()),
            }
        )
        if variant == "different"
        else pa.table({"sku": ["001", "002"], "quantity": ["4", None]})
    )
    source = CapturedSource(
        ef.LoadedTable(actual, notes=("Synthetic retail input; expected is separate",))
    )
    adapter = ProjectionAdapter()
    compilers = ef.native_compiler_registry()
    compilers.register(ProjectionCompiler())
    spec = ef.MigrationSpec(
        contract=contract,
        ir=plan,
        source_engine=ENGINE,
        target_engine="duckdb",
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            justification="Synthetic data has explicit SKU identity and no domain index",
        ),
    )
    result = ef.migrate(
        spec,
        source=source,
        expected=ef.ArrowInput(expected),
        compilers=compilers,
        adapters={ENGINE: adapter},
        work_dir=output,
    )
    return result, source.resolutions, adapter.native_executions
