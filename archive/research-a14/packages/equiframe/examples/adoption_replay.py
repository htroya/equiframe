"""Offline synthetic repeat-use replay, not human adoption or a production CI run.

Copy this single file from the verified sdist outside the checkout and run it
with the exact installed wheel and reviewed pandas/duckdb/Arrow dependencies:
    python adoption_replay.py --output new-replay --wheel-sha256 <verified-hash>

Three consumer contexts keep their exact contracts across an initial fixture and
a genuinely changed input. Each checks literal expectations, a deliberate bug,
an invalid expected output and resource-limit abstention. The replay exits zero
only when these expected outcomes, including failed assertions, are observed.
That zero is a replay check, NEVER acceptance of the deliberately bad outputs.

Only redacted reports and a technical receipt survive; temporary raw captures
are deleted. The receipt includes explicit local import paths for provenance;
review those paths before sharing it. No environment dump, private input, network,
timing-as-human-effort, user identity or human confirmation is collected. The
runner-supplied wheel hash is recorded, not authenticated or verified by this
script. The runner must independently establish its exact installed artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
import tempfile
from datetime import datetime
from datetime import timezone as _timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import equiframe as ef

UTC = _timezone.utc

CONTEXTS = ("refactor_python", "sql_duckdb", "ci_regression")
PHASES = ("initial", "follow_up")
CASES = ("equivalent", "different", "invalid_expected", "resource_limited")
REPORT_FILES = {"report.json", "report.html", "report.txt", "evidence-manifest.json"}


class ReplayError(RuntimeError):
    """A replay/setup failure; not a successful comparison."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2).encode() + b"\n"


def declaration(context: str) -> ef.DiffContract:
    """Same exact revision in both phases; nothing is relaxed after a failure."""
    sql = context == "sql_duckdb"
    columns = (
        ef.ColumnSpec(
            name="id",
            logical_type=ef.StringType(),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
        ),
        ef.ColumnSpec(
            name="value",
            logical_type=(
                ef.DecimalType(precision=12, scale=2)
                if sql
                else ef.IntegerType(bits=64, signed=True)
            ),
            nullable=sql,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(
                comparison="exact",
                unit="USD" if sql else "USD_cent" if context == "refactor_python" else "items",
            ),
        ),
    )
    kwargs = {"contract_id": "replay.synthetic." + context, "revision": 1}
    if sql:
        return ef.bag_contract(columns, multiplicity="preserve", **kwargs)
    return ef.keyed_contract(columns, keys=["id"], **kwargs)


def fixture(context: str, phase: str) -> tuple[dict[str, Any], Any]:
    """The expected values below are literals, never generated from a candidate."""
    import pyarrow as pa

    repeat = phase == "follow_up"
    if context == "sql_duckdb":
        source = {
            "id": ["café", "空", "café", "", "niño"] + (["new"] if repeat else []),
            "unit_price": ["10.10", None, "10.10", "0.00", "1.05"] + (["0.75"] if repeat else []),
            "quantity": [3, 1, 3, 3, 4, 3] if repeat else [2, 1, 2, 3, 3],
        }
        ids = ["niño", "café", "空", "", "café"] + (["new"] if repeat else [])
        values = (
            ["4.20", "30.30", None, "0.00", "30.30", "2.25"]
            if repeat
            else ["3.15", "20.20", None, "0.00", "20.20"]
        )
        expected = pa.table(
            {
                "id": pa.array(ids, type=pa.string()),
                "value": pa.array(
                    [None if value is None else Decimal(value) for value in values],
                    type=pa.decimal128(12, 2),
                ),
            }
        )
    else:
        ids = ["A", "B", "C", "D"] if repeat else ["A", "B", "C"]
        if context == "refactor_python":
            quantities = [1, 4, 3, 2] if repeat else [1, 2, 3]
            prices = [1000, 1250, 1000, 500] if repeat else [1000, 1000, 1000]
            values = [1000, 5000, 3000, 1000] if repeat else [1000, 2000, 3000]
            source = {"id": ids, "quantity": quantities, "unit_cents": prices}
        else:
            source = {"id": ids, "quantity": [3, 0, 5, 8] if repeat else [1, 2, 3]}
            values = [6, 0, 10, 16] if repeat else [2, 4, 6]
        expected = pa.table({"id": ids, "value": pa.array(values, type=pa.int64())})
    return source, expected


