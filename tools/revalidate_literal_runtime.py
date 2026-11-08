"""Replay original literal semantic tests against an exact installed A14 wheel.

The original tests, helpers and expectations remain byte-for-byte bound to the
A13 source archive. This extends the list of reviewed complete return contracts;
an import, frame hit, passing suite or non-estimable return earns no coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SHA = "556a3534dcc204c16742fe30ca32843438cb46782e91bb566054a2a0d32014d3"
EXTRA_APIS = {
    "equiframe.validate_contract",
    "equiframe.canonical_contract_bytes",
    "equiframe.contract_fingerprint",
    "equiframe.read_diff_contract",
    "equiframe.get_adapter_capabilities",
    "equiframe.get_stability_register",
    "equiframe.fit_preprocessor",
    "equiframe.read_preprocessor",
    "equiframe.transform_profiles",
    "equiframe.fit_detectors",
    "equiframe.calibrate_detectors",
    "equiframe.score_detectors",
    "equiframe.detect",
    "equiframe.detect_component",
    "equiframe.read_detector_bundle",
    "equiframe.read_profile",
    "equiframe.profile_execution",
    "equiframe.read_pipeline",
    "equiframe.run_pipeline",
    "equiframe.read_rule_evaluation",
    "equiframe.comparison_report",
    "equiframe.read_comparison_report",
    "equiframe.equivalence_decision",
    "equiframe.combine_decisions",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "Owned verifier unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configured_verifier():
    verifier = helper(
        "owned_original_literal", ROOT / "tools/option_test_calls_followup.py"
    )
    original_complete = verifier.complete_return

    def complete(api, value):
        if api not in EXTRA_APIS:
            return original_complete(api, value)
        if value is None:
            return False
        if api in {"equiframe.validate_contract", "equiframe.read_diff_contract"}:
            # Validated metadata only, not runtime or scientific evidence.
            return True
        if api == "equiframe.canonical_contract_bytes":
            return isinstance(value, bytes) and bool(value)
        if api == "equiframe.contract_fingerprint":
            return (
                isinstance(value, str)
                and len(value) == 64
                and all(c in "0123456789abcdef" for c in value)
            )
        if api in {
            "equiframe.get_adapter_capabilities",
            "equiframe.get_stability_register",
        }:
            return isinstance(value, tuple) and bool(value)
        if api in {"equiframe.fit_preprocessor", "equiframe.read_preprocessor"}:
            return value.state == "ready"
        if api == "equiframe.transform_profiles":
            return bool(value.values) and bool(value.columns)
        if api == "equiframe.fit_detectors":
            return (
                value.preprocessor.state == "ready"
                and value.m.state == value.b.state == "fitted"
            )
        if api in {"equiframe.calibrate_detectors", "equiframe.read_detector_bundle"}:
            return (
                value.fit.preprocessor.state == "ready"
                and value.m.state == value.b.state == "ready"
            )
        if api == "equiframe.score_detectors":
            return value.rows > 0 and value.m.state == value.b.state == "scored"
        if api == "equiframe.detect":
            return value.scores.rows > 0 and all(
                d.result.complete for d in (*value.m, *value.b)
            )
        if api == "equiframe.detect_component":
            return (
                value.rows > 0
                and value.scores.state == "scored"
                and all(d.result.complete for d in value.decisions)
            )
        if api in {"equiframe.comparison_report", "equiframe.read_comparison_report"}:
            return value.complete and value.evidence.acceptance == "satisfied"
        if api == "equiframe.equivalence_decision":
            return value.accepted and value.complete
        if api == "equiframe.combine_decisions":
            return value.complete
        if api in {"equiframe.run_pipeline", "equiframe.read_pipeline"}:
            return (
                value.complete
                and value.execution is not None
                and value.execution.state == "completed"
            )
        return value.complete

    verifier.ALLOWED_APIS |= EXTRA_APIS
    verifier.complete_return = complete
    return verifier


def original_fixture(verifier, tests, workspace):
    """Bind all original files, including owned tools loaded indirectly by tests."""
    archive = (
        workspace
        / "respaldo_equiframe_20261010/distribuciones-final-a13/equiframe-0.12.0a13.tar.gz"
    )
    require(
        verifier.op.digest(archive)
        == "164b70270344343094dc0a688bf8dbfe20a27112f7227e2f7fe318f085b71935",
        "Original source archive differs",
    )
    files = {}
    total = 0
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            if member.isdir():
                continue
            parts = Path(member.name).parts
            require(
                member.isfile()
                and len(parts) >= 2
                and not Path(member.name).is_absolute()
                and ".." not in parts
                and member.size <= 64 * 1024**2,
                "Invalid original fixture member",
            )
            relative = Path(*parts[1:])
            path = tests.parent / relative
            require(
                path.is_file() and not path.is_symlink(),
                "Original fixture file missing",
            )
            total += member.size
            require(
                len(files) < 20000 and total <= 1024**3,
                "Original fixture budget exceeded",
            )
            with source.extractfile(member) as stream:
                expected = stream.read(member.size + 1)
            require(path.read_bytes() == expected, "Original helper differs")
            files[relative.as_posix()] = {
                "sha256": hashlib.sha256(expected).hexdigest(),
                "size_bytes": member.size,
            }
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "workspace",
        "inventory",
        "tests",
        "baseline",
        "exclude-covered",
        "binding",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--exclude-covered-sha256", required=True)
    args = parser.parse_args()
    require(sys.flags.isolated, "Isolated installed interpreter required")
    reader = helper("owned_literal_inputs", ROOT / "tools/revalidate_root_contexts.py")
    raw, inventory = reader.bounded_json(args.inventory)
    require(
        hashlib.sha256(raw).hexdigest() == INVENTORY_SHA, "Frozen inventory differs"
    )
    raw, baseline = reader.bounded_json(args.baseline)
    require(
        hashlib.sha256(raw).hexdigest() == args.baseline_sha256
        and baseline["total"] == 8438
        and baseline["optimized"] is (not __debug__),
        "A14 baseline or mode differs",
    )
    raw, exclusion = reader.bounded_json(args.exclude_covered)
    require(
        hashlib.sha256(raw).hexdigest() == args.exclude_covered_sha256
        and exclusion["total"] == 9142,
        "Exclusion scope differs",
    )
    covered = {r["id"] for r in exclusion["rows"] if r["status"] != "NOT_RUN"}
    pending = {r["id"] for r in baseline["rows"] if r["status"] == "NOT_RUN"} - covered
    _, binding = reader.bounded_json(args.binding)
    require(
        binding["wheel_sha256"] == baseline["wheel_sha256"],
        "Binding differs from baseline",
    )
    helper(
        "owned_literal_binding",
        ROOT / "packages/equiframe/tools/compatibility_probe.py",
    ).runtime_binding(binding)
    import equiframe as ef

    require(ef.__version__ == baseline["candidate"] == "0.12.0a14", "A14 required")
    reader.require_ordinary_parents(args.output.absolute().parent)
    require(
        not args.output.exists() and not args.output.absolute().is_relative_to(ROOT),
        "New private output required",
    )
    verifier = configured_verifier()
    catalog = verifier.plan(args.tests.absolute(), inventory, args.workspace.absolute())
    catalog["all_original_fixture_files"] = original_fixture(
        verifier, args.tests.absolute(), args.workspace.absolute()
    )
    catalog["complete_return_contracts"] = sorted(EXTRA_APIS)
    catalog["scope"] = (
        "Original literal semantic assertions; full original test and complete outcome required. No invalid-type or scientific coverage inferred."
    )
    require(catalog["cases"], "No qualifying literal test cases")
    tool_paths = [
        Path(__file__),
        ROOT / "tools/option_test_calls_followup.py",
        ROOT / "tools/option_operations.py",
        ROOT / "tools/revalidate_root_contexts.py",
        ROOT / "packages/equiframe/tools/compatibility_probe.py",
    ]
    tool_hashes = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tool_paths
    }
    args.output.mkdir()
    frozen = (json.dumps(catalog, indent=2, allow_nan=False) + "\n").encode()
    (args.output / "catalog.json").write_bytes(frozen)
    plugin = verifier.Calls(catalog, args.tests.absolute(), ef, pending)
    nodes = sorted(
        {str(args.tests.absolute() / r["test_node"]) for r in catalog["cases"]}
    )
    import pytest

    exit_code = int(
        pytest.main(
            [
                "--import-mode=prepend",
                "--assert=rewrite",
                "-q",
                "-x",
                "-o",
                "addopts=",
                "-o",
                "pythonpath=",
                "-p",
                "no:cacheprovider",
                "--basetemp=" + str(args.output.absolute() / "pytest-temp"),
                "--junitxml=" + str(args.output.absolute() / "tests.xml"),
                *nodes,
            ],
            plugins=[plugin],
        )
    )
    require(
        verifier.source_fixture(args.tests.absolute(), args.workspace.absolute())
        == catalog["source_fixture"],
        "Original helpers changed during execution",
    )
    require(
        original_fixture(verifier, args.tests.absolute(), args.workspace.absolute())
        == catalog["all_original_fixture_files"],
        "Original tools changed during execution",
    )
    require(
        all(
            hashlib.sha256(p.read_bytes()).hexdigest()
            == tool_hashes[p.relative_to(ROOT).as_posix()]
            for p in tool_paths
        ),
        "Execution tool changed",
    )
    require(
        (args.output / "catalog.json").read_bytes() == frozen,
        "Literal catalogue changed",
    )
    ids = set()
    for receipt in plugin.receipts:
        if exit_code:
            receipt["uncredited_obligations"] = receipt["obligations"]
            receipt["obligations"] = []
        if receipt["status"] in {"PASS", "EXPECTED_REJECTION"}:
            ids.update(receipt["obligations"])
    require(ids <= pending, "Unexpected obligation credit")
    result = {
        "source_commit": baseline["source_commit"],
        "wheel_sha256": baseline["wheel_sha256"],
        "optimized": not __debug__,
        "baseline_sha256": args.baseline_sha256,
        "exclusion_scope_sha256": args.exclude_covered_sha256,
        "historical_counts_imported": False,
        "catalog_sha256": hashlib.sha256(frozen).hexdigest(),
        "tool_sha256": tool_hashes[Path(__file__).relative_to(ROOT).as_posix()],
        "tool_hashes": tool_hashes,
        "pytest_exit_code": exit_code,
        "counts": dict(Counter(r["status"] for r in plugin.receipts)),
        "verified_obligations": sorted(ids),
        "receipts": plugin.receipts,
        "scientific_credit": False,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "pytest_exit_code": exit_code,
                "counts": result["counts"],
                "new_ids": len(ids),
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
