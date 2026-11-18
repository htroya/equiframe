"""Evaluate five technical synthetic captures using only the installed Arrow extra.

These captures are constructed for API demonstration; they are not native ETL runs,
oracle outputs, scientific benchmark cases or evidence about the DW.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.compute as pc

import equiframe as ef


def value(column: ef.ColumnSpec) -> object:
    literal = next((v for v in column.allowed_values if v.kind != "null"), None)
    if literal is not None:
        if isinstance(literal, ef.DateValue):
            return date.fromisoformat(literal.value)
        if isinstance(literal, ef.TimestampValue):
            epoch = date(1970, 1, 1).toordinal() * 86400 * 10**9
            return literal.nanoseconds(instant=True) - epoch
        if isinstance(literal, ef.NaNValue):
            return float("nan")
        return literal.value
    return {"currency": "USD", "supplier_id": "S1", "name": "supplier"}.get(column.name, "sample")


def arrow_type(dtype: ef.LogicalType) -> pa.DataType:
    if isinstance(dtype, ef.StringType):
        return pa.string()
    if isinstance(dtype, ef.BooleanType):
        return pa.bool_()
    if isinstance(dtype, ef.IntegerType):
        return getattr(pa, ("int" if dtype.signed else "uint") + str(dtype.bits))()
    if isinstance(dtype, ef.FloatType):
        return getattr(pa, "float" + str(dtype.bits))()
    if isinstance(dtype, ef.DecimalType):
        return (pa.decimal128 if dtype.precision <= 38 else pa.decimal256)(
            dtype.precision, dtype.scale
        )
    if isinstance(dtype, ef.DateType):
        return pa.date32()
    if isinstance(dtype, ef.TimestampType):
        return pa.timestamp(dtype.unit, dtype.timezone)
    raise TypeError("unsupported synthetic column type")


def table(spec: ef.TableSpec) -> pa.Table:
    return pa.table(
        {
            column.name: pa.array(
                [value(column)], type=arrow_type(column.logical_type), from_pandas=False
            )
            for column in spec.schema_spec.columns
        }
    )


def captured(contract: ef.Contract, directory: Path) -> ef.ExecutionResult:
    directory.mkdir(parents=True, exist_ok=False)
    store = ef.LocalArtifactStore(directory / "artifacts")

    def artifact(spec: ef.TableSpec) -> ef.TableArtifact:
        data = table(spec)
        path = directory / (spec.name + ".arrow")
        with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, data.schema) as writer:
            writer.write_table(data)
        columns = tuple(
            ef.PhysicalColumn(
                name=field.name,
                engine_type=str(field.type),
                arrow_type=str(field.type),
                null_count=data[field.name].null_count,
                nan_count=int(pc.sum(pc.is_nan(data[field.name])).as_py() or 0)
                if pa.types.is_floating(field.type)
                else 0,
            )
            for field in data.schema
        )
        return ef.TableArtifact(
            name=spec.name,
            data=store.put(path, media_type="application/vnd.apache.arrow.file"),
            row_count=data.num_rows,
            columns=columns,
        )

    plan = ef.ExecutionPlan(contract=contract, engine="synthetic", transformation_id="capture")
    result = ef.ExecutionResult(
        run_id="run_" + uuid4().hex,
        execution_id="exec_" + uuid4().hex,
        plan=plan,
        contract_sha256=ef.contract_fingerprint(contract),
        implementation_version="synthetic-capture-1",
        state="completed",
        started_at="2026-09-30T00:00:00Z",
        finished_at="2026-09-30T00:00:01Z",
        elapsed_seconds=1,
        timings=(),
        versions=(),
        capabilities=ef.EngineCapabilities(
            engine="synthetic",
            decimal_precision=76,
            timestamp_units=("s", "ms", "us", "ns"),
            zoned_timestamp_units=("s", "ms", "us", "ns"),
            lazy=False,
            cancellation="cooperative",
            resource_controls=(),
        ),
        effective_configuration=(),
        inputs=tuple(artifact(spec) for spec in contract.inputs),
        output=artifact(contract.output),
        problem=None,
    )
    with (directory / "run.json").open("x", encoding="utf-8") as manifest:
        manifest.write(result.model_dump_json())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(__file__).parent / "rules" / "catalog-1.0.json",
    )
    parser.add_argument("--work-dir", type=Path, default=Path.cwd() / "rule-example-runs")
    args = parser.parse_args()
    document = json.loads(args.catalog.read_text(encoding="utf-8"))
    digest = document.pop("catalog_sha256")
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf8"
    )
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("catalog fingerprint mismatch")
    registry, options = (
        ef.default_rule_registry(),
        ef.RuleOptions.model_validate(document["options"]),
    )
    for entry in document["entries"]:
        contract = ef.read_contract(args.catalog.parent / entry["contract_file"])
        if ef.contract_fingerprint(contract) != entry["contract_sha256"]:
            raise ValueError("contract fingerprint mismatch: " + entry["family"])
        if ef.rule_set_fingerprint(contract, registry, options) != entry["rule_set_sha256"]:
            raise ValueError("rule set fingerprint mismatch: " + entry["family"])
        execution = captured(contract, args.work_dir / (entry["family"] + "_" + uuid4().hex))
        result = ef.evaluate_rules(
            execution, options=options, registry=registry, work_dir=args.work_dir
        )
        print(entry["family"], result.decision, result.rule_set_sha256)
        if result.decision != "no_alert":
            raise RuntimeError("synthetic control failed: " + entry["family"])


if __name__ == "__main__":
    main()
