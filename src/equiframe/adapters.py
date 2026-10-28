"""Three independent native engines; imports and connections are per execution."""

from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Mapping
from threading import Event, Thread
from typing import TYPE_CHECKING, cast

from equiframe._duckdb_transport import (
    duckdb_arrow_schema,
    duckdb_parameters,
    duckdb_temporal_capabilities,
    verify_duckdb_table,
)
from equiframe.errors import (
    CapabilityError,
    InvalidExecutionInput,
    NativeEngineError,
    ResourceLimitError,
)
from equiframe.execution import RunContext
from equiframe.execution_types import EngineCapabilities
from equiframe.registry import (
    DuckDBTransformation,
    PandasTransformation,
    PolarsTransformation,
    Transformation,
)
from equiframe.tables import (
    LoadedTable,
    check_arrow,
    copy_pandas_frame,
    pandas_capture,
    require_dependency,
)

if TYPE_CHECKING:
    import pyarrow as pa

    from equiframe.migration.backends._timestamp_transport import _TimestampCodec
    from equiframe.ports import EngineAdapter


def _input_capabilities(loaded: LoadedTable, engine: str, context: RunContext) -> None:
    import pyarrow as pa

    check_arrow(loaded.table)
    if engine == "duckdb" and len({name.casefold() for name in loaded.table.column_names}) != len(
        loaded.table.column_names
    ):
        raise CapabilityError("DuckDB would rename input columns that differ only by case")
    if loaded.meaningful_index and engine != "pandas":
        raise CapabilityError(
            "Pandas index requires index_policy='columns' or 'discard' for other engines"
        )
    if loaded.table.num_columns == 0 and (
        engine == "duckdb" or (engine == "pandas" and loaded.table.num_rows > 0)
    ):
        raise CapabilityError(f"{engine} does not support faithful zero-column table input")
    for field in loaded.table.schema:
        dtype = field.type
        if (
            engine != "pandas"
            and pa.types.is_decimal(dtype)
            and (pa.types.is_decimal256(dtype) or dtype.scale < 0)
        ):
            raise CapabilityError(f"{engine} requires decimal128 with a nonnegative scale")
        if engine == "polars" and pa.types.is_timestamp(dtype) and dtype.unit == "s":
            import pyarrow.compute as pc

            bounds = pc.min_max(loaded.table[field.name].cast(pa.int64())).as_py()
            if bounds["min"] is not None and (
                bounds["min"] < -(2**63 // 1000) or bounds["max"] > (2**63 - 1) // 1000
            ):
                raise CapabilityError(
                    "Polars seconds-to-milliseconds transport would overflow int64"
                )
        if engine == "polars" and pa.types.is_date64(dtype):
            raise CapabilityError("Polars converts date64 to timestamp; use explicit date32 input")
        if engine != "pandas" and pa.types.is_decimal(dtype) and dtype.precision > 38:
            raise CapabilityError(f"{engine} supports decimal precision at most 38")
        if (
            engine == "duckdb"
            and pa.types.is_timestamp(dtype)
            and dtype.tz
            and (dtype.unit == "ns" or dtype.tz != context.plan.options.duckdb_timezone)
        ):
            raise CapabilityError(
                "DuckDB rejects zoned ns and zones different from its session timezone"
            )
        if (
            engine == "duckdb"
            and pa.types.is_timestamp(dtype)
            and dtype.tz
            and dtype.unit in ("s", "ms")
        ):
            import pyarrow.compute as pc

            factor = 1_000_000 if dtype.unit == "s" else 1_000
            limit = (2**63 - 2) // factor
            bounds = pc.min_max(loaded.table[field.name].cast(pa.int64())).as_py()
            if bounds["min"] is not None and (bounds["min"] < -limit or bounds["max"] > limit):
                raise CapabilityError(
                    "DuckDB zoned timestamp transport requires finite int64 microseconds"
                )


class PandasAdapter:
    engine = "pandas"

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine=self.engine,
            required_packages=(self.engine, "pyarrow"),
            decimal_precision=76,
            timestamp_units=("s", "ms", "us", "ns"),
            zoned_timestamp_units=("s", "ms", "us", "ns"),
            lazy=False,
            cancellation="cooperative",
            resource_controls=("materialized rows/buffer checkpoints",),
        )

    def execute(
        self, transformation: Transformation, inputs: Mapping[str, LoadedTable], context: RunContext
    ) -> LoadedTable:
        require_dependency("pandas", "pandas")
        require_dependency("pyarrow", "pandas")
        import pandas as pd

        if not isinstance(transformation, PandasTransformation):
            raise InvalidExecutionInput("Pandas adapter requires a PandasTransformation")
        with context.measure("input_conversion"):
            tables = {}
            for name, loaded in inputs.items():
                _input_capabilities(loaded, self.engine, context)
                tables[name] = (
                    copy_pandas_frame(loaded.native)
                    if isinstance(loaded.native, pd.DataFrame)
                    else loaded.table.to_pandas(types_mapper=pd.ArrowDtype, ignore_metadata=True)
                )
        context.record_configuration(
            "pandas_timezone_source",
            "input tzinfo provider; Arrow retains zone/unit; engine rules are independent",
        )
        with context.measure("transformation"):
            frame = transformation.callback(tables, context)
        with context.measure("materialization"):
            return pandas_capture(frame)


