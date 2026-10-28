"""Isolated, public-API consumer of an exact installed EquiFrame wheel.

Executed by verify_compatibility.py with the selected virtualenv's Python -I.
No checkout imports, editable install, private API, or replacement dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import stat
import sys
from pathlib import Path
from typing import Any

OPTIONAL = ("pyarrow", "pandas", "polars", "duckdb", "numpy", "sklearn")


def check_runtime_files(package: Path, expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare the entire regular installed package payload to the wheel."""
    if package.is_symlink() or not package.is_dir():
        raise ValueError("runtime package must be a regular directory")
    found: dict[str, dict[str, Any]] = {}
    for path in package.rglob("*"):
        if path.is_symlink():
            raise ValueError("runtime symlink: " + str(path))
        if path.is_dir():
            continue
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("runtime file is not regular: " + str(path))
        relative = "equiframe/" + path.relative_to(package).as_posix()
        if "__pycache__" in path.relative_to(package).parts and path.suffix == ".pyc":
            continue
        raw = path.read_bytes()
        found[relative] = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    if found != expected:
        raise ValueError("runtime payload differs from exact wheel bytes")
    return {"verified": True, "files": found, "root": str(package.resolve())}


def runtime_binding(manifest: dict[str, Any]) -> dict[str, Any]:
    spec = importlib.util.find_spec("equiframe")
    if spec is None or spec.origin is None or spec.submodule_search_locations is None:
        raise ValueError("equiframe is not an installed regular package")
    origin = Path(spec.origin)
    root = origin.parent
    if origin.is_symlink() or not root.resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("equiframe import is outside the clean virtualenv")
    checkout = Path(manifest["checkout"]).resolve()
    if Path.cwd().resolve().is_relative_to(checkout):
        raise ValueError("consumer cwd is inside checkout")
    if any(Path(entry).resolve().is_relative_to(checkout) for entry in sys.path if entry):
        raise ValueError("checkout is present on interpreter search path")
    result = check_runtime_files(root, manifest["runtime_files"])
    import equiframe as ef

    if Path(ef.__file__).resolve() != origin.resolve() or [
        Path(entry).resolve() for entry in ef.__path__
    ] != [root.resolve()]:
        raise ValueError("equiframe changed package location while importing")
    if (
        ef.__version__ != manifest["version"]
        or importlib.metadata.version("equiframe") != (manifest["version"])
    ):
        raise ValueError("installed distribution version differs from wheel")
    if any(name in sys.modules for name in OPTIONAL):
        raise ValueError("base import eagerly loaded an optional runtime")
    result.update(
        origin=str(origin.resolve()),
        python=sys.version,
        executable=sys.executable,
        prefix=sys.prefix,
        platform=platform.platform(),
        machine=platform.machine(),
        isolated=bool(sys.flags.isolated),
        versions={
            distribution.metadata["Name"].lower().replace("_", "-"): distribution.version
            for distribution in importlib.metadata.distributions()
        },
    )
    if not sys.flags.isolated:
        raise ValueError("consumer must run with Python -I")
    return result


def profile_availability(profile: str) -> dict[str, bool]:
    expected = {
        "pyarrow": profile not in ("base", "ml"),
        "pandas": profile in ("pandas", "engines", "all"),
        "polars": profile in ("polars", "engines", "all"),
        "duckdb": profile in ("duckdb", "engines", "all"),
        "sklearn": profile in ("ml", "all"),
    }
    actual = {name: importlib.util.find_spec(name) is not None for name in expected}
    if actual != expected:
        raise ValueError(f"profile {profile} does not provide its exact optional extras: {actual}")
    if profile == "base" and importlib.util.find_spec("numpy") is not None:
        raise ValueError("base installed an unexpected NumPy dependency")
    if profile in ("ml", "all") and importlib.util.find_spec("numpy") is None:
        raise ValueError("ML profile is missing NumPy")
    return actual


