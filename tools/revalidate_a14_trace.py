"""Re-execute frozen literal cases; never import historical pass counts."""

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--wheel", type=Path, required=True)
parser.add_argument("--sha256", required=True)
parser.add_argument("--commit", required=True)
args = parser.parse_args()
ROOT = args.workspace.resolve()
REPO = Path(__file__).resolve().parents[1]
if args.output.exists() or args.output.resolve().is_relative_to(REPO):
    raise ValueError("Use a new private output directory outside the repository")

CATALOG_HASHES = {
    "revision_95_20261011/trace_inputs/catalog-a13.json": "9eaa56aa71b803d901b07b56da0a89eb3cb610a44dc67a78513b553288ab59e1",
    "metas_90_80_85_50_20261011/catalog-boundaries-v3.json": "d83a7389205852de4c10eb699885f83e6cfd892bef7116fb2a70ac750499b0fd",
    "metas_90_80_85_50_20261011/catalog-literal-fields-v1.json": "96a1d6a23aa138ab70513a80eb565334590965c15dce93d31481844263b75c50",
    "trace85_20261011/public-types-catalog.json": "f8f46b571775bb6f97f31415f2887aa775794358b3db79f3ea58c862dbc24822",
    "trace85_20261011/properties-catalog.json": "7cb93ec05d412d30a892d609de3f76b2416566d48bd016a6c70fb0a809f620ca",
    "trace85_20261011/seed-bounds-catalog.json": "bea5179a99e703ef579de13373d669551e8aedffcb82f9d50d99934737d5dc52",
    "trace85_20261011/model-default-catalog-v1.json": "364f0579e86384a270cbff0713ced281ecf2be721f0f833256b9b66ba33532a3",
    "metas_90_80_85_50_20261011/catalog-methods-v1.json": "bac7ffb2d41843b98767a1deb32bc76a57850617cc1f59d39db7e1725737801d",
    "trace85_20261011/context-constructor-catalog-v1.json": "56c4cb44a57e6d36cb01c28f4e1fc0b57032194ae8a3c70cea2e8211de8517fa",
    "trace85_20261011/exception-catalog-v1.json": "a708c50cd0750178b623c98d6871a31d5cb9d4574facb0b02d40113f0406ed7b",
    "trace85_20261011/cli-parser-catalog-v2.json": "847e207775d36e4bd6173e714120e2c4c7576183b6bf55620065846832dc223b",
}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if path.is_relative_to(ROOT):
        key = path.relative_to(ROOT).as_posix()
        if key in CATALOG_HASHES and sha(path) != CATALOG_HASHES[key]:
            raise ValueError("Frozen independent oracle catalog changed")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("Duplicate member")
            out[key] = value
        return out

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite")),
    )


import equiframe as ef

if ef.__version__ != "0.12.0a14":
    raise ValueError("A14 required")
source = REPO / "packages/equiframe/src/equiframe"
installed = Path(ef.__file__).resolve().parent
expected = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*.py")}
observed = {
    p.relative_to(installed).as_posix(): sha(p) for p in installed.rglob("*.py")
}
if any(observed.get(name) != digest for name, digest in expected.items()):
    raise ValueError("Installed Python payload differs from current source")
wheel = args.wheel.resolve()
if sha(wheel) != args.sha256:
    raise ValueError("Previously built private wheel changed")
with zipfile.ZipFile(wheel) as archive:
    payload = {
        n.removeprefix("equiframe/"): hashlib.sha256(archive.read(n)).hexdigest()
        for n in archive.namelist()
        if n.startswith("equiframe/") and n.endswith(".py")
    }
if observed != payload:
    raise ValueError("Installed inventory differs from previously identified wheel")
