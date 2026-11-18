"""Execute reviewed native cases against an identified installed A13 wheel.

This deliberately bounded driver complements the metadata-only catalog. Every
linked obligation has an explicit input and expected effect. Counts retain the
frozen denominator; repetitions and automatic reviews add no obligations.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


def read(path: Path) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON member")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Nonfinite JSON token: " + value)

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def baseline_identity(baseline, expected_wheel):
    rows = baseline["rows"]
    require(
        baseline["wheel_sha256"] == expected_wheel,
        "Baseline belongs to another wheel",
    )
    commits = {baseline["source_commit"]}
    require(
        commits == {"96769ad15d0807a501e6141725c8d4198d7715b0"},
        "Baseline source commit changed",
    )
    ids = sorted(r["id"] for r in rows)
    require(len(ids) == len(set(ids)) == 8385, "Frozen denominator changed")
    ids_hash = hashlib.sha256(
        json.dumps(ids, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    require(
        ids_hash == "22308238f613b50aefc0d5bb876e743443b3585c69f5f92d2ce9c22a5c2c3de1",
        "Frozen obligation identities changed",
    )
    require(
        baseline["obligation_ids_sha256"] == ids_hash,
        "Baseline denominator identity is inconsistent",
    )
    return {"source_commit": next(iter(commits)), "obligation_ids_sha256": ids_hash}


def identity(wheel: Path, expected_sha256: str, root: Path) -> dict[str, Any]:
    import equiframe as ef

    require(digest(wheel) == expected_sha256, "Wheel differs from trusted identity")
    package = Path(ef.__file__).resolve().parent
    require(
        not package.is_relative_to(root.resolve()),
        "SDK must be installed outside checkout",
    )
    require(ef.__version__ == "0.12.0a13", "Driver requires the frozen A13 candidate")
    count = 0
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith("equiframe/") and not name.endswith("/"):
                relative = Path(name).relative_to("equiframe")
                require(".." not in relative.parts, "Unsafe wheel payload")
                require(
                    (package / relative).read_bytes() == archive.read(name),
                    "Installed payload differs",
                )
                count += 1
    require(count > 0, "No SDK payload verified")
    return {
        "version": ef.__version__,
        "wheel_sha256": expected_sha256,
        "payload_files": count,
    }


def cases() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for argument in ["options", "capture_options"]:
        prefix = f"parameter:equiframe.diff:{argument}:"
        result.append(
            {
                "case_id": f"diff-null-{argument}",
                "driver": "diff_null",
                "argument": argument,
                "input": None,
                "expected": {"state": "equivalent", "all_default_options": True},
                "obligations": [prefix + "value:null"],
                "basis": "test_diff.py:test_none_and_valid_empty_option_mappings_preserve_defaults",
            }
        )
        result.append(
            {
                "case_id": f"diff-reject-{argument}",
                "driver": "diff_invalid",
                "argument": argument,
                "input": False,
                "expected": {"exception": "ValidationError", "workspace_empty": True},
                "obligations": [prefix + "invalid", prefix + "class:1"],
                "basis": "test_diff.py:test_falsey_invalid_options_are_rejected_before_capture",
            }
        )
    for value, links in [
        (16, []),
        (1, ["class:2"]),
        (4096, ["class:4"]),
        (0, ["class:3"]),
        (4097, ["class:5"]),
        ("1", []),
    ]:
        result.append(
            {
                "case_id": f"partitions-{type(value).__name__}-{value}",
                "driver": "partitions",
                "input": value,
                "expected": {"admitted": type(value) is int and 1 <= value <= 4096},
                "obligations": [
                    "field:equiframe.ComparisonOptions:partitions:" + link
                    for link in links
                ],
                "basis": "ComparisonOptions declares strict integer ge=1/le=4096; native admitted cases preserve complete literal equality",
            }
        )
    result.append(
        {
            "case_id": "diff-omitted-options",
            "driver": "diff_defaults",
            "input": {"candidate": [1, 2], "expected": [1, 2]},
            "expected": {"state": "equivalent", "default_partitions": 16},
            "obligations": [
                "api:equiframe.diff",
                "parameter:equiframe.diff:candidate:class:0",
                "parameter:equiframe.diff:expected:class:0",
                "parameter:equiframe.diff:options:default",
                "parameter:equiframe.diff:capture_options:default",
                "parameter:equiframe.diff:work_dir:class:0",
            ],
            "basis": "Literal Arrow tables, omitted options/capture_options and a new persisted workspace",
        }
    )
    for argument in ["candidate", "expected"]:
        result.append(
            {
                "case_id": "diff-missing-" + argument,
                "driver": "diff_missing",
                "argument": argument,
                "input": "omitted",
                "expected": {
                    "exception": "TypeError",
                    "missing_argument": argument,
                    "workspace_empty": True,
                },
                "obligations": [
                    f"parameter:equiframe.diff:{argument}:required_omission"
                ],
                "basis": "Python's required signature; supplying only the other table must reject before capture",
            }
        )
    return result


# Bounds transcribed from the reviewed A13 declarations. Expectations are fixed
# before execution, independent of observed validation. For gt=0, the declared
# boundary is literally zero (rejected), not a post-hoc first admitted value.
def boundary_cases(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    groups = {
        "ComparisonOptions": (
            "batch_rows max_batch_bytes max_row_bytes sqlite_cache_kib max_rows max_work max_disk_bytes max_evidence_bytes max_matching_rows max_matching_bytes max_pair_checks max_numeric_digits timeout_seconds",
            "max_examples",
        ),
        "DiffCaptureOptions": ("max_rows max_bytes", ""),
        "ExecutionOptions": (
            "timeout_seconds max_transport_bytes duckdb_memory_mb duckdb_threads",
            "max_input_rows max_output_rows",
        ),
        "DuckDBCaptureOptions": (
            "batch_rows max_batch_bytes max_bytes timeout_seconds",
            "max_rows",
        ),
        "MigrationOptions": ("timeout_seconds max_capture_bytes", "max_capture_rows"),
        "ReductionOptions": ("max_evaluations timeout_seconds max_input_rows", ""),
        "RuleOptions": (
            "max_rows max_artifact_bytes max_evidence_bytes max_work timeout_seconds",
            "max_examples",
        ),
        "ProfileOptions": (
            "max_rows max_artifact_bytes max_work max_distinct timeout_seconds",
            "",
        ),
        "ReportOptions": (
            "max_report_bytes max_evidence_bytes max_records",
            "max_examples",
        ),
        "ReportViewPolicy": (
            "max_value_chars max_report_bytes",
            "redacted_column_count max_examples",
        ),
        "IsolationForestConfig": ("", "random_state"),
    }
    specs = {}
    for model, (positive, nonnegative) in groups.items():
        for field in positive.split():
            specs[(model, field)] = ("gt", 0, None)
        for field in nonnegative.split():
            specs[(model, field)] = ("ge", 0, None)
    specs.update(
        {
            ("ReductionOptions", "confirmations"): ("ge", 1, 5),
            ("ReportOptions", "max_examples"): ("ge", 0, 10000),
            ("ReportOptions", "max_value_chars"): ("ge", 16, 1048576),
            ("ReportOptions", "max_records"): ("gt", 0, 1000000),
            ("IsolationForestConfig", "random_state"): ("ge", 0, 4294967295),
            ("IsolationForestConfig", "n_estimators"): ("ge", 1, 2048),
            ("IsolationForestConfig", "max_samples"): ("ge", 2, 4096),
        }
    )
    result = []
    for (model, field), (kind, lower, upper) in specs.items():
        variants = [
            (2, lower, kind == "ge", None if kind == "ge" else "greater_than"),
            (
                3,
                lower - 1,
                False,
                "greater_than" if kind == "gt" else "greater_than_equal",
            ),
        ]
        if upper is not None:
            variants += [
                (4, upper, True, None),
                (5, upper + 1, False, "less_than_equal"),
            ]
        for suffix, value, admitted, error_code in variants:
            data = copy.deepcopy(catalog["seeds"][model]["input"])
            data[field] = value
            result.append(
                {
                    "case_id": f"boundary-{model}-{field}-{suffix}",
                    "driver": "metadata_boundary",
                    "model": model,
                    "field": field,
                    "input": data,
                    "expected": {
                        "admitted": admitted,
                        "value": value,
                        "error_code": error_code,
                    },
                    "obligations": [f"field:equiframe.{model}:{field}:class:{suffix}"],
                    "basis": {
                        "lower_constraint": kind,
                        "lower": lower,
                        "upper_constraint": "le" if upper is not None else None,
                        "upper": upper,
                        "scope": "Declared numeric metadata only; no engine effects inferred",
                    },
                }
            )
    require(len(result) == 128, "Reviewed numeric plan changed")
    return result


def execute(case: dict[str, Any], directory: Path) -> dict[str, Any]:
    import equiframe as ef
    import pyarrow as pa
    from pydantic import ValidationError

    table = pa.table({"value": [1, 2]})
    observed: dict[str, Any]
    status = "PASS"
    driver = case["driver"]
    if driver == "metadata_boundary":
        model = getattr(ef, case["model"])
        field = case["field"]
        try:
            output = model.model_validate_json(
                json.dumps(case["input"], allow_nan=False)
            ).model_dump(mode="json")
        except ValidationError as error:
            errors = [
                {"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()
            ]
            require(
                not case["expected"]["admitted"]
                and any(
                    e["loc"] == [field] and e["type"] == case["expected"]["error_code"]
                    for e in errors
                ),
                "Boundary rejected for an unexpected reason",
            )
            observed = {"admitted": False, "errors": errors}
            status = "EXPECTED_REJECTION"
        else:
            require(
                case["expected"]["admitted"]
                and output[field] == case["expected"]["value"],
                "Boundary admission or serialization differs",
            )
            observed = {"admitted": True, "value": output[field]}
    elif driver == "diff_invalid":
        try:
            ef.diff(
                table, table, **{case["argument"]: case["input"]}, work_dir=directory
            )
        except ValidationError:
            observed = {
                "exception": "ValidationError",
                "workspace_empty": not any(directory.iterdir()),
            }
            require(observed == case["expected"], "Invalid options changed workspace")
            status = "EXPECTED_REJECTION"
        else:
            raise ValueError("Invalid options were accepted")
    elif driver == "diff_missing":
        supplied = "expected" if case["argument"] == "candidate" else "candidate"
        try:
            ef.diff(**{supplied: table}, work_dir=directory)
        except TypeError as error:
            require(
                case["argument"] in str(error) and "required" in str(error),
                "Unexpected TypeError",
            )
            observed = {
                "exception": "TypeError",
                "missing_argument": case["argument"],
                "workspace_empty": not any(directory.iterdir()),
            }
            require(observed == case["expected"], "Missing argument changed workspace")
            status = "EXPECTED_REJECTION"
        else:
            raise ValueError("Required argument omission was accepted")
    elif driver == "partitions":
        value = case["input"]
        try:
            options = (
                ef.ComparisonOptions()
                if value == 16
                else ef.ComparisonOptions(partitions=value)
            )
        except ValidationError as error:
            require(not case["expected"]["admitted"], "Declared boundary was rejected")
            require(
                any(e["loc"] == ("partitions",) for e in error.errors()),
                "Rejection was not partitions",
            )
            observed = {
                "admitted": False,
                "exception": "ValidationError",
                "field": "partitions",
            }
            status = "EXPECTED_REJECTION"
        else:
            require(
                case["expected"]["admitted"] and options.partitions == value,
                "Incorrect partitions admission/default",
            )
            comparison = ef.diff(table, table, options=options, work_dir=directory)
            require(
                comparison.state == "equivalent", "Native partitions changed equality"
            )
            observed = {
                "admitted": True,
                "partitions": options.partitions,
                "state": comparison.state,
            }
    elif driver in {"diff_defaults", "diff_null"}:
        kwargs = {case["argument"]: None} if driver == "diff_null" else {}
        comparison = ef.diff(table, table, work_dir=directory, **kwargs)
        require(comparison.state == "equivalent", "Literal equality changed")
        require(
            comparison.options == ef.ComparisonOptions(), "Comparison defaults changed"
        )
        receipt = read(directory / comparison.comparison_id / "diff-contract.json")
        require(
            receipt["capture_options"]
            == ef.DiffCaptureOptions().model_dump(mode="json"),
            "Capture defaults changed",
        )
        observed = {
            "state": comparison.state,
            "partitions": comparison.options.partitions,
            "capture_defaults_verified": True,
            "receipt_persisted": True,
        }
    else:
        raise ValueError("Unknown reviewed operation driver")
    return {**case, "observed": observed, "status": status}


def summarize(
    rows: list[dict[str, Any]], receipts: list[dict[str, Any]]
) -> dict[str, Any]:
    index = {row["id"]: row for row in rows}
    require(len(index) == len(rows) == 8385, "Frozen A13 denominator changed")
    case_ids: set[str] = set()
    linked: dict[str, str] = {}
    for receipt in receipts:
        require(receipt["case_id"] not in case_ids, "Repeated case receipt")
        case_ids.add(receipt["case_id"])
        require(
            receipt["status"] in {"PASS", "EXPECTED_REJECTION"},
            "Unverified operation receipt",
        )
        for identifier in receipt["obligations"]:
            require(identifier in index, "Unknown obligation")
            require(
                index[identifier]["status"] == "NOT_RUN",
                "Driver must add only previously unverified obligations",
            )
            require(identifier not in linked, "Repeated obligation mapping")
            linked[identifier] = receipt["status"]
    counts = Counter(row["status"] for row in rows)
    require(
        counts["PASS"] + counts["EXPECTED_REJECTION"] == 4298
        and counts["NOT_RUN"] == 4087,
        "Frozen baseline changed",
    )
    for status in linked.values():
        counts["NOT_RUN"] -= 1
        counts[status] += 1
    verified = counts["PASS"] + counts["EXPECTED_REJECTION"]
    return {
        "total": len(rows),
        "verified": verified,
        "percent": verified / len(rows) * 100,
        "counts": dict(sorted(counts.items())),
        "new_verified_obligations": len(linked),
        "unique_new_cases": sum(bool(r["obligations"]) for r in receipts),
        "regression_cases": sum(not r["obligations"] for r in receipts),
        "linked_obligations": linked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    require(digest(args.baseline) == args.baseline_sha256, "Baseline identity changed")
    original = read(args.baseline)
    rows = original["rows"]
    baseline = baseline_identity(original, args.sha256)
    require(
        digest(args.catalog) == args.catalog_sha256, "Seed catalog identity changed"
    )
    catalog = read(args.catalog)
    require(
        catalog["wheel_sha256"] == args.sha256
        and catalog["source_commit"] == baseline["source_commit"]
        and catalog["obligation_ids_sha256"] == baseline["obligation_ids_sha256"],
        "Seed catalog belongs to another candidate/denominator",
    )
    planned = cases() + boundary_cases(catalog)
    # Reject coverage errors before any native capture or workspace creation.
    summarize(rows, [{**c, "status": "PASS"} for c in planned])
    package = identity(args.wheel, args.sha256, root)
    args.work_dir.mkdir(parents=True, exist_ok=False)
    receipts = []
    for case in planned:
        directory = args.work_dir / case["case_id"]
        directory.mkdir()
        receipts.append(execute(case, directory))
    result = {
        "schema": "equiframe.option-operation-receipts.v1",
        "candidate": "0.12.0a13",
        "package": package,
        "baseline_sha256": args.baseline_sha256,
        "catalog_sha256": args.catalog_sha256,
        **baseline,
        "driver_sha256": digest(Path(__file__)),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "optimized": bool(sys.flags.optimize),
        "automated": True,
        "human_review": False,
        "summary": summarize(rows, receipts),
        "receipts": receipts,
        "scope": "Reviewed subset of native diff operations/partitions plus 128 numeric metadata boundaries; not exhaustive engine interactions or independent human acceptance",
    }
    with (args.work_dir / "result.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