def materialize(
    context: str,
    source: dict[str, Any],
    expected: Any,
    *,
    fault: bool,
    private: Path,
) -> object:
    """Native pandas/SQL, or the small application transform used by the CI gate."""
    if context == "refactor_python":
        import pandas as pd

        frame = pd.DataFrame(source)
        frame["id"] = frame["id"].astype("string[pyarrow]")
        legacy = [
            int(quantity) * int(price)
            for quantity, price in zip(frame["quantity"], frame["unit_cents"], strict=True)
        ]
        if legacy != expected["value"].to_pylist():
            raise ReplayError("The old implementation does not match the literal fixture")
        return (
            pd.DataFrame(
                {
                    "id": frame["id"],
                    "value": frame["quantity"] * frame["unit_cents"]
                    + frame["id"].eq("B").astype("int64") * int(fault),
                }
            )
            .iloc[::-1]
            .reset_index(drop=True)
        )
    if context == "sql_duckdb":
        import duckdb

        with duckdb.connect(
            ":memory:",
            config={
                "autoinstall_known_extensions": False,
                "autoload_known_extensions": False,
                "enable_external_access": False,
                "python_enable_replacements": False,
                "threads": 1,
            },
        ) as connection:
            connection.execute(
                "CREATE TABLE sales (id VARCHAR, unit_price DECIMAL(12, 2), quantity INTEGER)"
            ).fetchall()
            connection.executemany(
                "INSERT INTO sales VALUES (?, ?, ?)",
                list(zip(source["id"], source["unit_price"], source["quantity"], strict=True)),
            )
            expression = "COALESCE(unit_price * quantity, 0)" if fault else "unit_price * quantity"
            captured = ef.capture_duckdb(
                f"SELECT id, CAST({expression} AS DECIMAL(12, 2)) AS value FROM sales",
                connection=connection,
                exclusive_connection=True,
                work_dir=private / "capture",
                options=ef.DuckDBCaptureOptions(max_rows=100, max_bytes=64 * 1024, batch_rows=2),
            )
            # Comparison must consume the detached capture after the live source
            # changes and disappears, never reexecute the SQL while reporting.
            connection.execute("UPDATE sales SET unit_price = 999.99").fetchall()
            connection.execute("DROP TABLE sales").fetchall()
        return captured
    import pyarrow as pa

    return pa.table(
        {
            "id": source["id"],
            "value": pa.array(
                [
                    quantity * 2 + int(fault and identifier == "B")
                    for identifier, quantity in zip(source["id"], source["quantity"], strict=True)
                ],
                type=pa.int64(),
            ),
        }
    )


def table_digest(table: Any) -> str:
    """Hash synthetic expected values with explicit schema and Decimal tags."""
    rows = [
        {
            key: {"decimal": str(value)} if isinstance(value, Decimal) else value
            for key, value in row.items()
        }
        for row in table.to_pylist()
    ]
    return digest(json_bytes({"schema": str(table.schema), "rows": rows}))


def verify_report(directory: Path) -> dict[str, str]:
    """Closed redacted publication check, adapted from the existing CI recipe."""
    if directory.is_symlink() or {path.name for path in directory.iterdir()} != REPORT_FILES:
        raise ReplayError("Unexpected report inventory")
    if any(
        (directory / name).is_symlink() or not (directory / name).is_file() for name in REPORT_FILES
    ):
        raise ReplayError("Report inventory contains a non-file")
    manifest = ef.ReportPublicationManifest.model_validate_json(
        (directory / "evidence-manifest.json").read_bytes()
    )
    if {item.path for item in manifest.files} != REPORT_FILES - {"evidence-manifest.json"}:
        raise ReplayError("Unexpected report manifest")
    for item in manifest.files:
        raw = (directory / item.path).read_bytes()
        if len(raw) != item.size_bytes or digest(raw) != item.sha256:
            raise ReplayError("Report integrity failed")
    report = ef.read_comparison_report(directory / "report.json")
    if (
        not manifest.publication_complete
        or report.options.mode != "diagnostic"
        or report.options.include_values
        or report.options.include_metadata
        or not report.evidence.values_withheld
        or not report.evidence.metadata_withheld
        or report.evidence.reproduction != "not_requested"
        or manifest.report_evidence != report.evidence
    ):
        raise ReplayError("Report is not a verified redacted publication")
    return {name: digest((directory / name).read_bytes()) for name in sorted(REPORT_FILES)}


