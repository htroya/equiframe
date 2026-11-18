"""Observe complete constructor contexts against frozen source/fixture oracles.

This covers storage, copied mappings, explicit values and actual list factories.
It does not execute transport, ETL, rules or callbacks or infer API/rejection IDs.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import inspect
import io
import json
import sys
from contextlib import contextmanager
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "prior_constructors", Path(__file__).with_name("option_constructor_followup.py")
)
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
op = prior.op
CONSTRUCTOR_RESULT = "53407ebb9d5187b75642475e3ba2ed503f57a1e81030b5d5d1a59dd46e6312d3"
SEED_CATALOG = "9eaa56aa71b803d901b07b56da0a89eb3cb610a44dc67a78513b553288ab59e1"
FACTORIES = ("timings", "effective_configuration", "captured_inputs")
RULE_KINDS = ("schema", "key", "cardinality", "join", "order", "aggregate")


def tuple_recipe(*values):
    return {"$tuple": list(values)}


def list_recipe(*values):
    return {"$list": list(values)}


REQUIRED = {
    "CompiledPlan": {
        "engine": "pandas",
        "transformation": "@transformation",
        "ir_sha256": "1" * 64,
        "contract_sha256": "2" * 64,
        "check": "@CompilationCheck",
    },
    "CompositeDataSource": {"bindings": "@bindings"},
    "FileInput": {"path": "@file", "spec": "@IngestionSpec"},
    "LocalDataSource": {"inputs": "@inputs"},
    "RecordBatchInput": {"open_batches": "@open_batches", "schema": "@schema"},
    "RuleContext": {
        "contract": "@Contract",
        "tables": "@tables",
        "options": "@RuleOptions",
        "cancellation": "@cancellation",
        "started": 0.0,
    },
    "RuleImplementation": {
        "kind": "schema",
        "revision": 1,
        "identity": "fixture-schema-v1",
        "evaluate": "@rule_schema",
    },
    "RunContext": {
        "run_id": "constructor-run",
        "execution_id": "constructor-execution",
        "plan": "@ExecutionPlan",
        "directory": "@directory",
        "store": "@store",
        "cancellation": "@cancellation",
        "deadline": 1000000000.0,
    },
    "SQLiteInput": {
        "path": "@sqlite_path",
        "query": "SELECT n FROM input WHERE id = ?",
        "spec": "@JsonlSpec",
    },
    "StreamInput": {"open_stream": "@open_stream", "spec": "@IngestionSpec"},
    "ValidatedIR": {
        "plan": "@RelationalPlan",
        "contract": "@Contract",
        "node_schemas": tuple_recipe("@NodeSchema"),
        "source_tables": tuple_recipe("input"),
        "output_columns": "@output_columns",
    },
}
DEFAULTS = {
    "FileInput": {"batch_rows": 4096},
    "RunContext": {
        "timings": list_recipe(),
        "effective_configuration": list_recipe(),
        "stage": "preflight",
        "captured_inputs": list_recipe(),
        "captured_output": None,
    },
    "SQLiteInput": {"parameters": tuple_recipe(), "batch_rows": 4096},
    "StreamInput": {"expected_sha256": None, "batch_rows": 4096},
}
EXPLICIT = {
    "FileInput": {"batch_rows": 32},
    "RunContext": {
        "timings": list_recipe("@StageTiming"),
        "effective_configuration": list_recipe("@Parameter"),
        "stage": "source-check",
        "captured_inputs": list_recipe("@TableArtifact"),
        "captured_output": "@TableArtifact",
    },
    "SQLiteInput": {"parameters": tuple_recipe(None), "batch_rows": 32},
    "StreamInput": {"expected_sha256": "0" * 64, "batch_rows": 32},
}


def inputs(workspace):
    inventory, baseline, done = prior.inputs(workspace)
    path = workspace / "trace85_20261011/constructor-normal-v2/result.json"
    op.require(
        op.digest(path) == CONSTRUCTOR_RESULT, "Prior constructor receipt differs"
    )
    done.update(i for row in op.read(path)["receipts"] for i in row["obligations"])
    op.require(len(done) == 6188, "Prior unique union differs")
    path = workspace / "revision_95_20261011/trace_inputs/catalog-a13.json"
    op.require(
        op.digest(path) == SEED_CATALOG, "Original literal fixture catalog differs"
    )
    return inventory, baseline, done, op.read(path)


def model_recipes(catalog):
    names = (
        "ExecutionPlan",
        "IngestionSpec",
        "RelationalPlan",
        "NodeSchema",
        "CompilationCheck",
        "RuleOptions",
        "StageTiming",
        "Parameter",
        "TableArtifact",
    )
    cases = {case["id"]: case for case in catalog["cases"]}
    result = {}
    for name in names:
        case = cases[name + ".construction"]
        op.require(case["operation"] == "model", "Complete model oracle required")
        result[name] = {
            "input": catalog["seeds"][name]["input"],
            "expected": case["expected"],
        }
    plan = result["ExecutionPlan"]
    result["Contract"] = {
        "input": plan["input"]["contract"],
        "expected": plan["expected"]["contract"],
    }
    # Author the JSONL variation before observing SDK output, preserving all
    # original field policies; constructor checks do not claim SQLite.load.
    result["JsonlSpec"] = json.loads(json.dumps(result["IngestionSpec"]))
    for role in ("input", "expected"):
        result["JsonlSpec"][role].update(format="jsonl", header=False)
    return result


def expected_attributes(name, kwargs):
    expected = {**REQUIRED[name], **DEFAULTS.get(name, {}), **kwargs}
    if name == "LocalDataSource":
        return {"_inputs": {"input": "@arrow_input"}}
    if name == "CompositeDataSource":
        return {"_bindings": {"input": tuple_recipe("@provider", "input")}}
    if name == "RuleContext":
        expected.update(
            work=0,
            examined=0,
            violations=0,
            evidence_bytes=0,
            examples=list_recipe(),
            check_id="",
            sink=None,
        )
    return expected


def plan(inventory, pending, seed_catalog):
    exports = {x["name"].split(".")[-1]: x for x in inventory["exports"]}
    cases = []
    for name, required in REQUIRED.items():
        declaration = exports[name]
        op.require(declaration["kind"] == "class", "Pydantic constructor IDs excluded")
        parameters = {p["id"].split(":")[-1]: p for p in declaration["parameters"]}
        op.require(
            {n for n, p in parameters.items() if p["required"]} == set(required),
            "Required signature differs",
        )
        variants = [("defaults", required)]
        if name in EXPLICIT:
            variants.append(("explicit", {**required, **EXPLICIT[name]}))
        if name == "RunContext":
            variants.append(
                (
                    "explicit-nulls",
                    {**required, "deadline": None, "captured_output": None},
                )
            )
        if name == "StreamInput":
            variants.append(("explicit-null", {**required, "expected_sha256": None}))
        if name == "RuleImplementation":
            variants = [
                (
                    kind,
                    {
                        **required,
                        "kind": kind,
                        "identity": "fixture-" + kind + "-v1",
                        "evaluate": "@rule_" + kind,
                    },
                )
                for kind in RULE_KINDS
            ]
        for variant, kwargs in variants:
            links = []
            for parameter, p in parameters.items():
                prefix = p["id"]
                if parameter not in kwargs:
                    links.append(prefix + ":default")
                else:
                    value = kwargs[parameter]
                    if (
                        value is not None
                        and "admitted representative" in p["continuous_classes"]
                    ):
                        links.append(
                            prefix
                            + ":class:"
                            + str(
                                p["continuous_classes"].index("admitted representative")
                            )
                        )
                    for finite in p["finite_values"]:
                        if type(finite) is type(value) and finite == value:
                            links.append(
                                prefix
                                + ":value:"
                                + prior.previous.calls.canonical(finite)
                            )
                    if name == "SQLiteInput" and parameter == "parameters":
                        op.require(
                            p["collection_member_values"]
                            == [{"member_index": 0, "values": [None]}],
                            "SQLite member declaration differs",
                        )
                        links.append(prefix + ":member:0:null")
            cases.append(
                {
                    "case_id": name + "." + variant,
                    "class": name,
                    "kwargs": kwargs,
                    "expected_attributes": expected_attributes(name, kwargs),
                    "parameters": declaration["parameters"],
                    "obligations": sorted(set(links) & pending),
                }
            )
    return {
        "schema": "equiframe.context-constructor-catalog.v1",
        "cases": cases,
        "models": model_recipes(seed_catalog),
        "seed_catalog_sha256": SEED_CATALOG,
        "prior_constructor_sha256": CONSTRUCTOR_RESULT,
        "scope": "Complete stored context attributes and real Python binding; actual copied mappings and independent list factories; explicit constructor admission/default/value/member only; no API/transport/ETL/rule or rejection inference",
    }


def resolve(recipe, references):
    if isinstance(recipe, str) and recipe.startswith("@"):
        return references[recipe]
    if isinstance(recipe, dict) and set(recipe) == {"$tuple"}:
        return tuple(resolve(item, references) for item in recipe["$tuple"])
    if isinstance(recipe, dict) and set(recipe) == {"$list"}:
        return [resolve(item, references) for item in recipe["$list"]]
    if isinstance(recipe, dict):
        return {key: resolve(value, references) for key, value in recipe.items()}
    return recipe


def matches(value, recipe, references):
    if type(recipe) is list:
        return (
            type(value) is list
            and len(value) == len(recipe)
            and all(
                matches(left, right, references)
                for left, right in zip(value, recipe, strict=True)
            )
        )
    if isinstance(recipe, str) and recipe.startswith("@"):
        expected = references[recipe]
        return type(value) is type(expected) and (
            value == expected if isinstance(expected, Path) else value is expected
        )
    if isinstance(recipe, dict) and set(recipe) in ({"$tuple"}, {"$list"}):
        key = "$tuple" if "$tuple" in recipe else "$list"
        expected_type = tuple if key == "$tuple" else list
        values = recipe[key]
        return (
            type(value) is expected_type
            and len(value) == len(values)
            and all(
                matches(left, right, references)
                for left, right in zip(value, values, strict=True)
            )
        )
    if isinstance(recipe, dict):
        return (
            type(value) is dict
            and set(value) == set(recipe)
            and all(
                matches(value[key], item, references) for key, item in recipe.items()
            )
        )
    return type(value) is type(recipe) and value == recipe


def factory_proof(cls, first, second, omitted):
    fields = {field.name: field for field in dataclasses.fields(cls)}
    lists = []
    for name in omitted:
        if name not in FACTORIES:
            continue
        if fields[name].default_factory is not list:
            return False
        for instance in (first, second):
            value = getattr(instance, name)
            if type(value) is not list or value:
                return False
            lists.append(value)
    return len({id(value) for value in lists}) == len(lists)


def fixtures(catalog, directory):
    import equiframe as ef
    import pandas as pd
    import pyarrow as pa
    from equiframe import rules

    refs = {}
    for name, recipe in catalog["models"].items():
        model_name = "IngestionSpec" if name == "JsonlSpec" else name
        model = getattr(ef, model_name).model_validate_json(json.dumps(recipe["input"]))
        op.require(
            matches(model.model_dump(mode="json"), recipe["expected"], {}),
            "Frozen complete model fixture differs: " + name,
        )
        refs["@" + name] = model
    expected_rows = [{"id": 1, "value": "one"}, {"id": 2, "value": None}]
    table = pa.Table.from_pylist(
        expected_rows,
        schema=pa.schema(
            [
                pa.field("id", pa.int64(), nullable=False),
                pa.field("value", pa.string(), nullable=True),
            ]
        ),
    )
    op.require(table.to_pylist() == expected_rows, "Literal Arrow fixture differs")
    directory.mkdir()
    file = directory / "input.csv"
    file.write_bytes(b"n\n1\n")
    sqlite_path = directory / "input.sqlite"
    refs.update(
        {
            "@directory": directory.resolve(),
            "@file": file.resolve(),
            "@sqlite_path": sqlite_path.resolve(),
            "@schema": table.schema,
            "@cancellation": ef.CancellationToken(),
            "@store": ef.LocalArtifactStore(directory / "artifacts"),
        }
    )
    op.require(refs["@cancellation"].cancelled is False, "Cancellation fixture differs")
    refs["@arrow_input"] = ef.ArrowInput(table)
    refs["@inputs"] = {"input": refs["@arrow_input"]}
    refs["@provider"] = ef.LocalDataSource(refs["@inputs"])
    op.require(
        type(refs["@provider"]) is ef.LocalDataSource
        and refs["@provider"].table_names == ("input",),
        "Actual provider fixture differs",
    )
    refs["@bindings"] = {"input": (refs["@provider"], "input")}
    refs["@tables"] = {"input": table}
    refs["@output_columns"] = refs["@NodeSchema"].columns

    @contextmanager
    def open_batches():
        yield tuple(table.to_batches())

    @contextmanager
    def open_stream():
        with io.BytesIO(b"n\n1\n") as source:
            yield source

    refs["@open_batches"], refs["@open_stream"] = open_batches, open_stream
    with open_batches() as batches:
        op.require(
            all(type(batch) is pa.RecordBatch for batch in batches)
            and pa.Table.from_batches(batches).to_pylist() == expected_rows,
            "Real batch factory fixture differs",
        )
    with open_stream() as stream:
        op.require(
            isinstance(stream, io.BufferedIOBase) and stream.read() == b"n\n1\n",
            "Real binary stream fixture differs",
        )

    def transform(inputs, context):
        return inputs["input"]

    native = pd.DataFrame({"id": [1, 2], "value": ["one", None]})
    op.require(
        transform({"input": native}, None) is native, "Transformation fixture differs"
    )
    refs["@transformation"] = ef.PandasTransformation(
        "fixture-identity", transform, "fixture-v1"
    )
    for kind in RULE_KINDS:
        refs["@rule_" + kind] = getattr(rules, "_" + kind)
        op.require(
            callable(refs["@rule_" + kind])
            and len(inspect.signature(refs["@rule_" + kind]).parameters) == 2,
            "Actual rule callback signature differs",
        )
    return refs


def execute(case, refs):
    import equiframe as ef

    cls = getattr(ef, case["class"])
    kwargs = {name: resolve(recipe, refs) for name, recipe in case["kwargs"].items()}
    signature = inspect.signature(cls)
    bound = signature.bind(**kwargs)
    bound.apply_defaults()
    code = cls.__init__.__code__
    observed = []

    def profile(frame, event, _):
        if event == "call" and frame.f_code is code:
            observed.append({name: frame.f_locals[name] for name in kwargs})

    saved = sys.getprofile()
    try:
        sys.setprofile(profile)
        instance = cls(**kwargs)
    finally:
        sys.setprofile(saved)
    passed = (
        len(observed) == 1
        and all(
            matches(observed[0][name], recipe, refs)
            for name, recipe in case["kwargs"].items()
        )
        and matches(vars(instance), case["expected_attributes"], refs)
    )
    copies = {}
    if case["class"] in ("LocalDataSource", "CompositeDataSource"):
        parameter, attribute = (
            ("inputs", "_inputs")
            if case["class"] == "LocalDataSource"
            else ("bindings", "_bindings")
        )
        copies[parameter] = getattr(instance, attribute) is not kwargs[parameter]
        passed = passed and copies[parameter]
    factories = {}
    if case["class"] == "RunContext" and any(name not in kwargs for name in FACTORIES):
        second = cls(**kwargs)
        factories["independent_empty_lists"] = factory_proof(
            cls, instance, second, set(FACTORIES) - set(kwargs)
        )
        passed = (
            passed
            and factories["independent_empty_lists"]
            and matches(vars(second), case["expected_attributes"], refs)
        )
    defaults = []
    for p in case["parameters"]:
        name = p["id"].split(":")[-1]
        if name not in kwargs:
            if p["default"] != {"repr": "<factory>"}:
                recipe = DEFAULTS[case["class"]][name]
                passed = (
                    passed
                    and matches(bound.arguments[name], recipe, refs)
                    and matches(getattr(instance, name), recipe, refs)
                )
            defaults.append(name)
    return {
        "case_id": case["case_id"],
        "status": "PASS" if passed else "FAIL",
        "actual_constructor_entries": len(observed),
        "whole_attributes_match": matches(
            vars(instance), case["expected_attributes"], refs
        ),
        "explicit_parameters_observed": sorted(observed[0])
        if len(observed) == 1
        else [],
        "omitted_defaults": defaults,
        "mapping_copy_proofs": copies,
        "factory_proofs": factories,
        "expected_attributes": case["expected_attributes"],
        "obligations": case["obligations"] if passed else [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in ("workspace", "catalog", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    inventory, baseline, done, seed = inputs(workspace)
    catalog = plan(inventory, {r["id"] for r in baseline["rows"]} - done, seed)
    if args.mode == "plan":
        prior.previous.write(args.catalog, catalog)
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
        "Frozen context catalog differs",
    )
    wheel = (
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13-py3-none-any.whl"
    )
    package = op.identity(wheel, prior.previous.calls.WHEEL, Path(__file__).parents[1])
    tool_sha = op.digest(Path(__file__))
    args.output.mkdir(parents=True, exist_ok=False)
    refs = fixtures(catalog, args.output / "owned-fixtures")
    receipts = [execute(case, refs) for case in catalog["cases"]]
    passed = all(row["status"] == "PASS" for row in receipts)
    if not passed:
        for row in receipts:
            row["uncredited_obligations"], row["obligations"] = row["obligations"], []
    current = {i for row in receipts for i in row["obligations"]}
    op.require(op.digest(Path(__file__)) == tool_sha, "Tool changed during run")
    op.identity(wheel, prior.previous.calls.WHEEL, Path(__file__).parents[1])
    prior.previous.write(
        args.output / "result.json",
        {
            "schema": "equiframe.context-constructor-result.v1",
            "candidate": "0.12.0a13",
            "package": package,
            "tool_sha256": tool_sha,
            "catalog_sha256": op.digest(args.catalog),
            "seed_catalog_sha256": SEED_CATALOG,
            "python": sys.version,
            "optimized": bool(sys.flags.optimize),
            "all_expected": passed,
            "receipts": receipts,
            "new_verified_ids": len(current),
            "verified": len(done | current),
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
                "new_verified_ids": len(current),
                "verified": len(done | current),
                "failures": [r["case_id"] for r in receipts if r["status"] != "PASS"],
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
