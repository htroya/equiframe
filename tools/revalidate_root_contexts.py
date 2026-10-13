"""Close pending root metadata fields with explicitly authored coupled contexts.

The original literal catalogue is immutable. New expected JSON is frozen before
execution; serializers and cross-field choices are declared, never learned from
observed results. Native command/runtime and science obligations remain separate.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import platform
import stat
import sys
from collections import Counter
from pathlib import Path

import equiframe as ef
from pydantic import ValidationError

specification = importlib.util.spec_from_file_location(
    "owned_eda_context_helpers", Path(__file__).with_name("revalidate_eda_contracts.py")
)
if specification is None or specification.loader is None:
    raise ValueError("Owned context helpers unavailable")
owned = importlib.util.module_from_spec(specification)
specification.loader.exec_module(owned)

CATALOG_SHA = "9eaa56aa71b803d901b07b56da0a89eb3cb610a44dc67a78513b553288ab59e1"
BASELINE_HASHES = {
    "9d60c85e1f572e7a223d940b056db60cd8bed5568049df4ed7605a55e18a5200",
    "61f640e16daf7a64d418b09b7ebce961d3f8665d1ba1c9cd40fc41a4c364398a",
}
MODELS = {
    "Aggregate",
    "AggregateCheck",
    "Arithmetic",
    "ArtifactRef",
    "CardinalityCheck",
    "CheckResult",
    "ColumnKeyScope",
    "ColumnSpec",
    "CompilationCheck",
    "ComparisonPolicy",
    "ComparisonValue",
    "ComponentDecision",
    "ConversionReceipt",
    "DatePolicy",
    "DecimalType",
    "Deduplicate",
    "DetectorDecision",
    "DetectorScoreResult",
    "EquiJoin",
    "ExecutionOptions",
    "ExecutionResult",
    "EvidenceBundle",
    "EvidenceFile",
    "ExpectedProvenance",
    "FeatureObservation",
    "FieldMapping",
    "Measure",
    "JoinCheck",
    "IngestionResult",
    "KeySpec",
    "LocalizeTimestamp",
    "NaNPolicy",
    "NullPolicy",
    "NumericPolicy",
    "OrderCheck",
    "ProfileFeature",
    "ReportCount",
    "ReportOptions",
    "ReportEvidenceManifest",
    "ReportValue",
    "ReportWitness",
    "RuleSpec",
    "TableArtifact",
    "TableSchema",
    "TimestampPolicy",
    "TimestampType",
    "TimestampValue",
    "Tolerance",
    "Window",
    "WindowMeasure",
    "WorkflowCheckpoint",
    "WorkflowSpec",
}


def require_ordinary_parents(path):
    path = path.absolute()
    for part in (path, *path.parents):
        info = part.lstat()
        owned.require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Input/output ancestors must be ordinary directories",
        )


def bounded_json(path):
    """Read at most 64 MiB, refusing links, duplicate keys and oversized trees."""
    path = path.absolute()
    require_ordinary_parents(path.parent)
    io = owned.tool("root_context_local_io", owned.ROOT / "tools/thesis_packet_io.py")
    raw = io.read_bytes(path.parent.resolve(strict=True), path.name)

    def pairs(items):
        value = {}
        for key, item in items:
            owned.require(key not in value, "Duplicate JSON key")
            value[key] = item
        return value

    def constant(_value):
        raise ValueError("Nonfinite JSON")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
        )
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("Invalid UTF-8 JSON input") from error
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        owned.require(depth <= 64 and nodes <= 750000, "JSON structure budget exceeded")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, float):
            owned.require(math.isfinite(item), "Nonfinite JSON number")
    owned.require(isinstance(value, dict), "JSON document must be an object")
    return raw, value


def context(name, field, value, data, expected):
    updates = {}
    if name == "AggregateCheck" and field == "measure" and value is None:
        updates["function"] = "count"
    elif name == "Arithmetic" and field == "rounding":
        updates["operation"] = "divide"
    elif name == "CardinalityCheck":
        updates["maximum" if field == "minimum" else "minimum"] = (
            None if field == "minimum" else 0
        )
    elif name == "CheckResult":
        if (field in {"revision", "required", "severity"} and value is None) or (
            field == "kind" and value == "precondition"
        ):
            updates = {"kind": "precondition", "required": None, "severity": None}
        elif field == "state":
            updates = {
                "complete": value != "not_evaluable",
                "violation_count": 1 if value == "violated" else 0,
                "reason": "synthetic_unavailable"
                if value in {"not_evaluable", "not_applicable"}
                else None,
                "examples": [],
                "findings": None,
            }
        elif field == "complete" and value is False:
            updates = {
                "state": "not_evaluable",
                "reason": "synthetic_unavailable",
                "violation_count": 0,
                "examples": [],
                "findings": None,
            }
    elif name == "ColumnSpec" and field == "nullable":
        updates["null_policy"] = {"representations": ["null"], "justification": None}
        updates["allowed_values"] = []
    elif name == "CompilationCheck" and field == "supported" and value is False:
        updates["diagnostics"] = [
            {
                "code": "unsupported_context",
                "message": "Synthetic unsupported feature",
                "node_id": None,
            }
        ]
    elif name == "ComparisonPolicy":
        if field == "justification" and value is None:
            updates = {
                "column_order": "significant",
                "physical_types": "exact",
                "index": "reject",
            }
        elif field != "justification":
            updates["justification"] = "Synthetic explicit comparison policy"
    elif name == "ComparisonValue":
        if field == "kind":
            values = {
                "null": None,
                "nan": None,
                "infinity": "positive",
                "boolean": "true",
                "integer": "3",
                "string": "literal",
                "decimal": "1.25",
                "float": "1.25",
                "date": "0",
                "timestamp": "0",
            }
            updates = {
                "value": values[value],
                "unit": "day"
                if value == "date"
                else "us"
                if value == "timestamp"
                else None,
                "timezone": None,
            }
        elif field == "unit":
            updates = {
                "kind": "date" if value == "day" else "timestamp",
                "value": "0",
                "timezone": None,
            }
    elif name == "ComponentDecision":
        if (
            field == "decision"
            or field == "complete"
            and value is True
            or field == "reason"
            and value is None
        ):
            updates = {"decision": "no_alert", "complete": True, "reason": None}
            updates[field] = value
    elif name == "DatePolicy" and field == "closed":
        updates = {"lower": None, "upper": None}
    elif name == "DecimalType" and field == "precision":
        updates["scale"] = 0
    elif name == "ConversionReceipt":
        if field == "attempted_rows":
            updates["failed_rows"] = []
        elif field == "failed_rows":
            updates["attempted_rows"] = [0, 1, 2, 3, 4]
    elif name == "Deduplicate":
        if field == "keep":
            updates["by"] = (
                [{"column": "id", "direction": "ascending", "nulls": "first"}]
                if value == "first"
                else []
            )
        elif field == "by":
            updates["keep"] = "first" if value else "identical"
    elif name == "DetectorDecision":
        if value is None:
            updates = {
                "result": {
                    "decision": "not_evaluable",
                    "complete": False,
                    "reason": "synthetic_unavailable",
                },
                "score": None,
                "threshold": None,
            }
        elif field == "score":
            updates = {
                "threshold": 1.0,
                "result": {
                    "decision": "alert"
                    if value == "+infinity" or value > 1
                    else "no_alert",
                    "complete": True,
                    "reason": None,
                },
            }
        elif field == "threshold":
            updates = {
                "score": 1.0,
                "result": {"decision": "alert", "complete": True, "reason": None},
            }
    elif name == "DetectorScoreResult":
        if field == "matrix_sha256" and value is None:
            updates = {
                "m": {
                    "state": "not_estimable",
                    "values": [],
                    "reason": "synthetic_unavailable",
                },
                "b": {
                    "state": "not_estimable",
                    "values": [],
                    "reason": "synthetic_unavailable",
                },
            }
        elif field == "rows" and value == 0:
            updates = {
                "m": {"state": "scored", "values": [], "reason": None},
                "b": {"state": "scored", "values": [], "reason": None},
            }
    elif name == "EvidenceBundle" and field == "root_document":
        for member in data["files"]:
            if member["path"] == "operation/verification.json":
                member["path"] = value
        expected["files"] = copy.deepcopy(data["files"])
    elif name == "ExecutionResult":
        updates = {
            "state": "failed" if field == "output" else value,
            "output": None,
            "problem": {
                "code": "synthetic_unavailable",
                "stage": "execute",
                "exception_type": "RuntimeError",
                "message": "Synthetic controlled failure",
            },
        }
    elif name == "FeatureObservation":
        available = (
            field == "value"
            or (field == "state" and value == "available")
            or (field == "reason" and value is None)
            or field == "denominator"
        )
        if available:
            updates = {
                "state": "available",
                "value": 0.0,
                "numerator": 0,
                "denominator": None,
                "reason": None,
            }
        else:
            updates = {
                "state": "not_evaluable",
                "value": None,
                "numerator": None,
                "denominator": None,
                "reason": "synthetic_unavailable",
            }
        updates[field] = value
    elif name == "FieldMapping":
        if field == "missing" and value == "null":
            data["column"]["nullable"] = expected["column"]["nullable"] = True
        if field == "decimal_separator":
            updates["thousands_separator"] = None
        elif field == "thousands_separator" and value == ".":
            updates["decimal_separator"] = ","
    elif name == "Measure":
        if field == "operation":
            updates["column"] = None if value == "count_rows" else "amount"
        elif field == "column":
            updates["operation"] = "count_rows" if value is None else "sum"
    elif name == "IngestionResult":
        if field == "state":
            updates = {
                "inspected_records": 1,
                "accepted_records": 1,
                "quarantined": [],
                "output": {
                    "schema_version": "1.0",
                    "uri": "file:///synthetic/trace-ingestion.arrow",
                    "sha256": "0" * 64,
                    "format": "arrow",
                    "media_type": "application/vnd.apache.arrow.file",
                    "size_bytes": 0,
                    "schema_ref": None,
                },
            }
            if value == "quarantined":
                updates["inspected_records"] = 2
                updates["quarantined"] = [
                    {
                        "record": 1,
                        "path": "$",
                        "original_text": "",
                        "code": "synthetic_invalid_record",
                    }
                ]
        elif field == "inspected_records" and value == 0:
            updates = {
                "state": "rejected",
                "accepted_records": 0,
                "quarantined": [],
                "output": None,
            }
    elif name == "NaNPolicy":
        updates["justification"] = (
            "Synthetic explicit NaN policy" if field != "justification" else value
        )
    elif name == "NullPolicy":
        if field == "representations":
            updates["justification"] = "Synthetic explicit absence equivalence"
        else:
            updates["representations"] = ["null"]
    elif name == "ProfileFeature":
        metric = (
            value
            if field == "metric"
            else (
                "log_filas"
                if field == "columns" and not value
                else "razon_salida_entrada"
                if field == "denominator_table"
                else "claves_sin_pareja"
                if field in {"right_table", "right_columns", "null_matches"}
                else data["metric"]
            )
        )
        rows = metric in {"log_filas", "razon_salida_entrada", "expansion_union"}
        ratio = metric in {"razon_salida_entrada", "expansion_union"}
        join = metric == "claves_sin_pareja"
        updates = {
            "metric": metric,
            "columns": [] if rows else ["x"],
            "denominator_table": "source" if ratio else None,
            "right_table": "right" if join else None,
            "right_columns": ["x"] if join else [],
            "null_matches": "never" if join else None,
            "target": None,
        }
        if metric in {"conversiones_fallidas", "fechas_invalidas"}:
            temporal = metric == "fechas_invalidas"
            updates["target"] = {
                "name": "x",
                "logical_type": {"kind": "date" if temporal else "string"},
                "nullable": True,
                "null_policy": {"representations": ["null"], "justification": None},
                "nan_policy": None,
                "numeric_policy": None,
                "temporal_policy": {
                    "kind": "date",
                    "granularity": "day",
                    "lower": None,
                    "upper": None,
                    "closed": "both",
                }
                if temporal
                else None,
                "allowed_values": [],
            }
        updates[field] = value
    elif name == "NumericPolicy":
        if field == "comparison":
            updates["tolerance"] = (
                {
                    "absolute": "0.1",
                    "relative": None,
                    "unit": data["unit"],
                    "justification": "Synthetic sensor resolution",
                }
                if value == "approximate"
                else None
            )
        elif field == "rounding":
            updates["rounding_justification"] = (
                "Synthetic explicit decimal rounding" if value is not None else None
            )
        elif field == "rounding_justification":
            updates["rounding"] = "ROUND_HALF_EVEN" if value is not None else None
    elif name == "ReportCount":
        if field == "value":
            updates["precision"] = "unknown" if value is None else "exact"
        elif field == "precision":
            updates["value"] = None if value == "unknown" else 3
    elif name == "ReportOptions" and field == "mode" and value == "reproduction":
        updates = {
            "include_values": True,
            "include_metadata": True,
            "redact_columns": [],
        }
    elif name == "ReportEvidenceManifest":
        if field == "display_complete":
            updates = {"available_records": 1, "included_examples": 0}
        elif field == "acceptance":
            updates = {"unmet_requirements": ["synthetic_missing_record"]}
    elif name == "ReportValue" and field == "disclosure":
        if value == "visible":
            updates = {
                "kind": "integer",
                "representation": "3",
                "value": {
                    "kind": "integer",
                    "value": "3",
                    "unit": None,
                    "timezone": None,
                },
            }
        else:
            updates = {"representation": "[" + value + "]", "value": None}
    elif name == "ReportWitness":
        if field == "category":
            updates = {"candidate_count": None, "reference_count": None}
        elif field in {"candidate_count", "reference_count"} and value is None:
            updates = {
                "category": "schema",
                "candidate_count": None,
                "reference_count": None,
            }
    elif name == "Tolerance" and field == "absolute" and value is None:
        updates["relative"] = "0.1"
    elif name == "TableSchema" and field == "columns":
        updates = {"keys": [], "order": {"kind": "ignored"}}
    elif name == "TimestampPolicy":
        if (
            field == "naive"
            and value == "preserve"
            or field == "timezone"
            and value is None
        ):
            updates = {
                "timezone": None,
                "naive": "preserve",
                "comparison": "wall_time",
                "ambiguous": "reject",
                "lower": None,
                "upper": None,
            }
        elif field == "ambiguous":
            updates = {"naive": "assume_zone", "timezone": "UTC"}
    elif name == "WindowMeasure":
        if field == "operation":
            updates["column"] = None if value == "row_number" else "amount"
            updates["offset"] = 1
        elif field == "column":
            updates["operation"] = "row_number" if value is None else "lag"
            updates["offset"] = 1
        elif field == "offset":
            updates = {"operation": "lag", "column": "amount"}
    elif name == "WorkflowCheckpoint":
        updates = {"migration": None, "code": "synthetic_controlled_state"}
        if field == "migration":
            updates["state"] = "skipped"
    data.update(copy.deepcopy(updates))
    expected.update(copy.deepcopy(updates))


def serialized(name, expected):
    if name == "Arithmetic" and expected.get("rounding", "exact") == "exact":
        expected.pop("rounding", None)
    if name == "Deduplicate":
        if not expected.get("by"):
            expected.pop("by", None)
        expected.pop("ties", None)
    if name == "EquiJoin" and expected.get("cardinality") == "many_to_many":
        expected.pop("cardinality", None)
    return expected


def prepare(catalog, baseline, discovery, boundary):
    records = {
        r["name"].rsplit(".", 1)[-1]: r for r in discovery.inspect_exports(ef, {})
    }
    literals = {
        c["model"]: c["expected"] for c in catalog["cases"] if c["operation"] == "model"
    }
    cases, exclusions = [], {}
    for row in baseline["rows"]:
        identifier = row["id"]
        if row["status"] != "NOT_RUN" or not identifier.startswith("field:equiframe."):
            continue
        _, qualified, field, suffix = identifier.split(":", 3)
        name = qualified.rsplit(".", 1)[-1]
        if name not in MODELS:
            continue
        data = copy.deepcopy(catalog["seeds"][name]["input"])
        expected = copy.deepcopy(literals[name])
        declaration = next(
            f
            for f in records[name]["fields"]
            if f["id"] == "field:" + qualified + ":" + field
        )
        admitted = True
        if suffix.startswith("value:"):
            value = json.loads(suffix.removeprefix("value:"))
        elif suffix.startswith("member:0:") and name == "NullPolicy":
            value = ["null", json.loads(suffix.removeprefix("member:0:"))]
        elif suffix == "invalid":
            value, admitted = {"wrong": 1}, False
        elif suffix == "default" and (name, field) in {
            ("WindowMeasure", "column"),
            ("Tolerance", "absolute"),
            ("ProfileFeature", "columns"),
            ("FeatureObservation", "numerator"),
            ("FeatureObservation", "denominator"),
            ("FeatureObservation", "reason"),
            ("ComponentDecision", "reason"),
            ("CheckResult", "revision"),
            ("CheckResult", "required"),
            ("CheckResult", "severity"),
            ("WorkflowCheckpoint", "migration"),
        }:
            value = declaration["default"]
            data.pop(field, None)
        elif suffix.startswith("class:"):
            number = int(suffix.removeprefix("class:"))
            label = declaration["continuous_classes"][number]
            if label == "admitted representative":
                value = copy.deepcopy(data.get(field, declaration["default"]))
            elif label == "wrong Python/JSON type":
                value, admitted = {"wrong": 1}, False
            else:
                # Distinct tuples use authored distinct representatives, not a
                # repeated key that would violate an unrelated uniqueness rule.
                if name in {"OrderCheck", "ColumnKeyScope"} and field == "columns":
                    value = ["a", "b"]
                else:
                    old = data.get(field)
                    if name == "ProfileFeature" and field == "right_columns":
                        old = ["x"]
                    if name == "RuleSpec" and field == "applicability":
                        old = ["rule_a"]
                    if name in {"Aggregate", "Window"} and field in {
                        "group_by",
                        "partition_by",
                    }:
                        old = ["a"]
                    if name == "Deduplicate" and field == "by" and not old:
                        old = [
                            {"column": "id", "direction": "ascending", "nulls": "first"}
                        ]
                    variation = boundary.boundary(
                        getattr(ef, name).model_fields[field].annotation,
                        declaration["bounds"],
                        label,
                        old,
                    )
                    if name == "WorkflowSpec" and field == "timeout_seconds":
                        variation = (
                            0.0 if label == "declared lower boundary" else -1.0,
                            False,
                            "greater_than",
                        )
                    if variation is None:
                        exclusions[identifier] = (
                            "Requires a more specific literal context"
                        )
                        continue
                    value, admitted, _ = variation
                    if name == "WorkflowSpec" and field == "stages" and admitted:
                        for position, stage in enumerate(value):
                            stage["stage_id"] = "synthetic_stage_" + str(position)
                    if name in {
                        "ArtifactRef",
                        "ExecutionOptions",
                        "LocalizeTimestamp",
                        "TimestampPolicy",
                        "TimestampType",
                        "TimestampValue",
                    } and field in {
                        "uri",
                        "duckdb_timezone",
                        "timezone",
                        "zone",
                    }:
                        # The one-character boundary 'a' passes length metadata
                        # but cannot satisfy either URI schemes or IANA zones.
                        # Expect semantic rejection without changing the input.
                        admitted = False
        else:
            exclusions[identifier] = "No authored expected for this operation"
            continue
        if suffix != "default":
            data[field] = copy.deepcopy(value)
        expected[field] = copy.deepcopy(value)
        if admitted:
            context(name, field, value, data, expected)
        if suffix == "default":
            data.pop(field, None)
        cases.append(
            {
                "case_id": identifier,
                "obligations": [identifier],
                "model": name,
                "input": data,
                "admitted": admitted,
                "expected": serialized(name, expected) if admitted else None,
                "basis": "Frozen literal baseline plus authored cross-field/serializer context; no observed oracle",
            }
        )
    return {"cases": cases, "exclusions": exclusions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog_raw, catalog = bounded_json(args.catalog)
    baseline_raw, baseline = bounded_json(args.baseline)
    owned.require(
        hashlib.sha256(baseline_raw).hexdigest() in BASELINE_HASHES,
        "Original root baseline bytes differ",
    )
    owned.require(
        hashlib.sha256(catalog_raw).hexdigest() == CATALOG_SHA,
        "Frozen original catalogue differs",
    )
    require_ordinary_parents(args.output.parent)
    owned.require(
        not args.output.exists() and not args.output.is_symlink(),
        "Preserve previous private receipts",
    )
    args.output = args.output.resolve(strict=False)
    owned.require(
        not args.output.is_relative_to(owned.ROOT), "Receipts must remain private"
    )
    owned.require(
        ef.__version__ == "0.12.0a14" and baseline["candidate"] == ef.__version__,
        "A14 baseline required",
    )
    owned.require(
        baseline.get("schema") == "equiframe.a14.contract-revalidation.v1"
        and baseline.get("installed_python_payload_equals_current_source") is True
        and baseline.get("historical_counts_imported") is False
        and baseline.get("total") == 8438
        and baseline.get("verified") == 6201
        and len(baseline.get("rows", ())) == 8438
        and len({row["id"] for row in baseline["rows"]}) == 8438,
        "Expected complete immutable A14 root baseline required",
    )
    package = Path(ef.__file__).absolute().parent
    source = owned.ROOT / "packages/equiframe/src/equiframe"
    owned.require(
        package.is_relative_to(Path(sys.prefix).absolute()), "Use installed SDK"
    )
    for path in source.rglob("*.py"):
        owned.require(
            path.read_bytes() == (package / path.relative_to(source)).read_bytes(),
            "Installed SDK differs from current source",
        )
    discovery = owned.tool(
        "root_context_inventory",
        owned.ROOT / "packages/equiframe/tools/option_inventory.py",
    )
    boundary = owned.tool(
        "root_context_boundaries", owned.ROOT / "tools/option_boundary_followup.py"
    )
    planned = prepare(catalog, baseline, discovery, boundary)
    args.output.mkdir(parents=True)
    raw = (json.dumps(planned, indent=2, allow_nan=False) + "\n").encode()
    (args.output / "catalog.json").write_bytes(raw)
    receipts = []
    for case in planned["cases"]:
        error, observed = None, None
        try:
            instance = getattr(ef, case["model"]).model_validate_json(
                owned.canonical(case["input"])
            )
            observed = instance.model_dump(mode="json")
            status = (
                "PASS"
                if case["admitted"]
                and owned.canonical(observed) == owned.canonical(case["expected"])
                else "FAIL"
            )
        except ValidationError:
            error = "ValidationError"
            status = "FAIL" if case["admitted"] else "EXPECTED_REJECTION"
        except (
            TypeError,
            ValueError,
            RuntimeError,
            AttributeError,
            LookupError,
            ArithmeticError,
            OSError,
            AssertionError,
        ) as failure:
            # Unexpected crashes are failures, never credited as validation.
            error = type(failure).__name__
            status = "FAIL"
        receipts.append(
            {
                "case_id": case["case_id"],
                "obligations": case["obligations"],
                "status": status,
                "observed": observed,
                "error": error,
            }
        )
    owned.require(
        (args.output / "catalog.json").read_bytes() == raw, "Expected catalogue changed"
    )
    result = {
        "schema": "equiframe.root-coupled-context-revalidation.v1",
        "optimized": not __debug__,
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "platform": platform.system(),
            "machine": platform.machine(),
        },
        "baseline_sha256": hashlib.sha256(baseline_raw).hexdigest(),
        "catalog_sha256": hashlib.sha256(raw).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": dict(Counter(r["status"] for r in receipts)),
        "receipts": receipts,
        "source_commit": baseline["source_commit"],
        "wheel_sha256": baseline["wheel_sha256"],
        "scientific_credit": False,
        "scope": "Only identified pending metadata-field contexts; full literal expected JSON",
    }
    (args.output / "result.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {"counts": result["counts"], "receipt": str(args.output / "result.json")}
        )
    )
    return 1 if result["counts"].get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
