"""Run complete installed consumer workflows and preserve their true exit status."""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import cast

import pyarrow as pa

import equiframe as ef

from .evidence import (
    ConsumerError,
    JsonObject,
    PublicationCommittedError,
    PublicationReceipt,
    environment,
    frozen_manifest_sha256,
    inventory,
    publish,
    replace_owned_json,
    require,
    sha256,
    verify_frozen,
    verify_report,
    write_json,
)
from .programs import ENGINES, PROGRAM_INPUT_PATHS, PROGRAMS, VARIANTS, load_program, table

EXPECTED_EXIT = {"good": 0, "defect": 1, "not_evaluable": 3}


def comparison_gate(result: ef.ComparisonResult) -> tuple[bool, str | None]:
    try:
        ef.assert_equivalent(result)
    except ef.EquivalenceAssertionError as error:
        return False, type(error).__name__
    return True, None


def run_case(
    data: Path, output: Path, *, program: str, variant: str, source: str, target: str
) -> int:
    require(
        not output.exists(), "Use a new output directory; existing evidence is never overwritten"
    )
    output.mkdir(parents=True)
    started = time.monotonic()
    record: JsonObject = {
        "consumer_version": "0.1.19",
        "program": program,
        "variant": variant,
        "direction": source + "->" + target,
        "expected_exit_code": EXPECTED_EXIT[variant],
        "status": "RUNNING",
        "accepted": False,
        "data_checks_accepted": False,
        "published": False,
        "publication_state": "not_attempted",
        "native_execution_count_complete": True,
        "independent_business_oracle": "not_established",
        "human_review": "not_claimed",
    }
    code = 2
    try:
        record["environment"] = environment()
        required_paths = (PROGRAM_INPUT_PATHS[program],)
        record["dataset_manifest_sha256"] = frozen_manifest_sha256(data)
        frozen = verify_frozen(
            data,
            required_paths=required_paths,
            expected_manifest_sha256=record["dataset_manifest_sha256"],
        )
        p = load_program(program, data)
        record["problem"] = p.description
        record["frozen_input_rows"] = len(p.independent_input_rows)
        record["expected_output_rows"] = len(p.independent_expected_rows)
        record["frozen_source"] = {
            "path": p.source_file.relative_to(data).as_posix(),
            "sha256": sha256(p.source_file),
        }
        # Independent expected literals/calculations are fixed before mutation/ETL.
        expected = table(p.independent_expected_rows, p.output_columns)
        expected_input = table(p.independent_input_rows, p.input_columns)
        write_json(output / "independent-expected.json", p.independent_expected_rows)
        write_json(
            output / "expected-method.json",
            {
                "method": (
                    "stdlib CSV/JSON parsing plus Decimal/integer accumulation and direct "
                    "timestamp parsing; no native-engine/EquiFrame transformation"
                ),
                "business_truth": "unknown",
                "data_domains": frozen.get("domains", []),
                "data_labels": "none",
                "model_training": "none",
            },
        )
        ingestion = ef.ingest_file(
            p.source_file, spec=p.ingestion, work_dir=output / "ingestion", batch_rows=17
        )
        if ingestion.state != "completed" or ingestion.output is None:
            raise ConsumerError("Real-data ingestion did not complete")
        record["ingestion"] = {
            "state": ingestion.state,
            "accepted_records": ingestion.accepted_records,
            "source_sha256": ingestion.source.sha256,
            "batch_rows": 17,
        }
        captured = ef.read_table(ingestion.output)
        input_comparison = ef.diff(
            captured, expected_input, work_dir=output / "ingestion-comparison"
        )
        ef.assert_equivalent(input_comparison)
        ef.write_comparison_report(input_comparison, output / "reports" / "ingestion-expected")
        verify_report(output / "reports" / "ingestion-expected")
        baseline = captured
        if variant == "defect":
            captured, mutation = p.mutate(captured)
            write_json(output / "derived-mutation.json", mutation)
        record["actual_candidate_input_rows"] = captured.num_rows
        spec = p.spec(source, target, variant)
        write_json(output / "migration-spec.json", spec.model_dump(mode="json"))
        record["native_execution_count_complete"] = False
        native = ef.migrate(
            spec,
            source=p.native_source(captured, baseline),
            expected=ef.ArrowInput(expected),
            work_dir=output / "native",
        )
        native_root = output / "native" / native.migration_id
        require(ef.read_migration(native_root) == native, "Migration evidence readback differs")
        record["native_result"] = {
            "state": native.state,
            "verification": native.verification,
            "complete": native.complete,
            "exit_code": native.exit_code,
            "migration_id": native.migration_id,
            "stages": [s.model_dump(mode="json") for s in native.stages],
            "compilers": [c.model_dump(mode="json") for c in native.compilers],
            "executions": [
                {
                    "engine": engine,
                    "state": child.execution.state,
                    "execution_id": child.execution.execution_id,
                    "rows": child.execution.output.row_count
                    if child.execution.output is not None
                    else None,
                }
                for engine, child in ((source, native.source), (target, native.target))
                if child is not None and child.execution is not None
            ],
        }
        record["native_execution_count_complete"] = True
        comparisons = (
            ("source-target", native.comparison),
            ("source-expected", native.verification_source),
            ("target-expected", native.verification_target),
        )
        gate_records = []
        for name, result in comparisons:
            if result is None:
                gate_records.append({"name": name, "present": False, "accepted": False})
                continue
            ef.write_comparison_report(result, output / "reports" / name, evidence_root=native_root)
            verify_report(output / "reports" / name)
            accepted, error = comparison_gate(result)
            gate_records.append(
                {
                    "name": name,
                    "present": True,
                    "state": result.state,
                    "complete": result.complete,
                    "counts": result.counts.model_dump(mode="json"),
                    "accepted": accepted,
                    "rejection": error,
                }
            )
        record["comparison_gates"] = gate_records
        accepted = (
            native.complete is True
            and native.exit_code == 0
            and native.verification == "correct"
            and len(gate_records) == 3
            and all(g["accepted"] is True for g in gate_records)
        )
        record["data_checks_accepted"] = accepted
        record["accepted"] = accepted
        record["evidence_integrity_verified"] = True
        # Hashes and closed inventory are evidence integrity, never acceptance.
        ef.export_bundle(native_root, output / "portable")
        bundle_hash = sha256(output / "portable" / "bundle.json")
        away = output / "native-origin-unavailable"
        (output / "native").rename(away)
        try:
            ef.read_bundle(output / "portable", expected_sha256=bundle_hash)
            record["portable_verified_without_native_origin"] = True
        finally:
            away.rename(output / "native")
        record["bundle_manifest_sha256"] = bundle_hash
        # Every required source/integrity/acceptance check precedes visibility commit.
        verify_frozen(
            data,
            required_paths=required_paths,
            expected_manifest_sha256=record["dataset_manifest_sha256"],
        )
        record["frozen_data_unchanged"] = True
        if accepted:
            if (
                native.target is None
                or native.target.execution is None
                or native.target.execution.output is None
            ):
                raise ConsumerError("No target materialization")
            result_table = ef.read_table(native.target.execution.output.data)
            record["publication"] = publish(
                result_table,
                output / "publication",
                accepted=accepted,
                precommit=lambda receipt: prepare_publication_receipts(output, record, receipt),
            )
            record["published"] = True
            record["publication_state"] = "committed"
        else:
            require(not (output / "publication").exists(), "Rejected data must not publish")
        code = 0 if accepted else native.exit_code
        if code == 0:
            # The core may report technically completed while app acceptance fails.
            code = 3
        if accepted:
            code = 0
        record["status"] = (
            "PASS"
            if code == 0
            else ("EXPECTED_REJECTION" if code == EXPECTED_EXIT[variant] else "FAIL")
        )
        record["observed_exit_code"] = code
    except Exception as error:
        if isinstance(error, PublicationCommittedError):
            record["published"] = True
            record["publication"] = error.receipt
        record["status"] = "FAIL"
        record["accepted"] = False
        record["publication_state"] = (
            "committed_application_incomplete" if record["published"] else "not_committed"
        )
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        try:
            (output / "failure-traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            record["traceback_receipt_unavailable"] = True
        record["observed_exit_code"] = 2
        code = 2
    record["elapsed_seconds"] = time.monotonic() - started
    code = finalize_case(output, record, code)
    print(
        json.dumps(
            {
                k: record.get(k)
                for k in (
                    "program",
                    "variant",
                    "direction",
                    "status",
                    "accepted",
                    "published",
                    "observed_exit_code",
                )
            }
        )
    )
    return code


def prepare_publication_receipts(
    output: Path, record: JsonObject, proposed: PublicationReceipt
) -> None:
    """Required acceptance/evidence receipts are prepared before visibility commit.

    The proposed version is explicitly not yet committed. The staging area is
    excluded from this inventory because publication moves it atomically.
    """
    prepublication = {
        **record,
        "phase": "precommit",
        "accepted": False,
        "published": False,
        "publication_state": "prepared_not_committed",
        "proposed_publication": proposed,
    }
    write_json(output / "prepublication.json", prepublication)
    members = [f for f in inventory(output) if not f["path"].startswith("publication/")]
    write_json(output / "required-evidence-manifest.json", {"phase": "precommit", "files": members})
    for item in members:
        path = output / item["path"]
        require(
            path.is_file()
            and path.stat().st_size == item["size_bytes"]
            and sha256(path) == item["sha256"],
            "Required prepublication evidence changed",
        )


def finalize_case(output: Path, record: JsonObject, code: int) -> int:
    """Final evidence failure never returns successful application acceptance.

    Publication is a distinct committed fact: a subsequent evidence write failure
    cannot truthfully claim it never occurred. One bounded receipt repair is made.
    """
    try:
        write_json(output / "case.json", record)
        write_json(
            output / "app-manifest.json", {"files": inventory(output), "status": record["status"]}
        )
        return code
    except Exception as error:
        record.update(
            status="FAIL",
            accepted=False,
            observed_exit_code=2,
            failure_stage="terminal_evidence",
            error={"type": type(error).__name__, "message": str(error)},
            publication_state="committed_application_incomplete"
            if record.get("published") is True
            else "not_committed",
        )
        try:
            replace_owned_json(output / "case.json", record)
            replace_owned_json(
                output / "app-manifest.json", {"files": inventory(output), "status": "FAIL"}
            )
        except Exception as repair_error:
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "exit_code": 2,
                        "stage": "terminal_evidence",
                        "published": record.get("published"),
                        "receipt_unavailable": True,
                        "error_type": type(repair_error).__name__,
                    }
                ),
                file=sys.stderr,
            )
        return 2


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _read_case(
    path: Path,
    expected: tuple[str, str, str, str],
    returncode: int,
    *,
    optimized: bool,
) -> tuple[JsonObject | None, str | None]:
    try:
        if not path.is_file():
            return None, "missing_case_receipt"
        if path.stat().st_size > 4 * 1024 * 1024:
            return None, "case_receipt_exceeds_4MiB"
        case = json.loads(path.read_text(encoding="utf-8"))
        p, v, s, t = expected
        if not isinstance(case, dict):
            return None, "case_receipt_not_object"
        if any(
            case.get(k) != wanted
            for k, wanted in (
                ("program", p),
                ("variant", v),
                ("direction", s + "->" + t),
                ("observed_exit_code", returncode),
            )
        ):
            return None, "case_receipt_identity_or_exit_differs"
        if type(case.get("accepted")) is not bool or type(case.get("published")) is not bool:
            return None, "case_receipt_gates_missing"
        native = case.get("native_result", {})
        if not isinstance(native, dict) or not isinstance(native.get("executions", []), list):
            return None, "case_receipt_native_inventory_malformed"
        if type(case.get("native_execution_count_complete")) is not bool:
            return None, "case_receipt_native_coverage_missing"
        child_environment = case.get("environment")
        if (
            not isinstance(child_environment, dict)
            or type(child_environment.get("isolated")) is not int
            or child_environment["isolated"] != 1
            or type(child_environment.get("optimized")) is not int
            or child_environment["optimized"] != int(optimized)
        ):
            return None, "case_receipt_interpreter_flags_differ"
        return cast(JsonObject, case), None
    except (OSError, UnicodeError, ValueError) as error:
        return None, "unreadable_case_receipt:" + type(error).__name__