class PolarsAdapter:
    engine = "polars"

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine=self.engine,
            required_packages=(self.engine, "pyarrow"),
            decimal_precision=38,
            timestamp_units=("s", "ms", "us", "ns"),
            zoned_timestamp_units=("s", "ms", "us", "ns"),
            lazy=True,
            cancellation="cooperative",
            resource_controls=("materialized rows/buffer checkpoints",),
        )

    def execute(
        self, transformation: Transformation, inputs: Mapping[str, LoadedTable], context: RunContext
    ) -> LoadedTable:
        require_dependency("polars", "polars")
        require_dependency("pyarrow", "polars")
        import polars as pl

        try:
            return self._execute_native(transformation, inputs, context)
        except pl.exceptions.PanicException as error:
            raise NativeEngineError(
                "Polars native code panicked; execution did not complete"
            ) from error

    def _execute_native(
        self, transformation: Transformation, inputs: Mapping[str, LoadedTable], context: RunContext
    ) -> LoadedTable:
        import polars as pl

        if not isinstance(transformation, PolarsTransformation):
            raise InvalidExecutionInput("Polars adapter requires a PolarsTransformation")
        codec = _timestamp_codec(self, transformation)
        with context.measure("input_conversion"):
            if codec is not None:
                inputs = codec.encode_inputs(inputs)
                context.record_configuration(
                    "ir_timestamp_transport", "unchanged int64 ticks with explicit unit/zone codec"
                )
            tables: dict[str, pl.DataFrame] = {}
            for name, loaded in inputs.items():
                _input_capabilities(loaded, self.engine, context)
                tables[name] = (
                    loaded.native.clone()
                    if isinstance(loaded.native, pl.DataFrame)
                    else cast("pl.DataFrame", pl.from_arrow(loaded.table))
                )
                if tables[name].shape != loaded.table.shape:
                    raise CapabilityError("Polars input conversion changed table dimensions")
        context.record_configuration(
            "polars_timezone_source",
            "chrono-tz compiled into locked polars runtime; IANA release not exposed by Python API",
        )
        context.record_configuration("polars_threads", str(pl.thread_pool_size()))
        with context.measure("planning"):
            output = transformation.callback(tables, context)
        if not isinstance(output, (pl.DataFrame, pl.LazyFrame)):
            raise InvalidExecutionInput("Polars transformation must return DataFrame/LazyFrame")
        with context.measure("materialization"):
            frame = output.collect() if isinstance(output, pl.LazyFrame) else output
            table = frame.to_arrow()
            if table.shape != frame.shape:
                raise CapabilityError("Polars output conversion changed table dimensions")
            if codec is not None:
                table = codec.decode_output(table)
            check_arrow(table)
        return LoadedTable(table, native_types=tuple((n, str(t)) for n, t in frame.schema.items()))