def expected_outcome(case: str) -> dict[str, Any]:
    return {
        "state": "equivalent"
        if case == "equivalent"
        else "different"
        if case == "different"
        else "not_evaluable",
        "complete": case != "resource_limited",
        "accepted": case == "equivalent",
        "gate_code": 0 if case == "equivalent" else 1 if case == "different" else 3,
        "assertion": None
        if case == "equivalent"
        else "EquivalenceDifferentError"
        if case == "different"
        else "EquivalenceNotEvaluableError",
    }


def run_case(context: str, phase: str, case: str, output: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": f"{context}-{phase}-{case}",
        "context": context,
        "phase": phase,
        "case": case,
        "expected": expected_outcome(case),
        "observed": None,
        "technical_pass": False,
        "stage": "fixture",
        "error_type": None,
    }
    try:
        import pyarrow as pa

        source, expected = fixture(context, phase)
        record["input_sha256"] = digest(json_bytes(source))
        record["literal_expected_sha256"] = table_digest(expected)
        contract = declaration(context)
        record["contract_sha256"] = ef.contract_fingerprint(contract.spec.contract)
        record["declaration_sha256"] = digest(contract.model_dump_json().encode())
        record["contract_revision"] = contract.spec.contract.revision
        record["contract_change"] = "unchanged"
        record["human_contract_review"] = "not_claimed"
        with tempfile.TemporaryDirectory(prefix="equiframe-replay-private-") as temporary:
            private = Path(temporary)
            record["stage"] = "materialize"
            candidate = materialize(
                context,
                source,
                expected,
                fault=case == "different",
                private=private,
            )
            if case == "invalid_expected":
                # An actual contract violation in the right-hand expected, not
                # a fabricated ComparisonResult and never a repaired baseline.
                ids = expected["id"].to_pylist()
                ids[0] = None
                expected = expected.set_column(0, "id", pa.array(ids, type=pa.string()))
            record["compared_expected_sha256"] = table_digest(expected)
            record["stage"] = "comparison"
            options = ef.ComparisonOptions(max_rows=1 if case == "resource_limited" else 100)
            record["comparison_options"] = options.model_dump(mode="json")
            result = ef.diff(
                candidate,
                expected,
                contract=contract,
                work_dir=private / "comparison",
                options=options,
            )
            policy = ef.EquivalencePolicy(require_persisted_evidence=True)
            decision = ef.equivalence_decision(result, policy=policy, evidence_root=private)
            # Preserve the real verdict even if later report publication fails.
            record["observed"] = {
                "state": result.state,
                "complete": result.complete,
                "accepted": decision.accepted,
                "gate_code": None,
                "assertion": "not_run",
            }
            record["evidence_status"] = decision.evidence_status
            record["captured_sha256"] = {
                "candidate": result.left.data.sha256 if result.left is not None else None,
                "expected": result.right.data.sha256 if result.right is not None else None,
            }
            record["diagnostic_codes"] = [item.code for item in result.diagnostics]
            record["counts"] = result.counts.model_dump(mode="json")
            record["stage"] = "report"
            report_dir = output / record["id"]
            ef.write_comparison_report(
                result,
                report_dir,
                evidence_root=private,
                options=ef.ReportOptions(include_values=False, include_metadata=False),
            )
            record["report_sha256"] = verify_report(report_dir)
            record["stage"] = "assertion"
            try:
                ef.assert_equivalent(
                    result,
                    policy=policy,
                    evidence_root=private,
                    report_path=report_dir / "report.html",
                )
                assertion, gate_code = None, 0
            except ef.EquivalenceAssertionError as error:
                assertion = type(error).__name__
                gate_code = (
                    1
                    if isinstance(error, ef.EquivalenceDifferentError)
                    else 3
                    if isinstance(error, ef.EquivalenceNotEvaluableError)
                    else 2
                )
            record["observed"].update(assertion=assertion, gate_code=gate_code)
            record["technical_pass"] = (
                record["observed"] == record["expected"] and decision.evidence_status == "verified"
            )
            record["stage"] = "complete"
    except Exception as error:
        # Preserve failures and prior observations without exception messages,
        # tracebacks, raw rows, paths from dependency errors or a false success.
        record["error_type"] = type(error).__name__
        record["technical_pass"] = False
    return record


