"""Independent expected fixtures exercise three genuine native backends."""

from decimal import Decimal
from itertools import combinations

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.contracts import (
    BooleanType,
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
from equiframe.migration.ports import native_compiler_registry
from equiframe.migration.types import (
    Aggregate,
    Boolean,
    Cast,
    CastColumn,
    Column,
    Compare,
    EquiJoin,
    Filter,
    IsNaN,
    IsNull,
    JoinKey,
    LiteralExpression,
    Measure,
    NamedExpression,
    Not,
    Project,
    RelationalPlan,
    Scan,
    Sort,
    SortKey,
)
from equiframe.values import IntegerValue, StringValue

ENGINES = ("pandas", "polars", "duckdb")
INT = IntegerType(bits=64, signed=True)
DEC = DecimalType(precision=10, scale=2)


def column(name, dtype, *, nullable=True, unit="units"):
    return ColumnSpec(
        name=name,
        logical_type=dtype,
        nullable=nullable,
        null_policy=NullPolicy(representations=("null",)),
        nan_policy=NaNPolicy(handling="distinct") if isinstance(dtype, FloatType) else None,
        numeric_policy=NumericPolicy(comparison="exact", unit=unit)
        if dtype.kind in ("integer", "decimal", "float")
        else None,
    )


def contract(inputs, output, *, family="nulls_types"):
    def table(name, columns):
        return TableSpec(
            name=name,
            schema_spec=TableSchema(
                columns=tuple(columns), keys=(), multiplicity="preserve", order=IgnoredOrder()
            ),
        )

    return Contract(
        schema_version="1.0",
        contract_id="test.migration",
        revision=1,
        family=family,
        inputs=tuple(table(name, columns) for name, columns in inputs.items()),
        output=table("output", output),
        preconditions=(),
        rules=(),
    )


def run(plan, schema, inputs, engine, tmp_path):
    compiled = native_compiler_registry().resolve(engine).compile(plan, schema)
    registry = ef.TransformationRegistry()
    registry.register(compiled.transformation)
    return ef.execute(
        ef.ExecutionPlan(
            contract=schema,
            engine=engine,
            transformation_id=compiled.transformation.transformation_id,
        ),
        source=ef.LocalDataSource({name: ef.ArrowInput(table) for name, table in inputs.items()}),
        registry=registry,
        work_dir=tmp_path,
    )


def verify(plan, schema, inputs, expected, tmp_path):
    results = [run(plan, schema, inputs, engine, tmp_path) for engine in ENGINES]
    for result in results:
        assert result.state == "completed", result.problem
        compared = ef.compare(
            result.output.data, ef.ArrowInput(expected), contract=schema, work_dir=tmp_path
        )
        assert compared.state == "equivalent", tuple(ef.iter_differences(compared.differences))
    for left, right in combinations(results, 2):
        assert (
            ef.compare(
                left,
                right,
                contract=schema,
                policy=ef.ComparisonPolicy(
                    index="ignore",
                    justification=(
                        "IR uses declared columns; generated RangeIndex is not a logical key"
                    ),
                ),
                work_dir=tmp_path,
            ).state
            == "equivalent"
        )
    return results


def test_native_null_nan_predicates_and_boolean_unknown(tmp_path):
    dtype = FloatType(bits=64)
    source = pa.table(
        {"v": pa.array([None, float("nan"), 0.0, 1.0], type=pa.float64(), from_pandas=False)}
    )
    schema = contract(
        {"input": [column("v", dtype)]},
        [
            column("v", dtype),
            column("null", BooleanType(), nullable=False),
            column("nan", BooleanType(), nullable=False),
            column("self_eq", BooleanType()),
        ],
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Project(
                node_id="project",
                source="scan",
                columns=(
                    NamedExpression(name="v", expression=Column(name="v")),
                    NamedExpression(name="null", expression=IsNull(argument=Column(name="v"))),
                    NamedExpression(name="nan", expression=IsNaN(argument=Column(name="v"))),
                    NamedExpression(
                        name="self_eq",
                        expression=Compare(
                            operation="eq", left=Column(name="v"), right=Column(name="v")
                        ),
                    ),
                ),
            ),
        ),
        output="project",
    )
    expected = (
        source.append_column("null", pa.array([True, False, False, False]))
        .append_column("nan", pa.array([False, True, False, False]))
        .append_column("self_eq", pa.array([None, False, True, True], type=pa.bool_()))
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)