class DuckDBAdapter:
    engine = "duckdb"

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine=self.engine,
            required_packages=(self.engine, "pyarrow"),
            decimal_precision=38,
            timestamp_units=("s", "ms", "us", "ns"),
            zoned_timestamp_units=("s", "ms", "us"),
            lazy=False,
            cancellation="interrupt_query",
            resource_controls=(
                "DuckDB memory_limit (engine-managed memory only)",
                "DuckDB threads",
                "materialized rows/buffer checkpoints",
            ),
        )

    def execute(
        self, transformation: Transformation, inputs: Mapping[str, LoadedTable], context: RunContext
    ) -> LoadedTable:
        require_dependency("duckdb", "duckdb")
        require_dependency("pyarrow", "duckdb")
        import duckdb

        if not isinstance(transformation, DuckDBTransformation):
            raise InvalidExecutionInput("DuckDB adapter requires a DuckDBTransformation")
        from equiframe.migration.backends.duckdb import _DuckDBProgram

        program = transformation if isinstance(transformation, _DuckDBProgram) else None
        codec = _timestamp_codec(self, transformation)
        with context.measure("input_capabilities"):
            if codec is not None:
                inputs = codec.encode_inputs(inputs)
                context.record_configuration(
                    "ir_timestamp_transport", "unchanged int64 ticks with explicit unit/zone codec"
                )
            for name, loaded in inputs.items():
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) is None:
                    raise CapabilityError(
                        "DuckDB input identifiers allow ASCII letters, digits and underscores"
                    )
                _input_capabilities(loaded, self.engine, context)
                duckdb_temporal_capabilities(loaded.table)
        options = context.plan.options
        stopped = Event()
        connection: duckdb.DuckDBPyConnection | None = None

        def watch() -> None:
            if not (connection is not None):
                raise AssertionError("Internal invariant check failed.")
            while not stopped.wait(0.01):
                if context.cancellation.cancelled or (
                    context.deadline is not None and time.perf_counter() >= context.deadline
                ):
                    connection.interrupt()
                    # Keep interrupting until the active stage finishes, covering start races.

        watcher = Thread(target=watch, name=context.execution_id + "_interrupt", daemon=False)
        try:
            with context.measure("engine_setup"):
                connection = duckdb.connect(
                    ":memory:",
                    config={
                        "memory_limit": f"{options.duckdb_memory_mb}MB",
                        "threads": options.duckdb_threads,
                        "enable_external_access": False,
                        "autoinstall_known_extensions": False,
                        "python_enable_replacements": False,
                        "max_temp_directory_size": "0B",
                        "preserve_insertion_order": True,
                    },
                )
                connection.execute("SET TimeZone = ?", [options.duckdb_timezone])
                connection.execute("SET autoload_known_extensions=false")
                settings = connection.execute(
                    "SELECT current_setting('memory_limit'), current_setting('threads'), "
                    "current_setting('TimeZone'), current_setting('max_temp_directory_size')"
                ).fetchone()
                if not (settings is not None):
                    raise AssertionError("Internal invariant check failed.")
                for name, value in zip(
                    ("memory_limit", "threads", "timezone", "max_spill"), settings, strict=True
                ):
                    context.record_configuration("duckdb_effective_" + name, str(value))
            queries = (
                (*tuple(step.sql for step in program.checkpoints), program.final_sql)
                if program is not None
                else (transformation.sql,)
            )
            for query in queries:
                statements = connection.extract_statements(query)
                if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
                    raise InvalidExecutionInput(
                        "registered DuckDB SQL must be one SELECT/WITH query"
                    )
                if set(statements[0].named_parameters) != set(context.parameters):
                    raise InvalidExecutionInput(
                        "SQL named parameters must match execution plan parameters"
                    )
            if len({name.casefold() for name in inputs}) != len(inputs):
                raise InvalidExecutionInput("DuckDB input names must also be unique ignoring case")
            context.record_configuration(
                "duckdb_memory_limit", f"{options.duckdb_memory_mb}MB (not a total Python RSS cap)"
            )
            context.record_configuration("duckdb_threads", str(options.duckdb_threads))
            context.record_configuration("duckdb_timezone", options.duckdb_timezone)
            context.record_configuration(
                "duckdb_timezone_source",
                "bundled ICU extension in installed DuckDB wheel; independent of Python tzdata",
            )
            context.record_configuration(
                "duckdb_iana_release", "not exposed; installed wheel version recorded"
            )
            context.record_configuration(
                "duckdb_external_access",
                "disabled; no shared database, filesystem SQL or extension downloads",
            )
            with context.measure("input_conversion"):
                for name, loaded in inputs.items():
                    connection.register(name, loaded.table)
            watcher.start()
            with context.measure("transformation"):
                if program is not None:
                    available = {name.casefold() for name in inputs}
                    remaining = Counter(
                        name for step in program.checkpoints for name in step.dependencies
                    )
                    remaining[program.output_relation] += 1
                    if not program.checkpoints or not program.final_sql:
                        raise InvalidExecutionInput("DuckDB IR program requires native checkpoints")
                    context.record_configuration(
                        "duckdb_ir_checkpoints", str(len(program.checkpoints))
                    )
                    for step in program.checkpoints:
                        context.check()
                        if step.name.casefold() in available or any(
                            name.casefold() not in available for name in step.dependencies
                        ):
                            raise InvalidExecutionInput("DuckDB IR checkpoint dependency mismatch")
                        connection.execute(step.sql, duckdb_parameters(context.parameters))
                        observed = tuple(
                            (str(item[0]), str(item[1])) for item in connection.description or ()
                        )
                        duckdb_arrow_schema(observed, options.duckdb_timezone)
                        intermediate = cast("pa.Table", connection.to_arrow_table(batch_size=2048))
                        verify_duckdb_table(intermediate, observed, options.duckdb_timezone)
                        context.check_table(intermediate, output=False, enforce_rows=False)
                        connection.register(step.name, intermediate)
                        available.add(step.name.casefold())
                        for name in step.dependencies:
                            remaining[name] -= 1
                            if remaining[name] == 0:
                                connection.unregister(name)
                                available.remove(name.casefold())
                    if program.output_relation.casefold() not in available:
                        raise InvalidExecutionInput("DuckDB IR output checkpoint is missing")
                    query = program.final_sql
                else:
                    query = transformation.sql
                connection.execute(query, duckdb_parameters(context.parameters))
                native_types = tuple(
                    (str(item[0]), str(item[1])) for item in connection.description or ()
                )
            with context.measure("materialization"):
                duckdb_arrow_schema(native_types, options.duckdb_timezone)
                table = cast("pa.Table", connection.to_arrow_table(batch_size=2048))
                verify_duckdb_table(table, native_types, options.duckdb_timezone)
                if codec is not None:
                    table = codec.decode_output(table)
            return LoadedTable(
                table,
                native_types=native_types,
                notes=(
                    "Observed DuckDB order retained; SQL without ORDER BY has no order guarantee.",
                ),
            )
        except duckdb.OutOfMemoryException as error:
            raise ResourceLimitError("DuckDB engine memory limit exhausted") from error
        except duckdb.InterruptException:
            context.check()
            raise
        finally:
            stopped.set()
            if watcher.ident is not None:
                watcher.join()
            if connection is not None:
                connection.close()


