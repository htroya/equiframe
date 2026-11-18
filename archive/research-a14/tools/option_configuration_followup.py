"""Exercise explicit optional configuration admission, never inferred defaults.

Original A13 fixtures provide the operations. Frozen declaration defaults
provide the complete normalization oracle. Synthetic captures are not native
executions or scientific labels, and no public API-wide coverage is credited.
"""

from __future__ import annotations

import argparse
import importlib.util
import platform
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "option_seed_bounds_followup",
    Path(__file__).with_name("option_seed_bounds_followup.py"),
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Prior verifier unavailable")
seed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed)
types, boundary, op = seed.types, seed.boundary, seed.op
SEED_RESULT = "54cf08ad5f0630465aade2056c7cda1b4cd4d3f1df73204e6a52b1662a2b5772"
SEED_TOOL = "5fe2679ea141cdfd832c5d5904d8d1a1744c9c93af39268ea82c70a0889ab46f"
TEST_SOURCE = "fd78ea28941db36bd8f255af0dd29cce7d11234b7ac9dc79eb533dd306c89ba0"
FIXTURE_SOURCE = "9850eac88513d2b6b3f49f2f45cc14d46b6caabb3af74484bbecc61c782ed3cd"
SOURCE_HASHES = {
    "comparison.py": "b391d657ecd4cfe70ef39472d9f946becef41ad8dc025f69f542f4b1dbc227b0",
    "comparison_report.py": "6c24dbe39a85e2212efb5302e22875623fb1f35cd20ac72618ac278524fdf7c9",
    "report_types.py": "5b2c1dea1d3c7aa6ce84bc58d8b2b42c34e566d03d4feac9f41cb731cde48c54",
}
# Transcribed from the A13 ReportViewPolicy construction, not an SDK result.
REPORT_VIEW = {
    "mode": "diagnostic",
    "include_values": False,
    "include_metadata": False,
    "redacted_column_count": 0,
    "max_examples": 20,
    "max_value_chars": 4096,
    "max_report_bytes": 2097152,
    "require_exhaustive": False,
}
PAIRS = (
    ("compare", "options", "ComparisonOptions"),
    ("compare", "policy", "ComparisonPolicy"),
    ("capture_duckdb", "options", "DuckDBCaptureOptions"),
    ("evaluate_rules", "options", "RuleOptions"),
    ("profile_execution", "options", "ProfileOptions"),
    ("reduce_case", "options", "ReductionOptions"),
    ("comparison_report", "options", "ReportOptions"),
    ("write_comparison_report", "options", "ReportOptions"),
    ("verify", "options", "ComparisonOptions"),
    ("verify", "policy", "ComparisonPolicy"),
)


class ConfigurationRejection(Exception):
    """An attributed validation error from the actual public API invocation."""

    def __init__(self, errors, entry, title):
        self.errors = errors
        self.entry = entry
        self.title = title
        super().__init__("Public API configuration rejected")