trace = module("trace", REPO / "packages/equiframe/tools/option_trace.py")
boundary = module("boundary", REPO / "tools/option_boundary_followup.py")
fields = module("literal_fields", REPO / "tools/option_literal_field_followup.py")
types = module("types", REPO / "tools/option_public_types_followup.py")
properties = module("properties", REPO / "tools/option_properties_followup.py")
seed_bounds = module("seed_bounds", REPO / "tools/option_seed_bounds_followup.py")
defaults = module("defaults", REPO / "tools/option_model_default_followup.py")
methods = module("methods", REPO / "tools/option_method_followup.py")
contexts = module("contexts", REPO / "tools/option_context_constructor_followup.py")
exceptions = module("exceptions", REPO / "tools/option_exception_followup.py")
parser_cases = module("parser_cases", REPO / "tools/option_cli_parser_followup.py")
discovery = module("discovery", REPO / "packages/equiframe/tools/option_inventory.py")
original = ROOT / "revision_95_20261011/trace_inputs/catalog-a13.json"
catalog = read(original)
if sha(original) != "9eaa56aa71b803d901b07b56da0a89eb3cb610a44dc67a78513b553288ab59e1":
    raise ValueError("Original oracle catalog changed")
rows = read(ROOT / "revision_95_20261011/trace_inputs/matrix.json")["rows"]
trace.validate_catalog(catalog, rows)
fresh_inventory = {
    "environment": {"python": sys.version, "executable": sys.executable},
    "commit": args.commit,
    "wheel_sha256": sha(wheel),
    "exports": discovery.inspect_exports(ef, {}),
    "cli": discovery.inspect_cli("equiframe.cli", "equiframe"),
    "distributions": [discovery.installed_identity(ef, "equiframe", wheel)],
}
fresh_rows = discovery.obligations(fresh_inventory)
before = {r["id"] for r in rows}
after = {r["id"] for r in fresh_rows}
if not before <= after or len(before) != 8385 or len(after) != 8438:
    raise ValueError("Unexpected A14 surface evolution")
added = sorted(after - before)
rows = fresh_rows
adaptations = []
for case in catalog["cases"]:
    if case["id"] == "DetectorVersions.equiframe.default":
        if case["expected"] != "0.12.0a13":
            raise ValueError("Unexpected historical version oracle")
        case["expected"] = "0.12.0a14"
        case["basis"] = (
            "Explicit A14 release identity; only this default is updated from the frozen A13 oracle."
        )
        adaptations.append(
            {
                "case_id": case["id"],
                "member": "expected",
                "old": "0.12.0a13",
                "new": "0.12.0a14",
            }
        )
receipts = []
catalogs = {str(original.relative_to(ROOT)): sha(original)}
for case in catalog["cases"]:
    receipts.append(trace.execute_case(case, catalog["seeds"], ef))
for name, executor in [
    ("metas_90_80_85_50_20261011/catalog-boundaries-v3.json", boundary.execute),
    ("metas_90_80_85_50_20261011/catalog-literal-fields-v1.json", fields.execute),
    ("trace85_20261011/public-types-catalog.json", types.execute),
    ("trace85_20261011/properties-catalog.json", properties.execute),
    ("trace85_20261011/seed-bounds-catalog.json", seed_bounds.execute),
]:
    path = ROOT / name
    catalogs[name] = sha(path)
    for case in read(path)["cases"]:
        if (
            name.endswith("public-types-catalog.json")
            and case["case_id"] == "public-constant.__version__"
        ):
            if case["expected"] != "0.12.0a13":
                raise ValueError("Unexpected historical version constant oracle")
            case["expected"] = "0.12.0a14"
            case["basis"] = (
                "Explicit A14 release constant; no behavioral oracle changed."
            )
            adaptations.append(
                {
                    "case_id": case["case_id"],
                    "member": "expected",
                    "old": "0.12.0a13",
                    "new": "0.12.0a14",
                }
            )
        receipts.append(executor(case, ef))
path = ROOT / "trace85_20261011/model-default-catalog-v1.json"
catalogs[str(path.relative_to(ROOT))] = sha(path)
for case in read(path)["cases"]:
    receipts.append(defaults.execute(case))
