"""Freeze literal EDA constructor cases before executing the installed SDK.

Metadata contracts only: no native calculation, normality or scientific credit.
The original root inventory stays separate. Unsupported field contexts remain
pending; observed outcomes must never become expected outcomes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
ZERO_SHA = "0" * 64
SOURCE = {
    "path": "synthetic.csv",
    "format": "csv",
    "snapshot_id": "synthetic",
    "expected_sha256": None,
    "expected_bytes": None,
    "manifest_path": None,
    "manifest_sha256": None,
    "delimiter": ",",
}
RESOURCES = {
    "memory_mb": 512,
    "threads": 1,
    "timeout_seconds": 300.0,
    "temp_disk_mb": 256,
    "max_input_bytes": 536870912,
    "max_rows": 10000000,
    "max_columns": 256,
    "max_groups": 100,
    "examples": 10,
    "top_categories": 10,
    "histogram_bins": 20,
    "chart_rows": 200,
    "max_report_bytes": 33554432,
}
SEEDS = {
    "Source": SOURCE,
    "Resources": RESOURCES,
    "Conversion": {
        "column": "amount",
        "target": "typed",
        "kind": "decimal",
        "empty": "invalid",
        "precision": 38,
        "scale": 6,
    },
    "KeyRule": {
        "columns": ["id"],
        "incomplete": "exclude",
        "empty_is_missing": True,
        "require_unique": False,
    },
    "NumericRule": {
        "column": "amount",
        "groups": [],
        "monetary": False,
        "currency_column": None,
        "unit": None,
        "outliers": "iqr",
        "multiplier": 1.5,
        "min_support": 5,
    },
    "EdaConfig": {
        "schema_version": "1.0",
        "rules_id": "generic",
        "rules_revision": 1,
        "identifiers": [],
        "conversions": [],
        "keys": [],
        "numeric": [],
        "percentiles": [0.25, 0.5, 0.75],
        "stddev": "population",
        "charts": False,
        "resources": RESOURCES,
    },
    "ColumnProfile": {
        "name": "amount",
        "physical_type": "BIGINT",
        "rows": 0,
        "nulls": 0,
        "nan": 0,
        "empty": 0,
        "zero": 0,
        "nonfinite": 0,
        "valid": 0,
        "distinct_present": 0,
        "null_rate": None,
        "empty_rate": None,
        "nan_rate": None,
        "frequencies": [],
    },
    "DuplicateProfile": {
        "columns": ["id"],
        "denominator": 0,
        "incomplete_rows": 0,
        "policy": "exclude",
        "repeated_groups": 0,
        "involved_rows": 0,
        "excess_rows": 0,
        "excess_rate": None,
        "examples": [],
    },
    "Finding": {
        "code": "synthetic",
        "severity": "observation",
        "column": None,
        "count": None,
        "denominator": None,
        "reason": "Synthetic metadata",
        "examples": [],
    },
    "ResultFile": {"path": "summary.json", "bytes": 0, "sha256": ZERO_SHA},
    "EdaManifest": {
        "schema_version": "1.0",
        "kind": "equiframe.eda",
        "run_id": "synthetic",
        "state": "failed",
        "files": [
            {"path": name, "bytes": 0, "sha256": ZERO_SHA}
            for name in (
                "summary.json",
                "source.json",
                "config.json",
                "findings.json",
                "report.html",
            )
        ],
    },
    "EdaResult": {
        "schema_version": "1.0",
        "run_id": "synthetic",
        "producer_version": "0.12.0a14",
        "snapshot_id": "synthetic",
        "state": "failed",
        "reason": None,
        "elapsed_seconds": 0.0,
        "calculation_elapsed_seconds": 0.0,
        "chart_state": "not_requested",
        "chart_reason": None,
        "source": SOURCE,
        "source_sha256": None,
        "source_unchanged": None,
        "snapshot_complete": False,
        "config_sha256": ZERO_SHA,
        "rows": 0,
        "columns": [],
        "duplicates": [],
        "conversions": [],
        "numeric": [],
        "findings": [],
        "environment": {},
        "limits": [],
        "evidence_links": [],
    },
}
# These are authored literal defaults, not model serialization or runtime output.
DEFAULT_KEYS = {
    "Source": (
        "format",
        "expected_sha256",
        "expected_bytes",
        "manifest_path",
        "manifest_sha256",
        "delimiter",
    ),
    "Resources": tuple(RESOURCES),
    "Conversion": ("empty", "precision", "scale"),
    "KeyRule": ("incomplete", "empty_is_missing", "require_unique"),
    "NumericRule": (
        "groups",
        "monetary",
        "currency_column",
        "unit",
        "outliers",
        "multiplier",
        "min_support",
    ),
    "EdaConfig": tuple(SEEDS["EdaConfig"]),
    "DuplicateProfile": ("incomplete_rows",),
    "Finding": ("column", "count", "denominator", "examples"),
    "EdaManifest": ("schema_version", "kind"),
    "EdaResult": (
        "schema_version",
        "calculation_elapsed_seconds",
        "chart_state",
        "chart_reason",
        "snapshot_complete",
        "columns",
        "duplicates",
        "conversions",
        "numeric",
        "findings",
        "evidence_links",
    ),
}
DEFAULTS = {
    name: {key: copy.deepcopy(SEEDS[name][key]) for key in keys}
    for name, keys in DEFAULT_KEYS.items()
}
DEFAULTS["Source"]["format"] = "parquet"
METHODS = {
    "Conversion": "scale_fits",
    "KeyRule": "columns_unique",
    "NumericRule": "monetary_groups",
    "EdaConfig": "conversions_unique",
    "EdaResult": "completed_capture",
    "ResultFile": "relative_member",
    "EdaManifest": "closed_names",
    "Source": "manifest_pair",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tool(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    require(
        specification is not None and specification.loader is not None,
        "Owned helper unavailable",
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


def contextualize(name, field, value, payload, expected):
    """Authored coupled contexts; unrelated primitive metadata remains literal."""
    updates = {}
    if name == "Source" and field == "manifest_path":
        updates["manifest_sha256"] = None if value is None else ZERO_SHA
    elif name == "Source" and field == "manifest_sha256":
        updates["manifest_path"] = None if value is None else "manifest.json"
    elif name == "Conversion" and field == "precision":
        updates["scale"] = 0
    elif name == "NumericRule" and field == "monetary" and value is True:
        updates = {"groups": ["currency"], "currency_column": "currency"}
    elif name == "EdaResult" and field == "state" and value == "completed":
        updates = {
            "snapshot_complete": True,
            "source_unchanged": True,
            "source_sha256": ZERO_SHA,
        }
    payload.update(copy.deepcopy(updates))
    expected.update(copy.deepcopy(updates))


def plan(eda, inventory, boundary):
    known = {row["id"] for row in inventory["rows"]}
    cases = []
    exclusions = {}

    def add(identifier, name, operation, payload, expected, admitted=True):
        require(identifier in known, "Unknown obligation")
        require(
            not any(c["obligation"] == identifier for c in cases), "Repeated obligation"
        )
        cases.append(
            {
                "id": identifier,
                "obligation": identifier,
                "model": name,
                "operation": operation,
                "input": payload,
                "expected": expected,
                "admitted": admitted,
                "basis": "Literal synthetic metadata and declared contract; no observed oracle",
            }
        )

    for record in inventory["inventory"]["exports"]:
        name = record["name"].rsplit(".", 1)[-1]
        if name not in SEEDS:
            continue
        seed = SEEDS[name]
        add(record["id"], name, "model", copy.deepcopy(seed), copy.deepcopy(seed))
        for field in record["fields"]:
            key = field["id"].rsplit(":", 1)[-1]
            prefix = field["id"]
            if field["required"]:
                payload = copy.deepcopy(seed)
                del payload[key]
                add(prefix + ":required_omission", name, "model", payload, None, False)
            else:
                require(key in DEFAULTS.get(name, {}), "Literal default missing")
                payload, expected = copy.deepcopy(seed), copy.deepcopy(seed)
                del payload[key]
                expected[key] = copy.deepcopy(DEFAULTS[name][key])
                add(prefix + ":default", name, "model", payload, expected)
            for value in field["finite_values"]:
                payload, expected = copy.deepcopy(seed), copy.deepcopy(seed)
                payload[key] = expected[key] = copy.deepcopy(value)
                contextualize(name, key, value, payload, expected)
                add(
                    prefix + ":value:" + canonical(value),
                    name,
                    "model",
                    payload,
                    expected,
                )
            wrong = [] if key == "environment" else {"unexpected": 1}
            payload = copy.deepcopy(seed)
            payload[key] = wrong
            add(prefix + ":invalid", name, "model", payload, None, False)
            for index, label in enumerate(field["continuous_classes"]):
                admitted = True
                if label == "admitted representative":
                    value = copy.deepcopy(seed[key])
                elif label == "wrong Python/JSON type":
                    value, admitted = wrong, False
                else:
                    variant = boundary.boundary(
                        getattr(eda, name).model_fields[key].annotation,
                        field["bounds"],
                        label,
                        seed[key],
                    )
                    if variant is None:
                        exclusions[prefix + ":class:" + str(index)] = (
                            "Unsupported annotated container context"
                        )
                        continue
                    value, admitted, _ = variant
                payload, expected = copy.deepcopy(seed), copy.deepcopy(seed)
                payload[key] = expected[key] = copy.deepcopy(value)
                if admitted:
                    contextualize(name, key, value, payload, expected)
                add(
                    prefix + ":class:" + str(index),
                    name,
                    "model",
                    payload,
                    expected if admitted else None,
                    admitted,
                )
        if name in METHODS:
            identifier = "method:equiframe.eda." + name + "." + METHODS[name]
            add(identifier, name, "method", copy.deepcopy(seed), "same_object")
    # Native expectations below describe authored fixture contents, not engines.
    for record in inventory["inventory"]["exports"]:
        if record["kind"] != "function":
            continue
        function = record["name"].rsplit(".", 1)[-1]
        expected = {
            "state": "completed",
            "rows": 2 if function == "analyze_migration" else 3,
            "columns": ["currency", "total"]
            if function == "analyze_migration"
            else ["id", "amount"],
            "nulls": [0, 1],
            "zero": [0, 0] if function == "analyze_migration" else [0, 1],
            "snapshot_complete": True,
            "source_unchanged": True,
        }

        def api_case(
            identifier,
            parameter=None,
            recipe="baseline",
            admitted=True,
            function=function,
            expected=expected,
        ):
            add(
                identifier,
                function,
                "api",
                {"function": function, "parameter": parameter, "recipe": recipe},
                copy.deepcopy(expected)
                if admitted
                else {"refused_invalid_metadata": True},
                admitted,
            )

        api_case(record["id"])
        for parameter in record["parameters"]:
            identifier = parameter["id"]
            name = identifier.rsplit(":", 1)[-1]
            api_case(
                identifier
                + (":required_omission" if parameter["required"] else ":default"),
                name,
                "omitted",
                not parameter["required"],
            )
            for value in parameter["finite_values"]:
                api_case(
                    identifier + ":value:" + canonical(value),
                    name,
                    "null" if value is None else value,
                )
            api_case(identifier + ":invalid", name, "wrong_type", False)
            for index, label in enumerate(parameter["continuous_classes"]):
                require(
                    label in ("admitted representative", "wrong Python/JSON type"),
                    "Native parameter boundary requires an authored fixture",
                )
                admitted = label == "admitted representative"
                api_case(
                    identifier + ":class:" + str(index),
                    name,
                    "representative" if admitted else "wrong_type",
                    admitted,
                )
    return {
        "cases": cases,
        "exclusions": exclusions,
        "scope": "EDA model metadata, eight validation methods and four native/read APIs with their declared parameters. Root SDK, other namespaces and scientific acceptance remain separate.",
    }


def native_fixtures(eda, directory):
    import equiframe as ef
    import pyarrow as pa
    from equiframe.examples.journeys import b_native_migration as journey

    inputs = directory / "inputs"
    inputs.mkdir(parents=True)
    path = inputs / "synthetic.arrow"
    table = pa.table(
        {
            "id": ["001", "002", "003"],
            "amount": pa.array([0.0, None, 10.0], type=pa.float64()),
        }
    )
    with pa.ipc.new_file(path, table.schema) as writer:
        writer.write_table(table)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source = eda.Source(
        path=str(path),
        format="arrow",
        snapshot_id="synthetic",
        expected_sha256=digest,
        expected_bytes=path.stat().st_size,
    )
    artifact = ef.TableArtifact(
        name="synthetic",
        row_count=3,
        data=ef.ArtifactRef(
            schema_version="1.0",
            uri=path.as_uri(),
            format="arrow",
            media_type="application/vnd.apache.arrow.file",
            sha256=digest,
            size_bytes=path.stat().st_size,
        ),
        columns=(
            ef.PhysicalColumn(
                name="id",
                engine_type="arrow",
                arrow_type="string",
                null_count=0,
                nan_count=0,
            ),
            ef.PhysicalColumn(
                name="amount",
                engine_type="arrow",
                arrow_type="double",
                null_count=1,
                nan_count=0,
            ),
        ),
    )
    reader = directory / "reader-fixture"
    eda.analyze(source, output=reader)
    # The packaged example uses two real engines and an authored Decimal oracle.
    # Its bytes were checked against the selected wheel before any invocation.
    migration_root = directory / "migration-fixture"
    journey.run(migration_root, scenario="good")
    documents = list(migration_root.rglob("migration.json"))
    require(len(documents) == 1, "Native migration fixture is not unique")
    return {
        "source": source,
        "artifact": artifact,
        "path": documents[0].parent,
        "reader": reader,
        "root": directory,
        "input": path,
        "sha256": digest,
    }


def observe_api(case, eda, fixtures, index):
    recipe = case["input"]
    function, parameter, variant = (
        recipe["function"],
        recipe["parameter"],
        recipe["recipe"],
    )
    arguments = {
        "analyze": {"source": fixtures["source"]},
        "analyze_artifact": {"artifact": fixtures["artifact"]},
        "analyze_migration": {"path": fixtures["path"]},
        "read_result": {"path": fixtures["reader"]},
    }[function].copy()
    if function != "read_result":
        arguments["output"] = fixtures["root"] / "cases" / str(index)
    if variant == "omitted":
        arguments.pop(parameter, None)
    elif variant == "wrong_type":
        arguments[parameter] = 17
    elif variant == "null":
        arguments[parameter] = None
    elif parameter == "side":
        arguments[parameter] = variant
    elif variant == "representative" and parameter == "config":
        arguments[parameter] = eda.EdaConfig()
    elif variant == "representative" and parameter == "cancellation":

        def continue_analysis():
            return False

        arguments[parameter] = continue_analysis
    result = getattr(eda, function)(**arguments)
    if not case["admitted"]:
        # Invalid callback metadata is recorded by the existing diagnostic API;
        # unrelated runtime/resource failures are not a successful rejection.
        return {
            "refused_invalid_metadata": result.state == "failed"
            and result.reason is not None
            and result.reason.startswith("TypeError:")
        }
    return {
        "state": result.state,
        "rows": result.rows,
        "columns": [column.name for column in result.columns],
        "nulls": [column.nulls for column in result.columns],
        "zero": [column.zero for column in result.columns],
        "snapshot_complete": result.snapshot_complete,
        "source_unchanged": result.source_unchanged,
    }


def execute(case, eda, fixtures=None, index=0):
    from pydantic import ValidationError

    observed, error = None, None
    try:
        if case["operation"] == "api":
            observed = observe_api(case, eda, fixtures, index)
            matched = canonical(observed) == canonical(case["expected"])
            status = (
                ("PASS" if case["admitted"] else "EXPECTED_REJECTION")
                if matched
                else "FAIL"
            )
            return {
                "case_id": case["id"],
                "obligations": [case["obligation"]],
                "status": status,
                "observed": observed,
                "error": error,
            }
        model = getattr(eda, case["model"]).model_validate_json(
            canonical(case["input"])
        )
        if case["operation"] == "method":
            returned = getattr(model, METHODS[case["model"]])()
            observed = "same_object" if returned is model else "different_object"
        else:
            observed = model.model_dump(mode="json")
        status = (
            "PASS"
            if case["admitted"] and canonical(observed) == canonical(case["expected"])
            else "FAIL"
        )
    except ValidationError:
        error = "ValidationError"
        status = "FAIL" if case["admitted"] else "EXPECTED_REJECTION"
    except (TypeError, ValueError, AttributeError) as exception:
        # Only the frozen wrong-type/omission API cases admit these refusals.
        error = type(exception).__name__
        status = (
            "EXPECTED_REJECTION"
            if case["operation"] == "api" and not case["admitted"]
            else "FAIL"
        )
    return {
        "case_id": case["id"],
        "obligations": [case["obligation"]],
        "status": status,
        "observed": observed,
        "error": error,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Preserve previous receipt")
    require(
        not args.output.absolute().is_relative_to(ROOT),
        "Use private outputs outside checkout",
    )
    import equiframe
    from equiframe import eda

    require(equiframe.__version__ == "0.12.0a14", "A14 required")
    require(
        hashlib.sha256(args.wheel.read_bytes()).hexdigest() == args.sha256,
        "Wheel identity mismatch",
    )
    package = Path(equiframe.__file__).absolute().parent
    require(
        package.is_relative_to(Path(sys.prefix).absolute())
        and not package.is_relative_to(ROOT),
        "Use installed SDK",
    )
    with zipfile.ZipFile(args.wheel) as archive:
        for member in archive.namelist():
            if member.startswith("equiframe/") and not member.endswith("/"):
                require(
                    (package.parent / member).read_bytes() == archive.read(member),
                    "Installed payload mismatch",
                )
    discovery = tool(
        "eda_owned_inventory", ROOT / "packages/equiframe/tools/option_inventory.py"
    )
    boundary = tool("eda_owned_boundaries", ROOT / "tools/option_boundary_followup.py")
    metadata = {
        "environment": {"python": sys.version, "executable": sys.executable},
        "commit": args.commit,
        "wheel_sha256": args.sha256,
        "exports": discovery.inspect_exports(eda, {}),
        "cli": [],
        "distributions": [],
    }
    inventory = {"inventory": metadata, "rows": discovery.obligations(metadata)}
    require(len(inventory["rows"]) == 704, "EDA public inventory changed")
    frozen = plan(eda, inventory, boundary)
    args.output.mkdir(parents=True)
    plan_bytes = (
        json.dumps(frozen, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode()
    with (args.output / "catalog.json").open("xb") as out:
        out.write(plan_bytes)
    # No execution has occurred before this catalogue is sealed on disk.
    fixtures = native_fixtures(eda, args.output / "native-fixtures")
    receipts = [
        execute(case, eda, fixtures, index)
        for index, case in enumerate(frozen["cases"])
    ]
    require(
        hashlib.sha256(fixtures["input"].read_bytes()).hexdigest()
        == fixtures["sha256"],
        "Native fixture changed",
    )
    require(
        (args.output / "catalog.json").read_bytes() == plan_bytes,
        "Expected catalogue changed",
    )
    by_id = {r["obligations"][0]: r for r in receipts}
    for row in inventory["rows"]:
        receipt = by_id.get(row["id"])
        row["status"] = receipt["status"] if receipt else "NOT_RUN"
        row["case_ids"] = [receipt["case_id"]] if receipt else []
    result = {
        "schema": "equiframe.eda-contract-revalidation.v1",
        "source_commit": args.commit,
        "wheel_sha256": args.sha256,
        "optimized": not __debug__,
        "catalog_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": dict(Counter(row["status"] for row in inventory["rows"])),
        "total": len(inventory["rows"]),
        "receipts": receipts,
        "rows": inventory["rows"],
        "scientific_credit": False,
        "scope": frozen["scope"],
    }
    with (args.output / "result.json").open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, ensure_ascii=True, allow_nan=False)
        out.write("\n")
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "total": result["total"],
                "receipt": str(args.output / "result.json"),
            }
        )
    )
    return 1 if result["counts"].get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