@pytest.mark.parametrize("how", ("inner", "left"))
@pytest.mark.parametrize("null_keys", ("equal", "never"))
def test_many_to_many_null_joins_preserve_every_right_column(tmp_path, how, null_keys):
    left = pa.table({"id": pa.array([1, 1, None, 2], type=pa.int64()), "x": ["a", "b", "n", "z"]})
    right = pa.table({"id": pa.array([1, 1, None], type=pa.int64()), "tag": ["r1", "r2", "rn"]})
    schema = contract(
        {
            "left": [column("id", INT), column("x", StringType())],
            "right": [column("id", INT), column("tag", StringType())],
        },
        [
            column("id", INT),
            column("x", StringType()),
            column("right.id", INT),
            column("right.tag", StringType()),
        ],
        family="joins",
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="left", table="left"),
            Scan(node_id="right", table="right"),
            EquiJoin(
                node_id="join",
                left="left",
                right="right",
                keys=(JoinKey(left="id", right="id"),),
                how=how,
                null_keys=null_keys,
            ),
        ),
        output="join",
    )
    rows = [(1, x, 1, tag) for x in ("a", "b") for tag in ("r1", "r2")]
    if null_keys == "equal":
        rows.append((None, "n", None, "rn"))
    elif how == "left":
        rows.append((None, "n", None, None))
    if how == "left":
        rows.append((2, "z", None, None))
    expected = pa.table(
        {
            "id": pa.array([r[0] for r in rows], type=pa.int64()),
            "x": [r[1] for r in rows],
            "right.id": pa.array([r[2] for r in rows], type=pa.int64()),
            "right.tag": [r[3] for r in rows],
        }
    )
    verify(plan, schema, {"left": left, "right": right}, expected, tmp_path)


def aggregation_plan(*, group_by=("currency",), empty_sum="null", null_groups="retain", dtype=DEC):
    return RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Aggregate(
                node_id="aggregate",
                source="scan",
                group_by=group_by,
                measures=(
                    Measure(name="total", operation="sum", column="amount", logical_type=dtype),
                    Measure(name="rows", operation="count_rows", logical_type=INT, unit="rows"),
                ),
                null_groups=null_groups,
                empty_sum=empty_sum,
            ),
        ),
        output="aggregate",
    )


@pytest.mark.parametrize("empty_sum", ("null", "zero"))
@pytest.mark.parametrize("null_groups", ("retain", "drop"))
def test_native_decimal_sum_currency_groups_and_all_null(tmp_path, empty_sum, null_groups):
    source = pa.table(
        {
            "currency": ["USD", "USD", "EUR", "EUR", None],
            "amount": pa.array(
                [Decimal("1.50"), Decimal("2.25"), None, None, Decimal("2.00")],
                type=pa.decimal128(10, 2),
            ),
        }
    )
    schema = contract(
        {"input": [column("currency", StringType()), column("amount", DEC)]},
        [
            column("currency", StringType()),
            column("total", DEC),
            column("rows", INT, nullable=False, unit="rows"),
        ],
        family="aggregations",
    )
    currencies = ["USD", "EUR"] + ([None] if null_groups == "retain" else [])
    values = [Decimal("3.75"), None if empty_sum == "null" else Decimal("0.00")] + (
        [Decimal("2.00")] if null_groups == "retain" else []
    )
    expected = pa.table(
        {
            "currency": currencies,
            "total": pa.array(values, type=pa.decimal128(10, 2)),
            "rows": pa.array([2, 2] + ([1] if null_groups == "retain" else []), type=pa.int64()),
        }
    )
    verify(
        aggregation_plan(empty_sum=empty_sum, null_groups=null_groups),
        schema,
        {"input": source},
        expected,
        tmp_path,
    )