def prepare(inventory, baseline, previous):
    done = {row["id"] for row in baseline["rows"] if row["status"] != "NOT_RUN"}
    done.update(
        identifier for receipt in previous for identifier in receipt["obligations"]
    )
    pending = {row["id"] for row in baseline["rows"]} - done
    exports = {row["name"]: row for row in inventory["exports"] if not row["alias_of"]}
    cases = []
    for api, parameter, model in PAIRS:
        declaration = exports["equiframe." + model]
        fields = declaration["fields"]
        op.require(
            all(
                not field["required"]
                and not field["default_factory"]
                and not field["alias"]
                and not field["serialization_alias"]
                for field in fields
            ),
            "Defaults need an explicitly reviewed complex fixture",
        )
        expected_options = {
            field["id"].split(":")[-1]: field["default"] for field in fields
        }
        definition = next(
            row
            for row in exports["equiframe." + api]["parameters"]
            if row["id"] == f"parameter:equiframe.{api}:{parameter}"
        )
        op.require(
            definition["continuous_classes"]
            == ["admitted representative", "wrong Python/JSON type"]
            and None in definition["finite_values"],
            "Configuration parameter declaration differs",
        )
        prefix = definition["id"]
        for kind, links in (
            ("invalid_bool", [prefix + ":invalid", prefix + ":class:1"]),
            ("unknown_field", []),
            ("model", [prefix + ":class:0"]),
            ("explicit_none", [prefix + ":value:null"]),
        ):
            op.require(
                all(identifier in pending for identifier in links),
                "Configuration selection is not pending",
            )
            cases.append(
                {
                    "case_id": f"configuration.{api}.{parameter}.{kind}",
                    "api": api,
                    "parameter": parameter,
                    "model": model,
                    "kind": kind,
                    "expected_options": expected_options,
                    "expected_returned_options": REPORT_VIEW
                    if api in ("comparison_report", "write_comparison_report")
                    else expected_options,
                    "returned_options_kind": "returned_view_policy"
                    if api in ("comparison_report", "write_comparison_report")
                    else "normalized_configuration",
                    "expected_error_title": "ComparisonSpec"
                    if (api, parameter) == ("compare", "policy")
                    else model,
                    "expected_error_prefix": ["policy"]
                    if (api, parameter) == ("compare", "policy")
                    else [],
                    "obligations": links,
                    "expected_error_codes": ["model_type"]
                    if kind == "invalid_bool"
                    else ["extra_forbidden"]
                    if kind == "unknown_field"
                    else [],
                    "basis": "Original optional configuration fixture and frozen declaration defaults; explicit argument, no omission",
                }
            )
    op.require(
        len(cases) == 40 and sum(len(c["obligations"]) for c in cases) == 40,
        "Frozen configuration selection cardinality differs",
    )
    return {
        "schema": "equiframe.optional-configuration-catalog.v2",
        "wheel_sha256": boundary.WHEEL,
        "inventory_sha256": seed.INVENTORY,
        "original_test_source_sha256": TEST_SOURCE,
        "synthetic_capture_helper_sha256": FIXTURE_SOURCE,
        "reviewed_source_sha256": SOURCE_HASHES,
        "cases": cases,
        "scope": "Explicit model/None admission and invalid argument rejection before work; no omitted default or API-wide semantics credited",
    }


