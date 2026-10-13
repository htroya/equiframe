"""Observe plain public constructors against prior complete attribute oracles.

Only named admitted parameters, explicit finite values and omitted defaults can
earn frozen inventory IDs. No API-completion, method or invalid-type credit is
inferred. These classes do not reject types merely because they annotate them.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "parser_previous", Path(__file__).with_name("option_cli_parser_followup.py")
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
op = previous.op
PRIOR_CLI = "0ea7684397a96b805731e44170eab5e24a3f15abba81f11eafc776cae34dd397"
REQUIRED = {
    "ArrowInput": {"table": "@arrow"},
    "ArtifactInput": {"ref": "@ref"},
    "PandasInput": {"frame": "@pandas"},
    "PolarsInput": {"frame": "@polars"},
    "LoadedTable": {"table": "@arrow"},
    "PandasTransformation": {
        "transformation_id": "identity",
        "callback": "@pandas_callback",
        "code_version": "manual-v1",
    },
    "PolarsTransformation": {
        "transformation_id": "identity",
        "callback": "@polars_callback",
        "code_version": "manual-v1",
    },
    "DuckDBTransformation": {
        "transformation_id": "identity",
        "sql": "SELECT * FROM input",
        "code_version": "manual-v1",
    },
    "ValidationIssue": {
        "code": "example",
        "location": ["records", 2, "amount"],
        "message": "manual literal",
    },
    "LocalArtifactStore": {"root": "@root"},
    "ParquetDestination": {"root": "@root"},
}
DEFAULTS = {
    "PandasInput": {"index_policy": "preserve"},
    "LoadedTable": {
        "native": None,
        "native_types": [],
        "index": None,
        "meaningful_index": False,
        "origin": None,
        "notes": [],
    },
    "PandasTransformation": {"revision": 1, "engine": "pandas"},
    "PolarsTransformation": {"revision": 1, "engine": "polars"},
    "DuckDBTransformation": {"revision": 1, "engine": "duckdb"},
}
EXPLICIT = {
    "PandasInput": {"index_policy": "preserve"},
    "LoadedTable": {
        "native": "@pandas",
        "native_types": [["id", "int64"], ["amount", "int64"]],
        "index": "@arrow",
        "meaningful_index": True,
        "origin": "@ref",
        "notes": ["manual literal"],
    },
    "PandasTransformation": {"revision": 2, "engine": "pandas"},
    "PolarsTransformation": {"revision": 2, "engine": "polars"},
    "DuckDBTransformation": {"revision": 2, "engine": "duckdb"},
}
ADMISSION = {
    "ArrowInput": {"table": "arrow"},
    "ArtifactInput": {"ref": "ref"},
    "PandasInput": {"frame": "pandas"},
    "PolarsInput": {"frame": "polars"},
    "LoadedTable": {
        "table": "arrow",
        "native": "pandas",
        "native_types": "pairs",
        "index": "arrow",
        "origin": "ref",
        "notes": "strings",
    },
    "PandasTransformation": {
        "transformation_id": "str",
        "callback": "pandas_callback",
        "code_version": "str",
        "revision": "int",
    },
    "PolarsTransformation": {
        "transformation_id": "str",
        "callback": "polars_callback",
        "code_version": "str",
        "revision": "int",
    },
    "DuckDBTransformation": {
        "transformation_id": "str",
        "sql": "str",
        "code_version": "str",
        "revision": "int",
    },
    "ValidationIssue": {"code": "str", "location": "location", "message": "str"},
    "LocalArtifactStore": {"root": "path"},
    "ParquetDestination": {"root": "path"},
}


def inputs(workspace):
    inventory, baseline, done = previous.inputs(workspace)
    path = workspace / "trace85_20261011/cli-parser-normal-v2/result.json"
    op.require(op.digest(path) == PRIOR_CLI, "Prior CLI receipt differs")
    done.update(i for row in op.read(path)["receipts"] for i in row["obligations"])
    op.require(len(done) == 6137, "Prior union differs")
    return inventory, baseline, done


def planned(inventory, pending):
    exports = {record["name"].split(".")[-1]: record for record in inventory["exports"]}
    cases = []
    for name, required in REQUIRED.items():
        declaration = exports[name]
        op.require(
            declaration["kind"] == "class", "Pydantic model constructor excluded"
        )
        parameters = {p["id"].split(":")[-1]: p for p in declaration["parameters"]}
        op.require(
            {n for n, p in parameters.items() if p["required"]} == set(required),
            "Required constructor signature differs",
        )
        defaults = DEFAULTS.get(name, {})
        op.require(
            {n: p["default"] for n, p in parameters.items() if not p["required"]}
            == defaults,
            "Prior literal defaults differ",
        )
        variants = [
            ("defaults", required),
            ("explicit", {**required, **EXPLICIT.get(name, {})}),
        ]
        for parameter, value in (
            (("index_policy", "columns"), ("index_policy", "discard"))
            if name == "PandasInput"
            else []
        ):
            variants.append(("finite-" + value, {**required, parameter: value}))
        if name == "LoadedTable":
            variants.append(("explicit-nulls", {**required, **defaults}))
        for variant, kwargs in variants:
            expected = {**required, **defaults, **kwargs}
            links = []
            for parameter, p in parameters.items():
                prefix = p["id"]
                if parameter not in kwargs:
                    links.append(prefix + ":default")
                else:
                    for finite in p["finite_values"]:
                        if (
                            type(finite) is type(kwargs[parameter])
                            and finite == kwargs[parameter]
                        ):
                            links.append(
                                prefix + ":value:" + previous.calls.canonical(finite)
                            )
                    # Explicit null tests finite null/default values, not a
                    # representative of a non-null branch.
                    if (
                        parameter in ADMISSION[name]
                        and "admitted representative" in p["continuous_classes"]
                        and kwargs[parameter] is not None
                    ):
                        links.append(
                            prefix
                            + ":class:"
                            + str(
                                p["continuous_classes"].index("admitted representative")
                            )
                        )
            links = sorted(set(links) & pending)
            if links:
                cases.append(
                    {
                        "case_id": name + "." + variant,
                        "class": name,
                        "kwargs": kwargs,
                        "expected_attributes": expected,
                        "admission_types": ADMISSION[name],
                        "obligations": links,
                        "parameters": declaration["parameters"],
                    }
                )
    return {
        "schema": "equiframe.plain-constructor-catalog.v1",
        "cases": cases,
        "inventory_sha256": previous.calls.INVENTORY,
        "prior_cli_sha256": PRIOR_CLI,
        "scope": "Complete plain constructor attribute oracles; named admitted parameters, explicit finite values and omitted defaults only; no API/method/rejection inference",
    }


def fixtures(directory):
    import equiframe
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    literal = [{"id": 1, "amount": 11}, {"id": 2, "amount": 22}]
    table = pa.Table.from_pylist(
        literal, schema=pa.schema([("id", pa.int64()), ("amount", pa.int64())])
    )
    pandas = pd.DataFrame({"id": [1, 2], "amount": [11, 22]}, dtype="int64")
    polars = pl.DataFrame(
        {"id": [1, 2], "amount": [11, 22]}, schema={"id": pl.Int64, "amount": pl.Int64}
    )
    op.require(
        table.to_pylist() == literal
        and pandas.to_dict("records") == literal
        and polars.to_dicts() == literal,
        "Independent native fixture differs",
    )
    ref_input = {
        "schema_version": "1.0",
        "uri": "file:///manual/source.arrow",
        "sha256": "0" * 64,
        "format": "arrow",
        "media_type": "application/vnd.apache.arrow.file",
        "size_bytes": 0,
        "schema_ref": None,
    }
    ref = equiframe.ArtifactRef.model_validate(ref_input)
    op.require(ref.model_dump(mode="json") == ref_input, "Reference fixture differs")

    def pandas_callback(inputs, context):
        return inputs["input"]

    def polars_callback(inputs, context):
        return inputs["input"]

    op.require(
        pandas_callback({"input": pandas}, None) is pandas
        and polars_callback({"input": polars}, None) is polars,
        "Callback fixture differs",
    )
    return {
        "@arrow": table,
        "@pandas": pandas,
        "@polars": polars,
        "@ref": ref,
        "@pandas_callback": pandas_callback,
        "@polars_callback": polars_callback,
        "@root": directory.resolve(),
    }


def resolve(value, references):
    if isinstance(value, str) and value in references:
        return references[value]
    if isinstance(value, list):
        return tuple(resolve(item, references) for item in value)
    return value


def strict_equal(observed, expected):
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, tuple):
        return len(observed) == len(expected) and all(
            strict_equal(left, right)
            for left, right in zip(observed, expected, strict=True)
        )
    return observed == expected


def attributes_match(observed, expected, references):
    if set(observed) != set(expected):
        return False
    for name, literal in expected.items():
        value = resolve(literal, references)
        if isinstance(literal, str) and literal in references and literal != "@root":
            if observed[name] is not value:
                return False
        elif not strict_equal(observed[name], value):
            return False
    return True


def admitted(kind, value, references):
    if kind in (
        "arrow",
        "pandas",
        "polars",
        "ref",
        "pandas_callback",
        "polars_callback",
    ):
        return value is references["@" + kind]
    if kind == "path":
        return isinstance(value, Path)
    if kind == "str":
        return type(value) is str
    if kind == "int":
        return type(value) is int
    if kind == "pairs":
        return type(value) is tuple and all(
            type(pair) is tuple and len(pair) == 2 and all(type(v) is str for v in pair)
            for pair in value
        )
    if kind == "strings":
        return type(value) is tuple and all(type(item) is str for item in value)
    if kind == "location":
        return type(value) is tuple and all(type(item) in (str, int) for item in value)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in ("workspace", "catalog", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    inventory, baseline, done = inputs(workspace)
    pending = {r["id"] for r in baseline["rows"]} - done
    catalog = planned(inventory, pending)
    if args.mode == "plan":
        previous.write(args.catalog, catalog)
        print(
            json.dumps(
                {
                    "planned_cases": len(catalog["cases"]),
                    "planned_new_ids": len(
                        {i for c in catalog["cases"] for i in c["obligations"]}
                    ),
                    "catalog_sha256": op.digest(args.catalog),
                    "new_verified_ids": 0,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256
        and op.digest(args.catalog) == args.catalog_sha256
        and op.read(args.catalog) == catalog,
        "Frozen constructor catalog differs",
    )
    package = op.identity(
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl",
        previous.calls.WHEEL,
        Path(__file__).parents[1],
    )
    tool_sha = op.digest(Path(__file__))
    args.output.mkdir(parents=True, exist_ok=False)
    references = fixtures(args.output / "constructor-root")
    import equiframe

    receipts = []
    for case in catalog["cases"]:
        cls = getattr(equiframe, case["class"])
        kwargs = {
            name: resolve(value, references) for name, value in case["kwargs"].items()
        }
        signature = inspect.signature(cls)
        bound = signature.bind(**kwargs)
        bound.apply_defaults()
        value = cls(**kwargs)
        success = attributes_match(vars(value), case["expected_attributes"], references)
        proofs = []
        for p in case["parameters"]:
            name = p["id"].split(":")[-1]
            if (
                name in kwargs
                and name in case["admission_types"]
                and kwargs[name] is not None
            ):
                admission = admitted(
                    case["admission_types"][name], kwargs[name], references
                )
                success = success and admission
                proofs.append(
                    {
                        "name": name,
                        "explicit": True,
                        "admitted": admission,
                        "python_type": type(kwargs[name]).__module__
                        + "."
                        + type(kwargs[name]).__qualname__,
                    }
                )
            if name not in kwargs:
                success = (
                    success
                    and p["required"] is False
                    and strict_equal(
                        bound.arguments[name], resolve(p["default"], references)
                    )
                )
                proofs.append(
                    {"name": name, "explicit": False, "omitted_default_observed": True}
                )
        receipts.append(
            {
                "case_id": case["case_id"],
                "class": case["class"],
                "status": "PASS" if success else "FAIL",
                "expected_attributes": case["expected_attributes"],
                "whole_attributes_match": attributes_match(
                    vars(value), case["expected_attributes"], references
                ),
                "parameter_proofs": proofs,
                "obligations": case["obligations"] if success else [],
            }
        )
    passed = all(row["status"] == "PASS" for row in receipts)
    if not passed:
        for row in receipts:
            row["uncredited_obligations"], row["obligations"] = row["obligations"], []
    ids = {i for row in receipts for i in row["obligations"]}
    op.require(op.digest(Path(__file__)) == tool_sha, "Tool changed during run")
    op.identity(
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl",
        previous.calls.WHEEL,
        Path(__file__).parents[1],
    )
    previous.write(
        args.output / "result.json",
        {
            "schema": "equiframe.plain-constructor-result.v1",
            "candidate": "0.12.0a13",
            "package": package,
            "catalog_sha256": op.digest(args.catalog),
            "tool_sha256": tool_sha,
            "python": sys.version,
            "optimized": bool(sys.flags.optimize),
            "all_expected": passed,
            "receipts": receipts,
            "new_verified_ids": len(ids),
            "verified": len(done | ids),
            "denominator": 8385,
            "human_review": False,
            "scope": catalog["scope"],
        },
    )
    print(
        json.dumps(
            {
                "all_expected": passed,
                "cases": len(receipts),
                "new_verified_ids": len(ids),
                "verified": len(done | ids),
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