def _timestamp_codec(
    adapter: EngineAdapter, transformation: Transformation
) -> _TimestampCodec | None:
    """Only native adapters for the matching compiler understand tick encodings."""
    from equiframe.migration.backends._timestamp_transport import (
        _TimestampDuckDBTransformation,
        _TimestampPolarsTransformation,
    )
    from equiframe.migration.backends.duckdb import _DuckDBProgram

    if isinstance(transformation, _DuckDBProgram) and not isinstance(adapter, DuckDBAdapter):
        raise CapabilityError("DuckDB IR checkpoints require the native DuckDB adapter")

    if (
        isinstance(adapter, DuckDBAdapter)
        and isinstance(transformation, _TimestampDuckDBTransformation)
    ) or (
        isinstance(adapter, PolarsAdapter)
        and isinstance(transformation, _TimestampPolarsTransformation)
    ):
        codec = transformation.timestamp_codec
        if codec is None:
            raise InvalidExecutionInput("IR timestamp transformation requires its explicit codec")
        return codec
    return None


def native_adapter(engine: str) -> EngineAdapter:
    adapters: dict[str, EngineAdapter] = {
        "pandas": PandasAdapter(),
        "polars": PolarsAdapter(),
        "duckdb": DuckDBAdapter(),
    }
    try:
        return adapters[engine]
    except KeyError:
        raise CapabilityError("unknown native engine; inject an explicit EngineAdapter") from None