def invoke(case, selected, root, ef, captured):
    import pyarrow as pa
    from pydantic import ValidationError

    table = pa.table({"n": [1]})
    contract = ef.infer_diff_contract(table.schema).spec.contract
    execution = captured(contract, {"source": table}, table, root / "fixture")
    compared = ef.diff(table, table, work_dir=root / "comparison_fixture")
    output, callbacks = root / "requested_output", []

    def predicate(_):
        callbacks.append("predicate")
        return ef.ReductionObservation(
            preconditions="satisfied", failure_signature="synthetic"
        )

    kwargs = {case["parameter"]: selected}
    api = case["api"]
    # All constructors execute before the region that can attribute rejection.
    arrow_left, arrow_right = ef.ArrowInput(table), ef.ArrowInput(table)
    reduction_inputs = {"source": ef.ArrowInput(table)}
    profile_spec = ef.ProfileSpec(
        family=contract.family,
        features=(ef.ProfileFeature(name="rows", metric="log_filas", table="result"),),
    )
    verification_inputs = {"observed": execution.output.data}
    target = getattr(ef, api)
    target_code = getattr(target, "__code__", None)
    op.require(
        target_code is not None, "Target API needs its exact Python code identity"
    )
    entry = {
        "count": 0,
        "explicit_argument_identity_matches": False,
        "argument_python_type": type(selected).__module__
        + "."
        + type(selected).__qualname__,
    }

    def record_entry(frame, event, arg):
        if (
            event == "call"
            and frame.f_code is target_code
            and frame.f_back is not None
            and frame.f_back.f_code is invoke.__code__
        ):
            entry["count"] += 1
            entry["explicit_argument_identity_matches"] = (
                frame.f_locals.get(case["parameter"], object()) is selected
            )

    previous_profile = sys.getprofile()
    op.require(previous_profile is None, "An unreviewed profiler is active")
    invalid = bool(case["expected_error_codes"])
    guard = (
        patch(
            "duckdb.connect",
            side_effect=AssertionError("Invalid configuration opened SQL connection"),
        )
        if invalid
        else nullcontext()
    )
    sys.setprofile(record_entry)
    try:
        with guard:
            if api == "compare":
                result = target(
                    arrow_left,
                    arrow_right,
                    contract=contract,
                    work_dir=output,
                    **kwargs,
                )
            elif api == "capture_duckdb":
                result = target("SELECT 1::BIGINT AS n", work_dir=output, **kwargs)
            elif api == "evaluate_rules":
                result = target(execution, work_dir=output, **kwargs)
            elif api == "profile_execution":
                result = target(execution, spec=profile_spec, work_dir=output, **kwargs)
            elif api == "reduce_case":
                result = target(
                    reduction_inputs,
                    predicate=predicate,
                    predicate_version="synthetic.1",
                    failure_signature="synthetic",
                    work_dir=output,
                    **kwargs,
                )
            elif api == "comparison_report":
                result = target(compared, **kwargs)
            elif api == "write_comparison_report":
                result = target(compared, output, **kwargs)
            else:
                op.require(api == "verify", "Unplanned API")
                result = target(
                    verification_inputs,
                    contract=contract,
                    work_dir=output,
                    **kwargs,
                )
    except Exception as error:
        op.require(
            entry["count"] == 1 and entry["explicit_argument_identity_matches"],
            "Target API did not receive the explicit argument",
        )
        # Side-effect assertions must still hold when an expected error returns.
        if invalid:
            op.require(
                not output.exists() and not callbacks,
                "Invalid configuration started work",
            )
        if isinstance(error, ValidationError):
            errors = error.errors(include_url=False)
            op.require(
                error.title == case["expected_error_title"],
                "Error title is not the selected configuration model",
            )
            if case["kind"] == "invalid_bool":
                op.require(
                    len(errors) == 1
                    and errors[0]["loc"] == tuple(case["expected_error_prefix"])
                    and errors[0].get("ctx", {}).get("class_name") == case["model"],
                    "Validation rejection is not the selected declared configuration model",
                )
                op.require(
                    errors[0]["input"] is False,
                    "Error input is not the explicit boolean False",
                )
            elif case["kind"] == "unknown_field":
                op.require(
                    len(errors) == 1
                    and errors[0]["loc"]
                    == (*case["expected_error_prefix"], "unknown_option")
                    and type(errors[0]["input"]) is int
                    and errors[0]["input"] == 1,
                    "Validation rejection is not the selected extra configuration field",
                )
            raise ConfigurationRejection(errors, entry, error.title) from error
        raise
    finally:
        sys.setprofile(previous_profile)
    op.require(
        entry["count"] == 1 and entry["explicit_argument_identity_matches"],
        "Target API did not receive the explicit argument",
    )
    if invalid:
        raise ValueError("Invalid configuration was admitted")
    op.require(
        output.is_dir() or api == "comparison_report", "Positive fixture output missing"
    )
    if api == "capture_duckdb":
        rows = ef.read_table(result.data).to_pylist()
        op.require(
            types.canonical(rows) == types.canonical([{"n": 1}]),
            "DuckDB fixture differs",
        )
        # Capture result has no options field; record exact declared model input
        # and independent complete data readback, not a normalized-result claim.
        options = None
    elif api == "compare":
        op.require(
            result.state == "equivalent" and result.complete,
            "Comparison fixture incomplete",
        )
        options = (
            result.options if case["parameter"] == "options" else result.spec.policy
        )
    elif api == "verify":
        op.require(result.publishable, "Verification fixture not accepted")
        options = (
            result.comparison_options
            if case["parameter"] == "options"
            else result.comparison_policy
        )
    else:
        options = result.options
        if api in ("comparison_report", "write_comparison_report"):
            op.require(result.state == "equivalent", "Report fixture differs")
        elif api == "profile_execution":
            op.require(result.complete, "Profile fixture incomplete")
        elif api == "reduce_case":
            op.require(result.baseline_verified, "Reduction fixture not confirmed")
        else:
            op.require(
                result.decision == "not_evaluable",
                "Synthetic fixture has no operational rules",
            )
    normalized = options.model_dump(mode="json") if options is not None else None
    if normalized is not None:
        op.require(
            types.canonical(normalized)
            == types.canonical(case["expected_returned_options"]),
            "Returned configuration or view policy differs from its source-backed literal oracle",
        )
    return {
        "admitted": True,
        "public_api_entry": entry,
        "returned_options_kind": case["returned_options_kind"]
        if normalized is not None
        else "capture_readback_only",
        "returned_options": normalized,
        "synthetic_capture_not_native_execution": api
        in ("evaluate_rules", "profile_execution", "verify"),
        "capture_rows": [{"n": 1}] if api == "capture_duckdb" else None,
    }


