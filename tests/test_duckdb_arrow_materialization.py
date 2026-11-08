"""Wide native Arrow exports retain complete typed rows across record batches."""

from decimal import Decimal

import duckdb
import pyarrow as pa
import pytest
from test_migration_backends import column

import equiframe as ef

DECIMAL = ef.DecimalType(precision=18, scale=2)
WIDER_DECIMAL = ef.DecimalType(precision=19, scale=2)
INTEGER = ef.IntegerType(bits=64, signed=True)


def wide_fixture(row_count, width, *, arithmetic):
    # Consecutive pairs are identical whole rows, including their order key.
    positions = [index // 2 for index in range(row_count)]
    arrays = [pa.array(positions, type=pa.int64())]
    columns = [column("position", INTEGER, nullable=False)]
    expected_arrays = list(arrays)
    output_columns = list(columns)
    for index in range(width - 1):
        name = f"decimal_{index:03}"
        values = [
            None
            if (position + index) % 11 == 0
            else Decimal((position * 7 + index * 13) % 2001 - 1000) / Decimal(100)
            for position in positions
        ]
        arrays.append(pa.array(values, type=pa.decimal128(18, 2)))
        columns.append(column(name, DECIMAL))
        if arithmetic and index == 0:
            values = [None if value is None else value + Decimal("0.01") for value in values]
            expected_arrays.append(pa.array(values, type=pa.decimal128(19, 2)))
            output_columns.append(column(name, WIDER_DECIMAL))
        else:
            expected_arrays.append(arrays[-1])
            output_columns.append(columns[-1])
    names = [item.name for item in columns]
    ordered_input = pa.Table.from_arrays(arrays, names=names)
    source = ordered_input.take(pa.array(list(reversed(range(row_count))), type=pa.int64()))
    expected = pa.Table.from_arrays(expected_arrays, names=names)
    schema = ef.Contract(
        schema_version="1.0",
        contract_id="test.duckdb.materialization",
        revision=1,
        family="duplicates_order",
        inputs=(
            ef.TableSpec(
                name="input",
                schema_spec=ef.TableSchema(
                    columns=tuple(columns),
                    keys=(),
                    multiplicity="preserve",
                    order=ef.IgnoredOrder(),
                ),
            ),
        ),
        output=ef.TableSpec(
            name="output",
            schema_spec=ef.TableSchema(
                columns=tuple(output_columns),
                keys=(),
                multiplicity="preserve",
                order=ef.IgnoredOrder()
                if arithmetic
                else ef.SignificantOrder(
                    by=(ef.SortSpec(column="position", direction="ascending", nulls="last"),),
                    ties="preserve",
                ),
            ),
        ),
        preconditions=(),
        rules=(),
    )
    return source, expected, schema


def observe_real_exports(monkeypatch):
    original = duckdb.DuckDBPyConnection.to_arrow_table
    observed = []

    def export(connection, *args, **kwargs):
        # Delegate to the real C extension and return its exact result object.
        table = original(connection, *args, **kwargs)
        observed.append(
            {
                "rows": table.num_rows,
                "columns": table.num_columns,
                "positions": table["position"].to_pylist(),
                "decimal_values": table["decimal_000"].to_pylist(),
                "decimal_type": table.schema.field("decimal_000").type,
                "chunk_lengths": [len(chunk) for chunk in table["decimal_000"].chunks],
            }
        )
        return table

    monkeypatch.setattr(duckdb.DuckDBPyConnection, "to_arrow_table", export)
    return observed


def execute_and_read(source, schema, transformation, tmp_path):
    registry = ef.TransformationRegistry()
    registry.register(transformation)
    result = ef.execute(
        ef.ExecutionPlan(
            contract=schema,
            engine="duckdb",
            transformation_id=transformation.transformation_id,
            options=ef.ExecutionOptions(
                timeout_seconds=120.0,
                max_input_rows=source.num_rows,
                max_output_rows=source.num_rows,
                max_transport_bytes=8 * 1024**2,
                duckdb_memory_mb=256,
                duckdb_threads=1,
                duckdb_timezone="UTC",
            ),
        ),
        source=ef.LocalDataSource({"input": ef.ArrowInput(source)}),
        registry=registry,
        work_dir=tmp_path,
    )
    assert result.state == "completed", result.problem
    assert result.output is not None
    return ef.read_table(result.output.data)


@pytest.mark.parametrize("row_count,width", ((0, 64), (2048, 64), (2049, 64), (4097, 64), (5, 256)))
def test_plain_sql_exports_every_wide_decimal_row_in_order(tmp_path, monkeypatch, row_count, width):
    source, expected, schema = wide_fixture(row_count, width, arithmetic=False)
    before = source.to_pylist()
    exports = observe_real_exports(monkeypatch)
    transformation = ef.DuckDBTransformation(
        "wide_sql", 'SELECT * FROM "input" ORDER BY "position"', "test.materialization.v1"
    )
    actual = execute_and_read(source, schema, transformation, tmp_path)
    assert actual.equals(expected, check_metadata=True)
    assert source.to_pylist() == before
    assert len(exports) == 1 and exports[0]["rows"] == row_count
    assert exports[0]["positions"] == expected["position"].to_pylist()
    assert sum(exports[0]["chunk_lengths"]) == row_count
    assert all(length <= 2048 for length in exports[0]["chunk_lengths"])
    if row_count > 2048:
        assert len(exports[0]["chunk_lengths"]) > 1


@pytest.mark.parametrize("row_count,width", ((0, 64), (2048, 64), (2049, 64), (4097, 64), (5, 256)))
def test_ir_checkpoints_and_final_export_retain_full_decimal_rows(
    tmp_path, monkeypatch, row_count, width
):
    source, expected, schema = wide_fixture(row_count, width, arithmetic=True)
    before = source.to_pylist()
    expressions = [ef.NamedExpression(name="position", expression=ef.Column(name="position"))]
    for name in source.column_names[1:]:
        expression = ef.Column(name=name)
        if name == "decimal_000":
            expression = ef.Arithmetic(
                operation="add",
                left=expression,
                right=ef.LiteralExpression(
                    value=ef.DecimalValue(value="0.01"), logical_type=DECIMAL, unit="units"
                ),
                logical_type=WIDER_DECIMAL,
                unit="units",
                overflow="reject",
                rounding="exact",
            )
        expressions.append(ef.NamedExpression(name=name, expression=expression))
    plan = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(node_id="project", source="scan", columns=tuple(expressions)),
            ef.Sort(
                node_id="ordered",
                source="project",
                by=(ef.SortKey(column="position", direction="ascending", nulls="last"),),
                # Equal positions are identical whole rows. The fixture still
                # checks their exact observed order and duplicate multiplicity.
                ties="unspecified",
            ),
        ),
        output="ordered",
    )
    compiled = ef.native_compiler_registry().resolve("duckdb").compile(plan, schema)
    exports = observe_real_exports(monkeypatch)
    actual = execute_and_read(source, schema, compiled.transformation, tmp_path)
    assert actual.equals(expected, check_metadata=True)
    assert source.to_pylist() == before
    # One real export for every eager checkpoint, followed by final materialization.
    assert len(exports) == len(compiled.transformation.checkpoints) + 1
    assert len(exports) >= 4
    assert all(item["rows"] == row_count for item in exports)
    assert exports[0]["positions"] == source["position"].to_pylist()
    assert exports[0]["decimal_values"] == source["decimal_000"].to_pylist()
    assert exports[0]["decimal_type"] == pa.decimal128(18, 2)
    assert exports[-2]["positions"] == exports[-1]["positions"] == expected["position"].to_pylist()
    assert (
        exports[-2]["decimal_values"]
        == exports[-1]["decimal_values"]
        == (expected["decimal_000"].to_pylist())
    )
    assert exports[-2]["decimal_type"] == exports[-1]["decimal_type"] == pa.decimal128(19, 2)
    assert all(sum(item["chunk_lengths"]) == row_count for item in exports)
    assert all(length <= 2048 for item in exports for length in item["chunk_lengths"])
    if row_count > 2048:
        assert all(len(item["chunk_lengths"]) > 1 for item in exports)