@pytest.mark.parametrize("grouped", (True, False))
def test_empty_aggregates_have_declared_shape_and_dtypes(tmp_path, grouped):
    source = pa.table(
        {
            "currency": pa.array([], type=pa.string()),
            "amount": pa.array([], type=pa.decimal128(10, 2)),
        }
    )
    outputs = ([column("currency", StringType())] if grouped else []) + [
        column("total", DEC),
        column("rows", INT, nullable=False, unit="rows"),
    ]
    schema = contract(
        {"input": [column("currency", StringType()), column("amount", DEC)]},
        outputs,
        family="aggregations",
    )
    expected = pa.table(
        {
            **({"currency": pa.array([], type=pa.string())} if grouped else {}),
            "total": pa.array([] if grouped else [None], type=pa.decimal128(10, 2)),
            "rows": pa.array([] if grouped else [0], type=pa.int64()),
        }
    )
    verify(
        aggregation_plan(group_by=("currency",) if grouped else ()),
        schema,
        {"input": source},
        expected,
        tmp_path,
    )


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("decimal", (False, True))
def test_overflow_never_returns_completed_or_wrapped_total(tmp_path, engine, decimal):
    dtype = DecimalType(precision=38, scale=0) if decimal else INT
    value = Decimal("9" * 38) if decimal else 2**63 - 1
    source = pa.table(
        {
            "amount": pa.array(
                [value, value if decimal else 1],
                type=pa.decimal128(38, 0) if decimal else pa.int64(),
            )
        }
    )
    schema = contract(
        {"input": [column("amount", dtype)]},
        [column("total", dtype), column("rows", INT, nullable=False, unit="rows")],
        family="aggregations",
    )
    result = run(
        aggregation_plan(group_by=(), dtype=dtype), schema, {"input": source}, engine, tmp_path
    )
    assert result.state != "completed"
    assert result.output is None


def test_cast_filter_sort_quoted_names_and_inputs_unchanged(tmp_path):
    name = 'value"; DROP TABLE input; --'
    source = pa.table({name: pa.array([3, None, 1], type=pa.int8()), "text": ["a'b", "x", "other"]})
    small, wide = IntegerType(bits=8, signed=True), IntegerType(bits=64, signed=True)
    schema = contract(
        {"odd_table": [column(name, small), column("text", StringType())]},
        [column(name, wide), column("text", StringType())],
    )
    predicate = Boolean(
        operation="or",
        arguments=(
            Compare(
                operation="gt",
                left=Column(name=name),
                right=LiteralExpression(logical_type=wide, value=IntegerValue(value=1)),
            ),
            Compare(
                operation="eq",
                left=Column(name="text"),
                right=LiteralExpression(logical_type=StringType(), value=StringValue(value="a'b")),
            ),
        ),
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="odd_table"),
            Cast(
                node_id="cast", source="scan", columns=(CastColumn(column=name, logical_type=wide),)
            ),
            Filter(node_id="filter", source="cast", predicate=predicate),
            Sort(
                node_id="sort",
                source="filter",
                by=(SortKey(column=name, direction="descending", nulls="last"),),
                ties="reject",
            ),
        ),
        output="sort",
    )
    original = source.to_pylist()
    expected = pa.table({name: pa.array([3], type=pa.int64()), "text": ["a'b"]})
    verify(plan, schema, {"odd_table": source}, expected, tmp_path)
    assert source.to_pylist() == original


@pytest.mark.parametrize("engine", ENGINES)
def test_forbidden_sort_ties_fail_natively(tmp_path, engine):
    source = pa.table({"v": pa.array([1, 1], type=pa.int64())})
    schema = contract({"input": [column("v", INT)]}, [column("v", INT)])
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Sort(
                node_id="sort",
                source="scan",
                by=(SortKey(column="v", direction="ascending", nulls="first"),),
                ties="reject",
            ),
        ),
        output="sort",
    )
    assert run(plan, schema, {"input": source}, engine, tmp_path).state != "completed"


@pytest.mark.parametrize("size", (0, 3))
def test_literal_only_projection_preserves_source_row_count(tmp_path, size):
    source = pa.table({"v": pa.array(range(size), type=pa.int64())})
    schema = contract(
        {"input": [column("v", INT)]}, [column("constant", StringType(), nullable=False)]
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Project(
                node_id="project",
                source="scan",
                columns=(
                    NamedExpression(
                        name="constant",
                        expression=LiteralExpression(
                            logical_type=StringType(), value=StringValue(value="fixed")
                        ),
                    ),
                ),
            ),
        ),
        output="project",
    )
    verify(
        plan,
        schema,
        {"input": source},
        pa.table({"constant": pa.array(["fixed"] * size, type=pa.string())}),
        tmp_path,
    )