def execute(case, root, ef, captured):
    selected = (
        False
        if case["kind"] == "invalid_bool"
        else {"unknown_option": 1}
        if case["kind"] == "unknown_field"
        else None
    )
    try:
        if case["kind"] == "model":
            selected = getattr(ef, case["model"]).model_validate_json(
                types.canonical(case["expected_options"])
            )
            op.require(
                type(selected) is getattr(ef, case["model"])
                and types.canonical(selected.model_dump(mode="json"))
                == types.canonical(case["expected_options"]),
                "Declared model argument differs",
            )
        observed = invoke(case, selected, root, ef, captured)
        status = "PASS" if not case["expected_error_codes"] else "FAIL"
    except ConfigurationRejection as error:
        codes = [row["type"] for row in error.errors]
        observed = {
            "admitted": False,
            "error_codes": codes,
            "errors": error.errors,
            "public_api_entry": error.entry,
            "validation_error_title": error.title,
        }
        status = (
            "EXPECTED_REJECTION"
            if codes and set(codes) == set(case["expected_error_codes"])
            else "FAIL"
        )
    except Exception as error:  # noqa: BLE001 - unexpected failures never add coverage
        observed, status = {"unexpected_exception": type(error).__name__}, "FAIL"
    return {**case, "observed": observed, "status": status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in (
        "wheel",
        "baseline",
        "inventory",
        "public-result",
        "seed-result",
        "original-tests",
        "catalog",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prior-result", type=Path, action="append", required=True)
    parser.add_argument("--prior-sha256", action="append", required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    expected_helpers = {
        **seed.HELPER_HASHES,
        "option_seed_bounds_followup.py": SEED_TOOL,
    }
    helper_hashes = {
        name: op.digest(Path(__file__).with_name(name)) for name in expected_helpers
    }
    op.require(helper_hashes == expected_helpers, "Verifier helpers differ")
    op.require(
        op.digest(args.original_tests / "test_optional_configuration.py") == TEST_SOURCE
        and op.digest(args.original_tests / "rule_helpers.py") == FIXTURE_SOURCE,
        "Original A13 fixture source differs",
    )
    op.require(
        op.digest(args.inventory) == seed.INVENTORY
        and op.digest(args.public_result) == seed.PUBLIC_RESULT
        and op.digest(args.seed_result) == SEED_RESULT,
        "Prior identity differs",
    )
    baseline, previous, prior_hashes = types.load_inputs(args)
    previous.extend(
        op.read(args.public_result)["receipts"] + op.read(args.seed_result)["receipts"]
    )
    op.require(
        boundary.aggregate(baseline, previous, [])["verified"] == 5902,
        "Prior union differs",
    )
    package = op.identity(
        args.wheel, boundary.WHEEL, Path(__file__).resolve().parents[1]
    )
    import equiframe as ef

    actual_sources = {
        name: op.digest(Path(ef.__file__).resolve().parent / name)
        for name in SOURCE_HASHES
    }
    op.require(
        actual_sources == SOURCE_HASHES, "Reviewed validation/report source differs"
    )
    catalog = prepare(op.read(args.inventory), baseline, previous)
    if args.mode == "plan":
        boundary.write(args.catalog, catalog)
        print(
            types.canonical(
                {
                    "planned_cases": 40,
                    "planned_obligations": 40,
                    "catalog_sha256": op.digest(args.catalog),
                    "executed": False,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256
        and op.digest(args.catalog) == args.catalog_sha256
        and types.canonical(op.read(args.catalog)) == types.canonical(catalog),
        "Frozen catalog differs",
    )
    import equiframe as ef

    fixture_spec = importlib.util.spec_from_file_location(
        "original_rule_helpers", args.original_tests / "rule_helpers.py"
    )
    op.require(
        fixture_spec is not None and fixture_spec.loader is not None,
        "Original fixture unavailable",
    )
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = [
        execute(case, args.output / case["case_id"], ef, fixture.captured)
        for case in catalog["cases"]
    ]
    result = {
        "schema": "equiframe.optional-configuration-result.v2",
        "package": package,
        "tool_sha256": op.digest(Path(__file__)),
        "helper_source_sha256": helper_hashes,
        "reviewed_source_sha256": actual_sources,
        "catalog_sha256": args.catalog_sha256,
        "prior_result_sha256": prior_hashes + [seed.PUBLIC_RESULT, SEED_RESULT],
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "optimization": sys.flags.optimize,
        },
        "receipts": receipts,
        "summary": boundary.aggregate(baseline, previous, receipts),
        "all_expected_results": all(
            row["status"] in ("PASS", "EXPECTED_REJECTION") for row in receipts
        ),
        "scope": catalog["scope"],
    }
    boundary.write(args.output / "result.json", result)
    print(
        types.canonical(
            {
                "all_expected_results": result["all_expected_results"],
                "verified": result["summary"]["verified"],
                "percent": result["summary"]["percent"],
                "result_sha256": op.digest(args.output / "result.json"),
            }
        )
    )
    return 0 if result["all_expected_results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
