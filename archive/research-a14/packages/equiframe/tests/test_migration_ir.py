"""IR metadata restrictions and deterministic, nonexecuting compilation."""

import subprocess
import sys

import pytest
from pydantic import ValidationError

from equiframe.contracts import (
    ColumnSpec,
    Contract,
    DecimalType,
    FloatType,
    IgnoredOrder,
    IntegerType,
    NaNPolicy,
    NullPolicy,
    NumericPolicy,
    StringType,
    TableSchema,
    TableSpec,
)
from equiframe.errors import CapabilityError
from equiframe.migration.ports import native_compiler_registry
from equiframe.migration.types import (
    Cast,
    CastColumn,
    Column,
    LiteralExpression,
    NamedExpression,
    Project,
    RelationalPlan,
    Scan,
)
from equiframe.migration.validation import ir_fingerprint, validate_ir
from equiframe.values import DecimalValue, IntegerValue


def ir_column(name, dtype, *, nullable=True):
    return ColumnSpec(
        name=name,
        logical_type=dtype,
        nullable=nullable,
        null_policy=NullPolicy(representations=("null",)),
        nan_policy=NaNPolicy(handling="distinct") if isinstance(dtype, FloatType) else None,
        numeric_policy=NumericPolicy(comparison="exact", unit="units")
        if dtype.kind in ("integer", "decimal", "float")
        else None,
    )


def ir_contract(inputs, output, *, family="nulls_types"):
    def table(name, columns):
        return TableSpec(
            name=name,
            schema_spec=TableSchema(
                columns=tuple(columns), keys=(), multiplicity="preserve", order=IgnoredOrder()
            ),
        )

    return Contract(
        schema_version="1.0",
        contract_id="test.ir",
        revision=1,
        family=family,
        inputs=tuple(table(name, columns) for name, columns in inputs.items()),
        output=table("output", output),
        preconditions=(),
        rules=(),
    )


def identity():
    column = ir_column("value", IntegerType(bits=64, signed=True))
    return RelationalPlan(nodes=(Scan(node_id="scan", table="input"),), output="scan"), ir_contract(
        {"input": [column]}, [column]
    )


def test_strict_roundtrip_schema_and_compilation_identity():
    plan, contract = identity()
    assert RelationalPlan.model_validate_json(plan.model_dump_json()) == plan
    assert RelationalPlan.model_json_schema()["title"] == "RelationalPlan"
    registry = native_compiler_registry()
    ids = set()
    for engine in ("pandas", "polars", "duckdb"):
        compiler = registry.resolve(engine)
        assert compiler.check(plan, contract).supported
        first = compiler.compile(plan, contract)
        assert (
            first == compiler.compile(plan, contract)
            if engine == "duckdb"
            else first.ir_sha256 == ir_fingerprint(plan)
        )
        ids.add(first.transformation.transformation_id)
    assert len(ids) == 3
    with pytest.raises(ValueError, match="once"):
        registry.register(registry.resolve("pandas"))
    with pytest.raises(CapabilityError):
        registry.resolve("unknown")


@pytest.mark.parametrize(
    "fault", ("forward", "duplicate", "unused", "missing_output", "unknown_table")
)
def test_graph_rejects_unbound_or_ambiguous_nodes(fault):
    plan, contract = identity()
    if fault == "forward":
        nodes = (
            Project(
                node_id="project",
                source="scan",
                columns=(NamedExpression(name="value", expression=Column(name="value")),),
            ),
            *plan.nodes,
        )
        plan = plan.model_copy(update={"nodes": nodes})
    elif fault == "duplicate":
        plan = plan.model_copy(update={"nodes": (*plan.nodes, *plan.nodes)})
    elif fault == "unused":
        plan = plan.model_copy(
            update={"nodes": (*plan.nodes, Scan(node_id="other", table="input"))}
        )
    elif fault == "missing_output":
        plan = plan.model_copy(update={"output": "missing"})
    else:
        plan = plan.model_copy(update={"nodes": (Scan(node_id="scan", table="other"),)})
    with pytest.raises(ValueError):
        validate_ir(plan, contract)
    assert not native_compiler_registry().resolve("pandas").check(plan, contract).supported


def test_json_rejects_code_extra_and_coercions():
    plan, _ = identity()
    document = plan.model_dump(mode="json")
    document["callback"] = "untrusted:execute"
    with pytest.raises(ValidationError):
        RelationalPlan.model_validate_json(__import__("json").dumps(document))
    with pytest.raises(ValidationError):
        IntegerType(bits="64", signed=True)


@pytest.mark.parametrize(
    "dtype,value",
    [
        (IntegerType(bits=8, signed=True), IntegerValue(value=128)),
        (DecimalType(precision=4, scale=2), DecimalValue(value="100.00")),
        (DecimalType(precision=4, scale=2), DecimalValue(value="1.234")),
        (DecimalType(precision=38, scale=0), DecimalValue(value="1e1000000")),
    ],
)
def test_literal_range_checked_before_backend_execution(dtype, value):
    output = ir_column("constant", dtype)
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Project(
                node_id="project",
                source="scan",
                columns=(
                    NamedExpression(
                        name="constant",
                        expression=LiteralExpression(logical_type=dtype, value=value, unit="units"),
                    ),
                ),
            ),
        ),
        output="project",
    )
    contract = ir_contract({"input": [ir_column("value", dtype)]}, [output])
    assert all(
        not native_compiler_registry().resolve(engine).check(plan, contract).supported
        for engine in ("pandas", "polars", "duckdb")
    )


def test_exact_widening_preserves_unit_and_rejects_lossy_cast():
    source = ir_column("value", DecimalType(precision=8, scale=2))
    target = ir_column("value", DecimalType(precision=12, scale=2))
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Cast(
                node_id="cast",
                source="scan",
                columns=(CastColumn(column="value", logical_type=target.logical_type),),
            ),
        ),
        output="cast",
    )
    assert (
        validate_ir(plan, ir_contract({"input": [source]}, [target])).output_columns[0].unit
        == "units"
    )
    lossy = plan.model_copy(
        update={
            "nodes": (
                plan.nodes[0],
                Cast(
                    node_id="cast",
                    source="scan",
                    columns=(
                        CastColumn(column="value", logical_type=DecimalType(precision=8, scale=1)),
                    ),
                ),
            )
        }
    )
    with pytest.raises(CapabilityError, match="widening"):
        validate_ir(lossy, ir_contract({"input": [source]}, [target]))


def test_duckdb_case_insensitive_names_are_unsupported_before_execution():
    columns = [ir_column("name", StringType()), ir_column("NAME", StringType())]
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"),), output="scan")
    assert (
        not native_compiler_registry()
        .resolve("duckdb")
        .check(plan, ir_contract({"input": columns}, columns))
        .supported
    )


def test_duckdb_nul_identifier_is_unsupported_before_execution():
    columns = [ir_column("name\x00tail", StringType())]
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"),), output="scan")
    check = (
        native_compiler_registry()
        .resolve("duckdb")
        .check(plan, ir_contract({"input": columns}, columns))
    )
    assert not check.supported
    assert check.diagnostics[0].code == "nul_identifier"


def test_compiler_import_and_factory_do_not_import_native_engines():
    script = (
        "from equiframe.migration.ports import native_compiler_registry; "
        "import sys; native_compiler_registry(); "
        "assert not any(n in sys.modules for n in ('pandas','polars','duckdb','pyarrow','numpy'))"
    )
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