def base_api(source: Path, output: Path, *, arrow: bool) -> list[str]:
    import equiframe as ef

    policy = ef.get_compatibility_policy()
    register = ef.get_stability_register()
    adapters = ef.get_adapter_capabilities()
    if ef.CompatibilityPolicy.model_validate_json(policy.model_dump_json()) != policy:
        raise ValueError("compatibility policy public roundtrip failed")
    classified = {(record.surface, record.name) for record in register}
    if (
        len(classified) != len(register)
        or not {
            ("api", "equiframe.get_compatibility_policy"),
            ("api", "equiframe.get_stability_register"),
            ("api", "equiframe.get_adapter_capabilities"),
        }
        <= classified
    ):
        raise ValueError("stability register is incomplete or ambiguous")
    if {adapter.adapter for adapter in adapters} != {"arrow", "pandas", "polars", "duckdb"}:
        raise ValueError("public adapter capability register is incomplete")
    for adapter in adapters:
        if ef.AdapterCapability.model_validate_json(adapter.model_dump_json()) != adapter:
            raise ValueError("adapter capability public roundtrip failed")
        if {stage.stage for stage in adapter.stages} != {
            "capture",
            "comparison",
            "native_execution",
            "migration",
        }:
            raise ValueError("adapter stage distinctions were lost")
    if any(name in sys.modules for name in OPTIONAL):
        raise ValueError("compatibility getters eagerly loaded an optional runtime")
    count = 0
    for fixture in sorted((source / "examples").glob("*.json")):
        contract = ef.read_contract(fixture)
        raw = ef.canonical_contract_bytes(contract)
        restored = ef.validate_contract(raw)
        if restored != contract or ef.contract_fingerprint(restored) != ef.contract_fingerprint(
            contract
        ):
            raise ValueError("contract public roundtrip failed")
        count += 1
    if count < 5:
        raise ValueError("sdist lacks the five public contract fixtures")
    try:
        ef.validate_contract({"schema_version": "unsupported"})
    except ef.ContractValidationError:
        pass
    else:
        raise ValueError("invalid contract was accepted")
    component = ef.combine_decisions(
        ef.ComponentDecision(decision="not_evaluable", complete=False, reason="not supplied"),
        ef.ComponentDecision(decision="no_alert", complete=True),
    )
    if component.result.decision != "not_evaluable":
        raise ValueError("unavailable component was converted into no alert")
    if not arrow:
        path = output / "missing-arrow.arrow"
        path.write_bytes(b"synthetic missing-optional-dependency input")
        ref = ef.LocalArtifactStore(output / "artifacts").put(
            path, media_type="application/vnd.apache.arrow.file"
        )
        try:
            ef.read_table(ref)
        except ef.MissingDependencyError:
            pass
        else:
            raise ValueError("missing Arrow did not fail safely")
    return [
        "compatibility_policy",
        "stability_register",
        "adapter_capabilities",
        "contract_roundtrip",
        "invalid_contract_rejected",
        "unavailable_component_preserved",
    ]


def tabular_api(output: Path) -> list[str]:
    import pyarrow as pa

    import equiframe as ef

    expected = pa.table({"id": [1, 2], "quantity": [10, 20]})
    cases = (
        ("equivalent", expected, 100),
        ("different", pa.table({"id": [1, 2], "quantity": [10, 21]}), 100),
        ("not_evaluable", expected, 1),
    )
    verified: list[str] = []
    for state, candidate, max_rows in cases:
        private = output / ("api-" + state)
        result = ef.diff(
            candidate,
            expected,
            keys=["id"],
            options=ef.ComparisonOptions(max_rows=max_rows),
            work_dir=private,
        )
        if result.state != state:
            raise ValueError(f"API verdict {result.state} differs from expected {state}")
        decision = ef.equivalence_decision(
            result,
            policy=ef.EquivalencePolicy(require_persisted_evidence=True),
            evidence_root=private,
        )
        if decision.accepted != (state == "equivalent") or decision.evidence_status != "verified":
            raise ValueError("API assertion decision or persisted evidence check failed")
        try:
            ef.assert_equivalent(result)
        except ef.EquivalenceAssertionError as error:
            if state == "equivalent" or error.code != state:
                raise
        else:
            if state != "equivalent":
                raise ValueError("non-equivalence passed assertion")
        try:
            bool(result)
        except TypeError:
            pass
        else:
            raise ValueError("ComparisonResult incorrectly supports truth testing")
        report = ef.comparison_report(result)
        if not report.to_text() or not report.to_html():
            raise ValueError("public report is empty")
        verified.append(state)
    cli = output / "cli"
    cli.mkdir()
    (cli / "spec.json").write_text(result.spec.model_dump_json(), "utf-8")
    tables = {
        "expected": expected,
        "different": pa.table({"id": [1, 2], "quantity": [10, 21]}),
        "invalid-reference": pa.table({"id": [1, 1], "quantity": [10, 20]}),
    }
    for name, table in tables.items():
        with (
            (cli / (name + ".arrow")).open("wb") as stream,
            pa.ipc.new_file(stream, table.schema) as writer,
        ):
            writer.write_table(table)
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--binding-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text("utf-8"))
    result = runtime_binding(manifest)
    result["extras"] = profile_availability(args.profile)
    if not args.binding_only:
        if args.source is None:
            raise ValueError("public API probes require the extracted sdist source")
        probes = args.output.parent / "public-api"
        probes.mkdir()
        result["base_api"] = base_api(args.source, probes, arrow=result["extras"]["pyarrow"])
        if result["extras"]["pyarrow"]:
            result["tabular_api"] = tabular_api(probes)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps({"verified": True, "profile": args.profile, "output": str(args.output)}))


if __name__ == "__main__":
    main()