def test_boolean_operators_use_three_states_on_all_native_engines(tmp_path):
    source = pa.table(
        {
            "a": pa.array([True, True, False, False, None, None], type=pa.bool_()),
            "b": pa.array([False, None, True, None, True, False], type=pa.bool_()),
        }
    )
    schema = contract(
        {"input": [column("a", BooleanType()), column("b", BooleanType())]},
        [
            column("both", BooleanType()),
            column("either", BooleanType()),
            column("negated", BooleanType()),
        ],
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Project(
                node_id="project",
                source="scan",
                columns=(
                    NamedExpression(
                        name="both",
                        expression=Boolean(
                            operation="and", arguments=(Column(name="a"), Column(name="b"))
                        ),
                    ),
                    NamedExpression(
                        name="either",
                        expression=Boolean(
                            operation="or", arguments=(Column(name="a"), Column(name="b"))
                        ),
                    ),
                    NamedExpression(name="negated", expression=Not(argument=Column(name="a"))),
                ),
            ),
        ),
        output="project",
    )
    expected = pa.table(
        {
            "both": pa.array([False, None, False, False, None, False], type=pa.bool_()),
            "either": pa.array([True, True, True, None, True, None], type=pa.bool_()),
            "negated": pa.array([False, False, True, True, None, None], type=pa.bool_()),
        }
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)


def test_each_native_adapter_is_invoked_once_without_other_backend_fallback(tmp_path, monkeypatch):
    from collections import Counter

    from equiframe.adapters import DuckDBAdapter, PandasAdapter, PolarsAdapter

    calls = Counter()

    def counted(adapter_type):
        original = adapter_type.execute

        def wrapper(self, transformation, inputs, context):
            calls[self.engine] += 1
            return original(self, transformation, inputs, context)

        return wrapper

    for adapter in (PandasAdapter, PolarsAdapter, DuckDBAdapter):
        monkeypatch.setattr(adapter, "execute", counted(adapter))
    source = pa.table({"v": pa.array([1, 2], type=pa.int64())})
    schema = contract({"input": [column("v", INT)]}, [column("v", INT)])
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"),), output="scan")
    verify(plan, schema, {"input": source}, source, tmp_path)
    assert calls == {"pandas": 1, "polars": 1, "duckdb": 1}


def test_pandas_consumer_frame_and_masks_are_not_modified(tmp_path):
    import pandas as pd

    source = pa.table({"v": pa.array([1, None, 2], type=pa.int64())})
    consumer = source.to_pandas(types_mapper=pd.ArrowDtype)
    original = consumer.copy(deep=True)
    schema = contract({"input": [column("v", INT)]}, [column("v", INT)])
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"),), output="scan")
    compiled = native_compiler_registry().resolve("pandas").compile(plan, schema)
    registry = ef.TransformationRegistry()
    registry.register(compiled.transformation)
    result = ef.execute(
        ef.ExecutionPlan(
            contract=schema,
            engine="pandas",
            transformation_id=compiled.transformation.transformation_id,
        ),
        source=ef.LocalDataSource({"input": ef.PandasInput(consumer)}),
        registry=registry,
        work_dir=tmp_path,
    )
    assert result.state == "completed"
    pd.testing.assert_frame_equal(consumer, original)


def test_nul_and_quotes_in_literal_are_preserved_by_every_native_engine(tmp_path):
    value = "a'\x00b\x00"
    source = pa.table({"v": pa.array([1, 2], type=pa.int64())})
    schema = contract(
        {"input": [column("v", INT)]},
        [column("text", StringType(), nullable=False)],
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Project(
                node_id="project",
                source="scan",
                columns=(
                    NamedExpression(
                        name="text",
                        expression=LiteralExpression(
                            logical_type=StringType(), value=StringValue(value=value)
                        ),
                    ),
                ),
            ),
        ),
        output="project",
    )
    verify(plan, schema, {"input": source}, pa.table({"text": [value, value]}), tmp_path)


def test_negative_decimal38_bound_is_exact_and_not_context_rounded(tmp_path):
    dtype = DecimalType(precision=38, scale=0)
    source = pa.table({"amount": pa.array([Decimal("-" + "9" * 38)], type=pa.decimal128(38, 0))})
    schema = contract({"input": [column("amount", dtype)]}, [column("amount", dtype)])
    plan = RelationalPlan(nodes=(Scan(node_id="scan", table="input"),), output="scan")
    verify(plan, schema, {"input": source}, source, tmp_path)