def provenance(wheel_sha256: str | None) -> dict[str, Any]:
    import duckdb
    import pandas
    import pyarrow

    modules = {"equiframe": ef, "pandas": pandas, "duckdb": duckdb, "pyarrow": pyarrow}
    return {
        "script_sha256": digest(Path(__file__).read_bytes()),
        "wheel_sha256": wheel_sha256,
        "wheel_binding": "runner_supplied_not_verified_here" if wheel_sha256 else "not_supplied",
        "python": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "imports": {
            name: {"version": importlib.metadata.version(name), "file": str(module.__file__)}
            for name, module in modules.items()
        },
    }


def run_replay(output: Path, *, wheel_sha256: str | None = None) -> dict[str, Any]:
    if wheel_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", wheel_sha256) is None:
        raise ReplayError("Wheel identity must be a lowercase SHA-256")
    if any(path.is_symlink() for path in (output, *output.parents)) or output.exists():
        raise ReplayError("Choose a new output directory without symlink ancestors")
    output.mkdir(parents=True)
    receipt: dict[str, Any] = {
        "receipt_format": "equiframe-synthetic-repeat-replay-1",
        "kind": "synthetic_replay",
        "occurred_at": datetime.now(UTC).isoformat(),
        "human_adoption": False,
        "independent_human_confirmation": False,
        "production_ci_job": False,
        "human_reporting_awareness": "pending",
        "human_upgrading_awareness": "pending",
        "human_integration_effort": None,
        "change": "Follow-up changes input quantities/prices and adds a row in each context",
        "contract_policy": "Same exact revision; no tolerance or expected-baseline relaxation",
        "technical_pass": False,
        "exit_code": 2,
        "error_type": None,
        "observations": [],
    }
    try:
        receipt["provenance"] = provenance(wheel_sha256)
        for context in CONTEXTS:
            for phase in PHASES:
                for case in CASES:
                    receipt["observations"].append(run_case(context, phase, case, output))
        receipt["repeat_checks"] = []
        for context in CONTEXTS:
            rows = [item for item in receipt["observations"] if item["context"] == context]
            initial, follow_up = rows[0], rows[len(CASES)]
            receipt["repeat_checks"].append(
                {
                    "context": context,
                    "input_changed": initial.get("input_sha256") != follow_up.get("input_sha256"),
                    "literal_expected_changed": initial.get("literal_expected_sha256")
                    != follow_up.get("literal_expected_sha256"),
                    "same_declaration": initial.get("declaration_sha256") is not None
                    and len({item.get("declaration_sha256") for item in rows}) == 1,
                }
            )
        receipt["technical_pass"] = all(
            item["technical_pass"] for item in receipt["observations"]
        ) and all(
            item["input_changed"] and item["literal_expected_changed"] and item["same_declaration"]
            for item in receipt["repeat_checks"]
        )
        receipt["exit_code"] = 0 if receipt["technical_pass"] else 2
    except Exception as error:
        receipt["error_type"] = type(error).__name__
    with (output / "receipt.json").open("xb") as stream:
        stream.write(json_bytes(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheel-sha256")
    args = parser.parse_args()
    try:
        receipt = run_replay(args.output, wheel_sha256=args.wheel_sha256)
    except Exception:
        print(
            "Replay setup/receipt failed; no technical pass established. Keep existing evidence.",
            file=sys.stderr,
        )
        return 2
    print("Synthetic repeat-use replay: " + ("passed" if receipt["technical_pass"] else "failed"))
    print("Expected failed gates are preserved; no human adoption or production CI claim.")
    return int(receipt["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