def run_all(data: Path, output: Path, *, require_optimized: bool = False) -> int:
    require(
        not require_optimized or sys.flags.optimize == 1,
        "The optimized matrix must be launched by the native interpreter with python -O",
    )
    require(not output.exists(), "Use a new suite output directory")
    output.mkdir(parents=True)
    env = environment()
    required_paths = tuple(PROGRAM_INPUT_PATHS[program] for program in PROGRAMS)
    manifest_sha256 = frozen_manifest_sha256(data)
    verify_frozen(data, required_paths=required_paths, expected_manifest_sha256=manifest_sha256)
    planned = [
        (p, v, s, t)
        for p in PROGRAMS
        for s, t in itertools.permutations(ENGINES, 2)
        for v in VARIANTS
    ]
    write_json(
        output / "plan.json",
        {
            "distinct_cases": len(planned),
            "variants": list(VARIANTS),
            "programs": list(PROGRAMS),
            "directions": [list(x) for x in itertools.permutations(ENGINES, 2)],
            "environment": env,
            "scope": (
                "new finite real-consumer workflow matrix; not universal option coverage "
                "or historical80 cases"
            ),
        },
    )
    records = []
    terminal_errors = []
    case_receipts = []
    for index, (p, v, s, t) in enumerate(planned, 1):
        if shutil.disk_usage(output).free < 4 * 1024**3:
            terminal_errors.append(
                {"stage": "reserve", "reason": "Less than4GiB free disk; remaining cases not run"}
            )
            break
        ident = f"{index:03d}-{p}-{s}-{t}-{v}"
        folder = output / "cases" / ident
        cmd = (
            [sys.executable, "-I"]
            + (["-O"] if sys.flags.optimize else [])
            + [
                "-m",
                "equiframe_consumer_lab",
                "run",
                "--program",
                p,
                "--variant",
                v,
                "--source",
                s,
                "--target",
                t,
                "--data",
                str(data.resolve()),
                "--output",
                str(folder.resolve()),
            ]
        )
        start = time.monotonic()
        actual_exit = None
        out = ""
        err = ""
        outcome = "not_started"
        launch_error = None
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            actual_exit = proc.returncode
            out = _text(proc.stdout)
            err = _text(proc.stderr)
            outcome = "completed"
        except subprocess.TimeoutExpired as error:
            out = _text(error.stdout)
            err = _text(error.stderr)
            outcome = "timeout"
            launch_error = {"type": "TimeoutExpired", "timeout_seconds": error.timeout}
        except OSError as error:
            outcome = "launch_failed"
            launch_error = {"type": type(error).__name__, "message": str(error)}
        logs = output / "logs"
        logs_error = None
        try:
            logs.mkdir(exist_ok=True)
            (logs / (ident + ".stdout.txt")).write_text(out, encoding="utf-8")
            (logs / (ident + ".stderr.txt")).write_text(err, encoding="utf-8")
        except OSError as error:
            logs_error = {"type": type(error).__name__, "message": str(error)}
            terminal_errors.append({"stage": "child_logs", "case_id": ident, **logs_error})
        case, receipt_error = (
            _read_case(
                folder / "case.json",
                (p, v, s, t),
                actual_exit,
                optimized=bool(sys.flags.optimize),
            )
            if actual_exit is not None
            else (None, "process_did_not_return")
        )
        case_receipts.append(case)
        okay = (
            outcome == "completed"
            and logs_error is None
            and receipt_error is None
            and case is not None
            and actual_exit == EXPECTED_EXIT[v]
            and case.get("status") in ("PASS", "EXPECTED_REJECTION")
            and case.get("accepted") is (v == "good")
            and case.get("published") is (v == "good")
        )
        rec = {
            "case_id": ident,
            "program": p,
            "variant": v,
            "source": s,
            "target": t,
            "command": cmd,
            "expected_exit": EXPECTED_EXIT[v],
            "actual_exit": actual_exit,
            "process_outcome": outcome,
            "process_error": launch_error,
            "receipt_error": receipt_error,
            "logs_error": logs_error,
            "unwritten_stdout": out if logs_error is not None else None,
            "unwritten_stderr": err if logs_error is not None else None,
            "accepted": case.get("accepted") if case is not None else None,
            "published": case.get("published") if case is not None else None,
            "status": ("PASS" if v == "good" else "EXPECTED_REJECTION") if okay else "FAIL",
            "harness_pass": okay,
            "elapsed_seconds": time.monotonic() - start,
            "case_receipt": f"cases/{ident}/case.json",
        }
        records.append(rec)
        attempt_error = None
        try:
            with (output / "attempts.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(rec) + "\n")
                stream.flush()
        except OSError as error:
            attempt_error = {"stage": "attempt_receipt", "type": type(error).__name__}
            terminal_errors.append(attempt_error)
        print(
            f"[{index}/{len(planned)}] {ident}: {rec['status']} "
            f"process={outcome} actual_exit={actual_exit}",
            flush=True,
        )
        if outcome != "completed" or logs_error is not None or attempt_error is not None:
            break
    try:
        verify_frozen(data, required_paths=required_paths, expected_manifest_sha256=manifest_sha256)
    except Exception as error:
        terminal_errors.append({"stage": "final_input_check", "type": type(error).__name__})
    known_native = sum(
        len(c.get("native_result", {}).get("executions", []))
        for c in case_receipts
        if c is not None
    )
    unavailable_native = sum(
        c is None or c.get("native_execution_count_complete") is not True for c in case_receipts
    )
    complete = len(records) == len(planned) and all(
        r["process_outcome"] == "completed" for r in records
    )
    passed = complete and all(r["harness_pass"] for r in records) and not terminal_errors
    summary = {
        "consumer_version": "0.1.19",
        "status": "PASS" if passed else ("FAIL" if complete else "PARTIAL"),
        "planned_cases": len(planned),
        "distinct_cases": len(records),
        "attempted_cases": len(records),
        "case_launch_attempts": len(records),
        "case_subprocesses": sum(r["process_outcome"] in ("completed", "timeout") for r in records),
        "completed_case_processes": sum(r["process_outcome"] == "completed" for r in records),
        "not_attempted_cases": len(planned) - len(records),
        "not_run_cases": len(planned)
        - sum(r["process_outcome"] in ("completed", "timeout") for r in records),
        "cases_with_valid_receipts": sum(c is not None for c in case_receipts),
        "native_execution_attempts": known_native if unavailable_native == 0 else None,
        "recorded_native_executions": known_native,
        "cases_with_unavailable_native_count": unavailable_native,
        "case_status_counts": {
            s: sum(r["status"] == s for r in records)
            for s in ("PASS", "EXPECTED_REJECTION", "FAIL")
        },
        "accepted_cases": sum(r["accepted"] is True for r in records),
        "rejected_cases": sum(r["accepted"] is False for r in records),
        "cases_with_unavailable_acceptance": sum(r["accepted"] is None for r in records),
        "optimization_required": require_optimized,
        "optimized": bool(sys.flags.optimize),
        "all_expected_outcomes_observed": passed,
        "terminal_errors": terminal_errors,
        "note": (
            "Expected nonzero exits never accept data; missing receipts/timeouts have "
            "unavailable native counts, not invented zeros"
        ),
        "records": records,
    }
    try:
        write_json(output / "summary.json", summary)
        write_json(
            output / "app-manifest.json", {"files": inventory(output), "status": summary["status"]}
        )
    except Exception as error:
        summary.update(status="FAIL", all_expected_outcomes_observed=False)
        summary["terminal_errors"].append(
            {"stage": "terminal_suite_evidence", "type": type(error).__name__}
        )
        try:
            replace_owned_json(output / "summary.json", summary)
        except Exception:
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "stage": "terminal_suite_evidence",
                        "summary_unavailable": True,
                    }
                ),
                file=sys.stderr,
            )
        return 1
    return 0 if passed else 1