receipts.append(
    trace.execute_case(
        {
            "id": "a14.DetectorVersions.equiframe.finite",
            "model": "DetectorVersions",
            "operation": "finite",
            "field": "equiframe",
            "value": "0.12.0a14",
            "expected": "0.12.0a14",
            "obligations": [
                'field:equiframe.DetectorVersions:equiframe:value:"0.12.0a14"'
            ],
            "basis": "A14 is now an explicitly admitted release identity; expected value fixed before invocation.",
        },
        catalog["seeds"],
        ef,
    )
)
path = ROOT / "metas_90_80_85_50_20261011/catalog-methods-v1.json"
catalogs[str(path.relative_to(ROOT))] = sha(path)
for case in read(path)["cases"]:
    for declaration in case["methods"]:
        if declaration["id"] == "method:equiframe.ColumnSpec.compatible_policies":
            old = "d11f78e30a7b54e9b1ff058d1caaaabc1a9d1dc18a8e98d57f7626a60b69dc7d"
            new = "c2c9b88f6202dd94d9cc8ead2ac067c55f1d01f4472a5e5f58e145a9db91a930"
            if declaration["source_sha256"] != old:
                raise ValueError("Unexpected historical method fingerprint")
            declaration["source_sha256"] = new
            adaptations.append(
                {
                    "case_id": case["case_id"],
                    "member": declaration["id"],
                    "old": old,
                    "new": new,
                    "reason": "Explicit assert-to-active-guard source update; whole literal return oracle preserved.",
                }
            )
    receipts.append(methods.execute(case, ef))
run_root = args.output.resolve()
run_root.mkdir(parents=True, exist_ok=False)
path = ROOT / "trace85_20261011/context-constructor-catalog-v1.json"
catalogs[str(path.relative_to(ROOT))] = sha(path)
context_catalog = read(path)
refs = contexts.fixtures(context_catalog, run_root / "contexts")
for case in context_catalog["cases"]:
    receipts.append(contexts.execute(case, refs))
path = ROOT / "trace85_20261011/exception-catalog-v1.json"
catalogs[str(path.relative_to(ROOT))] = sha(path)
exception_catalog = read(path)
refs = exceptions.fixtures(exception_catalog)
for case in exception_catalog["cases"]:
    receipts.append(exceptions.execute(case, refs))
path = ROOT / "trace85_20261011/cli-parser-catalog-v2.json"
catalogs[str(path.relative_to(ROOT))] = sha(path)
from equiframe.cli import app
from typer.main import get_command
from typer.testing import CliRunner

fixture = run_root / "existing.json"
fixture.write_text("{}\n", encoding="utf-8")
tree = get_command(app)
for case in read(path)["cases"]:
    receipts.append(
        parser_cases.execute(
            case, app, tree, CliRunner(), {"@file": fixture, "@directory": run_root}
        )
    )
extra_parser_plan = parser_cases.plan(fresh_inventory, set(added), tree)
for case in extra_parser_plan["cases"]:
    receipts.append(
        parser_cases.execute(
            case, app, tree, CliRunner(), {"@file": fixture, "@directory": run_root}
        )
    )
if {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*.py")} != expected:
    raise ValueError("Source changed during execution")
aggregate = trace.aggregate(rows, receipts)
receipt = {
    "schema": "equiframe.a14.contract-revalidation.v1",
    "source_commit": args.commit,
    "recorded_at_utc": datetime.now(UTC).isoformat(),
    "candidate": ef.__version__,
    "python": sys.version,
    "wheel_sha256": sha(wheel),
    "installed_python_modules": len(observed),
    "optimized": not __debug__,
    "source_sha256": expected,
    "installed_python_payload_equals_current_source": True,
    "metadata_and_sdist_revalidated": False,
    "historical_counts_imported": False,
    "oracle_adaptations": adaptations,
    "frozen_obligations_preserved": len(before),
    "added_a14_obligations": added,
    "fresh_surface_total": len(after),
    "catalog_sha256": catalogs,
    "tool_sha256": sha(Path(__file__)),
    "receipts": receipts,
    **aggregate,
    "scope": "Explicit literal model/field/alias/getter/default/method, constructor context, exception and CLI-parser contracts. No complete native command, missing case, scientific acceptance or entire A14 score inferred.",
}
target = run_root / "result.json"
with target.open("x", encoding="utf-8") as stream:
    json.dump(receipt, stream, ensure_ascii=True, indent=2, allow_nan=False)
print(
    json.dumps(
        {
            "receipt": str(target),
            "cases": len(receipts),
            "case_counts": dict(Counter(r["status"] for r in receipts)),
            "all_executed_contracts_match": all(
                r["status"] != "FAIL" for r in receipts
            ),
            "obligation_counts": aggregate["counts"],
            "verified": aggregate["verified"],
            "failures": [r["case_id"] for r in receipts if r["status"] == "FAIL"],
        }
    )
)
