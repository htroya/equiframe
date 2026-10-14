"""Freeze native operation expectations and map only executed pending obligations.

Three synthetic rows, including a duplicate, have an authored expected output.
This validates actual operations, defaults and path rejection, not scientific O.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

import equiframe as ef

ROOT = Path(__file__).resolve().parents[1]
ROWS = [{"id": 1}, {"id": 1}, {"id": 2}]
ARGUMENTS = {
    "execute": ("plan", "source", "registry"),
    "run_pipeline": ("spec", "source", "registry"),
    "compare": ("left", "right", "contract"),
    "diff": ("candidate", "expected", "contract"),
    "migrate": ("spec", "source"),
    "verify": ("outputs", "contract", "snapshots", "policy"),
    "evaluate_rules": ("execution",),
    "profile_execution": ("execution", "spec"),
    "reduce_case": ("inputs", "predicate", "predicate_version", "failure_signature"),
    "run_workflow": ("spec", "source"),
    "ingest_file": ("path", "spec"),
    "capture_duckdb": ("sql",),
    "ParquetDestination": (),
}
EXPECTED = {
    "execute": {"state": "completed", "rows": ROWS},
    "run_pipeline": {"complete": True, "execution": "completed", "rows": ROWS},
    "compare": {"complete": True, "state": "equivalent", "differences": 0},
    "diff": {"complete": True, "state": "equivalent", "differences": 0},
    "migrate": {
        "complete": True,
        "state": "equivalent",
        "source": ROWS,
        "target": ROWS,
    },
    "verify": {"operational_state": "passed", "technical": ["passed"]},
    "evaluate_rules": {"complete": True, "decision": "no_alert"},
    "profile_execution": {"complete": True, "values": [math.log1p(3)]},
    "reduce_case": {"status": "reduced", "baseline_verified": True, "retained": []},
    "run_workflow": {"complete": True, "rows": ROWS, "states": ["passed"]},
    "ingest_file": {
        "state": "completed",
        "accepted": 3,
        "rows": ROWS,
        "source_unchanged": True,
    },
    "capture_duckdb": {"count": 3, "rows": ROWS},
    "ParquetDestination": {"current": None},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "Owned helper missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(pending):
    cases = []
    remaining = set(pending)

    def add(owner, variant, links, *, reject=False, none_parameters=()):
        selected = sorted(set(links) & remaining)
        remaining.difference_update(selected)
        cases.append(
            {
                "id": owner + "." + variant,
                "owner": owner,
                "variant": variant,
                "none_parameters": list(none_parameters),
                "obligations": selected,
                **(
                    {"expected_error": "TypeError"}
                    if reject
                    else {"expected": EXPECTED[owner]}
                ),
            }
        )

    for owner, arguments in ARGUMENTS.items():
        directory = "root" if owner == "ParquetDestination" else "work_dir"
        prefix = "parameter:equiframe." + owner + ":"
        signature = inspect.signature(getattr(ef, owner))
        provided = {*arguments, directory}
        defaults = [
            p.name
            for p in signature.parameters.values()
            if p.default is not inspect.Parameter.empty and p.name not in provided
        ]
        links = [
            "api:equiframe." + owner,
            *[prefix + name + ":class:0" for name in provided],
            *[prefix + name + ":default" for name in defaults],
        ]
        add(owner, "explicit_root", links)
        nullable = [
            name for name in defaults if signature.parameters[name].default is None
        ]
        if nullable:
            add(
                owner,
                "explicit_none_options",
                [prefix + name + ":value:null" for name in nullable],
                none_parameters=nullable,
            )
        if signature.parameters[directory].default is None:
            add(owner, "default_root", [prefix + directory + ":default"])
            add(owner, "none_root", [prefix + directory + ":value:null"])
        add(owner, "wrong_zero_root", [prefix + directory + ":invalid"], reject=True)
        add(owner, "wrong_mapping_root", [prefix + directory + ":class:1"], reject=True)
    return {
        "scope": "Actual native operations/defaults and typed output-root rejection",
        "fixture": {
            "rows": ROWS,
            "rules": "One required output schema check",
            "science": False,
        },
        "cases": cases,
    }


def setup(root):
    import pyarrow as pa

    root.mkdir()
    column = ef.ColumnSpec(
        name="id",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    contract = ef.bag_contract((column,)).spec.contract
    contract = ef.Contract.model_validate(
        contract.model_copy(
            update={
                "rules": (
                    ef.RuleSpec(
                        rule_id="schema",
                        revision=1,
                        specification=ef.SchemaCheck(table="result"),
                        required=True,
                        severity="error",
                    ),
                )
            }
        )
    )
    data = pa.table({"id": [1, 1, 2]})
    source: ef.DataSource = ef.LocalDataSource({"source": ef.ArrowInput(data)})
    registry = ef.TransformationRegistry()
    registry.register(
        ef.PandasTransformation(
            "identity",
            lambda inputs, context: inputs["source"].copy(),
            "owned-three-row-v1",
        )
    )
    execution_plan = ef.ExecutionPlan(
        contract=contract, engine="pandas", transformation_id="identity"
    )
    execution = ef.execute(
        execution_plan, source=source, registry=registry, work_dir=root / "baseline"
    )
    require(
        execution.state == "completed" and execution.output is not None,
        "Baseline execution incomplete",
    )
    require(
        ef.read_table(execution.output.data).to_pylist() == ROWS,
        "Baseline changed authored rows",
    )
    migration = ef.MigrationSpec(
        ir=ef.RelationalPlan(
            nodes=(ef.Scan(node_id="scan", table="source"),), output="scan"
        ),
        contract=contract,
        source_engine="pandas",
        target_engine="polars",
        require_rules=False,
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            justification="Fixture RangeIndex is transport metadata; id is explicit",
        ),
    )
    workflow = ef.WorkflowSpec(
        workflow_id="owned",
        stages=(
            ef.WorkflowStage(
                stage_id="one",
                migration=migration,
                inputs=(ef.WorkflowInputBinding(name="source", source="source"),),
            ),
        ),
    )
    profile = ef.ProfileSpec(
        family="nulls_types",
        features=(ef.ProfileFeature(name="rows", metric="log_filas", table="result"),),
    )
    source_file = root / "source.csv"
    source_file.write_bytes(b"id\n1\n1\n2\n")
    return {
        "column": column,
        "contract": contract,
        "data": data,
        "source": source,
        "registry": registry,
        "execution_plan": execution_plan,
        "execution": execution,
        "migration": migration,
        "workflow": workflow,
        "profile": profile,
        "source_file": source_file,
    }


def arguments(owner, fixture):
    f = fixture
    return {
        "execute": {
            "plan": f["execution_plan"],
            "source": f["source"],
            "registry": f["registry"],
        },
        "run_pipeline": {
            "spec": ef.PipelineSpec(execution=f["execution_plan"]),
            "source": f["source"],
            "registry": f["registry"],
        },
        "compare": {
            "left": ef.ArrowInput(f["data"]),
            "right": ef.ArrowInput(f["data"]),
            "contract": f["contract"],
        },
        "diff": {
            "candidate": f["data"],
            "expected": f["data"],
            "contract": f["contract"],
        },
        "migrate": {"spec": f["migration"], "source": f["source"]},
        "verify": {
            "outputs": {"owned": f["execution"]},
            "contract": f["contract"],
            "snapshots": {t.name: t.data for t in f["execution"].inputs},
            "policy": ef.ComparisonPolicy(
                index="ignore",
                justification="Fixture RangeIndex is transport metadata; id is explicit",
            ),
        },
        "evaluate_rules": {"execution": f["execution"]},
        "profile_execution": {"execution": f["execution"], "spec": f["profile"]},
        "reduce_case": {
            "inputs": {"source": ef.ArrowInput(f["data"])},
            "predicate": lambda tables: ef.ReductionObservation(
                preconditions="satisfied", failure_signature="owned"
            ),
            "predicate_version": "controlled-fixture-v1",
            "failure_signature": "owned",
        },
        "run_workflow": {"spec": f["workflow"], "source": f["source"]},
        "ingest_file": {
            "path": f["source_file"],
            "spec": ef.IngestionSpec(
                format="csv",
                fields=(ef.FieldMapping(column=f["column"], path=("id",)),),
            ),
        },
        "capture_duckdb": {"sql": "SELECT id FROM (VALUES (1),(1),(2)) AS t(id)"},
        "ParquetDestination": {},
    }[owner]


def observed(owner, result, fixture):
    if owner == "execute":
        return {
            "state": result.state,
            "rows": ef.read_table(result.output.data).to_pylist()
            if result.output is not None
            else None,
        }
    if owner == "run_pipeline":
        return {
            "complete": result.complete,
            "execution": result.execution.state
            if result.execution is not None
            else None,
            "rows": ef.read_table(result.execution.output.data).to_pylist()
            if result.execution is not None and result.execution.output is not None
            else None,
        }
    if owner in {"compare", "diff"}:
        return {
            "complete": result.complete,
            "state": result.state,
            "differences": result.counts.difference_records,
        }
    if owner == "migrate":
        source = result.source.execution if result.source is not None else None
        target = result.target.execution if result.target is not None else None
        return {
            "complete": result.complete,
            "state": result.state,
            "source": ef.read_table(source.output.data).to_pylist()
            if source is not None and source.output is not None
            else None,
            "target": ef.read_table(target.output.data).to_pylist()
            if target is not None and target.output is not None
            else None,
        }
    if owner == "verify":
        return {
            "operational_state": result.operational_state,
            "technical": [check.state for check in result.technical_outcomes],
        }
    if owner == "evaluate_rules":
        return {"complete": result.complete, "decision": result.decision}
    if owner == "profile_execution":
        return {
            "complete": result.complete,
            "values": [o.value for o in result.vector.observations],
        }
    if owner == "reduce_case":
        return {
            "status": result.status,
            "baseline_verified": result.baseline_verified,
            "retained": list(result.tables[0].retained_positions),
        }
    if owner == "run_workflow":
        return {
            "complete": result.complete,
            "rows": ef.read_table(result.outputs["one"]).to_pylist(),
            "states": [c.state for c in result.checkpoints],
        }
    if owner == "ingest_file":
        return {
            "state": result.state,
            "accepted": result.accepted_records,
            "rows": ef.read_table(result.output).to_pylist()
            if result.output is not None
            else None,
            "source_unchanged": fixture["source_file"].read_bytes() == b"id\n1\n1\n2\n",
        }
    if owner == "capture_duckdb":
        return {
            "count": result.row_count,
            "rows": ef.read_table(result.data).to_pylist(),
        }
    return {"current": result.current()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--exclude-covered", type=Path, required=True)
    parser.add_argument("--exclude-covered-sha256", required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(sys.flags.isolated, "Isolated installed interpreter required")
    reader = helper("owned_native_inputs", ROOT / "tools/revalidate_root_contexts.py")
    raw, baseline = reader.bounded_json(args.baseline)
    require(
        hashlib.sha256(raw).hexdigest() == args.baseline_sha256,
        "Baseline identity differs",
    )
    require(
        baseline["candidate"] == ef.__version__ == "0.12.0a14"
        and baseline["total"] == 8438
        and baseline["optimized"] is (not __debug__),
        "Full A14 baseline and matching mode required",
    )
    raw, exclusion = reader.bounded_json(args.exclude_covered)
    require(
        hashlib.sha256(raw).hexdigest() == args.exclude_covered_sha256
        and exclusion["total"] == 9142,
        "Exclusion scope identity differs",
    )
    covered = {r["id"] for r in exclusion["rows"] if r["status"] != "NOT_RUN"}
    # Prior IDs delimit new work only. No prior count is credited to this wheel.
    pending = {r["id"] for r in baseline["rows"] if r["status"] == "NOT_RUN"} - covered
    _, binding = reader.bounded_json(args.binding)
    require(
        binding["wheel_sha256"] == baseline["wheel_sha256"],
        "Binding and baseline differ",
    )
    helper(
        "owned_native_binding", ROOT / "packages/equiframe/tools/compatibility_probe.py"
    ).runtime_binding(binding)
    reader.require_ordinary_parents(args.output.absolute().parent)
    require(
        not args.output.exists() and not args.output.absolute().is_relative_to(ROOT),
        "New private output required",
    )
    planned = plan(pending)
    ids = [i for case in planned["cases"] for i in case["obligations"]]
    require(
        len(ids) == len(set(ids)) and set(ids) <= pending,
        "Overlapping or unplanned obligation",
    )
    args.output.mkdir()
    frozen = (json.dumps(planned, indent=2, allow_nan=False) + "\n").encode()
    (args.output / "catalog.json").write_bytes(frozen)
    fixture = setup(args.output.absolute() / "inputs")
    receipts = []
    initial_cwd = Path.cwd()
    for position, case in enumerate(planned["cases"]):
        owner = case["owner"]
        directory = args.output.absolute() / f"case-{position:03}"
        directory.mkdir()
        kwargs = arguments(owner, fixture)
        keyword = "root" if owner == "ParquetDestination" else "work_dir"
        variant = case["variant"]
        if variant != "default_root":
            kwargs[keyword] = (
                0
                if variant == "wrong_zero_root"
                else {"wrong": 1}
                if variant == "wrong_mapping_root"
                else None
                if variant == "none_root"
                else directory / "operation"
            )
        kwargs.update({name: None for name in case["none_parameters"]})
        observation = error = None
        try:
            os.chdir(directory)
            result = getattr(ef, owner)(**kwargs)
            observation = observed(owner, result, fixture)
            status = "PASS" if observation == case.get("expected") else "FAIL"
        except TypeError as failure:
            error = type(failure).__name__
            status = (
                "EXPECTED_REJECTION"
                if error == case.get("expected_error") and not list(directory.iterdir())
                else "FAIL"
            )
        except (
            ValueError,
            OSError,
            ef.EquiFrameError,
            AttributeError,
            KeyError,
            RuntimeError,
        ) as failure:
            error = type(failure).__name__
            status = "FAIL"
        finally:
            os.chdir(initial_cwd)
        receipts.append(
            {
                "case_id": case["id"],
                "status": status,
                "observed": observation,
                "error": error,
                "obligations": case["obligations"],
            }
        )
    require(
        (args.output / "catalog.json").read_bytes() == frozen,
        "Expected catalogue changed",
    )
    result = {
        "source_commit": baseline["source_commit"],
        "wheel_sha256": baseline["wheel_sha256"],
        "optimized": not __debug__,
        "baseline_sha256": args.baseline_sha256,
        "exclusion_scope_sha256": args.exclude_covered_sha256,
        "historical_counts_imported": False,
        "catalog_sha256": hashlib.sha256(frozen).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": dict(Counter(r["status"] for r in receipts)),
        "receipts": receipts,
        "scientific_credit": False,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"counts": result["counts"], "obligations": len(ids)}))
    return int(bool(result["counts"].get("FAIL")))


if __name__ == "__main__":
    raise SystemExit(main())