@pytest.mark.parametrize("guard", ("aggregate", "sort"))
def test_intermediate_error_nodes_execute_before_optimizer_can_prune(tmp_path, guard):
    if guard == "aggregate":
        source = pa.table({"amount": pa.array([2**63 - 1, 1], type=pa.int64())})
        base = aggregation_plan(group_by=(), dtype=INT)
        plan = RelationalPlan(
            nodes=(
                *base.nodes,
                Project(
                    node_id="project",
                    source="aggregate",
                    columns=(NamedExpression(name="rows", expression=Column(name="rows")),),
                ),
            ),
            output="project",
        )
        schema = contract(
            {"input": [column("amount", INT)]},
            [column("rows", INT, nullable=False, unit="rows")],
            family="aggregations",
        )
    else:
        source = pa.table(
            {"drop_me": pa.array([1, 2], type=pa.int64()), "key": pa.array([9, 9], type=pa.int64())}
        )
        plan = RelationalPlan(
            nodes=(
                Scan(node_id="scan", table="input"),
                Sort(
                    node_id="sort",
                    source="scan",
                    by=(SortKey(column="key", direction="ascending", nulls="last"),),
                    ties="reject",
                ),
                Project(
                    node_id="project",
                    source="sort",
                    columns=(NamedExpression(name="key", expression=Column(name="key")),),
                ),
            ),
            output="project",
        )
        schema = contract(
            {"input": [column("drop_me", INT), column("key", INT)]}, [column("key", INT)]
        )
    registry = native_compiler_registry()
    for engine in ENGINES:
        assert registry.resolve(engine).check(plan, schema).supported
        result = run(plan, schema, {"input": source}, engine, tmp_path)
        assert result.state != "completed"
        assert result.output is None
        assert result.problem is not None
        assert result.problem.stage == ("planning" if engine == "polars" else "transformation")


def test_native_aggregate_with_final_sort_remains_supported(tmp_path):
    source = pa.table(
        {"currency": ["USD", "EUR", "USD"], "amount": pa.array([2, 4, 1], type=pa.int64())}
    )
    base = aggregation_plan(dtype=INT)
    plan = RelationalPlan(
        nodes=(
            *base.nodes,
            Sort(
                node_id="sort",
                source="aggregate",
                by=(SortKey(column="currency", direction="ascending", nulls="last"),),
                ties="reject",
            ),
        ),
        output="sort",
    )
    schema = contract(
        {"input": [column("currency", StringType()), column("amount", INT)]},
        [
            column("currency", StringType()),
            column("total", INT),
            column("rows", INT, nullable=False, unit="rows"),
        ],
        family="aggregations",
    )
    expected = pa.table(
        {
            "currency": ["EUR", "USD"],
            "total": pa.array([4, 3], type=pa.int64()),
            "rows": pa.array([1, 2], type=pa.int64()),
        }
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)


def test_native_count_valid_min_max_preserve_null_groups_and_exact_types(tmp_path):
    source = pa.table(
        {
            "currency": ["USD", "USD", "EUR", None],
            "amount": pa.array([3, None, None, 2], type=pa.int64()),
        }
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="scan", table="input"),
            Aggregate(
                node_id="aggregate",
                source="scan",
                group_by=("currency",),
                null_groups="retain",
                empty_sum="null",
                measures=(
                    Measure(
                        name="valid",
                        operation="count_valid",
                        column="amount",
                        logical_type=INT,
                        unit="rows",
                    ),
                    Measure(name="low", operation="min", column="amount", logical_type=INT),
                    Measure(name="high", operation="max", column="amount", logical_type=INT),
                ),
            ),
        ),
        output="aggregate",
    )
    schema = contract(
        {"input": [column("currency", StringType()), column("amount", INT)]},
        [
            column("currency", StringType()),
            column("valid", INT, nullable=False, unit="rows"),
            column("low", INT),
            column("high", INT),
        ],
        family="aggregations",
    )
    expected = pa.table(
        {
            "currency": ["USD", "EUR", None],
            "valid": pa.array([1, 0, 1], type=pa.int64()),
            "low": pa.array([3, None, 2], type=pa.int64()),
            "high": pa.array([3, None, 2], type=pa.int64()),
        }
    )
    verify(plan, schema, {"input": source}, expected, tmp_path)