def fault_checks(output: Path) -> int:
    require(not output.exists(), "Use a new fault-check directory")
    output.mkdir(parents=True)
    records = []
    env = environment()
    expected = pa.table({"id": ["001", "002"], "cents": [100, 200]})
    bad = pa.table({"id": ["001", "002"], "cents": [101, 199]})
    for label, candidate, options, wanted in (
        ("accept", expected, None, True),
        ("compensated_reject", bad, None, False),
        ("budget_reject", expected, ef.ComparisonOptions(max_rows=1), False),
    ):
        result = ef.diff(candidate, expected, keys=["id"], options=options, work_dir=output / label)
        accepted, error = comparison_gate(result)
        require(accepted is wanted, "Explicit functional acceptance gate differs")
        records.append({"case": label, "state": result.state, "accepted": accepted, "error": error})
    published = output / "published"
    publish(expected, published, accepted=True)
    previous = (published / "current.json").read_bytes()
    for label, accepted, fault in (
        ("rejected_input", False, None),
        ("write_fault", True, "before_commit"),
    ):
        try:
            publish(bad, published, accepted=accepted, fault=fault)
        except ConsumerError:
            pass
        else:
            raise ConsumerError("Fault publication unexpectedly succeeded")
        require(
            (published / "current.json").read_bytes() == previous, "Fault changed prior publication"
        )
        require(not list(published.glob(".staging-*")), "Fault staging was not cleaned")
        records.append({"case": label, "prior_publication_preserved": True, "staging_clean": True})
    corruption = output / "corrupt-report"
    result = ef.diff(expected, expected, work_dir=output / "corrupt-source")
    ef.write_comparison_report(result, corruption)
    verify_report(corruption)
    with (corruption / "report.txt").open("a") as stream:
        stream.write("controlled corruption\n")
    try:
        verify_report(corruption)
    except ConsumerError:
        records.append({"case": "report_corruption", "rejected": True})
    else:
        raise ConsumerError("Corrupt report was accepted")
    write_json(
        output / "fault-checks.json",
        {"status": "PASS", "environment": env, "synthetic_fixture": True, "checks": records},
    )
    write_json(output / "app-manifest.json", {"files": inventory(output), "status": "PASS"})
    print(
        json.dumps({"fault_checks": "PASS", "count": len(records), "optimized": sys.flags.optimize})
    )
    return 0
