"""Synthetic captured execution evidence for rules; no engine or oracle is invoked."""

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

import equiframe as ef


def captured(
    contract: ef.Contract, inputs: dict[str, pa.Table], output: pa.Table, root: Path
) -> ef.ExecutionResult:
    root.mkdir(parents=True, exist_ok=True)
    store = ef.LocalArtifactStore(root / "artifacts")

    def artifact(name: str, table: pa.Table) -> ef.TableArtifact:
        path = root / (name + ".arrow")
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)
        columns = tuple(
            ef.PhysicalColumn(
                name=field.name,
                engine_type=str(field.type),
                arrow_type=str(field.type),
                null_count=table[field.name].null_count,
                nan_count=int(pc.sum(pc.is_nan(table[field.name])).as_py() or 0)
                if pa.types.is_floating(field.type)
                else 0,
            )
            for field in table.schema
        )
        return ef.TableArtifact(
            name=name,
            data=store.put(path, media_type="application/vnd.apache.arrow.file"),
            row_count=table.num_rows,
            columns=columns,
        )

    plan = ef.ExecutionPlan(contract=contract, engine="captured", transformation_id="synthetic")
    return ef.ExecutionResult(
        run_id="run_synthetic",
        execution_id="exec_synthetic",
        plan=plan,
        contract_sha256=ef.contract_fingerprint(contract),
        implementation_version="synthetic-1",
        state="completed",
        started_at="2026-09-30T00:00:00Z",
        finished_at="2026-09-30T00:00:01Z",
        elapsed_seconds=1,
        timings=(),
        versions=(),
        capabilities=ef.EngineCapabilities(
            engine="captured",
            decimal_precision=76,
            timestamp_units=("s", "ms", "us", "ns"),
            zoned_timestamp_units=("s", "ms", "us", "ns"),
            lazy=False,
            cancellation="cooperative",
            resource_controls=(),
        ),
        effective_configuration=(),
        inputs=tuple(artifact(item.name, inputs[item.name]) for item in contract.inputs),
        output=artifact(contract.output.name, output),
        problem=None,
    )
