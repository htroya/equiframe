"""Generate a synthetic order batch, its reference binding and three CLI outcomes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow as pa

import equiframe as ef
from equiframe.evidence import canonical_bytes, describe_file, publish_json
from equiframe.serialization import contract_fingerprint

GROUP = ("buyer", "currency")
PLAN = {"operation": "sum", "measure": "cents", "group_by": GROUP}


def table_spec(name: str, columns: tuple[str, ...], keys: tuple[str, ...]) -> ef.TableSpec:
    return ef.TableSpec(
        name=name,
        schema_spec=ef.TableSchema(
            columns=tuple(
                ef.ColumnSpec(
                    name=column,
                    logical_type=ef.IntegerType(bits=64, signed=True)
                    if column == "cents"
                    else ef.StringType(),
                    nullable=False,
                    null_policy=ef.NullPolicy(representations=("null",)),
                    numeric_policy=ef.NumericPolicy(comparison="exact", unit="cents")
                    if column == "cents"
                    else None,
                )
                for column in columns
            ),
            keys=(
                ef.KeySpec(
                    name="primary",
                    columns=keys,
                    unique=True,
                    incomplete="reject",
                    scope=ef.TableKeyScope(),
                ),
            ),
            multiplicity="preserve",
            order=ef.IgnoredOrder(),
        ),
    )


def write_arrow(table: pa.Table, path: Path) -> ef.ArtifactRef:
    with path.open("xb") as stream, pa.ipc.new_file(stream, table.schema) as writer:
        writer.write_table(table)
    identity = describe_file(path, path.parent)
    return ef.ArtifactRef(
        schema_version="1.0",
        uri=path.as_uri(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        sha256=identity.sha256,
        size_bytes=identity.size_bytes,
    )


def prepare(work_dir: Path) -> None:
    work_dir.mkdir(parents=True, exist_ok=False)
    trusted = work_dir / "reference"
    trusted.mkdir()
    source = trusted / "orders.csv"
    source.write_text(
        "order_id,buyer,currency,cents\n1,A,USD,125\n2,A,USD,275\n3,B,USD,0\n",
        encoding="utf-8",
    )
    with source.open(encoding="utf-8", newline="") as stream:
        rows = [{**row, "cents": int(row["cents"])} for row in csv.DictReader(stream)]
    orders = pa.Table.from_pylist(rows)
    snapshot = write_arrow(orders, trusted / "orders.arrow")
    contract = ef.Contract(
        schema_version="1.0",
        contract_id="example.order_totals",
        revision=1,
        family="aggregations",
        inputs=(table_spec("orders", ("order_id", *GROUP, "cents"), ("order_id",)),),
        output=table_spec("totals", (*GROUP, "cents"), GROUP),
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="sum_by_group",
                revision=1,
                required=True,
                severity="error",
                specification=ef.AggregateCheck(
                    table="orders",
                    group_by=GROUP,
                    measure="cents",
                    function="sum",
                    output_table="totals",
                    output_column="cents",
                ),
            ),
        ),
    )

    # The reference producer computes from the input rows in integer cents.
    totals: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        totals[str(row["buyer"]), str(row["currency"])] += int(row["cents"])
    expected = pa.Table.from_pylist(
        [
            {"buyer": buyer, "currency": currency, "cents": cents}
            for (buyer, currency), cents in sorted(totals.items())
        ]
    )
    reference = write_arrow(expected, trusted / "expected.arrow")
    plan_sha256 = hashlib.sha256(canonical_bytes(PLAN)).hexdigest()
    binding = ef.ReferenceBinding(
        contract_sha256=contract_fingerprint(contract),
        plan_sha256=plan_sha256,
        comparison_spec_sha256=ef.comparison_fingerprint(ef.ComparisonSpec(contract=contract)),
        snapshots=(("orders", snapshot.sha256),),
        expected_sha256=reference.sha256,
        outputs=(),
    )
    publish_json(binding, trusted / "binding.json")

    # The candidate uses a separate Arrow aggregation and a separate output file.
    candidate = (
        orders.group_by(list(GROUP)).aggregate([("cents", "sum")]).rename_columns((*GROUP, "cents"))
    )
    values = candidate["cents"].to_pylist()
    values[0] += 1
    changed = candidate.set_column(2, "cents", pa.array(values, type=pa.int64()))
    for name, result in (("match", candidate), ("different", changed)):
        output = write_arrow(result, work_dir / f"{name}.arrow")
        request = ef.VerificationRequest(
            contract=contract,
            snapshots=(ef.PipelineInput(name="orders", artifact=snapshot),),
            outputs=(ef.PipelineInput(name="candidate", artifact=output),),
            expected=reference,
            plan_sha256=plan_sha256,
        )
        publish_json(request, work_dir / f"{name}.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True, help="New output directory.")
    args = parser.parse_args()
    directory = args.work_dir.resolve()
    prepare(directory)
    outcomes = {}
    for case, request, expected_exit, flags in (
        ("match", "match", 0, ()),
        ("different", "different", 1, ()),
        ("missing_execution", "match", 3, ("--require-execution",)),
    ):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "equiframe",
                "verify",
                "accept",
                str(directory / f"{request}.json"),
                "--reference-binding",
                str(directory / "reference" / "binding.json"),
                "--output",
                str(directory / "runs"),
                *flags,
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != expected_exit:
            raise RuntimeError(f"{case} exited {result.returncode}; expected {expected_exit}")
        report = json.loads(result.stdout)
        if report["publishable"] is not (expected_exit == 0):
            raise RuntimeError(f"{case} reported an unexpected acceptance decision")
        outcomes[case] = {
            "exit_code": result.returncode,
            "state": report["operational_state"],
            "report": "runs/" + report["verification_id"] + "/report.json",
        }
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
